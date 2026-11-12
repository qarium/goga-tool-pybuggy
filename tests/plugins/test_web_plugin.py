"""Tests for the `goga_tool_pybuggy.plugins.web_plugin` module — the web plugin and the config gate."""

import inspect
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import goga_tool_pybuggy.plugins.web_plugin as web_plugin_module
import goga_tool_pybuggy.web.allure_hooks as allure_hooks_module
import pytest
from goga_tool_pybuggy.plugins import defaults
from goga_tool_pybuggy.plugins.loaders import ModuleLoader
from goga_tool_pybuggy.plugins.web_plugin import WebConfigKeys, WebPlugin, web_cache_path
from goga_tool_pybuggy.web.allure_hooks import AllureStepHooks
from goga_tool_pybuggy.web.logging_setup import EventLogFormatter
from prettyplay import PrettyConfig
from pydantic import ValidationError
from yaml import YAMLError

VALID_DOCUMENT = {
    "provider": "openai",
    "generation_model": "g",
    "classification_model": "c",
    "browser": {"name": "chrome"},
}


class _FakePytestConfig:
    """Config double serving typed CLI flags and collecting ini registrations.

    Attributes:
        lines: The ``(name, line)`` pairs every ``addinivalue_line`` call registered.
    """

    def __init__(
        self,
        *,
        strict_mode: bool = False,
        interactive: bool = False,
        browser_endpoint: str | None = None,
    ) -> None:
        self._options = {
            "strict_mode": strict_mode,
            "interactive": interactive,
            "browser_endpoint": browser_endpoint,
        }
        self.lines: list[tuple[str, str]] = []

    def getoption(self, name: str, default: Any = None) -> Any:
        """Serve the typed flag by dest name, accepting the ``--flag`` form too.

        Args:
            name: The option dest (``strict_mode``) or flag (``--strict-mode``).
            default: The value returned when the option is unknown.

        Returns:
            The configured flag value, or ``default`` for an unknown option.
        """
        if name.startswith("-"):
            name = name.lstrip("-").replace("-", "_")

        return self._options.get(name, default)

    def addinivalue_line(self, name: str, line: str) -> None:
        """Record one ini value registration.

        Args:
            name: The ini key being extended.
            line: The registered line.
        """
        self.lines.append((name, line))


class _RefusingPlugin(WebPlugin):
    """Plugin double whose config reader refuses — the unparsable-document seam."""

    @property
    def plugin_config(self) -> dict:
        """Raise the reader's parse error instead of serving a document.

        Returns:
            Never returns — the property raises.

        Raises:
            YAMLError: The simulated reader parse failure.
        """
        raise YAMLError("bad indentation")


