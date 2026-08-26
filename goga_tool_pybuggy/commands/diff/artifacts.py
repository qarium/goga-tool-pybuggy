"""Artifact-tree routines for the endpoint diff command.

sanitize_id derives the artifact-directory segment of an endpoint id;
orphan_artifact_dirs discovers the artifact directories of one spec's api
tree that match no endpoint of the spec (the removed side of the report).
"""

import re
from pathlib import Path

from ...spec import Endpoint

# Characters of an endpoint id that cannot appear in a Python identifier.
# The rule reproduces generate._safe_identifier (non-word character -> "_",
# leading digit -> "_" prefix) so a segment computed here locates every
# generated artifact directory and never mismatches one; the rule is kept
# local because a private import from commands/generate would cross cell
# boundaries.
_NON_IDENT_RE = re.compile(r"\W")


def sanitize_id(endpoint_id: str) -> str:
    """Derive the artifact-directory segment of a raw endpoint id.

    Replaces every non-word character with ``_`` (Unicode word characters
    are preserved) and prefixes ``_`` when the result would start with a
    digit. The mapping is not injective — ``v1.0_clients_get`` and
    ``v1_0_clients_get`` collapse into the same segment ``v1_0_clients_get``
    (both name the same generated directory).

    Args:
        endpoint_id: The raw `Endpoint` id (e.g., ``v1.0_clients_get``,
            ``2fa_verify_get``).

    Returns:
        The segment naming the endpoint's artifact directory
        ``api/<spec>/<segment>/``.
    """
    segment = _NON_IDENT_RE.sub("_", endpoint_id)
    return f"_{segment}" if segment[:1].isdigit() else segment


def orphan_artifact_dirs(api_spec_dir: Path, endpoints: list[Endpoint]) -> list[Path]:
    """Discover the artifact directories of a spec's api tree matching no endpoint.

    An absent api tree is a normal case and yields an empty list. Matching
    runs over sanitized segments — never raw ids — and over the full
    endpoint list of the spec, never a filtered subset. Files found in the
    tree (e.g., the ``__init__.py`` package marker written by generate)
    are never reported: only directories participate in orphan discovery.
    Discovery is read-only and keys on names only — directory contents are
    never read.

    Args:
        api_spec_dir: The spec's artifact tree directory (``api/<spec>``);
            may be absent.
        endpoints: Every endpoint of the spec (the unfiltered list).

    Returns:
        The artifact directories matching no endpoint, sorted by segment.
    """
    if not api_spec_dir.is_dir():
        return []

    expected = {sanitize_id(endpoint.id) for endpoint in endpoints}
    return sorted(
        (d for d in api_spec_dir.iterdir() if d.is_dir() and d.name not in expected),
        key=lambda d: d.name,
    )
