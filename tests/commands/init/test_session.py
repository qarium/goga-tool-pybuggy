"""Tests for the session module — pure builders, participation hooks, session seam.

Covers the kind-gated question block, the api/web/spec surveys, the pure builders, the
participation hooks, and the session seam.
"""

import importlib.metadata
import logging

import click
import goga_tool_pybuggy.commands.init.session as session_module
import pytest
import yaml
from goga.onboarding import FileGenerator, Question, Questionnaire, ToolParticipation
from goga_tool_pybuggy.commands.init import (
    amend_pybuggy_config,
    build_config_amendments,
    build_config_data,
    build_web_config_data,
    declare_pybuggy_session,
    parse_specs,
    pybuggy_questions,
    run_session,
    survey_api_options,
    survey_autonomy,
    survey_specs,
    survey_web_config,
)
from goga_tool_pybuggy.config import SpecEntry
from goga_tool_pybuggy.plugins import PluginConfigKeys, WebConfigKeys

_FIRST_SPEC = {
    "name": "shop",
    "type": "swagger",
    "location": "specs/shop.yaml",
    "git_url": "",
    "git_location": "",
    "git_ref": "",
}

_EXTRA_SPEC = {
    "name": "billing",
    "type": "openapi",
    "location": "specs/billing.yaml",
    "git_url": "https://git/b.git",
    "git_location": "specs/b.yaml",
    "git_ref": "",
}

# The survey_api_options output — the answered api scalar keys, Enter-skipped keys dropped.
_API_ANSWERS = {
    "base_url": "https://{{ HOST }}/api",
    "timeout": "30",
    "retries": "3",
    "assert_delay": "",
}

# The survey_web_config output — the five-key web minimum the payload builder maps.
_WEB_ANSWERS = {
    "provider": "openai",
    "generation_model": "g",
    "classification_model": "c",
    "browser_name": "chromium",
    "headless": True,
}

# The block answer view carrying the image inputs — the source of the Dockerfile amendments.
_IMAGE_ANSWERS = {
    **_API_ANSWERS,
    "base_image": "qarium/goga-python-3.13:2.0",
    "image": "shop-api:latest",
}

_SCALAR_MEMBERS = [
    member
    for member in PluginConfigKeys
    if member not in (PluginConfigKeys.BASE_URL, PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER)
]


class _ScriptedClick:
    """A ``click.prompt``/``click.confirm`` double answering from two FIFO queues.

    Sequence-strict: an unexpected or reordered ask fails the test at the exact prompt.

    Attributes:
        confirm_calls: The ``(prompt, default)`` confirm calls, in ask order.
        prompt_calls: The ``(text, default)`` prompt calls, in ask order.
    """

    def __init__(self, confirms: list[bool], prompts: list[tuple[str, object]]) -> None:
        """Build the double from the scripted answer queues.

        Args:
            confirms: The confirm answers, one per expected gate in ask order.
            prompts: The ``(prompt text, answer)`` pairs, one per expected ask in order.
        """
        self._confirms = list(confirms)
        self._prompts = list(prompts)
        self.confirm_calls: list[tuple[str, bool]] = []
        self.prompt_calls: list[tuple[str, object | None]] = []

    def confirm(self, prompt: str, default: bool = False, **_: object) -> bool:
        """Answer one confirm gate from the queue.

        Args:
            prompt: The gate text the survey asks.
            default: The offered default (recorded with the prompt — the pin of the gate default).
            **_: The remaining click kwargs (absorbed).

        Returns:
            The next scripted gate answer.
        """
        self.confirm_calls.append((prompt, default))
        return self._confirms.pop(0)

    def prompt(self, prompt: str, default: object = None, **_: object) -> object:
        """Answer one input ask from the queue, asserting the expected prompt text.

        Args:
            prompt: The prompt text the survey asks.
            default: The offered default (recorded, unused — the queue owns the answer).
            **_: The remaining click kwargs (the choice type, absorbed).

        Returns:
            The next scripted answer.
        """
        expected, answer = self._prompts.pop(0)

        assert prompt == expected, f"unexpected prompt {prompt!r} (expected {expected!r})"

        self.prompt_calls.append((prompt, default))
        return answer


def _scalar_prompts(answers: dict[str, object]) -> list[tuple[str, object]]:
    """Build the scripted scalar-prompt queue — the given answers, Enter for the rest.

    Args:
        answers: The answered scalar keys (the ``survey_api_options`` answers).

    Returns:
        The ``(prompt text, answer)`` pairs, one per scalar member in declaration order.
    """
    return [(session_module._SCALAR_PROMPTS[member], answers.get(member.value, "")) for member in _SCALAR_MEMBERS]


