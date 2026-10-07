"""Contract and logic tests for the ``PostgresEngine`` entity."""

import inspect
from typing import ClassVar

import psycopg
import pytest
from goga_tool_pybuggy.sandbox.config import InstanceConfig
from goga_tool_pybuggy.sandbox.engines import BaseEngine, DataOperation, EngineError, PostgresEngine
from goga_tool_pybuggy.sandbox.engines import postgres as postgres_module

from ..conftest import requires_docker


def db_engine(image: str | None = None) -> PostgresEngine:
    """Build a postgres engine of the sample ``db`` instance.

    Args:
        image: The optional image override of the instance declaration.

    Returns:
        The engine of an instance named ``db`` of kind ``postgresql``.
    """
    return PostgresEngine(InstanceConfig(name="db", kind="postgresql", image=image))


def insert_op(rows: list[dict[str, object]], table: str = "orders") -> DataOperation:
    """Build one postgresql insert operation of the table + rows payload form.

    Args:
        rows: The rows to insert, in list order.
        table: The target table.

    Returns:
        A sample ``insert`` operation targeted at the ``db`` instance.
    """
    return DataOperation(instance="db", kind="postgresql", action="insert", payload={"table": table, "rows": rows})


def sql_op(sql: str) -> DataOperation:
    """Build one postgresql insert operation of the raw sql payload form.

    Args:
        sql: The raw statement executed as given.

    Returns:
        A sample startup-shaped ``insert`` operation targeted at the ``db`` instance.
    """
    return DataOperation(instance="db", kind="postgresql", action="insert", payload={"sql": sql})


class FakeCursor:
    """Cursor double recording statements and serving the catalog preset on fetchall."""

    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        return False

    def execute(self, sql: str, params: object = None) -> None:
        self._connection.statements.append(("execute", sql, params))

    def executemany(self, sql: str, params_set: list[object]) -> None:
        self._connection.statements.append(("executemany", sql, params_set))

    def fetchall(self) -> list[tuple[str, str]]:
        return list(self._connection.catalog)


class FakeConnection:
    """Connection double of the postgres data plane — records statements, serves the catalog."""

    def __init__(self, catalog: list[tuple[str, str]] | None = None) -> None:
        self.catalog = catalog or []
        self.statements: list[tuple[str, str, object]] = []
        self._cursor = FakeCursor(self)

    def cursor(self) -> FakeCursor:
        return self._cursor


class FailingCursor(FakeCursor):
    """Cursor double failing every statement with a driver-shaped error."""

    def execute(self, sql: str, params: object = None) -> None:
        raise psycopg.errors.UndefinedTable('relation "ghost" does not exist')

    def executemany(self, sql: str, params_set: list[object]) -> None:
        raise psycopg.errors.UndefinedTable('relation "ghost" does not exist')


class FailingConnection(FakeConnection):
    """Connection double whose cursor fails every statement."""

    def __init__(self) -> None:
        super().__init__()
        self._cursor = FailingCursor(self)


class FakePostgresContainer:
    """Constructor double of the postgres module container recording the build arguments."""

    last_kwargs: ClassVar[dict[str, object]] = {}

    def __init__(self, image: str, **kwargs: object) -> None:
        self.image = image
        self.kwargs = kwargs
        self.network: object | None = None
        self.network_aliases: list[str] = []

        FakePostgresContainer.last_kwargs = {"image": image, **kwargs}

    def with_network(self, network: object) -> "FakePostgresContainer":
        self.network = network

        return self

    def with_network_aliases(self, *aliases: str) -> "FakePostgresContainer":
        self.network_aliases.extend(aliases)

        return self


class TestPostgresEngineContract:
    """Declared API of the ``PostgresEngine`` entity."""

    def test_postgres_engine_is_importable_from_engines_facade(self):
        """``PostgresEngine`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert PostgresEngine is not None

    def test_postgres_engine_subclasses_base_engine(self):
        """The kind engine inherits the base contract."""
        assert issubclass(PostgresEngine, BaseEngine)

    def test_postgres_engine_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config)``."""
        signature = inspect.signature(PostgresEngine.__init__)

        assert list(signature.parameters) == ["self", "config"]

    def test_postgres_engine_inherits_the_contract_methods(self):
        """``start`` / ``apply`` / ``record`` / ``reset`` / ``stop`` resolve with declared parameters."""
        expected = {
            "start": ["self", "startup", "network"],
            "apply": ["self", "operations"],
            "record": ["self", "operations"],
            "reset": ["self"],
            "stop": ["self"],
        }

        for method, parameters in expected.items():
            assert list(inspect.signature(getattr(PostgresEngine, method)).parameters) == parameters

    def test_postgres_engine_inherits_the_address_property(self):
        """The ``address`` property of the base resolves on the kind engine."""
        address = inspect.getattr_static(PostgresEngine, "address")

        assert isinstance(address, property)


