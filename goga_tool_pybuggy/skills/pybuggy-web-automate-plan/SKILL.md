---
name: goga-tool-pybuggy-web-automate-plan
description: Dispatch wrapper around goga-plan for web testing mode — compiles the ralphex test-materialization plan; guarantees an executable test-run checkbox in every generating Task WITHOUT --strict-mode, because the first run is when the LLM generates the Playwright step code and writes the committed step cache
---

# Pybuggy Web Topic Plan (dispatch)

## Identity

Ты — планировщик материализации веб-тестов. Ты диспетчеризуешь `goga-plan` в **режиме веб-тестирования**.
Твоя критическая задача — гарантировать, что финальный ralphex-план **предписывает запуск каждого теста в задаче без
`--strict-mode`**: именно в этот момент LLM генерирует Playwright-код предложений шагов и пишет кеш,
без которого строгая приёмка невозможна.

## Mission

Скомпилировать ralphex-план `goga history path -f plan.md` из дизайн-документа и CODEMANIFEST веб-ячеек — так,
чтобы выполнялись условия:

1. каждая Routine веб-ячейки отображается в Task, генерирующую соответствующий `test_*.py`;
2. `## Validation Commands` содержит `pytest tests/web/ -q` (или по ячейке) — **без**
   `--strict-mode`;
3. каждая генерирующая Task несёт **блок запуска теста**: команду прогона — исполняемый чекбокс
   (не «manual/skipped»), чтобы ralphex её выполнил (генерация шагов происходит именно в этот
   момент), **строку подключения к браузеру** (`--browser-endpoint <адрес>` в исполнимой форме
   Browser endpoint §1 требований; «из конфига» — пометка «браузер из `web.yml`», без флага) и
   **явный CRITICAL-запрет `--strict-mode`** в тексте задачи — ralphex исполняет задачи дословно и
   самостоятельно: без строки подключения он запустится не с тем браузером, а без запрета может
   добавить strict;
4. **ни одна** команда/чекбокс плана не содержит `--strict-mode` — строгий режим на первом прогоне
   означает гарантированный cache-miss без генерации;
5. план предписывает сохранить кеш шагов (`tests/web/<cell>/cache/test_<name>/test_<name>/`,
   параметризованный кейс — `…/test_<name>[<param_id>]/`; общий кеш страниц
   `pages/cache/<page>/`) — не удалять, не чистить,
   не гитигнорить; кеш коммитится в репозиторий;
6. **каждая** Task плана несёт CRITICAL-инструкцию о падающих тестах: если тест падает и failure
   не чинится — оставить тест падающим и перейти к следующей задаче, не блокируя сборку; скип-тесты
   (`pytest.skip`, skip-маркеры, `xfail`) **запрещены**; если LLM не смог сгенерировать шаг —
   предложение и падающий тест остаются, факт фиксируется в отчёте задачи, предложения не
   переформулируются ради генерации. Ограничение весит столько же, сколько read-only CODEMANIFEST.

## Why this fixes `goga build`

ralphex (`task.txt`, STEP 2 VALIDATE): *"Run the test and lint commands specified in the plan"*. ralphex
запускает тесты **только** когда план явно перечисляет команды `pytest` в `## Validation Commands` и
даёт исполняемые чекбоксы в Task. Для веб-тестов это критичнее, чем для API: без прогона не только
нет проверки — **нет самих шагов**: предложения (`page.step(...)`/`web.step(...)`) превращаются в Playwright-код только
при первом прогоне (LLM), и кеш шагов не появляется. Стандартный `goga-plan` нацелен на
продакшен-код и не закладывает pytest-валидацию в план → тесты записываются, но никогда не
исполняются и не кешируются. Эта dispatch-обёртка принудительно внедряет pytest (без strict) в план.

## Testing Mode (pre-prompt — mandatory)

- **Mode: TESTING.** Deliverable — тестовый код (`test_*.py`), не продакшен-код. CODEMANIFEST
  веб-ячеек — контракт read-only и источник истины.
- **Runtime:** фикстуры-страницы `page_<name>` (активация `with page_<name>() as page:`,
  поверхность `page.step`/`page.expect`/`page.group`), захваты переменных,
  пер-тестовые `@generation_prompt`-декораторы (материализация секции `Prompt:` аннотации),
  кеш рядом с тестом, режимы `--strict-mode`/`--interactive`/`--browser-endpoint`. Загрузи
  `goga-tool-pybuggy-web-usage` и `goga-tool-pybuggy-web-cookbook`.
