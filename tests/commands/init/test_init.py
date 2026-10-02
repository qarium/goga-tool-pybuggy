"""Tests for the init module — CLI surface, mode resolution, three-mode orchestrator, bootstrap.

Covers ``init.py`` in the goga 2.0 shape: the contract surface (facade names, the Click
wrapper's bound parameters, the handler signatures), the carried-over pure
``resolve_init_mode`` flag table, the rewired ``run_init`` orchestrator (Task 6) — bare guard
on ``.goga`` directory existence, engine scaffold codes propagated as-is, the session seam
propagated unchanged with the bootstrap skipped on failure — and ``run_bootstrap`` (Task 7):
the 10-step post-session delivery with mode-dependent gates, the config-resolved Dockerfile
path, the tool-config example documentation, the ERROR-and-return-1 failure tier, and the
mandatory-Dockerfile invariant. The wrapper is driven through a fake ``ctx`` (M-R2.6 — no
CliRunner).
"""

import importlib.metadata
import importlib.resources
import logging
from pathlib import Path

import click
import pytest
import yaml
from goga_tool_pybuggy.commands.init import init as init_module
from goga_tool_pybuggy.commands.init import init_cmd, resolve_init_mode, run_bootstrap, run_init

# The seams run_init dispatches through, patched at the import point (M-R2.8): the session
# seam and the bootstrap seam live in init.py's namespace; the scaffold engine is reached
# through init.py's Scaffold constructor.
_SESSION_SEAM = "goga_tool_pybuggy.commands.init.init.run_session"
_BOOTSTRAP_SEAM = "goga_tool_pybuggy.commands.init.init.run_bootstrap"

_EXPECTED_CONFTEST = (
    "from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugin\n\nplugin.install()\n"
)

_API_PACKAGE = importlib.resources.files("goga_tool_pybuggy.api")
_PACKAGED_USAGES = {
    "api": (_API_PACKAGE / ".usages" / "api.md").read_text(encoding="utf-8"),
    "asserts": (_API_PACKAGE / "asserts" / ".usages" / "asserts.md").read_text(encoding="utf-8"),
}

# The install line expected under the patched package version "2.0.3" (minor x-range derivation).
_INSTALL_LINE = "RUN goga install pybuggy -v 2.0.x"


class _FakeCtx:
    """A ``click.Context`` double recording ``ctx.exit`` calls for the wrapper test.

    Attributes:
        exit_codes: The codes passed to ``exit``, in call order.
    """

    def __init__(self) -> None:
        """Build a recorder with no recorded exits."""
        self.exit_codes: list[int] = []

    def exit(self, code: int = 0) -> None:
        """Record one ``ctx.exit`` invocation.

        Args:
            code: The exit code the wrapper propagates.
        """
        self.exit_codes.append(code)


class _RunInitRecorder:
    """A ``run_init`` double recording the parsed surface and yielding a scripted code.

    Attributes:
        calls: The ``(tpl, ref, upgrade)`` argument tuples, in call order.
        return_code: The exit code every call yields.
    """

    def __init__(self, return_code: int) -> None:
        """Build a recorder yielding the given exit code on every call.

        Args:
            return_code: The exit code to return.
        """
        self.calls: list[tuple[str | None, str | None, bool]] = []
        self.return_code = return_code

    def __call__(self, tpl: str | None, ref: str | None, upgrade: bool) -> int:
        """Record one handler call and return the scripted code.

        Args:
            tpl: The parsed positional template source.
            ref: The parsed ``--ref`` override.
            upgrade: The parsed ``--upgrade`` flag.

        Returns:
            The scripted exit code.
        """
        self.calls.append((tpl, ref, upgrade))
        return self.return_code


