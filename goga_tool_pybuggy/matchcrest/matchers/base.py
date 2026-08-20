import contextlib
import time
import typing as t

from hamcrest.core.base_matcher import BaseMatcher as _BaseMatcher
from hamcrest.core.description import Description

from ..utils import allow_failure, waiting_for


class BaseContext:
    @property
    def value(self) -> t.Any:
        raise NotImplementedError(
            f'Property "value" is not implemented in "{self.__class__.__name__}"',
        )

    @property
    def key(self) -> t.Optional[str]:
        raise NotImplementedError(
            f'Property "key" is not implemented in "{self.__class__.__name__}"',
        )

    def update(self):
        raise NotImplementedError(
            f'Method "update" is not implemented in "{self.__class__.__name__}"',
        )


class MatchResult:
    def __init__(
        self,
        result: bool,
        *,
        errors: t.Optional[list[str] | tuple[str]] = None,
        expectations: t.Optional[list[str]] = None,
    ):
        self._result = result

        self._errors = errors
        self._expectations = expectations

        if not self._result:
            assert self._errors, '"errors" is required for negative result'
            assert self._expectations, '"expectations" is required for negative result'

    def __bool__(self):
        return self._result

    @property
    def errors(self):
        return self._errors or []

    @property
    def expectations(self):
        return self._expectations or []


class BaseMatcher(_BaseMatcher):
    def __init__(
        self,
        expected_value: t.Any = None,
        *,
        proofs: t.Optional[int] = None,
        timeout: t.Optional[int] = None,
        delay: t.Optional[int | float] = None,
    ):
        self.expected_value = expected_value

        self._proofs = proofs or 1
        self._timeout = timeout
        self._delay = delay

        self._tries = 0

        self.item: t.Optional[BaseContext] = None
        self.result: t.Optional[MatchResult] = None

        super().__init__()

    def _assert(self, item: BaseContext) -> MatchResult:
        raise NotImplementedError(
            f'Method "_assert" is not implemented in "{self.__class__.__name__}"',
        )

    def _matches(self, item: BaseContext) -> bool:
        self.item = item

        with contextlib.suppress(TimeoutError):
            self.__matches__(item) if self._timeout is None else waiting_for(
                self.__matches__, args=[item], timeout=self._timeout, delay=self._delay
            )

        if self.result is None:
            self.result = MatchResult(
                False, errors=["unknown error, result is None"], expectations=['result set by "_assert" method']
            )

        if not bool(self.result):
            self.__save_report__()

        return bool(self.result)

    def __matches__(self, item: BaseContext) -> bool:
        for i in range(self._proofs):
            self.__assert_try(item)

            if not bool(self.result):
                return bool(self.result)

            if self._delay is not None and i < self._proofs - 1:
                time.sleep(self._delay)

        return bool(self.result)

    def __assert_try(self, item: BaseContext) -> None:
        if self._tries > 0:
            item.update()

        self.result = self._assert(item)
        self._tries += 1

    @allow_failure
    def __save_report__(self):
        pass

    def describe_to(self, description: Description):
        for index, msg in enumerate(self.result.expectations):
            description.append_text(msg if index == 0 else f", {msg}")

    def describe_mismatch(self, _, mismatch_description: Description):
        for index, msg in enumerate(self.result.errors):
            mismatch_description.append_text(msg if index == 0 else f", {msg}")
