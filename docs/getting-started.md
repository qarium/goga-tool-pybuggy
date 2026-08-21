# Getting Started

This walkthrough takes a project from zero to a running API test suite.

## 1. Initialize: `goga tool pybuggy init`

Run in the target project root:

```bash
goga tool pybuggy init
```

The command (see [CLI — init](cli/init.md)):

1. **Interactively initializes the goga project** — creates `.goga/config.yml`
   (language fixed to `python`) and the mandatory `.goga/Dockerfile` with
   `RUN goga install pybuggy -v 1.0.x`. Init runs **offline** — the goga
   "Download base convention" question is never asked.
2. Occupies the `conventions` slot with the pybuggy test convention
   (`.goga/usages/conventions.md`) — this file is package-owned and always overwritten.
3. Sets `build.review_executor.skip: true` in `.goga/config.yml` (idempotent).
4. Registers the usage keys `pybuggy-api` / `pybuggy-asserts` in
   `codemanifest.usages` (idempotent; user-defined keys are never overwritten).
5. **Interactively builds** `.goga/tools/pybuggy/config.yml` — plugin options plus the
   `specs` section (at least one spec is required).
6. Generates the root `conftest.py`:

   ```python
   from dotenv import load_dotenv

   load_dotenv()

   from goga_tool_pybuggy import plugin

   plugin.install()
   ```

Existing files (`.goga/config.yml`, `.goga/tools/pybuggy/config.yml`, `conftest.py`) are
only overwritten after an explicit confirmation (default: **no**).

## 2. Configure specs

`.goga/tools/pybuggy/config.yml` describes where your specifications live (see
[Configuration](configuration.md)):

```yaml
base_url: https://{{ env }}.svc.example/api
timeout: 10.0
data_key: data
error_key: error
specs:
  shop:
    type: openapi
    location: .specs/openapi/shop/shop-openapi.yaml
    git:
      url: https://git.example.com/specs/shop.git
      location: openapi/shop-openapi.yaml
      ref: main
```

`base_url` is a Jinja2 template rendered against `os.environ` + the CLI options you pass
(e.g. `pytest --env=dev`).

## 3. Pull the specs

```bash
goga tool pybuggy endpoint pull               # all specs
goga tool pybuggy endpoint pull --spec shop   # a single spec
PYBUGGY_REF=v2 goga tool pybuggy endpoint pull   # pin every spec to ref v2
```

Each spec with a `git` block is shallow-cloned at the effective ref, and `git.location`
is copied into the local `location` path. Details: [CLI — pull](cli/pull.md).

## 4. Inspect endpoints

```bash
goga tool pybuggy endpoint list                    # id, method and path per spec
goga tool pybuggy endpoint info clients_startup_get   # full endpoint details as JSON
```

## 5. Generate fixtures

```bash
goga tool pybuggy endpoint generate -s shop
```

This scaffolds, per endpoint (see [CLI — generate](cli/generate.md)):

```
api/shop/clients_startup_get/schemas/200.json   # response JSON schemas
api/shop/clients_startup_get/api.py             # endpoint fixture
tests/shop/clients_startup_get/                 # empty test directory
```

## 6. Write the first test

```python
# tests/shop/clients_startup_get/test_clients_startup_get.py
from pydantic import BaseModel


class Request(BaseModel):
    order_id: int


def test_startup(post_clients_startup_get):
    with post_clients_startup_get(json=Request(order_id=1)) as response:
        response.expected.has_status_code(200)
        response.expected("items").has_length(3)
```

The `api` fixture and the generated endpoint fixtures are provided by the plugin —
no manual wiring needed. The auto-check (status → `error_key` absent → `data_key`
present → JSON-schema validation) fires on first access to `response.expected`.

## 7. Run

```bash
pytest                          # run from the project root
pytest --base-url https://staging.example   # override base_url for this run
```

Run pytest from the project root — the directory that contains `api/` and is on
`sys.path`; running elsewhere makes fixture discovery silently return nothing.

Next steps: [HTTP API](api/index.md), [Assertions](api/asserts.md),
[Pytest Plugin](plugin/index.md).
