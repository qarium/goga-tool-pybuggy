---
name: goga-tool-pybuggy-web-automate-cells-assembly
description: Assembles and saves the web test cells architecture plan to the path printed by `goga history path -f arch.md`
---

# Pybuggy Web Topic Cells — Assembly

## Identity

Ты собираешь финальный план архитектуры тест-ячеек из утверждённых CODEMANIFEST и сохраняешь его в
файл. План — единственный источник истины для материализации (apply) и ревью.

## Core Principle

Ничего не добавлять и не менять: план собирается из [CONTRACTS_REPORT] и [CELL_MAP_REPORT] дословно;
каждый кейс обязан быть покрыт.

---

## Algorithm

1. Собери входы: [CONTRACTS_REPORT] (утверждённые CODEMANIFEST), [CELL_MAP_REPORT] (ячейки,
   TC → Routine → ячейка).
2. Собери план:
   - **Implementation order** — перечень ячеек `tests/web/<slug>/` (в порядке cell-map; существующие
     ячейки помечены — merge при apply);
   - **CODEMANIFEST каждой ячейки** — полный, дословно из [CONTRACTS_REPORT];
   - **Cell-specific usages** — таблица ключей по ячейкам;
   - **Coverage map** — TC → Routine → ячейка (из cell-map);
   - **Verification checklist** — что проверить после материализации (`goga lint`, `goga schema tests/`,
     все ячейки созданы, кеши шагов появятся при первом прогоне).
3. Проверь полноту: каждый TC из testcases.md присутствует в coverage map (напрямую или вариантом
   параметризованной Routine); каждая Routine из CODEMANIFEST-ов встречается в coverage map.
4. Сохрани [CELLS_PLAN] по пути, напечатанному `goga history path -f arch.md`
   (перезаписывай при повторных запусках).

STOP if:

- план неполон (нет CODEMANIFEST ячейки, потерян кейс);
- кейс остался непокрытым.

---

## Output Format

Сохрани результат по пути, напечатанному `goga history path -f arch.md`. Содержимое файла следует
формату ниже. Fill in every section. Empty sections are forbidden.

```md
### Web test cells architecture plan: [Topic name]

## Implementation Order

| # | Ячейка | Путь | Статус |
|---|--------|------|--------|
| 1 | <slug> | tests/web/<slug>/ | новая / существующая (merge) |

## Cell-specific Usages

| Ячейка | key | path | назначение |
|--------|-----|------|------------|
| […] | `<key>` | .goga/usages/cooks/<key>.md | […] |

[Если cell-specific usages нет — `none`]

## CODEMANIFEST: <slug> (tests/web/<slug>/)

[Полный CODEMANIFEST — Header / --- / Body (Routines с шагами-предложениями) / --- / Footer]

## CODEMANIFEST: <следующая ячейка>

[…]

## Coverage Map

| TC | Routine | Ячейка |
|----|---------|--------|
| TC-1 | test_search_finds_results | catalog |
| TC-2, TC-3 | test_search_query_variant (варианты) | catalog |

## Verification Checklist

- [ ] Все ячейки плана материализованы в tests/web/<slug>/
- [ ] `goga lint` зелёный
- [ ] `goga schema tests/` показывает новые ячейки
- [ ] Каждый TC покрыт Routine (coverage map полна)
- [ ] После первого прогона кеши шагов появятся в tests/web/<cell>/test_<name>/ — не удалять
```
