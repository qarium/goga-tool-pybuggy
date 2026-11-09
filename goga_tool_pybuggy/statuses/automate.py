"""The pybuggy api automate status line — the topic status registrations for api.automate runs.

Middle statuses are registered in reverse pipeline order from the ``done`` anchor.
"""


def register_automate_statuses(context: object) -> None:
    """Register the api automate status line.

    Registered names carry no tool prefix; the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("api.automate.done", "completed/plan.md", after="done")

    context.register("api.automate.coding-planned", "plan.md", after="planned", before="pybuggy.api.automate.done")

    context.register(
        "api.automate.code-designed", "design.md", after="designed", before="pybuggy.api.automate.coding-planned"
    )

    context.register(
        "api.automate.arch-prepared", "arch.md", after="designed", before="pybuggy.api.automate.code-designed"
    )

    context.register(
        "api.automate.testcases-designed",
        "testcases.md",
        after="backlog",
        before="pybuggy.api.automate.arch-prepared",
    )

    context.register(
        "api.automate.requirements-created",
        "requirements.md",
        after="defined",
        before="pybuggy.api.automate.testcases-designed",
    )
