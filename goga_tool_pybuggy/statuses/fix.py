"""The pybuggy fix status line — the topic status registrations for fix runs.

An independent chain anchored at the built-in ``empty``, sharing no statuses with the automate line.
"""


def register_fix_statuses(context: object) -> None:
    """Register the fix status line.

    Registered names carry no tool prefix; the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("fix.collected", "fix-collect.md", after="empty")

    context.register("fix.analyzed", "fix-analysis.md", after="pybuggy.fix.collected")

    context.register("fix.planned", "fix-plan.md", after="pybuggy.fix.analyzed")

    context.register("fix.executed", "fix-execute.md", after="pybuggy.fix.planned")

    context.register("fix.reviewed", "fix-review.md", after="pybuggy.fix.executed")
