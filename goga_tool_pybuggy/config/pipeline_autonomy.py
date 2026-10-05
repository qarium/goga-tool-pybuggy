"""Pipeline autonomy entity: one entry of the ``pipelines`` config axis."""

from pydantic import BaseModel, ConfigDict


class PipelineAutonomy(BaseModel):
    """Autonomy record of a single pipeline name (``pipelines`` axis entry).

    Extra members fail validation, so a mistyped key cannot silently disable autonomy.

    Attributes:
        autonomous: Whether the pipeline named by the entry's dict key runs
            unattended.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    autonomous: bool
