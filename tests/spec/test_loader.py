"""Contract tests for load_spec routine."""

import pytest


class TestLoadSpecContract:
    """Contract tests for load_spec routine."""

    def test_import_load_spec_from_facade(self):
        """load_spec must be importable from goga_tool_pybuggy.spec facade."""
        from goga_tool_pybuggy.spec import load_spec

        assert callable(load_spec)

    def test_load_spec_signature(self):
        """load_spec must have signature (spec_path: pathlib.Path) -> dict[str, Any]."""
        import inspect
        from typing import get_type_hints

        from goga_tool_pybuggy.spec import load_spec

        sig = inspect.signature(load_spec)
        params = list(sig.parameters.keys())

        assert len(params) == 1, f"Expected 1 parameter, got {len(params)}"
        assert params[0] == "spec_path", f"Expected parameter 'spec_path', got '{params[0]}'"

        # Check return type annotation
        type_hints = get_type_hints(load_spec)
        assert "return" in type_hints, "load_spec must have return type annotation"
        # The return type should be dict[str, Any] or similar
        return_hint = type_hints["return"]
        # Check if it's a dict (the origin could be dict or Dict)
        from typing import get_origin

        origin = get_origin(return_hint)
        assert origin is dict, f"Expected return type dict, got {return_hint}"


class TestLoadSpecLogic:
    """Logic tests for load_spec routine."""

    def test_load_spec_parses_valid_spec(self, tmp_path):
        """load_spec should return a dict with 'paths' key for a valid minimal spec."""
        import yaml
        from goga_tool_pybuggy.spec import load_spec

        # Create a minimal valid OpenAPI 3.0 spec
        spec_content = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml.dump(spec_content), encoding="utf-8")

        result = load_spec(spec_file)

        assert isinstance(result, dict)
        assert "paths" in result
        assert result["paths"]["/test"]["get"]["responses"]["200"]["description"] == "OK"

    def test_load_spec_maps_parse_error_to_click_exception(self, tmp_path):
        """load_spec should map SpecParseError to click.ClickException."""
        import click
        from goga_tool_pybuggy.spec import load_spec

        # Create an invalid spec file
        spec_file = tmp_path / "invalid.yaml"
        spec_file.write_text("invalid: {{{}", encoding="utf-8")

        with pytest.raises(click.ClickException) as exc_info:
            load_spec(spec_file)

        # The exception message should contain the path
        assert "failed to parse spec" in str(exc_info.value).lower()
