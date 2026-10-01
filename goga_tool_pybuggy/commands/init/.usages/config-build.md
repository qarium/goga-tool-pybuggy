# goga_tool_pybuggy.commands.init — the pybuggy tool configuration survey and contribution

## Domain

The onboarding step that collects the pybuggy tool configuration and delivers it as the tool's session contribution:
the file `.goga/tools/pybuggy/config.yml`. The questions are declared by pybuggy and asked by the goga onboarding
engine — in `pybuggy init` and in a native `goga init -t pybuggy` session alike. Two follow-ups are the exception:
the additional specs (a confirm-gated repeated group is beyond the declarative engine records) and the autonomy
confirm (it must close the survey after the specs, never interleave them) — pybuggy asks both itself at the
amendment moment, right after the engine survey, specs first and autonomy last. The audience is the integrator
wiring pybuggy in, and the consumer's goga agent.

## What is asked

- `base_image` — the FROM of the always-created Dockerfile. The prompt embeds the goga-python family hints of the
  running goga minor line (`qarium/goga-python-3.10` … `qarium/goga-python-3.14`, each tagged with the minor line);
  the newest member is the default. The pybuggy test runtime is pytest, so the python family serves every pybuggy
  project regardless of the surveyed language.
- `image` — the built-image name. Default `{project}:latest` from the git origin; a required input when no origin
  is configured.
- `base_url` — **required**. A Jinja2 template string rendered once before the test run; a plain URL is a valid
  template that renders to itself.
- The optional scalar plugin keys, one input each, skippable with Enter: `timeout`, `retries`, `assert_timeout`,
  `assert_delay`, `assert_field_class`, `assert_response_class`.
- The first spec, field by field: `name`, `type` (a choice of `swagger` or `openapi`), `location`, and the optional
  git fields `git_url`, `git_location`, `git_ref` — an empty `git_url` means no git source.
- The additional specs, asked by pybuggy at the amendment moment: `Add another spec?` (confirm, default no) gates
  the block; each accepted spec is asked field by field in the first-spec order (`name` required and re-asked when
  empty, `type` a swagger/openapi choice, `location` required, then the optional git fields); the confirm repeats
  after every spec until declined. A name colliding with an earlier spec keeps the earlier spec and warns. The
  first spec is validated strictly, so at least one spec always lands in the config.
- `autonomous` — **asked last, after the spec survey completed**. A confirm (default no): enable the autonomous
  runs of the `api.automate` pipeline.

## What is not asked

`headers` and `loader` are never surveyed — the tool config is serialized as plain YAML carrying only the answered
values, and the `pybuggy init` bootstrap then documents the unanswered members as commented example records in the
file itself (uncomment and fill them when needed):

      # headers: example (skipped complex member)   # emitted by the bootstrap
      #   X-Example: value
      #   default request headers dict
      # timeout: (skipped optional scalar)
      # loader: example (skipped complex member)
      #   packages:
      #     - api
      #   modules: []

## The contribution

The answers never touch the filesystem directly — the amendment hook surveys the additional specs and the autonomy
confirm, buffers the contribution, and the engine commits it:

- the tool config file `.goga/tools/pybuggy/config.yml` — the specs mapping plus the answered scalar keys
  (unanswered keys are dropped, never written empty; the bootstrap adds their commented examples afterwards), plus
  the `pipelines` axis entry — the `api.automate` record with `autonomous: true` — when the autonomy confirm was
  enabled; absent otherwise;
- the `build.review.skip: true` amendment — the tool's declared intent in the session answer space. The engine's
  config mapper does not carry the flag into the generated `.goga/config.yml`; the `pybuggy init` bootstrap
  enforces it afterwards (`ensure_review_skip`). A native `goga init -t pybuggy` session runs no bootstrap and
  sets no flag — add it by hand or run the bootstrap programmatically;
- the Dockerfile pair amendment — the fixed `.goga/Dockerfile` path plus the answered `base_image` (the engine's
  generator writes the Dockerfile from exactly this pair), and the answered `image` as the built-image name — the
  engine's core docker-image section is skipped, so the file is delivered through the answers, never asked about;
- the `tools` amendment — the record `pybuggy: <installed-minor>.x` (the same minor x-range the Dockerfile install
  line pins; `latest` in a metadata-less run). The platform merge folds it into whatever the core tools question
  collected — pybuggy is always recorded in `.goga/config.yml`, and a user-typed pybuggy entry is overridden by
  the installed line.

## Failure and re-run semantics

- An exception raised while building the contribution — including a Ctrl-C at the additional-spec or autonomy
  prompts — drops the whole contribution with a warning naming pybuggy; the session continues and returns 0; the
  pybuggy bootstrap then still delivers its own files.
- An existing `.goga/config.yml` ends the session immediately — no questions, no contribution. Whoever created the
  config first wins: the tool config file is never rewritten by a later session.

## Programmatic usage (tests/scripts)

`parse_specs`, `build_config_data`, and `build_config_amendments` are pure mappings from the answer view — test
them directly with dict inputs, no TTY and no filesystem (`extra_specs` is the list of surveyed mappings, or None
for a declined gate; `autonomous` carries the surveyed confirm answer; `build_config_amendments` reads the image
inputs from the answer view). `pybuggy_questions` is likewise pure: assert the record shapes and the survey order
against the `PluginConfigKeys` members. `survey_extra_specs` and `survey_autonomy` are the TTY routines — stub
`click.prompt`/`click.confirm` of the session module to script them in tests.

## Preconditions and side effects

- Writes `.goga/tools/pybuggy/config.yml` through the engine (the parent directory is created).
- The generated file is valid for configuration loading: `specs` is present with the required entry fields; the
  scalar plugin keys are ignored on loading (extra=ignore).
- The `pipelines` axis entry is written only on an enabling answer — the disabling default leaves the axis absent,
  so an onboarded project stays interactive until the user opts in.
- The key list is data-driven from `PluginConfigKeys` — no duplication.
