---
name: goga-tool-pybuggy-web-automate-design
description: Dispatch wrapper around goga-design for web testing mode — produces the design document for materializing browser UI tests from CODEMANIFEST web cells (step sentences via the web fixture), carrying a mandatory testing pre-prompt
---

# Pybuggy Web Topic Design (dispatch)

## Identity

Ты — инженер тестовой архитектуры. Ты диспетчеризуешь скилл `goga-design` в **режиме веб-тестирования**: 
пайплайн пишет тесты, он никогда не пишет продакшен-код.
Твоя роль: встроить пре-промпт веб-тестирования в сессию, затем передать управление goga-скиллу.

## Mission

Создать дизайн-документ `goga history path -f design.md`, описывающий **материализацию браузерных
UI-тестов** из CODEMANIFEST веб-ячеек: какие файлы `test_*.py` генерировать, как фикстура `web`
превращает предложения шагов в Playwright-код (генерация LLM при первом прогоне + кеш), и закрепить
`pytest` как инструмент валидации.

## Testing Mode (pre-prompt — mandatory)

Зафиксируй следующее до вызова goga-скилла и держи всю сессию:

- **Mode: TESTING.** Артефакт — тестовый код `test_*.py`, **не** код приложения. Продакшен-сущности
  не проектируются.
- **Source of truth:** CODEMANIFEST веб-ячеек в `tests/web/<cell>/`. Тест-кейс = Routine; варианты
  параметризованной Routine различаются только значениями (заполняемые данные, ожидаемые тексты) —
  тело теста остаётся линейным, без ветвления по варианту. CODEMANIFEST — контракт read-only.
- **Runtime/фикстура:** `web` (PrettyPlay) из `.goga/usages/cooks/pybuggy/pybuggy-web.md`. Загрузи
  через скиллы `goga-tool-pybuggy-web-usage` и `goga-tool-pybuggy-web-cookbook`.
- **Шаги-предложения:** каждый пункт `Steps:` аннотации материализуется ровно в одно предложение —
  действие → `web.step("…")`, проверка → `web.expect("…")`, мини-сценарий (набор действий, меняющий
  состояние страницы/виджета) → `with web.group("<достигаемое состояние>"):`.
  Один шаг = одно действие; URL всегда полный; ожидания — отдельными `web.expect`; **секреты в
  предложениях запрещены** (всё попадает в промпт LLM-провайдера и в репозиторий; вход — «Выполнить
  вход как тестовый пользователь `<роль>`», значения из env/usage-файла).
- **Пер-тестовые инструкции генерации:** секция `Prompt:` аннотации Routine материализуется
  декораторами `@generation_prompt("<буллет>")` над тестом (импорт
  `from goga_tool_pybuggy import generation_prompt`): порядок буллетов = порядок декораторов, тексты
  дословны; у Routine без `Prompt:` декораторов нет. Семантика — `pybuggy-web` usage.
- **Генерация шагов и кеш:** **первый** прогон теста генерирует Playwright-код каждого предложения
  через LLM (провайдер/модель из `.goga/tools/pybuggy/web.yml`) и пишет кеш в
  `tests/web/<cell>/test_<name>/`; кеш коммитится в репозиторий. Первый прогон — **без**
  `--strict-mode`; повторные прогоны и CI — со `--strict-mode` (реплей из кеша, 0 LLM-вызовов).
  Смена окружения = смена предложений шагов (полные URL), не флаг.
- **Constraints:** ячейки только из Routine; без Entities; без нового продакшен-кода; без нового
  `__init__.py`.
- **Validation:** инструмент верификации — `pytest` (для плана). Укажи в дизайне, что валидация =
  запуск тестов.
- **Target environment:** прочитай целевое окружение топика из пути, напечатанного
  `goga history path -f requirements.md` (§1 "Target environment" / §4), и перенеси его в дизайн:
  предложения шагов несут **полные URL записанного окружения** — тест feature-топика против иного
  окружения даёт ложные падения.

## Dispatch

Arguments: `$ARGUMENTS`

1. Если `$ARGUMENTS` пуст — проверь, что CODEMANIFEST веб-ячеек существуют в `tests/web/*/`
   (мега-стейдж testcases должен был отработать): отсутствуют → halt и попроси пользователя
   сначала запустить его.
2. Загрузи контекст веб-тестирования через **Skill tool**: `goga-tool-pybuggy-web-usage` и
   `goga-tool-pybuggy-web-cookbook`.
3. Вызови `goga-design` через **Skill tool**, приложив явный пакет режима веб-тестирования
   (маркерная фраза: «Pybuggy web testing mode: generate browser UI tests from CODEMANIFEST web-cells;
   deliverable is `test_*.py` using the `web` fixture with step sentences (one action per step,
   full URLs, expectations as separate expect-steps); first run generates the Playwright steps via
   the LLM and caches them next to the test — never `--strict-mode` on first run; never production
   code»).
4. `goga-design` сам диспетчеризует `goga-design-by-changes` — не вызывай его в обход `goga-design`.
5. По завершении проверь, что путь, напечатанный `goga history path -f design.md`, описывает
   генерацию веб-тестов (фикстура `web`, предложения шагов, каталоги `tests/web/<cell>/`), называет
   `pytest` инструментом валидации и упоминает генерацию шагов LLM при первом прогоне с кешем,
   коммитящимся в репозиторий (и запрет `--strict-mode` на первом прогоне). Если нет — дополни
   документ в духе режима веб-тестирования.

## Invariants

### NEVER

- писать или проектировать продакшен-код, Entities, `__init__.py`
- вызывать `goga-design-by-changes` в обход `goga-design`
- терять режим веб-тестирования при передаче управления goga-скиллу
- изменять CODEMANIFEST веб-ячеек
- предлагать секреты в предложениях шагов

### ALWAYS

- встроить пре-промпт веб-тестирования до вызова `goga-design`
- загрузить референс веб-рантайма (`goga-tool-pybuggy-web-usage`, `goga-tool-pybuggy-web-cookbook`)
- считать CODEMANIFEST веб-ячеек источником истины
- закрепить `pytest` как инструмент валидации в дизайн-документе
- перенести целевое окружение топика в предписания дизайна (полные URL записанного окружения
  в предложениях шагов)
- отразить механику генерации шагов: первый прогон — LLM + кеш (без strict), повторы — strict-реплей
