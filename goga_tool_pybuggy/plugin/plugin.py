"""pybuggy pytest-plugin cell.

Built on ``pluginator``: provides the function-scope ``api`` fixture and the ``install`` entry point.
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
from .envvars import API_TIMEOUT, BASE_URL
from .loaders import BaseLoader, ModuleLoader, PackageLoader
from .render import render_base_url

logger = logging.getLogger(__name__)


class PluginConfigKeys(str, Enum):
    """Config-file keys for the ``ApiPlugin`` options.

    Implementation-hint enum; ``LOADER`` is not an option but the fixture-discovery section.
    """

    BASE_URL = "base_url"
    HEADERS = "headers"
    TIMEOUT = "timeout"
    RETRIES = "retries"
    LOADER = "loader"
    ASSERT_TIMEOUT = "assert_timeout"
    ASSERT_DELAY = "assert_delay"
    ASSERT_FIELD_CLASS = "assert_field_class"
    ASSERT_RESPONSE_CLASS = "assert_response_class"


# A typed CLI option token (``--key``, ``-k``, ``--key=value``); captures the option name.
_PLACEHOLDER_SOURCE_PATTERN = re.compile(r"^--?([A-Za-z_][\w-]*)(?:=(.*))?$")

# Normalized ``--base-url`` flag name, matching the keys of ``_passed_cli_options`` output.
_BASE_URL_CLI_KEY: t.Final[str] = "base_url"


def _passed_cli_options(config: t.Any) -> dict[str, t.Any]:
    """Collect the CLI options the user actually typed, keyed by normalized name.

    Raw ``invocation_params.args`` tokens only — the full ``config.option`` namespace must not leak into templates.

    Args:
        config: The pytest ``Config`` exposing ``invocation_params.args`` and ``option``.

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
        name: getattr(option, name) for name in names if hasattr(option, name) and getattr(option, name) is not None
    }


@define.plugin("pybuggy", config=defaults.CONFIG_FILE)
class ApiPlugin:
    """Pluginator plugin exposing the Api options and the ``api`` fixture.

    Lazy options resolve via ``plugin_config_key -> env_var -> command_line -> default_from``.

    Attributes:
        plugin_config: Anchor declaration; ``BasePlugin`` supplies the parsed yaml dict.
        base_url: Required base-URL Jinja2 template (``BASE_URL`` env / ``--base-url``), rendered in ``configure()``.
        headers: Default request headers (default ``{}``).
        timeout: Request timeout in seconds (nullable; ``API_TIMEOUT`` env / ``--api-timeout`` CLI).
        retries: Flaky rerun count (default ``0``; ``--retries``); when positive, unmarked items get a ``flaky`` marker.
        assert_timeout: Baseline assert-polling timeout in seconds (nullable; ``--api-assert-timeout``).
        assert_delay: Seconds between assert-polling attempts (nullable; ``--api-assert-delay``).
        assert_field_class: Dotted ``module:Class`` path of a custom ``AssertField`` subclass (nullable).
        assert_response_class: Dotted ``module:Class`` path of a custom ``Expect`` subclass (nullable).
    """

    plugin_config: dict

    base_url = define.option(
        str,
        plugin_config_key=PluginConfigKeys.BASE_URL,
        env_var=BASE_URL,
        command_line=CommandLine("--base-url", action="store", help="Base URL of the service under test"),
        required=True,
    )
    headers = define.option(dict, plugin_config_key=PluginConfigKeys.HEADERS)
    timeout = define.option(
        float,
        plugin_config_key=PluginConfigKeys.TIMEOUT,
        env_var=API_TIMEOUT,
        command_line=CommandLine("--api-timeout", action="store", help="Network timeout"),
        nullable=True,
    )
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
        default_assert_delay: t.Optional[int | float] = None,
    ) -> None:
        """Initialize the plugin and synchronously register generated fixtures.

        ``_load_plugins`` assembles ``pytest_plugins`` from the ``loader`` config section plus the explicit ``loaders``.

        Args:
            context: Namespace dict the plugin installs into; its ``pytest_plugins`` key is populated here.
            loaders: Explicit loaders in addition to the ``loader`` config section; defaults to none.
            default_retries: Default flaky rerun count when unset via config or ``--retries``.
            default_assert_timeout: Default assert-polling timeout when unset via config or ``--api-assert-timeout``.
            default_assert_delay: Default assert-polling delay when unset via config or ``--api-assert-delay``.
        """
        super().__init__()

        self._default_retries = default_retries
        self._default_assert_timeout = default_assert_timeout
        self._default_assert_delay = default_assert_delay

        self._load_plugins(context, loaders or [])

    def configure(self) -> None:
        """Render ``base_url`` once against the full environment and passed CLI options.

        Pluginator lifecycle callback at pytest configphase — a missing required ``base_url`` fails before any fixture.
        """
        cli_options = _passed_cli_options(self.pytest_config)

        cli_base_url = cli_options.get(_BASE_URL_CLI_KEY)
        if cli_base_url is not None:
            self.base_url = cli_base_url

        logger.debug("rendering base_url template", extra={"base_url": self.base_url})
        context: dict[str, t.Any] = dict(os.environ)
        context.update(cli_options)
        self.base_url = render_base_url(self.base_url, context)

    @pytest.fixture
    def api(self) -> t.Iterator[Api]:
        """Build an :class:`Api` from the resolved plugin options and tear it down.

        Minimal profile — ``base_url``/``headers``/``timeout`` plus the assert options; no auth, no cookies.

        Yields:
            An :class:`Api` constructed from the resolved options.
        """
        logger.debug("building api fixture", extra={"base_url": self.base_url})
        api = Api(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
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

        Items already marked by ``flaky`` (``_flaky_max_runs``) are left untouched to avoid double-marking.

        Args:
            items: The collected pytest items to mark.
        """
        if self.retries and self.retries > 0:
            for item in items:
                if getattr(item, "_flaky_max_runs", 0) == 0:
                    item.add_marker(pytest.mark.flaky(max_runs=self.retries))

    def _load_plugins(self, context: dict, loaders: list[BaseLoader]) -> None:
        """Assemble the recursive ``pytest_plugins`` list from the config + loaders.

        Existing ``context["pytest_plugins"]`` entries seed the accumulator; the deduplicated result is written back.

        Args:
            context: Namespace dict whose ``pytest_plugins`` key seeds the list and receives the result.
            loaders: Explicit loaders in addition to those from the ``loader`` config section.
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
