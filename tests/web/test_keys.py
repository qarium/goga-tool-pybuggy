"""Tests for the `goga_tool_pybuggy.web.keys` module (`WebConfigKeys` + `CONFIG_FILE`).

Covers the fixed 20-member key set in contract order and the standard web-config path constant.
"""

import typing as t

from goga_tool_pybuggy.plugin import defaults as plugin_defaults
from goga_tool_pybuggy.web.config import WebConfig
from goga_tool_pybuggy.web.keys import CONFIG_FILE, WebConfigKeys

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
    ("SEND_SCREENSHOTS", "send_screenshots"),
    ("GENERATION_APPROVE", "generation_approve"),
    ("PROBE_TIMEOUT", "probe_timeout"),
    ("CACHE_ROOT", "cache_root"),
    ("BROWSER", "browser"),
]


class TestWebConfigKeysContract:
    """Contract tests for the `WebConfigKeys` enum and the `CONFIG_FILE` constant."""

    def test_web_config_keys_importable_from_location(self):
        """`WebConfigKeys` and `CONFIG_FILE` are importable from the `web.keys` module location."""
        import goga_tool_pybuggy.web.keys as keys_module

        assert keys_module.WebConfigKeys is WebConfigKeys
        assert keys_module.CONFIG_FILE is CONFIG_FILE

    def test_web_config_keys_exposes_twenty_members(self):
        """The enum carries exactly the 20 contract members — no extras, none missing."""
        assert len(WebConfigKeys) == 20

    def test_web_config_keys_members_contract_order_exact_values(self):
        """Members appear in contract order with the exact `web.yml` key values."""
        assert [(member.name, member.value) for member in WebConfigKeys] == _CONTRACT_MEMBERS

    def test_web_config_keys_values_are_str(self):
        """Every member value is a plain `str` (the `web.yml` key spelling)."""
        assert all(isinstance(member.value, str) for member in WebConfigKeys)

    def test_config_file_names_standard_web_config_path(self):
        """`CONFIG_FILE` names the standard platform tool-config path of the web document."""
        assert CONFIG_FILE == ".goga/tools/pybuggy/web.yml"


class TestWebConfigKeysLogic:
    """Logic tests for the `WebConfigKeys` enum and the `CONFIG_FILE` constant."""

    def test_web_config_keys_filename_names_the_document(self):
        # FILENAME names the document file; CONFIG_FILE is built from it (the plugin binding and
        # error-naming source). The plugin cell's gate constant names the same document — the
        # installation gate and the @define.plugin binding read different constants.
        assert WebConfigKeys.FILENAME.value == "web.yml"
        assert CONFIG_FILE == ".goga/tools/pybuggy/web.yml"
        assert plugin_defaults.WEB_CONFIG_FILE == CONFIG_FILE

    def test_web_config_keys_members_mirror_web_config_fields(self):
        # The 19 scalar/browser key members (everything but FILENAME) equal the WebConfig field
        # names in order — the validation alignment.
        members = [member.value for member in WebConfigKeys if member is not WebConfigKeys.FILENAME]

        assert members == list(WebConfig.model_fields)
