"""Tests for the `goga_tool_pybuggy.web.config` module (the document validator)."""

import pytest
from goga_tool_pybuggy.web.config import validate_web_config
from prettyplay import PrettyConfig
from pydantic import ValidationError


class TestValidateWebConfigContract:
    """Contract tests for the `validate_web_config` routine."""

    def test_validate_web_config_is_module_level_callable(self):
        """`validate_web_config` is a callable on the `web.config` module."""
        import goga_tool_pybuggy.web.config as config_module

        assert callable(config_module.validate_web_config)
        assert config_module.validate_web_config is validate_web_config

    def test_validate_web_config_returns_the_library_model(self):
        """The validated document is the library `PrettyConfig` — no mirror model exists."""
        config = validate_web_config({"provider": "openai", "browser": {"name": "chromium"}})

        assert isinstance(config, PrettyConfig)


class TestValidateWebConfigLogic:
    """Logic tests for the validator — acceptance, defaults, and the rejection set."""

    def test_validate_web_config_accepts_surveyed_minimum(self):
        # The surveyed minimum validates; browser subkeys and scalars fill in from the library defaults.
        config = validate_web_config(
            {
                "provider": "anthropic",
                "generation_model": "glm-5.3",
                "classification_model": "glm-5.3",
                "browser": {"name": "chrome", "headless": False},
            }
        )

        assert config.provider == "anthropic"
        assert config.generation_model == "glm-5.3"
        assert config.browser.name == "chrome"
        assert config.browser.headless is False
        assert config.browser.screen == ""
        assert config.strict is False
        assert config.polling_timeout is None
        assert config.generation_attempts == 3
        assert config.generation_approve is True

    def test_validate_web_config_rejects_non_mapping_root(self):
        # A document parsing to a non-mapping root fails naming the document.
        with pytest.raises(ValueError, match=r"web\.yml: the document must parse to a mapping"):
            validate_web_config(["not", "a", "mapping"])

    def test_validate_web_config_rejects_empty_mapping(self):
        # An empty document fails naming the document.
        with pytest.raises(ValueError, match=r"web\.yml: the document is empty"):
            validate_web_config({})

    def test_validate_web_config_wraps_validation_error_naming_document(self):
        # A document violating the library model fails naming the document; the pydantic detail chained.
        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as exc_info:
            validate_web_config({"provider": "nope"})

        assert isinstance(exc_info.value.__cause__, ValidationError)

    def test_validate_web_config_rejects_unknown_key(self):
        # A mistyped key is an extra input — a validation error, never a silent no-op.
        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as exc_info:
            validate_web_config({"provider": "openai", "browesr": {"name": "chromium"}})

        assert "browesr" in str(exc_info.value.__cause__)

    def test_validate_web_config_rejects_off_matrix_browser_name_at_configphase(self):
        # The library semantic validators run at activation — an off-matrix name fails here,
        # at configphase, not at the first web test.
        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as exc_info:
            validate_web_config({"provider": "openai", "browser": {"name": "safari"}})

        assert "must be one of" in str(exc_info.value.__cause__)

    def test_validate_web_config_rejects_non_ws_endpoint(self):
        # A non-ws/wss remote endpoint fails the library endpoint validator at activation.
        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as exc_info:
            validate_web_config({"provider": "openai", "browser": {"endpoint": "https://example"}})

        assert "ws/wss" in str(exc_info.value.__cause__)

    def test_validate_web_config_rejects_out_of_range_speed(self):
        # An out-of-range speed fails the library pace validator at activation.
        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as exc_info:
            validate_web_config({"provider": "openai", "browser": {"speed": 200}})

        assert "0-100" in str(exc_info.value.__cause__)
