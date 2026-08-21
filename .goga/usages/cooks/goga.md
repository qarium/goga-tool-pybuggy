# goga — in-process initialization of a goga project (Python API)

## Domain

The `goga` package provides a Python API for interactively initializing a goga project — the same flow the `goga init` CLI command runs, but in-process. The intended consumers are pybuggy cells that initialize a goga project under the hood (e.g. `goga_tool_pybuggy/commands/init`). The API is a construction kit: `Questionnaire` asks the config fields one by one; `FileGenerator` writes the files from the collected answers.

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

## Notes for the calling side

- The API is **interactive** (TTY prompts via click). In tests, the caller substitutes the call site (monkeypatch) so that the prompts never appear — tests never construct real `Questionnaire()`/`FileGenerator()` instances (TTY/network; mocks only).
- The flow returns **a number and never raises an exception** on cancellation/failure (`click.Abort`→1, any other `Exception`→log+echo+1 — parity with the old `InitLogic.run()`); the caller prints the diagnostics itself.
- `InitLogic`/`ask`/`ask_goga_config` **are not used** — manual per-field orchestration pins `language="python"` and splits the image into the built image's name (`ask_image_name`) and the `FROM` baseline (`ask_base_image`); `ask_image` (pre-built pull, no Dockerfile) **is never called** — a Dockerfile is mandatory.
- pybuggy-driven initialization stays offline: the `conventions` key never enters the answers; the flow makes no network calls.
- This is an external package — reference it in CODEMANIFEST via `Usages`, **not** via `Imports` (Imports binds only project cells); place the absolute import at the top of the module, isort third-party group.

## Dependencies

- The calling package's `pyproject.toml` must list `goga` among its dependencies.
- In dev, `goga` resolves from `.libs/goga` via a symlink into `site-packages` (dev snapshot newer than 1.1.2, no version metadata); **do NOT run `uv sync`** — it would recreate the dependencies and bring back an outdated resolver.
