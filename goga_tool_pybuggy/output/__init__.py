"""Output cell — formatting routines for endpoint display.

Pure functions render endpoints as list text, info JSON, and diff JSON.
"""

from .diff import render_diff
from .info import render_info
from .list import render_list, render_status_list

__all__ = ["render_diff", "render_info", "render_list", "render_status_list"]
