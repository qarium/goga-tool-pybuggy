"""Contract and logic tests for run_generate / generate_cmd handler."""

import json
from pathlib import Path

import click
import pytest
from goga_tool_pybuggy.commands.generate import generate_cmd, render_api_module, run_generate
from goga_tool_pybuggy.plugin.loaders.loaders import _module_is_pytest_plugin
from goga_tool_pybuggy.spec import Endpoint

CONFIG_PATH_ATTR = "goga_tool_pybuggy.config.storage.CONFIG_PATH"

# Shared OpenAPI fragments ---------------------------------------------------

_OPENAPI_PREFIX = """\
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
"""


def _write_spec(spec_dir: Path, filename: str, body: str) -> None:
    """Write a YAML spec file under ``spec_dir`` prefixed with minimal OpenAPI header."""
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / filename).write_text(_OPENAPI_PREFIX + body)


def _write_config(tmp_path: Path, specs: dict) -> Path:
    """Write a config.yml whose ``specs`` map mirrors ``specs`` (name -> location)."""
    config_path = tmp_path / "config.yml"
    if not specs:
        config_path.write_text("specs: {}\n")
        return config_path

    lines = ["specs:"]
    for name, location in specs.items():
        lines.append(f"  {name}:")
        lines.append("    type: openapi")
        lines.append(f"    location: {location}")
    config_path.write_text("\n".join(lines) + "\n")
    return config_path


# Contract tests -------------------------------------------------------------


def test_run_generate_importable_and_signature() -> None:
    """run_generate should be importable with signature (spec_name, force, endpoint_ids) and no ctx."""
    params = run_generate.__code__.co_varnames[: run_generate.__code__.co_argcount]

    assert {"spec_name", "force", "endpoint_ids"} <= set(params)
    assert "ctx" not in params


def test_render_api_module_importable_and_signature() -> None:
    """render_api_module should be importable from the cell facade with a single (endpoint) arg returning str."""
    assert render_api_module.__code__.co_argcount == 1
    assert render_api_module.__code__.co_varnames[:1] == ("endpoint",)
    assert render_api_module.__annotations__["return"] is str


def test_generate_cmd_is_click_command() -> None:
    """generate_cmd is a Click command 'generate' with spec/force options and a variadic endpoint-ids argument."""
    assert generate_cmd.name == "generate"

    param_names = {p.name for p in generate_cmd.params}
    assert {"spec_name", "force", "endpoint_ids"} <= param_names
    assert "ctx" not in param_names

    all_opts = {opt for p in generate_cmd.params for opt in p.opts}
    assert "--spec" in all_opts
    assert "--force" in all_opts

    # The endpoint-id filter is a variadic positional argument (nargs=-1)
    endpoint_arg = next(p for p in generate_cmd.params if p.name == "endpoint_ids")
    assert isinstance(endpoint_arg, click.Argument)
    assert endpoint_arg.nargs == -1


def test_generate_cmd_force_help_names_full_artifact_set() -> None:
    """The -f/--force help text should name every regenerable artifact."""
    force_opt = next(p for p in generate_cmd.params if p.name == "force")
    assert isinstance(force_opt, click.Option)

    for artifact in ("schema", "meta.json", "api.py", "__init__.py"):
        assert artifact in force_opt.help


def test_apply_ruff_maps_subprocess_failure_to_click_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing ruff invocation must surface as click.ClickException, not a raw traceback."""
    import subprocess as subprocess_module

    from goga_tool_pybuggy.commands.generate.generate import _apply_ruff

    def failing_run(*args, **kwargs):
        raise subprocess_module.CalledProcessError(returncode=2, cmd=["ruff", "format"], stderr="ruff: syntax error")

    monkeypatch.setattr("goga_tool_pybuggy.commands.generate.generate._find_ruff", lambda: "ruff")
    monkeypatch.setattr(subprocess_module, "run", failing_run)

    with pytest.raises(click.ClickException, match="ruff failed"):
        _apply_ruff("not valid python source at all {{{")


# Logic tests ----------------------------------------------------------------


def test_run_generate_writes_response_schemas_and_tests_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should write response schema files and an empty tests directory."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      description: Start a client
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
        '404':
          description: Not found
          content:
            application/json:
              schema:
                type: object
                properties:
                  error:
                    type: string
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    schema_dir = tmp_path / "api" / "shop" / "clients_startup_get" / "schemas"
    file_200 = schema_dir / "200.json"
    file_404 = schema_dir / "404.json"
    assert file_200.exists()
    assert file_404.exists()

    assert json.loads(file_200.read_text()) == {
        "type": "object",
        "properties": {"id": {"type": "string"}},
    }
    assert json.loads(file_404.read_text()) == {
        "type": "object",
        "properties": {"error": {"type": "string"}},
    }

    test_dir = tmp_path / "tests" / "shop" / "clients_startup_get"
    assert test_dir.is_dir()
    assert not any(test_dir.iterdir())


def test_run_generate_rewrites_openapi_nullable_to_jsonschema_union(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_generate should store OpenAPI nullable: true as a JSON-Schema union type.

    Normalization happens in ``extract_endpoints`` (the OpenAPI → JSON-Schema
    boundary); ``run_generate`` writes that already-normalized schema, so the jsonschema
    validator at runtime accepts ``null``. This pins the end-to-end contract: an
    OpenAPI spec with ``nullable`` produces a JSON-Schema file with union types and
    no ``nullable`` key (recursing into array items).
    """
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      description: Start a client
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      type: object
                      nullable: true
                  error:
                    type: object
                    nullable: true
                  tag:
                    type: string
                    nullable: true
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    schema_file = tmp_path / "api" / "shop" / "clients_startup_get" / "schemas" / "200.json"
    assert schema_file.exists()
    assert json.loads(schema_file.read_text()) == {
        "type": "object",
        "properties": {
            "data": {
                "type": "array",
                "items": {"type": ["object", "null"]},
            },
            "error": {"type": ["object", "null"]},
            "tag": {"type": ["string", "null"]},
        },
    }


