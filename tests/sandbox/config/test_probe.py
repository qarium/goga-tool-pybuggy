"""Contract and logic tests for the ``ProbeConfig`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import ProbeConfig
from pydantic import BaseModel, ValidationError


class TestProbeConfigContract:
    """Declared API of the ``ProbeConfig`` entity."""

    def test_probe_config_is_importable_from_config_facade(self):
        """``ProbeConfig`` is re-exported by the ``goga_tool_pybuggy.sandbox.config`` facade."""
        assert ProbeConfig is not None

    def test_probe_config_is_a_pydantic_model(self):
        """``ProbeConfig`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(ProbeConfig, BaseModel)

    def test_probe_config_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(ProbeConfig)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_probe_config_declares_the_contract_fields(self):
        """The model declares the ``timeout``, ``interval`` and ``path`` fields only."""
        assert set(ProbeConfig.model_fields) == {"timeout", "interval", "path"}

    def test_probe_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        probe = ProbeConfig(timeout=45.0, interval=1.0, path="/healthz")

        assert isinstance(probe.timeout, float)
        assert isinstance(probe.interval, float)
        assert isinstance(probe.path, str)

    def test_probe_config_path_accepts_none(self):
        """``path`` carries the explicit absence of a health path as ``None``."""
        probe = ProbeConfig(path=None)

        assert probe.path is None


class TestProbeConfigLogic:
    """Construction and behavior of ``ProbeConfig``."""

    def test_probe_config_defaults_reproduce_the_established_wait(self):
        """Defaults are timeout 30.0, interval 0.5, path ``None``."""
        probe = ProbeConfig()

        assert probe.timeout == 30.0
        assert probe.interval == 0.5
        assert probe.path is None

    def test_probe_config_partial_override_keeps_the_rest(self):
        """Overriding one bound keeps the other bound and the path at their defaults."""
        probe = ProbeConfig(timeout=45.0)

        assert probe.timeout == 45.0
        assert probe.interval == 0.5
        assert probe.path is None

    def test_probe_config_path_free_construction_is_valid(self):
        """Construction without ``path`` is valid — port readiness applies."""
        probe = ProbeConfig(timeout=0.3, interval=0.05)

        assert probe.path is None

    def test_probe_config_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            ProbeConfig(30.0, 0.5, None)  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("fields", "offender"),
        [
            ({"timeout": 0}, "timeout"),
            ({"timeout": -1.0}, "timeout"),
            ({"interval": 0}, "interval"),
            ({"interval": -1.0}, "interval"),
            ({"interval": 60.0, "timeout": 30.0}, "interval"),
            ({"interval": 0.75, "timeout": 0.5}, "interval"),
        ],
    )
    def test_probe_config_rejects_invalid_bounds(self, fields: dict[str, object], offender: str):
        """Non-positive bounds and an interval above the timeout fail validation."""
        with pytest.raises(ValidationError, match=offender):
            ProbeConfig(**fields)

    def test_probe_config_interval_above_timeout_names_the_rule(self):
        """The interval-above-timeout rejection names the default interval in its message."""
        with pytest.raises(ValidationError, match="the probe interval"):
            ProbeConfig(interval=60.0, timeout=30.0)

    def test_probe_config_accepts_interval_equal_to_timeout(self):
        """The legal boundary ``interval == timeout`` constructs (guards the ``<=`` comparator)."""
        probe = ProbeConfig(timeout=30.0, interval=30.0)

        assert probe.timeout == 30.0
        assert probe.interval == 30.0

    def test_probe_config_accepts_sub_second_bounds(self):
        """Sub-second timeout/interval pairs construct when the interval fits the timeout."""
        probe = ProbeConfig(timeout=0.3, interval=0.05)

        assert probe.timeout == 0.3
        assert probe.interval == 0.05
