"""Contract and logic tests for the ``RedisEngine`` entity."""

import inspect

import pytest
import redis
from goga_tool_pybuggy.sandbox import engines as engines_facade
from goga_tool_pybuggy.sandbox.config import ProbeConfig, ServiceConfig
from goga_tool_pybuggy.sandbox.engines import BaseEngine, DataOperation, EngineError, RedisEngine
from goga_tool_pybuggy.sandbox.engines import redis as redis_module
from testcontainers.community.redis import PingWaitStrategy

from .test_http import install_fake_clock


def cache_engine(
    image: str | None = None,
    probe: ProbeConfig | None = None,
    password: str | None = None,
    db: int = 0,
) -> RedisEngine:
    """Build a redis engine of the sample ``cache`` service.

    Args:
        image: The optional image override of the service declaration.
        probe: The optional readiness declaration of the service entry.
        password: The optional redis auth password of the service declaration.
        db: The redis logical database index of the service declaration.

    Returns:
        The engine of a service named ``cache`` of kind ``redis``.
    """
    return RedisEngine(ServiceConfig(name="cache", kind="redis", image=image, probe=probe, password=password, db=db))


def redis_op(action: str, payload: dict[str, object]) -> DataOperation:
    """Build one redis operation of the sample ``cache`` service.

    Args:
        action: The redis action of the operation.
        payload: The declared payload of the operation.

    Returns:
        A sample operation targeted at the ``cache`` service.
    """
    return DataOperation(instance="cache", kind="redis", action=action, payload=payload)


class FakeRedisContainer:
    """Container double of the community redis module recording build and lifecycle calls.

    Mirrors the module contract the engine drives: the constructor publishes 6379, wires
    ``--requirepass`` for a truthy password, and installs the built-in ``PingWaitStrategy``;
    ``waiting_for`` overwrites the installed strategy — the replacement seam.

    Attributes:
        image: The image the constructor carried.
        kwargs: The further constructor keywords — password and labels among them.
        command: The ``--requirepass`` command a truthy password wired, else None.
        wait_strategy: The currently installed wait strategy.
        wait_strategies: Every strategy handed to ``waiting_for``, in call order.
        network: The sandbox network the container joined, else None.
        network_aliases: The aliases the container joined the network under.
        starts: The number of ``start`` calls.
        stops: The number of ``stop`` calls.
    """

    def __init__(self, image: str, port: int = 6379, password: str | None = None, **kwargs: object) -> None:
        """Record the module constructor call — image, port, password, the further keywords.

        Args:
            image: The image the engine built the container with.
            port: The in-container service port the module publishes.
            password: The declared redis password; truthy wires ``--requirepass``.
            **kwargs: The further constructor keywords — labels among them.
        """
        self.image = image
        self.port = port
        self.kwargs = dict(password=password, **kwargs)
        self.command: str | list[str] | None = f"redis-server --requirepass {password}" if password else None
        self.exposed_ports: list[int] = [port]
        self.wait_strategy: object = PingWaitStrategy()
        self.wait_strategies: list[object] = []
        self.network: object | None = None
        self.network_aliases: list[str] = []
        self.starts = 0
        self.stops = 0

    def waiting_for(self, strategy: object) -> "FakeRedisContainer":
        """Overwrite the installed wait strategy — the module replacement seam.

        Args:
            strategy: The strategy the engine installs after construction.

        Returns:
            The container itself, chainable like the core container.
        """
        self.wait_strategies.append(strategy)
        self.wait_strategy = strategy

        return self

    def with_network(self, network: object) -> "FakeRedisContainer":
        """Record the sandbox network join.

        Args:
            network: The sandbox network the container joins.

        Returns:
            The container itself, chainable like the core container.
        """
        self.network = network

        return self

    def with_network_aliases(self, *aliases: str) -> "FakeRedisContainer":
        """Record the network aliases.

        Args:
            *aliases: The aliases the container joins the network under.

        Returns:
            The container itself, chainable like the core container.
        """
        self.network_aliases.extend(aliases)

        return self

    def start(self) -> "FakeRedisContainer":
        """Count the container start."""
        self.starts += 1

        return self

    def stop(self) -> None:
        """Count the container stop."""
        self.stops += 1

    def get_container_host_ip(self) -> str:
        """The mapped host of the sample address."""
        return "127.0.0.2"

    def get_exposed_port(self, port: int) -> str:
        """The published host-side port of the sample address.

        Args:
            port: The in-container service port to resolve.
        """
        return {6379: "16379"}[port]


