"""Tests for the workflow amendment hook — ``autonomous/amendment.py``.

Contract: the facade signature; behavior: the identity gate, autonomy resolution, and buffered contribution.
"""

import inspect

import goga_tool_pybuggy.autonomous.amendment as amendment_module
import pytest
from goga_tool_pybuggy.autonomous import amend_workflow, build_autonomous_workflow

from tests.autonomous.conftest import _AmendmentView, amendment_identity


class TestAmendWorkflowContract:
    """Facade exposure and signature surface of the amendment hook."""

    def test_amend_workflow_importable_from_facade(self):
        """The hook is importable from the autonomous cell facade."""
        assert callable(amend_workflow)

    def test_amend_workflow_signature_matches_contract(self):
        """The hook carries exactly one ``context: object`` parameter and returns ``None``."""
        signature = inspect.signature(amend_workflow)

        assert list(signature.parameters) == ["context"]
        assert signature.parameters["context"].annotation is object
        assert signature.return_annotation is None


class TestAmendWorkflowBehavior:
    """The identity gate, the autonomy resolution, and the buffered contribution."""

    def test_amend_workflow_contributes_when_enabled(self, amendment_view, monkeypatch):
        """A qualifying pipeline with autonomy enabled receives the fixed contribution."""
        monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline: True)

        amend_workflow(amendment_view)

        assert amendment_view.contributed == [build_autonomous_workflow()]

    def test_amend_workflow_no_op_for_other_pipeline_even_when_axis_enabled(self, monkeypatch):
        """The api.automate-shaped window never leaks into another pipeline (the D1 fix)."""
        monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline: True)
        view = _AmendmentView(amendment_identity("pybuggy:code.review"))

        amend_workflow(view)

        assert view.contributed == []

    def test_amend_workflow_no_op_when_autonomy_disabled(self, amendment_view, monkeypatch):
        """A disabled axis entry contributes nothing and raises nothing."""
        monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline: False)

        amend_workflow(amendment_view)

        assert amendment_view.contributed == []

    def test_amend_workflow_errors_propagate_undamped(self, amendment_view, monkeypatch):
        """A raising resolver stops the hook — autonomy never disables silently."""

        def _raise(pipeline: str) -> bool:
            raise ValueError("pybuggy tool config: boom")

        monkeypatch.setattr(amendment_module, "resolve_autonomy", _raise)

        with pytest.raises(ValueError, match="pybuggy tool config: boom"):
            amend_workflow(amendment_view)

        assert amendment_view.contributed == []
