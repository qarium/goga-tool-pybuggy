"""HTTP client of the `goga_tool_pybuggy.api` cell.

``Api`` composes a ``resq.Session`` over a base URL, stores the per-client
authenticator, default headers/cookies, a request timeout, and the assert
settings, and exposes them as properties. ``auth`` is read/write.

``Api`` owns the adapter: it holds one cached ``resq.Session`` per adapter name
(the default session is the composed ``_client``) and routes each request to the
session matching the effective adapter. Only ``"requests"`` (sync) is supported
in the sync runtime; ``"httpx"`` (async in resq) is rejected until an async
stack lands.

``request`` serializes a single request: it dumps pydantic ``params``/``json``
(with optional ``by_alias``), substitutes ``:name`` path placeholders, injects
the stored auth/headers/cookies defaults with call-level precedence, resolves
the effective adapter (call-level override falling back to the ``Api`` default),
and dispatches to the matching resq verb — one request, never forwarding
``timeout``/``delay``/polling options.
"""

from __future__ import annotations

import logging
import re
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any

import resq
from pydantic import BaseModel
from requests.auth import AuthBase

if TYPE_CHECKING:
    import resq.http

logger = logging.getLogger(__name__)

# Adapter names the sync runtime can drive. resq's "httpx" adapter is async and
# is rejected by _validate_adapter until an async stack lands.
_SYNC_ADAPTERS = frozenset({"requests"})


