"""The workflow amendment hook — the autonomy contribution moment.

Contributes pybuggy's autonomous-run instructions when the running pipeline
is ``pybuggy:api.automate`` and autonomy is enabled in the tool config; every
other pipeline and every disabled state is a silent no-op. Errors propagate
untouched — the platform stops the command with a clean error naming pybuggy
and discards the whole contribution.
"""

from ..config import resolve_autonomy
from .workflow import build_autonomous_workflow

# The discovered identity of the only pipeline the autonomous window applies
# to — the installer namespaces tool pipelines as ``<tool>:<name>``, so the
# platform discovers the package's ``api.automate.yml`` as
# ``pybuggy:api.automate``.
_PIPELINE = "pybuggy:api.automate"

# The ``pipelines``-axis key naming the same pipeline in the tool config —
# the tool's own vocabulary, the key the init confirm writes.
_AXIS = "api.automate"


def amend_workflow(context: object) -> None:
    """Contribute the autonomous workflow amendment when the run qualifies.

    Reads the identity of the running pipeline from the amendment view — a
    platform ``PipelineIdentity``, gated by its discovered name — resolves
    autonomy through the tool config, and — only when enabled — buffers the
    fixed workflow document through the view. Every disqualifying state
    contributes nothing and raises nothing.

    Args:
        context: The amendment view delivered by the platform — the identity
            of the running pipeline and the contribute buffer.

    Raises:
        ValueError: Propagated from the autonomy resolver on a structural
            violation of the tool config (never dampened into a no-op).
        yaml.YAMLError: Propagated from the autonomy resolver on an invalid
            tool config file.
    """
    pipeline = context.pipeline

    if pipeline.name != _PIPELINE:
        return

    enabled = resolve_autonomy(_AXIS)

    if not enabled:
        return

    context.contribute(build_autonomous_workflow())
