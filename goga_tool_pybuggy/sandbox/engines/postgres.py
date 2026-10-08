"""PostgresEngine: the postgresql kind engine — a real postgres service."""

import logging

import psycopg
from psycopg.rows import dict_row
from testcontainers.community.postgres import PostgresContainer

from ..config.service import ServiceConfig
from .base import BaseEngine
from .operation import DataOperation
from .refs import LOOKUP_KEY, REF_KEY, is_reference, parse_ref_address

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "postgres:16-alpine"
CONTAINER_PORT = 5432
PLANE_USER = "test"
PLANE_PASSWORD = "test"
PLANE_DBNAME = "test"
PROBE_CONNECT_TIMEOUT = 2
SANDBOX_LABELS = {"pybuggy-sandbox": "true"}

CATALOG_QUERY = (
    "SELECT table_schema, table_name FROM information_schema.tables "
    "WHERE table_type = 'BASE TABLE' "
    "AND table_schema NOT IN ('pg_catalog', 'information_schema')"
)

PK_QUERY = (
    "SELECT kcu.column_name FROM information_schema.table_constraints AS tc "
    "JOIN information_schema.key_column_usage AS kcu "
    "ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
    "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = %s "
    "AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')"
)


class _PostgresContainer(PostgresContainer):
    """The postgres module container with its internal readiness wait disabled.

    The module's ``_connect`` builds its ``ExecWaitStrategy`` from the global testcontainers
    configuration — bounds that cannot be re-parameterized from outside — so the subclass
    disables the internal wait: readiness probing is engine-owned, bounded by the declared
    deadline.
    """

    def _connect(self) -> None:
        """No-op — readiness probing is engine-owned, bounded by the declared deadline."""


