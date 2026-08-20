# Testing Convention: pytest Configuration, Logging, Allure

This convention defines mandatory rules for all test code in this project. The convention covers
four areas: pytest configuration, logging via the built-in `logging` library, Allure reporting,
and automatic failure-context capture. The convention does not duplicate pybuggy mechanics
(endpoint fixtures, API calls, asserts) — the pybuggy reference lives in the usages `pybuggy-api`
and `pybuggy-asserts`.

General principles:

1. Tests are independent and reproducible: each test generates scenario data that is unique per
   run (uuid identifiers)
2. Tests are deterministic: test code waits for state changes only through pybuggy polling
   asserts; `time.sleep` and any other timer-based waits are **FORBIDDEN**
3. Test failures are informative: the violated contract is visible directly from the failed
   check — status, field, value

---

## 1. pytest Configuration (pytest.ini)

The `pytest.ini` file **MUST** reside in the project root and contain a valid configuration —
running tests without it is **FORBIDDEN**. pytest reads exactly one configuration source, and a
root `pytest.ini` takes precedence over `[tool.pytest.ini_options]` in `pyproject.toml` — the
project may keep its own settings there without conflicting with the test configuration.

### Mandatory template

```ini
[pytest]
# 1. Core execution options
addopts =
    --tb=short
    -v

# 2. Test discovery rules
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# 3. Custom marker registration (typo protection)
markers =
    positive: positive endpoint scenario
    negative: negative endpoint scenario (4xx/5xx, invalid bodies)
    integration: scenario across multiple endpoints or services
    smoke: critical path, smoke sampling
    regression: full regression run
    flaky: set by the pybuggy plugin when retries > 0; do not apply manually

# 4. Live console logging
log_cli = true
log_cli_level = INFO
log_cli_format = %(asctime)s [%(levelname)s] %(name)s: %(message)s (%(filename)s:%(lineno)d)
log_cli_date_format = %Y-%m-%d %H:%M:%S

# 5. File logging — CI artifact
log_file = logs/pytest.log
log_file_level = DEBUG
log_file_format = %(asctime)s [%(levelname)s] %(name)s: %(message)s (%(filename)s:%(lineno)d)
log_file_date_format = %Y-%m-%d %H:%M:%S

# 6. Strictness and collection boundaries
minversion = 9.0
pythonpath = .
strict_markers = true
strict_config = true
xfail_strict = true
filterwarnings =
    error
# targeted exceptions: a justification comment + the narrowest possible scope
# ignore:<message fragment>:<Category>:<module>
```

### Absolute requirements for pytest.ini

1. **addopts**: holds the execution defaults shared by every run (`--tb=short`, `-v`). Allure
   result collection is a CI concern: the CI job passes
   `--alluredir=allure-results --clean-alluredir` on the pytest command line — local runs stay
   free of result directories
2. **Marker control**: All custom markers **MUST** be explicitly registered in `markers`. Using
   an unregistered marker is a blocking violation (`strict_markers = true` fails the run; the
   runner catches typos before execution). Every test **MUST** carry exactly one scenario marker
   (`positive`, `negative`, `integration`); `smoke`/`regression` **MAY** be applied additionally
   for run selection; only the pybuggy plugin sets `flaky`
3. **Output levels**: `log_cli_level = INFO` — the standard execution console; `log_file_level =
   DEBUG` — full system logs persist to the CI artifact (`logs/pytest.log`)
4. **Strictness**: `strict_config = true` — a typo in an ini option name fails the run instead of
   being silently ignored; `xfail_strict = true` — an xfail test that passes counts as an error,
   ruling out 'permanently green' xfails. Both ini options ship with pytest 9.0 — hence
   `minversion = 9.0`
5. **filterwarnings = error**: Every warning becomes a test error. Targeted `ignore` lines are
   **ALLOWED** under two conditions: a justification comment and the narrowest possible scope
   (warning category + module). Ignoring an entire category is **FORBIDDEN**
6. `pythonpath = .` is mandatory: tests import the generated `api/` tree from the project root

---

## 2. Logging in Python (built-in `logging`)

Test code uses **only the built-in `logging` library**. This single library delivers logs to
three destinations: the console (`log_cli`), the CI file (`log_file`), and the Allure report (the
`log` pseudo-attachment). pytest performs all configuration — levels, format, output — through
`pytest.ini`.

### Base restrictions

