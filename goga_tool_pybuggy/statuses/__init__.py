"""Statuses cell facade — the four pybuggy topic-status registration routines."""

from .automate import register_automate_statuses
from .fix import register_fix_statuses
from .patch import register_patch_statuses
from .web import register_web_statuses

__all__ = [
    "register_automate_statuses",
    "register_fix_statuses",
    "register_patch_statuses",
    "register_web_statuses",
]
