# psycopg — the SQL driver of the sandbox postgres instance

## Domain

`psycopg` (version 3) is the postgres driver of the pybuggy sandbox capability. It executes the
data operations against the real postgres container: row inserts for preconditions, the catalog
query that discovers tables for reset, `TRUNCATE` reset, and baseline-journal replay.

Import in code:
```python
import psycopg
```

---

## Connect

The sandbox connects with the host/port/credentials taken from the started postgres container:

```python
conn = psycopg.connect(
    host=host, port=port, user=user, password=password, dbname=dbname,
    autocommit=True,
)
```

- `autocommit=True` commits every statement immediately — the right mode for the sandbox: data
  operations are individual idempotent statements, not interactive transactions.
- **Gotcha:** `with psycopg.connect(...) as conn:` is a *transaction* scope, not a connection
  scope — on exit it commits or rolls back but does **not** close the connection. Close explicitly
  (`conn.close()` in the teardown) or wrap with `contextlib.closing`.
- Keep one connection per postgres instance for the session; reopen (or reconnect) rather than
  pooling — the volumes are tiny and the lifecycle is session-scoped.

---

## Execute — inserts and replay

Row inserts apply one row per statement with `RETURNING` — every applied row is captured for
`$ref` addressing:

```python
from psycopg.rows import dict_row

with conn.transaction():  # explicit block — all-or-nothing per operation
    with conn.cursor(row_factory=dict_row) as cur:  # dict rows — column-name addressing
        cur.execute(
            'INSERT INTO "orders" (customer, total) VALUES (%s, %s) RETURNING *',
            (customer, total),
        )
        applied = cur.fetchone()  # the applied row with generated values (serial ids included)
```

- Placeholders: `%s` positional or `%(name)s` named. Parameters are bound server-side — never
  format SQL with f-strings/`%` formatting.
- `conn.transaction()` works on `autocommit` connections: it opens an explicit transaction for
  the block and commits or rolls back on exit — the per-operation atomicity seam.
- Row-per-statement instead of `executemany`: `executemany` returns no results, while the
  sandbox needs each row's applied values (later rows may reference earlier ones).
- `row_factory=dict_row` is per-cursor — the catalog queries keep the default tuple rows.
- Results: `cur.fetchall()` / `cur.fetchone()` for `SELECT` (catalog query, reference lookups,
  verification during development).
- JSON columns (`jsonb`): wrap python dicts with `psycopg.types.json.Json(payload)`.

Every applied operation that raises must surface as a readable error identifying the failed
operation (the requirement applies at the sandbox layer; psycopg provides the cause):
psycopg exceptions live in `psycopg.errors` (`UndefinedTable`, `UniqueViolation`, …) and carry
`.diag.message_primary` with the server-side message.

---

## Reference resolution — $ref and $lookup

`$ref` reads the engine's captured applied rows (no SQL); `$lookup` runs one parameterized match
query against the current database state:

```python
cur.execute('SELECT "id" FROM "customers" WHERE "email" = %s LIMIT 2', ("ann@x.io",))
matches = cur.fetchall()
# exactly one match resolves; zero matches = missing precondition, two = ambiguous predicate
```

- `LIMIT 2` is the match counter: one row resolves, two rows prove ambiguity — never fetch more.
- The default resolved column is the table's primary key, discovered through
  `information_schema.table_constraints` joined with `information_schema.key_column_usage`
  (`constraint_type = 'PRIMARY KEY'`, `table_name = %s`); an explicit column skips the discovery.
- A lookup sees rows created by anyone — the data plane, the service, migrations — because it
  reads the live database state at apply time.

---

## Catalog discovery — which tables to reset

Reset must not reference tables by hand. Discover the user tables from the catalog:

```python
with conn.cursor() as cur:
    cur.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        """
    )
    tables = cur.fetchall()
```

- The exclusion list covers the system schemas; every other base table belongs to the service's
  data and participates in reset.
- Run discovery at reset time (not once at start): migrations or DDL executed by the service
  mid-session change the table set.

---

## Reset — TRUNCATE with identity restart

```python
targets = ", ".join(f'"{schema}"."{name}"' for schema, name in tables)
with conn.cursor() as cur:
    cur.execute(f"TRUNCATE TABLE {targets} RESTART IDENTITY CASCADE")
```

- One statement over all discovered tables: `CASCADE` handles FK ordering, `RESTART IDENTITY`
  resets sequences — the state returns to "empty schema".
- Table names come from the catalog and are quoted; no user input reaches this statement except
  through the catalog query.
- After `TRUNCATE`, the sandbox replays the baseline journal (the same execute path as inserts) —
  reset + replay together restore the author-declared baseline.
