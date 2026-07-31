"""Contract tests for the exception matchers."""


from goga_tool_pybuggy.matchcrest.matchers import (
    NotRaisedExceptionMatcher,
    RaisedExceptionMatcher,
)


class TestRaisedExceptionMatcher:
    """Assert the raised exception is one of the expected types."""

    def test_matching_type_passes(self, ctx):
        """A raised exception whose type is expected passes."""
        expected = ((ValueError,), ValueError("boom"))
        assert RaisedExceptionMatcher(expected)._matches(ctx(None)) is True

    def test_non_matching_type_fails(self, ctx):
        """A raised exception of an unexpected type fails."""
        expected = ((ValueError,), TypeError("boom"))
        assert RaisedExceptionMatcher(expected)._matches(ctx(None)) is False

    def test_no_exception_raised_fails(self, ctx):
        """No exception raised is reported as a failure."""
        expected = ((ValueError,), None)
        matcher = RaisedExceptionMatcher(expected)
        assert matcher._matches(ctx(None)) is False
        assert matcher.result.errors == ["No exception was raised"]


class TestNotRaisedExceptionMatcher:
    """Assert that no exception was raised."""

    def test_no_exception_passes(self, ctx):
        """None (no exception) passes."""
        assert NotRaisedExceptionMatcher(None)._matches(ctx(None)) is True

    def test_exception_fails(self, ctx):
        """A raised exception fails."""
        matcher = NotRaisedExceptionMatcher(ValueError("boom"))
        assert matcher._matches(ctx(None)) is False
        assert matcher.result.errors
