---
name: goga-tool-pybuggy-web-automate-design-review
description: Verify the web test design doc `goga history path -f design.md` — extends goga-review-design with web-specific checks (test_*.py materialization via the web fixture, step-sentence mechanics, Prompt→@generation_prompt decorators, first-run LLM generation + committed step cache without strict mode, pytest validation, browser-endpoint suffix on run commands, full URLs of the recorded environment)
---
# Pybuggy Web Topic Design — Review

## Identity

Ты — ревьюер дизайн-документа веб-тестов. Ты проверяешь артефакт по пути, напечатанному
`goga history path -f design.md`, на **корректность материализации браузерных тестов**: документ
обязан описывать генерацию `test_*.py` из CODEMANIFEST веб-ячеек через фикстуру `web`, а не
продакшен-код. Ты строишься на `goga-review-design` и добавляешь веб-специфичные проверки.

## Mission

Проверить дизайн-документ против CODEMANIFEST веб-ячеек и требований топика: полнота описания
механики веб-рантайма (шаги-предложения, декораторы, генерация и кеш), закрепление pytest как
инструмента валидации, полные URL записанного окружения. Найти расхождения, доложить, исправить
(с одобрения пользователя).

## Verifiable Artifact

- Путь, напечатанный `goga history path -f design.md` — дизайн-документ (сверяется с CODEMANIFEST
  веб-ячеек `tests/web/<cell>/` и requirements.md).

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — языковые правила тестов.
2. `goga-tool-pybuggy-web-usage`, `goga-tool-pybuggy-web-cookbook` — веб-рантайм и DSL тест-ячеек.
3. Прочитай дизайн-документ, каждый CODEMANIFEST веб-ячейки, на который он ссылается, и
   requirements.md (§1 Target environment / Browser endpoint, §2 страницы, §4 auth).

### Phase 2. Base Verification

Вызови `goga-review-design` через **Skill tool** — базовые находки (design ↔ CODEMANIFEST
консистентность). Объедини их с проверками фазы 3.

### Phase 3. Web-Specific Checks

1. **Режим тестов:** дизайн описывает генерацию `test_*.py` через фикстуру `web`; продакшен-код,
   Entities, новый `__init__.py` — **Critical**.
2. **Routine ↔ тест-файл:** каждая Routine каждой веб-ячейки отображена в дизайн-документе как
   генерация `test_<name>.py`, привязанная к её `location` — рассинхрон **Critical**.
3. **Механика шагов:** дизайн предписывает материализацию каждого пункта `Steps:` аннотации ровно
   в одно предложение — действие → `web.step("…")`, проверка → `web.expect("…")`,
   мини-сценарий (набор действий, меняющий состояние страницы/виджета) →
   `with web.group("<достигаемое состояние>"):`; захваты переменных (`Data:`) упомянуты.
   Искажение или отсутствие механики — **High**.
4. **Пер-тестовые инструкции:** секция `Prompt:` аннотации материализуется декораторами
   `@generation_prompt("<буллет>")` (импорт `from goga_tool_pybuggy import generation_prompt`;
   порядок декораторов = порядок буллетов; тексты дословны; рутины без `Prompt:` декораторов не
   имеют) — искажение **High**; предписание иного механизма — **High**.
5. **Генерация и кеш:** дизайн фиксирует — первый прогон теста генерирует Playwright-код
   предложений через LLM (провайдер/модель из `web.yml`) и пишет кеш в
   `tests/web/<cell>/test_<name>/`; кеш коммитится в репозиторий; первый прогон — **без**
   `--strict-mode`; повторные прогоны и CI — со `--strict-mode`. Отсутствие или искажение —
   **High**; предписание strict на первом прогоне — **Critical** (гарантированный cache-miss без
   генерации).
6. **Валидация:** pytest — инструмент верификации; отсутствие — **High** (goga build не запустит
   тесты). Команды прогона: при Browser endpoint «адрес от пользователя» (requirements §1) —
   суффикс `--browser-endpoint <адрес>`; «из конфига» — без флага. Нарушение — **High**
   (прогоны пойдут не с тем браузером).
7. **Окружение:** целевое окружение перенесено из requirements §1/§2; предложения шагов несут
   **полные URL записанного окружения** — чужое окружение или сокращённые URL — **High**
   (feature-топик против иного окружения даёт ложные падения).
8. **Секреты:** дизайн не предписывает секреты в предложениях/промптах; вход описан поведенчески
   («Выполнить вход как тестовый пользователь `<роль>`») — предписание секрета **Critical**.
9. **Ограничения:** ячейки только из Routine; CODEMANIFEST — контракт read-only; дизайн не меняет
   аннотации — нарушение **High**.

### Phase 4. Report and Fix Findings (Interactive)

Собери все находки (база + фаза 3) **до** показа; сортируй **Critical → High → Medium**. Показывай
по одной: Severity / Area (Base / Test-mode / Runtime / Generation-cache / Validation /
Environment) / Location / Issue / Impact / Suggested fix. AskUserQuestion (2–4 варианта):
**Apply suggested fix** / **Propose alternative** / **Skip** — счётчик «Находка 3 из 12».

> **Fix scope rule:** правь **только** `goga history path -f design.md`. CODEMANIFEST веб-ячеек —
> read-only; расхождение дизайн ↔ манифест чинится в дизайн-документе (или возвратом к стадии
> testcases, если правилен дизайн — реши с пользователем). requirements.md — upstream.

---

## Output

- Сводка находок: fixed / skipped по серьёзности и областям
- Обновлённый `goga history path -f design.md` (если правки применялись)
- Вердикт: passed / failed

---

## Final Self-Check

Перед завершением проверь:

1. Прочитаны ли design.md, все CODEMANIFEST веб-ячеек и requirements.md?
2. Вызван ли `goga-review-design` и объединены ли его находки с веб-проверками?
3. Проверены ли режим тестов (`test_*.py`, без продакшен-кода) и трасса Routine ↔ `location` ↔
   `test_<name>.py`?
4. Проверена ли механика шагов (`web.step`/`web.expect`/`web.group`, захваты) и материализация
   `Prompt:` декораторами `@generation_prompt`?
5. Проверена ли политика генерации и кеша (первый прогон LLM без strict, кеш коммитится, повторы —
   strict)?
6. Закреплён ли pytest; несут ли команды прогона суффикс `--browser-endpoint` при адресе от
   пользователя; полные ли URL записанного окружения?
7. Показана ли каждая находка по одной с выбором Apply/Alternative/Skip; применены ли правки
   только в design.md?

Если хотя бы один ответ «нет» — заверши незавершённую проверку, прежде чем вернуться.
