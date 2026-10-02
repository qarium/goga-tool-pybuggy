"""Config reading routines: the platform-facade read and the autonomy resolver."""

from pydantic import ValidationError

from .config import Config
from .pipeline_autonomy import PipelineAutonomy

# Tool-config read arguments for the platform facade: the fixed standard
# location ``.goga/tools/pybuggy/config.yml``.
_TOOL = "pybuggy"
_FILENAME = "config.yml"


def load_config() -> Config:
    """Load the pybuggy tool config and validate it into a ``Config`` model.

    Obtains the raw parse of ``.goga/tools/pybuggy/config.yml`` through the
    platform tool-config facade and validates the result into :class:`Config`.
    Extra keys — including the ``pipelines`` axis — are ignored by the model.

    Returns:
        A validated :class:`Config` instance.

    Raises:
        FileNotFoundError: If the tool config file is absent or empty (the
            facade returns ``None`` for both).
        yaml.YAMLError: If the file contains invalid YAML (propagated raw).
        pydantic.ValidationError: If the parse does not match the ``Config``
            schema (propagated raw).
    """
    # Call-time import — contract: keeps goga out of the runtime dependencies.
    from goga.config import load_tool_config  # noqa: PLC0415

    raw = load_tool_config(_TOOL, _FILENAME)

    if raw is None:
        raise FileNotFoundError("tool config not found: .goga/tools/pybuggy/config.yml")

    return Config.model_validate(raw)


def resolve_autonomy(pipeline: str) -> bool:
    """Resolve whether autonomy is enabled for the running pipeline.

    Validates the whole ``pipelines`` axis of the tool config on every call:
    each entry must be a mapping validatable into :class:`PipelineAutonomy`.
    Absent file, absent ``pipelines`` section, absent name, and
    ``autonomous: false`` all mean disabled.

    Args:
        pipeline: The identity of the running pipeline.

    Returns:
        True only when the axis carries an enabling entry for ``pipeline``.

    Raises:
        ValueError: On a structural violation — a non-mapping config root, a
            non-mapping ``pipelines`` value, or an entry not validatable into
            :class:`PipelineAutonomy` (the pydantic detail is chained).
        yaml.YAMLError: If the file contains invalid YAML (propagated raw).
    """
    # Call-time import — contract: keeps goga out of the runtime dependencies.
    from goga.config import load_tool_config  # noqa: PLC0415

    raw = load_tool_config(_TOOL, _FILENAME)

    if raw is None:
        return False

    if not isinstance(raw, dict):
        raise ValueError("pybuggy tool config: the file must parse to a mapping")

    axis = raw.get("pipelines")

    if axis is None:
        return False

    if not isinstance(axis, dict):
        raise ValueError("pybuggy tool config: pipelines must be a mapping")

    records: dict[str, PipelineAutonomy] = {}
    for name, entry in axis.items():
        try:
            records[name] = PipelineAutonomy.model_validate(entry)
        except ValidationError as err:
            raise ValueError(f"pybuggy tool config: invalid pipelines entry {name!r}") from err

    if pipeline not in records:
        return False

    return bool(records[pipeline].autonomous)
