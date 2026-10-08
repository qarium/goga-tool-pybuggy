"""Shared pytest fixtures for the sandbox test package.

Also carries the container-runtime availability probe and the ``requires_docker`` skip condition
every docker-gated test in the plan reuses (``from ..conftest import requires_docker``), and the
``FakeEngine`` / ``FakeService`` recording stubs the sandbox cell unit tests drive — import them
the same way, or take the ``fake_engine`` / ``fake_service`` fixtures for the default shapes.
"""

import functools
import pathlib
from collections.abc import Callable
from typing import ClassVar

import docker
import pytest
from goga_tool_pybuggy.sandbox.engines import DataOperation, InstanceAddress


@functools.lru_cache(maxsize=1)
def docker_available() -> bool:
    """Probe the container-runtime availability once per test session.

    Pings the daemon through the docker SDK client — the same client testcontainers drives — and
    treats any failure as unavailability, so container-dependent tests skip instead of hanging on
    a silent connection timeout.

    Returns:
        True when a docker-compatible daemon answers the ping, False otherwise.
    """
    try:
        return bool(docker.from_env().ping())
    except Exception:
        return False


requires_docker = pytest.mark.skipif(
    not docker_available(),
    reason="docker-compatible container runtime unavailable",
)


DOCUMENT_PATH = pathlib.Path(".goga") / "tools" / "pybuggy" / "sandbox.yml"


@pytest.fixture
def sandbox_yaml(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], pathlib.Path]:
    """Write the sandbox document under ``tmp_path`` at its fixed location and chdir there.

    Args:
        tmp_path: The per-test temporary directory serving as the consumer repository root.
        monkeypatch: The pytest monkeypatch fixture performing the chdir.

    Returns:
        A writer placing ``content`` at ``.goga/tools/pybuggy/sandbox.yml`` under ``tmp_path``
        (creating the parent directories), returning the written path.
    """
    monkeypatch.chdir(tmp_path)

    def _write(content: str) -> pathlib.Path:
        path = tmp_path / DOCUMENT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    return _write


class FakeEngine:
    """Recording engine double for the sandbox cell unit tests.

    The double mirrors the ``BaseEngine`` surface the ``Sandbox`` drives — lifecycle, apply,
    record, reset, address — without touching containers: every call is recorded, so tests
    assert ordering, grouping and cleanup against the records instead of live services.

    Attributes:
        name: The service name the sandbox resolves this engine by.
        kind: The configured service kind — the view factories and the preset enqueue
            validate against it.
        address: The mapped address the service views bind to.
        events: An optional shared sink recording the lifecycle call sequence across fakes.
        applied: Operations executed through ``apply``, in call order.
        journaled: Operations that joined the baseline journal — startup and recorded.
        reset_count: The number of ``reset`` calls.
        started: Whether the last lifecycle call left the service started.
        stopped: Whether ``stop`` was called.
    """

    def __init__(
        self,
        name: str = "db",
        kind: str = "postgresql",
        address: InstanceAddress | None = None,
        fail_start: bool = False,
        events: list[str] | None = None,
    ) -> None:
        """Initialize the recording engine.

        Args:
            name: The service name the sandbox resolves this engine by.
            kind: The configured service kind.
            address: The mapped address the service views bind to; defaults to a sample address.
            fail_start: Make ``start`` raise — the failed-start cleanup scenarios.
            events: An optional shared sink recording the lifecycle call sequence across fakes.
        """
        self.name = name
        self.kind = kind
        self.address = address if address is not None else InstanceAddress(host="127.0.0.2", port=5432)
        self.fail_start = fail_start
        self.events = events
        self.applied: list[DataOperation] = []
        self.journaled: list[DataOperation] = []
        self.reset_count = 0
        self.started = False
        self.stopped = False

    def start(self, startup: list[DataOperation], network: object = None) -> None:
        """Record a start; the startup operations join the journal as the initial baseline.

        Args:
            startup: The startup data of this service, in declaration order.
            network: The sandbox network handed through — recorded, never used.

        Raises:
            RuntimeError: ``fail_start`` is set — the failed-start scenarios.
        """
        self._emit("start")

        if self.fail_start:
            raise RuntimeError(f"service '{self.name}': start failed: fake refused to start")

        self.started = True
        self.stopped = False
        self.journaled.extend(startup)

    def apply(self, operations: list[DataOperation]) -> None:
        """Record operations as applied, in order; they never join the journal.

        Args:
            operations: Operations of this service's kind, in application order.
        """
        self._emit("apply")
        self.applied.extend(operations)

    def record(self, operations: list[DataOperation]) -> None:
        """Record operations as journaled baseline entries.

        Args:
            operations: Applied operations to remember as the baseline.
        """
        self._emit("record")
        self.journaled.extend(operations)

    def reset(self) -> None:
        """Record a reset call — the wipe-and-replay contract asserted by count."""
        self._emit("reset")
        self.reset_count += 1

    def stop(self) -> None:
        """Record a stop; safe when already stopped."""
        self._emit("stop")
        self.started = False
        self.stopped = True

    def _emit(self, event: str) -> None:
        """Append one lifecycle event label to the shared sink when present.

        Args:
            event: The event name of the recorded call.
        """
        if self.events is not None:
            self.events.append(f"engine:{self.name}:{event}")


