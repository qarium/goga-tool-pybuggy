"""pybuggy pytest-plugin cell.

Built on ``pluginator``: provides the function-scope ``api`` fixture and the ``install`` entry point.
"""

import logging
import os
import typing as t
from enum import Enum

import pytest
from pluginator import CommandLine, define

from ..api import Api
from . import defaults
from .discovery import LOADER_SECTION, load_fixture_plugins, loader_section_of
from .envvars import API_TIMEOUT, BASE_URL
from .loaders import BaseLoader, PackageLoader
from .render import passed_cli_options, render_base_url

logger = logging.getLogger(__name__)


class PluginConfigKeys(str, Enum):
    """Config-file keys for the ``ApiPlugin`` options.

    Implementation-hint enum; ``LOADER`` is not an option but the fixture-discovery section — the
    shared ``loader:`` key of every tool document (`discovery.LOADER_SECTION`).
    """

    BASE_URL = "base_url"
    HEADERS = "headers"
    TIMEOUT = "timeout"
    RETRIES = "retries"
    LOADER = LOADER_SECTION
    ASSERT_TIMEOUT = "assert_timeout"
    ASSERT_DELAY = "assert_delay"
    ASSERT_FIELD_CLASS = "assert_field_class"
    ASSERT_RESPONSE_CLASS = "assert_response_class"


# Normalized ``--base-url`` flag name, matching the keys of ``passed_cli_options`` output.
_BASE_URL_CLI_KEY: t.Final[str] = "base_url"


@define.plugin("pybuggy-api", config=defaults.API_CONFIG_FILE)
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

        ``_load_plugins`` assembles ``pytest_plugins`` from the ``loader`` config section plus the
        explicit ``loaders``; ``loaders=None`` (the default) adds the generated ``api/`` package
        tree to the discovery, an empty list disables it — the plugin owns its own default.

        Args:
            context: Namespace dict the plugin installs into; its ``pytest_plugins`` key is populated here.
            loaders: Explicit loaders in addition to the ``loader`` config section; ``None`` (the
                default) adds ``PackageLoader("api", required=False)``, ``[]`` disables the
                default discovery.
            default_retries: Default flaky rerun count when unset via config or ``--retries``.
            default_assert_timeout: Default assert-polling timeout when unset via config or ``--api-assert-timeout``.
            default_assert_delay: Default assert-polling delay when unset via config or ``--api-assert-delay``.
        """
        super().__init__()

        self._default_retries = default_retries
        self._default_assert_timeout = default_assert_timeout
        self._default_assert_delay = default_assert_delay

        self._load_plugins(context, loaders if loaders is not None else [PackageLoader("api", required=False)])

    def configure(self) -> None:
        """Render ``base_url`` once against the full environment and passed CLI options.

        Pluginator lifecycle callback at pytest configphase — a missing required ``base_url`` fails before any fixture.
        """
        cli_options = passed_cli_options(self.pytest_config)

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

        The client carries the rendered static ``base_url``; binding an address (the running
        sandbox) is explicit in the test body through ``Api.bind``/``Endpoint.bind``.

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

        Delegates to the shared discovery routine (`discovery.load_fixture_plugins`) with the
        ``loader`` section of the api document — the section read is guarded, so an unparsable
        document defers to the configphase; existing namespace entries seed the accumulator, the
        deduplicated result is written back synchronously (the ``pytest_plugins`` deadline of the
        conftest import).

        Args:
            context: Namespace dict whose ``pytest_plugins`` key seeds the list and receives the result.
            loaders: Explicit loaders in addition to the section — the api package default among
                them (resolved by ``__init__`` when no explicit loaders arrive).
        """
        load_fixture_plugins(context, loaders, loader_section_of(self))
