"""Contract and logic tests for the lifecycle post-install hook (install)."""

import getpass
import inspect
import logging
import subprocess

import pytest
from goga_tool_pybuggy.lifecycle import install as facade_install
from goga_tool_pybuggy.lifecycle.lifecycle import install

_NPM = "/usr/bin/npm"
_CLI = "/usr/local/bin/playwright-cli"


def _ok(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")


def _wire_happy_path(monkeypatch: pytest.MonkeyPatch, calls: list[list[str]]) -> None:
    """Wire the module for the happy path: fixed npm/cli resolution, a recording runner."""
    monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._find_npm", lambda: _NPM)
    monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._resolve_cli", lambda _npm: _CLI)

    def run(argv, **kwargs):
        calls.append(list(argv))
        return _ok(argv)

    monkeypatch.setattr(subprocess, "run", run)


class TestInstallContract:
    def test_facade_reexport_resolves_to_cell_entity(self) -> None:
        """The cell facade re-export should be the implementation entity, not a copy."""
        assert facade_install is install

    def test_signature_declares_keyword_capable_user(self) -> None:
        """The platform introspects the signature and injects the initiating user by name.

        A positional-only or **kwargs drift silently stops the injection — this pins the
        exact contract goga checks (goga/commands/install/hook.py).
        """
        parameter = inspect.signature(install).parameters["user"]

        assert parameter.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        assert parameter.default is None

    def test_install_callable_with_no_arguments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A manual recovery call without arguments should work (npm absent → warning skip)."""
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._find_npm", lambda: None)

        install()  # no exception


class TestInstallLogic:
    def test_without_npm_warns_and_skips_subprocess(self, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
        """npm absent from PATH is a warning and a quiet skip — no subprocess call."""
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._find_npm", lambda: None)

        def forbidden(*args, **kwargs):
            raise AssertionError("subprocess.run must not run when npm is absent")

        monkeypatch.setattr(subprocess, "run", forbidden)

        with caplog.at_level(logging.WARNING):
            install()

        assert "npm not found; playwright cli install skipped" in caplog.text
        warning = next(record for record in caplog.records if record.levelno == logging.WARNING)
        assert warning.requirement == "npm"

    def test_runs_npm_then_skills_in_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The happy path runs exactly the npm install then the skills step, in order."""
        calls: list[list[str]] = []
        _wire_happy_path(monkeypatch, calls)

        install()

        assert calls == [
            [_NPM, "install", "-g", "@playwright/cli"],
            [_CLI, "install", "--skills", "--global"],
        ]

    def test_npm_failure_maps_to_runtime_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failing npm step raises RuntimeError carrying npm's own stderr."""
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._find_npm", lambda: _NPM)

        def failing(argv, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=1, cmd=argv, stderr="EACCES: permission denied, mkdir '/usr/lib/node_modules'"
            )

        monkeypatch.setattr(subprocess, "run", failing)

        with pytest.raises(RuntimeError, match=r"npm install -g @playwright/cli failed.*EACCES"):
            install()

    def test_skills_failure_maps_to_runtime_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failing skills step raises RuntimeError carrying its stderr."""
        calls: list[list[str]] = []
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._find_npm", lambda: _NPM)
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._resolve_cli", lambda _npm: _CLI)

        def run(argv, **kwargs):
            calls.append(list(argv))
            if len(calls) == 2:
                raise subprocess.CalledProcessError(returncode=1, cmd=argv, stderr="skills write failed")
            return _ok(argv)

        monkeypatch.setattr(subprocess, "run", run)

        with pytest.raises(RuntimeError, match=r"playwright-cli install --skills --global failed.*skills write failed"):
            install()

    def test_skills_direct_when_user_matches_current(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """user equal to the current user (plain install, Docker root) runs skills directly."""
        calls: list[list[str]] = []
        _wire_happy_path(monkeypatch, calls)
        monkeypatch.setattr(getpass, "getuser", lambda: "root")

        install(user="root")

        assert calls[1] == [_CLI, "install", "--skills", "--global"]

    def test_skills_direct_when_user_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A None user (manual no-arg call) runs skills directly."""
        calls: list[list[str]] = []
        _wire_happy_path(monkeypatch, calls)

        install()

        assert calls[1] == [_CLI, "install", "--skills", "--global"]

    def test_skills_via_sudo_for_initiating_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A root process with an initiating user runs only the skills step under sudo -H -u."""
        calls: list[list[str]] = []
        _wire_happy_path(monkeypatch, calls)
        monkeypatch.setattr(getpass, "getuser", lambda: "root")

        install(user="alice")

        assert calls[0] == [_NPM, "install", "-g", "@playwright/cli"]  # npm never under sudo
        assert calls[1] == ["sudo", "-H", "-u", "alice", _CLI, "install", "--skills", "--global"]

    def test_cli_resolved_from_npm_prefix_when_not_on_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """playwright-cli off PATH resolves through the npm global prefix."""
        calls: list[list[str]] = []
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._find_npm", lambda: _NPM)
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle.shutil.which", lambda _name: None)

        prefix_process = subprocess.CompletedProcess(args=[], returncode=0, stdout=f"{tmp_path}\n", stderr="")

        def run(argv, **kwargs):
            calls.append(list(argv))
            return prefix_process if argv[1:] == ["prefix", "-g"] else _ok(argv)

        monkeypatch.setattr(subprocess, "run", run)
        (tmp_path / "bin").mkdir()
        (tmp_path / "bin" / "playwright-cli").touch()

        install()

        assert calls[-1][0] == str(tmp_path / "bin" / "playwright-cli")

    def test_unresolvable_cli_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """An executable neither on PATH nor under the npm prefix is a clean error."""
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle._find_npm", lambda: _NPM)
        monkeypatch.setattr("goga_tool_pybuggy.lifecycle.lifecycle.shutil.which", lambda _name: None)

        prefix_process = subprocess.CompletedProcess(args=[], returncode=0, stdout=f"{tmp_path}\n", stderr="")

        def run(argv, **kwargs):
            return prefix_process if argv[1:] == ["prefix", "-g"] else _ok(argv)

        monkeypatch.setattr(subprocess, "run", run)

        with pytest.raises(RuntimeError, match="playwright-cli executable not found"):
            install()

    def test_success_logs_info_steps(self, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
        """Both completed steps log at INFO with terse extra keys."""
        calls: list[list[str]] = []
        _wire_happy_path(monkeypatch, calls)

        with caplog.at_level(logging.INFO):
            install()

        package_record = next(r for r in caplog.records if r.message == "playwright cli package installed")
        skills_record = next(r for r in caplog.records if r.message == "playwright cli skills installed")
        assert package_record.package == "@playwright/cli"
        assert skills_record.scope == "global"
        assert skills_record.user == getpass.getuser()
