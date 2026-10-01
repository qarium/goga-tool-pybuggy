"""Onboarding-session participation — question block, answer payloads, and the session seam.

The goga 2.0 session-participation model: ``run_session`` drives the engine-owned
onboarding session with pybuggy invited; ``declare_pybuggy_session`` and
``amend_pybuggy_config`` are the two participation hooks subscribed by the root
facade callback; the pure builders (``pybuggy_questions``, ``build_config_data``,
``build_config_amendments``, ``parse_specs``) turn session answers into the plain
serializable tool-config payload the engine writes verbatim into
``.goga/tools/pybuggy/config.yml``.
"""

import logging

from goga.onboarding import FileGenerator, InitLogic, Question, QuestionGroup, Questionnaire, ToolParticipation

from ...config import GitEntry, SpecEntry
from ...plugin import PluginConfigKeys

logger = logging.getLogger(__name__)

# Human-readable prompt text for each optional scalar plugin key — mirrors the
# ``ApiPlugin`` option docstrings so the user knows what every field is for.
# ``BASE_URL`` is collected separately as a (possibly multi-line) Jinja2 template;
# ``HEADERS``/``LOADER`` are complex members and never surveyed here.
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

# Numeric plugin members coerced to their ``ApiPlugin`` option types in ``build_config_data``,
# so the emitted YAML scalar is a number instead of the plain string captured by the session
# answer. All other scalar members stay plain strings; an unanswered member (``None``/``""``)
# is dropped from the payload entirely.
_NUMERIC_MEMBERS: dict[PluginConfigKeys, type] = {
    PluginConfigKeys.TIMEOUT: float,
    PluginConfigKeys.RETRIES: int,
    PluginConfigKeys.ASSERT_TIMEOUT: int,
    PluginConfigKeys.ASSERT_DELAY: float,
}

# Field count of the ``extra_specs`` compact form: ``name|type|location|git_url|git_location|git_ref``.
# On a longer line the first six fields win; anything past ``git_ref`` is ignored.
_GIT_FIELDS = 6

# The spec formats a ``SpecEntry`` accepts — the shared strictness of the first spec and the
# lenient extra lines (a ``type`` outside this tuple is always rejected).
_SPEC_TYPES = ("swagger", "openapi")

# Minimum field count of a well-formed ``extra_specs`` line: ``name``, ``type``, ``location``.
# Shorter lines are malformed and skipped; the git fields (up to ``_GIT_FIELDS`` total) are optional.
_SPEC_MIN_FIELDS = 3


def pybuggy_questions() -> list[Question]:
    """Build the declarative pybuggy question block in survey order.

    Exact ids and order — they are the answer keys consumed downstream: ``base_url``
    first (input, no default — the engine re-asks until non-empty, so it is required);
    then one input per ``PluginConfigKeys`` member except ``BASE_URL``, ``HEADERS``, and
    ``LOADER`` (``default=""`` — Enter yields ``""``, optional; prompt texts from
    ``_SCALAR_PROMPTS``); then the one-level group ``first_spec`` (children
    ``name``/``type``/``location``/``git_url``/``git_location``/``git_ref`` — name and
    location required, type a ``swagger``/``openapi`` choice, git fields optional); then
    ``extra_specs`` (input, ``default=""`` — one spec per line in the compact form
    ``name|type|location|git_url|git_location|git_ref``). Survey order equals declaration
    order, and every record is fresh per call.

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
            id="extra_specs",
            kind="input",
            default="",
            prompt="Additional specs, one per line: name|type|location|git_url|git_location|git_ref",
        )
    )

    return items


def build_config_data(answers: dict[str, object]) -> dict[str, object]:
    """Build the plain serializable tool-config payload from the session answers.

    Scalar walk in ``PluginConfigKeys`` declaration order skipping ``HEADERS``/``LOADER``:
    unanswered members (``None``/``""``) are dropped — never written empty — and numeric
    members (``timeout``→float, ``retries``→int, ``assert_timeout``→int, ``assert_delay``→float
    via ``_NUMERIC_MEMBERS``) are coerced. The specs from :func:`parse_specs` land under
    ``specs`` as ``model_dump(exclude_none=True)`` plain mappings, with ``specs`` last. The
    payload is plain serializable data only — never pydantic objects (the engine
    ``yaml.dump``s buffered data verbatim and silently drops unserializable files).

    Args:
        answers: The pybuggy answer view (core sections plus the own block under local names).

    Returns:
        The tool-config payload keyed in plugin key order with ``specs`` last.

    Raises:
        ValueError: If a numeric member's answer cannot coerce to its target type (the
            mediator soft-drops the contribution).
    """
    specs = parse_specs(answers.get("first_spec") or {}, answers.get("extra_specs") or None)
    data: dict[str, object] = {}

    for member in PluginConfigKeys:
        if member in (PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER):
            continue

        value = answers.get(member.value)
        if value is None or value == "":
            continue

        data[member.value] = _NUMERIC_MEMBERS[member](value) if member in _NUMERIC_MEMBERS else value

    data["specs"] = {name: entry.model_dump(exclude_none=True) for name, entry in specs.items()}

    return data


def build_config_amendments() -> dict[str, object]:
    """Return the tool's declared-intent answer amendments.

    Exactly ``{"build.review.skip": True}`` — unconditional, no parameters. The engine
    config mapper drops the key (``_build_config_document`` emits only ``agent``/``env``
    for the build block); consumer-visible enforcement is the bootstrap's
    :func:`goga_tool_pybuggy.commands.init.ensure_review_skip`.

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

    Strict — the single source of the first spec: a non-empty ``name``, a ``type``
    in ``_SPEC_TYPES``, and a non-empty ``location`` are all required.

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


