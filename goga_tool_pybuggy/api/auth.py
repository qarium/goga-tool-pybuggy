"""Call-level combined authentication primitives for the `goga_tool_pybuggy.api` cell.

``CombineAuth`` chains auths in registration order; ``AuthWrapper`` adapts a callable to ``AuthBase``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from requests.auth import AuthBase
from requests.models import PreparedRequest


@runtime_checkable
class Auth(Protocol):
    """Structural protocol for a per-call authenticator.

    Any object exposing an ``auth(request)`` method qualifies.
    """

    def auth(self, request: PreparedRequest) -> PreparedRequest:
        """Sign the prepared request in place.

        Args:
            request: the ``PreparedRequest`` being signed.

        Returns:
            The signed ``PreparedRequest``.
        """

        ...


class AuthWrapper(AuthBase):
    """``requests`` ``AuthBase`` adapter delegating to a plain callable.

    Lets non-``AuthBase`` callables participate in a ``CombineAuth`` chain.

    Args:
        func: callable taking a ``PreparedRequest`` and returning it, or ``None`` when mutating in place.
    """

    def __init__(self, func: Callable[[PreparedRequest], PreparedRequest | None]) -> None:
        self.func = func

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Invoke the wrapped callable on the request and return its result.

        Args:
            request: the ``PreparedRequest`` being signed.

        Returns:
            The wrapped callable's result — the signed ``PreparedRequest``, or ``None`` for in-place mutation.
        """
        return self.func(request)


class CombineAuth(AuthBase):
    """``requests`` ``AuthBase`` that chains multiple auths.

    Applies each auth to the ``PreparedRequest`` in registration order.

    Attributes:
        _chain: ordered list of appended ``AuthBase`` auths.
    """

    def __init__(self) -> None:
        self._chain: list[AuthBase] = []

    def add_auth(self, auth: AuthBase) -> CombineAuth:
        """Append an ``AuthBase`` to the chain.

        Args:
            auth: the ``AuthBase`` to append.

        Returns:
            This ``CombineAuth``, for chaining.

        Raises:
            TypeError: when ``auth`` is not an ``AuthBase``.
        """
        if not isinstance(auth, AuthBase):
            raise TypeError(f"CombineAuth.add_auth expects AuthBase, got {type(auth).__name__}")
        self._chain.append(auth)
        return self

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Apply every auth in the chain to the request, in registration order.

        Auths returning ``None`` (mutating in place) are tolerated.

        Args:
            request: the ``PreparedRequest`` being signed.

        Returns:
            The signed ``PreparedRequest``.
        """
        for auth in self._chain:
            signed = auth(request)
            if signed is not None:
                request = signed
        return request
