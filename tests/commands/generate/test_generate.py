"""Contract and logic tests for run_generate / generate_cmd handler."""

import json
from pathlib import Path

import click
import pytest
from goga_tool_pybuggy.commands.generate import generate_cmd, render_api_module, run_generate
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
