# allure-pytest — optional Allure reporting integration

## Domain

`allure-pytest` provides the `allure` package (decorators, `allure.step`, `allure.attach`) and the
pytest plugin behind `--alluredir`. In this repository allure-pytest is **never a runtime
dependency**: pybuggy activates its Allure integration (web-test step reporting with failure
screenshots) only when the package is installed in the target environment. Declared in
`[project.optional-dependencies].test` so the repository's own tests exercise the hooks against
the real package.

The consumer-facing convention (packaged `assets/conventions.md`) already makes allure-pytest a
mandatory test dependency of consumer projects — the guard makes the integration degrade
gracefully when it is absent.

---

## Guarded import pattern

The integration point imports `allure` under a guard and reports nothing when it is missing:

```python
try:
    import allure
except ImportError:
    allure = None  # the Allure integration stays inactive
```

- Feature detection checks the module object (`allure is None`), never `importlib.util.find_spec`
  dances — one import, one truth.
- With the package absent, no Allure hooks are constructed and no `--alluredir` behavior changes;
  web tests run exactly the same, only without step decoration in the report.

---

## StepHooks → Allure mapping

`StepHooks` events map onto Allure steps and groups (see `prettyplay` usage for the hook
contract):

- `on_step_started(step_text, step_type)` — enter `allure.step(f"[{step_type}] {step_text}")`
- `on_step_finished(...)` — exit the step context; an accumulated failure exits it as broken
- `on_step_failed(step_text, step_type, error)` — mark the step failed (AssertionError for
  `"assertion"`, generic Exception otherwise) and attach the screenshot:
  ```python
  try:
      allure.attach(play.get_screenshot(), name="screenshot.png",
                    attachment_type=allure.attachment_type.PNG)
  except (PrettyplayError, PlaywrightError):
      # best-effort: no page (PrettyplayError) or a capture failure (PlaywrightError) —
      # no screenshot, the failure itself is already recorded
      pass
  ```
- `on_group_started(group_prompt)` / `on_group_finished(...)` — enter/exit an
  `allure.step("[group] " + group_prompt)` wrapper

Stack discipline: steps nest inside groups; `contextlib.ExitStack` per level keeps the
enter/exit pairs balanced even when a step fails mid-group.
