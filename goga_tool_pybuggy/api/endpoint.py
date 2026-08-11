"""Callable route over an ``Api`` for the `goga_tool_pybuggy.api` cell.

``Endpoint`` binds an ``Api`` client, an HTTP verb, a route path, and an optional
adapter override into a callable that issues a single request per call and
returns a ``ResponseWrapper``.

``__call__`` (positive path) and ``error`` (negative path) both delegate to
``_call``, the shared internal routine. ``_call`` resolves a call-level
authenticator, combining it with the stored ``Api`` auth via ``CombineAuth`` /
``AuthWrapper`` in the precedence order ``AuthBase`` → ``Auth`` protocol →
callable → ``TypeError``. It copies the caller's kwargs without mutating them,
pops the call-level ``auth``/``use_autocheck``, resolves the data/error keys with
fallback to the ``Api``-level keys, injects the effective adapter (this
``Endpoint``'s override falling back to the ``Api`` default), issues the request
through ``api.request``, and wraps the raw response.
"""

from __future__ import annotations

import inspect
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from requests.auth import AuthBase

from .asserts.config import AssertConfig
from .auth import AuthWrapper, CombineAuth
from .response import ResponseWrapper

if TYPE_CHECKING:
    from .api import Api


class Endpoint:
    """Callable route over an ``Api`` issuing one request per call.

    Args:
        api: the ``Api`` client used to issue the request.
        url_path: route path forwarded to ``Api.request``.
        method: HTTP verb forwarded to ``Api.request``.
        status: expected success status code; an Enum is normalized to its value.
        use_autocheck: whether the lazy auto-check fires on first ``expected``.
        data_key: per-endpoint data key; falls back to ``api.data_key``.
        error_key: per-endpoint error key; falls back to ``api.error_key``.
        adapter: per-endpoint resq adapter override forwarded to ``api.request``;
            ``None`` falls back to the ``Api``-level default adapter.
    """

    def __init__(  # noqa: PLR0913
        self,
        api: Api,
        url_path: str,
        method: str,
        status: int | None = 200,
        use_autocheck: bool = True,
        data_key: str | None = None,
        error_key: str | None = None,
        adapter: str | None = None,
    ) -> None:
        self.api = api
        self._url_path = url_path
        self._method = method
        self.status = status.value if isinstance(status, Enum) else status
        self.use_autocheck = use_autocheck
        self.data_key = data_key
        self.error_key = error_key
        self._adapter = adapter
        caller_file = inspect.stack()[1].frame.f_globals.get("__file__")
        self.schemas_dir = Path(caller_file).parent / "schemas" if caller_file is not None else None

    @property
    def url_path(self) -> str:
        """Route path forwarded to ``Api.request``."""
        return self._url_path

    @property
    def method(self) -> str:
        """HTTP verb forwarded to ``Api.request``."""
        return self._method

    @property
    def adapter(self) -> str | None:
        """Per-endpoint resq adapter override; ``None`` falls back to the ``Api`` default."""
        return self._adapter

    def __call__(self, **kwargs: Any) -> ResponseWrapper:
        """Positive-path request; delegates to ``_call`` with is_negative=False.

        Args:
            **kwargs: call-level request arguments.

        Returns:
            The ``ResponseWrapper`` over the raw response.
        """
        return self._call(False, **kwargs)

    def error(self, **kwargs: Any) -> ResponseWrapper:
        """Negative-path request; delegates to ``_call`` with is_negative=True.

        Args:
            **kwargs: call-level request arguments.

        Returns:
            The ``ResponseWrapper`` over the raw response.
        """
        return self._call(True, **kwargs)

    def _resolve_call_auth(self, call_auth: Any) -> CombineAuth:
        """Build a ``CombineAuth`` from ``api.auth`` plus the call-level auth.

        ``api.auth`` is added first (yields on conflict); the call-level auth is
        added in precedence order: ``AuthBase`` directly, an ``Auth`` protocol
        object's bound ``auth`` method wrapped in ``AuthWrapper``, or a plain
        callable wrapped in ``AuthWrapper``. Anything else raises ``TypeError``.

        Args:
            call_auth: the call-level authenticator supplied to the call.

        Returns:
            The populated ``CombineAuth``.

        Raises:
            TypeError: when ``call_auth`` is not a supported auth type.
        """
        combine = CombineAuth()
        if self.api.auth is not None:
            combine.add_auth(self.api.auth)
        if isinstance(call_auth, AuthBase):
            combine.add_auth(call_auth)
        elif hasattr(call_auth, "auth"):
            combine.add_auth(AuthWrapper(call_auth.auth))
        elif callable(call_auth):
            combine.add_auth(AuthWrapper(call_auth))
        else:
            raise TypeError(f"unsupported call-level auth: {type(call_auth).__name__}")
        return combine

    def _call(self, is_negative: bool, **kwargs: Any) -> ResponseWrapper:
        """Shared internal call routine for ``__call__`` and ``error``.

        Resolves the call-level auth and the data/error keys, injects the
        effective adapter, issues the request via ``api.request``, and wraps the
        raw response. The caller's kwargs dict is never mutated: a copy is made
        and ``auth``/``use_autocheck`` are popped from it.

        Args:
            is_negative: selects the negative ``ResponseWrapper`` path.
            **kwargs: call-level request arguments and the optional call-level
                ``auth``/``use_autocheck``.

        Returns:
            The ``ResponseWrapper`` over the raw response.
        """
        call_kwargs = dict(kwargs)
        call_auth = call_kwargs.pop("auth", None)
        autocheck = call_kwargs.pop("use_autocheck", self.use_autocheck)
        if call_auth is not None:
            call_kwargs["auth"] = self._resolve_call_auth(call_auth)
        call_kwargs["adapter"] = self._adapter
        data_key = self.data_key if self.data_key is not None else self.api.data_key
        error_key = self.error_key if self.error_key is not None else self.api.error_key
        config = AssertConfig(
            status=self.status,
            data_key=data_key,
            error_key=error_key,
            schemas_dir=self.schemas_dir,
            timeout=self.api.assert_timeout,
            delay=self.api.assert_delay,
            assert_field_class=self.api.assert_field_class,
            assert_response_class=self.api.assert_response_class,
        )
        raw = self.api.request(self.method, self.url_path, **call_kwargs)
        return ResponseWrapper(raw, config, autocheck, is_negative)
