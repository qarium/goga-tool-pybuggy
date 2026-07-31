"""Tests for the `pybuggy.plugin.loaders` discovery cell.

Mirrors the source layout (`tests/plugin/loaders/test_loaders.py`). Covers the
contract surface (importability + signatures) and the behavioral logic of every
entity of the loaders cell.

The loaders mutate a caller-supplied accumulator list (`load(modules) -> None`)
rather than returning a list — every behavioral test drives an accumulator and
asserts its contents after the call.
"""

import inspect
import sys

import pytest
from pybuggy.plugin.loaders import ModuleLoader, PackageLoader
from pybuggy.plugin.loaders import loaders as loaders_module
from pybuggy.plugin.loaders.loaders import _module_is_pytest_plugin

FIXTURE_MODULE_SOURCE = """
import pytest


@pytest.fixture
def thing():
    return 1
"""

BROKEN_MODULE_SOURCE = "import does_not_exist_module\n"

# A module exposing only a public ``pytest_*`` hook (no fixture marker). The
# probe's ``attr.startswith("pytest_")`` branch should detect it.
HOOK_MODULE_SOURCE = """
def pytest_collection_modifyitems(items):
    ...
"""

# A module exposing only an underscore-prefixed (private) name. The public-name
# guard (``not attr.startswith("_")``) should exclude it.
PRIVATE_HOOK_MODULE_SOURCE = """
def _pytest_collection_modifyitems(items):
    ...
"""


@pytest.fixture(autouse=True)
def isolate_sys_modules():
    """Snapshot and restore sys.modules so trial imports never leak across tests."""
    snapshot = sys.modules.copy()

    yield

    extra = set(sys.modules) - set(snapshot)
    for key in extra:
        del sys.modules[key]


class TestModuleIsPytestPluginContract:
    """Contract tests for `_module_is_pytest_plugin`."""

    def test_routine_is_callable(self):
        assert callable(_module_is_pytest_plugin)

    def test_routine_has_expected_signature(self):
        sig = inspect.signature(_module_is_pytest_plugin)

        params = list(sig.parameters)
        assert params == ["name"]

        name_param = sig.parameters["name"]
        assert name_param.annotation is str

        assert sig.return_annotation is bool

    def test_routine_not_in_facade_all(self):
        from pybuggy.plugin.loaders import __all__ as loaders_all

        assert "_module_is_pytest_plugin" not in loaders_all


class TestModuleIsPytestPluginLogic:
    """Behavioral logic tests for `_module_is_pytest_plugin`."""

    def test_module_is_pytest_plugin_detects_fixture_module(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(tmp_path)

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text(FIXTURE_MODULE_SOURCE)

        is_plugin = _module_is_pytest_plugin("pkg.mod")

        assert is_plugin is True
        assert "pkg.mod" not in sys.modules

    def test_module_is_pytest_plugin_keeps_preexisting_module(self, tmp_path, monkeypatch):
        import importlib

        monkeypatch.syspath_prepend(tmp_path)

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text(FIXTURE_MODULE_SOURCE)

        importlib.import_module("pkg.mod")
        assert "pkg.mod" in sys.modules

        _module_is_pytest_plugin("pkg.mod")

        assert "pkg.mod" in sys.modules

    def test_module_is_pytest_plugin_broken_candidate_raises(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(tmp_path)

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "broken.py").write_text(BROKEN_MODULE_SOURCE)

        with pytest.raises(ModuleNotFoundError):
            _module_is_pytest_plugin("pkg.broken")

        assert "pkg.broken" not in sys.modules

    def test_module_is_pytest_plugin_detects_hook_module(self, tmp_path, monkeypatch):
        # A module exposing only a public ``pytest_*`` hook (no fixture marker) is
        # detected via the ``attr.startswith("pytest_")`` branch.
        monkeypatch.syspath_prepend(tmp_path)

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "hook.py").write_text(HOOK_MODULE_SOURCE)

        is_plugin = _module_is_pytest_plugin("pkg.hook")

        assert is_plugin is True
        assert "pkg.hook" not in sys.modules

    def test_module_is_pytest_plugin_cleans_up_parent_packages(self, tmp_path, monkeypatch):
        # `importlib.import_module("pkg.sub.mod")` also inserts the ancestor
        # packages "pkg" and "pkg.sub" into sys.modules. The probe must remove
        # those too (CODEMANIFEST: probing a module must not pollute
        # sys.modules), not just the leaf module.
        monkeypatch.syspath_prepend(tmp_path)

        pkg = tmp_path / "pkg"
        (pkg / "sub").mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "sub" / "__init__.py").write_text("")
        (pkg / "sub" / "mod.py").write_text(FIXTURE_MODULE_SOURCE)

        assert "pkg" not in sys.modules
        assert "pkg.sub" not in sys.modules

        is_plugin = _module_is_pytest_plugin("pkg.sub.mod")

        assert is_plugin is True
        assert "pkg.sub.mod" not in sys.modules
        assert "pkg.sub" not in sys.modules
        assert "pkg" not in sys.modules

    def test_module_is_pytest_plugin_ignores_private_hook(self, tmp_path, monkeypatch):
        # A module exposing only an underscore-prefixed name is excluded by the
        # public-name guard, so it is not treated as a plugin.
        monkeypatch.syspath_prepend(tmp_path)

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "priv.py").write_text(PRIVATE_HOOK_MODULE_SOURCE)

        is_plugin = _module_is_pytest_plugin("pkg.priv")

        assert is_plugin is False
        assert "pkg.priv" not in sys.modules


