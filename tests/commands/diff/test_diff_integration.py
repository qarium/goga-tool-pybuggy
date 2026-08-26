"""Integration tests for the generate → diff symmetry and the read-only guarantee.

Cross-cell scenarios (generate cell + diff cell + output facade): the strongest symmetry
guarantee is that artifacts written by ``run_generate`` read back as no-drift through
``run_diff``; the read-only acceptance criterion is a byte-identical api tree after a run.
Handlers are called directly (no CliRunner) over real files under ``tmp_path``, with the
config path redirected through ``CONFIG_PATH_ATTR``.
"""

import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest
from goga_tool_pybuggy.commands.diff import run_diff
from goga_tool_pybuggy.commands.generate import run_generate

CONFIG_PATH_ATTR = "goga_tool_pybuggy.config.storage.CONFIG_PATH"

_OPENAPI_PREFIX = """\
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
"""

_STARTUP_GET = """\
paths:
  /clients/startup:
    get:
      description: Start a client
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
"""


def _write_spec(spec_dir: Path, filename: str, body: str) -> None:
    """Write a YAML spec file under ``spec_dir`` prefixed with minimal OpenAPI header."""
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / filename).write_text(_OPENAPI_PREFIX + body)


def _write_config(tmp_path: Path, specs: dict) -> Path:
    """Write a config.yml whose ``specs`` map mirrors ``specs`` (name -> location)."""
    config_path = tmp_path / "config.yml"
    if not specs:
        config_path.write_text("specs: {}\n")
        return config_path

    lines = ["specs:"]
    for name, location in specs.items():
        lines.append(f"  {name}:")
        lines.append("    type: openapi")
        lines.append(f"    location: {location}")
    config_path.write_text("\n".join(lines) + "\n")
    return config_path


def _write_artifact(root: Path, spec: str, segment: str, meta: dict, schemas: dict) -> None:
    """Write ``api/<spec>/<segment>/`` with a meta.json and one schemas/<code>.json per code."""
    endpoint_dir = root / "api" / spec / segment
    schemas_dir = endpoint_dir / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    (endpoint_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    for status_code, schema in schemas.items():
        (schemas_dir / f"{status_code}.json").write_text(
            json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _setup_generated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Write a one-spec workspace and run run_generate to produce the full artifact set."""
    monkeypatch.chdir(tmp_path)
    _write_spec(tmp_path / ".specs", "client.yaml", _STARTUP_GET)
    monkeypatch.setattr(CONFIG_PATH_ATTR, _write_config(tmp_path, {"client": ".specs/client.yaml"}))
    run_generate(None, force=True)


def _tree_snapshot(root: Path) -> dict[str, str]:
    """Snapshot every file under ``root`` as {relative posix path: sha256 of contents}."""
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


# Cross-entity interaction: generate (writer) ↔ diff (reader) ----------------


def test_run_diff_after_generate_no_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Artifacts written by run_generate read back through run_diff with an empty diff.

    The full artifact set (meta.json, schemas/, api.py, markers, tests tree) comes from a real
    ``run_generate`` run, so this catches any sanitize-rule or meta-key drift between the
    generate and diff cells: an asymmetric rule would surface as a non-empty diff document.
    """
    _setup_generated_workspace(tmp_path, monkeypatch)

    run_diff(None, None)

    assert capsys.readouterr().out.splitlines() == ['{"clients_startup_get": {}}']
    # The generated tree exists with the full artifact set, not a hand-written subset.
    endpoint_dir = tmp_path / "api" / "client" / "clients_startup_get"
    assert (endpoint_dir / "meta.json").is_file()
    assert (endpoint_dir / "schemas" / "200.json").is_file()


def test_run_diff_read_only_leaves_tree_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Two diff runs leave every generated file byte-identical (mtime-independent check)."""
    _setup_generated_workspace(tmp_path, monkeypatch)
    api_root = tmp_path / "api"
    snapshot_before = _tree_snapshot(api_root)

    run_diff(None, None)
    capsys.readouterr()
    run_diff(None, None)
    capsys.readouterr()

    assert _tree_snapshot(api_root) == snapshot_before


def test_run_diff_after_importing_generated_tree_still_no_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A run over an imported (pytest-executed) artifact tree still reports no drift.

    Importing the generated fixture package — the documented generate -> test
    workflow — leaves ``__pycache__`` directories under ``api/<spec>/``. Those
    are tooling output, not removed endpoints, and must not be reported.
    """
    _setup_generated_workspace(tmp_path, monkeypatch)

    # Import the generated fixture module the way the plugin loader does,
    # which materializes api/<spec>/__pycache__/ on disk. The sys.path entry
    # and every "api*" module are dropped afterwards so the import cannot
    # leak into later tests.
    sys.path.insert(0, str(tmp_path))
    try:
        importlib.import_module("api.client.clients_startup_get.api")
        assert (tmp_path / "api" / "client" / "__pycache__").is_dir()
    finally:
        sys.path.remove(str(tmp_path))
        for module_name in [n for n in sys.modules if n == "api" or n.startswith("api.")]:
            del sys.modules[module_name]

    assert (tmp_path / "api" / "client" / "__pycache__").is_dir()

    run_diff(None, None)

    assert capsys.readouterr().out.splitlines() == ['{"clients_startup_get": {}}']