def _patch_scripted_click(monkeypatch: pytest.MonkeyPatch, scripted: _ScriptedClick) -> None:
    """Route ``click.prompt``/``click.confirm`` of the session module through the double.

    Args:
        monkeypatch: The test's monkeypatch.
        scripted: The scripted double answering the asks.
    """
    monkeypatch.setattr(session_module.click, "confirm", scripted.confirm)
    monkeypatch.setattr(session_module.click, "prompt", scripted.prompt)


class TestSessionBuildersContract:
    """Facade exposure and signature surface of the five pure builders."""

    def test_facade_exports_pure_builders(self):
        """All five pure builder routines are importable from the cell facade."""
        assert callable(pybuggy_questions)
        assert callable(build_config_data)
        assert callable(build_config_amendments)
        assert callable(build_web_config_data)
        assert callable(parse_specs)

    def test_module_no_longer_carries_survey_extra_specs(self):
        """The absorbed extra-specs survey is gone from the session module."""
        assert not hasattr(session_module, "survey_extra_specs")

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (pybuggy_questions, {"return": list[Question]}),
            (
                build_config_data,
                {
                    "answers": dict[str, object],
                    "specs": list[dict[str, object]],
                    "autonomous": dict[str, bool] | None,
                    "return": dict[str, object],
                },
            ),
            (build_config_amendments, {"answers": dict[str, object], "return": dict[str, object]}),
            (
                build_web_config_data,
                {
                    "web_answers": dict[str, object],
                    "autonomous": bool | None,
                    "return": dict[str, object],
                },
            ),
            (
                parse_specs,
                {
                    "spec_answers": dict[str, object],
                    "extra_specs": list[dict[str, object]] | None,
                    "return": dict[str, SpecEntry],
                },
            ),
        ],
    )
    def test_builder_signature_matches_contract(self, routine, expected):
        """Every builder carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected


class TestSessionParticipationContract:
    """Facade exposure and signature surface of the hooks, the surveys, and the session seam."""

    def test_facade_exports_participation_routines(self):
        """The two hooks, the four amend-moment surveys, and the session seam are importable."""
        assert callable(declare_pybuggy_session)
        assert callable(amend_pybuggy_config)
        assert callable(survey_api_options)
        assert callable(survey_specs)
        assert callable(survey_autonomy)
        assert callable(survey_web_config)
        assert callable(run_session)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (declare_pybuggy_session, {"context": object, "return": None}),
            (amend_pybuggy_config, {"context": object, "return": None}),
            (survey_api_options, {"return": dict[str, object]}),
            (survey_specs, {"return": list[dict[str, object]]}),
            (survey_autonomy, {"axes": tuple[str, ...], "return": dict[str, bool]}),
            (survey_web_config, {"return": dict[str, object]}),
            (run_session, {"return": int}),
        ],
    )
    def test_participation_signature_matches_contract(self, routine, expected):
        """Every participation routine carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected


class TestPybuggyQuestions:
    """The declarative question block — the kind choice and the two image inputs."""

    def test_pybuggy_questions_declares_kind_base_image_image(self, monkeypatch):
        """Exactly three records — the kind choice first, then the two image inputs."""
        monkeypatch.setattr(session_module, "resolve_project_name", lambda: "shop")

        items = pybuggy_questions()

        assert [item.id for item in items] == ["kind", "base_image", "image"]

        kind = items[0]
        assert kind.kind == "choice"
        assert kind.choices == ["api", "web", "both"]
        assert kind.default == "api"
        assert kind.prompt == "Test kind (api — API tests over specs, web — browser UI tests, both)"

        assert items[1].prompt.startswith("Base image (FROM)")
        assert items[1].default is not None
        assert items[2].prompt == "Built image name"
        assert items[2].default == "shop:latest"

        plugin_values = {member.value for member in PluginConfigKeys}
        assert {item.id for item in items} & plugin_values == set()
        assert all(isinstance(item, Question) for item in items)

    def test_pybuggy_questions_image_required_when_name_underivable(self, monkeypatch):
        """An underivable project name leaves the image input engine-required (default None)."""
        monkeypatch.setattr(session_module, "resolve_project_name", lambda: None)

        assert pybuggy_questions()[2].default is None

    def test_pybuggy_questions_base_image_hints_follow_runtime_tag(self):
        """The FROM prompt embeds the python-family hints completed with the running goga minor tag."""
        from goga.version import host_goga_version, minor_version

        base_image = pybuggy_questions()[1]
        tag = minor_version(host_goga_version())

        hints = [line.strip()[2:] for line in base_image.prompt.splitlines() if line.strip().startswith("- ")]
        assert hints == [f"{name}:{tag}" for name in session_module._BASE_IMAGE_NAMES]
        assert hints[0].startswith("qarium/goga-python-3.10:")
        assert base_image.default == hints[-1]


