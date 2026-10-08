"""HttpInstance entity: test-facing view of a started http service."""

from ..engines import DataOperation, InstanceAddress
from .batch import DataBatch


class HttpInstance:
    """Test-facing view of a started http service.

    The view declares stub mappings into the mapped service — nothing executes at
    declaration time. The declared operation joins the batch and the session facade
    applies it right before the first call to the service under test.

    Attributes:
        name: The configured service name.
        host: The mapped host — the value the env placeholders of the instance under test resolve to.
        port: The published port — the value the env placeholders of the instance under test resolve to.
    """

    def __init__(self, name: str, address: InstanceAddress, batch: DataBatch) -> None:
        """Initialize the view of one started http service.

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

    def stub(self, mapping: dict[str, object]) -> None:
        """Declare one stub mapping.

        Matching, priority, delays, and faults pass through as given — the mapping is
        the operation payload, untouched.

        Args:
            mapping: The mapping object of the http mock.
        """
        operation = DataOperation(
            instance=self._name,
            kind="http",
            action="stub",
            payload=mapping,
        )

        self._batch.add(operation)
