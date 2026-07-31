"""Response-wrapper layer of the `goga_tool_pybuggy.api` cell.

``ResponseWrapper`` is a context manager over a raw ``resq.http.Response`` that
lazily exposes an :class:`Expected` dispatcher (from the `asserts` sub-cell) and
runs the auto-check once on first access. The static check configuration
(status/data_key/error_key/schemas_dir) is carried by an :class:`AssertConfig`
value; ``is_negative`` and ``use_autocheck`` are runtime flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .asserts import load_assert_class
from .asserts.config import AssertConfig
from .asserts.expected import Expected

if TYPE_CHECKING:
    import resq.http


class ResponseWrapper:
    """Context manager wrapping a ``resq.http.Response``.

    Delegates response-level checks to a lazily built :class:`Expected`. On first
    access of ``expected``, when ``use_autocheck`` is True, the auto-check runs
    exactly once (memoized).

    Args:
        response: the raw ``resq.http.Response`` being wrapped.
        config: the static check configuration — status/data_key/error_key/
            schemas_dir (each optional; ``None`` skips that check).
        use_autocheck: when True, the auto-check runs once on first access.
        is_negative: selects the negative auto-check path.
    """

    def __init__(
        self,
        response: resq.http.Response,
        config: AssertConfig,
        use_autocheck: bool = True,
        is_negative: bool = False,
    ) -> None:
        self._response = response
        self._config = config
        self._use_autocheck = use_autocheck
        self._is_negative = is_negative
        self._expected: Expected | None = None
        self._autocheck_ran = False

    @property
    def response(self) -> resq.http.Response:
        """The wrapped raw resq.http.Response."""
        return self._response

    @property
    def expected(self) -> Expected:
        """The response-level check dispatcher.

        Built lazily on first access; when ``use_autocheck`` is True, the
        auto-check runs exactly once at that point. When
        ``config.assert_response_class`` is set, the configured ``Expected``
        subclass is loaded (it must subclass ``Expected``); otherwise the
        built-in ``Expected`` is used.
        """
        if self._expected is None:
            response_cls = Expected
            if self._config.assert_response_class is not None:
                response_cls = load_assert_class(self._config.assert_response_class, Expected)

            expected = response_cls(self._response, self._config, self._is_negative)

            if self._use_autocheck and not self._autocheck_ran:
                self._autocheck_ran = True
                expected.autocheck()

            self._expected = expected

        return self._expected

    def __enter__(self) -> ResponseWrapper:
        """Enter the context; returns this wrapper."""
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit the context without suppression — exceptions propagate."""
        return None
