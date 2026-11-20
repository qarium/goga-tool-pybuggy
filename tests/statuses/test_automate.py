"""Tests for the automate status line — ``statuses/automate.py``.

Contract: the facade signature; behavior: the six literal registration calls in the normative table order.
"""

import inspect

from goga_tool_pybuggy.statuses import register_automate_statuses


class TestRegisterAutomateStatusesContract:
    """Facade exposure and signature surface of the automate status routine."""

    def test_register_automate_statuses_importable_from_facade(self):
        """The routine is importable from the statuses cell facade."""
        assert callable(register_automate_statuses)

    def test_register_automate_statuses_signature_matches_contract(self):
        """The routine carries exactly one ``context: object`` parameter and returns ``None``."""
        signature = inspect.signature(register_automate_statuses)

        assert list(signature.parameters) == ["context"]
        assert signature.parameters["context"].annotation is object
        assert signature.return_annotation is None


class TestRegisterAutomateStatusesBehavior:
    """The six literal registration calls in the normative table order."""

    def test_register_automate_statuses_registers_six_statuses_in_order(self, recorder_context):
        """The automate line registers bottom-up, each status anchored above its built-in twin."""
        register_automate_statuses(recorder_context)

        assert recorder_context.calls == [
            ("api.automate.done", "completed/plan.md", "done", None),
            ("api.automate.coding-planned", "plan.md", "planned", "pybuggy.api.automate.done"),
            ("api.automate.code-designed", "design.md", "designed", "pybuggy.api.automate.coding-planned"),
            ("api.automate.arch-prepared", "arch.md", "designed", "pybuggy.api.automate.code-designed"),
            ("api.automate.testcases-designed", "testcases.md", "backlog", "pybuggy.api.automate.arch-prepared"),
            (
                "api.automate.requirements-created",
                "requirements.md",
                "defined",
                "pybuggy.api.automate.testcases-designed",
            ),
        ]
