"""PostgresInstance entity: test-facing view of a started postgresql instance."""

from ..engines import DataOperation, InstanceAddress, validate_insert_rows
from .batch import DataBatch


class PostgresInstance:
    """Test-facing view of a started postgresql instance.

    The view declares row inserts into the mapped instance — nothing executes at
    declaration time. The declared operation joins the batch and the session facade
    applies it right before the first call to the service under test.

    Attributes:
        name: The configured instance name.
        host: The mapped host — the value the service env placeholders resolve to.
        port: The published port — the value the service env placeholders resolve to.
    """

    def __init__(self, name: str, address: InstanceAddress, batch: DataBatch) -> None:
        """Initialize the view of one started postgresql instance.

        Args:
            name: The instance name from the sandbox configuration.
            address: The mapped address of the started instance.
            batch: The accumulation target of declared operations.
        """
        self._name = name
        self._address = address
        self._batch = batch

    @property
    def name(self) -> str:
        """The configured instance name."""
        return self._name

    @property
    def host(self) -> str:
        """The mapped host — the value the service env placeholders resolve to."""
        return self._address.host

    @property
    def port(self) -> int:
        """The published port — the value the service env placeholders resolve to."""
        return self._address.port

    def insert(self, table: str, rows: list[dict[str, object]]) -> None:
        """Declare row inserts into one table.

        One call targets one table; rows apply in list order. Foreign-key chains across
        tables follow the declaration order — parents first — while generated parent keys
        resolve through row values: ``$ref`` addresses the data plane's own applied rows,
        ``$lookup`` matches the current database state.

        Args:
            table: The target table.
            rows: The rows to insert, in order.

        Raises:
            ValueError: A row value carries a malformed ``$ref`` / ``$lookup`` reference.
        """
        validate_insert_rows(rows, context=f"table '{table}'")

        operation = DataOperation(
            instance=self._name,
            kind="postgresql",
            action="insert",
            payload={"table": table, "rows": rows},
        )

        self._batch.add(operation)
