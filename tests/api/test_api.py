"""Contract and logic tests for `goga_tool_pybuggy.api.api`.

``request`` serialization behavior is asserted in ``tests/api/test_api_request.py``.
"""

from __future__ import annotations

import inspect
from unittest import mock

import pytest
from goga_tool_pybuggy.api.api import Api
from requests.auth import AuthBase

from .conftest import BindTarget, HeaderAuth, PlainTarget, UrlTarget


class TestApi:
    """Contract tests for the `Api` facade/API shape."""

    def test_imports_succeed(self) -> None:
        """Api is importable from goga_tool_pybuggy.api.api."""
        assert isinstance(Api, type)

    def test_constructs_without_body_keys(self) -> None:
        """Api constructs with the base profile (no body-key parameters)."""
        api = Api(base_url="https://x")

        assert api.base_url == "https://x"

    def test_data_key_error_key_rejected(self) -> None:
        """The removed data_key/error_key parameters raise TypeError."""
        with pytest.raises(TypeError):
            Api(base_url="https://x", data_key="d")

        with pytest.raises(TypeError):
            Api(base_url="https://x", error_key="e")

    def test_expected_alias_absent(self) -> None:
        """The pre-1.0 Expected name is gone from the api facade and ResponseWrapper."""
        import goga_tool_pybuggy.api as api_facade

        assert "Expected" not in api_facade.__all__
        assert not hasattr(api_facade, "Expected")

        from goga_tool_pybuggy.api.response import ResponseWrapper

        assert not hasattr(ResponseWrapper, "expected")

    def test_properties_present(self) -> None:
        """All stored-field properties are exposed on the facade."""
        api = Api(base_url="https://x")

        for name in ("base_url", "auth", "headers", "cookies"):
            assert hasattr(api, name)

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

    def test_composes_sync_resq_session(self) -> None:
        """Api composes a resq.Session in sync mode (adapter='requests')."""
        api = Api(base_url="https://x")

        assert api._client.adapter == "requests"


class TestApiProperties:
    """Logic tests for the stored-field properties and defaults."""

    def test_base_url_returns_session_base_url(self) -> None:
        """base_url mirrors the underlying resq.Session base_url."""
        api = Api(base_url="https://api.example.com")

        assert api.base_url == "https://api.example.com"

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


class TestApiAdapter:
    """Contract + behavior tests for the resq adapter plumbing.

    ``Api`` validates the adapter name (sync-only) and resolves per-request sessions via ``_get_session``.
    """

    def test_adapter_defaults_to_requests(self) -> None:
        """Api defaults to the 'requests' (sync) adapter."""
        api = Api(base_url="https://x")

        assert api.adapter == "requests"

    def test_adapter_stored_from_construction(self) -> None:
        """Api exposes the adapter passed at construction."""
        api = Api(base_url="https://x", adapter="requests")

        assert api.adapter == "requests"

    def test_adapter_is_read_only(self) -> None:
        """adapter has no setter: assignment raises AttributeError."""
        api = Api(base_url="https://x")

        with pytest.raises(AttributeError):
            api.adapter = "requests"

    def test_default_session_built_with_adapter(self) -> None:
        """The composed _client session carries the default adapter."""
        api = Api(base_url="https://x")

        assert api._client.adapter == "requests"

    def test_httpx_adapter_rejected_at_construction(self) -> None:
        """Constructing with the async 'httpx' adapter raises ValueError (sync-only)."""
        with pytest.raises(ValueError, match="httpx"):
            Api(base_url="https://x", adapter="httpx")

    def test_unknown_adapter_rejected_at_construction(self) -> None:
        """Constructing with an unknown adapter raises ValueError."""
        with pytest.raises(ValueError, match="unsupported adapter"):
            Api(base_url="https://x", adapter="grpc")

    def test_get_session_returns_default_client_for_default_adapter(self) -> None:
        """_get_session returns the composed _client for the default adapter."""
        api = Api(base_url="https://x")

        assert api._get_session("requests") is api._client

    def test_get_session_rejects_httpx(self) -> None:
        """_get_session rejects the async 'httpx' adapter (sync-only)."""
        api = Api(base_url="https://x")

        with pytest.raises(ValueError, match="httpx"):
            api._get_session("httpx")

    def test_get_session_builds_and_caches_override(self) -> None:
        """_get_session builds (once) and caches a session for a non-default adapter.

        Validation is bypassed and ``resq.Session`` is patched to reach the build+cache path.
        """
        api = Api(base_url="https://x", timeout=5.0)
        fake_session = mock.Mock()

        with (
            mock.patch.object(api, "_validate_adapter"),
            mock.patch("goga_tool_pybuggy.api.api.resq.Session", return_value=fake_session) as session_cls,
        ):
            first = api._get_session("other")
            second = api._get_session("other")

        assert first is fake_session
        assert second is fake_session
        session_cls.assert_called_once_with("https://x", "other", timeout=5.0)
        assert api._sessions["other"] is fake_session


