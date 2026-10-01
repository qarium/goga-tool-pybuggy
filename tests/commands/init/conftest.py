"""Local pytest fixtures for the init-cell tests — the participation recorder doubles.

The doubles mirror the member surface of the engine's onboarding contexts
(``ToolDeclaration`` / ``ToolContribution``) without reaching into engine
internals: plain recorders asserting member usage — what the hooks declared,
amended, and buffered.
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
