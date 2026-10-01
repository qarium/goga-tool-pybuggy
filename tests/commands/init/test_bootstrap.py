"""Tests for the seven bootstrap writers — contract surface, round-trip guarantees, deltas.

Covers the writers relocated from the 1.x ``init.py``, the two migration deltas, and the 2.0.1 restoration.
"""

import importlib.metadata
import importlib.resources
import logging
from pathlib import Path

import pytest
from goga_tool_pybuggy.commands.init import (
    document_config_examples,
    ensure_review_skip,
    install_pybuggy,
    register_annotations,
    register_usages,
    write_pybuggy_conftest,
    write_test_convention,
)
from goga_tool_pybuggy.plugin import PluginConfigKeys
from ruamel.yaml import YAML

_EXPECTED_CONFTEST = (
    "from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugin\n\nplugin.install()\n"
)

# The exact first lines the documentation step re-delivers for absent complex members.
_HEADERS_FIRST_LINE = "headers: example (skipped complex member)"
_LOADER_FIRST_LINE = "loader: example (skipped complex member)"

_USAGE_INPUT = {"pybuggy-api": "new.md", "conventions": ".goga/usages/conventions.md"}

_ANNOTATION_INPUT = {
    "pybuggy-api": "Use `pybuggy-api` for executing HTTP requests from test fixtures.",
    "conventions": "Use `conventions` for test code: pytest configuration, logging, and Allure reporting.",
}


class TestBootstrapContract:
    """Facade exposure and signature surface of the seven bootstrap writers."""

    def test_facade_exports_seven_bootstrap_writers(self):
        """All seven writer routines are importable from the cell facade."""
        assert callable(ensure_review_skip)
        assert callable(install_pybuggy)
        assert callable(register_usages)
        assert callable(register_annotations)
        assert callable(write_pybuggy_conftest)
        assert callable(write_test_convention)
        assert callable(document_config_examples)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (write_test_convention, {"path": Path, "return": None}),
            (ensure_review_skip, {"config_path": Path, "return": bool}),
            (install_pybuggy, {"dockerfile_path": Path, "return": str | None}),
            (register_usages, {"config_path": Path, "usage_keys": dict[str, str], "return": list[str]}),
            (register_annotations, {"config_path": Path, "annotation_lines": dict[str, str], "return": list[str]}),
            (write_pybuggy_conftest, {"path": Path, "return": None}),
            (document_config_examples, {"config_path": Path, "return": list[str]}),
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

    @pytest.mark.parametrize(
        "config_text",
        [
            pytest.param("build:\n  review:\n    skip: false\n", id="explicit-false"),
            pytest.param("build:\n  review:\n    skip: maybe\n", id="non-boolean-string"),
        ],
    )
    def test_ensure_review_skip_corrects_a_present_non_true_value(self, tmp_path, config_text):
        """A present false (or non-boolean) skip value is corrected to true."""
        config = tmp_path / "config.yml"
        config.write_text(config_text, encoding="utf-8")

        assert ensure_review_skip(config) is True
        assert YAML().load(config)["build"]["review"]["skip"] is True


