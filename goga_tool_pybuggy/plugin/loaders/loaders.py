"""Generic pytest-plugin discovery for the `goga_tool_pybuggy.plugin` cell.

Discovers pytest-plugin modules by trial import and by walking the filesystem.
"""

import abc
import os
import sys
import typing as t
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path

# Attribute names by which a pytest fixture self-identifies; `_fixture_function_marker` covers pytest >= 8.
PYTEST_OBJ_ATTRS: t.Final = (
    "__pytest_wrapped__",
    "_pytestfixturefunction",
    "_fixture_function_marker",
)

# Public attribute-name prefixes that mark a module as a pytest plugin (a hook).
PYTEST_OBJ_NAME_PREFIXES: t.Final = ("pytest_",)


def _module_is_pytest_plugin(name: str) -> bool:
    """Probe whether a module is a pytest plugin by trial import.

    The probe removes the imported module and pulled-in ancestors from ``sys.modules``, never pre-existing entries.

    Args:
        name: Dotted module name to probe.

    Returns:
        True when the module exposes a pytest-plugin surface.

    Raises:
        Exception: Any error raised while importing ``name`` propagates unchanged.
    """
    # Record which ancestor packages already existed so cleanup removes only newly imported modules.
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
        # Remove only the modules the probe just imported, never pre-existing entries.
        for candidate in chain:
            if candidate not in present_before and candidate in sys.modules:
                del sys.modules[candidate]


class BaseLoader(abc.ABC):
    """Abstract loader contract.

    Discovers pytest-plugin module names from a source and appends them into a caller-supplied accumulator.
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

    Resolved relative to the working directory; only subdirectories with an ``__init__.py`` are walked.
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
                # Only .py files are candidates — importing a sibling like meta.json fails on its parent package.
                for module in (i.removesuffix(".py") for i in files if i.endswith(".py")):
                    package = root.replace(os.sep, ".")
                    name = f"{package}.{module}"

                    if _module_is_pytest_plugin(name):
                        modules.append(name)


@dataclass
class ModuleLoader(PythonImportLoader):
    """Inspects a single module file and appends its name when it is a plugin.

    The file is resolved relative to the working directory as ``name`` with ``.py`` appended.
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
