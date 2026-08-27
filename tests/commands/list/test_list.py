"""Contract and logic tests for run_list handler and endpoint_statuses classifier."""

import json
from pathlib import Path

import click
import goga_tool_pybuggy.commands.list
import pytest
from goga_tool_pybuggy.commands.list import endpoint_statuses, run_list
from goga_tool_pybuggy.spec import Endpoint, extract_endpoints, load_spec

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
_CANONICAL_OK_META = {"parameters": {}, "request_body": {}, "vars": {}}
_CANONICAL_OK_SCHEMAS = {"200": {"type": "object"}}


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


def _spec_endpoints(spec_path: Path) -> list[Endpoint]:
    """Load a spec from disk and extract its endpoints (the run_list extraction path)."""
    return extract_endpoints(load_spec(spec_path))


def _endpoint(method: str, path: str) -> Endpoint:
    """Build a minimal Endpoint model with empty request/response sides."""
    return Endpoint(
        method=method,
        path=path,
        request={},
        response={},
        query_params={},
        description="",
    )


def test_run_list_importable_from_facade() -> None:
    """run_list should be importable from goga_tool_pybuggy.commands.list facade."""
    from goga_tool_pybuggy.commands.list import run_list as imported

    assert imported is run_list


def test_run_list_signature() -> None:
    """run_list should have signature (spec_name: Optional[str]) with no ctx."""
    params = run_list.__code__.co_varnames[: run_list.__code__.co_argcount]

    assert "spec_name" in params
    assert "ctx" not in params


def test_run_list_signature_with_status_default_false() -> None:
    """run_list should take with_status as a keyword argument defaulting to False."""
    params = run_list.__code__.co_varnames[: run_list.__code__.co_argcount]

    assert {"spec_name", "with_status"} <= set(params)
    assert run_list.__defaults__ == (False,)


# Logic tests


def test_run_list_prints_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """run_list should print formatted block with header and endpoint lines."""
    monkeypatch.chdir(tmp_path)

    spec_dir = tmp_path / ".specs"
    spec_dir.mkdir()
    (spec_dir / "client.yaml").write_text(
        """
openapi: 3.0.0
info:
  title: Client API
  version: 1.0.0
paths:
  /clients/startup:
    get:
      description: Get startup info
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
  /clients/profile:
    delete:
      description: Delete profile
      responses:
        '204':
          description: No content
"""
    )

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_list(None)

    output = capsys.readouterr().out
    assert "client (.specs/client.yaml)" in output
    assert "* clients_profile_delete -> [DELETE] /clients/profile" in output
    assert "* clients_startup_get -> [GET] /clients/startup" in output


def test_run_list_handles_empty_endpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_list should print only header when spec has no endpoints."""
    monkeypatch.chdir(tmp_path)

    spec_dir = tmp_path / ".specs"
    spec_dir.mkdir()
    (spec_dir / "empty.yaml").write_text(
        """
openapi: 3.0.0
info:
  title: Empty API
  version: 1.0.0
paths: {}
"""
    )

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  empty:
    type: openapi
    location: .specs/empty.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_list(None)

    output = capsys.readouterr().out
    assert "empty (.specs/empty.yaml)" in output
    assert "* " not in output


def test_run_list_filters_by_spec_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_list should only list specified spec when spec_name provided."""
    monkeypatch.chdir(tmp_path)

    spec_dir = tmp_path / ".specs"
    spec_dir.mkdir()
    (spec_dir / "client.yaml").write_text(
        """
openapi: 3.0.0
info:
  title: Client API
  version: 1.0.0
paths:
  /clients/startup:
    get:
      description: Get startup
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
"""
    )
    (spec_dir / "server.yaml").write_text(
        """
openapi: 3.0.0
info:
  title: Server API
  version: 1.0.0
paths:
  /server/status:
    get:
      description: Get status
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
"""
    )

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
  server:
    type: openapi
    location: .specs/server.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_list("client")

    output = capsys.readouterr().out
    assert "client (.specs/client.yaml)" in output
    assert "server" not in output


