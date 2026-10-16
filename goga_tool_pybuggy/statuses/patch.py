"""The pybuggy patch status line — the topic status registrations for patch runs.

An independent chain anchored at the built-in ``empty``, sharing no statuses with the automate and fix lines.
"""


def register_patch_statuses(context: object) -> None:
    """Register the patch status line.

    Registered names carry no tool prefix; the platform assigns the tool identity.

    Args:
        context: The registration surface scoped to the tool.
    """
    context.register("patch.intended", "intent.md", after="empty")

    context.register("patch.analyzed", "impact.md", after="pybuggy.patch.intended")

    context.register("patch.applied", "apply.md", after="pybuggy.patch.analyzed")

    context.register("patch.designed", "rework.md", after="pybuggy.patch.applied")

    context.register("patch.planned", "workplan.md", after="pybuggy.patch.designed")

    context.register("patch.done", "completed/workplan.md", after="pybuggy.patch.planned")
