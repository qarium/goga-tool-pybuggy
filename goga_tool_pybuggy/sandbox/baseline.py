"""BaselineBoundary entity: the immediate-apply session baseline boundary."""

import logging
from types import TracebackType
from typing import TYPE_CHECKING

from .data import DataBatch
from .engines import BaseEngine, DataOperation

if TYPE_CHECKING:
    from .sandbox import Sandbox

logger = logging.getLogger(__name__)


class BoundaryBatch(DataBatch):
    """The immediate-apply batch of an open baseline boundary.

    Internal to the sandbox cell. While the boundary is open, the sandbox hands this
    batch to the instance views: every declared operation applies to its instance's
    engine and joins the engine journal at declaration time — the declaration itself
    is the execution. ``take`` never yields operations; nothing is ever pending
    inside the boundary.
    """

    def __init__(self, engines: dict[str, BaseEngine]) -> None:
        """Initialize the boundary batch over the sandbox engines.

        Args:
            engines: The started instance engines, keyed by instance name.
        """
        super().__init__()
        self._engines = engines

    def add(self, operation: DataOperation) -> None:
        """Apply one operation immediately and journal it as baseline.

        Args:
            operation: The declared operation; its instance identifies the engine.
        """
        engine = self._engines[operation.instance]

        engine.apply([operation])
        engine.record([operation])

        logger.debug("boundary operation applied and journaled", extra={"instance": operation.instance})

    def take(self) -> list[DataOperation]:
        """Never yield operations; the boundary applies at declaration time.

        Returns:
            An empty list — the boundary drains nothing.
        """
        return []


class BaselineBoundary:
    """The session baseline boundary of one sandbox.

    While open, the sandbox routes view declarations through the immediate-apply
    boundary batch — each declared operation runs against its engine and lands in
    the engine journal at declaration time. Closing the boundary freezes the
    journals as the session baseline: startup operations plus boundary operations,
    in application order, replayed by every engine reset. Outside the boundary the
    sandbox keeps its lazy declaration contract.

    Attributes:
        sandbox: The sandbox whose declaration routing the boundary switches.
    """

    def __init__(self, sandbox: "Sandbox") -> None:
        """Initialize the boundary of one sandbox.

        Args:
            sandbox: The sandbox whose declaration routing the boundary switches.
        """
        self._sandbox = sandbox

    def open(self) -> None:
        """Switch the sandbox to immediate-apply declaration routing."""
        self._sandbox._boundary_batch = BoundaryBatch(self._sandbox.engines)
        self._sandbox._boundary_open = True

        logger.info("baseline boundary opened", extra={"instances": list(self._sandbox.engines)})

    def close(self) -> None:
        """Freeze the session baseline and restore lazy declaration routing."""
        self._sandbox._boundary_open = False
        self._sandbox._boundary_batch = None

        logger.info("baseline boundary closed", extra={"instances": list(self._sandbox.engines)})

    def __enter__(self) -> "BaselineBoundary":
        """Open the boundary on entry of the ``with`` form.

        Returns:
            The opened boundary.
        """
        self.open()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the boundary on exit; exceptions leaving the block propagate.

        Args:
            exc_type: The type of the exception leaving the block, if any.
            exc_value: The exception leaving the block, if any.
            traceback: The traceback of the exception leaving the block, if any.
        """
        self.close()
