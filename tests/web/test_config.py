"""Tests for the `goga_tool_pybuggy.web.config` module (models + the validator)."""

import typing as t

import pytest
from goga_tool_pybuggy.web.config import BrowserSettings, WebConfig, validate_web_config
from prettyplay import BrowserConfig, PrettyConfig
from pydantic import ValidationError

# The contract field list of `BrowserSettings` in signature order.
_BROWSER_CONTRACT_FIELDS: t.Final[list[str]] = [
    "name",
    "headless",
    "screen",
    "endpoint",
    "accept_dialogs",
    "speed",
    "timeout",
]

# The contract field list of `WebConfig` in signature order (the `WebConfigKeys` order minus
# FILENAME — the validation alignment walks it).
_CONTRACT_FIELDS: t.Final[list[str]] = [
    "provider",
    "base_url",
    "model",
    "generation_model",
    "classification_model",
    "generation_prompt",
    "classification_prompt",
    "strict",
    "interactive",
    "polling_timeout",
    "polling_delay",
    "generation_attempts",
    "healing_attempts",
    "llm_request_attempts",
    "send_screenshots",
    "generation_approve",
    "probe_timeout",
    "cache_root",
    "browser",
]


class TestWebConfigModelsContract:
    """Contract tests for the `BrowserSettings` and `WebConfig` models."""

    def test_browser_settings_carries_exactly_seven_fields(self):
        """`BrowserSettings` exposes exactly the seven contract fields in signature order."""
        assert list(BrowserSettings.model_fields) == _BROWSER_CONTRACT_FIELDS

    def test_web_config_carries_exactly_nineteen_fields_in_contract_order(self):
        """`WebConfig` exposes exactly the 19 contract fields in signature order."""
        assert list(WebConfig.model_fields) == _CONTRACT_FIELDS

    def test_models_are_kw_only(self):
        """Both models declare `kw_only=True` — construction is keyword-only."""
        assert BrowserSettings.model_config["kw_only"] is True
        assert WebConfig.model_config["kw_only"] is True

    def test_models_forbid_unknown_keys(self):
        """Both models declare `extra="forbid"` — an unknown key is a validation error."""
        assert BrowserSettings.model_config["extra"] == "forbid"
        assert WebConfig.model_config["extra"] == "forbid"

        with pytest.raises(ValidationError):
            BrowserSettings(name="chromium", unexpected=True)

        with pytest.raises(ValidationError):
            WebConfig(provider="openai", unexpected=True)

    def test_browser_defaults_to_factory_built_settings(self):
        """An omitted `browser` key defaults to a factory-built `BrowserSettings` instance."""
        field = WebConfig.model_fields["browser"]

        assert field.default_factory is BrowserSettings
        assert isinstance(WebConfig().browser, BrowserSettings)


class TestValidateWebConfigContract:
    """Contract tests for the `validate_web_config` routine."""

    def test_validate_web_config_is_module_level_callable(self):
        """`validate_web_config` is a callable on the `web.config` module."""
        import goga_tool_pybuggy.web.config as config_module

        assert callable(config_module.validate_web_config)
        assert config_module.validate_web_config is validate_web_config


class TestWebConfigModelsLogic:
    """Logic tests for the model defaults — the prettyplay mirroring."""

    def test_browser_settings_defaults_mirror_prettyplay(self):
        # Every BrowserSettings default equals the prettyplay BrowserConfig default (dump-level).
        assert BrowserSettings().model_dump() == BrowserConfig().model_dump()
        assert BrowserSettings().model_dump() == {
            "name": "chromium",
            "headless": True,
            "screen": "",
            "endpoint": "",
            "accept_dialogs": False,
            "speed": 100,
            "timeout": 30.0,
        }

    def test_web_config_defaults_mirror_prettyplay(self):
        # Per-field: every WebConfig default equals the PrettyConfig default of the shared name.
        for name in _CONTRACT_FIELDS:
            if name == "browser":
                assert WebConfig().browser.model_dump() == PrettyConfig().browser.model_dump()
                continue

            assert WebConfig.model_fields[name].default == PrettyConfig.model_fields[name].default

        assert WebConfig.model_fields["polling_timeout"].default is None
        assert PrettyConfig.model_fields["polling_timeout"].default is None


class TestValidateWebConfigLogic:
    """Logic tests for the three-rejection validator."""

    def test_validate_web_config_accepts_surveyed_minimum(self):
        # The surveyed minimum validates; browser subkeys and scalars fill in from the defaults.
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

    def test_validate_web_config_rejects_non_mapping_root(self):
        # A document parsing to a non-mapping root fails naming the document.
        with pytest.raises(ValueError, match=r"web\.yml: the document must parse to a mapping"):
            validate_web_config(["not", "a", "mapping"])

    def test_validate_web_config_rejects_empty_mapping(self):
        # An empty document fails naming the document.
        with pytest.raises(ValueError, match=r"web\.yml: the document is empty"):
            validate_web_config({})

    def test_validate_web_config_wraps_validation_error_naming_document(self):
        # A structurally invalid document fails naming the document; the pydantic detail chained.
        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as exc_info:
            validate_web_config({"provider": "nope"})

        assert isinstance(exc_info.value.__cause__, ValidationError)

    def test_web_config_rejects_unknown_key(self):
        # A mistyped key is an extra input — a validation error, never a silent no-op.
        with pytest.raises(ValidationError, match="extra_forbidden"):
            WebConfig.model_validate({"provider": "openai", "browesr": {"name": "chromium"}})
