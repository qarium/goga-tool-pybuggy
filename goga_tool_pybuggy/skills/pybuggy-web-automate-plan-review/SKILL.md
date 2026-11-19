---
name: goga-tool-pybuggy-web-automate-plan-review
description: Verification of the web ralphex plan `goga history path -f plan.md` — guarantees the plan actually runs the tests WITHOUT --strict-mode (the first run generates the Playwright steps via the LLM and writes the committed step cache), the browser connection line in executable form in every generating Task, the cache-preservation instruction, and the CRITICAL failing-test policy in every Task
---
# Pybuggy Web Topic Plan — Review

## Identity

Ты — ревьюер ralphex-плана материализации веб-тестов: путь, напечатанный `goga history path -f
plan.md`. Твоя главная цель — гарантировать, что план **предписывает запуск каждого теста без
`--strict-mode`**: именно в этот момент LLM генерирует Playwright-код предложений шагов и пишет
кеш. План без прогона оставляет топик без шагов — не только без проверки.

## Mission

Проверить план против дизайн-документа (`goga history path -f design.md`) и CODEMANIFEST веб-ячеек:
полное покрытие Routine → `test_*.py`, исполняемый прогон без strict в каждой генерирующей задаче,
строка подключения к браузеру в исполнимой форме, инструкция о сохранении кеша, failing-test policy
в каждой задаче.

## Verifiable Artifact

- Путь, напечатанный `goga history path -f plan.md` — ralphex-план. Сверяется с design.md,
  CODEMANIFEST веб-ячеек `tests/web/<cell>/` и requirements.md (§1 Browser endpoint / Target
  environment, §2 страницы).

## Why the run checks are critical

ralphex (`task.txt`, STEP 2 VALIDATE): *"Run the test and lint commands specified in the plan"*.
ralphex запускает тесты **только** когда план явно перечисляет pytest-команды в
`## Validation Commands` и даёт исполняемые чекбоксы в Task. Для веб-тестов ставки выше, чем для
API: без прогона нет не только проверки — **нет шагов** (предложения превращаются в Playwright-код
при первом прогоне). Веб-инверсия относительно API-планов: `--strict-mode` запрещён **везде** —
первый прогон обязан генерировать; strict на первом прогоне = гарантированный cache-miss без
генерации. ralphex, самостоятельно перезапуская упавший тест, может добавить флаг сам — поэтому
запрет обязан стоять текстом в каждой генерирующей задаче.

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — языковые правила; `goga-cell`,
   `goga-tool-pybuggy-web-cookbook` — DSL тест-ячеек; `goga-tool-pybuggy-web-usage` — референс
   веб-рантайма (режимы `--strict-mode`/`--browser-endpoint`, кеш).
2. Прочитай четыре артефакта: план, дизайн-документ, каждый CODEMANIFEST веб-ячеек,
   requirements.md (§1 — Browser endpoint, Base URL и Target environment; §2 — страницы/адреса).

### Phase 2. Base Verification

Вызови `goga-review-plan` через **Skill tool** — базовые находки (plan ↔ design ↔ CODEMANIFEST
консистентность). Объедини с проверками фазы 3.

### Phase 3. Critical Test-Execution Checks

1. **`## Validation Commands` содержит** `pytest tests/web/ -q` (или `pytest tests/web/<cell>/ -q`)
   — **без** `--strict-mode`. Отсутствие pytest — **Critical** (тесты не запустятся); флаг strict
   в команде — **Critical** (шаги не сгенерируются).
2. **Ни одна команда или чекбокс плана не содержит `--strict-mode`** — любое вхождение —
   **Critical**.
3. **Исполняемый чекбокс прогона** в каждой генерирующей Task (например
   `[ ] Run tests: pytest tests/web/<cell>/ -q`) — именно в этот момент генерируются шаги. Чекбокс
   «manual/skipped/not automatable» или его отсутствие — **Critical**: ralphex пропускает такие
   пункты.
4. **Строка подключения к браузеру** в каждой генерирующей Task: при адресе от пользователя
   (Browser endpoint требований §1) — `--browser-endpoint <адрес>` в исполнимой форме (адрес
   loopback `127.0.0.1`/`localhost` внутри Docker-контейнера → `host.docker.internal` с резолвом
   IP через `getent hosts`; иначе — дословно); при «из конфига» — пометка «браузер из `web.yml`»
   без флага. Отсутствие строки/пометки — **High** (ralphex запустится не с тем браузером);
   неисполнимая форма адреса — **High**.
