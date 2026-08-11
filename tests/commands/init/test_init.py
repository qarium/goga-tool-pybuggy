"""Contract and logic tests for run_init / register_usages / init_cmd handler."""

import typing
from pathlib import Path
from unittest import mock

import click
import click.testing
import pytest
import yaml
from goga_tool_pybuggy.commands.init import (
    build_pybuggy_config,
    init_cmd,
    install_pybuggy,
    register_annotations,
    register_usages,
    run_goga_init,
    run_init,
    write_pybuggy_config,
)
from goga_tool_pybuggy.config import GitEntry, SpecEntry
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
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)

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
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)

    run_init()

    assert (tmp_path / ".goga/usages/cooks/pybuggy/asserts.md").exists()


def test_run_init_in_initialized_project_skips_goga_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On an already-initialized project run_init asks to recreate goga config; declining skips run_goga_init."""
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages:\n    conventions: .goga/usages/conventions.md\n")
    monkeypatch.chdir(tmp_path)
    run_goga_init_spy = mock.Mock(return_value=0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", run_goga_init_spy)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))  # decline goga recreate

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
    """A second run_init (both recreates declined) overwrites copied files and skips keys — no diff."""
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages:\n    conventions: .goga/usages/conventions.md\n")
    monkeypatch.chdir(tmp_path)
    run_goga_init_spy = mock.Mock(return_value=0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", run_goga_init_spy)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))  # decline both recreates

    run_init()
    before = config.read_text()

    run_init()
    after = config.read_text()

    assert run_goga_init_spy.call_count == 0
    assert before == after


def test_run_init_recreates_goga_config_on_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When .goga/config.yml exists and the user confirms, run_init re-runs run_goga_init (overwrites)."""
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages:\n    conventions: .goga/usages/conventions.md\n")
    monkeypatch.chdir(tmp_path)
    run_goga_init_spy = mock.Mock(return_value=0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", run_goga_init_spy)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=True))  # accept goga recreate

    assert run_init() == 0

    assert run_goga_init_spy.call_count == 1


def test_run_init_rebuilds_pybuggy_config_on_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the pybuggy tool config exists and the user confirms, run_init rebuilds it."""
    (tmp_path / ".goga" / "tools" / "pybuggy").mkdir(parents=True)
    (tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml").write_text("base_url: stale\n")
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages:\n    conventions: .goga/usages/conventions.md\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 0)
    build_spy = mock.Mock(return_value=0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", build_spy)
    # decline goga recreate, accept pybuggy rebuild
    monkeypatch.setattr(click, "confirm", mock.Mock(side_effect=[False, True]))

    assert run_init() == 0

    assert build_spy.call_count == 1


def test_run_init_skips_pybuggy_rebuild_on_decline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the pybuggy tool config exists and the user declines, run_init skips build_pybuggy_config."""
    (tmp_path / ".goga" / "tools" / "pybuggy").mkdir(parents=True)
    (tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml").write_text("base_url: stale\n")
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages:\n    conventions: .goga/usages/conventions.md\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 0)
    build_spy = mock.Mock(return_value=0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", build_spy)
    # decline both recreates
    monkeypatch.setattr(click, "confirm", mock.Mock(side_effect=[False, False]))

    assert run_init() == 0

    assert build_spy.call_count == 0


def test_run_init_maps_bootstrap_failure_to_click_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_init should map a file-write failure to click.ClickException."""
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages: {}\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))  # decline goga recreate

    with (
        mock.patch("goga_tool_pybuggy.commands.init.init.Path.write_text", side_effect=OSError("denied")),
        pytest.raises(click.ClickException),
    ):
        run_init()


def test_run_init_propagates_config_build_failure_without_registering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-zero build_pybuggy_config exit code is returned without registering any usages.

    Step 3 short-circuits run_init on a non-zero config-build code: no usages are discovered/copied and
    register_usages is never called (scenario C — early return before the discovery block).
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 1)
    register_spy = mock.Mock(wraps=register_usages)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.register_usages", register_spy)

    assert run_init() == 1

    assert register_spy.call_count == 0
    assert not (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()


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
    # ask_dockerfile_path is intentionally NOT stubbed here — run_goga_init hardcodes the
    # mandatory Dockerfile path and never calls ask_dockerfile_path.
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
    """run_goga_init assembles GogaConfigAnswers from the per-field answers and feeds InitAnswers.

    ``dockerfile_path`` is the hardcoded mandatory path (``_DOCKERFILE_PATH``), not the return
    value of goga's optional ``ask_dockerfile_path`` (which is never called).
    """
    from goga_tool_pybuggy.commands.init.init import _DOCKERFILE_PATH

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
        dockerfile_path=_DOCKERFILE_PATH,
        codemanifest_usages=questionnaire.ask_codemanifest_usages.return_value,
        codemanifest_annotations=questionnaire.ask_codemanifest_annotations.return_value,
    )
    answers_spy.assert_called_once_with(goga_config=config_spy.return_value)
    generator.generate.assert_called_once_with(answers_spy.return_value)


def test_run_goga_init_hardcodes_mandatory_dockerfile_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_goga_init makes the Dockerfile mandatory.

    The Dockerfile path is the hardcoded ``_DOCKERFILE_PATH`` (never ``None``, so ``FileGenerator``
    always creates the Dockerfile and always emits the top-level ``dockerfile`` config field), and
    goga's optional ``ask_dockerfile_path`` is never called.
    """
    from goga_tool_pybuggy.commands.init.init import _DOCKERFILE_PATH

    questionnaire = _stub_questionnaire(monkeypatch)
    generator = mock.Mock()
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.FileGenerator", mock.Mock(return_value=generator))

    assert run_goga_init() == 0

    questionnaire.ask_dockerfile_path.assert_not_called()
    answers = generator.generate.call_args.args[0]
    assert answers.goga_config.dockerfile_path == _DOCKERFILE_PATH
    assert answers.goga_config.dockerfile_path is not None


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


def test_run_goga_init_calls_install_pybuggy_after_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_goga_init pins the running pybuggy version by calling install_pybuggy after generate."""
    from goga_tool_pybuggy.commands.init.init import _DOCKERFILE_PATH

    _stub_questionnaire(monkeypatch)
    generator = mock.Mock()
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.FileGenerator", mock.Mock(return_value=generator))
    install_spy = mock.Mock(return_value=None)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.install_pybuggy", install_spy)

    assert run_goga_init() == 0

    generator.generate.assert_called_once()
    install_spy.assert_called_once_with(Path(_DOCKERFILE_PATH))


# install_pybuggy contract tests ---------------------------------------------


def test_install_pybuggy_importable_from_facade() -> None:
    """install_pybuggy should be importable from the goga_tool_pybuggy.commands.init facade."""
    from goga_tool_pybuggy.commands.init import install_pybuggy as imported

    assert imported is install_pybuggy


def test_install_pybuggy_is_public_in_facade() -> None:
    """install_pybuggy is exposed on the facade __all__ (public test seam)."""
    from goga_tool_pybuggy.commands.init import __all__ as facade_all

    assert "install_pybuggy" in facade_all


def test_install_pybuggy_signature() -> None:
    """install_pybuggy takes only a dockerfile path (the install line is hardcoded, no version override)."""
    import inspect

    sig = inspect.signature(install_pybuggy)

    assert list(sig.parameters) == ["dockerfile_path"]


# install_pybuggy logic tests ------------------------------------------------


def test_install_pybuggy_appends_hardcoded_line(tmp_path: Path) -> None:
    """install_pybuggy appends the hardcoded `RUN goga install pybuggy -v 0.1.x` line to the Dockerfile."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM qarium/goga-python-3.12:1.1\n", encoding="utf-8")

    returned = install_pybuggy(dockerfile)

    expected = "RUN goga install pybuggy -v 0.1.x\n"
    assert returned == expected

    text = dockerfile.read_text(encoding="utf-8")
    assert text.startswith("FROM qarium/goga-python-3.12:1.1\n")
    assert text.endswith(expected)


def test_install_pybuggy_noop_when_file_absent(tmp_path: Path) -> None:
    """install_pybuggy is a no-op (None, nothing written) when the Dockerfile does not exist."""
    dockerfile = tmp_path / "Dockerfile"

    assert install_pybuggy(dockerfile) is None
    assert not dockerfile.exists()


def test_install_pybuggy_is_idempotent(tmp_path: Path) -> None:
    """install_pybuggy appends the line once even when called repeatedly on the same file."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM image:tag\n", encoding="utf-8")

    first = install_pybuggy(dockerfile)
    second = install_pybuggy(dockerfile)

    assert first is not None
    assert second is None
    assert dockerfile.read_text(encoding="utf-8").count("goga install") == 1


def test_install_pybuggy_ensures_newline_separator(tmp_path: Path) -> None:
    """install_pybuggy inserts a newline before the RUN line when the file lacks a trailing one."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM image:tag", encoding="utf-8")  # no trailing newline

    install_pybuggy(dockerfile)

    assert dockerfile.read_text(encoding="utf-8") == "FROM image:tag\nRUN goga install pybuggy -v 0.1.x\n"


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


