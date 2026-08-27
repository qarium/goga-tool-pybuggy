"""Diff formatter for endpoint comparison results.

Provides render_diff - a pure function that wraps one comparison result
into a single-line JSON document keyed by the compared unit's identifier.
"""

import json
from typing import Any


def render_diff(endpoint_id: str, diff: dict[str, Any]) -> str:
    """Render one comparison result as a single-line JSON document.

    Builds a single-entry mapping ``endpoint_id`` -> ``diff`` and serializes
    it as one JSON line:
    - ``{"<endpoint_id>": <diff>}`` for a reported drift
    - ``{"<endpoint_id>": {}}`` when there is no drift (empty mapping)

    Args:
        endpoint_id: Identifier key of the compared unit - the raw endpoint id
            for spec-side entries or the sanitized artifact segment for removed
            artifact directories; supplied by the caller.
        diff: The comparison result as a JSON-native plain mapping; an empty
            mapping means no drift.

    Returns:
        One single-line JSON document keyed by ``endpoint_id``.
    """
    return json.dumps({endpoint_id: diff}, ensure_ascii=False)
