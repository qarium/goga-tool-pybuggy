"""Contract and logic tests for spec_contract / artifact_contract."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import click
import goga_tool_pybuggy.commands.diff
import pytest
from goga_tool_pybuggy.commands.diff import artifact_contract, spec_contract
from goga_tool_pybuggy.spec import Endpoint


def _endpoint(**overrides: Any) -> Endpoint:
    """Build a minimal kw_only Endpoint, overridable per test scenario."""
    fields: dict[str, Any] = {
        "method": "get",
        "path": "/clients/{id}",
        "request": {"type": "object"},
        "response": {"200": {"type": "object"}},
        "query_params": {"id": {"type": "string"}},
        "path_params": {"id": {"type": "string"}},
        "description": "d",
    }
    fields.update(overrides)
    return Endpoint(**fields)


# Contract tests ---------------------------------------------------------------


def test_spec_contract_importable_and_signature() -> None:
    """spec_contract is importable from the cell facade as (endpoint,) -> dict[str, Any]."""
    params = spec_contract.__code__.co_varnames[: spec_contract.__code__.co_argcount]

    assert params == ("endpoint",)
    assert spec_contract.__annotations__["return"] == dict[str, Any]


def test_artifact_contract_importable_and_signature() -> None:
    """artifact_contract is importable from the cell facade as (artifact_dir,) -> dict[str, Any]."""
    params = artifact_contract.__code__.co_varnames[: artifact_contract.__code__.co_argcount]

    assert params == ("artifact_dir",)
    assert artifact_contract.__annotations__["return"] == dict[str, Any]


def test_contract_routines_listed_in_facade_all() -> None:
    """The commands/diff facade exports both contract routines and keeps __all__ sorted."""
    assert "spec_contract" in goga_tool_pybuggy.commands.diff.__all__
    assert "artifact_contract" in goga_tool_pybuggy.commands.diff.__all__
    assert goga_tool_pybuggy.commands.diff.__all__ == sorted(goga_tool_pybuggy.commands.diff.__all__)


# Logic tests ------------------------------------------------------------------


def test_spec_contract_maps_endpoint_fields() -> None:
    """The unified structure carries the meta.json keys plus schemas from the response."""
    contract = spec_contract(
        _endpoint(
            method="get",
            path="/clients/{id}",
            request={"type": "object"},
            response={"200": {"type": "object"}},
            query_params={"id": {"type": "string"}},
            path_params={"id": {"type": "string"}},
            description="d",
        )
    )

    assert contract == {
        "parameters": {"id": {"type": "string"}},
        "request_body": {"type": "object"},
        "vars": {"id": {"type": "string"}},
        "schemas": {"200": {"type": "object"}},
    }


def test_spec_contract_normalizes_dates_to_iso() -> None:
    """YAML date objects carried by the resolved spec become ISO 8601 strings via round-trip."""
    contract = spec_contract(
        _endpoint(request={"properties": {"since": {"type": "string", "format": "date", "example": date(2020, 1, 1)}}})
    )

    assert contract["request_body"]["properties"]["since"]["example"] == "2020-01-01"
    json.dumps(contract)  # no datetime objects remain in the structure


def test_spec_contract_non_serializable_value_raises_type_error() -> None:
    """A value the serializer cannot handle re-raises TypeError with json.dumps' message.

    Dates are the only non-JSON-native type a resolved spec is expected to carry;
    anything else (a set, bytes) is a programming error and must surface as
    TypeError rather than being silently coerced.
    """
    with pytest.raises(TypeError, match="set is not JSON serializable"):
        spec_contract(_endpoint(request={"properties": {"tags": {"example": {1, 2}}}}))


def test_artifact_contract_reads_meta_and_schemas(tmp_path: Path) -> None:
    """meta.json supplies the first three keys; every schemas/*.json lands under its stem."""
    seg_dir = tmp_path / "api" / "client" / "seg"
    (seg_dir / "schemas").mkdir(parents=True)
    (seg_dir / "meta.json").write_text(
        json.dumps({"parameters": {"q": {"type": "string"}}, "request_body": {"type": "object"}, "vars": {}}),
        encoding="utf-8",
    )
    (seg_dir / "schemas" / "200.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")
    (seg_dir / "schemas" / "418.json").write_text(json.dumps({}), encoding="utf-8")

    contract = artifact_contract(seg_dir)

    assert contract == {
        "parameters": {"q": {"type": "string"}},
        "request_body": {"type": "object"},
        "vars": {},
        "schemas": {"200": {"type": "object"}, "418": {}},
    }


def test_artifact_contract_missing_meta_raises(tmp_path: Path) -> None:
    """An artifact directory without meta.json is corrupt — ClickException names the file."""
    seg_dir = tmp_path / "api" / "client" / "seg"
    (seg_dir / "schemas").mkdir(parents=True)

    with pytest.raises(click.ClickException, match=r"meta\.json"):
        artifact_contract(seg_dir)


def test_artifact_contract_corrupt_meta_raises(tmp_path: Path) -> None:
    """A meta.json that is not valid JSON maps to ClickException."""
    seg_dir = tmp_path / "api" / "client" / "seg"
    seg_dir.mkdir(parents=True)
    (seg_dir / "meta.json").write_text("{ not json", encoding="utf-8")

    with pytest.raises(click.ClickException, match=r"meta\.json"):
        artifact_contract(seg_dir)


@pytest.mark.parametrize("payload", ["null", "[1, 2]", '"text"', "42"])
def test_artifact_contract_non_object_meta_raises(tmp_path: Path, payload: str) -> None:
    """A meta.json holding valid non-object JSON is corrupt — ClickException, not TypeError.

    ``json.loads`` accepts any JSON document, but key lookups on a null/list/
    scalar raise ``TypeError``, which must not escape as a traceback.
    """
    seg_dir = tmp_path / "api" / "client" / "seg"
    seg_dir.mkdir(parents=True)
    (seg_dir / "meta.json").write_text(payload, encoding="utf-8")

    with pytest.raises(click.ClickException, match=r"meta\.json"):
        artifact_contract(seg_dir)


def test_artifact_contract_corrupt_schema_raises(tmp_path: Path) -> None:
    """A schema file that is not valid JSON maps to ClickException naming the file."""
    seg_dir = tmp_path / "api" / "client" / "seg"
    (seg_dir / "schemas").mkdir(parents=True)
    (seg_dir / "meta.json").write_text(json.dumps({"parameters": {}, "request_body": {}, "vars": {}}), encoding="utf-8")
    (seg_dir / "schemas" / "200.json").write_text("[", encoding="utf-8")

    with pytest.raises(click.ClickException, match=r"200\.json"):
        artifact_contract(seg_dir)


def test_artifact_contract_non_utf8_meta_raises(tmp_path: Path) -> None:
    """A non-UTF-8 meta.json is unreadable — ClickException, not a raw UnicodeDecodeError.

    ``UnicodeDecodeError`` is a ``ValueError`` outside the plain OSError family,
    so without it in the caught tuple the decode error escapes as a traceback
    instead of the documented CLI error.
    """
    seg_dir = tmp_path / "api" / "client" / "seg"
    seg_dir.mkdir(parents=True)
    (seg_dir / "meta.json").write_bytes(b"\xff\xfe{}")

    with pytest.raises(click.ClickException, match=r"meta\.json"):
        artifact_contract(seg_dir)


def test_artifact_contract_non_utf8_schema_raises(tmp_path: Path) -> None:
    """A non-UTF-8 schema file is unreadable — ClickException naming the file."""
    seg_dir = tmp_path / "api" / "client" / "seg"
    (seg_dir / "schemas").mkdir(parents=True)
    (seg_dir / "meta.json").write_text(json.dumps({"parameters": {}, "request_body": {}, "vars": {}}), encoding="utf-8")
    (seg_dir / "schemas" / "200.json").write_bytes(b"\xff\xfe{}")

    with pytest.raises(click.ClickException, match=r"200\.json"):
        artifact_contract(seg_dir)


def test_artifact_contract_meta_missing_keys_raises(tmp_path: Path) -> None:
    """A meta.json missing any of the three mandatory keys is corrupt — ClickException."""
    seg_dir = tmp_path / "api" / "client" / "seg"
    seg_dir.mkdir(parents=True)
    (seg_dir / "meta.json").write_text(json.dumps({"parameters": {}}), encoding="utf-8")

    with pytest.raises(click.ClickException, match=r"meta\.json"):
        artifact_contract(seg_dir)


def test_artifact_contract_missing_schemas_dir_yields_empty(tmp_path: Path) -> None:
    """An absent schemas/ subdirectory yields schemas: {} — glob over a missing dir is empty."""
    seg_dir = tmp_path / "api" / "client" / "seg"
    seg_dir.mkdir(parents=True)
    (seg_dir / "meta.json").write_text(json.dumps({"parameters": {}, "request_body": {}, "vars": {}}), encoding="utf-8")

    contract = artifact_contract(seg_dir)

    assert contract == {"parameters": {}, "request_body": {}, "vars": {}, "schemas": {}}
