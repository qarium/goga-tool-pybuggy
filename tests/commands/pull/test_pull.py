"""Contract and logic tests for run_pull handler."""

import logging
import shutil
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from goga_tool_pybuggy.commands.pull import run_pull

CONFIG_PATH_ATTR = "goga_tool_pybuggy.config.storage.CONFIG_PATH"


def test_run_pull_importable_from_facade() -> None:
    """run_pull should be importable from goga_tool_pybuggy.commands.pull facade."""
    from goga_tool_pybuggy.commands.pull import run_pull as imported

    assert imported is run_pull


def test_run_pull_signature() -> None:
    """run_pull should expose spec_name and ref params, with no ctx."""
    params = run_pull.__code__.co_varnames[: run_pull.__code__.co_argcount]

    assert "spec_name" in params
    assert "ref" in params
    assert "ctx" not in params


# Logic tests


def test_run_pull_copies_spec_from_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should clone repo and copy spec file to destination."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    clone_root = tmp_path / "clone"
    clone_root.mkdir()
    (clone_root / "specs").mkdir()
    (clone_root / "specs" / "client.yaml").write_text("spec content here")

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        run_pull(None)

    dest_file = tmp_path / ".specs" / "client.yaml"
    assert dest_file.exists()
    assert dest_file.read_text() == "spec content here"

    # Idempotent: run again overwrites
    (clone_root / "specs" / "client.yaml").write_text("updated content")
    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone2:
        mock_clone2.return_value.__enter__.return_value = clone_root
        run_pull(None)
    assert dest_file.read_text() == "updated content"


def test_run_pull_copies_spec_directory_from_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should handle directory copies from clone."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client
    git:
      url: https://example.com/repo.git
      location: specs/client
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    clone_root = tmp_path / "clone"
    clone_root.mkdir()
    (clone_root / "specs").mkdir()
    client_dir = clone_root / "specs" / "client"
    client_dir.mkdir()
    (client_dir / "openapi.yaml").write_text("dir content")

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        run_pull(None)

    dest_dir = tmp_path / ".specs" / "client"
    assert dest_dir.exists()
    assert (dest_dir / "openapi.yaml").read_text() == "dir content"


def test_run_pull_raises_on_missing_repo_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should raise ClickException when path not found in repo."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: nonexistent.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    clone_root = tmp_path / "clone"
    clone_root.mkdir()

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)

        with pytest.raises(click.ClickException) as exc_info:
            run_pull(None)
        assert "spec path not found in repo" in str(exc_info.value)


def test_run_pull_skips_local_only_spec_silently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """run_pull silently skips specs without a git field — no file pulled, no warning."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  local_spec:
    type: openapi
    location: .specs/local.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    with caplog.at_level(logging.WARNING):
        run_pull(None)

    # the local-only spec is skipped silently: nothing is pulled ...
    assert not (tmp_path / ".specs" / "local.yaml").exists()
    # ... and no warning (or higher) is logged
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_run_pull_raises_on_spec_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should raise ClickException when spec_name not found in config."""
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
        run_pull("nonexistent_spec")
    assert "spec not found: nonexistent_spec" in str(exc_info.value)


def test_run_pull_handles_git_clone_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should map GitCommandError to ClickException."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    from git import GitCommandError

    with patch("goga_tool_pybuggy.commands.pull.pull.Repo.clone_from") as mock_clone:
        mock_clone.side_effect = GitCommandError("clone", "failed to clone")

        with pytest.raises(click.ClickException) as exc_info:
            run_pull(None)
        assert "git clone failed" in str(exc_info.value)


def test_run_pull_filters_by_spec_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should only pull specified spec when spec_name provided."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
  server:
    type: openapi
    location: .specs/server.yaml
    git:
      url: https://example.com/repo2.git
      location: specs/server.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    clone1 = tmp_path / "clone1"
    clone1.mkdir()
    (clone1 / "specs").mkdir()
    (clone1 / "specs" / "client.yaml").write_text("client spec")

    clone2 = tmp_path / "clone2"
    clone2.mkdir()
    (clone2 / "specs").mkdir()
    (clone2 / "specs" / "server.yaml").write_text("server spec")

    from contextlib import contextmanager

    @contextmanager
    def mock_clone_func(url, ref=None):
        if "repo.git" in str(url):
            yield str(clone1)
        else:
            yield str(clone2)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.side_effect = mock_clone_func
        run_pull("client")

    assert (tmp_path / ".specs" / "client.yaml").exists()
    assert not (tmp_path / ".specs" / "server.yaml").exists()


