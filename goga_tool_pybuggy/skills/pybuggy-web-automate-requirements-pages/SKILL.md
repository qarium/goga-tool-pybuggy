---
name: goga-tool-pybuggy-web-automate-requirements-pages
description: Binds the confirmed topic pages to page objects — derives each page's path against the site base URL, agrees the page names with the user (WAIT), scaffolds the modules via `goga tool pybuggy page generate` (pages/** — a BasePage subclass plus its page_<name> fixture), and produces the page-artifact registry for requirements §2
---

# Pybuggy Web Topic Requirements — Pages

## Identity

Ты связываешь подтверждённые страницы топика с page-объектами pybuggy. Для каждой страницы ты:

- выводишь её path относительно базового URL сайта;
- согласуешь с пользователем имя страницы;
- генерируешь модуль командой `goga tool pybuggy page generate`;
- фиксируешь артефакты.

Артефакты станут адресацией навигационных шагов рутин (активационный вызов `page_<name>()`):

- фикстура `page_<name>`;
- класс `<Name>Page`;
- модуль `pages/**`.

## Core Principle

- Page-объект — единственный способ навигации на страницы тестируемого сайта.
- Базовый URL живёт в директиве `site.base_url` (web.yml); страница добавляет свой path.
- Path выводится только из итоговых URL досье [EXPLORE_REPORT].
- Имя страницы — решение пользователя (фикстура и класс — контракт, на который ссылаются рутины и ячейки).
- Внешние страницы (иной origin) и адреса с query-параметрами page-объектами не становятся — их навигация остаётся шагом-предложением с полным URL.

---

## Algorithm

### Step 1. Load context

1. [INTAKE_REPORT] — `site.base_url` из web.yml (дословно, Jinja2-шаблон).
2. [EXPLORE_REPORT] — досье PAGE-<N>: итоговые URL после редиректов.
3. [ELABORATION_REPORT] — подтверждённый набор страниц (Page Purposes).

### Step 2. Derive the paths

Для каждой подтверждённой PAGE-<N> из её итогового URL:

1. **Origin-сверка**: сравни origin итогового URL (scheme+host+port) с origin базового URL
   сайта. Шаблон `site.base_url` без плейсхолдеров — сравнение напрямую; с плейсхолдерами —
   сравнивай с base окружения, в котором шло исследование (origin итоговых URL досье), и
   зафиксируй соответствие. Иной origin — **внешняя страница**: page-объект неприменим,
   навигация литеральная (полный URL в предложении шага).
2. **Path**: часть итогового URL после origin — с ведущим `/`; query-часть и фрагмент
   (`?…`, `#…`) отделяются (страница — её path-часть; query создаются действиями теста).
   Path без непустого сегмента (корневая страница, `""` после слэша) — CLI не генерирует
   (`path carries no non-empty segment`): корневая страница помечается литеральной
   (полный URL — сам base).
3. **Предложи имя**: короткое `snake_case` от назначения страницы из досье (`login`,
   `catalog`, `checkout`); одно слово — лучший вариант. Имя задаёт нейминг артефактов:
   фикстура `page_<name>`, класс `<Name>Page`, модуль `pages/[<сегменты path кроме
   последнего>]<name>_page.py` (без name последний сегмент path сам становится стемом файла:
   `/admin/api/v1/mocks` → `pages/admin/api/v1/mocks_page.py`; с name=`auth` для
   `/admin/login` → `pages/admin/auth_page.py`).

### Step 3. WAIT — согласовать имена

Покажи таблицу целиком текстом, затем AskUserQuestion (один вопрос, 2–4 варианта):

- **question**: «Page-объекты: <таблица>. Утверждаем?»
- **options**: «Утверждаю» / «Правка имён» (какие — уточни текстом) / «Исключить страницу»
  (литеральная навигация; какая — уточни).

Таблица: PAGE | path | name | фикстура | класс | модуль.

### Step 4. Generate the modules

Из корня целевого проекта (каталог с `.goga/`):

1. По каждой утверждённой строке выполни `goga tool pybuggy page generate <path> <name>`
   (без `-f`).
2. Существующий модуль пропускается молча — прочитай его:
   - фикстура конструирует класс с тем же `path`, фикстура и класс названы ожидаемо → «существует, годен» (методы-сценарии внутри сохраняются — их трогать нельзя);
   - расхождение (другой path/имена) — предупреждение в отчёте;
   - перезапись только по явному решению пользователя (`-f` стирает методы-сценарии).
3. Проверь артефакты на диске: файл модуля существует, `__init__.py`-маркеры на пути,
   фикстура/класс соответствуют таблице. Загрузка фикстур — автоматическая: `pages/` — дефолтный
   пакет фикстур web-вида (web-плагин обнаруживает модули сам; `loader:`-секция не нужна).

### Step 5. Produce the [PAGES_REPORT]

STOP if:

- `site.base_url` не задан или пуст — верни в intake (там директива обязательна);
- CLI `goga tool pybuggy page generate` недоступен или упал с ошибкой валидации;
- пользователь не утверждает имена после итераций правок.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [PAGES_REPORT]

## Site Base URL

[site.base_url из web.yml дословно (шаблон); origin исследованного окружения: <scheme://host[:port]>]

## Page Objects

| PAGE | Path | Name | Фикстура | Класс | Модуль | Статус |
|------|------|------|----------|-------|--------|--------|
| PAGE-1 | /login | login | page_login | LoginPage | pages/login_page.py | создан / существует, годен |

[Подтверждённые page-объекты. Статус — результат шага генерации.]

## Literal Navigation

| PAGE / URL | Причина |
|------------|---------|
| https://… | внешний origin / query-адрес / корневая страница |

[Страницы и адреса без page-объекта — навигация полным URL в предложении шага. Напиши `none`, если таких нет.]

## User Decision

[Утверждено / изменено — что именно подтвердил пользователь]

## Warnings

[Коллизии с существующими модулями, перезаписи, странности path. Напиши `none`, если ничего.]
```
