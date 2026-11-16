"""Contract and logic tests for run_page_generate / page_generate_cmd handler."""

from pathlib import Path

import click
import pytest
from goga_tool_pybuggy.commands.page import page_generate_cmd, render_page_module, run_page_generate

# Contract tests -------------------------------------------------------------


def test_run_page_generate_importable_and_signature() -> None:
    """run_page_generate should be importable with signature (path, name, force) and no ctx."""
    params = run_page_generate.__code__.co_varnames[: run_page_generate.__code__.co_argcount]

    assert {"path", "name", "force"} <= set(params)
    assert "ctx" not in params


def test_render_page_module_importable_and_signature() -> None:
    """render_page_module should be importable from the cell facade with (path, class_name, fixture_name)."""
    assert render_page_module.__code__.co_argcount == 3
    assert render_page_module.__code__.co_varnames[:3] == ("path", "class_name", "fixture_name")
    assert render_page_module.__annotations__["return"] is str


def test_page_generate_cmd_is_click_command() -> None:
    """page_generate_cmd is a Click command 'generate' with path/name arguments and a force flag."""
    assert page_generate_cmd.name == "generate"

    param_names = {p.name for p in page_generate_cmd.params}
    assert {"path", "name", "force"} <= param_names
    assert "ctx" not in param_names

    all_opts = {opt for p in page_generate_cmd.params for opt in p.opts}
    assert "--force" in all_opts

    # path is a required positional, name an optional one
    path_arg = next(p for p in page_generate_cmd.params if p.name == "path")
    name_arg = next(p for p in page_generate_cmd.params if p.name == "name")
    assert isinstance(path_arg, click.Argument)
    assert path_arg.required is True
    assert isinstance(name_arg, click.Argument)
    assert name_arg.required is False


def test_page_generate_cmd_force_help_names_artifact_set() -> None:
    """The -f/--force help names the page-object module and the create-only marker rule."""
    force_opt = next(p for p in page_generate_cmd.params if p.name == "force")
    assert isinstance(force_opt, click.Option)

    assert "page-object module" in force_opt.help
    assert "__init__.py markers are created only when missing" in force_opt.help


# Renderer tests -------------------------------------------------------------


def test_render_page_module_login() -> None:
    """The fixed-shape module: imports, the class with its path attribute, the fixture."""
    module = render_page_module("/login", "LoginPage", "page_login")

    assert module == (
        "import pytest\n"
        "\n"
        "from goga_tool_pybuggy.web import BasePage\n"
        "from prettyplay import PrettyPlay\n"
        "\n"
        "\n"
        "class LoginPage(BasePage):\n"
        '    path = "/login"\n'
        "\n"
        "\n"
        '@pytest.fixture(scope="function")\n'
        "def page_login(web: PrettyPlay) -> LoginPage:\n"
        "    return LoginPage(web)\n"
    )


def test_render_page_module_deterministic() -> None:
    """Identical input yields identical output — no timestamps, no formatter runs."""
    assert render_page_module("/login", "LoginPage", "page_login") == render_page_module(
        "/login", "LoginPage", "page_login"
    )


def test_render_page_module_quotes_path_with_special_characters() -> None:
    """A path carrying a quote stays a valid literal via repr."""
    module = render_page_module("/o'brien", "BrienPage", "page_brien")

    compile(module, "brien_page.py", "exec")


# Handler logic tests --------------------------------------------------------


def test_run_page_generate_writes_module_and_markers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A deep path maps to nested directories, the last segment naming the module."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/admin/api/v1/mocks")

    module_file = tmp_path / "pages" / "admin" / "api" / "v1" / "mocks_page.py"
    text = module_file.read_text(encoding="utf-8")
    assert "class MocksPage(BasePage):" in text
    assert "def page_admin_api_v1_mocks(" in text
    assert 'path = "/admin/api/v1/mocks"' in text

    # Empty __init__.py markers on every directory of the module path
    for marker in (
        tmp_path / "pages" / "__init__.py",
        tmp_path / "pages" / "admin" / "__init__.py",
        tmp_path / "pages" / "admin" / "api" / "__init__.py",
        tmp_path / "pages" / "admin" / "api" / "v1" / "__init__.py",
    ):
        assert marker.exists()
        assert marker.read_text(encoding="utf-8") == ""


def test_run_page_generate_with_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit name drives the fixture and the class; a single-segment path writes at the root."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/login", "login")

    module = (tmp_path / "pages" / "login_page.py").read_text(encoding="utf-8")
    assert "class LoginPage(BasePage):" in module
    assert "def page_login(" in module
    assert (tmp_path / "pages" / "__init__.py").exists()