class _RecordingPrettyPlay:
    """PrettyPlay double recording the construction and lifecycle the fixture drives.

    Attributes:
        cache_key: The cache key the constructor received.
        cache_path: The cache path the constructor received.
        cleanup: The cleanup switch the constructor received.
        config: The prettyplay config the constructor received.
        added_hooks: The hook objects ``add_hooks`` received, in call order.
        entered: Whether the context manager was entered.
        exited: Whether the context manager was exited.
    """

    def __init__(
        self,
        cache_key: str,
        cache_path: str | None = None,
        *,
        cleanup: bool = True,
        hooks: list[object] | None = None,
        config: PrettyConfig | None = None,
    ) -> None:
        """Record the construction arguments of the runtime.

        Args:
            cache_key: The per-test cache key.
            cache_path: The optional subdirectory inside the cache.
            cleanup: The cache lifecycle switch.
            hooks: The constructor-seeded integrator callbacks.
            config: The programmatic settings layer.
        """
        self.cache_key = cache_key
        self.cache_path = cache_path
        self.cleanup = cleanup
        self.config = config
        self.added_hooks: list[object] = []
        self.entered = False
        self.exited = False

    def add_hooks(self, hooks: object) -> None:
        """Record one late hook attachment.

        Args:
            hooks: The integrator callbacks object the fixture attaches.
        """
        self.added_hooks.append(hooks)

    def __enter__(self) -> "_RecordingPrettyPlay":
        """Open the runtime double.

        Returns:
            The double itself — the yielded runtime.
        """
        self.entered = True

        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the runtime double.

        Args:
            exc_type: The type of the exception leaving the block, if any.
            exc_value: The exception leaving the block, if any.
            traceback: The traceback of the exception leaving the block, if any.
        """
        self.exited = True


def _configured_plugin(
    monkeypatch: pytest.MonkeyPatch,
    document: dict | None = None,
    config: _FakePytestConfig | None = None,
) -> WebPlugin:
    """Build a plugin driven through ``configure`` with a document of the test's choosing.

    Args:
        monkeypatch: The pytest monkeypatch fixture carrying the ``plugin_config`` override.
        document: The parsed document ``plugin_config`` reports; ``None`` keeps a valid one.
        config: The fake pytest config ``configure`` reads the typed flags from.

    Returns:
        The configured plugin — ``configure`` ran, ``activation`` is set.
    """
    plugin = WebPlugin(context={})
    monkeypatch.setattr(plugin, "plugin_config", document if document is not None else VALID_DOCUMENT, raising=False)
    plugin.init_pytest_config(config if config is not None else _FakePytestConfig())
    plugin.configure()

    return plugin


def _wire_recording_prettyplay(monkeypatch: pytest.MonkeyPatch) -> list[_RecordingPrettyPlay]:
    """Patch the module's ``PrettyPlay`` seam to the recording double.

    Args:
        monkeypatch: The pytest monkeypatch fixture replacing the seam.

    Returns:
        The list the seam appends every constructed double to — ``[0]`` after one build.
    """
    made: list[_RecordingPrettyPlay] = []

    def factory(
        cache_key: str,
        cache_path: str | None = None,
        *,
        cleanup: bool = True,
        hooks: list[object] | None = None,
        config: PrettyConfig | None = None,
    ) -> _RecordingPrettyPlay:
        double = _RecordingPrettyPlay(cache_key, cache_path, cleanup=cleanup, hooks=hooks, config=config)
        made.append(double)

        return double

    monkeypatch.setattr(web_plugin_module, "PrettyPlay", factory)

    return made


def _request_for(
    path: str, name: str, originalname: str | None = None, markers: list[pytest.Mark] | None = None
) -> SimpleNamespace:
    """Build a request double whose node carries the addressing attributes of a test item.

    Args:
        path: The module file path of the test item.
        name: The node name of the test item (parametrize-aware).
        originalname: The parametrize-agnostic name; ``None`` omits the attribute.
        markers: The marks of the test item in collection order (bottom decorator first);
            ``None`` serves the empty list.

    Returns:
        The request double the fixture reads ``node`` from.
    """
    node: dict[str, Any] = {
        "path": Path(path),
        "name": name,
        "iter_markers": lambda name_: [m for m in (markers or []) if m.name == name_],
    }

    if originalname is not None:
        node["originalname"] = originalname

    return SimpleNamespace(node=SimpleNamespace(**node))


class TestWebPluginContract:
    """Declared API of the ``WebPlugin`` and ``web_cache_path`` entities."""

    def test_web_plugin_constructs_with_the_namespace_and_loaders(self):
        """The plugin takes the namespace and optional loaders — the activation arrives with ``configure``."""
        parameters = list(inspect.signature(WebPlugin.__init__).parameters)

        assert parameters == ["self", "context", "loaders"]
        assert WebPlugin(context={}).activation is None

    def test_web_plugin_meta_declares_the_name_and_the_document(self):
        """The plugin name is ``pybuggy-web``; its config file is the web config document."""
        plugin = WebPlugin(context={})

        assert plugin.meta.name == "pybuggy-web"
        assert plugin.meta.config_file == defaults.WEB_CONFIG_FILE
        assert plugin.meta.config_file == ".goga/tools/pybuggy/web.yml"

    def test_web_plugin_declares_the_web_options(self):
        """Twenty one options: the 20 config directives bound to their config keys, plus the endpoint.

        Every directive option carries its own ``web.yml`` key as the ``plugin_config_key`` — the
        standard pluginator loading resolves the value; the endpoint option stays CLI-only.
        """
        plugin = WebPlugin(context={})

        options = {option._name: option for option in plugin.plugin_options}

        assert sorted(options) == [
            "base_url",
            "browser",
            "browser_endpoint",
            "cache_root",
            "classification_model",
            "classification_prompt",
            "generation_approve",
            "generation_attempts",
            "generation_model",
            "generation_prompt",
            "healing_attempts",
            "interactive",
            "llm_request_attempts",
            "model",
            "polling_delay",
            "polling_timeout",
            "probe_timeout",
            "provider",
            "request_max_tokens",
            "send_screenshots",
            "strict",
        ]

        directives = {
            member.value: options[member.value]._plugin_config_key
            for member in WebConfigKeys
            if member is not WebConfigKeys.FILENAME
        }

        assert directives == {
            member.value: member.value for member in WebConfigKeys if member is not WebConfigKeys.FILENAME
        }
        assert options["strict"].command_line.opt == "--strict-mode"
        assert options["strict"].command_line.kwargs["action"] == "store_true"
        assert options["interactive"].command_line.opt == "--interactive"
        assert options["interactive"].command_line.kwargs["action"] == "store_true"
        assert options["browser_endpoint"].command_line.opt == "--browser-endpoint"
        assert options["browser_endpoint"].command_line.kwargs["action"] == "store"
        assert options["browser_endpoint"]._nullable is True
        assert options["browser_endpoint"]._plugin_config_key is None

    def test_web_plugin_carries_the_web_fixture(self):
        """A function-scope ``web`` fixture method exists on the plugin."""
        assert WebPlugin.web.name == "web"
        assert callable(WebPlugin.web.__wrapped__)

    def test_web_cache_path_is_a_module_level_callable(self):
        """``web_cache_path`` is a public routine of the plugin module."""
        assert callable(web_cache_path)
        assert web_cache_path.__module__ == "goga_tool_pybuggy.plugins.web_plugin"


class TestWebCachePath:
    """The pure cache-path computation: module stem, class segment, node name."""

    def test_web_cache_path_shapes(self):
        """Plain items render ``<stem>/<name>``; class items insert the class; the parametrize
        suffix addresses — one directory per parameter case."""

        class TestLogin:
            pass

        plain = SimpleNamespace(
            path=Path("/proj/tests/test_search.py"),
            name="test_duckduckgo_search",
            originalname="test_duckduckgo_search",
        )
        grouped = SimpleNamespace(
            path=Path("/proj/tests/test_login.py"), name="test_foo", originalname="test_foo", cls=TestLogin
        )
        parametrized = SimpleNamespace(
            path=Path("/proj/tests/test_mod.py"), name="test_foo[x-1]", originalname="test_foo"
        )

        assert web_cache_path(plain) == "test_search/test_duckduckgo_search"
        assert web_cache_path(grouped) == "test_login/TestLogin/test_foo"
        assert web_cache_path(parametrized) == "test_mod/test_foo[x-1]"

    def test_web_cache_path_sanitizes_unsafe_segment_characters(self):
        """Path-unsafe id characters flatten to dashes — the tail stays one directory."""
        item = SimpleNamespace(path=Path("/proj/tests/test_mod.py"), name="test_foo[a/b\\c:d]")

        assert web_cache_path(item) == "test_mod/test_foo[a-b-c-d]"

    def test_web_cache_path_decodes_the_pytest_ascii_escape(self):
        """A non-latin id restored from pytest's ``\\u`` escape keeps a readable directory."""
        escaped = "test_edit[\\u0438\\u043c\\u044f \\u0438 \\u043e\\u0442\\u0447\\u0435\\u0441\\u0442\\u0432\\u043e]"
        item = SimpleNamespace(path=Path("/proj/tests/test_mod.py"), name=escaped)

        assert web_cache_path(item) == "test_mod/test_edit[имя-и-отчество]"

    def test_web_cache_path_flattens_whitespace_runs_and_keeps_plain_names(self):
        """Space runs flatten to single dashes; an escaping-disabled run keeps the real letters."""
        spaced = SimpleNamespace(path=Path("/proj/tests/test_mod.py"), name="test_foo[a  b]")
        native = SimpleNamespace(path=Path("/proj/tests/test_mod.py"), name="test_foo[имя и отчество]")

        assert web_cache_path(spaced) == "test_mod/test_foo[a-b]"
        assert web_cache_path(native) == "test_mod/test_foo[имя-и-отчество]"


