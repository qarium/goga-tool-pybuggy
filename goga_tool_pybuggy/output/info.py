"""Info formatter for endpoint display.

render_info formats endpoint data as JSON for CLI consumption.
"""

import json
import re
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..spec import Endpoint


def _json_default(obj: object) -> str:
    """Serialize non-JSON-native objects carried in resolved specs.

    YAML date-like values arrive as ``date``/``datetime``; one ``date`` check covers both.

    Args:
        obj: Object that ``json.dumps`` could not encode natively.

    Returns:
        ISO 8601 string for date/datetime values.

    Raises:
        TypeError: For any unhandled type; re-raised so ``json.dumps`` reports its standard message.
    """
    if isinstance(obj, date):
        return obj.isoformat()

    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def render_info(endpoints: list["Endpoint"]) -> str:
    """Render endpoint info as JSON.

    Path parameters are converted from {param} to :param; non-JSON-native values render as ISO 8601 strings.

    Args:
        endpoints: List of endpoints to render.

    Returns:
        JSON string representation (object for single, array for multiple).
    """
    objs = []
    for endpoint in endpoints:
        # Convert path parameters from {param} to :param
        path = re.sub(r"\{([^}]+)\}", r":\1", endpoint.path)

        obj = {
            "Method": endpoint.method,
            "Path": path,
            "Request": endpoint.request,
            "Response": endpoint.response,
            "QueryParams": endpoint.query_params,
            "Description": endpoint.description,
        }
        objs.append(obj)

    # Return single object for one endpoint, array for multiple
    data = objs[0] if len(objs) == 1 else objs

    return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)
