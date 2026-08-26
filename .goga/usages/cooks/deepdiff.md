# deepdiff — structural comparison of nested data (library)

## Domain

`deepdiff` is a library for deep comparison of nested Python structures (dicts, lists, sets, objects). The project uses it to compare an endpoint contract extracted from a spec with previously generated JSON artifacts (`meta.json`, response `schemas/*.json`).

```python
from deepdiff import DeepDiff
```

This practice covers only the `deepdiff` API. The respective cells' `.usages/` describe how the project's commands assemble comparison flows from these primitives.

---

## Basic comparison

```python
diff = DeepDiff(generated_side, spec_side)
if diff:
    print(diff.to_json())
```

- `DeepDiff(t1, t2)` returns a diff object; it is **falsy when the structures are equal** — use `if diff:` to detect drift.
- `t1` is the old/left side (generated artifacts), `t2` is the new/right side (current spec); `dictionary_item_added` / `dictionary_item_removed` are reported relative to this order.
- The diff object is not a plain dict — convert explicitly via `to_dict()` or `to_json()` before printing or serializing.

---

## JSON output

```python
diff.to_json()   # JSON string — machine-readable, ready to print
diff.to_dict()   # plain dict — for programmatic inspection
```

- `to_json()` is the canonical console output: one JSON document per compared unit.
- An empty diff serializes to `{}`.

---

## Change categories

- `values_changed` — a leaf value differs; each entry carries `old_value` and `new_value`.
- `type_changes` — the type of a node differs (e.g. `str` vs `int`), with `old_type` / `new_type`.
- `dictionary_item_added` / `dictionary_item_removed` — keys present in only one side.
- `iterable_item_added` / `iterable_item_removed` — list items present in only one side.
- `iterable_item_moved` — list order changed (with `verbose=True`).
- `unprocessed` — values deepdiff could not compare; treat as drift, not as equality.

---

## Options

```python
DeepDiff(t1, t2, ignore_order=False, exclude_paths=["root['meta']"])
```

- `ignore_order=False` (default) — the order of list items matters; keep the default for contract comparison (`required` lists, status-code sequences are order-sensitive).
- `report_repetition` — detects repeated list items; off by default.
- `exclude_paths` — pointwise exclusions (`root['x']` paths) when a node must not participate in the comparison.
- Do not enable `ignore_order`, `ignore_type_in_groups`, or similar relaxations unless the task explicitly requires them — a relaxed comparison can silently hide drift.

---

## Working with JSON loaded from disk

```python
import json

meta = json.loads(meta_path.read_text(encoding="utf-8"))
spec_side = json.loads(json.dumps(contract, ensure_ascii=False, default=_json_default))
diff = DeepDiff(meta, spec_side)
```

- Artifacts (`meta.json`, `schemas/*.json`) are read with `json.loads` into plain dicts/lists — directly comparable, no pre-processing.
- The spec side is normalized to JSON-native via a round-trip, not `model_dump()` — pydantic does not coerce `dict[str, Any]` payloads, so a dumped model still carries `datetime.date` objects. `_json_default` renders date/datetime as ISO 8601 (`isinstance(obj, date)` covers datetime); anything else re-raises `TypeError`.
- YAML-parsed specs may carry non-JSON-native values (e.g. `datetime.date` from `format: date` examples); normalize them to strings before comparing, or the diff reports `type_changes` noise.

---

## Testing

- Pure comparison logic — tests without mocks: build both sides as plain dicts and assert on `to_dict()` categories.
- File I/O — via the `tmp_path` fixture; command handlers are called directly (see `conventions`, CLI Testing section).
