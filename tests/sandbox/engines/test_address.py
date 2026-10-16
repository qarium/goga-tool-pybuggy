"""Contract and logic tests for the ``InstanceAddress`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.engines import InstanceAddress
from pydantic import BaseModel


class TestInstanceAddressContract:
    """Declared API of the ``InstanceAddress`` entity."""

    def test_instance_address_is_importable_from_engines_facade(self):
        """``InstanceAddress`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert InstanceAddress is not None

    def test_instance_address_is_a_pydantic_model(self):
        """``InstanceAddress`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(InstanceAddress, BaseModel)

    def test_instance_address_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(InstanceAddress)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_instance_address_declares_the_contract_fields(self):
        """The model declares the ``host`` and ``port`` fields only."""
        assert set(InstanceAddress.model_fields) == {"host", "port"}

    def test_instance_address_properties_return_declared_types(self):
        """Construction with a mapped address exposes the declared property types."""
        address = InstanceAddress(host="127.0.0.1", port=54329)

        assert isinstance(address.host, str)
        assert isinstance(address.port, int)


class TestInstanceAddressLogic:
    """Construction behavior of ``InstanceAddress``."""

    def test_instance_address_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            InstanceAddress("127.0.0.1", 54329)  # type: ignore[misc]

    def test_instance_address_carries_the_published_host_port(self):
        """The port carries the published host-side port read back from the container engine."""
        address = InstanceAddress(host="192.168.65.2", port=49153)

        assert address.host == "192.168.65.2"
        assert address.port == 49153
