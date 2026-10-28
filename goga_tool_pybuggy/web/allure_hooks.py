"""Allure step reporting over the prettyplay hook contract — steps, groups, failure screenshots.

Active only when allure-pytest is installed: the guarded import leaves ``allure`` None and the
web fixture constructs no hooks (see ``allure-pytest``).
"""

from contextlib import ExitStack, suppress
from types import TracebackType

from playwright.sync_api import Error as PlaywrightError
from prettyplay import PrettyPlay, StepHooks
from prettyplay.failures import PrettyplayError

try:
    import allure
except ImportError:
    allure = None  # the Allure integration stays inactive


class _AllureStepWrapper:
    """Enter/exit an allure step context, exiting broken when a failure was recorded.

    The recorded exception marks the step broken in the report — ``AssertionError`` for
    assertion steps, a generic ``Exception`` otherwise (the class is chosen by ``fail``).
    """

    def __init__(self, title: str) -> None:
        """Hold the allure step context of ``title`` — entered by ``__enter__``.

        Args:
            title: The rendered step title, e.g. ``[assertion] Find results``.
        """
        self._step = allure.step(title)
        self._failed_exception: Exception | None = None

    def __enter__(self) -> "_AllureStepWrapper":
        """Enter the underlying allure step context.

        Returns:
            The wrapper itself — ``fail`` records the broken-exit exception on it.
        """
        self._step.__enter__()

        return self

    def fail(self, reason: str, *, cls: type[Exception] = AssertionError) -> None:
        """Record the failure the step context exits with.

        Args:
            reason: The failure description.
            cls: The exception class marking the step broken in the report.
        """
        self._failed_exception = cls(reason)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Close the underlying allure step context — broken when an error is pending.

        Args:
            exc_type: The type of the exception leaving the block, if any.
            exc_value: The exception leaving the block, if any.
            traceback: The traceback of the exception leaving the block, if any.

        Returns:
            The suppression decision of the underlying allure step context.
        """
        error_to_raise = exc_type or self._failed_exception

        if error_to_raise:
            return self._step.__exit__(AssertionError, error_to_raise, traceback)

        return self._step.__exit__(None, None, None)


class AllureStepHooks(StepHooks):
    """Allure reporting over the prettyplay step events — nested steps and groups, balanced exits.

    Two exit stacks (steps and groups) keep the enter/exit pairs balanced even when a step fails
    mid-group; the failure screenshot is captured best-effort. Constructed only when the guarded
    ``allure`` import succeeded — never on import failure.

    Args:
        play: The prettyplay runtime whose steps are reported — the failure screenshot source.
    """

    def __init__(self, play: PrettyPlay) -> None:
        """Hold the reported runtime and open the two balanced exit stacks.

        Args:
            play: The prettyplay runtime whose steps are reported — the failure screenshot source.
        """
        self._play = play

        self._step: _AllureStepWrapper | None = None
        self._step_stack = ExitStack()
        self._group_stack = ExitStack()

    def on_group_started(self, group_prompt: str) -> None:
        """Enter an allure step context titled ``[group] <group_prompt>`` on the group stack.

        Args:
            group_prompt: The group sentence.
        """
        self._group_stack.enter_context(allure.step("[group] " + group_prompt))

    def on_group_finished(self, group_prompt: str) -> None:  # noqa: ARG002
        """Close the group stack — every entered group context exits.

        Args:
            group_prompt: The group sentence.
        """
        self._group_stack.close()
        self._group_stack = ExitStack()

    def on_step_started(self, step_text: str, step_type: str) -> None:
        """Enter an allure step wrapper titled ``[<step_type>] <step_text>`` on the step stack.

        Args:
            step_text: The step sentence.
            step_type: The step type (action or assertion).
        """
        self._step = _AllureStepWrapper(f"[{step_type}] {step_text}")
        self._step_stack.enter_context(self._step)

    def on_step_failed(self, step_text: str, step_type: str, error: str) -> None:  # noqa: ARG002
        """Mark the current step failed and attach the best-effort failure screenshot.

        ``AssertionError`` marks an assertion step broken, a generic ``Exception`` every other
        type. The capture is best-effort: the no-page error (a ``PrettyplayError``) and a capture
        failure (a ``PlaywrightError``) are both swallowed — no page, no screenshot, the failure
        itself is already recorded.

        Args:
            step_text: The step sentence.
            step_type: The step type.
            error: The failure description.
        """
        self._step.fail(error, cls=AssertionError if step_type == "assertion" else Exception)

        # best-effort: no page (PrettyplayError) or a capture failure (PlaywrightError) —
        # no screenshot, the failure itself is already recorded
        with suppress(PlaywrightError, PrettyplayError):
            allure.attach(
                self._play.get_screenshot(),
                name="screenshot.png",
                attachment_type=allure.attachment_type.PNG,
            )

    def on_step_finished(self, step_text: str, step_type: str, outcome: str) -> None:  # noqa: ARG002
        """Close the step stack — the step context exits with the accumulated failure.

        Args:
            step_text: The step sentence.
            step_type: The step type.
            outcome: The step outcome.
        """
        self._step_stack.close()
        self._step_stack = ExitStack()