1. **Zero `print()` policy**: `print()` in tests and source code is **COMPLETELY FORBIDDEN** —
   code with `print` fails review. Third-party loggers (`loguru`, `structlog`) are **FORBIDDEN**
2. **Logger initialization**: Initialize one isolated logger per module (`.py`), exactly this
   way, at the top of the file:

   ```python
   import logging

   logger = logging.getLogger(__name__)
   ```

3. Calling `logging.basicConfig` or adding handlers in code is **FORBIDDEN** — manual setup
   breaks log capture by pytest and Allure
4. Assert on logs through the built-in `caplog` fixture (`caplog.records`, `caplog.text`); do not
   write stdout parsers. `caplog` sees only the pytest process's logs — remote service logs are
   unavailable to it
5. Keep secrets, credentials, and tokens out of log messages and metadata. Pass context through
   `extra` or message substitution

### Level matrix

| Level    | FORBIDDEN                                               | MUST                                                                        |
|----------|---------------------------------------------------------|-----------------------------------------------------------------------------|
| `DEBUG`  | high-level step descriptions                            | request and response bodies, field values, payload details                  |
| `INFO`   | bulk data, loop iterations                              | test start and end, key scenario actions, HTTP calls                        |
| `WARNING`| routine operational exceptions                          | flaky retries, safe fallbacks, deprecation notices                          |
| `ERROR`  | test assertion failures — a failure surfaces through the failed check | caught exceptions that do not block execution; state dump before the failure |

Do not use `CRITICAL` in test code.

---

## 3. Data Preparation Fixtures

Place reusable fixtures (scenario data preparation, utilities) in the `conftest.py` of the same
package as the tests; pytest picks them up automatically through the directory hierarchy:

```text
tests/
    conftest.py                  # fixtures shared by all tests (+ automatic capture — section 5)
    <spec>/
        conftest.py              # fixtures shared by the domain/specification
        <endpoint_id>/
            conftest.py          # fixtures of a specific endpoint
            test_<name>.py       # markup, steps, and checks only
```

RULES:

1. A data preparation fixture **MUST** live in the `conftest.py` of the package closest to the
   tests: one endpoint — `tests/<spec>/<endpoint_id>/conftest.py`; several endpoints of a domain —
   `tests/<spec>/conftest.py`; all tests — `tests/conftest.py`. Importing fixtures or declaring
   them in test modules is **FORBIDDEN**
2. Give every fixture a docstring and a typed return
3. Keep test modules to markup, steps, and checks only — data generation and preparation logging
   stay in fixtures
4. Section 2 rules apply to fixture code in full (isolated module logger, level discipline,
   prohibitions)
5. Fixture-generated data is unique per run (uuid) — see General principles

---

## 4. Allure Reporting Standards

Build reporting on Allure; the pytest integration is the `allure-pytest` plugin — a mandatory
test dependency: test code imports `allure` decorators, and the CI run passes `--alluredir`
(without the plugin both fail).

### Metadata markup

Every test class and every standalone test function **MUST** carry Allure categorization
decorators. A test without metadata is a direct policy violation.

1. **Architectural hierarchy**: Maintain a strict three-level feature tree —
   `@allure.epic("System/Domain")` → `@allure.feature("Service/Module")` →
   `@allure.story("User action/Story")`
2. **Test titles**: Technical function names are unreadable for business stakeholders — every
   test function **MUST** have a human-readable `@allure.title("Action description")`
3. **Priorities**: Set `@allure.severity(...)` on critical paths (authorization, payments,
   domain core) — level `CRITICAL` or `BLOCKER`; other tests **MAY** use `NORMAL`/`MINOR`/
   `TRIVIAL`
4. **docstring as description**: Without `@allure.description`, a test function's docstring
   automatically becomes the test description in the report — keep it meaningful (preconditions,
   steps, expected result). allure-pytest does **NOT** parse structured keys inside a docstring
   (`title:`, `severity:`, etc.): set title, severity, and the epic/feature/story hierarchy only
   through decorators or `allure.dynamic.*` from the test body

### Step architecture

1. **Test functions**: Wrap test phases in the `with allure.step("...")` context manager —
   nested blocks form substeps
2. **Helpers/utilities**: Decorate methods with `@allure.step("...")`, parameterizing the step
   name with placeholders to inject runtime data:

