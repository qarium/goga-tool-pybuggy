"""Strict rendering of the service env values against the mapped instance addresses."""

import logging

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import UndefinedError

from .engines.address import InstanceAddress

logger = logging.getLogger(__name__)


def render_service_env(env: dict[str, str], addresses: dict[str, InstanceAddress]) -> dict[str, str]:
    """Render the service env values with strict placeholder resolution.

    Each value renders through a ``StrictUndefined`` Jinja2 environment against the context
    ``{name: {"host", "port"}}`` built from the mapped instance addresses; a value without
    placeholders renders to itself. Unlike the configure-phase ``render_base_url``, results are
    not whitespace-stripped — env values are not URLs.

    Args:
        env: The raw service env mapping; values may carry ``{{<name>.host}}`` /
            ``{{<name>.port}}`` placeholders.
        addresses: The mapped address of every started instance, keyed by instance name.

    Returns:
        The rendered env mapping with every placeholder resolved.

    Raises:
        ValueError: A value references an unknown placeholder — the message names the env key
            and the offending value. Defense in depth: the load-time validation already rejects
            such documents.
    """
    context = {name: {"host": address.host, "port": address.port} for name, address in addresses.items()}

    environment = Environment(undefined=StrictUndefined)
    rendered: dict[str, str] = {}

    for key, value in env.items():
        try:
            rendered[key] = environment.from_string(value).render(context)
        except UndefinedError as exc:
            raise ValueError("env key '" + key + "': cannot render value '" + value + "': " + str(exc)) from exc

        logger.debug("service env value rendered", extra={"env_key": key})

    return rendered
