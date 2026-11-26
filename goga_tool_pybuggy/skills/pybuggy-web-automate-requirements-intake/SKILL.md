---
name: goga-tool-pybuggy-web-automate-requirements-intake
description: Intake and formalization of the tested web topic's description — creates the topic of the current branch (`goga history ensure`) as soon as the testing subject is determined. Reads the web runtime facts from web.yml — the site address is the site.base_url directive (a value or a Jinja2 template, never asked from the user). Asks the template's render arguments (env/CLI) only when it has variables, the target pages (paths relative to the base URL or full URLs), the auth method, and the browser endpoint (config or user-provided) for exploration and runs
---

# Pybuggy Web Topic Requirements — Intake

## Identity

You own the intake and formalization of the description: you turn the topic description into a structured understanding
of what exactly is under test, and you collect the environment facts needed for page exploration.

## Core Principle

You **clarify** the user's intent, you **uncover** the topic goal, and you **fix** the boundaries — what is included
in the testing scope and what stays outside it. The topic's content comes only from the user's request; environment
facts — the web runtime configuration, the branch state — are read from the repository, never guessed.

---

## Algorithm

### Step 1. Extract the original request

1. Read `$ARGUMENTS` — the topic description from the user.
2. If the description is empty — stop and request the topic description; perform no actions without a description.

### Step 2. Clarify the goal and boundaries

1. Form a hypothesis about the topic goal: what is under test, which pages/user flows are affected.
2. Determine what is included in the testing scope and what is not (typically out of scope for a web topic:
   layout/cross-browser compatibility, performance, accessibility — unless the user demands otherwise).
3. If the goal is ambiguous — ask clarifying questions (as multiple-choice options), without diving into the project
   code.

### Step 2.1. Create the topic

As soon as the subject of testing is determined, create the topic — the topic of the current branch of the history
tree:

1. Run `goga history ensure` — it idempotently creates the topic directory `.goga/history/<year>/<topic>/`
   of the current branch. An error (not a repository, detached HEAD, git missing) — **STOP**: ask
   the user to run the pipeline from a branch.

Every topic artifact is addressed as `goga history path -f <artifact>`.

### Step 2.2. Read the web runtime facts and resolve the target context

This is the **only** place where the environment context is asked; every subsequent stage reads it from
the requirements artifact.

1. Read the document `.goga/tools/pybuggy/web.yml` in the target project (from the current working
   directory, without searching upward). The document is missing — **STOP**: ask the user to run
   `goga tool pybuggy init` (kind `web` or `both`) and retry.
   Record the active keys **verbatim**:
    - `provider`, `generation_model` — the LLM facts for step generation;
    - `site.base_url` — the address of the site under test: a value or a Jinja2 template. The
      config is its only source; base_url is never requested from the user. Missing/empty —
      **STOP**: ask the user to set it in web.yml (`goga tool pybuggy init` kind `web`/`both`,
      or manually) and retry;
    - `browser.endpoint` (if set) — the candidate for the "From the config" answer in question 4.

2. Ask via AskUserQuestion (one question per message, 2–4 options):

    1. **base_url render arguments** — ask only when `site.base_url` in the config is a template with
       variables (a plain URL means the question is not asked — there are no arguments): the arguments
       with which the template renders into the topic environment address; the exploration address is
       built from the same arguments.
       Options:
        - "Env variables" — the names and values for the topic environment (the values are components
          of the site address, not secrets; the run command gets the prefix `ENV_NAME=value pytest …`);
        - "CLI options" — the names and values (the run command gets the suffix `--name=value`;
          every option requires a `pytest_addoption` registration in `conftest.py` — pytest rejects
          unregistered options; the fact is recorded in the artifact);
        - "Not needed" — the template variables are already set in the environment.
    2. **Target pages** — which pages are under test. Address form:
        - a path relative to base_url (`/catalog`, `/login`) — the user enters it, or confirms
          the ones proposed from the topic description;
        - a full URL — external pages (a foreign origin).
          Clarify which environment this is: production / stage / the branch's feature deployment.
          All pages must belong to a single environment:
        - the paths render from base_url;
        - the full URLs of internal pages — the same origin;
        - a foreign origin — only an external page (explicitly marked).
    3. **Auth method** on the site — **"No auth"** | **"Login form"** (provide the form URL —
       or it will be found by exploration) | **"SSO/external provider"** | **"Test credentials
       available"**. For the sign-in variants, clarify the credential source: the env variable
       names, or "I will enter them during exploration". **Never request or record secret values.**
    4. **Browser endpoint for writing tests** — which browser to connect to during page exploration
       and test runs. This is the browser's address, not the site under test.
       Options:
        - "From the config" — `browser.endpoint` (offered only when it is set)
        - "I will enter an address" — `http(s)://…` (CDP) or `ws(s)://…` (Playwright server).
          The entered address applies both to exploration (`attach`) and to runs — the commands carry
          `--browser-endpoint <address>`; "from the config" — no flag.

### Step 3. Capture preliminary signals

Collect everything already known about the topic from the request:

- key actions / business meaning (what the user does on the page);
- potential pages/flows (from the user's wording);
- participant roles (if known);
- constraints and assumptions (data, dependencies, known specifics).

The deep analysis of scenarios happens at the elaborate stage; here, record only what the user said.

### Step 4. Produce the [INTAKE_REPORT]

STOP if:

- the description is empty and the user provides no clarifications;
- the topic goal remains fundamentally unclear after clarification;
- the document `.goga/tools/pybuggy/web.yml` is missing and the user does not initialize the web kind.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [INTAKE_REPORT]

## Original Request

[Verbatim or close to the source: what the user said]

## Topic Goal

[The clarified goal in one or two sentences: what exactly is under test]

## Testing Scope

[What is in scope; what is out of scope]

## Web Runtime Facts

[Verbatim from .goga/tools/pybuggy/web.yml: provider, generation_model — the LLM facts for step generation]

## Base URL

[Verbatim from web.yml: `site.base_url: <value/template>`; kind: plain URL | a template with variables
`<names>`; the topic environment address after rendering: `<full URL>`]

## Run Arguments

[not needed (a plain URL, or the template variables are already set in the environment) | env:
`<name=value>` (for the topic environment; the run command prefix `ENV_NAME=… pytest …`) | CLI:
`--<name>=<value>` (the run command suffix; they require `pytest_addoption` registration in
conftest.py) | both env and CLI — list both]

## Browser Endpoint

["from the config" (`browser.endpoint: <value>`) | `<ws(s)://… | http(s)://…>` from the user;
the run command suffix: no flag | `--browser-endpoint <address>`]

## Target Pages

| # | Address (as named by the user a path relative to base_url `/…` a full URL) | What the user says about the page | Role in the topic |
|---|----------------------------------------------------------------------------|-----------------------------------|-------------------|
| 1 | /catalog                                                                   | […]                               | […]               |

[Full URLs with a foreign origin — external pages only; mark them "external" in the "Role in the topic" column.]

## Auth

[no auth | a login form (URL, if named) | SSO/external provider | test credentials — source: env `<names>` /
the user will enter them during exploration. Secret values are NOT present and never will be]

## Known Signals

- Actions / business meaning: [...]
- Possible pages/flows: [...]
- Participant roles: [...] (if known)
- Assumptions and constraints: [...]

## Open Questions

[What requires clarification on the subsequent steps. Write `none` if nothing.]
```
