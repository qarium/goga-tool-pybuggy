"""Endpoint entity with computed id."""

from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field

from .endpoint_id import build_endpoint_id


class Endpoint(BaseModel):
    """HTTP endpoint representation with computed id.

    Represents a single API endpoint extracted from an OpenAPI/Swagger spec.
    The `id` field is computed from method and path via `build_endpoint_id`.

    Attributes:
        method: HTTP method, lowercased.
        path: Path template with parameters in braces, e.g., "/clients/{id}".
        request: Resolved request-body schema (primary JSON content) or {}.
        response: {status_code: resolved_schema} for each response (primary JSON content).
        query_params: {param_name: schema} for query parameters only.
        description: Operation description or "".
        id: Stable identifier derived from method and path (computed field).
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    method: str
    path: str
    request: dict[str, Any]
    response: dict[str, Any]
    query_params: dict[str, Any]
    description: str

    @computed_field  # type: ignore[misc]
    @property
    def id(self) -> str:
        """Stable identifier derived from method and path.

        Generated via `build_endpoint_id(self.method, self.path)`.
        """
        return build_endpoint_id(self.method, self.path)
