"""Contract and logic tests for the ``check_runtime``, ``normalize_container_host`` and ``build_engine`` routines."""

import inspect
import os
import types

import docker
import pytest
import requests
from goga_tool_pybuggy.sandbox.config import ProbeConfig, ServiceConfig, TopicConfig
from goga_tool_pybuggy.sandbox.engines import (
    BaseEngine,
    EngineError,
    HttpEngine,
    KafkaEngine,
    PostgresEngine,
    RedisEngine,
    VaultEngine,
    build_engine,
    check_runtime,
    normalize_container_host,
)
from goga_tool_pybuggy.sandbox.engines import runtime as runtime_module


class TestRuntimeContract:
    """Declared API of the ``check_runtime``, ``normalize_container_host`` and ``build_engine`` routines."""

    def test_check_runtime_is_importable_from_engines_facade(self):
        """``check_runtime`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert callable(check_runtime)

    def test_normalize_container_host_is_importable_from_engines_facade(self):
        """``normalize_container_host`` is re-exported by the engines facade."""
        assert callable(normalize_container_host)

    def test_build_engine_is_importable_from_engines_facade(self):
        """``build_engine`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert callable(build_engine)

    def test_check_runtime_takes_no_arguments(self):
        """``check_runtime`` probes with no parameters."""
        assert list(inspect.signature(check_runtime).parameters) == []

    def test_normalize_container_host_takes_no_arguments(self):
        """``normalize_container_host`` resolves the topology with no parameters."""
        assert list(inspect.signature(normalize_container_host).parameters) == []

    def test_build_engine_signature_takes_the_service_config(self):
        """``build_engine`` takes the service declaration as its single parameter."""
        signature = inspect.signature(build_engine)

        assert list(signature.parameters) == ["config"]
        assert signature.parameters["config"].annotation is ServiceConfig
        assert signature.return_annotation is BaseEngine

    @pytest.mark.parametrize(
        ("kind", "engine_class"),
        [
            ("postgresql", PostgresEngine),
            ("kafka", KafkaEngine),
            ("vault", VaultEngine),
            ("http", HttpEngine),
            ("redis", RedisEngine),
        ],
    )
    def test_build_engine_returns_the_kind_engine(self, kind: str, engine_class: type[BaseEngine]):
        """Every supported kind maps onto its engine, a ``BaseEngine`` subclass."""
        engine = build_engine(ServiceConfig(name="x", kind=kind))

        assert isinstance(engine, engine_class)
        assert isinstance(engine, BaseEngine)


class TestCheckRuntime:
    """Behavior of the pre-start daemon probe."""

    def test_check_runtime_succeeds_on_answering_daemon(self, monkeypatch: pytest.MonkeyPatch):
        """An answering daemon passes the probe — one ping, nothing started, no raise."""
        pings: list[int] = []

        class FakeClientFactory:
            """Docker client factory double whose ping answers without a daemon."""

            def __init__(self) -> None:
                self.client = self

            def ping(self) -> bool:
                pings.append(1)

                return True

        monkeypatch.setattr(runtime_module, "DockerClient", FakeClientFactory)

        assert check_runtime() is None
        assert pings == [1]

    def test_check_runtime_fails_actionable_without_daemon(self, monkeypatch: pytest.MonkeyPatch):
        """An unreachable daemon fails immediately with the actionable requirement message."""

        def unreachable() -> object:
            raise docker.errors.DockerException("Error while fetching server API version")

        monkeypatch.setattr(runtime_module, "DockerClient", unreachable)

        with pytest.raises(RuntimeError, match="docker-compatible container runtime"):
            check_runtime()

    def test_check_runtime_fails_on_ping_transport_error(self, monkeypatch: pytest.MonkeyPatch):
        """A transport-level ping failure maps onto the same actionable error."""

        def broken_factory() -> object:
            raise requests.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(runtime_module, "DockerClient", broken_factory)

        with pytest.raises(RuntimeError, match="docker-compatible container runtime"):
            check_runtime()


class TestNormalizeContainerHost:
    """Behavior of the container-host override defaulting — one address space per topology."""

    @pytest.fixture(autouse=True)
    def fresh_config_singleton(self, monkeypatch: pytest.MonkeyPatch):
        """Isolate the testcontainers config singleton the routine patches."""
        self.config = types.SimpleNamespace(tc_host_override=None)
        monkeypatch.setattr(runtime_module, "testcontainers_config", self.config)

    def test_explicit_override_wins_and_detection_never_runs(self, monkeypatch: pytest.MonkeyPatch):
        """An explicit override is kept as-is, no detection runs, and the frozen-empty
        testcontainers singleton is repaired to the explicit value."""
        monkeypatch.setenv(runtime_module.CONTAINER_HOST_OVERRIDE, "10.9.8.7")

        def unexpected() -> str:
            raise AssertionError("detection must not run when the override is explicit")

        monkeypatch.setattr(runtime_module, "_routable_host_ip", unexpected)

        normalize_container_host()

        assert os.environ[runtime_module.CONTAINER_HOST_OVERRIDE] == "10.9.8.7"
        assert self.config.tc_host_override == "10.9.8.7"

    def test_container_marker_defaults_to_host_docker_internal(self, monkeypatch: pytest.MonkeyPatch):
        """A runner inside a container (/.dockerenv) defaults to the Docker Desktop name —
        in the environment and in the already-frozen testcontainers singleton."""
        monkeypatch.delenv(runtime_module.CONTAINER_HOST_OVERRIDE, raising=False)
        monkeypatch.setattr(runtime_module, "_DOCKER_ENV_MARKER", types.SimpleNamespace(exists=lambda: True))

        normalize_container_host()

        assert os.environ[runtime_module.CONTAINER_HOST_OVERRIDE] == "host.docker.internal"
        assert self.config.tc_host_override == "host.docker.internal"

    def test_host_run_defaults_to_the_routable_host_ip(self, monkeypatch: pytest.MonkeyPatch):
        """A host run defaults the override to the host's own routable IP."""
        monkeypatch.delenv(runtime_module.CONTAINER_HOST_OVERRIDE, raising=False)
        monkeypatch.setattr(runtime_module, "_DOCKER_ENV_MARKER", types.SimpleNamespace(exists=lambda: False))
        monkeypatch.setattr(runtime_module, "_routable_host_ip", lambda: "192.168.1.115")

        normalize_container_host()

        assert os.environ[runtime_module.CONTAINER_HOST_OVERRIDE] == "192.168.1.115"
        assert self.config.tc_host_override == "192.168.1.115"

    def test_failed_detection_changes_nothing(self, monkeypatch: pytest.MonkeyPatch):
        """A failed host-IP detection is a no-op — the mapped-localhost behavior stays."""
        monkeypatch.delenv(runtime_module.CONTAINER_HOST_OVERRIDE, raising=False)
        monkeypatch.setattr(runtime_module, "_DOCKER_ENV_MARKER", types.SimpleNamespace(exists=lambda: False))
        monkeypatch.setattr(runtime_module, "_routable_host_ip", lambda: "")

        normalize_container_host()

        assert runtime_module.CONTAINER_HOST_OVERRIDE not in os.environ
        assert self.config.tc_host_override is None

    def test_a_tc_host_frozen_singleton_stays_untouched(self, monkeypatch: pytest.MonkeyPatch):
        """A non-empty tc_host_override (an explicit TC_HOST frozen at import) wins for
        testcontainers; the routine only still defaults the environment variable."""
        monkeypatch.delenv(runtime_module.CONTAINER_HOST_OVERRIDE, raising=False)
        monkeypatch.setattr(runtime_module, "_DOCKER_ENV_MARKER", types.SimpleNamespace(exists=lambda: False))
        monkeypatch.setattr(runtime_module, "_routable_host_ip", lambda: "192.168.1.115")
        self.config.tc_host_override = "tc-explicit"

        normalize_container_host()

        assert os.environ[runtime_module.CONTAINER_HOST_OVERRIDE] == "192.168.1.115"
        assert self.config.tc_host_override == "tc-explicit"

    def test_routable_host_ip_answers_without_raising(self):
        """The routing-table probe returns a string — an address or an empty string."""
        assert isinstance(runtime_module._routable_host_ip(), str)


class TestBuildEngine:
    """Behavior of the kind → engine factory."""

    def test_build_engine_fails_unmapped_kind(self):
        """A fabricated unmapped kind fails listing the supported kinds (loader bypassed)."""
        config = ServiceConfig(name="x", kind="grpc")

        with pytest.raises(
            EngineError,
            match=r"service 'x': kind 'grpc' has no engine.*postgresql.*kafka.*vault.*http.*redis",
        ):
            build_engine(config)

    def test_build_engine_carries_the_service_declaration(self):
        """The engine keeps the declaration — name, image override, topics, probe and the
        redis password/db reach it."""
        override = build_engine(ServiceConfig(name="db", kind="postgresql", image="postgres:17-alpine"))
        events = build_engine(
            ServiceConfig(
                name="events",
                kind="kafka",
                topics=[TopicConfig(name="orders.events", partitions=6)],
                probe=ProbeConfig(timeout=45.0, interval=1.0),
            ),
        )
        cache = build_engine(ServiceConfig(name="cache", kind="redis", password="sandbox-redis", db=7))

        assert override.config.name == "db"
        assert override.config.image == "postgres:17-alpine"
        assert events.config.name == "events"
        assert events.config.image is None
        assert [topic.name for topic in events.config.topics] == ["orders.events"]
        assert events.config.probe is not None
        assert events.config.probe.timeout == 45.0
        assert events.config.probe.interval == 1.0
        assert isinstance(cache, RedisEngine)
        assert cache.config.name == "cache"
        assert cache.config.password == "sandbox-redis"
        assert cache.config.db == 7
