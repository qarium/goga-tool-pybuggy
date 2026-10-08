"""Shared doubles of the migrations cell tests — the psycopg execution seam.

The doubles mirror the fake family of ``tests/sandbox/engines/test_postgres.py``: the
connection records every ``transaction`` / ``execute`` call as a ``(kind, payload, params)``
tuple, so the apply tests assert execution shape and ordering against the records; the
failing variants raise the driver-shaped statement error on every execute.
"""

import psycopg


class FakeCursor:
    """Cursor double recording every executed statement on its connection."""

    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        return False

    def execute(self, sql: str, params: object = None) -> None:
        self._connection.statements.append(("execute", sql, params))


class FakeTransaction:
    """Transaction double recording the begin/commit/rollback markers of one block."""

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
    """Connection double of the postgres session plane — records statements."""

    def __init__(self) -> None:
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
