# goga_tool_pybuggy.commands.init — the pybuggy tool configuration survey and contribution

## Domain

The onboarding step that collects the pybuggy tool configuration and delivers it as the tool's session contribution:
the file `.goga/tools/pybuggy/config.yml`. The questions are declared by pybuggy and asked by the goga onboarding
engine — in `pybuggy init` and in a native `goga init -t pybuggy` session alike. The audience is the integrator
wiring pybuggy in, and the consumer's goga agent.

## What is asked

- `base_url` — **required**. A Jinja2 template string rendered once before the test run; a plain URL is a valid
  template that renders to itself.
- The optional scalar plugin keys, one input each, skippable with Enter: `timeout`, `retries`, `assert_timeout`,
  `assert_delay`, `assert_field_class`, `assert_response_class`.
- The first spec, field by field: `name`, `type` (a choice of `swagger` or `openapi`), `location`, and the optional
  git fields `git_url`, `git_location`, `git_ref` — an empty `git_url` means no git source.
- `extra_specs` — optional. Additional specs, one per line, in the compact form:

      name|type|location|git_url|git_location|git_ref

  A line carrying fewer than the three required fields (name, type, location) is malformed. A malformed line is
  skipped with a warning — the rest of the contribution is unaffected. A name colliding with the first spec keeps
  the first spec and warns. The first spec is validated strictly, so at least one spec always lands in the config.

## What is not asked

`headers` and `loader` are never surveyed, and the tool config is serialized as plain YAML — the file carries only
the answered values. The two complex sections stay documented as hand-added examples (add them to the file
yourself when needed):

      # headers:                        # optional section, hand-added: mapping of header name to value/template
      #   X-Api-Key: "{{ API_KEY }}"
      # loader:                         # optional section, hand-added: packages/modules structure
      #   packages: [api]

## The contribution

The answers never touch the filesystem directly — the amendment hook buffers the contribution and the engine
commits it:

- the tool config file `.goga/tools/pybuggy/config.yml` — the specs mapping plus the answered scalar keys
  (unanswered keys are dropped, never written empty);
- the `build.review.skip: true` amendment — the tool's declared intent in the session answer space. The engine's
  config mapper does not carry the flag into the generated `.goga/config.yml`; the `pybuggy init` bootstrap
  enforces it afterwards (`ensure_review_skip`). A native `goga init -t pybuggy` session runs no bootstrap and
  sets no flag — add it by hand or run the bootstrap programmatically.

## Failure and re-run semantics

- An exception raised while building the contribution drops the whole contribution with a warning naming pybuggy —
  the session continues and returns 0; the pybuggy bootstrap then still delivers its own files.
- An existing `.goga/config.yml` ends the session immediately — no questions, no contribution. Whoever created the
  config first wins: the tool config file is never rewritten by a later session.

## Programmatic usage (tests/scripts)

`parse_specs`, `build_config_data`, and `build_config_amendments` are pure mappings from the answer view — test
them directly with dict inputs, no TTY and no filesystem. `pybuggy_questions` is likewise pure: assert the record
shapes and the survey order against the `PluginConfigKeys` members.

## Preconditions and side effects

- Writes `.goga/tools/pybuggy/config.yml` through the engine (the parent directory is created).
- The generated file is valid for configuration loading: `specs` is present with the required entry fields; the
  scalar plugin keys are ignored on loading (extra=ignore).
- The key list is data-driven from `PluginConfigKeys` — no duplication.
