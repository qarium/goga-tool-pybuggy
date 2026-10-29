# Breaking Change Escalation Report

**Pipeline stop**: goga-change Step 2 (Investigation) — breaking change detected.
**Verdict**: the requested fix changes observable output for identical inputs. Corrective intent does
not downgrade the classification; per the project rule the implementation proceeds only after an
explicit user override of this stop.

**User override (q2, 2026-10-29)**: approved. Kind-gated delivery/registration proceeds as proposed;
D3 resolved as option A (explanatory prompts, the two models stay required); the browser question
becomes a choice of the five runtime-valid names.

## What breaks (concrete account)

| # | Same input | Output today | Output after the fix |
|---|---|---|---|
| 1 | `pybuggy init`, kind `api` | `.goga/usages/cooks/pybuggy/pybuggy-web.md` delivered | file not delivered |
| 2 | `pybuggy init`, kind `web` | `api.md` + `asserts.md` delivered; `codemanifest.usages` gains `pybuggy-api`, `pybuggy-asserts` (+ annotation lines) | neither delivered nor registered |
| 3 | `pybuggy init`, kind `web`, browser typed `Chrome`/`safari`/anything outside the matrix | accepted at the prompt, written to `web.yml`, fails later at test runtime (`must be one of: chromium, firefox, webkit, chrome, msedge`) | rejected at the prompt (a choice of the five runtime-valid names) |
| 4 | template-mode bootstrap over a tree with no tool configs | api pair + conventions registered | only `conventions` registered (api registration becomes kind-gated on `api.yml` presence) |
| 5 | tests | `test_bootstrap.py::TestRunBootstrapUsages` (2 asserts), `test_init.py::test_run_bootstrap_web_kind_delivers_web_artifacts`, `test_init.py::test_run_bootstrap_api_only_skips_web_steps`, docs assertions | rewritten to the corrected contract |

Projects initialized before the fix keep their delivered files/registrations — nothing is removed on
upgrade; only fresh initializations produce the corrected output.

## Minimal proposed fix

1. **Kind-gate the copy** (`run_bootstrap` step 2): the api root's files copy only when `api.yml`
   was written; the web root's `pybuggy-web.md` only when `web.yml` was written; the sandbox subtree
   stays unconditional (kind-neutral, download-only by design).
2. **Kind-gate the api registration** (step 7): `pybuggy-api`/`pybuggy-asserts` + their annotation
   lines register only when `api.yml` was written — the same written-file kind signal the web steps
   already use. `conventions` stays unconditional (kind-neutral).
3. **Browser question becomes a choice** of the runtime matrix (chromium, firefox, webkit, chrome,
   msedge; default chromium) — invalid names can no longer enter `web.yml`.
4. **Web questions become answerable** — approach pending the user's choice (see question q2):
   explanatory prompts with required models, or models with defaults.
5. Contract surfaces move in lockstep: `commands/init` CODEMANIFEST (step 2/7 + Requirements +
   global annotation), `.usages/init.md`, `.usages/config-build.md`, `docs/cli/init.md`,
   `docs/getting-started.md`, and the pinning tests.

## Explicitly NOT changed

- Session seam, kind question, image inputs, spec/autonomy surveys — untouched.
- Sandbox usage delivery (download-only, kind-neutral) — untouched.
- `web.yml` payload shape (`build_web_config_data`) — untouched apart from the browser value source.
- Web cell contracts (`WebConfig`/`BrowserSettings`) — planned to stay code-unchanged; the choice
  lives at the prompt.
