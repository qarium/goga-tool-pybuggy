---
name: goga-tool-pybuggy-web-automate-requirements-review
description: Verification of the web test requirements artifact `goga history path -f requirements.md` — requirement quality (checkable browser-observable behavior with a concrete outcome, no vague predicates, no locators/selectors outside §4 auth), internal consistency (base URL with its render arguments, page paths vs the base URL, page-object bindings vs `pages/**` on disk, auth, roles, pages), realness of web runtime facts and the usage registry against the disk, and targeted live re-verification via the saved exploration command (§1) when a fact is unclear or disputed; no `goga schema` (cells and routines do not exist yet at this stage)
---
# Pybuggy Web Topic Requirements — Review

## Identity

You are the reviewer of the "Detailed web topic requirements" artifact — the file at the path printed
by `goga history path -f requirements.md`, the output of the `goga-tool-pybuggy-web-automate-requirements`
pipeline. The artifact describes the **behavior** of the pages under test for subsequent Routine design;
it contains no test code.

## Objective

Verify the artifact for **requirement quality, internal consistency, and realness of facts**.
Success criterion: every requirement genuinely requires — formulates checkable page behavior with a
concrete observable outcome — and the `testcases` stage can derive concrete Routines from §3 without
guessing. You **analyze** the artifact, **report** findings, and **fix** them (every fix requires user
approval). An unclear or disputed fact is re-verified on the live page (phase 5, via the re-exploration
command from §1), not reconstructed from memory.

## Core Principle

