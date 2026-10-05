"""Onboarding-session participation — question block, answer payloads, and the session seam.

``run_session`` drives the engine-owned session; the declare/amend hooks and the pure builders feed it.
"""

import importlib.metadata
import logging

import click
from goga.config import resolve_project_name
from goga.onboarding import FileGenerator, InitLogic, Question, QuestionGroup, Questionnaire, ToolParticipation
from goga.version import host_goga_version, minor_version

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

# The goga-python image family in age order — the base-image hints the pybuggy block offers.
# The pybuggy test runtime is pytest, so the python family serves every pybuggy project
# regardless of the surveyed language; the runtime minor tag completes each name (the
# platform's per-language hint table is not part of its public facade — a package constant,
# drifting visibly when a new family member ships).
_BASE_IMAGE_NAMES: tuple[str, ...] = (
    "qarium/goga-python-3.10",
    "qarium/goga-python-3.11",
    "qarium/goga-python-3.12",
    "qarium/goga-python-3.13",
    "qarium/goga-python-3.14",
)

# The fixed Dockerfile path of every pybuggy-initialized project — matches the engine's own
# prompt default and the bootstrap's fallback; the path is never asked.
_DOCKERFILE_PATH = ".goga/Dockerfile"


def pybuggy_questions() -> list[Question]:
    """Build the declarative pybuggy question block in survey order.

    Exact ids and order — the answer keys consumed downstream; the extra specs and the
    autonomy confirm go to the amend-moment surveys (:func:`survey_extra_specs`,
    :func:`survey_autonomy`).

    Returns:
        The question records — the two image inputs, ``base_url``, the scalar members, and
        the single ``first_spec`` ``QuestionGroup`` (exactly one nesting level, simple
        children only).
    """
    tag = minor_version(host_goga_version())
    hints = [f"{name}:{tag}" for name in _BASE_IMAGE_NAMES]
    base_image_prompt = "\n".join(["Base image (FROM)", "Available images:", *[f"  - {hint}" for hint in hints]])
    project_name = resolve_project_name()

    items: list[Question] = [
        Question(id="base_image", kind="input", prompt=base_image_prompt, default=hints[-1]),
        Question(
            id="image",
            kind="input",
            prompt="Built image name",
            default=f"{project_name}:latest" if project_name is not None else None,
        ),
        Question(id="base_url", kind="input", prompt="Base URL (Jinja2 template, required)"),
    ]

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


def survey_autonomy() -> bool:
    """Interactively survey the autonomy confirm — the amend-moment follow-up after the specs.

    Asked by the tool once the whole spec survey completed, so the question never interleaves
    the spec fields; the disabled default keeps existing projects interactive until opted in.

    Returns:
        The autonomy answer — True enables the unattended api.automate window.

    Raises:
        click.Abort: Forwarded unchanged from a cancelled prompt; the mediator drops the
            contribution with a warning.
    """
    return click.confirm("Run the api.automate pipeline unattended (autonomous mode)?", default=False)


def build_config_data(
    answers: dict[str, object],
    extra_specs: list[dict[str, object]] | None = None,
    autonomous: bool = False,
) -> dict[str, object]:
    """Build the plain serializable tool-config payload from the session answers.

    The payload is plain serializable data only — the engine ``yaml.dump``s it verbatim.

    Args:
        answers: The pybuggy answer view (core sections plus the own block under local names).
        extra_specs: The ``survey_extra_specs`` mappings; None when the gate was declined.
        autonomous: The ``survey_autonomy`` answer; False (also the default) writes no axis.

    Returns:
        The tool-config payload keyed in plugin key order, then ``pipelines`` when
        ``autonomous`` enables it, with ``specs`` last.

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

    if autonomous:
        data["pipelines"] = {"api.automate": {"autonomous": True}}

    data["specs"] = {name: entry.model_dump(exclude_none=True) for name, entry in specs.items()}

    return data


def _pybuggy_version_axis() -> str:
    """Derive the recorded pybuggy version form — the minor x-range of the installed package.

    Mirrors the Dockerfile install pin of ``install_pybuggy`` (the same minor line); a
    metadata-less source-tree run records ``latest`` — the amend-moment contribution is
    soft and must never die on unreadable metadata.
    """
    try:
        version = importlib.metadata.version("goga-tool-pybuggy")
    except importlib.metadata.PackageNotFoundError:
        return "latest"

    return f"{'.'.join(version.split('.')[:2])}.x"


def build_config_amendments(answers: dict[str, object]) -> dict[str, object]:
    """Return the tool's declared-intent answer amendments derived from the block answers.

    Fixed entries — ``build.review.skip`` true (consumer enforcement is the bootstrap's
    ``ensure_review_skip``) and the ``tools`` record pinning pybuggy to the installed minor
    line (merged over any user-collected tools, so pybuggy is always recorded). The
    Dockerfile pair — the fixed path plus the answered base image (the generator writes the
    file from exactly this pair) — and the answered built-image name.

    Args:
        answers: The pybuggy answer view (the block answers under local names).

    Returns:
        The amendment mapping — path → value pairs the platform merges into the answer
        space before generation.
    """
    amendments: dict[str, object] = {"build.review.skip": True}

    base_image = answers.get("base_image")
    if base_image:
        amendments["docker_image.dockerfile"] = _DOCKERFILE_PATH
        amendments["docker_image.base_image"] = base_image

    image = answers.get("image")
    if image:
        amendments["docker_image.image"] = image

    amendments["tools"] = {"pybuggy": _pybuggy_version_axis()}

    return amendments


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

    No-op unless invited; the ``convention`` skip keeps the conventions slot for the pybuggy
    test convention, and the ``docker_image`` skip removes the engine's Dockerfile gate —
    the block asks the base image and the built-image name itself, and the Dockerfile is
    always created through the amendments.

    Args:
        context: The ``ToolDeclaration`` proxy delivered by name from the hooks platform.
    """
    if not context.invited:
        return

    for item in pybuggy_questions():
        context.declare(item)

    context.skip("convention")
    context.skip("docker_image")


def amend_pybuggy_config(context: object) -> None:
    """Amend the session answers and buffer the tool config (participation moment two).

    No-op unless invited; the surveys run in order — the extra specs first, the autonomy
    confirm after them, so the spec survey completes before the autonomy question; any
    exception makes the mediator drop the contribution (the session continues).

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
    autonomous = survey_autonomy()

    for id, value in build_config_amendments(answers).items():
        context.answer(id, value)

    context.write_config("config.yml", build_config_data(answers, extra_specs, autonomous))
