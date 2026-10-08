"""load_sandbox_config routine: fail-fast reading and validation of the sandbox document."""

import logging
import re
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .instance import InstanceConfig
from .sandbox_config import SandboxConfig
from .service import ServiceConfig
from .startup_data import StartupData
from .topic import TopicConfig

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

_DOCUMENT_PATH = Path(".goga") / "tools" / "pybuggy" / "sandbox.yml"
_TOP_LEVEL_KEYS = ("instance", "services", "data")
_SUPPORTED_KINDS = ("postgresql", "kafka", "vault", "http")
_REQUIRED_INSTANCE_FIELDS = ("image", "env", "port")
_SECTION_KINDS = {"vault": "vault", "http": "http", "postgres": "postgresql"}

_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_PLACEHOLDER_ATTRIBUTE = re.compile(r"^(?P<name>[^.\s]+)\.(?P<attribute>host|port)$")

# A service name doubles as the Jinja2 identifier of the {{<name>.host}} /
# {{<name>.port}} placeholders — anything else breaks template parsing at render time.
_SERVICE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def load_sandbox_config(path: str | None = None) -> SandboxConfig | None:
    """Read and validate the sandbox document ``.goga/tools/pybuggy/sandbox.yml``.

    Validation completes fully before anything could start — an invalid document fails fast with
    an error naming the document location and the offending entry.

    Args:
        path: Explicit document location; ``None`` resolves
            ``.goga/tools/pybuggy/sandbox.yml`` in the current working directory — resolution
            never searches upward.

    Returns:
        The validated configuration model; ``None`` when the document is absent — the sandbox
        stays fully inert.

    Raises:
        ValueError: The document is present but invalid; the message names the document location
            and the offending entry.
    """
    location = Path(path) if path is not None else Path.cwd() / _DOCUMENT_PATH

    if not location.is_file():
        return None

    document = _parse_document(location)
    _validate_top_level_keys(document, location)
    instance = _read_instance(document, location)
    services = _read_services(document, location)
    data = _read_data(document, location, services)
    _validate_placeholders(instance, services, location)

    logger.info("sandbox document loaded", extra={"document": str(location)})

    return _build_model(SandboxConfig, {"instance": instance, "services": services, "data": data}, str(location))


def _parse_document(location: Path) -> dict[str, object]:
    """Parse the document at ``location`` into a mapping.

    Args:
        location: The resolved document location.

    Returns:
        The parsed document mapping.

    Raises:
        ValueError: The document is unparsable, empty, or not a mapping.
    """
    try:
        document = YAML().load(location)
    except YAMLError as exc:
        raise ValueError(f"{location}: unparsable document: {exc}") from exc

    if document is None:
        raise ValueError(f"{location}: the document is empty — a sandbox document must carry the instance entry")

    if not isinstance(document, dict):
        raise ValueError(f"{location}: the document must be a mapping")

    return document


def _validate_top_level_keys(document: dict[str, object], location: Path) -> None:
    """Apply the top-level key diagnostics to the parsed document.

    Args:
        document: The parsed document mapping.
        location: The resolved document location.

    Raises:
        ValueError: A former key name or an unknown key sits at the document top level.
    """
    if "service" in document:
        raise ValueError(f"{location}: top-level key 'service' was renamed to 'instance'")

    if "instances" in document:
        raise ValueError(f"{location}: top-level key 'instances' was renamed to 'services'")

    for key in document:
        if key not in _TOP_LEVEL_KEYS:
            raise ValueError(
                f"{location}: unknown top-level key '{key}' (supported keys: {', '.join(_TOP_LEVEL_KEYS)})"
            )


def _read_instance(document: dict[str, object], location: Path) -> InstanceConfig:
    """Validate and build the instance-under-test entry.

    Args:
        document: The parsed document mapping.
        location: The resolved document location.

    Returns:
        The validated instance-under-test entry.

    Raises:
        ValueError: A required instance field is missing or mistyped.
    """
    entry = _mapping_entry(document, "instance", location)

    for field in _REQUIRED_INSTANCE_FIELDS:
        if field not in entry:
            raise ValueError(f"{location}: instance.{field}: required entry missing")

    return _build_model(InstanceConfig, dict(entry), f"{location}: instance")


