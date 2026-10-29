"""`goga_tool_pybuggy.plugins` cell facade.

Exposes ``ApiPlugin``, ``PluginConfigKeys``, ``SandboxPlugin``, ``WebPlugin`` and ``install``;
the plugins are enabled by calling ``install()``.
"""

import logging
from pathlib import Path

from pluginator import call_context, install_pytest_plugins

from ..sandbox.engines import normalize_container_host
from . import defaults
from .api_plugin import ApiPlugin, PluginConfigKeys
from .loaders import PackageLoader
from .sandbox_plugin import SandboxPlugin
from .web_plugin import WebPlugin

__all__ = ["ApiPlugin", "PluginConfigKeys", "SandboxPlugin", "WebPlugin", "install"]

logger = logging.getLogger(__name__)


def install(**kwargs: object) -> None:
    """Wire the ``ApiPlugin`` into pytest and, when its document is present, the ``SandboxPlugin``.

    ``loaders`` defaults to ``[PackageLoader("api", required=False)]``; ``install(loaders=[])``
    disables discovery. The sandbox document ``.goga/tools/pybuggy/sandbox.yml`` gates the
    second plugin by presence only: with the document the ``SandboxPlugin`` joins the same
    installation call and owns the product ``sandbox`` fixtures — it reads and validates its
    config itself at configphase — and the container-host address is normalized first, so a
    plain host run resolves the same address space as a container run; without the document
    nothing sandbox-related is registered, and a test requesting the ``sandbox`` fixture gets
    pytest's standard "fixture 'sandbox' not found".

    The web document ``.goga/tools/pybuggy/web.yml`` gates the ``WebPlugin`` by presence only
    as well: with the document the web plugin joins the same installation call and owns the
    ``web`` fixture — it reads and validates its config itself at configphase —; without the
    document nothing web-related is registered, and a test requesting the ``web`` fixture gets
    pytest's standard "fixture 'web' not found".

    Args:
        kwargs: Forwarded to ``ApiPlugin``; ``context`` and ``loaders`` are defaulted here when omitted.
    """
    kwargs.setdefault("context", call_context())
    kwargs.setdefault("loaders", [PackageLoader("api", required=False)])

    plugins = [ApiPlugin(**kwargs)]

    if Path(defaults.SANDBOX_CONFIG_FILE).is_file():
        normalize_container_host()
        plugins.append(SandboxPlugin())
        logger.info("sandbox plugin enabled", extra={"document": defaults.SANDBOX_CONFIG_FILE})
    else:
        logger.debug("sandbox plugin absent", extra={"document": defaults.SANDBOX_CONFIG_FILE})

    if Path(defaults.WEB_CONFIG_FILE).is_file():
        plugins.append(WebPlugin())
        logger.info("web plugin enabled", extra={"document": defaults.WEB_CONFIG_FILE})
    else:
        logger.debug("web plugin absent", extra={"document": defaults.WEB_CONFIG_FILE})

    install_pytest_plugins(*plugins, context=kwargs["context"])
