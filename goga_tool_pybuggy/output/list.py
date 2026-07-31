"""List formatter for endpoint display.

Provides render_list - a pure function that formats endpoint data into
text blocks for CLI consumption.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..spec import Endpoint


def render_list(name: str, location: str, endpoints: list["Endpoint"]) -> str:
    """Render endpoint list as text.

    Produces a header line followed by one line per endpoint, sorted by id.
    Format: "<name> (<location>)" then "* <id> -> [<METHOD>] <path>" for each.

    Args:
        name: Spec name for the header.
        location: Spec location path for the header.
        endpoints: List of endpoints to render.

    Returns:
        Formatted text block with header and endpoint lines.
    """
    lines = [f"{name} ({location})"]

    for endpoint in sorted(endpoints, key=lambda e: e.id):
        method_upper = endpoint.method.upper()
        lines.append(f"* {endpoint.id} -> [{method_upper}] {endpoint.path}")

    return "\n".join(lines)