def test_run_page_generate_snake_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A snake_case name camel-cases the class and keeps the file slug verbatim."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/login", "user_profile")

    module = (tmp_path / "pages" / "user_profile_page.py").read_text(encoding="utf-8")
    assert "class UserProfilePage(BasePage):" in module
    assert "def page_user_profile(" in module


def test_run_page_generate_name_replaces_last_segment_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With a name, the last path segment still becomes the directory part, not the file name."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/admin/login", "auth")

    module = tmp_path / "pages" / "admin" / "auth_page.py"
    assert module.exists()
    text = module.read_text(encoding="utf-8")
    assert "class AuthPage(BasePage):" in text
    assert "def page_auth(" in text
    assert 'path = "/admin/login"' in text


def test_run_page_generate_trailing_slash_path_collapses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty segments drop: '/login/' behaves exactly like '/login'."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/login/")

    assert (tmp_path / "pages" / "login_page.py").exists()


@pytest.mark.parametrize("path", ["login", "", "/"])
def test_run_page_generate_rejects_invalid_path(
    path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path without a leading slash or without a non-empty segment fails and writes nothing."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(click.ClickException):
        run_page_generate(path)

    assert not (tmp_path / "pages").exists()


def test_run_page_generate_rejects_blank_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank name fails and writes nothing — the rejection precedes any disk change."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(click.ClickException, match="name must not be blank"):
        run_page_generate("/login", "   ")

    assert not (tmp_path / "pages").exists()


def test_run_page_generate_sanitizes_segments_and_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-word characters become underscores in every derived name and directory."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/v1.0/settings", "my-page")

    module = tmp_path / "pages" / "v1_0" / "my_page_page.py"
    assert module.exists()
    text = module.read_text(encoding="utf-8")
    assert "class MyPagePage(BasePage):" in text
    assert "def page_my_page(" in text
    compile(text, "my_page_page.py", "exec")


def test_run_page_generate_leading_digit_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A leading-digit name keeps the sanitization underscore through the class stem."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/login", "2fa")

    text = (tmp_path / "pages" / "_2fa_page.py").read_text(encoding="utf-8")
    assert "class _2faPage(BasePage):" in text
    assert "def page__2fa(" in text
    compile(text, "_2fa_page.py", "exec")


def test_run_page_generate_idempotent_skips_existing_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Without force an existing module is silently preserved."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/login", "login")
    target = tmp_path / "pages" / "login_page.py"
    target.write_text("STALE\n", encoding="utf-8")

    run_page_generate("/login", "login")

    assert target.read_text(encoding="utf-8") == "STALE\n"
    assert capsys.readouterr().out == ""


def test_run_page_generate_force_overwrites_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With force the module regenerates over an existing file."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/login", "login")
    (tmp_path / "pages" / "login_page.py").write_text("STALE\n", encoding="utf-8")

    run_page_generate("/login", "login", force=True)

    text = (tmp_path / "pages" / "login_page.py").read_text(encoding="utf-8")
    assert "class LoginPage(BasePage):" in text


def test_run_page_generate_markers_never_overwritten_even_with_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A consumer-owned __init__.py marker survives both a plain and a forced rerun."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/admin/login")
    marker = tmp_path / "pages" / "admin" / "__init__.py"
    marker.write_text("from .auth_page import page_auth  # consumer re-export\n", encoding="utf-8")

    run_page_generate("/admin/login", "auth")
    assert "consumer re-export" in marker.read_text(encoding="utf-8")

    run_page_generate("/admin/login", "auth", force=True)
    assert "consumer re-export" in marker.read_text(encoding="utf-8")


def test_run_page_generate_module_is_valid_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The written module compiles."""
    monkeypatch.chdir(tmp_path)

    run_page_generate("/admin/api/v1/mocks")

    compile(
        (tmp_path / "pages" / "admin" / "api" / "v1" / "mocks_page.py").read_text(encoding="utf-8"),
        "mocks_page.py",
        "exec",
    )


# Click wrapper tests --------------------------------------------------------


def test_page_generate_cmd_binds_path_name_and_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The wrapper binds PATH, the optional NAME and -f/--force onto run_page_generate."""
    from click.testing import CliRunner

    monkeypatch.chdir(tmp_path)

    captured: dict = {}

    def fake_run_page_generate(path, name, force):
        captured["path"] = path
        captured["name"] = name
        captured["force"] = force

    monkeypatch.setattr("goga_tool_pybuggy.commands.page.page.run_page_generate", fake_run_page_generate)

    result = CliRunner().invoke(page_generate_cmd, ["/login", "login", "-f"])

    assert result.exit_code == 0
    assert captured == {"path": "/login", "name": "login", "force": True}

    # Without NAME and the flag the optionals resolve to None/False
    captured.clear()
    result = CliRunner().invoke(page_generate_cmd, ["/x"])

    assert result.exit_code == 0
    assert captured == {"path": "/x", "name": None, "force": False}