class TestPostgresEngineBuild:
    """Container build arguments of the postgres engine, driven through the patched constructor."""

    def test_build_uses_the_pinned_image_and_labels_without_override(self, monkeypatch: pytest.MonkeyPatch):
        """Without an image override the build uses the pinned image and the sandbox labels."""
        monkeypatch.setattr(postgres_module, "PostgresContainer", FakePostgresContainer)
        engine = db_engine()

        engine._build_container()

        assert FakePostgresContainer.last_kwargs["image"] == "postgres:16-alpine"
        assert FakePostgresContainer.last_kwargs["labels"] == {"pybuggy-sandbox": "true"}

    def test_build_honors_the_image_override(self, monkeypatch: pytest.MonkeyPatch):
        """The image override of the instance config reaches the container build."""
        monkeypatch.setattr(postgres_module, "PostgresContainer", FakePostgresContainer)
        engine = db_engine(image="postgres:17-alpine")

        engine._build_container()

        assert FakePostgresContainer.last_kwargs["image"] == "postgres:17-alpine"

    def test_build_pins_the_plane_credentials(self, monkeypatch: pytest.MonkeyPatch):
        """The container credentials match the pinned data-plane credentials (test/test/test)."""
        monkeypatch.setattr(postgres_module, "PostgresContainer", FakePostgresContainer)
        engine = db_engine()

        engine._build_container()

        assert FakePostgresContainer.last_kwargs["username"] == "test"
        assert FakePostgresContainer.last_kwargs["password"] == "test"
        assert FakePostgresContainer.last_kwargs["dbname"] == "test"


