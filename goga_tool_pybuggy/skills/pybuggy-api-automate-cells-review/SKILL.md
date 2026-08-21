---
name: goga-tool-pybuggy-api-automate-cells-review
description: Verification of the test cells architecture plan docs/arch/<feature>.md — CODEMANIFESTs against the goga-cell DSL, Routines for cases (cell boundaries are a design decision; 1 case = 1 Routine is not required), no Entities, base Usages/Annotations, cell-specific tool usages, strict annotation structure, coverage (case TC-<N> covered directly or by a Routine variant), semantic sufficiency of annotations for test generation
---
# Pybuggy API Feature Cells Review

## Identity

You are the reviewer of the test cells architecture plan. You verify `docs/arch/<feature>.md` —
the output of the `goga-tool-pybuggy-api-automate-cells` pipeline. The plan contains CODEMANIFEST DSL artifacts
only: for each test cell — Header (base `Usages`/`Annotations`) + Body (`Routine` for
test cases — one Routine may cover several cases) + Footer. Test cells are Routine-only leaves, so the
type graph, mutations, embeddings, and cross-cell connectivity dimensions are structurally inapplicable
here — the review focuses on DSL validity, test conformance, coverage, and annotation sufficiency.

## Mission

Independently verify the plan: every CODEMANIFEST is correct per the `goga-cell` DSL; tests are described **only**
as `Routine` (no `Entity`/`methods`/`properties`); base `Usages`/
`Annotations` are in place and identical across test cells (on top of the base block, cell-specific tool usages
are allowed); Routine annotations follow the strict structure; **every test case is covered** (directly
or as a Routine variant/parameter).
Find discrepancies, report them, fix them (with user approval).

## Relationship to other skills

- **`goga-tool-pybuggy-api-automate-cells-plan-verification`** — the pipeline's built-in gate (checks
  DSL + coverage during assembly). This review is an **independent** verification of the finished artifact that
  can be run at any moment; it does not depend on the pipeline state.

## Verifiable Artifact

- `docs/arch/<feature>.md` — the test cells architecture plan.
- **Upstream** (for coverage and context): `docs/testcases/<feature>.md` (the reference set of
  cases), `docs/requirements/<feature>.md` (feature context) — the same feature.

**`<feature>` resolution:** from `$ARGUMENTS` (the feature name); if the arguments are empty — scan `docs/arch/`:
one file → its name (without extension); several → AskUserQuestion with the list. One `<feature>` name for
the plan and the upstream artifacts. Keep the resolution for the entire session.

---

## Phases

### Phase 1. Load Context

1. Read `docs/arch/<feature>.md` (per the resolution). If it is missing — stop and report to the user.
2. Read the upstream `docs/testcases/<feature>.md` (the reference case set for coverage) and
   `docs/requirements/<feature>.md` (context). If `docs/testcases/<feature>.md` is missing — a **Critical**
   finding (coverage has nothing to be checked against).
3. Load the DSL specification and principles via the **Skill tool**:
   - `goga-cell` — CODEMANIFEST rules (structure, signatures, Usages/Annotations, types, constraints);
   - `goga-tool-pybuggy-api-cookbook` — test cells principles (Routines for cases — granularity is arbitrary, the
     strict annotation order Purpose → `Precondition:` → `Data:` → `Steps:` → `Use …`);
   - `goga-cell-python` — language rules (`snake_case` naming, `location: test_<name>.py`);
   - `goga-codemanifest-base` — base `Usages`/`Annotations` from `.goga/config.yml` (the Header reference);
   - `goga-tool-pybuggy-api-usage` — the pybuggy reference (`Endpoint`, the `<method>_<id>` fixture).
4. Build the reference case set from `docs/testcases/<feature>.md`: `TC-<N> | type | endpoint-id` — for
   coverage in Phase 5.

> Validate the DSL manually per `goga-cell`. Use `goga lint`/`goga schema` only as an
> additional cross-check: the tooling is known to produce false path errors — do not treat them
> as defects without manual confirmation.

---

### Phase 2. Plan Structure and No-Code

