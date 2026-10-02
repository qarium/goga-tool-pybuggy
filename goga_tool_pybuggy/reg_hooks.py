"""pybuggy hook registration — the platform subscription table on the package root.

Subscribes the pybuggy platform hooks: the two statuses registrations (the
automate and fix status lines) and the two onboarding participation moments
(question declaration, config amendment) implemented by the init cell's
session module. The subscription surface arrives as the ``hooks`` argument;
the handlers are the cell objects themselves.
"""

from .commands.init import amend_pybuggy_config, declare_pybuggy_session
from .statuses import register_automate_statuses, register_fix_statuses


def register_hooks(hooks: object) -> None:
    """Subscribe the pybuggy platform hooks — four subscriptions in platform order.

    Makes exactly four subscriptions: the two statuses registrations on the
    statuses domain registration action (the automate line under the hook
    name ``automate`` and the fix line under the hook name ``fix``) and the
    two onboarding participation moments (question declaration under the hook
    name ``declare`` and config amendment under the hook name ``amend``). The
    platform imports this callback from the package root.

    Args:
        hooks: The subscription surface delivered by the platform.
    """
    hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)

    hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)

    hooks.subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)

    hooks.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)
