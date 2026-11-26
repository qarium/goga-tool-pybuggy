---
name: goga-tool-pybuggy-web-usage
description: Loads and provides the pybuggy web runtime documentation (pybuggy-web) from .goga/usages/cooks/pybuggy/ — the reference for skills and tasks that write browser UI tests
---

# Pybuggy Web Runtime Usage

## Purpose

This skill provides documentation for the pybuggy web runtime — the `web` fixture (`pybuggy-web`): browser UI tests in
which each step is a natural-language sentence that the LLM converts into Playwright code once and caches next to the
test. This skill is the single source of context about the actual pybuggy web API.

Other skills and tasks (test design, code generation, and acceptance stages) invoke this skill to obtain an up-to-date
reference. The reference is based on the project's cooks file, not on guesswork.

---

## Behavior

1. Check the file `.goga/usages/cooks/pybuggy/pybuggy-web.md`. If the file is missing or empty, the web documentation is
   not loaded: ask the user to run `goga tool pybuggy init` (kind `web` or `both`; the command copies the web runtime
   documentation and registers the `pybuggy-web` key in `.goga/config.yml`), and stop.

2. Read the file in full. The file corresponds to the usage key `pybuggy-web`.

3. If `$ARGUMENTS` is passed (a theme: `web` or another), use only the parts relevant to the theme; otherwise use the
   entire file.

4. Apply the read content to the context of the calling skill. Web runtime surface:

    - The `web` fixture — activated by the document `.goga/tools/pybuggy/web.yml`.
    - Steps: `web.step(sentence)` — an action step; `web.expect(sentence)` — a check step (polling until the condition
      is true); `web.group(...)` — a mini-scenario block: a set of tightly coupled actions that changes the state of the
      page or widget; the group prompt names the target state, and the group is healed as a whole (diagnosis across all
      steps, regeneration of the row); `run_on_page(...)`.
    - Page objects: `BasePage(web, path)` — a subclass per page; the fixture `page_<name>` binds the path at
      construction and **returns the page instance** — the object the test receives as its parameter. The page object is
      **callable** (`__call__`): the activation call `page_<name>()` opens the page (one action step carrying the full
      URL composed from `site.base_url`) and returns the instance; `with page_<name>() as page:` scopes the work on the
      opened page. The `page.step/expect/group` surface is proxied (the same sentences and keyword-only parameters as
      the runtime's); generate the skeleton with `goga tool pybuggy page generate <path> <name>`; `pages/` fixtures are
      picked up automatically.
    - **Call protocol: activation first, then methods.** A page method (`page.<method>()`) never navigates — its
      sentences run on the page currently open in the test's single-page session, so the navigation/activation step
      precedes the method calls. Inside a method the surface is the instance's own: `self.step(...)` /
      `self.expect(...)` / `with self.group(...)`.
    - Variable capture: the `{% var <name> %}` marker inside a step sentence captures a value from the page; the
      `{{ <name> }}` marker in subsequent sentences (steps and checks) substitutes the captured value. Sentences are
      string literals: `{{ … }}` / `{{ vars.<name> }}` are engine markers passed verbatim; a Python value enters a
      sentence only via the `vars={...}` kwarg (separate namespaces: `{{ name }}` — memory, `{{ vars.name }}` — call
      inputs). Capture is only for page dynamics (values unknown at test-writing time); static literals are written
      without markers.
    - Page addressing: for pages of the site under test, use a path relative to `site.base_url` in the step sentence (
      the runtime composes site navigation from the directive; switching environments means switching `site.base_url`
      plus one run without `--strict-mode`); for external pages (a foreign origin), use the full URL in the step.
    - One step = one action.
    - The step cache is committed to the repository; the cache location is resolved automatically by call site: an
      inline step of a test — `tests/…/.cache/<module>/<test_name>/`; a step from a page-object method (the activation
      call included) — the shared cache `pages/.cache/<page>/<method>/` of that method: the step binds to the method, so
      the same sentence of two methods is two entries.
    - Modes: `--strict-mode` (0 LLM calls, cache-miss = failure; for CI and repeat runs); `--interactive` (interactive
      step healing); `--browser-endpoint ws://…|http://…`.

   Rules for applying the reference:

    - **Secrets in step sentences are forbidden** (everything reaches the provider prompt and the repository).
    - Use only the file's actual content as the source — do not invent API details.
    - Do not retell the file verbatim — give an applicable reference.

5. Provide the file path so the caller can read the full details if needed.
