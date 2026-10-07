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
    """Cursor double recording statements and serving the queued fetch results."""

    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        return False

    def execute(self, sql: str, params: object = None) -> None:
        self._connection.statements.append(("execute", sql, params))

    def fetchall(self) -> list[object]:
        if not self._connection.result_sets:
            return []

        return list(self._connection.result_sets.pop(0))

    def fetchone(self) -> object:
        if not self._connection.row_queue:
            return None

        return self._connection.row_queue.pop(0)


class FakeTransaction:
    """Transaction double recording the begin/commit markers of one block."""

    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection

    def __enter__(self) -> "FakeTransaction":
        self._connection.statements.append(("transaction", "begin", None))

        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        outcome = "rollback" if exc_type is not None else "commit"
        self._connection.statements.append(("transaction", outcome, None))

        return False


class FakeConnection:
    """Connection double of the postgres data plane — records statements, serves queued results.

    ``result_sets`` feeds ``fetchall`` calls in first-in-first-out order (the catalog is the
    default first set); ``row_queue`` feeds the per-row ``fetchone`` calls of inserts.
    """

    def __init__(
        self,
        catalog: list[tuple[str, str]] | None = None,
        result_sets: list[list[object]] | None = None,
        row_queue: list[dict[str, object]] | None = None,
    ) -> None:
        self.catalog = catalog or []
        self.result_sets = result_sets if result_sets is not None else [self.catalog]
        self.row_queue = row_queue if row_queue is not None else []
        self.statements: list[tuple[str, str, object]] = []

    def cursor(self, row_factory: object = None) -> FakeCursor:
        return FakeCursor(self)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)


class FailingCursor(FakeCursor):
    """Cursor double failing every statement with a driver-shaped error."""

    def execute(self, sql: str, params: object = None) -> None:
        raise psycopg.errors.UndefinedTable('relation "ghost" does not exist')