class TestApiClose:
    """Contract + behavior tests for `Api.close()`.

    In sync mode the delegated close is a no-op by resq's design; ``close`` is idempotent.
    """

    def test_close_is_callable_method(self) -> None:
        """Api exposes a callable close()."""
        api = Api(base_url="https://x")

        assert callable(api.close)

    def test_close_delegates_to_resq_session(self) -> None:
        """close() delegates to the public resq.Session.close()."""
        api = Api(base_url="https://x")

        with mock.patch.object(api._client, "close") as client_close:
            api.close()

        client_close.assert_called_once_with()

    def test_close_is_idempotent(self) -> None:
        """close() may be called more than once without raising."""
        api = Api(base_url="https://x")

        api.close()
        api.close()  # second close — requests.Session.close is idempotent


class _DiedTarget(BindTarget):
    """Guard target whose instance died — ``ensure_service`` raises."""

    def ensure_service(self) -> None:
        """Fail like the sandbox's died-service check."""
        raise RuntimeError("the instance under test died")


class _PartialTarget(PlainTarget):
    """Target with ``apply_pending`` but no ``ensure_service`` — no guard may install."""

    def __init__(self, base_url: str = "http://partial.test:9000") -> None:
        super().__init__(base_url)
        self.calls: list[str] = []

    def apply_pending(self) -> None:
        """Record the pending-batch apply (must stay uncalled — no guard)."""
        self.calls.append("apply_pending")