def _read_services(document: dict[str, object], location: Path) -> dict[str, ServiceConfig]:
    """Validate and build the dependency service entries keyed by service name.

    Args:
        document: The parsed document mapping.
        location: The resolved document location.

    Returns:
        The validated service entries keyed by service name.

    Raises:
        ValueError: A service name, kind, topics, or probe entry is invalid.
    """
    raw = document.get("services", {})

    if not isinstance(raw, dict):
        raise ValueError(f"{location}: services: must be a mapping of service name to entry")

    services: dict[str, ServiceConfig] = {}

    for name, entry in raw.items():
        scope = f"{location}: services.{name}"

        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{scope}: the service name must be a non-empty string")

        if not _SERVICE_NAME.fullmatch(name):
            raise ValueError(
                f"{scope}: the service name must be a template identifier "
                f"(letters, digits, underscores; not starting with a digit) — it names the "
                f"{{{{<name>.host}}}} / {{{{<name>.port}}}} placeholders"
            )

        if not isinstance(entry, dict):
            raise ValueError(f"{scope}: the entry must be a mapping")

        _validate_kind(entry, scope)
        _validate_topics(entry, scope)
        services[name] = _build_model(ServiceConfig, dict(entry, name=name), scope)

    return services


def _validate_topics(entry: dict[str, object], scope: str) -> None:
    """Validate the inline topic declarations of one service entry.

    Args:
        entry: The raw service entry mapping.
        scope: The error scope naming the document location and the entry.

    Raises:
        ValueError: The topics declaration is absent on a kafka entry, present on a non-kafka
            entry, malformed, or carries a duplicate topic name.
    """
    if entry.get("kind") != "kafka":
        if "topics" in entry:
            raise ValueError(f"{scope}: topics are accepted only on kafka entries")

        return

    topics = entry.get("topics")

    if not isinstance(topics, list) or not topics:
        raise ValueError(
            f"{scope}: a kafka entry requires a non-empty 'topics' list — "
            f"without topics the mock opens no kafka listener"
        )

    declared: set[str] = set()

    for declaration in topics:
        if not isinstance(declaration, dict):
            raise ValueError(f"{scope}.topics: every topic declaration must be a mapping")

        topic = _build_model(TopicConfig, dict(declaration), f"{scope}.topics")

        if topic.name in declared:
            raise ValueError(
                f"{scope}.topics: duplicate topic '{topic.name}' — "
                f"each topic name must be unique within the service entry"
            )

        declared.add(topic.name)


def _read_data(document: dict[str, object], location: Path, services: dict[str, ServiceConfig]) -> StartupData:
    """Validate the startup data sections and build the startup data layer.

    Args:
        document: The parsed document mapping.
        location: The resolved document location.
        services: The validated service entries.

    Returns:
        The validated startup data layer.

    Raises:
        ValueError: A data section or one of its targets is invalid.
    """
    raw = document.get("data", {})

    if not isinstance(raw, dict):
        raise ValueError(f"{location}: data: must be a mapping of data section to declarations")

    for section in raw:
        if section == "kafka":
            raise ValueError(f"{location}: data.kafka was removed — declare topics inline on the kafka service entry")

        if section not in _SECTION_KINDS:
            raise ValueError(
                f"{location}: data.{section}: unknown data section (supported sections: {', '.join(_SECTION_KINDS)})"
            )

    sections: dict[str, dict[str, object]] = {}

    for section, kind in _SECTION_KINDS.items():
        sections[section] = _read_section(section, kind, raw[section], services, location) if section in raw else {}

    return _build_model(StartupData, sections, f"{location}: data")


def _read_section(
    section: str,
    kind: str,
    targets: object,
    services: dict[str, ServiceConfig],
    location: Path,
) -> dict[str, object]:
    """Validate one data section.

    Args:
        section: The data section name.
        kind: The service kind the section targets.
        targets: The raw section value — service name to declarations.
        services: The validated service entries.
        location: The resolved document location.

    Returns:
        The section declarations keyed by service name.

    Raises:
        ValueError: A section target is not a configured service of the matching kind.
    """
    if not isinstance(targets, dict):
        raise ValueError(f"{location}: data.{section}: must be a mapping of service name to declarations")

    declarations: dict[str, object] = {}

    for target, value in targets.items():
        name = str(target)
        service = services.get(name)

        if service is None:
            configured = ", ".join(sorted(services)) or "none"
            raise ValueError(
                f"{location}: data.{section}.{name}: targets service '{name}' "
                f"which is not configured (configured services: {configured})"
            )

        if service.kind != kind:
            raise ValueError(
                f"{location}: data.{section}.{name}: targets service '{name}' of kind "
                f"'{service.kind}', the section requires kind '{kind}'"
            )

        if section == "vault":
            _validate_vault_declarations(name, value, location)

        declarations[name] = value

    return declarations


