# Getting Started

Three steps take a project from zero to an automated API-test lifecycle:

```bash
goga install pybuggy                 # 1. install
goga tool pybuggy init               # 2. initialize
goga pipeline pybuggy:api.automate   # 3. run the pipeline
```

## 1. Install: `goga install pybuggy`

Installs the pybuggy package into the **goga**(<https://github.com/qarium/goga>)
environment of the target project. The package carries the container/DB/Kafka/redis stack as
main dependencies (`testcontainers`, `psycopg`, `kafka-python`, `redis`, `requests`); running
tests with a sandbox document (`.goga/tools/pybuggy/sandbox.yml`) present additionally
requires a docker-compatible container runtime in the test environment (see
[Sandbox](sandbox/index.md)).

## 2. Initialize: `goga tool pybuggy init`

Run in the target project root:

```bash
goga tool pybuggy init
```

The command (see [CLI — init](cli/init.md)) runs two stages — the engine-owned
onboarding session with pybuggy invited, then the pybuggy bootstrap.

**The onboarding session.** The goga engine asks the core project questions — the
language (`python`), the optional codemanifest / build-agent / pipeline sections, the
tools, and the usages records — followed by the pybuggy block. The block is
**kind-aware**: its first record asks the test kind — `api`, `web`, or `both`
(default `api`) — then the base image (FROM — the goga-python family hints, newest as
the default) and the built-image name. The Dockerfile itself is never asked about — it
is always created at `.goga/Dockerfile` from the answered base image. Every
kind-dependent ask happens at the amendment moment, where pybuggy prompts on its own:
the **api branch** (kind `api` or `both`) asks `base_url` (required, a Jinja2
template), the optional scalar plugin keys (Enter skips), the specs as one flow — the
first spec field by field (`name`, `type`, `location`, optional git fields), then
`Add another spec?` (default No) gating additional specs — and last the autonomy
confirms, one per pipeline — **"Run the api.automate pipeline unattended
(autonomous mode)?"** and **"Run the api.patch pipeline unattended (autonomous
mode)?"**, each defaulting to No; a Yes writes that pipeline's entry in the
`pipelines` section (see [Automate — Autonomous
runs](pipelines/api-automate.md#autonomous-runs) and [Patch — Autonomous
runs](pipelines/api-patch.md#autonomous-runs)). The **web branch** (kind `web` or
`both`) asks the web minimum — the LLM `provider` (its models write and classify the
browser-test steps), the two required model names, the browser name (a choice of the
five names the runtime accepts — `chromium`, `firefox`, `webkit`, `chrome`, `msedge`;
default `chromium`), and the headless confirm (default yes) — then its own autonomy
confirm, **"Run the web.automate pipeline unattended (autonomous mode)?"** (default No;
a Yes writes the entry into `web.yml` — see
[web.automate — Автономные прогоны](pipelines/web-automate.md#автономные-прогоны)).
Whatever you
answer to the core tools question, pybuggy is always recorded in `.goga/config.yml`.
The session writes `.goga/config.yml`, the Dockerfile, and the tool config of the
chosen kind — `.goga/tools/pybuggy/api.yml` (kind api or both) and/or
`.goga/tools/pybuggy/web.yml` (kind web or both):

```yaml
base_url: https://{{ env }}.svc.example/api
timeout: 10.0
specs:
  shop:
    type: openapi
    location: .specs/openapi/shop/shop-openapi.yaml
    git:
      url: https://git.example.com/specs/shop.git
      location: openapi/shop-openapi.yaml
      ref: main
```
`base_url` is a Jinja2 template rendered against `os.environ` + the CLI options you pass (e.g. `pytest --env=dev`).
Unanswered keys are dropped — never written empty; `headers`/`loader` are not surveyed (hand-add them when needed).
See [Configuration](configuration.md).

**The pybuggy bootstrap.** The files the session does not carry:

| Artifact | Gate |
|----------|------|
| `.goga/usages/cooks/pybuggy/<stem>.md` — the packaged api usages (`api.md`, `asserts.md`) and the web usage (`pybuggy-web.md`) | kind-gated (the api pair only for the api kind, `pybuggy-web.md` only for the web kind); written (bare overwrites; template skips existing) |
| `.goga/usages/cooks/pybuggy/sandbox/<stem>.md` — the packaged sandbox usages (`sandbox-session.md`, `sandbox-file.md`, `data-operations.md`, `migration-set.md`) | written (bare overwrites; template skips existing); flat copies from earlier distributions stay untouched |
| commented example records for absent plugin members in `.goga/tools/pybuggy/api.yml` | emitted (idempotent, comment-only) |
| commented example records for absent web keys in `.goga/tools/pybuggy/web.yml` | emitted when the web config was written (idempotent, comment-only) |
| `.goga/usages/conventions.md` — the pybuggy test convention | created when absent; an existing file is left untouched |
| `build.review.skip: true` in `.goga/config.yml` | always enforced (idempotent) |
| the pybuggy install block in the project Dockerfile (`USER root` / `COPY . /tmp/project` / `RUN cd /tmp/project && goga install && rm -rf /tmp/project` / `USER goga`) | written when the file exists (idempotent); the bulk `goga install` reads the project's own `tools:` pin — no version in the block |
| the playwright browser-install `RUN` line — `RUN playwright install --with-deps <browser>`, the browser read from the written `web.yml` | when the web config was written — appended when absent, repinned in place on a browser change (idempotent) |
| usage keys `pybuggy-api` / `pybuggy-asserts` + annotation lines in `codemanifest` | registered when `api.yml` was written (idempotent; user-defined keys are never overwritten); a web-only project registers neither — the `pybuggy-web` usage key + annotation registers only when `web.yml` was written; the sandbox capability usage files are copied to `.goga/usages/cooks/pybuggy/sandbox/` without registration — they may or may not apply to a given cell, and the config usages bind every cell |
| root `conftest.py` (`load_dotenv()` → `plugins.install()`) | generated when absent; bare mode asks before overwriting (default: no) |

The command requires a Dockerfile — and the session always creates one (the fixed
`.goga/Dockerfile` path plus the answered base image), so the mandatory-Dockerfile
check is a safety net, not a question to answer
(see [CLI — init, the mandatory Dockerfile](cli/init.md)).

This is the **bare** flow: it runs in a fresh project. A repeated invocation (an existing
`.goga/`) is refused — `Project already initialized`, exit code 1, nothing updated — the
same guard `goga init` applies. The command also scaffolds a project from a
copier-compatible template (`init <tpl> [--ref <git-ref>]`) and upgrades a scaffolded
project (`init --upgrade`) — see [CLI — init](cli/init.md). A native
`goga init -t pybuggy` runs the same session without the bootstrap — the flag and the
pybuggy-owned files land only through the pybuggy CLI.

## 3. Run the pipeline: `goga pipeline pybuggy:api.automate`

```bash
goga pipeline pybuggy:api.automate
```

This is the primary way to create tests with pybuggy. The pipeline:

- asks for the **testing subject** and collects detailed requirements from your
  description and the service spec — the topic is the current git branch;
- walks the whole chain — requirements → test cases → test cells → test code → review →
  acceptance — involving you at every communication stage in the default interactive
  mode (see [Autonomous runs](pipelines/api-automate.md#autonomous-runs));
- scaffolds the `api/` fixtures and materializes the tests into `tests/<spec>/<id>/`;
- commits nothing without your confirmation; failures found at acceptance are triaged
  with you and recorded in the topic's `bugs.md` (the `goga history` tree).

Run the resulting suite with:

```bash
pytest
```

The full stage list and the artifact chain: [Pipelines](pipelines/api-automate.md).
