"""pybuggy post-install lifecycle: provision the playwright agent CLI."""

import getpass
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# The npm package owning the playwright-cli agent binary of the web.automate page exploration.
_CLI_PACKAGE = "@playwright/cli"
# The argv tail of the global skills step — the agent skills into the target home directory.
_SKILLS_ARGS = ["install", "--skills", "--global"]


def _find_npm() -> str | None:
    """Locate the npm executable on PATH.

    Unlike the ruff lookup of the generate cell there is no interpreter-venv fallback —
    npm never lives next to a python interpreter — and absence is not an error: ``None``
    is the warning-skip signal of the api/sandbox-only environments.

    Returns:
        Absolute path to the npm executable, or ``None`` when npm is not on PATH.
    """
    return shutil.which("npm")


def _run(argv: list[str], step: str) -> subprocess.CompletedProcess:
    """Run one provisioning command, mapping a failure to the hook error.

    Args:
        argv: The full command line to run.
        step: The human-readable command name carried by the raised error.

    Returns:
        The completed process with captured stdout/stderr.

    Raises:
        RuntimeError: When the command exits non-zero, carrying the command's own stderr.
    """
    try:
        return subprocess.run(argv, capture_output=True, check=True, text=True)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip() or str(error)
        raise RuntimeError(f"{step} failed: {detail}") from error


def _resolve_cli(npm: str) -> str:
    """Resolve the playwright-cli executable installed by the npm step.

    PATH wins; otherwise the executable is derived from the npm global prefix — the npm
    global bin directory may sit outside the process PATH, and the sudo branch of the
    skills step requires an absolute path (sudo resets PATH through secure_path).

    Args:
        npm: Absolute path to the npm executable.

    Returns:
        Absolute path to the playwright-cli executable.

    Raises:
        RuntimeError: When the executable is neither on PATH nor under the npm global prefix.
    """
    found = shutil.which("playwright-cli")
    if found:
        return found

    prefix = _run([npm, "prefix", "-g"], "npm prefix -g").stdout.strip()
    candidate = Path(prefix) / "bin" / "playwright-cli"
    if candidate.is_file():
        return str(candidate)

    raise RuntimeError(f"playwright-cli executable not found (looked on PATH and under {prefix}/bin after npm install)")


def install(user: str | None = None) -> None:
    """The pybuggy post-install hook: provision the playwright agent CLI of the web kind.

    The goga platform imports this callable from the package facade after a successful pip
    and passes the initiating user by name; it is not called by users or test suites.

    Args:
        user: The initiating user of the installation (SUDO_USER when goga runs under
            sudo, else the current OS user); ``None`` when invoked by hand without the
            argument.
    """
    npm = _find_npm()
    if npm is None:
        logger.warning("npm not found; playwright cli install skipped", extra={"requirement": "npm"})
        return

    _run([npm, "install", "-g", _CLI_PACKAGE], "npm install -g @playwright/cli")
    logger.info("playwright cli package installed", extra={"package": _CLI_PACKAGE})

    cli = _resolve_cli(npm)

    argv = [cli, *_SKILLS_ARGS]
    if user is not None and user != getpass.getuser():
        # Root install initiated by a real user: -H pins HOME to the target user, so the
        # global skills land in the initiating user's home, not in /root.
        argv = ["sudo", "-H", "-u", user, *argv]
    _run(argv, "playwright-cli install --skills --global")
    logger.info(
        "playwright cli skills installed",
        extra={"user": user if user is not None else getpass.getuser(), "scope": "global"},
    )
