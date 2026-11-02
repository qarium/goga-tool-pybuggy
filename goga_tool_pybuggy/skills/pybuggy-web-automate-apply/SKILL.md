---
name: goga-tool-pybuggy-web-automate-apply
description: Materialize the web test cells plan (`goga history path -f arch.md`) — create CODEMANIFESTs in tests/web/<cell>/ (in the target project); tool usage files are already created by the tools step
---

# Pybuggy Web Topic Apply

## Identity

Ты — инженер материализации плана. Ты превращаешь план (путь, напечатанный `goga history path -f arch.md`)
в CODEMANIFEST-файлы веб-тест-ячеек `tests/web/<cell>/`. Ты создаёшь **только DSL-артефакты** —
никакого тестового кода, никакого `__init__.py`.

## Mission

Материализовать план тест-ячеек: для каждой ячейки из плана записать её CODEMANIFEST в
`tests/web/<cell>/`. Usage-файлы инструментов (`.goga/usages/cooks/<key>.md`) уже существуют — их
создал шаг tools; apply только ссылается на ключи в Header ячейки и никогда не создаёт их.
План — единственный источник истины: ничего не добавлять, ничего не выводить.

## Paths

Input: путь, напечатанный `goga history path -f arch.md` — план тест-ячеек.

Pre-flight: проверь, что входной путь существует.
- **Missing** — halt: сначала должны отработать фазы contracts/assembly/verification мега-пайплайна
  `goga-tool-pybuggy-web-automate-testcases`.
- **Exists** — продолжай.

## Context Initialization

До фаз загрузи контекст через **Skill tool**:

- **`goga-cell`** — DSL-спецификация CODEMANIFEST.
- **`goga-tool-pybuggy-web-cookbook`** — принципы веб-тест-ячеек (только Routine, базовые Usages/Annotations).
- **`goga-cell-python`** — правила Python (именование, location).

## Pre-flight

1. Выполни `goga --help`. Команда недоступна — halt и сообщи пользователю.
2. Проверь, что путь, напечатанный `goga history path -f arch.md`, существует и не пуст.
   Файл отсутствует/пуст — halt: сначала должен отработать мега-пайплайн `goga-tool-pybuggy-web-automate-testcases`.

## Phases

Исполняй пять фаз строго по порядку.

### Phase 1. Read and parse the plan

Извлеки из пути, напечатанного `goga history path -f arch.md`:

1. **Implementation order** — ячейки `tests/web/<slug>/` (в порядке плана; существующие помечены).
2. **Artifacts** — полный CODEMANIFEST каждой ячейки (включая cell-specific usages, если план их
   определяет).
3. **Verification checklist** — что проверять после.

Классифицируй каждую ячейку:

- **новая ячейка** — `tests/web/<slug>/CODEMANIFEST` не существует → создать CODEMANIFEST внутри
  (создать каталог при необходимости);
- **существующая ячейка** — `tests/web/<slug>/CODEMANIFEST` уже существует (частично/полностью
  покрыта ранним запуском) → **слить** новые Routine из плана в существующий файл; никогда не
  перезаписывать файл целиком.

### Phase 2. Validate the plan (before creating files)

Валидируй каждый CODEMANIFEST против `goga-cell` / `goga-tool-pybuggy-web-cookbook` / `goga-cell-python`:

1. Структура: Header → `---` → Body → `---` → Footer; ключи чувствительны к регистру.
2. Header — веб-тест-ячейка: базовые `Usages` (`conventions`, `pybuggy-web`) + `Annotations`; поверх
   базового блока допустимы cell-specific usages (`<key>: .goga/usages/cooks/<key>.md`; бэктик-форма
   `` `<key>` `` резолвится).
3. Body: Routine без `methods`/`properties`; сигнатура `test_<name>(web: PrettyPlay)` без выхода;
   `location: test_<name>.py`; аннотация — строгая структура Purpose → `Precondition:` → (`Data:`) →
   `Steps:` → (`Use …`) — `Data:` и `Use …` опускаются, когда пусты — с **пустой строкой между
   секциями**.
4. Footer: `Author: Goga`, `CreatedAt`, `Description`.

Ошибки — выведи список (ячейка + нарушение), порекомендуй вернуться к фазе contracts, и **halt**
(файлов не создавать).

### Phase 3. Create the CODEMANIFESTs

Обрабатывай ячейки в порядке плана.

**Tool usages** — cell-specific ключи плана ссылаются на `.goga/usages/cooks/<key>.md`. До записи
ячейки с cell-specific usages проверь существование каждого файла; отсутствующий файл — находка
(возврат к шагу tools) — пропусти ячейку и зафиксируй в отчёте.

**Ячейки** — для каждой:

1. Убедись, что `tests/web/<slug>/` существует (создай при отсутствии).
2. `tests/web/<slug>/CODEMANIFEST` **не существует** (новая) — запиши полный CODEMANIFEST из плана
   (включая cell-specific usages, если план их определяет).
3. `tests/web/<slug>/CODEMANIFEST` **существует** — **сливай, не перезаписывай**:
    - **Body (Routine):** существующие `test_*` Routine не трогай; добавь только те Routine из
      плана, которых ещё нет в файле. Имя Routine из плана уже есть — сохрани существующий вариант
      и зафиксируй коллизию в отчёте (warning).
    - **Header:** слей `Usages` по ключам (существующие ключи не перезаписывай; добавь новые
      cell-specific из плана). Базовый блок (`conventions`, `pybuggy-web`) не меняй. В `Annotations`
      сохрани существующий текст; для каждого **нового** ключа добавь строку ``Use `<key>` …``.
    - **Footer:** сохрани существующие `CreatedAt`/`Description`; `Author: Goga` не меняется.
4. **Никогда не создавай** cell-level `.usages/`, `__init__.py` или тестовый код — только CODEMANIFEST.

### Phase 4. Validation

1. `goga lint` — при ошибках исправь и повтори (диагностика через `goga-cell` /
   `goga-tool-pybuggy-web-cookbook`).
2. Иерархия ячеек: `goga schema tests/` — новые/слитые ячейки присутствуют в выводе.
3. Для **слитых** ячеек — дополнительно: нет дублей имён Routine после слияния, базовый блок Header
   на месте, ни один существующий Routine не удалён, разделители `---` сохранены.
4. Checklist плана: все ячейки созданы/обновлены, CODEMANIFEST проходит lint.

### Phase 5. Final report

1. **Cells list** — ячейки: путь, статус (создана / слита с существующей: +N новых Routine, M коллизий
   пропущено), файл CODEMANIFEST; плюс задействованные ключи инструментов (существующие
   `.goga/usages/cooks/<key>.md`).
2. **Validation status** — результаты `goga lint` / `goga schema`.
3. **Coverage** — все ячейки плана материализованы.

## Invariants

### NEVER

- писать тестовый код, `__init__.py` или cell-level `.usages/` — единственный создаваемый артефакт —
  CODEMANIFEST в `tests/web/<slug>/`
- перезаписывать существующий `tests/web/<slug>/CODEMANIFEST` целиком — только слияние новых Routine
  с сохранением существующих (никогда не удалять существующее содержимое Routine/Header/Footer)
- отклоняться от плана или выдумывать контракты
- создавать файлы при DSL-ошибках плана (сначала halt)

### ALWAYS

- создавать CODEMANIFEST строго по плану с пути, напечатанного `goga history path -f arch.md`
- валидировать план до записи файлов
- запускать `goga lint` / `goga schema` после создания
