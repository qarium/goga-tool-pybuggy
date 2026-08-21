# jinja2 — the base_url rendering engine

## Domain

`jinja2` renders the `base_url` of cell `goga_tool_pybuggy/plugin`. The plugin renders the `base_url` template through `jinja2.Environment(undefined=StrictUndefined)` with a registered custom test `match_re`. The Jinja mode gives the consumer conditional logic and regex checks directly in the URL template — with no precomputation of variables in `conftest`.

The render runs in the `configure()` lifecycle hook (once, during the pytest configphase); the plugin stores the resulting value back into the `base_url` option.

---

## Environment — configuration

pybuggy creates a `jinja2.Environment` with the following settings:

- `undefined=jinja2.StrictUndefined` — an unknown variable **raises an error** (`UndefinedError`) instead of rendering to an empty string. A URL must never be silently truncated.
- `keep_trailing_newline=False` — a trailing newline (e.g. from a YAML `>` folded scalar) never reaches the URL.

The rendering context is a plain `dict`: the full `os.environ` plus the CLI options the user actually typed. Template variables use Jinja syntax: `{{ name }}`.

After the engine renders the template, **all whitespace characters are stripped** from the result (`re.sub(r"\s+", "", ...)`). A URL by definition contains no literal spaces — otherwise the spaces would become `%20` and break the request path (the classic bug with the folded scalar `>`: a line break between URL segments plus an empty Jinja block left a dangling space). Consequently, multi-line templates (YAML folded `>` / literal `|` scalars, empty Jinja blocks) render into a single clean URL. A plain URL without Jinja placeholders renders to itself.

---

## The custom test `match_re` — regex in conditions

Jinja2 ships no built-in regex filter/test. pybuggy registers a custom **test**, `match_re`, wrapping `re.match`:

```jinja
{% if service_version is match_re("^feature-.*$") %}-{{ service_version }}{% endif %}
```

- `x is match_re(pattern)` → `re.match(pattern, str(x)) is not None`.
- `re.match` anchors the pattern at the start of the string (an explicit `^` in the pattern is redundant but allowed).

---

## Examples

A variable:

```yaml
# .goga/tools/pybuggy/config.yml
base_url: "http://{{ env }}.svc.example/api"
```

```bash
pytest --env=dev   # -> http://dev.svc.example/api
```

Conditional URL assembly (the `-{version}` suffix appears only for feature branches):

```yaml
base_url: "http://x/api/v1{% if service_version is match_re('^feature-.*$') %}-{{ service_version }}{% endif %}"
```

```bash
pytest --service-version=feature-123   # -> http://x/api/v1-feature-123
pytest --service-version=1.2.3         # -> http://x/api/v1
```

A multi-line template (YAML folded scalar `>` — line breaks fold into spaces, which normalization removes; works in both branches of the condition):

```yaml
base_url: >
  http://{{ env }}.svc.example/api/v1
  {% if some_version is match_re("^feature-.*$") %}-{{ some_version }}{% endif %}
```

```bash
pytest --env=stage-el --some-version=1.2.3        # -> http://stage-el.svc.example/api/v1
pytest --env=stage-el --some-version=feature-123   # -> http://stage-el.svc.example/api/v1-feature-123
```

The consumer registers CLI placeholders (e.g. `--env`, `--service-version`) itself via `pytest_addoption` in `conftest.py` — pytest rejects unregistered options before any hook runs.

---

## Limitations

- **An unknown variable** → `UndefinedError` (`StrictUndefined`). A URL must never be silently truncated — use only variables from `os.environ` or variables passed via CLI.
- **Literal curly braces** in a URL are unsupported: single `{`/`}` are neutral for Jinja2 (emitted as is), but `{{ }}` is always treated as a variable.
- **Spaces in a URL are normalized**: `render_base_url` strips all whitespace from the result, so YAML folded (`>`) / literal (`|`) multi-line scalars and empty Jinja blocks leave no dangling spaces in the URL (an explicit `%20` in the template survives — it is not whitespace).
- The render is single-shot and eager: it happens in `configure()` (configphase), before any test or fixture.
