"""Assert configuration of the `pybuggy.api.asserts` cell.

``AssertConfig`` bundles the response-check configuration — the fields that
answer "what to check" — passed from ``Endpoint`` through ``ResponseWrapper``
to ``Expected``. Runtime flags (``is_negative``/``use_autocheck``) stay on the
consuming entities; ``AssertConfig`` holds only the static check parameters.

The polling options (``timeout``/``delay``) drive matchcrest's retry loop (the
context re-fetches the response via ``resq.http.Response.reload()`` between
attempts), and the pluggable-class hooks (``assert_field_class``/
``assert_response_class``) select custom assert classes by dotted import path.
``timeout``/``delay`` set here are the baseline; per-check ``timeout``/``delay``
kwargs on ``Expected``/``AssertField`` methods override them for one assertion.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class AssertConfig(BaseModel):
    """Static configuration for response-level asserts.

    Bundles the expected success status and the success/error body keys plus the
    json-schema directory so that ``Expected``/``ResponseWrapper`` accept one
    value instead of a positional parameter spread. Every field is optional;
    ``None`` means "not configured / skip that check".

    Attributes:
        status: expected success status code; ``None`` disables the status
            auto-check.
        data_key: success-body key asserted present (positive) / absent
            (negative); also the positive field-search root. ``None`` skips it.
        error_key: error-body key asserted absent (positive) / present
            (negative); also the negative field-search root. ``None`` skips it.
        schemas_dir: directory of json-schema files (``<status>*.json``) for
            auto-validation; ``None`` or a missing directory skips it.
        timeout: baseline polling timeout in seconds — when set, matchcrest
            retries each assertion (re-fetching the response) until it passes or
            the timeout elapses; ``None`` runs the assertion once.
        delay: seconds slept between polling attempts; ``None`` uses matchcrest's
            matcher default.
        assert_field_class: dotted import path (``module:Class``) of a custom
            ``AssertField`` subclass; ``None`` uses the built-in ``AssertField``.
        assert_response_class: dotted import path (``module:Class``) of a custom
            ``Expected`` subclass; ``None`` uses the built-in ``Expected``.
    """

    model_config = ConfigDict(kw_only=True)

    status: int | None = None
    data_key: str | None = None
    error_key: str | None = None
    schemas_dir: Path | None = None
    timeout: int | float | None = None
    delay: int | float | None = None
    assert_field_class: str | None = None
    assert_response_class: str | None = None
