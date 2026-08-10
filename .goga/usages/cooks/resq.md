# resq — HTTP-клиент pybuggy (sync)

## Предметная область

`resq` — HTTP-клиент проекта, используется ячейкой `goga_tool_pybuggy/api` как транспорт под капотом
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
(пул соединений, cookies). Режим sync/async задаётся **по экземпляру** обязательным аргументом
`adapter` (не по глаголу):

```python
session = resq.Session("https://api.example.com", "requests", timeout=10.0)
```

- `Session(base_url: str, adapter: str, timeout: float | None = None)`.
- `adapter` — обязательный селектор режима, 2-й позиционный: `"requests"` = sync, `"httpx"` = async;
  неизвестное значение → `ValueError`. pybuggy использует строго `"requests"`.
- `timeout` — сетевой таймаут (3-й позиционный); `None` отключает.
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

### Жизненный цикл и close()

`Session` предоставляет **публичный** `close()` и sync context manager (`__enter__`/`__exit__`).
В sync-режиме (`adapter="requests"`) `close()` — **no-op по дизайну resq**: удерживаемый
`requests.Session` освобождается сборщиком мусора, а не закрывается явно (контракт resq:
«Do NOT close the requests.Session held by the `Session` flavor»). `Api.close()` делегирует
в этот публичный `session.close()`.

```python
session = resq.Session("https://api.example.com", "requests")
session.close()  # sync: no-op (пул requests.Session — на GC)

# либо sync context manager:
with resq.Session("https://api.example.com", "requests") as s:
    s.get("/path")
```

---

## AuthBase работает напрямую

Sync resq = `requests` под капотом, поэтому `requests.auth.AuthBase` (любой callable-объект
`(PreparedRequest) -> PreparedRequest`) подключается штатным аргументом `auth=` и применяется к
`PreparedRequest`. Это основа для `CombineAuth`/`AuthWrapper` в `goga_tool_pybuggy/api`.

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
