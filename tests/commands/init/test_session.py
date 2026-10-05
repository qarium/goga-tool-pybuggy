"""Tests for the session module — pure builders, participation hooks, session seam.

Covers the pure builders, the image/spec/autonomy surveys, the participation hooks, and the session seam.
"""

import importlib.metadata
import logging

import goga_tool_pybuggy.commands.init.session as session_module
import pytest
import yaml
from goga.onboarding import FileGenerator, Question, QuestionGroup, Questionnaire, ToolParticipation
from goga_tool_pybuggy.commands.init import (
    amend_pybuggy_config,
    build_config_amendments,
    build_config_data,
    declare_pybuggy_session,
    parse_specs,
    pybuggy_questions,
    run_session,
    survey_autonomy,
    survey_extra_specs,
)
from goga_tool_pybuggy.config import SpecEntry
from goga_tool_pybuggy.plugin import PluginConfigKeys

_FIRST_SPEC = {
    "name": "shop",
    "type": "swagger",
    "location": "specs/shop.yaml",
    "git_url": "",
    "git_location": "",
    "git_ref": "",
}

_ANSWERS = {
    "base_url": "https://{{ HOST }}/api",
    "timeout": "30",
    "retries": "3",
    "assert_delay": "",
    "first_spec": dict(_FIRST_SPEC),
}

# The block answer view carrying the image inputs — the source of the Dockerfile amendments.
_IMAGE_ANSWERS = {
    **_ANSWERS,
    "base_image": "qarium/goga-python-3.13:2.0",
    "image": "shop-api:latest",
}

