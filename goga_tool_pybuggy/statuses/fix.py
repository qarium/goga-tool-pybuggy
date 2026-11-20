"""The pybuggy api fix status line — the topic status registrations for api.fix runs.

An independent chain anchored at the built-in ``empty``, sharing no statuses with the automate lines.
"""


def register_fix_statuses(context: object) -> None:
    """Register the api fix status line.

    Registered names carry no tool prefix; the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("api.fix.collected", "fix-collect.md", after="empty")

    context.register("api.fix.analyzed", "fix-analysis.md", after="pybuggy.api.fix.collected")

    context.register("api.fix.planned", "fix-plan.md", after="pybuggy.api.fix.analyzed")

    context.register("api.fix.executed", "fix-execute.md", after="pybuggy.api.fix.planned")

    context.register("api.fix.reviewed", "fix-review.md", after="pybuggy.api.fix.executed")
