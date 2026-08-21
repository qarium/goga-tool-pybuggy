# click — the CLI facade (library)

## Domain

`click` is a library for building CLIs in Python. The project uses it for groups, subgroups, commands, options/arguments, and a uniform mapping of domain errors to a non-zero exit.

```python
import click
```

This practice covers only the `click` API. The respective cells' `.usages/` (composition root, commands) describe how the project assembles its CLI from these primitives.

---

## Groups and subgroups

A group (`@click.group`) is the root of the command tree. A subgroup is a separate group attached to its parent via `add_command`. Nested commands `parent child ...` are built this way:

```python
@click.group()
def parent():
    """Root group."""


@click.group("child", help="Child subgroup.")
def child_group():
    """Child subgroup."""


parent.add_command(child_group)
```

- The decorator argument sets the group name (`@click.group("child")`); without an argument, click takes the function name.
- The group's `help` appears in `--help`.

---

## Commands, options, arguments

A command (`@click.command`) is a leaf of the command tree. Options use `@click.option`; positional arguments use `@click.argument`. The decorated function's name becomes the command name unless set explicitly.

```python
@click.command("pull")
@click.option("--spec", "spec_name", default=None, help="Filter by spec name.")
def pull_cmd(spec_name):
    """Pull specs."""
    ...
```

- `@click.option("--flag", "dest", default=None, ...)` — an option; `dest` sets the callback parameter name.
- A boolean flag: `is_flag=True, default=False`.
- A short form: `@click.option("-s", "--spec", "spec_name", ...)`.
- `@click.argument("endpoint_id")` — a positional argument.

---

## Interactive prompts — confirm and prompt

`click.confirm` asks a yes/no question (a gate in front of a dangerous action); `click.prompt` asks for a value. Handlers use them for interactive gates and surveys:

```python
# Overwrite gate: the file exists — ask for explicit confirmation (default is refusal)
if not path.exists() or click.confirm(f"{path} exists — rebuild it?", default=False):
    build(path)

# Asking for a value: default="" accepts empty input (skipping an optional field)
name = click.prompt("spec name", default="", show_default=False).strip()

# A choice from a fixed set
spec_type = click.prompt("spec type", type=click.Choice(["swagger", "openapi"]))
```

- The `default` of `confirm` is the answer that Enter yields; `default=False` means "refuse by default" for overwrites and other dangerous actions.
- `prompt` returns the entered value; `type=click.Choice([...])` restricts the set of valid answers; `show_default=False` hides the default hint.
- A declined `confirm` is not an error: the handler skips the step and continues execution (exit 0).
- An interruption (Ctrl-C) raises `click.Abort` — the handler catches it and returns a non-zero exit without crashing the process.

---

## The handler is separated from the wrapper

The click decorator only binds options/arguments and calls a pure handler function. This lets tests exercise the logic by **calling the handler directly**, without `CliRunner`:

```python
def run_pull(spec_name):
    """Pure handler — callable directly from tests."""
    ...


@click.command("pull")
@click.option("--spec", "spec_name", default=None)
def pull_cmd(spec_name):
    run_pull(spec_name)
```

---

## Mapping domain errors — ClickException

Map domain errors (not found, invalid input, an external dependency refusing) to `click.ClickException`. Click prints the message and terminates the process with a non-zero exit — uniform behavior for all commands:

```python
if spec_name not in config.specs:
    raise click.ClickException(f"spec not found: {spec_name}")
```

---

## CLI testing

- Tests call handler functions by **direct call** (see `conventions`, CLI Testing section), without `CliRunner`.
- git/FS — via `mock.patch`/`tmp_path`; pure logic — without mocks.