def test_run_pull_clones_specified_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should clone the configured git ref via ``branch=<ref>``."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
      ref: v1
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    fixture = tmp_path / "fixture"
    (fixture / "specs").mkdir(parents=True)
    (fixture / "specs" / "client.yaml").write_text("spec content")

    def fake_clone(url, to_path, depth, branch):
        target = Path(to_path) / "specs"
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture / "specs" / "client.yaml", target / "client.yaml")

    with patch("goga_tool_pybuggy.commands.pull.pull.Repo.clone_from") as mock_clone:
        mock_clone.side_effect = fake_clone
        run_pull(None)

    assert mock_clone.call_count == 1
    _, kwargs = mock_clone.call_args
    assert kwargs.get("depth") == 1
    assert kwargs.get("branch") == "v1"
    assert (tmp_path / ".specs" / "client.yaml").read_text() == "spec content"


def test_run_pull_clones_default_branch_when_no_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull passes ``branch=None`` (no --branch) when git.ref is absent."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    fixture = tmp_path / "fixture"
    (fixture / "specs").mkdir(parents=True)
    (fixture / "specs" / "client.yaml").write_text("spec content")

    def fake_clone(url, to_path, depth, branch):
        target = Path(to_path) / "specs"
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture / "specs" / "client.yaml", target / "client.yaml")

    with patch("goga_tool_pybuggy.commands.pull.pull.Repo.clone_from") as mock_clone:
        mock_clone.side_effect = fake_clone
        run_pull(None)

    assert mock_clone.call_count == 1
    _, kwargs = mock_clone.call_args
    assert kwargs.get("depth") == 1
    assert kwargs.get("branch") is None


def _write_client_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ref: str | None) -> Path:
    """Write a one-spec config (with/without git.ref) and point CONFIG_PATH at it."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    ref_line = f"      ref: {ref}\n" if ref is not None else ""
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
"""
        + ref_line
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    return config_path


def _fake_clone_root(tmp_path: Path) -> Path:
    """Build a pseudo-clone dir with the spec file that clone_repo would yield."""
    clone_root = tmp_path / "clone"
    (clone_root / "specs").mkdir(parents=True)
    (clone_root / "specs" / "client.yaml").write_text("spec content")
    return clone_root


def test_run_pull_cli_ref_overrides_config_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should pass the CLI ``ref`` to clone_repo when both it and git.ref are set."""
    _write_client_config(tmp_path, monkeypatch, ref="v1")
    clone_root = _fake_clone_root(tmp_path)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        run_pull(None, ref="v2")

    assert mock_clone.call_count == 1
    args, _ = mock_clone.call_args
    # clone_repo(url, ref) — positional ref is the effective ref (CLI wins over config).
    assert args[1] == "v2"


def test_run_pull_cli_ref_overrides_absent_config_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_pull should pass the CLI ``ref`` to clone_repo when git.ref is absent."""
    _write_client_config(tmp_path, monkeypatch, ref=None)
    clone_root = _fake_clone_root(tmp_path)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        run_pull(None, ref="v2")

    assert mock_clone.call_count == 1
    args, _ = mock_clone.call_args
    assert args[1] == "v2"


def test_run_pull_ref_none_uses_config_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_pull should fall back to git.ref when the CLI ``ref`` is None (backward compatible)."""
    _write_client_config(tmp_path, monkeypatch, ref="v1")
    clone_root = _fake_clone_root(tmp_path)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        run_pull(None)  # ref defaults to None

    assert mock_clone.call_count == 1
    args, _ = mock_clone.call_args
    assert args[1] == "v1"


def test_run_pull_ref_none_uses_default_branch_when_config_ref_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_pull should pass None (default branch) when neither CLI ref nor git.ref is set."""
    _write_client_config(tmp_path, monkeypatch, ref=None)
    clone_root = _fake_clone_root(tmp_path)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        run_pull(None)

    assert mock_clone.call_count == 1
    args, _ = mock_clone.call_args
    assert args[1] is None


