---
name: goga-tool-pybuggy-web-automate-requirements-report
description: Assemble the final "Detailed web topic requirements" artifact and save it to the path printed by `goga history path -f requirements.md`
---

# Pybuggy Web Topic Requirements — Report

## Identity

Ты синтезируешь финальный артефакт [TOPIC_SPEC] из выводов всех предыдущих шагов и сохраняешь его в файл.

## Algorithm

1. Собери выводы всех предыдущих шагов: [INTAKE_REPORT], [EXPLORE_REPORT], [ELABORATION_REPORT].
2. Синтезируй их в единый артефакт [TOPIC_SPEC].
3. Назначь каждому требованию §3 стабильный идентификатор `REQ-<N>` — на него ссылается сессионный
   реестр покрытия фазы routines design. Правила:
    - нумеруй последовательно внутри §3, начиная с 1, без пропусков и дублей;
    - порядок нумерации по подразделам: "Main behavior" → "Error behavior (contract)" →
      "Acceptance criteria" → "Constraints and boundaries";
    - идентификаторы вводятся только в §3 — §4 (предусловия) и §5 (роли) остаются текстовыми.
4. Назначь каждой странице §2 стабильный идентификатор `PAGE-<N>` (порядок — как в [EXPLORE_REPORT]);
   на него ссылаются рутины (стартовые URL) и границы ячеек.
5. Включай только проверенные факты — из досье [EXPLORE_REPORT] и решения пользователя из
   [ELABORATION_REPORT]. Не выдумывай.
6. Скопируй факты веб-рантайма из [INTAKE_REPORT] в §1 ("Web runtime") и §4 — **дословно**
   (provider, generation model — LLM-факты генерации шагов). Нижестоящие пайплайны читают их отсюда.
7. Скопируй целевое окружение из [INTAKE_REPORT] в §1 ("Target environment") и §4 — дословно, с
   подтверждённым решением пользователя. Правило веб-тестов: шаги несут **полные URL**, никакой
   base_url-шаблонизации — смена окружения означает смену предложений шагов; каждая записанная
   команда прогона — `pytest tests/web/<cell>/ -q` (без `--strict-mode` на первом прогоне)
   + суффикс Browser Endpoint (см. ниже), если задан. Скопируй решение Browser Endpoint из
   [INTAKE_REPORT] в §1 ("Browser endpoint") и §4: адрес от пользователя добавляет в каждую
   записанную команду прогона суффикс `--browser-endpoint <адрес>`; «из конфига» — без суффикса.
   Исследование и прогоны используют один браузер.
8. Скопируй описание топика из секции "Original Request" [INTAKE_REPORT] в §1 дословно — стадия
   testcases сопоставляет это описание с досье страниц.
9. Скопируй механизм авторизации из [INTAKE_REPORT]/[EXPLORE_REPORT] в §4 ("Auth") дословно:
   механизм (нет / форма `<URL>` поля `<name>` сабмит `<кнопка>` / SSO), источник креденшалов
   (env `<имена>` / пользователь). **Значений секретов в артефакте нет и не должно быть.**
10. Скопируй реестр usages проекта в §8: просканируй `.goga/usages/` целевого проекта
    (key | path | role | purpose — справочник доступных активов, без выбора инструментов; выбор —
    на стадии testcases, шаг tools).
11. Скопируй статус покрытия из [EXPLORE_REPORT]/[INTAKE_REPORT] в §9: какие страницы уже покрыты
    существующими тестами `tests/web/**`, какие Routine существуют, действие по каждой —
    reuse / extend / regenerate.
12. Проверь полноту: каждая секция заполнена.
13. Сохрани [TOPIC_SPEC] по пути, напечатанному `goga history path -f requirements.md`
    (перезаписывай файл при повторных запусках).

---

## Output Format

Сохрани результат по пути, напечатанному `goga history path -f requirements.md`. Содержимое файла
следует формату ниже. Fill in every section. Empty sections are forbidden.

