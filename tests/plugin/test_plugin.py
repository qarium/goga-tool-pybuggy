"""Tests for the `goga_tool_pybuggy.plugin` cell (`ApiPlugin` + service constants).

Options resolve via env vars (``BASE_URL``/``API_TIMEOUT``); ``Api`` is mocked to stay independent of the stub ``resq``.
"""

import inspect
from unittest import mock

import pytest
from goga_tool_pybuggy.plugin import ApiPlugin
from goga_tool_pybuggy.plugin import plugin as plugin_module
from goga_tool_pybuggy.plugin.loaders import PackageLoader
from goga_tool_pybuggy.sandbox.config import SandboxConfig, ServiceConfig, StartupData

# Jinja2 is a core dependency, so the render-path tests run unconditionally.

# Jinja base_url template exercising conditional logic + the match_re test.
_JINJA_CONDITIONAL_URL = (
    "http://x/api/v1{% if service_version is match_re('^feature-.*$') %}-{{ service_version }}{% endif %}"
)

# Generated-fixture source for the `_load_plugins` tests (carries a `@pytest.fixture`).
_GENERATED_FIXTURE_SOURCE = """
import pytest


@pytest.fixture
def get_orders():
    return 1
"""


# Minimal pytest ``Config`` stand-ins for the ``configure()`` lifecycle tests:
# only ``invocation_params.args``, ``option`` and ``getoption`` are emulated.
class _FakeOption:
    """Minimal ``Config.option`` stand-in: an attribute namespace."""

    def __init__(self, **options: object) -> None:
        self.__dict__.update(options)


class _FakeInvocationParams:
    """Minimal ``Config.invocation_params`` stand-in: exposes ``args``."""

    def __init__(self, args: list[str]) -> None:
        self.args = list(args)


class _FakePytestConfig:
    """Minimal pytest ``Config`` stand-in for the ``configure()`` lifecycle."""

    def __init__(
        self,
        *,
        args: list[str] | None = None,
        options: dict[str, object] | None = None,
        getopt: dict[str, object] | None = None,
    ) -> None:
        self.invocation_params = _FakeInvocationParams(args or [])
        self.option = _FakeOption(**(options or {}))
        self._getopt = getopt or {}

    def getoption(self, name: str, default: object = None) -> object:
        return self._getopt.get(name, default)


def _lifecycle(
    plugin: ApiPlugin,
    *,
    args: list[str] | None = None,
    options: dict[str, object] | None = None,
    getopt: dict[str, object] | None = None,
) -> None:
    """Emulate pluginator's ``pytest_configure``: init config, then ``configure()``."""
    plugin.init_pytest_config(_FakePytestConfig(args=args, options=options, getopt=getopt))
    plugin.configure()


