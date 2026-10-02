"""The autonomous workflow document — the fixed contribution of a qualifying run.

Compile-time constants of the autonomy contribution: the seven-stage
auto-approval window ending at ``commit-changes`` and the build stage added
after it. The module is a pure leaf — it imports nothing at module scope and
performs no I/O; the builder assembles the constants into the platform's
``WorkflowDocument``, equal on every call.
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

    Assembles the fixed auto-approval window — each of the seven stages
    carries the ``approve: "auto"`` directive — and the build extend entry
    positioned after ``commit-changes``: the topic plan build with its
    scratch-tree cleanup script and the eight-hour timeout. The acceptance
    stage is never part of the document.

    Returns:
        The autonomy contribution: a platform :class:`WorkflowDocument`
        built exactly as the equivalent authored workflow-file would parse —
        the ``stages`` overrides plus the single ``extend`` entry.
    """
    # Call-time import — contract: keeps goga out of the module's import-time
    # dependencies; the platform models are reached only when the hook fires
    # (the platform itself is running then).
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
