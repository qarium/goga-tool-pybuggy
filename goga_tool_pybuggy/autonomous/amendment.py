"""The workflow amendment hook — the autonomy contribution moment.

Contributes the record's document on a qualifying pipeline with autonomy enabled; every other state is a silent no-op.
"""

from ..config import resolve_autonomy
from .contributions import CONTRIBUTIONS
from .workflow import build_autonomous_workflow


def amend_workflow(context: object) -> None:
    """Contribute the autonomous workflow amendment when the run qualifies.

    The record whose identity equals the discovered pipeline name drives qualification, axis routing, and the
    contributed document; disqualifying states contribute nothing and raise nothing.

    Args:
        context: The platform amendment view — pipeline identity plus the contribute buffer.

    Raises:
        ValueError: Propagated from the autonomy resolver on a structural tool-config violation.
        yaml.YAMLError: Propagated from the autonomy resolver on an invalid tool-config file.
    """
    pipeline = context.pipeline

    contribution = next((c for c in CONTRIBUTIONS if c.identity == pipeline.name), None)

    if contribution is None:
        return

    enabled = resolve_autonomy(contribution.axis)

    if not enabled:
        return

    context.contribute(build_autonomous_workflow(contribution))
