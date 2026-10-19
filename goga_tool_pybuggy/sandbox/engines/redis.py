"""RedisEngine: the redis kind engine — a real redis service."""

import json
import logging

import redis
from testcontainers.community.redis import RedisContainer
from testcontainers.core.waiting_utils import WaitStrategy, WaitStrategyTarget

from ..config.service import ServiceConfig
from .base import BaseEngine
from .operation import DataOperation

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "redis:8-alpine"
CONTAINER_PORT = 6379
PLANE_TIMEOUT = 5
PROBE_CONNECT_TIMEOUT = 2
SANDBOX_LABELS = {"pybuggy-sandbox": "true"}

_REDIS_ACTIONS = {
    "set": ("key", "value"),
    "hset": ("key", "values"),
    "rpush": ("key", "values"),
    "sadd": ("key", "members"),
}


class _NoWaitStrategy(WaitStrategy):
    """The no-op wait strategy replacing the redis module's built-in PING wait.

    The community module installs its ``PingWaitStrategy`` in its constructor — bounds the
    engine cannot re-parameterize from outside — so the engine overwrites the installed
    strategy right after construction: readiness probing is engine-owned, bounded by the
    declared deadline.
    """

    def wait_until_ready(self, container: WaitStrategyTarget) -> None:
        """No-op — readiness probing is engine-owned, bounded by the declared deadline."""


