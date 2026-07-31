"""Generic pytest-plugin discovery for the `goga_tool_pybuggy.plugin` cell.

Discovers pytest-plugin modules by trial import and by walking the filesystem.
It exposes no network or framework surface of its own; it is a leaf cell
consumed by the parent ``goga_tool_pybuggy.plugin`` cell.

Entities realized in this module:

- ``_module_is_pytest_plugin`` — probe whether a module exposes a pytest-plugin
  surface (a ``pytest_*`` hook or a wrapped fixture) by trial import, without
  polluting ``sys.modules``.
- ``BaseLoader`` — abstract loader contract (``from_config`` factory + ``load``
  that mutates an accumulator list).
- ``PythonImportLoader`` — shared name/required fields and ``from_config``
  parsing for the two concrete loaders.
- ``PackageLoader`` — walk a package directory and append its pytest-plugin
  module names into the accumulator.
- ``ModuleLoader`` — inspect a single module file and append its name into the
  accumulator when it is a pytest plugin.

The assembly of the ``pytest_plugins`` list (reading the plugin's ``loader``
config section and driving the loaders) is the parent plugin's responsibility —
see ``ApiPlugin._load_plugins`` in ``goga_tool_pybuggy/plugin/plugin.py``.

Only the standard library is used — no new runtime dependencies.
"""

import abc
import os
import sys
import typing as t
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path

# Attribute names by which a pytest fixture self-identifies on a module member.
# `__pytest_wrapped__` and `_pytestfixturefunction` are the markers named in the
# contract; `_fixture_function_marker` is the marker carried by the
# `FixtureFunctionDefinition` that `@pytest.fixture` returns on pytest >= 8, so
# the probe still recognizes fixtures across the supported pytest range.
PYTEST_OBJ_ATTRS: t.Final = (
    "__pytest_wrapped__",
    "_pytestfixturefunction",
    "_fixture_function_marker",
)

# Public attribute-name prefixes that mark a module as a pytest plugin (a hook).
PYTEST_OBJ_NAME_PREFIXES: t.Final = (
    "pytest_",
)


def _module_is_pytest_plugin(name: str) -> bool:
    """Probe whether a module is a pytest plugin by trial import.

    A module is treated as a pytest plugin when it exposes a public attribute
    whose name starts with ``pytest_`` (a hook), or an attribute carrying a
    pytest-fixture marker such as ``__pytest_wrapped__`` /
    ``_pytestfixturefunction`` (see ``PYTEST_OBJ_ATTRS``).

    The probe imports the module by its dotted ``name`` and removes it — along
    with any ancestor packages the import pulled in (e.g. probing ``a.b.c``
    also imports ``a`` and ``a.b``) — from ``sys.modules`` afterwards, but only
    the entries that were absent before the probe, so a freshly imported
    candidate never pollutes ``sys.modules``.

    Args:
        name: Dotted module name to probe.

    Returns:
        True when the module exposes a pytest-plugin surface.

    Raises:
        Exception: Any error raised while importing ``name`` (e.g. a
            ``ModuleNotFoundError`` from a broken candidate) propagates
            unchanged — the contract does not swallow import failures.
    """
    # `importlib.import_module` of a dotted `name` also imports every ancestor
    # package (probing "a.b.c" pulls in "a" and "a.b"). Record which of those
    # chain members already existed so the probe removes only the ones it
    # introduced — honoring the constraint that probing must not pollute
    # sys.modules.
    parts = name.split(".")
    chain = [".".join(parts[:i]) for i in range(1, len(parts) + 1)]
    present_before = {candidate for candidate in chain if candidate in sys.modules}

    try:
        module = import_module(name)

        for attr in (i for i in dir(module) if not i.startswith("_")):
            if any(attr.startswith(prefix) for prefix in PYTEST_OBJ_NAME_PREFIXES):
                return True

            obj_attrs = dir(getattr(module, attr))

            if any(i in obj_attrs for i in PYTEST_OBJ_ATTRS):
                return True

        return False
    finally:
        # Remove the probed module and any ancestor packages the probe just
        # imported, but never entries that existed before the probe.
        for candidate in chain:
            if candidate not in present_before and candidate in sys.modules:
                del sys.modules[candidate]


