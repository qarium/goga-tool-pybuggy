"""Contract and logic tests for `pybuggy.api.auth`.

Pure-logic tests (no mocks): the auth primitives operate on stub
``PreparedRequest``-like objects (the ``stub_request`` fixture) and on real
``HeaderAuth`` ``AuthBase`` instances shared from ``tests/api/conftest.py``.
"""

from __future__ import annotations

import pytest
from pybuggy.api.auth import Auth, AuthWrapper, CombineAuth
from requests.auth import AuthBase

from tests.api.conftest import HeaderAuth


class TestAuthContract:
    """Contract tests for the auth entities' facade/API shape."""

    def test_imports_succeed(self) -> None:
        """CombineAuth, AuthWrapper, Auth are importable from pybuggy.api.auth."""
        assert isinstance(CombineAuth, type)
        assert isinstance(AuthWrapper, type)
        assert isinstance(Auth, type)

    def test_auth_is_runtime_checkable_protocol(self) -> None:
        """Auth is a runtime_checkable Protocol: isinstance works on duck type."""

        class _Consumer:
            def auth(self, request: object) -> object:
                return request

        # An object exposing `auth(request)` satisfies the protocol.
        assert isinstance(_Consumer(), Auth)
        # A bare object without `auth` does not.
        assert not isinstance(object(), Auth)


class TestAuthWrapper:
    """Contract + logic tests for AuthWrapper."""

    def test_authwrapper_is_authbase(self) -> None:
        """AuthWrapper is an honest AuthBase."""
        assert isinstance(AuthWrapper(lambda r: r), AuthBase)

    def test_authwrapper_delegates_and_returns_request(self, stub_request: object) -> None:
        """AuthWrapper delegates to the wrapped callable and returns its result."""
        wrapper = AuthWrapper(lambda r: r.headers.__setitem__("X", "1") or r)

        result = wrapper(stub_request)

        assert result is stub_request
        assert stub_request.headers["X"] == "1"


class TestCombineAuth:
    """Contract + logic tests for CombineAuth."""

    def test_combineauth_is_authbase(self) -> None:
        """CombineAuth is an honest AuthBase."""
        assert isinstance(CombineAuth(), AuthBase)

    def test_add_auth_is_fluent(self) -> None:
        """add_auth returns the CombineAuth for chaining."""
        combine = CombineAuth()

        result = combine.add_auth(HeaderAuth("X", "1"))

        assert result is combine

    def test_call_returns_prepared_request_like(self, stub_request: object) -> None:
        """__call__ returns the (signed) PreparedRequest-like object."""
        signed = CombineAuth()(stub_request)

        assert signed is stub_request

    def test_combineauth_applies_in_registration_order(self, stub_request: object) -> None:
        """Auths apply in registration order; a later auth wins on conflict."""
        first = HeaderAuth("X-A", "first")
        over = HeaderAuth("X-A", "over")

        CombineAuth().add_auth(first).add_auth(over)(stub_request)

        assert stub_request.headers["X-A"] == "over"

    def test_add_auth_rejects_non_authbase(self) -> None:
        """add_auth raises TypeError for a non-AuthBase and leaves the chain empty."""
        combine = CombineAuth()

        with pytest.raises(TypeError):
            combine.add_auth(object())  # type: ignore[arg-type]

        assert len(combine._chain) == 0

    def test_combineauth_empty_chain_returns_request_unchanged(self, stub_request: object) -> None:
        """An empty chain returns the request unchanged."""
        signed = CombineAuth()(stub_request)

        assert signed is stub_request
        assert stub_request.headers == {}

    def test_nested_combineauth_added_directly(self) -> None:
        """A CombineAuth accepts another CombineAuth (both are AuthBase)."""
        outer = CombineAuth()
        inner = CombineAuth()
        inner.add_auth(HeaderAuth("X-I", "1"))

        outer.add_auth(inner)

        assert inner in outer._chain

    def test_combineauth_callable_returning_none_kept(self, stub_request: object) -> None:
        """An auth returning None does not break the chain; a later auth still signs."""
        combine = CombineAuth()
        combine.add_auth(AuthWrapper(lambda _r: None))
        combine.add_auth(HeaderAuth("X-Sign", "yes"))

        signed = combine(stub_request)

        assert signed is stub_request
        assert stub_request.headers["X-Sign"] == "yes"
