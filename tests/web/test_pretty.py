"""Tests for the `goga_tool_pybuggy.web.pretty` module (the prettyplay settings materialization)."""

import pytest
from goga_tool_pybuggy.web.pretty import build_pretty_config
from prettyplay import BrowserConfig, PrettyConfig


class TestBuildPrettyConfigContract:
    """Contract tests for the `build_pretty_config` routine."""

    def test_build_pretty_config_is_module_level_callable(self):
        """`build_pretty_config` is a callable on the `web.pretty` module."""
        import goga_tool_pybuggy.web.pretty as pretty_module

        assert callable(pretty_module.build_pretty_config)
        assert pretty_module.build_pretty_config is build_pretty_config

    def test_build_pretty_config_returns_pretty_config_instance(self):
        """Called with `(PrettyConfig, bool, bool)` the routine returns a `PrettyConfig` instance."""
        config = PrettyConfig.model_validate({"provider": "openai"})

        assert isinstance(build_pretty_config(config, False, False), PrettyConfig)


class TestBuildPrettyConfigLogic:
    """Logic tests for the field mapping, the OR semantics, and the explicit materialization."""

    def test_build_pretty_config_maps_every_field(self):
        """Every surveyed field lands on the same-named prettyplay field; defaults stay defaults."""
        config = PrettyConfig.model_validate(
            {
                "provider": "anthropic",
                "base_url": "https://api.example",
                "generation_model": "g",
                "classification_model": "c",
                "generation_attempts": 7,
                "probe_timeout": 3.0,
                "cache_root": "/tmp/x",
                "browser": {"name": "firefox", "speed": 50},
            }
        )

        result = build_pretty_config(config, False, False)

        assert result.provider == "anthropic"
        assert result.base_url == "https://api.example"
        assert result.generation_model == "g"
        assert result.classification_model == "c"
        assert result.generation_attempts == 7
        assert result.probe_timeout == 3.0
        assert result.cache_root == "/tmp/x"
        assert result.browser.speed == 50
        assert result.polling_timeout is None
        assert result.generation_approve is True

    def test_build_pretty_config_materializes_every_field_explicitly(self):
        """The load-bearing materialization: every field lands in the constructed model — the
        runtime adopts it verbatim, making the web config the single source."""
        config = PrettyConfig.model_validate({"provider": "openai", "browser": {"name": "firefox"}})

        result = build_pretty_config(config, False, False)

        assert result.model_fields_set == set(PrettyConfig.model_fields)
        assert result.browser.model_fields_set == set(BrowserConfig.model_fields)

    @pytest.mark.parametrize(
        ("config_value", "flag", "expected"),
        [(False, False, False), (False, True, True), (True, False, True), (True, True, True)],
    )
    def test_build_pretty_config_or_semantics_forces_on_never_off(self, config_value, flag, expected):
        """The same boundary table covers strict and interactive — a flag forces on, never off."""
        config = PrettyConfig.model_validate({"strict": config_value, "interactive": config_value})

        assert build_pretty_config(config, flag, False).strict == expected
        assert build_pretty_config(config, False, flag).interactive == expected
