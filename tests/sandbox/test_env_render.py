"""Contract and logic tests for the ``render_service_env`` routine."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.engines import InstanceAddress


class TestRenderServiceEnvContract:
    """Declared API of the ``render_service_env`` routine."""

    def test_render_service_env_is_importable_from_env_render_module(self):
        """``render_service_env`` lives in ``goga_tool_pybuggy.sandbox.env_render``."""
        from goga_tool_pybuggy.sandbox.env_render import render_service_env

        assert callable(render_service_env)

    def test_render_service_env_signature_takes_env_and_addresses(self):
        """The routine takes ``env`` and ``addresses`` as its two parameters."""
        from goga_tool_pybuggy.sandbox.env_render import render_service_env

        parameters = list(inspect.signature(render_service_env).parameters)

        assert parameters == ["env", "addresses"]

    def test_render_service_env_returns_a_string_dict(self):
        """The routine returns a plain ``dict`` mapping env keys to rendered strings."""
        from goga_tool_pybuggy.sandbox.env_render import render_service_env

        addresses = {"db": InstanceAddress(host="127.0.0.2", port=5432)}
        rendered = render_service_env({"DATABASE_URL": "postgres://{{db.host}}:{{db.port}}/test"}, addresses)

        assert isinstance(rendered, dict)
        assert isinstance(rendered["DATABASE_URL"], str)


class TestRenderServiceEnvLogic:
    """Rendering behavior of the service env values."""

    def test_render_service_env_resolves_placeholders(self):
        """``{{<name>.host}}`` / ``{{<name>.port}}`` render from the mapped addresses."""
        from goga_tool_pybuggy.sandbox.env_render import render_service_env

        env = {"DATABASE_URL": "postgres://{{db.host}}:{{db.port}}/test", "PLAIN": "no-placeholders"}
        addresses = {"db": InstanceAddress(host="127.0.0.2", port=5432)}

        rendered = render_service_env(env, addresses)

        assert rendered["DATABASE_URL"] == "postgres://127.0.0.2:5432/test"
        assert rendered["PLAIN"] == "no-placeholders"

    def test_render_service_env_empty_env_returns_empty_dict(self):
        """An empty env renders to an empty dict — nothing to resolve."""
        from goga_tool_pybuggy.sandbox.env_render import render_service_env

        assert render_service_env({}, {}) == {}

    def test_render_service_env_keeps_value_whitespace_untouched(self):
        """Env values are not URLs — literal whitespace survives the render."""
        from goga_tool_pybuggy.sandbox.env_render import render_service_env

        addresses = {"db": InstanceAddress(host="127.0.0.2", port=5432)}

        rendered = render_service_env({"BANNER": "hello  {{db.host}}  world"}, addresses)

        assert rendered["BANNER"] == "hello  127.0.0.2  world"

    def test_render_service_env_fails_unknown_placeholder_naming_key_and_value(self):
        """An unknown placeholder fails naming the env key and the offending value."""
        from goga_tool_pybuggy.sandbox.env_render import render_service_env

        value = "postgres://{{ghost.host}}:{{ghost.port}}/x"
        addresses = {"db": InstanceAddress(host="127.0.0.2", port=5432)}

        with pytest.raises(ValueError, match=r"DATABASE_URL.*ghost\.host"):
            render_service_env({"DATABASE_URL": value}, addresses)

    def test_render_service_env_fails_unknown_attribute_naming_key_and_value(self):
        """An unknown attribute of a configured instance fails naming the env key."""
        from goga_tool_pybuggy.sandbox.env_render import render_service_env

        value = "{{db.hst}}"
        addresses = {"db": InstanceAddress(host="127.0.0.2", port=5432)}

        with pytest.raises(ValueError, match=r"DATABASE_URL.*db\.hst"):
            render_service_env({"DATABASE_URL": value}, addresses)
