"""List formatter for endpoint display.

Provides render_list - a pure function that formats endpoint data into
text blocks for CLI consumption - and render_status_list, the same block
with the artifact synchronization status annotated on every line.
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


def render_status_list(
    name: str,
    location: str,
    endpoints: list["Endpoint"],
    statuses: dict[str, str],
    removed: list[str],
) -> str:
    """Render endpoint list as text with the synchronization status of every line.

    Produces a header line followed by one line per entry - endpoints and removed
    artifact segments merged into one list sorted by line name. Endpoint lines read
    "* <id> -> [<METHOD>] <path> — STATUS: <status>", removed lines read
    "* <segment> — STATUS: REMOVED".

    Args:
        name: Spec name for the header.
        location: Spec location path for the header.
        endpoints: List of endpoints to render.
        statuses: Mapping of endpoint id to its status (ADD, UPD, OK); must cover
            every endpoint of `endpoints`.
        removed: Artifact directory segments matching no endpoint (the REMOVED side).

    Returns:
        Formatted text block with header and status-annotated lines.
    """
    lines = [f"{name} ({location})"]

    entries: list[tuple[str, str]] = []
    for endpoint in endpoints:
        line = f"* {endpoint.id} -> [{endpoint.method.upper()}] {endpoint.path} — STATUS: {statuses[endpoint.id]}"
        entries.append((endpoint.id, line))
    for segment in removed:
        entries.append((segment, f"* {segment} — STATUS: REMOVED"))

    entries.sort(key=lambda entry: entry[0])
    lines += [text for _, text in entries]

    return "\n".join(lines)
