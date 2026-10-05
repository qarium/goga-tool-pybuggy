"""Integration tests for the autonomy bridge — the feature's end-to-end chains.

Covers the run chain with the real resolver, the emit↔consume YAML bridge, and the real platform delivery.
"""

import pathlib

import yaml
from goga.pipeline.hooks.events import PipelineHooks
from goga.pipeline.hooks.identity import PipelineIdentity, WorkflowDecision, WorkIdentity
from goga_tool_pybuggy.autonomous import build_autonomous_workflow
from goga_tool_pybuggy.autonomous.amendment import amend_workflow
from goga_tool_pybuggy.commands.init import build_config_data
from goga_tool_pybuggy.config import resolve_autonomy

from .autonomous.conftest import _AmendmentView, amendment_identity

# Minimal survey answers; the autonomy confirm rides on top as the enabling or disabling answer.
_ANSWERS = {
    "base_url": "https://{{ HOST }}/api",
    "first_spec": {"name": "shop", "type": "swagger", "location": "specs/shop.yaml"},
}

# The tool's pipeline identity as the platform delivers it at the amendment checkpoint.
_RUN_PIPELINE = PipelineIdentity(
    name="pybuggy:api.automate",
    description="Pybuggy API-test automate lifecycle",
    source="user",
)


def _deliver(pipeline: PipelineIdentity) -> object:
    """Drive the real platform amendment emission for one pipeline identity.

    Builds the run registry with the real ``register_hooks`` and delivers the checkpoint as ``run_pipeline`` does.

    Args:
        pipeline: The identity of the pipeline being composed.

    Returns:
        The ``WorkflowOverlay`` — the effective workflow and the provenance.
    """
    return PipelineHooks().amend_workflow(
        pipeline=pipeline,
        decision=WorkflowDecision(kind="silent-miss", workflow_name=None),
        workflow=None,
        work=WorkIdentity(branch="main"),
    )


class TestRunChain:
    """``amend_workflow`` end to end with the real resolver and a real config tree."""

    def test_amend_workflow_end_to_end_with_real_config(self, tool_config) -> None:
        """An enabled axis in the standard tree makes the hook contribute the fixed document."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: true\n")
        view = _AmendmentView(_RUN_PIPELINE)

        amend_workflow(view)

        assert view.contributed == [build_autonomous_workflow()]

    def test_amend_workflow_end_to_end_disabled_is_silent_no_op(self, tool_config) -> None:
        """A disabled axis in the standard tree contributes nothing and raises nothing."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: false\n")
        view = _AmendmentView(_RUN_PIPELINE)

        amend_workflow(view)

        assert view.contributed == []


class TestPlatformDelivery:
    """The hook through the real platform emission — registry, delivery, merge."""

    def test_real_delivery_contributes_and_merges_the_window(self, tool_config) -> None:
        """An enabled run's contribution survives the delivery check and merges."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: true\n")

        overlay = _deliver(_RUN_PIPELINE)

        assert overlay.provenance == ["pybuggy"]
        assert overlay.workflow is not None
        assert overlay.workflow.prompt is None
        assert list(overlay.workflow.stages) == list(build_autonomous_workflow().stages)
        assert all(stage.approve == "auto" for stage in overlay.workflow.stages.values())
        assert overlay.workflow.extend["build"].after == ["commit-changes"]

    def test_real_delivery_other_pipeline_is_the_passthrough(self, tool_config) -> None:
        """A non-qualifying pipeline commits nothing — the D1 gate at the platform boundary."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: true\n")

        overlay = _deliver(amendment_identity("pybuggy:api.fix"))

        assert overlay.provenance == []
        assert overlay.workflow is None

    def test_real_delivery_disabled_axis_is_the_passthrough(self, tool_config) -> None:
        """A disabled axis commits nothing through the real emission."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: false\n")

        overlay = _deliver(_RUN_PIPELINE)

        assert overlay.provenance == []
        assert overlay.workflow is None


class TestEmitConsumeBridge:
    """The onboarding payload, serialized to the standard tree, consumed by the resolver."""

    def test_build_config_data_payload_enables_resolve_autonomy(self, tool_config) -> None:
        """The enabling payload enables the resolver; the disabling one writes no axis at all."""
        enabling = build_config_data(dict(_ANSWERS), None, True)
        tool_config(yaml.safe_dump(enabling))

        assert resolve_autonomy("api.automate") is True

        disabling = build_config_data(dict(_ANSWERS), None, False)

        assert "pipelines" not in disabling

        written: pathlib.Path = tool_config(yaml.safe_dump(disabling))

        assert "pipelines" not in yaml.safe_load(written.read_text(encoding="utf-8"))
        assert resolve_autonomy("api.automate") is False
