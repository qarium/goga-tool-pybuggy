"""Artifact-tree routines for the endpoint diff command."""

import re
from pathlib import Path

from ...spec import Endpoint

# Mirrors generate._safe_identifier (non-word -> "_", leading digit -> "_" prefix)
# so segments always match generated directories; kept local to avoid a cross-cell import.
_NON_IDENT_RE = re.compile(r"\W")


def _is_tooling_dir(name: str) -> bool:
    """Report whether a directory name is tooling output, not an artifact segment.

    ``__pycache__`` and hidden directories are tooling state, not artifact sets — reporting one fails a healthy tree.

    Args:
        name: Directory name from the api tree.

    Returns:
        True when the directory belongs to tooling and must be skipped.
    """
    return name == "__pycache__" or name.startswith(".")


def sanitize_id(endpoint_id: str) -> str:
    """Derive the artifact-directory segment of a raw endpoint id.

    Non-word characters become ``_``, a leading digit gets a ``_`` prefix; the mapping is not injective.

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

    Matches sanitized segments over the full (unfiltered) endpoint list; an absent tree yields an empty list.

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
        (d for d in api_spec_dir.iterdir() if d.is_dir() and not _is_tooling_dir(d.name) and d.name not in expected),
        key=lambda d: d.name,
    )
