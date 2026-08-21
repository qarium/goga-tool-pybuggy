# matchcrest/utils — helper routines

## Domain Overview

matchcrest/utils is an internal utility cell that provides a retry loop, URL helpers, date conversion, and the
`allow_failure` decorator. The cell serves the `matchers` cell (which imports `waiting_for`, `allow_failure`,
`date_to_timestamp`, and `url_is_valid`) and rare direct consumers of `allow_failure` (re-exported
through the matchcrest root). This usage file provides ready-made patterns for consuming the cell facade.

---

## Facade

```python
from goga_tool_pybuggy.matchcrest.utils import (
    waiting_for,
    join,
    url_is_valid,
    url_is_live,
    date_to_timestamp,
    allow_failure,
)
```

---

## Retry loop

`waiting_for` invokes the target function repeatedly until it returns a truthy value or the timeout expires.

```python
from goga_tool_pybuggy.matchcrest.utils import waiting_for


def ready() -> bool:
    return poll_resource()  # True when the resource is ready


try:
    result = waiting_for(ready, timeout=10, delay=0.5)
except TimeoutError:
    ...
```

- `args`/`kwargs` — positional and keyword arguments passed to `f`.
- `hook` — optional transformer applied to the return value before the truthiness check.

---

## URL helpers

```python
from goga_tool_pybuggy.matchcrest.utils import join, url_is_valid

join("https://api.example.com/", "/v1/", "/users/")  # 'https://api.example.com/v1/users/'
url_is_valid("https://example.com")  # True (structural check)
url_is_valid("https://example.com", is_live=True)  # True only on a 2xx response
```

- `url_is_valid` accepts relative URLs and substitutes the first allowed protocol.
- `is_live=True` issues a real GET request via `url_is_live` — a network side effect.

---

## Date conversion

```python
from datetime import date
from goga_tool_pybuggy.matchcrest.utils import date_to_timestamp

ts = date_to_timestamp(date(2026, 7, 14))  # float
```

- `date_to_timestamp` accepts only `date`/`datetime` instances; otherwise it raises `ValueError`.

---

## allow_failure decorator

The `allow_failure` decorator suppresses any exception raised by the decorated function, logs the exception,
and returns `None`. Apply the decorator to fault-tolerant calls whose failure must not interrupt the
surrounding flow.

```python
from goga_tool_pybuggy.matchcrest.utils import allow_failure


@allow_failure
def risky(): ...
```
