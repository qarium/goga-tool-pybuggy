# Migrate pybuggy to goga 2.0 via the canonical onboarding model

pybuggy moves fully to goga 2.0 and 1.x support is dropped. goga stays an **environment precondition**, not a pyproject dependency (`goga install pybuggy` installs the tool into an already-provisioned goga environment); only the CI `test` extra pins `goga>=2.0.1,<2.1`. The `init` command is rebuilt on the goga 2.0 onboarding model — tool participation via `declare_session`/`amend_config`, config writes through `ToolContribution`, the renamed `build.review.skip` key — keeping the `goga tool pybuggy init` UX and gaining native `goga init -t pybuggy`; pybuggy-only bootstrap (conftest.py, Dockerfile install line, usages→cooks copy) remains in pybuggy. All other integration surfaces were verified compatible with 2.0 unchanged: the install hook, `register_hooks`/statuses subscription, `goga tool` dispatch, skills/pipelines layout (`pybuggy:api.automate`), the pipeline DSL, `usages/cooks`, and the 16-command CLI surface referenced throughout the skills.

## Considered Options

- **init architecture** — canonical 2.0 participation (chosen) vs minimal import port vs hybrid: goga 2.0 declares the onboarding generator the single write path for `.goga/tools/<tool>/*`; hand-rolled config edits would drift from release to release.
- **tool config loading** — keep self-load via `config/storage.py` (chosen) vs accept the goga `config` injection: one code path, same file, works for direct `pybuggy` calls too.
- **hooks scope** — keep `statuses/register_statuses` only (chosen) vs adopting new 2.0 hook actions: a migration must not grow features.
- **consumer migration guide** — `MIGRATION.md` at repo root (chosen, GitHub-visible) vs a published mkdocs page.
- **host version guard** — none (chosen) vs a friendly check on old goga hosts: `goga install` and goga's own version-check own the environment; version-sniffing code in the tool would drift.

## Consequences

- `goga.onboarding` imports move to the 2.0 facade (`GogaConfigAnswers`/`InitAnswers`/`FileGenerator` are gone; replaced by `SessionAnswers`/`SessionPlan` and the participation entities); `goga.scaffold.Scaffold` carries over, pinned by the existing parity test.
- `_INSTALL_LINE` ("RUN goga install pybuggy -v 1.0.x") becomes dynamic, derived from the package's own version line.
- Tests: parity stubs updated to 2.0 signatures; an automated smoke test runs `init` + `endpoint generate` in a tmp dir; the full `goga pipeline pybuggy:api.automate` e2e is accepted after one manual run.
- Definition of done: the suite is green on goga 2.0.1 and the consumer quickstart works end-to-end (`goga install pybuggy` → `goga tool pybuggy init` → `goga pipeline pybuggy:api.automate`).
- pybuggy release tagging stays with the maintainer and is out of scope for the migration.