class TestApiPluginContract:
    """Contract tests for `ApiPlugin`."""

    def test_api_plugin_importable_from_facade(self):
        """The ApiPlugin class is re-exported by the plugin cell facade."""
        import goga_tool_pybuggy.plugin as plugin_facade

        assert plugin_facade.ApiPlugin is ApiPlugin

    def test_api_plugin_importable_from_location(self):
        """The ApiPlugin class is importable from its defining plugin module."""
        import goga_tool_pybuggy.plugin.plugin as plugin_module

        assert plugin_module.ApiPlugin is ApiPlugin

    def test_api_plugin_is_class(self):
        """ApiPlugin is defined as a class."""
        assert isinstance(ApiPlugin, type)

    @pytest.mark.parametrize(
        "option",
        [
            "base_url",
            "headers",
            "timeout",
            "retries",
            "assert_timeout",
            "assert_delay",
            "assert_field_class",
            "assert_response_class",
        ],
    )
    def test_api_plugin_has_option_descriptor(self, option):
        """Every canonical CLI option is declared as a descriptor attribute on ApiPlugin."""
        assert hasattr(ApiPlugin, option)

    def test_api_plugin_has_no_body_key_options(self):
        """The removed data_key/error_key options are absent from the plugin."""
        assert not hasattr(ApiPlugin, "data_key")
        assert not hasattr(ApiPlugin, "error_key")

    def test_api_plugin_has_api_method(self):
        """The api fixture method is callable on ApiPlugin."""
        assert callable(ApiPlugin.api)

    def test_api_plugin_has_collection_modifyitems_hook(self):
        """The pytest_collection_modifyitems hook is callable on ApiPlugin."""
        assert callable(ApiPlugin.pytest_collection_modifyitems)

    def test_api_plugin_has_configure_method(self):
        # configure() is a pluginator lifecycle callback (no @pytest.hookimpl).
        assert callable(ApiPlugin.configure)
        assert "pytest.hookimpl" not in str(ApiPlugin.configure.__dict__)

    def test_api_plugin_init_accepts_default_retries(self):
        """The constructor accepts an optional default_retries parameter defaulting to None."""
        sig = inspect.signature(ApiPlugin.__init__)

        assert "default_retries" in sig.parameters
        assert sig.parameters["default_retries"].default is None

    def test_api_plugin_init_accepts_default_assert_timeout(self):
        """The constructor accepts an optional default_assert_timeout parameter defaulting to None."""
        sig = inspect.signature(ApiPlugin.__init__)

        assert "default_assert_timeout" in sig.parameters
        assert sig.parameters["default_assert_timeout"].default is None

    def test_api_plugin_init_accepts_default_assert_delay(self):
        """The constructor accepts an optional default_assert_delay parameter defaulting to None."""
        sig = inspect.signature(ApiPlugin.__init__)

        assert "default_assert_delay" in sig.parameters
        assert sig.parameters["default_assert_delay"].default is None

    def test_plugin_config_keys_enum(self):
        """Each PluginConfigKeys member maps to its canonical snake_case config key."""
        from goga_tool_pybuggy.plugin.plugin import PluginConfigKeys

        assert PluginConfigKeys.BASE_URL.value == "base_url"
        assert PluginConfigKeys.HEADERS.value == "headers"
        assert PluginConfigKeys.TIMEOUT.value == "timeout"
        assert PluginConfigKeys.RETRIES.value == "retries"
        assert PluginConfigKeys.LOADER.value == "loader"
        assert PluginConfigKeys.ASSERT_TIMEOUT.value == "assert_timeout"
        assert PluginConfigKeys.ASSERT_DELAY.value == "assert_delay"
        assert PluginConfigKeys.ASSERT_FIELD_CLASS.value == "assert_field_class"
        assert PluginConfigKeys.ASSERT_RESPONSE_CLASS.value == "assert_response_class"

    def test_plugin_config_keys_set_is_fixed(self):
        """The key set is exactly the nine canonical members (no body keys)."""
        from goga_tool_pybuggy.plugin.plugin import PluginConfigKeys

        assert {member.name for member in PluginConfigKeys} == {
            "BASE_URL",
            "HEADERS",
            "TIMEOUT",
            "RETRIES",
            "LOADER",
            "ASSERT_TIMEOUT",
            "ASSERT_DELAY",
            "ASSERT_FIELD_CLASS",
            "ASSERT_RESPONSE_CLASS",
        }

    def test_env_var_names_contract(self):
        """The env-contract names are exactly BASE_URL and API_TIMEOUT."""
        from goga_tool_pybuggy.plugin import envvars

        assert envvars.BASE_URL == "BASE_URL"
        assert envvars.API_TIMEOUT == "API_TIMEOUT"

    def test_api_plugin_has_sandbox_activation_defaulting_to_none(self, tmp_path, monkeypatch):
        """Plain construction leaves ``sandbox_activation`` at None; it is not a constructor kwarg."""
        monkeypatch.chdir(tmp_path)

        plugin = ApiPlugin(context={})

        assert plugin.sandbox_activation is None
        assert "sandbox_activation" not in inspect.signature(ApiPlugin.__init__).parameters


