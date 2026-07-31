"""Contract and logic tests for run_info / info_cmd handler."""

import json
from pathlib import Path

import click
import pytest
from goga_tool_pybuggy.commands.info import info_cmd, run_info

CONFIG_PATH_ATTR = "goga_tool_pybuggy.config.storage.CONFIG_PATH"

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


# Contract tests ---------------------------------------------------------------


def test_run_info_importable_from_facade() -> None:
    """run_info should be importable from goga_tool_pybuggy.commands.info facade."""
    from goga_tool_pybuggy.commands.info import run_info as imported

    assert imported is run_info


def test_run_info_signature() -> None:
    """run_info should have signature (endpoint_ids, spec_name) with no ctx."""
    params = run_info.__code__.co_varnames[: run_info.__code__.co_argcount]

    assert "endpoint_ids" in params
    assert "spec_name" in params
    assert "ctx" not in params


def test_info_cmd_is_click_command() -> None:
    """info_cmd is a Click command 'info' with a --spec option and a variadic endpoint-ids argument."""
    assert info_cmd.name == "info"

    param_names = {p.name for p in info_cmd.params}
    assert {"spec_name", "endpoint_ids"} <= param_names
    assert "ctx" not in param_names

    all_opts = {opt for p in info_cmd.params for opt in p.opts}
    assert "--spec" in all_opts

    # The endpoint-id filter is a variadic positional argument (nargs=-1)
    endpoint_arg = next(p for p in info_cmd.params if p.name == "endpoint_ids")
    assert isinstance(endpoint_arg, click.Argument)
    assert endpoint_arg.nargs == -1


# Logic tests ------------------------------------------------------------------


def test_run_info_returns_json_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info should print JSON object with Method in lower case."""
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
      parameters:
        - name: verbose
          in: query
          schema:
            type: boolean
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

    run_info(["clients_startup_get"])

    parsed = json.loads(capsys.readouterr().out)
    assert isinstance(parsed, dict)
    assert set(parsed.keys()) == {"Method", "Path", "Request", "Response", "QueryParams", "Description"}
    assert parsed["Method"] == "get"
    assert parsed["Path"] == "/clients/startup"
    assert parsed["QueryParams"]["verbose"]["type"] == "boolean"


def test_run_info_raises_when_endpoint_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_info should raise ClickException when endpoint_id not found."""
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
        run_info(["nonexistent_id"])
    assert "endpoint not found: nonexistent_id" in str(exc_info.value)


def test_run_info_handles_collision_across_specs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info should return JSON array when endpoint_id matches multiple specs."""
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
      description: Get startup info from client spec
      responses:
        '200':
          description: Success
"""
    )
    (spec_dir / "server.yaml").write_text(
        """
openapi: 3.0.0
info:
  title: Server API
  version: 1.0.0
paths:
  /clients/startup:
    get:
      description: Get startup info from server spec
      responses:
        '200':
          description: Success
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

    run_info(["clients_startup_get"])

    parsed = json.loads(capsys.readouterr().out)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert all(ep["Method"] == "get" for ep in parsed)


def test_run_info_filters_by_spec_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info should only search in specified spec when spec_name provided."""
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
      description: Get startup from client
      responses:
        '200':
          description: Success
"""
    )
    (spec_dir / "server.yaml").write_text(
        """
openapi: 3.0.0
info:
  title: Server API
  version: 1.0.0
paths:
  /clients/startup:
    get:
      description: Get startup from server
      responses:
        '200':
          description: Success
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

    run_info(["clients_startup_get"], spec_name="client")

    parsed = json.loads(capsys.readouterr().out)
    assert isinstance(parsed, dict)
    assert parsed["Description"] == "Get startup from client"


# Click binding ---------------------------------------------------------------


def test_info_cmd_binds_endpoint_ids_and_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """info_cmd should bind the positional endpoint-ids and the --spec option, then delegate to run_info."""
    from click.testing import CliRunner

    monkeypatch.chdir(tmp_path)

    captured: dict = {}

    def fake_run_info(endpoint_ids, spec_name):
        captured["endpoint_ids"] = endpoint_ids
        captured["spec_name"] = spec_name

    monkeypatch.setattr("goga_tool_pybuggy.commands.info.info.run_info", fake_run_info)

    # Options precede the variadic positional endpoint-ids (click parses options before the variadic tail)
    result = CliRunner().invoke(info_cmd, ["--spec", "client", "id1", "id2"])

    assert result.exit_code == 0
    assert captured == {"spec_name": "client", "endpoint_ids": ["id1", "id2"]}

    # Without positional ids the variadic argument is empty → None (no filter)
    captured.clear()
    result = CliRunner().invoke(info_cmd, ["--spec", "client"])
    assert result.exit_code == 0
    assert captured == {"spec_name": "client", "endpoint_ids": None}


# Endpoint-id filter tests -----------------------------------------------------


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


def test_run_info_filters_to_single_endpoint_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info should print only the endpoint whose id is in endpoint_ids."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    run_info(["clients_startup_get"])

    parsed = json.loads(capsys.readouterr().out)
    assert isinstance(parsed, dict)
    assert parsed["Path"] == "/clients/startup"


def test_run_info_filters_to_multiple_endpoint_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info should print every endpoint whose id is in endpoint_ids (as a JSON array)."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    run_info(["clients_startup_get", "health_get"])

    parsed = json.loads(capsys.readouterr().out)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert {ep["Path"] for ep in parsed} == {"/clients/startup", "/health"}


def test_run_info_empty_endpoint_ids_shows_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info with an empty endpoint_ids list should print all endpoints (no filter)."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    run_info([])

    parsed = json.loads(capsys.readouterr().out)
    assert isinstance(parsed, list)
    assert len(parsed) == 2


def test_run_info_no_endpoint_ids_shows_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info with no endpoint_ids (None default) should print all endpoints (no filter)."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    run_info()

    parsed = json.loads(capsys.readouterr().out)
    assert isinstance(parsed, list)
    assert len(parsed) == 2


def test_run_info_raises_for_unknown_endpoint_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info should raise ClickException for an unknown endpoint id and print nothing."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    with pytest.raises(click.ClickException) as exc:
        run_info(["does_not_exist_get"])

    assert "endpoint not found: does_not_exist_get" in str(exc.value)
    # Read-only + validate-before-print: nothing was written to stdout
    assert capsys.readouterr().out == ""


def test_run_info_unknown_ids_message_sorted_and_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_info should list every missing id (sorted) in the ClickException message."""
    _two_endpoint_spec(tmp_path, monkeypatch)

    with pytest.raises(click.ClickException) as exc:
        run_info(["zebra_get", "alpha_get"])

    msg = str(exc.value)
    assert "alpha_get" in msg
    assert "zebra_get" in msg
    # Sorted order within the comma-joined list
    assert msg.index("alpha_get") < msg.index("zebra_get")


def test_run_info_finds_endpoint_id_across_specs_without_spec_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """run_info should find an endpoint id in any spec when spec_name is not set."""
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

    run_info(["health_get"])

    parsed = json.loads(capsys.readouterr().out)
    assert isinstance(parsed, dict)
    assert parsed["Path"] == "/health"


def test_run_info_raises_when_endpoint_id_absent_from_selected_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_info with spec_name should raise when the endpoint id lives only in another spec."""
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
        run_info(["health_get"], spec_name="shop")
    assert "endpoint not found: health_get" in str(exc.value)