# write_pybuggy_config contract tests -----------------------------------------


def test_write_pybuggy_config_importable_from_facade() -> None:
    """write_pybuggy_config should be importable from the goga_tool_pybuggy.commands.init facade."""
    from goga_tool_pybuggy.commands.init import write_pybuggy_config as imported

    assert imported is write_pybuggy_config


def test_write_pybuggy_config_is_public_in_facade() -> None:
    """write_pybuggy_config is exposed on the facade __all__ (public contract)."""
    from goga_tool_pybuggy.commands.init import __all__ as facade_all

    assert "write_pybuggy_config" in facade_all


def test_write_pybuggy_config_signature() -> None:
    """write_pybuggy_config has signature (path, scalar_values, specs)."""
    params = write_pybuggy_config.__code__.co_varnames[: write_pybuggy_config.__code__.co_argcount]

    assert params == ("path", "scalar_values", "specs")


# build_pybuggy_config contract tests -----------------------------------------


def test_build_pybuggy_config_in_all_public_and_returns_int() -> None:
    """build_pybuggy_config is importable from the facade, in __all__, and takes no args."""
    from goga_tool_pybuggy.commands.init import build_pybuggy_config as imported

    assert imported is build_pybuggy_config
    from goga_tool_pybuggy.commands.init import __all__ as facade_all

    assert "build_pybuggy_config" in facade_all
    assert build_pybuggy_config.__code__.co_argcount == 0


