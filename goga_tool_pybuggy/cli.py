"""pybuggy CLI assembly: root group + endpoint subgroup with all commands."""

import click

from .commands.generate import generate_cmd
from .commands.info import info_cmd
from .commands.init import init_cmd
from .commands.list import list_cmd
from .commands.pull import pull_cmd


@click.group()
def main() -> None:
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
