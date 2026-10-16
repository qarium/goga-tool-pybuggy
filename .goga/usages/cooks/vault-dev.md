# vault dev mode — the sandbox secrets mock

## Domain

`hashicorp/vault` in **dev mode** is the secrets dependency mock of the pybuggy sandbox
capability. The instance under test reads secrets from this vault service; the sandbox puts
secrets over the KV v2 HTTP API with plain `requests` — no `hvac` client dependency.

---

## Dev server — flags and guarantees

```bash
docker run --rm -p 8200:8200 hashicorp/vault:1.17 \
  server -dev -dev-root-token-id=sandbox-root -dev-listen-address=0.0.0.0:8200
```

Equivalent env form (what the sandbox passes as container env): `VAULT_DEV_ROOT_TOKEN_ID`,
`VAULT_DEV_LISTEN_ADDRESS`.

Dev mode properties the sandbox relies on:

- **In-memory storage** — nothing persists; a container restart returns the vault service to a
  pristine state (the reset mechanism, followed by baseline replay).
- **Plain HTTP** — TLS is disabled; the API is `http://<host>:<port>/v1/...`.
- **Auto-initialized and auto-unsealed** — no operator steps; ready when the health endpoint says
  so.
- **Fixed dev root token** — the sandbox pins a known token via `VAULT_DEV_ROOT_TOKEN_ID`; it is a
  test-fixture credential, never a real secret.

## Authentication

Every request carries the token header:

```python
headers = {"X-Vault-Token": "sandbox-root"}
```

---

## KV v2 over HTTP

The dev server mounts `secret/` as KV **v2** by default. The v2 data path inserts `/data/`:

```python
# write a secret
requests.post(
    f"http://{host}:{port}/v1/secret/data/payment/api-key",
    headers=headers,
    json={"data": {"api_key": "test-key", "ttl": "1h"}},
    timeout=5,
)

# read a secret (response: {"data": {"data": {...}, "metadata": {...}}})
requests.get(f"http://{host}:{port}/v1/secret/data/payment/api-key", headers=headers, timeout=5)
```

| operation | call |
|---|---|
| write | `POST /v1/secret/data/<path>` body `{"data": {...}}` |
| read | `GET /v1/secret/data/<path>` |
| delete latest versions | `DELETE /v1/secret/data/<path>` |
| delete all versions + metadata | `DELETE /v1/secret/metadata/<path>` |
| list keys under a prefix | `LIST` (or GET with `?list=true`) `/v1/secret/metadata/<path>` |
| enable another KV v2 mount | `POST /v1/sys/mounts/<name>` body `{"type": "kv", "options": {"version": "2"}}` |

- Writes **create a new version** — they never overwrite in place; reset cannot rely on writes
  alone, which is why reset restarts the container instead of un-writing paths.
- Every operation answers with JSON; errors come as `{"errors": [...]}` with a 4xx status — map a
  failed put onto a readable failed-operation error for the author.

---

## Readiness and reset

- Readiness: poll `GET /v1/sys/health` — it returns `200` when the server is initialized, unsealed,
  and active.
- Reset: restart the container (in-memory storage wipes) + replay the baseline journal (the same
  `POST /v1/secret/data/...` path). The instance under test must tolerate the vault service
  reappearing — the accepted trade-off of the reset strategy.
