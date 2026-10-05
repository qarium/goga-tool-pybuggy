"""`goga_tool_pybuggy.plugin` cell facade.

Exposes ``ApiPlugin``, ``PluginConfigKeys`` and ``install``; the plugin is enabled by calling ``install()``.
"""

import logging

from pluginator import call_context, install_pytest_plugins

from .loaders import PackageLoader
from .plugin import ApiPlugin, PluginConfigKeys

__all__ = ["ApiPlugin", "PluginConfigKeys", "install"]

logger = logging.getLogger(__name__)


def install(**kwargs: object) -> None:
    """Wire the ``ApiPlugin`` into pytest and register generated fixtures.

    ``loaders`` defaults to ``[PackageLoader("api", required=False)]``; ``install(loaders=[])`` disables discovery.

    Args:
        kwargs: Forwarded to ``ApiPlugin``; ``context`` and ``loaders`` are defaulted here when omitted.
    """
    kwargs.setdefault("context", call_context())
    kwargs.setdefault("loaders", [PackageLoader("api", required=False)])
    plugin = ApiPlugin(**kwargs)
    install_pytest_plugins(plugin, context=kwargs["context"])
