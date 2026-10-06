"""`goga_tool_pybuggy.sandbox.engines` cell facade — per-kind instance engines.

The facade is populated progressively by the engine entity tasks: ``DataOperation``,
``InstanceAddress``, ``check_runtime``, ``build_engine``, ``BaseEngine``, ``PostgresEngine``,
``KafkaEngine``, ``VaultEngine``, ``HttpEngine``.
"""

from .address import InstanceAddress
from .base import BaseEngine, EngineError
from .operation import DataOperation

__all__ = ["BaseEngine", "DataOperation", "EngineError", "InstanceAddress"]
