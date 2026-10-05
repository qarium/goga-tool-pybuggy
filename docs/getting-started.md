# Getting Started

Three steps take a project from zero to an automated API-test lifecycle:

```bash
goga install pybuggy                 # 1. install
goga tool pybuggy init               # 2. initialize
goga pipeline pybuggy:api.automate   # 3. run the pipeline
```

## 1. Install: `goga install pybuggy`

Installs the pybuggy package into the **goga**(<https://github.com/qarium/goga>)
environment of the target project.

## 2. Initialize: `goga tool pybuggy init`

Run in the target project root:

```bash
goga tool pybuggy init
```

The command (see [CLI — init](cli/init.md)) runs two stages — the engine-owned
onboarding session with pybuggy invited, then the pybuggy bootstrap.

**The onboarding session.** The goga engine asks the core project questions — the
language (`python`), the optional codemanifest / build-agent / pipeline sections, the
tools, and the usages records — followed by the pybuggy block: the base image (FROM —
the goga-python family hints, newest as the default) and the built-image name, then
`base_url` (required, a Jinja2 template), the optional scalar plugin keys
(Enter skips), and the first spec (`name`, `type`, `location`, optional git fields).
The Dockerfile itself is never asked about — it is always created at
`.goga/Dockerfile` from the answered base image. After the block, pybuggy asks its two
follow-ups itself: the additional specs (`Add another spec?`, a per-field loop), then
the autonomy confirm (**"Run the api.automate pipeline unattended (autonomous mode)?"
defaults to No**; Yes writes the `pipelines` axis entry — see
[Autonomous runs](pipelines/api-automate.md#autonomous-runs)). Whatever you answer to
the core tools question, pybuggy is always recorded in `.goga/config.yml`. The session
writes `.goga/config.yml`, the Dockerfile, and the tool config
`.goga/tools/pybuggy/config.yml`:
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
| `.goga/usages/cooks/pybuggy/api.md`, `asserts.md` — the packaged usages | written (bare overwrites; template skips existing) |
| `.goga/usages/conventions.md` — the pybuggy test convention | created when absent; an existing file is left untouched |
| `build.review.skip: true` in `.goga/config.yml` | always enforced (idempotent) |
| `RUN goga install pybuggy -v <N.M>.x` in the project Dockerfile | appended when the file exists (idempotent); the version range is derived from the installed pybuggy version |
| usage keys `pybuggy-api` / `pybuggy-asserts` / `conventions` + annotation lines in `codemanifest` | registered (idempotent; user-defined keys are never overwritten) |
| root `conftest.py` (`load_dotenv()` → `plugin.install()`) | generated when absent; bare mode asks before overwriting (default: no) |

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
pybuggy-owned files land only through the pybuggy CLI (see `MIGRATION.md` at the
repository root).

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
