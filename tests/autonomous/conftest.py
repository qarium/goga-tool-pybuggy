"""Local fixtures for the autonomous cell tests — the amendment view double."""

import pytest


class _AmendmentView:
    """Amendment view double capturing the contributed documents.

    Attributes:
        pipeline: The identity of the running pipeline the view reports.
        contributed: The documents passed to ``contribute``, in call order.
    """

    def __init__(self, pipeline: str) -> None:
        self.pipeline = pipeline
        self.contributed: list[dict[str, object]] = []

    def contribute(self, document: dict[str, object]) -> None:
        """Buffer one contribution exactly as the platform delivers it.

        Args:
            document: The WorkflowDocument-shaped mapping contributed by the hook.
        """
        self.contributed.append(document)


@pytest.fixture
def amendment_view() -> _AmendmentView:
    """A fresh amendment view double reporting the ``api.automate`` pipeline."""
    return _AmendmentView("api.automate")
