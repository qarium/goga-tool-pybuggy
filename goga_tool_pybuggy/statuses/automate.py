"""The pybuggy automate status line — the topic status registrations for api.automate runs.

Registers the automate status line on the goga topic status scale: the
completed-accept status anchored at the built-in ``done``, then the middle
automate statuses in reverse pipeline order. The registration surface
arrives as the ``context`` argument — the routine is a leaf with no imports.
"""


def register_automate_statuses(context: object) -> None:
    """Register the automate status line.

    Performs 6 literal registration calls in the normative table order: the
    completed-accept status anchored above the built-in ``done``, then the
    middle automate statuses in reverse pipeline order (plan, design, arch,
    testcases, requirements) each anchored above its built-in twin and below
    the previously registered automate status. Registered names carry no tool
    prefix — the platform assigns the tool identity.

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
