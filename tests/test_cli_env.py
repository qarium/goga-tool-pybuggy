"""Contract and logic tests for the main() --env-file eager option (cli.py)."""

import os
import types
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

# Contract tests — facade surface and the --env-file option shape.


def test_main_importable_from_facade() -> None:
    """main should be importable from the goga_tool_pybuggy facade."""
    from goga_tool_pybuggy import main

    assert main is not None


def test_main_is_click_command() -> None:
    """main should be a click BaseCommand (group or command)."""
    from goga_tool_pybuggy import main

    assert isinstance(main, click.BaseCommand)


def test_main_has_env_file_option() -> None:
    """main should declare an --env-file option (param named env_file)."""
    from goga_tool_pybuggy import main

    param_names = {p.name for p in main.params}
    assert "env_file" in param_names


def test_env_file_option_is_eager() -> None:
    """The --env-file option should be eager (fires before the subcommand)."""
    from goga_tool_pybuggy import main

    env_file_param = next(p for p in main.params if p.name == "env_file")
    assert env_file_param.is_eager is True


def test_load_env_callback_exists_in_cli_module() -> None:
    """The internal _load_env_callback helper should exist in goga_tool_pybuggy.cli."""
    from goga_tool_pybuggy import cli

    assert hasattr(cli, "_load_env_callback")
    assert callable(cli._load_env_callback)


# Logic tests — behavior.


def test_env_file_callback_sets_ctx_obj(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_load_env_callback loads .env, stores EnvContext on ctx.obj, and passes value through."""
    from goga_tool_pybuggy import EnvContext
    from goga_tool_pybuggy.cli import _load_env_callback

    env_file = tmp_path / ".env"
    env_file.write_text("PYBUGGY_REF=v2\n")
    monkeypatch.delenv("PYBUGGY_REF", raising=False)
    monkeypatch.chdir(tmp_path)

    ctx = types.SimpleNamespace(obj=None)
    value = str(env_file)

    returned = _load_env_callback(ctx, None, value)

    assert isinstance(ctx.obj, EnvContext)
    assert ctx.obj.values["PYBUGGY_REF"] == "v2"
    assert os.environ["PYBUGGY_REF"] == "v2"
    assert returned == value


def test_env_file_option_must_precede_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    """--env-file after the subcommand is a click usage error (exit 2)."""
    from goga_tool_pybuggy import main

    runner = CliRunner()
    monkeypatch.delenv("PYBUGGY_REF", raising=False)

    result = runner.invoke(main, ["endpoint", "pull", "--env-file", "x.env"])

    assert result.exit_code == 2
    assert "No such option" in result.output
