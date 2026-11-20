# The `web.automate` lifecycle

The `PybuggyWebAutomate` pipeline automates browser UI-test creation end to end: from the
user interview and live page exploration to materialized, generated, and accepted tests.
Each stage is a goga skill; the stages exchange only topic artifacts (a clean context per
stage). The durable traceability chain is `Routine` → `test_*.py`: CODEMANIFESTs carry no
REQ identifiers — requirement coverage is checked by the testcases stage's session registry
(a mechanical reconciliation against §3 at assembly). Page identifiers `PAGE-<N>` link
requirements and cells.

Tests are written as **step sentences** through the `web` fixture (see
[Web / Overview](../web/index.md)): the first run turns every sentence into Playwright code
with an LLM and caches it next to the test; the cache is committed to the repository, and
every later run replays it with no LLM.

```bash
goga pipeline pybuggy:web.automate
```

## Stages

| #  | Stage                  | Purpose                                                                                                       | Artifact                       |
|----|------------------------|---------------------------------------------------------------------------------------------------------------|--------------------------------|
| 1  | `create-requirements`  | Interview (what to test, which pages), page exploration via playwright-cli, discrepancy reconciliation, requirements assembly | `requirements.md`             |
| 2  | `requirements-review`  | Requirements review: quality and consistency of requirements, realness of runtime facts and the usage registry, targeted live re-verification | —                              |
| 3  | `create-testcases`     | Mega-stage: routines (a test case = a Routine, each approved by the user) → cell distribution → CODEMANIFEST assembly and materialization | `tests/web/<cell>/CODEMANIFEST` |
| 4  | `testcases-review`     | Review of the materialized CODEMANIFESTs: semantic REQ coverage, step-sentence quality, DSL structure — fixes applied with user approval | —                              |
| 5  | `code-design`          | Design document of web-test materialization (a `goga-design` wrapper)                                          | `design.md`                    |
| 6  | `design-review`        | Design review extended with web-specific checks (step-sentence mechanics, generating first run, committed cache) | —                              |
| 7  | `coding-plan`          | ralphex plan: every task carries an executable checkbox that runs the test **without** `--strict-mode`          | `plan.md`                      |
| 8  | `plan-review`          | Plan review: guarantees the generating run stays non-strict, the browser connection line, the cache-preservation policy | —                              |
| 9  | `commit-changes`       | Commit the tests and step caches                                                                               | git commit                     |
| 10 | `accept-result`        | Acceptance: chain consistency, strict run, failure triage, bugs                                                | `bugs.md` + [ACCEPT_REPORT]    |

The full flow: **requirements → testcases (routines → cells → materialization) → design →
plan → ralphex build → accept**.

