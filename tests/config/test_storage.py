"""Contract tests for load_config routine."""

import pathlib
import typing

import pydantic
import pytest
import yaml
from pybuggy.config import Config, load_config


def test_load_config_importable_from_facade() -> None:
    """Contract test: load_config is importable from pybuggy.config facade."""
    assert callable(load_config)


def test_load_config_signature() -> None:
    """Contract test: load_config has signature (path: Optional[Path] = None) -> Config."""
    import inspect

    sig = inspect.signature(load_config)
    params = list(sig.parameters.keys())

    assert params == ["path"]
    assert sig.parameters["path"].annotation == typing.Optional[pathlib.Path]
    assert sig.parameters["path"].default is None
    assert sig.return_annotation == Config


def test_load_config_parses_valid_config(tmp_path: pathlib.Path) -> None:
    """Logic test: valid YAML with nested GitEntry is parsed correctly."""
    config_content = """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
"""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content, encoding="utf-8")

    config = load_config(config_file)

    assert "client" in config.specs
    assert config.specs["client"].location == ".specs/client.yaml"
    assert config.specs["client"].type == "openapi"
    assert config.specs["client"].git is not None
    assert config.specs["client"].git.url == "https://example.com/repo.git"
    assert config.specs["client"].git.location == "specs/client.yaml"


def test_load_config_rejects_unknown_spec_type(tmp_path: pathlib.Path) -> None:
    """Logic test: invalid spec type (raml) raises ValidationError."""
    config_content = """
specs:
  x:
    type: raml
    location: y.yaml
"""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content, encoding="utf-8")

    with pytest.raises(pydantic.ValidationError):
        load_config(config_file)


def test_load_config_propagates_file_not_found(tmp_path: pathlib.Path) -> None:
    """Logic test: missing config file raises FileNotFoundError."""
    nonexistent = tmp_path / "nonexistent.yml"

    with pytest.raises(FileNotFoundError):
        load_config(nonexistent)


def test_load_config_accepts_local_only_spec(tmp_path: pathlib.Path) -> None:
    """Logic test: spec without git field (local-only) is parsed correctly."""
    config_content = """
specs:
  local:
    type: swagger
    location: specs/local.yaml
"""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content, encoding="utf-8")

    config = load_config(config_file)

    assert config.specs["local"].git is None


def test_load_config_multiple_specs(tmp_path: pathlib.Path) -> None:
    """Logic test: multiple specs in config are parsed correctly."""
    config_content = """
specs:
  client:
    type: openapi
    location: specs/client.yaml
  server:
    type: swagger
    location: specs/server.yaml
    git:
      url: https://github.com/example/server.git
      location: openapi.yaml
"""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content, encoding="utf-8")

    config = load_config(config_file)

    assert len(config.specs) == 2
    assert "client" in config.specs
    assert "server" in config.specs
    assert config.specs["client"].git is None
    assert config.specs["server"].git is not None


def test_load_config_handles_utf8_encoding(tmp_path: pathlib.Path) -> None:
    """Logic test: UTF-8 encoded file (with comments) is parsed correctly."""
    config_content = """
# Comment with unicode: пример
specs:
  test:
    type: openapi
    location: тест.yaml
"""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content, encoding="utf-8")

    config = load_config(config_file)

    assert config.specs["test"].location == "тест.yaml"


def test_load_config_rejects_invalid_yaml(tmp_path: pathlib.Path) -> None:
    """Logic test: malformed YAML raises an error (yaml.YAMLError)."""
    config_content = """
specs:
  - invalid
    yaml:
"""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content, encoding="utf-8")

    # yaml.YAMLError is a subclass of ValueError, but YAMLError itself may be raised
    with pytest.raises((yaml.YAMLError, ValueError)):
        load_config(config_file)
