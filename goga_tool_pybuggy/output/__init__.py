"""Output cell — formatting routines for endpoint display.

This cell provides pure functions that render endpoint data into text
(list format), JSON (info format), and comparison-result JSON documents
(diff format) for CLI consumption.
"""

from .diff import render_diff
from .info import render_info
from .list import render_list, render_status_list

__all__ = ["render_diff", "render_info", "render_list", "render_status_list"]
