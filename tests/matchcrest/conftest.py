"""Shared fixtures for the matchcrest test suite."""

import pytest
from goga_tool_pybuggy.matchcrest.matchers import BaseContext


class ValueContext(BaseContext):
    """Concrete ``BaseContext`` wrapping a plain value, for matcher tests.

    The matchers read the value under test from ``item.value`` and use ``item.key``
    only as a label in messages. ``update()`` is a no-op retry hook.
    """

    def __init__(self, value, key="src"):
        self._value = value
        self._key = key

    @property
    def value(self):
        return self._value

    @property
    def key(self):
        return self._key

    def update(self):
        pass


@pytest.fixture
def ctx():
    """Factory building a ``ValueContext``: ``ctx(value, key='src')``."""

    def _make(value, key="src"):
        return ValueContext(value, key)

    return _make
