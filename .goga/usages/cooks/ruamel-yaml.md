# ruamel.yaml — round-trip YAML (библиотека)

## Предметная область

`ruamel.yaml` — YAML в режиме round-trip: сохраняет комментарии, порядок ключей, кавычки и
block-scalars при load→modify→dump. Используется, когда нужно точечно дописать пользовательский
YAML, не переформатируя его (pyyaml для этого непригоден — сбрасывает кавычки и удаляет комментарии).

```python
from ruamel.yaml import YAML
```

Эта практика описывает только round-trip API `ruamel.yaml`. Парсинг собственных конфигов проекта
через pyyaml — в клеточных `.usages/`.

---

## Round-trip: load → изменить → dump

```python
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True          # сохранять стиль кавычек исходного файла

data = yaml.load(path)               # Path | file-like; CommentedMap, либо None для пустого файла
usages = data["codemanifest"]["usages"]
usages["pybuggy-api"] = ".goga/usages/cooks/pybuggy/api.md"

yaml.dump(data, path)
```

- `yaml.load` пустого файла/None → `None`; проверяй перед доступом.
- `preserve_quotes=True` — сохранять кавычки значений.
- Порядок ключей, комментарии и block-scalars (`|`, `>`) сохраняются по умолчанию.

---

## Идемпотентное дополнение (не затирать существующие ключи)

```python
for key, value in new_usages.items():
    if key not in usages:
        usages[key] = value
```

Существующие ключи (включая пользовательские) не трогаются — повторный запуск не даёт diff.

---

## Создать файл с нуля

Если файла нет — собери структуру из `CommentedMap` (не из `{}`) и dump:

```python
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

yaml = YAML()
usages = CommentedMap()
usages["pybuggy-api"] = ".goga/usages/cooks/pybuggy/api.md"
data = CommentedMap()
codemanifest = CommentedMap()
codemanifest["usages"] = usages
data["codemanifest"] = codemanifest

path.parent.mkdir(parents=True, exist_ok=True)
yaml.dump(data, path)
```

---

## Эмиссия закомментированных записей (создание с нуля)

Когда конфиг собирается из ответов, часть полей — пропущенные необязательные скаляры и сложные секции (`headers`-dict,
`loader`-section, `git`-block) — нужно записать **закомментированными** примерами (`# key:`), а не активными ключами.
Round-trip API `ruamel.yaml` умеет это через комментарии, привязанные к следующему активному ключу: комментарий НЕ
становится ключом (при round-trip `load` он отсутствует в `keys()`).

```python
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

yaml = YAML()
yaml.preserve_quotes = True

doc = CommentedMap()
# только АКТИВНЫЕ ключи; пропущенные поля как ключи НЕ добавляем
doc["base_url"] = "https://{{ host }}/api"
doc["data_key"] = "data"

# (1) однострочная закомментированная запись ПЕРЕД следующим активным ключом:
doc.yaml_set_comment_before_after_key("data_key", before="timeout: (skipped optional scalar)")
#     ->  "# timeout: (skipped optional scalar)" строкой выше data_key

# (2) многострочный закомментированный блок (сложная секция) — "\n"-joined текст, каждая строка получает префикс "# ":
doc.yaml_set_comment_before_after_key(
    "specs",
    before="headers: example (skipped complex member)\nX-Example: value\ndefault headers dict",
)
#     ->  "# headers: example (skipped complex member)"
#         "# X-Example: value"
#         "# default headers dict"  строками выше specs

doc["specs"] = CommentedMap()  # обязательная непустая секция — якорь для предшествующих комментариев

# (3) trailing-комментарий к значению активного ключа:
doc.yaml_add_eol_comment("required, Jinja2 template", "base_url")
#     ->  "base_url: https://{{ host }}/api  # required, Jinja2 template"

yaml.dump(doc, path)
```

- `yaml_set_comment_before_after_key(key, before=...)` — строки `# ...` **перед** ключом `key`; `before` — одна строка
  (однострочный комментарий) либо `\n`-joined текст (многострочный блок, каждая строка получает префикс `# `).
- `yaml_add_eol_comment(text, key)` — trailing-комментарий `# text` в конце строки значения ключа `key`.
- Порядок детерминирован: `CommentedMap` сохраняет порядок вставки активных ключей; комментарий привязывается к
  следующему за ним активному ключу.
- Комментарий не становится ключом: round-trip `yaml.load` вернёт только активные ключи (закомментированные записи
  отсутствуют в `keys()`), т.е. они игнорируются валидатором схемы (extra=ignore).
- Ограничение: comment-before крепится к **следующему** активному ключу — после последней закомментированной записи
  обязан быть активный ключ (например, обязательная непустая секция `specs`), иначе комментарий не выведется.

---

## Тестирование

- Файл I/O — через `tmp_path`; исходный YAML готовь фикстурой.
- Проверяй round-trip: load→dump без правок даёт идентичный текст (комментарии/кавычки на месте).
- Проверяй идемпотентность: второй запуск с теми же ключами не меняет файл.
