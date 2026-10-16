"""Statuses cell facade — the three pybuggy topic-status registration routines."""

from .automate import register_automate_statuses
from .fix import register_fix_statuses
from .patch import register_patch_statuses

__all__ = ["register_automate_statuses", "register_fix_statuses", "register_patch_statuses"]