class FailingConnection(FakeConnection):
    """Connection double whose cursor fails every statement."""

    def cursor(self, row_factory: object = None) -> FailingCursor:
        return FailingCursor(self)


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

    def test_execute_insert_applies_rows_one_by_one_with_returning(self):
        """A ``table`` + ``rows`` payload applies one parameterized insert per row with ``RETURNING``."""
        engine = db_engine()
        connection = FakeConnection(row_queue=[{"id": 1, "n": 5}, {"id": 2, "n": 7}])
        engine._connection = connection

        engine._execute(insert_op([{"id": 1, "n": 5}, {"id": 2, "n": 7}]))

        statement = 'INSERT INTO "orders" ("id", "n") VALUES (%s, %s) RETURNING *'
        assert connection.statements == [
            ("transaction", "begin", None),
            ("execute", statement, (1, 5)),
            ("execute", statement, (2, 7)),
            ("transaction", "commit", None),
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
        connection = FakeConnection(row_queue=[{"n": 5, "id": 1}, {"id": 2, "n": 7}])
        engine._connection = connection

        engine._execute(insert_op([{"n": 5, "id": 1}, {"id": 2, "n": 7}]))

        statement = connection.statements[1]
        assert statement[1] == 'INSERT INTO "orders" ("n", "id") VALUES (%s, %s) RETURNING *'
        assert statement[2] == (5, 1)

    def test_insert_captures_every_applied_row_into_the_symbol_stream(self):
        """Every applied row joins its table's symbol stream for later ``$ref`` addressing."""
        engine = db_engine()
        connection = FakeConnection(row_queue=[{"id": 1, "n": 5}, {"id": 2, "n": 7}])
        engine._connection = connection

        engine._execute(insert_op([{"id": 1, "n": 5}, {"id": 2, "n": 7}]))

        assert engine._symbols == {"orders": [{"id": 1, "n": 5}, {"id": 2, "n": 7}]}

    def test_raw_sql_never_populates_the_symbol_stream(self):
        """A raw ``sql`` payload applies without symbol capture — its rows are not addressable."""
        engine = db_engine()
        connection = FakeConnection()
        engine._connection = connection

        engine._execute(sql_op("INSERT INTO orders (id, n) VALUES (1, 5)"))

        assert engine._symbols == {}

    def test_ref_value_resolves_against_the_captured_rows(self):
        """A ``$ref`` value resolves to the captured column value of the addressed row."""
        engine = db_engine()
        connection = FakeConnection(row_queue=[{"id": 100, "customer_id": 42, "total": 5}])
        engine._connection = connection
        engine._symbols["customers"] = [{"id": 42, "name": "Ann"}]

        engine._execute(insert_op([{"customer_id": {"$ref": "customers.0.id"}, "total": 5}]))

        assert connection.statements[1] == (
            "execute",
            'INSERT INTO "orders" ("customer_id", "total") VALUES (%s, %s) RETURNING *',
            (42, 5),
        )

    def test_intra_operation_ref_resolves_the_earlier_row(self):
        """A later row may reference an earlier row of the same insert."""
        engine = db_engine()
        connection = FakeConnection(row_queue=[{"id": 5, "n": 5}, {"id": 5, "n": 7}])
        engine._connection = connection

        engine._execute(insert_op([{"id": 5, "n": 5}, {"id": {"$ref": "orders.0.id"}, "n": 7}]))

        assert connection.statements[2][2] == (5, 7)
        assert engine._symbols["orders"][1] == {"id": 5, "n": 7}

    def test_resolution_never_rewrites_the_declared_payload(self):
        """The declared rows keep their references — the journal replays them unresolved."""
        engine = db_engine()
        connection = FakeConnection(row_queue=[{"id": 100, "customer_id": 42}])
        engine._connection = connection
        engine._symbols["customers"] = [{"id": 42, "name": "Ann"}]
        operation = insert_op([{"customer_id": {"$ref": "customers.0.id"}}])

        engine._execute(operation)

        assert operation.payload["rows"] == [{"customer_id": {"$ref": "customers.0.id"}}]

    def test_ref_to_an_unapplied_table_names_the_lookup_alternative(self):
        """A ``$ref`` to a table without data-plane rows names ``$lookup`` as the alternative."""
        engine = db_engine()
        engine._connection = FakeConnection()

        with pytest.raises(RuntimeError, match=r"no rows of \"customers\" were applied.*through \$lookup"):
            engine._execute(insert_op([{"customer_id": {"$ref": "customers.0.id"}}]))

    def test_ref_with_an_out_of_range_index_names_the_applied_row_count(self):
        """An out-of-range ``$ref`` index names how many rows the table holds."""
        engine = db_engine()
        engine._connection = FakeConnection()
        engine._symbols["customers"] = [{"id": 42}]

        with pytest.raises(RuntimeError, match=r'"customers" holds 1 applied row\(s\)'):
            engine._execute(insert_op([{"customer_id": {"$ref": "customers.3.id"}}]))

    def test_ref_to_an_absent_column_names_the_row_columns(self):
        """A ``$ref`` to a column the captured row lacks names the available columns."""
        engine = db_engine()
        engine._connection = FakeConnection()
        engine._symbols["customers"] = [{"id": 42, "name": "Ann"}]

        with pytest.raises(RuntimeError, match=r'no column "email" \(columns: id, name\)'):
            engine._execute(insert_op([{"customer_id": {"$ref": "customers.0.email"}}]))

    def test_lookup_builds_a_parameterized_match_query_with_limit_two(self):
        """A ``$lookup`` runs one parameterized match query capped at two matches."""
        engine = db_engine()
        connection = FakeConnection(result_sets=[[(42,)]], row_queue=[{"id": 100, "customer_id": 42}])
        engine._connection = connection

        engine._execute(
            insert_op(
                [{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "a@x.io"}, "column": "id"}}}]
            )
        )

        assert connection.statements[1][1] == ('SELECT "id" FROM "customers" WHERE "email" = %s LIMIT 2')
        assert connection.statements[1][2] == ("a@x.io",)

    def test_lookup_discovers_the_primary_key_from_the_catalog(self):
        """Without an explicit column the lookup resolves the table's primary key first."""
        engine = db_engine()
        connection = FakeConnection(result_sets=[[("id",)], [(42,)]], row_queue=[{"id": 100, "customer_id": 42}])
        engine._connection = connection

        engine._execute(insert_op([{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "a@x.io"}}}}]))

        assert connection.statements[1][1].startswith("SELECT kcu.column_name")
        assert connection.statements[1][2] == ("customers",)
        assert connection.statements[2][1] == 'SELECT "id" FROM "customers" WHERE "email" = %s LIMIT 2'

    def test_lookup_with_an_explicit_column_skips_the_primary_key_discovery(self):
        """An explicit ``column`` resolves without the catalog query."""
        engine = db_engine()
        connection = FakeConnection(result_sets=[[(42,)]], row_queue=[{"id": 100, "customer_id": 42}])
        engine._connection = connection

        engine._execute(
            insert_op(
                [{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "a@x.io"}, "column": "uid"}}}]
            )
        )

        assert connection.statements[1][1] == 'SELECT "uid" FROM "customers" WHERE "email" = %s LIMIT 2'

    def test_lookup_matching_no_row_fails_naming_the_missing_precondition(self):
        """A ``$lookup`` matching no row names the missing precondition data."""
        engine = db_engine()
        connection = FakeConnection(result_sets=[[("id",)], []])
        engine._connection = connection

        with pytest.raises(RuntimeError, match=r"matched no row — the precondition data is missing"):
            engine._execute(
                insert_op([{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "a@x.io"}}}}])
            )

    def test_lookup_matching_several_rows_fails_naming_the_ambiguity(self):
        """A ``$lookup`` matching more than one row names the ambiguity."""
        engine = db_engine()
        connection = FakeConnection(result_sets=[[("id",)], [(1,), (2,)]])
        engine._connection = connection

        with pytest.raises(RuntimeError, match=r"matched 2 rows"):
            engine._execute(
                insert_op([{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "a@x.io"}}}}])
            )

    def test_lookup_without_a_primary_key_fails_asking_for_the_column(self):
        """A ``$lookup`` on a table without a discoverable primary key asks for ``column``."""
        engine = db_engine()
        connection = FakeConnection(result_sets=[[]])
        engine._connection = connection

        with pytest.raises(RuntimeError, match=r'found no primary key — pass an explicit "column"'):
            engine._execute(
                insert_op([{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "a@x.io"}}}}])
            )

    def test_lookup_with_a_composite_primary_key_fails_naming_the_candidates(self):
        """A composite primary key surfaces its candidate columns for an explicit choice."""
        engine = db_engine()
        connection = FakeConnection(result_sets=[[("a",), ("b",)], []])
        engine._connection = connection

        with pytest.raises(RuntimeError, match=r"several primary-key candidates \(\"a\", \"b\"\)"):
            engine._execute(
                insert_op([{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "a@x.io"}}}}])
            )

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

    def test_wipe_clears_the_symbol_stream_with_the_tables(self):
        """Wipe clears the symbol stream — the addressed rows are gone after the truncate."""
        engine = db_engine()
        connection = FakeConnection(catalog=[("public", "orders")])
        engine._connection = connection
        engine._symbols["orders"] = [{"id": 1}]

        engine._wipe()

        assert engine._symbols == {}

    def test_wipe_clears_the_symbol_stream_even_without_user_tables(self):
        """The replay-only wipe clears the symbol stream too."""
        engine = db_engine()
        connection = FakeConnection(catalog=[])
        engine._connection = connection
        engine._symbols["orders"] = [{"id": 1}]

        engine._wipe()

        assert engine._symbols == {}


