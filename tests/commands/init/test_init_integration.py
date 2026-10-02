"""Integration tests — the native-session smoke end-to-end and the CLI composition.

The acceptance-level proof of the participation mechanism, in process (Task 9):
``test_session_smoke_end_to_end_with_prompt_stubs`` runs the REAL engine session
(``run_session`` → ``InitLogic`` → registry → real ``register_hooks`` → real
hooks) with only the terminal stubbed — a scripted TTY answering the pinned
answer map — and asserts the artifact set on disk: the project config, the
Dockerfile at the answered path, and the tool config written by the engine from
the plain payload our amend hook buffered, attributed ``(tool: pybuggy)`` in the
report. The smoke run then composes the REAL bootstrap over the real session
artifacts — the full bare-init path in one process. The CLI composition tests
drive the whole chain ``init_cmd.callback → run_init → run_session +
run_bootstrap`` with the engine seams stubbed at the orchestrator's import
point — delegation order and exit propagation across the layers (the
wrapper-binding surface alone is Task 6's; the top-level ``init`` registration
is ``tests/test_cli.py``'s).
"""

import importlib.metadata
import importlib.resources
import logging
from pathlib import Path

import click
import yaml
from goga_tool_pybuggy.commands.init import init_cmd, run_bootstrap, run_session

# The seams of the CLI chain, patched at the orchestrator's import point (M-R2.8).
_SESSION_SEAM = "goga_tool_pybuggy.commands.init.init.run_session"
_BOOTSTRAP_SEAM = "goga_tool_pybuggy.commands.init.init.run_bootstrap"

# The pinned confirm map (review q3/A): every core gate declined EXCEPT the
# Dockerfile creation — declining it is the failed-init branch of q1/A, so the
# smoke run accepts it. The goga base-convention gate is ABSENT — the declaration
# hook skips the core convention section, and the strict map would fail the run
# if the engine asked the gate anyway. The autonomy confirm of the pybuggy block
# is declined — the default — so the tool config carries no pipelines axis. The
# add-another-spec loop of the amend hook is answered from a FIFO queue: one
# accepted extra spec, then a decline.
_CONFIRM_ANSWERS = {
    "Add codemanifest usages?": False,
    "Add codemanifest annotations?": False,
    "Configure a build agent?": False,
    "Create Dockerfile?": True,
    "Configure a pipeline agent?": False,
    "Add tools?": False,
    "Add usages records?": False,
    "Run the api.automate pipeline unattended (autonomous mode)?": False,
    "Add another spec?": [True, False],
}

# The expected confirm ask order — the seven core gates, the block's autonomy
# confirm (last item of the pybuggy survey), then the amend-moment loop (accepted
# once for the extra spec, then declined).
_EXPECTED_CONFIRMS = [
    "Add codemanifest usages?",
    "Add codemanifest annotations?",
    "Configure a build agent?",
    "Create Dockerfile?",
    "Configure a pipeline agent?",
    "Add tools?",
    "Add usages records?",
    "Run the api.automate pipeline unattended (autonomous mode)?",
    "Add another spec?",
    "Add another spec?",
]

# The pinned prompt inputs: only the prompts that must carry an explicit value.
# ``resolve_project_name()`` returns None in the pytest tmp dir (no git origin),
# so "Built image name" offers NO default and Enter is impossible — the map
# carries an explicit image name. The repeated spec-field prompts are answered
# from FIFO queues: the engine's ``first_spec`` ask consumes the first entry,
# the amend hook's surveyed extra spec the second. The optional prompts (the
# Dockerfile path, the base image, the optional scalars, the git fields) stay
# unscripted and read as Enter through the ScriptedTTY default rule; the offline
# guarantee holds because the conventions download is never offered (the skipped
# section) and no answer activates it.
_PROMPT_ANSWERS = {
    "Language": "python",
    "Built image name": "pybuggy-smoke:latest",
    "Base URL (Jinja2 template, required)": "https://{{ HOST }}/api",
    "Spec name": ["shop", "billing"],
    "Spec type": ["swagger", "openapi"],
    "Spec location (path from project root)": ["specs/shop.yaml", "specs/billing.yaml"],
}

# The plain payload the engine must serialize verbatim into .goga/tools/pybuggy/config.yml:
# the answered base_url, the surveyed first spec, the surveyed extra spec (both git-less —
# the git prompts read as Enter), and no optional scalar keys (every one Enter-skipped).
_EXPECTED_TOOL_CONFIG = {
    "base_url": "https://{{ HOST }}/api",
    "specs": {
        "shop": {"type": "swagger", "location": "specs/shop.yaml"},
        "billing": {"type": "openapi", "location": "specs/billing.yaml"},
    },
}


