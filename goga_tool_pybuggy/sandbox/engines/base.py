"""BaseEngine entity and EngineError: the common per-instance engine contract."""

import logging
import socket
from collections.abc import Callable
from typing import TypeVar

from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network

from ..config.instance import InstanceConfig
from .address import InstanceAddress
from .operation import DataOperation

logger = logging.getLogger(__name__)

StepT = TypeVar("StepT")


class EngineError(RuntimeError):
    """A failed engine operation.

    Every engine failure surfaces as this type — the message names the instance, the failed
    operation or lifecycle step, and the underlying cause.
    """


class BaseEngine:
    """Common per-instance engine: lifecycle, data-plane execution, baseline journal, reset.

    The base owns the shared control flow — start the kind's container to readiness, execute
    operations in order, hold the baseline journal, wipe-then-replay on reset, and stop safely.
    Each kind engine implements the internal kind hooks: ``_build_container``, ``_wait_ready``,
    ``_open_plane``, ``_execute``, ``_wipe`` and ``_close_plane``, plus the ``_container_port``
    class attribute carrying the kind's service port the ``address`` property publishes.

    Attributes:
        config: The instance declaration — name, kind, image override.
    """

    _container_port: int

    def __init__(self, config: InstanceConfig) -> None:
        """Initialize the engine of one configured dependency instance.

        Args:
            config: The instance declaration — name, kind, image override.
        """
        self.config = config
        self._journal: list[DataOperation] = []
        self._started = False
        self._container: DockerContainer | None = None
        self._network: Network | None = None

    @property
    def address(self) -> InstanceAddress:
        """The mapped address of the started instance, read back from the container engine.

        Returns:
            The mapped host and the published host-side port of the running instance.

        Raises:
            EngineError: The instance is not started — there is no mapped address to read.
        """
        if self._container is None:
            raise EngineError(f"instance '{self.config.name}': address requested before start")

        return InstanceAddress(
            host=self._container.get_container_host_ip(),
            port=int(self._container.get_exposed_port(self._container_port)),
        )

    def start(self, startup: list[DataOperation], network: Network | None = None) -> None:
        """Start the instance container and bring it to readiness.

        The startup operations apply in declaration order and join the journal as the initial
        baseline entries. A failed start leaves nothing behind — the started parts are removed
        and the failure re-raises.

        Args:
            startup: The startup data of this instance, in declaration order.
            network: The sandbox network the container joins under its instance-name alias —
                the per-sandbox isolation boundary between parallel sessions.

        Raises:
            EngineError: A lifecycle step or a startup operation failed; the message names the
                instance and the failed step or operation.
        """
        self._network = network

        logger.info("instance starting", extra={"instance": self.config.name, "kind": self.config.kind})

        try:
            self._container = self._run_step("start failed at container build", self._build_container)
            self._run_step("start failed at container start", self._container.start)
            self._run_step("start failed at readiness wait", self._wait_ready)
            self._run_step("start failed at data-plane open", self._open_plane)
            self._apply_operations(startup)
        except Exception:
            logger.error("instance start failed", extra={"instance": self.config.name, "kind": self.config.kind})
            self.stop()
            raise

        self._journal.extend(startup)
        self._started = True
        logger.info(
            "instance ready",
            extra={"instance": self.config.name, "kind": self.config.kind, "startup_operations": len(startup)},
        )

    def apply(self, operations: list[DataOperation]) -> None:
        """Execute operations against the instance data plane, in order.

        The operations never join the journal here — recording belongs to the baseline boundary.

        Args:
            operations: Operations of this instance's kind, in application order.

        Raises:
            EngineError: An operation failed or the instance is not started.
        """
        self._require_started("apply")
        self._apply_operations(operations)

    def record(self, operations: list[DataOperation]) -> None:
        """Append operations to the baseline journal.

        Args:
            operations: Applied operations to remember as the baseline.
        """
        self._journal.extend(operations)

    def reset(self) -> None:
        """Return the instance to its baseline.

        Wipes the instance to the kind's empty state, then replays the journal through the same
        execution path as apply.

        Raises:
            EngineError: The wipe or a replayed operation failed, or the instance is not started.
        """
        self._require_started("reset")
        self._run_step("reset failed at wipe", self._wipe)
        self._apply_operations(list(self._journal))

    def stop(self) -> None:
        """Remove the container and close the data-plane connection.

        Safe on an already-stopped instance — teardown steps log their failures instead of
        raising, so a partial stop never blocks the removal of the remaining parts.
        """
        had_container = self._container is not None

        self._run_quietly("data-plane close", self._close_plane)

        if had_container:
            self._run_quietly("container stop", self._container.stop)
            self._container = None

        self._started = False

        if had_container:
            logger.info("instance stopped", extra={"instance": self.config.name, "kind": self.config.kind})

    def _build_container(self) -> DockerContainer:
        """Build the kind's container — pinned image unless overridden, labels, published ports.

        Returns:
            The built, not yet started, kind container.

        Raises:
            NotImplementedError: The kind engine did not override the hook.
        """
        raise NotImplementedError("the kind engine did not override _build_container")

    def _wait_ready(self) -> None:
        """Wait for kind readiness after the container started.

        The default returns immediately — module containers are ready once ``start`` returns;
        generic containers override with an explicit probe loop bounded by a deadline.
        """

    def _open_plane(self) -> None:
        """Open the kind's data-plane connection.

        Raises:
            NotImplementedError: The kind engine did not override the hook.
        """
        raise NotImplementedError("the kind engine did not override _open_plane")

    def _execute(self, operation: DataOperation) -> None:
        """Execute one operation through the kind's data plane.

        Args:
            operation: The operation to execute.

        Raises:
            NotImplementedError: The kind engine did not override the hook.
        """
        raise NotImplementedError(f"the kind engine did not override _execute (action '{operation.action}')")

    def _wipe(self) -> None:
        """Wipe the instance to the kind's empty state.

        Raises:
            NotImplementedError: The kind engine did not override the hook.
        """
        raise NotImplementedError("the kind engine did not override _wipe")

    def _close_plane(self) -> None:
        """Close the kind's data-plane connection; safe when nothing is open.

        Raises:
            NotImplementedError: The kind engine did not override the hook.
        """
        raise NotImplementedError("the kind engine did not override _close_plane")

    def _apply_operations(self, operations: list[DataOperation]) -> None:
        """Execute operations in order through the guarded execution path.

        Args:
            operations: Operations to execute, in application order.

        Raises:
            EngineError: An operation failed; the message names instance, action and cause.
        """
        for operation in operations:
            self._run_operation(operation)

    def _run_operation(self, operation: DataOperation) -> None:
        """Execute one operation, wrapping failures into a readable ``EngineError``.

        Args:
            operation: The operation to execute.

        Raises:
            EngineError: The operation failed — ``instance '<name>': <action> failed: <cause>``.
        """
        try:
            self._execute(operation)
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"instance '{self.config.name}': {operation.action} failed: {exc}") from exc

        logger.debug("operation executed", extra={"instance": self.config.name, "action": operation.action})

    def _run_step(self, failure: str, action: Callable[[], StepT]) -> StepT:
        """Run one lifecycle step, wrapping failures into a readable ``EngineError``.

        Args:
            failure: The failure prefix naming the lifecycle step.
            action: The step callable.

        Returns:
            Whatever the step callable returns.

        Raises:
            EngineError: The step failed; the message names the instance and the step.
        """
        try:
            return action()
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"instance '{self.config.name}': {failure}: {exc}") from exc

    def _run_quietly(self, step: str, action: Callable[[], object]) -> None:
        """Run one teardown step, logging failures instead of raising.

        Args:
            step: The teardown step name for the failure log.
            action: The step callable.
        """
        try:
            action()
        except Exception:
            logger.error(
                "instance teardown step failed",
                extra={"instance": self.config.name, "kind": self.config.kind, "step": step},
            )

    def _require_started(self, action: str) -> None:
        """Enforce the no-operations-before-start constraint.

        Args:
            action: The calling operation name for the error message.

        Raises:
            EngineError: The instance is not started.
        """
        if not self._started:
            raise EngineError(f"instance '{self.config.name}': {action} failed: the instance is not started")

    def _attach_network(self, container: DockerContainer) -> None:
        """Join the built container to the sandbox network.

        A no-op without a network — engines stay usable standalone.

        Args:
            container: The built, not yet started, kind container.
        """
        if self._network is None:
            return

        container.with_network(self._network)


def reserve_port() -> int:
    """Reserve a free TCP port on the docker host.

    Binds port 0, reads back the assigned port and releases the socket — the standard
    reservation probe for engines that restart their container as the reset mechanism: a
    dynamically assigned published port changes on every restart, breaking the
    restart-stable-address contract, so such engines publish a reserved fixed port on both
    sides instead. A race window remains between the release and the daemon's bind a moment
    later; losing it fails the container start with the daemon's clear already-allocated
    error instead of a silent misbehavior.

    Returns:
        A port number currently free on every local interface.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("", 0))

        return int(probe.getsockname()[1])