> **Building the tests:** the design stages produce documents only. After `plan-review`
> approves the plan, the test code is built with `goga build <path-to-plan.md>` —
> [goga](https://github.com/qarium/goga) executes the ralphex plan: it writes each
> `test_*.py` from the plan's Tasks and runs the task checkboxes — the **first, generating
> run** (the LLM writes the Playwright steps, the cache lands next to the test). There is
> no separate build stage in the pipeline: the command runs by hand — or is added
> automatically on [autonomous runs](#autonomous-runs).

## The testcases mega-stage

Five steps of one session, every intermediate result staying in the dialogue context:

1. **Intake** — validate `requirements.md` (§2 pages, §3 `REQ-<N>`), load it into the
   context verbatim along with the whole goga context: the `goga-cell` DSL, the Python
   rules, the web cookbook, the base Header block (via `goga-codemanifest-base`), the web
   runtime reference.
2. **Tools** — the tool needs of the tests (data setup via API, backend mocks, a
   credentials usage file); agree with the user (WAIT), create
   `.goga/usages/cooks/<key>.md`.
3. **Routines design** — the routines in one pass, without an intermediate case layer:
   name, Purpose, Precondition, Data (parameterization by the linearity criterion), Steps
   sentences (the future `web.step`/`web.expect`), Use. Every routine is approved by the
   user (WAIT).
4. **Cell map** — distribute the ready routines across cells (a variant is proposed;
   WAIT).
5. **Assembly** — assemble the complete CODEMANIFEST of every cell (Header: base block +
   cell-specific usages; Body: routines; Footer), validate against the DSL before writing,
   write into `tests/web/<cell>/` (existing cells merge, never overwrite), and run the
   gates: `goga lint`, `goga schema tests/`, REQ coverage.

**REQ policy:** `REQ-<N>` identifiers live in `requirements.md` §3 only; the CODEMANIFESTs
carry none. Coverage is the session registry (the Coverage section of the routines-design
report): at assembly it is mechanically checked that `covered ∪ excluded = the §3 registry`
(no gaps, duplicates, or intersections) and that every routine of the registry is present
by name in the materialized manifests. The requirement → routine link is never persisted
anywhere.

## Artifacts

Every topic artifact is addressed with `goga history path -f <artifact>` and lives under
`.goga/history/<year>/<topic>/`:

- **requirements.md** — the requirements: environment and the Browser endpoint (§1), the
  page dossiers (§2 `PAGE-<N>`), functional requirements (§3 `REQ-<N>`), authorization and
  environment (§4), the usage registry (§8), existing coverage (§9).
- **design.md** — the design of test materialization from the web cells' CODEMANIFESTs.
- **plan.md** — the ralphex plan with executable run checkboxes in every generating task.
- **bugs.md** — service bug records found at acceptance.
- **tests/web/<cell>/** — the materialized cells: `CODEMANIFEST`, `test_<name>.py`, and the
  step cache `test_<name>/` (committed).

## Status model

Every artifact of the chain (except `bugs.md` and the materialization in the target
project — those are history records, not statuses) marks a status on the topic's goga
status scale: the package registers one `pybuggy.*` status per artifact, and the web topic
reports the reached stage under its own name:

| Artifact            | Status                                       |
|---------------------|----------------------------------------------|
| `requirements.md`   | `pybuggy.web.automate.requirements-created`  |
| `design.md`         | `pybuggy.web.automate.designed`              |
| `plan.md`           | `pybuggy.web.automate.planned`               |
| `completed/plan.md` | `pybuggy.web.automate.done`                  |

Every status is anchored above its built-in twin (`web.automate.done` above the built-in
`done`). The web line carries no statuses for testcases/arch: the web pipeline writes no
such artifacts — its cases live as Routines in the target project. The web line's artifact
names match the `pybuggy.api.automate.*` line, and the two apply independently — one topic
can carry several statuses at once. Read the scale with `goga history status`; filter
topics by status name — `goga history status -s <name>`.

## Page exploration

The create-requirements stage explores the live site's real pages with `playwright-cli`
(the npm package `@playwright/cli`) in the named session `-s=pybuggy-explore`. The browser
is never launched locally: the intake asks for the **browser endpoint for writing tests** —
"from the config" (`browser.endpoint` of `web.yml`) or an address from the user
(`ws(s)://…` a Playwright server / `http(s)://…` CDP; the browser's address, not the tested
site's) — and the exploration connects to it via `attach`. The entered address applies to
the runs too: run commands carry `--browser-endpoint <address>`. The pipeline's constraint
supplies a ready bootstrap command: a loopback address (`127.0.0.1`/`localhost` — the
browser on the Docker host) is rewritten to `host.docker.internal` and resolved to the
host's IP (`getent`, Linux); a remote address is attached as-is. The session's artifacts
(screenshots/traces) land in `<topic history>/playwright/`
(`PLAYWRIGHT_MCP_OUTPUT_DIR`).

Every page gets a dossier: the final URL after redirects, its purpose, key elements with
stable locators (`generate-locator`), forms with validations, the navigation map,
observable states, console and network errors (the page's API endpoints included). Target
pages are all explored; the walk over adjacent pages is bounded by a budget (crawl depth,
interactions per page, an adjacent-URL allowance); an exhausted budget is not an error:
the unvisited remainder is recorded in the report.

Entry to closed pages happens in the session with test credentials; the authorization
state is saved (`state-save`). **Secrets are never written** into reports or artifacts —
only the login mechanism and the credentials source (env names).

Every user-request ↔ observation discrepancy becomes a separate question to the user
before the requirements are fixed.

## Step generation

The pipeline's core mechanic. Step sentences from Routine annotations materialize into
`test_*.py` as `web.step(...)` / `web.expect(...)`:

- the **first** run of a test — at the ralphex-build stage, through the plan's task
  checkboxes — generates every sentence's Playwright code via an LLM (the provider and
  model come from `.goga/tools/pybuggy/web.yml`) and writes the step cache into
  `tests/web/<cell>/test_<name>/`; the cache is **committed** to the repository together
  with the test (the commit-changes stage);
- the first run must go **without** `--strict-mode` — the strict mode makes no LLM calls,
  and a new step fails there with a cache miss;
- repeated runs and CI go with `--strict-mode`: replay from the cache, zero LLM calls;
- acceptance (accept-result) runs the suite in strict mode; a cache miss is healed by one
  non-strict run that regenerates the missing steps;
- the cache is never edited by hand — to regenerate a step, delete its cache file, and the
  next non-strict run recreates it.

Steps carry the **full URLs** of the recorded environment (no base_url templating): an
environment switch means new step sentences. **Secrets are forbidden in sentences** — the
whole sentence reaches the provider prompt and the repository; login is described
behaviorally ("Log in as the test user `<role>`"), values come from env/usage files.

## Environment

The pipeline's preconditions:

- the web kind initialized: `.goga/tools/pybuggy/web.yml` exists — `goga tool pybuggy
  init` with kind `web` or `both` (see [Web / Configuration](../web/configuration.md));
- an external browser: the endpoint comes from the config (`browser.endpoint`) or the
  intake; a host browser runs with remote debugging (Chrome, for example:
  `--remote-debugging-port=9222 --user-data-dir=<dir>`). Browser binaries
  (`playwright install --with-deps <browser>`) are needed only for local runtime launches
  outside an endpoint — the pipeline never uses them;
- `playwright-cli` for page exploration: installed automatically by the pybuggy
  post-install hook at `goga install` (node/npm on PATH required in the image); when
  unavailable, the pipeline stops;
- an LLM provider key in env/`.env` — required by the generating first run
  (regeneration).

## Autonomous runs

The pipeline can run unattended starting from the review of the materialized cells.
Autonomy is enabled per pipeline in the `pipelines` section of the **web config** — by
hand or through the autonomy confirmation of the [`pybuggy init`](../cli/init.md) command
(the session's web branch):

```yaml
# .goga/tools/pybuggy/web.yml
pipelines:
  web.automate:
    autonomous: true
```

The web line's axis lives in `web.yml` — the web kind's own document (the plugin ignores
the `pipelines` section; the autonomy resolver reads it); the api lines' axes stay in
`api.yml`.

With the entry enabled, pybuggy contributes a fixed workflow document (the
[Workflows](workflows.md) mechanism) to every `web.automate` run:

- The auto-approval window of six stages `testcases-review` → `commit-changes` (stages
  4–9 of the table above): every window stage is approved automatically — the
  communication stages no longer wait for review.
- The `build` stage added after `commit-changes`: the same `goga build` step as in the
  "Building the tests" note above, over the topic's `plan.md` with an eight-hour timeout
  and a scratch-tree (`.ralphex`) cleanup afterwards — the tests are built and committed
  with no manual build.

Everything outside the window stays with the human: the requirement- and routine-forming
stages (`create-requirements` … `create-testcases`) run interactively, and `accept-result`
is never part of the contribution — the trigger stays manual; acceptance (the strict run
and the failure triage) remains an interactive step.

The web line's specifics for the autonomous `build` is that **first, generating run**: the
LLM provider key must be in the run's env (without it step generation is impossible), and
`--strict-mode` must appear nowhere in the plan (the `coding-plan` wrapper's guarantee).

The contribution is a silent no-op for every pipeline outside the three autonomous lines
(automate, patch, web-automate — the window's shape comes from the per-pipeline record)
and for every disabled state: a missing file, a missing `pipelines` section, a missing
`web.automate` entry, and `autonomous: false` are all an ordinary interactive run.
Autonomy is never silently disabled on a broken structure: a structural violation of the
section (a non-mapping `pipelines` root or value, an entry other than exactly
`autonomous: <boolean>`) stops the command with a clean error naming pybuggy, and the
whole contribution is discarded.

A project's authored workflow wins per slot over the contribution — the file
`.goga/workflows/pybuggy:web.automate.yml` can re-enable interaction for any window stage
or displace the `build` entry.

## Relation to the rest

- [Web / Overview](../web/index.md) — the `web` fixture, step sentences, the cache, run
  modes.
- [Web / Configuration](../web/configuration.md) — the `web.yml` keys (browser, provider,
  models).
- [Workflows](workflows.md) — overriding/extending the pipeline with the
  `.goga/workflows/pybuggy:web.automate.yml` file.
- The `api.*` line ([api.automate](api-automate.md), [api.fix](api-fix.md),
  [api.patch](api-patch.md)) — the same context-handling principles for API tests; the
  web line mirrors them.