5. **Явный CRITICAL-запрет `--strict-mode` текстом** в каждой генерирующей Task — отсутствие
   **High** (отсутствия флага в командах недостаточно).
6. **Инструкция о кеше шагов**: каталоги `tests/web/<cell>/cache/test_<name>/test_<name>/`
   (параметризованный кейс — `…/test_<name>[<param_id>]/`; общие кеши страниц
   `pages/cache/<page>/`) создаются первым
   прогоном; не удалять, не чистить, не гитигнорить; кеш коммитится; после прогона убедиться, что
   кеш-файлы появились. Отсутствие инструкции — **High**; предписание чистки/гитигнора —
   **Critical**.
7. **CRITICAL failing-test policy в каждой Task:** на неустранимом падении — оставить тест
   падающим и перейти к следующей задаче без блокировки сборки; `pytest.skip`/skip-маркеры/
   `xfail` запрещены; неудачная генерация шага — предложение и падающий тест остаются, факт
   фиксируется в отчёте задачи, предложения не переформулируются ради генерации. Отсутствие
   инструкции в Task — **Critical**; любое вхождение skip/xfail в плане — **Critical** (маскировка
   падений).
8. **Routine → Task:** каждая Routine CODEMANIFEST покрыта задачей, генерирующей `test_<name>.py`
   по её `location` (задача ссылается на `location`) — пропуск **High**.
9. **Сверка адресов:** страницы топика в задачах — путями относительно base_url, сверка с §2
   требований; Base URL ↔ §1; полный URL чужого домена без пометки «внешняя» или адресация вне
   модели Base URL (голый host без схемы) — **High**.
10. **Предусловия прогона** названы рядом с командами: LLM-ключ провайдера в env, доступность
    целевых URL и адреса браузера из Browser endpoint — отсутствие **Medium**.
11. **Completion Criteria** описывают best-effort: «все тесты запущены; на неустранимом падении —
    следующая задача без блокировки сборки; ни один тест не помечен skipped/xfail; кеш шагов
    сохранён». Отсутствие — **High**; жёсткое «all must pass» — **High** (одно неустранимое падение
    заблокирует сборку).

### Phase 4. Report and Fix Findings (Interactive)

Собери все находки (база + фаза 3) **до** показа; сортируй **Critical → High → Medium**. Показывай
по одной: Severity / Area (Base / Execution / Browser / Cache / Policy / Coverage / Environment) /
Location / Issue / Impact / Suggested fix. Для Critical-находок исполнения (pytest отсутствует,
strict присутствует, чекбокс замаскирован, skip-маркеры) предлагай конкретный fix обязательно.

AskUserQuestion (2–4 варианта): **Apply suggested fix** / **Propose alternative** / **Skip** —
счётчик «Находка 3 из 12».

> **Fix scope rule:** правь **только** `goga history path -f plan.md`. CODEMANIFEST — read-only;
> design.md и requirements.md — upstream (расхождение — находка с предложением вернуться к
> соответствующей стадии).

---

## Output

- Сводка находок: fixed / skipped по серьёзности и областям
- Обновлённый `goga history path -f plan.md` (если правки применялись)
- Вердикт: passed / failed

---

## Final Self-Check

Перед завершением проверь:

1. Прочитаны ли план, дизайн-документ, все CODEMANIFEST веб-ячеек и requirements.md?
2. Вызван ли `goga-review-plan` и объединены ли его находки с критическими проверками исполнения?
3. Есть ли pytest без `--strict-mode` в `## Validation Commands`, и нет ли strict **нигде** в
   командах/чекбоксах плана?
4. Несёт ли каждая генерирующая Task исполняемый чекбокс прогона, строку подключения к браузеру в
   исполнимой форме и явный CRITICAL-запрет strict текстом?
5. Присутствует ли инструкция о кеше (коммитится, не чистится, проверить появление) и
   failing-test policy в каждой Task; нет ли skip/xfail где-либо?
6. Покрыты ли все Routine (ссылки на `location`) и сверены ли адреса страниц (пути относительно
   base_url; внешние — полные URL) с §1/§2?
7. Показана ли каждая находка по одной с выбором Apply/Alternative/Skip; применены ли правки
   только в plan.md?

Если хотя бы один ответ «нет» — заверши незавершённую проверку, прежде чем вернуться.