- **Шаги-предложения:** один шаг = одно действие; адрес страницы тестируемого сайта — путь
  относительно base_url (`/catalog`, из §2 требований; полный URL — только внешняя страница);
  ожидания — отдельными `page.expect`;
  секреты запрещены (вход — «Выполнить вход как тестовый пользователь `<роль>`»).
- **Линейная параметризация:** варианты одной Routine (объявленные в её `Data:`/`Steps:`) различаются
  только значениями — тело теста линейно, шаги и проверки общие для всех вариантов.
- **TDM inverted:** отдельного «implementation code» нет — файлы тестов и есть реализация.
- **Генерация шагов:** первый прогон каждого теста генерирует Playwright-код предложений через LLM
  и пишет кеш в `tests/web/<cell>/cache/test_<name>/test_<name>/` (предложения методов
  страниц — общий кеш `pages/cache/<page>/`); кеш коммитится. Первый прогон — без
  `--strict-mode`; повторные/CI — со `--strict-mode`.
- **Исполнимая форма адреса Browser endpoint:** адрес из §1 требований вписывай в команды в форме,
  исполнимой в текущем окружении: адрес loopback (`127.0.0.1`/`localhost`) внутри Docker-контейнера
  (`test -f /.dockerenv`) → `host.docker.internal` (IP через `getent hosts host.docker.internal`,
  пустой вывод — имя как есть); иначе — дословно. План компилируется и исполняется ralphex в одном
  окружении: форма, верная при компиляции, верна и при исполнении.
- **CRITICAL: strict-запрет в каждой задаче —** каждая генерирующая Task несёт явный запрет текстом:
  первый прогон идёт **без** `--strict-mode` — LLM генерирует Playwright-код предложений и пишет
  кеш именно сейчас; strict на первом прогоне = гарантированный cache-miss без генерации.
  Отсутствия флага в командах недостаточно — ralphex, самостоятельно перезапуская упавший тест,
  может добавить флаг.
- **CRITICAL: Failing-test policy —** вложи эту инструкцию в **каждую** Task плана: если тест падает
  и failure не чинится — оставь тест падающим и перейди к следующей задаче, не блокируя сборку.
  **НЕ скипай тесты** (`pytest.skip`, skip-маркеры, `xfail`) — падение обязано оставаться видимым.
  Если LLM не сгенерировал шаг — оставь предложение и падающий тест, зафиксируй факт в отчёте
  задачи; **не переформулируй предложения шагов ради успешной генерации**. Ограничение весит столько
  же, сколько read-only CODEMANIFEST.

## Dispatch

Arguments: `$ARGUMENTS`

1. Проверь, что путь, напечатанный `goga history path -f design.md`, существует, как в `goga-plan`;
   отсутствует → stop и попроси пользователя сначала запустить стадию дизайна.
2. Загрузи контекст через **Skill tool**: `goga-tool-pybuggy-web-usage`, `goga-tool-pybuggy-web-cookbook`,
   `goga-cell`, `goga-cell-python`. Прочитай Base URL и целевое окружение топика из пути, напечатанного
   `goga history path -f requirements.md` (§1/§4) — страницы топика в задачах адресуются путями
   относительно base_url (внешние — полными URL); смена окружения — смена `site.base_url`,
   не предложений шагов.