class TestSurveyApiOptions:
    """The api options survey — the required base URL, then the Enter-skippable scalars."""

    def test_survey_api_options_asks_base_url_then_scalars(self, monkeypatch):
        """base_url is asked first; Enter-skipped scalar keys drop from the returned mapping."""
        scripted = _ScriptedClick(
            confirms=[],
            prompts=[
                ("Base URL (Jinja2 template, required)", "https://api.example"),
                *_scalar_prompts({"timeout": "5"}),
            ],
        )
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_api_options() == {"base_url": "https://api.example", "timeout": "5"}
        assert scripted.prompt_calls[0][0] == "Base URL (Jinja2 template, required)"

    def test_survey_api_options_reasks_empty_base_url(self, monkeypatch):
        """An empty base URL entry re-asks with the (required) prompt suffix."""
        scripted = _ScriptedClick(
            confirms=[],
            prompts=[
                ("Base URL (Jinja2 template, required)", ""),
                ("Base URL (Jinja2 template, required) (required)", "https://api.example"),
                *_scalar_prompts({}),
            ],
        )
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_api_options() == {"base_url": "https://api.example"}

    def test_survey_api_options_forwards_cancelled_prompt(self, monkeypatch):
        """A cancelled prompt propagates — the survey never catches click.Abort."""

        def cancelled(prompt: str, **_: object) -> str:
            raise click.Abort

        monkeypatch.setattr(session_module.click, "prompt", cancelled)

        with pytest.raises(click.Abort):
            survey_api_options()


class TestSurveySpecs:
    """The specs survey — the first spec field by field, then the confirm-gated extras."""

    def test_survey_specs_first_spec_then_confirm_gate(self, monkeypatch):
        """The first spec is asked field by field; a declined confirm adds nothing."""
        scripted = _ScriptedClick(
            confirms=[False],
            prompts=[
                ("Spec name", "client"),
                ("Spec type", "swagger"),
                ("Spec location (path from project root)", ".specs/client.yaml"),
                ("Git URL (empty — no git source)", ""),
                ("Path inside the repository", ""),
                ("Git ref (branch/tag; empty — default branch)", ""),
            ],
        )
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_specs() == [
            {
                "name": "client",
                "type": "swagger",
                "location": ".specs/client.yaml",
                "git_url": "",
                "git_location": "",
                "git_ref": "",
            }
        ]
        assert scripted.confirm_calls == [("Add another spec?", False)]

    def test_survey_specs_loops_until_declined(self, monkeypatch):
        """The gate repeats after every accepted spec — the first spec stays first."""
        scripted = _ScriptedClick(
            confirms=[True, False],
            prompts=[
                ("Spec name", "shop"),
                ("Spec type", "swagger"),
                ("Spec location (path from project root)", "specs/shop.yaml"),
                ("Git URL (empty — no git source)", ""),
                ("Path inside the repository", ""),
                ("Git ref (branch/tag; empty — default branch)", ""),
                ("Spec name", "billing"),
                ("Spec type", "openapi"),
                ("Spec location (path from project root)", "specs/billing.yaml"),
                ("Git URL (empty — no git source)", "https://git/b.git"),
                ("Path inside the repository", "specs/b.yaml"),
                ("Git ref (branch/tag; empty — default branch)", ""),
            ],
        )
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_specs() == [dict(_FIRST_SPEC), dict(_EXTRA_SPEC)]
        assert scripted.confirm_calls == [("Add another spec?", False)] * 2

    def test_survey_specs_reasks_required_fields(self, monkeypatch):
        """Empty name and location entries re-ask with the (required) prompt suffix."""
        scripted = _ScriptedClick(
            confirms=[False],
            prompts=[
                ("Spec name", ""),
                ("Spec name (required)", "billing"),
                ("Spec type", "swagger"),
                ("Spec location (path from project root)", ""),
                ("Spec location (path from project root) (required)", "specs/b.yaml"),
                ("Git URL (empty — no git source)", ""),
                ("Path inside the repository", ""),
                ("Git ref (branch/tag; empty — default branch)", ""),
            ],
        )
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_specs() == [
            {
                "name": "billing",
                "type": "swagger",
                "location": "specs/b.yaml",
                "git_url": "",
                "git_location": "",
                "git_ref": "",
            }
        ]


