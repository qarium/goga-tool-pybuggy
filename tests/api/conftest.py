"""Shared fixtures and helpers for `pybuggy.api` cell tests.

Provides:
- ``HeaderAuth`` — an ``AuthBase`` that sets a single configurable header on a
  prepared request; reused as ``Api.auth`` and as a call-level ``AuthBase``.
- ``stub_request`` — a fixture returning a minimal object exposing a mutable
  ``headers`` dict, standing in for a ``requests`` ``PreparedRequest`` in
  pure-logic auth tests.
- ``FakeResponse`` / ``make_response`` — a minimal ``resq.http.Response`` stand-in
  exposing ``status_code``/``headers``/``url``/``json()`` for assert tests.
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

    Exposes the surface the asserts read: ``status_code``, ``headers``, ``url``,
    and ``json()``. ``resq.http.Response`` has no ``.request``, so neither does
    this stand-in.

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


@pytest.fixture
def stub_request() -> StubRequest:
    """Return a fresh ``StubRequest`` exposing a mutable ``headers`` dict."""
    return StubRequest()


@pytest.fixture
def make_response() -> type[FakeResponse]:
    """Return the ``FakeResponse`` factory for building canned responses."""
    return FakeResponse