class RedisEngine(BaseEngine):
    """Redis kind engine: module container, engine-owned PING readiness, one session client.

    The container uses the product-pinned redis image unless the service config overrides it.
    A declared password reaches the container command through the module constructor — the
    module wires ``--requirepass`` — while an absent password starts redis without
    authentication, the primary mode. Readiness is engine-owned: the module container's
    built-in PING wait is replaced with a no-op and the engine probes the server with the
    official client — one throwaway PING connection per attempt at the declared bounds; a
    refused or timed-out connection keeps the loop probing, an authentication failure fails
    fast within the bounds instead of retrying to expiry.

    The data plane is one session connection of the official client to the declared logical
    database, opened after readiness, held for the session, closed on stop. The four v1
    operations apply as their redis commands — ``set``, ``hset``, ``rpush``, ``sadd`` — with
    values serialized to the wire form at execution: a string rides as given, anything else
    takes its JSON form, so the declared payload is never rewritten and journal replay stays
    deterministic. Empty values, members or field mappings execute nothing — the postgres
    empty-rows precedent.

    Reset flushes the declared database with one ``FLUSHDB`` over the open connection — the
    container never restarts and the connection survives the reset — and the base replays the
    journal through the same execution path. Migrations are rejected on the redis kind at
    document load; the migrate hook keeps the no-op default.

    Attributes:
        config: The service declaration — name, kind, image override, probe, password, db.
    """

    _container_port = CONTAINER_PORT

    def __init__(self, config: ServiceConfig) -> None:
        """Initialize the redis engine of one configured dependency service.

        Args:
            config: The service declaration — name, kind, image override, probe, password, db.
        """
        super().__init__(config)
        self._client: redis.Redis | None = None

    def _build_container(self) -> RedisContainer:
        """Build the redis module container — pinned image, labels, published port.

        The declared password reaches the container command through the module constructor;
        the module's built-in PING wait is replaced with the engine's no-op strategy right
        after construction — the only override seam — so readiness stays engine-owned.

        Returns:
            The built, not yet started, redis container with the internal readiness wait
            disabled.
        """
        image = self.config.image or DEFAULT_IMAGE

        container = RedisContainer(image, password=self.config.password or None, labels=SANDBOX_LABELS)
        container.waiting_for(_NoWaitStrategy())

        self._attach_network(container)

        return container

    def _wait_ready(self) -> None:
        """Wait for the server to answer PING, bounded by the declared deadline.

        The engine owns the readiness probe: every attempt opens one throwaway client of the
        official library — the same authentication and wire condition the session connection
        needs — and closes it on every outcome. A refused or timed-out connection returns the
        attempt to the ``_probe_until`` loop at the declared bounds; an authentication failure
        escapes the loop immediately — the clause order is load-bearing because
        ``AuthenticationError`` is a ``ConnectionError`` subclass.

        Raises:
            RuntimeError: The authentication failed — the message names the waited check and
                the cause; or the declared deadline expired — the start lifecycle wrapper
                converts either into ``EngineError`` naming the service and the deadline.
        """
        address = self.address
        timeout, interval = self._readiness_bounds
        failure = f"the redis service did not answer PING at {address.host}:{address.port}"

        def attempt() -> bool:
            probe = redis.Redis(
                host=address.host,
                port=address.port,
                password=self.config.password or None,
                socket_timeout=PROBE_CONNECT_TIMEOUT,
                connect_timeout=PROBE_CONNECT_TIMEOUT,
            )

            try:
                return bool(probe.ping())
            except redis.exceptions.AuthenticationError as exc:
                raise RuntimeError(f"{failure}: authentication failed: {exc}") from exc
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
                return False
            finally:
                probe.close()

        self._probe_until(timeout, interval, attempt, failure)

        logger.debug(
            "redis service ready",
            extra={"service": self.config.name, "kind": self.config.kind, "host": address.host, "port": address.port},
        )

    def _open_plane(self) -> None:
        """Open the session client against the declared logical database.

        One client of the official library over one connection to the declared database —
        ``decode_responses`` stays off, reads keep their bytes form. An eager PING binds the
        connection, so a data-plane failure surfaces at this start step instead of the first
        operation.

        Raises:
            EngineError: The connection or the binding PING failed — wrapped by the start
                lifecycle step.
        """
        address = self.address

        self._client = redis.Redis(
            host=address.host,
            port=address.port,
            db=self.config.db,
            password=self.config.password or None,
            socket_timeout=PLANE_TIMEOUT,
            connect_timeout=PLANE_TIMEOUT,
        )
        self._client.ping()

        logger.debug(
            "redis plane open",
            extra={"service": self.config.name, "kind": self.config.kind, "host": address.host, "port": address.port},
        )

    def _execute(self, operation: DataOperation) -> None:
        """Execute one redis operation over the session connection.

        The action dispatches onto its redis command with the declared payload — a string
        value rides as given, every other value takes its JSON wire form at execution; the
        declared payload itself is never rewritten. Empty values, members or field mappings
        execute nothing.

        Args:
            operation: The ``set`` / ``hset`` / ``rpush`` / ``sadd`` operation to execute.

        Raises:
            RuntimeError: The action is unknown or the command failed; the base wrapper
                converts it into ``EngineError`` naming the service, the action and the cause.
        """
        if operation.action not in _REDIS_ACTIONS:
            raise RuntimeError(f"unknown redis action '{operation.action}' ({', '.join(_REDIS_ACTIONS)})")

        payload = operation.payload
        key = payload["key"]

        if operation.action == "set":
            self._client.set(key, _wire(payload["value"]))
        elif operation.action == "hset":
            values = payload.get("values") or {}

            if values:
                self._client.hset(key, mapping={field: _wire(value) for field, value in values.items()})
        elif operation.action == "rpush":
            values = payload.get("values") or []

            if values:
                self._client.rpush(key, *[_wire(value) for value in values])
        else:
            members = payload.get("members") or []

            if members:
                self._client.sadd(key, *[_wire(member) for member in members])

    def _wipe(self) -> None:
        """Flush the declared logical database — back to the empty state.

        One ``FLUSHDB`` over the open session connection: the declared database empties, no
        other logical database is touched, the container keeps running and the connection
        survives. The base replays the journal after the wipe through the same execution
        path.
        """
        self._client.flushdb()

        logger.debug("redis database flushed", extra={"service": self.config.name, "db": self.config.db})

    def _close_plane(self) -> None:
        """Close the session client; safe when nothing is open."""
        if self._client is not None:
            self._client.close()
            self._client = None


def _wire(value: object) -> str:
    """Serialize one declared value to the redis wire form.

    Args:
        value: The declared value — a string or JSON-serializable plain data.

    Returns:
        The string as given, or the JSON form of every other value — the deterministic wire
        form journal replay depends on.
    """
    if isinstance(value, str):
        return value

    return json.dumps(value)
