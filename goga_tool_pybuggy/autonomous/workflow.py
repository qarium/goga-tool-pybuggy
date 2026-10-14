"""The autonomous workflow document — the record-driven contribution of a qualifying run.

The record's auto-approval window ending at ``commit-changes``, plus the build stage after it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .contributions import PipelineContribution

if TYPE_CHECKING:  # the platform document type — reached at call time in the builder
    from goga.pipeline.workflow import WorkflowDocument

_BUILD_NAME = "build"
_BUILD_TITLE = "Build tests"
_BUILD_AFTER_SCRIPT = "rm -rf .ralphex"
_BUILD_TIMEOUT = "8h"


def build_autonomous_workflow(contribution: PipelineContribution) -> WorkflowDocument:
    """Build the declarative autonomy contribution from the pipeline's record.

    Every stage of the record's window carries ``approve: "auto"``; the acceptance stage is never included.

    Args:
        contribution: The pipeline's compile-time record — the window, the build artifact, and the
            extend positioning derive from it.

    Returns:
        A :class:`WorkflowDocument` with the ``stages`` overrides plus the single ``extend`` entry.
    """
    # Call-time import keeps goga out of the module's import-time dependencies.
    from goga.pipeline.workflow import (  # noqa: PLC0415
        WorkflowDocument,
        WorkflowExtendStage,
        WorkflowStage,
    )

    stages = {name: WorkflowStage(approve="auto") for name in contribution.window}

    build_entry = WorkflowExtendStage(
        after=[contribution.window[-1]],
        body={
            "title": _BUILD_TITLE,
            "script": f'python3 -P -m goga.build "$(python3 -m goga history path -f {contribution.build_artifact})"',
            "after_script": _BUILD_AFTER_SCRIPT,
            "timeout": _BUILD_TIMEOUT,
        },
    )

    return WorkflowDocument(stages=stages, extend={_BUILD_NAME: build_entry})
