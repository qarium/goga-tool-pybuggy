"""Assert configuration of the `goga_tool_pybuggy.api.asserts` cell.

``AssertConfig`` carries the static check parameters; runtime flags stay on the consuming entities.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class AssertConfig(BaseModel):
    """Static configuration for response-level asserts.

    Every field is optional; ``None`` disables that check.

    Attributes:
        expected_status: expected success status code; ``None`` disables the auto-check.
        schemas_dir: directory of json-schema files (``<status>*.json``); ``None`` skips validation.
        timeout: baseline polling timeout (seconds); ``None`` runs the assertion once.
        delay: seconds between polling attempts; ``None`` uses the matcher default.
        assert_field_class: dotted import path of a custom ``AssertField``; ``None`` uses the built-in.
        assert_response_class: dotted import path of a custom ``Expect``; ``None`` uses the built-in.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    expected_status: int | None = None
    schemas_dir: Path | None = None
    timeout: int | float | None = None
    delay: int | float | None = None
    assert_field_class: str | None = None
    assert_response_class: str | None = None