class Api:
    """HTTP client composing a ``resq.Session`` over a base URL.

    Args:
        base_url: base URL held by the underlying resq.Session.
        auth: default ``requests`` authenticator applied to every request.
        headers: default request headers (empty dict when None).
        cookies: default request cookies.
        timeout: network timeout forwarded to resq.Session; not re-sent per
            request.
        assert_timeout: baseline assert-polling timeout in seconds (distinct
            from the network ``timeout``); forwarded to ``AssertConfig``.
        assert_delay: baseline assert-polling delay in seconds; forwarded to
            ``AssertConfig``.
        assert_field_class: dotted ``module:Class`` path of a custom
            ``AssertField`` subclass; forwarded to ``AssertConfig``.
        assert_response_class: dotted ``module:Class`` path of a custom
            ``Expect`` subclass; forwarded to ``AssertConfig``.
        adapter: default resq adapter name used to build the composed session;
            ``"requests"`` (sync) only — ``"httpx"`` is async in resq and is
            rejected by :meth:`_validate_adapter` until an async stack lands.
    """

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        base_url: str,
        auth: AuthBase | None = None,
        headers: dict[str, str] | None = None,
        cookies: SimpleCookie | None = None,
        timeout: float | None = None,
        assert_timeout: int | float | None = None,
        assert_delay: int | float | None = None,
        assert_field_class: str | None = None,
        assert_response_class: str | None = None,
        adapter: str = "requests",
    ) -> None:
        self._validate_adapter(adapter)
        self._default_adapter = adapter
        self._base_url = base_url
        self._timeout = timeout
        self._sessions: dict[str, resq.Session] = {}
        self._client = resq.Session(base_url, adapter, timeout=timeout)
        self._auth = auth
        self._headers = headers or {}
        self._cookies = cookies
        self._assert_timeout = assert_timeout
        self._assert_delay = assert_delay
        self._assert_field_class = assert_field_class
        self._assert_response_class = assert_response_class

    @property
    def base_url(self) -> str:
        """Base URL held by the underlying resq.Session."""
        return self._client.base_url

    @property
    def adapter(self) -> str:
        """Default resq adapter name fixed at construction (``"requests"`` in the sync runtime)."""
        return self._default_adapter

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
        """Dotted path of a custom ``Expect`` subclass (``module:Class``)."""
        return self._assert_response_class

    def request(self, method: str, url_path: str, **kwargs: Any) -> resq.http.Response:
        """Dispatch a single serialized request to the matching resq verb.

        Serializes pydantic ``params``/``json`` (with optional ``by_alias`` via
        ``use_aliases``), substitutes ``:name`` path placeholders, injects the
        stored auth/headers/cookies with call-level precedence, resolves the
        effective adapter (call-level ``adapter`` override falling back to the
        ``Api`` default), and dispatches to the resq verb on the matching cached
        session. Never forwards ``timeout``/``delay``/polling options.

        Args:
            method: HTTP verb name (case-insensitive), e.g. ``"GET"``.
            url_path: request path resolved against the session base URL.
            **kwargs: request arguments (``params``, ``json``, ``headers``,
                ``cookies``, ``auth``, ``use_aliases``, ``adapter``).

        Returns:
            The raw ``resq.http.Response``.
        """
        logger.debug("api request", extra={"method": method, "url_path": url_path})

        use_aliases = kwargs.pop("use_aliases", False)
        adapter = kwargs.pop("adapter", None)

        kwargs["params"] = self._resolve_params(kwargs.get("params"), use_aliases)
        url_path = self._substitute_path_params(url_path, kwargs["params"])

        if isinstance(kwargs.get("json"), BaseModel):
            kwargs["json"] = kwargs["json"].model_dump(by_alias=use_aliases)

        self._inject_defaults(kwargs)

        kwargs.pop("timeout", None)
        kwargs.pop("delay", None)

        effective_adapter = adapter if adapter is not None else self._default_adapter
        client = self._get_session(effective_adapter)
        verb = getattr(client, method.lower())
        return verb(url_path, **kwargs)

    def close(self) -> None:
        """Close the composed resq.Session plus any cached override sessions.

        Delegates to each session's public ``close()``. In sync mode (the only
        mode pybuggy uses — ``adapter="requests"``) each close is a no-op by
        resq's design: the held ``requests.Session`` is released by garbage
        collection, not closed here. pybuggy never issues async requests, so the
        lazily created ``httpx`` client is never created and is left untouched.
        Called by the ``api`` fixture teardown.
        """
        self._client.close()

        for session in self._sessions.values():
            session.close()

    @staticmethod
    def _validate_adapter(adapter: str) -> None:
        """Reject any adapter the sync runtime cannot drive.

        Only ``"requests"`` is supported: resq's ``"httpx"`` adapter is async
        (verbs return coroutines, the wrapper is ``AsyncResponse``) and pybuggy
        has no async stack yet. When async lands, relax this set.

        Args:
            adapter: the adapter name to check.

        Raises:
            ValueError: when ``adapter`` is not in the sync-supported set.
        """
        if adapter not in _SYNC_ADAPTERS:
            raise ValueError(
                f"unsupported adapter {adapter!r} in sync pybuggy; "
                f"only {sorted(_SYNC_ADAPTERS)!r} are supported "
                f"('httpx' requires async, not yet implemented)",
            )

    def _get_session(self, adapter: str) -> resq.Session:
        """Return the cached resq.Session for ``adapter``, building it on first use.

        The default adapter reuses the composed ``_client``; any other validated
        adapter is built once (same base URL and network timeout as the default)
        and cached in ``_sessions`` for reuse. ``adapter`` is validated first, so
        an unsupported value raises before any session is built.

        Args:
            adapter: the adapter name to resolve a session for.

        Returns:
            The resq.Session bound to ``adapter``.
        """
        self._validate_adapter(adapter)

        if adapter == self._default_adapter:
            return self._client

        if adapter not in self._sessions:
            self._sessions[adapter] = resq.Session(self._base_url, adapter, timeout=self._timeout)

        return self._sessions[adapter]

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
        keys stay as the query string. Only the names actually present in
        ``params`` are matched, each as a whole token (a name is never matched
        inside a longer one, so ``:id`` / ``:id2`` stay distinct and ``:id``
        leaves ``:identity`` untouched) — a ``:word`` with no matching parameter
        is literal path content (e.g. ``09:30``) and is left untouched.
        """
        names = sorted((key for key in params if key.startswith(":")), key=len, reverse=True)
        if not names:
            return url_path

        # A name ends where the token ends: the next character must not continue
        # it. A word char would (``:id`` must not match the ``:id`` prefix of
        # ``:identity``), and so would ``-`` before a word char (``:order`` must
        # not match inside ``:order-id``). Everything else ends the name — the
        # segment end, a literal ``.``/``-`` (``/files/{id}.json`` substitutes),
        # and the ``:`` of the next placeholder (``/range/{from}-{to}``).
        pattern = re.compile("|".join(re.escape(name) + r"(?!\w|-\w)" for name in names))
        values = {name: params.pop(name) for name in names}

        def _replace(match: re.Match[str]) -> str:
            return str(values[match.group(0)])

        return pattern.sub(_replace, url_path)

    def _inject_defaults(self, kwargs: dict[str, Any]) -> None:
        """Inject stored auth/headers/cookies with call-level precedence."""
        kwargs.setdefault("auth", self._auth)

        call_headers = kwargs.get("headers") or {}
        kwargs["headers"] = {**self._headers, **call_headers}

        if self._cookies is not None:
            kwargs.setdefault("cookies", self._cookies)