class TestSurveyAutonomy:
    """The autonomy confirms — the closing questions of each amendment branch."""

    def test_survey_autonomy_asks_both_axes_in_order_with_disabled_defaults(self, monkeypatch):
        """One confirm per pipeline — automate first, patch after it — each defaulting to disabled."""
        scripted = _ScriptedClick(confirms=[False, False], prompts=[])
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_autonomy(session_module._AUTONOMY_AXES) == {"api.automate": False, "api.patch": False}
        assert scripted.confirm_calls == [
            ("Run the api.automate pipeline unattended (autonomous mode)?", False),
            ("Run the api.patch pipeline unattended (autonomous mode)?", False),
        ]

    def test_survey_autonomy_acceptance_enables_each_axis(self, monkeypatch):
        """Accepted confirms return True per axis — the enabling answers of the pipelines axis."""
        scripted = _ScriptedClick(confirms=[True, True], prompts=[])
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_autonomy(session_module._AUTONOMY_AXES) == {"api.automate": True, "api.patch": True}

    def test_survey_autonomy_answers_are_independent_per_axis(self, monkeypatch):
        """A mixed run — automate accepted, patch declined — records each axis separately."""
        scripted = _ScriptedClick(confirms=[True, False], prompts=[])
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_autonomy(session_module._AUTONOMY_AXES) == {"api.automate": True, "api.patch": False}

    def test_survey_autonomy_asks_the_web_axis_after_the_web_minimum(self, monkeypatch):
        """The web branch's single confirm — the same prompt pattern, defaulting to disabled."""
        scripted = _ScriptedClick(confirms=[False], prompts=[])
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_autonomy(session_module._WEB_AUTONOMY_AXES) == {"web.automate": False}
        assert scripted.confirm_calls == [
            ("Run the web.automate pipeline unattended (autonomous mode)?", False),
        ]

    def test_survey_autonomy_accepted_web_axis_enables(self, monkeypatch):
        """An accepted web confirm returns the enabling answer of the web axis."""
        scripted = _ScriptedClick(confirms=[True], prompts=[])
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_autonomy(session_module._WEB_AUTONOMY_AXES) == {"web.automate": True}


class TestSurveyWebConfig:
    """The web minimum survey — the five asks of the web amendment branch."""

    def test_survey_web_config_asks_minimum_in_order(self, monkeypatch):
        """The explained provider, the two required models, the browser name, then the headless confirm."""
        scripted = _ScriptedClick(
            confirms=[True],
            prompts=[
                ("LLM provider (writes and classifies the browser-test steps)", "openai"),
                ("Generation model (the LLM writing the browser-step code, required)", "g"),
                ("Classification model (the LLM classifying captured steps, required)", "c"),
                ("Browser name", "chromium"),
            ],
        )
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_web_config() == dict(_WEB_ANSWERS)
        assert [text for text, _default in scripted.prompt_calls] == [
            "LLM provider (writes and classifies the browser-test steps)",
            "Generation model (the LLM writing the browser-step code, required)",
            "Classification model (the LLM classifying captured steps, required)",
            "Browser name",
        ]
        assert scripted.confirm_calls == [("Run the browser headless?", True)]

    def test_survey_web_config_reasks_empty_models(self, monkeypatch):
        """Empty model entries re-ask with the (required) prompt suffix."""
        scripted = _ScriptedClick(
            confirms=[False],
            prompts=[
                ("LLM provider (writes and classifies the browser-test steps)", "anthropic"),
                ("Generation model (the LLM writing the browser-step code, required)", ""),
                ("Generation model (the LLM writing the browser-step code, required) (required)", "g"),
                ("Classification model (the LLM classifying captured steps, required)", ""),
                ("Classification model (the LLM classifying captured steps, required) (required)", "c"),
                ("Browser name", "firefox"),
            ],
        )
        _patch_scripted_click(monkeypatch, scripted)

        assert survey_web_config() == {
            "provider": "anthropic",
            "generation_model": "g",
            "classification_model": "c",
            "browser_name": "firefox",
            "headless": False,
        }

    def test_survey_web_config_browser_name_is_a_choice_of_the_runtime_matrix(self, monkeypatch):
        """The browser ask offers exactly the five runtime-accepted names, defaulting to chromium."""
        seen: list[tuple[str, object, object]] = []
        required_answers = {
            "Generation model (the LLM writing the browser-step code, required)": "g",
            "Classification model (the LLM classifying captured steps, required)": "c",
        }

        def _prompt(text: str, default: object = None, **kwargs: object) -> object:
            seen.append((text, default, kwargs.get("type")))
            # The required asks carry an empty default — answer them, never loop.
            return required_answers[text] if default in (None, "") else default

        monkeypatch.setattr(session_module.click, "prompt", _prompt)
        monkeypatch.setattr(session_module.click, "confirm", lambda *_args, **_kwargs: True)

        assert survey_web_config()["browser_name"] == "chromium"

        text, default, choice = seen[3]
        assert (text, default) == ("Browser name", "chromium")
        assert isinstance(choice, click.Choice)
        assert list(choice.choices) == ["chromium", "firefox", "webkit", "chrome", "msedge"]


