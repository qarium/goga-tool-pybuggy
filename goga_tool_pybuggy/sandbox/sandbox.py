"""Sandbox entity: the session runtime of the sandbox."""

import logging
from typing import TypeVar

from .baseline import BaselineBoundary
from .config import SandboxConfig
from .data import DataBatch, HttpInstance, KafkaInstance, PostgresInstance, VaultInstance
from .engines import BaseEngine, DataOperation, InstanceAddress, build_engine, check_runtime
from .env_render import render_service_env
from .service_container import ServiceContainer

logger = logging.getLogger(__name__)

ViewT = TypeVar("ViewT", PostgresInstance, KafkaInstance, VaultInstance, HttpInstance)


class Sandbox:
    """The running session sandbox.

    One sandbox owns one pytest-session environment: the ordered startup of the dependency
    instance engines and the service under test, the readiness gates, the per-test data
    batch the instance views declare into, and the guaranteed removal on every exit path.
    The service container is never restarted on reset — only dependency instance data resets.

    Attributes:
        config: The validated sandbox configuration.
        engines: The dependency instance engines, keyed by instance name in declaration order.
        service: The service-under-test container.
    """

    def __init__(self, config: SandboxConfig) -> None:
        """Initialize the session sandbox of one validated configuration.

        Args:
            config: The validated sandbox configuration.
        """
        self.config = config
        self.engines: dict[str, BaseEngine] = {
            name: build_engine(instance_config) for name, instance_config in config.instances.items()
        }
        self.service = ServiceContainer(config.service)
        self._batch = DataBatch()
        self._boundary_open = False
        self._boundary_batch: DataBatch | None = None

    @property
    def base_url(self) -> str:
        """The service address of the running sandbox.

        Returns:
            The mapped service address — the value the api fixture uses while a sandbox
            is active; readable once the service has started.
        """
        return f"http://{self.service.host}:{self.service.port}"

    def start(self) -> None:
        """Bring the sandbox up in the ordered sequence.

        Probes the container runtime, starts every configured instance engine — in
        declaration order, each with its startup data — renders the service env against
        the started instance addresses, then starts the service container to readiness.
        A failure at any step removes everything started so far and re-raises.

        Raises:
            RuntimeError: The container runtime is unavailable or the service did not
                become ready; engines wrap their own failures into ``EngineError``.
        """
        logger.info("sandbox starting", extra={"image": self.config.service.image, "instances": list(self.engines)})

        try:
            check_runtime()

            addresses = self._start_engines()
            rendered = render_service_env(self.config.service.env, addresses)
            logger.info("service env rendered", extra={"values": len(rendered)})

            self.service.start(rendered)
        except Exception:
            logger.error("sandbox start failed", extra={"image": self.config.service.image})
            self.stop()

            raise

        logger.info("sandbox ready", extra={"base_url": self.base_url, "source": "sandbox"})

    def stop(self) -> None:
        """Remove everything the sandbox started.

        The service stops first, then the engines in reverse start order — each guarded,
        so one failing removal never blocks the remaining ones. Safe when already stopped.

        Raises:
            RuntimeError: Never; a failing engine stop is logged instead of raising.
        """
        self.service.stop()

        for name in reversed(list(self.engines)):
            try:
                self.engines[name].stop()
            except Exception:
                logger.error("engine stop failed", extra={"instance": name})

        logger.info("sandbox stopped", extra={"image": self.config.service.image})

    def clear(self) -> None:
        """Return every dependency instance to its baseline.

        Resets every engine — wipe and journal replay — in declaration order. The service
        container keeps running: only dependency instance data resets.

        Raises:
            EngineError: An engine reset failed.
        """
        for name, engine in self.engines.items():
            engine.reset()
            logger.info("instance reset", extra={"instance": name})

    def baseline(self) -> BaselineBoundary:
        """Open the session baseline boundary.

        Returns:
            The boundary of this sandbox; inside it declared operations apply immediately
            and land in the engine journals.
        """
        return BaselineBoundary(self)

    def apply_pending(self) -> None:
        """Apply the current test's accumulated operations as one consistent batch.

        Takes the accumulated data batch, groups the operations by instance preserving
        accumulation order, and applies each group to the instance's engine. Runs before
        the first service call of a test; a second call applies nothing — the batch
        drained.

        Raises:
            EngineError: An operation failed; the message identifies it.
        """
        operations = self._batch.take()

        groups: dict[str, list[DataOperation]] = {}

        for operation in operations:
            groups.setdefault(operation.instance, []).append(operation)

        for instance, group in groups.items():
            self.engines[instance].apply(group)
            logger.debug("pending operations applied", extra={"instance": instance, "operations": len(group)})

    def ensure_service(self) -> None:
        """Fail fast when the service container has died.

        Raises:
            RuntimeError: The service under test is no longer running — the message names
                the service image and attaches its output; a no-op while the service runs.
        """
        if not self.service.alive():
            logger.error("service under test died", extra={"image": self.config.service.image})

            raise RuntimeError(
                f"the service under test (image {self.config.service.image}) died; its output:\n{self.service.logs()}"
            )

    def new_test_batch(self) -> None:
        """Create the fresh data batch of the next test.

        Called by the registered per-test hook before every test, so a new test never
        sees a previous test's operations.
        """
        self._batch = DataBatch()

    def postgresql(self, name: str) -> PostgresInstance:
        """The test-facing view of the named postgresql instance.

        Args:
            name: The instance name from the sandbox configuration.

        Returns:
            The view of the instance, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                instances.
        """
        return self._view(PostgresInstance, "postgresql", name)

    def kafka(self, name: str) -> KafkaInstance:
        """The test-facing view of the named kafka instance.

        Args:
            name: The instance name from the sandbox configuration.

        Returns:
            The view of the instance, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                instances.
        """
        return self._view(KafkaInstance, "kafka", name)

    def vault(self, name: str) -> VaultInstance:
        """The test-facing view of the named vault instance.

        Args:
            name: The instance name from the sandbox configuration.

        Returns:
            The view of the instance, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                instances.
        """
        return self._view(VaultInstance, "vault", name)

    def http(self, name: str) -> HttpInstance:
        """The test-facing view of the named http instance.

        Args:
            name: The instance name from the sandbox configuration.

        Returns:
            The view of the instance, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                instances.
        """
        return self._view(HttpInstance, "http", name)

    def _start_engines(self) -> dict[str, InstanceAddress]:
        """Start every instance engine with its startup data, in declaration order.

        Returns:
            The mapped address of every started instance, keyed by instance name.
        """
        addresses: dict[str, InstanceAddress] = {}

        for name, engine in self.engines.items():
            startup = self._startup_operations(name)

            engine.start(startup)
            addresses[name] = engine.address
            logger.info("startup data applied", extra={"instance": name, "operations": len(startup)})

        return addresses

    def _startup_operations(self, name: str) -> list[DataOperation]:
        """Assemble the startup operations of one instance from the startup data sections.

        The fixed section order is vault secrets, http mappings, the kafka spec, then
        postgres init — within a section the declaration order is the application order.

        Args:
            name: The instance name whose startup data is assembled.

        Returns:
            The instance's startup operations, in application order.
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

        spec_path = data.kafka.get(name)

        if spec_path is not None:
            operations.append(DataOperation(instance=name, kind="kafka", action="spec", payload={"path": spec_path}))

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

    def _view(self, view_class: type[ViewT], kind: str, name: str) -> ViewT:
        """Build the view of one configured instance, validating kind and name.

        Args:
            view_class: The view class of the requested kind.
            kind: The requested instance kind — the factory's kind.
            name: The requested instance name.

        Returns:
            The view of the instance, bound to the current batch.

        Raises:
            ValueError: Unknown name or kind mismatch — the message lists the configured
                instances.
        """
        instances = self.config.instances

        if name not in instances or instances[name].kind != kind:
            listing = ", ".join(
                f"{instance_name} ({instance_config.kind})" for instance_name, instance_config in instances.items()
            )

            raise ValueError(f"no {kind} instance named '{name}'; configured instances: {listing}")

        return view_class(name=name, address=self.engines[name].address, batch=self._current_batch())
