import re
import typing as t

import jinja2

# A typed CLI option token (``--key``, ``-k``, ``--key=value``); captures the option name.
_PLACEHOLDER_SOURCE_PATTERN = re.compile(r"^--?([A-Za-z_][\w-]*)(?:=(.*))?$")


def _match_re(value: t.Any, pattern: str) -> bool:
    return re.match(pattern, str(value)) is not None


def passed_cli_options(config: t.Any) -> dict[str, t.Any]:
    """Collect the CLI options the user actually typed, keyed by normalized name.

    Raw ``invocation_params.args`` tokens only — the full ``config.option`` namespace must not leak into templates.

    Args:
        config: The pytest ``Config`` exposing ``invocation_params.args`` and ``option``.

    Returns:
        A name -> value mapping of the options the user passed on the CLI.
    """
    names: set[str] = set()
    invocation_params = getattr(config, "invocation_params", None)
    tokens = getattr(invocation_params, "args", None) or []
    for token in tokens:
        match = _PLACEHOLDER_SOURCE_PATTERN.match(str(token))
        if match:
            names.add(match.group(1).replace("-", "_"))

    option = config.option
    return {
        name: getattr(option, name) for name in names if hasattr(option, name) and getattr(option, name) is not None
    }


def render_base_url(template: str, context: dict[str, t.Any]) -> str:
    """Render a ``base_url`` template with Jinja2 and normalize URL whitespace.

    Rendering uses ``StrictUndefined`` (unknown variables raise) and a ``match_re`` test for conditional assembly.

    Args:
        template: The ``base_url`` option value, a Jinja2 template string.
        context: The rendering context — the full environment plus the passed CLI options.

    Returns:
        The rendered URL with all literal whitespace removed.
    """
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=False)
    env.tests["match_re"] = _match_re

    rendered = env.from_string(template).render(**context)

    # A URL never contains literal whitespace — strip it so multi-line templates render to one clean URL.
    return re.sub(r"\s+", "", rendered)
