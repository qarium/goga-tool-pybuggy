import typing as t
from enum import Enum
from pprint import pformat

import jsonschema
import requests

from .base import (
    BaseContext,
    BaseMatcher,
    MatchResult,
)


class ResponseCodeMatcher(BaseMatcher):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if isinstance(self.expected_value, Enum):
            self.expected_value = self.expected_value.value
        if isinstance(self.expected_value, str):
            self.expected_value = requests.codes[self.expected_value]

        if not isinstance(self.expected_value, int):
            raise ValueError(
                'Code is expected to be either integer or string "requests.codes.{name}" object',
            )

    def _assert(self, item: BaseContext) -> MatchResult:
        actual_code = item.value

        expectations = [
            f'Response code from "{item.key}" should be equal to {pformat(self.expected_value)}',
        ]

        return MatchResult(
            self.expected_value == actual_code,
            expectations=expectations,
            errors=[f"Response code was {pformat(actual_code)}"],
        )


class ResponseHeadersByValueMatcher(BaseMatcher):
    def __init__(self, *args, **kwargs):
        self.contains = kwargs.pop("contains", False)
        self.startswith = kwargs.pop("startswith", False)
        self.endswith = kwargs.pop("endswith", False)
        self.key = kwargs.pop("key", None)

        super().__init__(*args, **kwargs)

    def _assert(self, item: BaseContext) -> MatchResult:
        headers = item.value or {}
        expected_header_value = self.expected_value.lower()
        errors: list[str] = []
        expectations = [
            f"Response header value should matching {pformat(expected_header_value)}",
        ]

        value = next((v for k, v in headers.items() if k.lower() == self.key), None)
        if value is None:
            return MatchResult(
                False, expectations=expectations, errors=[f'Response header by key "{self.key}" not found']
            )
        value = value.lower()
        if self.contains and expected_header_value not in value:
            errors.append(f'Response header value {value} does not contain "{expected_header_value}"')

        if self.startswith and not value.startswith(expected_header_value):
            errors.append(f'Response header value {value} does not startswith "{expected_header_value}"')

        if self.endswith and not value.endswith(expected_header_value):
            errors.append(f'Response header value {value} does not endswith "{expected_header_value}"')

        if errors:
            return MatchResult(False, expectations=expectations, errors=errors)

        if self.contains or self.startswith or self.endswith:
            return MatchResult(True)

        if value != expected_header_value:
            return MatchResult(
                False,
                expectations=expectations,
                errors=[f'Response header value {value} does not equal "{expected_header_value}"'],
            )

        return MatchResult(True)


class ResponseHeadersByKeyMatcher(BaseMatcher):
    def __init__(self, *args, **kwargs):
        self.count = kwargs.pop("count", None)
        self.contains = kwargs.pop("contains", False)
        self.startswith = kwargs.pop("startswith", False)
        self.endswith = kwargs.pop("endswith", False)

        super().__init__(*args, **kwargs)

    def _assert(self, item: BaseContext) -> MatchResult:
        headers = item.value or {}
        expected_header_key = self.expected_value.lower()

        expectations = [
            f'Response headers from "{item.key}" should matching header by key "{expected_header_key}"',
        ]

        actual_headers = headers
        if self.contains:
            actual_headers = {k: v for k, v in actual_headers.items() if expected_header_key in k.lower()}

        if self.startswith:
            actual_headers = {k: v for k, v in actual_headers.items() if k.lower().startswith(expected_header_key)}

        if self.endswith:
            actual_headers = {k: v for k, v in actual_headers.items() if k.lower().endswith(expected_header_key)}

        if not self.contains and not self.startswith and not self.endswith:
            actual_headers = next(({k: v} for k, v in headers.items() if k.lower() == expected_header_key), {})

        if not actual_headers:
            return MatchResult(
                False,
                expectations=expectations,
                errors=[f'Response headers does not exist by key "{expected_header_key}"'],
            )

        if self.count and (len(actual_headers.items()) != self.count):
            return MatchResult(
                False,
                expectations=expectations,
                errors=[f"Response headers count {len(actual_headers)} != {self.count}"],
            )

        return MatchResult(True)


class ResponseBodyMatcher(BaseMatcher):
    MAX_BODY_LEN: t.Final[int] = 75

    def _assert(self, item: BaseContext) -> MatchResult:
        actual_body = item.value

        expectations = [
            f'Request body from "{item.key}" is equal to {pformat(actual_body[: self.MAX_BODY_LEN])}',
        ]

        if actual_body == self.expected_value:
            return MatchResult(True)

        return MatchResult(
            False,
            expectations=expectations,
            errors=[
                f"{pformat(actual_body[: self.MAX_BODY_LEN])} != {pformat(self.expected_value[: self.MAX_BODY_LEN])}"
            ],
        )


class JsonschemaMatcher(BaseMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        expectations = [
            f'Json data from "{item.key}" should correspond to jsonschema',
        ]

        try:
            jsonschema.validate(item.value, self.expected_value)
        except jsonschema.ValidationError as e:
            return MatchResult(
                False,
                expectations=expectations,
                errors=[f'Json data from "{e.json_path}" is not correspond to jsonschema', e.message],
            )

        return MatchResult(True)


class JsonHasDataByKeyMatcher(BaseMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        current_value = item.value or {}

        expectations = [
            f'Response json from "{item.key}" should has data by key {pformat(self.expected_value)}',
        ]

        if not isinstance(current_value, dict):
            current_value = {}

        if current_value.get(self.expected_value) is None:
            return MatchResult(
                False,
                expectations=expectations,
                errors=[f"Response json has not data by key {pformat(self.expected_value)}"],
            )

        return MatchResult(True)


class JsonHasNotDataByKeyMatcher(BaseMatcher):
    def _assert(self, item: BaseContext) -> MatchResult:
        current_value = item.value or {}

        expectations = [
            f'Response json from "{item.key}" should has not data by key {pformat(self.expected_value)}',
        ]

        if not isinstance(current_value, dict):
            current_value = {}

        if current_value.get(self.expected_value) is not None:
            return MatchResult(
                False,
                expectations=expectations,
                errors=[
                    f"Response json has data by key {pformat(self.expected_value)}",
                ],
            )

        return MatchResult(True)


class JsonContainsKeyMatcher(BaseMatcher):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not isinstance(self.expected_value, (list, tuple)):
            self.expected_value = [self.expected_value]

    def _assert(self, item: BaseContext) -> MatchResult:
        current_value = item.value or {}

        expectations = [
            f'Response json from "{item.key}" should contains key {pformat(self.expected_value)}',
        ]

        if not isinstance(current_value, dict):
            current_value = {}

        for key in self.expected_value:
            if key not in current_value:
                return MatchResult(
                    False,
                    expectations=expectations,
                    errors=[
                        f"Response json not contains {pformat(key)}",
                    ],
                )

            current_value = current_value[key]

        return MatchResult(True)
