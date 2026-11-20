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
UI-тестов** из CODEMANIFEST веб-ячеек: какие файлы `test_*.py` генерировать, как фикстуры-страницы
`page_<name>` превращают предложения шагов в
Playwright-код (генерация LLM при первом прогоне + кеш), и закрепить
`pytest` как инструмент валидации.

## Testing Mode (pre-prompt — mandatory)

Зафиксируй следующее до вызова goga-скилла и держи всю сессию:

- **Mode: TESTING.** Артефакт — тестовый код `test_*.py`, **не** код приложения. Продакшен-сущности
  не проектируются.
- **Source of truth:** CODEMANIFEST веб-ячеек в `tests/web/<cell>/`. Тест-кейс = Routine; варианты
  параметризованной Routine различаются только значениями (заполняемые данные, ожидаемые тексты) —
  тело теста остаётся линейным, без ветвления по варианту. CODEMANIFEST — контракт read-only.
- **Runtime/фикстуры:** фикстуры-страницы `page_<name>` (`pages/<…>_page.py`,
  активация `with page_<name>() as page:`, поверхность `page.step/expect/group`); внешние/литеральные
  страницы — шаги с полным URL через поверхность page-фикстуры.
  Референс — `.goga/usages/cooks/pybuggy/pybuggy-web.md`; загрузи
  через скиллы `goga-tool-pybuggy-web-usage` и `goga-tool-pybuggy-web-cookbook`.
- **Шаги-предложения:** каждый пункт `Steps:` аннотации материализуется ровно в одно предложение —
  действие → `page.step("…")`, проверка → `page.expect("…")`, мини-сценарий (набор действий, меняющий
  состояние страницы/виджета) → `with page.group("<достигаемое состояние>"):`
  (через поверхность активированной страницы).
  Один шаг = одно действие; адрес страницы тестируемого сайта — путь относительно base_url
  (`/catalog`, из §2 требований; навигация сайта компонуется рантаймом из `site.base_url`),
  полный URL — только внешняя страница (чужой origin); ожидания — отдельными `page.expect`
  (исключение — транзитные тосты/баннеры с временем жизни из §2: их подтверждение/чтение живёт
  в самом предложении-триггере — отдельное expect-предложение не успеет: код предложения
  генерируется LLM непосредственно перед его исполнением, за LLM-раунд транзит исчезает);
  захваты
  значений — маркерами в предложениях дословно: `{% var <имя> %}` захватывает значение со
  страницы, `{{ <имя> }}` подставляет захваченное в последующие предложения (только динамика
  страницы — значения, неизвестные при написании теста; статические литералы идут без
  маркеров); предложения материализуются **строковыми литералами** — `{{ … }}` /
  `{{ vars.<имя> }}` маркеры движка дословно, python-значение входит в предложение только
  kwarg-ом `vars={...}` (`{{ имя }}` — память, `{{ vars.имя }}` — колл-входы); **секреты в
  предложениях запрещены** (всё попадает в промпт LLM-провайдера и в репозиторий; вход — «Выполнить
  вход как тестовый пользователь `<роль>`», значения из env/usage-файла).
- **Пер-тестовые инструкции генерации:** секция `Prompt:` аннотации Routine материализуется
  декораторами `@generation_prompt("<буллет>")` над тестом (импорт
  `from goga_tool_pybuggy import generation_prompt`): порядок буллетов = порядок декораторов, тексты
  дословны; у Routine без `Prompt:` декораторов нет. Семантика — `pybuggy-web` usage.
- **Методы страниц:** методы page-объектов уже написаны стадией pages пайплайна testcases
  (`pages/<…>_page.py`; их контракт — usage-файлы `.goga/usages/cooks/page-<name>.md`).
  Предложение-цель со ссылкой ``Use `page-<name>` for <цель> — метод `<method>`` `
  материализуется вызовом `page_<name>.<method>()` через фикстуру страницы (pytest резолвит
  её по имени) — **inline-шаги для такого предложения не генерируются**: предложения уже
  живут в методе, их кеш общий для страницы (`pages/.cache/<page>/`).
