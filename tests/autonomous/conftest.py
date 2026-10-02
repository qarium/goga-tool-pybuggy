"""Local fixtures for the autonomous cell tests — the amendment view double."""

import pytest
from goga.pipeline.hooks.identity import PipelineIdentity

# The discovered identity of the autonomy target, exactly as the platform
# delivers it at the amendment checkpoint — a PipelineIdentity carrying the
# installer's namespaced tool-pipeline name, never a bare string.
_AUTONOMOUS_PIPELINE = PipelineIdentity(
    name="pybuggy:api.automate",
    description="Pybuggy API-test automate lifecycle",
    source="user",
)


def amendment_identity(name: str) -> PipelineIdentity:
    """Build a platform pipeline identity for the amendment-view double.

    Args:
        name: The discovered pipeline name the view reports.

    Returns:
        A ``PipelineIdentity`` shaped like the platform's amendment delivery.
    """
    return PipelineIdentity(name=name, description="", source="user")


class _AmendmentView:
    """Amendment view double capturing the contributed documents.

    Mirrors the platform's ``WorkflowAmendment`` read-and-contribute
    contract: ``pipeline`` is the ``PipelineIdentity`` of the running
    pipeline (the delivery hands the dataclass, never a bare string), and
    ``contribute`` buffers one document per call.

    Attributes:
        pipeline: The identity of the running pipeline the view reports.
        contributed: The documents passed to ``contribute``, in call order.
    """

    def __init__(self, pipeline: PipelineIdentity) -> None:
        self.pipeline = pipeline
        self.contributed: list[object] = []

    def contribute(self, document: object) -> None:
        """Buffer one contribution exactly as the platform delivers it.

        Args:
            document: The ``WorkflowDocument`` contributed by the hook.
        """
        self.contributed.append(document)


@pytest.fixture
def amendment_view() -> _AmendmentView:
    """A fresh amendment view double reporting the autonomy-target pipeline."""
    return _AmendmentView(_AUTONOMOUS_PIPELINE)
