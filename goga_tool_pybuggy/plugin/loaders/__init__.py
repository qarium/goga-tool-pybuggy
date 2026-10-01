"""`goga_tool_pybuggy.plugin.loaders` cell facade.

Exposes ``BaseLoader``, ``PackageLoader`` and ``ModuleLoader``; ``pytest_plugins`` assembly is the parent cell's job.
"""

from .loaders import BaseLoader, ModuleLoader, PackageLoader

__all__ = ["BaseLoader", "ModuleLoader", "PackageLoader"]