# Source for a generated-fixture module (carries a `pytest_*`-style fixture so the
# probe recognizes it as a pytest plugin).
GENERATED_FIXTURE_SOURCE = """
import pytest


@pytest.fixture
def get_orders():
    return 1
"""

# Source for a non-plugin module (no pytest surface).
PLAIN_MODULE_SOURCE = "value = 1\n"


class TestLoadersContract:
    """Contract tests for `PackageLoader` and `ModuleLoader`."""

    def test_loaders_importable_from_facade(self):
        from pybuggy.plugin.loaders import ModuleLoader, PackageLoader

        assert PackageLoader is not None
        assert ModuleLoader is not None

    def test_loaders_importable_from_location(self):
        from pybuggy.plugin.loaders.loaders import ModuleLoader, PackageLoader

        assert PackageLoader is not None
        assert ModuleLoader is not None

    @pytest.mark.parametrize("loader_name", ["PackageLoader", "ModuleLoader"])
    def test_loader_is_class_with_api(self, loader_name):
        from pybuggy.plugin.loaders import loaders

        loader_cls = getattr(loaders, loader_name)

        assert isinstance(loader_cls, type)
        # Methods live on the class.
        for method in ("from_config", "load"):
            assert callable(getattr(loader_cls, method)), f"{loader_name} missing {method}"
        # `name`/`required` are dataclass fields resolved on the instance.
        instance = loader_cls(name="anything", required=False)

        assert instance.name == "anything"
        assert instance.required is False

    @pytest.mark.parametrize("loader_name", ["PackageLoader", "ModuleLoader"])
    def test_loader_required_defaults_true(self, loader_name):
        from pybuggy.plugin.loaders import loaders

        loader_cls = getattr(loaders, loader_name)

        instance = loader_cls(name="anything")

        assert instance.required is True

    @pytest.mark.parametrize("loader_name", ["PackageLoader", "ModuleLoader"])
    def test_loader_from_config_signature(self, loader_name):
        from pybuggy.plugin.loaders import loaders

        loader_cls = getattr(loaders, loader_name)

        sig = inspect.signature(loader_cls.from_config)

        assert list(sig.parameters) == ["config"]

    @pytest.mark.parametrize("loader_name", ["PackageLoader", "ModuleLoader"])
    def test_loader_load_takes_modules_accumulator(self, loader_name):
        # `load` mutates a caller-supplied accumulator: `load(self, modules)`.
        from pybuggy.plugin.loaders import loaders

        loader_cls = getattr(loaders, loader_name)

        sig = inspect.signature(loader_cls.load)

        assert list(sig.parameters) == ["self", "modules"]


