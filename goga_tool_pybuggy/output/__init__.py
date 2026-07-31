"""Output cell — formatting routines for endpoint display.

This cell provides pure functions that render endpoint data into text
(list format) and JSON (info format) for CLI consumption.
"""

from .info import render_info
from .list import render_list

__all__ = ["render_info", "render_list"]
