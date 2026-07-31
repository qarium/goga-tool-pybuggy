"""Configuration cell facade.

Exposes the contract entities declared by the ``config`` cell: the pydantic
models ``GitEntry``, ``SpecEntry``, ``Config``, the ``load_config`` loader, and
the fixed ``CONFIG_PATH``.
"""

from .config import Config
from .git_entry import GitEntry
from .spec_entry import SpecEntry
from .storage import CONFIG_PATH, load_config

__all__ = ["CONFIG_PATH", "Config", "GitEntry", "SpecEntry", "load_config"]
