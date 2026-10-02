"""Onboarding-session participation — question block, answer payloads, and the session seam.

The goga 2.0 session-participation model: ``run_session`` drives the engine-owned
onboarding session with pybuggy invited; ``declare_pybuggy_session`` and
``amend_pybuggy_config`` are the two participation hooks subscribed by the root
facade callback; the pure builders (``pybuggy_questions``, ``build_config_data``,
``build_config_amendments``, ``parse_specs``) turn session answers into the plain
serializable tool-config payload the engine writes verbatim into
``.goga/tools/pybuggy/config.yml``. The additional specs are the one part the
declarative engine records cannot express (a confirm gate plus repeated per-field
groups), so ``survey_extra_specs`` asks them itself at the amendment moment —
right after the engine survey, in the same screen position the 1.x wizard used.
"""

import logging

import click
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

# The spec formats a ``SpecEntry`` accepts — the shared strictness of the first spec and the
# surveyed extras (a ``type`` outside this tuple is always rejected).
_SPEC_TYPES = ("swagger", "openapi")


def pybuggy_questions() -> list[Question]:
    """Build the declarative pybuggy question block in survey order.

    Exact ids and order — they are the answer keys consumed downstream: ``base_url``
    first (input, no default — the engine re-asks until non-empty, so it is required);
    then one input per ``PluginConfigKeys`` member except ``BASE_URL``, ``HEADERS``, and
    ``LOADER`` (``default=""`` — Enter yields ``""``, optional; prompt texts from
    ``_SCALAR_PROMPTS``); then the one-level group ``first_spec`` (children
    ``name``/``type``/``location``/``git_url``/``git_location``/``git_ref`` — name and
    location required, type a ``swagger``/``openapi`` choice, git fields optional). The
    additional specs are NOT declared here — a confirm-gated repeated group is beyond the
    declarative records, so ``survey_extra_specs`` asks them at the amendment moment.
    Survey order equals declaration order, and every record is fresh per call.

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

    return items


def _required(prompt: str) -> str:
    """Ask a required free-text value, re-asking while the entry strips to nothing.

    The first ask is plain; an empty entry re-asks with a ``(required)`` prompt suffix —
    the 1.x wizard pattern. A ``click.Abort`` (Ctrl-C) propagates unchanged.

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

    The one pybuggy-owned ask of the session, run at the amendment moment (right after the
    engine survey asked the ``first_spec`` group): ``Add another spec?`` (confirm, default
    no) gates the whole block; each accepted spec is then asked field by field in the
    ``first_spec`` order — ``name`` (required, re-asked when empty), ``type`` (a
    ``swagger``/``openapi`` choice), ``location`` (required, re-asked), then the optional
    git fields (an empty ``git_url`` means no git source; an empty ``git_ref`` means the
    default branch) — and the confirm repeats, so any number of extras can be entered.

    Returns:
        The surveyed specs — one mapping per accepted spec, keyed by the ``first_spec``
        child ids (``name``/``type``/``location``/``git_url``/``git_location``/``git_ref``).

    Raises:
        click.Abort: Forwarded unchanged from any cancelled prompt — the engine mediator
            then drops the whole pybuggy contribution with a warning and the session
            continues.
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

    Scalar walk in ``PluginConfigKeys`` declaration order skipping ``HEADERS``/``LOADER``:
    unanswered members (``None``/``""``) are dropped — never written empty — and numeric
    members (``timeout``→float, ``retries``→int, ``assert_timeout``→int, ``assert_delay``→float
    via ``_NUMERIC_MEMBERS``) are coerced. The specs from :func:`parse_specs` — the
    ``first_spec`` group answer plus the ``survey_extra_specs`` mappings — land under
    ``specs`` as ``model_dump(exclude_none=True)`` plain mappings, with ``specs`` last. The
    payload is plain serializable data only — never pydantic objects (the engine
    ``yaml.dump``s buffered data verbatim and silently drops unserializable files).

    Args:
        answers: The pybuggy answer view (core sections plus the own block under local names).
        extra_specs: The ``survey_extra_specs`` mappings; None when the gate was declined.

    Returns:
        The tool-config payload keyed in plugin key order with ``specs`` last.

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


def _extra_spec_entry(spec_answers: dict[str, object]) -> tuple[str, SpecEntry] | None:
    """Build one surveyed extra spec into a typed entry.

    Lenient guard of the (prompt-validated) ``survey_extra_specs`` mapping: a record
    without a non-empty ``name``, a ``type`` in ``_SPEC_TYPES``, and a non-empty
    ``location`` is WARNING-logged and dropped, never raised.

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

    The first spec is strict: a non-empty ``name``, ``type`` in {``swagger``, ``openapi``},
    and a non-empty ``location`` are required — anything else raises ``ValueError`` (the
    mediator soft-drops the contribution upstream). A ``GitEntry(url, location, ref)`` is
    attached only when ``git_url`` AND ``git_location`` are both non-empty
    (``ref = git_ref or None``). The extras are lenient: every surveyed mapping becomes
    its ``SpecEntry``; a malformed record (unreachable through the prompt validation) and
    a duplicate name are skipped with a WARNING; a name collision keeps the first entry.

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
    ``context.declare``, and the core ``convention`` section is skipped via
    ``context.skip`` — a pybuggy session must not offer the goga base-convention
    download, because the engine would land the language conventions in
    ``.goga/usages/conventions.md`` first and the bootstrap's skip-if-exists slot gate
    would then keep them instead of the pybuggy test convention. Nothing is surveyed or
    prompted (the engine owns the asking) and no answers are read. The skip no-ops with
    an engine warning when the section is already absent (an existing conventions file).

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

    When ``context.invited`` is falsy the routine returns without calling anything;
    otherwise the additional specs are surveyed first via :func:`survey_extra_specs`
    (the confirm-gated per-field follow-up — the declarative engine records cannot
    express it), then the declared-intent amendments from
    :func:`build_config_amendments` are committed via ``context.answer`` and the
    plain-data payload from :func:`build_config_data` is buffered via
    ``context.write_config("config.yml", ...)`` — the engine serializes it into
    ``.goga/tools/pybuggy/config.yml``. Files are never written directly and another
    tool's answers are never read; an exception (including a ``click.Abort`` at the
    extra-spec prompts) propagates to the mediator, which drops the whole contribution
    with a warning naming pybuggy (soft — the session and the bootstrap still complete).

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
