"""Onboarding-session participation — question block, answer payloads, and the session seam.

``run_session`` drives the engine-owned session; the declare/amend hooks and the pure builders feed it.
"""

import importlib.metadata
import logging

import click
from goga.config import resolve_project_name
from goga.onboarding import FileGenerator, InitLogic, Question, Questionnaire, ToolParticipation
from goga.version import host_goga_version, minor_version

from ...config import GitEntry, SpecEntry
from ...plugins import PluginConfigKeys, WebConfigKeys

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

# The browser names the web runtime accepts — a mirror of the prettyplay browser matrix, the
# runtime's own authority (an out-of-matrix name fails at test startup with its "must be one of"
# rejection). The survey offers exactly these as the choice set, so an invalid name never reaches
# ``web.yml``.
_BROWSER_NAMES: tuple[str, ...] = ("chromium", "firefox", "webkit", "chrome", "msedge")

# The autonomous pipelines of the amend-moment survey — one confirm per axis, asked and
# written in the given order: the api pair in the api branch (automate first, patch after
# it), the web axis in the web branch (into the web tool config).
_AUTONOMY_AXES: tuple[str, ...] = ("api.automate", "api.patch")

_WEB_AUTONOMY_AXES: tuple[str, ...] = ("web.automate",)

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

    Exact ids and order — the answer keys consumed downstream: the kind answer gates every
    amend-moment branch; the image inputs feed the Dockerfile amendments. The api and web
    option sets are surveyed at the amendment moment (:func:`survey_api_options`,
    :func:`survey_specs`, :func:`survey_autonomy`, :func:`survey_web_config`) — the
    declarative engine records carry no conditional visibility.

    Returns:
        The question records — the kind choice, then the two image inputs (exactly three;
        no scalar keys, no spec group, no web records).
    """
    tag = minor_version(host_goga_version())
    hints = [f"{name}:{tag}" for name in _BASE_IMAGE_NAMES]
    base_image_prompt = "\n".join(["Base image (FROM)", "Available images:", *[f"  - {hint}" for hint in hints]])
    project_name = resolve_project_name()

    return [
        Question(
            id="kind",
            kind="choice",
            prompt="Test kind (api — API tests over specs, web — browser UI tests, both)",
            choices=["api", "web", "both"],
            default="api",
        ),
        Question(id="base_image", kind="input", prompt=base_image_prompt, default=hints[-1]),
        Question(
            id="image",
            kind="input",
            prompt="Built image name",
            default=f"{project_name}:latest" if project_name is not None else None,
        ),
    ]


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


def survey_api_options() -> dict[str, object]:
    """Interactively survey the api plugin options — the api branch of the amendment moment.

    The base URL is required (an empty entry re-asks); every scalar member is an
    Enter-to-skip optional, so unanswered keys drop from the returned mapping. The prompt
    texts are preserved from the former declarative block so both flows read as one.

    Returns:
        The answered api scalar keys — ``base_url`` plus every scalar member carrying an answer.

    Raises:
        click.Abort: Forwarded unchanged from a cancelled prompt; the mediator drops the
            contribution with a warning.
    """
    answers: dict[str, object] = {"base_url": _required("Base URL (Jinja2 template, required)")}

    for member in PluginConfigKeys:
        if member in (PluginConfigKeys.BASE_URL, PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER):
            continue

        value = click.prompt(_SCALAR_PROMPTS[member], default="", show_default=False)

        if value:
            answers[member.value] = value

    return answers


def _survey_one_spec() -> dict[str, object]:
    """Ask one spec's fields in the fixed order — the shared body of the first and additional specs.

    Returns:
        The surveyed spec mapping keyed by the field names
        (``name``/``type``/``location``/``git_url``/``git_location``/``git_ref``).
    """
    return {
        "name": _required("Spec name"),
        "type": click.prompt("Spec type", type=click.Choice(list(_SPEC_TYPES))),
        "location": _required("Spec location (path from project root)"),
        "git_url": click.prompt("Git URL (empty — no git source)", default="", show_default=False).strip(),
        "git_location": click.prompt("Path inside the repository", default="", show_default=False).strip(),
        "git_ref": click.prompt("Git ref (branch/tag; empty — default branch)", default="", show_default=False).strip(),
    }


def survey_specs() -> list[dict[str, object]]:
    """Interactively survey the specs — the first spec and the confirm-gated additional specs.

    The first spec is asked field by field, then the repeating confirm accepts any number of
    extras in the same field order; empty git fields mean no source / default branch.

    Returns:
        The surveyed specs — one mapping per accepted spec, the first spec first, keyed by
        the spec field names (``name``/``type``/``location``/``git_url``/``git_location``/``git_ref``).

    Raises:
        click.Abort: Forwarded unchanged from a cancelled prompt; the mediator drops the
            contribution with a warning.
    """
    surveyed: list[dict[str, object]] = [_survey_one_spec()]

    while click.confirm("Add another spec?", default=False):
        surveyed.append(_survey_one_spec())

    return surveyed


def survey_autonomy(axes: tuple[str, ...]) -> dict[str, bool]:
    """Interactively survey the autonomy confirms of the given axes — the amend-moment follow-ups.

    Asked by the tool once the branch's own survey completed, so the questions never interleave
    its fields: the api branch asks after the specs (its two axes, automate first, patch after
    it), the web branch after the web minimum (its single axis). One confirm per axis, in the
    given order; the disabled defaults keep each pipeline interactive until opted in.

    Args:
        axes: The pipeline axes to confirm, in ask order — ``_AUTONOMY_AXES`` (api branch)
            or ``_WEB_AUTONOMY_AXES`` (web branch).

    Returns:
        The autonomy answers keyed by pipeline axis — True enables that pipeline's unattended
        window.

    Raises:
        click.Abort: Forwarded unchanged from a cancelled prompt; the mediator drops the
            contribution with a warning.
    """
    return {
        axis: click.confirm(f"Run the {axis} pipeline unattended (autonomous mode)?", default=False)
        for axis in axes
    }


def survey_web_config() -> dict[str, object]:
    """Interactively survey the web minimum — the web branch of the amendment moment.

    The minimum only — the remaining ``WebConfigKeys`` arrive as commented examples in the
    written ``web.yml`` (the bootstrap's example documentation). The LLM prompts state their
    purpose — browser steps are written and classified by the provider's models — so a web-only
    user can answer them; the models stay required. The browser name is a choice of the
    runtime-accepted ``_BROWSER_NAMES``, so an invalid name never reaches ``web.yml``.

    Returns:
        The five surveyed keys — ``provider``, ``generation_model``, ``classification_model``,
        ``browser_name``, and ``headless`` — the exact shape :func:`build_web_config_data` maps.

    Raises:
        click.Abort: Forwarded unchanged from a cancelled prompt; the mediator drops the
            contribution with a warning.
    """
    return {
        "provider": click.prompt(
            "LLM provider (writes and classifies the browser-test steps)",
            type=click.Choice(["openai", "anthropic"]),
            default="openai",
        ),
        "generation_model": _required("Generation model (the LLM writing the browser-step code, required)"),
        "classification_model": _required("Classification model (the LLM classifying captured steps, required)"),
        "browser_name": click.prompt("Browser name", type=click.Choice(list(_BROWSER_NAMES)), default="chromium"),
        "headless": click.confirm("Run the browser headless?", default=True),
    }


def build_config_data(
    answers: dict[str, object],
    specs: list[dict[str, object]],
    autonomous: dict[str, bool] | None = None,
) -> dict[str, object]:
    """Build the plain serializable tool-config payload from the session answers.

    The payload is plain serializable data only — the engine ``yaml.dump``s it verbatim.

    Args:
        answers: The pybuggy answer view — the ``survey_api_options`` answers plus the block
            answers under local names.
        specs: The ``survey_specs`` output — the surveyed spec mappings, the first spec first.
        autonomous: The ``survey_autonomy`` answers keyed by axis; absent, None, or an
            all-disabled mapping writes no axis entries.

    Returns:
        The tool-config payload keyed in plugin key order, then ``pipelines`` holding one
        entry per enabled axis, with ``specs`` last.

    Raises:
        ValueError: If a numeric member's answer cannot coerce to its target type, or the
            first surveyed spec is invalid (the mediator soft-drops the contribution).
    """
    typed_specs = parse_specs(specs[0], specs[1:] or None)
    data: dict[str, object] = {}

    for member in PluginConfigKeys:
        if member in (PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER):
            continue

        value = answers.get(member.value)
        if value is None or value == "":
            continue

        data[member.value] = _NUMERIC_MEMBERS[member](value) if member in _NUMERIC_MEMBERS else value

    enabled_axes = [axis for axis in _AUTONOMY_AXES if autonomous and autonomous.get(axis)]

    if enabled_axes:
        data["pipelines"] = {axis: {"autonomous": True} for axis in enabled_axes}

    data["specs"] = {name: entry.model_dump(exclude_none=True) for name, entry in typed_specs.items()}

    return data


def build_web_config_data(
    web_answers: dict[str, object],
    autonomous: bool | None = None,
) -> dict[str, object]:
    """Build the plain serializable web-config payload from the surveyed web answers.

    The keys are spelled via ``WebConfigKeys`` members — data-driven, no duplicated literals;
    the payload order is the insertion order the example documentation walks.

    Args:
        web_answers: The ``survey_web_config`` answers.
        autonomous: The web-branch autonomy answer of the ``web.automate`` axis; absent, None,
            or False writes no ``pipelines`` entry.

    Returns:
        The payload carrying the surveyed minimum (the provider, the two models, the browser
        group), the explicit ``strict`` and ``interactive`` defaults, and — when enabled — the
        ``pipelines`` entry of the ``web.automate`` axis, last.
    """
    data: dict[str, object] = {
        WebConfigKeys.PROVIDER.value: web_answers["provider"],
        WebConfigKeys.GENERATION_MODEL.value: web_answers["generation_model"],
        WebConfigKeys.CLASSIFICATION_MODEL.value: web_answers["classification_model"],
        WebConfigKeys.BROWSER.value: {
            "name": web_answers["browser_name"],
            "headless": web_answers["headless"],
        },
        WebConfigKeys.STRICT.value: False,
        WebConfigKeys.INTERACTIVE.value: False,
    }

    if autonomous:
        data["pipelines"] = {"web.automate": {"autonomous": True}}

    return data


def _pybuggy_version_axis() -> str:
    """Derive the recorded pybuggy version form — the installed package's major.minor x-range.

    The recorded x-range (e.g. ``2.0.x`` — a floating patch pin, never the concrete line, which the
    installer would pin to ``==N.M`` forever; the engine's YAML serialization keeps the value a quoted
    string, never a float) is the version source the image-build bulk ``goga install`` reads from the
    copied project — the Dockerfile install block carries no version of its own. A metadata-less
    source-tree run records ``latest`` — the amend-moment contribution is soft and must never die on
    unreadable metadata.
    """
    try:
        version = importlib.metadata.version("goga-tool-pybuggy")
    except importlib.metadata.PackageNotFoundError:
        return "latest"

    return ".".join(version.split(".")[:2]) + ".x"


def build_config_amendments(answers: dict[str, object]) -> dict[str, object]:
    """Return the tool's declared-intent answer amendments derived from the block answers.

    Fixed entries — ``build.review.skip`` true (consumer enforcement is the bootstrap's
    ``ensure_review_skip``) and the ``tools`` record pinning pybuggy to the installed
    major.minor x-range — a quoted string value, e.g. ``"2.0.x"`` (merged over any user-collected
    tools, so pybuggy is always recorded). The
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
    """Amend the session answers and buffer the tool configs (participation moment two).

    No-op unless invited; the kind answer gates the branches — the api branch surveys the
    api options, the specs, and the api autonomy confirms (in that order), the web branch
    surveys the web minimum and the web autonomy confirm after it; the amendments buffer
    unconditionally (the image inputs are kind-neutral); any exception makes the mediator
    drop the contribution (the session continues).

    Args:
        context: The ``ToolContribution`` proxy delivered by name from the hooks platform.

    Raises:
        ValueError: If a numeric answer cannot coerce — propagated so the mediator
            soft-drops the contribution.
        click.Abort: Forwarded unchanged from a cancelled survey prompt — the same soft drop.
    """
    if not context.invited:
        return

    answers = context.answers
    kind = str(answers.get("kind") or "api")

    if kind in ("api", "both"):
        api_answers = survey_api_options()
        specs = survey_specs()
        autonomous = survey_autonomy(_AUTONOMY_AXES)

    if kind in ("web", "both"):
        web_answers = survey_web_config()
        web_autonomous = survey_autonomy(_WEB_AUTONOMY_AXES)

    for id, value in build_config_amendments(answers).items():
        context.answer(id, value)

    if kind in ("api", "both"):
        context.write_config("api.yml", build_config_data({**answers, **api_answers}, specs, autonomous))

    if kind in ("web", "both"):
        context.write_config("web.yml", build_web_config_data(web_answers, web_autonomous.get("web.automate")))
