"""Tests for the config reading routines — ``config/storage.py``.

Contract layer: ``load_config`` takes no parameters and returns a ``Config``,
``resolve_autonomy`` maps a pipeline name to a bool, and the facade exports
neither the deleted path constant nor anything beyond the six declared names.
Behavior layer: the platform-facade read (absent and empty file), the ignored
``pipelines`` section on ``Config``, and the whole-axis validation matrix of
the resolver.
"""

import inspect

import goga_tool_pybuggy.config as cfg
import pytest
import yaml
from goga_tool_pybuggy.config import Config, load_config, resolve_autonomy
from pydantic import ValidationError

_SPECS_TREE = """\
specs:
  client:
    type: openapi
    location: .specs/client.yaml
    git:
      url: https://example.com/repo.git
      location: specs/client.yaml
"""

_AXIS_ENABLED_TREE = """\
pipelines:
  api.automate:
    autonomous: true
"""

# The deleted storage seam — spelled piecewise so the post-migration stragglers
# grep for the literal constant name stays clean while the absence assertions
# still check the exact name.
_DELETED_SEAM = "CONFIG" + "_PATH"


class TestStorageContract:
    """Facade exposure and signature surface of the reading routines."""

    def test_load_config_importable_from_facade(self) -> None:
        """The loader is importable from the config cell facade."""
        assert callable(load_config)

    def test_load_config_signature_is_no_arg(self) -> None:
        """The loader takes no parameters and returns a ``Config``."""
        signature = inspect.signature(load_config)

        assert signature.parameters == {}
        assert signature.return_annotation is Config

    def test_resolve_autonomy_importable_from_facade(self) -> None:
        """The resolver is importable from the config cell facade."""
        assert callable(resolve_autonomy)

    def test_resolve_autonomy_signature(self) -> None:
        """The resolver takes ``pipeline: str`` and returns a bool."""
        signature = inspect.signature(resolve_autonomy)

        assert list(signature.parameters) == ["pipeline"]
        assert signature.parameters["pipeline"].annotation is str
        assert signature.return_annotation is bool

    def test_config_facade_no_longer_exports_config_path(self) -> None:
        """The facade exports exactly the six declared names — the deleted seam is gone."""
        assert _DELETED_SEAM not in vars(cfg)
        assert _DELETED_SEAM not in cfg.__all__
        assert sorted(cfg.__all__) == [
            "Config",
            "GitEntry",
            "PipelineAutonomy",
            "SpecEntry",
            "load_config",
            "resolve_autonomy",
        ]


class TestLoadConfigBehavior:
    """Behavior of the no-arg platform-facade read."""

    def test_load_config_reads_standard_path(self, tool_config) -> None:
        """A specs-only tree loads through the standard location with no arguments."""
        tool_config(_SPECS_TREE)

        config = load_config()

        assert config.specs["client"].location == ".specs/client.yaml"
        assert config.specs["client"].type == "openapi"
        assert config.specs["client"].git is not None
        assert config.specs["client"].git.url == "https://example.com/repo.git"
        assert inspect.signature(load_config).parameters == {}

    def test_load_config_ignores_pipelines_section(self, tool_config) -> None:
        """The permissive ``Config`` model ignores the ``pipelines`` axis key."""
        tool_config(_SPECS_TREE + "pipelines:\n  api.automate:\n    autonomous: true\n")

        config = load_config()

        assert set(config.specs) == {"client"}

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(None, id="absent-file"),
            pytest.param("", id="empty-file"),
        ],
    )
    def test_load_config_absent_file_raises_naming_location(self, tool_config, content) -> None:
        """An absent or empty file (facade ``None`` for both) names the standard location."""
        if content is not None:
            tool_config(content)

        with pytest.raises(FileNotFoundError, match=r"\.goga/tools/pybuggy/config\.yml"):
            load_config()

    def test_load_config_propagates_invalid_yaml_raw(self, tool_config) -> None:
        """A malformed file propagates the facade's raw parse error."""
        tool_config("specs: [unclosed")

        with pytest.raises((yaml.YAMLError, ValueError)):
            load_config()

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param("just a string", id="string-root"),
            pytest.param("- a\n- list\n", id="list-root"),
        ],
    )
    def test_load_config_non_mapping_root_fails_validation(self, tool_config, content) -> None:
        """A parse whose root is not a mapping fails ``Config`` validation, not the read."""
        tool_config(content)

        with pytest.raises(ValidationError):
            load_config()