**Requirements must genuinely require.** Each `REQ-<N>` is "condition → observable page reaction"
behavior with enough concreteness for future step suggestions: verbatim texts, concrete page addresses
(a path relative to the Base URL or a full URL), visible elements. A vague expectation ("works
correctly"), an expectation not verifiable through the browser, behavior without grounding in the
artifact's facts — findings. Format (sections, identifiers) is background: violating it is a finding,
but the review does not reduce to it.

### User Interaction Rule

**Always offer answer options.** Route every decision request to the user through AskUserQuestion with
concrete options (2–4); never ask an open-ended question without choices.

---

## Verifiable Artifact

- The path printed by `goga history path -f requirements.md` — the topic's detailed requirements.

No upstream artifact exists: this artifact is the head of the topic chain.

---

## Phases

### Phase 1. Load Context

1. Read the artifact at the path printed by `goga history path -f requirements.md`. If the file is
   missing or empty — **STOP**: ask the user to run the `goga-tool-pybuggy-web-automate-requirements`
   pipeline first.
2. Load via the **Skill tool**:
   - `goga-tool-pybuggy-web-usage` — the web runtime reference: the fixture sees only the page
     (DOM/text/URL/state); step suggestions are born from requirement formulations
     (`page.step`/`page.expect` via page fixtures) — this defines what "observable through the browser"
     means;
   - `goga-tool-pybuggy-web-cookbook` — what the `testcases` stage needs: Routines are built from
     §2/§3/§4, and §3 expectations will become `page.expect` suggestions.
3. Collect ground truth from disk (without `goga schema`):
   - `.goga/tools/pybuggy/web.yml` — the active `provider`, `generation_model`, `site.base_url`
     (if set — the value/template verbatim), `browser.endpoint` (if set) — verbatim;
   - a scan of the target project's `.goga/usages/` — the registry for cross-checking §8;
   - a scan of `pages/**` — existing page objects (module/fixture/class) for cross-checking the §2
     bindings;
   - the presence of `tests/web/**` — a fact for §9 (empty is expected for the first topic, not a
     finding);
   - §2 "page details" and the §1 "re-exploration command" — the dossier's recorded factual base:
     the cross-check of REQ wording against the §2 details goes by them; live re-verification
     (phase 5) is for facts outside the details or raising doubt. An old-format artifact (without
     details/command) is not a finding; missing facts are covered by phase 5.

### Phase 2. Structure (background)

1. Sections §1–§9 are present. A missing section — **Critical**; an empty section or one with a
   placeholder (TBD, TODO, "…", "later") — **High**. §6/§7/§9 may be empty only with an explicit
   marker (`none` / "no coverage" / real links).
2. **REQ identifiers**: every §3 item (all four subsections) carries a `REQ-<N>` — absence is
   **High** (the requirement is invisible to Routine traceability); identifiers are unique (a
   duplicate — **High**) and continuous from 1 in subsection order (a gap — **Medium**); `REQ-<N>`
   appear only in §3 (otherwise — **Medium**).
3. **PAGE identifiers**: `PAGE-<N>` in §2 are unique and continuous (a violation — **Medium**).
4. **No code**: pytest/playwright/fixtures/step suggestions in step form — **Critical** (a violation
   of the requirements pipeline invariant).

### Phase 3. Requirement Quality (main focus)

**Testability** (consumer — routines design):

1. Every REQ is "condition → reaction" behavior or a measurable criterion, not a bare description of
   a fact. "The product catalog is displayed on the page" without a verifiable outcome — **High**;
   fix — reformulate behaviorally (what the user does and what is observed).
2. The reaction is observable **through the browser**: text, URL, element, page state. An expectation
   verifiable only in the DB/API/logs/metrics — **High**: the web runtime will not verify it; fix —
   reformulate it to what is observable in the page or move it to Constraints.
3. Acceptance criteria are unambiguously checkable ("yes/no"). An ambiguous criterion — **High**.
4. Error behavior is a contract: condition → concrete reaction (verbatim validation text / the empty
   state's appearance / a 404 page). "An error message is shown" without concreteness — **High**.
   The absence of an error-REQ when forms/validation exist — **not a finding**: negative coverage in
   UI tests is optional (a rare case; a topic without negative behavior is the norm). An error-REQ
   must exist only for errors observed in the dossier (verbatim texts in the §2 details) or named by
   the user; an error-REQ **without such grounding** (invented/hypothetical, including unconfirmed
   contracts from client code without a user decision) — **High**.

**Concreteness** (consumer — generation of `page.expect` from these formulations):

5. Observables are named concretely: reaction texts verbatim (in quotes), page addresses concrete
   (a path relative to the Base URL or a full URL), elements by visible names. Vague filler words in
   expectations — "correctly", "properly", "successfully", "up-to-date data", "in an acceptable
   form" — **High**: no stable check can be built from such an expectation. Locators/selectors (CSS,
   XPath, testid, addressing attributes) outside the §4 Auth entry mechanism — **High**: addressing
   in test steps goes by visible names; a locator from the requirements leaks into Routine
   annotations (`Prompt:`, step suggestions).
6. Conditions may be behavioral (the `testcases` stage will pick concrete test data), but placeholder
   stubs `<…>`, "some", "etc." inside a REQ — **Medium**.

**Grounding** (consumer — accept: an invention = a false failure):

7. Every scenario relies on the artifact's facts: §2 pages, §4 auth, §6 integrations. Behavior
   without grounding — not from the pages, not from user decisions — **High** (an invention
   candidate); fix — remove it or confirm the fact with the user.
8. Atomicity: one REQ — one behavior. A conjunction of independent behaviors in one REQ — **Medium**
   (fix — split it). Two REQs about the same thing — **Medium**.
9. Constraints meaningfully describe what the topic does **not** do; an empty general phrase —
   **Medium**.
10. Roles (§5): every "who cannot" **with an observed fact** (dossier/§2: redirect to login, login
    form, 403) is reflected by an error-REQ or deliberately excluded by a user decision — absence
    with an observed fact **Medium** (**High** if authorization is the topic's essence); the fact
    not observed — a proposal to the user, not a finding.

### Phase 4. Consistency and Realness

1. **Base URL**: §1/§4 carry the web.yml `site.base_url` **verbatim** (value or Jinja2 template; the
   only source is the config, the "from the user" variant is inadmissible) — a discrepancy, or a
   manual address instead of the config — **High**; the template is covered by render arguments:
   every template variable has an argument (env/CLI) in §1 — a variable without an argument **High**
   (an unknown variable crashes the run at start); the topic environment's address after rendering is
   present — absence **Medium**; a CLI-option argument is accompanied by a marker about registering
   `pytest_addoption` in `conftest.py` — absence **Medium**.
2. **Environment**: the final URLs of §2 have the same origin (scheme+host+port) as the rendered
   Base URL of §1; the topic's pages are addressed by `/…` paths relative to the Base URL. A full
   URL of a foreign domain without an "external" marker / mixing environments — **High**.
3. **Page addressing**: internal pages — by paths relative to the Base URL (`/catalog`) or by full
   URLs of the same origin; addressing outside the Base URL model (a bare host without a scheme, a
   query-relative address of an internal page) — **High**.
4. **Web runtime facts**: §1 and §4 repeat `provider`, `generation_model` from web.yml **verbatim**
   — a discrepancy **High**.
5. **Browser endpoint**: "from the config" ↔ `browser.endpoint` is actually set in web.yml (a
   mismatch — **High**); an address from the user — a valid `ws(s)://` / `http(s)://` form (any
   other — **High**); it is the **browser's** address, not the tested site's (mixed up — **High**:
   it breaks the `--browser-endpoint` suffixes of the recorded run commands).
6. **§1 ↔ §4**: repeated facts (runtime, endpoint, base URL, environment) match verbatim — a
   discrepancy **High**.
7. **Auth**: the §4 mechanism is consistent with the description of the protected pages in §2/§3;
   the source of credentials — only env names or "the user"; **secret values anywhere in the
   artifact — Critical**.
8. **Pages**: every PAGE-<N> is used in §3/§5 — a page without a role **Medium**; a scenario
   references an existing PAGE/address — a phantom **High**; a §2 page-object binding (fixture
   `page_<name>`, class `<Name>Page`, module `pages/**`) exists on disk — a phantom **High** (a
   simple scan of `pages/**`); "literal" navigation is marked with a reason (external origin / query
   address / root page) — unmarked **Medium**.
9. **§8 ↔ disk**: every table key corresponds to an existing `.goga/usages/**` file (a key without
   a file — **High**, a dangling reference for testcases; a path mismatch — **Medium**); a file in
   `.goga/usages/` outside the registry — **Medium** (an incomplete registry); an empty
   `.goga/usages/` without a "no usages" marker — **High**.
10. **§9**: with an empty `tests/web/**` — an explicit "no coverage" marker (without it — **High**);
    the mentioned existing Routine/files exist on disk (a simple file scan; do not run
    `goga schema`) — a phantom **High**.

### Phase 5. Live Re-verification (as needed)

A fact is unclear, has diverged from the §2 details, or a remark concerns UI and cannot be checked
on disk — re-verify it on the live page before proposing a fix or guessing. Do not connect to the
browser at stage start — the session is started only at the first finding that requires a live
check.

1. **Attach** — execute the re-exploration command from §1 of the artifact verbatim (the command is
   already in executable form for the writing environment; the `PLAYWRIGHT_MCP_OUTPUT_DIR` prefix is
   part of it).
2. **Vocabulary** — the minimum set of commands to answer the finding's question: `goto <url>` /
   `snapshot --depth=4` / `find "text"` / `--raw eval "<js>"` / `console` / `requests` / `go-back`.
   Interactions (`click`/`fill`) — only to observe a state (a harmless empty form submit → the
   verbatim validation text). The command vocabulary — load
   `goga-tool-pybuggy-web-playwright-cli` via the Skill tool (if the upstream `playwright-cli`
   skill is available in the environment, it carries the full reference).
3. **Auth wall** — WAIT (AskUserQuestion): "I'll enter now" / "from env `<names>`" / "skip" — then
   the finding is marked "not confirmed on the live page". Secrets are not written into the report.
4. **Budget** — only the §2 topic pages; no more than 3 pages per finding and 5 interactions per
   page; crawling adjacent pages — no. A full re-exploration of the topic is a restart of the
   `requirements` pipeline, not this stage.
5. **Observation → Evidence** — record verbatim (texts in quotes, final URLs after redirects,
   visible element names; no locators/selectors). The observation becomes the finding's Evidence;
   the artifact fix is based on it. If the fact has changed — update this page's §2 details as well.
6. **Hygiene** — after the re-verification, `detach` (the user's browser is not closed); a session
   crash — one restart (attach again), after that — the finding goes without a live check.

### Phase 6. Report and Fix Findings (Interactive)

Collect all findings of phases 2–5 **before** showing them. Sort by severity: **Critical → High →
Medium**.

Show them one at a time. For each:

1. **Severity** (Critical / High / Medium)
2. **Area** (Structure / Testability / Concreteness / Grounding / Consistency / Realness)
3. **Location** — an exact reference (section, REQ-<N>, PAGE-<N>, line)
4. **Issue** — what the problem is
5. **Evidence** — confirmation (web.yml, a missing file on disk, a contradiction inside the
   artifact)
6. **Suggested fix** — a concrete fix, not general advice

AskUserQuestion (2–4 options): **Apply suggested fix** / **Propose alternative** / **Skip**.
Counter: "Finding 3 of 12".

- **Apply**: update requirements.md, then re-check that the fix created no new problems (repeat the
  affected checks — including REQ numbering and cross-references). Report briefly.
- **Skip**: mark it "skipped", continue.
- **Propose alternative**: discuss, agree, apply, re-check.

After all findings — a summary: Fixed N / Skipped N (by severity and areas); artifact status:
updated / unchanged.

> **Fix rule:** edit **only** the artifact `goga history path -f requirements.md`. The browser — only
> the targeted live re-verification of phase 5 (topic pages, via the re-exploration command from §1);
> a full re-exploration is a restart of the `requirements` pipeline. Do not run `goga schema`; do
> not create cells or usage files. Do not mark a fact as confirmed when it is confirmed by neither
> disk, nor the artifact, nor live re-verification.

---

## Output

- Findings summary: fixed / skipped by severity and areas
- The updated `goga history path -f requirements.md` (if fixes were applied)
- Verdict: passed / failed

---

## Final Self-Check

Before finishing, check:

1. Has the artifact been read at the path printed by `goga history path -f requirements.md`?
2. Have `goga-tool-pybuggy-web-usage` and `goga-tool-pybuggy-web-cookbook` been loaded?
3. Has ground truth been collected from disk (web.yml, the `.goga/usages/` scan, the `tests/web/**`
   fact; the §2 details and the §1 re-exploration command) — without `goga schema`?
4. Has the structure been checked (§1–§9, REQ/PAGE identifiers, absence of code)?
5. Has every REQ's **testability** been checked (condition → browser-observable reaction, measurable
   acceptance criteria, error contracts with concreteness)?
6. Has **concreteness** been checked (verbatim texts, concrete page addresses (a Base URL-relative
   path / a full URL), absence of vague filler words and locators outside §4 Auth) and
   **grounding** (reliance on §2/§4/§6, atomicity, roles)?
7. Has consistency been checked (the Base URL and its render arguments, §2 paths ↔ Base URL, a
   single origin of the final URLs, §1↔§4, auth, usage of the pages) and realness (web runtime
   facts, §8/§9 ↔ disk, secrets)?
8. Has live re-verification been conducted for unclear/disputed facts and UI remarks (phase 5, via
   the re-exploration command from §1); have observations been recorded as Evidence and the §2
   details updated when a fact changed?
9. Has every finding been shown one at a time with an Apply/Alternative/Skip choice?
10. Have the approved fixes been applied with re-verification (including REQ numbering)?

If at least one answer is "no" — finish the unfinished check before returning.