def schema_ops() -> list[DataOperation]:
    """Build the sample customers/orders schema as startup sql operations.

    Returns:
        The idempotent schema statements — serial primary keys, one foreign-key reference.
    """
    return [
        sql_op("CREATE TABLE IF NOT EXISTS customers (id bigserial PRIMARY KEY, name text, email text UNIQUE)"),
        sql_op(
            "CREATE TABLE IF NOT EXISTS orders ("
            "id bigserial PRIMARY KEY, customer_id bigint REFERENCES customers(id), total int)"
        ),
    ]


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

    def fetch_pairs(self, engine: PostgresEngine, query: str) -> list[tuple[object, ...]]:
        """Read arbitrary joined rows through the engine connection.

        Args:
            engine: The started engine whose connection runs the query.
            query: The SELECT to run.

        Returns:
            Every row of the query result.
        """
        with engine._connection.cursor() as cursor:
            cursor.execute(query)

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

    def test_ref_resolves_the_generated_parent_key(self):
        """A ``$ref`` carries the serial-generated parent key into the child insert."""
        engine = db_engine()
        engine.start(schema_ops())

        try:
            engine.apply([insert_op([{"name": "Ann", "email": "ann@x.io"}], table="customers")])
            engine.apply([insert_op([{"customer_id": {"$ref": "customers.0.id"}, "total": 500}], table="orders")])

            assert self.fetch_pairs(
                engine, "SELECT o.total, c.name FROM orders o JOIN customers c ON c.id = o.customer_id"
            ) == [(500, "Ann")]
        finally:
            engine.stop()

    def test_ref_rebuilds_and_re_resolves_on_reset_replay(self):
        """Reset rebuilds the symbol stream and the journaled ``$ref`` re-resolves."""
        engine = db_engine()
        engine.start(schema_ops())

        try:
            engine.apply([insert_op([{"name": "Ann", "email": "ann@x.io"}], table="customers")])
            engine.apply([insert_op([{"customer_id": {"$ref": "customers.0.id"}, "total": 5}], table="orders")])
            engine.record([insert_op([{"name": "Ann", "email": "ann@x.io"}], table="customers")])

            engine.reset()

            assert engine._symbols["customers"] == [{"id": 1, "name": "Ann", "email": "ann@x.io"}]

            engine.apply([insert_op([{"customer_id": {"$ref": "customers.0.id"}, "total": 7}], table="orders")])

            assert self.fetch_pairs(engine, "SELECT total, customer_id FROM orders") == [(7, 1)]
        finally:
            engine.stop()

    def test_lookup_resolves_rows_created_outside_the_data_plane(self):
        """A ``$lookup`` matches rows created by raw sql — the service-created case."""
        engine = db_engine()
        engine.start(schema_ops())

        try:
            engine.apply([sql_op("INSERT INTO customers (name, email) VALUES ('Service', 'svc@x.io')")])
            engine.apply(
                [
                    insert_op(
                        [
                            {
                                "customer_id": {"$lookup": {"table": "customers", "where": {"email": "svc@x.io"}}},
                                "total": 9,
                            }
                        ],
                        table="orders",
                    )
                ]
            )

            assert self.fetch_pairs(
                engine, "SELECT o.total, c.name FROM orders o JOIN customers c ON c.id = o.customer_id"
            ) == [(9, "Service")]
        finally:
            engine.stop()

    def test_lookup_with_an_explicit_column_resolves_the_named_column(self):
        """A ``$lookup`` with ``column`` resolves the named column without PK discovery."""
        engine = db_engine()
        engine.start(schema_ops())

        try:
            engine.apply([insert_op([{"name": "Ann", "email": "ann@x.io"}], table="customers")])
            engine.apply(
                [
                    insert_op(
                        [
                            {
                                "customer_id": {
                                    "$lookup": {"table": "customers", "where": {"email": "ann@x.io"}, "column": "id"}
                                },
                                "total": 3,
                            }
                        ],
                        table="orders",
                    )
                ]
            )

            assert self.fetch_pairs(engine, "SELECT total, customer_id FROM orders") == [(3, 1)]
        finally:
            engine.stop()

    def test_lookup_matching_no_row_fails_readably(self):
        """A ``$lookup`` matching no row surfaces as a readable engine error."""
        engine = db_engine()
        engine.start(schema_ops())

        try:
            with pytest.raises(EngineError, match=r"matched no row — the precondition data is missing"):
                engine.apply(
                    [
                        insert_op(
                            [{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "none@x.io"}}}}],
                            table="orders",
                        )
                    ]
                )
        finally:
            engine.stop()

    def test_lookup_matching_several_rows_fails_readably(self):
        """A ``$lookup`` matching several rows surfaces the ambiguity."""
        engine = db_engine()
        engine.start(schema_ops())

        try:
            engine.apply([insert_op([{"name": "Sam"}, {"name": "Sam"}], table="customers")])

            with pytest.raises(EngineError, match=r"matched 2 rows"):
                engine.apply(
                    [
                        insert_op(
                            [{"customer_id": {"$lookup": {"table": "customers", "where": {"name": "Sam"}}}}],
                            table="orders",
                        )
                    ]
                )
        finally:
            engine.stop()

    def test_intra_operation_ref_references_the_earlier_row(self):
        """A later row of one insert resolves a reference to an earlier row of the same insert."""
        engine = db_engine()
        engine.start(
            [
                sql_op(
                    "CREATE TABLE IF NOT EXISTS staff "
                    "(id bigserial PRIMARY KEY, name text, boss_id bigint REFERENCES staff(id))"
                )
            ]
        )

        try:
            engine.apply(
                [
                    insert_op(
                        [{"name": "Chief", "boss_id": None}, {"name": "Ann", "boss_id": {"$ref": "staff.0.id"}}],
                        table="staff",
                    )
                ]
            )

            assert self.fetch_pairs(
                engine,
                "SELECT s.name, b.name FROM staff s JOIN staff b ON b.id = s.boss_id",
            ) == [("Ann", "Chief")]
        finally:
            engine.stop()

    def test_failing_row_leaves_nothing_applied(self):
        """One transaction per insert — a failing later row rolls the earlier rows back."""
        engine = db_engine()
        engine.start(schema_ops())

        try:
            with pytest.raises(EngineError, match="duplicate key"):
                engine.apply(
                    [
                        insert_op(
                            [
                                {"name": "Ann", "email": "ann@x.io"},
                                {"name": "Ann", "email": "ann@x.io"},
                            ],
                            table="customers",
                        )
                    ]
                )

            assert self.fetch_pairs(engine, "SELECT count(*) FROM customers") == [(0,)]
            assert engine._symbols == {}
        finally:
            engine.stop()