# write_pybuggy_config logic tests --------------------------------------------

# The 9 scalar plugin members (enum minus the complex HEADERS/LOADER), in declaration order.
_ALL_SCALAR_KEYS = [
    "base_url",
    "timeout",
    "data_key",
    "error_key",
    "retries",
    "assert_timeout",
    "assert_delay",
    "assert_field_class",
    "assert_response_class",
]


def _spec_entry(git: bool = False) -> SpecEntry:
    """Build a deterministic SpecEntry, optionally with a git source."""
    if git:
        return SpecEntry(
            type="openapi",
            location="specs/api.yaml",
            git=GitEntry(url="https://example.com/specs.git", location="api.yaml", ref="main"),
        )
    return SpecEntry(type="openapi", location="specs/api.yaml")


def test_write_pybuggy_config_all_scalars_answered_emits_active_and_commented_complex(
    tmp_path: Path,
) -> None:
    """All 9 scalars answered + specs: complex headers/loader still commented, scalars active.

    Numeric scalars (``timeout``/``retries``/``assert_timeout``/``assert_delay``) are emitted as
    numbers matching their ``ApiPlugin`` option types; the remaining string scalars stay strings.
    """
    scalar_values = {key: f"v-{key}" for key in _ALL_SCALAR_KEYS}
    scalar_values["base_url"] = "https://{{ host }}/api"
    # numeric members must carry valid numbers for their ApiPlugin option types (int/float)
    scalar_values["timeout"] = "30"
    scalar_values["retries"] = "2"
    scalar_values["assert_timeout"] = "10"
    scalar_values["assert_delay"] = "0.5"
    config = tmp_path / "config.yml"

    write_pybuggy_config(config, scalar_values, {"api": _spec_entry()})

    text = config.read_text()
    assert "base_url:" in text
    assert "# required, Jinja2 template" in text  # eol comment on base_url
    assert "# headers:" in text  # complex member still emitted as a commented example
    assert "# loader:" in text
    assert "specs:" in text  # active specs section

    cfg = yaml.safe_load(text)
    assert set(cfg) == set(_ALL_SCALAR_KEYS) | {"specs"}
    # numeric scalars emitted as numbers, not quoted strings
    assert isinstance(cfg["timeout"], float)
    assert cfg["timeout"] == 30.0
    assert isinstance(cfg["retries"], int)
    assert cfg["retries"] == 2
    assert isinstance(cfg["assert_timeout"], int)
    assert cfg["assert_timeout"] == 10
    assert isinstance(cfg["assert_delay"], float)
    assert cfg["assert_delay"] == 0.5
    # the remaining answered scalars stay plain strings
    assert isinstance(cfg["data_key"], str)
    assert cfg["data_key"] == "v-data_key"

    from goga_tool_pybuggy.config import load_config

    load_config(config)  # validates against Config (ignores scalar plugin keys)