class _ScaffoldRecorder:
    """A ``Scaffold`` double recording ``generate``/``upgrade`` calls and their codes.

    Attributes:
        generate_returns: Exit codes ``generate`` yields, one per call.
        upgrade_returns: Exit codes ``upgrade`` yields, one per call.
        generate_calls: The ``(template_input, ref_override)`` pairs, in call order.
        upgrade_calls: The ``(ref_override,)`` pairs, in call order.
    """

    def __init__(self, generate_returns: list[int] | None = None, upgrade_returns: list[int] | None = None) -> None:
        """Build a recorder with the scripted exit codes (one per allowed call).

        Args:
            generate_returns: Exit codes for successive ``generate`` calls.
            upgrade_returns: Exit codes for successive ``upgrade`` calls.
        """
        self.generate_returns = generate_returns if generate_returns is not None else [0]
        self.upgrade_returns = upgrade_returns if upgrade_returns is not None else [0]
        self.generate_calls: list[tuple[str | None, str | None]] = []
        self.upgrade_calls: list[tuple[str | None]] = []

    def generate(self, template_input: str | None, ref_override: str | None) -> int:
        """Record one scaffold generation and return the scripted code.

        Args:
            template_input: The raw template source (positional ``<tpl>``).
            ref_override: The ``--ref`` override, or ``None``.

        Returns:
            The next scripted exit code.
        """
        self.generate_calls.append((template_input, ref_override))
        return self.generate_returns[len(self.generate_calls) - 1]

    def upgrade(self, ref_override: str | None = None) -> int:
        """Record one scaffold migration and return the scripted code.

        Args:
            ref_override: The ``--ref`` override, or ``None``.

        Returns:
            The next scripted exit code.
        """
        self.upgrade_calls.append((ref_override,))
        return self.upgrade_returns[len(self.upgrade_calls) - 1]


class _SeamLog:
    """A call recorder for the session/bootstrap seams, tracking call order.

    Attributes:
        calls: The keyword arguments of every call, in call order.
    """

    def __init__(self, name: str, log: list[str], return_codes: list[int]) -> None:
        """Build a seam recorder appending its name to the shared order log.

        Args:
            name: The seam label appended on every call.
            log: The shared call-order log across all seams of a test.
            return_codes: Exit codes yielded, one per allowed call.
        """
        self._name = name
        self._log = log
        self._return_codes = return_codes
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> int:
        """Record one seam call with its kwargs and return the scripted code.

        Args:
            kwargs: The seam's keyword arguments (``template_mode`` for the bootstrap).

        Returns:
            The next scripted exit code.
        """
        self._log.append(self._name)
        self.calls.append(dict(kwargs))
        return self._return_codes[len(self.calls) - 1]