class TestNeverOverwriteGuards:
    """The never-overwrite guards — a non-conforming section raises instead of clobbering."""

    @pytest.mark.parametrize(
        ("config_text", "writer"),
        [
            pytest.param("build: scalar\n", ensure_review_skip, id="build-not-a-mapping"),
            pytest.param("build:\n  review: [list]\n", ensure_review_skip, id="review-not-a-mapping"),
            pytest.param(
                "codemanifest: [a, b]\n",
                lambda config: register_usages(config, _USAGE_INPUT),
                id="codemanifest-not-a-mapping",
            ),
            pytest.param(
                "codemanifest:\n  usages: scalar\n",
                lambda config: register_usages(config, _USAGE_INPUT),
                id="usages-not-a-mapping",
            ),
            pytest.param(
                "codemanifest:\n  annotations: {k: v}\n",
                lambda config: register_annotations(config, _ANNOTATION_INPUT),
                id="annotations-not-a-scalar",
            ),
        ],
    )
    def test_non_conforming_section_raises_and_keeps_file_unchanged(self, tmp_path, config_text, writer):
        """A non-mapping/non-scalar guarded section raises ValueError and leaves the file untouched."""
        config = tmp_path / "config.yml"
        config.write_text(config_text, encoding="utf-8")
        before = config.read_bytes()

        with pytest.raises(ValueError, match="cannot be extended"):
            writer(config)

        assert config.read_bytes() == before


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

    def test_install_pybuggy_ensures_newline_separator(self, tmp_path, monkeypatch):
        """A Dockerfile without a trailing newline still gets the install line on a fresh line."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12", encoding="utf-8")
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")

        assert install_pybuggy(dockerfile) == "RUN goga install pybuggy -v 2.0.x"
        assert dockerfile.read_text(encoding="utf-8") == "FROM python:3.12\nRUN goga install pybuggy -v 2.0.x\n"

    def test_install_pybuggy_noop_without_file(self, tmp_path):
        """An absent Dockerfile is a no-op — the file is never created."""
        absent = tmp_path / "Dockerfile"

        assert install_pybuggy(absent) is None
        assert not absent.exists()

    def test_install_pybuggy_missing_metadata_raises_clean_value_error(self, tmp_path, monkeypatch):
        """A metadata-less run raises ValueError (the bootstrap's wrapped tier), not a traceback."""

        def _missing(name: str) -> str:
            raise importlib.metadata.PackageNotFoundError(name)

        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12\n", encoding="utf-8")
        monkeypatch.setattr(importlib.metadata, "version", _missing)

        with pytest.raises(ValueError, match="distribution metadata not found"):
            install_pybuggy(dockerfile)

        assert dockerfile.read_text(encoding="utf-8") == "FROM python:3.12\n"


class TestDocumentConfigExamples:
    """The commented example records — the 1.x option surface restored post-session."""

    def test_document_adds_records_in_key_order_with_specs_anchor(self, tmp_path):
        """Absent members land as commented records pinned before the next active key / specs."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://{{ HOST }}/api\ntimeout: 30.0\nspecs:\n"
            "  shop:\n    type: swagger\n    location: specs/shop.yaml\n",
            encoding="utf-8",
        )

        documented = document_config_examples(config)

        assert [record.split("\n", 1)[0] for record in documented] == [
            _HEADERS_FIRST_LINE,
            "retries: (skipped optional scalar)",
            _LOADER_FIRST_LINE,
            "assert_timeout: (skipped optional scalar)",
            "assert_delay: (skipped optional scalar)",
            "assert_field_class: (skipped optional scalar)",
            "assert_response_class: (skipped optional scalar)",
        ]
        text = config.read_text(encoding="utf-8")
        assert text == (
            "base_url: https://{{ HOST }}/api\n"
            f"# {_HEADERS_FIRST_LINE}\n"
            "#   X-Example: value\n"
            "#   default request headers dict\n"
            "timeout: 30.0\n"
            "# retries: (skipped optional scalar)\n"
            f"# {_LOADER_FIRST_LINE}\n"
            "#   packages:\n"
            "#     - api\n"
            "#   modules: []\n"
            "# assert_timeout: (skipped optional scalar)\n"
            "# assert_delay: (skipped optional scalar)\n"
            "# assert_field_class: (skipped optional scalar)\n"
            "# assert_response_class: (skipped optional scalar)\n"
            "specs:\n"
            "  shop:\n"
            "    type: swagger\n"
            "    location: specs/shop.yaml\n"
        )

    def test_document_is_idempotent_and_preserves_active_values(self, tmp_path):
        """A repeat run adds nothing, and the active keys keep their values throughout."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://{{ HOST }}/api\ntimeout: 30.0\nretries: 3\nspecs:\n"
            "  shop:\n    type: swagger\n    location: specs/shop.yaml\n",
            encoding="utf-8",
        )

        assert document_config_examples(config) != []
        snapshot = config.read_text(encoding="utf-8")

        assert document_config_examples(config) == []
        assert config.read_text(encoding="utf-8") == snapshot

        data = YAML().load(config)
        assert data["timeout"] == 30.0
        assert data["retries"] == 3
        assert data["specs"]["shop"] == {"type": "swagger", "location": "specs/shop.yaml"}
        assert "headers" not in data
        assert "loader" not in data

    def test_document_pins_pending_records_before_midway_active_key(self, tmp_path):
        """Records accumulate only up to the next active key — mid-walk anchors split the blocks."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://x\nretries: 3\nspecs:\n  shop:\n    type: swagger\n    location: s.yaml\n",
            encoding="utf-8",
        )

        document_config_examples(config)

        text = config.read_text(encoding="utf-8")
        headers_at = text.index(f"# {_HEADERS_FIRST_LINE}")
        timeout_at = text.index("# timeout: (skipped optional scalar)")
        retries_at = text.index("retries: 3")
        loader_at = text.index(f"# {_LOADER_FIRST_LINE}")
        specs_at = text.index("specs:")
        assert headers_at < timeout_at < retries_at < loader_at < specs_at

    def test_document_active_member_never_gains_a_record(self, tmp_path):
        """A member the user activated (headers hand-added) is documented nowhere."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://x\nheaders:\n  X-Api-Key: k\nspecs:\n  shop:\n    type: swagger\n    location: s.yaml\n",
            encoding="utf-8",
        )

        documented = document_config_examples(config)

        assert _HEADERS_FIRST_LINE not in "\n".join(documented)
        assert f"# {_HEADERS_FIRST_LINE}" not in config.read_text(encoding="utf-8")
        assert any(record.startswith("timeout:") for record in documented)

    def test_document_noop_without_file_or_mapping(self, tmp_path):
        """An absent config and a non-mapping document are no-ops."""
        absent = tmp_path / "config.yml"
        assert document_config_examples(absent) == []
        assert not absent.exists()

        scalar = tmp_path / "scalar.yml"
        scalar.write_text("just a string\n", encoding="utf-8")
        assert document_config_examples(scalar) == []
        assert scalar.read_text(encoding="utf-8") == "just a string\n"

    def test_document_covers_every_plugin_member(self, tmp_path):
        """The walk is data-driven — every PluginConfigKeys member gets its record shape."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://x\nspecs:\n  shop:\n    type: swagger\n    location: s.yaml\n", encoding="utf-8"
        )

        document_config_examples(config)

        text = config.read_text(encoding="utf-8")
        for member in PluginConfigKeys:
            if member in (PluginConfigKeys.BASE_URL, PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER):
                continue

            assert f"# {member.value}: (skipped optional scalar)" in text

        assert f"# {_HEADERS_FIRST_LINE}" in text
        assert f"# {_LOADER_FIRST_LINE}" in text
        assert "# base_url:" not in text


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

    def test_register_annotations_appends_after_plain_scalar_without_trailing_newline(self, tmp_path):
        """A plain-scalar annotations value gains the line on a fresh line, then no-ops."""
        config = tmp_path / "config.yml"
        config.write_text("codemanifest:\n  annotations: some text", encoding="utf-8")

        assert register_annotations(config, {"pybuggy-api": "Use `pybuggy-api` for requests."}) == ["pybuggy-api"]
        assert YAML().load(config)["codemanifest"]["annotations"] == "some text\nUse `pybuggy-api` for requests.\n"
        assert register_annotations(config, {"pybuggy-api": "Use `pybuggy-api` for requests."}) == []

    def test_register_annotations_replaces_only_the_first_matching_line(self, tmp_path):
        """When several lines carry the same backtick reference, exactly the first is replaced."""
        config = tmp_path / "config.yml"
        config.write_text(
            "codemanifest:\n  annotations: |\n    old `pybuggy-api` line\n    another `pybuggy-api` line\n",
            encoding="utf-8",
        )

        assert register_annotations(config, {"pybuggy-api": "Use `pybuggy-api` for requests."}) == ["pybuggy-api"]

        annotations = YAML().load(config)["codemanifest"]["annotations"]
        assert annotations == "Use `pybuggy-api` for requests.\nanother `pybuggy-api` line\n"

    @pytest.mark.parametrize(
        ("operation", "config_text"),
        [
            pytest.param("usages", None, id="usages-absent-file"),
            pytest.param("usages", "", id="usages-empty-file"),
            pytest.param("annotations", None, id="annotations-absent-file"),
            pytest.param("annotations", "", id="annotations-empty-file"),
        ],
    )
    def test_registrations_create_minimal_document_when_no_file(self, tmp_path, operation, config_text):
        """An absent or zero-byte config gets a minimal document carrying the registrations."""
        config = tmp_path / "config.yml"
        if config_text is not None:
            config.write_text(config_text, encoding="utf-8")

        yaml = YAML()

        if operation == "usages":
            assert register_usages(config, _USAGE_INPUT) == ["pybuggy-api", "conventions"]
            assert yaml.load(config)["codemanifest"]["usages"] == _USAGE_INPUT
        else:
            assert register_annotations(config, _ANNOTATION_INPUT) == ["pybuggy-api", "conventions"]

            annotations = yaml.load(config)["codemanifest"]["annotations"]
            assert "Use `pybuggy-api` for executing HTTP requests" in annotations
            assert "`conventions`" in annotations


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
