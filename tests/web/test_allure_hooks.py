"""Tests for the `goga_tool_pybuggy.web.allure_hooks` module (the Allure step reporting hooks)."""

import inspect
from contextlib import ExitStack

import allure
import goga_tool_pybuggy.web.allure_hooks as allure_hooks_module
import pytest
from goga_tool_pybuggy.web.allure_hooks import AllureStepHooks
from playwright.sync_api import Error as PlaywrightError
from prettyplay import StepHooks
from prettyplay.failures import PrettyplayError


class TestAllureStepHooksContract:
    """Guarded import, subclass relation, and the contract signatures of the hooks."""

    def test_module_exposes_guarded_allure_attribute(self):
        """The module carries the guarded ``allure`` import — the real package in this environment."""
        assert allure_hooks_module.allure is allure
        assert allure_hooks_module.allure is not None

    def test_allure_step_hooks_is_step_hooks_subclass(self):
        """``AllureStepHooks`` subclasses the prettyplay ``StepHooks`` contract."""
        assert issubclass(AllureStepHooks, StepHooks)

    def test_allure_step_hooks_constructor_signature(self):
        """The hooks construct from the reported prettyplay runtime."""
        signature = inspect.signature(AllureStepHooks.__init__)

        assert list(signature.parameters) == ["self", "play"]

    @pytest.mark.parametrize(
        ("method", "params"),
        [
            ("on_group_started", ["group_prompt"]),
            ("on_group_finished", ["group_prompt"]),
            ("on_step_started", ["step_text", "step_type"]),
            ("on_step_failed", ["step_text", "step_type", "error"]),
            ("on_step_finished", ["step_text", "step_type", "outcome"]),
        ],
    )
    def test_hook_methods_carry_contract_signatures(self, method, params):
        """Each of the five hook methods exists with its contract parameter list."""
        signature = inspect.signature(getattr(AllureStepHooks, method))

        assert list(signature.parameters) == ["self", *params]
        assert all(signature.parameters[name].annotation is str for name in params)
        assert signature.return_annotation is None


class _ScreenshotPlay:
    """Play double standing in for the prettyplay runtime at the screenshot boundary."""

    def __init__(self, outcome: bytes | Exception) -> None:
        """Store the capture outcome — bytes are served, an exception is raised.

        Args:
            outcome: The screenshot bytes, or the capture error to raise.
        """
        self._outcome = outcome

    def get_screenshot(self) -> bytes:
        """Serve the configured screenshot bytes or raise the configured capture error.

        Returns:
            The configured screenshot bytes.

        Raises:
            Exception: The configured capture error, raised instead of serving bytes.
        """
        if isinstance(self._outcome, Exception):
            raise self._outcome

        return self._outcome


def _stack_depth(stack: ExitStack) -> int:
    """Count the pending exit callbacks of a stack — the enter/exit balance probe.

    Args:
        stack: The exit stack to measure.

    Returns:
        The number of contexts the stack still owes an exit.
    """
    return len(stack._exit_callbacks)


class TestAllureStepHooksLogic:
    """Logic tests for the screenshot attach, the swallowed capture errors, and the stack balance."""

    def test_allure_step_hooks_failed_step_attaches_screenshot(self, monkeypatch):
        """A failed step attaches the screenshot and exits broken with the type-mapped exception."""
        play = _ScreenshotPlay(b"PNG")
        calls: list[tuple[tuple, dict]] = []

        monkeypatch.setattr(allure, "attach", lambda *args, **kwargs: calls.append((args, kwargs)))

        hooks = AllureStepHooks(play)

        hooks.on_step_started("Find results", "assertion")
        hooks.on_step_failed("Find results", "assertion", "not found")
        assertion_wrapper = hooks._step
        hooks.on_step_finished("Find results", "assertion", "failed")

        hooks.on_step_started("Click search", "action")
        hooks.on_step_failed("Click search", "action", "not clickable")
        action_wrapper = hooks._step
        hooks.on_step_finished("Click search", "action", "failed")

        assert calls == [
            ((b"PNG",), {"name": "screenshot.png", "attachment_type": allure.attachment_type.PNG}),
            ((b"PNG",), {"name": "screenshot.png", "attachment_type": allure.attachment_type.PNG}),
        ]
        assert assertion_wrapper._failed_exception.__class__ is AssertionError
        assert action_wrapper._failed_exception.__class__ is Exception

    @pytest.mark.parametrize(
        "capture_error",
        [
            PlaywrightError("no page"),
            PrettyplayError("no test page yet: run a step first"),
        ],
    )
    def test_allure_step_hooks_swallows_playwright_error(self, capture_error):
        """A capture error of the screenshot never escapes the failed-step hook — the step stays broken."""
        hooks = AllureStepHooks(_ScreenshotPlay(capture_error))

        hooks.on_step_started("Find results", "assertion")
        hooks.on_step_failed("Find results", "assertion", "not found")

        assert hooks._step._failed_exception is not None

        hooks.on_step_finished("Find results", "assertion", "failed")

    def test_allure_step_hooks_stacks_balance_mid_group(self):
        """A step failing mid-group leaves both stacks empty and a later cycle works."""
        hooks = AllureStepHooks(_ScreenshotPlay(b"PNG"))

        hooks.on_group_started("search flow")
        hooks.on_step_started("Find results", "assertion")
        hooks.on_step_failed("Find results", "assertion", "not found")
        hooks.on_step_finished("Find results", "assertion", "failed")
        hooks.on_group_finished("search flow")

        assert _stack_depth(hooks._step_stack) == 0
        assert _stack_depth(hooks._group_stack) == 0

        hooks.on_group_started("second flow")
        hooks.on_step_started("Click search", "action")
        hooks.on_step_finished("Click search", "action", "passed")
        hooks.on_group_finished("second flow")

        assert _stack_depth(hooks._step_stack) == 0
        assert _stack_depth(hooks._group_stack) == 0
        assert hooks._step._failed_exception is None
