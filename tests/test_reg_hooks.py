"""Tests for the root facade callback — the five hook subscriptions (reg_hooks.py).

Covers the facade signature contract and the exact five-entry subscription table in platform order.
"""

from goga_tool_pybuggy import register_hooks
from goga_tool_pybuggy.autonomous import amend_workflow
from goga_tool_pybuggy.commands.init import amend_pybuggy_config, declare_pybuggy_session
from goga_tool_pybuggy.statuses import register_automate_statuses, register_fix_statuses


class _RecorderHooks:
    """Subscription surface double capturing every subscribe call as a tuple."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, object]] = []

    def subscribe(self, domain: str, action: str, name: str, hook: object) -> None:
        """Record one subscription exactly as the platform delivers it.

        Args:
            domain: The subscription domain (e.g. ``statuses``, ``pipeline``).
            action: The subscription action inside the domain.
            name: The hook name the platform addresses the handler by.
            hook: The subscribed callable.
        """
        self.calls.append((domain, action, name, hook))


class TestRegisterHooksContract:
    """Facade exposure and signature surface of the root facade callback."""

    def test_register_hooks_facade_and_signature(self):
        """The callback is callable and carries its contract signature with the typed parameter and return."""
        assert callable(register_hooks)
        assert register_hooks.__annotations__ == {"hooks": object, "return": None}


class TestRegisterHooksSubscriptions:
    """The subscription table — five entries, platform order, cell-identity handlers."""

    def test_register_hooks_subscribes_five_hooks(self):
        """Exactly five subscriptions land in order: statuses pair, onboarding pair, autonomy."""
        recorder = _RecorderHooks()

        register_hooks(recorder)

        assert recorder.calls == [
            ("statuses", "register_statuses", "automate", register_automate_statuses),
            ("statuses", "register_statuses", "fix", register_fix_statuses),
            ("onboarding", "declare_session", "declare", declare_pybuggy_session),
            ("onboarding", "amend_config", "amend", amend_pybuggy_config),
            ("pipeline", "amend_workflow", "autonomy", amend_workflow),
        ]
