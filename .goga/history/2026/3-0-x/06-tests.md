# Test Report

## Changes Requiring Coverage

| Change | Type | Notes |
|---|---|---|
| `pyproject.toml` test-extra pin `goga>=2.0.1,<2.1` → `goga>=2.1,<2.2` | regression (environment provisioning) | Not a code behavior — verified at the environment level: a fresh venv resolved from the updated extras auto-selects a 2.1.x goga, and the unmodified full suite passes inside it |
| Synced usages (`.goga/usages/github/goga/**`) | documentation | No executable behavior; the platform-facing behaviors they describe are covered by the existing suite, which imports the real goga platform (`goga.pipeline.workflow`, `goga.pipeline.hooks.identity`, `goga.config` facade) |

No new pytest files: the plan's test strategy (approved by the user) explicitly defines
verification steps instead of new tests — the pin governs environment provisioning, which
pytest cannot observe from inside the environment it is provisioned into.

## Tests Added

None (per the approved plan). Verification runs executed in their place:

| Verification | Command | Result |
|---|---|---|
| Pin resolves to the 2.1 line | fresh venv + `pip install -e ".[test]"` | goga 2.1.4 auto-selected |
| Full suite in the freshly resolved env | `pytest tests/` | 2152 passed, 21 skipped, 20 warnings |
| Compatibility matrix (both sides of the pin) | `pytest tests/` with goga 2.0.5 / 2.1.0 / 2.1.2 / 2.1.4 | 2152 passed, 21 skipped — identical on all four |
| Affected-area focus | `pytest tests/autonomous/ tests/config/ tests/test_reg_hooks.py tests/test_autonomy_integration.py` | 120 passed |
| Lint | `ruff check goga_tool_pybuggy/` | All checks passed |
| Facade | `python -c "import goga_tool_pybuggy"` | OK |
| Manifests | `goga lint` | 27 cells, 0 errors |

## Test Results

| Test set | Status | Details |
|---|---|---|
| Existing full suite (unmodified) | PASS | 2152 passed, 21 environment-gated skips, 20 pre-existing warnings — on goga 2.0.5, 2.1.0, 2.1.2, 2.1.4, and the fresh pin-resolved env (2.1.4) |
| Platform-facing area (autonomous, config, reg_hooks, autonomy integration) | PASS | 120 passed; these tests import the real goga platform classes and facade, so they exercise the updated platform surface directly |

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| Test env resolves goga from the 2.1 line | YES (environment-level) | Fresh-venv resolution run proved pip selects 2.1.4; not assertable from inside pytest |
| Autonomy contribution composes under 2.1 (template rendering, vocabulary) | YES | `tests/autonomous/test_workflow.py` builds the real `WorkflowDocument` via `build_autonomous_workflow` against the installed platform |
| Config facade reads under 2.1 (`!ENV`-aware loader) | YES | `tests/config/test_storage.py` drives `load_config`/`resolve_autonomy` through the real facade |
| Hook registration addresses valid under 2.1 | YES | `tests/test_reg_hooks.py` + `tests/test_autonomy_integration.py` |
| Statuses / onboarding / init flows under 2.1 | YES | Full suite (unchanged practices, unchanged code) |

## Missing Coverage Analysis

Nothing material is untested. The only non-pytest observable is the pip resolution of the
`test` extra itself, which was verified operationally (fresh venv → goga 2.1.4). The ~21 new
unbound practice files describe optional platform capabilities pybuggy does not implement —
no pybuggy behavior exists to cover.