class TestApiPluginLogic:
    """Behavioral logic tests for the `api` fixture.

    pytest 9 forbids calling fixture methods directly, so the raw function is reached via `__wrapped__`.
    """

    def test_api_fixture_builds_api_from_options(self, tmp_path, monkeypatch):
        """The api fixture builds Api from env-resolved base_url/timeout and plugin-config assert options."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://x.example")
        monkeypatch.setenv("API_TIMEOUT", "5")

        plugin = ApiPlugin(context={})
        # The assert/class options resolve from plugin config (no pytest-config step here).
        plugin.plugin_config = {
            "assert_timeout": 10,
            "assert_delay": 0.5,
            "assert_field_class": "mod:FieldCls",
            "assert_response_class": "mod:ResponseCls",
        }
        # base_url is rendered once in configure(); a plain URL renders to itself.
        _lifecycle(plugin)

        with mock.patch("goga_tool_pybuggy.plugin.plugin.Api") as mock_api:
            gen = ApiPlugin.api.__wrapped__(plugin)
            result = next(gen)  # drive the generator up to the yield

        mock_api.assert_called_once()
        assert mock_api.call_args.kwargs == {
            "base_url": "https://x.example",
            "headers": {},
            "timeout": 5.0,
            "assert_timeout": 10,
            "assert_delay": 0.5,
            "assert_field_class": "mod:FieldCls",
            "assert_response_class": "mod:ResponseCls",
        }
        # Minimal profile: no auth / no cookies forwarded.
        assert "auth" not in mock_api.call_args.kwargs
        assert "cookies" not in mock_api.call_args.kwargs
        assert result is mock_api.return_value

    def test_base_url_required_raises_in_configure(self, tmp_path, monkeypatch):
        """A base_url resolving from no source raises ValueError during configure()."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        # base_url resolves nowhere -> configure() raises the required-option ValueError eagerly.
        plugin = ApiPlugin(context={})
        plugin.init_pytest_config(_FakePytestConfig())  # --base-url absent

        with pytest.raises(ValueError, match="base_url"):
            plugin.configure()

    def test_old_qa_env_names_not_resolved(self, tmp_path, monkeypatch):
        """The retired QA_BASE_URL/QA_API_TIMEOUT names are no longer env sources."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)
        monkeypatch.setenv("QA_BASE_URL", "https://old.example")

        plugin = ApiPlugin(context={})
        plugin.init_pytest_config(_FakePytestConfig())  # --base-url absent

        with pytest.raises(ValueError, match="base_url"):
            plugin.configure()

    def test_api_fixture_uses_config_file_base_url(self, tmp_path, monkeypatch):
        """The api fixture uses base_url and timeout resolved from the config file."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        config = tmp_path / ".goga" / "tools" / "pybuggy"
        config.mkdir(parents=True)
        (config / "config.yml").write_text(
            "base_url: https://cfg.example\n"
            "timeout: 9\n"
            "assert_timeout: 8\n"
            "assert_delay: 0.2\n"
            "assert_field_class: mod:FieldCls\n"
            "assert_response_class: mod:ResponseCls\n"
        )

        plugin = ApiPlugin(context={})
        _lifecycle(plugin)  # base_url from the config file renders to itself

        with mock.patch("goga_tool_pybuggy.plugin.plugin.Api") as mock_api:
            next(ApiPlugin.api.__wrapped__(plugin))  # drive up to the yield

        assert mock_api.call_args.kwargs["base_url"] == "https://cfg.example"
        assert mock_api.call_args.kwargs["timeout"] == 9.0

    def test_api_fixture_closes_api_on_teardown(self, tmp_path, monkeypatch):
        """Exhausting the generator runs the teardown — api.close() is called.

        Driving past the yield raises StopIteration after close() ran exactly once.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://x.example")
        monkeypatch.setenv("API_TIMEOUT", "5")  # resolve via env

        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"assert_timeout": 1, "assert_delay": 0.1}
        _lifecycle(plugin)

        with mock.patch("goga_tool_pybuggy.plugin.plugin.Api") as mock_api:
            instance = mock_api.return_value
            gen = ApiPlugin.api.__wrapped__(plugin)

            assert next(gen) is instance  # yielded Api

            with pytest.raises(StopIteration):
                next(gen)  # teardown

        instance.close.assert_called_once_with()


class TestApiPluginConfigure:
    """Behavioral tests for the ``configure()`` lifecycle hook and template rendering.

    ``configure()`` renders ``base_url`` once with Jinja2 against ``os.environ`` plus the typed CLI options.
    """

    def test_configure_renders_env_placeholder(self, tmp_path, monkeypatch):
        """The configure() callback renders a base_url placeholder against os.environ variables."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://{{ qa_host }}.svc.example")
        monkeypatch.setenv("qa_host", "dev")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin)

        assert plugin.base_url == "https://dev.svc.example"

    def test_configure_renders_cli_option(self, tmp_path, monkeypatch):
        """The configure() callback renders a typed CLI option into the base_url template."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://{{ env }}.svc.example")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev"})

        assert plugin.base_url == "https://dev.svc.example"

    def test_configure_renders_multiple_cli_options(self, tmp_path, monkeypatch):
        """The configure() callback renders multiple typed CLI options into the base_url template."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://{{ env }}.svc.example/api/{{ version }}")

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--env=dev", "--version=1.2"],
            options={"env": "dev", "version": "1.2"},
        )

        assert plugin.base_url == "https://dev.svc.example/api/1.2"

    def test_configure_no_placeholders_backward_compat(self, tmp_path, monkeypatch):
        """A plain URL without Jinja placeholders renders to itself (backward compat)."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://plain.example/api")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin)

        assert plugin.base_url == "https://plain.example/api"

    def test_configure_is_idempotent_after_first_render(self, tmp_path, monkeypatch):
        """Re-running configure() after the first render leaves the URL unchanged.

        The first render consumes the template, so a second render is a no-op.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://{{ env }}.svc.example")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev"})
        assert plugin.base_url == "https://dev.svc.example"

        _lifecycle(plugin, args=["--env", "prod"], options={"env": "prod"})
        # No {{ env }} placeholder remains -> the second render is a no-op.
        assert plugin.base_url == "https://dev.svc.example"

    def test_passed_cli_options_filters_to_typed_only(self, tmp_path, monkeypatch):
        """Only CLI keys present in invocation_params.args enter the context.

        config.option carries 150+ internal options; untyped ones must not leak.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://x.example")

        plugin = ApiPlugin(context={})
        # args names ONLY --env; option carries env plus an unrelated internal key.
        with mock.patch("goga_tool_pybuggy.plugin.plugin.render_base_url", return_value="rendered") as spy:
            _lifecycle(
                plugin,
                args=["--env", "dev"],
                options={"env": "dev", "leaked_internal": "SECRET"},
            )

        context = spy.call_args.args[1]
        assert context["env"] == "dev"
        # leaked_internal is NOT in args -> excluded from the context (no leak).
        assert "leaked_internal" not in context

    def test_passed_cli_options_excludes_none(self, tmp_path, monkeypatch):
        """A typed option resolving to None is excluded (does not clobber env)."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://x.example")

        plugin = ApiPlugin(context={})
        # --unset is typed but resolves to None -> dropped from the context.
        with mock.patch("goga_tool_pybuggy.plugin.plugin.render_base_url", return_value="rendered") as spy:
            _lifecycle(
                plugin,
                args=["--env", "dev", "--unset"],
                options={"env": "dev", "unset": None},
            )

        context = spy.call_args.args[1]
        assert context["env"] == "dev"
        assert "unset" not in context

    def test_configure_uses_base_url_resolution(self, tmp_path, monkeypatch):
        """base_url is resolved (config->env->CLI->required) before rendering."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        config = tmp_path / ".goga" / "tools" / "pybuggy"
        config.mkdir(parents=True)
        (config / "config.yml").write_text("base_url: https://{{ env }}.cfg.example\n")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev"})

        assert plugin.base_url == "https://dev.cfg.example"


class TestBaseUrlCliPrecedence:
    """``--base-url`` CLI precedence for the ``base_url`` option.

    A typed ``--base-url`` is re-applied in ``configure()`` with top precedence over config/env.
    """

    def test_cli_base_url_overrides_config(self, tmp_path, monkeypatch):
        # The reported bug: the config-file base_url used to win over the CLI flag.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        config = tmp_path / ".goga" / "tools" / "pybuggy"
        config.mkdir(parents=True)
        (config / "config.yml").write_text("base_url: https://cfg.example\n")

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--base-url", "https://cli.example"],
            options={"base_url": "https://cli.example"},
        )

        assert plugin.base_url == "https://cli.example"

    def test_cli_base_url_overrides_env(self, tmp_path, monkeypatch):
        """A typed --base-url CLI flag overrides the BASE_URL environment variable."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://env.example")

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--base-url", "https://cli.example"],
            options={"base_url": "https://cli.example"},
        )

        assert plugin.base_url == "https://cli.example"

    def test_cli_base_url_renders_as_template(self, tmp_path, monkeypatch):
        # The typed --base-url value is a template, rendered like any other source.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--base-url", "https://{{ env }}.cli.example", "--env", "dev"],
            options={"base_url": "https://{{ env }}.cli.example", "env": "dev"},
        )

        assert plugin.base_url == "https://dev.cli.example"

    def test_config_wins_when_cli_flag_absent(self, tmp_path, monkeypatch):
        # Without a typed flag the chain stands (config wins; untyped options are ignored).
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        config = tmp_path / ".goga" / "tools" / "pybuggy"
        config.mkdir(parents=True)
        (config / "config.yml").write_text("base_url: https://cfg.example\n")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev", "base_url": "https://cfg.example"})

        assert plugin.base_url == "https://cfg.example"


