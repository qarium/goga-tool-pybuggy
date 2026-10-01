"""Tests for the init module — CLI surface, mode resolution, three-mode orchestrator.

Covers ``init.py`` in the goga 2.0 shape (Task 6): the contract surface (facade
names, the Click wrapper's bound parameters, the handler signatures), the
carried-over pure ``resolve_init_mode`` flag table, and the rewired ``run_init``
orchestrator — bare guard on ``.goga`` directory existence, engine scaffold
codes propagated as-is, the session seam propagated unchanged with the
bootstrap skipped on failure, and the bootstrap last with the template-mode
flag. The wrapper is driven through a fake ``ctx`` (M-R2.6 — no CliRunner).
"""

import click
import pytest
from goga_tool_pybuggy.commands.init import init as init_module
from goga_tool_pybuggy.commands.init import init_cmd, resolve_init_mode, run_init

# The seams run_init dispatches through, patched at the import point (M-R2.8): the session
# seam and the bootstrap seam live in init.py's namespace; the scaffold engine is reached
# through init.py's Scaffold constructor.
_SESSION_SEAM = "goga_tool_pybuggy.commands.init.init.run_session"
_BOOTSTRAP_SEAM = "goga_tool_pybuggy.commands.init.init.run_bootstrap"


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
        """The wrapper, the orchestrator, and the mode resolver are importable from the cell facade."""
        assert callable(init_cmd)
        assert callable(run_init)
        assert callable(resolve_init_mode)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (run_init, {"tpl": str | None, "ref": str | None, "upgrade": bool, "return": int}),
            (resolve_init_mode, {"tpl": str | None, "ref": str | None, "upgrade": bool, "return": str}),
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
