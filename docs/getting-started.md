# Getting Started

Three steps take a project from zero to an automated API-test lifecycle:

```bash
goga install pybuggy                 # 1. install
goga tool pybuggy init               # 2. initialize
goga pipeline pybuggy:api.automate   # 3. run the pipeline
```

## 1. Install: `goga install pybuggy`

Installs the pybuggy package into the **goga**(<https://github.com/qarium/goga>)
environment of the target project.

## 2. Initialize: `goga tool pybuggy init`

Run in the target project root:

```bash
goga tool pybuggy init
```

The command (see [CLI — init](cli/init.md)):

1. Interactively initializes the goga project — creates `.goga/config.yml`
   (language fixed to `python`) and the mandatory `.goga/Dockerfile` with
   `RUN goga install pybuggy -v 1.0.x`.
2. Delivers the `conventions` slot — creates `.goga/usages/conventions.md` with the
   pybuggy test convention when the file is absent; an existing file is left untouched.
3. Sets `build.review_executor.skip: true` in `.goga/config.yml` (idempotent).
4. Registers the usage keys `pybuggy-api` / `pybuggy-asserts` in
   `codemanifest.usages` (idempotent; user-defined keys are never overwritten).
5. Interactively builds `.goga/tools/pybuggy/config.yml` — plugin options plus the
   `specs` section (at least one spec is required):
    ```yaml
    base_url: https://{{ env }}.svc.example/api
    timeout: 10.0
    specs:
      shop:
        type: openapi
        location: .specs/openapi/shop/shop-openapi.yaml
        git:
          url: https://git.example.com/specs/shop.git
          location: openapi/shop-openapi.yaml
          ref: main
    ```
   `base_url` is a Jinja2 template rendered against `os.environ` + the CLI options you pass (e.g. `pytest --env=dev`).
   See [Configuration](configuration.md).

6. Generates the root `conftest.py`:
   ```python
   from dotenv import load_dotenv

   load_dotenv()

   from goga_tool_pybuggy import plugin

   plugin.install()
   ```
This is the **bare** flow: it runs in a fresh project. A repeated invocation (an existing
`.goga/`) is refused — `Project already initialized`, exit code 1, nothing updated — the
same guard `goga init` applies. The command also scaffolds a project from a
copier-compatible template (`init <tpl> [--ref <git-ref>]`) and upgrades a scaffolded
project (`init --upgrade`) — see [CLI — init](cli/init.md).

## 3. Run the pipeline: `goga pipeline pybuggy:api.automate`

```bash
goga pipeline pybuggy:api.automate
```

This is the primary way to create tests with pybuggy. The pipeline:

- asks for the **topic under test** and collects detailed requirements from your
  description and the service spec;
- walks the whole chain — requirements → test cases → test cells → test code → review →
  acceptance — involving you at every communication stage;
- scaffolds the `api/` fixtures and materializes the tests into `tests/<spec>/<id>/`;
- commits nothing without your confirmation; failures found at acceptance are triaged
  with you and recorded in `docs/bugs/<topic>.md`.

Run the resulting suite with:

```bash
pytest
```

The full stage list and the artifact chain: [Pipelines](pipelines/api-automate.md).
