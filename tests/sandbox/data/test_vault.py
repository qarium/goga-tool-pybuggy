"""Contract and logic tests for the ``VaultInstance`` view."""

import inspect

from goga_tool_pybuggy.sandbox.data import DataBatch, VaultInstance
from goga_tool_pybuggy.sandbox.engines import InstanceAddress

from .conftest import RecordingBatch


class TestVaultInstanceContract:
    """Declared API of the ``VaultInstance`` entity."""

    def test_vault_instance_is_importable_from_data_facade(self):
        """``VaultInstance`` is re-exported by the ``goga_tool_pybuggy.sandbox.data`` facade."""
        assert VaultInstance is not None

    def test_vault_instance_constructor_declares_the_contract_parameters(self):
        """The constructor takes ``name``, ``address`` and ``batch`` with the declared types."""
        parameters = inspect.signature(VaultInstance.__init__).parameters

        assert list(parameters) == ["self", "name", "address", "batch"]
        assert parameters["name"].annotation is str
        assert parameters["address"].annotation is InstanceAddress
        assert parameters["batch"].annotation is DataBatch

    def test_vault_instance_declares_the_contract_properties(self):
        """The class exposes ``name``, ``host`` and ``port`` as read-only properties."""
        for property_name in ("name", "host", "port"):
            attribute = inspect.getattr_static(VaultInstance, property_name)

            assert isinstance(attribute, property), property_name

    def test_vault_instance_declares_the_one_declaring_method(self):
        """The class exposes exactly one declaring method — ``put(path, data)``."""
        parameters = inspect.signature(VaultInstance.put).parameters

        assert list(parameters) == ["self", "path", "data"]
        assert parameters["path"].annotation is str
        assert parameters["data"].annotation == dict[str, object]


class TestVaultInstanceLogic:
    """Declaration behavior of the ``VaultInstance`` view."""

    def test_put_appends_exactly_one_operation_with_the_payload_table_shape(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """One ``put`` call declares one vault put operation carrying path and data."""
        view = VaultInstance(name="secrets", address=address, batch=recording_batch)

        view.put("payment/api-key", {"api_key": "test-key"})

        assert len(recording_batch.added) == 1

        operation = recording_batch.added[0]

        assert operation.instance == "secrets"
        assert operation.kind == "vault"
        assert operation.action == "put"
        assert operation.payload == {"path": "payment/api-key", "data": {"api_key": "test-key"}}

    def test_properties_read_from_name_and_address(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """``name`` comes from construction; ``host`` and ``port`` read through the address."""
        view = VaultInstance(name="secrets", address=address, batch=recording_batch)

        assert view.name == "secrets"
        assert view.host == "127.0.0.5"
        assert view.port == 5432

    def test_put_declares_only_the_batch_executes_nothing(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """The declaration only accumulates — the batch still holds it for a later drain."""
        view = VaultInstance(name="secrets", address=address, batch=recording_batch)

        view.put("payment/api-key", {"api_key": "test-key"})

        assert recording_batch.take() == recording_batch.added
        assert recording_batch.take() == []

    def test_put_passes_data_through_untouched(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """The secret data passes through as given — the payload is the author's data."""
        data: dict[str, object] = {"api_key": "k", "nested": {"a": [1, 2]}}
        view = VaultInstance(name="secrets", address=address, batch=recording_batch)

        view.put("payment/api-key", data)

        assert recording_batch.added[0].payload["data"] == data

    def test_put_with_empty_data_still_declares(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """An empty data dict is a valid edge declaration."""
        view = VaultInstance(name="secrets", address=address, batch=recording_batch)

        view.put("empty/secret", {})

        assert recording_batch.added[0].payload == {"path": "empty/secret", "data": {}}
