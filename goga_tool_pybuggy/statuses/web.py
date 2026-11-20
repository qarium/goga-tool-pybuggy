"""The pybuggy web automate status line — the topic status registrations for web.automate runs.

Middle statuses are registered in reverse pipeline order from the ``done`` anchor. The web
pipeline writes no testcases or arch artifacts — its cases live as Routines in the target
project — so the line carries no statuses for them.
"""


def register_web_statuses(context: object) -> None:
    """Register the web automate status line.

    Registered names carry no tool prefix; the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("web.automate.done", "completed/plan.md", after="done")

    context.register("web.automate.planned", "plan.md", after="planned", before="pybuggy.web.automate.done")

    context.register("web.automate.designed", "design.md", after="designed", before="pybuggy.web.automate.planned")

    context.register(
        "web.automate.requirements-created",
        "requirements.md",
        after="defined",
        before="pybuggy.web.automate.designed",
    )