# Per-spec ref tests


def _write_two_spec_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a two-spec config (client+server, distinct repos, no git.ref) and point CONFIG_PATH at it."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
  server:
    type: openapi
    location: .specs/server.yaml
    git:
      url: https://example.com/repo2.git
      location: specs/server.yaml
"""
    )
    monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)

    return config_path


def _two_spec_clone_roots(tmp_path: Path) -> tuple:
    """Build pseudo-clone dirs for the two-spec config, returning (clone1, clone2)."""
    clone1 = tmp_path / "clone1"
    (clone1 / "specs").mkdir(parents=True)
    (clone1 / "specs" / "client.yaml").write_text("client")

    clone2 = tmp_path / "clone2"
    (clone2 / "specs").mkdir(parents=True)
    (clone2 / "specs" / "server.yaml").write_text("server")

    return clone1, clone2


def test_run_pull_applies_per_spec_refs_in_one_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_pull applies a distinct per-spec ref to each spec in a single call."""
    _write_two_spec_config(tmp_path, monkeypatch)
    clone1, clone2 = _two_spec_clone_roots(tmp_path)

    seen: dict = {}

    from contextlib import contextmanager

    @contextmanager
    def mock_clone(url, ref=None):
        seen[url] = ref
        yield str(clone1) if "repo.git" in str(url) else str(clone2)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone_repo:
        mock_clone_repo.side_effect = mock_clone
        run_pull(None, ref=(("client", "v1"), ("server", "v2")))

    assert seen["https://example.com/repo.git"] == "v1"
    assert seen["https://example.com/repo2.git"] == "v2"
    assert (tmp_path / ".specs" / "client.yaml").read_text() == "client"
    assert (tmp_path / ".specs" / "server.yaml").read_text() == "server"


def test_run_pull_per_spec_ref_overrides_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per-spec ref overrides the global ref for that spec only; others use the global."""
    _write_two_spec_config(tmp_path, monkeypatch)
    clone1, clone2 = _two_spec_clone_roots(tmp_path)

    seen: dict = {}

    from contextlib import contextmanager

    @contextmanager
    def mock_clone(url, ref=None):
        seen[url] = ref
        yield str(clone1) if "repo.git" in str(url) else str(clone2)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone_repo:
        mock_clone_repo.side_effect = mock_clone
        run_pull(None, ref=("v9", ("server", "v3")))

    assert seen["https://example.com/repo.git"] == "v9"
    assert seen["https://example.com/repo2.git"] == "v3"


def test_run_pull_per_spec_ref_overrides_config_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per-spec ref wins over the configured git.ref for that spec."""
    _write_client_config(tmp_path, monkeypatch, ref="v1")
    clone_root = _fake_clone_root(tmp_path)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        run_pull(None, ref=(("client", "v2"),))

    assert mock_clone.call_count == 1
    args, _ = mock_clone.call_args
    assert args[1] == "v2"


def test_run_pull_raises_on_unknown_per_spec_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per-spec ref naming a spec absent from the configuration raises ClickException."""
    _write_client_config(tmp_path, monkeypatch, ref="v1")
    _fake_clone_root(tmp_path)

    with pytest.raises(click.ClickException) as exc_info:
        run_pull(None, ref=(("nonexistent", "v2"),))

    assert "unknown spec in --ref" in str(exc_info.value)
    assert "nonexistent" in str(exc_info.value)


def test_run_pull_unknown_per_spec_ref_lists_all_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Multiple unknown per-spec refs are all reported in the ClickException."""
    _write_client_config(tmp_path, monkeypatch, ref="v1")
    _fake_clone_root(tmp_path)

    with pytest.raises(click.ClickException) as exc_info:
        run_pull(None, ref=(("zeta", "v2"), ("alpha", "v3")))

    msg = str(exc_info.value)
    assert "alpha" in msg
    assert "zeta" in msg