class TestInitContract:
    """Facade exposure, Click wrapper surface, and handler signatures."""

    def test_facade_exports_init_routines(self):
        """The wrapper, the orchestrator, the mode resolver, and the bootstrap are on the cell facade."""
        assert callable(init_cmd)
        assert callable(run_init)
        assert callable(resolve_init_mode)
        assert callable(run_bootstrap)

    def test_resolve_dockerfile_helper_present_in_module(self):
        """The private Dockerfile-resolution helper lives in the init module."""
        assert callable(init_module._resolve_dockerfile_path)

    def test_annotation_for_unknown_stem_falls_back_to_bare_backtick(self):
        """A discovered stem outside the hand-authored table still gets a binding backtick reference."""
        assert init_module._annotation_for("future-stem") == "`pybuggy-future-stem`"
        assert init_module._annotation_for("api").startswith("Use `pybuggy-api`")

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (run_init, {"tpl": str | None, "ref": str | None, "upgrade": bool, "return": int}),
            (resolve_init_mode, {"tpl": str | None, "ref": str | None, "upgrade": bool, "return": str}),
            (run_bootstrap, {"template_mode": bool, "return": int}),
        ],
    )
    def test_handler_signature_matches_contract(self, routine, expected):
        """Every handler carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected

    def test_init_cmd_binds_surface_and_propagates_exit(self, monkeypatch):
        """The wrapper binds tpl/--ref/--upgrade and propagates run_init's code via ctx.exit.

        The bound-parameter surface is introspected on the built command (click consumes
        ``__click_params__`` while assembling it); the body is driven directly with a fake
        ctx through the pass-context seam (M-R2.6 — no CliRunner).
        """
        by_name = {param.name: param for param in init_cmd.params}

        assert init_cmd.name == "init"
        assert set(by_name) == {"tpl", "ref", "upgrade"}
        assert isinstance(by_name["tpl"], click.Argument)
        assert by_name["tpl"].required is False
        assert isinstance(by_name["upgrade"], click.Option)
        assert by_name["upgrade"].is_flag is True
        assert by_name["upgrade"].opts == ["--upgrade"]
        assert isinstance(by_name["ref"], click.Option)
        assert by_name["ref"].opts == ["--ref"]

        recorder = _RunInitRecorder(return_code=3)
        monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_init", recorder)
        ctx = _FakeCtx()
        monkeypatch.setattr("click.decorators.get_current_context", lambda: ctx)

        init_cmd.callback(None, None, False)

        assert recorder.calls == [(None, None, False)]
        assert ctx.exit_codes == [3]


class TestResolveInitMode:
    """The carried-over pure flag table — mapping and nothing else."""

    @pytest.mark.parametrize(
        ("tpl", "ref", "upgrade", "expected"),
        [
            (None, None, False, "bare"),
            ("tpl", None, False, "template"),
            ("tpl", "v2", False, "template"),
            (None, "v2", True, "upgrade"),
            (None, None, True, "upgrade"),
        ],
    )
    def test_resolve_init_mode_table(self, tpl, ref, upgrade, expected):
        """Every valid flag combination maps to exactly one mode."""
        assert resolve_init_mode(tpl, ref, upgrade) == expected


class TestRunInit:
    """The three-mode orchestrator — guard, scaffold delegation, session seam, bootstrap last."""

    @pytest.mark.parametrize(
        ("mode_args", "message"),
        [
            (("t", None, True), "mutually exclusive"),
            ((None, "v2", False), "--ref requires"),
        ],
    )
    def test_run_init_invalid_flag_combinations_raise(self, tmp_path, monkeypatch, mode_args, message):
        """An invalid flag combination raises ClickException with its message before any side effect."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(click.ClickException, match=message):
            run_init(*mode_args)

    def test_run_init_bare_runs_session_then_bootstrap(self, tmp_path, monkeypatch):
        """Bare mode over a fresh directory runs the session first, then the bootstrap with template_mode False."""
        monkeypatch.chdir(tmp_path)
        order: list[str] = []
        session = _SeamLog("session", order, [0])
        bootstrap = _SeamLog("bootstrap", order, [0])
        monkeypatch.setattr(_SESSION_SEAM, session)
        monkeypatch.setattr(_BOOTSTRAP_SEAM, bootstrap)

        code = run_init(None, None, False)

        assert code == 0
        assert order == ["session", "bootstrap"]
        assert session.calls == [{}]
        assert bootstrap.calls == [{"template_mode": False}]

    def test_run_init_template_passes_template_mode(self, tmp_path, monkeypatch):
        """Template mode scaffolds first, then flags the bootstrap with template_mode True."""
        monkeypatch.chdir(tmp_path)
        scaffold = _ScaffoldRecorder()
        monkeypatch.setattr(init_module, "Scaffold", lambda: scaffold)
        order: list[str] = []
        session = _SeamLog("session", order, [0])
        bootstrap = _SeamLog("bootstrap", order, [0])
        monkeypatch.setattr(_SESSION_SEAM, session)
        monkeypatch.setattr(_BOOTSTRAP_SEAM, bootstrap)

        code = run_init("https://t.git#v1", None, False)

        assert code == 0
        assert scaffold.generate_calls == [("https://t.git#v1", None)]
        assert order == ["session", "bootstrap"]
        assert bootstrap.calls == [{"template_mode": True}]

    def test_run_init_bare_guard_refuses_initialized_project(self, tmp_path, monkeypatch, capsys):
        """Bare mode over an existing .goga directory refuses with stderr text and zero side effects."""
        monkeypatch.chdir(tmp_path)
        goga = tmp_path / ".goga"
        goga.mkdir()
        (goga / "config.yml").write_text("language: python\n", encoding="utf-8")
        before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

        def _fail(*args: object, **kwargs: object) -> int:
            raise AssertionError("refused run must not reach the seams")

        monkeypatch.setattr(_SESSION_SEAM, _fail)
        monkeypatch.setattr(_BOOTSTRAP_SEAM, _fail)
        monkeypatch.setattr(init_module, "Scaffold", _fail)

        code = run_init(None, None, False)

        assert code == 1
        assert "Project already initialized" in capsys.readouterr().err
        assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before

    def test_run_init_guard_checks_directory_existence_only(self, tmp_path, monkeypatch):
        """A .goga regular file passes the guard — the recorders run and the stubbed code returns."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").write_text("not a directory\n", encoding="utf-8")
        order: list[str] = []
        session = _SeamLog("session", order, [0])
        bootstrap = _SeamLog("bootstrap", order, [6])
        monkeypatch.setattr(_SESSION_SEAM, session)
        monkeypatch.setattr(_BOOTSTRAP_SEAM, bootstrap)

        assert run_init(None, None, False) == 6
        assert order == ["session", "bootstrap"]

    @pytest.mark.parametrize(
        ("mode_args", "failing_seam", "expected_code"),
        [
            pytest.param(("https://t.git#v1", None, False), "scaffold", 3, id="scaffold-generate-returns-3"),
            pytest.param((None, None, False), "session", 4, id="session-returns-4"),
            pytest.param((None, None, True), "upgrade", 5, id="upgrade-returns-5"),
        ],
    )
    def test_run_init_propagates_engine_and_session_codes(
        self, tmp_path, monkeypatch, mode_args, failing_seam, expected_code
    ):
        """A non-zero code at any seam is propagated as-is and every downstream seam is skipped."""
        monkeypatch.chdir(tmp_path)
        order: list[str] = []
        monkeypatch.setattr(_SESSION_SEAM, _SeamLog("session", order, [4]))
        monkeypatch.setattr(_BOOTSTRAP_SEAM, _SeamLog("bootstrap", order, [0]))
        scaffold = _ScaffoldRecorder(generate_returns=[3], upgrade_returns=[5])
        monkeypatch.setattr(init_module, "Scaffold", lambda: scaffold)

        assert run_init(*mode_args) == expected_code

        if failing_seam == "scaffold":
            assert order == []
            assert scaffold.generate_calls == [("https://t.git#v1", None)]
        elif failing_seam == "session":
            assert order == ["session"]
            assert scaffold.generate_calls == []
        else:
            assert order == []
            assert scaffold.upgrade_calls == [(None,)]

    def test_run_init_template_mode_not_guarded_by_existing_goga(self, tmp_path, monkeypatch):
        """Template mode over an initialized project still scaffolds and runs both seams."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir()
        (tmp_path / ".goga" / "config.yml").write_text("language: python\n", encoding="utf-8")
        scaffold = _ScaffoldRecorder()
        monkeypatch.setattr(init_module, "Scaffold", lambda: scaffold)
        order: list[str] = []
        session = _SeamLog("session", order, [0])
        bootstrap = _SeamLog("bootstrap", order, [0])
        monkeypatch.setattr(_SESSION_SEAM, session)
        monkeypatch.setattr(_BOOTSTRAP_SEAM, bootstrap)

        assert run_init("tpl", None, False) == 0
        assert order == ["session", "bootstrap"]
        assert bootstrap.calls == [{"template_mode": True}]


