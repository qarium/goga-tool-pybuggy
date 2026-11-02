---
name: goga-tool-pybuggy-web-automate-cells-context
description: Base context loading for web test cells — base Usages/Annotations block (conventions + pybuggy-web) via goga-codemanifest-base, with key resolution checks, plus the pybuggy-web runtime reference and language rules
---

# Pybuggy Web Topic Cells — Context

## Identity

Ты загружаешь базовый контекст проектирования веб-тест-ячеек: базовый блок Header (одинаковый для всех
ячеек топика) и правила, по которым строятся CODEMANIFEST.

## Core Principle

Базовый блок — константа топика: он приходит из конфига проекта и не меняется от ячейки к ячейке.
Cell-specific usages лягут поверх него на фазе contracts — но только существующими файлами.

---

## Algorithm

### Step 1. Load the base block

1. Загрузи базовые usages/annotations через **Skill tool** `goga-codemanifest-base` (читает
   `codemanifest.usages` / `codemanifest.annotations` из `.goga/config.yml`).
2. Зафиксируй базовый блок веб-ячейки: `Usages` (включая `conventions` и `pybuggy-web` с путями) +
   базовые `Annotations` — **дословно**.
3. Загрузи веб-референс через **Skill tool** `goga-tool-pybuggy-web-usage` и правила языка через
   `goga-cell-python`.

### Step 2. Resolve the keys

1. Для каждого ключа базового `Usages` проверь, что файл по пути существует и не пуст
   (`pybuggy-web` → `.goga/usages/cooks/pybuggy/pybuggy-web.md`).
2. Для каждого ключа из [TOOLS_REPORT] (созданные usage-файлы) проверь существование
   `.goga/usages/cooks/<key>.md` — они кандидаты на cell-specific usages.
3. Нерезолвящийся базовый ключ — **STOP** (запуск `goga tool pybuggy init` kind web/both).

### Step 3. Produce the [CELLS_CONTEXT]

STOP if:

- `codemanifest`/базовые usages отсутствуют в конфиге (`goga-codemanifest-base` ничего не вернул);
- ключ `pybuggy-web` не резолвится (файла нет).

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [CELLS_CONTEXT]

## Base Header Block

    Usages:
      conventions: .goga/usages/conventions.md
      pybuggy-web: .goga/usages/cooks/pybuggy/pybuggy-web.md
    Annotations: |
      [дословно из .goga/config.yml]

[Базовый блок идентичен для всех веб-ячеек топика; cell-specific usages лягут поверх — только
существующими файлами.]

## Key Resolution

| key | path | статус |
|-----|------|--------|
| pybuggy-web | .goga/usages/cooks/pybuggy/pybuggy-web.md | резолвится |
| `<key из TOOLS_REPORT>` | .goga/usages/cooks/<key>.md | резолвится / отсутствует |

## Runtime Reference

[Ключевые факты фикстуры `web` из референса: шаги-предложения (один шаг = одно действие), полные URL,
кеш рядом с тестом, секреты запрещены, первый прогон без --strict-mode]

## Language Rules

[Ключевые правила goga-cell-python: snake_case, location: test_<name>.py, параметризация по линейности]
```
