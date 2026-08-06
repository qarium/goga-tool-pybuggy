"""Contract and logic tests for env loading (EnvContext + load_env)."""

import inspect
import os
from pathlib import Path

import click
import pytest

# Contract tests — facade surface and shapes.


def test_envcontext_importable_from_facade() -> None:
    """EnvContext should be importable from the goga_tool_pybuggy facade."""
    from goga_tool_pybuggy import EnvContext

    assert EnvContext is not None


def test_envcontext_is_pydantic_basemodel() -> None:
    """EnvContext should be a pydantic BaseModel subclass."""
    from goga_tool_pybuggy import EnvContext
    from pydantic import BaseModel

    assert issubclass(EnvContext, BaseModel)


def test_load_env_importable_from_facade() -> None:
    """load_env should be importable from the goga_tool_pybuggy facade."""
    from goga_tool_pybuggy import load_env

    assert callable(load_env)


def test_load_env_has_env_file_parameter() -> None:
    """load_env should take one positional arg named env_file and return an EnvContext."""
    from goga_tool_pybuggy import EnvContext, load_env

    sig = inspect.signature(load_env)
    params = sig.parameters
    assert "env_file" in params
    ctx = load_env(None)
    assert isinstance(ctx, EnvContext)


# Logic tests — behavior.


def test_env_context_defaults() -> None:
    """EnvContext() defaults: env_path=None, values={}, and a kw-only constructor."""
    from goga_tool_pybuggy import EnvContext

    ctx = EnvContext()
    assert ctx.env_path is None
    assert ctx.values == {}
    assert ctx.model_config.get("kw_only") is True


def test_load_env_explicit_file_applies_and_returns_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit --env-file is parsed, applied to os.environ, and returned in EnvContext."""
    from goga_tool_pybuggy import load_env

    env_file = tmp_path / ".env"
    env_file.write_text("PYBUGGY_REF=v2\nDEBUG=1\n")
    monkeypatch.delenv("PYBUGGY_REF", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.chdir(tmp_path)

    ctx = load_env(str(env_file))

    assert ctx.env_path is not None
    assert ctx.env_path.endswith(".env")
    assert ctx.values == {"PYBUGGY_REF": "v2", "DEBUG": "1"}
    assert os.environ["PYBUGGY_REF"] == "v2"
    assert os.environ["DEBUG"] == "1"


def test_load_env_explicit_missing_file_raises_clickexception(tmp_path: Path) -> None:
    """An explicit --env-file pointing at a missing file raises click.ClickException."""
    from goga_tool_pybuggy import load_env

    with pytest.raises(click.ClickException) as exc_info:
        load_env(str(tmp_path / "nope.env"))

    assert "env file not found" in str(exc_info.value)


def test_load_env_implicit_dotenv_absent_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An implicit .env absent in the CWD is silent: empty EnvContext, no os.environ change."""
    from goga_tool_pybuggy import load_env

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYBUGGY_REF", raising=False)

    ctx = load_env(None)

    assert ctx.env_path is None
    assert ctx.values == {}
    assert "PYBUGGY_REF" not in os.environ


def test_load_env_does_not_override_existing_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """override=False: an already-set env var is never overwritten by the file."""
    from goga_tool_pybuggy import load_env

    (tmp_path / ".env").write_text("PYBUGGY_REF=fromfile\n")
    monkeypatch.setenv("PYBUGGY_REF", "fromshell")
    monkeypatch.chdir(tmp_path)

    ctx = load_env(None)

    assert ctx.values == {"PYBUGGY_REF": "fromfile"}
    assert os.environ["PYBUGGY_REF"] == "fromshell"


def test_load_env_key_without_value_coerced_to_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """KEY= -> '' directly; a bare key -> '' via None->'' coercion; all values are str."""
    from goga_tool_pybuggy import load_env

    (tmp_path / ".env").write_text("EMPTY=\nBARE\nFULL=x\n")
    monkeypatch.chdir(tmp_path)

    ctx = load_env(None)

    assert ctx.values["EMPTY"] == ""
    assert ctx.values["BARE"] == ""
    assert ctx.values["FULL"] == "x"
    assert all(isinstance(v, str) for v in ctx.values.values())


def test_load_env_explicit_directory_raises_clickexception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit --env-file pointing at a directory raises click.ClickException."""
    from goga_tool_pybuggy import load_env

    (tmp_path / "subdir").mkdir()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(click.ClickException) as exc_info:
        load_env(str(tmp_path / "subdir"))

    assert "not a regular file" in str(exc_info.value)
