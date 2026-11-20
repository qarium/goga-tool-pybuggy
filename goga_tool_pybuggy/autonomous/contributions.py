"""The compile-time contribution table — one ``PipelineContribution`` record per qualifying pipeline."""

from pydantic import BaseModel, ConfigDict, Field


class PipelineContribution(BaseModel):
    """Compile-time record of one pipeline's autonomy contribution.

    Extra members fail validation, so a mistyped record key fails at import time — before any
    hook can fire — instead of silently disabling autonomy.

    Attributes:
        identity: The qualifying run identity — the installer-namespaced pipeline name the
            platform delivers (e.g. ``pybuggy:api.patch``).
        axis: The tool-config ``pipelines``-axis key of the pipeline (e.g. ``api.patch``).
        config_file: The tool-config file the axis lives in (``api.yml`` / ``web.yml``) —
            the kind's own document.
        window: The ordered stage names that carry the auto-approval directive — never
            empty: the build stage anchors at its last entry.
        build_artifact: The topic artifact the build stage builds (e.g. ``workplan.md``).
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    identity: str
    axis: str
    config_file: str
    window: list[str] = Field(min_length=1)
    build_artifact: str


AUTOMATE_CONTRIBUTION = PipelineContribution(
    identity="pybuggy:api.automate",
    axis="api.automate",
    config_file="api.yml",
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
    config_file="api.yml",
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

WEB_AUTOMATE_CONTRIBUTION = PipelineContribution(
    identity="pybuggy:web.automate",
    axis="web.automate",
    config_file="web.yml",
    window=(
        "testcases-review",
        "code-design",
        "design-review",
        "coding-plan",
        "plan-review",
        "commit-changes",
    ),
    build_artifact="plan.md",
)

CONTRIBUTIONS = (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION, WEB_AUTOMATE_CONTRIBUTION)