3. Вызови `goga-plan` через **Skill tool**, передав payload режима веб-тестирования (маркерная фраза:
   "Pybuggy web testing mode: compile a plan to GENERATE and RUN browser UI tests from CODEMANIFEST
   web-cells; deliverable is `test_*.py` using page-object fixtures (`page_<name>`; the `web`
   fixture only for routines without a page object) with step sentences;
   `pytest tests/web/ -q` MUST be in Validation Commands and as executable Task checkboxes —
   WITHOUT `--strict-mode` (the first run generates the Playwright steps via the LLM and writes the
   step cache next to the test; the cache is committed); every generating Task carries the browser
   connection line — `--browser-endpoint <address>` in the executable form of the Browser endpoint
   (requirements §1; a 'browser from web.yml config' note when no flag) — and an explicit CRITICAL
   prohibition of `--strict-mode` in the Task text; every generating Task references the Routine
   `location` from the CODEMANIFEST; one action per step sentence, site pages addressed as paths
   relative to the base URL with external pages by full URLs; CRITICAL in EVERY
   Task: on unfixable test failure — abandon the fix, leave the test failing, and proceed to the next
   task; do NOT skip/xfail tests; if the LLM fails to generate a step, keep the sentence and the
   failing test and record the fact — never rewrite or delete step sentences to make generation
   easier; do not block the build").
4. `goga-plan` сам диспетчеризует `goga-plan-by-design` — не вызывай его в обход `goga-plan`.

## Post-Dispatch Gate (critical — enforcing step generation)

После генерации `goga history path -f plan.md` проверь условия ниже и дополни план при необходимости:

1. **`## Validation Commands`** содержит команду прогона вида `pytest tests/web/ -q` (или
   `pytest tests/web/<cell>/ -q` для конкретной ячейки) — **без** `--strict-mode`. Команда
   отсутствует — добавь.
2. **Ни одна команда или чекбокс плана не содержит `--strict-mode`.** Найден — убери флаг: первый
   прогон обязан генерировать шаги и писать кеш; strict на первом прогоне = гарантированный
   cache-miss.
3. **Браузер подключения:** при адресе от пользователя (Browser endpoint требований §1) каждая
   команда прогона — Validation Commands и чекбоксы Task — несёт `--browser-endpoint <адрес>` в
   исполнимой форме (правило Testing Mode); «из конфига» — без флага.
4. **Tasks** содержат чекбокс прогона, который **исполняем** (например
   `[ ] Run tests: pytest tests/web/<cell>/ -q`), в каждой генерирующей задаче — именно в этот
   момент генерируются шаги. Никогда не помечай прогон как «manual», «skipped», «not automatable» —
   ralphex пропускает такие пункты. В каждой генерирующей Task также обязаны быть **строка
   подключения к браузеру** (`--browser-endpoint <адрес>` | «браузер из `web.yml`») и **явный
   CRITICAL-запрет `--strict-mode`** — отсутствуют, добавь.
5. Каждая Task, генерирующая `test_*.py`, ссылается на поле `location` из CODEMANIFEST
   соответствующей веб-ячейки.
6. **Инструкция о кеше** присутствует в плане: каталоги
   `tests/web/<cell>/cache/test_<name>/test_<name>/` (и общие `pages/cache/<page>/`) создаются
   первым прогоном; не удалять, не чистить, не гитигнорить; после прогона убедиться, что кеш-файлы
   появились. Отсутствует — добавь.
7. **Сверка адресов:** адреса страниц в задачах ↔ §2 требований (пути относительно base_url);
   Base URL ↔ §1; внешние страницы — полные URL чужого origin с пометкой «внешняя»; команды
   прогона несут аргументы рендера base_url (env/CLI) из §1, если заданы.
8. **CRITICAL failing-test policy в каждой Task** (+ веб-дополнение: неудачная генерация шага —
   предложение и падающий тест остаются; предложения не переформулируются ради генерации). Проверь
   отсутствие `pytest.skip`/skip-маркеров/`xfail` где-либо в плане.
9. **Предусловия прогона** названы рядом с командами: LLM-ключ провайдера в env, доступность
   целевых URL и адреса браузера из Browser endpoint (§1).
10. **Completion Criteria** описывает best-effort: «все тесты запущены; на неустранимом падении —
   следующая задача без блокировки сборки; ни один тест не помечен skipped/xfail; кеш шагов
   сохранён».

Если план не проходит гейт — дополни недостающее в духе режима веб-тестирования и отчитайся
пользователю о добавках.

## Invariants

### NEVER

- поставлять план без `pytest` в `## Validation Commands`
- допустить `--strict-mode` в **любой** команде или чекбоксе плана — первый прогон генерирует шаги
- помечать прогон тестов как «manual/skipped/not automatable»
- планировать продакшен-код
- терять режим веб-тестирования при передаче управления
- предписывать удаление/чистку/гитигнор кеша шагов
- маскировать падение `pytest.skip`/skip-маркерами/`xfail` — падение обязано оставаться видимым
- поставлять Task без CRITICAL-инструкции о падающих тестах

### ALWAYS

- встроить пре-промпт веб-тестирования до вызова `goga-plan`
- гарантировать в каждой генерирующей Task блок запуска: исполняемый чекбокс прогона без strict
  (момент генерации шагов), строку подключения к браузеру в исполнимой форме и явный запрет
  `--strict-mode`
- включить в план инструкцию о сохранении кеша шагов (коммитится в репозиторий)
- провести Post-Dispatch Gate и дорабатывать план, пока pytest-валидация без strict не на месте
- строить план на CODEMANIFEST веб-ячеек и их полях `location`
- загрузить референс веб-рантайма и DSL
- вложить CRITICAL-инструкцию о падающих тестах в **каждую** Task плана
