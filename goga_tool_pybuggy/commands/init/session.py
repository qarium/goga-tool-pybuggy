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

from goga.onboarding import Question

from ...config import SpecEntry
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
    raise NotImplementedError


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
    raise NotImplementedError


def build_config_amendments() -> dict[str, object]:
    """Return the tool's declared-intent answer amendments.

    Exactly ``{"build.review.skip": True}`` — unconditional, no parameters. The engine
    config mapper drops the key (``_build_config_document`` emits only ``agent``/``env``
    for the build block); consumer-visible enforcement is the bootstrap's
    :func:`goga_tool_pybuggy.commands.init.ensure_review_skip`.

    Returns:
        The single amendment mapping.
    """
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


def declare_pybuggy_session(context: object) -> None:
    """Declare the pybuggy question block in the session (participation moment one).

    When ``context.invited`` is falsy the routine returns without calling anything;
    otherwise every item of :func:`pybuggy_questions` is declared in survey order via
    ``context.declare``. Nothing is surveyed or prompted (the engine owns the asking),
    no answers are read, and no core subtree is skipped.

    Args:
        context: The ``ToolDeclaration`` proxy delivered by name from the hooks platform.
    """
    raise NotImplementedError


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
    raise NotImplementedError