def _validate_vault_declarations(target: str, declarations: object, location: Path) -> None:
    """Validate the shape of one vault section's secret declarations.

    Every declaration must be a mapping carrying a non-empty string ``path`` and a mapping
    ``data`` — the keys the startup assembly reads; a malformed declaration fails here,
    at load time, instead of crashing the sandbox start with a bare lookup error.

    Args:
        target: The vault service name the declarations target.
        declarations: The raw section value — the target's declaration list.
        location: The resolved document location.

    Raises:
        ValueError: A secret declaration is missing its ``path`` or ``data`` entry.
    """
    if not isinstance(declarations, list):
        return  # a non-list section value fails the model build with the scope-named error

    for declaration in declarations:
        if not isinstance(declaration, dict):
            continue  # a non-mapping declaration fails the model build the same way

        path = declaration.get("path")

        if not isinstance(path, str) or not path.strip():
            raise ValueError(
                f"{location}: data.vault.{target}: every secret declaration requires a non-empty string 'path'"
            )

        if not isinstance(declaration.get("data"), dict):
            raise ValueError(f"{location}: data.vault.{target}: every secret declaration requires a mapping 'data'")


def _validate_placeholders(instance: InstanceConfig, services: dict[str, ServiceConfig], location: Path) -> None:
    """Validate every service placeholder in the instance env values against the full grammar.

    Every ``{{ … }}`` occurrence must be ``{{ <name>.host }}`` or ``{{ <name>.port }}`` with
    ``<name>`` a configured service.

    Args:
        instance: The validated instance-under-test entry.
        services: The validated service entries.
        location: The resolved document location.

    Raises:
        ValueError: A placeholder is malformed or names an unconfigured service.
    """
    configured = set(services)

    for key, value in instance.env.items():
        if "{{" in _PLACEHOLDER.sub("", value):
            raise ValueError(
                f"{location}: instance.env.{key}: invalid placeholder — an unterminated '{{{{' in value '{value}'"
            )

        for token in _PLACEHOLDER.findall(value):
            placeholder = "{{" + token + "}}"
            match = _PLACEHOLDER_ATTRIBUTE.match(token)

            if match is None:
                raise ValueError(_placeholder_error(key, placeholder, token, location))

            name = match.group("name")

            if name not in configured:
                known = ", ".join(sorted(configured)) or "none"
                raise ValueError(
                    f"{location}: instance.env.{key}: invalid placeholder '{placeholder}' "
                    f"— service '{name}' is not configured (configured services: {known})"
                )


def _placeholder_error(key: str, placeholder: str, token: str, location: Path) -> str:
    """Build the error message for one malformed placeholder token.

    Args:
        key: The instance env key carrying the placeholder.
        placeholder: The rendered ``{{ … }}`` occurrence.
        token: The placeholder inner text.
        location: The resolved document location.

    Returns:
        The error message naming the env key and the malformed part.
    """
    if "." in token:
        attribute = token.split(".", 1)[1]

        return (
            f"{location}: instance.env.{key}: invalid placeholder '{placeholder}' "
            f"— unknown attribute '{attribute}', expected '.host' or '.port'"
        )

    return (
        f"{location}: instance.env.{key}: invalid placeholder '{placeholder}' "
        f"— the service name is missing its '.host' or '.port' attribute"
    )


def _validate_kind(entry: dict[str, object], scope: str) -> None:
    """Validate the kind of one service entry.

    Args:
        entry: The raw service entry mapping.
        scope: The error scope naming the document location and the entry.

    Raises:
        ValueError: The kind is missing, not supported yet, or unknown.
    """
    kind = entry.get("kind")

    if not isinstance(kind, str) or not kind:
        raise ValueError(f"{scope}.kind: required entry missing")

    if kind == "grpc":
        raise ValueError(f"{scope}: kind 'grpc' is not supported yet")

    if kind not in _SUPPORTED_KINDS:
        raise ValueError(f"{scope}: kind '{kind}' is not one of the supported kinds ({', '.join(_SUPPORTED_KINDS)})")


def _mapping_entry(parent: dict[str, object], key: str, location: Path) -> dict[str, object]:
    """Return ``parent[key]`` as a mapping.

    Args:
        parent: The parsed mapping holding the entry.
        key: The entry key.
        location: The resolved document location.

    Returns:
        The entry mapping.

    Raises:
        ValueError: The entry is absent or not a mapping.
    """
    entry = parent.get(key)

    if not isinstance(entry, dict):
        raise ValueError(f"{location}: {key}: required mapping entry missing")

    return entry


def _build_model(model: type[ModelT], payload: dict[str, object], scope: str) -> ModelT:
    """Construct the pydantic ``model`` from ``payload``, wrapping type errors with the scope.

    Args:
        model: The pydantic model class to construct.
        payload: The keyword payload for the model constructor.
        scope: The error scope naming the document location and the entry.

    Returns:
        The constructed model.

    Raises:
        ValueError: The payload violates the model field types.
    """
    try:
        return model(**payload)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'entry'}: {error['msg']}" for error in exc.errors()
        )
        raise ValueError(f"{scope}: {details}") from exc
