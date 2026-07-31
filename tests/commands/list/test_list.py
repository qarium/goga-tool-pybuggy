"""Contract and logic tests for run_list handler."""

from pathlib import Path

import click
import pytest
from goga_tool_pybuggy.commands.list import run_list

CONFIG_PATH_ATTR = "goga_tool_pybuggy.config.storage.CONFIG_PATH"


def test_run_list_importable_from_facade() -> None:
    """run_list should be importable from goga_tool_pybuggy.commands.list facade."""
    from goga_tool_pybuggy.commands.list import run_list as imported

    assert imported is run_list


def test_run_list_signature() -> None:
    """run_list should have signature (spec_name: Optional[str]) with no ctx."""
    params = run_list.__code__.co_varnames[: run_list.__code__.co_argcount]

    assert "spec_name" in params
    assert "ctx" not in params


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
