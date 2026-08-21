# requests

An HTTP library for Python. matchcrest uses it directly (not through resq) in two places.

## Status codes — requests.codes

`requests.codes` is a registry of HTTP code names; access by name returns the numeric code.

```python
import requests

requests.codes["ok"]          # 200
requests.codes["not_found"]   # 404
```

`matchcrest.matchers.response.ResponseCodeMatcher` uses this registry — the matcher accepts a code name as a string and resolves it to a number via `requests.codes[name]`.

## Issuing a request — requests.get

```python
import requests

response = requests.get(url)
response.status_code   # int
```

`matchcrest.utils.utils.url_is_live` uses this call — a liveness probe over GET; 2xx counts as "alive".
