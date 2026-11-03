"""Tests for the workflow amendment hook — ``autonomous/amendment.py``.

Contract: the facade signature; behavior: record resolution, axis routing, and buffered contribution.
"""

import inspect

import goga_tool_pybuggy.autonomous.amendment as amendment_module
import pytest
from goga_tool_pybuggy.autonomous import amend_workflow, build_autonomous_workflow
from goga_tool_pybuggy.autonomous.contributions import (
    AUTOMATE_CONTRIBUTION,
    PATCH_CONTRIBUTION,
    WEB_AUTOMATE_CONTRIBUTION,
)

from .conftest import _AmendmentView, amendment_identity


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
    """Record resolution, axis routing, and the buffered contribution."""

    def test_amend_workflow_contributes_when_enabled(self, amendment_view, monkeypatch):
        """A qualifying pipeline with autonomy enabled receives the record's document."""
        monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline, _filename: True)

        amend_workflow(amendment_view)

        assert amendment_view.contributed == [build_autonomous_workflow(AUTOMATE_CONTRIBUTION)]

    def test_amend_workflow_contributes_patch_window_for_patch_pipeline(self, monkeypatch):
        """The patch identity contributes the patch record's window, not the automate one."""
        monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline, _filename: True)
        view = _AmendmentView(amendment_identity("pybuggy:api.patch"))

        amend_workflow(view)

        assert view.contributed == [build_autonomous_workflow(PATCH_CONTRIBUTION)]

    def test_amend_workflow_contributes_web_window_for_web_pipeline(self, monkeypatch):
        """The web identity contributes the web record's window, not the api ones."""
        monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline, _filename: True)
        view = _AmendmentView(amendment_identity("pybuggy:web.automate"))

        amend_workflow(view)

        assert view.contributed == [build_autonomous_workflow(WEB_AUTOMATE_CONTRIBUTION)]

    @pytest.mark.parametrize(
        ("identity", "expected_axis", "expected_file"),
        [
            ("pybuggy:api.automate", "api.automate", "api.yml"),
            ("pybuggy:api.patch", "api.patch", "api.yml"),
            ("pybuggy:web.automate", "web.automate", "web.yml"),
        ],
    )
    def test_amend_workflow_resolves_the_records_axis_and_file(
        self, identity, expected_axis, expected_file, monkeypatch
    ):
        """Each qualifying identity routes the resolver through its record's axis and config file."""
        captured: list[tuple[str, str]] = []

        def _record(axis: str, filename: str) -> bool:
            captured.append((axis, filename))
            return False

        monkeypatch.setattr(amendment_module, "resolve_autonomy", _record)
        view = _AmendmentView(amendment_identity(identity))

        amend_workflow(view)

        assert captured == [(expected_axis, expected_file)]
        assert view.contributed == []

    @pytest.mark.parametrize("name", ["pybuggy:code.review", "pybuggy:api.fix"])
    def test_amend_workflow_no_op_for_other_pipeline_even_when_axis_enabled(self, name, monkeypatch):
        """No record's window leaks into a non-qualifying pipeline (the D1 fix)."""
        monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline, _filename: True)
        view = _AmendmentView(amendment_identity(name))

        amend_workflow(view)

        assert view.contributed == []

    def test_amend_workflow_no_op_when_autonomy_disabled(self, amendment_view, monkeypatch):
        """A disabled axis entry contributes nothing and raises nothing."""
        monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline, _filename: False)

        amend_workflow(amendment_view)

        assert amendment_view.contributed == []

    def test_amend_workflow_errors_propagate_undamped(self, amendment_view, monkeypatch):
        """A raising resolver stops the hook — autonomy never disables silently."""

        def _raise(pipeline: str, filename: str) -> bool:
            raise ValueError("pybuggy tool config: boom")

        monkeypatch.setattr(amendment_module, "resolve_autonomy", _raise)

        with pytest.raises(ValueError, match="pybuggy tool config: boom"):
            amend_workflow(amendment_view)

        assert amendment_view.contributed == []
