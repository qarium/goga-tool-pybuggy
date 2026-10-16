"""Scale-assembly regression tests — the three status lines against the real goga platform axis.

The registration routines hand anchors to the platform; the platform resolves them against
its built-in axis at scale assembly. These tests resolve every anchor through the platform's
own placement code, so an anchor naming a status that does not exist fails here — the defect
class that silently dropped four automate statuses with ``skipping status registration``
warnings on every pipeline run.
"""

import logging
from importlib.metadata import packages_distributions

import pytest
from goga.history.statuses.assembly import _BUILTIN_AXIS, _placement_index, assemble_status_scale
from goga.history.statuses.registry import StatusRegistry
from goga_tool_pybuggy.statuses import register_automate_statuses, register_fix_statuses, register_patch_statuses

# The full assembled scale in normative order — observed from the platform's own placement
# logic over the real built-in axis: nine built-ins plus the seventeen pybuggy statuses.
_EXPECTED_SCALE: list[str] = [
    "empty",
    "pybuggy.fix.collected",
    "pybuggy.patch.intended",
    "pybuggy.patch.analyzed",
    "pybuggy.patch.applied",
    "pybuggy.patch.designed",
    "pybuggy.patch.planned",
    "pybuggy.patch.done",
    "pybuggy.fix.analyzed",
    "pybuggy.fix.planned",
    "pybuggy.fix.executed",
    "pybuggy.fix.reviewed",
    "todo",
    "defined",
    "discovered",
    "backlog",
    "prototyped",
    "designed",
    "planned",
    "done",
    "pybuggy.automate.requirements-created",
    "pybuggy.automate.testcases-designed",
    "pybuggy.automate.arch-prepared",
    "pybuggy.automate.code-designed",
    "pybuggy.automate.coding-planned",
    "pybuggy.automate.done",
]

_ALL_PYBUGGY_STATUSES: list[str] = [name for name in _EXPECTED_SCALE if name.startswith("pybuggy.")]

# The public assembly enumerates installed tool packages — the source distribution alone,
# without an install, hides pybuggy from the platform for environmental (not code) reasons.
_PYBUGGY_INSTALLED = "goga_tool_pybuggy" in packages_distributions()


class TestScaleAssembly:
    """Anchor resolution of the three lines through the platform placement code."""

    def test_three_lines_place_completely_in_normative_order(self):
        """Every pybuggy registration resolves against the real built-in axis with zero skips."""
        registry = StatusRegistry(builtin_stages=list(_BUILTIN_AXIS), tool_prefix="pybuggy")

        register_automate_statuses(registry)

        register_fix_statuses(registry)

        register_patch_statuses(registry)

        # The placement loop of the platform assembly: an unresolvable anchor of any entry
        # raises here instead of logging a skip.
        stages = list(_BUILTIN_AXIS)

        for entry in registry.stages[len(_BUILTIN_AXIS) :]:
            index = _placement_index(stages, entry)

            stages.insert(index, entry)

        assert [stage.name for stage in stages] == _EXPECTED_SCALE

    @pytest.mark.skipif(not _PYBUGGY_INSTALLED, reason="pybuggy is not an installed distribution in this environment")
    def test_public_assembly_registers_all_pybuggy_statuses_without_warnings(self, caplog):
        """The public platform assembly accepts all seventeen pybuggy statuses and logs no skips."""
        caplog.set_level(logging.WARNING)

        scale = assemble_status_scale()

        names = [stage.name for stage in scale.stages]

        assert all(qualified in names for qualified in _ALL_PYBUGGY_STATUSES)

        assert not [record for record in caplog.records if record.getMessage() == "skipping status registration"]