- **Навигация на страницы сайта:** навигационное предложение с путём («Открыть страницу
  `/login`») материализуется **активацией фикстуры страницы** `page_<name>()` — вызов
  открывает страницу одним шагом, URL компонуется рантаймом из `site.base_url`; inline-шаг
  с полным URL — только внешние страницы (чужой origin) и query-адреса.
- **Генерация шагов и кеш:** **первый** прогон теста генерирует Playwright-код каждого предложения
  через LLM (провайдер/модель из `.goga/tools/pybuggy/web.yml`) и пишет кеш в
  `tests/web/<cell>/.cache/test_<name>/test_<name>/` (параметризованный кейс —
  `…/test_<name>[<param_id>]/`; предложения методов страниц — общий кеш `pages/.cache/<page>/`);
  кеш коммитится в репозиторий. Первый прогон — **без**
  `--strict-mode`; повторные прогоны и CI — со `--strict-mode` (реплей из кеша, 0 LLM-вызовов).
  Смена окружения = смена `site.base_url` (+ один прогон без `--strict-mode`), не смена
  предложений шагов.
- **Constraints:** ячейки только из Routine; без Entities; без нового продакшен-кода; без нового
  `__init__.py`.
- **Validation:** инструмент верификации — `pytest` (для плана). Укажи в дизайне, что валидация =
  запуск тестов.
- **Target environment:** прочитай Base URL и целевое окружение топика из пути, напечатанного
  `goga history path -f requirements.md` (§1 "Base URL" / "Target environment" / §4), и перенеси
  их в дизайн: страницы топика адресуются **путями относительно base_url** (внешние — полными
  URL с пометкой); смена окружения — смена `site.base_url` (+ один прогон без `--strict-mode`),
  предложения шагов не меняются; записанные команды прогона несут аргументы рендера base_url
  (env/CLI) из §1.

## Dispatch

Arguments: `$ARGUMENTS`

1. Если `$ARGUMENTS` пуст — проверь, что CODEMANIFEST веб-ячеек существуют в `tests/web/*/`
   (мега-стейдж testcases должен был отработать): отсутствуют → halt и попроси пользователя
   сначала запустить его.
2. Загрузи контекст веб-тестирования через **Skill tool**: `goga-tool-pybuggy-web-usage` и
   `goga-tool-pybuggy-web-cookbook`.
3. Вызови `goga-design` через **Skill tool**, приложив явный пакет режима веб-тестирования
   (маркерная фраза: «Pybuggy web testing mode: generate browser UI tests from CODEMANIFEST web-cells;
   deliverable is `test_*.py` using page-object fixtures (`page_<name>`; external/literal pages
   open by full-URL step sentences through the page fixture's surface) with step sentences (one action per step,
   site pages addressed as paths relative to the base URL with external pages by full URLs,
   expectations as separate expect-steps); goal sentences carrying a
   `Use page-<name> — method <method>` reference materialize as `page_<name>.<method>()`
   calls — the page-object methods already exist in pages/**, never generate inline steps
   for them; first run generates the Playwright steps via
   the LLM and caches them next to the test — never `--strict-mode` on first run; never production
   code»).
4. `goga-design` сам диспетчеризует `goga-design-by-changes` — не вызывай его в обход `goga-design`.
5. По завершении проверь, что путь, напечатанный `goga history path -f design.md`, описывает
   генерацию веб-тестов (фикстуры-страницы `page_<name>`,
   предложения шагов, каталоги `tests/web/<cell>/`), называет
   `pytest` инструментом валидации, упоминает генерацию шагов LLM при первом прогоне с кешем,
   коммитящимся в репозиторий (и запрет `--strict-mode` на первом прогоне), и закрепляет
   материализацию предложение-цель вызовом метода page-объекта
   (`page_<name>.<method>()` по ссылке `Use page-<name>`, без inline-шагов). Если нет — дополни
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
- перенести Base URL и целевое окружение топика в предписания дизайна (страницы топика — путями
  относительно base_url; смена окружения — смена `site.base_url`, не предложений шагов)
- отразить механику генерации шагов: первый прогон — LLM + кеш (без strict), повторы — strict-реплей
