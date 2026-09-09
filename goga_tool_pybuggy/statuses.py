"""pybuggy topic statuses on the goga status scale.

Registers the automate status line with the shared bugs marker and the
independent fix status line on the goga topic status scale. The two platform
surfaces arrive as arguments — ``hooks`` (subscription) and ``context``
(status registration) — so the module needs no imports.
"""


def register_hooks(hooks: object) -> None:
    """Subscribe the pybuggy topic-status hooks to the statuses registration action.

    Makes exactly two subscriptions on the statuses domain registration
    action: the automate line under the hook name ``automate_statuses`` and
    the fix line under the hook name ``fix_statuses``. The platform imports
    this callback from the package root.

    Args:
        hooks: The subscription surface delivered by the platform.
    """
    hooks.subscribe("statuses", "register_statuses", "automate_statuses", register_automate_statuses)

    hooks.subscribe("statuses", "register_statuses", "fix_statuses", register_fix_statuses)


def register_automate_statuses(context: object) -> None:
    """Register the automate status line and the shared bugs marker.

    Performs 7 literal registration calls in the normative table order: the
    completed-accept status anchored above the built-in ``done``, the middle
    automate statuses in reverse pipeline order (plan, design, arch,
    testcases, requirements) each anchored above its built-in twin and below
    the previously registered automate status, then the shared bugs marker
    above the completed-accept status. Registered names carry no tool prefix
    — the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("automate.done", "completed/plan.md", after="done")

    context.register("automate.plan", "plan.md", after="planned", before="pybuggy.automate.done")

    context.register("automate.design", "design.md", after="specified", before="pybuggy.automate.plan")

    context.register("automate.arch", "arch.md", after="designed", before="pybuggy.automate.design")

    context.register("automate.testcases", "testcases.md", after="backlog", before="pybuggy.automate.arch")

    context.register(
        "automate.requirements", "requirements.md", after="defined", before="pybuggy.automate.testcases"
    )

    context.register("bugs", "bugs.md", after="pybuggy.automate.done")


def register_fix_statuses(context: object) -> None:
    """Register the fix status line — an independent chain anchored at the built-in empty.

    Performs 5 literal registration calls in the normative table order
    (pipeline order: collect, analysis, plan, execute, review), each anchored
    above the previously registered fix status. The line is independent of
    the automate line and the built-in progression. Registered names carry
    no tool prefix — the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("fix.collect", "fix-collect.md", after="empty")

    context.register("fix.analysis", "fix-analysis.md", after="pybuggy.fix.collect")

    context.register("fix.plan", "fix-plan.md", after="pybuggy.fix.analysis")

    context.register("fix.execute", "fix-execute.md", after="pybuggy.fix.plan")

    context.register("fix.review", "fix-review.md", after="pybuggy.fix.execute")
