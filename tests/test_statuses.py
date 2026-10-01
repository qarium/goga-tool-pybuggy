"""Tests for the root facade callback — the four hook subscriptions (statuses.py).

Covers ``register_hooks`` in two layers. The contract layer (Task 8): the
callback is exposed on the package root (the platform import point) with the
``register_hooks(hooks: object) -> None`` signature. The behavior layer: the
subscription table itself — exactly four ``hooks.subscribe`` calls in the
platform order (two statuses registrations, then the two onboarding
participation moments), with the onboarding callables being the init-cell
session objects by identity.
"""

import pytest
from goga_tool_pybuggy import register_hooks
from goga_tool_pybuggy.commands.init import amend_pybuggy_config, declare_pybuggy_session
from goga_tool_pybuggy.statuses import register_automate_statuses, register_fix_statuses


class _RecorderHooks:
    """Subscription surface double capturing every subscribe call as a tuple."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, object]] = []

    def subscribe(self, domain: str, action: str, name: str, hook: object) -> None:
        """Record one subscription exactly as the platform delivers it.

        Args:
            domain: The subscription domain (e.g. ``statuses``, ``onboarding``).
            action: The subscription action inside the domain.
            name: The hook name the platform addresses the handler by.
            hook: The subscribed callable.
        """
        self.calls.append((domain, action, name, hook))


class TestRegisterHooksContract:
    """Facade exposure and signature surface of the root facade callback."""

    def test_register_hooks_exposed_on_root_facade(self):
        """The callback is importable from the package root — the platform import point."""
        assert callable(register_hooks)

    def test_register_hooks_signature_matches_contract(self):
        """The callback carries its contract signature with the typed parameter and return."""
        assert register_hooks.__annotations__ == {"hooks": object, "return": None}


class TestRegisterHooksSubscriptions:
    """The subscription table — four entries, platform order, cell-identity handlers."""

    def test_register_hooks_subscribes_four_hooks(self):
        """Exactly four subscriptions land in order: statuses pair, then the onboarding pair."""
        recorder = _RecorderHooks()

        register_hooks(recorder)

        assert recorder.calls == [
            ("statuses", "register_statuses", "automate", register_automate_statuses),
            ("statuses", "register_statuses", "fix", register_fix_statuses),
            ("onboarding", "declare_session", "declare", declare_pybuggy_session),
            ("onboarding", "amend_config", "amend", amend_pybuggy_config),
        ]

    @pytest.mark.parametrize(
        ("index", "expected"),
        [
            (2, declare_pybuggy_session),
            (3, amend_pybuggy_config),
        ],
    )
    def test_onboarding_handlers_are_init_cell_session_objects(self, index, expected):
        """The onboarding callables are the init-cell session objects by identity."""
        recorder = _RecorderHooks()

        register_hooks(recorder)

        assert recorder.calls[index][3] is expected


class _RecorderContext:
    """Registration surface double capturing every register call with its anchors.

    Attributes:
        calls: The ``(name, artifact, after, before)`` tuples, in call order.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None, str | None]] = []

    def register(self, name: str, artifact: str, after: str | None = None, before: str | None = None) -> None:
        """Record one registration exactly as the platform delivers it.

        Args:
            name: The registered status name (no tool prefix — the platform assigns identity).
            artifact: The topic artifact path the status tracks.
            after: The anchor the status sits above.
            before: The anchor the status must stay below.
        """
        self.calls.append((name, artifact, after, before))


class TestStatusLines:
    """The two status lines — registration calls, order, and anchors against a recorder context."""

    def test_register_automate_statuses_registers_six_statuses_in_order(self):
        """The automate line registers bottom-up, each status anchored above its built-in twin."""
        context = _RecorderContext()

        register_automate_statuses(context)

        assert context.calls == [
            ("automate.done", "completed/plan.md", "done", None),
            ("automate.coding-planned", "plan.md", "planned", "pybuggy.automate.done"),
            ("automate.code-designed", "design.md", "specified", "pybuggy.automate.coding-planned"),
            ("automate.arch-prepared", "arch.md", "designed", "pybuggy.automate.code-designed"),
            ("automate.testcases-designed", "testcases.md", "backlog", "pybuggy.automate.arch-prepared"),
            ("automate.requirements-created", "requirements.md", "defined", "pybuggy.automate.testcases-designed"),
        ]

    def test_register_fix_statuses_registers_five_statuses_in_order(self):
        """The fix line is an independent chain anchored at the built-in empty status."""
        context = _RecorderContext()

        register_fix_statuses(context)

        assert context.calls == [
            ("fix.collected", "fix-collect.md", "empty", None),
            ("fix.analyzed", "fix-analysis.md", "pybuggy.fix.collected", None),
            ("fix.planned", "fix-plan.md", "pybuggy.fix.analyzed", None),
            ("fix.executed", "fix-execute.md", "pybuggy.fix.planned", None),
            ("fix.reviewed", "fix-review.md", "pybuggy.fix.executed", None),
        ]