def test_write_pybuggy_config_skipped_scalars_become_commented_records(tmp_path: Path) -> None:
    """Only base_url answered: the 8 optional scalars become '# <skipped>: (skipped ...)' records."""
    config = tmp_path / "config.yml"

    write_pybuggy_config(config, {"base_url": "https://{{ host }}/api"}, {"api": _spec_entry()})

    text = config.read_text()
    optional_keys = [k for k in _ALL_SCALAR_KEYS if k != "base_url"]
    for key in optional_keys:
        assert f"# {key}: (skipped optional scalar)" in text
    assert "# headers:" in text
    assert "# loader:" in text
    assert text.index("# loader:") < text.index("specs:")  # trailing buffer pinned before specs

    cfg = yaml.safe_load(text)
    assert set(cfg) == {"base_url", "specs"}


def test_write_pybuggy_config_spec_with_git_emits_git_block(tmp_path: Path) -> None:
    """A SpecEntry carrying a GitEntry emits an active git block round-tripping through load_config."""
    config = tmp_path / "config.yml"

    write_pybuggy_config(config, {"base_url": "https://{{ host }}/api"}, {"api": _spec_entry(git=True)})

    text = config.read_text()
    assert "git:" in text
    assert "url: https://example.com/specs.git" in text
    assert "location: api.yaml" in text
    assert "ref: main" in text

    from goga_tool_pybuggy.config import load_config

    cfg = load_config(config)
    assert cfg.specs["api"].git is not None
    assert cfg.specs["api"].git.url == "https://example.com/specs.git"
    assert cfg.specs["api"].git.location == "api.yaml"
    assert cfg.specs["api"].git.ref == "main"


