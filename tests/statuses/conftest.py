"""Local fixtures for the statuses cell tests — the registration surface double."""

import pytest


class _RecorderContext:
    """Registration surface double capturing every register call with its anchors.

    Attributes:
        calls: The ``(name, artifact, after, before)`` tuples, in call order.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None, str | None]] = []

    def register(self, name: str, artifact: str, after: str | None = None, before: str | None = None) -> None:
        """Record one registration exactly as the platform delivers it.

        Args:
            name: The registered status name (no tool prefix — the platform assigns identity).
            artifact: The topic artifact path the status tracks.
            after: The anchor the status sits above.
            before: The anchor the status must stay below.
        """
        self.calls.append((name, artifact, after, before))


@pytest.fixture
def recorder_context() -> _RecorderContext:
    """A fresh registration surface double per test."""
    return _RecorderContext()
