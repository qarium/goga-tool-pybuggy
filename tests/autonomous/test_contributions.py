"""Tests for the ``PipelineContribution`` records — ``autonomous/contributions.py``.

Contract: the record type on the facade; behavior: the fail-fast data carrier and the normative contribution table.
"""

import goga_tool_pybuggy.autonomous
import pydantic
import pytest
from goga_tool_pybuggy.autonomous import PipelineContribution
from goga_tool_pybuggy.autonomous.contributions import (
    AUTOMATE_CONTRIBUTION,
    CONTRIBUTIONS,
    PATCH_CONTRIBUTION,
    WEB_AUTOMATE_CONTRIBUTION,
)
from pydantic import ValidationError


class TestPipelineContributionContract:
    """Facade exposure and pydantic configuration surface of the record."""

    def test_pipeline_contribution_importable_from_facade(self) -> None:
        """The record is importable from the autonomous cell facade as a pydantic model."""
        assert issubclass(PipelineContribution, pydantic.BaseModel)
        assert "PipelineContribution" in goga_tool_pybuggy.autonomous.__all__

    def test_pipeline_contribution_model_config_kw_only_and_extra_forbid(self) -> None:
        """The record is ``kw_only`` and forbids members outside the five fields."""
        assert PipelineContribution.model_config.get("kw_only") is True
        assert PipelineContribution.model_config.get("extra") == "forbid"
        assert set(PipelineContribution.model_fields) == {
            "identity",
            "axis",
            "config_file",
            "window",
            "build_artifact",
        }


class TestPipelineContributionBehavior:
    """Validation outcomes of the record: acceptance, rejection, coercion."""

    def test_pipeline_contribution_is_kw_only_data_carrier(self) -> None:
        """Keyword construction reads back the five fields; positional and extra keys fail."""
        record = PipelineContribution(identity="i", axis="a", config_file="c.yml", window=["s"], build_artifact="f.md")

        assert record.identity == "i"
        assert record.axis == "a"
        assert record.config_file == "c.yml"
        assert record.window == ["s"]
        assert record.build_artifact == "f.md"

        with pytest.raises(TypeError):
            PipelineContribution("i", "a", "c.yml", ["s"], "f.md")  # type: ignore[call-arg]

        with pytest.raises(ValidationError):
            PipelineContribution(
                identity="i", axis="a", config_file="c.yml", window=["s"], build_artifact="f.md", typo=1
            )

    def test_pipeline_contribution_coerces_tuple_window_to_list(self) -> None:
        """A tuple-constructed window reads back as a list and equals the list form (REPL-pinned)."""
        from_tuple = PipelineContribution(
            identity="i", axis="a", config_file="c.yml", window=("s", "t"), build_artifact="f.md"
        )
        from_list = PipelineContribution(identity="i", axis="a", config_file="c.yml", window=["s", "t"], build_artifact="f.md")

        assert from_tuple.window == ["s", "t"]
        assert from_tuple == from_list

    def test_pipeline_contribution_rejects_an_empty_window(self) -> None:
        """An empty window fails validation at construction — the build anchor needs its last entry."""
        with pytest.raises(ValidationError, match="window"):
            PipelineContribution(identity="i", axis="a", config_file="c.yml", window=[], build_artifact="f.md")


class TestContributionTable:
    """The normative compile-time contribution table."""

    def test_contribution_table_is_normative(self) -> None:
        """All three records carry the exact identity, axis, config-file, window, and build-artifact literals."""
        assert CONTRIBUTIONS == (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION, WEB_AUTOMATE_CONTRIBUTION)

        assert AUTOMATE_CONTRIBUTION.identity == "pybuggy:api.automate"
        assert AUTOMATE_CONTRIBUTION.axis == "api.automate"
        assert AUTOMATE_CONTRIBUTION.config_file == "api.yml"
        assert AUTOMATE_CONTRIBUTION.window == [
            "review-testcases",
            "create-testcases",
            "code-design",
            "design-review",
            "coding-plan",
            "plan-review",
            "commit-changes",
        ]
        assert AUTOMATE_CONTRIBUTION.build_artifact == "plan.md"

        assert PATCH_CONTRIBUTION.identity == "pybuggy:api.patch"
        assert PATCH_CONTRIBUTION.axis == "api.patch"
        assert PATCH_CONTRIBUTION.config_file == "api.yml"
        assert PATCH_CONTRIBUTION.window == [
            "review-impact",
            "apply-manifests",
            "code-design",
            "design-review",
            "coding-plan",
            "plan-review",
            "commit-changes",
        ]
        assert PATCH_CONTRIBUTION.build_artifact == "workplan.md"

        assert WEB_AUTOMATE_CONTRIBUTION.identity == "pybuggy:web.automate"
        assert WEB_AUTOMATE_CONTRIBUTION.axis == "web.automate"
        assert WEB_AUTOMATE_CONTRIBUTION.config_file == "web.yml"
        assert WEB_AUTOMATE_CONTRIBUTION.window == [
            "testcases-review",
            "code-design",
            "design-review",
            "coding-plan",
            "plan-review",
            "commit-changes",
        ]
        assert WEB_AUTOMATE_CONTRIBUTION.build_artifact == "plan.md"

    def test_contribution_windows_end_at_commit_changes(self) -> None:
        """Every window is non-empty and ends at ``commit-changes`` — the build anchor."""
        assert all(record.window for record in CONTRIBUTIONS)
        assert all(record.window[-1] == "commit-changes" for record in CONTRIBUTIONS)

    def test_contribution_axes_route_per_kind_config_file(self) -> None:
        """The api lines read their axis from api.yml, the web line from web.yml — never crossed."""
        assert all(record.config_file == "api.yml" for record in CONTRIBUTIONS if record.axis.startswith("api."))
        assert all(record.config_file == "web.yml" for record in CONTRIBUTIONS if record.axis.startswith("web."))
