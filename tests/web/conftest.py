"""Local fixtures of the web cell test tree."""

import logging
import pathlib
from collections.abc import Callable

import pytest


@pytest.fixture(autouse=True)
def _restore_prettyplay_logger():
    """Snapshot and restore the process-global ``prettyplay`` logger around every web test.

    ``WebPlugin.configure`` installs the event-log formatter on that logger; without the restore
    the stdout handler and the INFO level leak out of the tests that drive ``configure`` into
    every later test of the session.

    Yields:
        Nothing — the restore runs after the test.
    """
    logger = logging.getLogger("prettyplay")
    handlers_before = logger.handlers[:]
    level_before = logger.level

    yield

    logger.handlers[:] = handlers_before
    logger.setLevel(level_before)


@pytest.fixture
def web_config(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], pathlib.Path]:
    """Write a pybuggy web config under the standard tree, rooted at ``tmp_path``.

    Chdirs into ``tmp_path`` so the cwd-relative standard path is exercised with zero patching.

    Args:
        tmp_path: The per-test temporary directory serving as the project root.
        monkeypatch: The pytest monkeypatch fixture performing the chdir.

    Returns:
        A writer placing ``text`` at the standard web-config path, returning the written path.
    """
    monkeypatch.chdir(tmp_path)

    def _write(text: str) -> pathlib.Path:
        path = tmp_path / ".goga" / "tools" / "pybuggy" / "web.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _write
