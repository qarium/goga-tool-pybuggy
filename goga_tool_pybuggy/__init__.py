"""pybuggy — OpenAPI/Swagger endpoint viewer and generator (package facade)."""

from .cli import main
from .env import EnvContext, load_env
from .plugin import install
from .tools import retries

__all__ = ["EnvContext", "install", "load_env", "main", "register_hooks", "retries"]


def register_hooks(hooks: object) -> None:
    """Subscribe the pybuggy status hooks to the goga hooks platform.

    The platform imports the package facade and calls this callback when a command
    first reaches a hook checkpoint of the run; the tool identity (``pybuggy``) is
    assigned by the platform from the package name, and every registered status
    is shown qualified as ``pybuggy.<name>``.

    Args:
        hooks: the registration surface delivered by the platform.

    Returns:
        None; the subscriptions land through ``hooks.subscribe``.
    """
    hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)
    hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)


def register_automate_statuses(context: object) -> None:
    """Register the PybuggyApiAutomate pipeline stages as goga topic statuses.

    Each stage name is the completed form of its pipeline stage, carries the
    pipeline prefix, and lands next to the topic artifacts it neighbors in the
    lifecycle: `automate.requirements-created` between `defined` and `discovered`,
    `automate.testcases-designed` between `backlog` and `designed`, and the
    arch/design/plan stages right after their built-in twins (their artifacts
    are the same files).

    Args:
        context: the registration surface delivered by the goga hooks platform —
            the read-only view of the per-tool status registry.

    Returns:
        None; every registration lands through ``context.register``.
    """
    context.register("automate.requirements-created", "requirements.md", after="defined", before="discovered")
    context.register("automate.testcases-designed", "testcases.md", after="backlog", before="designed")
    context.register("automate.cells-prepared", "arch.md", after="designed", before="specified")
    context.register("automate.code-designed", "design.md", after="specified", before="planned")
    context.register("automate.coding-planned", "plan.md", after="planned", before="done")


def register_fix_statuses(context: object) -> None:
    """Register the PybuggyApiFix pipeline stages as goga topic statuses.

    Stage names are the completed forms of the pipeline stages and carry the
    pipeline prefix (`fix.collected`, `fix.analyzed`, ...); the chain rides above
    the built-in top (`done`) in pipeline order — every stage anchored to the
    previous one.

    Args:
        context: the registration surface delivered by the goga hooks platform —
            the read-only view of the per-tool status registry.

    Returns:
        None; every registration lands through ``context.register``.
    """
    context.register("fix.collected", "fix-collect.md", after="done")
    context.register("fix.analyzed", "fix-analysis.md", after="pybuggy.fix.collected")
    context.register("fix.planned", "fix-plan.md", after="pybuggy.fix.analyzed")
    context.register("fix.executed", "fix-execute.md", after="pybuggy.fix.planned")
    context.register("fix.reviewed", "fix-review.md", after="pybuggy.fix.executed")
