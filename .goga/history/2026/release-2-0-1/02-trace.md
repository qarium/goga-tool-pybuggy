# Trace Report

## Call Flow

- `init`: `run_session` → session answers → `_first_spec_entry(spec_answers)` / `_extra_spec_entry(spec)` → `parse_specs` → `build_config_data` → `data["specs"][name] = SpecEntry.model_dump()` → written verbatim to `.goga/tools/pybuggy/config.yml`. Name is used raw (`str(name)`; extras only `.strip()`).
- `generate`: `generate_cmd` → `run_generate(spec_name, force, endpoint_ids)` → `load_config()` [config] → select `config.specs` (keyed by raw name) → per spec: `load_spec(cwd / entry.location)` [spec] → `extract_endpoints` → collision check (`_safe_identifier(endpoint.id)`) → `_write_artifacts(to_generate, force, cwd)`:
  - `safe_id = _safe_identifier(endpoint.id)` (generate.py:394)
  - `endpoint_dir = cwd / "api" / name / safe_id` (generate.py:395) — **raw `name`**
  - `test_dir = cwd / "tests" / name / safe_id` (generate.py:399) — **raw `name`**
  - `_write_package_markers(endpoint_dir, cwd / "api", force)` → `__init__.py` in `api/`, `api/<name>/`, `api/<name>/<id>/`
- `diff`: `diff_cmd` → `run_diff(spec_name, endpoint_ids)` → `load_config()` → per spec: parse + extract → `api_spec_dir = cwd / "api" / name` (diff.py:118) — **raw `name`** → `endpoint_dir = api_spec_dir / sanitize_id(endpoint.id)` → `artifact_contract` / `spec_contract` / `orphan_artifact_dirs`.
- `list`: `list_cmd` → `run_list(spec_name, with_status)` → `load_config()` → per spec: `endpoint_statuses(cwd / "api" / name, endpoints)` (list.py:128) — **raw `name`**; `endpoint_statuses` imports `sanitize_id`/`artifact_contract`/`orphan_artifact_dirs`/`spec_contract` from `commands/diff` (list.py:13).
- `pull`: destination = `Path.cwd() / entry.location` (pull.py:79) — name-independent; name only echoed.

## Data Flow

Spec name (user answer in init) → config.yml `specs:` dict key → `load_config()` → `Config.specs: dict[str, SpecEntry]` → three consumers derive the artifact-tree segment `api/<name>`: generate (write), diff (read), list (status read). Endpoint-level segment is sanitized (`_safe_identifier` in generate, `sanitize_id` in diff — same rule: non-word → `_`, leading digit → `_` prefix); spec-level segment is NOT sanitized anywhere. The plugin cell later imports every generated `api/<spec>/<id>/api.py` via recursive `pytest_plugins` discovery (plugin/.usages/enable.md) — a hyphenated segment is not a valid Python identifier, so the dotted import path `api.<spec>.<id>` cannot resolve.

## Manifest Algorithm Mapping

| CODEMANIFEST step | Code path | Match |
|---|---|---|
| generate 7.1 sanitize endpoint id → importable segment | generate.py:394 `_safe_identifier(endpoint.id)` | matches |
| generate 7.2 create `cwd/api/<name>/<sanitized id>` and `cwd/tests/<name>/<sanitized id>` | generate.py:395,399 — `<name>` raw | **mismatch with the importability intent** (see Inconsistencies) |
| generate req: "Every directory on the api.py path … carries an empty `__init__.py` so the generated fixture modules form an importable package" | generate.py:404 markers written, but `api/<name>` with a hyphen is not a package name | **violated for non-identifier names** |
| generate req: "a module is always importable under the dotted path it is written to" | holds per-endpoint, broken at the spec segment | **violated for non-identifier names** |
| diff 7: `api_spec_dir` from spec name; locate endpoint dir by `sanitize_id` | diff.py:118,121 | matches code; shares the raw-name assumption |
| list: status mode reads `api/<name>/` tree | list.py:128 | matches code; shares the raw-name assumption |
| diff `sanitize_id`: "segment rule equals the artifact-directory naming rule" | artifacts.py:27-35, mirrors generate.py:45 `_safe_identifier` | matches (rule duplicated in two cells by design) |

## Cross-Cell Traversals

| Source Cell | Target Cell | Type | Path |
|---|---|---|---|
| commands/generate | config | data/call | `load_config()` → `Config.specs` name keys |
| commands/generate | spec | data/call | `load_spec` / `extract_endpoints` / `Endpoint.id` |
| commands/diff | config | data/call | `load_config()` → name keys |
| commands/diff | spec | data/call | `load_spec` / `extract_endpoints` / `build_endpoint_id` |
| commands/list | commands/diff | call | `sanitize_id`, `artifact_contract`, `orphan_artifact_dirs`, `spec_contract` (list.py:13) |
| commands/list | config, spec, output | data/call | `load_config`, `extract_endpoints`, `render_*` |
| plugin | (generated tree) | usage | recursive `pytest_plugins` discovery of `api/<spec>/<id>/api.py` |
| commands/init | config | data | `parse_specs` → `SpecEntry` name keys written to config.yml |

## Inconsistencies

| Type | Location | Expected | Actual |
|---|---|---|---|
| Manifest-vs-intent | generate CODEMANIFEST steps 7.2–7.6 + requirements | importable package on the whole api.py path | `<name>` segment used raw; hyphenated names produce non-importable `api/some-spec/` despite `__init__.py` markers |
| Code-vs-code | generate.py:395/399 vs diff.py:118 vs list.py:128 | one shared naming rule for the spec segment | all three derive the segment independently from the raw name (consistent today only because all use it raw) |
| Doc-vs-behavior | generate.md/diff.md/list.md | document the artifact tree layout | `<spec>`/`<name>` documented without a sanitization rule for the spec segment (only `<endpoint.dir>` has one) |
| Missing guard | generate step 6.5 analog | spec-name segments that collide after sanitization (`some-spec` vs `some_spec`) rejected before writes | no check; a fix without it would silently mix two specs' artifacts in one directory |

## Trace Graph

```
init answers ──(raw name)──► config.yml specs:<name>
                                     │ load_config()
                                     ▼
                          Config.specs{<name>: SpecEntry}
                     ┌───────────────┼────────────────┐
                     ▼               ▼                ▼
              run_generate      run_diff         run_list
              api/<name>/…      api/<name>       api/<name>
              tests/<name>/…    (sanitize_id     (sanitize_id,
                 │               per endpoint)     artifact_contract …)
                 ▼
        plugin pytest_plugins discovery ──► import api.<name>.<id>.api
                                              ▲
                            hyphen in <name> ──┘ IMPORT FAILS (defect)
```
