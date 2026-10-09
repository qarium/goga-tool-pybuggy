"""`goga_tool_pybuggy.plugin` cell facade.

Exposes ``ApiPlugin``, ``PluginConfigKeys``, ``SandboxPlugin`` and ``install``;
the plugin is enabled by calling ``install()``.
"""

import logging
from pathlib import Path

from pluginator import call_context, install_pytest_plugins

from . import defaults
from .loaders import PackageLoader
from .plugin import ApiPlugin, PluginConfigKeys
from .sandbox_plugin import SandboxPlugin

__all__ = ["ApiPlugin", "PluginConfigKeys", "SandboxPlugin", "install"]

logger = logging.getLogger(__name__)


def install(**kwargs: object) -> None:
    """Wire the ``ApiPlugin`` into pytest and, when its document is present, the ``SandboxPlugin``.

    ``loaders`` defaults to ``[PackageLoader("api", required=False)]``; ``install(loaders=[])``
    disables discovery. The sandbox document ``.goga/tools/pybuggy/sandbox.yml`` gates the
    second plugin by presence only: with the document the ``SandboxPlugin`` joins the same
    installation call and owns the product ``sandbox`` fixtures — it reads and validates its
    config itself at configphase; without the document nothing sandbox-related is registered,
    and a test requesting the ``sandbox`` fixture gets pytest's standard
    "fixture 'sandbox' not found".

    Args:
        kwargs: Forwarded to ``ApiPlugin``; ``context`` and ``loaders`` are defaulted here when omitted.
    """
    kwargs.setdefault("context", call_context())
    kwargs.setdefault("loaders", [PackageLoader("api", required=False)])

    plugins = [ApiPlugin(**kwargs)]

    if Path(defaults.SANDBOX_CONFIG_FILE).is_file():
        plugins.append(SandboxPlugin())
        logger.info("sandbox plugin enabled", extra={"document": defaults.SANDBOX_CONFIG_FILE})
    else:
        logger.debug("sandbox plugin absent", extra={"document": defaults.SANDBOX_CONFIG_FILE})

    install_pytest_plugins(*plugins, context=kwargs["context"])
