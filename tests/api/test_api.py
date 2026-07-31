"""Contract and logic tests for `goga_tool_pybuggy.api.api`.

Contract tests (``TestApi``) lock the facade/API shape: importability,
construction, the set of stored-field properties, the read-only nature of
``data_key``/``error_key``, the read/write ``auth`` property, and the ``request``
signature. Logic tests (``TestApiProperties``) cover the property values and
defaults. ``request`` serialization behavior (pydantic dump, ``:name``
substitution, headers/cookies merge, auth precedence, verb dispatch) is asserted
in ``tests/api/test_api_request.py``.
"""

from __future__ import annotations

import inspect
from unittest import mock

import pytest
from goga_tool_pybuggy.api.api import Api
from requests.auth import AuthBase

from tests.api.conftest import HeaderAuth


class TestApi:
    """Contract tests for the `Api` facade/API shape."""

    def test_imports_succeed(self) -> None:
        """Api is importable from goga_tool_pybuggy.api.api."""
        assert isinstance(Api, type)

    def test_constructs_with_keys(self) -> None:
        """Api stores the given data_key/error_key."""
        api = Api(base_url="https://x", data_key="d", error_key="e")

        assert api.data_key == "d"
        assert api.error_key == "e"

    def test_data_key_error_key_default_to_none(self) -> None:
        """Api defaults data_key/error_key to None when omitted."""
        api = Api(base_url="https://x")

        assert api.data_key is None
        assert api.error_key is None

    def test_properties_present(self) -> None:
        """All stored-field properties are exposed on the facade."""
        api = Api(base_url="https://x")

        for name in ("base_url", "auth", "headers", "cookies", "data_key", "error_key"):
            assert hasattr(api, name)

    def test_data_key_is_read_only(self) -> None:
        """data_key has no setter: assignment raises AttributeError."""
        api = Api(base_url="https://x")

        with pytest.raises(AttributeError):
            api.data_key = "x"

    def test_error_key_is_read_only(self) -> None:
        """error_key has no setter: assignment raises AttributeError."""
        api = Api(base_url="https://x")

        with pytest.raises(AttributeError):
            api.error_key = "x"

    def test_auth_is_read_write(self) -> None:
        """auth is read/write: the setter updates and the getter returns it."""
        api = Api(base_url="https://x")
        sentinel = HeaderAuth("X-Auth", "1")

        api.auth = sentinel

        assert api.auth is sentinel

    def test_request_signature(self) -> None:
        """request has the (method, url_path, **kwargs) signature."""
        params = inspect.signature(Api.request).parameters

        assert "method" in params
        assert "url_path" in params
        assert params["kwargs"].kind == inspect.Parameter.VAR_KEYWORD

    def test_composes_resq_session(self) -> None:
        """Api composes a resq.Session exposing the base_url."""
        api = Api(base_url="https://x")

        assert api.base_url == "https://x"


class TestApiProperties:
    """Logic tests for the stored-field properties and defaults."""

    def test_base_url_returns_session_base_url(self) -> None:
        """base_url mirrors the underlying resq.Session base_url."""
        api = Api(base_url="https://api.example.com")

        assert api.base_url == "https://api.example.com"

    def test_data_key_returns_stored_value(self) -> None:
        """data_key returns the value passed at construction."""
        api = Api(base_url="https://x", data_key="payload")

        assert api.data_key == "payload"

    def test_error_key_returns_stored_value(self) -> None:
        """error_key returns the value passed at construction."""
        api = Api(base_url="https://x", error_key="errors")

        assert api.error_key == "errors"

    def test_data_key_defaults_to_none(self) -> None:
        """data_key defaults to None."""
        assert Api(base_url="https://x").data_key is None

    def test_error_key_defaults_to_none(self) -> None:
        """error_key defaults to None."""
        assert Api(base_url="https://x").error_key is None

    def test_assert_options_return_stored_values(self) -> None:
        """The assert-polling / pluggable-class options are exposed read-only."""
        api = Api(
            base_url="https://x",
            assert_timeout=12,
            assert_delay=0.25,
            assert_field_class="mod:FieldCls",
            assert_response_class="mod:ResponseCls",
        )

        assert api.assert_timeout == 12
        assert api.assert_delay == 0.25
        assert api.assert_field_class == "mod:FieldCls"
        assert api.assert_response_class == "mod:ResponseCls"

    def test_assert_options_default_to_none(self) -> None:
        """The assert-polling / pluggable-class options default to None."""
        api = Api(base_url="https://x")

        assert api.assert_timeout is None
        assert api.assert_delay is None
        assert api.assert_field_class is None
        assert api.assert_response_class is None

    def test_auth_setter_updates_auth(self) -> None:
        """Assigning auth updates the stored authenticator."""
        api = Api(base_url="https://x")
        assert api.auth is None

        auth = HeaderAuth("X-Token", "abc")
        api.auth = auth

        assert api.auth is auth
        assert isinstance(api.auth, AuthBase)

    def test_headers_defaults_to_empty_dict(self) -> None:
        """headers defaults to an empty dict when none are given."""
        api = Api(base_url="https://x")

        assert api.headers == {}

    def test_headers_returns_stored_mapping(self) -> None:
        """headers returns the mapping passed at construction."""
        api = Api(base_url="https://x", headers={"Accept": "application/json"})

        assert api.headers == {"Accept": "application/json"}

    def test_cookies_none_by_default(self) -> None:
        """cookies default to None."""
        assert Api(base_url="https://x").cookies is None


class TestApiClose:
    """Contract + behavior tests for `Api.close()`.

    `close()` tears down the composed `resq.Session` by closing its held
    `requests.Session` (the sync connection pool). `resq.Session` exposes no
    public sync `close()`, so `Api` reaches the held session directly — these
    tests pin that contract: `close` is callable and delegates to
    `resq.Session._session.close()`.
    """

    def test_close_is_callable_method(self) -> None:
        """Api exposes a callable close()."""
        api = Api(base_url="https://x")

        assert callable(api.close)

    def test_close_delegates_to_resq_session(self) -> None:
        """close() closes the held requests.Session of the resq.Session."""
        api = Api(base_url="https://x")

        with mock.patch.object(api._client._session, "close") as session_close:
            api.close()

        session_close.assert_called_once_with()

    def test_close_is_idempotent(self) -> None:
        """close() may be called more than once without raising."""
        api = Api(base_url="https://x")

        api.close()
        api.close()  # second close — requests.Session.close is idempotent
