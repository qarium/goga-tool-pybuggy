# goga_tool_pybuggy.commands.init — the pybuggy tool configuration survey and contribution

## Domain

The onboarding step that collects the pybuggy tool configuration and delivers it as the tool's session
contribution: the tool config files `.goga/tools/pybuggy/api.yml` (the api kind) and
`.goga/tools/pybuggy/web.yml` (the web kind). The survey is kind-aware: the first record of the pybuggy block
asks the test kind (`api` / `web` / `both`, default `api`) and gates every kind-dependent ask on it. The
declarative records are asked by the goga onboarding engine — in `pybuggy init` and in a native
`goga init -t pybuggy` session alike; every kind-dependent question is asked by pybuggy itself at the amendment
moment, right after the engine survey, branching on the kind answer (a confirm-gated repeated group and
conditional visibility are beyond the declarative engine records). The api and web question sets never cross.
The audience is the integrator wiring pybuggy in, and the consumer's goga agent.

## What is asked

Unconditional records of the declarative block (asked by the engine):

- `kind` — the test kind: a choice of `api`, `web`, or `both` (default `api`); the first record of the block,
  gating every downstream survey.
- `base_image` — the FROM of the always-created Dockerfile. The prompt embeds the goga-python family hints of the
  running goga minor line (`qarium/goga-python-3.10` … `qarium/goga-python-3.14`, each tagged with the minor line);
  the newest member is the default. The pybuggy test runtime is pytest, so the python family serves every pybuggy
  project regardless of the surveyed language.
- `image` — the built-image name. Default `{project}:latest` from the git origin; a required input when no origin
  is configured.

The api branch (kind `api` or `both`), asked by pybuggy at the amendment moment:

- `base_url` — **required**. A Jinja2 template string rendered once before the test run; a plain URL is a valid
  template that renders to itself.
- The optional scalar plugin keys, one input each, skippable with Enter: `timeout`, `retries`, `assert_timeout`,
  `assert_delay`, `assert_field_class`, `assert_response_class`.
- The specs as one flow: the first spec field by field — `name`, `type` (a choice of `swagger` or `openapi`),
  `location`, and the optional git fields `git_url`, `git_location`, `git_ref` (an empty `git_url` means no git
  source) — then `Add another spec?` (confirm, default no) gating the additional specs; each accepted spec is
  asked field by field in the first-spec order (`name` required and re-asked when empty, `type` a swagger/openapi
  choice, `location` required, then the optional git fields); the confirm repeats after every spec until declined.
  A name colliding with an earlier spec keeps the earlier spec and warns. The first spec is validated strictly, so
  at least one spec always lands in the config.
- `autonomous` — **asked last, after the spec survey completed**. One confirm per pipeline, each default no,
  in a fixed order — `api.automate` first, then `api.patch`: each accepted confirm enables that pipeline's
  autonomous runs; a declined confirm leaves that pipeline interactive.

The web branch (kind `web` or `both`), asked by pybuggy at the amendment moment:

- `provider` — the LLM provider: a choice of `openai` or `anthropic` (default `openai`).
- `generation_model` — **required**; re-asked when empty.
- `classification_model` — **required**; re-asked when empty.
- `browser_name` — the browser for web tests; default `chromium`.
- `headless` — whether the browser runs without a visible window; confirm, default yes.

A `both` session asks both branches in order — the api branch first, the web branch after it.

## What is not asked

`headers` and `loader` are never surveyed (api) — the tool config is serialized as plain YAML carrying only the
answered values, and the `pybuggy init` bootstrap then documents the unanswered members as commented example
records in the file itself (uncomment and fill them when needed):

      # headers: example (skipped complex member)   # emitted by the bootstrap
      #   X-Example: value
      #   default request headers dict
      # timeout: (skipped optional scalar)
      # loader: example (skipped complex member)
      #   packages:
      #     - api
      #   modules: []

