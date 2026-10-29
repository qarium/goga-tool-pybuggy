"""Local fixtures of the web cell test tree."""

import logging

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
