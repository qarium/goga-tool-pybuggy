"""Shared pytest fixtures for the pybuggy test suite."""

import os
import pathlib
from collections.abc import Callable

import pytest


@pytest.fixture(autouse=True)
def _isolate_os_environ() -> None:
    """Snapshot os.environ, scrub pybuggy-owned vars, and restore afterward.

    ``load_env`` writes os.environ directly, invisible to ``monkeypatch``; the snapshot restore is authoritative.
    """
    snapshot = os.environ.copy()
    # Scrub the host ``PYBUGGY_REF`` — it flips ``pull_cmd``'s ``--ref`` envvar resolution.
    os.environ.pop("PYBUGGY_REF", None)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)


@pytest.fixture
def tool_config(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], pathlib.Path]:
    """Write a pybuggy tool config under the standard tree, rooted at ``tmp_path``.

    Chdirs into ``tmp_path`` so the cwd-relative standard path is exercised with zero patching.

    Args:
        tmp_path: The per-test temporary directory serving as the project root.
        monkeypatch: The pytest monkeypatch fixture performing the chdir.

    Returns:
        A writer placing ``text`` at the standard tool-config path, returning the written path.
    """
    monkeypatch.chdir(tmp_path)

    def _write(text: str) -> pathlib.Path:
        path = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _write
