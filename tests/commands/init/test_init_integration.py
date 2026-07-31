"""Integration tests for the init command composition.

End-to-end scenarios through the full chain ``init_cmd`` (Click wrapper) →
``run_init`` (handler) → ``run_goga_init`` / ``register_usages`` / discovery,
plus the top-level command registration in ``pybuggy.cli``. They complement —
and do not replace — the contract and logic tests in ``test_init.py``.
"""

from pathlib import Path
from unittest import mock

import click.testing
import pytest
import yaml
from pybuggy.commands.init import init_cmd

# End-to-end through the Click wrapper ---------------------------------------


def test_init_cmd_end_to_end_fresh_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_cmd drives the full chain on a fresh project: goga init then usages registered."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("pybuggy.commands.init.init.run_goga_init", lambda: 0)

    runner = click.testing.CliRunner()
    result = runner.invoke(init_cmd, [])

    assert result.exit_code == 0
    assert (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()
    assert (tmp_path / ".goga/usages/cooks/pybuggy/asserts.md").exists()

    cfg = yaml.safe_load((tmp_path / ".goga/config.yml").read_text())
    usages = cfg["codemanifest"]["usages"]
    assert "pybuggy-api" in usages
    assert "pybuggy-asserts" in usages


def test_init_cmd_propagates_goga_cancel_without_writing_usages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A goga-init cancel is propagated by the wrapper; no usages are written."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("pybuggy.commands.init.init.run_goga_init", lambda: 1)

    runner = click.testing.CliRunner()
    result = runner.invoke(init_cmd, [])

    assert result.exit_code == 1
    assert not (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()


def test_init_cmd_maps_bootstrap_failure_to_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bootstrap file-write failure surfaces as a non-zero exit through the wrapper."""
    config = tmp_path / ".goga" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("codemanifest:\n  usages: {}\n")
    monkeypatch.chdir(tmp_path)

    runner = click.testing.CliRunner()
    with mock.patch("pybuggy.commands.init.init.Path.write_text", side_effect=OSError("denied")):
        result = runner.invoke(init_cmd, [])

    assert result.exit_code != 0


# Top-level command registration --------------------------------------------


def test_init_cmd_registered_top_level_on_main() -> None:
    """init_cmd is registered under the name 'init' on the pybuggy main group."""
    from pybuggy.cli import main

    assert "init" in main.commands
    assert main.commands["init"] is init_cmd
