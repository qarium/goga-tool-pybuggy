"""Shared pytest fixtures for the pybuggy test suite.

Stub module — extended with shared fixtures as cells are implemented.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_os_environ() -> None:
    """Snapshot os.environ before a test and restore it afterward.

    ``load_env`` applies a ``.env`` to ``os.environ`` via ``load_dotenv``, which writes
    the real process environment directly — those writes are invisible to ``monkeypatch``
    (which only reverts its own ``setenv``/``delenv`` calls) and would otherwise leak
    across tests (e.g. a leaked ``PYBUGGY_REF`` changes ``_effective_ref`` resolution for
    later ``pull`` tests). Restoring the full snapshot makes isolation authoritative
    regardless of teardown ordering: ``monkeypatch`` only reverts keys it set, never
    re-adding them, so it cannot undo this restore.
    """
    snapshot = os.environ.copy()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)
