# Steps

The step sentence is the unit of generation: each sentence becomes Playwright code through
an LLM **once**, is cached next to the test, and replays from the cache on every later run.
The basic forms — `web.step` / `web.expect` / `web.group` — are covered in
[Web — Overview](index.md#writing-a-web-test); this page covers the step parameters,
captured variables, groups, the raw-Playwright escape hatch, and the failure verdicts.

## Step parameters

`step` and `expect` (and the page-object proxies `page.step` / `page.expect`) take three
keyword-only parameters:

- `tries=N` — the total number of executions of the step's code, the first execution
  included. `None` (default) — the **settle mode**: on a pollable failure the same code
  re-executes after `polling_delay` while time remains inside `polling_timeout`
  ([web.yml](configuration.md#keys)). The settle window starts at the **first execution**,
  never at the first failure; the step's internal auto-waits count inside it, and the first
  execution may consume the whole window (no repetitions follow). Non-pollable failures
  (locator ambiguity, Python-level errors of the step code) never re-execute — they
  propagate.
- `delay=S` — a quiet pause before the step, seconds (non-negative, fractional allowed).
- `vars={...}` — call-local string inputs of this one step; every value must be a string.
  A separate namespace from captures: `{{ name }}` reads a captured memory value,
  `{{ vars.name }}` reads a call input — call inputs never establish memory.

A sentence is always a plain string literal: `{{ … }}` and `{{ vars.… }}` are prettyplay
markers reaching the engine verbatim, and a Python value enters a sentence only through
`vars=`:

```python
page.expect(
    "The driver row {{ driver_id }} shows {{ vars.expected_telephone }}",
    vars={"expected_telephone": expected_telephone},
)
```

## Capture vars from a page

```python
def test_open_third_video(web):
    web.step("Open https://video.example.com/feed")
    web.step("Save the title of the third video in {% var video_title %}")
    web.step("Open the video '{{ video_title }}'")

    web.expect("The opened video page shows the text '{{ video_title }}'")
```

- `{% var <name> %}` inside a step sentence captures a value from the page into a variable —
  place the marker inline at the point of the sentence where the value belongs.
- `{{ <name> }}` in any later sentence — a step or an expectation — interpolates the captured
  value; `{{ vars.<name> }}` interpolates a call-local input of this step (the `vars=`
  parameter) — a separate namespace: `{{ <name> }}` reads memory, `{{ vars.<name> }}` reads
  the call inputs, and call inputs never establish memory.
- Capture only a value the test cannot know at write time — dynamic page data (the title of
  the third video, a generated order number). A value known in advance — a URL, a typed
  text, an expected literal — stays inline in the sentence; capturing it is noise. A
  captured var lives inside its own test only (one session per test, nothing carries
  between tests).
- Everything captured — and every step sentence — reaches the LLM provider prompt and the
  repository: **never put secrets in step sentences** (no passwords, tokens, keys, personal
  data).

## Transient elements

A toast / notification banner that appears on an action and auto-disappears seconds later is
checked (or read) **in the very sentence that triggers it**:

```python
web.step('Click the "Save" button — the "Changes saved" toast appears in the top-left corner')
```

On the generating run each sentence's code is produced by an LLM round (tens of seconds)
immediately before the sentence executes, so a separate expectation sentence only starts
generating after the trigger already ran — by the time its check executes the transient
element is long gone and the polling can never observe it. The sentence is the unit of
generation: wrapping the two in a group or a page-object method does not help — fold the
check into the triggering sentence. A toast-borne value rides a `{% var %}` capture placed
in that same sentence.

## Groups

```python
def test_checkout(web):
    web.step("Open https://shop.example.com/checkout")

    with web.group("Submit the order form") as g:
        g.step('Fill the "Email" field with user@example.com')
        g.step("Submit the form")
        g.expect("The order confirmation appears")
```

- `web.group(prompt)` — the authoring block for one coherent mini-scenario with a shared
  goal; the prompt names that goal and reaches generation requests verbatim. Inside the
  block the surface is the ordinary one: `g.step` / `g.expect` with the `tries` / `delay` /
  `vars` step parameters.
- Use a group when a set of actions moves the page or a widget from one state to another —
  fill and submit a form, walk a multi-field dialog to its outcome, log in. Such steps are
  meaningful together and the group prompt names the reached state; independent actions stay
  as ordinary steps.
- A group heals as a unit: on a non-strict run a failed group step is diagnosed once against
  the whole group, and a `recoverable` verdict regenerates the affected steps forward — the
  case where a later step fails because an earlier action never actually moved the page to
  the expected state. A diagnosed product defect still fails the test loudly.
- Group membership changes no step's cache address: cached group steps replay as ordinary
  steps, `--strict-mode` included; the steps after the block are ordinary steps again.
- `speed` (0–100, the between-step pace) and `delay` (the entry pause, seconds) optionally
  pace the block.
- The group prompt follows the same no-secrets rule as step sentences.

## Raw Playwright escape hatch (`run_on_page`)

`web.run_on_page(action)` (or `page.web.run_on_page(action)` from a page object) executes
the callable wholly inside the driver worker thread with the **genuine sync Playwright
`Page`** — the stateful actions excluded from generated code (auth headers, dialog handlers,
downloads, uploads, exact waits) are the author's explicit tools here:

```python
def test_delete_confirm(page_drivers):
    with page_drivers() as page:
        page.web.run_on_page(lambda pw: pw.on("dialog", lambda dialog: dialog.accept()))
        page.step("Click the Delete button of the first row")
```

- The callable runs sequentially with every step; whatever it raises propagates to the
  caller as-is; a call back into the test object from inside is rejected loudly.
- Returns plain data only — Playwright objects never cross back to the calling thread.
- Requires an open page: the page opens lazily on the first step — run a step (or activate a
  page object) first; before that the call fails with the loud "no test page yet" error.
- The same no-secrets rule: credentials come from env inside the callable, never from
  sentences.

## Terminal failures and verdicts

Every library failure is a structured `PrettyplayError`. The terminal ones a test author
meets:

- `ProductDefectError` — the step's expectation is genuinely broken in the product: neither
  replay nor regeneration helps, the test fails loudly (the triage signal of a service bug).
- `IncurableStepError` — the step never generated successfully, or the diagnosis verdict
  says regeneration cannot help.
- A **recoverable** verdict — a later step failed because an earlier action never actually
  moved the page to the expected state — regenerates the affected steps forward (group
  healing on non-strict runs); a diagnosed product defect still fails the test loudly.

In `--strict-mode` nothing regenerates: a cache miss or a failing step fails the test as-is —
that is exactly what CI replay checks.
