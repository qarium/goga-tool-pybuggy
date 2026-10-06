# wiremock — the sandbox http mock, driven over the admin API

## Domain

`wiremock` (image `wiremock/wiremock`) is the http dependency mock of the pybuggy sandbox
capability. The service under test calls it as an external integration; the sandbox manages stubs
over the HTTP admin API (`/__admin`) — with plain `requests` — for startup mappings, per-test
stubs, and reset. There is no python wrapper dependency: everything is HTTP.

---

## Stub mappings — `POST /__admin/mappings`

```python
requests.post(
    f"http://{host}:{port}/__admin/mappings",
    json={
        "name": "payment-provider-charge",
        "priority": 1,
        "request": {
            "method": "POST",
            "urlPath": "/v1/charge",
            "headers": {"X-Api-Key": {"equalTo": "secret"}},
        },
        "response": {
            "status": 200,
            "jsonBody": {"status": "captured", "amount": 100},
            "headers": {"Content-Type": "application/json"},
            "fixedDelayMilliseconds": 50,
        },
    },
    timeout=5,
)
```

- `request` matching: `urlPath` (exact path, query-agnostic), `urlPathPattern` (regex path),
  `url` / `urlPattern` (path + query), `method`, `headers` and `queryParameters` with matchers
  (`equalTo`, `matching` regex, `contains`, `absent`), `bodyPatterns` (`equalToJson`,
  `matchesJsonPath`).
- Matching is exhaustive by default — unmatched requests get a 404 with a near-miss report in the
  response body, which makes wiring mistakes visible in test failures.
- `priority` breaks multi-match ties (lower wins).
- Response failure simulation: `fixedDelayMilliseconds`, `fixedDelayMilliseconds` with chunked
  dribble, and `"fault": "CONNECTION_RESET_BY_PEER"` / `"EMPTY_RESPONSE"` — the levers for
  exercising the service's error paths.
- A mapping created over the API is runtime state: it lives until reset (or
  `DELETE /__admin/mappings/{id}`).

---

## Reset — the two endpoints and their semantics

| endpoint | effect |
|---|---|
| `POST /__admin/mappings/reset` | drops API-created mappings, restores the loaded/persisted mapping set |
| `POST /__admin/requests/reset` | clears the request journal only — stubs untouched |

The sandbox reset for an http instance is `mappings/reset` + replay of the baseline mappings (the
yaml startup mappings and the author's session baseline): reset returns the instance to an
effective empty state, replay re-establishes the declared baseline.

---

## Startup mappings and readiness

- Startup mappings from `.sandbox.yml` are applied the same way — a sequence of
  `POST /__admin/mappings` calls after the container is up, before the service under test starts.
- Readiness: poll any admin GET (`GET /__admin/mappings`, or `GET /__admin/health` on wiremock 3.x)
  with a deadline; the mock is ready when the admin endpoint answers.
- WireMock serves stub traffic and the admin API on the same port — one exposed port per instance.

---

## Out of the v1 boundary

- `GET /__admin/requests` (the request journal) supports read-back assertions on what the service
  sent — deliberately out of scope for v1 (assertions are response-only); it is the natural first
  candidate for the next iteration.
