"""pybuggy pytest-plugin cell.

This cell turns pybuggy into a pytest plugin so a consumer enables it with a
single ``pytest_plugins = ["goga_tool_pybuggy.plugin"]`` line in ``conftest.py``. It is
built on the ``pluginator`` framework and provides:

- the function-scope ``api`` fixture that constructs an :class:`Api` from the
  plugin's resolved options; and
- the :func:`install` entry point (defined in the package ``__init__.py``) that
  wires the plugin into pytest at import time and synchronously registers the
  discovered generated-fixture modules via the ``loaders`` sub-cell.

Entities realized in this module:

- ``PluginConfigKeys`` — the yaml config-file keys for the ``ApiPlugin``
  options (an implementation-hint enum, co-located here).
- ``ApiPlugin`` — pluginator plugin class exposing the configurable options
  (``base_url``/``headers``/``timeout``/``data_key``/``error_key`` for the
  ``api`` fixture, plus ``retries`` for test-run flaky reruns, and
  ``assert_timeout``/``assert_delay``/``assert_field_class``/
  ``assert_response_class`` for assert polling and pluggable assert classes) and
  the ``api`` fixture.

Only the minimal fixture profile (``base_url``, ``headers``, ``timeout``,
``data_key``, ``error_key``) plus the assert-polling/pluggable-class options
(``assert_timeout``/``assert_delay``/``assert_field_class``/
``assert_response_class``) is fed to ``Api`` — no auth, no cookies. The
fixture yields the ``Api`` and closes it afterwards (``Api.close()``, delegating to
the underlying resq.Session's public close()). ``retries`` is orthogonal to the
``api`` fixture: when resolved to a
positive int, the ``pytest_collection_modifyitems`` hook stamps every collected
item without an existing flaky marker with ``pytest.mark.flaky(max_runs=retries)``.
Option resolution is lazy: errors (e.g. a missing required ``base_url``) surface
on fixture invocation, not on import. ``base_url`` is a Jinja2 template string
rendered once in the pluginator ``configure()`` lifecycle hook against the full
environment plus the CLI options the user actually passed, and the rendered value
is stored back on ``self.base_url`` and consumed by the ``api`` fixture (no
rendering inside the fixture). Rendering uses Jinja2 (``StrictUndefined``; unknown
variables raise) with a ``match_re`` test for conditional URL assembly; a plain URL
without placeholders renders to itself, and any literal whitespace in the rendered
value is removed so a multi-line template yields one clean URL. The renderer lives in
the ``render`` sub-cell (``render_base_url``).
"""

import logging
import os
import re
import typing as t
from enum import Enum

import pytest
from pluginator import CommandLine, define

from ..api import Api
from . import defaults
from .envvars import QA_API_TIMEOUT, QA_BASE_URL
from .loaders import BaseLoader, ModuleLoader, PackageLoader
from .render import render_base_url

logger = logging.getLogger(__name__)


class PluginConfigKeys(str, Enum):
    """Config-file keys for the ``ApiPlugin`` options.

    Implementation-hint enum (not a contract type): each member's value is the
    yaml key read via the pluginator ``plugin_config_key`` resolution step.
    ``LOADER`` is the exception — it is not an option but the section
    ``_load_plugins`` reads to discover generated-fixture modules.
    """

    BASE_URL = "base_url"
    HEADERS = "headers"
    TIMEOUT = "timeout"
    DATA_KEY = "data_key"
    ERROR_KEY = "error_key"
    RETRIES = "retries"
    LOADER = "loader"
    ASSERT_TIMEOUT = "assert_timeout"
    ASSERT_DELAY = "assert_delay"
    ASSERT_FIELD_CLASS = "assert_field_class"
    ASSERT_RESPONSE_CLASS = "assert_response_class"


# A CLI token that declares an option the user typed: ``--key``, ``-k``,
# ``--key=value``. Captures the option name (letters/digits/underscore/dash).
_PLACEHOLDER_SOURCE_PATTERN = re.compile(r"^--?([A-Za-z_][\w-]*)(?:=(.*))?$")

