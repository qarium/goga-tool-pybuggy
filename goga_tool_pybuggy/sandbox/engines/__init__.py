"""`goga_tool_pybuggy.sandbox.engines` cell facade — per-kind dependency service engines.

The facade is populated progressively by the engine entity tasks: ``DataOperation``,
``InstanceAddress``, ``check_runtime``, ``normalize_container_host``, ``build_engine``,
``BaseEngine``, ``EngineError``, ``PostgresEngine``, ``KafkaEngine``, ``VaultEngine``,
``HttpEngine``, ``RedisEngine``, and the ``refs`` grammar routine ``validate_insert_rows``.
"""

from .address import InstanceAddress
from .base import BaseEngine
from .base import EngineError as EngineError
from .http import HttpEngine
from .kafka import KafkaEngine
from .operation import DataOperation
from .postgres import PostgresEngine
from .redis import RedisEngine
from .refs import validate_insert_rows
from .runtime import build_engine, check_runtime, normalize_container_host
from .vault import VaultEngine

__all__ = [
    "BaseEngine",
    "DataOperation",
    "EngineError",
    "HttpEngine",
    "InstanceAddress",
    "KafkaEngine",
    "PostgresEngine",
    "RedisEngine",
    "VaultEngine",
    "build_engine",
    "check_runtime",
    "normalize_container_host",
    "validate_insert_rows",
]
