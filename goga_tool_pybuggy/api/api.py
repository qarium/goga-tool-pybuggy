"""HTTP client of the `goga_tool_pybuggy.api` cell.

``Api`` composes a ``resq.Session`` over a base URL, stores the per-client
authenticator, default headers/cookies, a request timeout, and the success/error
body keys, and exposes them as properties. ``data_key``/``error_key`` are
read-only fallbacks consulted by ``Endpoint._call`` when an endpoint has no
per-endpoint key; ``auth`` is read/write.

``request`` serializes a single request: it dumps pydantic ``params``/``json``
(with optional ``by_alias``), substitutes ``:name`` path placeholders, injects
the stored auth/headers/cookies defaults with call-level precedence, and
dispatches to the matching resq verb — one request, never forwarding
``timeout``/``delay``/polling options.
"""

from __future__ import annotations

import logging
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any

import resq
from pydantic import BaseModel
from requests.auth import AuthBase

if TYPE_CHECKING:
    import resq.http

logger = logging.getLogger(__name__)


class Api:
    """HTTP client composing a ``resq.Session`` over a base URL.

    Args:
        base_url: base URL held by the underlying resq.Session.
        auth: default ``requests`` authenticator applied to every request.
        headers: default request headers (empty dict when None).
        cookies: default request cookies.
        timeout: default request timeout in seconds.
        data_key: success-body key fallback for endpoints without one.
        error_key: error-body key fallback for endpoints without one.
        assert_timeout: baseline assert-polling timeout in seconds (distinct
            from the network ``timeout``); forwarded to ``AssertConfig``.
        assert_delay: baseline assert-polling delay in seconds; forwarded to
            ``AssertConfig``.
        assert_field_class: dotted ``module:Class`` path of a custom
            ``AssertField`` subclass; forwarded to ``AssertConfig``.
        assert_response_class: dotted ``module:Class`` path of a custom
            ``Expected`` subclass; forwarded to ``AssertConfig``.
    """

    def __init__(  # noqa: PLR0913
        self,
        base_url: str,
        auth: AuthBase | None = None,
        headers: dict[str, str] | None = None,
        cookies: SimpleCookie | None = None,
        timeout: float | None = None,
        data_key: str | None = None,
        error_key: str | None = None,
        assert_timeout: int | float | None = None,
        assert_delay: int | float | None = None,
        assert_field_class: str | None = None,
        assert_response_class: str | None = None,
    ) -> None:
        self._client = resq.Session(base_url, "requests", timeout=timeout)
        self._auth = auth
        self._headers = headers or {}
        self._cookies = cookies
        self._data_key = data_key
        self._error_key = error_key
        self._assert_timeout = assert_timeout
        self._assert_delay = assert_delay
        self._assert_field_class = assert_field_class
        self._assert_response_class = assert_response_class

    @property
    def base_url(self) -> str:
        """Base URL held by the underlying resq.Session."""
        return self._client.base_url

    @property
    def auth(self) -> AuthBase | None:
        """Default authenticator applied to every request."""
        return self._auth

    @auth.setter
    def auth(self, value: AuthBase | None) -> None:
        self._auth = value

    @property
    def headers(self) -> dict[str, str]:
        """Default request headers (empty dict when none given)."""
        return self._headers

    @property
    def cookies(self) -> SimpleCookie | None:
        """Default request cookies, or None."""
        return self._cookies

    @property
    def data_key(self) -> str | None:
        """Success-body key fallback for endpoints without a per-endpoint key."""
        return self._data_key

    @property
    def error_key(self) -> str | None:
        """Error-body key fallback for endpoints without a per-endpoint key."""
        return self._error_key

    @property
    def assert_timeout(self) -> int | float | None:
        """Baseline assert-polling timeout forwarded into each ``AssertConfig``."""
        return self._assert_timeout

    @property
    def assert_delay(self) -> int | float | None:
        """Baseline assert-polling delay forwarded into each ``AssertConfig``."""
        return self._assert_delay

    @property
    def assert_field_class(self) -> str | None:
        """Dotted path of a custom ``AssertField`` subclass (``module:Class``)."""
        return self._assert_field_class

    @property
    def assert_response_class(self) -> str | None:
        """Dotted path of a custom ``Expected`` subclass (``module:Class``)."""
        return self._assert_response_class

    def request(self, method: str, url_path: str, **kwargs: Any) -> resq.http.Response:
        """Dispatch a single serialized request to the matching resq verb.

        Serializes pydantic ``params``/``json`` (with optional ``by_alias`` via
        ``use_aliases``), substitutes ``:name`` path placeholders, injects the
        stored auth/headers/cookies with call-level precedence, and dispatches to
        the resq verb. Never forwards ``timeout``/``delay``/polling options.

        Args:
            method: HTTP verb name (case-insensitive), e.g. ``"GET"``.
            url_path: request path resolved against the session base URL.
            **kwargs: request arguments (``params``, ``json``, ``headers``,
                ``cookies``, ``auth``, ``use_aliases``).

        Returns:
            The raw ``resq.http.Response``.
        """
        logger.debug("api request", extra={"method": method, "url_path": url_path})

        use_aliases = kwargs.pop("use_aliases", False)

        kwargs["params"] = self._resolve_params(kwargs.get("params"), use_aliases)
        url_path = self._substitute_path_params(url_path, kwargs["params"])

        if isinstance(kwargs.get("json"), BaseModel):
            kwargs["json"] = kwargs["json"].model_dump(by_alias=use_aliases)

        self._inject_defaults(kwargs)

        kwargs.pop("timeout", None)
        kwargs.pop("delay", None)

        verb = getattr(self._client, method.lower())
        return verb(url_path, **kwargs)

    def close(self) -> None:
        """Close the composed resq.Session via its public ``close()``.

        Delegates to ``resq.Session.close()``. In sync mode (the only mode
        pybuggy uses — ``adapter="requests"``) that close is a no-op by resq's
        design: the held ``requests.Session`` is released by garbage collection,
        not closed here. pybuggy never issues async requests, so the lazily
        created ``httpx`` client is never created and is left untouched. Called
        by the ``api`` fixture teardown.
        """
        self._client.close()

    @staticmethod
    def _resolve_params(params: Any, use_aliases: bool) -> dict[str, Any]:
        """Serialize ``params`` into a fresh dict (never the caller's dict).

        A pydantic model is dumped with ``by_alias``; a dict is copied; None
        becomes an empty dict.
        """
        if isinstance(params, BaseModel):
            return params.model_dump(by_alias=use_aliases)

        if params is None:
            return {}

        return dict(params)

    @staticmethod
    def _substitute_path_params(url_path: str, params: dict[str, Any]) -> str:
        """Move ``:name`` keys out of ``params`` into ``url_path`` (in place).

        ``params`` is the fresh dict from :meth:`_resolve_params`; the remaining
        keys stay as the query string.
        """
        for key in [name for name in params if name.startswith(":")]:
            url_path = url_path.replace(key, str(params.pop(key)))

        return url_path

    def _inject_defaults(self, kwargs: dict[str, Any]) -> None:
        """Inject stored auth/headers/cookies with call-level precedence."""
        kwargs.setdefault("auth", self._auth)

        call_headers = kwargs.get("headers") or {}
        kwargs["headers"] = {**self._headers, **call_headers}

        if self._cookies is not None:
            kwargs.setdefault("cookies", self._cookies)
