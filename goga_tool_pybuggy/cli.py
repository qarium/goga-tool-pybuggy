"""pybuggy CLI assembly: root group + endpoint subgroup with all commands."""

import click

from .commands.generate import generate_cmd
from .commands.info import info_cmd
from .commands.init import init_cmd
from .commands.list import list_cmd
from .commands.pull import pull_cmd
from .env import load_env


def _load_env_callback(ctx: click.Context, _param: click.Parameter, value: str | None) -> str | None:
    """Eager-callback: load .env into os.environ and store EnvContext on ctx.obj.

    Fires before any subcommand is chosen (``is_eager=True``), so the env file is
    applied to ``os.environ`` (``override=False``) before the command runs.

    Args:
        ctx: the click context; its ``obj`` is set to the returned ``EnvContext``.
        _param: the option parameter (unused).
        value: the ``--env-file`` value (explicit path) or ``None`` for the implicit ``.env``.

    Returns:
        The option value unchanged (env loading is the only side effect).
    """
    ctx.obj = load_env(value)
    return value


@click.group()
@click.option(
    "--env-file",
    "env_file",
    default=None,
    callback=_load_env_callback,
    is_eager=True,
    help="Path to a .env file loaded into os.environ (override=False) before the command runs.",
)
def main(env_file: str | None) -> None:
    """pybuggy — CLI tool for work with OpenAPI/Swagger endpoints."""


@click.group("endpoint", help="Manage OpenAPI/Swagger endpoint specs.")
def endpoint_group() -> None:
    """Endpoint management commands."""


endpoint_group.add_command(pull_cmd)
endpoint_group.add_command(list_cmd)
endpoint_group.add_command(info_cmd)
endpoint_group.add_command(generate_cmd)

main.add_command(endpoint_group)
main.add_command(init_cmd)
