"""`goga_tool_pybuggy.sandbox.engines` cell facade — per-kind instance engines.

The facade is populated progressively by the engine entity tasks: ``DataOperation``,
``InstanceAddress``, ``check_runtime``, ``build_engine``, ``BaseEngine``, ``EngineError``,
``PostgresEngine``, ``KafkaEngine``, ``VaultEngine``, ``HttpEngine``, and the ``refs``
grammar routine ``validate_insert_rows``.
"""

from .address import InstanceAddress
from .base import BaseEngine
from .base import EngineError as EngineError
from .http import HttpEngine
from .kafka import KafkaEngine
from .operation import DataOperation
from .postgres import PostgresEngine
from .refs import validate_insert_rows
from .runtime import build_engine, check_runtime
from .vault import VaultEngine

__all__ = [
    "BaseEngine",
    "DataOperation",
    "EngineError",
    "HttpEngine",
    "InstanceAddress",
    "KafkaEngine",
    "PostgresEngine",
    "VaultEngine",
    "build_engine",
    "check_runtime",
    "validate_insert_rows",
]
