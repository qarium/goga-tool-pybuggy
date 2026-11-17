"""`goga_tool_pybuggy.plugins` cell facade.

Exposes ``ApiPlugin``, ``PluginConfigKeys``, ``SandboxPlugin``, ``WebConfigKeys``, ``WebPlugin``
and ``install``; the plugins are enabled by calling ``install()``.
"""

import logging
from pathlib import Path

from pluginator import call_context, install_pytest_plugins

from ..sandbox.engines import normalize_container_host
from . import defaults
from .api_plugin import ApiPlugin, PluginConfigKeys
from .sandbox_plugin import SandboxPlugin
from .web_plugin import WebConfigKeys, WebPlugin

__all__ = ["ApiPlugin", "PluginConfigKeys", "SandboxPlugin", "WebConfigKeys", "WebPlugin", "install"]

logger = logging.getLogger(__name__)


def install(**kwargs: object) -> None:
    """Wire the plugins into pytest, each gated on its own activation document.

    The api plugin activates when the api document ``.goga/tools/pybuggy/api.yml`` exists;
    without the document nothing api-related is registered — the required ``base_url`` never
    fails a web-only or sandbox-only run — and a test requesting the ``api`` fixture gets
    pytest's standard "fixture 'api' not found" (``BASE_URL`` stays a value source, not an
    activation source).

    The explicit ``loaders`` join every active plugin's own fixture discovery: the api plugin
    defaults to the generated ``api/`` package tree and the web plugin to the generated
    ``pages/`` package tree when none arrive (``install(loaders=[])`` disables both defaults),
    and the sandbox plugin discovers what the explicit loaders
    plus its document's ``loader:`` section name — a project wires external fixture packages
    in through the config, without touching the conftest. The sandbox document
    ``.goga/tools/pybuggy/sandbox.yml`` gates the sandbox plugin by presence only: with the
    document the ``SandboxPlugin`` joins the same installation call and owns the product
    ``sandbox`` fixtures — it reads and validates its config itself at configphase — and the
    container-host address is normalized first, so a plain host run resolves the same address
    space as a container run; without the document nothing sandbox-related is registered, and a
    test requesting the ``sandbox`` fixture gets pytest's standard "fixture 'sandbox' not found".

    The web document ``.goga/tools/pybuggy/web.yml`` gates the ``WebPlugin`` by presence only
    as well: with the document the web plugin joins the same installation call and owns the
    ``web`` fixture — it reads and validates its config itself at configphase —; without the
    document nothing web-related is registered, and a test requesting the ``web`` fixture gets
    pytest's standard "fixture 'web' not found".

    Args:
        kwargs: The installation surface, forwarded by name — ``context`` is defaulted here when
            omitted and reaches every plugin; the explicit ``loaders`` reach every active plugin's
            discovery; ``default_retries``, ``default_assert_timeout``, and ``default_assert_delay``
            tune the api plugin's option defaults.
    """
    kwargs.setdefault("context", call_context())
    context = kwargs["context"]
    loaders = kwargs.get("loaders")

    plugins = []

    if Path(defaults.API_CONFIG_FILE).is_file():
        plugins.append(
            ApiPlugin(
                context=context,
                loaders=loaders,
                default_retries=kwargs.get("default_retries"),
                default_assert_timeout=kwargs.get("default_assert_timeout"),
                default_assert_delay=kwargs.get("default_assert_delay"),
            )
        )
        logger.info("api plugin enabled", extra={"document": defaults.API_CONFIG_FILE})
    else:
        logger.debug("api plugin absent", extra={"document": defaults.API_CONFIG_FILE})

    if Path(defaults.SANDBOX_CONFIG_FILE).is_file():
        normalize_container_host()
        plugins.append(SandboxPlugin(context=context, loaders=loaders))
        logger.info("sandbox plugin enabled", extra={"document": defaults.SANDBOX_CONFIG_FILE})
    else:
        logger.debug("sandbox plugin absent", extra={"document": defaults.SANDBOX_CONFIG_FILE})

    if Path(defaults.WEB_CONFIG_FILE).is_file():
        plugins.append(WebPlugin(context=context, loaders=loaders))
        logger.info("web plugin enabled", extra={"document": defaults.WEB_CONFIG_FILE})
    else:
        logger.debug("web plugin absent", extra={"document": defaults.WEB_CONFIG_FILE})

    install_pytest_plugins(*plugins, context=context)
