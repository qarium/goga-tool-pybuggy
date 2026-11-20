---
name: goga-tool-pybuggy-web-automate-testcases-tools
description: Identifying the tool needs of the web tests (data preparation via API, backend mocks, test-credentials usage files) from the requirements, agreeing on the tools with the user, and creating usage files .goga/usages/cooks/<key>.md
---

# Pybuggy Web Topic Testcases — Tools

## Identity

You identify the tool needs of the topic's tests, agree on them with the user,
and create usage files for new tools. A web test is self-sufficient in the browser, but it often needs
data preparation, mocks, or a documented way to log in.

## Core Principle

A tool is anything that exists **outside** step suggestions: a data-preparation library (API client),
a backend mock, or a usage file "how to log in".

Boundaries:

- The assembly phase wires a usage key into the cell Header — you only create/select the files.
- The web runtime (`pybuggy-web`) is not a tool — it is already in the base block.
- Page usage files (`page-<name>`) are not created here either — they originate at the pages stage
  from repeated steps of approved routines.

---

## Algorithm

### Step 1. Identify the needs

Walk through [TESTCASES_INTAKE] and identify needs of three kinds:

1. **Data preparation via API** — the §3 scenarios need entities that cannot be created through the UI
   (or it is impractical): a product catalog, reference records. Tools: existing
   cooks keys from the §8 registry (for example, `requests`/`httpx`) or new libraries.
2. **Backend mock** — rare: when a §3 REQ describes the page's reaction to an unavailable/failing
   backend. Tools: for example, `mokapi`/`wiremock` (if present in the registry or the user
   confirms them).
3. **Test credentials / how to log in** — a usage file documenting the login mechanism and the source
   of credentials from §4 (env names), **without secret values**: routines reference it in
   preconditions ("logged in as test user `<role>`" — see `<key>`).

A need without a tool in the §8 registry is a candidate for a new usage file.

### Step 2. Agree with the user (WAIT)

For each need, use AskUserQuestion (one question per message, 2–4 options):

- **"Existing usages"** — the key is already in the §8 registry;
- **"New usage file"** — create `.goga/usages/cooks/<key>.md` here (the key is the library name
  in snake_case/kebab-case; the content is how to consume the tool in this project's tests: purpose,
  base calls, where to get values; secrets — env names only);
- **"Defer"** — the need does not block the tests (record it in the report as open).

### Step 3. Create the usage files

For confirmed new tools, create `.goga/usages/cooks/<key>.md` (`page-<name>`
is not created here — that is the pages stage):

1. Heading `# <key> — <purpose in this project>`.
2. Sections: Domain (what it covers), Enable (connection/dependencies), Usage (how to use in
   tests — patterns, without secret values), Examples (2–3 fragments).
3. Write for an agent without topic context:
   - a tool reference — purpose, calls, sources of values;
   - topic identifiers (`REQ-<N>`, case/ticket numbers, artifact § links) must not
     get into the file — the coverage registry is session-scoped.
4. The file must exist on disk before the end of the step — the assembly phase wires into the Header
   only the keys of existing files.

### Step 4. Produce the [TOOLS_REPORT]

STOP if:

- a blocking need (routines cannot be built without it) remains without a tool after the agreement step.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [TOOLS_REPORT]

## Identified Needs

| Need | REQ §3 | Kind (data / mock / credentials) |
|-------------|--------|---------------------------------|
| […] | REQ-1, REQ-4 | data |

## Decisions

| Need | Decision | Key |
|-------------|---------|------|
| […] | existing usages / new usage file | `<key>` |

## Created Usage Files

| key | path |
|-----|------|
| `<key>` | .goga/usages/cooks/<key>.md |

[If nothing is created — `none`]

## Deferred Needs

[Deferred needs + why they do not block. Write `none` if nothing.]
```
