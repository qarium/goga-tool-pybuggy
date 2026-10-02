"""Tests for the fix status line — ``statuses/fix.py``.

Contract layer: the routine is importable from the cell facade with the
``register_fix_statuses(context: object) -> None`` signature. Behavior
layer: the five literal registration calls in pipeline order.
"""

import inspect

from goga_tool_pybuggy.statuses import register_fix_statuses


class TestRegisterFixStatusesContract:
    """Facade exposure and signature surface of the fix status routine."""

    def test_register_fix_statuses_importable_from_facade(self):
        """The routine is importable from the statuses cell facade."""
        assert callable(register_fix_statuses)

    def test_register_fix_statuses_signature_matches_contract(self):
        """The routine carries exactly one ``context: object`` parameter and returns ``None``."""
        signature = inspect.signature(register_fix_statuses)

        assert list(signature.parameters) == ["context"]
        assert signature.parameters["context"].annotation is object
        assert signature.return_annotation is None


class TestRegisterFixStatusesBehavior:
    """The five literal registration calls in pipeline order."""

    def test_register_fix_statuses_registers_five_statuses_in_order(self, recorder_context):
        """The fix line is an independent chain anchored at the built-in empty status."""
        register_fix_statuses(recorder_context)

        assert recorder_context.calls == [
            ("fix.collected", "fix-collect.md", "empty", None),
            ("fix.analyzed", "fix-analysis.md", "pybuggy.fix.collected", None),
            ("fix.planned", "fix-plan.md", "pybuggy.fix.analyzed", None),
            ("fix.executed", "fix-execute.md", "pybuggy.fix.planned", None),
            ("fix.reviewed", "fix-review.md", "pybuggy.fix.executed", None),
        ]