def test_run_generate_writes_empty_schema_for_non_json_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should write an empty {} schema for a response code without application/json."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      description: Start a client
      responses:
        '204':
          description: No content
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    schema_file = tmp_path / "api" / "shop" / "clients_startup_get" / "schemas" / "204.json"
    assert schema_file.exists()
    assert schema_file.read_text() == "{}"


def test_run_generate_filters_single_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should only scaffold the requested spec when spec_name is set."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    _write_spec(
        tmp_path / ".specs",
        "server.yaml",
        """\
paths:
  /health:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    config_path = _write_config(
        tmp_path,
        {"shop": ".specs/shop.yaml", "server": ".specs/server.yaml"},
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate("shop", False)

    assert (tmp_path / "api" / "shop").exists()
    assert not (tmp_path / "api" / "server").exists()


def test_run_generate_force_overwrites_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate with force should overwrite a stale existing schema file."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    schema_file = tmp_path / "api" / "shop" / "clients_startup_get" / "schemas" / "200.json"
    expected = schema_file.read_text()
    # Corrupt the file
    schema_file.write_text("STALE CONTENT")

    run_generate(None, True)

    assert schema_file.read_text() == expected


def test_run_generate_raises_when_spec_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should raise ClickException when spec_name is not in config."""
    monkeypatch.chdir(tmp_path)

    config_path = _write_config(tmp_path, {})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException) as exc:
        run_generate("missing", False)
    assert "spec not found: missing" in str(exc.value)


def test_run_generate_raises_when_spec_has_no_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should raise ClickException when a spec has no paths."""
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".specs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".specs" / "shop.yaml").write_text(_OPENAPI_PREFIX)
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException) as exc:
        run_generate(None, False)
    assert "spec has no paths" in str(exc.value)


def test_run_generate_non_mapping_spec_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty spec file parses to None — the guard must not crash before classifying."""
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".specs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".specs" / "shop.yaml").write_text("")
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException) as exc:
        run_generate(None, False)
    assert "spec has no paths" in str(exc.value)


def test_run_generate_illegal_response_key_raises_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A response key carrying path content must not become an artifact filename."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      responses:
        '../../evil':
          description: d
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException) as exc:
        run_generate(None, False)
    assert "invalid response status key" in str(exc.value)
    # Validation happens in phase 1 — nothing may be on disk
    assert not (tmp_path / "api").exists()


def test_run_generate_versionless_spec_raises_click_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A spec declaring no version key maps the extract ValueError to ClickException."""
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".specs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".specs" / "shop.yaml").write_text("paths:\n  /a:\n    get: {}\n")
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException) as exc:
        run_generate(None, False)
    assert "invalid spec file" in str(exc.value)


def test_run_generate_skips_spec_silently_when_no_endpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """run_generate should silently skip a spec with no endpoints and create no artifacts."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    parameters:
      - name: verbose
        in: query
        schema:
          type: boolean
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with caplog.at_level("WARNING"):
        run_generate(None, False)

    assert not any("no endpoints" in rec.message for rec in caplog.records)
    assert not (tmp_path / "api").exists()
    assert not (tmp_path / "tests").exists()


def test_run_generate_idempotent_skips_existing_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture
) -> None:
    """run_generate should not overwrite existing files (and stay silent) without force."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    schema_file = tmp_path / "api" / "shop" / "clients_startup_get" / "schemas" / "200.json"
    assert schema_file.exists()
    schema_file.write_text("STALE CONTENT")

    run_generate(None, False)

    # File preserved as stale (no overwrite), no skip output emitted
    assert schema_file.read_text() == "STALE CONTENT"
    captured = capfd.readouterr()
    assert "skip" not in captured.out.lower()
    assert "skip" not in captured.err.lower()

    # Directory tree stays in place
    assert schema_file.parent.is_dir()
    assert (tmp_path / "tests" / "shop" / "clients_startup_get").is_dir()


def test_run_generate_creates_dirs_for_endpoint_without_responses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_generate should create schema/test dirs even when an endpoint has no responses."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "t.yaml",
        """\
paths:
  /health:
    get:
      description: Health check
