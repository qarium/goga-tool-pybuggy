# jinja2 — движок рендеринга base_url

## Предметная область

`jinja2` — используется для рендеринга `base_url` ячейки `pybuggy/plugin`. Шаблон `base_url` рендерится
через `jinja2.Environment(undefined=StrictUndefined)` с зарегистрированным кастомным тестом
`match_re`. Jinja-режим даёт потребителю условную логику и regex-проверку прямо в шаблоне URL —
без предварительного вычисления переменных в `conftest`.

Рендеринг выполняется в lifecycle-хуке `configure()` (один раз, pytest configphase), значение
сохраняется обратно в опцию `base_url`.

---

## Environment — конфигурация

pybuggy создаёт `jinja2.Environment` со следующими настройками:

- `undefined=jinja2.StrictUndefined` — неизвестная переменная **поднимает ошибку**
  (`UndefinedError`), а не рендерится в пустую строку. URL не должен молчаливо
  обрезаться.
- `keep_trailing_newline=False` — завершающий перенос (например, от YAML `>`
  folded-scalar) не попадает в URL.

Контекст рендеринга — обычный `dict`: полная `os.environ` + CLI-опции, которые
пользователь реально набрал. Переменные шаблона пишутся в Jinja-синтаксисе: `{{ name }}`.

После рендеринга движком (Jinja2) из результата **удаляются все пробельные символы**
(`re.sub(r"\s+", "", ...)`). URL по определению не содержит литеральных пробелов —
иначе они превратятся в `%20` и сломают путь запроса (классический баг с folded-scalar
`>`: перенос строки между сегментами URL и пустой Jinja-блок оставляли висячий пробел).
Поэтому многострочные шаблоны (YAML folded `>` / literal `|` скаляры, пустые Jinja-блоки)
рендерятся в один чистый URL. Plain URL без Jinja-плейсхолдеров рендерится сам в себя.

---

## Custom test `match_re` — regex в условиях

В Jinja2 нет встроенного regex-фильтра/теста. pybuggy регистрирует кастомный
**test** `match_re`, оборачивающий `re.match`:

```jinja
{% if service_version is match_re("^feature-.*$") %}-{{ service_version }}{% endif %}
```

- `x is match_re(pattern)` → `re.match(pattern, str(x)) is not None`.
- `re.match` анкорит паттерн в начале строки (явный `^` в паттерне избыточен, но
  допустим).

---

## Примеры

Переменная:

```yaml
# .goga/tools/pybuggy/config.yml
base_url: "http://{{ env }}.svc.example/api"
```

```bash
pytest --env=dev   # -> http://dev.svc.example/api
```

Условная сборка URL (суффикс `-{version}` только для feature-веток):

```yaml
base_url: "http://x/api/v1{% if service_version is match_re('^feature-.*$') %}-{{ service_version }}{% endif %}"
```

```bash
pytest --service-version=feature-123   # -> http://x/api/v1-feature-123
pytest --service-version=1.2.3         # -> http://x/api/v1
```

Многострочный шаблон (YAML folded-scalar `>` — переноды строк сворачиваются в пробелы,
которые нормализация удаляет; работает и в обеих ветках условия):

```yaml
base_url: >
  http://{{ env }}.svc.example/api/v1
  {% if some_version is match_re("^feature-.*$") %}-{{ some_version }}{% endif %}
```

```bash
pytest --env=stage-el --some-version=1.2.3        # -> http://stage-el.svc.example/api/v1
pytest --env=stage-el --some-version=feature-123   # -> http://stage-el.svc.example/api/v1-feature-123
```

CLI-плейсхолдеры (например `--env`, `--service-version`) потребитель регистрирует
сам через `pytest_addoption` в `conftest.py` — pytest отвергает незарегистрированные
опции ещё до хуков.

---

## Ограничения

- **Неизвестная переменная** → `UndefinedError` (`StrictUndefined`). URL не должен
  молчаливо обрезаться — используйте только переменные из `os.environ` или переданные
  через CLI.
- **Literal фигурные скобки** в URL не поддерживаются: одинарные `{`/`}` нейтральны для
  Jinja2 (выводятся как есть), но `{{ }}` всегда трактуется как переменная.
- **Пробелы в URL нормализуются**: `render_base_url` удаляет из результата все
  пробельные символы, поэтому YAML folded (`>`) / literal (`|`) многострочные скаляры
  и пустые Jinja-блоки не оставляют висячих пробелов в URL (явные `%20` в шаблоне
  сохраняются — это не whitespace).
- Рендеринг однократный и eager: выполняется в `configure()` (configphase), до любого
  теста или фикстуры.
