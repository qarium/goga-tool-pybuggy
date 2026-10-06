"""Shared pytest fixtures for the sandbox test package."""

import pathlib
from collections.abc import Callable

import pytest


@pytest.fixture
def sandbox_yaml(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], pathlib.Path]:
    """Write ``.sandbox.yml`` under ``tmp_path`` and chdir there.

    Args:
        tmp_path: The per-test temporary directory serving as the consumer repository root.
        monkeypatch: The pytest monkeypatch fixture performing the chdir.

    Returns:
        A writer placing ``content`` at ``.sandbox.yml`` under ``tmp_path``, returning the written path.
    """
    monkeypatch.chdir(tmp_path)

    def _write(content: str) -> pathlib.Path:
        path = tmp_path / ".sandbox.yml"
        path.write_text(content, encoding="utf-8")
        return path

    return _write
