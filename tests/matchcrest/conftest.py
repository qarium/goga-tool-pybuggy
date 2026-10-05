"""Shared fixtures for the matchcrest test suite."""

import pytest
from goga_tool_pybuggy.matchcrest.matchers import BaseContext


class ValueContext(BaseContext):
    """Concrete ``BaseContext`` wrapping a plain value, for matcher tests.

    Matchers read the value under test from ``item.value``; ``item.key`` is a message label; ``update()`` is a no-op.
    """

    def __init__(self, value, key="src"):
        self._value = value
        self._key = key

    @property
    def value(self):
        """Returns the wrapped value under test."""
        return self._value

    @property
    def key(self):
        """Returns the message label attached to the context."""
        return self._key

    def update(self):
        """A no-op refresh — the wrapped value never changes."""
        pass


@pytest.fixture
def ctx():
    """Factory building a ``ValueContext``: ``ctx(value, key='src')``."""

    def _make(value, key="src"):
        return ValueContext(value, key)

    return _make
