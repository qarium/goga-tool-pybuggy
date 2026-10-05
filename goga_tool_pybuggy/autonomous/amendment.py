"""The workflow amendment hook — the autonomy contribution moment.

Contributes only on pipeline ``pybuggy:api.automate`` with autonomy enabled; every other state is a silent no-op.
"""

from ..config import resolve_autonomy
from .workflow import build_autonomous_workflow

# The installer namespaces tool pipelines as ``<tool>:<name>``, so the package's
# ``api.automate.yml`` is discovered as ``pybuggy:api.automate``.
_PIPELINE = "pybuggy:api.automate"

# The ``pipelines``-axis key naming the same pipeline in the tool config.
_AXIS = "api.automate"


def amend_workflow(context: object) -> None:
    """Contribute the autonomous workflow amendment when the run qualifies.

    Disqualifying states contribute nothing and raise nothing.

    Args:
        context: The platform amendment view — pipeline identity plus the contribute buffer.

    Raises:
        ValueError: Propagated from the autonomy resolver on a structural tool-config violation.
        yaml.YAMLError: Propagated from the autonomy resolver on an invalid tool-config file.
    """
    pipeline = context.pipeline

    if pipeline.name != _PIPELINE:
        return

    enabled = resolve_autonomy(_AXIS)

    if not enabled:
        return

    context.contribute(build_autonomous_workflow())
