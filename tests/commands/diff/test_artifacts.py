"""Contract and logic tests for sanitize_id / orphan_artifact_dirs."""

from pathlib import Path

import goga_tool_pybuggy.commands.diff
import pytest
from goga_tool_pybuggy.commands.diff import orphan_artifact_dirs, sanitize_id
from goga_tool_pybuggy.spec import Endpoint


def _endpoint(method: str, path: str) -> Endpoint:
    """Build a minimal kw_only Endpoint for segment computation."""
    return Endpoint(
        method=method,
        path=path,
        request={},
        response={},
        query_params={},
        path_params={},
        description="d",
    )


# Contract tests ---------------------------------------------------------------


def test_sanitize_id_importable_and_signature() -> None:
    """sanitize_id is importable from the cell facade as (endpoint_id) -> str."""
    params = sanitize_id.__code__.co_varnames[: sanitize_id.__code__.co_argcount]

    assert params == ("endpoint_id",)
    assert sanitize_id.__annotations__["return"] is str
    assert sanitize_id.__annotations__["endpoint_id"] is str


def test_orphan_artifact_dirs_importable_and_signature() -> None:
    """orphan_artifact_dirs is importable from the cell facade as (api_spec_dir, endpoints) -> list[Path]."""
    params = orphan_artifact_dirs.__code__.co_varnames[: orphan_artifact_dirs.__code__.co_argcount]

    assert params == ("api_spec_dir", "endpoints")
    assert orphan_artifact_dirs.__annotations__["return"] == list[Path]


def test_artifacts_routines_listed_in_facade_all() -> None:
    """The commands/diff facade exports both artifacts routines and keeps __all__ sorted."""
    assert "sanitize_id" in goga_tool_pybuggy.commands.diff.__all__
    assert "orphan_artifact_dirs" in goga_tool_pybuggy.commands.diff.__all__
    assert goga_tool_pybuggy.commands.diff.__all__ == sorted(goga_tool_pybuggy.commands.diff.__all__)


# Logic tests ------------------------------------------------------------------


def test_sanitize_id_replaces_non_word_and_prefixes_digit() -> None:
    """Non-word characters become "_" and a leading digit gets a "_" prefix."""
    assert sanitize_id("v1.0_clients_get") == "v1_0_clients_get"
    assert sanitize_id("2fa_verify_get") == "_2fa_verify_get"
    assert sanitize_id("clients_startup_get") == "clients_startup_get"


def test_sanitize_id_preserves_unicode_word_chars() -> None:
    """Unicode word characters (e.g. Cyrillic) survive sanitization untouched."""
    assert sanitize_id("клиенты_получить_get") == "клиенты_получить_get"


def test_sanitize_id_pure_no_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """sanitize_id never touches the filesystem — Path discovery/reading is never reached."""

    def _fail(*args: object, **kwargs: object) -> object:
        raise AssertionError("sanitize_id must not access the filesystem")

    monkeypatch.setattr(Path, "iterdir", _fail)
    monkeypatch.setattr(Path, "read_text", _fail)
    monkeypatch.setattr("builtins.open", _fail)

    assert sanitize_id("clients_startup_get") == "clients_startup_get"


def test_orphan_artifact_dirs_absent_tree_returns_empty(tmp_path: Path) -> None:
    """An absent api tree is a normal case — no orphans, no error."""
    result = orphan_artifact_dirs(tmp_path / "api" / "client", [])

    assert result == []


def test_orphan_artifact_dirs_ignores_files_and_sorts(tmp_path: Path) -> None:
    """Files never count as orphans; uncovered directories are reported sorted by name."""
    api_spec_dir = tmp_path / "api" / "client"
    (api_spec_dir / "b_get").mkdir(parents=True)
    (api_spec_dir / "a_legacy").mkdir()
    (api_spec_dir / "__init__.py").write_text("")

    result = orphan_artifact_dirs(api_spec_dir, [_endpoint("get", "/b")])

    assert result == [tmp_path / "api" / "client" / "a_legacy"]


def test_orphan_artifact_dirs_ignores_tooling_directories(tmp_path: Path) -> None:
    """__pycache__ and hidden directories are never reported as removed endpoints.

    Importing the generated fixture package (the documented generate -> test
    workflow) leaves ``api/<spec>/__pycache__`` behind; treating it as an
    orphan would make the report fail on a healthy tree.
    """
    api_spec_dir = tmp_path / "api" / "client"
    (api_spec_dir / "b_get").mkdir(parents=True)
    (api_spec_dir / "__pycache__").mkdir()
    (api_spec_dir / ".venv").mkdir()
    (api_spec_dir / "a_legacy").mkdir()

    result = orphan_artifact_dirs(api_spec_dir, [_endpoint("get", "/b")])

    assert result == [tmp_path / "api" / "client" / "a_legacy"]
