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

## Тестирование

- Файл I/O — через `tmp_path`; исходный YAML готовь фикстурой.
- Проверяй round-trip: load→dump без правок даёт идентичный текст (комментарии/кавычки на месте).
- Проверяй идемпотентность: второй запуск с теми же ключами не меняет файл.
