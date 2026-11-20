---
name: goga-tool-pybuggy-web-automate-testcases-intake
description: Input validation and context load — checks requirements.md, prints it verbatim, loads the goga context (goga-cell DSL, python rules, web cookbook, runtime reference) and the base Header block via goga-codemanifest-base with key resolution
---

# Pybuggy Web Topic Testcases — Intake

## Identity

Ты отвечаешь за загрузку входных данных: валидируешь артефакт требований, загружаешь его
в контекст дословно и поднимаешь весь goga-контекст проектирования.

## Core Principle

requirements.md уже структурирован стабильными идентификаторами (PAGE-<N>, REQ-<N>) — его читают
напрямую все следующие шаги пайплайна. Goga-контекст (DSL, базовый блок Header, референс
веб-рантайма) грузится один раз здесь.

---

## Algorithm

### Step 1. Validate the input

1. Прочитай путь, напечатанный `goga history path -f requirements.md`. Файл отсутствует/пуст —
   **STOP**: сначала запусти пайплайн `goga-tool-pybuggy-web-automate-requirements`.
2. Проверь структуру: §2 (Topic pages) непуст; §3 (Functional requirements) содержит `REQ-<N>`.
   Нет — **STOP**: вернись к пайплайну requirements.

### Step 2. Load the goga context

Загрузи через **Skill tool**:

- **`goga-cell`** — DSL-спецификация ячеек и CODEMANIFEST.
- **`goga-cell-python`** — правила Python (snake_case, `location`).
- **`goga-tool-pybuggy-web-cookbook`** — принципы веб-тест-ячеек.
- **`goga-codemanifest-base`** — базовые usages/annotations из `.goga/config.yml`; зафиксируй
  базовый блок Header **дословно**: `Usages` (`conventions`, `pybuggy-web` с путями) + `Annotations`.
- **`goga-tool-pybuggy-web-usage`** — референс веб-рантайма (page-фикстуры, шаги-предложения, кеш).

Резолв ключей: для каждого ключа базового `Usages` проверь, что файл по пути существует и не пуст
(`pybuggy-web` → `.goga/usages/cooks/pybuggy/pybuggy-web.md`). Нерезолвящийся базовый ключ —
**STOP** (попроси пользователя запустить `goga tool pybuggy init` kind web/both).

### Step 3. Load requirements into context

Загрузи в контекст requirements.md **дословно** под заголовком [TESTCASES_INTAKE] — это вход всех
следующих шагов.

---

## Output Format

```md
# [TESTCASES_INTAKE]

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

## Requirements

[requirements.md, напечатанный дословно. Новый формат не создаётся.]
```
