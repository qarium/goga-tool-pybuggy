"""Tests for the patch status line — ``statuses/patch.py``.

Contract: the facade signature; behavior: the six literal registration calls in pipeline order.
"""

import inspect

import goga_tool_pybuggy.statuses
from goga_tool_pybuggy.statuses import register_patch_statuses


class TestRegisterPatchStatusesContract:
    """Facade exposure and signature surface of the patch status routine."""

    def test_register_patch_statuses_importable_from_facade(self):
        """The routine is importable from the statuses cell facade."""
        assert callable(register_patch_statuses)
        assert "register_patch_statuses" in goga_tool_pybuggy.statuses.__all__

    def test_register_patch_statuses_signature_matches_contract(self):
        """The routine carries exactly one ``context: object`` parameter and returns ``None``."""
        signature = inspect.signature(register_patch_statuses)

        assert list(signature.parameters) == ["context"]
        assert signature.parameters["context"].annotation is object
        assert signature.return_annotation is None


class TestRegisterPatchStatusesBehavior:
    """The six literal registration calls in pipeline order."""

    def test_register_patch_statuses_registers_six_statuses_in_order(self, recorder_context):
        """The patch line is an independent chain anchored at the built-in empty status."""
        register_patch_statuses(recorder_context)

        assert recorder_context.calls == [
            ("patch.intended", "intent.md", "empty", None),
            ("patch.analyzed", "impact.md", "pybuggy.patch.intended", None),
            ("patch.applied", "apply.md", "pybuggy.patch.analyzed", None),
            ("patch.designed", "rework.md", "pybuggy.patch.applied", None),
            ("patch.planned", "workplan.md", "pybuggy.patch.designed", None),
            ("patch.done", "completed/workplan.md", "pybuggy.patch.planned", None),
        ]
