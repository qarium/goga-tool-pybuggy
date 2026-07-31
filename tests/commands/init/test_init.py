"""Contract and logic tests for run_init / register_usages / init_cmd handler."""

import typing
from pathlib import Path
from unittest import mock

import click
import click.testing
import pytest
import yaml
from goga_tool_pybuggy.commands.init import (
    init_cmd,
    register_annotations,
    register_usages,
    run_goga_init,
    run_init,
)
from ruamel.yaml import YAMLError

_USAGE_KEYS = {
    "pybuggy-api": ".goga/usages/cooks/pybuggy/api.md",
    "pybuggy-asserts": ".goga/usages/cooks/pybuggy/asserts.md",
}

_ANNOTATION_LINES = {
    "pybuggy-api": "`pybuggy-api` — runtime facade of goga_tool_pybuggy.api for executing HTTP requests.",
    "pybuggy-asserts": "`pybuggy-asserts` — full assert layer of goga_tool_pybuggy.api.asserts built on matchcrest.",
}


# Contract tests ---------------------------------------------------------------


def test_run_init_importable_from_facade() -> None:
    """run_init should be importable from the goga_tool_pybuggy.commands.init facade."""
    from goga_tool_pybuggy.commands.init import run_init as imported

    assert imported is run_init


def test_register_usages_importable_from_facade() -> None:
    """register_usages should be importable from the goga_tool_pybuggy.commands.init facade."""
    from goga_tool_pybuggy.commands.init import register_usages as imported

    assert imported is register_usages


def test_init_cmd_carries_no_options() -> None:
    """init_cmd is a Click command named 'init' carrying no options or arguments."""
    assert init_cmd.name == "init"
    assert init_cmd.params == []


