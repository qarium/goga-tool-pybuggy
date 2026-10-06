"""`goga_tool_pybuggy.sandbox` — session-scoped isolated service testing.

The cell facade: ``Sandbox``, ``BaselineBoundary``, ``ServiceContainer``,
``render_service_env``, ``activate_sandbox``, ``active_sandbox``.
"""

from .activation import activate_sandbox, active_sandbox
from .baseline import BaselineBoundary
from .env_render import render_service_env
from .sandbox import Sandbox
from .service_container import ServiceContainer

__all__ = [
    "BaselineBoundary",
    "Sandbox",
    "ServiceContainer",
    "activate_sandbox",
    "active_sandbox",
    "render_service_env",
]
