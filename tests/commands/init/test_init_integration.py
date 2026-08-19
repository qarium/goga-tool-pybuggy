"""Integration tests for the init command composition.

End-to-end scenarios through the full chain ``init_cmd`` (Click wrapper) →
``run_init`` (handler) → ``run_goga_init`` / ``register_usages`` / discovery,
plus the top-level command registration in ``goga_tool_pybuggy.cli``. They complement —
and do not replace — the contract and logic tests in ``test_init.py``.
"""

from pathlib import Path
from unittest import mock

import click
import click.testing
import pytest
import yaml
from goga_tool_pybuggy.commands.init import build_pybuggy_config, init_cmd, write_pybuggy_config
from goga_tool_pybuggy.config import GitEntry, SpecEntry, load_config

# Fixed conftest template (single source: the write_pybuggy_conftest CODEMANIFEST annotation).
EXPECTED_CONFTEST = (
    "from dotenv import load_dotenv\n"
    "\n"
    "load_dotenv()\n"
    "\n"
    "from goga_tool_pybuggy import plugin\n"
    "\n"
    "plugin.install()\n"
)

# End-to-end through the Click wrapper ---------------------------------------


def test_init_cmd_end_to_end_fresh_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_cmd drives the full chain on a fresh project: goga init then usages registered."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)

    runner = click.testing.CliRunner()
    result = runner.invoke(init_cmd, [])

    assert result.exit_code == 0
    assert (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()
    assert (tmp_path / ".goga/usages/cooks/pybuggy/asserts.md").exists()

    cfg = yaml.safe_load((tmp_path / ".goga/config.yml").read_text())
    usages = cfg["codemanifest"]["usages"]
    assert "pybuggy-api" in usages
    assert "pybuggy-asserts" in usages


def test_init_cmd_end_to_end_writes_conftest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_cmd writes the root conftest.py verbatim; absent file means no confirm is asked."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 0)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)

    runner = click.testing.CliRunner()
    result = runner.invoke(init_cmd, [])

    assert result.exit_code == 0
    assert (tmp_path / "conftest.py").read_text(encoding="utf-8") == EXPECTED_CONFTEST


def test_init_cmd_propagates_goga_cancel_without_writing_usages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A goga-init cancel is propagated by the wrapper; no usages are written."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 1)

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
    monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)

    runner = click.testing.CliRunner()
    with mock.patch("goga_tool_pybuggy.commands.init.init.Path.write_text", side_effect=OSError("denied")):
        result = runner.invoke(init_cmd, [])

    assert result.exit_code != 0


# Top-level command registration --------------------------------------------


def test_init_cmd_registered_top_level_on_main() -> None:
    """init_cmd is registered under the name 'init' on the pybuggy main group."""
    from goga_tool_pybuggy.cli import main

    assert "init" in main.commands
    assert main.commands["init"] is init_cmd


# Cross-cell (init ↔ config) and full-chain (interactive → emit → validate) ----


def test_write_pybuggy_config_emits_config_cell_validates_with_git(tmp_path: Path) -> None:
    """write_pybuggy_config emits a document the config cell validates, including a git source.

    Cross-cell Interface↔Interface contract: the init emitter produces a YAML document whose
    ``specs`` section round-trips through ``load_config`` → ``Config`` exactly, including a
    ``GitEntry`` source (the strictest ``SpecEntry`` form), while the scalar plugin keys stay as
    extra keys ignored by ``Config`` (``extra="ignore"``). The destination parent tree is created.
    """
    config = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
    scalar_values = {
        "base_url": "https://{{ host }}/api",
        "timeout": "30",
        # data_key / error_key / retries / assert_* left out -> None (skipped commented records)
    }
    specs = {
        "api": SpecEntry(
            type="openapi",
            location="specs/api.yaml",
            git=GitEntry(url="https://example.com/specs.git", location="api.yaml", ref="main"),
        )
    }

    write_pybuggy_config(config, scalar_values, specs)

    cfg = load_config(config)

    api = cfg.specs["api"]
    assert api.type == "openapi"
    assert api.location == "specs/api.yaml"
    assert api.git is not None
    assert api.git.url == "https://example.com/specs.git"
    assert api.git.location == "api.yaml"
    assert api.git.ref == "main"

    # scalar plugin keys are emitted into the file but not surfaced on Config (extra="ignore").
    raw = yaml.safe_load(config.read_text())
    assert {"base_url", "timeout"} <= set(raw)
    assert not hasattr(cfg, "base_url")
    assert not hasattr(cfg, "timeout")


def test_build_pybuggy_config_full_chain_validates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real build_pybuggy_config with a stubbed TTY emits a config that validates end-to-end.

    Full chain interactive → emission → validation: the testable-seam, driven by scripted
    ``click.prompt``/``click.confirm`` answers, writes the canonical config path; no file exists
    beforehand so the overwrite confirmation is skipped, and the git source is confirmed so the full
    ``SpecEntry``/``GitEntry`` form is exercised. ``load_config`` then validates the emitted file.
    """
    monkeypatch.chdir(tmp_path)
    # config file absent -> overwrite confirm skipped; git confirm answered 'yes'.
    monkeypatch.setattr(click, "confirm", mock.Mock(return_value=True))
    monkeypatch.setattr(
        click,
        "prompt",
        mock.Mock(
            side_effect=[
                "https://{{ host }}/api",  # base_url (required)
                "30",  # timeout
                "",  # data_key -> None
                "errors",  # error_key
                "",  # retries -> None
                "",  # assert_timeout -> None
                "",  # assert_delay -> None
                "",  # assert_field_class -> None
                "",  # assert_response_class -> None
                "api",  # first spec name (required)
                "openapi",  # type (click.Choice)
                "specs/api.yaml",  # location (required)
                # git source confirmed 'yes':
                "https://example.com/specs.git",  # git url
                "api.yaml",  # git location
                "main",  # git ref (optional)
                "",  # second spec name (empty to finish) -> break
            ]
        ),
    )

    assert build_pybuggy_config() == 0

    config = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
    assert config.exists()

    cfg = load_config(config)
    api = cfg.specs["api"]
    assert api.type == "openapi"
    assert api.location == "specs/api.yaml"
    assert api.git is not None
    assert api.git.url == "https://example.com/specs.git"
    assert api.git.location == "api.yaml"
    assert api.git.ref == "main"
