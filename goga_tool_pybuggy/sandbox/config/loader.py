"""load_sandbox_config routine: fail-fast reading and validation of ``.sandbox.yml``."""

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

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

_DOCUMENT_NAME = ".sandbox.yml"
_SUPPORTED_KINDS = ("postgresql", "kafka", "vault", "http")
_REQUIRED_SERVICE_FIELDS = ("image", "env", "port")
_SECTION_KINDS = {"vault": "vault", "http": "http", "kafka": "kafka", "postgres": "postgresql"}

_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_PLACEHOLDER_ATTRIBUTE = re.compile(r"^(?P<name>[^.\s]+)\.(?P<attribute>host|port)$")


def load_sandbox_config(path: str | None = None) -> SandboxConfig | None:
    """Read and validate the sandbox configuration document ``.sandbox.yml``.

    Validation completes fully before anything could start — an invalid document fails fast with
    an error naming the document location and the offending entry.

    Args:
        path: Explicit document location; ``None`` resolves ``.sandbox.yml`` in the current
            working directory.

    Returns:
        The validated configuration model; ``None`` when the document is absent — the sandbox
        stays fully inert.

    Raises:
        ValueError: The document is present but invalid; the message names the document location
            and the offending entry.
    """
    location = Path(path) if path is not None else Path.cwd() / _DOCUMENT_NAME

    if not location.is_file():
        return None

    document = _parse_document(location)
    service = _read_service(document, location)
    instances = _read_instances(document, location)
    data = _read_data(document, location, instances)
    _validate_placeholders(service, instances, location)

    logger.info("sandbox document loaded", extra={"document": str(location)})

    return _build_model(SandboxConfig, {"service": service, "instances": instances, "data": data}, str(location))


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
        raise ValueError(f"{location}: the document is empty — a sandbox document must carry the service entry")

    if not isinstance(document, dict):
        raise ValueError(f"{location}: the document must be a mapping")

    return document


def _read_service(document: dict[str, object], location: Path) -> ServiceConfig:
    """Validate and build the service entry.

    Args:
        document: The parsed document mapping.
        location: The resolved document location.

    Returns:
        The validated service entry.

    Raises:
        ValueError: A required service field is missing or mistyped.
    """
    entry = _mapping_entry(document, "service", location)

    for field in _REQUIRED_SERVICE_FIELDS:
        if field not in entry:
            raise ValueError(f"{location}: service.{field}: required entry missing")

    return _build_model(ServiceConfig, dict(entry), f"{location}: service")


def _read_instances(document: dict[str, object], location: Path) -> dict[str, InstanceConfig]:
    """Validate and build the dependency instance entries keyed by instance name.

    Args:
        document: The parsed document mapping.
        location: The resolved document location.

    Returns:
        The validated instance entries keyed by instance name.

    Raises:
        ValueError: An instance name, kind, or image entry is invalid.
    """
    raw = document.get("instances", {})

    if not isinstance(raw, dict):
        raise ValueError(f"{location}: instances: must be a mapping of instance name to entry")

    instances: dict[str, InstanceConfig] = {}

    for name, entry in raw.items():
        scope = f"{location}: instances.{name}"

        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{scope}: the instance name must be a non-empty string")

        if not isinstance(entry, dict):
            raise ValueError(f"{scope}: the entry must be a mapping")

        _validate_kind(entry, scope)
        instances[name] = _build_model(InstanceConfig, dict(entry, name=name), scope)

    return instances


def _read_data(document: dict[str, object], location: Path, instances: dict[str, InstanceConfig]) -> StartupData:
    """Validate the startup data sections and build the startup data layer.

    Kafka spec paths are resolved against the document directory — relative paths become
    absolute, absolute paths stay as-is (string resolution only; the file is not read).

    Args:
        document: The parsed document mapping.
        location: The resolved document location.
        instances: The validated instance entries.

    Returns:
        The validated startup data layer.

    Raises:
        ValueError: A data section or one of its targets is invalid.
    """
    raw = document.get("data", {})

    if not isinstance(raw, dict):
        raise ValueError(f"{location}: data: must be a mapping of data section to declarations")

    for section in raw:
        if section not in _SECTION_KINDS:
            raise ValueError(
                f"{location}: data.{section}: unknown data section (supported sections: {', '.join(_SECTION_KINDS)})"
            )

    sections: dict[str, dict[str, object]] = {}

    for section, kind in _SECTION_KINDS.items():
        sections[section] = _read_section(section, kind, raw[section], instances, location) if section in raw else {}

    return _build_model(StartupData, sections, f"{location}: data")


