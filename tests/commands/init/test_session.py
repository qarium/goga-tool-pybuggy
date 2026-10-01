"""Tests for the session module — pure builders, participation hooks, session seam.

Covers ``session.py`` in two layers. The pure builders (Task 4):
``pybuggy_questions`` (the declarative block in survey order — exact
ids/defaults, one-level nesting), ``parse_specs`` (strict first spec, lenient
extras), ``build_config_data`` (plain serializable payload, numeric coercion,
``specs`` last), and ``build_config_amendments`` (the single declared-intent
amendment). The participation hooks and the session seam (Task 5):
``declare_pybuggy_session`` (moment one — the invited guard and the in-order
declarations), ``amend_pybuggy_config`` (moment two — the buffered amendment and
the plain-data config payload), and ``run_session`` (the engine logic
construction with pybuggy invited, exit code propagated).
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
    "extra_specs": "billing|openapi|specs/billing.yaml|https://git/b.git|specs/b.yaml|",
}

_SCALAR_MEMBERS = [
    member
    for member in PluginConfigKeys
    if member not in (PluginConfigKeys.BASE_URL, PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER)
]


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
            (build_config_data, {"answers": dict[str, object], "return": dict[str, object]}),
            (build_config_amendments, {"return": dict[str, object]}),
            (
                parse_specs,
                {"spec_answers": dict[str, object], "extra_specs": str | None, "return": dict[str, SpecEntry]},
            ),
        ],
    )
    def test_builder_signature_matches_contract(self, routine, expected):
        """Every builder carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected


class TestSessionParticipationContract:
    """Facade exposure and signature surface of the hooks and the session seam."""

    def test_facade_exports_participation_routines(self):
        """The two hooks and the session seam are importable from the cell facade."""
        assert callable(declare_pybuggy_session)
        assert callable(amend_pybuggy_config)
        assert callable(run_session)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (declare_pybuggy_session, {"context": object, "return": None}),
            (amend_pybuggy_config, {"context": object, "return": None}),
            (run_session, {"return": int}),
        ],
    )
    def test_participation_signature_matches_contract(self, routine, expected):
        """Every participation routine carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected


class TestPybuggyQuestions:
    """The declarative question block — ids, order, defaults, nesting."""

    def test_pybuggy_questions_returns_block_in_survey_order(self):
        """base_url first (required), scalars in declaration order, the group, extra_specs last."""
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
        assert items[-1].id == "extra_specs"

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


class TestParseSpecs:
    """First-spec strictness and extra-line leniency."""

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

    def test_parse_specs_adds_wellformed_extra_line(self):
        """A well-formed extra line adds a typed entry with its git block."""
        specs = parse_specs(dict(_FIRST_SPEC), "billing|openapi|specs/billing.yaml|https://git/b.git|specs/b.yaml|")

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

    def test_parse_specs_skips_malformed_and_colliding_extra_lines(self, caplog):
        """Malformed and duplicate extra lines are skipped with the two stable WARNING events."""
        with caplog.at_level(logging.WARNING):
            specs = parse_specs(
                dict(_FIRST_SPEC), "billing|yaml|x.yaml\nbad|swagger\n| swagger | loc\nshop|openapi|other.yaml"
            )

        assert set(specs) == {"shop"}
        assert specs["shop"].location == "specs/shop.yaml"
        warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
        assert len(warnings) == 4
        assert warnings.count("malformed extra spec line skipped") == 3
        assert warnings.count("duplicate spec name skipped") == 1


class TestBuildConfigData:
    """The plain serializable tool-config payload."""

    def test_build_config_data_emits_plain_serializable_payload(self):
        """Unanswered scalars drop, numerics coerce, specs land as plain mappings last."""
        data = build_config_data(dict(_ANSWERS))

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

    def test_build_config_data_non_numeric_answer_raises(self):
        """A non-numeric numeric answer raises ValueError (soft-drop upstream)."""
        with pytest.raises(ValueError, match="could not convert"):
            build_config_data({**_ANSWERS, "timeout": "abc"})


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

    def test_declare_pybuggy_session_declares_block_when_invited(self, declaration_recorder):
        """An invited context receives every block item in survey order and no skips."""
        context = declaration_recorder(invited=True)

        declare_pybuggy_session(context)

        assert [item.id for item in context.declared] == [item.id for item in pybuggy_questions()]
        assert context.skips == []


class TestAmendPybuggyConfig:
    """Participation moment two — the amendment hook against a recorder context."""

    def test_amend_pybuggy_config_buffers_contribution_when_invited(self, contribution_recorder):
        """An invited context receives the single amendment and the plain-data config payload."""
        context = contribution_recorder(invited=True, answers=dict(_ANSWERS))

        amend_pybuggy_config(context)

        assert context.amendments == [("build.review.skip", True)]
        assert context.files == [("config.yml", build_config_data(dict(_ANSWERS)))]
        assert context.files[0][1]["specs"]["shop"]["location"] == "specs/shop.yaml"

    def test_amend_pybuggy_config_exception_drops_contribution_upstream(self, contribution_recorder):
        """A bad numeric answer raises before any write is buffered — the write never happens."""
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
                    participation: The engine tool-participation mediator.
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

    def test_declare_and_amend_no_invitation_call_nothing(self, declaration_recorder, contribution_recorder):
        """Both hooks return without touching the context when not invited."""
        declaration = declaration_recorder(invited=False)
        contribution = contribution_recorder(invited=False, answers=dict(_ANSWERS))

        declare_pybuggy_session(declaration)
        amend_pybuggy_config(contribution)

        assert declaration.declared == []
        assert declaration.skips == []
        assert contribution.amendments == []
        assert contribution.files == []
