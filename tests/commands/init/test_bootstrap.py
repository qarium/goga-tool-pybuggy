"""Tests for the six bootstrap writers — contract surface, round-trip guarantees, deltas.

Covers the relocation from the 1.x ``init.py`` (four writers carried over verbatim:
``write_test_convention``, ``register_usages``, ``register_annotations``,
``write_pybuggy_conftest``) and the two migration deltas: ``ensure_review_skip``
(renamed from ``ensure_review_executor_skip``, key path ``build.review_executor.skip``
→ ``build.review.skip``) and ``install_pybuggy`` (dynamic minor x-range install line).
"""

import importlib.metadata
import importlib.resources
import logging
from pathlib import Path

import pytest
from goga_tool_pybuggy.commands.init import (
    ensure_review_skip,
    install_pybuggy,
    register_annotations,
    register_usages,
    write_pybuggy_conftest,
    write_test_convention,
)
from ruamel.yaml import YAML

_EXPECTED_CONFTEST = (
    "from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugin\n\nplugin.install()\n"
)

_USAGE_INPUT = {"pybuggy-api": "new.md", "conventions": ".goga/usages/conventions.md"}

_ANNOTATION_INPUT = {
    "pybuggy-api": "Use `pybuggy-api` for executing HTTP requests from test fixtures.",
    "conventions": "Use `conventions` for test code: pytest configuration, logging, and Allure reporting.",
}


class TestBootstrapContract:
    """Facade exposure and signature surface of the six bootstrap writers."""

    def test_facade_exports_six_bootstrap_writers(self):
        """All six writer routines are importable from the cell facade."""
        assert callable(ensure_review_skip)
        assert callable(install_pybuggy)
        assert callable(register_usages)
        assert callable(register_annotations)
        assert callable(write_pybuggy_conftest)
        assert callable(write_test_convention)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (write_test_convention, {"path": Path, "return": None}),
            (ensure_review_skip, {"config_path": Path, "return": bool}),
            (install_pybuggy, {"dockerfile_path": Path, "return": str | None}),
            (register_usages, {"config_path": Path, "usage_keys": dict[str, str], "return": list[str]}),
            (register_annotations, {"config_path": Path, "annotation_lines": dict[str, str], "return": list[str]}),
            (write_pybuggy_conftest, {"path": Path, "return": None}),
        ],
    )
    def test_writer_signature_matches_contract(self, routine, expected):
        """Every writer carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected


class TestEnsureReviewSkip:
    """``build.review.skip`` enforcement with round-trip preservation."""

    def test_ensure_review_skip_enforces_key_and_preserves_config(self, tmp_path, caplog):
        """The new key lands, comments and siblings survive, and a repeat run never writes."""
        config = tmp_path / "config.yml"
        config.write_text(
            "# keep me\nlanguage: python\nbuild:\n  task_executor:  # sibling stays\n    agent: swax\n",
            encoding="utf-8",
        )

        with caplog.at_level(logging.INFO):
            assert ensure_review_skip(config) is True

        assert "review executor skip enabled" in caplog.text
        yaml = YAML()
        data = yaml.load(config)
        assert data["build"]["review"]["skip"] is True
        assert data["build"]["task_executor"] == {"agent": "swax"}
        assert "# keep me" in config.read_text(encoding="utf-8")
        assert "# sibling stays" in config.read_text(encoding="utf-8")

        first_bytes = config.read_bytes()
        mtime = config.stat().st_mtime_ns
        assert ensure_review_skip(config) is False
        assert config.read_bytes() == first_bytes
        assert config.stat().st_mtime_ns == mtime


class TestInstallPybuggy:
    """Dynamic minor x-range install line derivation and idempotency."""

    def test_install_pybuggy_derives_minor_line_and_is_idempotent(self, tmp_path, monkeypatch, caplog):
        """The line derives from the installed version, appends once, then no-ops."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12\n", encoding="utf-8")
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")

        with caplog.at_level(logging.INFO):
            line = install_pybuggy(dockerfile)

        assert line == "RUN goga install pybuggy -v 2.0.x"
        assert dockerfile.read_text(encoding="utf-8") == "FROM python:3.12\nRUN goga install pybuggy -v 2.0.x\n"
        assert "pybuggy install line added to Dockerfile" in caplog.text

        assert install_pybuggy(dockerfile) is None
        assert dockerfile.read_text(encoding="utf-8") == "FROM python:3.12\nRUN goga install pybuggy -v 2.0.x\n"

        dockerfile.write_text("FROM python:3.12\n", encoding="utf-8")
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "1.1.1.dev4+gabc")

        assert install_pybuggy(dockerfile) == "RUN goga install pybuggy -v 1.1.x"
        assert dockerfile.read_text(encoding="utf-8") == "FROM python:3.12\nRUN goga install pybuggy -v 1.1.x\n"

    def test_install_pybuggy_noop_without_file(self, tmp_path):
        """An absent Dockerfile is a no-op — the file is never created."""
        absent = tmp_path / "Dockerfile"

        assert install_pybuggy(absent) is None
        assert not absent.exists()