class TestApiPluginJinjaBaseUrl:
    """Jinja2 ``base_url`` rendering and the custom ``match_re`` test.

    ``StrictUndefined``: an unknown variable raises rather than silently truncating the URL.
    """

    def test_configure_renders_jinja_variable(self, tmp_path, monkeypatch):
        """A Jinja variable in base_url is rendered from the typed CLI options."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "http://{{ env }}.svc.example/api")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev"})

        assert plugin.base_url == "http://dev.svc.example/api"

    def test_configure_jinja_conditional_url_match(self, tmp_path, monkeypatch):
        """The conditional Jinja suffix is appended when service_version matches the match_re regex."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", _JINJA_CONDITIONAL_URL)

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--service-version=feature-123"],
            options={"service_version": "feature-123"},
        )

        assert plugin.base_url == "http://x/api/v1-feature-123"

    def test_configure_jinja_conditional_url_no_match(self, tmp_path, monkeypatch):
        """The conditional Jinja suffix is omitted when service_version fails the match_re regex."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", _JINJA_CONDITIONAL_URL)

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--service-version=1.2.3"],
            options={"service_version": "1.2.3"},
        )

        assert plugin.base_url == "http://x/api/v1"

    def test_configure_jinja_strict_undefined_raises(self, tmp_path, monkeypatch):
        """An unknown variable raises (StrictUndefined), not a silent empty URL."""
        import jinja2

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "http://{{ undefined_var }}.svc.example")

        plugin = ApiPlugin(context={})
        with pytest.raises(jinja2.UndefinedError):
            _lifecycle(plugin)

    def test_configure_jinja_uses_env_and_cli_context(self, tmp_path, monkeypatch):
        """Both os.environ and the passed CLI options are available in the Jinja context."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_HOST", "env-host")
        monkeypatch.setenv("BASE_URL", "http://{{ QA_HOST }}.svc.example/{{ region }}")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--region", "eu"], options={"region": "eu"})

        assert plugin.base_url == "http://env-host.svc.example/eu"

    def test_configure_multiline_folded_url_no_match(self, tmp_path, monkeypatch):
        """A multi-line folded-scalar base_url renders to a clean URL (no trailing space).

        The folded space before `{% if %}` becomes `%20` in the request path; it is stripped.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        config = tmp_path / ".goga" / "tools" / "pybuggy"
        config.mkdir(parents=True)
        (config / "config.yml").write_text(
            "base_url: >\n"
            "  http://{{ env }}.svc.example/api/v1\n"
            "  {% if some_version is match_re('^feature-.*$') %}"
            "-{{ some_version }}{% endif %}\n"
        )

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--env", "stage-el", "--some-version", "1.2.3"],
            options={"env": "stage-el", "some_version": "1.2.3"},
        )

        assert plugin.base_url == "http://stage-el.svc.example/api/v1"

    def test_configure_multiline_folded_url_match(self, tmp_path, monkeypatch):
        """The matched branch of a multi-line folded-scalar base_url is also clean.

        The folded space would land mid-URL (`/api/v1 -feature-123`); it is stripped.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        config = tmp_path / ".goga" / "tools" / "pybuggy"
        config.mkdir(parents=True)
        (config / "config.yml").write_text(
            "base_url: >\n"
            "  http://{{ env }}.svc.example/api/v1\n"
            "  {% if some_version is match_re('^feature-.*$') %}"
            "-{{ some_version }}{% endif %}\n"
        )

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--env", "stage-el", "--some-version", "feature-123"],
            options={"env": "stage-el", "some_version": "feature-123"},
        )

        assert plugin.base_url == "http://stage-el.svc.example/api/v1-feature-123"