class FakeRedisClient:
    """Client double of the redis data plane — records commands, serves scripted outcomes.

    Every command records as ``(name, args, kwargs)``; a scripted error of the command name
    raises after the record. ``ping`` serves the shared outcome script — an exception class
    or instance raises, anything truthy or falsy returns.

    Attributes:
        commands: The executed commands, in call order.
        closed: The number of ``close`` calls.
    """

    def __init__(self, ping_outcomes: list[object] | None = None, errors: dict[str, Exception] | None = None) -> None:
        """Initialize the client double over its shared ping script and scripted errors.

        Args:
            ping_outcomes: The ping outcome script shared with the other probe clients.
            errors: The scripted error of each command name, raised when recorded.
        """
        self.ping_outcomes = ping_outcomes if ping_outcomes is not None else []
        self.errors = dict(errors or {})
        self.commands: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.closed = 0

    def ping(self) -> bool:
        """Serve one scripted ping outcome — the readiness and the binding condition."""
        self.commands.append(("ping", (), {}))

        if not self.ping_outcomes:
            return True

        outcome = self.ping_outcomes.pop(0)

        if isinstance(outcome, type) and issubclass(outcome, BaseException):
            raise outcome()

        if isinstance(outcome, BaseException):
            raise outcome

        return bool(outcome)

    def set(self, key: object, value: object) -> None:
        """Record one string value write."""
        self._record("set", (key, value))

    def hset(self, key: object, mapping: dict[str, object] | None = None) -> None:
        """Record one hash write."""
        self._record("hset", (key,), {"mapping": mapping})

    def rpush(self, key: object, *values: object) -> None:
        """Record one list tail append."""
        self._record("rpush", (key, *values))

    def sadd(self, key: object, *members: object) -> None:
        """Record one set members add."""
        self._record("sadd", (key, *members))

    def flushdb(self) -> None:
        """Record the database flush."""
        self._record("flushdb", ())

    def close(self) -> None:
        """Count the connection close."""
        self.closed += 1

    def _record(self, name: str, args: tuple[object, ...], kwargs: dict[str, object] | None = None) -> None:
        """Record one command, then serve its scripted error when present.

        Args:
            name: The command name.
            args: The positional command arguments.
            kwargs: The keyword command arguments.
        """
        self.commands.append((name, args, kwargs if kwargs is not None else {}))

        error = self.errors.get(name)

        if error is not None:
            raise error


class FakeRedisNamespace:
    """Namespace double of ``redis`` recording client constructions over a shared ping script.

    Carries the real ``redis.exceptions`` classes — the engine's catch clauses resolve against
    the same hierarchy under the patch — and hands out one recording client per
    ``Redis(...)`` construction; the readiness loop constructs one probe client per attempt.

    Attributes:
        constructions: The keyword arguments of every ``Redis(...)`` construction.
        clients: The handed-out client doubles, in construction order.
    """

    exceptions = redis.exceptions

    def __init__(self, ping_outcomes: list[object] | None = None) -> None:
        """Initialize the namespace over the ping script shared by its clients.

        Args:
            ping_outcomes: The ping outcome script the handed-out clients serve.
        """
        self.ping_outcomes = list(ping_outcomes or [])
        self.constructions: list[dict[str, object]] = []
        self.clients: list[FakeRedisClient] = []

    def Redis(self, **kwargs: object) -> FakeRedisClient:  # noqa: N802 — mirrors the redis API name
        """Record one client construction and hand out the next recording client double."""
        self.constructions.append(dict(kwargs))

        client = FakeRedisClient(ping_outcomes=self.ping_outcomes)
        self.clients.append(client)

        return client


def armed_engine(
    monkeypatch: pytest.MonkeyPatch,
    ping_outcomes: list[object] | None = None,
) -> tuple[RedisEngine, FakeRedisNamespace]:
    """Build a redis engine whose container and client seams are faked.

    Args:
        monkeypatch: The pytest monkeypatch fixture swapping the module seams.
        ping_outcomes: The scripted ping outcomes shared by the constructed clients.

    Returns:
        An engine driven entirely over the fakes — no daemon, no network — and the recording
        client namespace.
    """
    namespace = FakeRedisNamespace(ping_outcomes)

    monkeypatch.setattr(redis_module, "RedisContainer", FakeRedisContainer)
    monkeypatch.setattr(redis_module, "redis", namespace)
    install_fake_clock(monkeypatch)

    return cache_engine(), namespace


