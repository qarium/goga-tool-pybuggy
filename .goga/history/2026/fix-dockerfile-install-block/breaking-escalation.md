# Breaking Change Escalation Report

**Pipeline stop**: goga-change Step 2 (Investigation) — breaking change detected (03-investigation.md).
**Verdict**: the requested fix changes observable output for identical inputs — generated artifact content,
return-value semantics, manifest guarantees, and pinning tests. Corrective intent does not downgrade the
classification; per the project rule the implementation proceeds only after an explicit user override of
this stop.

**User override (q2, 2026-10-30)**: approved — option A. The block lands without `-v` (the project's `tools:`
record is the single version source); the playwright line slots inside the root section before `USER goga`;
a stranded post-`USER goga` playwright line is relocated on the next regeneration.

## What breaks (concrete account)

| # | Same input | Output today | Output after the fix |
|---|---|---|---|
| 1 | `pybuggy init` (any kind), Dockerfile exists | `RUN goga install pybuggy -v 2.0.x` appended as the image's default (`goga`) user | the root block: `USER root` / `COPY . /tmp/project` / `RUN cd /tmp/project && goga install && rm -rf /tmp/project` / `USER goga` |
| 2 | `install_pybuggy(path)` call (API) | returns the single line; raises `ValueError` on a metadata-less run | returns the multi-line block; no version derivation → no `ValueError` branch (the bulk install reads the project's `tools:` pin) |
| 3 | web-kind init, Dockerfile exists | playwright `RUN` appended last (as the `goga` user) | playwright `RUN` inserted inside the root section (before `USER goga`) — `--with-deps` needs root |
| 4 | previously bootstrapped project, re-run | old single line repinned in place | the old single line is **replaced in place** by the block; a stranded playwright line is relocated inside the root section — the next regeneration repairs the layout (staged rollout; existing projects keep their prior output until then) |
| 5 | tests | `TestInstallPybuggy` (5), `test_init.py` `_INSTALL_LINE`/ordering pins (5+), `test_init_integration.py` (2) | rewritten to the corrected contract |
| 6 | mirrors | CODEMANIFEST `install_pybuggy`/`install_playwright`/`run_bootstrap` step 6/6c; `.usages/init.md`, `.usages/config-build.md`, `docs/cli/init.md`, `docs/getting-started.md`, `session.py::_recorded_version` docstring | moved in lockstep to the block form |

## Minimal proposed fix

1. **`install_pybuggy` writes the block** (bootstrap.py): `USER root` / `COPY . /tmp/project` /
   `RUN cd /tmp/project && goga install && rm -rf /tmp/project` / `USER goga`; presence-gated (file absent →
   no-op), idempotent at the current block; an existing install line of any previous shape (the
   `_INSTALL_LINE` prefix match) is **replaced in place** by the block. The `importlib.metadata` derivation
   and its `ValueError` branch are removed from this writer (the session's `tools:` amendment —
   `_recorded_version`, untouched — is the single version source the image build reads).
2. **`install_playwright` slots inside the root section**: the line is inserted before the block's trailing
   `USER goga` when the block is present (fresh and repaired layouts alike); repin-in-place semantics on the
   command prefix are kept; when a stranded playwright line sits after `USER goga`, it is relocated (repair
   in place).
3. **Lockstep contract move**: `commands/init` CODEMANIFEST (`install_pybuggy` signature label
   `-> block:str | None`, algorithm, requirements; `install_playwright` algorithm; `run_bootstrap` step 6/6c
   wording), `.usages/init.md`, `.usages/config-build.md`, `docs/cli/init.md`, `docs/getting-started.md`,
   `session.py::_recorded_version` docstring (drop the "mirrors the Dockerfile install pin" phrasing), and
   the pinning tests — one change, all surfaces, per the project's lockstep rule, closed by a repo-wide text
   search for the old line form.

## Explicitly NOT changed

- The session seam: questions, kind gating, config payloads, `tools:` amendment (still
  `<major.minor>.x` from installed metadata) — untouched.
- `_resolve_dockerfile_path`, the mandatory-Dockerfile invariant (step 9), every other bootstrap writer.
- The `install_playwright` browser source (written `web.yml`), line text, and prefix-repin semantics.
- All other cells.
