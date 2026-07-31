# requests

Библиотека HTTP для Python. matchcrest использует её напрямую (не через resq) в двух местах.

## Коды статусов — requests.codes

`requests.codes` — реестр имён HTTP-кодов; доступ по имени возвращает числовой код.

```python
import requests

requests.codes["ok"]          # 200
requests.codes["not_found"]   # 404
```

Используется в `matchcrest.matchers.response.ResponseCodeMatcher` — принимает имя кода
строкой и резолвит его в число через `requests.codes[name]`.

## Выполнение запроса — requests.get

```python
import requests

response = requests.get(url)
response.status_code   # int
```

Используется в `matchcrest.utils.utils.url_is_live` — liveness-проба GET'ом; 2xx = «жив».