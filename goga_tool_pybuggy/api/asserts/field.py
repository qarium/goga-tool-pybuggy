"""Field-level asserts for `goga_tool_pybuggy.api`.

``AssertField`` wraps a search :class:`~goga_tool_pybuggy.api.asserts.contexts.BaseContext`
and exposes matchcrest-backed assertions over the resolved field value. Every
check is an ``assert_that(context, matcher, reason=...)`` that returns ``self``
for fluent chaining; calling the field (``field(search=..., index=..., hook=...)``
or ``field(index=0)``) drills one level deeper.

pybuggy ships plain classes (no reporting layer). The ``timeout``/``delay``
polling options drive matchcrest's retry loop — the context re-fetches the
response via ``resq.http.Response.reload()`` between attempts. The
``timeout``/``delay`` inherited from ``AssertConfig`` are the baseline; the
per-check ``timeout``/``delay`` kwargs override them for one assertion.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

from ...matchcrest import (
    BaseContext,
    NotRaisedExceptionMatcher,
    RaisedExceptionMatcher,
    ValueContainsDictMatcher,
    ValueContainsMatcher,
    ValueDateEqualMatcher,
    ValueDateGreaterMatcher,
    ValueDateLesserMatcher,
    ValueEndsWithMatcher,
    ValueIsDisjointMatcher,
    ValueIsEmpty,
    ValueIsEqualMatcher,
    ValueIsGreaterMatcher,
    ValueIsInMatcher,
    ValueIsLesserMatcher,
    ValueIsNotEmpty,
    ValueIsNotEqualMatcher,
    ValueIsNotInMatcher,
    ValueIsSubsetMatcher,
    ValueIsUrlMatcher,
    ValueLengthEqualMatcher,
    ValueLengthGreaterMatcher,
    ValueLengthLesserMatcher,
    ValueNotContainsMatcher,
    ValueRegexMatcher,
    ValueStartsWithMatcher,
    assert_that,
)
from .base import BaseAssert


class AssertField(BaseAssert):
    """Field-level assert over a resolved response value.

    Args:
        context: the search context providing ``value``/``key``.
        is_negative: negative-path flag (error-key/data-key resolution is done
            by the context; kept here for drill-down propagation).
        in_array: when True, the resolved value is treated as a list and each
            matcher option (``any``) applies element-wise.
        timeout: baseline polling timeout (seconds) inherited from
            ``AssertConfig``; per-check ``timeout`` kwargs override it.
        delay: baseline polling delay (seconds) inherited from ``AssertConfig``;
            per-check ``delay`` kwargs override it.
    """

    def __init__(
        self,
        context: BaseContext,
        *,
        is_negative: bool = False,
        in_array: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> None:
        self._context = context
        self._is_negative = is_negative
        self._in_array = in_array
        self._timeout = timeout
        self._delay = delay

    def __call__(self, *args: Any, **kwargs: Any) -> AssertField:
        """Drill one level deeper, returning a new ``AssertField``.

        The baseline ``timeout``/``delay`` propagate to the drilled field.

        Args:
            *args/**kwargs: forwarded to ``context()`` (``search``/``index``/
                ``hook``), plus the optional ``in_array`` override.

        Returns:
            A new ``AssertField`` over the extended search context.
        """
        in_array = kwargs.pop("in_array", self._in_array)

        return AssertField(
            self._context(*args, **kwargs),
            is_negative=self._is_negative,
            in_array=in_array,
            timeout=self._timeout,
            delay=self._delay,
        )

    @property
    def value(self) -> Any:
        """The currently resolved field value."""
        return self._context.value

    def contains(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value contains ``value``."""
        matcher = self._create_matcher(
            ValueContainsMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def not_contains(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value does not contain ``value``."""
        matcher = self._create_matcher(
            ValueNotContainsMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def equal_to(  # noqa: PLR0913
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        strict: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value equals ``value`` (``strict`` → identity)."""
        matcher = self._create_matcher(
            ValueIsEqualMatcher,
            value,
            any=any,
            in_array=self._in_array,
            strict=strict,
            timeout=timeout,
            delay=delay,
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def not_equal_to(  # noqa: PLR0913
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        strict: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value does not equal ``value``."""
        matcher = self._create_matcher(
            ValueIsNotEqualMatcher,
            value,
            any=any,
            in_array=self._in_array,
            strict=strict,
            timeout=timeout,
            delay=delay,
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def greater_than(  # noqa: PLR0913
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        or_equal: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value is greater than ``value`` (``or_equal`` → ≥)."""
        matcher = self._create_matcher(
            ValueIsGreaterMatcher,
            value,
            any=any,
            in_array=self._in_array,
            or_equal=or_equal,
            timeout=timeout,
            delay=delay,
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def lesser_than(  # noqa: PLR0913
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        or_equal: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value is lesser than ``value`` (``or_equal`` → ≤)."""
        matcher = self._create_matcher(
            ValueIsLesserMatcher,
            value,
            any=any,
            in_array=self._in_array,
            or_equal=or_equal,
            timeout=timeout,
            delay=delay,
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def has_length(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert ``len(value)`` of the resolved value equals ``value``."""
        matcher = self._create_matcher(
            ValueLengthEqualMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def has_length_greater(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert ``len(value)`` of the resolved value is greater than ``value``."""
        matcher = self._create_matcher(
            ValueLengthGreaterMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def has_length_lesser(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert ``len(value)`` of the resolved value is lesser than ``value``."""
        matcher = self._create_matcher(
            ValueLengthLesserMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def is_url(  # noqa: PLR0913
        self,
        *,
        reason: str = "",
        any: bool = False,
        is_live: bool = False,
        allowed_protocols: list[str] | None = None,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value is a valid URL (optionally live/2xx)."""
        matcher = self._create_matcher(
            ValueIsUrlMatcher,
            None,
            any=any,
            in_array=self._in_array,
            is_live=is_live,
            allowed_protocols=allowed_protocols,
            timeout=timeout,
            delay=delay,
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def match_regex(
        self,
        pattern: str,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value matches ``pattern`` (regex)."""
        matcher = self._create_matcher(
            ValueRegexMatcher, re.compile(pattern), any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def contains_dict(
        self,
        dct: dict,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved dict contains every key/value from ``dct``."""
        matcher = self._create_matcher(
            ValueContainsDictMatcher, dct, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def startswith(
        self,
        value: str,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved string starts with ``value``."""
        matcher = self._create_matcher(
            ValueStartsWithMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def endswith(
        self,
        value: str,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved string ends with ``value``."""
        matcher = self._create_matcher(
            ValueEndsWithMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def empty(
        self,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value is empty (falsy)."""
        matcher = self._create_matcher(
            ValueIsEmpty, None, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def not_empty(
        self,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value is not empty (truthy)."""
        matcher = self._create_matcher(
            ValueIsNotEmpty, None, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def has_date(
        self,
        value: date | datetime,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved date/datetime equals ``value``."""
        matcher = self._create_matcher(
            ValueDateEqualMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def has_date_greater(
        self,
        value: date | datetime,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved date/datetime is greater than ``value``."""
        matcher = self._create_matcher(
            ValueDateGreaterMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def has_date_lesser(
        self,
        value: date | datetime,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved date/datetime is lesser than ``value``."""
        matcher = self._create_matcher(
            ValueDateLesserMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def is_in(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value is a member of ``value``."""
        matcher = self._create_matcher(
            ValueIsInMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def is_not_in(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved value is not a member of ``value``."""
        matcher = self._create_matcher(
            ValueIsNotInMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def is_subset(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved iterable is a subset of ``value``."""
        matcher = self._create_matcher(
            ValueIsSubsetMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    def is_disjoint(
        self,
        value: Any,
        /,
        *,
        reason: str = "",
        any: bool = False,
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> AssertField:
        """Assert the resolved iterable is disjoint from ``value``."""
        matcher = self._create_matcher(
            ValueIsDisjointMatcher, value, any=any, in_array=self._in_array, timeout=timeout, delay=delay
        )
        assert_that(self._context, matcher, reason=reason)

        return self

    @contextmanager
    def raise_exc(
        self,
        expected_exc: type[Exception] | tuple[type[Exception], ...],
        /,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Generator[Any, None, None]:
        """Assert that accessing the value raises one of ``expected_exc``.

        Yields the value; any raised exception is matched against ``expected_exc``.
        """
        if not isinstance(expected_exc, tuple):
            expected_exc = (expected_exc,)

        raised_exc: Exception | None = None

        try:
            yield self._context.value
        except Exception as exc:
            raised_exc = exc

        matcher = self._create_matcher(RaisedExceptionMatcher, (expected_exc, raised_exc), timeout=timeout, delay=delay)
        assert_that(self._context, matcher, reason=reason)

    @contextmanager
    def not_raise_exc(
        self,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Generator[Any, None, None]:
        """Assert that accessing the value raises no exception.

        Yields the value; any raised exception fails the assertion.
        """
        raised_exc: Exception | None = None

        try:
            yield self._context.value
        except Exception as exc:
            raised_exc = exc

        matcher = self._create_matcher(NotRaisedExceptionMatcher, raised_exc, timeout=timeout, delay=delay)
        assert_that(self._context, matcher, reason=reason)
