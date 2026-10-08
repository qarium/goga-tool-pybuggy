"""Sandbox entity: the session runtime of the sandbox."""

import logging
from typing import TypeVar

from testcontainers.core.network import Network

from .baseline import BaselineBoundary
from .config import SandboxConfig
from .data import DataBatch, HttpInstance, KafkaInstance, PostgresInstance, VaultInstance
from .engines import BaseEngine, DataOperation, InstanceAddress, build_engine, check_runtime
from .env_render import render_service_env
from .service_container import ServiceContainer

logger = logging.getLogger(__name__)

ViewT = TypeVar("ViewT", PostgresInstance, KafkaInstance, VaultInstance, HttpInstance)

SANDBOX_NETWORK_LABELS = {"pybuggy-sandbox": "true"}


class Sandbox:
    """The running session sandbox.

    One sandbox owns one pytest-session environment: the ordered startup of the dependency
    service engines and the instance under test, the readiness gates, the per-test data
    batch the service views declare into, and the guaranteed removal on every exit path.
    The instance container is never restarted on reset — only dependency service data
    resets.

    Attributes:
        config: The validated sandbox configuration.
        engines: The dependency service engines, keyed by service name in declaration order.
        service: The instance-under-test container.
    """

    def __init__(self, config: SandboxConfig) -> None:
        """Initialize the session sandbox of one validated configuration.

        Args:
            config: The validated sandbox configuration.
        """
        self.config = config
        self.engines: dict[str, BaseEngine] = {
            name: build_engine(service_config) for name, service_config in config.services.items()
        }
        self.service = ServiceContainer(config.instance)
        self._batch = DataBatch()
        self._boundary_open = False
        self._boundary_batch: DataBatch | None = None
        self._network: Network | None = None

    @property
    def base_url(self) -> str:
        """The service address of the running sandbox.

        Returns:
            The mapped instance address — the value the api fixture uses while a sandbox
            is active; readable once the instance has started.
        """
        return f"http://{self.service.host}:{self.service.port}"

    def start(self) -> None:
        """Bring the sandbox up in the ordered sequence.

        Probes the container runtime, creates the sandbox network — the per-session isolation
        boundary every container joins — starts every configured service engine in
        declaration order, each with its startup data, renders the instance env against the
        started service addresses, then starts the instance container and waits for its
        readiness — the port, or the health path when declared — within the readiness
        declaration's deadline at its interval. A failure at any step removes everything
        started so far and re-raises.

        Raises:
            RuntimeError: The container runtime is unavailable; engines wrap their own
                failures into ``EngineError``, and the instance readiness expiry raises it.
        """
        logger.info("sandbox starting", extra={"image": self.config.instance.image, "services": list(self.engines)})

        try:
            check_runtime()

            self._network = Network(docker_network_kw={"labels": SANDBOX_NETWORK_LABELS})
            self._network.create()

            addresses = self._start_engines()
            rendered = render_service_env(self.config.instance.env, addresses)
            logger.info("instance env rendered", extra={"values": len(rendered)})

            self.service.start(rendered, self._network)
        except Exception:
            logger.error("sandbox start failed", extra={"image": self.config.instance.image})
            self.stop()

            raise

        logger.info("sandbox ready", extra={"base_url": self.base_url, "source": "sandbox"})

    def stop(self) -> None:
        """Remove everything the sandbox started.

        The instance stops first, then the engines in reverse start order — each guarded,
        so one failing removal never blocks the remaining ones — then the sandbox network
        goes. Safe when already stopped.

        Raises:
            RuntimeError: Never; a failing engine stop is logged instead of raising.
        """
        self.service.stop()

        for name in reversed(list(self.engines)):
            try:
                self.engines[name].stop()
            except Exception:
                logger.error("engine stop failed", extra={"service": name})

        self._remove_network()

        logger.info("sandbox stopped", extra={"image": self.config.instance.image})

    def clear(self) -> None:
        """Return every dependency service to its baseline.

        Resets every engine — wipe and journal replay — in declaration order. The instance
        container keeps running: only dependency service data resets.

        Raises:
            EngineError: An engine reset failed.
        """
        for name, engine in self.engines.items():
            engine.reset()
            logger.info("service reset", extra={"service": name})

    def baseline(self) -> BaselineBoundary:
        """Open the session baseline boundary.

        Returns:
            The boundary of this sandbox; inside it declared operations apply immediately
            and land in the engine journals.
        """
        return BaselineBoundary(self)

    def apply_pending(self) -> None:
        """Apply the current test's accumulated operations as one consistent batch.

        Takes the accumulated data batch, groups the operations by service preserving
        accumulation order, and applies each group to the service's engine. Runs before
        the first service call of a test; a second call applies nothing — the batch
        drained.

        Raises:
            EngineError: An operation failed; the message identifies it.
        """
        operations = self._batch.take()

        groups: dict[str, list[DataOperation]] = {}

        for operation in operations:
            groups.setdefault(operation.instance, []).append(operation)

        for service, group in groups.items():
            self.engines[service].apply(group)
            logger.debug("pending operations applied", extra={"service": service, "operations": len(group)})

    def ensure_service(self) -> None:
        """Fail fast when the instance container has died.

        Raises:
            RuntimeError: The instance under test is no longer running — the message names
                the instance image and attaches its output; a no-op while the instance
                runs.
        """
        if not self.service.alive():
            logger.error("instance under test died", extra={"image": self.config.instance.image})

            raise RuntimeError(
                f"the instance under test (image {self.config.instance.image}) died; its output:\n{self.service.logs()}"
            )

    def new_test_batch(self) -> None:
        """Create the fresh data batch of the next test.

        Called by the registered per-test hook before every test, so a new test never
        sees a previous test's operations.
        """
        self._batch = DataBatch()

    def postgresql(self, name: str) -> PostgresInstance:
        """The test-facing view of the named postgresql service.

        Args:
            name: The service name from the sandbox configuration.

        Returns:
            The view of the service, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                services.
        """
        return self._view(PostgresInstance, "postgresql", name)

    def kafka(self, name: str) -> KafkaInstance:
        """The test-facing view of the named kafka service.

        Args:
            name: The service name from the sandbox configuration.

        Returns:
            The view of the service, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                services.
        """
        return self._view(KafkaInstance, "kafka", name)

    def vault(self, name: str) -> VaultInstance:
        """The test-facing view of the named vault service.

        Args:
            name: The service name from the sandbox configuration.

        Returns:
            The view of the service, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                services.
        """
        return self._view(VaultInstance, "vault", name)

    def http(self, name: str) -> HttpInstance:
        """The test-facing view of the named http service.

        Args:
            name: The service name from the sandbox configuration.

        Returns:
            The view of the service, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                services.
        """
        return self._view(HttpInstance, "http", name)

    def _start_engines(self) -> dict[str, InstanceAddress]:
        """Start every service engine with its startup data, in declaration order.

        Each engine's container joins the sandbox network.

        Returns:
            The mapped address of every started service, keyed by service name.
        """
        addresses: dict[str, InstanceAddress] = {}

        for name, engine in self.engines.items():
            startup = self._startup_operations(name)

            engine.start(startup, self._network)
            addresses[name] = engine.address
            logger.info("startup data applied", extra={"service": name, "operations": len(startup)})

        return addresses

    def _remove_network(self) -> None:
        """Remove the sandbox network — guarded, after every container left it.

        Raises:
            RuntimeError: Never; a failing removal is logged instead of raising, so teardown
                of the remaining parts never gets blocked.
        """
        if self._network is None:
            return

        network = self._network
        self._network = None

        try:
            network.remove()
        except Exception:
            logger.error("sandbox network removal failed", extra={"services": list(self.engines)})

            return

        logger.debug("sandbox network removed", extra={"services": list(self.engines)})

    def _startup_operations(self, name: str) -> list[DataOperation]:
        """Assemble the startup operations of one service from the startup data sections.

        The fixed section order is vault secrets, http mappings, then postgres init —
        within a section the declaration order is the application order. Kafka services
        carry no startup operations: their topology is declared inline on the service
        entry and consumed at container build.

        Args:
            name: The service name whose startup data is assembled.

        Returns:
            The service's startup operations, in application order.
        """
        data = self.config.data
        operations: list[DataOperation] = []

        for declaration in data.vault.get(name, []):
            operations.append(
                DataOperation(
                    instance=name,
                    kind="vault",
                    action="put",
                    payload={"path": declaration["path"], "data": declaration["data"]},
                )
            )

        for mapping in data.http.get(name, []):
            operations.append(DataOperation(instance=name, kind="http", action="stub", payload=mapping))

        for statement in data.postgres.get(name, []):
            operations.append(
                DataOperation(instance=name, kind="postgresql", action="insert", payload={"sql": statement})
            )

        return operations

    def _current_batch(self) -> DataBatch:
        """The batch the view factories bind to.

        Returns:
            The boundary batch while the baseline boundary is open, the per-test batch
            otherwise.
        """
        return self._boundary_batch if self._boundary_open else self._batch

    def _require_service(self, kind: str, name: str) -> None:
        """Validate that ``name`` names a configured service of ``kind``.

        Args:
            kind: The required service kind.
            name: The requested service name.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                services.
        """
        services = self.config.services

        if name not in services or services[name].kind != kind:
            listing = ", ".join(
                f"{service_name} ({service_config.kind})" for service_name, service_config in services.items()
            )

            raise ValueError(f"no {kind} service named '{name}'; configured services: {listing}")

    def _view(self, view_class: type[ViewT], kind: str, name: str) -> ViewT:
        """Build the view of one configured service, validating kind and name.

        Args:
            view_class: The view class of the requested kind.
            kind: The requested service kind — the factory's kind.
            name: The requested service name.

        Returns:
            The view of the service, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                services.
        """
        self._require_service(kind, name)

        return view_class(name=name, address=self.engines[name].address, batch=self._current_batch())
