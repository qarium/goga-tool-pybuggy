"""`goga_tool_pybuggy.sandbox.data` cell facade — lazy declaration surface.

The facade is populated progressively by the data entity tasks: ``DataBatch``,
``PostgresInstance``, ``KafkaInstance``, ``VaultInstance``, ``HttpInstance``,
``services``.
"""

from .batch import DataBatch
from .http import HttpInstance
from .kafka import KafkaInstance
from .postgres import PostgresInstance
from .vault import VaultInstance

__all__ = [
    "DataBatch",
    "HttpInstance",
    "KafkaInstance",
    "PostgresInstance",
    "VaultInstance",
]
