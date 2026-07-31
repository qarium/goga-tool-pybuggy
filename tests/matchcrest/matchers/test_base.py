"""Contract and branch tests for the matchcrest matcher base infrastructure."""

import pytest
from goga_tool_pybuggy.matchcrest.matchers import BaseContext, BaseMatcher, MatchResult


class TestBaseContext:
    """Abstract data-source context defaults."""

    def test_value_raises_not_implemented(self):
        """The default ``value`` property is abstract."""
        with pytest.raises(NotImplementedError):
            _ = BaseContext().value

    def test_key_raises_not_implemented(self):
        """The default ``key`` property is abstract."""
        with pytest.raises(NotImplementedError):
            _ = BaseContext().key

    def test_update_raises_not_implemented(self):
        """The default ``update`` method is abstract."""
        with pytest.raises(NotImplementedError):
            BaseContext().update()


class TestMatchResult:
    """Outcome of a matcher's _assert."""

    def test_positive_result_is_truthy(self):
        """A positive result is truthy with empty message lists."""
        result = MatchResult(True)

        assert bool(result) is True
        assert result.errors == []
        assert result.expectations == []

    def test_negative_result_carries_messages(self):
        """A negative result is falsy and carries its messages."""
        result = MatchResult(False, errors=["bad"], expectations=["good"])

        assert bool(result) is False
        assert result.errors == ["bad"]
        assert result.expectations == ["good"]

    def test_negative_without_errors_raises(self):
        """A negative result requires non-empty errors."""
        with pytest.raises(AssertionError):
            MatchResult(False, expectations=["good"])

    def test_negative_without_expectations_raises(self):
        """A negative result requires non-empty expectations."""
        with pytest.raises(AssertionError):
            MatchResult(False, errors=["bad"])

    def test_none_messages_default_to_empty_lists(self):
        """``None`` messages are exposed as empty lists."""
        result = MatchResult(True, errors=None, expectations=None)

        assert result.errors == []
        assert result.expectations == []


class _StubContext(BaseContext):
    """Minimal concrete context for BaseMatcher tests."""

    def __init__(self):
        self.updates = 0

    @property
    def value(self):
        return 1

    @property
    def key(self):
        return "stub"

    def update(self):
        self.updates += 1


class _RecordingDescription:
    """Stand-in for ``hamcrest.core.description.Description`` capturing appended text."""

    def __init__(self):
        self.text = ""

    def append_text(self, text):
        self.text += text
        return self


class TestBaseMatcher:
    """Retry/timeout engine and reporting contract."""

    def test_assert_is_abstract(self):
        """The ``_assert`` hook raises NotImplementedError until implemented."""
        with pytest.raises(NotImplementedError):
            BaseMatcher()._assert(_StubContext())

    def test_matches_positive_returns_true(self):
        """A positive _assert yields a truthy _matches and a truthy result."""

        class AlwaysOk(BaseMatcher):
            def _assert(self, item):
                return MatchResult(True)

        matcher = AlwaysOk()

        assert matcher._matches(_StubContext()) is True
        assert bool(matcher.result) is True

    def test_matches_negative_populates_result(self):
        """A negative _assert yields False and stores the messages."""

        class AlwaysBad(BaseMatcher):
            def _assert(self, item):
                return MatchResult(False, errors=["bad"], expectations=["good"])

        matcher = AlwaysBad()

        assert matcher._matches(_StubContext()) is False
        assert matcher.result.errors == ["bad"]
        assert matcher.result.expectations == ["good"]

    def test_proof_count_repeats_assert_and_updates_between_tries(self):
        """``proofs`` repeats _assert, calling ``update()`` between attempts."""

        class Counting(BaseMatcher):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.asserts = 0

            def _assert(self, item):
                self.asserts += 1
                return MatchResult(True)

        context = _StubContext()
        matcher = Counting(proofs=3)

        assert matcher._matches(context) is True
        assert matcher.asserts == 3
        assert context.updates == 2

    def test_unknown_error_when_assert_leaves_result_none(self):
        """A None _assert result triggers the 'unknown error' fallback."""

        class ReturnsNone(BaseMatcher):
            def _assert(self, item):
                return None

        matcher = ReturnsNone()

        assert matcher._matches(_StubContext()) is False
        assert matcher.result.errors == ["unknown error, result is None"]

    def test_timeout_retries_until_success(self):
        """With a timeout set, _matches retries until _assert succeeds."""

        class SucceedsOnThird(BaseMatcher):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.tries = 0

            def _assert(self, item):
                self.tries += 1
                if self.tries >= 3:
                    return MatchResult(True)
                return MatchResult(False, errors=["not yet"], expectations=["third try"])

        matcher = SucceedsOnThird(timeout=2, delay=0)

        assert matcher._matches(_StubContext()) is True
        assert matcher.tries >= 3

    def test_timeout_exhaustion_yields_failure(self):
        """When _assert never succeeds within the timeout, _matches fails after exhausting retries."""

        class AlwaysBad(BaseMatcher):
            def _assert(self, item):
                return MatchResult(False, errors=["no"], expectations=["yes"])

        matcher = AlwaysBad(timeout=0.05, delay=0)

        assert matcher._matches(_StubContext()) is False
        assert matcher.result.errors == ["no"]

    def test_describe_to_renders_expectations(self):
        """``describe_to`` appends the stored expectation messages."""

        class WithExpectation(BaseMatcher):
            def _assert(self, item):
                return MatchResult(False, errors=["err"], expectations=["exp"])

        matcher = WithExpectation()
        matcher._matches(_StubContext())

        description = _RecordingDescription()
        matcher.describe_to(description)

        assert description.text == "exp"