class TestWebPluginOptions:
    """The standard option loading of the config directives — the values resolve before configure."""

    def test_directive_options_resolve_from_the_document(self, monkeypatch: pytest.MonkeyPatch):
        """Every directive option routes its ``web.yml`` key through the standard chain, uncast."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(
            plugin,
            "plugin_config",
            {
                "provider": "anthropic",
                "generation_model": "glm-5.3",
                "polling_delay": 1.5,
                "generation_attempts": 5,
                "cache_root": "/tmp/webcache",
                "browser": {"name": "firefox", "headless": False},
            },
            raising=False,
        )
        plugin.init_pytest_config(_FakePytestConfig())

        assert plugin.provider == "anthropic"
        assert plugin.generation_model == "glm-5.3"
        assert plugin.polling_delay == 1.5
        assert plugin.generation_attempts == 5
        assert plugin.cache_root == "/tmp/webcache"
        assert plugin.browser == {"name": "firefox", "headless": False}

    def test_unset_directive_options_resolve_the_library_defaults(self, monkeypatch: pytest.MonkeyPatch):
        """An absent directive falls back to the library default — the model is the single source.

        The directives whose empty option fallback would diverge carry a ``default_from``
        computed from ``PrettyConfig.model_fields``; the rest fall back to the empty value that
        equals the library default.
        """
        plugin = WebPlugin(context={})
        monkeypatch.setattr(
            plugin, "plugin_config", {"provider": "openai", "browser": {"name": "chromium"}}, raising=False
        )
        plugin.init_pytest_config(_FakePytestConfig())

        assert plugin.provider == "openai"
        assert plugin.model == ""
        assert plugin.polling_timeout is None
        assert plugin.polling_delay == PrettyConfig.model_fields["polling_delay"].get_default()
        assert plugin.generation_attempts == PrettyConfig.model_fields["generation_attempts"].get_default()
        assert plugin.healing_attempts == PrettyConfig.model_fields["healing_attempts"].get_default()
        assert plugin.llm_request_attempts == PrettyConfig.model_fields["llm_request_attempts"].get_default()
        assert plugin.request_max_tokens == PrettyConfig.model_fields["request_max_tokens"].get_default()
        assert plugin.generation_approve is True
        assert plugin.send_screenshots is False
        assert plugin.browser == {"name": "chromium"}


class TestWebPluginConfigure:
    """Configphase behavior: CLI authority, validation, and the env scrub."""

    def test_configure_validates_document_and_scrubs_env(self, monkeypatch: pytest.MonkeyPatch):
        """``configure`` validates the document into the activation and scrubs the env layer."""
        monkeypatch.setenv("PRETTYPLAY_STRICT", "true")
        monkeypatch.setenv("PRETTYPLAY_BROWSER_SPEED", "10")
        monkeypatch.setenv("PYBUGGY_UNRELATED", "keep")

        plugin = _configured_plugin(monkeypatch)

        assert plugin.activation is not None
        assert plugin.activation.provider == "openai"
        assert "PRETTYPLAY_STRICT" not in os.environ
        assert "PRETTYPLAY_BROWSER_SPEED" not in os.environ
        assert os.environ["PYBUGGY_UNRELATED"] == "keep"

    def test_configure_installs_the_event_log_formatter_unconditionally(self, monkeypatch: pytest.MonkeyPatch):
        """``configure`` lands the console formatter on the ``prettyplay`` logger — not allure-gated.

        The requirement pins the install as unconditional: with the guarded allure import
        resolved to ``None`` the formatter still lands, at INFO, exactly once.
        """
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        logger = logging.getLogger("prettyplay")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)

        _configured_plugin(monkeypatch)

        assert logger.level == logging.INFO
        assert [type(handler.formatter) for handler in logger.handlers] == [EventLogFormatter]

    def test_configure_registers_the_generation_prompt_marker(self, monkeypatch: pytest.MonkeyPatch):
        """``configure`` registers the per-test generation-prompt marker with a help line."""
        config = _FakePytestConfig()
        plugin = _configured_plugin(monkeypatch, config=config)

        assert any(name == "markers" and "pybuggy_generation_prompt" in line for name, line in config.lines)
        assert plugin.activation is not None

    def test_configure_registers_the_marker_before_the_document_gates(self, monkeypatch: pytest.MonkeyPatch):
        """The registration precedes the gates — the marker line is recorded even in a failing run."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(plugin, "plugin_config", {"provider": "nope"}, raising=False)
        config = _FakePytestConfig()
        plugin.init_pytest_config(config)

        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document"):
            plugin.configure()

        assert any(name == "markers" for name, _ in config.lines)

    def test_configure_applies_cli_authority(self, monkeypatch: pytest.MonkeyPatch):
        """A typed ``--strict-mode`` flag beats an explicit ``strict: false`` in the document."""
        flagged = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": {"name": "chromium"}, "strict": False},
            config=_FakePytestConfig(strict_mode=True),
        )
        unflagged = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": {"name": "chromium"}, "strict": False},
        )

        assert flagged.strict is True
        assert unflagged.strict is False

    def test_configure_applies_cli_authority_interactive_flag(self, monkeypatch: pytest.MonkeyPatch):
        """A typed ``--interactive`` flag beats an explicit ``interactive: false`` in the document."""
        flagged = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": {"name": "chromium"}, "interactive": False},
            config=_FakePytestConfig(interactive=True),
        )
        unflagged = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": {"name": "chromium"}, "interactive": False},
        )

        assert flagged.interactive is True
        assert unflagged.interactive is False

    def test_configure_applies_cli_authority_browser_endpoint(self, monkeypatch: pytest.MonkeyPatch):
        """A typed ``--browser-endpoint`` beats the document's ``browser.endpoint``; untyped keeps it."""
        document = {"provider": "openai", "browser": {"name": "chromium", "endpoint": "wss://doc.example"}}
        flagged = _configured_plugin(
            monkeypatch, document=document, config=_FakePytestConfig(browser_endpoint="ws://flag.example")
        )
        unflagged = _configured_plugin(monkeypatch, document=document)

        assert flagged.activation is not None
        assert flagged.activation.browser.endpoint == "ws://flag.example"
        assert unflagged.activation is not None
        assert unflagged.activation.browser.endpoint == "wss://doc.example"

    def test_configure_browser_endpoint_creates_the_missing_browser_section(self, monkeypatch: pytest.MonkeyPatch):
        """A typed flag on a document without the browser section validates the created section."""
        plugin = _configured_plugin(
            monkeypatch, document={"provider": "openai"}, config=_FakePytestConfig(browser_endpoint="ws://flag.example")
        )

        assert plugin.activation is not None
        assert plugin.activation.browser.endpoint == "ws://flag.example"
        assert plugin.activation.browser.name == "chromium"

    def test_configure_browser_endpoint_overrides_a_null_browser_section(self, monkeypatch: pytest.MonkeyPatch):
        """A ``browser:`` null document with a typed flag validates the created section."""
        plugin = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": None},
            config=_FakePytestConfig(browser_endpoint="ws://flag.example"),
        )

        assert plugin.activation is not None
        assert plugin.activation.browser.endpoint == "ws://flag.example"

    def test_configure_typed_empty_endpoint_forces_local_launch(self, monkeypatch: pytest.MonkeyPatch):
        """A typed empty flag applies verbatim — it clears the document endpoint (the local launch)."""
        plugin = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": {"name": "chromium", "endpoint": "wss://doc.example"}},
            config=_FakePytestConfig(browser_endpoint=""),
        )

        assert plugin.activation is not None
        assert plugin.activation.browser.endpoint == ""

    def test_configure_fails_configphase_on_invalid_typed_endpoint(self, monkeypatch: pytest.MonkeyPatch):
        """A typed non-URL endpoint fails the same document gate at configphase."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(
            plugin, "plugin_config", {"provider": "openai", "browser": {"name": "chromium"}}, raising=False
        )
        plugin.init_pytest_config(_FakePytestConfig(browser_endpoint="not-an-endpoint"))

        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as excinfo:
            plugin.configure()

        assert "ws/wss or http/https" in str(excinfo.value.__cause__)
        assert plugin.activation is None

    def test_configure_does_not_mutate_the_read_document(self, monkeypatch: pytest.MonkeyPatch):
        """The endpoint injection works on a copy — the document the reader supplied stays intact."""
        document = {"provider": "openai", "browser": {"name": "chromium", "endpoint": "wss://doc.example"}}
        plugin = _configured_plugin(
            monkeypatch, document=document, config=_FakePytestConfig(browser_endpoint="ws://flag.example")
        )

        assert plugin.activation is not None
        assert plugin.activation.browser.endpoint == "ws://flag.example"
        assert document["browser"]["endpoint"] == "wss://doc.example"
        assert set(document["browser"]) == {"name", "endpoint"}

    def test_configure_drops_the_pipelines_section_before_validation(self, monkeypatch: pytest.MonkeyPatch):
        """The foreign ``pipelines`` section (the web autonomy axis) is dropped from the copy —
        the document with it still validates; the read document keeps it."""
        document = {
            "provider": "openai",
            "browser": {"name": "chromium"},
            "pipelines": {"web.automate": {"autonomous": True}},
        }
        plugin = _configured_plugin(monkeypatch, document=document)

        assert plugin.activation is not None
        assert plugin.activation.provider == "openai"
        assert document["pipelines"] == {"web.automate": {"autonomous": True}}

    def test_configure_resolves_modes_from_the_validated_document(self, monkeypatch: pytest.MonkeyPatch):
        """String-typed mode values resolve through the validated model — never the raw parse.

        The options route the raw document values without casting; the resolved options must
        mirror the validated activation instead, so a document the model reads as false never
        flips a mode on (an accidentally interactive run could hang CI).
        """
        document = {
            "provider": "openai",
            "browser": {"name": "chromium"},
            "strict": "false",
            "interactive": "no",
        }
        unflagged = _configured_plugin(monkeypatch, document=document)
        flagged = _configured_plugin(
            monkeypatch, document=document, config=_FakePytestConfig(strict_mode=True, interactive=True)
        )

        assert unflagged.activation is not None
        assert unflagged.activation.strict is False
        assert unflagged.activation.interactive is False
        assert unflagged.strict is False
        assert unflagged.interactive is False
        assert flagged.strict is True
        assert flagged.interactive is True

    def test_configure_fails_configphase_on_invalid_document(self, monkeypatch: pytest.MonkeyPatch):
        """A structurally invalid document fails the run naming the document; the detail chained."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(plugin, "plugin_config", {"provider": "nope"}, raising=False)
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as excinfo:
            plugin.configure()

        assert isinstance(excinfo.value.__cause__, ValidationError)
        assert plugin.activation is None

    def test_configure_fails_configphase_on_unparsable_document(self, monkeypatch: pytest.MonkeyPatch):
        """A document the config reader cannot parse surfaces as the clean wrap, cause chained."""
        plugin = _RefusingPlugin(context={})
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: unparsable document.*bad indentation") as excinfo:
            plugin.configure()

        assert isinstance(excinfo.value.__cause__, YAMLError)
        assert plugin.activation is None

    def test_configure_fills_library_defaults_from_surveyed_minimum(self, monkeypatch: pytest.MonkeyPatch):
        """The surveyed minimum validates into the library model; the omitted keys fill from defaults."""
        plugin = _configured_plugin(
            monkeypatch,
            document={
                "provider": "anthropic",
                "generation_model": "glm-5.3",
                "classification_model": "glm-5.3",
                "browser": {"name": "chrome", "headless": False},
            },
        )

        assert isinstance(plugin.activation, PrettyConfig)
        assert plugin.activation.provider == "anthropic"
        assert plugin.activation.generation_model == "glm-5.3"
        assert plugin.activation.browser.name == "chrome"
        assert plugin.activation.browser.headless is False
        assert plugin.activation.browser.screen == ""
        assert plugin.activation.strict is False
        assert plugin.activation.polling_timeout is None
        assert plugin.activation.generation_attempts == 3
        assert plugin.activation.generation_approve is True

    def test_configure_fails_configphase_on_non_mapping_document(self, monkeypatch: pytest.MonkeyPatch):
        """A document parsing to a non-mapping root fails naming the document."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(plugin, "plugin_config", ["not", "a", "mapping"], raising=False)
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: the document must parse to a mapping"):
            plugin.configure()

        assert plugin.activation is None

    def test_configure_fails_configphase_on_empty_document(self, monkeypatch: pytest.MonkeyPatch):
        """An empty document fails naming the document."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(plugin, "plugin_config", {}, raising=False)
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: the document is empty"):
            plugin.configure()

        assert plugin.activation is None

    def test_configure_fails_configphase_on_unknown_key(self, monkeypatch: pytest.MonkeyPatch):
        """A mistyped key is an extra input — a validation error, never a silent no-op."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(
            plugin, "plugin_config", {"provider": "openai", "browesr": {"name": "chromium"}}, raising=False
        )
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as excinfo:
            plugin.configure()

        assert "browesr" in str(excinfo.value.__cause__)
        assert plugin.activation is None

    def test_configure_fails_configphase_on_off_matrix_browser_name(self, monkeypatch: pytest.MonkeyPatch):
        """The library semantic validators run at activation — an off-matrix name fails at configphase."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(
            plugin, "plugin_config", {"provider": "openai", "browser": {"name": "safari"}}, raising=False
        )
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as excinfo:
            plugin.configure()

        assert "must be one of" in str(excinfo.value.__cause__)
        assert plugin.activation is None

    def test_configure_accepts_http_cdp_endpoint(self, monkeypatch: pytest.MonkeyPatch):
        """prettyplay 0.0.4: an http/https endpoint addresses a CDP browser of the chromium family."""
        plugin = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": {"name": "chromium", "endpoint": "https://cdp.example"}},
        )

        assert plugin.activation is not None
        assert plugin.activation.browser.endpoint == "https://cdp.example"

    def test_configure_fails_configphase_on_document_endpoint(self, monkeypatch: pytest.MonkeyPatch):
        """A document endpoint that is neither ws/wss nor http/https fails the library validator."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(
            plugin,
            "plugin_config",
            {"provider": "openai", "browser": {"name": "chromium", "endpoint": "not-an-endpoint"}},
            raising=False,
        )
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as excinfo:
            plugin.configure()

        assert "ws/wss or http/https" in str(excinfo.value.__cause__)
        assert plugin.activation is None

    def test_configure_fails_configphase_on_out_of_range_speed(self, monkeypatch: pytest.MonkeyPatch):
        """An out-of-range speed fails the library pace validator at activation."""
        plugin = WebPlugin(context={})
        monkeypatch.setattr(plugin, "plugin_config", {"provider": "openai", "browser": {"speed": 200}}, raising=False)
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: invalid web config document") as excinfo:
            plugin.configure()

        assert "0-100" in str(excinfo.value.__cause__)
        assert plugin.activation is None


class TestWebPluginConfigureRealDocument:
    """Configphase against the real on-disk document — the pluginator read seam."""

    def test_configure_reads_the_real_document_from_the_standard_path(self, web_config):
        """A valid document at the fixed path configures the plugin through the real reader."""
        web_config(
            "provider: anthropic\n"
            "generation_model: g\n"
            "classification_model: c\n"
            "browser:\n"
            "  name: firefox\n"
            "  headless: false\n"
        )

        plugin = WebPlugin(context={})
        plugin.init_pytest_config(_FakePytestConfig())
        plugin.configure()

        assert plugin.activation is not None
        assert plugin.activation.provider == "anthropic"
        assert plugin.activation.browser.name == "firefox"
        assert plugin.activation.browser.headless is False

    def test_configure_fails_on_an_unparsable_real_document(self, web_config):
        """A malformed document on disk fails configphase with the parse cause chained."""
        web_config("provider: [unclosed\n")

        plugin = WebPlugin(context={})
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: unparsable document") as excinfo:
            plugin.configure()

        assert isinstance(excinfo.value.__cause__, YAMLError)
        assert plugin.activation is None

    def test_configure_reports_a_non_mapping_real_document_as_empty(self, web_config):
        """A list document collapses to the reader's empty default — the empty-document rejection.

        The pluginator reader replaces a non-mapping parse with its default (empty) config, so
        the user-facing failure of such a file is the empty-document error, not the mapping one.
        """
        web_config("- just\n- a list\n")

        plugin = WebPlugin(context={})
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match="the document is empty"):
            plugin.configure()

        assert plugin.activation is None


class TestWebPluginWebFixture:
    """The function-scope ``web`` fixture: address, config, guarded hooks, lifecycle."""

    def test_web_fixture_builds_address_and_cleanup(self, monkeypatch: pytest.MonkeyPatch):
        """The runtime is addressed from the item, cleanup-disabled, allure-absent, closed."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(monkeypatch)
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        runtime = next(generator)

        assert runtime is made[0]
        assert made[0].cache_key == "test_a"
        assert made[0].cache_path == "test_a/test_a"
        assert made[0].cleanup is False
        assert made[0].config.cache_root == str(Path("/proj/tests").resolve())
        assert made[0].config.browser.name == "chrome"
        assert made[0].added_hooks == []
        assert made[0].entered

        with pytest.raises(StopIteration):
            next(generator)

        assert made[0].exited

    def test_web_fixture_addresses_each_parameter_case_apart(self, monkeypatch: pytest.MonkeyPatch):
        """A parametrized item addresses its own cache directory — the suffix rides the path."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(monkeypatch)
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a[x-1]", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].cache_key == "test_a[x-1]"
        assert made[0].cache_path == "test_a/test_a[x-1]"

    def test_web_fixture_carries_the_typed_endpoint(self, monkeypatch: pytest.MonkeyPatch):
        """The typed endpoint flows through the activation into the runtime config unchanged."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": {"name": "chromium"}},
            config=_FakePytestConfig(browser_endpoint="ws://flag.example"),
        )
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].config.browser.endpoint == "ws://flag.example"

    def test_web_fixture_closes_runtime_when_test_fails(self, monkeypatch: pytest.MonkeyPatch):
        """An exception raised in the test body still closes the runtime — no browser leak."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(monkeypatch)
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        with pytest.raises(AssertionError, match="test failed"):
            generator.throw(AssertionError("test failed"))

        assert made[0].exited

    def test_web_fixture_honors_cache_root_key(self, monkeypatch: pytest.MonkeyPatch):
        """A non-empty ``cache_root`` in the document passes through without the item override."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(
            monkeypatch, document={"provider": "openai", "browser": {"name": "chromium"}, "cache_root": "/tmp/webcache"}
        )
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].config.cache_root == "/tmp/webcache"

    def test_web_fixture_modes_mirror_the_validated_document(self, monkeypatch: pytest.MonkeyPatch):
        """A string-typed ``strict: "false"`` document builds a non-strict runtime config.

        The raw parse never reaches the prettyplay config — the modes flow through the validated
        activation and the CLI flags only, so the descriptor's bare ``bool()`` cast cannot turn a
        denied mode on.
        """
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(
            monkeypatch,
            document={"provider": "openai", "browser": {"name": "chromium"}, "strict": "false", "interactive": "no"},
        )
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].config.strict is False
        assert made[0].config.interactive is False

    def test_web_fixture_without_configure_raises_runtime_error(self, monkeypatch: pytest.MonkeyPatch):
        """Driving the fixture on an unconfigured plugin names the missing configure step."""
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a")

        with pytest.raises(RuntimeError, match="not configured"):
            next(WebPlugin.web.__wrapped__(WebPlugin(context={}), request))

        assert made == []

    def test_web_fixture_attaches_allure_hooks_when_importable(self, monkeypatch: pytest.MonkeyPatch):
        """An importable allure attaches the reporting hooks to the runtime exactly once."""
        monkeypatch.setattr(allure_hooks_module, "allure", object())
        plugin = _configured_plugin(monkeypatch)
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert len(made[0].added_hooks) == 1
        assert isinstance(made[0].added_hooks[0], AllureStepHooks)

    def test_web_fixture_resolves_outside_project_root(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """The cache root derives from the item's own file — never from the cwd."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        monkeypatch.chdir(tmp_path)
        plugin = _configured_plugin(monkeypatch)
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/elsewhere/tests/test_a.py", "test_a", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].config.cache_root == str(Path("/elsewhere/tests").resolve())

    def test_web_fixture_collects_prompt_extras_in_written_order(self, monkeypatch: pytest.MonkeyPatch):
        """The marker texts apply in written order (top decorator first), joined by one newline."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(monkeypatch, document={"provider": "openai", "browser": {"name": "chromium"}})
        made = _wire_recording_prettyplay(monkeypatch)
        markers = [
            pytest.mark.pybuggy_generation_prompt(text="bottom text").mark,
            pytest.mark.pybuggy_generation_prompt(text="top text").mark,
        ]
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a", markers=markers)

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].config.generation_prompt == "top text\nbottom text"
        assert made[0].cleanup is False
        assert made[0].cache_key == "test_a"

    def test_web_fixture_appends_extras_to_the_document_prompt(self, monkeypatch: pytest.MonkeyPatch):
        """The document prompt comes first, the per-test extras second, one newline between."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(
            monkeypatch,
            document={
                "provider": "openai",
                "generation_prompt": "global instructions",
                "browser": {"name": "chromium"},
            },
        )
        made = _wire_recording_prettyplay(monkeypatch)
        markers = [
            pytest.mark.pybuggy_generation_prompt(text="extra two").mark,
            pytest.mark.pybuggy_generation_prompt(text="extra one").mark,
        ]
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a", markers=markers)

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].config.generation_prompt == "global instructions\nextra one\nextra two"

    def test_web_fixture_without_markers_builds_the_unchanged_config(self, monkeypatch: pytest.MonkeyPatch):
        """No markers — the runtime config is exactly the activation, no cross-test leakage."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(monkeypatch, document={"provider": "openai", "browser": {"name": "chromium"}})
        made = _wire_recording_prettyplay(monkeypatch)
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a")

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].config.generation_prompt == plugin.activation.generation_prompt == ""
        assert made[0].config.provider == "openai"

    def test_web_fixture_ignores_a_marker_without_the_text_kwarg(self, monkeypatch: pytest.MonkeyPatch):
        """A hand-written marker without ``text`` contributes nothing — never a setup crash."""
        monkeypatch.setattr(allure_hooks_module, "allure", None)
        plugin = _configured_plugin(monkeypatch, document={"provider": "openai", "browser": {"name": "chromium"}})
        made = _wire_recording_prettyplay(monkeypatch)
        markers = [
            pytest.mark.pybuggy_generation_prompt.mark,
            pytest.mark.pybuggy_generation_prompt(text="real text").mark,
        ]
        request = _request_for("/proj/tests/test_a.py", "test_a", "test_a", markers=markers)

        generator = WebPlugin.web.__wrapped__(plugin, request)
        next(generator)

        assert made[0].config.generation_prompt == "real text"


