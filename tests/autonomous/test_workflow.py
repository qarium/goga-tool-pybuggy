"""Tests for the autonomous workflow builder — ``autonomous/workflow.py``.

Contract layer: the builder is importable from the cell facade with the
``build_autonomous_workflow() -> dict[str, object]`` signature. Behavior
layer: the fixed seven-stage auto-approval window and the build extend entry.
"""

import inspect

from goga_tool_pybuggy.autonomous import build_autonomous_workflow

_WINDOW_STAGES = [
    "review-testcases",
    "create-testcases",
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
        """The builder takes no parameters and returns ``dict[str, object]``."""
        signature = inspect.signature(build_autonomous_workflow)

        assert signature.parameters == {}
        assert signature.return_annotation == dict[str, object]


class TestBuildAutonomousWorkflowBehavior:
    """The fixed document shape and the deterministic rebuild."""

    def test_build_autonomous_workflow_document_shape(self):
        """The document carries the seven-stage auto window and the build extend entry."""
        document = build_autonomous_workflow()

        assert set(document) == {"stages", "extend"}
        assert list(document["stages"]) == _WINDOW_STAGES
        assert all(value == {"approve": "auto"} for value in document["stages"].values())

        build = document["extend"]["build"]

        assert set(build) == {"after", "title", "script", "after_script", "timeout"}
        assert build["after"] == ["commit-changes"]
        assert build["title"] == "Build tests"
        assert build["script"] == 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'
        assert build["after_script"] == "rm -rf .ralphex"
        assert build["timeout"] == "8h"

        assert "accept-result" not in document["stages"]
        assert "accept-result" not in document["extend"]

    def test_build_autonomous_workflow_deterministic(self):
        """Two calls return deeply equal documents — pure compile-time constants only."""
        first = build_autonomous_workflow()
        second = build_autonomous_workflow()

        assert first == second
