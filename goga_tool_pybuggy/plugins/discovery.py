"""Shared fixture-plugin discovery of the plugins cell.

The ``loader:`` section every pybuggy tool document carries (api, sandbox, web alike) wires
external fixture packages/modules into the run — e.g. a shared presets package with fixtures
over ``sandbox``. The section is read at install time, synchronously: pytest reads
``pytest_plugins`` from the conftest namespace once its import finishes, so the discovery must
complete inside the plugin constructors the installation entry calls — never in ``configure``
(too late) and never at import of this module.
"""

import typing as t

from yaml import YAMLError

from .loaders import BaseLoader, ModuleLoader, PackageLoader

#: The discovery section key shared by every pybuggy tool document — api.yml, sandbox.yml, web.yml.
LOADER_SECTION: t.Final[str] = "loader"


def loader_section_of(plugin: t.Any) -> dict:
    """Read the parsed ``loader:`` section of a plugin's config document.

    An unparsable document yields an empty section — the discovery defers to the configure-time
    gate of the plugin, which fails the run with its clean error; a null or missing section is an
    empty one.

    Args:
        plugin: The plugin whose config document carries the section.

    Returns:
        The parsed section mapping; ``{}`` when absent, null, or unparsable.
    """
    try:
        section = plugin.plugin_config.get(LOADER_SECTION, {})
    except YAMLError:
        return {}

    return section or {}


def load_fixture_plugins(context: dict, loaders: list[BaseLoader], loader_section: t.Mapping[str, t.Any]) -> None:
    """Assemble the recursive ``pytest_plugins`` list of a namespace from loaders and the section.

    Existing ``context["pytest_plugins"]`` entries seed the accumulator — a consumer's own
    declarations survive; the explicit loaders run, then the section's ``packages`` and
    ``modules`` items (each a dotted name or a ``{name, required}`` mapping — ``from_config``),
    and the deduplicated result is written back.

    Args:
        context: Namespace dict whose ``pytest_plugins`` key seeds the list and receives the result.
        loaders: Explicit loaders (empty when none).
        loader_section: The parsed ``loader:`` section of a tool document; empty means no
            configured discovery.

    Raises:
        OSError: A required package directory is missing (``PackageLoader``).
        FileNotFoundError: A required module file is missing (``ModuleLoader``).
        TypeError: A section item is neither a dotted name nor a mapping.
    """
    section = loader_section or {}

    configured = [PackageLoader.from_config(item) for item in section.get("packages", [])]
    configured += [ModuleLoader.from_config(item) for item in section.get("modules", [])]

    modules = list(context.get("pytest_plugins", []))

    for loader in [*loaders, *configured]:
        loader.load(modules)

    context["pytest_plugins"] = list(set(modules))
