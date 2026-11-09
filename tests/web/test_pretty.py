"""Tests for the `goga_tool_pybuggy.web.pretty` module (the settings materialization and the
per-test generation-prompt declaration)."""

import inspect

import pytest
from goga_tool_pybuggy.web.pretty import build_pretty_config, generation_prompt
from prettyplay import BrowserConfig, PrettyConfig


class TestGenerationPrompt:
    """Contract tests for the `generation_prompt` decorator."""

    def test_generation_prompt_is_module_level_callable(self):
        """`generation_prompt` is a callable defined on the `web.pretty` module."""
        import goga_tool_pybuggy.web.pretty as pretty_module

        assert callable(pretty_module.generation_prompt)
        assert pretty_module.generation_prompt.__module__ == "goga_tool_pybuggy.web.pretty"

    def test_generation_prompt_attaches_marker_with_stripped_text(self):
        """One prompt marker carries the stripped text and a `usefixtures` stamp lands too."""

        def sample(): ...

        generation_prompt("  Dates render as DD.MM.YYYY.  ")(sample)

        prompt_marks = [m for m in sample.pytestmark if m.name == "pybuggy_generation_prompt"]
        assert len(prompt_marks) == 1
        assert prompt_marks[0].kwargs == {"text": "Dates render as DD.MM.YYYY."}

        usefixtures_marks = [m for m in sample.pytestmark if m.name == "usefixtures"]

        assert len(usefixtures_marks) == 1
        assert usefixtures_marks[0].args == ("web",)

    def test_generation_prompt_returns_function_unchanged(self):
        """The decorator returns the same function object — no wrapping, nothing executed."""

        def sample(): ...

        decorated = generation_prompt("Dates render as DD.MM.YYYY.")(sample)

        assert decorated is sample
        assert callable(decorated)

    def test_generation_prompt_stacks_attaching_own_markers_in_written_order(self):
        """Stacked applications attach one marker each in application order, bottom first."""

        def sample(): ...

        generation_prompt("Dates render as DD.MM.YYYY.")(sample)
        generation_prompt("The #country dropdown is a native <select>.")(sample)

        texts = [m.kwargs["text"] for m in sample.pytestmark if m.name == "pybuggy_generation_prompt"]
        assert texts == ["Dates render as DD.MM.YYYY.", "The #country dropdown is a native <select>."]

    @pytest.mark.parametrize("text", [123, None, "", "   ", "\n\t"])
    def test_generation_prompt_rejects_invalid_text(self, text):
        """Every invalid text — non-string or whitespace-only — fails at decoration time."""
        with pytest.raises(ValueError, match="generation_prompt"):
            generation_prompt(text)

    def test_generation_prompt_double_application_preserves_both_texts(self):
        """The same text applied twice keeps both markers — duplicates are never dropped."""

        def sample(): ...

        generation_prompt("same text")(sample)
        generation_prompt("same text")(sample)

        texts = [m.kwargs["text"] for m in sample.pytestmark if m.name == "pybuggy_generation_prompt"]
        assert texts == ["same text", "same text"]


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

    def test_build_pretty_config_declares_the_prompt_extra_parameter(self):
        """The signature declares the defaulted `prompt_extra` parameter in the last slot."""
        signature = inspect.signature(build_pretty_config)

        assert list(signature.parameters) == ["config", "strict_flag", "interactive_flag", "prompt_extra"]
        assert signature.parameters["prompt_extra"].default == ""


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

    def test_build_pretty_config_prompt_extra_appends_to_document_prompt(self):
        """Extras append after the document prompt — a single newline between, both kept."""
        config = PrettyConfig.model_validate(
            {"provider": "openai", "generation_prompt": "global instructions", "browser": {"name": "chromium"}}
        )

        result = build_pretty_config(config, False, False, prompt_extra="per-test quirk")

        assert result.generation_prompt == "global instructions\nper-test quirk"

    def test_build_pretty_config_prompt_extra_alone_when_document_prompt_empty(self):
        """An empty document prompt is skipped — the extras stand alone with no leading newline."""
        config = PrettyConfig.model_validate({"provider": "openai"})

        result = build_pretty_config(config, False, False, prompt_extra="only extras")

        assert result.generation_prompt == "only extras"

    def test_build_pretty_config_without_prompt_extra_keeps_document_prompt(self):
        """The positional three-argument call is unchanged — the document prompt and OR forcing hold."""
        config = PrettyConfig.model_validate(
            {"provider": "openai", "generation_prompt": "global instructions", "browser": {"name": "chromium"}}
        )

        result = build_pretty_config(config, True, False)

        assert result.generation_prompt == "global instructions"
        assert result.strict is True

    def test_build_pretty_config_both_prompts_empty_keeps_library_default(self):
        """Both parts empty keep the library default — and the all-fields materialization survives."""
        config = PrettyConfig.model_validate({"provider": "openai"})

        result = build_pretty_config(config, False, False)

        assert result.generation_prompt == ""
        assert result.model_fields_set == set(PrettyConfig.model_fields)