class TestBuildWebConfigData:
    """The plain serializable web-config payload."""

    def test_build_web_config_data_payload_shape(self):
        """The surveyed minimum plus the strict/interactive defaults, in WebConfigKeys order."""
        data = build_web_config_data(dict(_WEB_ANSWERS))

        assert data == {
            "provider": "openai",
            "generation_model": "g",
            "classification_model": "c",
            "browser": {"name": "chromium", "headless": True},
            "strict": False,
            "interactive": False,
        }
        assert list(data) == [
            "provider",
            "generation_model",
            "classification_model",
            "browser",
            "strict",
            "interactive",
        ]
        assert set(data) <= {member.value for member in WebConfigKeys}
        assert yaml.safe_load(yaml.safe_dump(data)) == data

    def test_build_web_config_data_enabling_answer_emits_the_web_axis(self):
        """An enabling autonomy answer appends the ``pipelines`` entry — the resolver's exact shape."""
        data = build_web_config_data(dict(_WEB_ANSWERS), True)

        assert data["pipelines"] == {"web.automate": {"autonomous": True}}
        assert list(data) == [
            "provider",
            "generation_model",
            "classification_model",
            "browser",
            "strict",
            "interactive",
            "pipelines",
        ]
        assert list(data)[-1] == "pipelines"
        assert yaml.safe_load(yaml.safe_dump(data)) == data

    @pytest.mark.parametrize("autonomous", [None, False], ids=["absent-answer", "declined-confirm"])
    def test_build_web_config_data_disabling_answers_emit_no_axis(self, autonomous):
        """An absent or declined autonomy answer writes no ``pipelines`` key."""
        data = build_web_config_data(dict(_WEB_ANSWERS), autonomous)

        assert "pipelines" not in data
        assert data["provider"] == "openai"

    def test_build_web_config_data_payload_validates_and_maps(self):
        """The payload the session writes validates as a web config and maps onto prettyplay.

        The seam pin: ``PrettyConfig`` (the library document model) forbids extras and types
        ``provider`` as a Literal, so any drift between the payload builder and the plugin-side
        validation bricks every web run at configphase while the payload-shape tests stay green.
        """
        from goga_tool_pybuggy.web import build_pretty_config
        from prettyplay import PrettyConfig

        config = PrettyConfig.model_validate(build_web_config_data(dict(_WEB_ANSWERS)))

        assert config.provider == "openai"
        assert config.browser.name == "chromium"
        assert config.browser.headless is True

        pretty = build_pretty_config(config, False, False)

        assert pretty.generation_model == "g"
        assert pretty.classification_model == "c"
        assert pretty.browser.name == "chromium"


class TestParseSpecs:
    """First-spec strictness and surveyed-extra leniency."""

    def test_parse_specs_builds_first_spec_without_git(self):
        """A valid git-less first spec yields a single local-only entry."""
        specs = parse_specs(dict(_FIRST_SPEC), None)

        assert list(specs) == ["shop"]
        assert isinstance(specs["shop"], SpecEntry)
        assert specs["shop"].type == "swagger"
        assert specs["shop"].location == "specs/shop.yaml"
        assert specs["shop"].git is None

    def test_parse_specs_attaches_git_when_url_and_location_present(self):
        """Git attaches only when url AND location are answered; an empty ref stays None."""
        attached = parse_specs(
            {**_FIRST_SPEC, "git_url": "https://git/b.git", "git_location": "specs/b.yaml", "git_ref": "v2"}, None
        )
        assert (attached["shop"].git.url, attached["shop"].git.location, attached["shop"].git.ref) == (
            "https://git/b.git",
            "specs/b.yaml",
            "v2",
        )

        empty_ref = parse_specs(
            {**_FIRST_SPEC, "git_url": "https://git/b.git", "git_location": "specs/b.yaml", "git_ref": ""}, None
        )
        assert empty_ref["shop"].git.ref is None

        missing_location = parse_specs({**_FIRST_SPEC, "git_url": "https://git/b.git", "git_location": ""}, None)
        assert missing_location["shop"].git is None

    def test_parse_specs_adds_surveyed_extra_spec(self):
        """A surveyed extra mapping adds a typed entry with its git block."""
        specs = parse_specs(dict(_FIRST_SPEC), [dict(_EXTRA_SPEC)])

        assert set(specs) == {"shop", "billing"}
        billing = specs["billing"]
        assert (billing.type, billing.location) == ("openapi", "specs/billing.yaml")
        assert (billing.git.url, billing.git.location, billing.git.ref) == ("https://git/b.git", "specs/b.yaml", None)

    @pytest.mark.parametrize(
        "spec_answers",
        [
            {**_FIRST_SPEC, "name": ""},
            {**_FIRST_SPEC, "type": "yaml"},
            {**_FIRST_SPEC, "location": ""},
        ],
        ids=["empty-name", "invalid-type", "empty-location"],
    )
    def test_parse_specs_rejects_invalid_first_spec(self, spec_answers):
        """An incomplete or invalid first spec raises ValueError."""
        with pytest.raises(ValueError, match="first spec"):
            parse_specs(spec_answers, None)

    def test_parse_specs_skips_malformed_and_colliding_extras(self, caplog):
        """Malformed and duplicate surveyed extras are skipped with the two stable WARNING events."""
        with caplog.at_level(logging.WARNING):
            specs = parse_specs(
                dict(_FIRST_SPEC),
                [
                    {"name": "", "type": "swagger", "location": "x.yaml"},
                    {"name": "bad", "type": "yaml", "location": "x.yaml"},
                    {"name": "noloc", "type": "swagger", "location": ""},
                    {"name": "shop", "type": "openapi", "location": "other.yaml"},
                    dict(_EXTRA_SPEC),
                ],
            )

        assert set(specs) == {"shop", "billing"}
        assert specs["shop"].location == "specs/shop.yaml"
        warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
        assert len(warnings) == 4
        assert warnings.count("malformed extra spec skipped") == 3
        assert warnings.count("duplicate spec name skipped") == 1


