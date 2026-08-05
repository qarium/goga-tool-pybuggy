"""`goga_tool_pybuggy.plugin` cell facade.

Exposes the contract entities of the pybuggy pytest-plugin cell:

- ``ApiPlugin`` — pluginator plugin class providing the configurable options
  (``base_url``/``headers``/``timeout``/``data_key``/``error_key`` for the
  ``api`` fixture, plus ``retries`` for test-run flaky reruns) and the
  function-scope ``api`` fixture that builds an ``Api`` from those options.
  Re-exported from ``.plugin``.
- ``install`` — entry point that wires the plugin into pytest and synchronously
  registers the discovered generated fixtures. ``context`` is defaulted via
  ``call_context()`` (the caller's namespace) and forwarded to ``ApiPlugin``,
  whose ``__init__`` runs ``_load_plugins``. A consumer calls
  ``goga_tool_pybuggy.plugin.install()`` from conftest.py — there is no import-time
  auto-wiring, so ``pytest_plugins = ["goga_tool_pybuggy.plugin"]`` alone does NOT enable
  the plugin.
- ``PluginConfigKeys`` — the config-key enum (the canonical pybuggy config keys
  consumed by ``ApiPlugin`` via the pluginator option-resolution chain and written
  into ``.goga/tools/pybuggy/config.yml``), re-exported so other cells iterate the
  key set data-driven. Re-exported from ``.plugin``.

``Api`` is consumed internally by ``ApiPlugin.api()`` and is deliberately not
re-exported through this facade.
"""

import logging

from pluginator import call_context, install_pytest_plugins

from .loaders import PackageLoader
from .plugin import ApiPlugin, PluginConfigKeys

__all__ = ["ApiPlugin", "install", "PluginConfigKeys"]

logger = logging.getLogger(__name__)


def install(**kwargs: object) -> None:
    """Wire the ``ApiPlugin`` into pytest and register generated fixtures.

    ``context`` is defaulted via ``call_context()`` (which resolves to the
    caller module's globals through the one-level wrapper) and forwarded to
    ``ApiPlugin``; the plugin's ``__init__`` then runs ``_load_plugins`` to
    populate ``context["pytest_plugins"]`` synchronously.

    ``loaders`` defaults to ``[PackageLoader("api", required=False)]`` when
    omitted, so the generated ``api/`` fixture tree is discovered out of the
    box; pass an explicit ``loaders`` (e.g. ``install(loaders=[...])``) to
    override, or ``install(loaders=[])`` to disable discovery.

    Args:
        kwargs: ``context`` (the namespace dict to install into) is defaulted
            here when omitted and forwarded to ``ApiPlugin``; ``loaders`` is
            defaulted to the ``api`` package; ``default_retries`` (default flaky
            rerun count) and the remaining kwargs are forwarded to
            ``ApiPlugin.__init__``.
    """
    kwargs.setdefault("context", call_context())
    kwargs.setdefault("loaders", [PackageLoader("api", required=False)])
    plugin = ApiPlugin(**kwargs)
    install_pytest_plugins(plugin, context=kwargs["context"])


