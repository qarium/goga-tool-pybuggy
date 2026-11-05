"""Tests for the `WebConfigKeys` enum of the `goga_tool_pybuggy.plugins.web_plugin` module.

Covers the fixed 21-member key set in contract order, the facade re-export, and the standard
web-config path pin against the plugins-cell `defaults.WEB_CONFIG_FILE`.
"""

import typing as t

from goga_tool_pybuggy.plugins import defaults as plugin_defaults
from goga_tool_pybuggy.plugins.web_plugin import WebConfigKeys
from prettyplay import PrettyConfig

# The contract member list: (name, value) pairs in contract order — the order the documenter walks.
_CONTRACT_MEMBERS: t.Final[list[tuple[str, str]]] = [
    ("FILENAME", "web.yml"),
    ("PROVIDER", "provider"),
    ("BASE_URL", "base_url"),
    ("MODEL", "model"),
    ("GENERATION_MODEL", "generation_model"),
    ("CLASSIFICATION_MODEL", "classification_model"),
    ("GENERATION_PROMPT", "generation_prompt"),
    ("CLASSIFICATION_PROMPT", "classification_prompt"),
    ("STRICT", "strict"),
    ("INTERACTIVE", "interactive"),
    ("POLLING_TIMEOUT", "polling_timeout"),
    ("POLLING_DELAY", "polling_delay"),
    ("GENERATION_ATTEMPTS", "generation_attempts"),
    ("HEALING_ATTEMPTS", "healing_attempts"),
    ("LLM_REQUEST_ATTEMPTS", "llm_request_attempts"),
    ("REQUEST_MAX_TOKENS", "request_max_tokens"),
    ("SEND_SCREENSHOTS", "send_screenshots"),
    ("GENERATION_APPROVE", "generation_approve"),
    ("PROBE_TIMEOUT", "probe_timeout"),
    ("CACHE_ROOT", "cache_root"),
    ("BROWSER", "browser"),
]


class TestWebConfigKeysContract:
    """Contract tests for the `WebConfigKeys` enum."""

    def test_web_config_keys_importable_from_location(self):
        """`WebConfigKeys` lives on the `plugins.web_plugin` module and is re-exported by the facade."""
        import goga_tool_pybuggy.plugins as plugins_module
        import goga_tool_pybuggy.plugins.web_plugin as web_plugin_module

        assert web_plugin_module.WebConfigKeys is WebConfigKeys
        assert plugins_module.WebConfigKeys is WebConfigKeys
        assert "WebConfigKeys" in plugins_module.__all__

    def test_web_config_keys_exposes_twenty_one_members(self):
        """The enum carries exactly the 21 contract members — no extras, none missing."""
        assert len(WebConfigKeys) == 21

    def test_web_config_keys_members_contract_order_exact_values(self):
        """Members appear in contract order with the exact `web.yml` key values."""
        assert [(member.name, member.value) for member in WebConfigKeys] == _CONTRACT_MEMBERS

    def test_web_config_keys_values_are_str(self):
        """Every member value is a plain `str` (the `web.yml` key spelling)."""
        assert all(isinstance(member.value, str) for member in WebConfigKeys)


class TestWebConfigKeysLogic:
    """Logic tests for the `WebConfigKeys` enum."""

    def test_web_config_keys_filename_names_the_document(self):
        # FILENAME names the document file; the plugins cell's WEB_CONFIG_FILE constant binds the
        # plugin config and gates the installation — both name the same document.
        assert WebConfigKeys.FILENAME.value == "web.yml"
        assert plugin_defaults.WEB_CONFIG_FILE == ".goga/tools/pybuggy/web.yml"

    def test_web_config_keys_members_mirror_pretty_config_fields(self):
        # The 20 scalar/browser key members (everything but FILENAME) equal the library PrettyConfig
        # field names as a set — the membership alignment and the drift guard: a renamed prettyplay
        # field fails here instead of silently diverging from web.yml. The member order stays the
        # web.yml document contract order (the documenter walks it), not the library field order.
        members = [member.value for member in WebConfigKeys if member is not WebConfigKeys.FILENAME]

        assert set(members) == set(PrettyConfig.model_fields)