class TestApiPluginLoadPlugins:
    """Contract + behavioral tests for `ApiPlugin._load_plugins`.

    It builds `pytest_plugins` from the `loader` config plus explicit loaders; the api/ default is `install()`'s job.
    """

    @staticmethod
    def _make_api_tree(tmp_path):
        """Create a one-fixture `api/orders/get_orders/api.py` tree under tmp_path."""
        api = tmp_path / "api"
        (api / "orders" / "get_orders").mkdir(parents=True)
        (api / "__init__.py").write_text("")
        (api / "orders" / "__init__.py").write_text("")
        (api / "orders" / "get_orders" / "__init__.py").write_text("")
        (api / "orders" / "get_orders" / "api.py").write_text(_GENERATED_FIXTURE_SOURCE)

    def test_load_plugins_is_method_of_api_plugin(self):
        """The _load_plugins routine is a callable method of ApiPlugin."""
        assert callable(ApiPlugin._load_plugins)

    def test_load_plugins_signature(self):
        """The _load_plugins routine takes exactly the self, context and loaders parameters."""
        sig = inspect.signature(ApiPlugin._load_plugins)

        # `self`, `context`, `loaders` (mirrors the contract signature).
        assert list(sig.parameters) == ["self", "context", "loaders"]

    def test_load_plugins_assembles_from_config_packages(self, tmp_path, monkeypatch):
        """The _load_plugins routine assembles pytest_plugins from the configured loader packages."""
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        self._make_api_tree(tmp_path)

        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"loader": {"packages": [{"name": "api", "required": False}], "modules": []}}
        context: dict[str, object] = {"pytest_plugins": []}

        plugin._load_plugins(context, [])

        assert context["pytest_plugins"] == ["api.orders.get_orders.api"]

    def test_load_plugins_empty_config_loads_nothing(self, tmp_path, monkeypatch):
        # No loader section and no explicit loaders -> nothing appended (the api/ default is install()'s).
        monkeypatch.chdir(tmp_path)

        plugin = ApiPlugin(context={})
        plugin.plugin_config = {}
        context: dict[str, object] = {}

        plugin._load_plugins(context, [])

        assert context["pytest_plugins"] == []

    def test_load_plugins_dedupes_real_duplicates(self, tmp_path, monkeypatch):
        """The _load_plugins routine collapses duplicate entries from the walk, config and seed into one."""
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        self._make_api_tree(tmp_path)

        # The walk, the config entry, and the seed context all name it — three duplicates collapse to one.
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {
            "loader": {
                "packages": [{"name": "api", "required": False}],
                "modules": [{"name": "api.orders.get_orders.api", "required": False}],
            }
        }
        context: dict[str, object] = {"pytest_plugins": ["api.orders.get_orders.api"]}

        plugin._load_plugins(context, [])

        assert context["pytest_plugins"] == ["api.orders.get_orders.api"]
        assert len(context["pytest_plugins"]) == 1

    def test_load_plugins_runs_explicit_loaders_and_keeps_seed(self, tmp_path, monkeypatch):
        """The _load_plugins routine runs explicit loaders while keeping the seeded pytest_plugins entries."""
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        self._make_api_tree(tmp_path)

        # The explicit loader discovers the module; `list(set(...))` dedupes, so only membership is asserted.
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"loader": {"packages": [], "modules": []}}
        context: dict[str, object] = {"pytest_plugins": ["seed.plugin"]}

        plugin._load_plugins(context, [PackageLoader("api", required=False)])

        assert set(context["pytest_plugins"]) == {"seed.plugin", "api.orders.get_orders.api"}


