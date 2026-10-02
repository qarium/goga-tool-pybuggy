"""pybuggy hook registration — the platform subscription table on the package root.

Subscribes the pybuggy platform hooks: the two statuses registrations (the
automate and fix status lines), the two onboarding participation moments
(question declaration, config amendment) implemented by the init cell's
session module, and the autonomy workflow amendment implemented by the
autonomous cell. The subscription surface arrives as the ``hooks`` argument;
the handlers are the cell objects themselves.
"""

from .autonomous import amend_workflow
from .commands.init import amend_pybuggy_config, declare_pybuggy_session
from .statuses import register_automate_statuses, register_fix_statuses


def register_hooks(hooks: object) -> None:
    """Subscribe the pybuggy platform hooks — five subscriptions in platform order.

    Makes exactly five subscriptions: the two statuses registrations on the
    statuses domain registration action (the automate line under the hook
    name ``automate`` and the fix line under the hook name ``fix``), the two
    onboarding participation moments (question declaration under the hook
    name ``declare`` and config amendment under the hook name ``amend``), and
    the autonomy workflow amendment on the pipeline domain amendment action
    (under the hook name ``autonomy``). The platform imports this callback
    from the package root.

    Args:
        hooks: The subscription surface delivered by the platform.
    """
    hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)

    hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)

    hooks.subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)

    hooks.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)

    hooks.subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)