""",
    )
    config_path = _write_config(tmp_path, {"t": ".specs/t.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    schemas_dir = tmp_path / "api" / "t" / "health_get" / "schemas"
    test_dir = tmp_path / "tests" / "t" / "health_get"
    assert schemas_dir.is_dir()
    assert test_dir.is_dir()
    assert not any(schemas_dir.glob("*.json"))


def test_run_generate_writes_api_py_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should write the per-endpoint api.py fixture module with the Request body."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/calls/{orderID}/status:
    post:
      description: Update call status
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                note:
                  type: string
              required:
                - note
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    api_file = tmp_path / "api" / "shop" / "clients_calls_orderid_status_post" / "api.py"
    assert api_file.exists()

    text = api_file.read_text()
    assert "def post_clients_calls_orderid_status(api: Api) -> Endpoint:" in text
    assert "class Request(BaseModel):" in text
    assert "    note: str" in text
    assert 'return Endpoint(api, "/clients/calls/:orderID/status", method="POST")' in text


def test_run_generate_force_overwrites_existing_api_py(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate with force should overwrite a stale existing api.py file."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/calls/{orderID}/status:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                note:
                  type: string
              required:
                - note
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    api_file = tmp_path / "api" / "shop" / "clients_calls_orderid_status_post" / "api.py"
    assert api_file.exists()
    expected = api_file.read_text()
    # Corrupt the file
    api_file.write_text("STALE")

    run_generate(None, True)

    text = api_file.read_text()
    assert text == expected
    assert "def post_clients_calls_orderid_status(api: Api) -> Endpoint:" in text


def test_run_generate_idempotent_skips_existing_api_py_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture
) -> None:
    """run_generate should preserve an existing api.py (and stay silent) without force."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/calls/{orderID}/status:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                note:
                  type: string
              required:
                - note
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    api_file = tmp_path / "api" / "shop" / "clients_calls_orderid_status_post" / "api.py"
    assert api_file.exists()
    api_file.write_text("STALE")

    run_generate(None, False)

    # File preserved as stale (no overwrite), no skip output emitted
    assert api_file.read_text() == "STALE"
    captured = capfd.readouterr()
    assert "skip" not in captured.out.lower()
    assert "skip" not in captured.err.lower()