class TestRedisEngineContract:
    """Declared API of the ``RedisEngine`` entity."""

    def test_redis_engine_is_importable_and_subclasses_base(self):
        """The facade re-exports the engine; it inherits the base contract and owns readiness."""
        assert issubclass(RedisEngine, BaseEngine)
        assert "RedisEngine" in engines_facade.__all__
        assert list(inspect.signature(RedisEngine.__init__).parameters) == ["self", "config"]
        assert RedisEngine._wait_ready is not BaseEngine._wait_ready
        assert RedisEngine._container_port == 6379


class TestRedisEngineBuild:
    """Container build arguments of the redis engine, driven through the patched module container."""

    def test_build_uses_the_pinned_image_labels_and_port(self, monkeypatch: pytest.MonkeyPatch):
        """Without an image override the build uses the pinned image, labels, the service port."""
        monkeypatch.setattr(redis_module, "RedisContainer", FakeRedisContainer)
        engine = cache_engine()

        container = engine._build_container()

        assert container.image == "redis:8-alpine"
        assert container.kwargs["labels"] == {"pybuggy-sandbox": "true"}
        assert container.exposed_ports == [6379]
        assert container.network is None

    def test_build_honors_the_image_override(self, monkeypatch: pytest.MonkeyPatch):
        """The image override of the service declaration reaches the container build."""
        monkeypatch.setattr(redis_module, "RedisContainer", FakeRedisContainer)
        engine = cache_engine(image="redis:9-alpine")

        container = engine._build_container()

        assert container.image == "redis:9-alpine"

    def test_build_passes_the_password_to_the_module_container(self, monkeypatch: pytest.MonkeyPatch):
        """A declared password reaches the module constructor; an absent one starts unauthenticated."""
        monkeypatch.setattr(redis_module, "RedisContainer", FakeRedisContainer)

        authenticated = cache_engine(password="sandbox-redis")._build_container()
        assert authenticated.kwargs["password"] == "sandbox-redis"
        assert authenticated.command == "redis-server --requirepass sandbox-redis"

        unauthenticated = cache_engine()._build_container()
        assert unauthenticated.kwargs["password"] is None
        assert unauthenticated.command is None

    def test_build_replaces_the_builtin_wait_strategy(self, monkeypatch: pytest.MonkeyPatch):
        """The module's built-in PING wait gives way to the engine's no-op — readiness is owned."""
        monkeypatch.setattr(redis_module, "RedisContainer", FakeRedisContainer)
        engine = cache_engine()

        container = engine._build_container()

        assert len(container.wait_strategies) == 1
        assert isinstance(container.wait_strategies[-1], redis_module._NoWaitStrategy)
        assert container.wait_strategy is container.wait_strategies[-1]
        assert not isinstance(container.wait_strategy, PingWaitStrategy)

    def test_build_joins_the_sandbox_network_under_the_service_alias(self, monkeypatch: pytest.MonkeyPatch):
        """With a network set, the built container joins it under the service-name alias."""
        monkeypatch.setattr(redis_module, "RedisContainer", FakeRedisContainer)
        engine = cache_engine()
        network = object()
        engine._network = network

        container = engine._build_container()

        assert container.network is network
        assert container.network_aliases == ["cache"]