class TestResolveDockerfilePath:
    """The private helper — field resolution and the fallback discipline (never raises into the tier)."""

    def test_resolve_dockerfile_path_returns_the_declared_field(self, tmp_path):
        """A non-empty string field wins over the fallback."""
        config = tmp_path / "config.yml"
        config.write_text("dockerfile: Dockerfile\n", encoding="utf-8")

        assert init_module._resolve_dockerfile_path(config) == Path("Dockerfile")

    @pytest.mark.parametrize(
        "config_text",
        [
            pytest.param("dockerfile: true\n", id="boolean"),
            pytest.param("dockerfile:\n  from: x\n  path: y\n", id="mapping"),
            pytest.param("dockerfile: 777\n", id="integer"),
            pytest.param("dockerfile:\n", id="null"),
        ],
    )
    def test_resolve_dockerfile_path_falls_back_on_non_string_field(self, tmp_path, config_text):
        """A null or non-string dockerfile field falls back to the default instead of raising."""
        config = tmp_path / "config.yml"
        config.write_text(config_text, encoding="utf-8")

        assert init_module._resolve_dockerfile_path(config) == Path(".goga") / "Dockerfile"

    def test_resolve_dockerfile_path_falls_back_on_pyyaml_unparsable_document(self, tmp_path):
        """A document PyYAML cannot parse falls back — the helper never raises into the tier."""
        config = tmp_path / "config.yml"
        config.write_text("? [complex, key]\n: value\n", encoding="utf-8")

        assert init_module._resolve_dockerfile_path(config) == Path(".goga") / "Dockerfile"