def test_run_pull_per_spec_ref_in_config_but_filtered_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per-spec ref for a spec present in config but filtered out by --spec is accepted."""
    _write_two_spec_config(tmp_path, monkeypatch)
    clone1, _ = _two_spec_clone_roots(tmp_path)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone1)
        # client is pulled (--spec client); server is in config but filtered — no error.
        run_pull("client", ref=(("server", "v3"),))

    assert mock_clone.call_count == 1


def test_run_pull_global_ref_as_str_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain string ref (direct handler call) remains a global override — backward compatible."""
    _write_two_spec_config(tmp_path, monkeypatch)
    clone1, clone2 = _two_spec_clone_roots(tmp_path)

    seen: dict = {}

    from contextlib import contextmanager

    @contextmanager
    def mock_clone(url, ref=None):
        seen[url] = ref
        yield str(clone1) if "repo.git" in str(url) else str(clone2)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone_repo:
        mock_clone_repo.side_effect = mock_clone
        run_pull(None, ref="v7")

    assert seen["https://example.com/repo.git"] == "v7"
    assert seen["https://example.com/repo2.git"] == "v7"


# _effective_ref precedence tests.
#
# PYBUGGY_REF is no longer read here — it is bound to ``--ref`` via click's envvar and
# reaches ``_effective_ref`` through ``global_ref`` (see the pull_cmd envvar tests below).
# These tests cover the pure precedence: per-spec > global > git.ref > None.


def test_effective_ref_per_spec_wins() -> None:
    """A per-spec ref overrides both the global ref and git.ref."""
    from goga_tool_pybuggy.commands.pull.pull import _effective_ref

    assert _effective_ref("client", git_ref="main", global_ref="v3", per_spec={"client": "v1"}) == "v1"


def test_effective_ref_global_wins_over_git_ref() -> None:
    """A global ref overrides the configured git.ref."""
    from goga_tool_pybuggy.commands.pull.pull import _effective_ref

    assert _effective_ref("client", git_ref="main", global_ref="v3", per_spec={}) == "v3"


def test_effective_ref_falls_back_to_git_ref() -> None:
    """With no per-spec or global override, the configured git.ref is used."""
    from goga_tool_pybuggy.commands.pull.pull import _effective_ref

    assert _effective_ref("client", git_ref="main", global_ref=None, per_spec={}) == "main"


def test_effective_ref_none_when_no_ref() -> None:
    """With no override and no git.ref, the effective ref is None (remote default branch)."""
    from goga_tool_pybuggy.commands.pull.pull import _effective_ref

    assert _effective_ref("client", git_ref=None, global_ref=None, per_spec={}) is None


def test_effective_ref_ignores_pybuggy_ref_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """_effective_ref no longer reads PYBUGGY_REF (now resolved at the click layer).

    Regression guard for the redesign: setting PYBUGGY_REF must NOT influence
    ``_effective_ref`` — it falls through to ``git.ref``.
    """
    from goga_tool_pybuggy.commands.pull.pull import _effective_ref

    monkeypatch.setenv("PYBUGGY_REF", "v2")
    assert _effective_ref("client", git_ref="main", global_ref=None, per_spec={}) == "main"


# PYBUGGY_REF is bound to --ref via click's envvar (resolved at the click layer).


def test_pull_cmd_reads_pybuggy_ref_from_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    """pull_cmd resolves PYBUGGY_REF into the --ref tuple via click's envvar."""
    from click.testing import CliRunner
    from goga_tool_pybuggy.commands.pull import pull_cmd

    captured: dict = {}

    def fake_run(spec_name, ref):
        captured["ref"] = ref

    monkeypatch.setattr("goga_tool_pybuggy.commands.pull.pull.run_pull", fake_run)
    monkeypatch.setenv("PYBUGGY_REF", "v2")

    result = CliRunner().invoke(pull_cmd, [])

    assert result.exit_code == 0, result.output
    assert captured["ref"] == ("v2",)


