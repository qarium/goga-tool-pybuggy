# CLI — `goga tool pybuggy init`

Initializes the goga project and bootstraps the consumer's pybuggy environment — bare,
from a template, or as a template upgrade. Top-level command (not under `endpoint`);
also available as `python -m goga_tool_pybuggy init`.

## Synopsis

```bash
goga tool pybuggy init [<tpl>] [--ref <git-ref>] [--upgrade]
```

- `pybuggy init` — bare onboarding.
- `pybuggy init <tpl>` — template onboarding. `<tpl>` is a local path or a git URL of a
  copier-compatible template project, optionally carrying a `#ref` fragment
  (`https://host/repo.git#v2`).
- `--ref <git-ref>` — overrides the template ref: beats the URL fragment in template
  mode; sets the migration target in upgrade mode.
- `--upgrade` — template migration only (the template source is read from
  `.goga/scaffold.yml`).

## Modes

| Mode | Invocation | Behavior |
|------|------------|----------|
| **bare** | `init` | Interactive onboarding of a fresh or existing project |
| **template** | `init <tpl> [--ref]` | Scaffold the template project first, then run the onboarding with silent-skip gates |
| **upgrade** | `init --upgrade [--ref]` | Migrate a previously scaffolded project to a newer template version; no onboarding |

Flag rules (mirroring `goga init`): `<tpl>` and `--upgrade` are mutually exclusive;
`--ref` requires `<tpl>` or `--upgrade`. Violations print an error message and exit
with code `1`.

**Template mode.** Scaffolding runs first (`goga.scaffold` engine, copier underneath):
the template is rendered into the current working directory; only `project_name` is
injected programmatically — the remaining template questions are asked interactively.
A failed scaffold stops the command with the engine's exit code — **no onboarding side
effects are applied**. After a successful scaffold the onboarding pipeline runs with
**silent-skip gates**: an existing file is left untouched with an INFO log and no
interactive confirmation; a missing file is created through the normal flow — including
the interactive goga questionnaire when the template brought no `.goga/config.yml`.

**Upgrade mode.** Only the template migration runs (copier `run_update` via the
`.goga/scaffold.yml` state file); no onboarding prompts appear, nothing else is
written. The state file is persisted by the template itself (the answers-file entry) —
a template without one leaves `--upgrade` unusable: the engine reports the missing
state file with a non-zero exit. Engine preconditions (a clean git repository, a
git-trackable template, a non-decreasing version) surface as non-zero exits; the
command propagates them without wrapping.

## What the command does

The onboarding pipeline (bare and template modes; upgrade skips it entirely):

1. **Goga project config** — `.goga/config.yml`. When absent, the goga project is
   initialized in-process (offline): the language is fixed to `python`, the goga
   "Download base convention" question is not asked — no network calls — and the
   mandatory `.goga/Dockerfile` is generated. When present — bare mode asks whether to
   re-create it (default: no); template mode silently skips it with an INFO log.
2. **Tool config** — `.goga/tools/pybuggy/config.yml` is built interactively when
   absent (see below). When present — bare mode asks whether to rebuild it
   (default: no); template mode silently skips it with an INFO log.
3. **Packaged usages** — `api.md`/`asserts.md` are copied to
   `.goga/usages/cooks/pybuggy/`. When a target file exists — bare mode overwrites it
   with the package version; template mode skips it with an INFO log.
4. **Conventions slot** — `.goga/usages/conventions.md` is created from the package
   asset **only when absent** — in every mode; an existing file (brought by a template
   or created/modified earlier) is left untouched. The `conventions` usage key and the
   annotation line are registered idempotently on every pass.
5. **Review-executor flag** — `.goga/config.yml` is brought to
   `build.review_executor.skip: true` on every pass (including a skipped or declined
   config re-creation) — idempotently and round-trip (comments, key order and the
   remaining `build` content are preserved).
6. **Dockerfile install line** — `RUN goga install pybuggy -v 1.0.x` is appended to
   `.goga/Dockerfile`; idempotent, a no-op when the Dockerfile is absent (e.g. a
   template without one). Together with steps 4–5 and 7 these additive augmentations
   are the only way pybuggy integrates itself into an arbitrary template.
7. **Usages registration** — the usage keys (`pybuggy-api`, `pybuggy-asserts`, …,
   `conventions`) are registered in `codemanifest.usages`; annotation lines with
   backtick references are replaced or appended in `codemanifest.annotations`.
   Idempotent; user-defined keys and foreign lines are preserved.
8. **Root conftest** — `<cwd>/conftest.py` is generated from the fixed template
   (`load_dotenv()` → `plugin.install()`). When present — bare mode asks whether to
   overwrite (default: no); template mode silently skips it with an INFO log.

## Interactive tool-config build

Step 2 builds `.goga/tools/pybuggy/config.yml` interactively when the file is missing.
What is prompted:

- Scalar plugin keys, one at a time: `base_url` (required, a Jinja2 URL template — empty
  input is re-prompted), `timeout`, `retries`, `assert_timeout`,
  `assert_delay`, `assert_field_class`, `assert_response_class`. Optional keys are skipped
  with Enter.
- `headers` and `loader` are **not** prompted — written as commented examples.
- `specs`: for each spec — `name`, `type` (`swagger`|`openapi`), `location` (required),
  and an optional git block (`url`, `location`, `ref`). Multiple specs are supported;
  **at least one spec is required**.

Skipped optional scalars are emitted as commented entries (`# key:`); `specs` is emitted
as active YAML. The generated file is valid for [configuration](../configuration.md)
loading.

## Idempotency

- **Bare mode.** A repeated run asks before re-creating the goga config, the tool
  config, and `conftest.py` (all default: no). When everything is refused, the copied
  `api.md`/`asserts.md` are still refreshed from the package, the `conventions` slot is
  skipped (it already exists), and the review-executor flag, the Dockerfile install
  line, and the registrations no-op. There are no `--force`/`--dry-run` flags.
- **Template mode.** A repeated `init <tpl>` re-runs the scaffold (engine semantics)
  and then silently skips every existing file — no prompts.
- **Upgrade mode.** No onboarding state is touched; the migration itself is managed by
  the engine.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid flag combination (`<tpl>` with `--upgrade`; `--ref` without `<tpl>`/`--upgrade`); goga initialization canceled/failed |
| scaffold engine code | A failed scaffold or migration — propagated unchanged; a failed scaffold leaves **no** onboarding side effects |
| non-zero (`ClickException`) | Usages bootstrap, Dockerfile augmentation, or conftest write error |

## Preconditions and side effects

- Requires the installed `goga` package (a pybuggy dependency) — for the onboarding and
  the scaffold engine.
- Writes to `<cwd>/.goga/` (config, the Dockerfile install line, usages, the tool
  config) and `<cwd>/conftest.py`; the scaffold engine renders template files into
  `<cwd>` and may persist `.goga/scaffold.yml` (template-owned; it must not be
  git-ignored in a scaffolded project, or `--upgrade` stops working).
- Reads assets from the **installed** package (`importlib.resources`), not from the
  checkout directory.
- No network calls in bare onboarding; template/upgrade modes reach the template
  source (a git URL) through the engine.
- Only the `api` cell usages are copied — internal development cells
  (`config`/`spec`/`output`/…) are not copied.
