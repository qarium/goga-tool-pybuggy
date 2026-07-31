"""
goga_tool_pybuggy.spec — OpenAPI endpoint extraction.

Exports build_endpoint_id, Endpoint, load_spec, extract_endpoints.
"""

from .endpoint import Endpoint
from .endpoint_id import build_endpoint_id
from .extract import extract_endpoints
from .loader import load_spec

__all__ = ["Endpoint", "build_endpoint_id", "extract_endpoints", "load_spec"]
