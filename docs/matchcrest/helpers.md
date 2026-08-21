# Helpers — `matchcrest.utils`

Utility routines of the matchcrest library: a retry loop, URL helpers, date conversion,
and the `allow_failure` decorator.

```python
from goga_tool_pybuggy.matchcrest.utils import (
    waiting_for, join, url_is_valid, url_is_live, date_to_timestamp, allow_failure,
)
```

## Retry loop — `waiting_for`

Invokes the target function repeatedly until it returns a truthy value or the timeout
expires:

```python
from goga_tool_pybuggy.matchcrest.utils import waiting_for


def ready() -> bool:
    return poll_resource()  # True when the resource is ready


try:
    result = waiting_for(ready, timeout=10, delay=0.5)
except TimeoutError:
    ...
```

| Parameter | Meaning |
|-----------|---------|
| `args` / `kwargs` | Positional and keyword arguments forwarded to `f` (empty when `None`) |
| `timeout` | Total seconds to keep retrying (default `5`) |
| `delay` | Pause between attempts (default `0.5`) |
| `hook` | Optional transformer applied to the return value before the truthiness check |

## URL helpers

```python
from goga_tool_pybuggy.matchcrest.utils import join, url_is_valid

join("https://api.example.com/", "/v1/", "/users/")  # 'https://api.example.com/v1/users/'
url_is_valid("https://example.com")                   # True (structural check)
url_is_valid("https://example.com", is_live=True)     # True only on a 2xx response
```

- `url_is_valid` accepts relative URLs and substitutes the first allowed protocol.
- `is_live=True` issues a real GET request via `url_is_live` — a network side effect.

## Date conversion — `date_to_timestamp`

```python
from datetime import date
from goga_tool_pybuggy.matchcrest.utils import date_to_timestamp

ts = date_to_timestamp(date(2026, 7, 14))  # float
```

Accepts only `date`/`datetime` instances; anything else raises `ValueError`. This is the
routine behind the date matchers' timestamp comparison (see
[Matcher Catalog](matchers.md)).

## `allow_failure` decorator

Suppresses any exception raised by the decorated function, logs it, and returns `None`.
Apply to fault-tolerant calls whose failure must not interrupt the surrounding flow:

```python
from goga_tool_pybuggy.matchcrest.utils import allow_failure


@allow_failure
def risky(): ...
```
