"""services entity: the per-test data-preset decorator."""

from collections.abc import Callable
from typing import Any

import pytest

from ..engines import validate_insert_rows

_SUPPORTED_KINDS = ("postgresql", "kafka", "vault", "http", "redis")

# The redis action grammar — the exact key set every declaration must carry: the `action`
# key plus the fields of the matching view operation. Duplicated from the config loader
# by design: the data cell cannot import the loader.
_REDIS_ACTIONS = {
    "set": ("key", "value"),
    "hset": ("key", "values"),
    "rpush": ("key", "values"),
    "sadd": ("key", "members"),
}
# The container-field type of every action — a `set` value rides as any plain object and
# is serialized at execution time, so its check is the always-true isinstance over `object`.
_REDIS_FIELD_TYPES = {
    "set": ("value", object),
    "hset": ("values", dict),
    "rpush": ("values", list),
    "sadd": ("members", list),
}


def services(**presets: dict[str, dict[str, list[dict[str, object]]]]) -> Callable[..., Any]:
    """Mark one test with per-test sandbox data presets.

    Each keyword names a supported service kind and carries that kind's service-targeted
    declarations: ``kind -> service name -> declaration list``. The declarations pass through
    as given — declaration order within one service is the application order. Presets apply
    only to the test declaring them: the marked presets are enqueued into the per-test batch at
    setup time, ahead of any in-test view declaration, and applied right before the first call
    to the service under test.

    Nothing executes at decoration time — the routine validates the kind keys, the
    declaration shapes, the ``$ref`` / ``$lookup`` grammar of postgresql rows, and the
    ``action`` grammar of redis declarations, then attaches the marker. Service names are
    validated later, at enqueue time, against the sandbox document.

    Args:
        **presets: The per-kind declarations. Every key must be one of the supported kinds
            (postgresql, kafka, vault, http, redis); each value maps service names to the
            declaration lists the kind's view methods would declare — a redis declaration
            carries the ``action`` key (set, hset, rpush, or sadd) plus the fields of the
            matching view operation.

    Returns:
        The decorator applying the ``pybuggy_services`` marker with the presets to a test.

    Raises:
        ValueError: When a preset key is not a supported kind, a preset value is not the
            declared ``service name -> declaration list`` shape, a postgresql row value
            carries a malformed ``$ref`` / ``$lookup`` reference, or a redis declaration
            misses its ``action`` key or carries a field set or field type outside its
            action's grammar.
    """
    for kind, targets in presets.items():
        if kind not in _SUPPORTED_KINDS:
            raise ValueError(
                f"services preset kind '{kind}' is not one of the supported kinds ({', '.join(_SUPPORTED_KINDS)})"
            )

        _validate_targets(kind, targets)

    def _decorate(item: Any) -> Any:
        marked = pytest.mark.pybuggy_services(presets=presets)(item)
        return pytest.mark.usefixtures("sandbox")(marked)

    return _decorate


def _validate_targets(kind: str, targets: object) -> None:
    """Validate the declarations of one preset kind at decoration time.

    Every target value must be the ``service name -> declaration list`` shape; the
    kind-specific grammar checks — the postgresql row references, the redis action
    declarations — run per declaration with the ``services preset '<kind>.<name>'``
    naming.

    Args:
        kind: The supported preset kind the declarations belong to.
        targets: The kind's raw value — service name to declaration list.

    Raises:
        ValueError: A kind value is not the declared mapping shape, a target value is not
            a declaration list, or a declaration violates its kind's grammar.
    """
    if not isinstance(targets, dict):
        raise ValueError(f"services preset kind '{kind}' must map service names to declaration lists")

    for name, declarations in targets.items():
        if not isinstance(declarations, list) or not all(isinstance(d, dict) for d in declarations):
            raise ValueError(f"services preset '{kind}.{name}' must be a list of declaration mappings")

        if kind == "postgresql":
            for declaration in declarations:
                if "rows" in declaration:
                    validate_insert_rows(declaration["rows"], context=f"services preset '{kind}.{name}'")

        if kind == "redis":
            _validate_redis_declarations(name, declarations)


def _validate_redis_declarations(name: str, declarations: list[dict[str, object]]) -> None:
    """Validate the redis declarations of one preset target at decoration time.

    Every declaration must carry the ``action`` key (set, hset, rpush, or sadd) plus
    exactly the fields of the matching view operation — ``key`` with ``value``,
    ``values``, or ``members``. The grammar mirrors the loader's ``data.redis``
    validation; a malformed declaration fails here, at decoration time, naming the
    ``services preset 'redis.<name>'`` declaration instead of crashing the enqueue loop.

    Args:
        name: The redis service name the declarations target.
        declarations: The target's declaration list — a list of mappings (the decorator
            has already checked the shape).

    Raises:
        ValueError: A declaration misses its ``action`` key, carries a field set outside
            its action's grammar, or carries a mistyped field.
    """
    context = f"services preset 'redis.{name}'"

    for declaration in declarations:
        action = declaration.get("action")

        if action not in _REDIS_ACTIONS:
            raise ValueError(f"{context}: every declaration requires an 'action' key (set, hset, rpush, or sadd)")

        _validate_redis_declaration_fields(context, declaration, action)


def _validate_redis_declaration_fields(
    context: str,
    declaration: dict[str, object],
    action: str,
) -> None:
    """Validate one redis declaration against its action's field grammar.

    Args:
        context: The error scope naming the ``services preset 'redis.<name>'`` declaration.
        declaration: The declaration mapping.
        action: The declared action — one of ``_REDIS_ACTIONS``.

    Raises:
        ValueError: The declaration's key set differs from the action's fields or a field
            carries a value of the wrong type.
    """
    expected = {"action", *_REDIS_ACTIONS[action]}
    actual = set(declaration)

    if actual != expected:
        problems = []

        if expected - actual:
            problems.append(f"missing {', '.join(sorted(expected - actual))}")

        if actual - expected:
            problems.append(f"unexpected {', '.join(sorted(actual - expected))}")

        raise ValueError(
            f"{context}: a '{action}' declaration carries exactly "
            f"{', '.join(sorted(expected))}, got {' and '.join(problems)}"
        )

    key = declaration.get("key")

    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"{context}: every '{action}' declaration requires a non-empty string 'key'")

    field, field_type = _REDIS_FIELD_TYPES[action]

    if not isinstance(declaration.get(field), field_type):
        shape = "mapping" if field_type is dict else "list"

        raise ValueError(f"{context}: a '{action}' declaration requires a {shape} '{field}'")
