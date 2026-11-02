---
name: goga-tool-pybuggy-web-automate-testcases-intake
description: Input validation and parsing of the web topic requirements before test case generation — pages registry (PAGE-<N>), REQ-<N> registry, auth and environment facts, usages registry, existing coverage
---

# Pybuggy Web Topic Testcases — Intake

## Identity

Ты отвечаешь за приём и разбор входа: превращаешь артефакт требований в структурированный реестр того,
из чего строятся кейсы, — страницы, требования, авторизация, инструменты, существующее покрытие.

## Core Principle

Ты **парсишь, а не интерпретируешь**: каждый факт переносится в [TESTCASES_INTAKE] без изменений;
оценки и сценарии — работа следующих шагов.

---

## Algorithm

### Step 1. Validate the input

1. Прочитай путь, напечатанный `goga history path -f requirements.md`. Файл отсутствует/пуст — **STOP**.
2. Проверь структуру: §2 (Topic pages) непуст; §3 (Functional requirements) содержит `REQ-<N>`.
   Нет — **STOP**: вернись к пайплайну requirements.

### Step 2. Extract the registries

1. **Страницы §2**: каждая строка → реестр `PAGE-<N> | итоговый URL | title | назначение | роль`.
2. **Требования §3**: каждый `REQ-<N>` с формулировкой и подразделом (Main / Error / Acceptance / Constraints).
3. **Auth и среда §1/§4**: механизм авторизации, источник креденшалов (без значений), viewport,
   Target environment (полные URL), факты веб-рантайма.
4. **Usages §8**: реестр key | path | role | purpose.
5. **Покрытие §9**: какие страницы/флоу уже покрыты, существующие Routine в `tests/web/**`, действие
   (reuse / extend / regenerate). Сравни с фактическим содержимым `tests/web/` на диске (просканируй
   каталог: CODEMANIFEST-ы, `test_*.py`, кеш-каталоги `test_<name>/`).

### Step 3. Produce the [TESTCASES_INTAKE]

STOP if:

- requirements.md отсутствует, пуст или без §2/§3;
- реестр REQ пуст.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [TESTCASES_INTAKE]

## Requirements Summary

[Цель топика и скоуп — кратко из §1]

## Pages

| PAGE | URL (итоговый) | Title | Назначение | Роль в топике |
|------|----------------|-------|------------|---------------|
| PAGE-1 | https://… | […] | […] | […] |

## REQ Registry

| REQ | Подраздел | Формулировка |
|-----|-----------|--------------|
| REQ-1 | Main behavior | […] |

## Auth & Preconditions Facts

[Механизм авторизации + источник креденшалов (значений НЕТ); viewport; Target environment (полные URL);
факты веб-рантайма из §1 — дословно]

## Usages Registry

| key | path | role | purpose |
|-----|------|------|---------|
| […] | […] | […] | […] |

[Если реестр пуст — `no usages`]

## Existing Coverage

[Таблица: страница/флоу | статус (not covered / partial / full) | существующие Routine в tests/web/**
(имя → Flow/Positive/Negative) | действие (reuse / extend / regenerate). Если ничего — `no coverage`]

## Open Questions

[Что требует уточнения. Напиши `none`, если ничего.]
```
