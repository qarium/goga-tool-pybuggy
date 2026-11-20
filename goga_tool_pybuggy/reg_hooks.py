"""pybuggy hook registration — the platform subscription table on the package root.

Covers statuses, onboarding participation, and the autonomy workflow amendment.
"""

from .autonomous import amend_workflow
from .commands.init import amend_pybuggy_config, declare_pybuggy_session
from .statuses import (
    register_automate_statuses,
    register_fix_statuses,
    register_patch_statuses,
    register_web_statuses,
)


def register_hooks(hooks: object) -> None:
    """Subscribe the pybuggy platform hooks — seven subscriptions in platform order.

    The platform imports this callback from the package root.

    Args:
        hooks: The subscription surface delivered by the platform.
    """
    hooks.subscribe("statuses", "register_statuses", "api.automate", register_automate_statuses)

    hooks.subscribe("statuses", "register_statuses", "web.automate", register_web_statuses)

    hooks.subscribe("statuses", "register_statuses", "api.fix", register_fix_statuses)

    hooks.subscribe("statuses", "register_statuses", "api.patch", register_patch_statuses)

    hooks.subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)

    hooks.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)

    hooks.subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)
