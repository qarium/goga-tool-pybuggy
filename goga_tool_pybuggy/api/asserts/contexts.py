"""Search contexts for `goga_tool_pybuggy.api` asserts.

Each context is a matchcrest ``BaseContext``: matchers read the value under test
from ``value`` and use ``key`` only as a label in mismatch messages.

pybuggy-specific constraints:

- wraps a ``resq.http.Response``;
- field paths always resolve from the root of the response body — there is no
  configurable root key, so a search must spell out the full path;
- pybuggy ships plain classes (no reporting layer), but polling is supported:
  ``update()`` re-fetches the response in place via
  ``resq.http.Response.reload()`` so matchcrest's retry loop observes fresh data;
- ``resq.http.Response`` has no ``.request``, so the response-level ``key`` is
  derived from the response URL rather than ``[method] path_url``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import reduce
from typing import TYPE_CHECKING, Any

from jsonpath_ng.ext import parse as create_jsonpath

from ...matchcrest import BaseContext as _BaseContext

if TYPE_CHECKING:
    import resq.http


@dataclass(frozen=True)
class SearchItem:
    """A single step of a field search history.

    Attributes:
        search: a dotted path (``a.b.c``), a jsonpath (``$.a.b[*]``), or None.
        index: an optional list index applied after the search.
        hook: an optional callable applied to the resolved value.
    """

    search: str | None = None
    index: int | None = None
    hook: Any = None


class BaseContext(_BaseContext):
    """Base context holding a response and a search history.

    Calling a context (``ctx(search=..., index=..., hook=...)``) returns a new
    context with the step appended to the history — enabling fluent drill-down
    on an ``AssertField``.

    Args:
        response: the raw ``resq.http.Response`` under inspection.
        search_history: ordered list of ``SearchItem`` steps.
    """

    def __init__(
        self,
        response: resq.http.Response,
        search_history: list[SearchItem] | None = None,
    ) -> None:
        self._response = response
        self._search_history: list[SearchItem] = [] if search_history is None else search_history

    def __call__(
        self,
        search: str | None = None,
        index: int | None = None,
        hook: Any = None,
    ) -> BaseContext:
        """Return a new context with one more search step appended.

        Args:
            search: a dotted path, a jsonpath, or None.
            index: an optional list index applied after the search.
            hook: an optional callable applied to the resolved value.

        Returns:
            A new context of the same class over the extended history; the
            original context's history is left untouched (immutable chain).
        """
        history = [*self._search_history, SearchItem(search=search, index=index, hook=hook)]

        return self.__class__(
            self._response,
            search_history=history,
        )

    @property
    def search(self) -> str:
        """Human-readable join of the search steps (label only)."""
        return " -> ".join(
            (
                f"{item.search}[{item.index}]{'[hook]' if item.hook else ''}"
                if item.index is not None
                else f"{item.search}{'[hook]' if item.hook else ''}"
                for item in self._search_history
                if item.search is not None
            ),
        )

    def update(self) -> None:
        """Re-fetch the response for the next polling attempt.

        Delegates to ``resq.http.Response.reload()``, which re-executes the
        stored request recipe in place (same object, refreshed ``_underlying``)
        so every cached read observes the new data. Called by matchcrest's
        retry loop between attempts.
        """
        self._response.reload()


class ResponseContext(BaseContext):
    """Context for response-level checks, keyed by a fixed search token.

    ``value`` resolves one of ``status`` / ``json`` / ``headers`` from the
    response; ``key`` is the response URL (a label for messages).
    """

    @property
    def value(self) -> Any:
        item = self._search_history[0]
        search = item.search

        if search is None:
            raise ValueError('"search" should be set')
        if search == "status":
            return self._response.status_code
        if search == "json":
            return self._response.json()
        if search == "headers":
            return self._response.headers

        raise ValueError(f'Unknown search "{search}"')

    @property
    def key(self) -> str | None:
        return self._response.url


class JsonFieldContext(BaseContext):
    """Field context resolving a dotted path (``a.b.c``) against the body root.

    Each history step drills by dotted keys from the response-body root, then
    optional ``index``, then optional ``hook``.
    """

    @property
    def value(self) -> Any:
        data = self._response.json()

        for item in self._search_history:
            if item.search is not None:
                keys = item.search.split(".")
                try:
                    data = reduce(lambda current, key: current[key], keys, data)
                except (KeyError, TypeError) as exc:
                    raise AssertionError(f'No results for path "{item.search}"') from exc
            if item.index is not None:
                data = data[item.index]
            if item.hook is not None:
                data = item.hook(data)

        return data

    @property
    def key(self) -> str | None:
        search_list = [item.search for item in self._search_history if item.search is not None]

        return ".".join(search_list)


class JsonPathFieldContext(BaseContext):
    """Field context resolving a jsonpath (``$.a.b[*]``) against the body root.

    Uses ``jsonpath_ng.ext``; the first match is taken (or the full list when the
    expression contains a slice/``*``). Falls back to dotted-style ``index`` and
    ``hook`` post-processing shared with :class:`JsonFieldContext`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.__data: Any = None
        self.__matches: list[Any] | None = None

    @property
    def value(self) -> Any:
        self._init_data_if_not_exists()

        return self.__data

    @property
    def key(self) -> str | None:
        self._init_data_if_not_exists()

        assert self.__matches is not None
        search_list = [self._match_to_string(match) for match in self.__matches]

        return ".".join(search_list)

    def _init_data_if_not_exists(self) -> None:
        if self.__data is not None and self.__matches is not None:
            return

        self.__data = self._response.json()

        self.__matches = []

        for item in self._search_history:
            if item.search is not None:
                expr = create_jsonpath(item.search)
                result = expr.find(self.__data)

                if len(result) == 0:
                    raise AssertionError(f'No results for jsonpath "{item.search}"')

                self.__matches.append(result[0])
                self.__data = [match.value for match in result]

                if not self._has_slice(item.search):
                    self.__data = self.__data[0]
            if item.index is not None:
                self.__data = self.__data[item.index]
            if item.hook is not None:
                self.__data = item.hook(self.__data)

    @staticmethod
    def _has_slice(expression: str) -> bool:
        return (
            "[*]" in expression
            or re.search(r"\[\d+:\d+]", expression) is not None
            or re.search(r"\[\d+:]", expression) is not None
            or re.search(r"\[:\d+]", expression) is not None
        )

    @staticmethod
    def _match_to_string(match: Any) -> str:
        full_path = str(match.full_path)

        for index_expr in re.findall(r"\[\d+]", full_path):
            full_path = full_path.replace(index_expr, "")

        for dots in re.findall(r"[.]{2,}", full_path):
            full_path = full_path.replace(dots, ".")

        return full_path.strip(".")

    def update(self) -> None:
        super().update()

        self.__data = None
        self.__matches = None
