"""Tests for the goga hooks-platform facade of the root `pybuggy` cell.

Mirrors the source layout (``tests/test_hooks.py`` for the ``register_hooks`` routines in
``goga_tool_pybuggy/__init__.py``). Covers the contract surface of the facade callback: the
subscription envelopes (address, hook names, callables) and the topic-status registrations
each hook delivers (qualified names, artifacts, anchors). The goga platform objects are real —
``HookRegistrar`` validates the address against the action catalog, ``StatusRegistry``
qualifies names with the tool prefix — and the end-to-end case assembles the full status
scale through the installed-package enumeration of the platform.
"""

import goga_tool_pybuggy
from goga.history.statuses.assembly import assemble_status_scale
from goga.history.statuses.registry import StatusRegistry
from goga.history.statuses.scale import Stage
from goga.hooks.tools import HookRegistrar

# The built-in axis of the status scale (the platform contract: nine entries in scale order).
BUILTIN_AXIS: list[Stage] = [
    Stage(name="empty", filepath=""),
    Stage(name="todo", filepath="todo.md"),
    Stage(name="defined", filepath="prd.md"),
    Stage(name="discovered", filepath="adr.md"),
    Stage(name="backlog", filepath="task.md"),
    Stage(name="designed", filepath="arch.md"),
    Stage(name="specified", filepath="design.md"),
    Stage(name="planned", filepath="plan.md"),
    Stage(name="done", filepath="completed/plan.md"),
]


def make_registry() -> StatusRegistry:
    """Build a StatusRegistry scoped to the pybuggy tool over the built-in axis."""
    return StatusRegistry(builtin_stages=list(BUILTIN_AXIS), tool_prefix="pybuggy")


def tool_entries(registry: StatusRegistry) -> list[Stage]:
    """The entries registered through the registry (the scale minus the built-in axis)."""
    return registry.stages[len(BUILTIN_AXIS) :]


class TestRegisterHooksContract:
    """Contract tests for `register_hooks`."""

    def test_register_hooks_subscribes_two_status_hooks(self):
        """`register_hooks` lands exactly two subscriptions at the statuses/register_statuses address."""
        registrar = HookRegistrar(tool="pybuggy")

        goga_tool_pybuggy.register_hooks(registrar)

        assert [(s.domain, s.action, s.name) for s in registrar.subscriptions] == [
            ("statuses", "register_statuses", "automate"),
            ("statuses", "register_statuses", "fix"),
        ]

    def test_register_hooks_binds_the_status_hooks(self):
        """Each subscription carries the matching module-level hook callable."""
        registrar = HookRegistrar(tool="pybuggy")

        goga_tool_pybuggy.register_hooks(registrar)

        assert registrar.subscriptions[0].hook is goga_tool_pybuggy.register_automate_statuses
        assert registrar.subscriptions[1].hook is goga_tool_pybuggy.register_fix_statuses

    def test_register_hooks_leaves_no_rejections(self):
        """The real registrar accepts every envelope — no rejections are recorded."""
        registrar = HookRegistrar(tool="pybuggy")

        goga_tool_pybuggy.register_hooks(registrar)

        assert registrar.rejections == []


class TestAutomateStatusesContract:
    """Contract tests for `register_automate_statuses`."""

    def test_automate_registers_five_qualified_stages(self):
        """Every automate stage lands with the pybuggy qualification and its pipeline artifact."""
        registry = make_registry()

        goga_tool_pybuggy.register_automate_statuses(registry)

        assert [(s.name, s.filepath) for s in tool_entries(registry)] == [
            ("pybuggy.automate.requirements-created", "requirements.md"),
            ("pybuggy.automate.testcases-designed", "testcases.md"),
            ("pybuggy.automate.cells-prepared", "arch.md"),
            ("pybuggy.automate.code-designed", "design.md"),
            ("pybuggy.automate.coding-planned", "plan.md"),
        ]

    def test_automate_anchors_between_builtin_neighbors(self):
        """Each automate stage carries both anchors — after its lower, before its upper built-in neighbor."""
        registry = make_registry()

        goga_tool_pybuggy.register_automate_statuses(registry)

        assert [(s.after, s.before) for s in tool_entries(registry)] == [
            ("defined", "discovered"),
            ("backlog", "designed"),
            ("designed", "specified"),
            ("specified", "planned"),
            ("planned", "done"),
        ]

    def test_automate_does_not_touch_builtin_axis(self):
        """Registration is add-only — the built-in entries stay untouched."""
        registry = make_registry()

        goga_tool_pybuggy.register_automate_statuses(registry)

        assert registry.stages[: len(BUILTIN_AXIS)] == BUILTIN_AXIS


class TestFixStatusesContract:
    """Contract tests for `register_fix_statuses`."""

    def test_fix_registers_five_qualified_stages(self):
        """Every fix stage lands with the pybuggy qualification and its fix artifact."""
        registry = make_registry()

        goga_tool_pybuggy.register_fix_statuses(registry)

        assert [(s.name, s.filepath) for s in tool_entries(registry)] == [
            ("pybuggy.fix.collected", "fix-collect.md"),
            ("pybuggy.fix.analyzed", "fix-analysis.md"),
            ("pybuggy.fix.planned", "fix-plan.md"),
            ("pybuggy.fix.executed", "fix-execute.md"),
            ("pybuggy.fix.reviewed", "fix-review.md"),
        ]

    def test_fix_chain_rides_above_done_in_pipeline_order(self):
        """The first fix stage anchors after done; every next one after its predecessor."""
        registry = make_registry()

        goga_tool_pybuggy.register_fix_statuses(registry)

        assert [(s.after, s.before) for s in tool_entries(registry)] == [
            ("done", None),
            ("pybuggy.fix.collected", None),
            ("pybuggy.fix.analyzed", None),
            ("pybuggy.fix.planned", None),
            ("pybuggy.fix.executed", None),
        ]

    def test_fix_does_not_touch_builtin_axis(self):
        """Registration is add-only — the built-in entries stay untouched."""
        registry = make_registry()

        goga_tool_pybuggy.register_fix_statuses(registry)

        assert registry.stages[: len(BUILTIN_AXIS)] == BUILTIN_AXIS


class TestStatusScaleEndToEnd:
    """End-to-end assembly through the real platform enumeration."""

    def test_assembled_scale_places_every_pybuggy_status(self):
        """The platform assembles all ten pybuggy statuses with resolvable anchors and documented placement."""
        names = [stage.name for stage in assemble_status_scale().stages]

        assert names.index("defined") < names.index("pybuggy.automate.requirements-created") < names.index("discovered")
        assert names.index("backlog") < names.index("pybuggy.automate.testcases-designed") < names.index("designed")
        assert names.index("designed") < names.index("pybuggy.automate.cells-prepared") < names.index("specified")
        assert names.index("specified") < names.index("pybuggy.automate.code-designed") < names.index("planned")
        assert names.index("planned") < names.index("pybuggy.automate.coding-planned") < names.index("done")

        fix_chain = [
            "pybuggy.fix.collected",
            "pybuggy.fix.analyzed",
            "pybuggy.fix.planned",
            "pybuggy.fix.executed",
            "pybuggy.fix.reviewed",
        ]
        assert [names.index(name) for name in fix_chain] == sorted(names.index(name) for name in fix_chain)
        assert names.index("done") < names.index("pybuggy.fix.collected")
