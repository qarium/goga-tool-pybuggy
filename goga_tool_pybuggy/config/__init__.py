"""Configuration cell facade: contract entities, loader, and resolver."""

from .config import Config
from .git_entry import GitEntry
from .pipeline_autonomy import PipelineAutonomy
from .spec_entry import SpecEntry
from .storage import load_config, resolve_autonomy

__all__ = ["Config", "GitEntry", "PipelineAutonomy", "SpecEntry", "load_config", "resolve_autonomy"]
