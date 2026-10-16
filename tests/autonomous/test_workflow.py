"""Tests for the autonomous workflow builder — ``autonomous/workflow.py``.

Contract: the facade signature; behavior: the record-driven auto-approval window and the build extend entry.
"""

import inspect

import pytest
from goga.pipeline.workflow import WorkflowDocument
from goga_tool_pybuggy.autonomous import build_autonomous_workflow
from goga_tool_pybuggy.autonomous.contributions import (
    AUTOMATE_CONTRIBUTION,
    CONTRIBUTIONS,
    PATCH_CONTRIBUTION,
)

_WINDOW_STAGES = [
    "review-testcases",
    "create-testcases",
    "code-design",
    "design-review",
    "coding-plan",
    "plan-review",
    "commit-changes",
]

_PATCH_WINDOW_STAGES = [
    "review-impact",
    "apply-manifests",
    "code-design",
    "design-review",
    "coding-plan",
    "plan-review",
    "commit-changes",
]


class TestBuildAutonomousWorkflowContract:
    """Facade exposure and signature surface of the workflow builder."""

    def test_build_autonomous_workflow_importable_from_facade(self):
        """The builder is importable from the autonomous cell facade."""
        assert callable(build_autonomous_workflow)

    def test_build_autonomous_workflow_signature_matches_contract(self):
        """The builder takes the contribution record and returns the platform document type."""
        signature = inspect.signature(build_autonomous_workflow)

        assert list(signature.parameters) == ["contribution"]
        assert signature.parameters["contribution"].annotation == "PipelineContribution"
        assert signature.return_annotation == "WorkflowDocument"


class TestBuildAutonomousWorkflowBehavior:
    """The record-driven document shape and the deterministic rebuild."""

    def test_build_autonomous_workflow_document_shape(self):
        """The automate record's document carries the seven-stage window and the build extend entry."""
        document = build_autonomous_workflow(AUTOMATE_CONTRIBUTION)

        assert isinstance(document, WorkflowDocument)
        assert document.prompt is None
        assert document.memory is None
        assert list(document.stages) == _WINDOW_STAGES
        assert all(stage.approve == "auto" for stage in document.stages.values())

        build = document.extend["build"]

        assert build.after == ["commit-changes"]
        assert build.before is None
        assert build.body == {
            "title": "Build tests",
            "script": 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"',
            "after_script": "rm -rf .ralphex",
            "timeout": "8h",
        }

        assert "accept-result" not in document.stages
        assert "accept-result" not in document.extend

    def test_build_autonomous_workflow_patch_document_shape(self):
        """The patch record's document carries the patch window and the workplan build script."""
        document = build_autonomous_workflow(PATCH_CONTRIBUTION)

        assert isinstance(document, WorkflowDocument)
        assert document.prompt is None
        assert document.memory is None
        assert list(document.stages) == _PATCH_WINDOW_STAGES
        assert all(stage.approve == "auto" for stage in document.stages.values())

        build = document.extend["build"]

        assert build.after == ["commit-changes"]
        assert build.before is None
        assert build.body == {
            "title": "Build tests",
            "script": 'python3 -P -m goga.build "$(python3 -m goga history path -f workplan.md)"',
            "after_script": "rm -rf .ralphex",
            "timeout": "8h",
        }

        assert "accept-result" not in document.stages
        assert "accept-result" not in document.extend

    @pytest.mark.parametrize("contribution", CONTRIBUTIONS, ids=["api.automate", "api.patch"])
    def test_build_autonomous_workflow_deterministic(self, contribution):
        """Two calls with the same record return deeply equal documents — a pure builder."""
        first = build_autonomous_workflow(contribution)
        second = build_autonomous_workflow(contribution)

        assert first == second
