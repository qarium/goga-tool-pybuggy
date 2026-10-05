"""Config config entity: root pybuggy configuration."""

from pydantic import BaseModel, ConfigDict

from .spec_entry import SpecEntry


class Config(BaseModel):
    """Root pybuggy configuration (``.goga/tools/pybuggy/config.yml``).

    Spec names (dict keys) surface in ``list``/``info`` command output.

    Attributes:
        specs: Mapping of spec name to spec entry; required, empty dict allowed.
    """

    model_config = ConfigDict(kw_only=True)

    specs: dict[str, SpecEntry]
