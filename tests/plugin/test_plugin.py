"""Tests for the `goga_tool_pybuggy.plugin` cell (`ApiPlugin` + service constants).

Mirrors the source layout (`tests/plugin/test_plugin.py`). Covers the contract
surface (importability + presence of the option descriptors and the `api`
method) and the behavioral logic of the `ApiPlugin` fixture.

Note: option resolution is driven through env vars (``QA_BASE_URL`` /
``QA_API_TIMEOUT``), the documented resolution chain. The `Api` constructor is
mocked in the positive case so the fixture logic is asserted independently of
the `resq` network layer (constructing `Api` performs no network I/O, but the
stub `resq` here has no `Session`).
"""

import inspect
from unittest import mock

import pytest
from goga_tool_pybuggy.plugin import ApiPlugin
from goga_tool_pybuggy.plugin.loaders import PackageLoader

# Jinja2 is a required dependency of pybuggy (declared in pyproject.toml core
# dependencies), so the Jinja render-path tests run unconditionally.

# Jinja base_url template exercising conditional logic + the match_re test.
_JINJA_CONDITIONAL_URL = (
    "http://x/api/v1"
    "{% if service_version is match_re('^feature-.*$') %}"
    "-{{ service_version }}"
    "{% endif %}"
)

# Source for a generated-fixture module (carries a `@pytest.fixture` so the probe
# recognizes it as a pytest plugin). Used by the `_load_plugins` tests.
_GENERATED_FIXTURE_SOURCE = """
import pytest


@pytest.fixture
def get_orders():
    return 1
"""


# Minimal pytest ``Config`` stand-ins for the ``configure()`` lifecycle tests.
# The real pytest Config exposes ``invocation_params.args`` (raw CLI tokens) and
# ``option`` (the resolved option namespace); ``getoption`` resolves one flag.
# These fakes emulate just that surface so ``configure()`` can be driven without
# a running pytest.
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
        import goga_tool_pybuggy.plugin as plugin_facade

        assert plugin_facade.ApiPlugin is ApiPlugin

    def test_api_plugin_importable_from_location(self):
        import goga_tool_pybuggy.plugin.plugin as plugin_module

        assert plugin_module.ApiPlugin is ApiPlugin

    def test_api_plugin_is_class(self):
        assert isinstance(ApiPlugin, type)

    @pytest.mark.parametrize(
        "option",
        [
            "base_url",
            "headers",
            "timeout",
            "data_key",
            "error_key",
            "retries",
            "assert_timeout",
            "assert_delay",
            "assert_field_class",
            "assert_response_class",
        ],
    )
    def test_api_plugin_has_option_descriptor(self, option):
        assert hasattr(ApiPlugin, option)

    def test_api_plugin_has_api_method(self):
        assert callable(ApiPlugin.api)

    def test_api_plugin_has_collection_modifyitems_hook(self):
        assert callable(ApiPlugin.pytest_collection_modifyitems)

    def test_api_plugin_has_configure_method(self):
        # configure() is a pluginator lifecycle callback (no @pytest.hookimpl).
        assert callable(ApiPlugin.configure)
        assert "pytest.hookimpl" not in str(ApiPlugin.configure.__dict__)

    def test_api_plugin_init_accepts_default_retries(self):
        sig = inspect.signature(ApiPlugin.__init__)

        assert "default_retries" in sig.parameters
        assert sig.parameters["default_retries"].default is None

    def test_api_plugin_init_accepts_default_assert_timeout(self):
        sig = inspect.signature(ApiPlugin.__init__)

        assert "default_assert_timeout" in sig.parameters
        assert sig.parameters["default_assert_timeout"].default is None

    def test_api_plugin_init_accepts_default_assert_delay(self):
        sig = inspect.signature(ApiPlugin.__init__)

        assert "default_assert_delay" in sig.parameters
        assert sig.parameters["default_assert_delay"].default is None

    def test_plugin_config_keys_enum(self):
        from goga_tool_pybuggy.plugin.plugin import PluginConfigKeys

        assert PluginConfigKeys.BASE_URL.value == "base_url"
        assert PluginConfigKeys.HEADERS.value == "headers"
        assert PluginConfigKeys.TIMEOUT.value == "timeout"
        assert PluginConfigKeys.DATA_KEY.value == "data_key"
        assert PluginConfigKeys.ERROR_KEY.value == "error_key"
        assert PluginConfigKeys.RETRIES.value == "retries"
        assert PluginConfigKeys.ASSERT_TIMEOUT.value == "assert_timeout"
        assert PluginConfigKeys.ASSERT_DELAY.value == "assert_delay"
        assert PluginConfigKeys.ASSERT_FIELD_CLASS.value == "assert_field_class"
        assert PluginConfigKeys.ASSERT_RESPONSE_CLASS.value == "assert_response_class"


