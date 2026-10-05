"""Onboarding-session participation — question block, answer payloads, and the session seam.

``run_session`` drives the engine-owned session; the declare/amend hooks and the pure builders feed it.
"""

import logging

import click
from goga.onboarding import FileGenerator, InitLogic, Question, QuestionGroup, Questionnaire, ToolParticipation

from ...config import GitEntry, SpecEntry
from ...plugin import PluginConfigKeys

logger = logging.getLogger(__name__)

# Prompt text per optional scalar key — mirrors the ``ApiPlugin`` option docstrings.
# ``BASE_URL``/``HEADERS``/``LOADER`` are never surveyed here.
_SCALAR_PROMPTS: dict[PluginConfigKeys, str] = {
    PluginConfigKeys.TIMEOUT: ("timeout — request timeout in seconds for HTTP calls (optional). Enter to skip"),
    PluginConfigKeys.RETRIES: (
        "retries — flaky rerun count for failing tests across the suite (optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_TIMEOUT: (
        "assert_timeout — baseline polling timeout in seconds for retrying assertions (optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_DELAY: (
        "assert_delay — seconds between assertion polling attempts (optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_FIELD_CLASS: (
        'assert_field_class — dotted "module:Class" of a custom AssertField subclass (optional). Enter to skip'
    ),
    PluginConfigKeys.ASSERT_RESPONSE_CLASS: (
        'assert_response_class — dotted "module:Class" of a custom Expect subclass (optional). Enter to skip'
    ),
}

# Numeric members coerced to their ``ApiPlugin`` types so the YAML scalar is a number;
# unanswered members are dropped from the payload.
_NUMERIC_MEMBERS: dict[PluginConfigKeys, type] = {
    PluginConfigKeys.TIMEOUT: float,
    PluginConfigKeys.RETRIES: int,
    PluginConfigKeys.ASSERT_TIMEOUT: int,
    PluginConfigKeys.ASSERT_DELAY: float,
}

# The spec formats a ``SpecEntry`` accepts — the shared strictness of the first spec and the
# surveyed extras (a ``type`` outside this tuple is always rejected).
_SPEC_TYPES = ("swagger", "openapi")


def pybuggy_questions() -> list[Question]:
    """Build the declarative pybuggy question block in survey order.

    Exact ids and order — the answer keys consumed downstream; extra specs go to :func:`survey_extra_specs`.

    Returns:
        The question records — ``Question`` items plus the single ``first_spec``
        ``QuestionGroup`` (exactly one nesting level, simple children only).
    """
    items: list[Question] = [Question(id="base_url", kind="input", prompt="Base URL (Jinja2 template, required)")]

    for member in PluginConfigKeys:
        if member in (PluginConfigKeys.BASE_URL, PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER):
            continue

        items.append(Question(id=member.value, kind="input", default="", prompt=_SCALAR_PROMPTS[member]))

    items.append(
        QuestionGroup(
            id="first_spec",
            prompt="The first spec",
            children=[
                Question(id="name", kind="input", prompt="Spec name"),
                Question(id="type", kind="choice", prompt="Spec type", choices=list(_SPEC_TYPES)),
                Question(id="location", kind="input", prompt="Spec location (path from project root)"),
                Question(id="git_url", kind="input", default="", prompt="Git URL (empty — no git source)"),
                Question(id="git_location", kind="input", default="", prompt="Path inside the repository"),
                Question(id="git_ref", kind="input", default="", prompt="Git ref (branch/tag; empty — default branch)"),
            ],
        )
    )

    items.append(
        Question(
            id="autonomous",
            kind="confirm",
            default=False,
            prompt="Run the api.automate pipeline unattended (autonomous mode)?",
        )
    )

    return items


def _required(prompt: str) -> str:
    """Ask a required free-text value, re-asking while the entry strips to nothing.

    An empty entry re-asks with a ``(required)`` suffix; a ``click.Abort`` propagates unchanged.

    Args:
        prompt: The prompt text of the required value.

    Returns:
        The non-empty stripped answer.
    """
    value = click.prompt(prompt, default="", show_default=False).strip()

    while not value:
        value = click.prompt(f"{prompt} (required)", default="", show_default=False).strip()

    return value