def test_write_pybuggy_config_spec_git_ref_none_comments_ref(tmp_path: Path) -> None:
    """A git source without a ref emits no active ``ref`` key; ref is documented as ``# ref:``.

    The commented ``ref`` is placed on its own indented line after ``location`` (the post-value
    comment slot — the slot ruamel's own loader uses for trailing comments; the eol/``after`` slots
    are dropped on the last key of a block mapping). It is NOT an end-of-line comment on
    ``location``, and no empty active ``ref:`` key is produced. The file round-trips through
    ``load_config`` with ``git.ref`` resolving to ``None``.
    """
    config = tmp_path / "config.yml"
    specs = {
        "api": SpecEntry(
            type="openapi",
            location="specs/api.yaml",
            git=GitEntry(url="https://example.com/specs.git", location="api.yaml", ref=None),
        )
    }

    write_pybuggy_config(config, {"base_url": "https://{{ host }}/api"}, specs)

    text = config.read_text()
    assert "location: api.yaml  # ref:" not in text  # not an end-of-line comment on location
    assert "location: api.yaml\n      # ref:\n" in text  # standalone indented line after location
    cfg = yaml.safe_load(text)
    assert "ref" not in cfg["specs"]["api"]["git"]  # no active ref key

    from goga_tool_pybuggy.config import load_config

    parsed = load_config(config)
    assert parsed.specs["api"].git is not None
    assert parsed.specs["api"].git.ref is None


def test_write_pybuggy_config_long_git_url_not_wrapped(tmp_path: Path) -> None:
    """A long git clone URL stays on one line (best_width raised so ruamel does not fold it)."""
    config = tmp_path / "config.yml"
    url = "git@gitlab.wildberries.ru:taxi/taxi/qa/platform/golang/services/traffic/insts/mock.git"
    specs = {
        "api": SpecEntry(
            type="openapi",
            location="specs/api.yaml",
            git=GitEntry(url=url, location="api.yaml", ref="main"),
        )
    }

    write_pybuggy_config(config, {"base_url": "https://{{ host }}/api"}, specs)

    text = config.read_text()
    assert f"url: {url}\n" in text  # url value on the same line as the key, not folded to a new line

    from goga_tool_pybuggy.config import load_config

    assert load_config(config).specs["api"].git.url == url


def test_write_pybuggy_config_is_deterministic(tmp_path: Path) -> None:
    """Two calls with identical inputs and order produce byte-identical output."""
    scalar_values = {"base_url": "https://{{ host }}/api", "timeout": "30", "data_key": "data"}
    specs = {"api": _spec_entry(), "admin": _spec_entry(git=True)}
    one = tmp_path / "one.yml"
    two = tmp_path / "two.yml"

    write_pybuggy_config(one, scalar_values, specs)
    write_pybuggy_config(two, scalar_values, specs)

    assert one.read_text() == two.read_text()


def test_write_pybuggy_config_creates_parent_dir(tmp_path: Path) -> None:
    """The destination parent directory tree is created when missing; load_config then passes."""
    config = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
    assert not config.parent.exists()

    write_pybuggy_config(config, {"base_url": "https://{{ host }}/api"}, {"api": _spec_entry()})

    assert config.exists()
    assert config.parent.is_dir()

    from goga_tool_pybuggy.config import load_config

    load_config(config)


def test_write_pybuggy_config_base_url_jinja_template_block_scalar(tmp_path: Path) -> None:
    """A Jinja2 base_url is emitted as a literal block scalar with the {{ }} preserved verbatim."""
    config = tmp_path / "config.yml"

    write_pybuggy_config(config, {"base_url": "https://{{ host }}/api"}, {"api": _spec_entry()})

    text = config.read_text()
    assert "base_url: |" in text  # clip indicator
    assert "base_url: |-" not in text  # no strip dash
    assert "{{ host }}" in text  # template preserved
    cfg = yaml.safe_load(text)
    assert cfg["base_url"].rstrip("\n") == "https://{{ host }}/api"  # round-trip (trailing \n is the clip marker)


