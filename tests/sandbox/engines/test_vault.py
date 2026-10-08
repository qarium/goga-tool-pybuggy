"""Contract and logic tests for the ``VaultEngine`` entity."""

import inspect
import logging
import time

import pytest
import requests
from goga_tool_pybuggy.sandbox.config import ProbeConfig, ServiceConfig
from goga_tool_pybuggy.sandbox.engines import (
    BaseEngine,
    DataOperation,
    EngineError,
    HttpEngine,
    VaultEngine,
)
from goga_tool_pybuggy.sandbox.engines import base as base_module
from goga_tool_pybuggy.sandbox.engines import http as http_module
from goga_tool_pybuggy.sandbox.engines import vault as vault_module

from ..conftest import requires_docker


def secrets_engine(image: str | None = None, probe: ProbeConfig | None = None) -> VaultEngine:
    """Build a vault engine of the sample ``secrets`` service.

    Args:
        image: The optional image override of the service declaration.
        probe: The optional readiness declaration of the service entry.

    Returns:
        The engine of a service named ``secrets`` of kind ``vault``.
    """
    return VaultEngine(ServiceConfig(name="secrets", kind="vault", image=image, probe=probe))


def put_op(path: str, data: dict[str, object]) -> DataOperation:
    """Build one vault put operation.

    Args:
        path: The secret path the write targets.
        data: The secret payload written at the path.

    Returns:
        A sample ``put`` operation targeted at the ``secrets`` service.
    """
    return DataOperation(instance="secrets", kind="vault", action="put", payload={"path": path, "data": data})


class FakeResponse:
    """Response double carrying a status and a JSON body."""

    def __init__(self, status_code: int, body: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self.body = body if body is not None else {}

    def json(self) -> dict[str, object]:
        return self.body


class FakeRequests:
    """Namespace double of ``requests`` recording probes and writes, serving scripted responses."""

    RequestException = requests.RequestException

    def __init__(
        self,
        statuses: list[int] | None = None,
        write_responses: list[FakeResponse] | None = None,
    ) -> None:
        self.statuses = list(statuses or [])
        self.write_responses = list(write_responses or [])
        self.probes: list[tuple[str, int | None]] = []
        self.writes: list[tuple[str, dict[str, str] | None, object, int | None]] = []

    def get(self, url: str, timeout: int | None = None) -> FakeResponse:
        self.probes.append((url, timeout))
        status = self.statuses.pop(0) if self.statuses else 200

        return FakeResponse(status)

    def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: object = None,
        timeout: int | None = None,
    ) -> FakeResponse:
        self.writes.append((url, headers, json, timeout))

        if self.write_responses:
            return self.write_responses.pop(0)

        return FakeResponse(200, {"request_id": "fake"})