class TestApiBind:
    """Logic tests for ``Api.bind`` — address resolution, session rebuild, and the pre-flight."""

    def test_bind_repoints_client_at_target_base_url(self) -> None:
        """bind rebuilds the composed session at the target's base_url."""
        api = Api(base_url="https://x")

        api.bind(PlainTarget("http://sandbox.test:9000"))

        assert api.base_url == "http://sandbox.test:9000"

    def test_bind_falls_back_to_url_attribute(self) -> None:
        """A target without base_url binds through its url attribute."""
        api = Api(base_url="https://x")

        api.bind(UrlTarget("http://via-url.test:8080"))

        assert api.base_url == "http://via-url.test:8080"

    def test_bind_prefers_base_url_over_url(self) -> None:
        """A target exposing both attributes binds base_url."""
        api = Api(base_url="https://x")
        target = BindTarget(base_url="http://from-base.test:9000")
        target.url = "http://from-url.test:9000"  # type: ignore[attr-defined]

        api.bind(target)

        assert api.base_url == "http://from-base.test:9000"

    def test_bind_raises_type_error_without_url_attribute(self) -> None:
        """A target exposing neither attribute fails, and nothing is rebound."""
        api = Api(base_url="https://x")

        with pytest.raises(TypeError, match="base_url"):
            api.bind(object())

        assert api.base_url == "https://x"

    def test_bind_returns_none(self) -> None:
        """bind returns None (statement-style call)."""
        api = Api(base_url="https://x")

        assert api.bind(PlainTarget("http://sandbox.test:9000")) is None

    def test_bind_installs_guard_when_target_has_capabilities(self) -> None:
        """A guarded target runs apply_pending + ensure_service before every request."""
        api = Api(base_url="https://x")
        target = BindTarget()
        api.bind(target)

        order: list[str] = target.calls

        with mock.patch.object(api._client, "get", side_effect=lambda *_args, **_kwargs: order.append("request")):
            api.request("GET", "/a")
            api.request("GET", "/b")

        assert order == [
            "apply_pending",
            "ensure_service",
            "request",
            "apply_pending",
            "ensure_service",
            "request",
        ]

    def test_bind_with_partial_capabilities_binds_url_only(self) -> None:
        """apply_pending without ensure_service binds the address without the guard."""
        api = Api(base_url="https://x")
        target = _PartialTarget()
        api.bind(target)

        with mock.patch.object(api._client, "get") as verb:
            api.request("GET", "/a")

        assert target.calls == []
        verb.assert_called_once()
        assert verb.call_args.args == ("/a",)

    def test_bind_without_capabilities_binds_url_only(self) -> None:
        """A plain URL holder binds the address; requests run with no checks."""
        api = Api(base_url="https://x")
        api.bind(PlainTarget("http://plain.test:9000"))

        with mock.patch.object(api._client, "get") as verb:
            api.request("GET", "/a")

        assert api.base_url == "http://plain.test:9000"
        verb.assert_called_once()
        assert verb.call_args.args == ("/a",)

    def test_bind_guard_blocks_request_when_service_died(self) -> None:
        """A died-service check raises before the request leaves; the verb never runs."""
        api = Api(base_url="https://x")
        api.bind(_DiedTarget())

        with mock.patch.object(api._client, "get") as verb, pytest.raises(RuntimeError, match="died"):
            api.request("GET", "/a")

        verb.assert_not_called()

    def test_rebind_replaces_previous_guard(self) -> None:
        """A second guarded bind replaces the first target's checks — nothing stacks."""
        api = Api(base_url="https://x")
        first = BindTarget(base_url="http://first.test:9000")
        second = BindTarget(base_url="http://second.test:9000")
        api.bind(first)
        api.bind(second)

        with mock.patch.object(api._client, "get"):
            api.request("GET", "/a")

        assert first.calls == []
        assert second.calls == ["apply_pending", "ensure_service"]

    def test_rebind_to_plain_target_clears_guard(self) -> None:
        """Binding a plain holder after a guarded target removes the pre-flight."""
        api = Api(base_url="https://x")
        guarded = BindTarget()
        api.bind(guarded)
        api.bind(PlainTarget("http://plain.test:9000"))

        with mock.patch.object(api._client, "get"):
            api.request("GET", "/a")

        assert guarded.calls == []

    def test_bind_rebuilds_override_sessions(self) -> None:
        """bind closes the old client and cached override sessions and rebuilds from the new URL."""
        api = Api(base_url="https://x", timeout=5.0)
        built: list[mock.Mock] = []

        def factory(base_url: str, adapter: str, timeout: float | None = None) -> mock.Mock:
            session = mock.Mock()
            session.base_url = base_url
            built.append(session)
            return session

        with (
            mock.patch.object(api, "_validate_adapter"),
            mock.patch("goga_tool_pybuggy.api.api.resq.Session", side_effect=factory),
            mock.patch.object(api._client, "close") as old_client_close,
        ):
            first = api._get_session("other")

            api.bind(PlainTarget("http://sandbox.test:9000"))

            new_client = api._client
            assert new_client is built[1]
            assert api._sessions == {}
            second = api._get_session("other")
            assert second is built[2]
            assert first is not second

        old_client_close.assert_called_once_with()
        built[0].close.assert_called_once_with()
        new_client.close.assert_not_called()
