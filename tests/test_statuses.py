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