```python
@allure.step("Create an order for customer '{customer}' with amount {amount}")
def create_order(customer: str, amount: int):
    ...
```

### Miscellaneous

1. Results are written to `allure-results/` in the project root only on CI runs (the CI command
   passes `--alluredir`); the `allure-results/`, `allure-report/`, and `logs/` directories
   **MUST** be excluded from VCS (`.gitignore`)
2. Allure attaches the `stdout`, `stderr`, and `log` pseudo-files (built-in `logging` output) to
   every test automatically — no separate `allure.attach` calls for logs
3. A selective test-plan run **MAY** be performed through the `ALLURE_TESTPLAN_PATH` environment
   variable (the `testplan.json` file); the `environment.properties` file in `allure-results/`
   **MAY** be added to describe the environment

---

## 5. Automatic Failure-Context Capture

To avoid attaching failure data manually, `tests/conftest.py` **MUST** contain two components:

```python
import logging

import allure
import pytest

logger = logging.getLogger(__name__)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Isolates test lifecycle phases: each phase's report is available on the item."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture(autouse=True)
def attach_failure_context(request):
    """Attaches failure context to Allure immediately after the call phase."""
    yield
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        rep = request.node.rep_call
        allure.attach(
            f"{rep.when}: {rep.longreprtext}",
            name="FAILURE_SUMMARY",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info("failure context attached to allure report")

        # Pattern for custom client wrappers: attach the last response body.
        # The built-in pybuggy Api does not store response history — the branch activates
        # when the project introduces a wrapper with a last_response_body attribute.
        if "api" in request.fixturenames:
            client = request.getfixturevalue("api")
            if hasattr(client, "last_response_body"):
                allure.attach(
                    str(client.last_response_body),
                    name="FAILED_RESPONSE_BODY",
                    attachment_type=allure.attachment_type.TEXT,
                )
```

RULES:

1. The `pytest_runtest_makereport` hook **MUST** store phase reports (`rep_setup`/`rep_call`/
   `rep_teardown`) on the item — the foundation of any automatic capture
2. The autouse fixture **MUST** run after the call phase and attach failure context to Allure —
   without manual actions in the test body
3. pybuggy projects have no UI branch (WebDriver screenshots) — the stack under test is API-only;
   extend the fixture with branches for your own context-owner fixtures following the pattern
   above

---

## 6. Reference Test Implementation

The reference implementation satisfies every section: a data preparation fixture in the
`conftest.py` of the test's package with an isolated logger (picked up by pytest automatically,
no import); mandatory Allure markup (epic → feature → story, title, severity); a scenario marker
+ smoke; `allure.step` steps. Call and assertion mechanics come from pybuggy (reference: the
usages `pybuggy-api` and `pybuggy-asserts`).

The data preparation fixture — in the test package's conftest:

```python
# tests/shop/api_v1_orders_post/conftest.py
import logging
import uuid

import pytest

from api.shop.api_v1_orders_post.api import Request

# Requirement: isolated module logger
logger = logging.getLogger(__name__)


@pytest.fixture
def order_payload() -> Request:
    """Prepares unique scenario data: a customer and an order body."""
    customer = f"cust-{uuid.uuid4().hex[:8]}"
    payload = Request(customer=customer, amount=100)
    logger.info("order payload prepared", extra={"customer": customer})
    logger.debug(f"payload: {payload.model_dump_json(indent=2)}")
    return payload
```

The test itself — markup, steps, and checks only:

```python
# tests/shop/api_v1_orders_post/test_create_order.py
import allure
import pytest

from api.shop.api_v1_orders_post.api import Request


@allure.epic("Shop")
@allure.feature("Orders")
@allure.story("Order creation")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-1: order is created with a minimal body")
@pytest.mark.positive
@pytest.mark.smoke
def test_create_order(order_payload: Request, post_api_v1_orders, get_api_v1_orders):
    with allure.step("create an order via POST /api/v1/orders"):
        allure.attach(order_payload.model_dump_json(indent=2), name="request",
                      attachment_type=allure.attachment_type.JSON)
        with post_api_v1_orders(json=order_payload) as response:
            response.expected.has_status_code(201)
            response.expected("id").not_empty()

    with allure.step("check the order in the list via GET /api/v1/orders"):
        with get_api_v1_orders(params={"customer": order_payload.customer}) as response:
            response.expected.has_status_code(200)
            response.expected("$[*]").has_length(1)
```