def survey_extra_specs() -> list[dict[str, object]]:
    """Interactively survey the additional specs — the confirm-gated per-field follow-up.

    The repeating confirm accepts any number of extras; empty git fields mean no source / default branch.

    Returns:
        The surveyed specs — one mapping per accepted spec, keyed by the ``first_spec``
        child ids (``name``/``type``/``location``/``git_url``/``git_location``/``git_ref``).

    Raises:
        click.Abort: Forwarded unchanged from a cancelled prompt; the mediator drops the
            contribution with a warning.
    """
    surveyed: list[dict[str, object]] = []

    while click.confirm("Add another spec?", default=False):
        spec: dict[str, object] = {
            "name": _required("Spec name"),
            "type": click.prompt("Spec type", type=click.Choice(list(_SPEC_TYPES))),
            "location": _required("Spec location (path from project root)"),
            "git_url": click.prompt("Git URL (empty — no git source)", default="", show_default=False).strip(),
            "git_location": click.prompt("Path inside the repository", default="", show_default=False).strip(),
            "git_ref": click.prompt(
                "Git ref (branch/tag; empty — default branch)", default="", show_default=False
            ).strip(),
        }

        surveyed.append(spec)

    return surveyed


def build_config_data(
    answers: dict[str, object],
    extra_specs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build the plain serializable tool-config payload from the session answers.

    The payload is plain serializable data only — the engine ``yaml.dump``s it verbatim.

    Args:
        answers: The pybuggy answer view (core sections plus the own block under local names).
        extra_specs: The ``survey_extra_specs`` mappings; None when the gate was declined.

    Returns:
        The tool-config payload keyed in plugin key order, then ``pipelines`` when the
        autonomy answer enables it, with ``specs`` last.

    Raises:
        ValueError: If a numeric member's answer cannot coerce to its target type (the
            mediator soft-drops the contribution).
    """
    specs = parse_specs(answers.get("first_spec") or {}, extra_specs)
    data: dict[str, object] = {}

    for member in PluginConfigKeys:
        if member in (PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER):
            continue

        value = answers.get(member.value)
        if value is None or value == "":
            continue

        data[member.value] = _NUMERIC_MEMBERS[member](value) if member in _NUMERIC_MEMBERS else value

    if answers.get("autonomous"):
        data["pipelines"] = {"api.automate": {"autonomous": True}}

    data["specs"] = {name: entry.model_dump(exclude_none=True) for name, entry in specs.items()}

    return data


def build_config_amendments() -> dict[str, object]:
    """Return the tool's declared-intent answer amendments.

    Exactly ``{"build.review.skip": True}`` — consumer enforcement is the bootstrap's ``ensure_review_skip``.

    Returns:
        The single amendment mapping.
    """
    return {"build.review.skip": True}


def _git_entry(url: object, location: object, ref: object) -> GitEntry | None:
    """Build a ``GitEntry`` from raw git answers — ``None`` unless url AND location are non-empty.

    Args:
        url: The ``git_url`` answer (clone URL).
        location: The ``git_location`` answer (path inside the repository).
        ref: The ``git_ref`` answer (branch/tag); empty maps to ``None`` (default branch).

    Returns:
        The typed git source, or ``None`` when the spec is local-only.
    """
    if not url or not location:
        return None

    return GitEntry(url=str(url), location=str(location), ref=str(ref) if ref else None)


def _first_spec_entry(spec_answers: dict[str, object]) -> tuple[str, SpecEntry]:
    """Validate the ``first_spec`` group answers and build the typed entry.

    Args:
        spec_answers: The ``first_spec`` group answers (child id → answer).

    Returns:
        The spec name and its typed ``SpecEntry`` (git attached only when both git
        url and git location are answered).

    Raises:
        ValueError: If any of name, type, or location is empty or invalid.
    """
    name = spec_answers.get("name")
    spec_type = spec_answers.get("type")
    location = spec_answers.get("location")

    if not name:
        raise ValueError("first spec name must not be empty")

    if spec_type not in _SPEC_TYPES:
        raise ValueError(f"first spec type {spec_type!r} must be swagger or openapi")

    if not location:
        raise ValueError("first spec location must not be empty")

    git = _git_entry(spec_answers.get("git_url"), spec_answers.get("git_location"), spec_answers.get("git_ref"))

    return str(name), SpecEntry(type=str(spec_type), location=str(location), git=git)


def _extra_spec_entry(spec_answers: dict[str, object]) -> tuple[str, SpecEntry] | None:
    """Build one surveyed extra spec into a typed entry.

    A malformed record is WARNING-logged and dropped, never raised.

    Args:
        spec_answers: One surveyed extra-spec mapping (the ``first_spec`` child ids).

    Returns:
        The spec name and its typed ``SpecEntry``, or ``None`` when the record is malformed.
    """
    name = str(spec_answers.get("name") or "").strip()
    spec_type = spec_answers.get("type")
    location = str(spec_answers.get("location") or "").strip()

    if not name or spec_type not in _SPEC_TYPES or not location:
        logger.warning("malformed extra spec skipped", extra={"spec": name})
        return None

    git = _git_entry(spec_answers.get("git_url"), spec_answers.get("git_location"), spec_answers.get("git_ref"))

    return name, SpecEntry(type=str(spec_type), location=location, git=git)


def parse_specs(
    spec_answers: dict[str, object],
    extra_specs: list[dict[str, object]] | None,
) -> dict[str, SpecEntry]:
    """Parse the first-spec answers and the surveyed extra specs into typed entries.

    Extras are lenient — malformed records and duplicate names are skipped with a WARNING, keeping the first entry.

    Args:
        spec_answers: The ``first_spec`` group answers (child id → answer).
        extra_specs: The ``survey_extra_specs`` mappings, or ``None`` when the gate was
            declined.

    Returns:
        The ordered mapping of spec name to ``SpecEntry``; always holds at least the first spec.

    Raises:
        ValueError: If the first spec is incomplete or invalid.
    """
    name, entry = _first_spec_entry(spec_answers)
    specs: dict[str, SpecEntry] = {name: entry}

    for spec in extra_specs or []:
        parsed = _extra_spec_entry(spec)

        if parsed is None:
            continue

        extra_name, extra_entry = parsed

        if extra_name in specs:
            logger.warning("duplicate spec name skipped", extra={"spec": extra_name})
            continue

        specs[extra_name] = extra_entry

    return specs


def run_session() -> int:
    """Run the engine-owned onboarding session with pybuggy invited.

    No engine error is caught or wrapped; a failed tool contribution is soft (warned and dropped).

    Returns:
        The engine session exit code, propagated as-is.
    """
    logic = InitLogic(
        questionnaire=Questionnaire(),
        generator=FileGenerator(),
        participation=ToolParticipation(invited=["pybuggy"]),
    )

    return logic.run()


def declare_pybuggy_session(context: object) -> None:
    """Declare the pybuggy question block in the session (participation moment one).

    No-op unless invited; the ``convention`` skip keeps the conventions slot for the pybuggy test convention.

    Args:
        context: The ``ToolDeclaration`` proxy delivered by name from the hooks platform.
    """
    if not context.invited:
        return

    for item in pybuggy_questions():
        context.declare(item)

    context.skip("convention")


def amend_pybuggy_config(context: object) -> None:
    """Amend the session answers and buffer the tool config (participation moment two).

    No-op unless invited; any exception makes the mediator drop the contribution (the session continues).

    Args:
        context: The ``ToolContribution`` proxy delivered by name from the hooks platform.

    Raises:
        ValueError: If a numeric answer cannot coerce — propagated so the mediator
            soft-drops the contribution.
    """
    if not context.invited:
        return

    answers = context.answers
    extra_specs = survey_extra_specs()

    for id, value in build_config_amendments().items():
        context.answer(id, value)

    context.write_config("config.yml", build_config_data(answers, extra_specs))
