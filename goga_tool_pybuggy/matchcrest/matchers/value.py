import typing as t
from collections.abc import Iterable
from datetime import date
from pprint import pformat

from ..utils import date_to_timestamp, url_is_valid
from .base import (
    BaseContext,
    BaseMatcher,
    MatchResult,
)


# pylint: disable=abstract-method
class BaseValueMatcher(BaseMatcher):
    def __init__(self, *args, **kwargs):
        self.any = kwargs.pop('any', False)
        self.in_array = kwargs.pop('in_array', False)

        if self.any and not self.in_array:
            raise ValueError(
                'Invalid parameters combination, '
                '"any" can be used with "in_array" only',
            )

        super().__init__(*args, **kwargs)


class BaseSetValueMatcher(BaseValueMatcher):
    def __init__(self, expected_value: t.Any, **kwargs):
        self._throw_if_not_iterable(expected_value)
        super().__init__(expected_value, **kwargs)

    def _throw_if_not_iterable(self, value: t.Any):
        if not isinstance(value, Iterable):
            raise ValueError(f'{self.__class__.__name__} can only be applied to iterable values')


class ValueContainsMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should contains {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if self.expected_value in value and self.any:
                return MatchResult(True)
            if self.expected_value not in value:
                errors.append(f'{pformat(self.expected_value)} not in {pformat(value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueNotContainsMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should not contains {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if self.expected_value not in value and self.any:
                return MatchResult(True)
            if self.expected_value in value:
                errors.append(f'{pformat(self.expected_value)} in {pformat(value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsEqualMatcher(BaseValueMatcher):
    def __init__(self, *args, **kwargs):
        self.strict = kwargs.pop('strict', False)

        super().__init__(*args, **kwargs)

    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should be equal {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if self.strict and self.expected_value is value and self.any:
                return MatchResult(True)
            if not self.strict and value == self.expected_value and self.any:
                return MatchResult(True)

            if self.strict and self.expected_value is not value:
                errors.append(f'{pformat(self.expected_value)} is not {pformat(value)}')
            if not self.strict and value != self.expected_value:
                errors.append(f'{pformat(self.expected_value)} != {pformat(value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsNotEqualMatcher(BaseValueMatcher):
    def __init__(self, *args, **kwargs):
        self.strict = kwargs.pop('strict', False)

        super().__init__(*args, **kwargs)

    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should be not equal {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if self.strict and self.expected_value is not value and self.any:
                return MatchResult(True)
            if not self.strict and value != self.expected_value and self.any:
                return MatchResult(True)

            if self.strict and self.expected_value is value:
                errors.append(f'{pformat(self.expected_value)} is {pformat(value)}')
            if not self.strict and value == self.expected_value:
                errors.append(f'{pformat(self.expected_value)} == {pformat(value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsGreaterMatcher(BaseValueMatcher):
    def __init__(self, *args, **kwargs):
        self.or_equal = kwargs.pop('or_equal', False)

        super().__init__(*args, **kwargs)

    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should be greater {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if self.or_equal and value >= self.expected_value and self.any:
                return MatchResult(True)
            if not self.or_equal and value > self.expected_value and self.any:
                return MatchResult(True)

            if self.or_equal and not value >= self.expected_value:
                errors.append(f'{pformat(value)} < {pformat(self.expected_value)}')
            if not self.or_equal and not value > self.expected_value:
                errors.append(
                    f'{pformat(value)} == {pformat(self.expected_value)}'
                    if value == self.expected_value else
                    f'{pformat(value)} < {pformat(self.expected_value)}'
                )

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsLesserMatcher(BaseValueMatcher):
    def __init__(self, *args, **kwargs):
        self.or_equal = kwargs.pop('or_equal', False)

        super().__init__(*args, **kwargs)

    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should be lesser {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if self.or_equal and value <= self.expected_value and self.any:
                return MatchResult(True)
            if not self.or_equal and value < self.expected_value and self.any:
                return MatchResult(True)

            if self.or_equal and not value <= self.expected_value:
                errors.append(f'{pformat(value)} > {pformat(self.expected_value)}')
            if not self.or_equal and not value < self.expected_value:
                errors.append(
                    f'{pformat(value)} == {pformat(self.expected_value)}'
                    if value == self.expected_value else
                    f'{pformat(value)} > {pformat(self.expected_value)}'
                )

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueLengthEqualMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value length from "{item.key}" should be equal {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            length = len(value)

            if self.expected_value == length and self.any:
                return MatchResult(True)

            if self.expected_value != length:
                errors.append(f'length of {pformat(value)}: {pformat(length)} != {pformat(self.expected_value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueLengthGreaterMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value length from "{item.key}" should be greater {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            length = len(value)

            if length > self.expected_value and self.any:
                return MatchResult(True)

            if length <= self.expected_value:
                message = f'{pformat(length)} == {pformat(self.expected_value)}' \
                    if length == self.expected_value else \
                    f'{pformat(length)} < {pformat(self.expected_value)}'
                errors.append(f'length of {pformat(value)}: {pformat(message)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueLengthLesserMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value length from "{item.key}" should be lesser {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            length = len(value)

            if length < self.expected_value and self.any:
                return MatchResult(True)

            if length >= self.expected_value:
                message = f'{pformat(length)} == {pformat(self.expected_value)}' \
                    if length == self.expected_value else \
                    f'{pformat(length)} > {pformat(self.expected_value)}'
                errors.append(f'length of {pformat(value)}: {pformat(message)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsUrlMatcher(BaseValueMatcher):
    def __init__(self, *args, **kwargs):
        self.is_live = kwargs.pop('is_live', False)
        self.allowed_protocols = kwargs.pop('allowed_protocols', None)

        super().__init__(*args, **kwargs)

    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" value should be match '
            f'URL RFC standard and response status code == 2xx',
        ] if self.is_live else [
            f'Value from "{item.key}" should be match URL RFC standard',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for url in current_value:
            is_valid = url_is_valid(url,
                                    is_live=self.is_live,
                                    allowed_protocols=self.allowed_protocols)

            if is_valid and self.any:
                return MatchResult(True)

            if not is_valid:
                message = f'{pformat(url)} is not valid. '
                errors.append(message + 'Check the status code and match RFC standard.'
                              if self.is_live else message + 'Check match RFC standard.')

        if not errors:
            return MatchResult(True)

        return MatchResult(False, errors=errors, expectations=expectations)


class ValueRegexMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should match regexp {pformat(self.expected_value.pattern)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            result = self.expected_value.match(value)

            if result and self.any:
                return MatchResult(True)

            if not result:
                errors.append(f'{pformat(value)} does not match regexp {pformat(self.expected_value.pattern)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueContainsDictMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should contains keys '
            f'and values from dict {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if not isinstance(value, dict):
                errors.append(f'{pformat(value)} is not type dict')
                continue

            success = True

            for key, expected_value_from_key in self.expected_value.items():
                current_value_from_key = value.get(key)

                if current_value_from_key != expected_value_from_key:
                    errors.append(
                        f'For key {pformat(key)} in dict {pformat(value)}: '
                        f'{pformat(current_value_from_key)} != {pformat(expected_value_from_key)}',
                    )
                    success = False

            if success and self.any:
                return MatchResult(True)

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueEndsWithMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should endswith {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if not isinstance(value, str):
                errors.append(f'{pformat(value)} is not string')
                continue

            if value.endswith(self.expected_value) and self.any:
                return MatchResult(True)

            if not value.endswith(self.expected_value):
                errors.append(f'{pformat(value)} does not endswith {pformat(self.expected_value)}')

        if errors:
            return MatchResult(False, errors=errors, expectations=expectations)

        return MatchResult(True)


class ValueStartsWithMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should startswith {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if not isinstance(value, str):
                errors.append(f'{pformat(value)} is not string')
                continue

            if value.startswith(self.expected_value) and self.any:
                return MatchResult(True)

            if not value.startswith(self.expected_value):
                errors.append(f'{pformat(value)} does not startswith {pformat(self.expected_value)}')

        if errors:
            return MatchResult(False, errors=errors, expectations=expectations)

        return MatchResult(True)


class ValueIsEmpty(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should be empty',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if not bool(value) and self.any:
                return MatchResult(True)

            if bool(value):
                errors.append(f'{pformat(value)} is not empty')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsNotEmpty(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" must not be empty',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if bool(value) and self.any:
                return MatchResult(True)

            if not bool(value):
                errors.append(f'{pformat(value)} is empty')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueDateEqualMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value date/datetime from "{item.key}" should be equal {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if not isinstance(value, date):
                errors.append(f'{pformat(value)} is not date or datetime object')
                continue

            current_datetime = date_to_timestamp(value)
            expected_datetime = date_to_timestamp(self.expected_value)

            if current_datetime == expected_datetime and self.any:
                return MatchResult(True)

            if current_datetime != expected_datetime:
                errors.append(f'{pformat(value)} != {pformat(self.expected_value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueDateGreaterMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value date/datetime from "{item.key}" should be greater than {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if not isinstance(value, date):
                errors.append(f'{pformat(value)} is not date or datetime object')
                continue

            current_datetime = date_to_timestamp(value)
            expected_datetime = date_to_timestamp(self.expected_value)

            if current_datetime > expected_datetime and self.any:
                return MatchResult(True)

            if current_datetime <= expected_datetime:
                errors.append(
                    f'{pformat(value)} == {pformat(self.expected_value)}'
                    if current_datetime == expected_datetime
                    else f'{pformat(value)} < {pformat(self.expected_value)}',
                )

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueDateLesserMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value date/datetime from "{item.key}" should be lesser than {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if not isinstance(value, date):
                errors.append(f'{pformat(value)} is not date or datetime object')
                continue

            current_datetime = date_to_timestamp(value)
            expected_datetime = date_to_timestamp(self.expected_value)

            if current_datetime < expected_datetime and self.any:
                return MatchResult(True)

            if current_datetime >= expected_datetime:
                errors.append(
                    f'{pformat(value)} == {pformat(self.expected_value)}'
                    if current_datetime == expected_datetime
                    else f'{pformat(value)} > {pformat(self.expected_value)}',
                )

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsInMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should be in {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if self.any and value in self.expected_value:
                return MatchResult(True)
            if value not in self.expected_value:
                errors.append(f'{pformat(value)} is not in {pformat(self.expected_value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsNotInMatcher(BaseValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        errors: list[str] = []
        expectations = [
            f'Value from "{item.key}" should not be in {pformat(self.expected_value)}',
        ]

        current_value = item.value

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            if self.any and value not in self.expected_value:
                return MatchResult(True)
            if value in self.expected_value:
                errors.append(f'{pformat(value)} is in {pformat(self.expected_value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsSubsetMatcher(BaseSetValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        current_value = item.value
        self._throw_if_not_iterable(current_value)

        errors: list[str] = []
        expectations = [
            f'Set of "{item.key}" should only contain values from {pformat(self.expected_value)}',
        ]

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            value_set = set(value)
            expected_set = set(self.expected_value)
            if self.any and value_set.issubset(expected_set):
                return MatchResult(True)
            if not value_set.issubset(expected_set):
                errors.append(f'{pformat(value)} is not a subset of {pformat(self.expected_value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)


class ValueIsDisjointMatcher(BaseSetValueMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        current_value = item.value
        self._throw_if_not_iterable(current_value)

        errors: list[str] = []
        expectations = [
            f'Set of "{item.key}" should not contain any values from {pformat(self.expected_value)}',
        ]

        if not self.in_array:
            current_value = [current_value]

        for value in current_value:
            value_set = set(value)
            expected_set = set(self.expected_value)
            if self.any and value_set.isdisjoint(expected_set):
                return MatchResult(True)
            if not value_set.isdisjoint(expected_set):
                errors.append(f'{pformat(value)} is not disjoint from {pformat(self.expected_value)}')

        if errors:
            return MatchResult(False,
                               errors=errors,
                               expectations=expectations)

        return MatchResult(True)
