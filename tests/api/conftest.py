"""Shared fixtures and helpers for `goga_tool_pybuggy.api` cell tests.

Provides ``HeaderAuth``, ``stub_request``, ``FakeResponse``/``make_response``, and the
``bind``-target doubles ``BindTarget``/``UrlTarget``/``PlainTarget``.
"""

from __future__ import annotations

from typing import Any

import pytest
from requests.auth import AuthBase
from requests.models import PreparedRequest


class HeaderAuth(AuthBase):
    """AuthBase that sets a single configurable header on a prepared request.

    Args:
        name: header name to set on the signed request.
        value: header value to set on the signed request.
    """

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Sign the request by setting the configured header."""
        request.headers[self.name] = self.value

        return request


class StubRequest:
    """Minimal stand-in for a requests ``PreparedRequest`` in pure-logic auth tests.

    Attributes:
        headers: mutable dict of headers, mutated in place by auth callables.
    """

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


class FakeResponse:
    """Minimal stand-in for ``resq.http.Response`` in assert tests.

    Exposes ``status_code``/``headers``/``url``/``json()``; no ``.request``, matching ``resq.http.Response``.

    Args:
        status_code: HTTP status code.
        body: object returned by ``json()``.
        headers: response headers dict.
        url: response URL (used as the assert message label).
    """

    def __init__(
        self,
        status_code: int = 200,
        body: Any = None,
        headers: dict[str, str] | None = None,
        url: str = "https://api.example.com/resource",
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers if headers is not None else {"Content-Type": "application/json"}
        self.url = url

    def json(self) -> Any:
        """Return the canned body (None default)."""
        return self._body


class BindTarget:
    """Duck-typed ``bind`` target: an address plus the guard capabilities, recording calls.

    Attributes:
        base_url: the address ``Api.bind`` resolves.
        calls: the capability invocations in call order (``apply_pending``/``ensure_service``).
    """

    def __init__(self, base_url: str = "http://sandbox.test:9000") -> None:
        self.base_url = base_url
        self.calls: list[str] = []

    def apply_pending(self) -> None:
        """Record the pending-batch apply."""
        self.calls.append("apply_pending")

    def ensure_service(self) -> None:
        """Record the liveness check."""
        self.calls.append("ensure_service")


class UrlTarget:
    """``bind`` target exposing only ``url`` — the fallback attribute."""

    def __init__(self, url: str) -> None:
        self.url = url


class PlainTarget:
    """``bind`` target exposing only an address — no guard capabilities."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url


@pytest.fixture
def stub_request() -> StubRequest:
    """Return a fresh ``StubRequest`` exposing a mutable ``headers`` dict."""
    return StubRequest()


@pytest.fixture
def make_response() -> type[FakeResponse]:
    """Return the ``FakeResponse`` factory for building canned responses."""
    return FakeResponse
