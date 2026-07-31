"""Config loading routine: read YAML file and validate through pydantic."""

import pathlib
from typing import Optional

import yaml

from .config import Config

# Fixed location of the pybuggy config (project-root relative).
# Commands load the config from here by default.
CONFIG_PATH = pathlib.Path(".goga/tools/pybuggy/config.yml")


def load_config(path: Optional[pathlib.Path] = None) -> Config:
    """Load a pybuggy config from a YAML file.

    Reads the file at ``path`` as UTF-8 text, parses it as YAML, and validates
    the result against the :class:`Config` pydantic model.

    Args:
        path: Path to the config YAML file. When None, defaults to the fixed
            pybuggy config location (``CONFIG_PATH`` =
            ``.goga/tools/pybuggy/config.yml``).

    Returns:
        A validated :class:`Config` instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
        pydantic.ValidationError: If the YAML does not match the Config schema.
    """
    if path is None:
        path = CONFIG_PATH

    # Step 1: Read file text as UTF-8
    text = path.read_text(encoding="utf-8")

    # Step 2: Parse YAML using safe_load only
    raw = yaml.safe_load(text)

    # Step 3: Validate through pydantic model
    # Errors (ValidationError, FileNotFoundError) propagate as-is
    return Config.model_validate(raw)