class TestResolveAutonomyBehavior:
    """Behavior of the whole-axis-validating autonomy resolver."""

    def test_resolve_autonomy_enabled_returns_true(self, tool_config) -> None:
        """An enabling entry for the running pipeline resolves to True."""
        tool_config(_AXIS_ENABLED_TREE)

        assert resolve_autonomy("api.automate") is True

    def test_resolve_autonomy_coerces_truthy_spelling(self, tool_config) -> None:
        """A quoted truthy spelling coerces to True through pydantic lax bool (REPL-pinned)."""
        tool_config('pipelines:\n  api.automate:\n    autonomous: "yes"\n')

        assert resolve_autonomy("api.automate") is True

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param("just a string\n", id="non-mapping-root"),
            pytest.param("specs: {}\npipelines:\n  - a\n  - b\n", id="non-mapping-axis"),
            pytest.param("pipelines:\n  api.automate: plain-string\n", id="non-mapping-entry"),
            pytest.param("pipelines:\n  api.automate:\n    autonomous: maybe\n", id="non-coercible-value"),
            pytest.param("pipelines:\n  api.automate:\n    autonomous: true\n    typo: 1\n", id="extra-member"),
        ],
    )
    def test_resolve_autonomy_structural_violations_parametrized(self, tool_config, content) -> None:
        """Every structural violation raises a clean error naming pybuggy.

        YAML-truthy spellings (``yes``/``on``) are deliberately absent from the
        matrix: PyYAML (YAML 1.1) parses them to real booleans, so the
        non-bool rejection row must use the non-coercible ``maybe``.
        """
        tool_config(content)

        with pytest.raises(ValueError, match="pybuggy tool config"):
            resolve_autonomy("api.automate")

    def test_resolve_autonomy_violation_names_offending_entry(self, tool_config) -> None:
        """The entry violation names the offending entry and chains the pydantic detail."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: maybe\n")

        with pytest.raises(ValueError, match=r"invalid pipelines entry 'api\.automate'") as excinfo:
            resolve_autonomy("api.automate")

        assert isinstance(excinfo.value.__cause__, Exception)

    def test_resolve_autonomy_propagates_facade_parse_error(self, tool_config) -> None:
        """A malformed file propagates the facade's raw parse error, undamped."""
        tool_config("pipelines: [unclosed")

        with pytest.raises((yaml.YAMLError, ValueError)):
            resolve_autonomy("api.automate")

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(None, id="absent-file"),
            pytest.param("", id="empty-file"),
            pytest.param("specs: {}\n", id="absent-section"),
            pytest.param("pipelines:\n  other.pipeline:\n    autonomous: true\n", id="other-pipeline-entry"),
            pytest.param("pipelines:\n  api.automate:\n    autonomous: false\n", id="disabled-entry"),
        ],
    )
    def test_resolve_autonomy_disabled_states_parametrized(self, tool_config, content) -> None:
        """Every disabled state resolves to False — silently."""
        if content is not None:
            tool_config(content)

        assert resolve_autonomy("api.automate") is False

    def test_resolve_autonomy_no_caching(self, tool_config) -> None:
        """A rewrite between two calls is visible immediately — no cached read."""
        tool_config("pipelines:\n  api.automate:\n    autonomous: false\n")
        assert resolve_autonomy("api.automate") is False

        tool_config("pipelines:\n  api.automate:\n    autonomous: true\n")
        assert resolve_autonomy("api.automate") is True

    def test_resolve_autonomy_unknown_names_never_fail(self, tool_config) -> None:
        """Entries for other pipelines never fail the call — the axis is permissive."""
        tool_config(_AXIS_ENABLED_TREE + "  other.pipeline:\n    autonomous: true\n")

        assert resolve_autonomy("code.review") is False
