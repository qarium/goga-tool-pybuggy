"""Contract and logic tests for run_diff / diff_cmd handler."""

import json
from pathlib import Path
from typing import Any, Optional

import click
import goga_tool_pybuggy.commands.diff
import pytest
from goga_tool_pybuggy.commands.diff import diff_cmd, run_diff

CONFIG_PATH_ATTR = "goga_tool_pybuggy.config.storage.CONFIG_PATH"

# Shared OpenAPI fragments ---------------------------------------------------

_OPENAPI_PREFIX = """\
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
"""

# Canonical endpoint: GET /clients/startup -> id "clients_startup_get"; the spec side
# is {"parameters": {}, "request_body": {}, "vars": {}, "schemas": {"200": {"type": "object"}}}.
_STARTUP_GET = """\
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


def _write_artifact(root: Path, spec: str, segment: str, meta: dict, schemas: dict) -> None:
    """Write ``api/<spec>/<segment>/`` with a meta.json and one schemas/<code>.json per code."""
    endpoint_dir = root / "api" / spec / segment
    schemas_dir = endpoint_dir / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    (endpoint_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    for status_code, schema in schemas.items():
        (schemas_dir / f"{status_code}.json").write_text(
            json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _setup_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str = _STARTUP_GET,
    meta: Optional[dict] = None,
    schemas: Optional[dict] = None,
) -> None:
    """Write a one-spec workspace: client spec + config + the startup endpoint artifacts."""
    monkeypatch.chdir(tmp_path)
    _write_spec(tmp_path / ".specs", "client.yaml", body)
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))
    _write_artifact(
        tmp_path,
        "client",
        "clients_startup_get",
        meta if meta is not None else {"parameters": {}, "request_body": {}, "vars": {}},
        schemas if schemas is not None else {"200": {"type": "object"}},
    )


# Contract tests -------------------------------------------------------------


def test_run_diff_importable_and_signature() -> None:
    """run_diff is importable from the cell facade with signature (spec_name, endpoint_ids=None)."""
    params = run_diff.__code__.co_varnames[: run_diff.__code__.co_argcount]

    assert {"spec_name", "endpoint_ids"} <= set(params)
    assert "ctx" not in params
    assert run_diff.__defaults__ == (None,)


def test_diff_cmd_is_click_command() -> None:
    """diff_cmd is a Click command 'diff' with a -s/--spec option and a variadic endpoint-ids argument."""
    assert diff_cmd.name == "diff"

    param_names = {p.name for p in diff_cmd.params}
    assert {"spec_name", "endpoint_ids"} <= param_names
    assert "ctx" not in param_names

    all_opts = {opt for p in diff_cmd.params for opt in p.opts}
    assert "-s" in all_opts
    assert "--spec" in all_opts

    # The endpoint-id filter is a variadic positional argument (nargs=-1)
    endpoint_arg = next(p for p in diff_cmd.params if p.name == "endpoint_ids")
    assert isinstance(endpoint_arg, click.Argument)
    assert endpoint_arg.nargs == -1


def test_facade_all_lists_full_six_names_sorted() -> None:
    """The commands/diff facade exports all six contract names, sorted."""
    assert goga_tool_pybuggy.commands.diff.__all__ == [
        "artifact_contract",
        "diff_cmd",
        "orphan_artifact_dirs",
        "run_diff",
        "sanitize_id",
        "spec_contract",
    ]


def test_diff_cmd_binds_spec_and_endpoint_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """diff_cmd binds -s/--spec and the positional endpoint-ids, then delegates to run_diff."""
    from click.testing import CliRunner

    monkeypatch.chdir(tmp_path)

    captured: dict = {}

    def fake_run_diff(spec_name, endpoint_ids):
        captured["spec_name"] = spec_name
        captured["endpoint_ids"] = endpoint_ids

    monkeypatch.setattr("goga_tool_pybuggy.commands.diff.diff.run_diff", fake_run_diff)

    # Options precede the variadic positional endpoint-ids (click parses options before the variadic tail)
    result = CliRunner().invoke(diff_cmd, ["-s", "x", "id1", "id2"])

    assert result.exit_code == 0
    assert captured == {"spec_name": "x", "endpoint_ids": ["id1", "id2"]}

    # Without positional ids the variadic argument is empty -> None (no filter)
    captured.clear()
    result = CliRunner().invoke(diff_cmd, ["-s", "x"])

    assert result.exit_code == 0
    assert captured == {"spec_name": "x", "endpoint_ids": None}


# Logic tests ----------------------------------------------------------------


def test_run_diff_no_drift_prints_empty_diff_per_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Matching artifacts print exactly one document with an empty diff value."""
    _setup_workspace(tmp_path, monkeypatch)

    run_diff(None, None)

    assert capsys.readouterr().out.splitlines() == ['{"clients_startup_get": {}}']


