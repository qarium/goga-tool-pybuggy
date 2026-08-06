"""Environment loading for the pybuggy CLI: .env → os.environ (override=False)."""

from pathlib import Path
from typing import Optional

import click
from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, ConfigDict


class EnvContext(BaseModel):
    """Context object carrying the resolved env-file path and loaded key→value pairs.

    Stored on click ctx.obj by main(); pure data carrier.
    """

    model_config = ConfigDict(kw_only=True)

    env_path: Optional[str] = None
    values: dict[str, str] = {}


def load_env(env_file: Optional[str]) -> EnvContext:
    """Resolve the env-file, load it into os.environ (override=False), and return EnvContext.

    Args:
        env_file: explicit path from --env-file, or None for the implicit .env in CWD.

    Returns:
        EnvContext with the resolved path and loaded key→value pairs.

    Raises:
        click.ClickException: when an explicit --env-file points at a missing file
            or a non-regular file (e.g. a directory).
    """
    if env_file is not None:
        path = Path(env_file)
        if not path.exists():
            raise click.ClickException(f"env file not found: {env_file}")
        if not path.is_file():
            raise click.ClickException(f"env file is not a regular file: {env_file}")
    else:
        path = Path(".env")
        if not path.is_file():
            return EnvContext()

    values = {k: (v if v is not None else "") for k, v in dotenv_values(str(path)).items()}
    load_dotenv(str(path), override=False)

    return EnvContext(env_path=str(path), values=values)
