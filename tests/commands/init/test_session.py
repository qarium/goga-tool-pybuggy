"""Tests for the session module — pure builders, participation hooks, session seam.

Covers ``session.py`` in three layers. The pure builders (Task 4):
``pybuggy_questions`` (the declarative block in survey order — exact ids/defaults,
one-level nesting, no compact extra-specs record), ``parse_specs`` (strict first
spec, lenient surveyed extras), ``build_config_data`` (plain serializable payload,
numeric coercion, ``specs`` last), and ``build_config_amendments`` (the single
declared-intent amendment). The interactive follow-up (the 2.0.1 hotfix):
``survey_extra_specs`` — the confirm-gated per-field additional-specs survey the
declarative engine records cannot express. The participation hooks and the session
seam (Task 5): ``declare_pybuggy_session`` (moment one — the invited guard, the
in-order declarations, and the core convention skip), ``amend_pybuggy_config``
(moment two — the surveyed extras, the buffered amendment, and the plain-data
config payload), and ``run_session`` (the engine logic construction with pybuggy
invited, exit code propagated).
"""

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

# One surveyed extra-spec mapping — the ``survey_extra_specs`` record shape (the
# ``first_spec`` child ids), as the interactive follow-up collects it.
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

    Every consumed entry asserts its prompt text — the double is sequence-strict, so a
    reordered or unexpected ask fails the test at the exact prompt.

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
                    "return": dict[str, object],
                },
            ),
            (build_config_amendments, {"return": dict[str, object]}),
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

    def test_pybuggy_questions_last_item_is_autonomy_confirm(self):
        """The block's final item is the autonomy confirm — id, kind, and the disabled default."""
        last = pybuggy_questions()[-1]

        assert isinstance(last, Question)
        assert last.id == "autonomous"
        assert last.kind == "confirm"
        assert last.default is False


class TestSessionParticipationContract:
    """Facade exposure and signature surface of the hooks and the session seam."""

    def test_facade_exports_participation_routines(self):
        """The two hooks, the extra-specs survey, and the session seam are importable."""
        assert callable(declare_pybuggy_session)
        assert callable(amend_pybuggy_config)
        assert callable(survey_extra_specs)
        assert callable(run_session)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (declare_pybuggy_session, {"context": object, "return": None}),
            (amend_pybuggy_config, {"context": object, "return": None}),
            (survey_extra_specs, {"return": list[dict[str, object]]}),
            (run_session, {"return": int}),
        ],
    )
    def test_participation_signature_matches_contract(self, routine, expected):
        """Every participation routine carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected


class TestPybuggyQuestions:
    """The declarative question block — ids, order, defaults, nesting."""

    def test_pybuggy_questions_returns_block_in_survey_order(self):
        """base_url first (required), scalars in declaration order, the first-spec group, the autonomy confirm."""
        items = pybuggy_questions()

        assert len(items) == 9
        assert items[0].id == "base_url"
        assert items[0].default is None

        scalar_items = [item for item in items if isinstance(item, Question)][1:-1]
        assert [item.id for item in scalar_items] == [member.value for member in _SCALAR_MEMBERS]
        assert all(item.default == "" for item in scalar_items)

        group = items[-2]
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

    def test_pybuggy_questions_appends_autonomy_confirm_last(self):
        """The autonomy confirm is the final item — a simple child right after the first-spec group."""
        items = pybuggy_questions()

        last = items[-1]
        assert isinstance(last, Question)
        assert last.id == "autonomous"
        assert last.kind == "confirm"
        assert last.default is False
        assert last.prompt == "Run the api.automate pipeline unattended (autonomous mode)?"
        assert items[-2].id == "first_spec"

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
        """An enabling autonomy answer adds the axis entry after the scalar keys — the resolver's exact shape."""
        data = build_config_data({**_ANSWERS, "autonomous": True}, None)

        assert data["pipelines"] == {"api.automate": {"autonomous": True}}
        assert list(data) == ["base_url", "timeout", "retries", "pipelines", "specs"]
        assert list(data)[-1] == "specs"
        assert yaml.safe_load(yaml.safe_dump(data)) == data

    @pytest.mark.parametrize(
        "answers",
        [{**_ANSWERS, "autonomous": False}, dict(_ANSWERS)],
        ids=["declined-confirm", "absent-key"],
    )
    def test_build_config_data_disabling_and_absent_answers_emit_no_axis(self, answers):
        """A falsy or absent autonomy answer emits no pipelines key — the specs still land."""
        data = build_config_data(answers, None)

        assert "pipelines" not in data
        assert "specs" in data
        assert list(data["specs"]) == ["shop"]


class TestBuildConfigAmendments:
    """The single declared-intent amendment."""

    def test_build_config_amendments_review_skip_declared_intent_only(self):
        """Exactly one amendment — build.review.skip with a bool True value."""
        amendments = build_config_amendments()

        assert amendments == {"build.review.skip": True}
        assert len(amendments) == 1
        assert amendments["build.review.skip"] is True


class TestDeclarePybuggySession:
    """Participation moment one — the declaration hook against a recorder context."""

    def test_declare_pybuggy_session_declares_block_and_skips_convention(self, declaration_recorder):
        """An invited context receives every block item in survey order and the convention skip."""
        context = declaration_recorder(invited=True)

        declare_pybuggy_session(context)

        assert [item.id for item in context.declared] == [item.id for item in pybuggy_questions()]
        assert context.skips == ["convention"]


class TestAmendPybuggyConfig:
    """Participation moment two — the amendment hook against a recorder context."""

    def test_amend_pybuggy_config_buffers_surveyed_contribution(self, contribution_recorder, monkeypatch):
        """The surveyed extras flow into the buffered amendment and the plain-data payload."""
        monkeypatch.setattr(session_module, "survey_extra_specs", lambda: [dict(_EXTRA_SPEC)])
        context = contribution_recorder(invited=True, answers=dict(_ANSWERS))

        amend_pybuggy_config(context)

        assert context.amendments == [("build.review.skip", True)]
        assert context.files == [("config.yml", build_config_data(dict(_ANSWERS), [dict(_EXTRA_SPEC)]))]
        assert context.files[0][1]["specs"]["billing"]["location"] == "specs/billing.yaml"

    def test_amend_pybuggy_config_declined_gate_keeps_first_spec(self, contribution_recorder, monkeypatch):
        """A declined extra-specs gate buffers the first-spec-only payload."""
        monkeypatch.setattr(session_module, "survey_extra_specs", lambda: [])
        context = contribution_recorder(invited=True, answers=dict(_ANSWERS))

        amend_pybuggy_config(context)

        assert list(context.files[0][1]["specs"]) == ["shop"]

    def test_amend_pybuggy_config_exception_drops_contribution_upstream(self, contribution_recorder, monkeypatch):
        """A bad numeric answer raises before any write is buffered — the write never happens."""
        monkeypatch.setattr(session_module, "survey_extra_specs", lambda: [])
        context = contribution_recorder(invited=True, answers={**_ANSWERS, "timeout": "abc"})

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
        declaration = declaration_recorder(invited=False)
        contribution = contribution_recorder(invited=False, answers=dict(_ANSWERS))

        declare_pybuggy_session(declaration)
        amend_pybuggy_config(contribution)

        assert declaration.declared == []
        assert declaration.skips == []
        assert contribution.amendments == []
        assert contribution.files == []
