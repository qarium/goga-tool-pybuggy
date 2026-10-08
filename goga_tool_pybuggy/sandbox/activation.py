"""activate_sandbox / active_sandbox routines: the presence-gated pytest activation."""

import logging
from collections.abc import Callable
from typing import Any

import pytest

from .config import SandboxConfig, load_sandbox_config
from .engines import DataOperation
from .sandbox import Sandbox

logger = logging.getLogger(__name__)

_ACTIVE: Sandbox | None = None
_ARMED: SandboxConfig | None = None

_SESSION_START = "pytest_sessionstart"
_SESSION_FINISH = "pytest_sessionfinish"
_RUNTEST_SETUP = "pytest_runtest_setup"

_MARKER_HELP = "pybuggy_services: per-test sandbox data presets (applied by the pybuggy sandbox)"

_KIND_ACTIONS = {"postgresql": "insert", "kafka": "produce", "vault": "put", "http": "stub"}


def activate_sandbox(context: dict[str, object]) -> SandboxConfig | None:
    """Arm the sandbox for the pytest session when the activation document is present.

    Reads and validates ``.goga/tools/pybuggy/sandbox.yml`` under the pybuggy tools home
    of the current working directory; an invalid document fails here, before anything is
    registered or started. With a valid document the three session lifecycle hooks land in
    ``context`` — a pre-existing same-name callable is wrapped, prior first. Without the
    document the call is fully inert.

    Args:
        context: The caller namespace the lifecycle hooks land in.

    Returns:
        The validated configuration — the armed activation; ``None`` when the document is
        absent and nothing is registered.

    Raises:
        ValueError: The document is present but invalid; the message names the document
            location and the offending entry.

    Constraints:
        No containers start here — start belongs to the registered session lifecycle.
    """
    global _ARMED  # noqa: PLW0603 -- module-level armed state, the design's seam

    config = load_sandbox_config(None)

    if config is None:
        logger.debug("sandbox inert", extra={"document": ".goga/tools/pybuggy/sandbox.yml"})

        return None

    _ARMED = config

    _register_hook(context, _SESSION_START, _session_start)
    _register_hook(context, _SESSION_FINISH, _session_finish)
    _register_hook(context, _RUNTEST_SETUP, _runtest_setup)

    logger.info("sandbox armed", extra={"image": config.instance.image, "services": list(config.services)})

    return config


def active_sandbox() -> Sandbox | None:
    """The running session sandbox — the module-level lookup seam.

    Returns:
        The sandbox started by the registered session lifecycle — the same object on every
        call within a session; ``None`` before start and while inactive.
    """
    return _ACTIVE


def _session_start(session: pytest.Session) -> None:
    """Start the armed sandbox before the first test.

    Registers the ``pybuggy_services`` marker first — pre-collection, so applying the
    marker in test modules never emits a warning — then starts the sandbox; its own start
    removes everything started so far on failure.

    Args:
        session: The pytest session about to run its first test.
    """
    global _ACTIVE  # noqa: PLW0603 -- module-level active sandbox, the design's lookup seam

    session.config.addinivalue_line("markers", _MARKER_HELP)

    sandbox = Sandbox(_armed_config())
    sandbox.start()

    _ACTIVE = sandbox

    logger.info("sandbox session started", extra={"base_url": sandbox.base_url})


def _session_finish(session: pytest.Session, exitstatus: int) -> None:
    """Stop the active sandbox at session end, on every exit path.

    Args:
        session: The pytest session that ended.
        exitstatus: The status the session ended with.
    """
    global _ACTIVE  # noqa: PLW0603 -- module-level active sandbox, the design's lookup seam

    logger.debug(
        "sandbox session finishing",
        extra={"exitstatus": exitstatus, "root": str(session.config.rootpath)},
    )

    sandbox = _ACTIVE

    if sandbox is None:
        return

    try:
        sandbox.stop()
    finally:
        _ACTIVE = None


