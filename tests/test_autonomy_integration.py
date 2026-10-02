"""Integration tests for the autonomy bridge — the feature's two end-to-end chains.

Chain one (the run chain): ``amend_workflow`` (autonomous cell) composed with
the REAL ``resolve_autonomy`` (config cell) reading a prepared standard tree —
the two cells integrate through the real file standard
(``.goga/tools/pybuggy/config.yml``) with no stubs: the enabled tree
contributes the fixed workflow document, the disabled tree is a silent no-op.

Chain two (the emit↔consume bridge): the ``build_config_data`` payload (init
cell), serialized as YAML to the standard path, is consumed by
``resolve_autonomy`` — emit → engine YAML → raw parse → axis validation — the
exact bridge the onboarding session writes and the run hook later reads.

Both scenarios ride the shared ``tool_config`` fixture, so the platform
facade's real cwd-relative path composition is exercised end to end.
"""

import pathlib

import yaml
from goga_tool_pybuggy.autonomous import amend_workflow, build_autonomous_workflow
from goga_tool_pybuggy.commands.init import build_config_data
from goga_tool_pybuggy.config import resolve_autonomy

from tests.autonomous.conftest import _AmendmentView

# A minimal survey-shaped answer view — a first spec plus the base template;
# the autonomy confirm rides on top as the enabling or disabling answer.
_ANSWERS = {
    "base_url": "https://{{ HOST }}/api",
    "first_spec": {"name": "shop", "type": "swagger", "location": "specs/shop.yaml"},
}


class TestRunChain:
    """``amend_workflow`` end to end with the real resolver and a real config tree."""

    def test_amend_workflow_end_to_end_with_real_config(self, tool_config) -> None:
        """An enabled axis in the standard tree makes the hook contribute the fixed document."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: true\n")
        view = _AmendmentView("api.automate")

        amend_workflow(view)

        assert view.contributed == [build_autonomous_workflow()]

    def test_amend_workflow_end_to_end_disabled_is_silent_no_op(self, tool_config) -> None:
        """A disabled axis in the standard tree contributes nothing and raises nothing."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: false\n")
        view = _AmendmentView("api.automate")

        amend_workflow(view)

        assert view.contributed == []


class TestEmitConsumeBridge:
    """The onboarding payload, serialized to the standard tree, consumed by the resolver."""

    def test_build_config_data_payload_enables_resolve_autonomy(self, tool_config) -> None:
        """The enabling payload enables the resolver; the disabling one writes no axis at all."""
        enabling = build_config_data({**_ANSWERS, "autonomous": True}, None)
        tool_config(yaml.safe_dump(enabling))

        assert resolve_autonomy("api.automate") is True

        disabling = build_config_data({**_ANSWERS, "autonomous": False}, None)

        assert "pipelines" not in disabling

        written: pathlib.Path = tool_config(yaml.safe_dump(disabling))

        assert "pipelines" not in yaml.safe_load(written.read_text(encoding="utf-8"))
        assert resolve_autonomy("api.automate") is False