def _seed_config(root: Path, text: str) -> Path:
    """Write the consumer ``.goga/config.yml`` carrying ``text`` and return its path.

    Args:
        root: The scratch project root (the test's ``tmp_path``).
        text: The raw YAML text of the consumer config.

    Returns:
        The written config path.
    """
    goga = root / ".goga"
    goga.mkdir(exist_ok=True)
    config = goga / "config.yml"
    config.write_text(text, encoding="utf-8")

    return config


def _error_records(caplog):
    """Return the ERROR-or-worse records captured so far."""
    return [record for record in caplog.records if record.levelno >= logging.ERROR]


def _no_prompt(*_args: object, **_kwargs: object) -> bool:
    """Fail the test when the bootstrap prompts in a mode that must not.

    Returns:
        Never returns — the AssertionError propagates.
    """
    raise AssertionError("template mode must not prompt")


class TestRunBootstrap:
    """The 10-step post-session orchestrator — gates, Dockerfile resolution, failure tier."""

    def test_run_bootstrap_full_pass_on_fresh_session_artifacts(self, tmp_path, monkeypatch, caplog):
        """A fresh session tree gets every artifact delivered with no ERROR logged."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_config(tmp_path, "language: python\ndockerfile: .goga/Dockerfile\n")
        (tmp_path / ".goga" / "Dockerfile").write_text("FROM x\n", encoding="utf-8")
        tool_config = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
        tool_config.parent.mkdir(parents=True)
        tool_config.write_text(
            "base_url: https://{{ HOST }}/api\nspecs:\n  shop:\n    type: swagger\n    location: specs/shop.yaml\n",
            encoding="utf-8",
        )

        with caplog.at_level(logging.INFO):
            code = run_bootstrap(template_mode=False)

        assert code == 0
        usages = tmp_path / ".goga" / "usages" / "cooks" / "pybuggy"
        assert (usages / "api.md").read_text(encoding="utf-8") == _PACKAGED_USAGES["api"]
        assert (usages / "asserts.md").read_text(encoding="utf-8") == _PACKAGED_USAGES["asserts"]
        slot = tmp_path / ".goga" / "usages" / "conventions.md"
        packaged_convention = (importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md").read_text(
            encoding="utf-8"
        )
        assert slot.read_text(encoding="utf-8") == packaged_convention

        tool_config_text = tool_config.read_text(encoding="utf-8")
        assert "# headers: example (skipped complex member)" in tool_config_text
        assert "# timeout: (skipped optional scalar)" in tool_config_text
        assert "# loader: example (skipped complex member)" in tool_config_text
        assert "# assert_response_class: (skipped optional scalar)" in tool_config_text
        assert "tool config examples documented" in caplog.text

        config = yaml.safe_load((tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8"))
        assert config["build"]["review"]["skip"] is True
        assert config["codemanifest"]["usages"]["pybuggy-api"] == ".goga/usages/cooks/pybuggy/api.md"
        assert config["codemanifest"]["usages"]["conventions"] == ".goga/usages/conventions.md"
        annotations = config["codemanifest"]["annotations"]
        assert "`pybuggy-api`" in annotations
        assert "`conventions`" in annotations

        assert (tmp_path / "conftest.py").read_text(encoding="utf-8") == _EXPECTED_CONFTEST
        dockerfile = (tmp_path / ".goga" / "Dockerfile").read_text(encoding="utf-8")
        assert dockerfile.endswith(f"{_INSTALL_LINE}\n")
        assert _error_records(caplog) == []

    def test_run_bootstrap_resolves_dockerfile_from_config_field(self, tmp_path, monkeypatch):
        """The install line lands in the config-declared root Dockerfile, never in the fallback."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_config(tmp_path, "language: python\ndockerfile: Dockerfile\n")
        (tmp_path / "Dockerfile").write_text("FROM x\n", encoding="utf-8")

        code = run_bootstrap(template_mode=True)

        assert code == 0
        assert (tmp_path / "Dockerfile").read_text(encoding="utf-8").endswith(f"{_INSTALL_LINE}\n")
        assert not (tmp_path / ".goga" / "Dockerfile").exists()

    @pytest.mark.parametrize(
        "config_text",
        [
            pytest.param("language: python\ndockerfile: custom/Dockerfile\n", id="field-points-at-absent-file"),
            pytest.param("language: python\n", id="declined-dockerfile-session"),
        ],
    )
    def test_run_bootstrap_missing_dockerfile_fails_with_error(self, tmp_path, monkeypatch, caplog, config_text):
        """A Dockerfile missing after the session fails at step 9 with steps 2-8 already applied."""
        monkeypatch.chdir(tmp_path)
        _seed_config(tmp_path, config_text)

        with caplog.at_level(logging.INFO):
            code = run_bootstrap(template_mode=False)

        assert code == 1
        errors = _error_records(caplog)
        assert len(errors) == 1
        assert "Dockerfile" in errors[0].message
        assert (tmp_path / ".goga" / "usages" / "cooks" / "pybuggy" / "api.md").exists()
        assert (tmp_path / "conftest.py").read_text(encoding="utf-8") == _EXPECTED_CONFTEST
        assert not (tmp_path / ".goga" / "Dockerfile").exists()

    def test_run_bootstrap_step_failure_maps_to_nonzero(self, tmp_path, monkeypatch, caplog):
        """A step failure is ERROR-logged and mapped to 1 — never raised as ClickException."""
        monkeypatch.chdir(tmp_path)
        _seed_config(tmp_path, "language: python\ndockerfile: .goga/Dockerfile\n")
        (tmp_path / ".goga" / "Dockerfile").write_text("FROM x\n", encoding="utf-8")

        def _boom(config_path: Path, usage_keys: dict[str, str]) -> list[str]:
            raise OSError("disk on fire")

        monkeypatch.setattr(init_module, "register_usages", _boom)

        with caplog.at_level(logging.INFO):
            code = run_bootstrap(template_mode=False)

        assert code == 1
        errors = _error_records(caplog)
        assert len(errors) == 1
        assert errors[0].error == "disk on fire"

    def test_run_bootstrap_template_mode_never_prompts(self, tmp_path, monkeypatch, caplog):
        """A template-mode rerun over a bootstrapped tree writes nothing and never confirms."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_config(tmp_path, "language: python\ndockerfile: .goga/Dockerfile\n")
        (tmp_path / ".goga" / "Dockerfile").write_text("FROM x\n", encoding="utf-8")

        assert run_bootstrap(template_mode=True) == 0
        snapshot = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
        monkeypatch.setattr(click, "confirm", _no_prompt)

        with caplog.at_level(logging.INFO):
            code = run_bootstrap(template_mode=True)

        assert code == 0
        assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == snapshot
        assert any("existing file kept untouched" in record.message for record in caplog.records)

    def test_run_bootstrap_bare_mode_gates(self, tmp_path, monkeypatch):
        """Bare mode overwrites a stale usages copy and asks for the conftest (decline keeps it)."""
        monkeypatch.chdir(tmp_path)
        _seed_config(tmp_path, "language: python\ndockerfile: .goga/Dockerfile\n")
        (tmp_path / ".goga" / "Dockerfile").write_text("FROM x\n", encoding="utf-8")
        api_copy = tmp_path / ".goga" / "usages" / "cooks" / "pybuggy" / "api.md"
        api_copy.parent.mkdir(parents=True)
        api_copy.write_text("stale api usage\n", encoding="utf-8")
        conftest = tmp_path / "conftest.py"
        conftest.write_text("# user conftest\n", encoding="utf-8")

        monkeypatch.setattr(click, "confirm", lambda *_args, **_kwargs: False)
        assert run_bootstrap(template_mode=False) == 0
        assert api_copy.read_text(encoding="utf-8") == _PACKAGED_USAGES["api"]
        assert conftest.read_text(encoding="utf-8") == "# user conftest\n"

        monkeypatch.setattr(click, "confirm", lambda *_args, **_kwargs: True)
        assert run_bootstrap(template_mode=False) == 0
        assert conftest.read_text(encoding="utf-8") == _EXPECTED_CONFTEST

    def test_run_bootstrap_existing_config_session_end_still_enforces(self, tmp_path, monkeypatch):
        """A template-brought config (session ended at once) still gets flag, keys, install line."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_config(tmp_path, "language: python\ndockerfile: .goga/Dockerfile\nbuild:\n  agent: swax\n")
        dockerfile = tmp_path / ".goga" / "Dockerfile"
        dockerfile.write_text("FROM python:3.12\n", encoding="utf-8")

        code = run_bootstrap(template_mode=True)

        assert code == 0
        config = yaml.safe_load((tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8"))
        assert config["build"]["review"]["skip"] is True
        assert config["build"]["agent"] == "swax"
        assert config["codemanifest"]["usages"]["pybuggy-api"] == ".goga/usages/cooks/pybuggy/api.md"
        assert dockerfile.read_text(encoding="utf-8").endswith(f"{_INSTALL_LINE}\n")

    def test_run_bootstrap_idempotent_rerun(self, tmp_path, monkeypatch, caplog):
        """A second bare run with a declined conftest overwrite leaves the tree byte-identical."""
        monkeypatch.chdir(tmp_path)
        _seed_config(tmp_path, "language: python\ndockerfile: .goga/Dockerfile\n")
        (tmp_path / ".goga" / "Dockerfile").write_text("FROM x\n", encoding="utf-8")

        with caplog.at_level(logging.INFO):
            assert run_bootstrap(template_mode=False) == 0
        snapshot = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
        monkeypatch.setattr(click, "confirm", lambda *_args, **_kwargs: False)

        with caplog.at_level(logging.INFO):
            assert run_bootstrap(template_mode=False) == 0
        assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == snapshot

        warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
        assert warnings.count("usage already registered, skipped") == 3
        assert warnings.count("annotation already registered, skipped") == 3

    @pytest.mark.parametrize(
        "config_text",
        [
            pytest.param(None, id="absent-config"),
            pytest.param("", id="empty-config"),
        ],
    )
    def test_run_bootstrap_empty_and_broken_config_variants(self, tmp_path, monkeypatch, config_text):
        """An absent or empty config still enforces, registers, and falls back for the Dockerfile."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        (tmp_path / ".goga").mkdir()
        if config_text is not None:
            (tmp_path / ".goga" / "config.yml").write_text(config_text, encoding="utf-8")
        dockerfile = tmp_path / ".goga" / "Dockerfile"
        dockerfile.write_text("FROM x\n", encoding="utf-8")

        code = run_bootstrap(template_mode=False)

        assert code == 0
        config = yaml.safe_load((tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8"))
        assert config["build"]["review"]["skip"] is True
        assert config["codemanifest"]["usages"]["pybuggy-api"] == ".goga/usages/cooks/pybuggy/api.md"
        assert dockerfile.read_text(encoding="utf-8").endswith(f"{_INSTALL_LINE}\n")

    @pytest.mark.parametrize(
        "config_text",
        [
            pytest.param("language: python\ndockerfile: true\n", id="boolean-field"),
            pytest.param("language: python\ndockerfile:\n  from: x\n  path: y\n", id="mapping-field"),
        ],
    )
    def test_run_bootstrap_non_string_dockerfile_field_falls_back(self, tmp_path, monkeypatch, caplog, config_text):
        """A non-string dockerfile field never escapes the tier — the fallback path gets the line."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_config(tmp_path, config_text)
        dockerfile = tmp_path / ".goga" / "Dockerfile"
        dockerfile.write_text("FROM x\n", encoding="utf-8")

        with caplog.at_level(logging.INFO):
            code = run_bootstrap(template_mode=True)

        assert code == 0
        assert dockerfile.read_text(encoding="utf-8").endswith(f"{_INSTALL_LINE}\n")
        assert _error_records(caplog) == []

    def test_run_bootstrap_corrupt_config_fails_through_the_wrapped_tier(self, tmp_path, monkeypatch, caplog):
        """An unparsable consumer config is ERROR-logged and mapped to 1 — never a traceback."""
        monkeypatch.chdir(tmp_path)
        _seed_config(tmp_path, "language: python\na: [unclosed\n")

        with caplog.at_level(logging.INFO):
            code = run_bootstrap(template_mode=False)

        assert code == 1
        errors = _error_records(caplog)
        assert len(errors) == 1
        assert errors[0].message == "onboarding bootstrap failed"
