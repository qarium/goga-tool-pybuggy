import re
import typing as t

import jinja2


def _match_re(value: t.Any, pattern: str) -> bool:
    return re.match(pattern, str(value)) is not None


def render_base_url(template: str, context: dict[str, t.Any]) -> str:
    """Render a ``base_url`` template with Jinja2 and normalize URL whitespace.

    The template is rendered once against ``context`` with Jinja2
    (``StrictUndefined``; the ``match_re`` test registered). A plain template
    without placeholders renders to itself.

    A URL never legitimately contains literal whitespace — it would be
    percent-encoded (``%20``) and break the request path. So every whitespace
    run in the rendered result is removed. This lets a multi-line ``base_url``
    template — whether a YAML folded scalar (``>``) or a literal block scalar
    (``|``) — render to a single clean URL regardless of where the newlines, or
    an empty Jinja conditional block, leave whitespace behind.

    Args:
        template: The ``base_url`` option value, a Jinja2 template string.
        context: The rendering context — the full environment plus the CLI
            options the user actually passed.

    Returns:
        The rendered URL with all literal whitespace removed.
    """
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=False)
    env.tests["match_re"] = _match_re

    rendered = env.from_string(template).render(**context)

    # base_url is a single URL token; literal whitespace is never valid in a URL
    # (it would be percent-encoded to %20). Drop whitespace introduced by YAML
    # folded/literal block scalars and empty Jinja blocks so a multi-line
    # template renders to one clean URL.
    return re.sub(r"\s+", "", rendered)