def test_write_pybuggy_config_multiline_base_url_emits_block_scalar(tmp_path: Path) -> None:
    """A multi-line base_url template is emitted as a literal block scalar (``|``), losslessly."""
    config = tmp_path / "config.yml"
    base_url = (
        "http://taxi-ingress-controller.taxi.k8s.dev-el/qa-platform-mock\n"
        '{% if match_re("^feature-.*$", service_version) %}-{{ service_version }}\n'
        "{% endif %}"
    )

    write_pybuggy_config(config, {"base_url": base_url}, {"api": _spec_entry()})

    text = config.read_text()
    assert "base_url: |" in text  # clip indicator
    assert "base_url: |-" not in text  # no strip dash
    assert "# required, Jinja2 template" in text  # marker kept (own line above the key)
    # each template line preserved verbatim, indented under the block
    assert "  http://taxi-ingress-controller.taxi.k8s.dev-el/qa-platform-mock" in text

    cfg = yaml.safe_load(text)
    assert cfg["base_url"].rstrip("\n") == base_url  # round-trip (trailing \n is the clip marker)

    from goga_tool_pybuggy.config import load_config

    load_config(config)  # validates against Config (ignores scalar plugin keys)


def test_write_pybuggy_config_long_single_line_base_url_not_wrapped(tmp_path: Path) -> None:
    """A long single-line base_url stays on one block-scalar line (ruamel does not line-wrap it)."""
    config = tmp_path / "config.yml"
    base_url = (
        "http://taxi-ingress-controller.taxi.k8s.dev-el/qa-platform-mock"
        '{% if match_re("^feature-.*$", service_version) %}-{{ service_version }}'
        "{% endif %}"
    )

    write_pybuggy_config(config, {"base_url": base_url}, {"api": _spec_entry()})

    text = config.read_text()
    assert "base_url: |" in text  # clip indicator
    assert "base_url: |-" not in text  # no strip dash
    # the whole template sits on a single indented block line — not wrapped across several
    assert f"  {base_url}" in text

    cfg = yaml.safe_load(text)
    assert cfg["base_url"].rstrip("\n") == base_url  # round-trip, unwrapped (trailing \n is the clip marker)


def test_write_pybuggy_config_multiple_specs_preserve_order(tmp_path: Path) -> None:
    """Multiple specs are emitted in insertion order."""
    config = tmp_path / "config.yml"
    specs = {"api": _spec_entry(), "admin": _spec_entry(git=True)}

    write_pybuggy_config(config, {"base_url": "https://{{ host }}/api"}, specs)

    text = config.read_text()
    assert text.index("api:") < text.index("admin:")


# build_pybuggy_config logic tests --------------------------------------------


def test_build_pybuggy_config_overwrites_existing_without_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing tool config is always overwritten — no existence check, no overwrite confirmation."""
    config = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("base_url: stale\nspecs: {}\n")  # pre-existing content to replace
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))  # git declined; never an overwrite prompt
    monkeypatch.setattr(
        click,
        "prompt",
        mock.Mock(
            side_effect=[
                "https://{{ host }}/api",  # base_url (required)
                *_OPTIONAL_SCALAR_EMPTIES,  # 8 optional scalars -> None
                "api",  # first spec name (required)
                "openapi",  # type (click.Choice)
                "specs/api.yaml",  # location (required)
                "",  # second spec name (empty to finish) -> break
            ]
        ),
    )

    assert build_pybuggy_config() == 0

    text = config.read_text()
    assert "stale" not in text  # previous content replaced
    assert "base_url: |" in text  # regenerated from the prompted answers


def test_build_pybuggy_config_returns_nonzero_on_abort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A click.Abort during prompting returns non-zero without raising (scenario C).

    With the overwrite confirmation removed, cancellation surfaces from the interactive prompts
    (here the first ``base_url`` prompt); it is never raised — ``build_pybuggy_config`` returns a
    code.
    """
    monkeypatch.chdir(tmp_path)  # no existing config
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))  # git source declined
    monkeypatch.setattr(click, "prompt", mock.Mock(side_effect=click.Abort()))  # abort at first prompt

    rc = build_pybuggy_config()

    assert rc != 0  # never raises; cancellation surfaces as a non-zero code


