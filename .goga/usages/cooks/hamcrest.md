# PyHamcrest

A library of declarative matchers (Hamcrest for Python). matchcrest is built on top of it.

## The assertion point — assert_that

```python
from hamcrest import assert_that

assert_that(actual, matcher)          # base form
assert_that(actual, matcher, reason)  # with a message prefix
```

`assert_that` applies `matcher` to `actual`; on a mismatch it raises an `AssertionError` carrying a description of the expectation and the actual value (produced by the matcher's `describe_to` / `describe_mismatch`).

## The base matcher — BaseMatcher

`hamcrest.core.base_matcher.BaseMatcher` is the base class for custom matchers.

- `_matches(self, item) -> bool` — the core of the check; the `assert_that` engine invokes it.
- `describe_to(self, description)` — writes the expectation into `Description`.
- `describe_mismatch(self, item, mismatch_description)` — writes the actual mismatch.

`hamcrest.core.description.Description` is the object that accumulates description text (`append_text`, etc.).

## Usage in matchcrest

`matchcrest.matchers.base.BaseMatcher` inherits from `hamcrest.core.base_matcher.BaseMatcher` and overrides `_matches` (a retry/timeout loop), delegating the check itself to the `_assert` hook. The matchcrest root facade re-exports `assert_that` from `hamcrest` as the entry point for checks.