def _write_minimal_specs(root: Path) -> None:
    """Write the two minimal spec files the surveyed answers point at.

    Args:
        root: The scratch project root (the test's ``tmp_path``).
    """
    specs = root / "specs"
    specs.mkdir()
    (specs / "shop.yaml").write_text(
        "openapi: 3.0.0\ninfo: {title: shop, version: '1.0'}\npaths: {}\n", encoding="utf-8"
    )
    (specs / "billing.yaml").write_text(
        "openapi: 3.0.0\ninfo: {title: billing, version: '1.0'}\npaths: {}\n", encoding="utf-8"
    )


class TestSessionSmoke:
    """The native-session path — real engine, real registry, real hooks, scripted TTY."""

    def test_session_smoke_end_to_end_with_prompt_stubs(self, tmp_path, monkeypatch, capsys, caplog, scripted_tty):
        """The engine session surveys core + pybuggy block and writes every artifact.

        The registry imports the real ``register_hooks`` of the installed package, so
        the two participation moments run for real: the declared block is surveyed
        under ``--- Tool: pybuggy ---``, the amend hook surveys the additional spec
        itself (the confirm-gated loop), buffers the single amendment and the plain
        payload, and the engine writes the tool config itself with attribution. The
        run stays offline — the skipped convention section means the base-convention
        download is never offered, so nothing leaves the process.
        """
        monkeypatch.chdir(tmp_path)
        _write_minimal_specs(tmp_path)
        tty = scripted_tty(confirms=_CONFIRM_ANSWERS, prompts=_PROMPT_ANSWERS)
        monkeypatch.setattr(click, "confirm", tty.confirm)
        monkeypatch.setattr(click, "prompt", tty.prompt)

        with caplog.at_level(logging.INFO):
            code = run_session()

        captured = capsys.readouterr()
        assert code == 0
        assert [text for text, _answer in tty.confirms] == _EXPECTED_CONFIRMS
        assert "created .goga/tools/pybuggy/config.yml (tool: pybuggy)" in captured.out
        assert not [record for record in caplog.records if record.levelno >= logging.ERROR]

        config = yaml.safe_load((tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8"))
        assert config["language"] == "python"
        assert config["image"] == "pybuggy-smoke:latest"
        assert config["dockerfile"] == ".goga/Dockerfile"
        assert "build" not in config  # the build.review.skip amendment never reaches the config (q2/A)
        assert "codemanifest" not in config  # both gates declined — the offline guarantee

        tool_config_path = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
        tool_config = yaml.safe_load(tool_config_path.read_text("utf-8"))
        assert tool_config == _EXPECTED_TOOL_CONFIG
        assert "#" not in tool_config_path.read_text(encoding="utf-8")  # plain engine serialization

        dockerfile = tmp_path / ".goga" / "Dockerfile"
        assert dockerfile.read_text(encoding="utf-8").startswith("FROM ")

        # The conventions slot is the bootstrap's delivery, never the session's — and the
        # skipped section means the engine never downloaded the goga base convention.
        assert not (tmp_path / ".goga" / "usages" / "conventions.md").exists()

        # The Enter-impossible prompt: no project name in the pytest tmp dir, so the
        # built-image ask offers no default — the scripted map must carry the value.
        prompt_defaults = {text: default for text, default, _returned in tty.prompts}
        assert prompt_defaults["Built image name"] is None
        assert prompt_defaults["Dockerfile path"] == ".goga/Dockerfile"

        # The full bare-init composition: the REAL bootstrap consumes the real session
        # artifacts — the config-declared Dockerfile carries the install line, the skip
        # flag and the registrations land, the tool config gains its commented examples,
        # and the conventions slot (the packaged pybuggy asset) and conftest appear.
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")

        with caplog.at_level(logging.INFO):
            assert run_bootstrap(template_mode=False) == 0

        packaged_convention = (importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md").read_text(
            encoding="utf-8"
        )
        assert (tmp_path / ".goga" / "usages" / "conventions.md").read_text(encoding="utf-8") == packaged_convention

        tool_config_text = tool_config_path.read_text(encoding="utf-8")
        assert yaml.safe_load(tool_config_text) == _EXPECTED_TOOL_CONFIG  # active keys untouched
        assert "# headers: example (skipped complex member)" in tool_config_text
        assert "# timeout: (skipped optional scalar)" in tool_config_text
        assert "# loader: example (skipped complex member)" in tool_config_text
        assert "# assert_response_class: (skipped optional scalar)" in tool_config_text

        config = yaml.safe_load((tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8"))
        assert config["build"]["review"]["skip"] is True
        assert config["codemanifest"]["usages"]["pybuggy-api"] == ".goga/usages/cooks/pybuggy/api.md"
        assert "`pybuggy-api`" in config["codemanifest"]["annotations"]
        assert (
            (tmp_path / ".goga" / "Dockerfile")
            .read_text(encoding="utf-8")
            .endswith("RUN goga install pybuggy -v 2.0.x\n")
        )
        assert (tmp_path / "conftest.py").exists()
        assert not [record for record in caplog.records if record.levelno >= logging.ERROR]

    def test_session_smoke_autonomy_confirm_accepted_writes_axis(self, tmp_path, monkeypatch, caplog, scripted_tty):
        """Answering the autonomy confirm True lands the ``pipelines`` axis in the written config.

        The declined smoke run cannot distinguish ``answer recorded False`` from
        ``answer key lost`` — both produce no axis; this variant accepts the
        confirm and asserts the enabling entry reaches the engine-written tool
        config, the exact bridge the run hook later reads.
        """
        monkeypatch.chdir(tmp_path)
        _write_minimal_specs(tmp_path)
        tty = scripted_tty(
            confirms={**_CONFIRM_ANSWERS, "Run the api.automate pipeline unattended (autonomous mode)?": True},
            prompts=_PROMPT_ANSWERS,
        )
        monkeypatch.setattr(click, "confirm", tty.confirm)
        monkeypatch.setattr(click, "prompt", tty.prompt)

        with caplog.at_level(logging.INFO):
            code = run_session()

        assert code == 0
        assert not [record for record in caplog.records if record.levelno >= logging.ERROR]

        tool_config = yaml.safe_load((tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml").read_text("utf-8"))
        assert tool_config["pipelines"] == {"api.automate": {"autonomous": True}}


class TestCliComposition:
    """The CLI chain — wrapper through orchestrator to the two seams, seams stubbed."""

    def test_cli_bare_init_runs_wrapper_through_session_and_bootstrap(
        self, tmp_path, monkeypatch, exit_recorder, seam_recorder
    ):
        """``init_cmd.callback`` drives the real ``run_init`` into session-then-bootstrap.

        Composition, not unit: the wrapper and the orchestrator are both real; only
        the two engine-facing seams are stubbed at the orchestrator's import point.
        A fresh project takes the bare chain — the guard passes, the session runs
        first, the bootstrap runs last with the bare gate (``template_mode False``),
        and the wrapper propagates the resulting code through ``ctx.exit``.
        """
        monkeypatch.chdir(tmp_path)
        order: list[str] = []
        session = seam_recorder("session", order, [0])
        bootstrap = seam_recorder("bootstrap", order, [0])
        monkeypatch.setattr(_SESSION_SEAM, session)
        monkeypatch.setattr(_BOOTSTRAP_SEAM, bootstrap)
        ctx = exit_recorder()
        monkeypatch.setattr("click.decorators.get_current_context", lambda: ctx)  # the pass-context seam (M-R2.6)

        init_cmd.callback(None, None, False)

        assert order == ["session", "bootstrap"]
        assert session.calls == [{}]
        assert bootstrap.calls == [{"template_mode": False}]
        assert ctx.exit_codes == [0]

    def test_cli_composition_propagates_bootstrap_failure_exit(
        self, tmp_path, monkeypatch, exit_recorder, seam_recorder
    ):
        """A bootstrap failure code reaches ``ctx.exit`` through the whole chain unchanged.

        The farthest seam's non-zero code (never normalized to 1) surfaces as the
        CLI exit code — the same propagation contract ``run_init`` owns, observed
        across both real layers.
        """
        monkeypatch.chdir(tmp_path)
        order: list[str] = []
        monkeypatch.setattr(_SESSION_SEAM, seam_recorder("session", order, [0]))
        monkeypatch.setattr(_BOOTSTRAP_SEAM, seam_recorder("bootstrap", order, [2]))
        ctx = exit_recorder()
        monkeypatch.setattr("click.decorators.get_current_context", lambda: ctx)

        init_cmd.callback(None, None, False)

        assert order == ["session", "bootstrap"]
        assert ctx.exit_codes == [2]
