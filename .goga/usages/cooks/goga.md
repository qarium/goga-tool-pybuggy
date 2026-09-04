# goga — in-process initialization and scaffolding of a goga project (Python API)

## Domain

The `goga` package provides a Python API for interactively initializing a goga project and for scaffolding it from a copier template — the same flows the `goga init` CLI command runs, but in-process. The intended consumers are pybuggy cells that initialize a goga project under the hood (e.g. `goga_tool_pybuggy/commands/init`). The onboarding API is a construction kit: `Questionnaire` asks the config fields one by one; `FileGenerator` writes the files from the collected answers. The scaffolding API (`goga.scaffold.Scaffold`) wraps the copier engine — see the scaffolding contract below.

## The initialization contract

Types from `goga.onboarding`:

- `Questionnaire()` — an interactive questionnaire built on click. No constructor arguments. The class provides per-field methods (one per config field) — pybuggy orchestrates them manually:
  - `ask_language() -> str` — one of python/golang/kotlin/swift/javascript (**pybuggy does NOT call this method — pybuggy hardcodes the language**).
  - `ask_base_convention() -> tuple[dict | None, str | None]` — the pair (usages_prefill, annotations_prefill). **pybuggy does NOT call this method** — the "Download base convention" question is never asked; the `conventions` key never enters the answers (the consumer fills its `conventions` slot with pybuggy's test convention from a package asset, not with a goga download).
  - `ask_codemanifest_usages(prefill: dict | None = None) -> dict | None`.
  - `ask_codemanifest_annotations(prefill: str | None = None) -> str | None`.
  - `ask_agent() -> str | None`.
  - `ask_image(language: str) -> str` — a pre-built Docker image for **PULL (the no-Dockerfile case)**; the suggestion list is limited to `_IMAGE_MAP[language]` (for `python` — `qarium/goga-python-3.10:1.1` … `qarium/goga-python-3.14:1.1`), **the default is the last list entry**; arbitrary input is accepted. **pybuggy does NOT call this method** — a Dockerfile is mandatory.
  - `ask_image_name(language: str) -> str` — **the name (tag) of the image built from the Dockerfile** (top-level `image` field, used by `docker build -t`); free input with placeholder default `{language}-image:latest`. **pybuggy calls this method** — the answer names the built image.
  - `ask_base_image(language: str) -> str` — **the base image for `FROM` in the Dockerfile** (field `dockerfile_base_image`); the suggestion list is limited to `_IMAGE_MAP[language]`, **the default is the last list entry**. **pybuggy calls this method** — the answer provides the Dockerfile baseline; the value is NOT written to `config.yml` (only the `FROM` line uses it).
  - `ask_dockerfile_path() -> str | None` — the path to the Dockerfile (default `.goga/Dockerfile`) or None (skip). **pybuggy does NOT call this method** — a Dockerfile is mandatory; pybuggy hardcodes `dockerfile_path` as `.goga/Dockerfile`.
  - `ask_env(agent: str | None) -> dict | None`.
  - `ask_pipeline_agent() -> str | None` — **takes no arguments**; optional (a confirm-gate; default None — does NOT inherit the build agent).
  - `ask_pipeline_env(pipeline_agent: str | None) -> dict | None`.
  - The orchestrators `ask_goga_config() -> GogaConfigAnswers` and `ask() -> InitAnswers` implement the full universal flow — **pybuggy does NOT use them**, because both call `ask_language`.
- `FileGenerator()` — the project file generator. No constructor arguments.
  - `generate(answers: InitAnswers) -> None` — writes `.goga/config.yml`; when `dockerfile_path` is set, first creates a Dockerfile `FROM {dockerfile_base_image}` (base image), with top-level `image` holding the built image's name; when `codemanifest_usages` contains the key `"conventions"`, downloads the language convention (via requests) into `.goga/usages/conventions.md`. Raises `RuntimeError` on a download failure (config.yml is NOT created).
- `InitLogic(questionnaire, generator).run() -> int` — the "full universal flow" orchestrator; **pybuggy does NOT use it** (it requires `ask_language`). Included only as an error-handling reference: catches `click.Abort`→1, `Exception`→log+echo+1.

Answer containers (frozen dataclasses, `kw_only=True`):

- `GogaConfigAnswers` — fields: `language: str`, `image: str`, `agent: str | None`, `pipeline_agent: str | None`, `pipeline_env: dict | None`, `env: dict | None`, `codemanifest_usages: dict | None`, `codemanifest_annotations: str | None`, `dockerfile_path: str | None`, `dockerfile_base_image: str | None`.
- `InitAnswers` — field `goga_config: GogaConfigAnswers`.

## Generated files (side effects, in cwd)

- `.goga/config.yml` — the full goga config (language, image, dockerfile, build, pipeline, codemanifest).
- `.goga/usages/conventions.md` — downloaded (via requests) **only when the `conventions` key is present in the answers' `codemanifest_usages`**; pybuggy never passes the key (residual: manually entering a `conventions` name in the questionnaire re-triggers the download; on failure — `RuntimeError`, and `config.yml` is not created).
- `Dockerfile` (at `dockerfile_path`) — `FROM {dockerfile_base_image}`; `generate` creates the file when `dockerfile_path` is set (pybuggy always passes it — a Dockerfile is mandatory). Afterwards pybuggy appends `RUN goga install pybuggy -v 1.0.x`.

## Pattern: in-process invocation (per-field assembly)

      from goga.onboarding import FileGenerator, GogaConfigAnswers, InitAnswers, Questionnaire

      questionnaire = Questionnaire()
      generator = FileGenerator()

      language = "python"  # hardcoded — pybuggy is a Python project; ask_language is NOT called

      codemanifest_usages = questionnaire.ask_codemanifest_usages()        # no prefill — pybuggy skips ask_base_convention
      codemanifest_annotations = questionnaire.ask_codemanifest_annotations()
      agent = questionnaire.ask_agent()
      image = questionnaire.ask_image_name(language)        # name of the image built from the Dockerfile (top-level image)
      dockerfile_base_image = questionnaire.ask_base_image(language)  # FROM baseline for the Dockerfile
      dockerfile_path = ".goga/Dockerfile"             # hardcoded — a Dockerfile is mandatory; ask_dockerfile_path is NOT called
      env = questionnaire.ask_env(agent)
      pipeline_agent = questionnaire.ask_pipeline_agent()   # no argument; optional (default None)
      pipeline_env = questionnaire.ask_pipeline_env(pipeline_agent)

      config = GogaConfigAnswers(
          language=language,
          agent=agent,
          image=image,
          dockerfile_base_image=dockerfile_base_image,
          pipeline_agent=pipeline_agent,
          pipeline_env=pipeline_env,
          env=env,
          dockerfile_path=dockerfile_path,
          codemanifest_usages=codemanifest_usages,
          codemanifest_annotations=codemanifest_annotations,
      )

      try:
          generator.generate(InitAnswers(goga_config=config))  # 0 on success
      except click.Abort:
          ...  # user cancellation → return 1
      except Exception:
          ...  # generation failure → log + return 1

## The scaffolding contract

Types from `goga.scaffold`:

- `Scaffold(dst_path: str = ".", answers_file: str = ".goga/scaffold.yml")` — wraps the copier template engine for a single scaffolding target. The goga hard conventions are construction state: `dst_path` (the target directory, cwd by default) and `answers_file` (the copier state file path, passed programmatically to both copier operations and overriding any `answers_file` declared in the template `copier.yml`).
- `Scaffold.generate(template_input: str, ref_override: str | None) -> int` — primary project generation from a copier template. Parses `template_input` via `parse_template_ref` (a git URL, optionally carrying a ref fragment `url.git#ref`; `ref_override` — the `--ref` value — takes precedence over the fragment), resolves the project name via `resolve_scaffold_name()` (the git origin name, falling back to an interactive prompt), and injects **only** `project_name` programmatically; every remaining template question is asked interactively by copier (`defaults=False`; questionary TUI — a TTY is required). Returns 0 on success, 1 on any copier error — the cause is echoed to stderr; exceptions never propagate to the caller.
- `Scaffold.upgrade(ref_override: str | None = None) -> int` — migration of a previously scaffolded project: `copier.run_update` reads the template source and answers from the state file (`defaults=True` — the survey is bypassed; `overwrite=True` — required by copier). `ref_override` optionally overrides the migration target ref. Returns 1 when the state file is missing; copier preconditions surface as a nonzero exit (the destination must be a git repository, clean of uncommitted changes; the template must be git-trackable — a git URL; the version must not decrease).

Both operations own their error handling — pybuggy receives only the exit code and never wraps copier exceptions.

## Scaffold side effects

- `generate` renders the template files into `dst_path`. The template is any copier-compatible project — pybuggy imposes no constraints on its content and injects no answers beyond `project_name`.
- The state file is persisted **by the template itself** (the answers-file entry — the copier `{{ _copier_conf.answers_file }}.jinja` convention); a template without such an entry leaves no state file, and `upgrade` then reports it missing.
- The state file must NOT be git-ignored in a scaffolded project — migration depends on it.
- `upgrade` rewrites files in `dst_path` according to the newer template version.

## Pattern: scaffolding invocation (pybuggy init)

      from goga.scaffold import Scaffold

      scaffold = Scaffold()  # defaults: cwd target, .goga/scaffold.yml state file

      # template mode: generate first; a nonzero code stops the command before onboarding
      exit_code = scaffold.generate(tpl, ref)
      if exit_code != 0:
          ...  # propagate the code; no onboarding runs

      # upgrade mode: migration only — no onboarding
      exit_code = scaffold.upgrade(ref)

## Notes for the calling side

- The API is **interactive** (TTY prompts via click). In tests, the caller substitutes the call site (monkeypatch) so that the prompts never appear — tests never construct real `Questionnaire()`/`FileGenerator()` instances (TTY/network; mocks only).
- `Scaffold.generate` is likewise **interactive** (copier questionary TUI; a TTY is required when template questions lack programmatic answers). In tests the calling side stubs `Scaffold` (monkeypatch) — no real copier runs, no network, no TTY.
- The flow returns **a number and never raises an exception** on cancellation/failure (`click.Abort`→1, any other `Exception`→log+echo+1 — parity with the old `InitLogic.run()`); the caller prints the diagnostics itself.
- `InitLogic`/`ask`/`ask_goga_config` **are not used** — manual per-field orchestration pins `language="python"` and splits the image into the built image's name (`ask_image_name`) and the `FROM` baseline (`ask_base_image`); `ask_image` (pre-built pull, no Dockerfile) **is never called** — a Dockerfile is mandatory.
- pybuggy-driven initialization stays offline: the `conventions` key never enters the answers; the flow makes no network calls.
- This is an external package — reference it in CODEMANIFEST via `Usages`, **not** via `Imports` (Imports binds only project cells); place the absolute import at the top of the module, isort third-party group.

## Dependencies

- The calling package's `pyproject.toml` must list `goga` among its dependencies. `goga.scaffold` ships in the same package.
- In dev, `goga` resolves from `.libs/goga` via a symlink into `site-packages` (dev snapshot newer than 1.1.2, no version metadata); **do NOT run `uv sync`** — it would recreate the dependencies and bring back an outdated resolver.