class TestBuildConfigData:
    """The plain serializable tool-config payload."""

    def test_build_config_data_emits_plain_serializable_payload(self):
        """Unanswered scalars drop, numerics coerce, specs land as plain mappings last."""
        data = build_config_data(dict(_API_ANSWERS), [dict(_FIRST_SPEC), dict(_EXTRA_SPEC)])

        assert data["timeout"] == 30.0
        assert isinstance(data["timeout"], float)
        assert data["retries"] == 3
        assert "assert_delay" not in data
        assert data["specs"]["shop"] == {"type": "swagger", "location": "specs/shop.yaml"}
        assert data["specs"]["billing"]["git"] == {"url": "https://git/b.git", "location": "specs/b.yaml"}
        assert list(data) == ["base_url", "timeout", "retries", "specs"]

        for value in data.values():
            assert isinstance(value, str | int | float | dict)

        dumped = yaml.safe_dump(data)
        assert "!!python" not in dumped

    def test_build_config_data_first_spec_only(self):
        """A single-mapping specs list (the declined gate) yields the first-spec-only payload."""
        data = build_config_data(dict(_API_ANSWERS), [dict(_FIRST_SPEC)])

        assert list(data["specs"]) == ["shop"]

    def test_build_config_data_non_numeric_answer_raises(self):
        """A non-numeric numeric answer raises ValueError (soft-drop upstream)."""
        with pytest.raises(ValueError, match="could not convert"):
            build_config_data({**_API_ANSWERS, "timeout": "abc"}, [dict(_FIRST_SPEC)])

    def test_build_config_data_emits_pipelines_axes_on_enabling_answers(self):
        """Enabling answers add the axis entries after the scalar keys — the resolver's exact shape."""
        data = build_config_data(dict(_API_ANSWERS), [dict(_FIRST_SPEC)], {"api.automate": True, "api.patch": True})

        assert data["pipelines"] == {"api.automate": {"autonomous": True}, "api.patch": {"autonomous": True}}
        assert list(data) == ["base_url", "timeout", "retries", "pipelines", "specs"]
        assert list(data)[-1] == "specs"
        assert yaml.safe_load(yaml.safe_dump(data)) == data

    def test_build_config_data_emits_only_the_enabled_axis(self):
        """A single enabling answer writes exactly that pipeline's entry — the axes are independent."""
        data = build_config_data(dict(_API_ANSWERS), [dict(_FIRST_SPEC)], {"api.automate": False, "api.patch": True})

        assert data["pipelines"] == {"api.patch": {"autonomous": True}}

    @pytest.mark.parametrize(
        ("autonomous", "answers"),
        [
            (None, dict(_API_ANSWERS)),
            ({"api.automate": False, "api.patch": False}, dict(_API_ANSWERS)),
            (None, {**_API_ANSWERS, "autonomous": True}),
        ],
        ids=["absent-answers", "declined-confirms", "stale-answer-key-ignored"],
    )
    def test_build_config_data_disabling_answers_and_stale_key_emit_no_axis(self, autonomous, answers):
        """No enabling answer emits no pipelines key; an answers-carried autonomous key is never read."""
        data = build_config_data(answers, [dict(_FIRST_SPEC)], autonomous)

        assert "pipelines" not in data
        assert "specs" in data
        assert list(data["specs"]) == ["shop"]

    def test_build_config_data_takes_surveyed_specs_list(self):
        """The specs parameter is the surveyed list — the first mapping is the first spec."""
        data = build_config_data(
            {"timeout": "5"},
            [
                {"name": "a", "type": "swagger", "location": "x"},
                {"name": "b", "type": "openapi", "location": "y"},
            ],
            {"api.automate": True},
        )

        assert list(data["specs"]) == ["a", "b"]
        assert data["timeout"] == 5.0
        assert data["pipelines"] == {"api.automate": {"autonomous": True}}


