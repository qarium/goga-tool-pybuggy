"""KafkaInstance entity: test-facing view of a started kafka service."""

from ..engines import DataOperation, InstanceAddress
from .batch import DataBatch


class KafkaInstance:
    """Test-facing view of a started kafka service.

    The view declares message produces into the mapped service — nothing executes at
    declaration time. The declared operation joins the batch and the session facade
    applies it right before the first call to the service under test.

    Attributes:
        name: The configured service name.
        host: The mapped host — the value the env placeholders of the instance under test resolve to.
        port: The published port — the value the env placeholders of the instance under test resolve to.
    """

    def __init__(self, name: str, address: InstanceAddress, batch: DataBatch) -> None:
        """Initialize the view of one started kafka service.

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

    def produce(self, topic: str, value: dict[str, object] | str, key: str | None = None) -> None:
        """Declare one message produce.

        Args:
            topic: The target topic — it must be declared on the kafka service entry of the
                sandbox document.
            value: The message value.
            key: The optional partition key.
        """
        operation = DataOperation(
            instance=self._name,
            kind="kafka",
            action="produce",
            payload={"topic": topic, "value": value, "key": key},
        )

        self._batch.add(operation)
