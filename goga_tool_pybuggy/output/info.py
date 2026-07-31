"""Info formatter for endpoint display.

Provides render_info - a pure function that formats endpoint data into
JSON for CLI consumption.
"""

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..spec import Endpoint


def render_info(endpoints: list["Endpoint"]) -> str:
    """Render endpoint info as JSON.

    Converts a list of endpoints to JSON format:
    - Single endpoint: JSON object with keys Method, Path, Request, Response,
      QueryParams, Description
    - Multiple endpoints: JSON array of such objects
    - Path parameters are converted from {param} to :param format

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

    return json.dumps(data, ensure_ascii=False, indent=2)
