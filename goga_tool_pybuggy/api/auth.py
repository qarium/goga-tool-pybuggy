"""Call-level combined authentication primitives for the `pybuggy.api` cell.

Three self-contained auth entities (only ``requests`` + stdlib ``typing``):

- ``CombineAuth`` — a ``requests`` ``AuthBase`` that chains multiple auths and
  applies each to the ``PreparedRequest`` in registration order. Built by
  ``Endpoint._call`` to merge the stored ``Api`` auth with a call-level auth.
- ``AuthWrapper`` — a ``requests`` ``AuthBase`` adapter that delegates to a plain
  callable, letting non-``AuthBase`` callables participate in a ``CombineAuth``
  chain.
- ``Auth`` — a structural ``Protocol`` for a per-call authenticator: any object
  exposing an ``auth(request)`` method is accepted as the call-level auth of an
  ``Endpoint`` call.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from requests.auth import AuthBase
from requests.models import PreparedRequest


@runtime_checkable
class Auth(Protocol):
    """Structural protocol for a per-call authenticator.

    Any object exposing an ``auth(request)`` method is accepted as the
    call-level auth of an ``Endpoint`` call. Implemented by consumers; never
    constructed by ``pybuggy``.
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
    ``Endpoint._call`` wraps the bound ``auth`` method of an ``Auth`` protocol
    object (or a plain callable) in an ``AuthWrapper`` before adding it to the
    chain.

    Args:
        func: a callable taking a ``PreparedRequest`` and returning it (or
            ``None`` to signal in-place mutation) — typically the bound ``auth``
            method of an ``Auth`` protocol object.
    """

    def __init__(self, func: Callable[[PreparedRequest], PreparedRequest | None]) -> None:
        self.func = func

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Invoke the wrapped callable on the request and return its result.

        Args:
            request: the ``PreparedRequest`` being signed.

        Returns:
            Whatever the wrapped callable returns (the signed
            ``PreparedRequest``, or ``None`` when it mutates in place —
            ``CombineAuth`` tolerates both).
        """
        return self.func(request)


class CombineAuth(AuthBase):
    """``requests`` ``AuthBase`` that chains multiple auths.

    Applies each auth in the chain to the ``PreparedRequest`` in registration
    order. Built by ``Endpoint._call`` to merge the stored ``Api`` auth with a
    call-level auth.

    Attributes:
        _chain: ordered list of appended ``AuthBase`` auths.
    """

    def __init__(self) -> None:
        self._chain: list[AuthBase] = []

    def add_auth(self, auth: AuthBase) -> CombineAuth:
        """Append an ``AuthBase`` to the chain.

        Args:
            auth: an ``AuthBase`` — a plain ``requests`` auth, an ``AuthWrapper``,
                or another ``CombineAuth``.

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

        Auths that return ``None`` (mutating the request in place) are tolerated:
        the previous request is kept and the chain continues.

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
