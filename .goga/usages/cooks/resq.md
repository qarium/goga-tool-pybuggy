# resq — HTTP-клиент pybuggy (sync)

## Предметная область

`resq` — HTTP-клиент проекта, используется ячейкой `pybuggy/api` как транспорт под капотом
`Api`. Sync-направление resq построено поверх `requests` (держит `requests.Session`), поэтому
аутентификация `requests.auth.AuthBase` применяется напрямую — без адаптеров.

Импорт в коде:
```python
import resq
from resq import Session          # фасад реэкспортит Session
from resq.http import Response    # тип ответа для аннотаций
```

---

## Session — клиент с base_url

`Session` — «persistent»-флавор: один `requests.Session`, переиспользуемый между sync-вызовами
(пул соединений, cookies). Конструктор принимает только `base_url` и сетевой `timeout`:

```python
session = resq.Session("https://api.example.com", timeout=10.0)
```

- `Session(base_url: str, timeout: float | None = None)`.
- `base_url` доступен как свойство `session.base_url` (строка; resq хранит её как есть).
- resq сам склеивает `base_url` + `path` (нормализует base до закрывающего `/` через `urljoin`).

Глаголы — по одному на HTTP-метод:
```python
session.get(path, **kwargs)
session.post(path, **kwargs)
session.put(path, **kwargs)
session.delete(path, **kwargs)
session.patch(path, **kwargs)
session.head(path, **kwargs)
session.options(path, **kwargs)
```

Каждый глагол: `(path, timeout=None, delay=1.0, **kwargs)`. `timeout`/`delay` относятся к
polling-окну resq — для одиночного запроса pybuggy их в глагол **не пробрасывает**; `**kwargs`
уходит в `requests.Session.request` (params, json, headers, cookies, auth, …).

Глагол выбирается динамически: `getattr(session, method.lower())`.

---

## AuthBase работает напрямую

Sync resq = `requests` под капотом, поэтому `requests.auth.AuthBase` (любой callable-объект
`(PreparedRequest) -> PreparedRequest`) подключается штатным аргументом `auth=` и применяется к
`PreparedRequest`. Это основа для `CombineAuth`/`AuthWrapper` в `pybuggy/api`.

```python
from requests.auth import AuthBase

class TokenAuth(AuthBase):
    def __call__(self, r):
        r.headers["Authorization"] = "Bearer x"
        return r
```

---

## Response — поверхность ответа

`resq.http.Response` (sync) проксирует **явные** свойства/методы — без `__getattr__`:

- свойства: `status_code`, `text`, `content`, `headers`, `url`, `encoding`, `ok`.
- методы: `json()`, `raise_for_status()`, `reload()` (повторный запрос).

У `resq.http.Response` **нет** свойства `.request` (`PreparedRequest`) — не использовать.
Обёртка `ResponseWrapper` в pybuggy **не проксирует** атрибуты `resq.http.Response`: доступ
к сырому ответу — только через свойство `.response` (например, `wrapper.response.status_code`).

---

## Что pybuggy НЕ использует

- polling: `resq.poll`/`resq.apoll` и окно `timeout`/`delay` — одиночный запрос их не пробрасывает.
- async-направление (`AsyncResponse`, `apoll`).
- `Requests` (one-shot sync-клиент) — pybuggy работает через `Session`.