class PostgresEngine(BaseEngine):
    """postgresql kind engine: module container, autocommit SQL plane, catalog-driven wipe.

    The container uses the product-pinned postgres image unless the service config overrides
    it. Readiness is engine-owned: the module container's internal wait is disabled and the
    engine probes the server with the data-plane driver — start returns after the server
    accepts connections, within the declared deadline at the declared interval. The data plane
    is one session-scoped autocommit connection. Reset discovers the user tables from the
    catalog and truncates them all in one statement — the container is never restarted.

    Row inserts resolve ``$ref`` / ``$lookup`` values at execution time and capture every
    applied row (``RETURNING``) into a per-table symbol stream — the address space later
    ``$ref`` declarations resolve against. The stream lives since the last wipe: reset clears
    it and the journal replay rebuilds it.

    Attributes:
        config: The service declaration — name, kind, image override, probe.
    """

    _container_port = CONTAINER_PORT

    def __init__(self, config: ServiceConfig) -> None:
        """Initialize the postgres engine of one configured dependency service.

        Args:
            config: The service declaration — name, kind, image override, probe.
        """
        super().__init__(config)
        self._connection: psycopg.Connection | None = None
        self._symbols: dict[str, list[dict[str, object]]] = {}

    def _build_container(self) -> PostgresContainer:
        """Build the postgres module container — pinned image, labels, published port.

        Returns:
            The built, not yet started, postgres container with the internal readiness wait
            disabled (``_PostgresContainer``) — the engine owns readiness probing.
        """
        image = self.config.image or DEFAULT_IMAGE

        container = _PostgresContainer(
            image,
            username=PLANE_USER,
            password=PLANE_PASSWORD,
            dbname=PLANE_DBNAME,
            labels=SANDBOX_LABELS,
        )

        self._attach_network(container)

        return container

    def _wait_ready(self) -> None:
        """Wait for the server to accept connections, bounded by the declared deadline.

        The engine owns the readiness probe: it connects with the data-plane driver — the same
        condition the session connection needs — inside the ``_probe_until`` loop at the
        declared bounds of the service's probe declaration. The probe connection closes on
        success; the session connection opens in ``_open_plane``.

        Raises:
            RuntimeError: The declared deadline expired; the start lifecycle wrapper converts
                it into ``EngineError`` naming the service, the waited check and the deadline.
        """
        address = self.address
        timeout, interval = self._readiness_bounds
        failure = f"the postgresql service did not accept connections at {address.host}:{address.port}"

        def attempt() -> bool:
            try:
                connection = psycopg.connect(
                    host=address.host,
                    port=address.port,
                    user=PLANE_USER,
                    password=PLANE_PASSWORD,
                    dbname=PLANE_DBNAME,
                    connect_timeout=PROBE_CONNECT_TIMEOUT,
                )
            except psycopg.Error:
                return False

            connection.close()

            return True

        self._probe_until(timeout, interval, attempt, failure)

        logger.debug(
            "postgres service ready",
            extra={"service": self.config.name, "kind": self.config.kind, "host": address.host, "port": address.port},
        )

    def _open_plane(self) -> None:
        """Open the session autocommit connection against the started container.

        Raises:
            EngineError: The connection failed — wrapped by the start lifecycle step.
        """
        address = self.address

        self._connection = psycopg.connect(
            host=address.host,
            port=address.port,
            user=PLANE_USER,
            password=PLANE_PASSWORD,
            dbname=PLANE_DBNAME,
            autocommit=True,
        )
        logger.debug("postgres plane open", extra={"service": self.config.name})

    def _execute(self, operation: DataOperation) -> None:
        """Execute one postgresql operation through the session connection.

        A raw ``sql`` payload executes as given — opaque: no reference resolution, no symbol
        capture. A ``table`` + ``rows`` payload resolves ``$ref`` / ``$lookup`` values and
        applies the rows one by one with ``RETURNING`` inside one transaction, capturing every
        applied row into the symbol stream; empty rows execute nothing. A payload carrying
        neither form is a malformed declaration and fails with a readable error naming both
        expected forms.

        Args:
            operation: The ``insert`` operation to execute.

        Raises:
            RuntimeError: The statement, the reference resolution, or the payload form failed;
                the failure message names the cause.
        """
        if "sql" not in operation.payload and not ("table" in operation.payload and "rows" in operation.payload):
            raise RuntimeError("an insert payload must carry either 'sql' or 'table' + 'rows'")

        try:
            if "sql" in operation.payload:
                with self._connection.cursor() as cursor:
                    cursor.execute(operation.payload["sql"])
            elif operation.payload["rows"]:
                self._insert_rows(operation.payload["table"], operation.payload["rows"])
        except psycopg.Error as exc:
            raise RuntimeError(_server_message(exc)) from exc

        logger.debug("postgres statement executed", extra={"service": self.config.name})

    def _insert_rows(self, table: object, rows: object) -> None:
        """Apply declared rows one by one, capturing every applied row for ``$ref`` addressing.

        The column list follows the first row's keys in insertion order; every row resolves
        its values first, so later rows may reference earlier rows of the same insert. The
        whole insert is one transaction — a failing row leaves nothing applied and the symbol
        stream rolls back with it. The declared payload is never rewritten: resolution builds
        fresh values.

        Args:
            table: The target table.
            rows: The declared rows, in list order.

        Raises:
            RuntimeError: A value failed to resolve or a row failed to apply.
        """
        row_list: list[dict[str, object]] = rows
        columns = list(row_list[0].keys())
        column_list = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        statement = f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders}) RETURNING *'

        stream = self._symbols.setdefault(table, [])
        base = len(stream)

        try:
            with self._connection.transaction(), self._connection.cursor(row_factory=dict_row) as cursor:
                for row in row_list:
                    resolved = {column: self._resolve_value(row[column]) for column in columns}
                    cursor.execute(statement, tuple(resolved[column] for column in columns))
                    applied = cursor.fetchone()

                    if applied is None:
                        raise RuntimeError(f'the insert into "{table}" returned no row')

                    stream.append(dict(applied))
        except BaseException:
            del stream[base:]

            if not stream:
                del self._symbols[table]

            raise

    def _resolve_value(self, value: object) -> object:
        """Resolve one declared row value — references resolve, plain values pass through.

        Args:
            value: The declared value of one column.

        Returns:
            The executable value — the resolved reference or the value as given.

        Raises:
            RuntimeError: The reference is malformed or unresolvable; the message names the
                cause.
        """
        if not is_reference(value):
            return value

        if REF_KEY in value:
            try:
                table, index, column = parse_ref_address(value[REF_KEY])
            except ValueError as exc:
                raise RuntimeError(f"malformed $ref value: {exc}") from exc

            return self._symbol_value(table, index, column)

        return self._lookup_value(value[LOOKUP_KEY])

    def _symbol_value(self, table: str, index: int, column: str) -> object:
        """Read one captured row value out of the engine's symbol stream.

        Args:
            table: The referenced table.
            index: The referenced row's position in the table's applied-row stream.
            column: The referenced column.

        Returns:
            The captured value of the addressed row's column.

        Raises:
            RuntimeError: The table holds no data-plane rows, the index is out of range, or
                the column is absent from the captured row.
        """
        rows = self._symbols.get(table)

        if not rows:
            raise RuntimeError(
                f'$ref "{table}.{index}.{column}": no rows of "{table}" were applied by the data '
                "plane — rows created by raw sql or the instance under test are addressable only through $lookup"
            )

        if index < 0 or index >= len(rows):
            raise RuntimeError(
                f'$ref "{table}.{index}.{column}": "{table}" holds {len(rows)} applied row(s) — '
                "the row index is out of range"
            )

        row = rows[index]

        if column not in row:
            available = ", ".join(sorted(str(key) for key in row))
            raise RuntimeError(
                f'$ref "{table}.{index}.{column}": the applied row carries no column "{column}" (columns: {available})'
            )

        return row[column]

    def _lookup_value(self, spec: object) -> object:
        """Resolve one ``$lookup`` against the current database state.

        The match query is fully parameterized; the predicate must match exactly one row —
        zero matches name the missing precondition, more than one names the ambiguity. The
        resolved column is the table's primary key unless the specification overrides it.

        Args:
            spec: The ``$lookup`` specification — table, where, optional column.

        Returns:
            The addressed column value of the single matched row.

        Raises:
            RuntimeError: The primary key is not discoverable or the predicate matches zero or
                more than one row.
        """
        lookup: dict[str, object] = spec
        column = lookup.get("column")

        if column is None:
            column = self._primary_key_column(lookup["table"])

        conditions: dict[str, object] = lookup["where"]
        keys = list(conditions.keys())
        predicate = " AND ".join(f'"{key}" = %s' for key in keys)
        statement = f'SELECT "{column}" FROM "{lookup["table"]}" WHERE {predicate} LIMIT 2'

        with self._connection.cursor() as cursor:
            cursor.execute(statement, tuple(conditions[key] for key in keys))
            matches = cursor.fetchall()

        if not matches:
            raise RuntimeError(f'$lookup on "{lookup["table"]}" matched no row — the precondition data is missing')

        if len(matches) > 1:
            raise RuntimeError(
                f'$lookup on "{lookup["table"]}" matched {len(matches)} rows — make the where '
                "predicate match exactly one row"
            )

        return matches[0][0]

    def _primary_key_column(self, table: str) -> str:
        """Discover the single primary-key column of one table from the catalog.

        Args:
            table: The looked-up table.

        Returns:
            The name of the table's primary-key column.

        Raises:
            RuntimeError: No primary key is discoverable, or several candidate columns were
                found — an explicit ``column`` disambiguates.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(PK_QUERY, (table,))
            found = cursor.fetchall()

        if not found:
            raise RuntimeError(f'$lookup on "{table}" found no primary key — pass an explicit "column"')

        columns = [row[0] for row in found]

        if len(columns) > 1:
            listed = ", ".join(f'"{column}"' for column in columns)
            raise RuntimeError(
                f'$lookup on "{table}" found several primary-key candidates ({listed}) — pass an explicit "column"'
            )

        return columns[0]

    def _wipe(self) -> None:
        """Truncate every user table discovered from the catalog at reset time.

        One statement over all discovered tables — cascade carries the foreign-key ordering,
        restart identity resets the sequences. The symbol stream clears with the tables: the
        rows it addressed are gone. Skipped when the catalog holds no user tables.

        Raises:
            RuntimeError: The discovery or the truncate failed; the message carries the server
                message.
        """
        self._symbols.clear()

        with self._connection.cursor() as cursor:
            cursor.execute(CATALOG_QUERY)
            tables = cursor.fetchall()

        if not tables:
            return

        targets = ", ".join(f'"{schema}"."{name}"' for schema, name in tables)

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(f"TRUNCATE TABLE {targets} RESTART IDENTITY CASCADE")
        except psycopg.Error as exc:
            raise RuntimeError(_server_message(exc)) from exc

    def _close_plane(self) -> None:
        """Close the session connection; safe when nothing is open."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None


def _server_message(error: psycopg.Error) -> str:
    """Extract the server-side message of a driver error.

    Args:
        error: The driver error raised by a failed statement.

    Returns:
        The server's primary message, or the driver message when the server sent none.
    """
    primary = error.diag.message_primary

    return primary if primary else str(error)