class TestRegistrations:
    """Codemanifest usage/annotation registration — never-overwrite and idempotency."""

    @pytest.mark.parametrize("operation", ["usages", "annotations"])
    def test_register_usages_and_annotations_idempotent(self, tmp_path, operation):
        """First run adds/replaces exactly the missing or stale keys; the second is a no-op."""
        config = tmp_path / "config.yml"
        config.write_text(
            "codemanifest:\n"
            "  usages:\n"
            "    pybuggy-api: old.md\n"
            "  annotations: |\n"
            "    Use `pybuggy-api` stale text here\n"
            "    foreign line untouched\n",
            encoding="utf-8",
        )
        yaml = YAML()

        if operation == "usages":
            assert register_usages(config, _USAGE_INPUT) == ["conventions"]
            usages = yaml.load(config)["codemanifest"]["usages"]
            assert usages["pybuggy-api"] == "old.md"
            assert usages["conventions"] == ".goga/usages/conventions.md"
            rerun = lambda: register_usages(config, _USAGE_INPUT)  # noqa: E731
        else:
            assert register_annotations(config, _ANNOTATION_INPUT) == ["pybuggy-api", "conventions"]
            annotations = yaml.load(config)["codemanifest"]["annotations"]
            assert "Use `pybuggy-api` for executing HTTP requests" in annotations
            assert "stale text here" not in annotations
            assert "foreign line untouched" in annotations
            rerun = lambda: register_annotations(config, _ANNOTATION_INPUT)  # noqa: E731

        snapshot = config.read_text(encoding="utf-8")
        assert rerun() == []
        assert config.read_text(encoding="utf-8") == snapshot


class TestFixedAssetWriters:
    """Deterministic emission of the packaged conftest template and convention asset."""

    def test_write_pybuggy_conftest_and_test_convention_emit_fixed_assets(self, tmp_path):
        """Both writers emit their fixed sources verbatim and overwrite on every call."""
        conftest = tmp_path / "conftest.py"
        slot = tmp_path / ".goga" / "usages" / "conventions.md"

        write_pybuggy_conftest(conftest)
        write_test_convention(slot)

        assert conftest.read_text(encoding="utf-8") == _EXPECTED_CONFTEST
        packaged = (importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md").read_text(
            encoding="utf-8"
        )
        assert slot.read_text(encoding="utf-8") == packaged
        assert packaged.startswith("# Testing Convention: pytest")

        conftest.write_text("mutated", encoding="utf-8")
        slot.write_text("mutated", encoding="utf-8")

        write_pybuggy_conftest(conftest)
        write_test_convention(slot)

        assert conftest.read_text(encoding="utf-8") == _EXPECTED_CONFTEST
        assert slot.read_text(encoding="utf-8") == packaged