def _extra_spec_entry(line: str) -> tuple[str, SpecEntry] | None:
    """Parse one ``extra_specs`` compact-form line into a typed entry.

    Lenient — a malformed line (fewer than three fields, an empty name or
    location, an invalid type) is WARNING-logged and dropped, never raised. On a
    line longer than ``_GIT_FIELDS`` fields the first six win.

    Args:
        line: The raw compact-form line ``name|type|location|git_url|git_location|git_ref``.

    Returns:
        The spec name and its typed ``SpecEntry``, or ``None`` when the line is malformed.
    """
    parts = [part.strip() for part in line.split("|")]

    if len(parts) < _SPEC_MIN_FIELDS or not parts[0] or parts[1] not in _SPEC_TYPES or not parts[2]:
        logger.warning("malformed extra spec line skipped", extra={"line": line})
        return None

    git_url, git_location, git_ref = ([*parts[3:_GIT_FIELDS], "", "", ""])[:3]

    return parts[0], SpecEntry(type=parts[1], location=parts[2], git=_git_entry(git_url, git_location, git_ref))


def parse_specs(spec_answers: dict[str, object], extra_specs: str | None) -> dict[str, SpecEntry]:
    """Parse the first-spec answers and the extra-specs compact lines into typed entries.

    The first spec is strict: a non-empty ``name``, ``type`` in {``swagger``, ``openapi``},
    and a non-empty ``location`` are required — anything else raises ``ValueError`` (the
    mediator soft-drops the contribution upstream). A ``GitEntry(url, location, ref)`` is
    attached only when ``git_url`` AND ``git_location`` are both non-empty
    (``ref = git_ref or None``). The extras are lenient: every non-empty line is split on
    ``|``, malformed lines (fewer than 3 parts, an empty name/location, an invalid type)
    and duplicate names are skipped with a WARNING; a name collision keeps the first entry.

    Args:
        spec_answers: The ``first_spec`` group answers (child id → answer).
        extra_specs: The raw ``extra_specs`` answer — one spec per line in the compact form
            ``name|type|location|git_url|git_location|git_ref`` — or ``None``/empty when absent.

    Returns:
        The ordered mapping of spec name to ``SpecEntry``; always holds at least the first spec.

    Raises:
        ValueError: If the first spec is incomplete or invalid.
    """
    name, entry = _first_spec_entry(spec_answers)
    specs: dict[str, SpecEntry] = {name: entry}

    if extra_specs:
        for line in extra_specs.splitlines():
            if not line.strip():
                continue

            parsed = _extra_spec_entry(line)
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

    Builds ``InitLogic(questionnaire=Questionnaire(), generator=FileGenerator(),
    participation=ToolParticipation(invited=["pybuggy"]))`` and returns ``logic.run()``
    unchanged. The session is engine-owned throughout: an existing ``.goga/config.yml``
    ends it with 0 and no side effects; a tool contribution failure is soft (the engine
    warns and drops the contribution, the session still returns 0); a user abort returns
    a quiet 1. No engine error is caught or wrapped here.

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

    When ``context.invited`` is falsy the routine returns without calling anything;
    otherwise every item of :func:`pybuggy_questions` is declared in survey order via
    ``context.declare``. Nothing is surveyed or prompted (the engine owns the asking),
    no answers are read, and no core subtree is skipped.

    Args:
        context: The ``ToolDeclaration`` proxy delivered by name from the hooks platform.
    """
    if not context.invited:
        return

    for item in pybuggy_questions():
        context.declare(item)


def amend_pybuggy_config(context: object) -> None:
    """Amend the session answers and buffer the tool config (participation moment two).

    When ``context.invited`` is falsy the routine returns without calling anything;
    otherwise the declared-intent amendments from :func:`build_config_amendments` are
    committed via ``context.answer`` and the plain-data payload from
    :func:`build_config_data` is buffered via ``context.write_config("config.yml", ...)``
    — the engine serializes it into ``.goga/tools/pybuggy/config.yml``. Files are never
    written directly and another tool's answers are never read; an exception propagates
    to the mediator, which drops the whole contribution with a warning naming pybuggy
    (soft — the session and the bootstrap still complete).

    Args:
        context: The ``ToolContribution`` proxy delivered by name from the hooks platform.

    Raises:
        ValueError: If a numeric answer cannot coerce — propagated so the mediator
            soft-drops the contribution.
    """
    if not context.invited:
        return

    answers = context.answers

    for id, value in build_config_amendments().items():
        context.answer(id, value)

    context.write_config("config.yml", build_config_data(answers))