def test_build_pybuggy_config_returns_nonzero_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure inside write_pybuggy_config is logged/echoed and returns non-zero without raising."""
    monkeypatch.chdir(tmp_path)  # no existing config → overwrite confirm skipped
    # git confirm answered 'no' so no extra prompts are consumed inside _ask_spec
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))
    monkeypatch.setattr(
        click,
        "prompt",
        mock.Mock(
            side_effect=[
                "https://{{ host }}/api",  # base_url (required)
                "",  # timeout -> None
                "",  # data_key -> None
                "",  # error_key -> None
                "",  # retries -> None
                "",  # assert_timeout -> None
                "",  # assert_delay -> None
                "",  # assert_field_class -> None
                "",  # assert_response_class -> None
                "api",  # first spec name (required)
                "openapi",  # type (click.Choice)
                "specs/api.yaml",  # location (required)
                "",  # second spec name (empty to finish) -> break
            ]
        ),
    )
    monkeypatch.setattr(
        "goga_tool_pybuggy.commands.init.init.write_pybuggy_config",
        mock.Mock(side_effect=RuntimeError("boom")),
    )
    logger = mock.Mock()
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.logger", logger)
    echo = mock.Mock()
    monkeypatch.setattr(click, "echo", echo)

    rc = build_pybuggy_config()

    assert rc != 0  # failure surfaces as non-zero, never raises
    logger.error.assert_called_once()
    echo.assert_called_once()
    assert "boom" in echo.call_args.args[0]


# The 8 optional scalar plugin members (everything except base_url, HEADERS, LOADER), in declaration
# order. Empty answers map to ``None`` (a skipped commented record).
_OPTIONAL_SCALAR_EMPTIES = [""] * 8


def _prompt_texts(prompt_mock: mock.Mock) -> list[str]:
    """Collect the first positional arg (the prompt text) of every prompt_mock call."""
    return [c.args[0] for c in prompt_mock.call_args_list if c.args]


def test_build_pybuggy_config_reprompts_empty_required_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty base_url is re-prompted (echoing 'base_url is required') until a non-empty value is given."""
    monkeypatch.chdir(tmp_path)  # no existing config -> overwrite confirm skipped
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))  # git source declined
    prompt = mock.Mock(
        side_effect=[
            "",  # base_url empty -> re-prompt
            "https://{{ host }}/api",  # base_url valid
            *_OPTIONAL_SCALAR_EMPTIES,  # 8 optional scalars -> None
            "api",  # first spec name
            "openapi",  # type
            "specs/api.yaml",  # location
            "",  # second spec name -> finish
        ]
    )
    monkeypatch.setattr(click, "prompt", prompt)
    echo = mock.Mock()
    monkeypatch.setattr(click, "echo", echo)

    assert build_pybuggy_config() == 0

    # the re-prompt body executed: the 'is required' message was echoed
    echoed = " ".join(c.args[0] for c in echo.call_args_list if c.args)
    assert "base_url is required" in echoed
    # and the valid (not empty) base_url landed in the emitted config
    config = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
    raw = yaml.safe_load(config.read_text())
    assert raw["base_url"].rstrip("\n") == "https://{{ host }}/api"  # trailing \n is the clip marker


