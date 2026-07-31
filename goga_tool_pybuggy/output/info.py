"""Info formatter for endpoint display.

Provides render_info - a pure function that formats endpoint data into
JSON for CLI consumption.
"""

import json
import re
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..spec import Endpoint


def _json_default(obj: object) -> str:
    """Serialize non-JSON-native objects carried in resolved specs.

    swax/Prance convert YAML date-like values (e.g. ``example: 2020-01-01``
    under ``format: date``/``date-time``) into ``datetime.date``/
    ``datetime.datetime`` objects, which ``json.dumps`` cannot encode by
    default. This renders them as ISO 8601 strings. ``datetime.datetime`` is a
    subclass of ``date``, so a single ``date`` check covers both.

    Args:
        obj: Object that ``json.dumps`` could not encode natively.

    Returns:
        ISO 8601 string for date/datetime values.

    Raises:
        TypeError: For any type this serializer does not handle, re-raised so
            ``json.dumps`` reports it with its standard message.
    """
    if isinstance(obj, date):
        return obj.isoformat()

    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def render_info(endpoints: list["Endpoint"]) -> str:
    """Render endpoint info as JSON.

    Converts a list of endpoints to JSON format:
    - Single endpoint: JSON object with keys Method, Path, Request, Response,
      QueryParams, Description
    - Multiple endpoints: JSON array of such objects
    - Path parameters are converted from {param} to :param format
    - Non-JSON-native values carried by resolved specs (e.g. ``datetime.date``/
      ``datetime.datetime`` from YAML date examples) are rendered as ISO 8601
      strings

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
