"""Diff formatter for endpoint comparison results.

render_diff wraps one comparison result into a single-line JSON document keyed by the unit's id.
"""

import json
from typing import Any


def render_diff(endpoint_id: str, diff: dict[str, Any]) -> str:
    """Render one comparison result as a single-line JSON document.

    Args:
        endpoint_id: Identifier key of the compared unit (raw id, or sanitized segment for removed artifact dirs).
        diff: Comparison result mapping; an empty mapping means no drift.

    Returns:
        One single-line JSON document keyed by ``endpoint_id``.
    """
    return json.dumps({endpoint_id: diff}, ensure_ascii=False)