def test_run_list_raises_on_spec_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_list should raise ClickException when spec_name not found in config."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException) as exc_info:
        run_list("nonexistent_spec")
    assert "spec not found: nonexistent_spec" in str(exc_info.value)


def test_run_list_invalid_response_key_raises_click_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_list should map an illegal response status key to ClickException, not a raw traceback.

    `_extract_responses` raises ValueError on response keys outside the shapes the
    specifications allow (the key becomes an artifact filename in generate); list must
    surface that as a CLI error, mirroring generate/diff (regression: raw ValueError
    traceback before the guard).
    """
    monkeypatch.chdir(tmp_path)

    spec_dir = tmp_path / ".specs"
    spec_dir.mkdir()
    (spec_dir / "client.yaml").write_text(
        """
openapi: 3.0.0
info:
  title: Client API
  version: 1.0.0
paths:
  /clients:
    get:
      responses:
        '2X0':
          description: bad key
"""
    )
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException) as exc_info:
        run_list("client")
    assert "invalid spec file" in str(exc_info.value)
    assert "2X0" in str(exc_info.value)
    # A CLI error is raised before anything is printed
    assert capsys.readouterr().out == ""


def test_run_list_null_paths_raises_click_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_list should treat `paths:` with a null value as a missing-paths spec, not crash on None.items()."""
    monkeypatch.chdir(tmp_path)

    spec_dir = tmp_path / ".specs"
    spec_dir.mkdir()
    (spec_dir / "client.yaml").write_text(
        """
openapi: 3.0.0
info:
  title: Client API
  version: 1.0.0
paths:
"""
    )
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException, match="missing 'paths'"):
        run_list("client")


# Logic tests: run_list status mode ------------------------------------------


