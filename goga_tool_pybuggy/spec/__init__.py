"""
goga_tool_pybuggy.spec — OpenAPI/Swagger endpoint extraction.

Exports build_endpoint_id, detect_spec_version, Endpoint, load_spec,
extract_endpoints.
"""

from .endpoint import Endpoint
from .endpoint_id import build_endpoint_id
from .extract import detect_spec_version, extract_endpoints
from .loader import load_spec

__all__ = [
    "Endpoint",
    "build_endpoint_id",
    "detect_spec_version",
    "extract_endpoints",
    "load_spec",
]