def _runtest_setup(item: pytest.Item) -> None:
    """Give the next test a fresh batch with its marked presets enqueued.

    Args:
        item: The test item being set up.
    """
    sandbox = _ACTIVE

    if sandbox is None:
        return

    sandbox.new_test_batch()

    _enqueue_presets(sandbox, item)


def _enqueue_presets(sandbox: Sandbox, item: pytest.Item) -> None:
    """Enqueue every marked preset of the item, ahead of any in-test declaration.

    Args:
        sandbox: The running session sandbox.
        item: The test item being set up.

    Raises:
        ValueError: A preset targets an unknown service or one of another kind — the
            message lists the configured services.
    """
    enqueued = 0

    for marker in item.iter_markers("pybuggy_services"):
        presets = marker.kwargs.get("presets", {})

        for kind, targets in presets.items():
            for name, declarations in targets.items():
                sandbox._require_service(kind, name)

                for declaration in declarations:
                    sandbox._batch.add(
                        DataOperation(instance=name, kind=kind, action=_KIND_ACTIONS[kind], payload=declaration)
                    )
                    enqueued += 1

    logger.debug("presets enqueued", extra={"item": item.name, "operations": enqueued})


def _armed_config() -> SandboxConfig:
    """The armed configuration the registered hooks act on.

    Returns:
        The configuration validated by ``activate_sandbox``.

    Raises:
        RuntimeError: No configuration is armed — the hooks only run when armed.
    """
    if _ARMED is None:
        raise RuntimeError("the sandbox is not armed — activate_sandbox found no document")

    return _ARMED


def _register_hook(context: dict[str, object], name: str, hook: Callable[..., Any]) -> None:
    """Register ``hook`` under ``name`` into ``context``, any prior callable wrapped first.

    Args:
        context: The caller namespace the hooks land in.
        name: The hook name — one of the three lifecycle hooks.
        hook: The sandbox hook body.
    """
    prior = context.get(name)

    if callable(prior):
        context[name] = _HOOK_WRAPPERS[name](prior, hook)
        logger.debug("prior hook wrapped", extra={"hook": name})

        return

    context[name] = hook


def _wrap_session_start(prior: Callable[..., Any], hook: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap two session-start hooks — the prior callable runs first.

    Args:
        prior: The callable already present in the context.
        hook: The sandbox hook body.

    Returns:
        The wrapped ``pytest_sessionstart``.
    """

    def pytest_sessionstart(session: pytest.Session) -> None:
        """Run the prior hook first, then the sandbox session start."""
        prior(session)
        hook(session)

    return pytest_sessionstart


def _wrap_session_finish(prior: Callable[..., Any], hook: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap two session-finish hooks — the prior callable runs first.

    Args:
        prior: The callable already present in the context.
        hook: The sandbox hook body.

    Returns:
        The wrapped ``pytest_sessionfinish``.
    """

    def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
        """Run the prior hook first, then the sandbox session finish."""
        prior(session, exitstatus)
        hook(session, exitstatus)

    return pytest_sessionfinish


def _wrap_runtest_setup(prior: Callable[..., Any], hook: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap two runtest-setup hooks — the prior callable runs first.

    Args:
        prior: The callable already present in the context.
        hook: The sandbox hook body.

    Returns:
        The wrapped ``pytest_runtest_setup``.
    """

    def pytest_runtest_setup(item: pytest.Item) -> None:
        """Run the prior hook first, then the sandbox test setup."""
        prior(item)
        hook(item)

    return pytest_runtest_setup


_HOOK_WRAPPERS: dict[str, Callable[[Callable[..., Any], Callable[..., Any]], Callable[..., Any]]] = {
    _SESSION_START: _wrap_session_start,
    _SESSION_FINISH: _wrap_session_finish,
    _RUNTEST_SETUP: _wrap_runtest_setup,
}
