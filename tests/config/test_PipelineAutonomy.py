"""Tests for the ``PipelineAutonomy`` record — ``config/pipeline_autonomy.py``.

Contract layer: the record is importable from the cell facade, admits exactly
the ``autonomous`` member, and is ``kw_only`` with ``extra="forbid"``.
Behavior layer: valid records validate (pydantic lax bool coercion included)
while structural violations reject.
"""

import pytest
from goga_tool_pybuggy.config import PipelineAutonomy
from pydantic import BaseModel, ValidationError


class TestPipelineAutonomyContract:
    """Facade exposure and pydantic configuration surface of the record."""

    def test_pipeline_autonomy_importable_from_facade(self) -> None:
        """The record is importable from the config cell facade as a pydantic model."""
        assert issubclass(PipelineAutonomy, BaseModel)

    def test_pipeline_autonomy_admits_exactly_the_autonomous_member(self) -> None:
        """The record's field set is exactly ``{"autonomous"}``."""
        assert set(PipelineAutonomy.model_fields) == {"autonomous"}

    def test_pipeline_autonomy_model_config_kw_only_and_extra_forbid(self) -> None:
        """The record is ``kw_only`` and forbids members outside ``autonomous``."""
        assert PipelineAutonomy.model_config.get("kw_only") is True
        assert PipelineAutonomy.model_config.get("extra") == "forbid"


class TestPipelineAutonomyBehavior:
    """Validation outcomes of the record: acceptance, rejection, coercion."""

    def test_pipeline_autonomy_accepts_valid_record(self) -> None:
        """A well-formed entry validates and yields the raw boolean."""
        assert PipelineAutonomy.model_validate({"autonomous": True}).autonomous is True
        assert PipelineAutonomy(autonomous=False).autonomous is False

    def test_pipeline_autonomy_coerces_truthy_spellings(self) -> None:
        """Pydantic v2 lax bool coercion accepts the truthy spellings (REPL-pinned).

        PyYAML (YAML 1.1) parses bare ``yes``/``on`` to real booleans, so the
        coercion path only matters for quoted spellings — it stays valid input.
        """
        assert PipelineAutonomy.model_validate({"autonomous": "yes"}).autonomous is True
        assert PipelineAutonomy.model_validate({"autonomous": "on"}).autonomous is True
        assert PipelineAutonomy.model_validate({"autonomous": "1"}).autonomous is True
        assert PipelineAutonomy.model_validate({"autonomous": 1}).autonomous is True

    def test_pipeline_autonomy_rejects_positional_construction(self) -> None:
        """``kw_only`` makes the positional spell ``PipelineAutonomy(True)`` a TypeError."""
        with pytest.raises(TypeError):
            PipelineAutonomy(True)  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param({}, id="missing-member"),
            pytest.param({"autonomous": True, "typo": 1}, id="extra-member"),
            pytest.param({"autonomous": "maybe"}, id="non-coercible-value"),
            pytest.param({"autonomous": None}, id="null-value"),
        ],
    )
    def test_pipeline_autonomy_rejects_parametrized(self, raw: dict[str, object]) -> None:
        """Every structural violation fails validation instead of silently disabling."""
        with pytest.raises(ValidationError):
            PipelineAutonomy.model_validate(raw)