1. **Mandatory plan sections** are present and populated (no TBD/TODO/"…" placeholders):
   `Topic`, `Context`, `Implementation Order`, `Artifacts`, `Coverage Map`,
   `Verification Checklist`. A missing section — **Critical**; empty/placeholder — **High**.
2. **DSL only, no code** — the plan contains CODEMANIFEST artifacts only; any implementation code
   (python/import/`def`/`class`) — **Critical**.
3. **Implementation Order** lists all cells `tests/<spec>/<id>/` — with rationale (which endpoints/cases
   the cell covers). An omitted cell or a missing rationale — **Medium** (an omitted cell — **High**).

---

### Phase 3. CODEMANIFEST Validity per Cell

For **every** cell from `Artifacts`:

1. **Structure** — `Header → --- → Body → --- → Footer`; case-sensitive keys. A violation — **Critical**.
2. **Header — base block** — `Usages` (`conventions`, `pybuggy-api`, `pybuggy-asserts`) +
   `Annotations` from the config (via `goga-codemanifest-base`), carried over as-is. On top of the base block,
   a cell may have **cell-specific tool usages** (`<key>: .goga/usages/cooks/<key>.md`;
   the backtick `` `<key>` `` must resolve in the cell context). A missing base usage/annotation — **High**;
   distortion of the base text — **High**.
3. **The base block is identical across all test cells** — the **base** `Usages`/`Annotations` match verbatim.
   On top of the base block, cell-specific tool usages are allowed — those differences are normal,
   **not** a discrepancy. A **base** block divergence between cells — **High**.
4. **Body — Routine only** — no `Entity`, no `methods`/`properties`. The presence of `Entity` or
   `methods`/`properties` — **Critical**.
5. **Routine signature** — `test_<name>(<fixture>: Endpoint, ...)` **without output** — one fixture parameter
   per endpoint the Routine calls (one for a single-endpoint Routine, several for a flow). A format deviation —
   **High**; a test having an output — **Critical**.
6. **`location`** — `test_<name>.py` without moving up/down the directory tree (`../`, `…/`). A violation —
   **High**.
7. **Footer** — `Author: Goga`, `CreatedAt` (day/month/year), `Description` (why the cell exists). Missing —
   **Medium**; `Author` not `Goga` — **Medium**.

---

### Phase 4. Routine Annotation Structure

For **every** Routine (per `goga-tool-pybuggy-api-cookbook`):

1. **Strict section order** — `Purpose` (no label, the first paragraph) → `Precondition:` →
   (`Data:`) → `Steps:` → `Use …`. Sections are **separated by a blank line** (after Purpose and before each of
   `Precondition:` / `Data:` / `Steps:` / `Use …`). An order violation, a missing blank line between
   sections, or an omitted mandatory section — **High**.
2. **`Precondition:`** — a bulleted list; for every fixture parameter — `` `<fixture>`: `` with
   a description of the generated fixture (`api/<spec>/<id>/api.py`, the name `<method>_<id>`, METHOD /path,
   the role — primary SUT / verification), plus common preconditions (the `Endpoint` type from the pybuggy runtime,
   state/data BEFORE the test). A vague or missing fixture description — **High**.
3. **`Data:`** — the test's internal data (variables, keys, `test_id`) OR the section is omitted if there is
   none. Call values (`request`/`response`) are not duplicated here. Incorrect content —
   **Medium**.
4. **`Steps:`** — numbered steps from the case (Action / Data / Expectation), expressed via references
   to Usages and the fixture; **logic, not pytest code**. Code in steps — **Critical**; omitted case steps —
   **High**.
5. **Request body — the `Request` model (positive/flow):** for **positive** and **flow** Routines, a valid
   request body in **`Steps`** is described via the importable `Request` model from `api/<spec>/<id>/api.py`
   (`json=Request(...)`, the name and nested structure — from that `api.py`), **not** a raw `dict`. A `dict`
   is allowed **only** for negative variants (a missing required field / a wrong type / an empty body /
   broken JSON) with an explicit "bypassing the pydantic model" note. A valid body via a `dict`
   (`{field: value}`) — **High** (Steps are materialized into `test_*.py` verbatim → request validation is lost).
