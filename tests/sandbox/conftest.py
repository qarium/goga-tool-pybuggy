"""Shared pytest fixtures for the sandbox test package.

Also carries the container-runtime availability probe and the ``requires_docker`` skip condition
every docker-gated test in the plan reuses: ``from ..conftest import requires_docker``.
"""

import functools
import pathlib
from collections.abc import Callable

import docker
import pytest


@functools.lru_cache(maxsize=1)
def docker_available() -> bool:
    """Probe the container-runtime availability once per test session.

    Pings the daemon through the docker SDK client — the same client testcontainers drives — and
    treats any failure as unavailability, so container-dependent tests skip instead of hanging on
    a silent connection timeout.

    Returns:
        True when a docker-compatible daemon answers the ping, False otherwise.
    """
    try:
        return bool(docker.from_env().ping())
    except Exception:
        return False


requires_docker = pytest.mark.skipif(
    not docker_available(),
    reason="docker-compatible container runtime unavailable",
)


@pytest.fixture
def sandbox_yaml(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], pathlib.Path]:
    """Write ``.sandbox.yml`` under ``tmp_path`` and chdir there.

    Args:
        tmp_path: The per-test temporary directory serving as the consumer repository root.
        monkeypatch: The pytest monkeypatch fixture performing the chdir.

    Returns:
        A writer placing ``content`` at ``.sandbox.yml`` under ``tmp_path``, returning the written path.
    """
    monkeypatch.chdir(tmp_path)

    def _write(content: str) -> pathlib.Path:
        path = tmp_path / ".sandbox.yml"
        path.write_text(content, encoding="utf-8")
        return path

    return _write