class FakeClock:
    """Clock double of the probe loop — instant monotonic, sleeps advance the clock."""

    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def install_fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Patch the probe-loop clock of the engines base — no wall-clock waiting in unit tests.

    Args:
        monkeypatch: The pytest monkeypatch fixture swapping the base seams.

    Returns:
        The installed clock double recording the interval sleeps.
    """
    clock = FakeClock()
    monkeypatch.setattr(base_module, "monotonic", clock.monotonic)
    monkeypatch.setattr(base_module, "sleep", clock.sleep)

    return clock


class FakeWrappedContainer:
    """Double of the docker SDK container object recording restarts."""

    def __init__(self) -> None:
        self.restarts: list[int | None] = []

    def restart(self, timeout: int = 10) -> None:
        self.restarts.append(timeout)


class FakeDockerContainer:
    """Container double recording the build configuration and the mapped address."""

    def __init__(self, image: str, **kwargs: object) -> "FakeDockerContainer":
        self.image = image
        self.kwargs = kwargs
        self.exposed_ports: list[int] = []
        self.bind_ports: list[tuple[int, int | None]] = []
        self.env: dict[str, str] = {}
        self.command: str | list[str] | None = None
        self.network: object | None = None
        self.network_aliases: list[str] = []
        self.wrapped = FakeWrappedContainer()
        self.stops = 0
        self.starts = 0

    def with_network(self, network: object) -> "FakeDockerContainer":
        self.network = network

        return self

    def with_network_aliases(self, *aliases: str) -> "FakeDockerContainer":
        self.network_aliases.extend(aliases)

        return self

    def start(self) -> "FakeDockerContainer":
        self.starts += 1

        return self

    def with_exposed_ports(self, *ports: int) -> "FakeDockerContainer":
        self.exposed_ports.extend(ports)

        return self

    def with_bind_ports(self, container: int, host: int | None = None) -> "FakeDockerContainer":
        self.bind_ports.append((container, host))

        return self

    def with_env(self, key: str, value: str) -> "FakeDockerContainer":
        self.env[key] = value

        return self

    def with_command(self, command: str | list[str]) -> "FakeDockerContainer":
        self.command = command

        return self

    def get_container_host_ip(self) -> str:
        return "127.0.0.2"

    def get_exposed_port(self, port: int) -> str:
        return {8200: "18200"}.get(port, str(port))

    def get_wrapped_container(self) -> FakeWrappedContainer:
        return self.wrapped

    def stop(self) -> None:
        self.stops += 1


def armed_engine(monkeypatch: pytest.MonkeyPatch, fake_requests: FakeRequests) -> VaultEngine:
    """Build a vault engine whose container and requests seams are faked.

    Args:
        monkeypatch: The pytest monkeypatch fixture swapping the module seams.
        fake_requests: The recording requests double serving the probes and writes.

    Returns:
        A vault engine driven entirely over the fakes — no daemon, no network.
    """
    monkeypatch.setattr(vault_module, "DockerContainer", FakeDockerContainer)
    monkeypatch.setattr(vault_module, "requests", fake_requests)
    monkeypatch.setattr(vault_module, "reserve_port", lambda: 18200)
    install_fake_clock(monkeypatch)

    return secrets_engine()


class TestVaultEngineContract:
    """Declared API of the ``VaultEngine`` entity."""

    def test_vault_engine_is_importable_from_engines_facade(self):
        """``VaultEngine`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert VaultEngine is not None

    def test_vault_engine_subclasses_base_engine(self):
        """The kind engine inherits the base contract."""
        assert issubclass(VaultEngine, BaseEngine)

    def test_vault_engine_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config)`` over ``ServiceConfig``."""
        signature = inspect.signature(VaultEngine.__init__)

        assert list(signature.parameters) == ["self", "config"]
        assert signature.parameters["config"].annotation is ServiceConfig

    def test_vault_engine_constructs_over_a_service_config(self):
        """The engine carries the service declaration — name, kind, image override, probe."""
        probe = ProbeConfig(timeout=45.0, interval=1.0)
        engine = VaultEngine(ServiceConfig(name="secrets", kind="vault", probe=probe))

        assert engine.config.name == "secrets"
        assert engine.config.kind == "vault"
        assert engine.config.probe is probe

    def test_vault_engine_inherits_the_contract_methods(self):
        """``start`` / ``apply`` / ``record`` / ``reset`` / ``stop`` resolve with declared parameters."""
        expected = {
            "start": ["self", "startup", "network"],
            "apply": ["self", "operations"],
            "record": ["self", "operations"],
            "reset": ["self"],
            "stop": ["self"],
        }

        for method, parameters in expected.items():
            assert list(inspect.signature(getattr(VaultEngine, method)).parameters) == parameters

    def test_vault_engine_inherits_the_address_property(self):
        """The ``address`` property of the base resolves on the kind engine."""
        address = inspect.getattr_static(VaultEngine, "address")

        assert isinstance(address, property)

    def test_vault_engine_declares_the_engine_owned_readiness_wait(self):
        """The kind engine overrides ``_wait_ready`` — readiness probing is engine-owned."""
        assert VaultEngine._wait_ready is not BaseEngine._wait_ready


class TestVaultEngineBuild:
    """Container build arguments of the vault engine, driven through the patched constructor."""

    def test_build_uses_the_pinned_image_labels_and_the_fixed_port(self, monkeypatch: pytest.MonkeyPatch):
        """Without an image override the build uses the pinned image, labels, fixed bound port."""
        monkeypatch.setattr(vault_module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(vault_module, "reserve_port", lambda: 18200)
        engine = secrets_engine()

        container = engine._build_container()

        assert container.image == "hashicorp/vault:1.17"
        assert container.kwargs["labels"] == {"pybuggy-sandbox": "true"}
        assert container.exposed_ports == []
        assert container.bind_ports == [(8200, 18200)]

    def test_build_honors_the_image_override(self, monkeypatch: pytest.MonkeyPatch):
        """The image override of the service declaration reaches the container build."""
        monkeypatch.setattr(vault_module, "DockerContainer", FakeDockerContainer)
        engine = secrets_engine(image="hashicorp/vault:1.18")

        container = engine._build_container()

        assert container.image == "hashicorp/vault:1.18"

    def test_build_pins_the_dev_mode_environment_and_command(self, monkeypatch: pytest.MonkeyPatch):
        """The dev-mode contract reaches the container — fixed root token, listen address, command."""
        monkeypatch.setattr(vault_module, "DockerContainer", FakeDockerContainer)
        engine = secrets_engine()

        container = engine._build_container()

        assert container.env == {
            "VAULT_DEV_ROOT_TOKEN_ID": "sandbox-root",
            "VAULT_DEV_LISTEN_ADDRESS": "0.0.0.0:8200",
        }
        assert container.command == "server -dev"


class TestVaultEngineReadiness:
    """Health probing of the vault engine, driven over the fake requests namespace."""

    def test_wait_ready_probes_health_until_success(self, monkeypatch: pytest.MonkeyPatch):
        """The probe polls the mapped health endpoint on the declared interval."""
        fake_requests = FakeRequests(statuses=[503, 429])
        monkeypatch.setattr(vault_module, "requests", fake_requests)
        clock = install_fake_clock(monkeypatch)
        engine = secrets_engine()
        engine._container = FakeDockerContainer("hashicorp/vault:1.17")

        engine._wait_ready()

        assert fake_requests.probes == [("http://127.0.0.2:18200/v1/sys/health", 5)] * 3
        assert clock.slept == [0.5, 0.5]

    def test_wait_ready_fails_past_the_declared_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """A health endpoint that never answers fails when the declared deadline expires."""
        fake_requests = FakeRequests(statuses=[503] * 8)
        monkeypatch.setattr(vault_module, "requests", fake_requests)
        clock = install_fake_clock(monkeypatch)
        engine = secrets_engine(probe=ProbeConfig(timeout=0.2, interval=0.05))
        engine._container = FakeDockerContainer("hashicorp/vault:1.17")

        with pytest.raises(RuntimeError, match=r"health endpoint .*did not succeed within 0\.2s"):
            engine._wait_ready()

        assert clock.slept == [0.05] * len(clock.slept)
        assert len(clock.slept) >= 4
        assert fake_requests.probes[0] == ("http://127.0.0.2:18200/v1/sys/health", 5)


class TestVaultEnginePlane:
    """KV v2 plane, execution and wipe of the vault engine, driven over the fakes."""

    def test_execute_put_posts_the_kv2_write_with_the_token_header(self, monkeypatch: pytest.MonkeyPatch):
        """A ``put`` posts the KV v2 body with the token header against the mapped address."""
        fake_requests = FakeRequests()
        monkeypatch.setattr(vault_module, "requests", fake_requests)
        engine = secrets_engine()
        engine._container = FakeDockerContainer("hashicorp/vault:1.17")

        engine._execute(put_op("payment/api-key", {"api_key": "test-key", "ttl": "1h"}))

        assert fake_requests.writes == [
            (
                "http://127.0.0.2:18200/v1/secret/data/payment/api-key",
                {"X-Vault-Token": "sandbox-root"},
                {"data": {"api_key": "test-key", "ttl": "1h"}},
                5,
            ),
        ]

    def test_execute_failed_write_names_the_path_and_status(self, monkeypatch: pytest.MonkeyPatch):
        """A rejected write surfaces as a readable error naming the path and the status."""
        fake_requests = FakeRequests(write_responses=[FakeResponse(400, {"errors": ["permission denied"]})])
        monkeypatch.setattr(vault_module, "requests", fake_requests)
        engine = secrets_engine()
        engine._container = FakeDockerContainer("hashicorp/vault:1.17")

        with pytest.raises(RuntimeError, match=r"payment/api-key.*400.*permission denied"):
            engine._execute(put_op("payment/api-key", {"api_key": "test-key"}))

    def test_execute_failed_write_wraps_into_engine_error_through_apply(self, monkeypatch: pytest.MonkeyPatch):
        """Through the base apply path the failed write names the service and the action."""
        fake_requests = FakeRequests(write_responses=[FakeResponse(403, {"errors": ["forbidden"]})])
        monkeypatch.setattr(vault_module, "requests", fake_requests)
        engine = secrets_engine()
        engine._container = FakeDockerContainer("hashicorp/vault:1.17")
        engine._started = True

        with pytest.raises(EngineError, match=r"service 'secrets': put failed.*x/y"):
            engine.apply([put_op("x/y", {"v": 1})])

    def test_wipe_restarts_the_same_container_and_rewaits_health(self, monkeypatch: pytest.MonkeyPatch):
        """Reset-wipe restarts the wrapped SDK container and re-probes the health endpoint."""
        fake_requests = FakeRequests()
        monkeypatch.setattr(vault_module, "requests", fake_requests)
        install_fake_clock(monkeypatch)
        engine = secrets_engine()
        engine._container = FakeDockerContainer("hashicorp/vault:1.17")

        address_before = engine.address
        engine._wipe()

        assert engine._container.wrapped.restarts == [10]
        assert fake_requests.probes == [("http://127.0.0.2:18200/v1/sys/health", 5)]
        assert fake_requests.writes == []
        assert engine.address == address_before

    def test_close_plane_is_a_noop_and_safe_twice(self):
        """Stop needs no plane close — requests is stateless; a second close touches nothing."""
        engine = secrets_engine()

        engine._close_plane()
        engine._close_plane()


class TestVaultEngineLifecycle:
    """Full lifecycle of the vault engine over the fakes — start, journal, reset, stop."""

    def test_start_applies_startup_puts_and_journals_them(self, monkeypatch: pytest.MonkeyPatch):
        """Startup puts execute in order and join the journal as the initial baseline."""
        fake_requests = FakeRequests()
        engine = armed_engine(monkeypatch, fake_requests)

        engine.start([put_op("payment/api-key", {"api_key": "test-key"}), put_op("x/y", {"v": 1})])

        try:
            container = engine._container
            assert container is not None
            assert container.starts == 1
            assert fake_requests.probes == [("http://127.0.0.2:18200/v1/sys/health", 5)]
            assert [write[0] for write in fake_requests.writes] == [
                "http://127.0.0.2:18200/v1/secret/data/payment/api-key",
                "http://127.0.0.2:18200/v1/secret/data/x/y",
            ]
            assert [write[2] for write in fake_requests.writes] == [
                {"data": {"api_key": "test-key"}},
                {"data": {"v": 1}},
            ]
            assert engine._journal == [put_op("payment/api-key", {"api_key": "test-key"}), put_op("x/y", {"v": 1})]
        finally:
            engine.stop()

        assert engine._container is None

    def test_reset_replays_the_journal_after_the_restart(self, monkeypatch: pytest.MonkeyPatch):
        """Reset restarts the container empty and replays the journaled baseline writes."""
        fake_requests = FakeRequests()
        engine = armed_engine(monkeypatch, fake_requests)
        engine._container = FakeDockerContainer("hashicorp/vault:1.17")
        engine._started = True
        engine._journal = [put_op("a/b", {"v": 1}), put_op("c/d", {"v": 2})]

        engine.reset()

        assert engine._container.wrapped.restarts == [10]
        assert [write[0] for write in fake_requests.writes] == [
            "http://127.0.0.2:18200/v1/secret/data/a/b",
            "http://127.0.0.2:18200/v1/secret/data/c/d",
        ]

    def test_stop_is_safe_twice(self, monkeypatch: pytest.MonkeyPatch):
        """A second stop touches nothing — the container is removed exactly once."""
        fake_requests = FakeRequests()
        engine = armed_engine(monkeypatch, fake_requests)
        engine.start([])

        container = engine._container
        engine.stop()
        engine.stop()

        assert container is not None
        assert container.stops == 1

    def test_engine_never_logs_the_dev_token(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
        """The fixed dev token never reaches any log message or contextual value."""
        caplog.set_level(logging.DEBUG, logger=vault_module.__name__)
        engine = armed_engine(monkeypatch, FakeRequests())

        with caplog.at_level(logging.DEBUG, logger=vault_module.__name__):
            engine.start([put_op("payment/api-key", {"api_key": "test-key"})])

            try:
                engine.apply([put_op("x/y", {"v": 1})])
                engine.reset()
            finally:
                engine.stop()

        assert caplog.records

        for record in caplog.records:
            assert "sandbox-root" not in record.getMessage()

            for value in record.__dict__.values():
                assert "sandbox-root" not in str(value)


class TestDeclaredBoundsReadiness:
    """Scenario 22: the declared probe bounds drive both HTTP-plane readiness waits."""

    def test_vault_and_http_wait_use_declared_bounds(self, monkeypatch: pytest.MonkeyPatch):
        """An expired declared deadline fails both kinds within the wall-clock deadline.

        With a patched ``requests.get`` answering failures and probe ``{timeout: 0.3,
        interval: 0.05}``, both waits expire as ``EngineError`` naming the endpoint within
        ~0.3s of wall clock; with no probe declared the loop bounds equal the former
        constants (30.0 / 0.5) — the default-equivalence regression.
        """
        monkeypatch.setattr(vault_module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(vault_module, "reserve_port", lambda: 18200)
        monkeypatch.setattr(http_module, "DockerContainer", FakeDockerContainer)
        failing_requests = FakeRequests(statuses=[500] * 64)
        monkeypatch.setattr(vault_module, "requests", failing_requests)
        monkeypatch.setattr(http_module, "requests", failing_requests)
        probe = ProbeConfig(timeout=0.3, interval=0.05)

        vault_started = time.monotonic()

        with pytest.raises(EngineError, match=r"service 'secrets'.*health endpoint .*did not succeed within 0\.3s"):
            secrets_engine(probe=probe).start([])

        vault_elapsed = time.monotonic() - vault_started

        http_started = time.monotonic()

        with pytest.raises(EngineError, match=r"service 'payments'.*admin endpoint .*did not succeed within 0\.3s"):
            HttpEngine(ServiceConfig(name="payments", kind="http", probe=probe)).start([])

        http_elapsed = time.monotonic() - http_started

        assert 0.25 <= vault_elapsed <= 2.0
        assert 0.25 <= http_elapsed <= 2.0
        assert not hasattr(vault_module, "READINESS_TIMEOUT")
        assert not hasattr(vault_module, "READINESS_INTERVAL")
        assert not hasattr(http_module, "READINESS_TIMEOUT")
        assert not hasattr(http_module, "READINESS_INTERVAL")
        assert secrets_engine()._readiness_bounds == (30.0, 0.5)
        assert HttpEngine(ServiceConfig(name="payments", kind="http"))._readiness_bounds == (30.0, 0.5)


@requires_docker
class TestVaultEngineContainer:
    """Live behavior of the vault engine against a real container (docker-gated)."""

    @staticmethod
    def _get(url: str, headers: dict[str, str]) -> requests.Response:
        """GET until any answer arrives — the first connections after a restart may reset.

        A container restart can leave the docker host's port proxy resetting connections
        for a moment; a readiness loop absorbs it, a single request does not.

        Args:
            url: The vault API URL to request.

        Returns:
            The first response the endpoint answers with.

        Raises:
            requests.RequestException: The endpoint answered nothing within the deadline.
        """
        deadline = time.monotonic() + 10.0

        while True:
            try:
                return requests.get(url, headers=headers, timeout=5)
            except requests.RequestException:
                if time.monotonic() >= deadline:
                    raise

                time.sleep(0.5)

    def test_vault_engine_put_and_restart_reset(self):
        """Reset restarts the container: test writes gone, baseline replayed, address stable."""
        engine = secrets_engine()
        engine.start([])

        try:
            address_before = engine.address
            engine.record([put_op("payment/api-key", {"api_key": "test-key"})])
            engine.apply([put_op("x/y", {"v": 1})])

            engine.reset()

            assert engine.address == address_before
            base = f"http://{engine.address.host}:{engine.address.port}"
            headers = {"X-Vault-Token": vault_module.DEV_ROOT_TOKEN}

            test_write = self._get(f"{base}/v1/secret/data/x/y", headers)
            assert test_write.status_code == 404

            baseline_secret = self._get(f"{base}/v1/secret/data/payment/api-key", headers)
            assert baseline_secret.status_code == 200
            assert baseline_secret.json()["data"]["data"] == {"api_key": "test-key"}
        finally:
            engine.stop()

        engine.stop()