class TestWebPluginDiscovery:
    """The install-time fixture discovery of the web document's ``loader:`` section."""

    @staticmethod
    def _make_presets_tree(tmp_path: Path):
        """Create a one-fixture ``presets/orders/api.py`` package tree under ``tmp_path``."""
        presets = tmp_path / "presets"
        (presets / "orders").mkdir(parents=True)
        (presets / "__init__.py").write_text("")
        (presets / "orders" / "__init__.py").write_text("")
        (presets / "orders" / "api.py").write_text(
            "import pytest\n\n\n@pytest.fixture\ndef get_orders():\n    return 1\n"
        )

    def _write_web_document(self, tmp_path: Path) -> None:
        """Write a web document carrying the provider, the browser, and a ``loader:`` section."""
        document = tmp_path / ".goga" / "tools" / "pybuggy" / "web.yml"
        document.parent.mkdir(parents=True)
        document.write_text(
            "provider: openai\nbrowser:\n  name: chromium\nloader:\n  packages:\n    - presets\n",
            encoding="utf-8",
        )

    def test_loader_section_discovers_and_never_rides_into_the_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The web document's ``loader:`` section wires an external fixture package into the run
        at construction, and configure treats the section as a foreign one — never an unknown
        key failing the gate."""
        self._make_presets_tree(tmp_path)
        self._write_web_document(tmp_path)
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)

        context: dict[str, Any] = {}
        plugin = WebPlugin(context=context)

        assert context["pytest_plugins"] == ["presets.orders.api"]

        plugin.init_pytest_config(_FakePytestConfig())
        plugin.configure()

        assert plugin.activation is not None
        assert plugin.activation.provider == "openai"

    def test_explicit_loaders_join_the_section(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """The explicit construction loaders run in addition to the document's section."""
        self._make_presets_tree(tmp_path)

        document = tmp_path / ".goga" / "tools" / "pybuggy" / "web.yml"
        document.parent.mkdir(parents=True)
        document.write_text("provider: openai\nbrowser:\n  name: chromium\n", encoding="utf-8")
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)

        context: dict[str, Any] = {}

        WebPlugin(context=context, loaders=[ModuleLoader("presets.orders.api", required=False)])

        assert context["pytest_plugins"] == ["presets.orders.api"]

    def test_loader_only_document_still_fails_the_empty_gate(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A document carrying only the foreign sections fails the empty gate — it must still
        carry at least the provider and the browser name."""
        document = tmp_path / ".goga" / "tools" / "pybuggy" / "web.yml"
        document.parent.mkdir(parents=True)
        document.write_text("loader:\n  modules:\n    - {name: presets, required: false}\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        plugin = WebPlugin(context={})
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"web\.yml: the document is empty"):
            plugin.configure()
