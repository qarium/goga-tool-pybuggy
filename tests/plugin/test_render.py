"""Tests for the `goga_tool_pybuggy.plugin.render` cell (`render_base_url`).

Mirrors the source layout (`tests/plugin/test_render.py`). Covers the contract
surface (importability + presence of `render_base_url`) and the rendering
behavior: Jinja2 variable substitution, `StrictUndefined`, the `match_re` test,
plain-URL backward compatibility, and URL whitespace normalization.

Whitespace normalization is the URL-specific behavior of `render_base_url`: a
URL never legitimately contains literal whitespace (it would be percent-encoded
to `%20` and break the request path), so every whitespace run in the rendered
result is removed. This is what makes multi-line `base_url` templates — whether
a YAML folded scalar (`>`) or a literal block scalar (`|`) — render to a single
clean URL in both conditional branches.
"""

import jinja2
import pytest
from goga_tool_pybuggy.plugin.render import _match_re, render_base_url


class TestRenderBaseUrlContract:
    """Contract tests for `render_base_url`."""

    def test_render_base_url_importable_from_location(self):
        import goga_tool_pybuggy.plugin.render as render_module

        assert render_module.render_base_url is render_base_url

    def test_render_base_url_is_callable(self):
        assert callable(render_base_url)

    def test_match_re_test_is_registered_helper(self):
        # _match_re is the regex-match helper backing the registered match_re test.
        assert _match_re("feature-123", "^feature-.*$") is True
        assert _match_re("1.2.3", "^feature-.*$") is False


class TestRenderBaseUrlRendering:
    """Jinja2 rendering behavior: substitution, StrictUndefined, match_re, backward compat."""

    def test_plain_url_renders_to_itself(self):
        # A plain URL without Jinja placeholders renders to itself (backward compat).
        assert render_base_url("https://plain.example/api", {}) == "https://plain.example/api"

    def test_renders_jinja_variable(self):
        assert render_base_url("http://{{ env }}.svc.example/api", {"env": "dev"}) == ("http://dev.svc.example/api")

    def test_renders_multiple_variables(self):
        assert (
            render_base_url(
                "https://{{ env }}.svc.example/api/{{ version }}",
                {
                    "env": "dev",
                    "version": "1.2",
                },
            )
            == "https://dev.svc.example/api/1.2"
        )

    def test_match_re_conditional_match(self):
        template = "http://x/api/v1{% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}"

        assert render_base_url(template, {"v": "feature-123"}) == "http://x/api/v1-feature-123"

    def test_match_re_conditional_no_match(self):
        template = "http://x/api/v1{% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}"

        assert render_base_url(template, {"v": "1.2.3"}) == "http://x/api/v1"

    def test_unknown_variable_raises(self):
        # StrictUndefined: an unknown variable raises, not a silent empty URL.
        with pytest.raises(jinja2.UndefinedError):
            render_base_url("http://{{ undefined_var }}.svc.example", {})


class TestRenderBaseUrlWhitespaceNormalization:
    """URL whitespace normalization — the fix for multi-line templates.

    These template strings mirror what YAML produces AFTER parsing a multi-line
    `base_url`: a folded scalar (`>`) folds newlines into spaces, and a literal
    block scalar (`|`) keeps them. `render_base_url` must strip every whitespace
    run so the URL is clean in both conditional branches (the trailing space
    left by an empty conditional, and the internal space left before a matched
    conditional suffix).
    """

    def test_strips_leading_and_trailing_whitespace(self):
        # Leading/trailing whitespace is never valid in a URL.
        assert render_base_url("  https://x.example/api  ", {}) == "https://x.example/api"

    def test_strips_trailing_space_from_empty_conditional(self):
        # The reported bug: a folded scalar puts a space before `{% if %}`, and an
        # empty (no-match) conditional leaves it as a trailing space -> `%20`.
        template = "http://{{ env }}.svc.example/api/v1 {% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}\n"

        assert render_base_url(template, {"env": "stage-el", "v": "1.2.3"}) == ("http://stage-el.svc.example/api/v1")

    def test_strips_internal_space_from_matched_conditional(self):
        # Same root cause, matched branch: the space before `{% if %}` would land
        # in the middle of the URL (`/api/v1 -feature-123` -> `/api/v1%20-feature-123`).
        template = "http://{{ env }}.svc.example/api/v1 {% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}\n"

        assert render_base_url(template, {"env": "stage-el", "v": "feature-123"}) == (
            "http://stage-el.svc.example/api/v1-feature-123"
        )

    def test_strips_newlines_from_literal_block_template(self):
        # A literal block scalar (`|`) keeps the newline between the URL line and
        # the conditional line; it must not survive into the rendered URL.
        template = "http://{{ env }}.svc.example/api/v1\n{% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}"

        assert render_base_url(template, {"env": "stage-el", "v": "feature-123"}) == (
            "http://stage-el.svc.example/api/v1-feature-123"
        )
        assert render_base_url(template, {"env": "stage-el", "v": "1.2.3"}) == ("http://stage-el.svc.example/api/v1")

    def test_collapses_multiple_internal_whitespace_runs(self):
        # Several spaces/tabs/newlines collapse to nothing — the URL is one token.
        assert render_base_url("http://h/\ta\t b\n/c", {}) == "http://h/ab/c"

    def test_plain_url_with_no_whitespace_is_unchanged(self):
        # Normalization is a no-op for an already-clean URL.
        assert render_base_url("https://x.example/api/v1", {}) == "https://x.example/api/v1"