# Normalized CLI token name of the ``--base-url`` flag (dashes -> underscores).
# Matches both the pytest option ``dest`` and the option name, so a typed
# ``--base-url`` is recognizable in ``_passed_cli_options`` output.
_BASE_URL_CLI_KEY: t.Final[str] = "base_url"


def _passed_cli_options(config: t.Any) -> dict[str, t.Any]:
    """Collect the CLI options the user actually typed, keyed by normalized name.

    Only options present in ``config.invocation_params.args`` (the raw CLI tokens)
    are considered — the full ``config.option`` namespace is intentionally NOT
    used, since it carries 150+ internal/plugin options that must not leak into
    the template. Names are normalized (``-`` -> ``_``); ``None`` values are
    dropped so an unset option does not overwrite a matching env entry.

    Args:
        config: the pytest ``Config`` (``self.pytest_config``), exposing
            ``invocation_params.args`` (raw token list) and ``option`` (the
            resolved option namespace).

    Returns:
        A name -> value mapping of the options the user passed on the CLI.
    """
    names: set[str] = set()
    invocation_params = getattr(config, "invocation_params", None)
    tokens = getattr(invocation_params, "args", None) or []
    for token in tokens:
        match = _PLACEHOLDER_SOURCE_PATTERN.match(str(token))
        if match:
            names.add(match.group(1).replace("-", "_"))

    option = config.option
    return {
        name: getattr(option, name)
        for name in names
        if hasattr(option, name) and getattr(option, name) is not None
    }