def test_run_generate_writes_api_py_for_endpoint_without_responses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_generate should write api.py even for an endpoint with no responses or body."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "t.yaml",
        """\
paths:
  /health:
    get:
      description: Health check
""",
    )
    config_path = _write_config(tmp_path, {"t": ".specs/t.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    api_file = tmp_path / "api" / "t" / "health_get" / "api.py"
    schemas_dir = tmp_path / "api" / "t" / "health_get" / "schemas"
    test_dir = tmp_path / "tests" / "t" / "health_get"
    assert api_file.exists()
    assert not any(schemas_dir.glob("*.json"))
    assert test_dir.is_dir()


def test_run_generate_writes_empty_init_markers_on_api_py_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should write an empty __init__.py in every directory on the api.py path."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "t.yaml",
        """\
paths:
  /health:
    get:
      description: Health check
""",
    )
    config_path = _write_config(tmp_path, {"t": ".specs/t.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    # Every directory on the api.py path carries an empty __init__.py
    for init_file in (
        tmp_path / "api" / "__init__.py",
        tmp_path / "api" / "t" / "__init__.py",
        tmp_path / "api" / "t" / "health_get" / "__init__.py",
    ):
        assert init_file.exists()
        assert init_file.read_text() == ""

    # Scope boundary: markers are written only on the api.py path, never on the tests/ path
    assert not (tmp_path / "tests" / "__init__.py").exists()
    assert not (tmp_path / "tests" / "t" / "__init__.py").exists()
    assert not (tmp_path / "tests" / "t" / "health_get" / "__init__.py").exists()


# meta.json input-contract tests ---------------------------------------------


def _startup_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str = "shop") -> Path:
    """Write a config + spec with a single GET /clients/startup endpoint (no request body)."""
    monkeypatch.chdir(tmp_path)
    _write_spec(
        tmp_path / ".specs",
        f"{name}.yaml",
        """\
paths:
  /clients/startup:
    get:
      description: Start a client
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
""",
    )
    config_path = _write_config(tmp_path, {name: f".specs/{name}.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)
    return tmp_path / "api" / name / "clients_startup_get"


def test_run_generate_writes_meta_json_exact_keys_and_pretty_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """meta.json must hold exactly parameters/request_body/vars in that order, prettified."""
    endpoint_dir = _startup_spec(tmp_path, monkeypatch)

    run_generate(None, False)

    meta_file = endpoint_dir / "meta.json"
    assert meta_file.exists()
    meta = json.loads(meta_file.read_text())
    assert list(meta.keys()) == ["parameters", "request_body", "vars"]
    assert meta_file.read_text() == '{\n  "parameters": {},\n  "request_body": {},\n  "vars": {}\n}'


def test_run_generate_meta_json_from_query_path_and_body(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """meta.json keys must map to their Endpoint sources: parameters←query, request_body←body, vars←path."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/{id}:
    put:
      description: Update a client
      parameters:
        - name: verbose
          in: query
          schema:
            type: boolean
        - name: id
          in: path
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
      responses:
        '200':
          description: Success
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    meta_file = tmp_path / "api" / "shop" / "clients_id_put" / "meta.json"
    assert meta_file.exists()
    assert json.loads(meta_file.read_text()) == {
        "parameters": {"verbose": {"type": "boolean"}},
        "request_body": {"type": "object", "properties": {"name": {"type": "string"}}},
        "vars": {"id": {"type": "string"}},
    }


def test_run_generate_meta_json_overwritten_with_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With force a stale meta.json must be replaced by the freshly generated one."""
    endpoint_dir = _startup_spec(tmp_path, monkeypatch)
    run_generate(None, False)

    meta_file = endpoint_dir / "meta.json"
    meta_file.write_text('{"parameters": "stale"}')

    run_generate(None, True)

    assert json.loads(meta_file.read_text()) == {"parameters": {}, "request_body": {}, "vars": {}}


def test_run_generate_meta_json_skipped_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture
) -> None:
    """Without force an existing meta.json must be preserved verbatim and silently."""
    endpoint_dir = _startup_spec(tmp_path, monkeypatch)
    run_generate(None, False)

    meta_file = endpoint_dir / "meta.json"
    meta_file.write_text('{"parameters": "keep"}')

    run_generate(None, False)

    assert meta_file.read_text() == '{"parameters": "keep"}'
    assert capfd.readouterr().out == ""


def test_run_generate_unknown_endpoint_id_writes_no_meta_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown endpoint id must raise before any write, meta.json included."""
    endpoint_dir = _startup_spec(tmp_path, monkeypatch)

    with pytest.raises(click.ClickException, match="endpoint not found: nope_get"):
        run_generate(None, False, ["clients_startup_get", "nope_get"])

    assert not (tmp_path / "api").exists()
    assert not (tmp_path / "tests").exists()
    assert not (endpoint_dir / "meta.json").exists()


def test_run_generate_meta_json_empty_objects_when_no_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An endpoint with no query/body/path data still gets a meta.json with all three keys as {}."""
    endpoint_dir = _startup_spec(tmp_path, monkeypatch)

    run_generate(None, False)

    meta_file = endpoint_dir / "meta.json"
    assert meta_file.exists()
    assert json.loads(meta_file.read_text()) == {"parameters": {}, "request_body": {}, "vars": {}}


def test_run_generate_writes_meta_json_when_api_py_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing meta.json must be written even when api.py already exists (per-file force semantics)."""
    endpoint_dir = _startup_spec(tmp_path, monkeypatch)
    run_generate(None, False)

    api_file = endpoint_dir / "api.py"
    assert api_file.exists()
    expected_api = api_file.read_text()

    (endpoint_dir / "meta.json").unlink()

    run_generate(None, False)

    assert api_file.read_text() == expected_api
    assert json.loads((endpoint_dir / "meta.json").read_text()) == {"parameters": {}, "request_body": {}, "vars": {}}


def test_run_generate_meta_json_serializes_date_examples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """date/datetime values carried in parameter schemas render as ISO strings, not TypeError.

    swax/Prance convert YAML date-like examples into ``datetime.date`` objects; the
    meta.json (and schema-file) writes must serialize them instead of aborting the run
    mid-write with a partial artifact tree (mirrors ``render_info``).
    """
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /orders/{since}:
    get:
      description: Orders since a date
      parameters:
        - name: until
          in: query
          schema:
            type: string
            format: date
            example: 2020-01-01
        - name: since
          in: path
          schema:
            type: string
            format: date
            example: 2020-02-02
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  created:
                    type: string
                    format: date
                    example: 2020-03-03
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    meta_file = tmp_path / "api" / "shop" / "orders_since_get" / "meta.json"
    assert meta_file.exists()
    assert json.loads(meta_file.read_text()) == {
        "parameters": {"until": {"type": "string", "format": "date", "example": "2020-01-01"}},
        "request_body": {},
        "vars": {"since": {"type": "string", "format": "date", "example": "2020-02-02"}},
    }
    schema_file = tmp_path / "api" / "shop" / "orders_since_get" / "schemas" / "200.json"
    assert json.loads(schema_file.read_text())["properties"]["created"]["example"] == "2020-03-03"


def test_run_generate_serializes_non_finite_numbers_as_null(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """YAML `.nan`/`.inf` values write as null — the bare tokens NaN/Infinity are not strict JSON.

    json.dumps encodes non-finite floats as ``NaN``/``Infinity`` by default,
    which Python's json.loads tolerates but other parsers reject. The artifact
    files must stay parseable by any JSON consumer, so the values render as
    ``null`` and the written text carries no bare token.
    """
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /orders:
    get:
      description: Orders
      parameters:
        - name: cutoff
          in: query
          schema:
            type: number
            example: .inf
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  ratio:
                    type: number
                    example: .nan
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    endpoint_dir = tmp_path / "api" / "shop" / "orders_get"
    meta_file = endpoint_dir / "meta.json"
    assert json.loads(meta_file.read_text())["parameters"]["cutoff"]["example"] is None
    schema_file = endpoint_dir / "schemas" / "200.json"
    assert json.loads(schema_file.read_text())["properties"]["ratio"]["example"] is None
    # The written text carries no bare non-finite token
    assert "NaN" not in meta_file.read_text()
    assert "NaN" not in schema_file.read_text()
    assert "Infinity" not in meta_file.read_text()
    assert "Infinity" not in schema_file.read_text()


def test_run_generate_request_body_date_example_writes_all_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A date-like value in the request body must not abort the artifact write.

    The schema/meta.json writes serialize dates via ``_json_default``; the
    request-model path must do the same, otherwise a spec with a YAML date
    example under ``format: date`` aborts the run with a raw ``TypeError``
    after earlier artifacts are already on disk.
    """
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /orders:
    post:
      description: Create an order
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [when]
              properties:
                when:
                  type: string
                  format: date
                  example: 2020-01-01
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)  # must not raise

    endpoint_dir = tmp_path / "api" / "shop" / "orders_post"
    assert (endpoint_dir / "schemas" / "200.json").exists()
    assert (endpoint_dir / "meta.json").exists()
    api_py = endpoint_dir / "api.py"
    assert api_py.exists()
    # the request model was actually rendered (the body had usable properties)
    assert "class Request" in api_py.read_text()


@pytest.mark.parametrize(
    ("force", "expected"),
    [
        (False, "# consumer-owned facade — do not touch\n"),
        (True, ""),
    ],
)
def test_run_generate_init_marker_follows_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, force: bool, expected: str
) -> None:
    """run_generate must skip an existing __init__.py without force and overwrite it with force."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "t.yaml",
        """\
paths:
  /health:
    get:
      description: Health check
""",
    )
    config_path = _write_config(tmp_path, {"t": ".specs/t.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    # A consumer placed a real package facade in an __init__.py along the path
    facade_dir = tmp_path / "api" / "t"
    facade_dir.mkdir(parents=True, exist_ok=True)
    (facade_dir / "__init__.py").write_text("# consumer-owned facade — do not touch\n")

    run_generate(None, force)

    # Without force the marker is preserved; with force it is overwritten with empty content
    assert (facade_dir / "__init__.py").read_text() == expected
    # The other markers are created empty either way
    assert (tmp_path / "api" / "__init__.py").read_text() == ""
    assert (tmp_path / "api" / "t" / "health_get" / "__init__.py").read_text() == ""


def test_run_generate_init_markers_idempotent_across_endpoints_and_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_generate should write shared markers once and stay idempotent across endpoints and re-runs."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "t.yaml",
        """\
paths:
  /clients/startup:
    get:
      responses:
        '200':
          description: Success
  /health:
    get:
      responses:
        '200':
          description: Success
""",
    )
    config_path = _write_config(tmp_path, {"t": ".specs/t.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)
    run_generate(None, False)  # re-run — must not raise, must not duplicate or clobber

    # Shared markers exist exactly once and stay empty
    assert (tmp_path / "api" / "__init__.py").read_text() == ""
    assert (tmp_path / "api" / "t" / "__init__.py").read_text() == ""
    # Each endpoint dir has its own marker
    assert (tmp_path / "api" / "t" / "clients_startup_get" / "__init__.py").read_text() == ""
    assert (tmp_path / "api" / "t" / "health_get" / "__init__.py").read_text() == ""


def test_run_generate_noop_on_empty_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """run_generate should be a no-op (no raise, no artifacts, no logs) on an empty config."""
    monkeypatch.chdir(tmp_path)

    config_path = _write_config(tmp_path, {})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with caplog.at_level("DEBUG"):
        run_generate(None, False)

    assert not (tmp_path / "api").exists()
    assert not (tmp_path / "tests").exists()
    assert caplog.records == []


def test_generate_cmd_binds_spec_force_and_endpoint_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """generate_cmd should bind -s/--spec, -f/--force and the positional endpoint-ids, then delegate to run_generate."""
    from click.testing import CliRunner

    monkeypatch.chdir(tmp_path)

    captured: dict = {}

    def fake_run_generate(spec_name, force, endpoint_ids):
        captured["spec_name"] = spec_name
        captured["force"] = force
        captured["endpoint_ids"] = endpoint_ids

    monkeypatch.setattr("goga_tool_pybuggy.commands.generate.generate.run_generate", fake_run_generate)

    # Options precede the variadic positional endpoint-ids (click parses options before the variadic tail)
    result = CliRunner().invoke(generate_cmd, ["-s", "x", "-f", "id1", "id2"])

    assert result.exit_code == 0
    assert captured == {"spec_name": "x", "force": True, "endpoint_ids": ["id1", "id2"]}

    # Without positional ids the variadic argument is empty → None (no filter)
    captured.clear()
    result = CliRunner().invoke(generate_cmd, ["-s", "x"])
    assert result.exit_code == 0
    assert captured == {"spec_name": "x", "force": False, "endpoint_ids": None}


# Endpoint-id filter tests ---------------------------------------------------


def _two_endpoint_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str = "shop") -> None:
    """Write a config + spec with two endpoints: clients_startup_get and health_get."""
    monkeypatch.chdir(tmp_path)
    _write_spec(
        tmp_path / ".specs",
        f"{name}.yaml",
        """\
paths:
  /clients/startup:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
  /health:
    get:
      responses:
        '200':
          description: Success
""",
    )
    config_path = _write_config(tmp_path, {name: f".specs/{name}.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)


def test_run_generate_filters_to_single_endpoint_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should scaffold only the endpoint whose id is in endpoint_ids."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    run_generate(None, False, ["clients_startup_get"])

    assert (tmp_path / "api" / "shop" / "clients_startup_get" / "api.py").exists()
    # The non-matching endpoint is filtered out — no artifact tree for it
    assert not (tmp_path / "api" / "shop" / "health_get").exists()
    assert not (tmp_path / "tests" / "shop" / "health_get").exists()


def test_run_generate_filters_to_multiple_endpoint_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should scaffold every endpoint whose id is in endpoint_ids."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    run_generate(None, False, ["clients_startup_get", "health_get"])

    assert (tmp_path / "api" / "shop" / "clients_startup_get" / "api.py").exists()
    assert (tmp_path / "api" / "shop" / "health_get" / "api.py").exists()


def test_run_generate_empty_endpoint_ids_is_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate with an empty endpoint_ids list should generate all endpoints (no filter)."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    run_generate(None, False, [])

    assert (tmp_path / "api" / "shop" / "clients_startup_get" / "api.py").exists()
    assert (tmp_path / "api" / "shop" / "health_get" / "api.py").exists()


def test_run_generate_raises_for_unknown_endpoint_id_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_generate should raise ClickException for an unknown endpoint id and write no artifacts."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    with pytest.raises(click.ClickException) as exc:
        run_generate(None, False, ["does_not_exist_get"])

    assert "endpoint not found: does_not_exist_get" in str(exc.value)
    # Atomicity: validation happens before any disk write, so nothing is produced
    assert not (tmp_path / "api").exists()
    assert not (tmp_path / "tests").exists()


def test_run_generate_unknown_ids_message_sorted_and_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should list every missing id (sorted) in the ClickException message."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    with pytest.raises(click.ClickException) as exc:
        run_generate(None, False, ["zebra_get", "alpha_get"])

    msg = str(exc.value)
    assert "alpha_get" in msg
    assert "zebra_get" in msg
    # Sorted order within the comma-joined list
    assert msg.index("alpha_get") < msg.index("zebra_get")


def test_run_generate_finds_endpoint_id_across_specs_without_spec_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_generate should find an endpoint id in any spec when spec_name is not set."""
    monkeypatch.chdir(tmp_path)
    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      responses:
        '200':
          description: Success
""",
    )
    _write_spec(
        tmp_path / ".specs",
        "billing.yaml",
        """\
paths:
  /health:
    get:
      responses:
        '200':
          description: Success
""",
    )
    config_path = _write_config(
        tmp_path,
        {"shop": ".specs/shop.yaml", "billing": ".specs/billing.yaml"},
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False, ["health_get"])

    # Found in the billing spec; the shop spec produces nothing
    assert (tmp_path / "api" / "billing" / "health_get" / "api.py").exists()
    assert not (tmp_path / "api" / "shop").exists()


def test_run_generate_raises_when_endpoint_id_absent_from_selected_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_generate with spec_name should raise when the endpoint id lives only in another spec."""
    monkeypatch.chdir(tmp_path)
    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients/startup:
    get:
      responses:
        '200':
          description: Success
""",
    )
    _write_spec(
        tmp_path / ".specs",
        "billing.yaml",
        """\
paths:
  /health:
    get:
      responses:
        '200':
          description: Success
""",
    )
    config_path = _write_config(
        tmp_path,
        {"shop": ".specs/shop.yaml", "billing": ".specs/billing.yaml"},
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    # health_get exists in billing but the --spec filter restricts the scope to shop
    with pytest.raises(click.ClickException) as exc:
        run_generate("shop", False, ["health_get"])
    assert "endpoint not found: health_get" in str(exc.value)
    assert not (tmp_path / "api").exists()


def test_run_generate_filter_preserves_force_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_generate should honor --force for the filtered endpoint only."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    run_generate(None, False, ["clients_startup_get"])

    schema_file = tmp_path / "api" / "shop" / "clients_startup_get" / "schemas" / "200.json"
    assert schema_file.exists()
    schema_file.write_text("STALE")

    run_generate(None, True, ["clients_startup_get"])

    assert schema_file.read_text() != "STALE"
    # The other endpoint stays filtered out even under --force
    assert not (tmp_path / "api" / "shop" / "health_get").exists()


# Render tests (render_api_module) -------------------------------------------


def test_render_api_module_with_request_body() -> None:
    """render_api_module should render the canonical ruff-aligned module for an endpoint with a request body."""
    endpoint = Endpoint(
        method="post",
        path="/clients/calls/{orderID}/status",
        request={
            "type": "object",
            "properties": {"note": {"type": "string"}, "count": {"type": "integer"}},
            "required": ["note"],
        },
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)

    assert module == (
        "import pytest\n"
        "from goga_tool_pybuggy.api import Api, Endpoint\n"
        "from pydantic import BaseModel\n\n\n"
        "class Request(BaseModel):\n"
        "    note: str\n"
        "    count: int | None = None\n\n\n"
        '@pytest.fixture(scope="function")\n'
        "def post_clients_calls_orderid_status(api: Api) -> Endpoint:\n"
        '    return Endpoint(api, "/clients/calls/:orderID/status", method="POST")\n'
    )


def test_render_api_module_without_request_body() -> None:
    """render_api_module should render the fixture-only module for an endpoint without a request body."""
    endpoint = Endpoint(
        method="get",
        path="/health",
        request={},
        response={},
        query_params={},
        description="",
    )
    assert endpoint.id == "health_get"

    module = render_api_module(endpoint)

    assert module == (
        "import pytest\n"
        "from goga_tool_pybuggy.api import Api, Endpoint\n\n\n"
        '@pytest.fixture(scope="function")\n'
        "def get_health(api: Api) -> Endpoint:\n"
        '    return Endpoint(api, "/health", method="GET")\n'
    )


def test_render_api_module_primitives_union_nested_and_array() -> None:
    """render_api_module should map primitives to builtins, use the union operator for optionals,
    and emit a nested object model plus a typed array — the capability datamodel-code-generator adds."""
    endpoint = Endpoint(
        method="post",
        path="/o",
        request={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "number"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "addr": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
            "required": ["a"],
        },
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)

    assert module == (
        "import pytest\n"
        "from goga_tool_pybuggy.api import Api, Endpoint\n"
        "from pydantic import BaseModel\n\n\n"
        "class Addr(BaseModel):\n"
        "    city: str | None = None\n\n\n"
        "class Request(BaseModel):\n"
        "    a: int\n"
        "    b: float | None = None\n"
        "    tags: list[str] | None = None\n"
        "    addr: Addr | None = None\n\n\n"
        '@pytest.fixture(scope="function")\n'
        "def post_o(api: Api) -> Endpoint:\n"
        '    return Endpoint(api, "/o", method="POST")\n'
    )


def test_render_api_module_object_without_properties_omits_request() -> None:
    """render_api_module should omit class Request when the body schema has no properties."""
    endpoint = Endpoint(
        method="post",
        path="/x",
        request={"type": "object"},
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)

    assert "class Request" not in module
    assert "BaseModel" not in module
    assert '@pytest.fixture(scope="function")' in module
    assert "def post_x(api: Api) -> Endpoint:" in module


def test_render_api_module_deterministic_for_same_endpoint() -> None:
    """render_api_module should produce identical text for two identical endpoints."""
    kwargs = {
        "method": "post",
        "path": "/clients/calls/{orderID}/status",
        "request": {
            "type": "object",
            "properties": {"note": {"type": "string"}, "count": {"type": "integer"}},
            "required": ["note"],
        },
        "response": {},
        "query_params": {},
        "description": "",
    }
    e1 = Endpoint(**kwargs)
    e2 = Endpoint(**kwargs)

    assert render_api_module(e1) == render_api_module(e2)


def test_render_api_module_multiple_path_params_preserve_case() -> None:
    """render_api_module should convert each {param} to :param preserving the original case."""
    endpoint = Endpoint(
        method="get",
        path="/v1/clients/{clientID}/orders/{orderID}",
        request={},
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)

    assert 'return Endpoint(api, "/v1/clients/:clientID/orders/:orderID", method="GET")' in module


def test_render_api_module_all_optional_fields_when_no_required() -> None:
    """render_api_module should treat every field as optional (X | None = None) when the body has no `required` list."""
    endpoint = Endpoint(
        method="post",
        path="/y",
        request={
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
        },
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)

    assert module == (
        "import pytest\n"
        "from goga_tool_pybuggy.api import Api, Endpoint\n"
        "from pydantic import BaseModel\n\n\n"
        "class Request(BaseModel):\n"
        "    a: str | None = None\n"
        "    b: int | None = None\n\n\n"
        '@pytest.fixture(scope="function")\n'
        "def post_y(api: Api) -> Endpoint:\n"
        '    return Endpoint(api, "/y", method="POST")\n'
    )


def test_render_api_module_nullable_required_field_uses_union_operator() -> None:
    """render_api_module should render a nullable required field as `str | None` (no default) via the union operator."""
    endpoint = Endpoint(
        method="post",
        path="/n",
        request={
            "type": "object",
            "properties": {"a": {"type": ["string", "null"]}},
            "required": ["a"],
        },
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)

    assert "    a: str | None\n" in module
    assert "Optional" not in module


def test_render_api_module_ref_field_renders_root_model_without_raising() -> None:
    """render_api_module should hand an unresolved $ref to datamodel-code-generator, which wraps it in a RootModel."""
    endpoint = Endpoint(
        method="post",
        path="/x",
        request={
            "type": "object",
            "properties": {"g": {"$ref": "#/x"}},
            "required": ["g"],
        },
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)  # must not raise

    assert "class X(RootModel[Any]):" in module
    assert "    root: Any" in module
    assert "    g: X" in module
    assert "from typing import Any" in module
    assert "from pydantic import BaseModel, RootModel" in module


@pytest.mark.parametrize("pschema", [True, False, None, "string", 5, []])
def test_render_api_module_non_dict_schema_maps_to_any_without_raising(pschema) -> None:
    """render_api_module should treat any non-dict property schema (incl. valid boolean
    JSON-Schema true/false) as the "any" schema -> `Any` and never raise."""
    endpoint = Endpoint(
        method="post",
        path="/b",
        request={"type": "object", "properties": {"a": pschema}, "required": ["a"]},
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)  # must not raise

    assert "    a: Any" in module
    assert "from typing import Any" in module


def test_render_api_module_quotes_route_with_special_characters() -> None:
    """A path key carrying a quote must render a valid string literal, not broken source.

    YAML permits quotes in path keys (e.g. "/o'brien/{id}"); a plain single-quoted
    interpolation would produce an unimportable api.py (ruff format aborts). The route
    itself is preserved verbatim — only the literal quoting changes.
    """
    endpoint = Endpoint(
        method="get",
        path="/o'brien/{id}",
        request={},
        response={},
        query_params={},
        description="",
    )

    module = render_api_module(endpoint)  # must not raise

    assert 'return Endpoint(api, "/o\'brien/:id", method="GET")' in module
    compile(module, "api.py", "exec")  # the rendered text is valid Python


def test_render_api_module_sanitizes_fixture_name_to_identifier() -> None:
    """A path segment outside [a-z0-9_] must not leak into the fixture name.

    build_endpoint_id normalizes "/" and "-" only; the dot in "/v1.0/clients"
    survives into the id, and the fixture name is emitted as source text —
    without sanitation the module is syntactically invalid.
    """
    endpoint = Endpoint(
        method="get",
        path="/v1.0/clients",
        request={},
        response={},
        query_params={},
        description="",
    )
    assert endpoint.id == "v1.0_clients_get"

    module = render_api_module(endpoint)  # must not raise

    assert "def get_v1_0_clients(api: Api) -> Endpoint:" in module
    compile(module, "api.py", "exec")


def test_run_generate_endpoint_dir_is_importable_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The per-endpoint directory must be an importable package name.

    The fixture module is loaded by dotted name from its directory path, so a
    non-identifier character in the endpoint id (the dot in "/v1.0/clients")
    would leave the generated tree unloadable even though api.py itself is valid.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /v1.0/clients:
    get:
      description: List clients
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    # the directory is a valid Python identifier segment
    endpoint_dirs = [p for p in (tmp_path / "api" / "shop").iterdir() if p.is_dir()]
    assert [d.name for d in endpoint_dirs] == ["v1_0_clients_get"]

    # ... and the module is importable under its dotted name from that tree
    assert _module_is_pytest_plugin("api.shop.v1_0_clients_get.api")


def test_run_generate_fixture_name_matches_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture name and directory derive from the same sanitized id.

    Distinct raw paths must not collapse onto the same fixture name while
    writing to distinct directories — the two fixtures would shadow each other
    with no warning. "/clients" and "/clients/" are distinct ids that stay
    distinct after sanitization.
    """
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /clients:
    get:
      description: List clients
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
  /clients/:
    get:
      description: List clients (trailing-slash variant)
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_generate(None, False)

    endpoint_dirs = sorted(p.name for p in (tmp_path / "api" / "shop").iterdir() if p.is_dir())
    fixture_names = [
        line
        for api_py in sorted((tmp_path / "api" / "shop").rglob("api.py"))
        for line in api_py.read_text().splitlines()
        if line.startswith("def ")
    ]
    # one directory and one fixture per endpoint — no silent collapse in either
    assert endpoint_dirs == ["clients__get", "clients_get"]
    assert len(fixture_names) == 2
    assert len(set(fixture_names)) == 2


def test_run_generate_rejects_sanitized_id_collision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two distinct ids sanitizing to one directory abort before any write.

    "/v1.0/clients" and "/v1_0/clients" both map to "v1_0_clients_get"; without
    the check the second endpoint's artifacts would be silently skipped (they
    "already exist") and its response schemas would land in the first endpoint's
    directory.
    """
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /v1.0/clients:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
  /v1_0/clients:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException, match="v1_0_clients_get"):
        run_generate(None, False)

    # the collision is detected in the collect/validate phase — nothing on disk
    assert not (tmp_path / "api").exists()


def test_run_generate_rejects_identical_id_from_distinct_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two paths producing the *identical* raw id also collide and must abort.

    ``build_endpoint_id`` maps both "-" and "/" to "_", so "/a-b/x" and "/a/b/x"
    (same method) yield the same id "a_b_x_get" — not two ids that merely
    sanitize alike. Keying the guard on the raw id lets this through: without
    --force the second endpoint's artifacts are silently skipped, and with
    --force they overwrite the first endpoint's schema.
    """
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /a-b/x:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  from:
                    type: string
  /a/b/x:
    get:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  other:
                    type: string
""",
    )
    config_path = _write_config(tmp_path, {"shop": ".specs/shop.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    # the message names both offending paths — the id alone cannot tell them apart
    with pytest.raises(click.ClickException, match=r"/a-b/x.*and.*/a/b/x"):
        run_generate(None, False)

    # the collision is detected in the collect/validate phase — nothing on disk
    assert not (tmp_path / "api").exists()
