"""Contract and logic tests for the ``RedisInstance`` view."""

import inspect

from goga_tool_pybuggy.sandbox import data as data_facade
from goga_tool_pybuggy.sandbox.data import DataBatch, RedisInstance
from goga_tool_pybuggy.sandbox.engines import InstanceAddress

from .conftest import RecordingBatch


class TestRedisInstanceContract:
    """Declared API of the ``RedisInstance`` entity."""

    def test_redis_instance_is_importable_from_the_data_facade(self):
        """``RedisInstance`` is re-exported by the ``goga_tool_pybuggy.sandbox.data`` facade."""
        assert "RedisInstance" in data_facade.__all__
        assert data_facade.RedisInstance is RedisInstance

    def test_redis_instance_constructor_declares_the_contract_parameters(self):
        """The constructor takes ``name``, ``address`` and ``batch`` with the declared types."""
        parameters = inspect.signature(RedisInstance.__init__).parameters

        assert list(parameters) == ["self", "name", "address", "batch"]
        assert parameters["name"].annotation is str
        assert parameters["address"].annotation is InstanceAddress
        assert parameters["batch"].annotation is DataBatch

    def test_redis_instance_declares_the_contract_properties(self):
        """The class exposes ``name``, ``host`` and ``port`` as read-only properties."""
        for property_name in ("name", "host", "port"):
            attribute = inspect.getattr_static(RedisInstance, property_name)

            assert isinstance(attribute, property), property_name

    def test_redis_instance_declares_the_four_declaring_methods(self):
        """The class exposes ``set``, ``hset``, ``rpush`` and ``sadd`` with the contract signatures."""
        expected = {
            "set": (["self", "key", "value"], {"key": str, "value": object}),
            "hset": (["self", "key", "values"], {"key": str, "values": dict[str, object]}),
            "rpush": (["self", "key", "values"], {"key": str, "values": list[object]}),
            "sadd": (["self", "key", "members"], {"key": str, "members": list[object]}),
        }

        for method_name, (parameter_names, annotations) in expected.items():
            parameters = inspect.signature(getattr(RedisInstance, method_name)).parameters

            assert list(parameters) == parameter_names, method_name

            for parameter_name, annotation in annotations.items():
                assert parameters[parameter_name].annotation == annotation, f"{method_name}.{parameter_name}"


class TestRedisInstanceLogic:
    """Declaration behavior of the ``RedisInstance`` view."""

    def test_redis_view_declares_the_four_operations(self, recording_batch: RecordingBatch):
        """The four view methods declare one redis operation each with the contract payloads."""
        address = InstanceAddress(host="127.0.0.2", port=16379)
        view = RedisInstance(name="cache", address=address, batch=recording_batch)

        view.set("k", "v")
        view.hset("h", {"f": 1})
        view.rpush("l", [1, 2])
        view.sadd("s", ["a"])

        drained = recording_batch.take()

        assert [(operation.action, operation.payload) for operation in drained] == [
            ("set", {"key": "k", "value": "v"}),
            ("hset", {"key": "h", "values": {"f": 1}}),
            ("rpush", {"key": "l", "values": [1, 2]}),
            ("sadd", {"key": "s", "members": ["a"]}),
        ]

        assert all(operation.instance == "cache" for operation in drained)
        assert all(operation.kind == "redis" for operation in drained)

        assert (view.name, view.host, view.port) == ("cache", "127.0.0.2", 16379)

        assert recording_batch.take() == []

    def test_redis_view_rides_non_string_values_as_given(self, recording_batch: RecordingBatch):
        """A non-string value rides in the payload as given — serialization is execution-time."""
        address = InstanceAddress(host="127.0.0.2", port=16379)
        view = RedisInstance(name="cache", address=address, batch=recording_batch)

        view.set("feature-flag/a", {"on": True})

        operation = recording_batch.take()[0]

        assert operation.payload == {"key": "feature-flag/a", "value": {"on": True}}

    def test_repeated_declarations_accumulate_in_call_order(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """Several declarations accumulate in call order — one operation each."""
        view = RedisInstance(name="cache", address=address, batch=recording_batch)

        view.rpush("queue:orders", [{"id": 1}])
        view.rpush("queue:orders", ["tail"])

        assert [operation.payload["values"] for operation in recording_batch.added] == [[{"id": 1}], ["tail"]]
