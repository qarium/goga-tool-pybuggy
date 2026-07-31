"""Config config entity: root pybuggy configuration."""

from pydantic import BaseModel, ConfigDict

from .spec_entry import SpecEntry


class Config(BaseModel):
    """Root pybuggy configuration (``.goga/tools/pybuggy/config.yml``).

    Holds a mapping of spec names to ``SpecEntry`` configurations. The spec name
    (dictionary key) is surfaced in ``list``/``info`` command output.

    Attributes:
        specs: Mapping of spec name to spec entry configuration. Required — a
            config without specs is considered invalid. An empty dict is
            allowed (no specs configured).
    """

    model_config = ConfigDict(kw_only=True)

    specs: dict[str, SpecEntry]
