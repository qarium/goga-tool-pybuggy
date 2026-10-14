"""The compile-time contribution table — one ``PipelineContribution`` record per qualifying pipeline."""

from pydantic import BaseModel, ConfigDict


class PipelineContribution(BaseModel):
    """Compile-time record of one pipeline's autonomy contribution.

    Extra members fail validation, so a mistyped record key fails at import time — before any
    hook can fire — instead of silently disabling autonomy.

    Attributes:
        identity: The qualifying run identity — the installer-namespaced pipeline name the
            platform delivers (e.g. ``pybuggy:api.patch``).
        axis: The tool-config ``pipelines``-axis key of the pipeline (e.g. ``api.patch``).
        window: The ordered stage names that carry the auto-approval directive.
        build_artifact: The topic artifact the build stage builds (e.g. ``workplan.md``).
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    identity: str
    axis: str
    window: list[str]
    build_artifact: str


AUTOMATE_CONTRIBUTION = PipelineContribution(
    identity="pybuggy:api.automate",
    axis="api.automate",
    window=(
        "review-testcases",
        "create-testcases",
        "code-design",
        "design-review",
        "coding-plan",
        "plan-review",
        "commit-changes",
    ),
    build_artifact="plan.md",
)

PATCH_CONTRIBUTION = PipelineContribution(
    identity="pybuggy:api.patch",
    axis="api.patch",
    window=(
        "review-impact",
        "apply-manifests",
        "code-design",
        "design-review",
        "coding-plan",
        "plan-review",
        "commit-changes",
    ),
    build_artifact="workplan.md",
)

CONTRIBUTIONS = (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)
