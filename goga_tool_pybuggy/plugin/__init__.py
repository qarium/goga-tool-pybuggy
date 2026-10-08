"""`goga_tool_pybuggy.plugin` cell facade.

Exposes ``ApiPlugin``, ``PluginConfigKeys`` and ``install``; the plugin is enabled by calling ``install()``.
"""

import logging

from pluginator import call_context, install_pytest_plugins

from ..sandbox import activate_sandbox
from .loaders import PackageLoader
from .plugin import ApiPlugin, PluginConfigKeys

__all__ = ["ApiPlugin", "PluginConfigKeys", "install"]

logger = logging.getLogger(__name__)


def install(**kwargs: object) -> None:
    """Wire the ``ApiPlugin`` into pytest, arming the sandbox when its document is present.

    ``loaders`` defaults to ``[PackageLoader("api", required=False)]``; ``install(loaders=[])``
    disables discovery. Before construction ``activate_sandbox(context)`` reads
    ``.goga/tools/pybuggy/sandbox.yml`` in the CWD — with a valid document it registers the
    session lifecycle hooks into the context; the activation is kept on the plugin as
    ``sandbox_activation`` (``None`` when the document is absent, leaving everything inert).

    Args:
        kwargs: Forwarded to ``ApiPlugin``; ``context`` and ``loaders`` are defaulted here when omitted.
    """
    kwargs.setdefault("context", call_context())
    kwargs.setdefault("loaders", [PackageLoader("api", required=False)])

    activation = activate_sandbox(kwargs["context"])

    plugin = ApiPlugin(**kwargs)
    plugin.sandbox_activation = activation
    install_pytest_plugins(plugin, context=kwargs["context"])
