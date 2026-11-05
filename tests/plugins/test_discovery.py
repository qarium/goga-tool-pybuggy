"""Tests for the `goga_tool_pybuggy.plugins.discovery` module — the shared fixture discovery.

The ``loader:`` section of every tool document (api, sandbox, web alike) feeds
``load_fixture_plugins``; ``loader_section_of`` guards the document read against an unparsable
parse (the configure-time gate owns that failure).
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from goga_tool_pybuggy.plugins.discovery import LOADER_SECTION, load_fixture_plugins, loader_section_of
from goga_tool_pybuggy.plugins.loaders import ModuleLoader, PackageLoader
from yaml import YAMLError

# Generated-fixture source (carries a `@pytest.fixture`) — the discovery probe must qualify it.
_GENERATED_FIXTURE_SOURCE = """
import pytest


@pytest.fixture
def get_orders():
    return 1
"""


def _make_fixture_tree(tmp_path: Path) -> None:
    """Create a one-fixture ``presets/orders/api.py`` package tree under ``tmp_path``."""
    presets = tmp_path / "presets"
    (presets / "orders").mkdir(parents=True)
    (presets / "__init__.py").write_text("")
    (presets / "orders" / "__init__.py").write_text("")
    (presets / "orders" / "api.py").write_text(_GENERATED_FIXTURE_SOURCE)


class _RefusingConfigPlugin:
    """Plugin double whose config reader refuses — the unparsable-document seam."""

    @property
    def plugin_config(self) -> dict:
        raise YAMLError("bad indentation")


class TestLoaderSectionOf:
    """The guarded section read of a plugin's config document."""

    def test_reads_the_section_of_the_document(self):
        # The section lands verbatim; any plugin exposing plugin_config qualifies.
        plugin = SimpleNamespace(plugin_config={"loader": {"modules": ["pkg"]}, "provider": "openai"})

        assert loader_section_of(plugin) == {"modules": ["pkg"]}

    def test_missing_section_is_empty(self):
        assert loader_section_of(SimpleNamespace(plugin_config={"provider": "openai"})) == {}

    def test_null_section_is_empty(self):
        assert loader_section_of(SimpleNamespace(plugin_config={"loader": None})) == {}

    def test_unparsable_document_defers_to_the_configure_gate(self):
        # An unparsable document never crashes the install-time discovery — the run fails at
        # configphase with the plugin's own clean error instead.
        assert loader_section_of(_RefusingConfigPlugin()) == {}


class TestLoadFixturePlugins:
    """The pytest_plugins assembly from the explicit loaders and the loader section."""

    def test_section_key_is_loader(self):
        """The shared discovery section key of every tool document is ``loader``."""
        assert LOADER_SECTION == "loader"

    def test_seeds_survive_and_dedupe_with_the_section(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A consumer's own pytest_plugins declarations seed the accumulator and dedupe with the walk."""
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        _make_fixture_tree(tmp_path)

        context: dict[str, Any] = {"pytest_plugins": ["presets.orders.api"]}
        section = {"packages": [{"name": "presets", "required": False}]}

        load_fixture_plugins(context, [], section)

        assert context["pytest_plugins"] == ["presets.orders.api"]

    def test_explicit_loaders_append_their_modules(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """The explicit loaders run in addition to the section."""
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        _make_fixture_tree(tmp_path)

        context: dict[str, Any] = {}
        section = {"modules": ["presets.orders.api"]}

        load_fixture_plugins(context, [ModuleLoader("presets.orders.api", required=False)], section)

        assert context["pytest_plugins"] == ["presets.orders.api"]

    def test_package_walk_of_the_section(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """The section's packages walk their trees and append the qualifying modules."""
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        _make_fixture_tree(tmp_path)

        context: dict[str, Any] = {}
        load_fixture_plugins(context, [], {"packages": ["presets"]})

        assert context["pytest_plugins"] == ["presets.orders.api"]

    def test_no_loaders_and_empty_section_write_an_empty_list(self):
        """With nothing to discover the result is the deduplicated empty list — the key lands."""
        context: dict[str, Any] = {}

        load_fixture_plugins(context, [], {})

        assert context["pytest_plugins"] == []

    def test_null_section_discovers_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A ``loader:`` null section is an empty one — no configured discovery."""
        monkeypatch.chdir(tmp_path)

        context: dict[str, Any] = {}

        load_fixture_plugins(context, [], None)

        assert context["pytest_plugins"] == []


class TestLoadFixturePluginsErrors:
    """The discovery failures surface the loader errors — never a silent skip."""

    def test_required_missing_package_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)

        with pytest.raises(OSError, match="not found"):
            load_fixture_plugins({}, [PackageLoader("nowhere", required=True)], {})

    def test_unsupported_section_item_raises(self):
        with pytest.raises(TypeError, match="Unsupported config"):
            load_fixture_plugins({}, [], {"packages": [42]})