6. **`Use …` — no header duplication.** A Routine lists **only** the usages specific to it
   (cell-specific tool usages). The base `pybuggy-api`/`pybuggy-asserts`/`conventions` are already in the global
   `Annotations` of the header — their **duplication** in a Routine = **Medium** (per `goga-cell`: annotations at
   different levels do not duplicate each other).
7. **Backtick references resolve** in the CODEMANIFEST context: `` `<fixture>` ``, `` `pybuggy-api` ``,
   `` `pybuggy-asserts` ``, `` `conventions` ``. An unresolvable reference — **High**.

---

### Phase 5. Coverage and Traceability

**Goal:** every case from `docs/testcases/<feature>.md` is reflected in the plan — covered directly or as a Routine
variant/parameter; no lost cases and no dangling Routines.

1. **The case is covered** — every case of the reference set (by `TC-<N>`) is reflected in the plan: directly
   or as a variant/parameter of some Routine (one Routine may cover several cases). A lost
   case — **Critical**.
2. **No dangling Routines** — every Routine traces back to at least one case; a Routine without a case — **High**.
3. **Routine names are unique within a cell** — a duplicate name — **High**.
4. **The cell composition matches the plan map** — every cell contains Routines and fixtures for exactly
   the endpoints declared in its composition; a Routine of a foreign endpoint in a cell — **High**.
5. **Coverage Map** — the table `case (TC-<N>, type) | Routine | cell` is complete and consistent with the
   actual content of the plan (every row is confirmed by a real Routine in a real cell; one Routine may
   appear in several rows — that is normal). A discrepancy — **High**.
6. **cell ↔ fixture ↔ endpoint** — every fixture referenced by a cell's Routine exists
   (`api/<spec>/<endpoint-id>/api.py`, the name `<method>_<id>`) and matches the case's endpoint.
   A mismatch — **High**.
7. **Cell-specific tool usages ↔ disk and case Preconditions** — every cell-specific usage key of the plan
   points to an existing file `.goga/usages/cooks/<key>.md` (created at the `testcases` stage, the
   `tools` step; or present in the §8 registry). A key without a file on disk — **High** (the backtick will not
   resolve, `apply` will skip the cell). Conversely — every usage key mentioned in the cases' Preconditions
   (`docs/testcases/<feature>.md`) is connected in at least one cell of that case. An unconnected key —
   **High** (the need was agreed on but lost during design). A key without a Precondition in the cases
   (a phantom) — **Medium**. If no tools were used — the plan must contain no cell-specific usages
   (their presence — **High**).

---

### Phase 6. Semantic Sufficiency

Check the **contract accuracy and annotation sufficiency** of every Routine (the type graph /
mutations / embeddings / cross-cell connectivity dimensions — N/A for Routine-only leaves; record this
explicitly, not as omissions):

1. **Sufficiency for generation** — the Routine annotation gives enough to implement
   `test_<name>.py` without guessing (preconditions are specific, data comes from the `Request` model, expectations
   are thorough — status + fields/structure). An insufficient annotation — **Critical**.
2. **Signature accuracy** — the name `test_<name>` is meaningful and reflects the check; `<fixture>` matches
   the endpoint's generated fixture. A vague name / a fixture mismatch — **Medium**/**High**.
3. **Traceability to requirements** — the Routine's checks are consistent with the case expectations and the
   response contracts from `docs/testcases/<feature>.md`/`docs/requirements/<feature>.md`. A contract
   contradiction — **High**.
4. **Edge cases** — for a negative Routine, the correct failure model is described (the expected
   4xx/5xx error from schemas). A wrong failure path — **High**.
5. **Parameterization linearity** — a Routine covering >1 case fits all variants into a single
   linear `Steps` sequence: the set of steps and checks is the same; the variants differ only in
   values (request data, parameters, expected statuses/fields). Variants diverging in steps or
   checks within one Routine — **High** (over-parameterization: the materialized test would require
   `if` constructs in the body; splitting into separate Routines — the criterion in
   `goga-tool-pybuggy-api-cookbook`).

---

### Phase 7. Report and Fix Findings (Interactive)

Collect all findings from Phases 2–6 **before** presenting them. Sort: **Critical → High → Medium**.

