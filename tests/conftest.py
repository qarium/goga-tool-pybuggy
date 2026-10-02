"""Shared pytest fixtures for the pybuggy test suite."""

import os
import pathlib
from collections.abc import Callable

import pytest


@pytest.fixture(autouse=True)
def _isolate_os_environ() -> None:
    """Snapshot os.environ, scrub pybuggy-owned vars, and restore afterward.

    ``load_env`` applies a ``.env`` to ``os.environ`` via ``load_dotenv``, which writes
    the real process environment directly — those writes are invisible to ``monkeypatch``
    (which only reverts its own ``setenv``/``delenv`` calls) and would otherwise leak
    across tests (e.g. a leaked ``PYBUGGY_REF`` changes ``pull_cmd``'s ``--ref`` envvar
    resolution for later ``pull`` CLI tests). Restoring the full snapshot makes isolation
    authoritative regardless of teardown ordering: ``monkeypatch`` only reverts keys it
    set, never re-adding them, so it cannot undo this restore. ``PYBUGGY_REF`` is also
    scrubbed at setup so a host shell exporting it does not flip fall-through ``pull`` tests.
    """
    snapshot = os.environ.copy()
    # ``PYBUGGY_REF`` is pybuggy-owned and materially changes ``pull_cmd``'s ``--ref``
    # envvar resolution (read from ``os.environ`` by click). Scrub the host value so tests
    # are deterministic regardless of the ambient environment — e.g. a developer or CI
    # shell with ``export PYBUGGY_REF=v2`` would otherwise flip fall-through pull CLI tests.
    os.environ.pop("PYBUGGY_REF", None)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)


@pytest.fixture
def tool_config(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], pathlib.Path]:
    """Write a pybuggy tool config under the standard tree, rooted at ``tmp_path``.

    Chdirs into ``tmp_path`` so the platform facade's cwd-relative composition
    (``<cwd>/.goga/tools/pybuggy/config.yml``) is exercised with zero patching:
    the routines under test resolve the real path against the test's own root.

    Args:
        tmp_path: The per-test temporary directory serving as the project root.
        monkeypatch: The pytest monkeypatch fixture performing the chdir.

    Returns:
        A writer placing ``text`` at the standard tool-config path and
        returning the written path.
    """
    monkeypatch.chdir(tmp_path)

    def _write(text: str) -> pathlib.Path:
        path = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _write
