"""Refs grammar: the declaration-time shape of ``$ref`` / ``$lookup`` row values."""

import re

REF_KEY = "$ref"
LOOKUP_KEY = "$lookup"

_ADDRESS_PATTERN = re.compile(r"^[^.]+\.[0-9]+\.[^.]+$")
_SCALARS = (str, int, float, bool, type(None))
_LOOKUP_KEYS = {"table", "where", "column"}


def is_reference(value: object) -> bool:
    """Whether one row value carries a reference form.

    Args:
        value: The row value inspected.

    Returns:
        True when the value is a dict carrying ``$ref`` or ``$lookup``; every other value,
        including plain dict column data, is not a reference.
    """
    return isinstance(value, dict) and (REF_KEY in value or LOOKUP_KEY in value)


def parse_ref_address(address: object) -> tuple[str, int, str]:
    """Split one ``$ref`` address into its table, row index, and column.

    Args:
        address: The address string of the ``table.index.column`` shape.

    Returns:
        The table name, the row index, and the column name.

    Raises:
        ValueError: The address does not match the ``table.index.column`` shape.
    """
    if not isinstance(address, str) or not _ADDRESS_PATTERN.match(address):
        raise ValueError(f"the $ref address '{address}' must match 'table.index.column'")

    table, index, column = address.split(".")

    return table, int(index), column


def validate_insert_rows(rows: object, context: str) -> None:
    """Validate the reference grammar of declared insert rows.

    Rows must be a list of mappings; every top-level row value carrying ``$ref`` or ``$lookup``
    must match the reference grammar. Resolution never happens here — only the shape is
    checked, at declaration time. Plain dict values (json-like columns) pass through
    untouched: references are recognized only as top-level row values.

    Args:
        rows: The declared rows of one insert.
        context: The declaration location naming the rows in error messages.

    Raises:
        ValueError: The rows or a row value carry a malformed reference form.
    """
    if not isinstance(rows, list):
        raise ValueError(f"{context}: rows must be a list of mappings")

    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{context} rows[{position}] must be a mapping")

        for column, value in row.items():
            _validate_value(value, f"{context} rows[{position}].{column}")


def _validate_value(value: object, location: str) -> None:
    """Validate one row value against the reference grammar.

    Args:
        value: The row value inspected.
        location: The value's declaration location for error messages.

    Raises:
        ValueError: The value carries a malformed reference form.
    """
    if not isinstance(value, dict):
        return

    if REF_KEY in value or LOOKUP_KEY in value:
        _validate_reference(value, location)


def _validate_reference(reference: dict[str, object], location: str) -> None:
    """Route one reference-carrying dict to its form validator.

    Args:
        reference: The row value carrying ``$ref`` or ``$lookup``.
        location: The value's declaration location for error messages.

    Raises:
        ValueError: The reference form is malformed.
    """
    if REF_KEY in reference:
        _validate_ref(reference, location)

        return

    if set(reference) != {LOOKUP_KEY}:
        raise ValueError(f"{location}: a $lookup value must carry only the '$lookup' key")

    _validate_lookup(reference[LOOKUP_KEY], location)


def _validate_ref(reference: dict[str, object], location: str) -> None:
    """Validate one ``$ref`` value.

    Args:
        reference: The row value carrying only ``$ref``.
        location: The value's declaration location for error messages.

    Raises:
        ValueError: The reference form is malformed.
    """
    if set(reference) != {REF_KEY}:
        raise ValueError(f"{location}: a $ref value must carry only the '$ref' key")

    try:
        parse_ref_address(reference[REF_KEY])
    except ValueError as exc:
        raise ValueError(f"{location}: {exc}") from exc


def _validate_lookup(spec: object, location: str) -> None:
    """Validate one ``$lookup`` specification.

    Args:
        spec: The mapping carried under ``$lookup`` — table, where, optional column.
        location: The value's declaration location for error messages.

    Raises:
        ValueError: The specification is malformed.
    """
    if not isinstance(spec, dict):
        raise ValueError(f"{location}: the $lookup specification must be a mapping")

    if unknown := set(spec) - _LOOKUP_KEYS:
        raise ValueError(f"{location}: unknown $lookup keys: {', '.join(sorted(unknown))}")

    table = spec.get("table")

    if not isinstance(table, str) or not table:
        raise ValueError(f"{location}: the $lookup table must be a non-empty string")

    column = spec.get("column")

    if column is not None and (not isinstance(column, str) or not column):
        raise ValueError(f"{location}: the $lookup column must be a non-empty string")

    where = spec.get("where")

    if not isinstance(where, dict) or not where:
        raise ValueError(f"{location}: the $lookup where must be a non-empty mapping")

    for key, condition in where.items():
        if not isinstance(condition, _SCALARS):
            raise ValueError(f"{location}: the $lookup where value of '{key}' must be a scalar")