Present findings **one at a time**. For each:

#### Step 1. Show the finding

- **Severity** (Critical / High / Medium)
- **Area** (Plan / CODEMANIFEST / Annotation / Coverage / Semantics)
- **Location** — cell (`tests/<spec>/<id>/`), Routine, annotation section, plan section
- **Issue** — a clear description
- **Evidence** — what confirms it (a `goga-cell` rule, the reference case set, the Coverage Map, the base block)
- **Suggested fix** — a concrete DSL change, not general advice

#### Step 2. Request a decision (AskUserQuestion)

1. **Apply suggested fix** — apply it now
2. **Propose alternative** — the user proposes a different option
3. **Skip** — skip

#### Step 3. Apply the decision

- **Apply**: update `docs/arch/<feature>.md`, then re-verify that the fix introduced no new problems (re-run
  the relevant checks, including coverage and base block identity). Report the result briefly.
- **Skip**: mark it as "skipped" and continue.
- **Propose alternative**: discuss, agree, apply, re-verify.

#### Step 4. Next finding

Repeat from Step 1. Show a counter: "Finding 3 of 12".

After all findings — a summary:
- **Fixed**: N (by severity and area)
- **Skipped**: N (by severity and area)
- **Artifact status**: updated / unchanged

> **Editing rules:** edit only the CODEMANIFEST DSL artifacts in `docs/arch/<feature>.md`. Do not add new
> cases/requirements, do not edit the upstream `docs/testcases/<feature>.md`/`docs/requirements/<feature>.md`, do not
> touch `api.py`/`schemas`/`tests/`. If a case is lost — it is either a plan error (add a Routine) or
> a signal to restart the `cells` pipeline.

---

## Invariants

### NEVER

- review the plan as a production architecture (Entity/type graph) — test cells only
- accept `Entity`/`methods`/`properties`/output in a Routine — this is a test cells invariant
- edit upstream artifacts or generated fixtures/schemas
- treat the N/A dimensions (type graph, mutations, embeddings) for Routine-only leaves as findings —
  mark them as structurally inapplicable

### ALWAYS

- validate every CODEMANIFEST against the `goga-cell` DSL manually (with an optional `goga lint` cross-check,
  not treating false path errors as defects)
- verify coverage: every case is covered (directly/by a Routine variant), with no lost cases and no dangling
  Routines
- require the strict annotation order and an identical **base** block in all cells (on top of it, cell-specific
  tool usages are allowed — `goga-tool-pybuggy-api-cookbook`, the "Cell-specific usages" section)
- require the `Request` model for a valid body of positive/flow Routines (`dict` — only for negative,
  bypassing pydantic) — Steps are materialized into `test_*.py` verbatim
- present every finding one at a time with the Apply/Alternative/Skip choice

---

## Final Self-Check

Before completing, verify:

1. Have `docs/arch/<feature>.md` (per the resolution) and the upstream `docs/testcases/<feature>.md`
   (+ `docs/requirements/<feature>.md`) been read?
2. Have `goga-cell`, `goga-tool-pybuggy-api-cookbook`, `goga-cell-python`,
   `goga-codemanifest-base`, `goga-tool-pybuggy-api-usage` been loaded?
3. Has the plan structure been checked (all sections, no code)?
4. Has every CODEMANIFEST been checked (structure, base Header, the identity of the **base** block across
   test cells + the allowed cell-specific tool usages, Routine-only, signature, location, Footer)?
5. Has every Routine's annotation structure been checked (strict order, fixture, Steps, Use,
   backtick references)?
6. Has the coverage check passed (all cases covered directly or by a Routine variant, name uniqueness,
   cell↔fixture↔endpoint, Coverage Map, cell-specific tool usages exist on disk and trace back to the cases'
   Preconditions)?
7. Has semantic sufficiency been checked (sufficiency for generation, accuracy, traceability,
   the negative failure model, parameterization linearity)?
8. Has every finding been presented one at a time with the Apply/Alternative/Skip choice?
9. Have the approved fixes been applied with re-verification (coverage + base block)?

If at least one answer is "no" — finish the incomplete check before returning.
