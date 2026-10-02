"""Pipeline autonomy entity: one entry of the ``pipelines`` config axis."""

from pydantic import BaseModel, ConfigDict


class PipelineAutonomy(BaseModel):
    """Autonomy record of a single pipeline name (``pipelines`` axis entry).

    The dict key of the axis entry names the pipeline; the entry itself carries
    exactly one boolean member — whether that pipeline runs unattended. The
    record forbids any other member: a mistyped key fails validation instead of
    silently disabling autonomy.

    Attributes:
        autonomous: Whether the pipeline named by the entry's dict key runs
            unattended.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    autonomous: bool
