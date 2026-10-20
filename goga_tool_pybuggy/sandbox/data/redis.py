"""RedisInstance entity: test-facing view of a started redis service."""

from ..engines import DataOperation, InstanceAddress
from .batch import DataBatch


class RedisInstance:
    """Test-facing view of a started redis service.

    The view declares data writes into the mapped service — nothing executes at
    declaration time. The declared operation joins the batch and the session facade
    applies it right before the first call to the service under test.

    Attributes:
        name: The configured service name.
        host: The mapped host — the value the env placeholders of the instance under test resolve to.
        port: The published port — the value the env placeholders of the instance under test resolve to.
    """

    def __init__(self, name: str, address: InstanceAddress, batch: DataBatch) -> None:
        """Initialize the view of one started redis service.

        Args:
            name: The service name from the sandbox document.
            address: The mapped address of the started service.
            batch: The accumulation target of declared operations.
        """
        self._name = name
        self._address = address
        self._batch = batch

    @property
    def name(self) -> str:
        """The configured service name."""
        return self._name

    @property
    def host(self) -> str:
        """The mapped host — the value the env placeholders of the instance under test resolve to."""
        return self._address.host

    @property
    def port(self) -> int:
        """The published port — the value the env placeholders of the instance under test resolve to."""
        return self._address.port

    def set(self, key: str, value: object) -> None:
        """Declare one string value write.

        The value is a string or JSON-serializable plain data, serialized at
        execution time; the declared payload is never rewritten.

        Args:
            key: The redis key to write.
            value: The value to store under the key.
        """
        operation = DataOperation(
            instance=self._name,
            kind="redis",
            action="set",
            payload={"key": key, "value": value},
        )

        self._batch.add(operation)

    def hset(self, key: str, values: dict[str, object]) -> None:
        """Declare one hash write.

        Args:
            key: The redis key of the hash.
            values: The field-to-value mapping to store under the key.
        """
        operation = DataOperation(
            instance=self._name,
            kind="redis",
            action="hset",
            payload={"key": key, "values": values},
        )

        self._batch.add(operation)

    def rpush(self, key: str, values: list[object]) -> None:
        """Declare one list tail append, in list order.

        Args:
            key: The redis key of the list.
            values: The values to append to the list tail, in order.
        """
        operation = DataOperation(
            instance=self._name,
            kind="redis",
            action="rpush",
            payload={"key": key, "values": values},
        )

        self._batch.add(operation)

    def sadd(self, key: str, members: list[object]) -> None:
        """Declare one set members add.

        Args:
            key: The redis key of the set.
            members: The members to add to the set.
        """
        operation = DataOperation(
            instance=self._name,
            kind="redis",
            action="sadd",
            payload={"key": key, "members": members},
        )

        self._batch.add(operation)
