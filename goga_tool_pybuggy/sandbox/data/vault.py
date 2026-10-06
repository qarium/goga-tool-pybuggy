"""VaultInstance entity: test-facing view of a started vault instance."""

from ..engines import DataOperation, InstanceAddress
from .batch import DataBatch


class VaultInstance:
    """Test-facing view of a started vault instance.

    The view declares secret writes into the mapped instance — nothing executes at
    declaration time. The declared operation joins the batch and the session facade
    applies it right before the first call to the service under test.

    Attributes:
        name: The configured instance name.
        host: The mapped host — the value the service env placeholders resolve to.
        port: The published port — the value the service env placeholders resolve to.
    """

    def __init__(self, name: str, address: InstanceAddress, batch: DataBatch) -> None:
        """Initialize the view of one started vault instance.

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

    def put(self, path: str, data: dict[str, object]) -> None:
        """Declare one secret write.

        Args:
            path: The secret path.
            data: The secret data.
        """
        operation = DataOperation(
            instance=self._name,
            kind="vault",
            action="put",
            payload={"path": path, "data": data},
        )

        self._batch.add(operation)
