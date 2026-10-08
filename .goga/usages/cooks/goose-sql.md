# goose SQL — the migration file format consumed by the sandbox runner

## Domain

The sandbox applies DB migrations from goose-compatible SQL files. goose itself (the Go tool) is
**not** a dependency — the sandbox ships a built-in up-only runner that parses the subset of the
goose SQL annotation format described here. The subset is deliberately narrow: real migration
sets already live as goose-generated files, and the runner consumes them as produced.

Target audience: the runner implementation (parsing, validation) and service test authors whose
migration folders the sandbox declares.

---

## File naming and ordering

- One migration per file: `<version>_<description>.sql`, e.g. `00003_create_orders.sql`.
- The version is the leading prefix before the first underscore — digits only, compared
  numerically. This covers both goose numbering styles: sequential (`00003`) and timestamp
  (`20230102103456`).
- Files apply exactly once per session, in ascending version order.
- Duplicate version prefixes inside one migrations folder are invalid — rejected at validation,
  before any container starts.
- Non-`.sql` files are ignored.

## Annotations — the supported subset

goose directives are SQL comments that start a line: `-- +goose <Name>`. The runner supports
exactly this subset:

| annotation | meaning |
|---|---|
| `-- +goose Up` | opens the Up section — the only section that executes |
| `-- +goose Down` | opens the Down section — parsed, never executed |
| `-- +goose StatementBegin` | starts a statement body whose interior may contain semicolons |
| `-- +goose StatementEnd` | ends that statement body |
| `-- +goose NO TRANSACTION` | the file runs without a wrapping transaction |

- **Up/Down split.** The canonical goose layout: everything after `-- +goose Up` until
  `-- +goose Down` (or end of file) is the Up section; the rest of the file after
  `-- +goose Down` is skipped. A file without an Up section is invalid — there is nothing to
  apply.
- **Statement bodies.** Between `StatementBegin` and `StatementEnd` the text is one statement —
  semicolons inside (function bodies, `DO` blocks, `$$`-quoted code) do not split it. Outside
  such blocks, statements split on the terminating semicolon.
- **NO TRANSACTION.** Placed before the Up section, as goose produces it. When present, the
  file's statements execute one by one in autocommit — required by DDL such as
  `CREATE INDEX CONCURRENTLY`. Without it, the default applies: one transaction per file,
  all or nothing.

```sql
-- +goose NO TRANSACTION
-- +goose Up
-- +goose StatementBegin
CREATE OR REPLACE FUNCTION audit_orders() RETURNS trigger AS $$
BEGIN
  INSERT INTO audit_log (order_id) VALUES (NEW.id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd
CREATE INDEX CONCURRENTLY idx_orders_customer ON orders (customer);

-- +goose Down
DROP INDEX idx_orders_customer;
DROP FUNCTION audit_orders;
```

## Outside the subset — unsupported

- Any `+goose` annotation beyond the five above, Go-based migrations, `{{...}}` variable
  interpolation, and every other goose behavior not described here.
- The runner fails with the file named rather than silently misapplying — a migration leaning
  on unsupported goose behavior surfaces as an actionable error, not as a wrong schema.

## How the runner consumes a set

- Up-only: `Down` sections never execute — not at startup, not on any reset or teardown.
- The set applies once per session, after the postgres container is ready and before the
  service under test starts; see `psycopg` for the execution patterns.
- Applied migrations are not journaled into the baseline — the schema is session-static, unlike
  `data.postgres` seed rows that replay after every reset.
