# Trace Report

**Cell under trace**: `goga_tool_pybuggy/commands/init` (single-cell scope per 01-scope.md).

## Call Flow

```
init_cmd (CLI wrapper, init.py:430)
└─ run_init(tpl, ref, upgrade) (init.py:266)
   ├─ onboarding session (amend_pybuggy_config, session.py)
   │    ├─ writes .goga/tools/pybuggy/api.yml and/or web.yml (kind signal)
   │    └─ buffers amendments: dockerfile pair, image name, build.review.skip,
   │         tools: {pybuggy: "<major.minor>.x"}  (session.py:338 — _recorded_version,
   │         importlib.metadata.version("goga-tool-pybuggy"))
   └─ run_bootstrap(template_mode) (init.py:335)
        ├─ step 6:  _resolve_dockerfile_path(config) (init.py:206; config `dockerfile`
        │           field, fallback .goga/Dockerfile)
        │           → install_pybuggy(dockerfile)            [bootstrap.py:325]
        ├─ step 6b/6c (web_written): _register_web_kind (init.py:158)
        │           → register_usages / register_annotations
        │           → install_playwright(dockerfile)         [bootstrap.py:408]
        └─ step 9: dockerfile.exists() — mandatory-Dockerfile invariant (init.py:423)
```

`install_pybuggy` and `install_playwright` are leaves — no further calls (file read/regex/write only).

## Data Flow

**install_pybuggy** (`bootstrap.py:325-379`):
`dockerfile_path` → exists? (absent → `None`, never created) → `importlib.metadata.version("goga-tool-pybuggy")`
(missing → `ValueError`, mapped by `run_bootstrap`'s wrapped tier to exit 1) → `pin = major.minor + ".x"` →
`line = "RUN goga install pybuggy -v {pin}"` → `_INSTALL_LINE` regex (`^RUN goga install pybuggy\b…`) →
equal → `None`; differ → replace span in place; absent → append with newline guard → INFO log → return line.

**install_playwright** (`bootstrap.py:408-461`):
`dockerfile_path` + cwd-relative `.goga/tools/pybuggy/web.yml` → lenient `browser.name` (absent/unreadable →
`None` + WARNING) → `line = "RUN playwright install --with-deps {browser}"` → `_PLAYWRIGHT_LINE` regex →
replace-in-place / append-at-end → INFO log → return line.

**Version-pin data flow (two independent derivations of the same x-range)**:
- session: `_recorded_version()` (session.py:338) → `.goga/config.yml` `tools: {pybuggy: "2.0.x"}` — the record
  the image-build bulk install reads;
- bootstrap: `install_pybuggy` → the Dockerfile `RUN … -v 2.0.x` line.
Both derive from installed-distribution metadata at init time; the Dockerfile line is the redundant second
derivation.

## Manifest Algorithm Mapping

| CODEMANIFEST (commands/init) | Code path | State |
|---|---|---|
| `install_pybuggy` Algorithm 1 (no-op when file absent) | bootstrap.py:347-348 | matches |
| `install_pybuggy` Algorithm 2 (derive pin from installed version; ValueError on metadata-less run) | bootstrap.py:350-356 | matches |
| `install_pybuggy` Algorithm 3/4 (repin in place on prefix match; append otherwise) | bootstrap.py:358-379 | matches |
| `install_pybuggy` Requirements (single RUN line, x-range floating pin, idempotent) | `_INSTALL_LINE` + line construction | matches |
| `install_playwright` Algorithm 1-4 (lenient browser read, prefix repin, append at end) | bootstrap.py:427-461 | matches |
| `run_bootstrap` step 6 (resolve path, augment via `install_pybuggy`) | init.py:399-400 | matches |
| `run_bootstrap` step 6c (web-gated `install_playwright`) | init.py:402-403 → init.py:174 | matches |

No manifest↔code drift exists on this path — the defect is requirement-level (see Inconsistencies).

## Cross-Cell Traversals

| Source Cell | Target Cell | Type | Path |
|---|---|---|---|
| `commands/init` | — (external boundary) | data | `importlib.metadata.version("goga-tool-pybuggy")` — the installed distribution, not a cell |
| `commands/init` | — (external boundary) | data | the consumer's Dockerfile and `.goga/config.yml` — written artifacts, not cells |

No cell-boundary traversal participates in the Dockerfile step; scope stays single-cell.

## Inconsistencies

| Type | Location | Expected | Actual |
|---|---|---|---|
| requirement vs contract (the defect) | `install_pybuggy` (CODEMANIFEST:720-752, bootstrap.py:325-379) | the install step runs as root over a copied project (`USER root` / `COPY . /tmp/project` / `RUN cd /tmp/project && goga install && rm -rf /tmp/project` / `USER goga`) so the config-driven bulk install can execute in the image | a single `RUN goga install pybuggy -v 2.0.x` line appended as the image's default (unprivileged `goga`) user, with a second, redundant version derivation |
| requirement vs contract (derivative) | `install_playwright` (CODEMANIFEST:754-783, bootstrap.py:408-461) | the playwright `RUN` must sit inside the root section (before `USER goga`) — `--with-deps` installs OS packages | the line appends at end-of-file; with the block ending in `USER goga` it would land in the non-root section |
| cross-reference drift risk | `session.py:331` (`_recorded_version` docstring "Mirrors the Dockerfile install pin of `install_pybuggy`"), `.usages/config-build.md:101`, `.usages/init.md:107`, `docs/cli/init.md:142`, `docs/getting-started.md:84` | after the fix these sentences describe the block form | they describe the single-line x-range pin |

## Trace Graph

```
[installed dist metadata] ──> _recorded_version ──> .goga/config.yml tools: pybuggy "2.0.x"
[installed dist metadata] ──> install_pybuggy ──> Dockerfile: RUN goga install pybuggy -v 2.0.x   ← DEFECT SITE
.goga/tools/pybuggy/web.yml ──> install_playwright ──> Dockerfile: RUN playwright install ... (appended last)
                                                        ↑ interaction: must land inside the root section
```

**Resolved external semantics** (validated against the installed `goga` CLI, `/opt/goga/bin/goga install --help`):
`goga install` with no `name` takes the **BULK** path — it reads `.goga/config.yml`'s `tools:` record of the
current working directory and installs every declared `goga-tool-<tool><spec>` in one pip call. This is why
`COPY . /tmp/project` + `cd /tmp/project && goga install` carries the correct pin without `-v`: the project's
own `tools:` record (written by the session amendment) is the single version source.
