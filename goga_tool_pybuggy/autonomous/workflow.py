"""The autonomous workflow document — the fixed contribution of a qualifying run.

Compile-time constants of the autonomy contribution: the seven-stage
auto-approval window ending at ``commit-changes`` and the build stage added
after it. The module is a pure leaf — it imports nothing and performs no
I/O; the builder assembles the constants into a WorkflowDocument-shaped
mapping, byte-identical on every call.
"""

_WINDOW_STAGES = (
    "review-testcases",
    "create-testcases",
    "code-design",
    "design-review",
    "coding-plan",
    "plan-review",
    "commit-changes",
)

_BUILD_NAME = "build"
_BUILD_TITLE = "Build tests"
_BUILD_SCRIPT = 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'
_BUILD_AFTER_SCRIPT = "rm -rf .ralphex"
_BUILD_TIMEOUT = "8h"
_BUILD_AFTER = ("commit-changes",)


def build_autonomous_workflow() -> dict[str, object]:
    """Build the declarative autonomy contribution from the compile-time constants.

    Assembles the fixed auto-approval window — each of the seven stages
    carries the ``approve: "auto"`` directive — and the build extend entry
    positioned after ``commit-changes``: the topic plan build with its
    scratch-tree cleanup script and the eight-hour timeout. The acceptance
    stage is never part of the document.

    Returns:
        The WorkflowDocument-shaped contribution: the ``stages`` overrides
        plus the single ``extend`` entry.
    """
    stages = {name: {"approve": "auto"} for name in _WINDOW_STAGES}

    build_entry = {
        "after": list(_BUILD_AFTER),
        "title": _BUILD_TITLE,
        "script": _BUILD_SCRIPT,
        "after_script": _BUILD_AFTER_SCRIPT,
        "timeout": _BUILD_TIMEOUT,
    }

    return {
        "stages": stages,
        "extend": {_BUILD_NAME: build_entry},
    }