def test_run_list_status_mode_unknown_spec_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Status mode rejects an unknown spec before any output, like the plain mode."""
    monkeypatch.chdir(tmp_path)

    config_path = _write_config(tmp_path, {"client": ".specs/client.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException, match="spec not found: nonexistent_spec"):
        run_list("nonexistent_spec", with_status=True)
    assert capsys.readouterr().out == ""


def test_run_list_status_mode_invalid_spec_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Status mode shares the plain mode's structure guard — `paths:` null fails equally."""
    monkeypatch.chdir(tmp_path)

    _write_spec(tmp_path / ".specs", "client.yaml", "paths:\n")
    config_path = _write_config(tmp_path, {"client": ".specs/client.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with pytest.raises(click.ClickException, match="missing 'paths'"):
        run_list("client", with_status=True)


def test_run_list_status_mode_no_artifact_tree_all_add(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A fresh workspace without an api/ tree lists every endpoint as ADD and exits cleanly."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "client.yaml",
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
""",
    )
    config_path = _write_config(tmp_path, {"client": ".specs/client.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    run_list(None, with_status=True)

    assert capsys.readouterr().out == (
        "client (.specs/client.yaml)\n"
        "* clients_startup_get -> [GET] /clients/startup — STATUS: ADD\n"
    )


def test_run_list_status_mode_empty_spec_no_lines_prints_no_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A spec with no endpoints prints nothing in status mode, but the warning still fires."""
    monkeypatch.chdir(tmp_path)

    _write_spec(tmp_path / ".specs", "empty.yaml", "paths: {}\n")
    config_path = _write_config(tmp_path, {"empty": ".specs/empty.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with caplog.at_level("WARNING"):
        run_list(None, with_status=True)

    assert capsys.readouterr().out == ""
    assert any("no endpoints found in spec: empty" in record.message for record in caplog.records)


def test_run_list_status_mode_empty_spec_with_orphan_prints_removed_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Removed segments count as lines — an endpoint-less spec still prints its removed block."""
    monkeypatch.chdir(tmp_path)

    _write_spec(tmp_path / ".specs", "empty.yaml", "paths: {}\n")
    config_path = _write_config(tmp_path, {"empty": ".specs/empty.yaml"})
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)
    _write_artifact(tmp_path, "empty", "legacy_get", _CANONICAL_OK_META, _CANONICAL_OK_SCHEMAS)

    run_list(None, with_status=True)

    assert capsys.readouterr().out == "empty (.specs/empty.yaml)\n* legacy_get — STATUS: REMOVED\n"


# Contract tests: endpoint_statuses ------------------------------------------


def test_endpoint_statuses_facade_export() -> None:
    """endpoint_statuses is exported from the cell facade, __all__ sorted."""
    assert "endpoint_statuses" in goga_tool_pybuggy.commands.list.__all__
    assert goga_tool_pybuggy.commands.list.__all__ == sorted(goga_tool_pybuggy.commands.list.__all__)
    assert goga_tool_pybuggy.commands.list.endpoint_statuses is endpoint_statuses


# Logic tests: endpoint_statuses ---------------------------------------------


def test_endpoint_statuses_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One workspace covers all four statuses: OK, UPD, ADD and the REMOVED orphan side."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "client.yaml",
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
    post:
      description: Create a client
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                type: object
  /clients/update:
    put:
      description: Update a client
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""",
    )
    endpoints = _spec_endpoints(tmp_path / ".specs" / "client.yaml")

    # OK — the artifact pair matches the spec side exactly
    _write_artifact(tmp_path, "client", "clients_startup_get", _CANONICAL_OK_META, _CANONICAL_OK_SCHEMAS)
    # UPD — same segment shape, drifted schema body
    _write_artifact(
        tmp_path,
        "client",
        "clients_update_put",
        _CANONICAL_OK_META,
        {"200": {"type": "string"}},
    )
    # ADD — no directory for clients_startup_post
    # REMOVED — a healthy artifact directory matching no endpoint of the spec
    _write_artifact(tmp_path, "client", "legacy_endpoint_get", _CANONICAL_OK_META, _CANONICAL_OK_SCHEMAS)

    statuses, removed = endpoint_statuses(tmp_path / "api" / "client", endpoints)

    assert statuses == {
        "clients_startup_get": "OK",
        "clients_startup_post": "ADD",
        "clients_update_put": "UPD",
    }
    assert removed == ["legacy_endpoint_get"]


def test_endpoint_statuses_absent_tree_all_add(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A spec without an artifact tree yields ADD for every endpoint and no removed side."""
    monkeypatch.chdir(tmp_path)

    api_dir = tmp_path / "api" / "client"
    endpoints = [_endpoint("get", "/a"), _endpoint("post", "/b")]

    statuses, removed = endpoint_statuses(api_dir, endpoints)

    assert statuses == {"a_get": "ADD", "b_post": "ADD"}
    assert removed == []


def test_endpoint_statuses_skips_tooling_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tooling directories under api/<spec>/ are never orphans and never fail the run."""
    monkeypatch.chdir(tmp_path)

    _write_spec(
        tmp_path / ".specs",
        "client.yaml",
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
""",
    )
    endpoints = _spec_endpoints(tmp_path / ".specs" / "client.yaml")
    _write_artifact(tmp_path, "client", "clients_startup_get", _CANONICAL_OK_META, _CANONICAL_OK_SCHEMAS)
    # No meta.json inside either directory — reading one would fail the run
    (tmp_path / "api" / "client" / "__pycache__" / "x").mkdir(parents=True)
    (tmp_path / "api" / "client" / ".hidden").mkdir(parents=True)

    statuses, removed = endpoint_statuses(tmp_path / "api" / "client", endpoints)

    assert statuses == {"clients_startup_get": "OK"}
    assert removed == []


def test_endpoint_statuses_segment_collision_classifies_both_against_one_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two ids sanitizing to one segment each classify against that directory — no orphan, no error."""
    monkeypatch.chdir(tmp_path)

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
    endpoints = _spec_endpoints(tmp_path / ".specs" / "client.yaml")
    # One artifact directory named by the shared segment v1_0_clients_get
    _write_artifact(tmp_path, "client", "v1_0_clients_get", _CANONICAL_OK_META, _CANONICAL_OK_SCHEMAS)

    statuses, removed = endpoint_statuses(tmp_path / "api" / "client", endpoints)

    assert statuses == {"v1.0_clients_get": "OK", "v1_0_clients_get": "OK"}
    assert removed == []