class FakeService:
    """Recording instance double for the sandbox cell unit tests.

    The double mirrors the ``ServiceContainer`` surface the ``Sandbox`` drives — start with the
    rendered env, stop, liveness, logs — with liveness and output configurable, so the
    died-instance diagnostics are assertable without containers.

    Attributes:
        events: An optional shared sink recording the lifecycle call sequence across fakes.
        started: Whether the last lifecycle call left the instance started.
        stopped: Whether ``stop`` was called.
        started_env: The rendered env of the last ``start`` call; None before the first.
        host: The mapped host the sandbox ``base_url`` reads resolve to.
        port: The published port the sandbox ``base_url`` reads resolve to.
    """

    def __init__(
        self,
        alive: bool = True,
        logs: str = "",
        host: str = "127.0.0.9",
        port: int = 9000,
        events: list[str] | None = None,
    ) -> None:
        """Initialize the recording instance container.

        Args:
            alive: The value every ``alive()`` probe returns.
            logs: The diagnostic output every ``logs()`` call returns.
            host: The mapped host the sandbox ``base_url`` reads resolve to.
            port: The published port the sandbox ``base_url`` reads resolve to.
            events: An optional shared sink recording the lifecycle call sequence across fakes.
        """
        self._alive = alive
        self._logs = logs
        self.host = host
        self.port = port
        self.events = events
        self.started = False
        self.stopped = False
        self.started_env: dict[str, str] | None = None
        self.started_network: object | None = None

    def start(self, env: dict[str, str], network: object = None) -> None:
        """Record a start carrying the rendered env.

        Args:
            env: The rendered instance environment.
            network: The sandbox network handed through — recorded for the lifecycle assertions.
        """
        self._emit("start")
        self.started = True
        self.stopped = False
        self.started_env = dict(env)
        self.started_network = network

    def stop(self) -> None:
        """Record a stop; safe when already stopped."""
        self._emit("stop")
        self.started = False
        self.stopped = True

    def alive(self) -> bool:
        """Report the configured liveness.

        Returns:
            The configured ``alive`` value.
        """
        return self._alive

    def logs(self) -> str:
        """Report the configured diagnostic output.

        Returns:
            The configured ``logs`` value.
        """
        return self._logs

    def _emit(self, event: str) -> None:
        """Append one lifecycle event label to the shared sink when present.

        Args:
            event: The event name of the recorded call.
        """
        if self.events is not None:
            self.events.append(f"instance:{event}")


@pytest.fixture
def fake_engine() -> FakeEngine:
    """A fresh recording engine of the default ``db`` service — postgresql kind."""
    return FakeEngine()


@pytest.fixture
def fake_service() -> FakeService:
    """A fresh recording instance container — running, with empty output."""
    return FakeService()


class FakeNetwork:
    """Recording network double for the sandbox cell unit tests.

    Mirrors the testcontainers ``Network`` surface the sandbox drives — construction with the
    labels keyword, ``create``, ``remove`` — without touching the daemon.

    Attributes:
        docker_network_kw: The network-creation keywords recorded from the constructor call.
    """

    created: ClassVar[list["FakeNetwork"]] = []
    removed: ClassVar[list["FakeNetwork"]] = []

    def __init__(self, docker_client_kw: dict | None = None, docker_network_kw: dict | None = None) -> None:
        """Initialize the recording network of one constructor call.

        Args:
            docker_client_kw: Unused by the double — accepted for signature parity.
            docker_network_kw: The network-creation keywords recorded for assertions.
        """
        self.docker_network_kw = docker_network_kw or {}

    def create(self) -> "FakeNetwork":
        """Record the creation; the double stays inert."""
        FakeNetwork.created.append(self)

        return self

    def remove(self) -> None:
        """Record the removal; the double stays inert."""
        FakeNetwork.removed.append(self)