class BaseLoader(abc.ABC):
    """Abstract loader contract.

    A loader discovers pytest-plugin module names from a source (a package
    directory or a single module file) and appends them into an accumulator
    list supplied by the caller.
    """

    @classmethod
    @abc.abstractmethod
    def from_config(cls, config: t.Any) -> "BaseLoader":
        """Build a loader from a loader-config item.

        Args:
            config: A dotted name (``str``) or a mapping with a ``name`` and an
                optional ``required`` flag.

        Returns:
            The constructed loader instance.
        """
        pass

    @abc.abstractmethod
    def load(self, modules: list[str]) -> None:
        """Append discovered pytest-plugin module names into ``modules``.

        Args:
            modules: The accumulator list to mutate in place.
        """
        pass


@dataclass
class PythonImportLoader(BaseLoader):
    """Shared fields and config parsing for the import-based loaders.

    Attributes:
        name: Dotted name of the target (dots map to path separators).
        required: When True, a missing target raises; when False, it is
            tolerated.
    """

    name: str
    required: bool = field(default=True, kw_only=True)

    @classmethod
    def from_config(cls, config: t.Any) -> "PythonImportLoader":
        """Build a loader from a loader-config item.

        A bare dotted name (``str``) yields ``cls(config)`` with the default
        ``required``; a mapping yields ``cls(name=config["name"],
        required=config.get("required", True))``.

        Args:
            config: A dotted name (``str``) or a mapping with a ``name`` and an
                optional ``required`` flag.

        Returns:
            The constructed loader instance.

        Raises:
            TypeError: When ``config`` is neither a ``str`` nor a mapping.
        """
        if isinstance(config, str):
            return cls(config)

        if isinstance(config, dict):
            conf = {
                "name": config["name"],
                "required": config.get("required", True),
            }
            return cls(**conf)

        raise TypeError(f'Unsupported config "{config}"')


@dataclass
class PackageLoader(PythonImportLoader):
    """Walks a package directory and appends its pytest-plugin module names.

    The package directory is resolved relative to the current working directory:
    dots in ``name`` map to path separators (``self.name.replace(".", os.sep)``).
    A subdirectory is walked only when it contains an ``__init__.py``; each
    ``.py`` file in it is probed via ``_module_is_pytest_plugin`` and appended
    when it exposes a plugin surface.
    """

    def load(self, modules: list[str]) -> None:
        """Walk the package and append its pytest-plugin module names.

        Args:
            modules: The accumulator list to mutate in place.

        Raises:
            OSError: When the package directory is missing and ``required`` is
                True.
        """
        path = self.name.lstrip(".").replace(".", os.sep)

        if not Path(path).exists() and self.required:
            raise OSError(f'Directory "{path}" not found')
        if not Path(path).exists() and not self.required:
            return

        for root, _, files in os.walk(path):
            if "__init__.py" in files:
                for module in (i.removesuffix(".py") for i in files):
                    package = root.replace(os.sep, ".")
                    name = f"{package}.{module}"

                    if _module_is_pytest_plugin(name):
                        modules.append(name)


@dataclass
class ModuleLoader(PythonImportLoader):
    """Inspects a single module file and appends its name when it is a plugin.

    The file is resolved relative to the current working directory:
    ``self.name.replace(".", os.sep) + ".py"``. When the file exists it is
    probed via ``_module_is_pytest_plugin`` and its dotted ``name`` is appended
    when it exposes a plugin surface.
    """

    def load(self, modules: list[str]) -> None:
        """Inspect the module file and append its name when it is a plugin.

        Args:
            modules: The accumulator list to mutate in place.

        Raises:
            FileNotFoundError: When the module file is missing and ``required``
                is True.
        """
        path = self.name.lstrip(".").replace(".", os.sep) + ".py"

        if not Path(path).is_file() and self.required:
            raise FileNotFoundError(f'Python file "{path}" not found')
        if not Path(path).is_file() and not self.required:
            return

        if _module_is_pytest_plugin(self.name):
            modules.append(self.name)
