import re
import typing as t

import jinja2


def _match_re(value: t.Any, pattern: str) -> bool:
    return re.match(pattern, str(value)) is not None


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
