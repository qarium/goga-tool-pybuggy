"""Integration tests — the native-session smoke end-to-end and the CLI composition.

The smoke run drives the real engine with only the TTY stubbed; the CLI tests stub the engine seams.
"""

import importlib.metadata
import importlib.resources
import logging
import re
from pathlib import Path

import click
import yaml
from goga_tool_pybuggy.commands.init import init_cmd, run_bootstrap, run_session

# The seams of the CLI chain, patched at the orchestrator's import point (M-R2.8).
_SESSION_SEAM = "goga_tool_pybuggy.commands.init.init.run_session"
_BOOTSTRAP_SEAM = "goga_tool_pybuggy.commands.init.init.run_bootstrap"

# Every core gate is declined; no Dockerfile gate exists (the section is skipped, the block asks
# the image inputs), and the pybuggy tools record is amended regardless of the declined gate.
_CONFIRM_ANSWERS = {
    "Add codemanifest usages?": False,
    "Add codemanifest annotations?": False,
    "Configure a build agent?": False,
    "Configure a pipeline agent?": False,
    "Add tools?": False,
    "Add usages records?": False,
    "Add another spec?": [True, False],
    "Run the api.automate pipeline unattended (autonomous mode)?": False,
}

# The expected confirm ask order — the core gates, the amend-moment spec loop, then the autonomy
# confirm closing the survey after the specs.
_EXPECTED_CONFIRMS = [
    "Add codemanifest usages?",
    "Add codemanifest annotations?",
    "Configure a build agent?",
    "Configure a pipeline agent?",
    "Add tools?",
    "Add usages records?",
    "Add another spec?",
    "Add another spec?",
    "Run the api.automate pipeline unattended (autonomous mode)?",
]

# Only the prompts that must carry an explicit value are pinned; the optional ones read as Enter
# (the FROM prompt keeps its newest-python-family default).
_PROMPT_ANSWERS = {
    "Language": "python",
    "Built image name": "pybuggy-smoke:latest",
    "Base URL (Jinja2 template, required)": "https://{{ HOST }}/api",
    "Spec name": ["shop", "billing"],
    "Spec type": ["swagger", "openapi"],
    "Spec location (path from project root)": ["specs/shop.yaml", "specs/billing.yaml"],
}

# The plain payload the engine must serialize verbatim into the tool config.
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

        The real ``register_hooks`` run for both participation moments; the run stays offline.
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
        assert config["dockerfile"] == ".goga/Dockerfile"  # the amended fixed path
        assert set(config["tools"]) == {"pybuggy"}  # amended regardless of the declined gate
        assert re.fullmatch(r"\d+\.\d+\.x", config["tools"]["pybuggy"])
        assert "build" not in config  # the build.review.skip amendment never reaches the config (q2/A)
        assert "codemanifest" not in config  # both gates declined — the offline guarantee

        tool_config_path = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
        tool_config = yaml.safe_load(tool_config_path.read_text("utf-8"))
        assert tool_config == _EXPECTED_TOOL_CONFIG
        assert "#" not in tool_config_path.read_text(encoding="utf-8")  # plain engine serialization

        # The Dockerfile always exists — the FROM pair comes from the block answers.
        dockerfile = tmp_path / ".goga" / "Dockerfile"
        assert re.fullmatch(r"FROM qarium/goga-python-3\.\d+:\d+\.\d+\n", dockerfile.read_text(encoding="utf-8"))

        # The conventions slot is the bootstrap's delivery — the session never downloads the base convention.
        assert not (tmp_path / ".goga" / "usages" / "conventions.md").exists()

        # No git origin in the pytest tmp dir, so the built-image ask offers no default; the FROM
        # ask defaults to the newest python-family member of the running minor tag, and the
        # Dockerfile path is never asked at all.
        prompt_defaults = {text: default for text, default, _returned in tty.prompts}
        from_default = prompt_defaults[next(text for text in prompt_defaults if text.startswith("Base image (FROM)"))]
        assert (prompt_defaults["Built image name"], "Dockerfile path" in prompt_defaults) == (None, False)
        assert re.fullmatch(r"qarium/goga-python-3\.\d+:\d+\.\d+", from_default)

        # The full bare-init composition — the real bootstrap consumes the real session artifacts.
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

        Accepting the confirm distinguishes a recorded False from a lost answer key.
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

        Composition test — the wrapper and orchestrator are real, only the two seams are stubbed.
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

        The farthest seam's non-zero code is never normalized to 1 across the layers.
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