# One surveyed extra-spec mapping — the record shape ``survey_extra_specs`` collects.
_EXTRA_SPEC = {
    "name": "billing",
    "type": "openapi",
    "location": "specs/billing.yaml",
    "git_url": "https://git/b.git",
    "git_location": "specs/b.yaml",
    "git_ref": "",
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
        confirm_calls: The confirm prompt texts, in ask order.
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
        self.confirm_calls: list[str] = []
        self.prompt_calls: list[tuple[str, object | None]] = []

    def confirm(self, prompt: str, default: bool = False, **_: object) -> bool:
        """Answer one confirm gate from the queue.

        Args:
            prompt: The gate text the survey asks.
            default: The offered default (recorded by the caller's kwargs, unused).
            **_: The remaining click kwargs (absorbed).

        Returns:
            The next scripted gate answer.
        """
        self.confirm_calls.append(prompt)
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


class TestSessionBuildersContract:
    """Facade exposure and signature surface of the four pure builders."""

    def test_facade_exports_pure_builders(self):
        """All four pure builder routines are importable from the cell facade."""
        assert callable(pybuggy_questions)
        assert callable(build_config_data)
        assert callable(build_config_amendments)
        assert callable(parse_specs)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (pybuggy_questions, {"return": list[Question]}),
            (
                build_config_data,
                {
                    "answers": dict[str, object],
                    "extra_specs": list[dict[str, object]] | None,
                    "autonomous": bool,
                    "return": dict[str, object],
                },
            ),
            (build_config_amendments, {"answers": dict[str, object], "return": dict[str, object]}),
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

    def test_pybuggy_questions_declares_no_autonomy_item(self):
        """The block carries no autonomy record — the amend-moment survey owns the question."""
        items = pybuggy_questions()

        assert "autonomous" not in {item.id for item in items if isinstance(item, Question)}
        assert all("unattended" not in (item.prompt or "") for item in items if isinstance(item, Question))


class TestSessionParticipationContract:
    """Facade exposure and signature surface of the hooks and the session seam."""

    def test_facade_exports_participation_routines(self):
        """The two hooks, the two amend-moment surveys, and the session seam are importable."""
        assert callable(declare_pybuggy_session)
        assert callable(amend_pybuggy_config)
        assert callable(survey_extra_specs)
        assert callable(survey_autonomy)
        assert callable(run_session)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (declare_pybuggy_session, {"context": object, "return": None}),
            (amend_pybuggy_config, {"context": object, "return": None}),
            (survey_extra_specs, {"return": list[dict[str, object]]}),
            (survey_autonomy, {"return": bool}),
            (run_session, {"return": int}),
        ],
    )
    def test_participation_signature_matches_contract(self, routine, expected):
        """Every participation routine carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected


class TestPybuggyQuestions:
    """The declarative question block — ids, order, defaults, nesting."""

    def test_pybuggy_questions_returns_block_in_survey_order(self):
        """The image inputs first, base_url, scalars in declaration order, the first-spec group last."""
        items = pybuggy_questions()

        assert len(items) == 10
        assert [item.id for item in items[:3]] == ["base_image", "image", "base_url"]
        assert items[0].prompt.startswith("Base image (FROM)")
        assert items[0].default is not None
        assert ":" in items[0].default
        assert items[1].prompt == "Built image name"
        assert items[2].default is None

        scalar_items = [item for item in items if isinstance(item, Question)][3:]
        assert [item.id for item in scalar_items] == [member.value for member in _SCALAR_MEMBERS]
        assert all(item.default == "" for item in scalar_items)

        group = items[-1]
        assert isinstance(group, QuestionGroup)
        assert group.id == "first_spec"
        assert group.prompt == "The first spec"
        assert [child.id for child in group.children] == [
            "name",
            "type",
            "location",
            "git_url",
            "git_location",
            "git_ref",
        ]
        assert group.children[1].choices == ["swagger", "openapi"]

    def test_pybuggy_questions_base_image_hints_follow_runtime_tag(self):
        """The FROM prompt embeds the python-family hints completed with the running goga minor tag."""
        from goga.version import host_goga_version, minor_version

        items = pybuggy_questions()
        base_image = items[0]
        tag = minor_version(host_goga_version())

        hints = [line.strip()[2:] for line in base_image.prompt.splitlines() if line.strip().startswith("- ")]
        assert hints == [f"{name}:{tag}" for name in session_module._BASE_IMAGE_NAMES]
        assert hints[0].startswith("qarium/goga-python-3.10:")
        assert base_image.default == hints[-1]

    def test_pybuggy_questions_declares_no_compact_extra_specs(self):
        """The compact one-per-line extra_specs record is gone — the amend-moment survey owns it."""
        items = pybuggy_questions()

        assert "extra_specs" not in {item.id for item in items if isinstance(item, Question)}
        assert all("one per line" not in (item.prompt or "") for item in items if isinstance(item, Question))

    def test_pybuggy_questions_covers_every_scalar_plugin_key(self):
        """The scalar questions cover exactly the scalar plugin keys — headers/loader never surveyed."""
        items = pybuggy_questions()

        collected = {item.id for item in items}
        for item in items:
            if isinstance(item, QuestionGroup):
                collected |= {child.id for child in item.children}

        plugin_values = {member.value for member in PluginConfigKeys}
        assert {key for key in collected if key in plugin_values} == plugin_values - {"headers", "loader"}
        assert "headers" not in collected
        assert "loader" not in collected

    def test_pybuggy_questions_holds_one_nesting_level(self):
        """Every group child is a simple Question — exactly one nesting level."""
        items = pybuggy_questions()

        for item in items:
            if isinstance(item, QuestionGroup):
                assert item.children is not None
                assert all(isinstance(child, Question) for child in item.children)


class TestSurveyExtraSpecs:
    """The confirm-gated per-field additional-specs survey — the amend-moment follow-up."""

    def test_survey_extra_specs_declined_gate_collects_nothing(self, monkeypatch):
        """A declined gate asks no field prompts and returns an empty list."""
        scripted = _ScriptedClick(confirms=[False], prompts=[])
        monkeypatch.setattr(session_module.click, "confirm", scripted.confirm)
        monkeypatch.setattr(session_module.click, "prompt", scripted.prompt)

        assert survey_extra_specs() == []
        assert scripted.confirm_calls == ["Add another spec?"]
        assert scripted.prompt_calls == []

    def test_survey_extra_specs_asks_fields_in_first_spec_order(self, monkeypatch):
        """An accepted spec is asked field by field — name, type, location, then the git fields."""
        scripted = _ScriptedClick(
            confirms=[True, False],
            prompts=[
                ("Spec name", "billing"),
                ("Spec type", "openapi"),
                ("Spec location (path from project root)", "specs/billing.yaml"),
                ("Git URL (empty — no git source)", "https://git/b.git"),
                ("Path inside the repository", "specs/b.yaml"),
                ("Git ref (branch/tag; empty — default branch)", ""),
            ],
        )
        monkeypatch.setattr(session_module.click, "confirm", scripted.confirm)
        monkeypatch.setattr(session_module.click, "prompt", scripted.prompt)

        assert survey_extra_specs() == [dict(_EXTRA_SPEC)]
        assert scripted.confirm_calls == ["Add another spec?", "Add another spec?"]

    def test_survey_extra_specs_reasks_required_fields(self, monkeypatch):
        """Empty name and location entries re-ask with the (required) prompt suffix."""
        scripted = _ScriptedClick(
            confirms=[True, False],
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
        monkeypatch.setattr(session_module.click, "confirm", scripted.confirm)
        monkeypatch.setattr(session_module.click, "prompt", scripted.prompt)

        surveyed = survey_extra_specs()

        assert surveyed == [
            {
                "name": "billing",
                "type": "swagger",
                "location": "specs/b.yaml",
                "git_url": "",
                "git_location": "",
                "git_ref": "",
            }
        ]

    def test_survey_extra_specs_loops_until_declined(self, monkeypatch):
        """The gate repeats after every accepted spec — two extras from three confirms."""
        scripted = _ScriptedClick(
            confirms=[True, True, False],
            prompts=[
                ("Spec name", "one"),
                ("Spec type", "swagger"),
                ("Spec location (path from project root)", "one.yaml"),
                ("Git URL (empty — no git source)", ""),
                ("Path inside the repository", ""),
                ("Git ref (branch/tag; empty — default branch)", ""),
                ("Spec name", "two"),
                ("Spec type", "openapi"),
                ("Spec location (path from project root)", "two.yaml"),
                ("Git URL (empty — no git source)", ""),
                ("Path inside the repository", ""),
                ("Git ref (branch/tag; empty — default branch)", ""),
            ],
        )
        monkeypatch.setattr(session_module.click, "confirm", scripted.confirm)
        monkeypatch.setattr(session_module.click, "prompt", scripted.prompt)

        surveyed = survey_extra_specs()

        assert [spec["name"] for spec in surveyed] == ["one", "two"]
        assert scripted.confirm_calls == ["Add another spec?"] * 3


class TestSurveyAutonomy:
    """The autonomy confirm — the closing question of the amendment moment."""

    def test_survey_autonomy_asks_the_disabled_default_confirm(self, monkeypatch):
        """The confirm carries the unattended-mode prompt with the disabled default."""
        scripted = _ScriptedClick(confirms=[False], prompts=[])
        monkeypatch.setattr(session_module.click, "confirm", scripted.confirm)
        monkeypatch.setattr(session_module.click, "prompt", scripted.prompt)

        assert survey_autonomy() is False
        assert scripted.confirm_calls == ["Run the api.automate pipeline unattended (autonomous mode)?"]

    def test_survey_autonomy_acceptance_enables(self, monkeypatch):
        """An accepted confirm returns True — the enabling answer of the pipelines axis."""
        scripted = _ScriptedClick(confirms=[True], prompts=[])
        monkeypatch.setattr(session_module.click, "confirm", scripted.confirm)
        monkeypatch.setattr(session_module.click, "prompt", scripted.prompt)

        assert survey_autonomy() is True


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
        data = build_config_data(dict(_ANSWERS), [dict(_EXTRA_SPEC)])

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

    def test_build_config_data_without_extras_keeps_first_spec_only(self):
        """A None extras list (the declined gate) yields the first-spec-only payload."""
        data = build_config_data(dict(_ANSWERS), None)

        assert list(data["specs"]) == ["shop"]

    def test_build_config_data_non_numeric_answer_raises(self):
        """A non-numeric numeric answer raises ValueError (soft-drop upstream)."""
        with pytest.raises(ValueError, match="could not convert"):
            build_config_data({**_ANSWERS, "timeout": "abc"}, None)

    def test_build_config_data_emits_pipelines_axis_on_enabling_answer(self):
        """An enabling autonomy flag adds the axis entry after the scalar keys — the resolver's exact shape."""
        data = build_config_data(dict(_ANSWERS), None, True)

        assert data["pipelines"] == {"api.automate": {"autonomous": True}}
        assert list(data) == ["base_url", "timeout", "retries", "pipelines", "specs"]
        assert list(data)[-1] == "specs"
        assert yaml.safe_load(yaml.safe_dump(data)) == data

    @pytest.mark.parametrize(
        ("autonomous", "answers"),
        [(False, dict(_ANSWERS)), (False, {**_ANSWERS, "autonomous": True})],
        ids=["declined-confirm", "stale-answer-key-ignored"],
    )
    def test_build_config_data_disabling_answer_and_stale_key_emit_no_axis(self, autonomous, answers):
        """A false flag emits no pipelines key; an answers-carried autonomous key is never read."""
        data = build_config_data(answers, None, autonomous)

        assert "pipelines" not in data
        assert "specs" in data
        assert list(data["specs"]) == ["shop"]


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
    """Participation moment two — the amendment hook against a recorder context."""

    def test_amend_pybuggy_config_buffers_surveyed_contribution(self, contribution_recorder, monkeypatch):
        """The surveyed extras and autonomy flow into the buffered amendments and the payload."""
        monkeypatch.setattr(session_module, "survey_extra_specs", lambda: [dict(_EXTRA_SPEC)])
        monkeypatch.setattr(session_module, "survey_autonomy", lambda: True)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        context = contribution_recorder(invited=True, answers=dict(_IMAGE_ANSWERS))

        amend_pybuggy_config(context)

        assert context.amendments == list(build_config_amendments(dict(_IMAGE_ANSWERS)).items())
        assert context.files == [("config.yml", build_config_data(dict(_IMAGE_ANSWERS), [dict(_EXTRA_SPEC)], True))]
        assert context.files[0][1]["specs"]["billing"]["location"] == "specs/billing.yaml"
        assert context.files[0][1]["pipelines"] == {"api.automate": {"autonomous": True}}

    def test_amend_pybuggy_config_declined_gate_keeps_first_spec(self, contribution_recorder, monkeypatch):
        """A declined extra-specs gate buffers the first-spec-only payload with no axis."""
        monkeypatch.setattr(session_module, "survey_extra_specs", lambda: [])
        monkeypatch.setattr(session_module, "survey_autonomy", lambda: False)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        context = contribution_recorder(invited=True, answers=dict(_IMAGE_ANSWERS))

        amend_pybuggy_config(context)

        assert list(context.files[0][1]["specs"]) == ["shop"]
        assert "pipelines" not in context.files[0][1]

    def test_amend_pybuggy_config_surveys_specs_before_autonomy(self, contribution_recorder, monkeypatch):
        """The extras survey completes before the autonomy confirm — the question never interleaves specs."""
        calls: list[str] = []
        monkeypatch.setattr(session_module, "survey_extra_specs", lambda: calls.append("specs") or [])
        monkeypatch.setattr(session_module, "survey_autonomy", lambda: calls.append("autonomy") or False)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        context = contribution_recorder(invited=True, answers=dict(_IMAGE_ANSWERS))

        amend_pybuggy_config(context)

        assert calls == ["specs", "autonomy"]

    def test_amend_pybuggy_config_exception_drops_contribution_upstream(self, contribution_recorder, monkeypatch):
        """A bad numeric answer raises before any write is buffered — the write never happens."""
        monkeypatch.setattr(session_module, "survey_extra_specs", lambda: [])
        monkeypatch.setattr(session_module, "survey_autonomy", lambda: False)
        context = contribution_recorder(invited=True, answers={**_IMAGE_ANSWERS, "timeout": "abc"})

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
            "survey_extra_specs",
            lambda: (_ for _ in ()).throw(AssertionError("an uninvited tool must never survey")),
        )
        monkeypatch.setattr(
            session_module,
            "survey_autonomy",
            lambda: (_ for _ in ()).throw(AssertionError("an uninvited tool must never survey")),
        )
        declaration = declaration_recorder(invited=False)
        contribution = contribution_recorder(invited=False, answers=dict(_ANSWERS))

        declare_pybuggy_session(declaration)
        amend_pybuggy_config(contribution)

        assert declaration.declared == []
        assert declaration.skips == []
        assert contribution.amendments == []
        assert contribution.files == []
