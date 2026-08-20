# goga_tool_pybuggy.config — чтение конфигурации

## Предметная область

Шаблоны потребления cell `goga_tool_pybuggy/config`: загрузка `.goga/tools/pybuggy/config.yml` в типизированные модели и доступ к spec-записям. Аудитория — команды-потребители и CLI-фасад.

## Загрузка конфигурации

```python
from goga_tool_pybuggy.config import load_config

config = load_config(path)  # path — от корня проекта; None → фиксированный путь .goga/tools/pybuggy/config.yml
```

`load_config` читает YAML (`yaml.safe_load`) и валидирует в `Config`. Невалидный конфиг падает с ошибкой валидации pydantic.

## Доступ к spec-записям

```python
for name, entry in config.specs.items():
    location = entry.location  # путь от корня проекта до файла спеки
    git = entry.git  # Optional[GitEntry]; None → spec локальная
    if git is not None:
        clone_url = git.url  # clone URL (без встроенных токенов)
        repo_path = git.location  # путь внутри репозитория
        repo_ref = git.ref  # Optional[str]; ветка/тег для клонирования; None → default branch
```

- `name` (ключ dict) используется потребителями в выводе и в фильтре `--spec`.
- `entry.git` может быть `None` — такая spec считается локальной; потребитель пропускает её с WARNING.
- `git.ref` — значение по умолчанию для клонирования; потребитель может переопределить его опцией `--ref` (приоритет `--ref` > `git.ref` > default branch).

## Предусловия

- Путь к конфигу — от корня проекта (cwd); значение по умолчанию `.goga/tools/pybuggy/config.yml`.
- Поле `type` декларативное — не влияет на разбор (Prance авто-детектит версию).