The remaining web keys are never surveyed either — only the web minimum lands as active keys in `web.yml`, and the
bootstrap documents every absent web key (models' prompts, attempts, polling, screenshots, probe timeout,
`cache_root`, the browser subkeys beyond name/headless) as commented example records in the same style.

## The contribution

The answers never touch the filesystem directly — the amendment hook surveys the kind-gated branches, buffers the
contribution, and the engine commits it. Both tool config files are written by the engine:

- the api tool config file `.goga/tools/pybuggy/api.yml` (kind api or both) — the specs mapping plus the answered
  scalar keys
  (unanswered keys are dropped, never written empty; the bootstrap adds their commented examples afterwards), plus
  the `pipelines` axis entries — one record with `autonomous: true` per accepted confirm (`api.automate`,
  `api.patch`) — the section is absent when every confirm was declined;
- the web tool config file `.goga/tools/pybuggy/web.yml` (kind web or both) — the surveyed minimum as active keys
  (`provider`, `generation_model`, `classification_model`, `browser.name`, `browser.headless`) plus the
  `strict: false` / `interactive: false` defaults; the bootstrap adds the commented examples of the remaining
  keys afterwards;
- the `build.review.skip: true` amendment — the tool's declared intent in the session answer space. The engine's
  config mapper does not carry the flag into the generated `.goga/config.yml`; the `pybuggy init` bootstrap
  enforces it afterwards (`ensure_review_skip`). A native `goga init -t pybuggy` session runs no bootstrap and
  sets no flag — add it by hand or run the bootstrap programmatically;
- the Dockerfile pair amendment — the fixed `.goga/Dockerfile` path plus the answered `base_image` (the engine's
  generator writes the Dockerfile from exactly this pair), and the answered `image` as the built-image name — the
  engine's core docker-image section is skipped, so the file is delivered through the answers, never asked about;
- the `tools` amendment — the record `pybuggy: <installed-major.minor>.x` (a quoted string, e.g. `"2.0.x"` — the
  same x-range the Dockerfile install line pins, a floating patch form; `latest` in a metadata-less run). The
  platform merge
  folds it into whatever the core tools question collected — pybuggy is always recorded in `.goga/config.yml`,
  and a user-typed pybuggy entry is overridden by the installed line.

## Failure and re-run semantics

- An exception raised while building the contribution — including a Ctrl-C at the additional-spec or autonomy
  prompts — drops the whole contribution with a warning naming pybuggy; the session continues and returns 0; the
  pybuggy bootstrap then still delivers its own files.
- An existing `.goga/config.yml` ends the session immediately — no questions, no contribution. Whoever created the
  config first wins: the tool config file is never rewritten by a later session.

## Programmatic usage (tests/scripts)

`parse_specs`, `build_config_data`, `build_web_config_data`, and `build_config_amendments` are pure mappings from
the answer view — test
them directly with dict inputs, no TTY and no filesystem (`specs` is the list of surveyed mappings; `autonomous`
carries the surveyed confirm answers — a mapping of pipeline axis to boolean; `build_config_amendments` reads the
image inputs from the answer view). `pybuggy_questions` is likewise
pure: assert the record shapes and the survey order — exactly the kind, base_image, and image records.
`survey_api_options`, `survey_specs`, `survey_autonomy`, and `survey_web_config` are the TTY routines — stub
`click.prompt`/`click.confirm` of the session module to script
them in tests.

## Preconditions and side effects

- Writes `.goga/tools/pybuggy/api.yml` and — for the web kind — `.goga/tools/pybuggy/web.yml` through the engine
  (the parent directory is created).
- The generated api file is valid for configuration loading: `specs` is present with the required entry fields; the
  scalar plugin keys are ignored on loading (extra=ignore).
- The generated web file carries the surveyed minimum plus the strict/interactive defaults; every key is a
  `WebConfigKeys` member.
- The `pipelines` entries are written only per enabling answer — a declined confirm leaves that axis absent,
  so an onboarded project stays interactive per pipeline until the user opts in.
- The key list is data-driven from `PluginConfigKeys` and `WebConfigKeys` — no duplication.
