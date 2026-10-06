"""DataBatch entity: the lazy per-test operation accumulator."""

from ..engines import DataOperation


class DataBatch:
    """The accumulated operations of the current test.

    One batch exists per test. Instance views and presets append declared operations
    with ``add`` — nothing is executed at declaration time; the session facade drains
    the batch with ``take`` when the declared operations are applied. The accumulation
    order is the application order per instance — presets precede in-test operations.
    """

    def __init__(self) -> None:
        """Initialize an empty batch."""
        self._operations: list[DataOperation] = []

    def add(self, operation: DataOperation) -> None:
        """Append one operation to the batch. Nothing is executed.

        Args:
            operation: The declared operation to accumulate, in declaration order.
        """
        self._operations.append(operation)

    def take(self) -> list[DataOperation]:
        """Drain the batch in accumulation order; the batch is empty afterwards.

        Returns:
            The accumulated operations in the order they were added.
        """
        drained = list(self._operations)

        self._operations.clear()

        return drained
