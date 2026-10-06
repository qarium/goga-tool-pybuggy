"""Shared pytest fixtures for the data cell tests."""

import pytest
from goga_tool_pybuggy.sandbox.data import DataBatch
from goga_tool_pybuggy.sandbox.engines import DataOperation, InstanceAddress


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``pybuggy_services`` marker for the local decorator tests.

    Consumers get the same registration from the sandbox sessionstart hook; without it,
    exercising the decorator inside this suite would emit ``PytestUnknownMarkWarning``.
    """
    config.addinivalue_line("markers", "pybuggy_services: per-test sandbox data presets")


class RecordingBatch(DataBatch):
    """``DataBatch`` double recording every ``add`` call.

    The record proves declaration-only behavior: one ``add`` per view call and nothing
    else — ``DataBatch`` exposes no execution surface, so no other interaction exists.
    """

    def __init__(self) -> None:
        """Initialize the recorder with an empty record."""
        super().__init__()
        self.added: list[DataOperation] = []

    def add(self, operation: DataOperation) -> None:
        """Record the operation, then accumulate it through the base behavior.

        Args:
            operation: The declared operation to record.
        """
        self.added.append(operation)

        super().add(operation)


@pytest.fixture
def recording_batch() -> RecordingBatch:
    """A fresh recording batch bound to no view."""
    return RecordingBatch()


@pytest.fixture
def address() -> InstanceAddress:
    """A sample mapped instance address."""
    return InstanceAddress(host="127.0.0.5", port=5432)
