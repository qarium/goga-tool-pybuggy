"""Statuses cell facade — the two pybuggy topic-status registration routines."""

from .automate import register_automate_statuses
from .fix import register_fix_statuses

__all__ = ["register_automate_statuses", "register_fix_statuses"]
