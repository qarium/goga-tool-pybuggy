"""`goga_tool_pybuggy.sandbox.data` cell facade — lazy declaration surface.

The facade is populated progressively by the data entity tasks: ``DataBatch``,
``PostgresInstance``, ``KafkaInstance``, ``VaultInstance``, ``HttpInstance``,
``services``.
"""

from .batch import DataBatch

__all__ = [
    "DataBatch",
]