def test_init_cmd_propagates_exit_code_via_ctx(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_cmd propagates run_init's exit code through ctx.exit via the Click context."""
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_init", lambda: 2)
    runner = click.testing.CliRunner()
    result = runner.invoke(init_cmd, [])

    assert result.exit_code == 2


def test_run_init_signature() -> None:
    """run_init takes no parameters and returns an exit code (int)."""
    assert run_init.__code__.co_argcount == 0
    assert typing.get_type_hints(run_init)["return"] is int


def test_register_usages_signature() -> None:
    """register_usages has signature (config_path, usage_keys)."""
    params = register_usages.__code__.co_varnames[: register_usages.__code__.co_argcount]

    assert params == ("config_path", "usage_keys")


def test_register_annotations_importable_from_facade() -> None:
    """register_annotations should be importable from the goga_tool_pybuggy.commands.init facade."""
    from goga_tool_pybuggy.commands.init import register_annotations as imported

    assert imported is register_annotations


def test_register_annotations_is_public_in_facade() -> None:
    """register_annotations is exposed on the facade __all__ (public contract)."""
    from goga_tool_pybuggy.commands.init import __all__ as facade_all

    assert "register_annotations" in facade_all


def test_register_annotations_signature() -> None:
    """register_annotations has signature (config_path, annotation_lines)."""
    params = (
        register_annotations.__code__.co_varnames[: register_annotations.__code__.co_argcount]
    )

    assert params == ("config_path", "annotation_lines")


# Logic tests ------------------------------------------------------------------


def test_run_init_in_fresh_project_calls_goga_init_then_registers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a fresh project run_init calls run_goga_init, then discovers/copies/registers usages+annotations."""
    monkeypatch.chdir(tmp_path)
    run_goga_init_stub = mock.Mock(return_value=0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", run_goga_init_stub)

    assert run_init() == 0

    assert run_goga_init_stub.call_count == 1
    assert (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()
    assert (tmp_path / ".goga/usages/cooks/pybuggy/asserts.md").exists()

    cfg = yaml.safe_load((tmp_path / ".goga/config.yml").read_text())
    assert set(cfg["codemanifest"]["usages"]) == {"pybuggy-api", "pybuggy-asserts"}
    assert cfg["codemanifest"]["usages"]["pybuggy-api"].endswith("api.md")

    from goga_tool_pybuggy.commands.init.init import PYBUGGY_ANNOTATIONS

    annotations = cfg["codemanifest"]["annotations"]
    assert PYBUGGY_ANNOTATIONS["api"] in annotations
    assert PYBUGGY_ANNOTATIONS["asserts"] in annotations


def test_run_init_recursive_discovery_picks_subcell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_init should discover the asserts subcell of api recursively."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 0)

    run_init()

    assert (tmp_path / ".goga/usages/cooks/pybuggy/asserts.md").exists()


def test_run_init_in_initialized_project_skips_goga_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On an already-initialized project run_init skips run_goga_init and only registers usages."""
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages:\n    conventions: .goga/usages/conventions.md\n")
    monkeypatch.chdir(tmp_path)
    run_goga_init_spy = mock.Mock(return_value=0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", run_goga_init_spy)

    assert run_init() == 0

    assert run_goga_init_spy.call_count == 0
    cfg = yaml.safe_load(config.read_text())
    assert {"pybuggy-api", "pybuggy-asserts"} <= set(cfg["codemanifest"]["usages"])


def test_run_init_propagates_goga_cancel_without_registering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-zero run_goga_init exit code is returned without registering any usages."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 1)
    register_spy = mock.Mock(wraps=register_usages)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.register_usages", register_spy)

    assert run_init() == 1

    assert register_spy.call_count == 0
    assert not (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()


def test_run_init_idempotent_second_run_no_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second run_init overwrites copied files and skips registered keys — no config diff."""
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages:\n    conventions: .goga/usages/conventions.md\n")
    monkeypatch.chdir(tmp_path)
    run_goga_init_spy = mock.Mock(return_value=0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", run_goga_init_spy)

    run_init()
    before = config.read_text()

    run_init()
    after = config.read_text()

    assert run_goga_init_spy.call_count == 0
    assert before == after


def test_run_init_maps_bootstrap_failure_to_click_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_init should map a file-write failure to click.ClickException."""
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages: {}\n")
    monkeypatch.chdir(tmp_path)

    with (
        mock.patch("goga_tool_pybuggy.commands.init.init.Path.write_text", side_effect=OSError("denied")),
        pytest.raises(click.ClickException),
    ):
        run_init()


# run_goga_init contract tests ------------------------------------------------


def test_run_goga_init_importable_from_facade() -> None:
    """run_goga_init should be importable from the goga_tool_pybuggy.commands.init facade."""
    from goga_tool_pybuggy.commands.init import run_goga_init as imported

    assert imported is run_goga_init


def test_run_goga_init_is_public_in_facade() -> None:
    """run_goga_init is exposed on the facade __all__ (public test seam)."""
    from goga_tool_pybuggy.commands.init import __all__ as facade_all

    assert "run_goga_init" in facade_all


def test_run_goga_init_signature() -> None:
    """run_goga_init takes no parameters and returns an exit code."""
    assert run_goga_init.__code__.co_argcount == 0


# run_goga_init logic tests ----------------------------------------------------


def _stub_questionnaire(monkeypatch: pytest.MonkeyPatch) -> mock.Mock:
    """Install a mocked Questionnaire on init.py and return its instance.

    The per-field ``ask_*`` methods return deterministic values; ``ask_image`` records its call
    so it doubles as a spy for the language argument.
    """
    questionnaire = mock.Mock()
    questionnaire.ask_base_convention.return_value = ({"conventions": "src"}, "annotations")
    questionnaire.ask_codemanifest_usages.return_value = {"conventions": "src"}
    questionnaire.ask_codemanifest_annotations.return_value = "annotations"
    questionnaire.ask_agent.return_value = "coder"
    questionnaire.ask_image.return_value = "qarium/goga-python-3.12:1.1"
    questionnaire.ask_dockerfile_path.return_value = "Dockerfile"
    questionnaire.ask_env.return_value = {"KEY": "v"}
    questionnaire.ask_pipeline_agent.return_value = "pcoder"
    questionnaire.ask_pipeline_env.return_value = {"PKEY": "pv"}

    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.Questionnaire", mock.Mock(return_value=questionnaire))

    return questionnaire


def test_run_goga_init_hardcodes_python_and_calls_ask_image_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_goga_init hardcodes language='python', skips ask_language, calls ask_image('python')."""
    questionnaire = _stub_questionnaire(monkeypatch)
    generator = mock.Mock()
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.FileGenerator", mock.Mock(return_value=generator))

    assert run_goga_init() == 0

    questionnaire.ask_language.assert_not_called()
    questionnaire.ask_image.assert_called_once_with("python")
    generator.generate.assert_called_once()
    answers = generator.generate.call_args.args[0]
    assert answers.goga_config.language == "python"


def test_run_goga_init_assembles_goga_config_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_goga_init assembles GogaConfigAnswers from the per-field answers and feeds InitAnswers."""
    questionnaire = _stub_questionnaire(monkeypatch)
    generator = mock.Mock()
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.FileGenerator", mock.Mock(return_value=generator))
    config_spy = mock.Mock(name="GogaConfigAnswers")
    answers_spy = mock.Mock(name="InitAnswers")
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.GogaConfigAnswers", config_spy)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.InitAnswers", answers_spy)

    assert run_goga_init() == 0

    config_spy.assert_called_once_with(
        language="python",
        agent=questionnaire.ask_agent.return_value,
        image=questionnaire.ask_image.return_value,
        pipeline_agent=questionnaire.ask_pipeline_agent.return_value,
        pipeline_env=questionnaire.ask_pipeline_env.return_value,
        env=questionnaire.ask_env.return_value,
        dockerfile_path=questionnaire.ask_dockerfile_path.return_value,
        codemanifest_usages=questionnaire.ask_codemanifest_usages.return_value,
        codemanifest_annotations=questionnaire.ask_codemanifest_annotations.return_value,
    )
    answers_spy.assert_called_once_with(goga_config=config_spy.return_value)
    generator.generate.assert_called_once_with(answers_spy.return_value)


def test_run_goga_init_returns_1_on_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_goga_init returns 1 (without raising) when generation is aborted by the user."""
    _stub_questionnaire(monkeypatch)
    generator = mock.Mock()
    generator.generate.side_effect = click.Abort()
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.FileGenerator", mock.Mock(return_value=generator))

    assert run_goga_init() == 1


def test_run_goga_init_returns_1_on_generation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_goga_init logs and echoes a generation failure, then returns 1 (never raises)."""
    _stub_questionnaire(monkeypatch)
    generator = mock.Mock()
    generator.generate.side_effect = RuntimeError("boom")
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.FileGenerator", mock.Mock(return_value=generator))
    logger = mock.Mock()
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.logger", logger)
    echo = mock.Mock()
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.click.echo", echo)

    assert run_goga_init() == 1

    logger.error.assert_called_once()
    echo.assert_called_once()
    assert "boom" in echo.call_args.args[0]


def test_run_goga_init_returns_1_on_abort_during_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_goga_init returns 1 (never raises) when the user cancels during a prompt."""
    questionnaire = _stub_questionnaire(monkeypatch)
    questionnaire.ask_agent.side_effect = click.Abort()  # user cancels mid-flow
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.FileGenerator", mock.Mock())

    assert run_goga_init() == 1


def test_run_goga_init_threads_answers_into_downstream_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each collected answer threads into the downstream prompt (prefill tuple, agent, pipeline_agent)."""
    questionnaire = _stub_questionnaire(monkeypatch)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.FileGenerator", mock.Mock())

    assert run_goga_init() == 0

    usages_prefill, annotations_prefill = questionnaire.ask_base_convention.return_value
    questionnaire.ask_codemanifest_usages.assert_called_once_with(usages_prefill)
    questionnaire.ask_codemanifest_annotations.assert_called_once_with(annotations_prefill)
    agent = questionnaire.ask_agent.return_value
    questionnaire.ask_env.assert_called_once_with(agent)
    questionnaire.ask_pipeline_agent.assert_called_once_with(agent)
    questionnaire.ask_pipeline_env.assert_called_once_with(questionnaire.ask_pipeline_agent.return_value)


def test_register_usages_creates_block_when_file_absent(tmp_path: Path) -> None:
    """register_usages creates a minimal config carrying the codemanifest.usages block."""
    config = tmp_path / "config.yml"

    added = register_usages(config, {"pybuggy-api": ".goga/usages/cooks/pybuggy/api.md"})

    assert added == ["pybuggy-api"]
    cfg = yaml.safe_load(config.read_text())
    assert cfg == {"codemanifest": {"usages": {"pybuggy-api": ".goga/usages/cooks/pybuggy/api.md"}}}


def test_register_usages_empty_existing_file_creates_block(tmp_path: Path) -> None:
    """register_usages treats an empty file as an empty document and creates the usages block."""
    config = tmp_path / "config.yml"
    config.write_text("")

    added = register_usages(config, {"pybuggy-api": ".goga/usages/cooks/pybuggy/api.md"})

    assert added == ["pybuggy-api"]
    cfg = yaml.safe_load(config.read_text())
    assert cfg == {"codemanifest": {"usages": {"pybuggy-api": ".goga/usages/cooks/pybuggy/api.md"}}}


def test_register_usages_merges_skipping_existing_keys(tmp_path: Path) -> None:
    """register_usages preserves existing keys/comments and only adds missing ones."""
    config = tmp_path / "config.yml"
    config.write_text("codemanifest:\n  usages:\n    conventions: .goga/usages/conventions.md  # пользовательский\n")

    added = register_usages(config, {"pybuggy-api": ".goga/usages/cooks/pybuggy/api.md"})

    assert added == ["pybuggy-api"]

    text = config.read_text()
    assert "# пользовательский" in text  # round-trip preserved the comment

    cfg = yaml.safe_load(text)
    assert cfg["codemanifest"]["usages"]["conventions"] == ".goga/usages/conventions.md"
    assert cfg["codemanifest"]["usages"]["pybuggy-api"] == ".goga/usages/cooks/pybuggy/api.md"


def test_register_usages_invalid_yaml_raises(tmp_path: Path) -> None:
    """register_usages propagates a YAML error for an invalid existing file."""
    config = tmp_path / "config.yml"
    config.write_text("codemanifest: [unclosed")

    with pytest.raises(YAMLError):
        register_usages(config, _USAGE_KEYS)


def test_register_usages_non_map_codemanifest_raises(tmp_path: Path) -> None:
    """register_usages raises ValueError when codemanifest is not a mapping (never overwrites)."""
    config = tmp_path / "config.yml"
    config.write_text("codemanifest: not-a-map")

    with pytest.raises(ValueError, match="not a mapping"):
        register_usages(config, _USAGE_KEYS)


# register_annotations logic tests --------------------------------------------


def test_register_annotations_creates_block_when_file_absent(tmp_path: Path) -> None:
    """register_annotations creates a minimal config carrying the codemanifest.annotations block."""
    config = tmp_path / "config.yml"

    added = register_annotations(config, _ANNOTATION_LINES)

    assert added == ["pybuggy-api", "pybuggy-asserts"]
    text = config.read_text()
    assert "annotations: |" in text
    cfg = yaml.safe_load(text)
    annotations = cfg["codemanifest"]["annotations"]
    assert "`pybuggy-api`" in annotations
    assert "`pybuggy-asserts`" in annotations


def test_register_annotations_preserves_existing_and_appends(tmp_path: Path) -> None:
    """register_annotations preserves the existing annotation text and only appends missing lines."""
    config = tmp_path / "config.yml"
    config.write_text(
        "codemanifest:\n"
        "  usages:\n"
        "    conventions: .goga/usages/conventions.md\n"
        "  annotations: |\n"
        "    Use `conventions` for code writing rules and testing.\n"
    )

    added = register_annotations(config, _ANNOTATION_LINES)

    assert added == ["pybuggy-api", "pybuggy-asserts"]
    text = config.read_text()
    assert "Use `conventions` for code writing rules and testing." in text  # base annotation preserved
    assert "`pybuggy-api`" in text
    assert "`pybuggy-asserts`" in text


def test_register_annotations_idempotent_skips_existing(tmp_path: Path) -> None:
    """register_annotations skips annotation lines whose backtick reference already exists."""
    config = tmp_path / "config.yml"
    config.write_text(
        "codemanifest:\n"
        "  annotations: |\n"
        "    `pybuggy-api` already described here.\n"
    )

    added = register_annotations(config, _ANNOTATION_LINES)

    assert added == ["pybuggy-asserts"]  # api skipped — its backtick reference already present
    text = config.read_text()
    assert text.count("`pybuggy-api`") == 1  # not duplicated


def test_register_annotations_round_trip_preserves_comments(tmp_path: Path) -> None:
    """register_annotations preserves comments via ruamel round-trip editing."""
    config = tmp_path / "config.yml"
    config.write_text(
        "codemanifest:\n"
        "  usages:\n"
        "    conventions: .goga/usages/conventions.md  # пользовательский\n"
    )

    register_annotations(config, _ANNOTATION_LINES)

    text = config.read_text()
    assert "# пользовательский" in text  # round-trip preserved the comment


def test_register_annotations_invalid_yaml_raises(tmp_path: Path) -> None:
    """register_annotations propagates a YAML error for an invalid existing file."""
    config = tmp_path / "config.yml"
    config.write_text("codemanifest: [unclosed")

    with pytest.raises(YAMLError):
        register_annotations(config, _ANNOTATION_LINES)


def test_register_annotations_non_map_codemanifest_raises(tmp_path: Path) -> None:
    """register_annotations raises ValueError when codemanifest is not a mapping (never overwrites)."""
    config = tmp_path / "config.yml"
    config.write_text("codemanifest: not-a-map")

    with pytest.raises(ValueError, match="not a mapping"):
        register_annotations(config, _ANNOTATION_LINES)


def test_register_annotations_non_scalar_annotations_raises(tmp_path: Path) -> None:
    """register_annotations raises ValueError when annotations exists but is not a scalar."""
    config = tmp_path / "config.yml"
    config.write_text("codemanifest:\n  annotations:\n    key: value\n")

    with pytest.raises(ValueError, match="not a scalar"):
        register_annotations(config, _ANNOTATION_LINES)


# _annotation_for (pybuggy usage stem → annotation line) tests ----------------


def test_annotation_for_known_stem_uses_hand_authored_text() -> None:
    """_annotation_for returns the hand-authored line for known pybuggy usage stems."""
    from goga_tool_pybuggy.commands.init.init import PYBUGGY_ANNOTATIONS, _annotation_for

    api_line = _annotation_for("api")
    asserts_line = _annotation_for("asserts")

    # the hand-authored line is returned verbatim, and references its usage key
    assert api_line == PYBUGGY_ANNOTATIONS["api"]
    assert asserts_line == PYBUGGY_ANNOTATIONS["asserts"]
    assert "`pybuggy-api`" in api_line
    assert "`pybuggy-asserts`" in asserts_line


def test_annotation_for_unknown_stem_uses_bare_backtick() -> None:
    """_annotation_for falls back to a bare backtick reference for an unknown future subcell."""
    from goga_tool_pybuggy.commands.init.init import _annotation_for

    assert _annotation_for("future-cell") == "`pybuggy-future-cell`"