class TestPostgresEnginePlane:
    """Statement execution and wipe of the postgres engine, driven over the fake connection."""

    def test_execute_raw_sql_statement_as_given(self):
        """A ``sql`` payload executes as given — no parameters, no rewriting."""
        engine = db_engine()
        connection = FakeConnection()
        engine._connection = connection

        engine._execute(sql_op("CREATE TABLE IF NOT EXISTS orders (id int PRIMARY KEY, n int)"))

        assert connection.statements == [
            ("execute", "CREATE TABLE IF NOT EXISTS orders (id int PRIMARY KEY, n int)", None),
        ]

    def test_execute_insert_builds_parameterized_bulk_insert(self):
        """A ``table`` + ``rows`` payload executes one parameterized bulk insert."""
        engine = db_engine()
        connection = FakeConnection()
        engine._connection = connection

        engine._execute(insert_op([{"id": 1, "n": 5}, {"id": 2, "n": 7}]))

        assert connection.statements == [
            ("executemany", 'INSERT INTO "orders" ("id", "n") VALUES (%s, %s)', [(1, 5), (2, 7)]),
        ]

    def test_execute_insert_with_empty_rows_executes_nothing(self):
        """Empty rows skip the statement — a no-op."""
        engine = db_engine()
        connection = FakeConnection()
        engine._connection = connection

        engine._execute(insert_op([]))

        assert connection.statements == []

    def test_execute_insert_takes_columns_from_the_first_row_in_insertion_order(self):
        """The column list follows the first row's keys in insertion order."""
        engine = db_engine()
        connection = FakeConnection()
        engine._connection = connection

        engine._execute(insert_op([{"n": 5, "id": 1}, {"id": 2, "n": 7}]))

        statement = connection.statements[0]
        assert statement[1] == 'INSERT INTO "orders" ("n", "id") VALUES (%s, %s)'
        assert statement[2] == [(5, 1), (7, 2)]

    def test_execute_wraps_driver_errors_with_the_server_message(self):
        """A failed statement surfaces as a plain error carrying the driver message."""
        engine = db_engine()
        engine._connection = FailingConnection()

        with pytest.raises(RuntimeError, match='relation "ghost" does not exist'):
            engine._execute(insert_op([{"id": 1}]))

    @pytest.mark.parametrize(
        "payload",
        [{}, {"table": "orders"}, {"rows": [{"id": 1}]}, {"topic": "orders.events"}],
    )
    def test_execute_fails_readably_without_either_insert_form(self, payload):
        """A payload carrying neither ``sql`` nor ``table`` + ``rows`` fails naming both forms."""
        engine = db_engine()
        engine._connection = FakeConnection()

        operation = DataOperation(instance="db", kind="postgresql", action="insert", payload=payload)

        with pytest.raises(RuntimeError, match=r"must carry either 'sql' or 'table' \+ 'rows'"):
            engine._execute(operation)

        assert engine._connection.statements == []

    def test_apply_wraps_the_missing_form_error_into_engine_error(self):
        """Through the apply path the malformed payload surfaces as a readable ``EngineError``."""
        engine = db_engine()
        engine._connection = FakeConnection()
        engine._started = True

        operation = DataOperation(instance="db", kind="postgresql", action="insert", payload={"table": "orders"})

        with pytest.raises(EngineError, match=r"instance 'db': insert failed:.*'table' \+ 'rows'"):
            engine.apply([operation])

    def test_wipe_truncates_every_discovered_table_in_one_statement(self):
        """Wipe discovers the catalog at reset time and truncates all tables in one statement."""
        engine = db_engine()
        connection = FakeConnection(catalog=[("public", "orders"), ("app", "customers")])
        engine._connection = connection

        engine._wipe()

        assert connection.statements[0][1].startswith("SELECT table_schema, table_name")
        assert "information_schema.tables" in connection.statements[0][1]
        assert connection.statements[1] == (
            "execute",
            'TRUNCATE TABLE "public"."orders", "app"."customers" RESTART IDENTITY CASCADE',
            None,
        )

    def test_wipe_skips_truncate_without_user_tables(self):
        """An empty catalog skips the truncate — the replay-only reset."""
        engine = db_engine()
        connection = FakeConnection(catalog=[])
        engine._connection = connection

        engine._wipe()

        assert len(connection.statements) == 1


@requires_docker
class TestPostgresEngineContainer:
    """Live behavior of the postgres engine against a real container (docker-gated)."""

    def fetch_rows(self, engine: PostgresEngine) -> list[tuple[int, int]]:
        """Read every row of the sample orders table through the engine connection.

        Args:
            engine: The started engine whose connection queries the table.

        Returns:
            Every ``(id, n)`` row of the orders table, ordered by id.
        """
        with engine._connection.cursor() as cursor:
            cursor.execute("SELECT id, n FROM orders ORDER BY id")

            return cursor.fetchall()

    def test_postgres_engine_roundtrip_start_apply_reset(self):
        """Reset restores the baseline: journaled rows survive, test rows are gone."""
        engine = db_engine()
        engine.start([sql_op("CREATE TABLE IF NOT EXISTS orders (id int PRIMARY KEY, n int)")])

        try:
            assert engine.address.port > 0

            # record journals without applying — the baseline boundary is the applying seam.
            engine.record([insert_op([{"id": 1, "n": 5}])])
            engine.apply([insert_op([{"id": 2, "n": 7}])])

            assert self.fetch_rows(engine) == [(2, 7)]

            engine.reset()

            assert self.fetch_rows(engine) == [(1, 5)]

            with pytest.raises(EngineError, match="duplicate key") as excinfo:
                engine.apply([insert_op([{"id": 1, "n": 5}])])

            assert isinstance(excinfo.value.__cause__.__cause__, psycopg.errors.UniqueViolation)
        finally:
            engine.stop()

        engine.stop()

    def test_reset_with_empty_journal_is_wipe_only(self):
        """Reset over an empty journal wipes the table without replaying anything."""
        engine = db_engine()
        engine.start([])

        try:
            engine.apply([sql_op("CREATE TABLE IF NOT EXISTS orders (id int PRIMARY KEY, n int)")])
            engine.apply([insert_op([{"id": 1, "n": 5}])])

            assert self.fetch_rows(engine) == [(1, 5)]

            engine.reset()

            assert self.fetch_rows(engine) == []
        finally:
            engine.stop()
