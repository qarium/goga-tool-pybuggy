"""Response-level assert dispatcher of the `pybuggy.api.asserts` cell.

``Expected`` is the two-level assert entry point:

- **response-level** methods (``has_status_code``/``has_header``/``json_*``/
  ``jsonschema_*``) — matchcrest matchers over a :class:`ResponseContext`;
- **field-level** dispatch via ``Expected.__call__(search)`` → :class:`AssertField`
  (dotted-path or jsonpath search through the body, with ``data_key``/``error_key``
  prefixing).

The check configuration (status/data_key/error_key/schemas_dir/timeout/delay/
assert_field_class/assert_response_class) is carried by an :class:`AssertConfig`
value; ``is_negative`` is a runtime flag selecting the negative auto-check path
and field root. Every check is a matchcrest ``assert_that`` returning ``self``
for chaining.

Polling: the ``timeout``/``delay`` from ``AssertConfig`` are the baseline —
``_create_matcher`` injects them into every matcher, and matchcrest retries
(re-fetching the response via ``BaseContext.update`` → ``response.reload()``)
until the assertion passes or the timeout elapses. Each check method also
accepts ``timeout``/``delay`` kwargs that override the baseline for that one
assertion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...matchcrest import (
    JsonContainsKeyMatcher,
    JsonHasDataByKeyMatcher,
    JsonHasNotDataByKeyMatcher,
    JsonschemaMatcher,
    ResponseCodeMatcher,
    ResponseHeadersByKeyMatcher,
    ResponseHeadersByValueMatcher,
    assert_that,
)
from .base import BaseAssert, load_assert_class
from .config import AssertConfig
from .contexts import (
    JsonFieldContext,
    JsonPathFieldContext,
    ResponseContext,
    SearchItem,
)
from .field import AssertField

if TYPE_CHECKING:
    import resq.http


_JSONPATH_CHARS = ("$", "[", "]", "*", "(", ")", "..", "{", "}", "|", ":", "?", "!", "&", "=", "<", ">", "~")


def _search_is_jsonpath(search: str) -> bool:
    """Return True when ``search`` looks like a jsonpath expression."""
    return any(char in search for char in _JSONPATH_CHARS)


class Expected(BaseAssert):
    """Dispatcher of response-level checks and field-level assert entry.

    Response-level checks are matchcrest assertions over a ``ResponseContext``
    and return ``self`` for fluent chaining. Calling the dispatcher
    (``expected('data.items')``) returns an :class:`AssertField` for field-level
    checks.

    This is also the default response-level assert class: when
    ``AssertConfig.assert_response_class`` is set, ``ResponseWrapper`` loads that
    subclass instead (it must subclass ``Expected``).

    Args:
        response: the raw ``resq.http.Response`` under inspection.
        config: the static check configuration — status/data_key/error_key/
            schemas_dir/timeout/delay/assert_field_class/assert_response_class
            (each optional; ``None`` skips/disables that check).
        is_negative: selects the negative auto-check path and field root.
    """

    def __init__(
        self,
        response: resq.http.Response,
        config: AssertConfig,
        is_negative: bool = False,
    ) -> None:
        self._response = response
        self._config = config
        self._is_negative = is_negative
        self._timeout = config.timeout
        self._delay = config.delay

    def _response_context(self, search: str) -> ResponseContext:
        """Build a response-level context for one of status/json/headers."""
        return ResponseContext(
            self._response,
            is_negative=self._is_negative,
            search_history=[SearchItem(search=search)],
        )

    def has_status_code(
        self,
        code: int,
        /,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Expected:
        """Assert the response status code equals ``code``."""
        matcher = self._create_matcher(ResponseCodeMatcher, code, timeout=timeout, delay=delay)
        assert_that(self._response_context("status"), matcher, reason=reason)

        return self

    def has_header(  # noqa: PLR0913
        self,
        key: str,
        value: str | None = None,
        /,
        *,
        contains: bool | None = None,
        startswith: bool | None = None,
        endswith: bool | None = None,
        count: int | None = None,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Expected:
        """Assert a header is present, and — when ``value`` is given — matches it.

        Without ``value``: assert a header named ``key`` exists (optionally
        filtered by ``contains``/``startswith``/``endswith`` and counted).
        With ``value``: assert that header's value matches (equals by default,
        or ``contains``/``startswith``/``endswith``).
        """
        context = self._response_context("headers")

        if count is not None and value is not None:
            raise ValueError('Invalid parameters combination, "count" can be used without "value" only.')

        # matchcrest's by-value matcher compares ``k.lower() == self.key`` and the
        # by-key matcher lowercases its expected value internally, so a lowercase
        # key works for both — let callers pass any-case header names.
        lookup_key = key.lower()

        if value is None:
            matcher = self._create_matcher(
                ResponseHeadersByKeyMatcher,
                lookup_key,
                count=count,
                contains=contains,
                startswith=startswith,
                endswith=endswith,
                timeout=timeout,
                delay=delay,
            )
        else:
            matcher = self._create_matcher(
                ResponseHeadersByValueMatcher,
                value,
                key=lookup_key,
                contains=contains,
                startswith=startswith,
                endswith=endswith,
                timeout=timeout,
                delay=delay,
            )

        assert_that(context, matcher, reason=reason)

        return self

    def json_has_data_by_key(
        self,
        key: str,
        /,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Expected:
        """Assert the response body contains ``key`` with a non-None value."""
        matcher = self._create_matcher(JsonHasDataByKeyMatcher, key, timeout=timeout, delay=delay)
        assert_that(self._response_context("json"), matcher, reason=reason)

        return self

    def json_has_not_data_by_key(
        self,
        key: str,
        /,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Expected:
        """Assert the response body does not contain ``key`` (or it is None)."""
        matcher = self._create_matcher(JsonHasNotDataByKeyMatcher, key, timeout=timeout, delay=delay)
        assert_that(self._response_context("json"), matcher, reason=reason)

        return self

    def json_contains_key(
        self,
        key: str | list[str],
        /,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Expected:
        """Assert the response body contains ``key`` (nested when given a list)."""
        matcher = self._create_matcher(JsonContainsKeyMatcher, key, timeout=timeout, delay=delay)
        assert_that(self._response_context("json"), matcher, reason=reason)

        return self

    def jsonschema_is_valid(
        self,
        schema: dict | str,
        /,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Expected:
        """Validate the response body against a json-schema (dict or file path)."""
        schema_dict = self._load_schema(schema)
        self._validate_schema(schema_dict, reason=reason, timeout=timeout, delay=delay)

        return self

    def jsonschemas_is_valid(
        self,
        schemas_dir: str | Path,
        status_code: int,
        /,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> Expected:
        """Validate the body against the first ``<status_code>*`` schema in a dir."""
        schema_dict = self._first_schema_for_status(Path(schemas_dir), status_code)
        if schema_dict is None:
            return self

        self._validate_schema(schema_dict, reason=reason, timeout=timeout, delay=delay)

        return self

    def __call__(
        self,
        search: str | None = None,
        /,
        *,
        index: int | None = None,
        hook: Any = None,
        in_array: bool = False,
    ) -> AssertField:
        """Start a field-level assert at ``search`` (dotted path or jsonpath).

        When ``AssertConfig.assert_field_class`` is set, the configured
        ``AssertField`` subclass is loaded (it must subclass ``AssertField``);
        otherwise the built-in ``AssertField`` is used. The config baseline
        ``timeout``/``delay`` are forwarded so the field's checks poll too.

        Args:
            search: a dotted path (``a.b.c``), a jsonpath (``$.a.b[*]``), or None
                to target the whole (key-rooted) body.
            index: an optional list index applied after the search.
            hook: an optional callable applied to the resolved value.
            in_array: treat the resolved value as a list for element-wise options.

        Returns:
            An :class:`AssertField` ready for chaining.

        Raises:
            TypeError: when ``hook`` is given but not callable.
        """
        if hook is not None and not callable(hook):
            raise TypeError("Hook should be callable type")

        search_item = SearchItem(search=search, index=index, hook=hook)
        context_cls = JsonPathFieldContext if (search is None or _search_is_jsonpath(search)) else JsonFieldContext

        context = context_cls(
            self._response,
            data_key=self._config.data_key,
            error_key=self._config.error_key,
            is_negative=self._is_negative,
            search_history=[search_item],
        )

        field_cls = AssertField
        if self._config.assert_field_class is not None:
            field_cls = load_assert_class(self._config.assert_field_class, AssertField)

        return field_cls(
            context,
            is_negative=self._is_negative,
            in_array=in_array,
            timeout=self._timeout,
            delay=self._delay,
        )

    def autocheck(self) -> None:
        """Run the configured auto-check once, selecting the path by is_negative."""
        if self._is_negative:
            self._autocheck_negative()
        else:
            self._autocheck_positive()

    def _autocheck_positive(self) -> None:
        if self._config.status is not None:
            self.has_status_code(self._config.status)

        self._response.json()

        if self._config.error_key is not None:
            self.json_has_not_data_by_key(self._config.error_key)

        if self._config.data_key is not None:
            self.json_has_data_by_key(self._config.data_key)

        schema_dict = self._first_schema_for_status(self._config.schemas_dir, self._response.status_code)
        if schema_dict is not None:
            self._validate_schema(schema_dict)

    def _autocheck_negative(self) -> None:
        self._response.json()

        if self._config.data_key is not None:
            self.json_has_not_data_by_key(self._config.data_key)

        if self._config.error_key is not None:
            self.json_has_data_by_key(self._config.error_key)

    def _validate_schema(
        self,
        schema_dict: dict,
        *,
        reason: str = "",
        timeout: int | float | None = None,
        delay: int | float | None = None,
    ) -> None:
        matcher = self._create_matcher(JsonschemaMatcher, schema_dict, timeout=timeout, delay=delay)
        assert_that(self._response_context("json"), matcher, reason=reason)

    @staticmethod
    def _load_schema(schema: dict | str) -> dict:
        if isinstance(schema, str):
            return json.loads(Path(schema).read_text(encoding="utf-8"))

        return schema

    @staticmethod
    def _first_schema_for_status(schemas_dir: Path | None, status_code: int) -> dict | None:
        if schemas_dir is None or not schemas_dir.is_dir():
            return None

        for schema_file in sorted(schemas_dir.glob(f"{status_code}*")):
            return json.loads(schema_file.read_text(encoding="utf-8"))

        return None