class TestRedisEngineReadiness:
    """PING probing of the redis engine, driven over the fake client namespace."""

    def test_wait_ready_probes_ping_until_success(self, monkeypatch: pytest.MonkeyPatch):
        """Refused connections keep one throwaway probe client per attempt until PING answers."""
        refused = redis.exceptions.ConnectionError("connection refused")
        namespace = FakeRedisNamespace(ping_outcomes=[refused, refused, True])
        monkeypatch.setattr(redis_module, "redis", namespace)
        clock = install_fake_clock(monkeypatch)
        engine = cache_engine(password="sandbox-redis")
        engine._container = FakeRedisContainer("redis:8-alpine")

        engine._wait_ready()

        assert [client.commands for client in namespace.clients] == [[("ping", (), {})]] * 3
        assert all(client.closed == 1 for client in namespace.clients)
        assert (
            namespace.constructions
            == [
                {
                    "host": "127.0.0.2",
                    "port": 16379,
                    "password": "sandbox-redis",
                    "socket_timeout": 2,
                    "connect_timeout": 2,
                }
            ]
            * 3
        )
        assert clock.slept == [0.5, 0.5]

    def test_wait_ready_fails_fast_on_authentication_error(self, monkeypatch: pytest.MonkeyPatch):
        """A wrong password escapes the retry loop immediately instead of probing to expiry."""
        rejected = redis.exceptions.AuthenticationError("invalid username-password pair")
        namespace = FakeRedisNamespace(ping_outcomes=[rejected])
        monkeypatch.setattr(redis_module, "redis", namespace)
        clock = install_fake_clock(monkeypatch)
        engine = cache_engine(password="wrong")
        engine._container = FakeRedisContainer("redis:8-alpine")

        with pytest.raises(RuntimeError, match=r"did not answer PING.*authentication failed"):
            engine._wait_ready()

        assert len(namespace.clients) == 1
        assert namespace.clients[0].commands == [("ping", (), {})]
        assert namespace.clients[0].closed == 1
        assert clock.slept == []

    def test_wait_ready_fails_past_the_declared_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """A service that never answers PING fails when the declared deadline expires."""
        refused = redis.exceptions.ConnectionError("connection refused")
        namespace = FakeRedisNamespace(ping_outcomes=[refused] * 100)
        monkeypatch.setattr(redis_module, "redis", namespace)
        clock = install_fake_clock(monkeypatch)
        engine = cache_engine(probe=ProbeConfig(timeout=0.2, interval=0.05))
        engine._container = FakeRedisContainer("redis:8-alpine")

        with pytest.raises(RuntimeError, match=r"did not answer PING.*within 0\.2s"):
            engine._wait_ready()

        assert clock.slept == [0.05] * len(clock.slept)
        assert len(clock.slept) >= 4


class TestRedisEnginePlane:
    """Session plane, execution and wipe of the redis engine, driven over the fakes."""

    def test_open_plane_connects_to_the_declared_database(self, monkeypatch: pytest.MonkeyPatch):
        """The session client opens one connection to the declared db and binds it with a PING."""
        namespace = FakeRedisNamespace()
        monkeypatch.setattr(redis_module, "redis", namespace)
        engine = cache_engine(password="p", db=3)
        engine._container = FakeRedisContainer("redis:8-alpine")

        engine._open_plane()

        assert namespace.constructions == [
            {
                "host": "127.0.0.2",
                "port": 16379,
                "db": 3,
                "password": "p",
                "socket_timeout": 5,
                "connect_timeout": 5,
            }
        ]
        assert "decode_responses" not in namespace.constructions[0]
        assert engine._client is namespace.clients[0]
        assert namespace.clients[0].commands == [("ping", (), {})]

    def test_execute_applies_the_four_operations_with_wire_serialization(self):
        """The four actions dispatch onto their redis commands with values in the wire form."""
        client = FakeRedisClient()
        engine = cache_engine()
        engine._client = client

        engine._execute(redis_op("set", {"key": "feature-flag/a", "value": {"on": True}}))
        engine._execute(redis_op("hset", {"key": "user:1", "values": {"name": "Ann", "plan": "pro"}}))
        engine._execute(redis_op("rpush", {"key": "queue:orders", "values": [{"id": 1}, "tail"]}))
        engine._execute(redis_op("sadd", {"key": "members:vip", "members": ["ann", 2]}))

        assert client.commands == [
            ("set", ("feature-flag/a", '{"on": true}'), {}),
            ("hset", ("user:1",), {"mapping": {"name": "Ann", "plan": "pro"}}),
            ("rpush", ("queue:orders", '{"id": 1}', "tail"), {}),
            ("sadd", ("members:vip", "ann", "2"), {}),
        ]

    def test_execute_skips_empty_values_members_and_mapping(self):
        """Empty values, members and field mappings execute nothing — the empty-rows precedent."""
        client = FakeRedisClient()
        engine = cache_engine()
        engine._client = client

        engine._execute(redis_op("rpush", {"key": "queue:orders", "values": []}))
        engine._execute(redis_op("sadd", {"key": "members:vip", "members": []}))
        engine._execute(redis_op("hset", {"key": "user:1", "values": {}}))

        assert client.commands == []

    def test_execute_unknown_action_names_the_operation(self):
        """An unknown action surfaces through apply as EngineError naming service and action."""
        engine = cache_engine()
        engine._started = True
        engine._client = FakeRedisClient()

        with pytest.raises(EngineError, match=r"service 'cache': zadd failed: unknown redis action 'zadd'"):
            engine.apply([redis_op("zadd", {"key": "k", "value": 1})])

    def test_execute_failure_wraps_into_engine_error_through_apply(self):
        """A failed command surfaces through apply as EngineError naming service, action, cause."""
        client = FakeRedisClient(errors={"set": redis.exceptions.ResponseError("OOM command not allowed")})
        engine = cache_engine()
        engine._started = True
        engine._client = client

        with pytest.raises(EngineError, match=r"service 'cache': set failed.*OOM"):
            engine.apply([redis_op("set", {"key": "k", "value": "v"})])

    def test_wipe_flushes_the_declared_database(self):
        """Reset-wipe is one FLUSHDB over the open session connection."""
        client = FakeRedisClient()
        engine = cache_engine(db=2)
        engine._client = client

        engine._wipe()

        assert client.commands == [("flushdb", (), {})]

    def test_close_plane_closes_the_client_once(self):
        """A second close touches nothing — the client reference clears with the first."""
        client = FakeRedisClient()
        engine = cache_engine()
        engine._client = client

        engine._close_plane()

        assert engine._client is None

        engine._close_plane()

        assert client.closed == 1

    @pytest.mark.parametrize(
        ("value", "wire"),
        [
            (5, "5"),
            (True, "true"),
            (None, "null"),
            (2.5, "2.5"),
        ],
    )
    def test_execute_serializes_plain_scalars_deterministically(self, value: object, wire: str):
        """Plain scalars take their JSON wire form — the deterministic replay basis."""
        client = FakeRedisClient()
        engine = cache_engine()
        engine._client = client

        engine._execute(redis_op("set", {"key": "k", "value": value}))

        assert client.commands == [("set", ("k", wire), {})]

    def test_execute_fails_readably_on_non_serializable_values(self):
        """A non-serializable value surfaces through apply as EngineError with the TypeError cause."""
        engine = cache_engine()
        engine._started = True
        engine._client = FakeRedisClient()

        with pytest.raises(EngineError, match=r"service 'cache': set failed") as failure:
            engine.apply([redis_op("set", {"key": "k", "value": object()})])

        assert isinstance(failure.value.__cause__, TypeError)


