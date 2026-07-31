"""`goga_tool_pybuggy.plugin.loaders` cell facade.

Exposes the contract entities of the generic pytest-plugin discovery cell:

- ``BaseLoader`` — abstract loader contract (``from_config`` factory + ``load``
  that mutates an accumulator list).
- ``PackageLoader`` — walks a package directory and appends its pytest-plugin
  module names into the accumulator.
- ``ModuleLoader`` — inspects a single module file and appends its name into
  the accumulator when it is an pytest plugin.

``_module_is_pytest_plugin`` is internal to the cell (used by
``PackageLoader.load``/``ModuleLoader.load``) and is deliberately not re-exported
here. Assembling the ``pytest_plugins`` list is the parent plugin's job — see
``ApiPlugin._load_plugins``.
"""

from .loaders import BaseLoader, ModuleLoader, PackageLoader

__all__ = ["BaseLoader", "ModuleLoader", "PackageLoader"]