class TestPackageLoaderLogic:
    """Behavioral logic tests for `PackageLoader`."""

    def test_package_loader_walks_tree_and_filters(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)

        api = tmp_path / "api"
        (api / "orders" / "get_orders").mkdir(parents=True)
        (api / "__init__.py").write_text("")
        (api / "util.py").write_text(PLAIN_MODULE_SOURCE)
        (api / "orders" / "__init__.py").write_text("")
        (api / "orders" / "get_orders" / "__init__.py").write_text("")
        (api / "orders" / "get_orders" / "api.py").write_text(GENERATED_FIXTURE_SOURCE)

        modules: list[str] = []
        PackageLoader(name="api", required=False).load(modules)

        assert modules == ["api.orders.get_orders.api"]

    def test_package_loader_required_missing_raises_oserror(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with pytest.raises(OSError, match="not found"):
            PackageLoader(name="absent_pkg", required=True).load([])

    def test_package_loader_optional_missing_appends_nothing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        modules: list[str] = []
        PackageLoader(name="absent_pkg", required=False).load(modules)

        assert modules == []

    def test_package_loader_skips_non_package_subdirs(self, tmp_path, monkeypatch):
        # A subdirectory WITHOUT __init__.py is pruned by the ``dirs[:]`` filter,
        # so the fixture .py it contains is never probed/discovered.
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)

        api = tmp_path / "api"
        (api / "orders" / "get_orders").mkdir(parents=True)
        (api / "notpkg").mkdir()
        (api / "__init__.py").write_text("")
        (api / "orders" / "__init__.py").write_text("")
        (api / "orders" / "get_orders" / "__init__.py").write_text("")
        (api / "orders" / "get_orders" / "api.py").write_text(GENERATED_FIXTURE_SOURCE)
        # `notpkg/` has no __init__.py -> pruned; its stray.py must not be discovered.
        (api / "notpkg" / "stray.py").write_text(GENERATED_FIXTURE_SOURCE)

        modules: list[str] = []
        PackageLoader(name="api", required=False).load(modules)

        assert modules == ["api.orders.get_orders.api"]
        assert "api.notpkg.stray" not in modules


class TestModuleLoaderLogic:
    """Behavioral logic tests for `ModuleLoader`."""

    def test_module_loader_appends_plugin_module(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)

        (tmp_path / "mod.py").write_text(FIXTURE_MODULE_SOURCE)

        modules: list[str] = []
        ModuleLoader(name="mod", required=True).load(modules)

        assert modules == ["mod"]

    def test_module_loader_skips_non_plugin_module(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)

        (tmp_path / "plain.py").write_text(PLAIN_MODULE_SOURCE)

        modules: list[str] = []
        ModuleLoader(name="plain", required=True).load(modules)

        assert modules == []

    def test_module_loader_required_missing_raises_filenotfound(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError):
            ModuleLoader(name="absent_mod", required=True).load([])

    def test_module_loader_optional_missing_appends_nothing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        modules: list[str] = []
        ModuleLoader(name="absent_mod", required=False).load(modules)

        assert modules == []


class TestLoaderFromConfig:
    """`from_config` str/dict branching for both loaders."""

    @pytest.mark.parametrize("loader_name", ["PackageLoader", "ModuleLoader"])
    def test_from_config_str_and_dict_forms(self, loader_name):
        loader_cls = getattr(loaders_module, loader_name)

        from_str = loader_cls.from_config("api")

        assert from_str.name == "api"
        assert from_str.required is True

        from_dict = loader_cls.from_config({"name": "api", "required": False})

        assert from_dict.name == "api"
        assert from_dict.required is False

    @pytest.mark.parametrize("loader_name", ["PackageLoader", "ModuleLoader"])
    def test_from_config_dict_required_defaults_true(self, loader_name):
        loader_cls = getattr(loaders_module, loader_name)

        from_dict = loader_cls.from_config({"name": "api"})

        assert from_dict.name == "api"
        assert from_dict.required is True
