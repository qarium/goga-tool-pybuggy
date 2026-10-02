"""The pybuggy fix status line — the topic status registrations for fix runs.

Registers the independent fix status line on the goga topic status scale —
a chain anchored at the built-in ``empty`` status with no shared statuses
with the automate line. The registration surface arrives as the ``context``
argument — the routine is a leaf with no imports.
"""


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
    context.register("fix.collected", "fix-collect.md", after="empty")

    context.register("fix.analyzed", "fix-analysis.md", after="pybuggy.fix.collected")

    context.register("fix.planned", "fix-plan.md", after="pybuggy.fix.analyzed")

    context.register("fix.executed", "fix-execute.md", after="pybuggy.fix.planned")

    context.register("fix.reviewed", "fix-review.md", after="pybuggy.fix.executed")