class TestBuildConfigAmendments:
    """The declared-intent amendments — review skip, the Dockerfile pair, the pybuggy tools record."""

    @pytest.fixture
    def pinned_version_axis(self, monkeypatch):
        """Pin the installed-version read so the pybuggy tools record is deterministic."""
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")

    def test_build_config_amendments_carry_all_five_entries(self, pinned_version_axis):
        """The amendments deliver the review skip, the Dockerfile pair, the image name, and the tools record."""
        amendments = build_config_amendments(dict(_IMAGE_ANSWERS))

        assert amendments == {
            "build.review.skip": True,
            "docker_image.dockerfile": ".goga/Dockerfile",
            "docker_image.base_image": "qarium/goga-python-3.13:2.0",
            "docker_image.image": "shop-api:latest",
            "tools": {"pybuggy": "2.0.x"},
        }
        assert list(amendments) == [
            "build.review.skip",
            "docker_image.dockerfile",
            "docker_image.base_image",
            "docker_image.image",
            "tools",
        ]

    def test_build_config_amendments_skip_dockerfile_pair_without_base_image(self, pinned_version_axis):
        """An absent base-image answer (the unreachable default-less branch) drops the whole pair."""
        amendments = build_config_amendments({k: v for k, v in _IMAGE_ANSWERS.items() if k != "base_image"})

        assert "docker_image.dockerfile" not in amendments
        assert "docker_image.base_image" not in amendments
        assert amendments["docker_image.image"] == "shop-api:latest"
        assert amendments["tools"] == {"pybuggy": "2.0.x"}

    def test_build_config_amendments_tools_record_falls_back_to_latest(self, monkeypatch):
        """A metadata-less run records latest — the soft contribution never dies on unreadable metadata."""

        def raise_missing(_name: str) -> str:
            raise importlib.metadata.PackageNotFoundError("goga-tool-pybuggy")

        monkeypatch.setattr(importlib.metadata, "version", raise_missing)

        amendments = build_config_amendments({})

        assert amendments["tools"] == {"pybuggy": "latest"}
        assert "docker_image.dockerfile" not in amendments

    def test_amendments_merge_pybuggy_into_user_collected_tools(self, pinned_version_axis):
        """The platform amend merge keeps the user's tools and forces the pybuggy record."""
        from goga.onboarding import SessionAnswers

        answers = SessionAnswers(tools=["pybuggy"])
        answers.record("tools", {"other": "1.x"})

        for path, value in build_config_amendments({}).items():
            answers.amend(path, value)

        snapshot = answers.snapshot()
        assert snapshot["tools"] == {"other": "1.x", "pybuggy": "2.0.x"}
        assert snapshot["build"] == {"review": {"skip": True}}


class TestDeclarePybuggySession:
    """Participation moment one — the declaration hook against a recorder context."""

    def test_declare_pybuggy_session_declares_block_and_skips_two_sections(self, declaration_recorder):
        """An invited context receives every block item in survey order and the two section skips."""
        context = declaration_recorder(invited=True)

        declare_pybuggy_session(context)

        assert [item.id for item in context.declared] == [item.id for item in pybuggy_questions()]
        assert context.skips == ["convention", "docker_image"]


