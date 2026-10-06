"""Contract and logic tests for the ``check_runtime`` and ``build_engine`` routines."""

import inspect

import docker
import pytest
import requests
from goga_tool_pybuggy.sandbox.config import InstanceConfig
from goga_tool_pybuggy.sandbox.engines import (
    BaseEngine,
    EngineError,
    HttpEngine,
    KafkaEngine,
    PostgresEngine,
    VaultEngine,
    build_engine,
    check_runtime,
)
from goga_tool_pybuggy.sandbox.engines import runtime as runtime_module


class TestRuntimeContract:
    """Declared API of the ``check_runtime`` and ``build_engine`` routines."""

    def test_check_runtime_is_importable_from_engines_facade(self):
        """``check_runtime`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert callable(check_runtime)

    def test_build_engine_is_importable_from_engines_facade(self):
        """``build_engine`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert callable(build_engine)

    def test_check_runtime_takes_no_arguments(self):
        """``check_runtime`` probes with no parameters."""
        assert list(inspect.signature(check_runtime).parameters) == []

    def test_build_engine_signature_takes_the_instance_config(self):
        """``build_engine`` takes the instance declaration as its single parameter."""
        parameters = list(inspect.signature(build_engine).parameters)

        assert parameters == ["config"]

    @pytest.mark.parametrize(
        ("kind", "engine_class"),
        [
            ("postgresql", PostgresEngine),
            ("kafka", KafkaEngine),
            ("vault", VaultEngine),
            ("http", HttpEngine),
        ],
    )
    def test_build_engine_returns_the_kind_engine(self, kind: str, engine_class: type[BaseEngine]):
        """Every supported kind maps onto its engine, a ``BaseEngine`` subclass."""
        engine = build_engine(InstanceConfig(name="x", kind=kind, image=None))

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


class TestBuildEngine:
    """Behavior of the kind → engine factory."""

    def test_build_engine_fails_unmapped_kind(self):
        """A fabricated unmapped kind fails listing the supported kinds (loader bypassed)."""
        config = InstanceConfig(name="x", kind="grpc", image=None)

        with pytest.raises(EngineError, match=r"postgresql.*kafka.*vault.*http"):
            build_engine(config)

    def test_build_engine_carries_the_instance_declaration(self):
        """The engine keeps the declaration — the name and the image override reach it."""
        override = build_engine(InstanceConfig(name="db", kind="postgresql", image="postgres:17-alpine"))
        pinned = build_engine(InstanceConfig(name="events", kind="kafka", image=None))

        assert override.config.name == "db"
        assert override.config.image == "postgres:17-alpine"
        assert pinned.config.name == "events"
        assert pinned.config.image is None
