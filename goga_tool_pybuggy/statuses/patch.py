"""The pybuggy api patch status line — the topic status registrations for api.patch runs.

An independent chain anchored at the built-in ``empty``, sharing no statuses with the automate
and fix lines.
"""


def register_patch_statuses(context: object) -> None:
    """Register the api patch status line.

    Registered names carry no tool prefix; the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("api.patch.intended", "intent.md", after="empty")

    context.register("api.patch.analyzed", "impact.md", after="pybuggy.api.patch.intended")

    context.register("api.patch.applied", "apply.md", after="pybuggy.api.patch.analyzed")

    context.register("api.patch.designed", "rework.md", after="pybuggy.api.patch.applied")

    context.register("api.patch.planned", "workplan.md", after="pybuggy.api.patch.designed")

    context.register("api.patch.done", "completed/workplan.md", after="pybuggy.api.patch.planned")