def test_pull_cmd_explicit_ref_overrides_pybuggy_ref_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit --ref overrides PYBUGGY_REF entirely (click envvar semantics)."""
    from click.testing import CliRunner
    from goga_tool_pybuggy.commands.pull import pull_cmd

    captured: dict = {}

    def fake_run(spec_name, ref):
        captured["ref"] = ref

    monkeypatch.setattr("goga_tool_pybuggy.commands.pull.pull.run_pull", fake_run)
    monkeypatch.setenv("PYBUGGY_REF", "v2")

    result = CliRunner().invoke(pull_cmd, ["--ref", "X"])

    assert result.exit_code == 0, result.output
    assert captured["ref"] == ("X",)


def test_pull_cmd_empty_pybuggy_ref_envvar_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty PYBUGGY_REF is treated as unset (no --ref override)."""
    from click.testing import CliRunner
    from goga_tool_pybuggy.commands.pull import pull_cmd

    captured: dict = {}

    def fake_run(spec_name, ref):
        captured["ref"] = ref

    monkeypatch.setattr("goga_tool_pybuggy.commands.pull.pull.run_pull", fake_run)
    monkeypatch.setenv("PYBUGGY_REF", "")

    result = CliRunner().invoke(pull_cmd, [])

    assert result.exit_code == 0, result.output
    assert captured["ref"] == ()


# Integration: PYBUGGY_REF (via the --ref envvar) flows into the clone ref (CLI level).


def test_pull_cmd_pybuggy_ref_envvar_used_as_clone_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PYBUGGY_REF, read via the --ref envvar, becomes the clone ref.

    End-to-end at the click layer: with no ``--ref`` and no configured ``git.ref``, the
    ``PYBUGGY_REF`` set in the environment is resolved by click's envvar into the
    ``--ref`` tuple and reaches ``clone_repo`` as the effective ref. Only the git-clone
    boundary is mocked.
    """
    from click.testing import CliRunner
    from goga_tool_pybuggy.commands.pull import pull_cmd

    monkeypatch.setenv("PYBUGGY_REF", "v2")
    _write_client_config(tmp_path, monkeypatch, ref=None)
    clone_root = _fake_clone_root(tmp_path)

    with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:
        mock_clone.return_value.__enter__.return_value = str(clone_root)
        result = CliRunner().invoke(pull_cmd, ["--spec", "client"])

    assert result.exit_code == 0, result.output
    assert mock_clone.call_count == 1
    args, _ = mock_clone.call_args
    # clone_repo(url, ref) — positional ref is the effective ref from PYBUGGY_REF.
    assert args[1] == "v2"


# SmartParam parsing tests


def test_smart_param_none_and_empty_yield_none() -> None:
    """SmartParam should map None/empty to None (no override)."""
    from goga_tool_pybuggy.commands.pull.pull import SmartParam

    smart = SmartParam()
    assert smart.convert(None, None, None) is None
    assert smart.convert("", None, None) is None


def test_smart_param_plain_value_is_global_ref() -> None:
    """SmartParam should return a colon-free value unchanged (global ref)."""
    from goga_tool_pybuggy.commands.pull.pull import SmartParam

    assert SmartParam().convert("v2", None, None) == "v2"


def test_smart_param_colon_value_is_per_spec_pair() -> None:
    """SmartParam should split 'NAME:REF' into a (name, ref) per-spec pair."""
    from goga_tool_pybuggy.commands.pull.pull import SmartParam

    assert SmartParam().convert("client:v2", None, None) == ("client", "v2")


def test_smart_param_splits_only_on_first_colon() -> None:
    """SmartParam should keep extra colons in the ref value (split on first ':' only)."""
    from goga_tool_pybuggy.commands.pull.pull import SmartParam

    assert SmartParam().convert("client:feat:x", None, None) == ("client", "feat:x")


# CLI wiring test


def test_pull_cmd_collects_multiple_refs_as_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    """pull_cmd should collect repeated --ref values (parsed by SmartParam) into one tuple."""
    from click.testing import CliRunner
    from goga_tool_pybuggy.commands.pull import pull_cmd

    captured: dict = {}

    def fake_run(spec_name, ref):
        captured["spec_name"] = spec_name
        captured["ref"] = ref

    monkeypatch.setattr("goga_tool_pybuggy.commands.pull.pull.run_pull", fake_run)

    runner = CliRunner()
    result = runner.invoke(pull_cmd, ["--ref", "client:v1", "--ref", "server:v2", "--ref", "v9"])

    assert result.exit_code == 0, result.output
    assert captured["spec_name"] is None
    assert captured["ref"] == (("client", "v1"), ("server", "v2"), "v9")
