"""Tests for the web automate status line — ``statuses/web.py``.

Contract: the facade signature; behavior: the four literal registration calls in the normative table order.
"""

import inspect

from goga_tool_pybuggy.statuses import register_web_statuses


class TestRegisterWebStatusesContract:
    """Facade exposure and signature surface of the web automate status routine."""

    def test_register_web_statuses_importable_from_facade(self):
        """The routine is importable from the statuses cell facade."""
        assert callable(register_web_statuses)

    def test_register_web_statuses_signature_matches_contract(self):
        """The routine carries exactly one ``context: object`` parameter and returns ``None``."""
        signature = inspect.signature(register_web_statuses)

        assert list(signature.parameters) == ["context"]
        assert signature.parameters["context"].annotation is object
        assert signature.return_annotation is None


class TestRegisterWebStatusesBehavior:
    """The four literal registration calls in the normative table order."""

    def test_register_web_statuses_registers_four_statuses_in_order(self, recorder_context):
        """The web automate line registers bottom-up, each status anchored above its built-in twin."""
        register_web_statuses(recorder_context)

        assert recorder_context.calls == [
            ("web.automate.done", "completed/plan.md", "done", None),
            ("web.automate.planned", "plan.md", "planned", "pybuggy.web.automate.done"),
            ("web.automate.designed", "design.md", "designed", "pybuggy.web.automate.planned"),
            ("web.automate.requirements-created", "requirements.md", "defined", "pybuggy.web.automate.designed"),
        ]