def test_build_pybuggy_config_reprompts_empty_required_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty spec location is re-prompted via 'location (required)' until a non-empty value is given."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))
    prompt = mock.Mock(
        side_effect=[
            "https://{{ host }}/api",  # base_url
            *_OPTIONAL_SCALAR_EMPTIES,  # 8 optional scalars -> None
            "api",  # first spec name
            "openapi",  # type
            "",  # location empty -> re-prompt
            "specs/api.yaml",  # location valid
            "",  # second spec name -> finish
        ]
    )
    monkeypatch.setattr(click, "prompt", prompt)

    assert build_pybuggy_config() == 0

    # the re-prompt fired: the descriptive '(required)' prompt variant was invoked
    assert "location — path from the project root to the spec file (required)" in _prompt_texts(prompt)
    from goga_tool_pybuggy.config import load_config

    cfg = load_config(tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml")
    assert cfg.specs["api"].location == "specs/api.yaml"


def test_build_pybuggy_config_reprompts_empty_required_first_spec_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty first spec name is re-prompted via 'spec name (required)' until a non-empty value is given."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))
    prompt = mock.Mock(
        side_effect=[
            "https://{{ host }}/api",  # base_url
            *_OPTIONAL_SCALAR_EMPTIES,  # 8 optional scalars -> None
            "",  # first spec name empty -> re-prompt
            "api",  # first spec name valid
            "openapi",  # type
            "specs/api.yaml",  # location
            "",  # second spec name -> finish
        ]
    )
    monkeypatch.setattr(click, "prompt", prompt)

    assert build_pybuggy_config() == 0

    assert "spec name — unique name for this spec (required)" in _prompt_texts(prompt)
    from goga_tool_pybuggy.config import load_config

    cfg = load_config(tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml")
    assert "api" in cfg.specs


def test_build_pybuggy_config_reprompts_whitespace_git_url_and_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whitespace-only git url/location are re-prompted until non-empty (mirrors the required location)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=True))  # git source added
    prompt = mock.Mock(
        side_effect=[
            "https://{{ host }}/api",  # base_url
            *_OPTIONAL_SCALAR_EMPTIES,  # 8 optional scalars -> None
            "api",  # first spec name
            "openapi",  # type
            "specs/api.yaml",  # location
            "   ",  # git url whitespace -> re-prompt
            "https://example.com/specs.git",  # git url valid
            "  ",  # git location whitespace -> re-prompt
            "api.yaml",  # git location valid
            "",  # git ref (optional) -> None
            "",  # second spec name -> finish
        ]
    )
    monkeypatch.setattr(click, "prompt", prompt)

    assert build_pybuggy_config() == 0

    texts = _prompt_texts(prompt)
    assert "git url — clone URL of the repository holding the spec (required)" in texts
    assert "git location — path inside the repository to the spec file (required)" in texts
    from goga_tool_pybuggy.config import load_config

    git = load_config(tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml").specs["api"].git
    assert git is not None
    assert git.url == "https://example.com/specs.git"
    assert git.location == "api.yaml"
    assert git.ref is None  # empty ref coerced to None


def test_build_pybuggy_config_base_url_emitted_as_block_scalar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single-line base_url is emitted as a | block scalar (not a wrapped plain scalar)."""
    monkeypatch.chdir(tmp_path)  # no existing config -> overwrite confirm skipped
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=False))  # no git source
    base_url = (
        "http://taxi-ingress-controller.taxi.k8s.dev-el/qa-platform-mock"
        '{% if service_version is match_re("^feature-.*$") %}-{{ service_version }}'
        "{% endif %}"
    )
    monkeypatch.setattr(
        click,
        "prompt",
        mock.Mock(
            side_effect=[
                base_url,  # base_url (required)
                *_OPTIONAL_SCALAR_EMPTIES,  # 8 optional scalars -> None
                "api",  # first spec name
                "openapi",  # type
                "specs/api.yaml",  # location
                "",  # second spec name -> finish
            ]
        ),
    )

    assert build_pybuggy_config() == 0

    config = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
    text = config.read_text()
    assert "base_url: |" in text
    assert "base_url: |-" not in text
    assert f"  {base_url}" in text  # one indented block line — not wrapped
    raw = yaml.safe_load(text)
    assert raw["base_url"].rstrip("\n") == base_url