class TestApiPluginLogic:
    """Behavioral logic tests for the `api` fixture.

    pytest 9 wraps `@pytest.fixture` methods in `FixtureFunctionDefinition` and
    forbids calling them directly. The raw function is reached via
    `__wrapped__` to unit-test the fixture body with an explicit instance.
    """

    def test_api_fixture_builds_api_from_options(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", "https://x.example")
        monkeypatch.setenv("QA_API_TIMEOUT", "5")

        plugin = ApiPlugin(context={})
        # The assert-polling / pluggable-class options resolve from the plugin
        # config (the CLI-bearing ones need a source before the pytest-config
        # step, which is absent in this unit test).
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
            "data_key": None,
            "error_key": None,
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
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("QA_BASE_URL", raising=False)

        # base_url resolves nowhere (no config/env/CLI) -> configure() raises the
        # required-option ValueError (rendering happens eagerly in configure(),
        # not lazily on fixture invocation).
        plugin = ApiPlugin(context={})
        plugin.init_pytest_config(_FakePytestConfig())  # --api-url absent

        with pytest.raises(ValueError, match="base_url"):
            plugin.configure()

    def test_api_fixture_uses_config_file_base_url(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("QA_BASE_URL", raising=False)

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

        The fixture yields the Api, then closes it on teardown to release the
        underlying resq session's connection pool. Driving the generator past
        the yield (a second `next`) raises StopIteration and must have invoked
        close() on the constructed Api exactly once.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", "https://x.example")
        monkeypatch.setenv("QA_API_TIMEOUT", "5")  # resolve via env

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

    ``configure()`` is a pluginator lifecycle callback (no ``@pytest.hookimpl``)
    that renders ``base_url`` once with Jinja2 against ``os.environ`` plus the CLI
    options the user actually typed, and stores the rendered value back onto
    ``self.base_url``. These tests emulate the lifecycle (``init_pytest_config``
    + ``configure()``) with a fake pytest Config carrying raw
    ``invocation_params.args`` and an ``option`` namespace.
    """

    def test_configure_renders_env_placeholder(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", "https://{{ qa_host }}.svc.example")
        monkeypatch.setenv("qa_host", "dev")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin)

        assert plugin.base_url == "https://dev.svc.example"

    def test_configure_renders_cli_option(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", "https://{{ env }}.svc.example")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev"})

        assert plugin.base_url == "https://dev.svc.example"

    def test_configure_renders_multiple_cli_options(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", "https://{{ env }}.svc.example/api/{{ version }}")

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
        monkeypatch.setenv("QA_BASE_URL", "https://plain.example/api")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin)

        assert plugin.base_url == "https://plain.example/api"

    def test_configure_is_idempotent_after_first_render(self, tmp_path, monkeypatch):
        """Re-running configure() after the first render leaves the URL unchanged.

        configure() stores the rendered value back onto self.base_url, so the
        template is consumed by the first render; a second configure() re-renders
        an already-resolved URL (no placeholders left) and is therefore a no-op.
        pluginator calls configure() exactly once at configphase.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", "https://{{ env }}.svc.example")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev"})
        assert plugin.base_url == "https://dev.svc.example"

        _lifecycle(plugin, args=["--env", "prod"], options={"env": "prod"})
        # No {{ env }} placeholder remains -> the second render is a no-op.
        assert plugin.base_url == "https://dev.svc.example"

    def test_passed_cli_options_filters_to_typed_only(self, tmp_path, monkeypatch):
        """Only CLI keys present in invocation_params.args enter the context.

        config.option carries 150+ internal/plugin options; the full namespace is
        intentionally NOT used. An option present on the namespace but NOT typed
        on the CLI must not leak into the template — its key is absent from the
        rendering context passed to render_base_url.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", "https://x.example")

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
        monkeypatch.setenv("QA_BASE_URL", "https://x.example")

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
        monkeypatch.delenv("QA_BASE_URL", raising=False)

        config = tmp_path / ".goga" / "tools" / "pybuggy"
        config.mkdir(parents=True)
        (config / "config.yml").write_text("base_url: https://{{ env }}.cfg.example\n")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev"})

        assert plugin.base_url == "https://dev.cfg.example"


class TestApiPluginJinjaBaseUrl:
    """Jinja2 ``base_url`` rendering and the custom ``match_re`` test.

    ``configure()`` renders every ``base_url`` with a single engine, Jinja2
    (``StrictUndefined``; the ``match_re`` test); the rendered value is stored
    back onto ``self.base_url``. An unknown variable raises (URLs must not be
    silently truncated); a plain URL renders to itself.
    """

    def test_configure_renders_jinja_variable(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", "http://{{ env }}.svc.example/api")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--env", "dev"], options={"env": "dev"})

        assert plugin.base_url == "http://dev.svc.example/api"

    def test_configure_jinja_conditional_url_match(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", _JINJA_CONDITIONAL_URL)

        plugin = ApiPlugin(context={})
        _lifecycle(
            plugin,
            args=["--service-version=feature-123"],
            options={"service_version": "feature-123"},
        )

        assert plugin.base_url == "http://x/api/v1-feature-123"

    def test_configure_jinja_conditional_url_no_match(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_BASE_URL", _JINJA_CONDITIONAL_URL)

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
        monkeypatch.setenv("QA_BASE_URL", "http://{{ undefined_var }}.svc.example")

        plugin = ApiPlugin(context={})
        with pytest.raises(jinja2.UndefinedError):
            _lifecycle(plugin)

    def test_configure_jinja_uses_env_and_cli_context(self, tmp_path, monkeypatch):
        """Both os.environ and the passed CLI options are available in the Jinja context."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QA_HOST", "env-host")
        monkeypatch.setenv("QA_BASE_URL", "http://{{ QA_HOST }}.svc.example/{{ region }}")

        plugin = ApiPlugin(context={})
        _lifecycle(plugin, args=["--region", "eu"], options={"region": "eu"})

        assert plugin.base_url == "http://env-host.svc.example/eu"

    def test_configure_multiline_folded_url_no_match(self, tmp_path, monkeypatch):
        """A multi-line folded-scalar base_url renders to a clean URL (no trailing space).

        The reported bug: a YAML folded scalar (`>`) folds the newline before
        `{% if %}` into a space, and an empty (no-match) conditional leaves it as a
        trailing space that becomes `%20` in the request path (404). render_base_url
        strips it, so the URL is clean.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("QA_BASE_URL", raising=False)

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

        Same root cause as the no-match case, matched branch: the space the folded
        scalar inserts before `{% if %}` would land in the MIDDLE of the URL
        (`/api/v1 -feature-123`). render_base_url strips it.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("QA_BASE_URL", raising=False)

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

    `_load_plugins` assembles the recursive `pytest_plugins` list from the
    `loader` section of `plugin_config` plus the explicit `loaders`, mutating
    `context['pytest_plugins']` in place. The api/ default discovery is
    `install()`'s job (via its `loaders` default), so an empty config with no
    explicit loaders loads nothing here.
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
        assert callable(ApiPlugin._load_plugins)

    def test_load_plugins_signature(self):
        sig = inspect.signature(ApiPlugin._load_plugins)

        # `self`, `context`, `loaders` (mirrors the contract signature).
        assert list(sig.parameters) == ["self", "context", "loaders"]

    def test_load_plugins_assembles_from_config_packages(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        self._make_api_tree(tmp_path)

        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"loader": {"packages": [{"name": "api", "required": False}], "modules": []}}
        context: dict[str, object] = {"pytest_plugins": []}

        plugin._load_plugins(context, [])

        assert context["pytest_plugins"] == ["api.orders.get_orders.api"]

    def test_load_plugins_empty_config_loads_nothing(self, tmp_path, monkeypatch):
        # No loader section and no explicit loaders -> nothing appended. The api/
        # default is install()'s responsibility, not _load_plugins'.
        monkeypatch.chdir(tmp_path)

        plugin = ApiPlugin(context={})
        plugin.plugin_config = {}
        context: dict[str, object] = {}

        plugin._load_plugins(context, [])

        assert context["pytest_plugins"] == []

    def test_load_plugins_dedupes_real_duplicates(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        self._make_api_tree(tmp_path)

        # The package walk discovers the module, the config module entry names it
        # directly, and the seed context already lists it — three real duplicates
        # that collapse to one.
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
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        self._make_api_tree(tmp_path)

        # An explicit loader (the install() default pattern) discovers the module;
        # a pre-existing seed entry is kept. `list(set(...))` dedupes, so order is
        # not asserted — only membership.
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"loader": {"packages": [], "modules": []}}
        context: dict[str, object] = {"pytest_plugins": ["seed.plugin"]}

        plugin._load_plugins(context, [PackageLoader("api", required=False)])

        assert set(context["pytest_plugins"]) == {"seed.plugin", "api.orders.get_orders.api"}


class _FakeItem:
    """Minimal stand-in for a collected pytest item.

    Records markers added via ``add_marker`` and exposes the ``_flaky_max_runs``
    attribute the retries hook reads to detect already-marked items.
    """

    def __init__(self, flaky_max_runs: int = 0) -> None:
        self._flaky_max_runs = flaky_max_runs
        self.markers: list[object] = []

    def add_marker(self, marker: object) -> None:
        self.markers.append(marker)


class TestApiPluginRetries:
    """Behavioral tests for the ``retries`` option and its collection hook.

    ``retries`` is driven through the ``retries`` plugin config key (resolution
    step 1), so the option resolves without an initialized pytest config — the
    command-line step is never reached. The flaky marker is the contract
    surface; ``flaky`` itself is not imported here.
    """

    @staticmethod
    def _mark_kwargs(marker: object) -> dict:
        # ``add_marker`` is fed a MarkDecorator; unwrap to the underlying Mark.
        mark = getattr(marker, "mark", marker)
        return dict(mark.kwargs)

    def test_default_retries_stored_on_construct(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        plugin = ApiPlugin(context={}, default_retries=4)

        assert plugin._default_retries == 4

    def test_default_retries_defaults_to_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        plugin = ApiPlugin(context={})

        assert plugin._default_retries is None

    def test_retries_adds_flaky_marker_when_positive(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 2}

        item = _FakeItem()
        plugin.pytest_collection_modifyitems([item])

        assert len(item.markers) == 1
        assert getattr(item.markers[0], "name", None) == "flaky"
        assert self._mark_kwargs(item.markers[0]) == {"max_runs": 2}

    def test_retries_marks_every_unmarked_item(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 3}

        items = [_FakeItem(), _FakeItem(), _FakeItem()]
        plugin.pytest_collection_modifyitems(items)

        assert all(len(i.markers) == 1 for i in items)
        assert all(self._mark_kwargs(i.markers[0]) == {"max_runs": 3} for i in items)

    def test_retries_skips_already_marked_items(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 2}

        already_marked = _FakeItem(flaky_max_runs=3)
        fresh = _FakeItem(flaky_max_runs=0)
        plugin.pytest_collection_modifyitems([already_marked, fresh])

        assert already_marked.markers == []
        assert len(fresh.markers) == 1

    def test_retries_zero_adds_no_markers(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 0}

        item = _FakeItem()
        plugin.pytest_collection_modifyitems([item])

        assert item.markers == []

    def test_retries_empty_collection_is_noop(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        plugin = ApiPlugin(context={})
        plugin.plugin_config = {"retries": 5}

        plugin.pytest_collection_modifyitems([])  # no items — must not raise
