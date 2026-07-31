"""End-to-end integration tests for the pybuggy CLI.

Tests the full CLI flow from entry point through subcommands. The config path is
static (``pybuggy.config.CONFIG_PATH``); tests point it at a local ``config.yml``
via monkeypatch and run inside an isolated filesystem.
"""

import json
import pathlib

import pytest
from click.testing import CliRunner
from pybuggy import main

CONFIG_PATH_ATTR = "pybuggy.config.storage.CONFIG_PATH"

_CLIENT_SPEC = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /clients/{id}:
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: string
    get:
      operationId: getClient
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: object
    delete:
      operationId: deleteClient
      responses:
        '204':
          description: No content
  /clients/startup:
    get:
      operationId: listClients
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: array
"""


def _write_config(specs_body: str) -> pathlib.Path:
    """Write a config.yml (relative path) in the current cwd and return it."""
    config_file = pathlib.Path("config.yml")
    config_file.write_text(f"specs:\n{specs_body}")

    return config_file


def test_cli_help_shows_endpoint_group() -> None:
    """Verify that --help shows the endpoint subgroup."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "endpoint" in result.output


def test_endpoint_group_help() -> None:
    """Verify that endpoint --help shows available subcommands."""
    runner = CliRunner()
    result = runner.invoke(main, ["endpoint", "--help"])

    assert result.exit_code == 0
    assert "pull" in result.output
    assert "list" in result.output
    assert "info" in result.output


def test_endpoint_group_help_includes_generate() -> None:
    """Verify that endpoint --help lists the generate subcommand.

    The facade ``CODEMANIFEST`` declares that ``generate_cmd`` is registered on
    the ``endpoint`` subgroup (``main()`` Algorithm step 3). This regression
    test fails fast if the registration is ever dropped.
    """
    runner = CliRunner()
    result = runner.invoke(main, ["endpoint", "--help"])

    assert result.exit_code == 0
    assert "generate" in result.output

    # Cross-check the group directly: ``generate`` must be a registered command.
    assert "generate" in main.commands["endpoint"].commands


def test_endpoint_list_with_real_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test endpoint list with a real minimal spec file."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        spec_file = pathlib.Path("specs") / "test_api.yaml"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(_CLIENT_SPEC)

        config_file = _write_config("  test:\n    type: openapi\n    location: specs/test_api.yaml\n")
        monkeypatch.setattr(CONFIG_PATH_ATTR, config_file)

        result = runner.invoke(main, ["endpoint", "list"])

        assert result.exit_code == 0
        assert "test (specs/test_api.yaml)" in result.output
        assert "clients_id_get" in result.output
        assert "[GET]" in result.output
        assert "clients_id_delete" in result.output
        assert "[DELETE]" in result.output
        assert "clients_startup_get" in result.output


def test_endpoint_info_with_real_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test endpoint info with a real minimal spec file."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        spec_file = pathlib.Path("specs") / "test_api.yaml"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(
            """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /clients/{id}:
    get:
      operationId: getClient
      description: Get a client by ID
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
        - name: verbose
          in: query
          schema:
            type: boolean
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: object
                properties:
                  name:
                    type: string
"""
        )

        config_file = _write_config("  test:\n    type: openapi\n    location: specs/test_api.yaml\n")
        monkeypatch.setattr(CONFIG_PATH_ATTR, config_file)

        result = runner.invoke(main, ["endpoint", "info", "clients_id_get"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["Method"] == "get"
        assert data["Path"] == "/clients/:id"
        assert data["Description"] == "Get a client by ID"
        assert "verbose" in data["QueryParams"]


def test_endpoint_info_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test endpoint info when endpoint_id is not found."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        spec_file = pathlib.Path("specs") / "test_api.yaml"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(
            """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /clients:
    get:
      responses:
        '200':
          description: Successful response
"""
        )

        config_file = _write_config("  test:\n    type: openapi\n    location: specs/test_api.yaml\n")
        monkeypatch.setattr(CONFIG_PATH_ATTR, config_file)

        result = runner.invoke(main, ["endpoint", "info", "nonexistent_id"])

        assert result.exit_code != 0
        assert "endpoint not found" in result.output.lower()


def test_endpoint_pull_command_structure() -> None:
    """Test that endpoint pull command has correct structure."""
    runner = CliRunner()

    result = runner.invoke(main, ["endpoint", "pull", "--help"])

    assert result.exit_code == 0
    assert "pull" in result.output.lower() or "Clone specs" in result.output


def test_endpoint_pull_exposes_ref_option() -> None:
    """Verify that endpoint pull --help lists the --ref override option."""
    runner = CliRunner()

    result = runner.invoke(main, ["endpoint", "pull", "--help"])

    assert result.exit_code == 0
    assert "--ref" in result.output
    assert "--spec" in result.output  # existing option still wired


def test_endpoint_list_with_spec_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test endpoint list with --spec filter."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        specs_dir = pathlib.Path("specs")
        specs_dir.mkdir(parents=True, exist_ok=True)
        (specs_dir / "api1.yaml").write_text(
            """
openapi: 3.0.0
info:
  title: API 1
  version: 1.0.0
paths:
  /users:
    get:
      responses:
        '200':
          description: OK
"""
        )
        (specs_dir / "api2.yaml").write_text(
            """
openapi: 3.0.0
info:
  title: API 2
  version: 1.0.0
paths:
  /orders:
    get:
      responses:
        '200':
          description: OK
"""
        )

        config_file = _write_config(
            "  api1:\n    type: openapi\n    location: specs/api1.yaml\n"
            "  api2:\n    type: openapi\n    location: specs/api2.yaml\n"
        )
        monkeypatch.setattr(CONFIG_PATH_ATTR, config_file)

        result = runner.invoke(main, ["endpoint", "list", "--spec", "api1"])

        assert result.exit_code == 0
        assert "api1 (specs/api1.yaml)" in result.output
        assert "users_get" in result.output
        assert "api2" not in result.output.lower()


def test_endpoint_generate_scaffolds_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test endpoint generate scaffolds response schemas and an empty tests dir end-to-end.

    Drives the full chain ``main`` → ``endpoint_group`` → ``generate_cmd`` → ``run_generate``
    → ``load_config``/``load_spec``/``extract_endpoints`` → filesystem. Confirms that the
    ``-s/--spec`` option is wired through the facade and the scaffolded tree matches the contract.
    """
    runner = CliRunner()

    with runner.isolated_filesystem():
        spec_file = pathlib.Path("specs") / "t.yaml"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(
            """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /clients/startup:
    get:
      operationId: listClients
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
"""
        )

        config_file = _write_config("  t:\n    type: openapi\n    location: specs/t.yaml\n")
        monkeypatch.setattr(CONFIG_PATH_ATTR, config_file)

        result = runner.invoke(main, ["endpoint", "generate", "-s", "t"])

        assert result.exit_code == 0
        assert pathlib.Path("api/t/clients_startup_get/schemas/200.json").exists()
        assert pathlib.Path("api/t/clients_startup_get/schemas/404.json").exists()
        assert pathlib.Path("tests/t/clients_startup_get").is_dir()


def test_entry_point_pybuggy_main() -> None:
    """Verify that the entry point pybuggy:main is accessible."""
    import pybuggy

    assert callable(pybuggy.main)
    assert hasattr(pybuggy.main, "commands")