class TestRedisEngineLifecycle:
    """Full lifecycle of the redis engine over the fakes — start, journal, reset, stop."""

    def test_start_applies_startup_operations_and_journals_them(self, monkeypatch: pytest.MonkeyPatch):
        """Startup operations execute in order over the session client and join the journal."""
        engine, namespace = armed_engine(monkeypatch)
        set_op = redis_op("set", {"key": "feature-flag/a", "value": "enabled"})
        hset_op = redis_op("hset", {"key": "user:1", "values": {"name": "Ann"}})

        engine.start([set_op, hset_op])

        try:
            container = engine._container
            session = namespace.clients[-1]
            assert container is not None
            assert container.starts == 1
            assert [command for command in session.commands if command[0] != "ping"] == [
                ("set", ("feature-flag/a", "enabled"), {}),
                ("hset", ("user:1",), {"mapping": {"name": "Ann"}}),
            ]
            assert engine._journal == [set_op, hset_op]
        finally:
            engine.stop()

        assert engine._container is None
        assert container.stops == 1
        assert session.closed == 1

    def test_reset_flushes_then_replays_the_journal(self, monkeypatch: pytest.MonkeyPatch):
        """Reset flushes the declared database and replays the journal without a restart."""
        engine, _ = armed_engine(monkeypatch)
        container = FakeRedisContainer("redis:8-alpine")
        client = FakeRedisClient()
        engine._container = container
        engine._client = client
        engine._started = True
        engine._journal = [redis_op("set", {"key": "feature-flag/a", "value": "enabled"})]

        engine.reset()

        assert client.commands == [
            ("flushdb", (), {}),
            ("set", ("feature-flag/a", "enabled"), {}),
        ]
        assert container.starts == 0
        assert container.stops == 0

    def test_reset_with_empty_journal_only_flushes(self, monkeypatch: pytest.MonkeyPatch):
        """A service without startup data resets to the plain empty database."""
        engine, _ = armed_engine(monkeypatch)
        client = FakeRedisClient()
        engine._container = FakeRedisContainer("redis:8-alpine")
        engine._client = client
        engine._started = True
        engine._journal = []

        engine.reset()

        assert client.commands == [("flushdb", (), {})]

    def test_stop_is_safe_before_start(self):
        """A stop of a never-started engine raises nothing — twice."""
        engine = cache_engine()

        engine.stop()
        engine.stop()
