import typing as t
from pprint import pformat

from .base import (
    BaseContext,
    BaseMatcher,
    MatchResult,
)


class RaisedExceptionMatcher(BaseMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        raised_exc: t.Optional[Exception]
        expected_exc: tuple[type[Exception], ...]
        expected_exc, raised_exc = self.expected_value

        expected_exc_names = ", ".join([e.__name__ for e in expected_exc])

        errors: list[str] = []
        expectations = [
            f'"{item.key}" should raise an exception {pformat(expected_exc_names)}',
        ]

        if raised_exc is None:
            return MatchResult(False, errors=["No exception was raised"], expectations=expectations)

        if isinstance(raised_exc, expected_exc):
            return MatchResult(True)

        message = " ".join(str(i) for i in raised_exc.args)
        errors.append(
            f"exception {pformat(raised_exc.__class__.__name__)} was raised with message {pformat(message)}",
        )

        return MatchResult(False, errors=errors, expectations=expectations)


class NotRaisedExceptionMatcher(BaseMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'"{item.key}" should not raise an exception',
        ]

        if self.expected_value is not None:
            message = " ".join(str(i) for i in self.expected_value.args)
            errors.append(
                f"exception {pformat(self.expected_value.__class__.__name__)} "
                f"was raised with message {pformat(message)}",
            )

        if errors:
            return MatchResult(False, errors=errors, expectations=expectations)

        return MatchResult(True)