def _read_section(
    section: str,
    kind: str,
    targets: object,
    instances: dict[str, InstanceConfig],
    location: Path,
) -> dict[str, object]:
    """Validate one data section and resolve its kafka spec paths.

    Args:
        section: The data section name.
        kind: The instance kind the section targets.
        targets: The raw section value — instance name to declarations.
        instances: The validated instance entries.
        location: The resolved document location.

    Returns:
        The section declarations keyed by instance name.

    Raises:
        ValueError: A section target is not a configured instance of the matching kind.
    """
    if not isinstance(targets, dict):
        raise ValueError(f"{location}: data.{section}: must be a mapping of instance name to declarations")

    declarations: dict[str, object] = {}

    for target, value in targets.items():
        name = str(target)
        instance = instances.get(name)

        if instance is None:
            configured = ", ".join(sorted(instances)) or "none"
            raise ValueError(
                f"{location}: data.{section}.{name}: targets instance '{name}' "
                f"which is not configured (configured instances: {configured})"
            )

        if instance.kind != kind:
            raise ValueError(
                f"{location}: data.{section}.{name}: targets instance '{name}' of kind "
                f"'{instance.kind}', the section requires kind '{kind}'"
            )

        declarations[name] = _resolve_spec_path(value, location, name) if section == "kafka" else value

    return declarations


def _resolve_spec_path(spec: object, location: Path, target: str) -> str:
    """Resolve one kafka spec path against the document directory.

    Args:
        spec: The raw spec declaration — a file path.
        location: The resolved document location.
        target: The kafka instance name the declaration targets.

    Returns:
        The resolved spec path; relative paths joined onto the document directory.

    Raises:
        ValueError: The spec declaration is not a non-empty string.
    """
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError(f"{location}: data.kafka.{target}: the spec path must be a non-empty string")

    path = Path(str(spec))

    return str(path if path.is_absolute() else location.parent / path)


def _validate_placeholders(service: ServiceConfig, instances: dict[str, InstanceConfig], location: Path) -> None:
    """Validate every instance placeholder in the service env values against the full grammar.

    Every ``{{ … }}`` occurrence must be ``{{ <name>.host }}`` or ``{{ <name>.port }}`` with
    ``<name>`` a configured instance.

    Args:
        service: The validated service entry.
        instances: The validated instance entries.
        location: The resolved document location.

    Raises:
        ValueError: A placeholder is malformed or names an unconfigured instance.
    """
    configured = set(instances)

    for key, value in service.env.items():
        for token in _PLACEHOLDER.findall(value):
            placeholder = "{{" + token + "}}"
            match = _PLACEHOLDER_ATTRIBUTE.match(token)

            if match is None:
                raise ValueError(_placeholder_error(key, placeholder, token, location))

            name = match.group("name")

            if name not in configured:
                known = ", ".join(sorted(configured)) or "none"
                raise ValueError(
                    f"{location}: service.env.{key}: invalid placeholder '{placeholder}' "
                    f"— instance '{name}' is not configured (configured instances: {known})"
                )


def _placeholder_error(key: str, placeholder: str, token: str, location: Path) -> str:
    """Build the error message for one malformed placeholder token.

    Args:
        key: The service env key carrying the placeholder.
        placeholder: The rendered ``{{ … }}`` occurrence.
        token: The placeholder inner text.
        location: The resolved document location.

    Returns:
        The error message naming the env key and the malformed part.
    """
    if "." in token:
        attribute = token.split(".", 1)[1]

        return (
            f"{location}: service.env.{key}: invalid placeholder '{placeholder}' "
            f"— unknown attribute '{attribute}', expected '.host' or '.port'"
        )

    return (
        f"{location}: service.env.{key}: invalid placeholder '{placeholder}' "
        f"— the instance name is missing its '.host' or '.port' attribute"
    )


def _validate_kind(entry: dict[str, object], scope: str) -> None:
    """Validate the kind of one instance entry.

    Args:
        entry: The raw instance entry mapping.
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
