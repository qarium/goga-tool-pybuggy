"""The autonomous workflow document — the fixed contribution of a qualifying run.

Seven-stage auto-approval window ending at ``commit-changes``, plus the build stage after it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # the platform document type — reached at call time in the builder
    from goga.pipeline.workflow import WorkflowDocument

_WINDOW_STAGES = (
    "review-testcases",
    "create-testcases",
    "code-design",
    "design-review",
    "coding-plan",
    "plan-review",
    "commit-changes",
)

_BUILD_NAME = "build"
_BUILD_TITLE = "Build tests"
_BUILD_SCRIPT = 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'
_BUILD_AFTER_SCRIPT = "rm -rf .ralphex"
_BUILD_TIMEOUT = "8h"
_BUILD_AFTER = ("commit-changes",)


def build_autonomous_workflow() -> WorkflowDocument:
    """Build the declarative autonomy contribution from the compile-time constants.

    All seven window stages carry ``approve: "auto"``; the acceptance stage is never included.

    Returns:
        A :class:`WorkflowDocument` with the ``stages`` overrides plus the single ``extend`` entry.
    """
    # Call-time import keeps goga out of the module's import-time dependencies.
    from goga.pipeline.workflow import (  # noqa: PLC0415
        WorkflowDocument,
        WorkflowExtendStage,
        WorkflowStage,
    )

    stages = {name: WorkflowStage(approve="auto") for name in _WINDOW_STAGES}

    build_entry = WorkflowExtendStage(
        after=list(_BUILD_AFTER),
        body={
            "title": _BUILD_TITLE,
            "script": _BUILD_SCRIPT,
            "after_script": _BUILD_AFTER_SCRIPT,
            "timeout": _BUILD_TIMEOUT,
        },
    )

    return WorkflowDocument(stages=stages, extend={_BUILD_NAME: build_entry})
