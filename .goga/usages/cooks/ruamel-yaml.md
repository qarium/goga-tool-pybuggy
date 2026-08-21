# ruamel.yaml — round-trip YAML (library)

## Domain

`ruamel.yaml` handles YAML in round-trip mode: it preserves comments, key order, quotes, and block-scalars across load→modify→dump. Use it when a user's YAML must be amended point-wise without reformatting (pyyaml is unfit for this — it drops quotes and deletes comments).

```python
from ruamel.yaml import YAML
```

This practice covers only the round-trip API of `ruamel.yaml`. The cells' `.usages/` describe how the project parses its own configs with pyyaml.

---

## Round-trip: load → modify → dump

```python
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True          # keep the source file's quote style

data = yaml.load(path)               # Path | file-like; CommentedMap, or None for an empty file
usages = data["codemanifest"]["usages"]
usages["pybuggy-api"] = ".goga/usages/cooks/pybuggy/api.md"

yaml.dump(data, path)
```

- `yaml.load` of an empty file/None → `None`; check before access.
- `preserve_quotes=True` — keep the quotes of values.
- Key order, comments, and block-scalars (`|`, `>`) are preserved by default.

---

## Idempotent amendment (never overwrite existing keys)

```python
for key, value in new_usages.items():
    if key not in usages:
        usages[key] = value
```

Existing keys (including user-defined ones) stay untouched — a repeated run produces no diff.

---

## Create a file from scratch

When the file does not exist, build the structure from `CommentedMap` (not from `{}`) and dump:

```python
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

yaml = YAML()
usages = CommentedMap()
usages["pybuggy-api"] = ".goga/usages/cooks/pybuggy/api.md"
data = CommentedMap()
codemanifest = CommentedMap()
codemanifest["usages"] = usages
data["codemanifest"] = codemanifest

path.parent.mkdir(parents=True, exist_ok=True)
yaml.dump(data, path)
```

---

## Emitting commented-out entries (creation from scratch)

When the config is assembled from answers, some fields — skipped optional scalars and complex sections (`headers` dict, `loader` section, `git` block) — must be written as **commented-out** examples (`# key:`), not as active keys. The `ruamel.yaml` round-trip API achieves this through comments attached to the next active key: a comment never becomes a key (round-trip `load` omits it from `keys()`).

```python
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

yaml = YAML()
yaml.preserve_quotes = True

doc = CommentedMap()
# ACTIVE keys only; never add skipped fields as keys
doc["base_url"] = "https://{{ host }}/api"
doc["data_key"] = "data"

# (1) a one-line commented-out entry BEFORE the next active key:
doc.yaml_set_comment_before_after_key("data_key", before="timeout: (skipped optional scalar)")
#     ->  "# timeout: (skipped optional scalar)" on the line above data_key

# (2) a multi-line commented block (a complex section) — "\n"-joined text; every line gets the "# " prefix:
doc.yaml_set_comment_before_after_key(
    "specs",
    before="headers: example (skipped complex member)\nX-Example: value\ndefault headers dict",
)
#     ->  "# headers: example (skipped complex member)"
#         "# X-Example: value"
#         "# default headers dict"  on the lines above specs

doc["specs"] = CommentedMap()  # the mandatory non-empty section — the anchor for the preceding comments

# (3) a trailing comment on an active key's value:
doc.yaml_add_eol_comment("required, Jinja2 template", "base_url")
#     ->  "base_url: https://{{ host }}/api  # required, Jinja2 template"

yaml.dump(doc, path)
```

- `yaml_set_comment_before_after_key(key, before=...)` — `# ...` lines **before** the key `key`; `before` is a single line (a one-line comment) or `\n`-joined text (a multi-line block; every line gets the `# ` prefix).
- `yaml_add_eol_comment(text, key)` — a trailing `# text` comment at the end of the value line of the key `key`.
- Ordering is deterministic: `CommentedMap` preserves the insertion order of active keys; the comment attaches to the active key that follows it.
- A comment never becomes a key: round-trip `yaml.load` returns only the active keys (commented-out entries are absent from `keys()`), so the schema validator ignores them (extra=ignore).
- Limitation: a comment-before attaches to the **next** active key — an active key must follow the last commented-out entry (e.g. the mandatory non-empty `specs` section), otherwise the comment is not emitted.

---

## Testing

- File I/O — via `tmp_path`; prepare the source YAML with a fixture.
- Verify the round-trip: load→dump without edits yields identical text (comments/quotes intact).
- Verify idempotency: a second run with the same keys leaves the file unchanged.