def test_run_diff_reports_value_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A drifted artifact value reports old_value from the artifact, new_value from the spec."""
    _setup_workspace(
        tmp_path,
        monkeypatch,
        body="""\
paths:
  /clients/startup:
    get:
      description: Start a client
      requestBody:
        content:
          application/json:
            schema:
              properties:
                note:
                  type: string
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
        meta={"parameters": {}, "request_body": {"properties": {"note": {"type": "integer"}}}, "vars": {}},
    )

    run_diff(None, None)

    doc = json.loads(capsys.readouterr().out.splitlines()[0])
    assert doc["clients_startup_get"]["values_changed"]["root['request_body']['properties']['note']['type']"] == {
        "old_value": "integer",
        "new_value": "string",
    }


def test_run_diff_added_status_code_is_dictionary_item_added(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A spec-only status code appears as dictionary_item_added (t1=generated, t2=spec)."""
    _setup_workspace(
        tmp_path,
        monkeypatch,
        body="""\
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
        '418':
          description: Teapot
          content:
            application/json:
              schema:
                type: object
""",
    )

    run_diff(None, None)

    doc = json.loads(capsys.readouterr().out.splitlines()[0])
    assert doc["clients_startup_get"]["dictionary_item_added"] == ["root['schemas']['418']"]


def test_run_diff_removed_artifact_dir_is_root_value_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A legacy artifact directory reports a root values_change keyed by the segment."""
    _setup_workspace(tmp_path, monkeypatch)
    _write_artifact(
        tmp_path,
        "client",
        "legacy_endpoint_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )

    run_diff(None, None)

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    vc = json.loads(lines[1])["legacy_endpoint_get"]["values_changed"]["root"]
    assert vc["new_value"] == {}
    assert set(vc["old_value"]) == {"parameters", "request_body", "vars", "schemas"}


def test_run_diff_orphan_discovery_not_narrowed_by_endpoint_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The endpoint-id filter selects only the added side; removed discovery scans the whole tree."""
    monkeypatch.chdir(tmp_path)
    _write_spec(
        tmp_path / ".specs",
        "client.yaml",
        _STARTUP_GET
        + """\
  /health:
    get:
      description: Health
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))
    _write_artifact(
        tmp_path,
        "client",
        "clients_startup_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )
    _write_artifact(
        tmp_path,
        "client",
        "health_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )
    _write_artifact(
        tmp_path,
        "client",
        "legacy_endpoint_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )

    run_diff(None, ["health_get"])

    lines = capsys.readouterr().out.splitlines()
    assert json.loads(lines[0]).keys() == {"health_get"}
    assert any(json.loads(line).keys() == {"legacy_endpoint_get"} for line in lines[1:])


def test_run_diff_spec_filter_selects_one_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """-s/--spec restricts the report to the selected spec's endpoints and api tree."""
    monkeypatch.chdir(tmp_path)
    _write_spec(
        tmp_path / ".specs",
        "shop.yaml",
        """\
paths:
  /orders/create:
    post:
      description: Create an order
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    _write_spec(tmp_path / ".specs", "client.yaml", _STARTUP_GET)
    monkeypatch.setattr(
        CONFIG_PATH_ATTR,
        _write_config(tmp_path, {"shop": ".specs/shop.yaml", "client": ".specs/client.yaml"}),
    )
    _write_artifact(
        tmp_path,
        "shop",
        "orders_create_post",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )
    _write_artifact(
        tmp_path,
        "client",
        "clients_startup_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )
    _write_artifact(
        tmp_path,
        "client",
        "client_legacy_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )

    run_diff("shop", None)

    out = capsys.readouterr().out
    lines = out.splitlines()
    keys = {key for line in lines for key in json.loads(line)}
    assert keys == {"orders_create_post"}
    assert "clients_startup_get" not in out
    assert "client_legacy_get" not in out


def test_run_diff_unknown_spec_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown --spec value fails with 'spec not found'."""
    monkeypatch.chdir(tmp_path)
    _write_spec(tmp_path / ".specs", "client.yaml", _STARTUP_GET)
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))

    with pytest.raises(click.ClickException, match="spec not found: nope"):
        run_diff("nope", None)


def test_run_diff_unknown_endpoint_id_raises_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """An unknown endpoint id fails before anything is printed."""
    _setup_workspace(tmp_path, monkeypatch)

    with pytest.raises(click.ClickException, match="endpoint not found: nope_endpoint_get"):
        run_diff(None, ["nope_endpoint_get"])

    assert capsys.readouterr().out == ""


def test_run_diff_missing_paths_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A spec without a 'paths' key fails with 'invalid spec file'."""
    monkeypatch.chdir(tmp_path)
    _write_spec(tmp_path / ".specs", "client.yaml", "")
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))

    with pytest.raises(click.ClickException, match="invalid spec file"):
        run_diff(None, None)


def test_run_diff_spec_without_api_tree_reports_all_added(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Endpoints without an api tree are added as a whole — root values_change with an empty old side."""
    monkeypatch.chdir(tmp_path)
    _write_spec(
        tmp_path / ".specs",
        "client.yaml",
        _STARTUP_GET
        + """\
  /health:
    get:
      description: Health
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))

    run_diff(None, None)

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    for line in lines:
        value = next(iter(json.loads(line).values()))
        assert set(value) == {"values_changed"}
        assert value["values_changed"]["root"]["old_value"] == {}


def test_run_diff_empty_filter_means_every_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """An empty endpoint-ids list means no filter — every endpoint is compared."""
    monkeypatch.chdir(tmp_path)
    _write_spec(
        tmp_path / ".specs",
        "client.yaml",
        _STARTUP_GET
        + """\
  /health:
    get:
      description: Health
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))
    _write_artifact(
        tmp_path,
        "client",
        "clients_startup_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )
    _write_artifact(
        tmp_path,
        "client",
        "health_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )

    run_diff(None, [])

    assert len(capsys.readouterr().out.splitlines()) == 2


def test_run_diff_multiple_missing_ids_listed_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Several unknown endpoint ids are listed sorted in one error."""
    monkeypatch.chdir(tmp_path)
    _write_spec(tmp_path / ".specs", "client.yaml", _STARTUP_GET)
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))

    with pytest.raises(click.ClickException, match="endpoint not found: aa_get, zz_get"):
        run_diff(None, ["zz_get", "aa_get"])


def test_run_diff_empty_spec_reports_all_dirs_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A spec with no operations prints no per-endpoint documents and every directory as removed."""
    monkeypatch.chdir(tmp_path)
    _write_spec(tmp_path / ".specs", "client.yaml", "paths: {}\n")
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))
    _write_artifact(
        tmp_path,
        "client",
        "legacy",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )

    run_diff("client", None)

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    doc = json.loads(lines[0])
    assert doc.keys() == {"legacy"}
    assert doc["legacy"]["values_changed"]["root"]["new_value"] == {}


def test_run_diff_endpoint_doc_serializes_all_categories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Every printed document is valid JSON regardless of the reported deepdiff categories."""
    _setup_workspace(tmp_path, monkeypatch)
    _write_artifact(
        tmp_path,
        "client",
        "legacy_endpoint_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )

    run_diff(None, None)

    for line in capsys.readouterr().out.splitlines():
        doc: dict[str, Any] = json.loads(line)
        assert len(doc) == 1
        for diff in doc.values():
            json.dumps(diff)


def test_run_diff_segment_collision_compares_both_against_one_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Two ids sanitizing to one segment each compare against that directory — no orphan, no error."""
    _write_spec(
        tmp_path / ".specs",
        "client.yaml",
        """\
paths:
  /v1.0/clients:
    get:
      description: dotted
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
  /v1_0/clients:
    get:
      description: underscored
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))
    monkeypatch.chdir(tmp_path)
    # One artifact directory named by the shared segment v1_0_clients_get
    _write_artifact(
        tmp_path,
        "client",
        "v1_0_clients_get",
        {"parameters": {}, "request_body": {}, "vars": {}},
        {"200": {"type": "object"}},
    )

    run_diff("client", None)

    lines = capsys.readouterr().out.splitlines()
    # Both endpoints print a document keyed by their RAW id; the directory is
    # covered, so it is never reported as removed and neither side errors.
    assert [next(iter(json.loads(line))) for line in lines] == ["v1.0_clients_get", "v1_0_clients_get"]
