"""Local pytest fixtures for the init-cell tests — the recorder doubles.

The participation doubles mirror the member surface of the engine's onboarding
contexts (``ToolDeclaration`` / ``ToolContribution``) without reaching into
engine internals: plain recorders asserting member usage — what the hooks
declared, amended, and buffered. The composition doubles (the exit-recording
``click.Context``, the order-logging seam, the scripted TTY) serve the
integration tests of the CLI chain and the native-session smoke run.
"""

from collections.abc import Callable

import pytest


class DeclarationRecorder:
    """A ``ToolDeclaration``-like double — records what the declare hook declared.

    Attributes:
        invited: The invitation marker the hook checks first.
        declared: The declared question records and groups, in declaration order.
        skips: The declared skip paths, in call order.
    """

    def __init__(self, invited: bool) -> None:
        """Build a recorder with the given invitation marker and empty buffers.

        Args:
            invited: The invitation marker delivered by the hooks platform.
        """
        self.invited = invited
        self.declared: list[object] = []
        self.skips: list[str] = []

    def declare(self, item: object) -> None:
        """Record one declared question record or group.

        Args:
            item: The declared item — a ``Question`` or a one-level ``QuestionGroup``.
        """
        self.declared.append(item)

    def skip(self, path: str) -> None:
        """Record one declared skip path.

        Args:
            path: The raw skip path.
        """
        self.skips.append(path)


class ContributionRecorder:
    """A ``ToolContribution``-like double — records what the amend hook buffered.

    Attributes:
        invited: The invitation marker the hook checks first.
        answers: The isolated answer view of the tool.
        amendments: The buffered amendments — the dot-path and the value, in call order.
        files: The buffered config files — the file name and the data, in call order.
    """

    def __init__(self, invited: bool, answers: dict[str, object] | None = None) -> None:
        """Build a recorder with the given invitation marker and answer view.

        Args:
            invited: The invitation marker delivered by the hooks platform.
            answers: The tool's answer view (core sections plus the own block).
        """
        self.invited = invited
        self.answers: dict[str, object] = answers or {}
        self.amendments: list[tuple[str, object]] = []
        self.files: list[tuple[str, dict[str, object]]] = []

    def answer(self, id: str, value: object) -> None:
        """Record one buffered amendment.

        Args:
            id: The dot-path of the addressed entry.
            value: The amendment value.
        """
        self.amendments.append((id, value))

    def write_config(self, file: str, data: dict[str, object]) -> None:
        """Record one buffered config file.

        Args:
            file: The file name inside the tool's config directory.
            data: The serializable mapping of the file.
        """
        self.files.append((file, data))


@pytest.fixture
def declaration_recorder() -> Callable[[bool], DeclarationRecorder]:
    """Provide the ``ToolDeclaration``-like recorder constructor for the declare-hook tests."""
    return DeclarationRecorder


@pytest.fixture
def contribution_recorder() -> Callable[..., ContributionRecorder]:
    """Provide the ``ToolContribution``-like recorder constructor for the amend-hook tests."""
    return ContributionRecorder


class ExitRecorder:
    """A ``click.Context`` double recording ``ctx.exit`` codes for the wrapper tests.

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


class SeamRecorder:
    """A seam double appending its name to a shared call-order log and yielding scripted codes.

    Doubles one ``run_init`` seam (``run_session`` / ``run_bootstrap``) patched at
    the orchestrator's import point: every call is recorded with its keyword
    arguments and returns the next scripted exit code.

    Attributes:
        calls: The keyword arguments of every call, in call order.
    """

    def __init__(self, name: str, log: list[str], return_codes: list[int]) -> None:
        """Build a seam recorder appending its name to the shared order log.

        Args:
            name: The seam label appended to the log on every call.
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


class ScriptedTTY:
    """A scripted TTY double answering the session's prompts from two pinned maps.

    The external boundary of the smoke test — the terminal. Confirms are answered
    strictly from the scripted map (an unscripted gate is an unexpected ask); a
    prompt carrying a scripted value returns it, an unscripted prompt accepts its
    offered default (pressing Enter — the optional scalars and git fields), and an
    unscripted prompt without a default is an unexpected ask.

    Attributes:
        confirms: The ``(text, answer)`` confirm calls, in ask order.
        prompts: The ``(text, default, returned)`` prompt calls, in ask order.
    """

    def __init__(self, confirms: dict[str, bool], prompts: dict[str, object]) -> None:
        """Build the double from the pinned answer maps.

        Args:
            confirms: The confirm gate texts and their scripted answers.
            prompts: The prompt texts and their scripted inputs — the optional
                ones stay unscripted and read as Enter.
        """
        self._confirms = dict(confirms)
        self._prompts = dict(prompts)
        self.confirms: list[tuple[str, bool]] = []
        self.prompts: list[tuple[str, object, object]] = []

    def confirm(self, text: str, default: bool = False, **_: object) -> bool:
        """Answer one confirm gate from the scripted map.

        Args:
            text: The gate text the engine asks.
            default: The offered default (recorded by the caller's kwargs, unused).
            **_: The remaining click kwargs (absorbed).

        Returns:
            The scripted gate answer.

        Raises:
            AssertionError: When the engine asks a gate the map does not carry.
        """
        if text not in self._confirms:
            raise AssertionError(f"unexpected confirm: {text!r}")

        answer = self._confirms[text]
        self.confirms.append((text, answer))
        return answer

    def prompt(self, text: str, default: object = None, **_: object) -> object:
        """Answer one input or choice prompt from the scripted map, or with Enter.

        Args:
            text: The prompt text the engine asks.
            default: The offered default — returned for an unscripted prompt.
            **_: The remaining click kwargs (the choice type, absorbed).

        Returns:
            The scripted input, or the offered default for an unscripted prompt.

        Raises:
            AssertionError: When an unscripted prompt offers no default — the
                map must carry every required input.
        """
        if text in self._prompts:
            answer = self._prompts[text]
        elif default is not None:
            answer = default
        else:
            raise AssertionError(f"unexpected prompt without a default: {text!r}")

        self.prompts.append((text, default, answer))
        return answer


@pytest.fixture
def exit_recorder() -> type[ExitRecorder]:
    """Provide the ``click.Context``-like exit recorder for the wrapper composition tests."""
    return ExitRecorder


@pytest.fixture
def seam_recorder() -> type[SeamRecorder]:
    """Provide the order-logging seam double constructor for the CLI chain tests."""
    return SeamRecorder


@pytest.fixture
def scripted_tty() -> type[ScriptedTTY]:
    """Provide the scripted-TTY double constructor for the session smoke test."""
    return ScriptedTTY
