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
    """main should declare an --env-file option wired to _load_env_callback (env_file param)."""
    from goga_tool_pybuggy import cli, main

    env_file_param = next((p for p in main.params if p.name == "env_file"), None)
    assert env_file_param is not None
    # The eager callback must actually be registered on the option — not merely exist in
    # the module — otherwise env loading silently never fires through click's dispatch.
    assert env_file_param.callback is cli._load_env_callback


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


def test_main_env_file_applied_before_subcommand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Driving main through click applies --env-file before the subcommand runs.

    Positive coverage of the click dispatch boundary (the eager callback firing in a real
    ``runner.invoke``): ``PYBUGGY_REF`` from the .env lands in ``os.environ`` before the
    ``pull`` subcommand's handler runs. Without ``callback=_load_env_callback`` wired on
    the option, this fails (env never loads) — the one-line regression the direct-call
    tests cannot catch.
    """
    from goga_tool_pybuggy import main

    env_file = tmp_path / ".env"
    env_file.write_text("PYBUGGY_REF=v2\n")
    monkeypatch.delenv("PYBUGGY_REF", raising=False)
    monkeypatch.chdir(tmp_path)

    # Avoid a real git clone: the handler reads os.environ, which is what we assert on.
    seen: dict = {}

    def fake_run_pull(spec_name, ref=None):
        seen["pybuggy_ref"] = os.environ.get("PYBUGGY_REF")

    monkeypatch.setattr("goga_tool_pybuggy.commands.pull.pull.run_pull", fake_run_pull)

    result = CliRunner().invoke(main, ["--env-file", str(env_file), "endpoint", "pull"])

    assert result.exit_code == 0, result.output
    assert os.environ["PYBUGGY_REF"] == "v2"
    assert seen["pybuggy_ref"] == "v2"


# Integration: end-to-end ROOT→pull runtime coupling via PYBUGGY_REF (no Imports edge)


def test_load_env_then_run_pull_env_coupling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_env writes PYBUGGY_REF to os.environ, then run_pull reads it into the clone ref.

    Proves the feature's foundation — the loose ``os.environ`` bridge between the ROOT
    cell (``load_env`` applies the ``.env`` with ``override=False``) and the pull cell
    (``run_pull`` reads ``PYBUGGY_REF`` via ``_effective_ref``) with no ``Imports`` edge
    between them. Only the git-clone boundary is mocked.
    """
    from unittest.mock import patch

    from goga_tool_pybuggy import load_env
    from goga_tool_pybuggy.commands.pull import run_pull

    config_path_attr = "goga_tool_pybuggy.config.storage.CONFIG_PATH"

    env_file = tmp_path / ".env"
    env_file.write_text("PYBUGGY_REF=v2\n")
    monkeypatch.delenv("PYBUGGY_REF", raising=False)
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
"""
    )
    monkeypatch.setattr(config_path_attr, config_path)

    clone_root = tmp_path / "clone"
    (clone_root / "specs").mkdir(parents=True)
    (clone_root / "specs" / "client.yaml").write_text("spec content")

    # ROOT side: load_env applies the .env to os.environ.
    load_env(str(env_file))
    assert os.environ["PYBUGGY_REF"] == "v2"

    # Pull side: run_pull resolves PYBUGGY_REF from os.environ and clones with it.
    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        run_pull("client")

    assert mock_clone.call_count == 1
    args, _ = mock_clone.call_args
    # clone_repo(url, ref) — positional ref is the effective ref bridged via os.environ.
    assert args[1] == "v2"