```md
### Detailed web topic requirements: [Topic name]

**1. Context and goal:**

- **Service:** [Краткое описание сайта/сервиса]
- **Topic description (verbatim):** [Исходный запрос пользователя — из intake "Original Request"]
- **Topic goal:** [Уточнённая цель]
- **Web runtime:** [Дословно из .goga/tools/pybuggy/web.yml: provider, generation_model —
  LLM-факты генерации шагов]
- **Browser endpoint:** [«из конфига» (`browser.endpoint: <значение>`) | `<ws(s)://… | http(s)://…>`
  от пользователя; суффикс команд прогона: без флага | `--browser-endpoint <адрес>` —
  адрес браузера для исследования и прогонов, не тестируемый сайт]
- **Target environment:** [Полные базовые URL тестируемого окружения (прод/stage/feature-деплой).
  Правило: шаги веб-тестов несут полные URL — смена окружения означает смену предложений шагов;
  записанные команды прогона — `pytest tests/web/<cell>/ -q` + суффикс Browser endpoint]

**2. Topic pages:**

Каждая страница несёт стабильный идентификатор `PAGE-<N>` — на него ссылаются рутины и ячейки.

| PAGE | URL (итоговый) | Title | Назначение | Роль в топике |
|------|----------------|-------|------------|---------------|
| PAGE-1 | https://… | […] | […] | […] |

Примечание: кеш шагов материализованных тестов живёт в `tests/web/<cell>/test_<name>/` и
коммитится в репозиторий.

**3. Functional requirements:**

Каждое требование несёт стабильный идентификатор `REQ-<N>` (последовательная нумерация внутри §3
в порядке подразделов, без пропусков и дублей) — реестр для трассируемости рутин.

- **Main behavior:**
    - `REQ-1` — [Сценарий/правило: условие → ожидаемое поведение страницы]
- **Error behavior (contract):**
    - `REQ-<N>` — [Условие ошибки → ожидаемая реакция: текст валидации / пустое состояние / 404]
- **Acceptance criteria:**
    - `REQ-<N>` — [Критерий]
- **Constraints and boundaries:**
    - `REQ-<N>` — [Что топик не делает]

**4. Preconditions and environment:**

- Business preconditions (данные/состояния — как потребность): [...]
- **Auth:** [механизм: без авторизации | форма `<URL>`, поля `<name>`, сабмит `<кнопка/локатор>` | SSO;
  источник креденшалов: env `<имена>` / пользователь. Значений секретов НЕТ]
- Target environment: [полные URL тестируемого окружения]
- Web runtime: [дословно из web.yml — повтор пункта §1]
- Browser endpoint: [повтор пункта §1 — «из конфига» | адрес + суффикс `--browser-endpoint <адрес>`]

**5. Roles and permissions:**

[Кто может / не может выполнять сценарии (роли, статусы авторизации)]

**6. Integration aspects:**

- [API-эндпоинты страниц (метод + путь), внешние скрипты/виджеты, куки-баннеры, pop-up]

**7. Links and resources:**

- [Документация, макеты, ссылки — если есть]

**8. Available project usages:**

| key     | path             | role                                              | purpose                     |
|---------|------------------|---------------------------------------------------|-----------------------------|
| `<key>` | [.goga/usages/…] | [runtime reference / data-mocks-utilities / other] | [предметная область — фраза] |

Реестр — результат сканирования `.goga/usages/` целевого проекта. Это **справочник доступных
активов**, а не выбор инструментов: потребности тестов согласуются с инструментами (существующими
или новыми) на стадии testcases — там же создаются usage-файлы новых библиотек
(`.goga/usages/cooks/<key>.md`). Если `.goga/usages/` пуст — напиши "no usages".

**9. Already covered by tests:**

[Таблица: страница/флоу | статус (not covered / partial / full) | существующие Routine в
`tests/web/**` (имя → Flow/Positive/Negative) | действие (reuse / extend — достающие / regenerate)].
Секция **опциональна**: если ничего не покрыто — напиши "no coverage".
```
