"""`goga_tool_pybuggy.lifecycle` cell facade.

Exposes ``install`` — the post-install hook the goga platform calls from the package
facade after a successful pip.
"""

from .lifecycle import install

__all__ = ["install"]