class _FakeItem:
    """Minimal stand-in for a collected pytest item.

    Exposes ``_flaky_max_runs`` and records ``add_marker`` calls.
    """

    def __init__(self, flaky_max_runs: int = 0) -> None:
        self._flaky_max_runs = flaky_max_runs
        self.markers: list[object] = []

    def add_marker(self, marker: object) -> None:
        self.markers.append(marker)


class TestApiPluginRetries:
    """Behavioral tests for the ``retries`` option and its collection hook.

    ``retries`` resolves from plugin config alone, so no pytest config is needed.
    """

    @staticmethod
    def _mark_kwargs(marker: object) -> dict:
        # ``add_marker`` is fed a MarkDecorator; unwrap to the underlying Mark.
        mark = getattr(marker, "mark", marker)
        return dict(mark.kwargs)

    def test_default_retries_stored_on_construct(self, tmp_path, monkeypatch):
        """A default_retries passed to the constructor is stored on the plugin."""
        monkeypatch.chdir(tmp_path)

        plugin = ApiPlugin(context={}, default_retries=4)

        assert plugin._default_retries == 4

    def test_default_retries_defaults_to_none(self, tmp_path, monkeypatch):
        """The default_retries option defaults to None when omitted from the constructor."""
        monkeypatch.chdir(tmp_path)

        plugin = ApiPlugin(context={})

        assert plugin._default_retries is None

    def test_retries_adds_flaky_marker_when_positive(self, tmp_path, monkeypatch):
        """A positive retries config adds a single flaky marker with the matching max_runs to an item."""
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 2}

        item = _FakeItem()
        plugin.pytest_collection_modifyitems([item])

        assert len(item.markers) == 1
        assert getattr(item.markers[0], "name", None) == "flaky"
        assert self._mark_kwargs(item.markers[0]) == {"max_runs": 2}

    def test_retries_marks_every_unmarked_item(self, tmp_path, monkeypatch):
        """Every unmarked item in the collection receives a flaky marker with max_runs from retries."""
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 3}

        items = [_FakeItem(), _FakeItem(), _FakeItem()]
        plugin.pytest_collection_modifyitems(items)

        assert all(len(i.markers) == 1 for i in items)
        assert all(self._mark_kwargs(i.markers[0]) == {"max_runs": 3} for i in items)

    def test_retries_skips_already_marked_items(self, tmp_path, monkeypatch):
        """Items already marked flaky are skipped while unmarked items still receive the marker."""
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 2}

        already_marked = _FakeItem(flaky_max_runs=3)
        fresh = _FakeItem(flaky_max_runs=0)
        plugin.pytest_collection_modifyitems([already_marked, fresh])

        assert already_marked.markers == []
        assert len(fresh.markers) == 1

    def test_retries_zero_adds_no_markers(self, tmp_path, monkeypatch):
        """A zero retries config adds no markers to collected items."""
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 0}

        item = _FakeItem()
        plugin.pytest_collection_modifyitems([item])

        assert item.markers == []

    def test_retries_empty_collection_is_noop(self, tmp_path, monkeypatch):
        """An empty item collection passes through the hook without raising."""
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 5}

        plugin.pytest_collection_modifyitems([])  # no items — must not raise


