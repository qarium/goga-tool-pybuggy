"""Tests for the `goga_tool_pybuggy.plugin.render` cell (`render_base_url`).

Covers Jinja2 substitution, `StrictUndefined`, `match_re`, plain-URL compat, and whitespace normalization.
"""

import jinja2
import pytest
from goga_tool_pybuggy.plugin.render import _match_re, render_base_url


class TestRenderBaseUrlContract:
    """Contract tests for `render_base_url`."""

    def test_render_base_url_importable_from_location(self):
        """The `render_base_url` routine is importable from the `plugin.render` module location."""
        import goga_tool_pybuggy.plugin.render as render_module

        assert render_module.render_base_url is render_base_url

    def test_render_base_url_is_callable(self):
        """The `render_base_url` routine is callable."""
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
        """A single Jinja variable is substituted with its context value."""
        assert render_base_url("http://{{ env }}.svc.example/api", {"env": "dev"}) == ("http://dev.svc.example/api")

    def test_renders_multiple_variables(self):
        """Multiple Jinja variables are substituted with their context values."""
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
        """A `match_re` conditional renders its branch when the value matches the pattern."""
        template = "http://x/api/v1{% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}"

        assert render_base_url(template, {"v": "feature-123"}) == "http://x/api/v1-feature-123"

    def test_match_re_conditional_no_match(self):
        """A `match_re` conditional renders nothing when the value fails the pattern."""
        template = "http://x/api/v1{% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}"

        assert render_base_url(template, {"v": "1.2.3"}) == "http://x/api/v1"

    def test_unknown_variable_raises(self):
        # StrictUndefined: an unknown variable raises, not a silent empty URL.
        with pytest.raises(jinja2.UndefinedError):
            render_base_url("http://{{ undefined_var }}.svc.example", {})


class TestRenderBaseUrlWhitespaceNormalization:
    """URL whitespace normalization — the fix for multi-line templates.

    Templates mirror parsed YAML scalars; every whitespace run must be stripped.
    """

    def test_strips_leading_and_trailing_whitespace(self):
        # Leading/trailing whitespace is never valid in a URL.
        assert render_base_url("  https://x.example/api  ", {}) == "https://x.example/api"

    def test_strips_trailing_space_from_empty_conditional(self):
        # A folded scalar's space before `{% if %}` is left trailing on no-match -> `%20`.
        template = "http://{{ env }}.svc.example/api/v1 {% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}\n"

        assert render_base_url(template, {"env": "stage-el", "v": "1.2.3"}) == ("http://stage-el.svc.example/api/v1")

    def test_strips_internal_space_from_matched_conditional(self):
        # Same root cause, matched branch: the space would land mid-URL (`/api/v1%20-feature-123`).
        template = "http://{{ env }}.svc.example/api/v1 {% if v is match_re('^feature-.*$') %}-{{ v }}{% endif %}\n"

        assert render_base_url(template, {"env": "stage-el", "v": "feature-123"}) == (
            "http://stage-el.svc.example/api/v1-feature-123"
        )

    def test_strips_newlines_from_literal_block_template(self):
        # A literal block scalar (`|`) keeps the newline; it must not survive the render.
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
