"""The pybuggy automate status line — the topic status registrations for api.automate runs.

Middle statuses are registered in reverse pipeline order from the ``done`` anchor.
"""


def register_automate_statuses(context: object) -> None:
    """Register the automate status line.

    Registered names carry no tool prefix; the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("automate.done", "completed/plan.md", after="done")

    context.register("automate.coding-planned", "plan.md", after="planned", before="pybuggy.automate.done")

    context.register("automate.code-designed", "design.md", after="specified", before="pybuggy.automate.coding-planned")

    context.register("automate.arch-prepared", "arch.md", after="designed", before="pybuggy.automate.code-designed")

    context.register(
        "automate.testcases-designed", "testcases.md", after="backlog", before="pybuggy.automate.arch-prepared"
    )

    context.register(
        "automate.requirements-created",
        "requirements.md",
        after="defined",
        before="pybuggy.automate.testcases-designed",
    )