class TestAmendPybuggyConfig:
    """Participation moment two — the kind-gated amendment hook against a recorder context."""

    @pytest.fixture
    def sentinel_surveys(self, monkeypatch) -> list[str]:
        """Patch the four amend-moment surveys to sentinel returns, recording the call order.

        The autonomy double records the axes it was asked for, so the per-branch routing is
        visible in the log; its return carries both branch axes — ``build_config_data`` filters
        to the api pair, the web builder reads its single key.

        Returns:
            The shared call-order log of the patched surveys.
        """
        calls: list[str] = []

        def _record(name: str, value: object):
            def _survey() -> object:
                calls.append(name)
                return value

            return _survey

        def _autonomy(axes: tuple[str, ...]) -> dict[str, bool]:
            calls.append(f"autonomy:{','.join(axes)}")
            return {"api.automate": True, "web.automate": True}

        monkeypatch.setattr(session_module, "survey_api_options", _record("api_options", dict(_API_ANSWERS)))
        monkeypatch.setattr(session_module, "survey_specs", _record("specs", [dict(_FIRST_SPEC), dict(_EXTRA_SPEC)]))
        monkeypatch.setattr(session_module, "survey_autonomy", _autonomy)
        monkeypatch.setattr(session_module, "survey_web_config", _record("web", dict(_WEB_ANSWERS)))
        return calls

    @pytest.mark.parametrize("kind", ["api", "web", "both"])
    def test_amend_pybuggy_config_kind_branches(self, kind, contribution_recorder, sentinel_surveys):
        """The kind answer gates the surveys and the buffered files; the api branch runs before web."""
        answers = {"kind": kind, "base_image": "img", "image": "p:latest"}
        context = contribution_recorder(invited=True, answers=dict(answers))

        amend_pybuggy_config(context)

        assert context.amendments == list(build_config_amendments(dict(answers)).items())

        if kind == "api":
            assert sentinel_surveys == ["api_options", "specs", "autonomy:api.automate,api.patch"]
            assert [file for file, _data in context.files] == ["api.yml"]
        elif kind == "web":
            assert sentinel_surveys == ["web", "autonomy:web.automate"]
            assert [file for file, _data in context.files] == ["web.yml"]
        else:
            assert sentinel_surveys == [
                "api_options",
                "specs",
                "autonomy:api.automate,api.patch",
                "web",
                "autonomy:web.automate",
            ]
            assert [file for file, _data in context.files] == ["api.yml", "web.yml"]

        if kind in ("api", "both"):
            payload = context.files[0][1]
            expected = build_config_data(
                {**answers, **_API_ANSWERS}, [_FIRST_SPEC, _EXTRA_SPEC], {"api.automate": True}
            )
            assert payload == expected
            assert payload["specs"]["billing"]["location"] == "specs/billing.yaml"
            assert payload["pipelines"] == {"api.automate": {"autonomous": True}}

        if kind in ("web", "both"):
            assert context.files[-1] == ("web.yml", build_web_config_data(dict(_WEB_ANSWERS), True))

    def test_amend_pybuggy_config_kind_missing_defaults_to_api(self, contribution_recorder, sentinel_surveys):
        """An answer view without a kind answer runs the api branch — the defensive default."""
        context = contribution_recorder(invited=True, answers={"base_image": "img", "image": "p:latest"})

        amend_pybuggy_config(context)

        assert sentinel_surveys == ["api_options", "specs", "autonomy:api.automate,api.patch"]
        assert [file for file, _data in context.files] == ["api.yml"]

    def test_amend_cancelled_prompt_drops_contribution(self, contribution_recorder, monkeypatch):
        """A cancelled survey prompt propagates click.Abort — never caught, the contribution drops."""

        def cancelled() -> list[dict[str, object]]:
            raise click.Abort

        monkeypatch.setattr(session_module, "survey_api_options", lambda: dict(_API_ANSWERS))
        monkeypatch.setattr(session_module, "survey_specs", cancelled)
        context = contribution_recorder(invited=True, answers={"kind": "api"})

        with pytest.raises(click.Abort):
            amend_pybuggy_config(context)

        assert context.files == []

    def test_amend_pybuggy_config_exception_drops_contribution_upstream(self, contribution_recorder, monkeypatch):
        """A bad numeric answer raises before any write is buffered — the write never happens."""
        monkeypatch.setattr(session_module, "survey_api_options", lambda: {"timeout": "abc"})
        monkeypatch.setattr(session_module, "survey_specs", lambda: [dict(_FIRST_SPEC)])
        monkeypatch.setattr(session_module, "survey_autonomy", lambda _axes: {})
        context = contribution_recorder(invited=True, answers={"kind": "api"})

        with pytest.raises(ValueError, match="could not convert"):
            amend_pybuggy_config(context)

        assert context.files == []


class TestRunSession:
    """The session seam — engine logic construction with pybuggy invited."""

    def test_run_session_builds_engine_logic_with_pybuggy_invited(self, monkeypatch):
        """InitLogic is built with the engine survey/generation parts and pybuggy invited."""
        constructed = {}

        class LogicRecorder:
            """An ``InitLogic``-like double — captures the constructor kwargs."""

            def __init__(self, questionnaire, generator, participation) -> None:
                """Store the constructor kwargs for the assertions.

                Args:
                    questionnaire: The engine questionnaire part.
                    generator: The engine file generator part.
                    participation: The engine tool-participation mediator part.
                """
                constructed.update(questionnaire=questionnaire, generator=generator, participation=participation)

            def run(self) -> int:
                """Return the scripted engine exit code."""
                return 7

        monkeypatch.setattr(session_module, "InitLogic", LogicRecorder)

        assert run_session() == 7
        assert isinstance(constructed["questionnaire"], Questionnaire)
        assert isinstance(constructed["generator"], FileGenerator)
        assert isinstance(constructed["participation"], ToolParticipation)
        assert constructed["participation"].invited == ["pybuggy"]


class TestNoInvitation:
    """The invited guard — an uninvited context receives nothing."""

    def test_declare_and_amend_no_invitation_call_nothing(
        self, declaration_recorder, contribution_recorder, monkeypatch
    ):
        """Both hooks return without touching the context (and without surveying) when not invited."""
        monkeypatch.setattr(
            session_module,
            "survey_api_options",
            lambda: (_ for _ in ()).throw(AssertionError("an uninvited tool must never survey")),
        )
        monkeypatch.setattr(
            session_module,
            "survey_web_config",
            lambda: (_ for _ in ()).throw(AssertionError("an uninvited tool must never survey")),
        )
        declaration = declaration_recorder(invited=False)
        contribution = contribution_recorder(invited=False, answers=dict(_API_ANSWERS))

        declare_pybuggy_session(declaration)
        amend_pybuggy_config(contribution)

        assert declaration.declared == []
        assert declaration.skips == []
        assert contribution.amendments == []
        assert contribution.files == []
