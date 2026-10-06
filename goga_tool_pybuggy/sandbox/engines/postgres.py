"""PostgresEngine: the postgresql kind engine — a real postgres instance."""

import logging

import psycopg
from testcontainers.postgres import PostgresContainer

from ..config.instance import InstanceConfig
from .base import BaseEngine
from .operation import DataOperation

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "postgres:16-alpine"
CONTAINER_PORT = 5432
PLANE_USER = "test"
PLANE_PASSWORD = "test"
PLANE_DBNAME = "test"
SANDBOX_LABELS = {"pybuggy-sandbox": "true"}

CATALOG_QUERY = (
    "SELECT table_schema, table_name FROM information_schema.tables "
    "WHERE table_type = 'BASE TABLE' "
    "AND table_schema NOT IN ('pg_catalog', 'information_schema')"
)


class PostgresEngine(BaseEngine):
    """postgresql kind engine: module container, autocommit SQL plane, catalog-driven wipe.

    The container uses the product-pinned postgres image unless the instance config overrides
    it; module readiness applies — start returns after the server accepts connections. The data
    plane is one session-scoped autocommit connection. Reset discovers the user tables from the
    catalog and truncates them all in one statement — the container is never restarted.

    Attributes:
        config: The instance declaration — name, kind, image override.
    """

    _container_port = CONTAINER_PORT

    def __init__(self, config: InstanceConfig) -> None:
        """Initialize the postgres engine of one configured instance.

        Args:
            config: The instance declaration — name, kind, image override.
        """
        super().__init__(config)
        self._connection: psycopg.Connection | None = None

    def _build_container(self) -> PostgresContainer:
        """Build the postgres module container — pinned image, labels, published port.

        Returns:
            The built, not yet started, postgres container.
        """
        image = self.config.image or DEFAULT_IMAGE

        return PostgresContainer(
            image,
            username=PLANE_USER,
            password=PLANE_PASSWORD,
            dbname=PLANE_DBNAME,
            labels=SANDBOX_LABELS,
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
        logger.debug("postgres plane open", extra={"instance": self.config.name})

    def _execute(self, operation: DataOperation) -> None:
        """Execute one postgresql operation through the session connection.

        A raw ``sql`` payload executes as given; a ``table`` + ``rows`` payload executes one
        parameterized bulk insert with the column list taken from the first row's keys in
        insertion order; empty rows execute nothing.

        Args:
            operation: The ``insert`` operation to execute.

        Raises:
            RuntimeError: The statement failed; the message carries the server message.
        """
        try:
            with self._connection.cursor() as cursor:
                if "sql" in operation.payload:
                    cursor.execute(operation.payload["sql"])
                elif operation.payload["rows"]:
                    statement, parameters = self._insert_plan(operation.payload["table"], operation.payload["rows"])
                    cursor.executemany(statement, parameters)
        except psycopg.Error as exc:
            raise RuntimeError(_server_message(exc)) from exc

        logger.debug("postgres statement executed", extra={"instance": self.config.name})

    def _wipe(self) -> None:
        """Truncate every user table discovered from the catalog at reset time.

        One statement over all discovered tables — cascade carries the foreign-key ordering,
        restart identity resets the sequences. Skipped when the catalog holds no user tables.

        Raises:
            RuntimeError: The discovery or the truncate failed; the message carries the server
                message.
        """
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

    def _insert_plan(self, table: object, rows: object) -> tuple[str, list[tuple[object, ...]]]:
        """Build the bulk-insert statement and its parameter sets.

        Args:
            table: The target table name.
            rows: The rows to insert, in list order.

        Returns:
            The parameterized insert statement and the parameter tuples in row order.
        """
        row_list: list[dict[str, object]] = rows
        columns = list(row_list[0].keys())
        column_list = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        parameters = [tuple(row[column] for column in columns) for row in row_list]

        return f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})', parameters


def _server_message(error: psycopg.Error) -> str:
    """Extract the server-side message of a driver error.

    Args:
        error: The driver error raised by a failed statement.

    Returns:
        The server's primary message, or the driver message when the server sent none.
    """
    primary = error.diag.message_primary

    return primary if primary else str(error)