class TestApiPluginSandboxIntegration:
    """The armed-sandbox behavior of ``configure()`` and the ``api`` fixture.

    ``sandbox_activation`` is assigned by ``install()`` (the arming seam); the tests below
    follow the same post-construction assignment pattern.
    """

    def test_configure_renders_base_url_unchanged_without_sandbox(self, tmp_path, monkeypatch):
        """Without an armed sandbox configure() renders base_url exactly as before."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "http://{{ ENV_X }}/api")
        monkeypatch.setenv("ENV_X", "x")

        plugin = ApiPlugin(context={})
        assert plugin.sandbox_activation is None  # constructor leaves it unarmed
        _lifecycle(plugin)

        assert plugin.base_url == "http://x/api"

    def test_configure_fails_fast_on_cli_base_url_with_armed_sandbox(self, tmp_path, monkeypatch):
        """A typed --base-url plus an armed sandbox raises pytest.UsageError naming both facts."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)

        plugin = ApiPlugin(context={})
        plugin.sandbox_activation = SandboxConfig(
            service=ServiceConfig(image="my-service:latest", env={}, port=8080, health=None),
            instances={},
            data=StartupData(),
        )

        with pytest.raises(pytest.UsageError, match=r"--base-url.*sandbox"):
            _lifecycle(plugin, args=["--base-url", "http://x"], options={"base_url": "http://x"})

    def test_api_fixture_substitutes_base_url_and_guards_first_request(self, tmp_path, monkeypatch):
        """An active sandbox wins the fixture base_url and guards every request."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BASE_URL", "http://rendered/api")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin)  # plugin.base_url rendered by configure()

        calls: list[object] = []

        class _FakeSandbox:
            """Recording sandbox double: the guard runs its two checks."""

            base_url = "http://10.0.0.1:9000"

            def apply_pending(self):
                calls.append("apply_pending")

            def ensure_service(self):
                calls.append("ensure_service")

        class _FakeApi:
            """Api double recording its construction base_url and requests."""

            def __init__(self, *, base_url: str, **kwargs: object) -> None:
                self.base_url = base_url

            def request(self, method: str, url_path: str, **kwargs: object) -> object:
                calls.append(("request", method, url_path))
                return "response"

            def close(self) -> None:
                pass

        monkeypatch.setattr(plugin_module, "active_sandbox", _FakeSandbox)
        monkeypatch.setattr(plugin_module, "Api", _FakeApi)

        gen = ApiPlugin.api.__wrapped__(plugin)
        api = next(gen)  # drive the fixture up to the yield

        api.request("GET", "/x")

        assert api.base_url == "http://10.0.0.1:9000"  # the sandbox address wins
        # The guard ran both checks before the original request.
        assert calls == ["apply_pending", "ensure_service", ("request", "GET", "/x")]
        # The read-time substitution leaves the option value untouched.
        assert plugin.base_url == "http://rendered/api"

        with pytest.raises(StopIteration):
            next(gen)  # teardown