@define.plugin("pybuggy", config=defaults.CONFIG_FILE)
class ApiPlugin:
    """pluginator plugin exposing the Api options and the ``api`` fixture.

    Options are lazy ``PluginOption`` descriptors: values resolve on access
    through ``plugin_config_key -> env_var -> command_line -> required/
    nullable``. ``__init__`` overrides the mixed-in ``BasePlugin.__init__`` to
    accept the install ``context`` and optional explicit ``loaders``, and to
    synchronously register discovered generated fixtures.

    Attributes:
        plugin_config: anchor declaration; ``BasePlugin`` supplies the parsed
            yaml dict.
        base_url: service base URL as a Jinja2 template string (required;
            ``QA_BASE_URL`` env / ``--base-url`` CLI). Rendered once in
            ``configure()`` against the environment + passed CLI options and stored
            back on ``self.base_url``; a plain URL without placeholders renders to
            itself. When ``--base-url`` is actually typed on the CLI, its value is
            applied with top precedence — overriding the plugin config and
            ``QA_BASE_URL`` (see ``configure()``).
        headers: default request headers (default ``{}``).
        timeout: request timeout in seconds (nullable; ``QA_API_TIMEOUT`` env /
            ``--api-timeout`` CLI).
        data_key: success-body key fallback (nullable).
        error_key: error-body key fallback (nullable).
        retries: flaky rerun count for the test run (default ``0``/no reruns;
            ``--retries`` CLI). When positive, ``pytest_collection_modifyitems``
            stamps unmarked items with ``pytest.mark.flaky(max_runs=retries)``.
        assert_timeout: baseline assert-polling timeout in seconds (nullable;
            ``assert_timeout`` config key / ``--api-assert-timeout`` CLI).
            Forwarded to ``Api`` → ``AssertConfig``; drives matchcrest's retry
            loop on each assertion.
        assert_delay: seconds between assert-polling attempts (nullable;
            ``assert_delay`` config key / ``--api-assert-delay`` CLI). Forwarded
            to ``Api`` → ``AssertConfig``.
        assert_field_class: dotted ``module:Class`` path of a custom
            ``AssertField`` subclass (nullable; ``assert_field_class`` config
            key). Forwarded to ``Api`` → ``AssertConfig``.
        assert_response_class: dotted ``module:Class`` path of a custom
            ``Expected`` subclass (nullable; ``assert_response_class`` config
            key). Forwarded to ``Api`` → ``AssertConfig``.
    """

    plugin_config: dict

    base_url = define.option(
        str,
        plugin_config_key=PluginConfigKeys.BASE_URL,
        env_var=QA_BASE_URL,
        command_line=CommandLine("--base-url", action="store", help="Base URL of the service under test"),
        required=True,
    )
    headers = define.option(dict, plugin_config_key=PluginConfigKeys.HEADERS)
    timeout = define.option(
        float,
        plugin_config_key=PluginConfigKeys.TIMEOUT,
        env_var=QA_API_TIMEOUT,
        command_line=CommandLine("--api-timeout", action="store", help="Network timeout"),
        nullable=True,
    )
    data_key = define.option(str, plugin_config_key=PluginConfigKeys.DATA_KEY, nullable=True)
    error_key = define.option(str, plugin_config_key=PluginConfigKeys.ERROR_KEY, nullable=True)
    retries = define.option(
        int,
        default_from="_default_retries",
        plugin_config_key=PluginConfigKeys.RETRIES,
        command_line=CommandLine("--retries", action="store", help="Flaky retries for testrun"),
    )
    assert_timeout = define.option(
        int,
        nullable=True,
        default_from="_default_assert_timeout",
        plugin_config_key=PluginConfigKeys.ASSERT_TIMEOUT,
        command_line=CommandLine("--api-assert-timeout", action="store", help="Base assert polling timeout"),
    )
    assert_delay = define.option(
        float,
        nullable=True,
        default_from="_default_assert_delay",
        plugin_config_key=PluginConfigKeys.ASSERT_DELAY,
        command_line=CommandLine("--api-assert-delay", action="store", help="Delay between assert polling attempts"),
    )
    assert_field_class = define.option(
        str,
        nullable=True,
        plugin_config_key=PluginConfigKeys.ASSERT_FIELD_CLASS,
    )
    assert_response_class = define.option(
        str,
        nullable=True,
        plugin_config_key=PluginConfigKeys.ASSERT_RESPONSE_CLASS,
    )

    def __init__(
            self,
            *,
            context: dict,
            loaders: t.Optional[list[BaseLoader]] = None,
            default_retries: t.Optional[int] = None,
            default_assert_timeout: t.Optional[int] = None,
            default_assert_delay: t.Optional[t.Union[int, float]] = None,
    ) -> None:
        """Initialize the plugin and synchronously register generated fixtures.

        After ``BasePlugin.__init__`` resolves the config file, ``_load_plugins``
        assembles the ``pytest_plugins`` list from the ``loader`` config section
        and the explicit ``loaders`` into ``context`` (the plugin module
        namespace), so pytest loads the discovered fixture modules recursively.

        Args:
            context: The namespace dict the plugin installs its hooks into
                (typically the plugin module globals); its ``pytest_plugins``
                key is populated here.
            loaders: Explicit loaders (e.g. ``PackageLoader('api')``) in addition
                to those declared in the ``loader`` config section. Defaults to
                none.
            default_retries: Default flaky rerun count for the ``retries`` option
                when neither the config key nor ``--retries`` CLI is set.
                Defaults to none (the option then resolves to ``0``/no reruns).
            default_assert_timeout: Default baseline assert-polling timeout for
                the ``assert_timeout`` option when neither the config key nor
                ``--api-assert-timeout`` CLI is set. Defaults to none (no
                polling unless configured).
            default_assert_delay: Default baseline assert-polling delay for the
                ``assert_delay`` option when neither the config key nor
                ``--api-assert-delay`` CLI is set. Defaults to none.
        """
        super().__init__()

        self._default_retries = default_retries
        self._default_assert_timeout = default_assert_timeout
        self._default_assert_delay = default_assert_delay

        self._load_plugins(context, loaders or [])

    def configure(self) -> None:
        """Render ``base_url`` once against the full environment and passed CLI options.

        Builds the template context from ``os.environ`` (the full environment)
        plus the CLI options the user actually typed (filtered via
        ``config.invocation_params.args``), then renders ``self.base_url`` exactly
        once with Jinja2 (``StrictUndefined``; the ``match_re`` test registered)
        and stores the result back on ``self.base_url`` for the ``api`` fixture to
        consume. A plain URL without placeholders renders to itself; any literal
        whitespace in the rendered value is removed so a multi-line template
        yields one clean URL.

        When the user typed ``--base-url``, its value is applied first, with top
        precedence over the plugin config and ``QA_BASE_URL``: the pluginator
        chain resolves the config before the CLI, so the typed CLI value is
        re-applied here to make the CLI authoritative for ``base_url``. The CLI
        value is itself a Jinja2 template and renders against the same context.

        This is a pluginator lifecycle callback: pluginator discovers a no-arg
        ``configure`` method and calls it from the injected ``pytest_configure``
        after ``init_pytest_config`` + ``install``, when ``self.pytest_config``
        and the resolved ``self.base_url`` are both available. It is NOT a
        ``@pytest.hookimpl``.
        """
        logger.debug("rendering base_url template")
        cli_options = _passed_cli_options(self.pytest_config)

        cli_base_url = cli_options.get(_BASE_URL_CLI_KEY)
        if cli_base_url is not None:
            self.base_url = cli_base_url

        context: dict[str, t.Any] = dict(os.environ)
        context.update(cli_options)
        self.base_url = render_base_url(self.base_url, context)

    @pytest.fixture
    def api(self) -> t.Iterator[Api]:
        """Build an :class:`Api` from the resolved plugin options and tear it down.

        Minimal profile only: ``base_url``/``headers``/``timeout``/
        ``data_key``/``error_key`` — no auth, no cookies. Yields the ``Api`` for
        the test, then closes it afterwards via ``Api.close()`` (delegating to the
        underlying resq.Session's public close()). ``base_url`` is the value rendered once in
        ``configure()`` (stored back on ``self.base_url``).

        Yields:
            An :class:`Api` constructed from the resolved options.
        """
        logger.debug("building api fixture")
        api = Api(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            data_key=self.data_key,
            error_key=self.error_key,
            assert_timeout=self.assert_timeout,
            assert_delay=self.assert_delay,
            assert_field_class=self.assert_field_class,
            assert_response_class=self.assert_response_class,
        )
        yield api
        api.close()

    @pytest.hookimpl(tryfirst=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Stamp collected items with a flaky rerun marker when ``retries > 0``.

        When the resolved ``retries`` option is a positive int, every collected
        item that does not already carry a flaky max-runs gets
        ``pytest.mark.flaky(max_runs=retries)`` so the configured rerun count
        applies uniformly across the suite. Items already marked by the ``flaky``
        plugin (``_flaky_max_runs`` attribute) are
        left untouched to avoid double-marking. The ``flaky`` package is NOT
        disabled here — the marker is the contract surface and takes effect when
        ``flaky`` is installed in the consumer suite.

        Args:
            items: The collected pytest items to mark.
        """
        if self.retries and self.retries > 0:
            for item in items:
                if getattr(item, "_flaky_max_runs", 0) == 0:
                    item.add_marker(pytest.mark.flaky(max_runs=self.retries))

    def _load_plugins(self, context: dict, loaders: list[BaseLoader]) -> None:
        """Assemble the recursive ``pytest_plugins`` list from the config + loaders.

        Reads the ``loader`` section of ``plugin_config`` (defaulting to an empty
        section when absent), builds ``PackageLoader``/``ModuleLoader`` from its
        ``packages``/``modules`` items, prepends the explicit ``loaders``, drives
        each loader to append discovered dotted names into the accumulator, and
        writes the deduplicated result back into ``context["pytest_plugins"]``.

        Args:
            context: The namespace dict whose ``pytest_plugins`` key is read for
                a starting list and written with the result.
            loaders: Explicit loaders to run in addition to those from the
                ``loader`` config section.
        """
        config_loader = self.plugin_config.get(PluginConfigKeys.LOADER, {})

        config_packages = config_loader.get("packages", [])
        config_package_loaders = [PackageLoader.from_config(i) for i in config_packages]

        config_modules = config_loader.get("modules", [])
        config_module_loaders = [ModuleLoader.from_config(i) for i in config_modules]

        modules = list(context.get("pytest_plugins", []))
        loaders = loaders + config_package_loaders + config_module_loaders

        for loader in loaders:
            loader.load(modules)

        context["pytest_plugins"] = list(set(modules))
