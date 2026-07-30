# SkynetVS Architecture Roadmap V1

**Дата фиксации:** 2026-07-30  
**Статус:** LOCKED  
**Стабильная база:** `skynet-runtime-foundation-v1` → `09f8708`  
**Назначение документа:** сохранить архитектурную последовательность между чатами и не допускать скрытого расширения этапов.

---

## 1. Северная звезда проекта

SkynetVS должен со временем превзойти обычный чат-ассистент в персональной среде пользователя не только качеством ответов, а сочетанием:

- постоянного персонального контекста и памяти;
- естественного голосового взаимодействия;
- безопасного управления компьютером и приложениями;
- понимания экрана и текущей рабочей ситуации;
- способности разрабатывать, проверять и улучшать собственный код;
- контролируемого обучения на обратной связи;
- наблюдаемости, воспроизводимости и отката каждой опасной операции;
- дальнейшего восприятия физического мира через камеру и другие источники.

Цель достигается поэтапно. Автономность не должна опережать безопасность, диагностику и проверяемость.

---

## 2. Неподвижные архитектурные принципы

1. **Safety before autonomy.** Сначала ограничения, sandbox, проверки и rollback; потом самостоятельные действия.
2. **Один владелец runtime-сервиса.** `main.py` остаётся composition root и создаёт по одному экземпляру сервисов.
3. **Никаких скрытых зависимостей.** Сервисы передаются явно.
4. **Правдивый health.** Система различает `ready`, `degraded`, `disabled`, `unknown`.
5. **Production не импортирует `tools`.**
6. **Типизированные действия и проверки.** Никакого произвольного shell-кода из developer-task.
7. **Основной worktree не используется как песочница.**
8. **Каждый этап имеет фиксированный scope.** Нельзя молча добавлять в этап новые файлы.
9. **Каждый этап закрывается targeted eval, полным pipeline, commit и обновлением roadmap.**
10. **Большой перенос файлов начинается только после Architecture Inventory и карты зависимостей.**
11. **`__init__.py` не превращаются в скрытые реэкспортирующие фасады без отдельного решения.**
12. **Для тестовых инструментов сохраняется запуск из корня проекта через `python -m tools.<module>` либо совместимый стабильный фасад.**

---

## 3. Что уже завершено

### 3.1 Runtime Foundation

- Runtime Ownership and Fault Injection Audit.
- Явное владение сервисами.
- Изолированное завершение runtime-компонентов.
- Fault boundaries для действий.
- Health report и периодический health monitor.
- STT/TTS lifecycle и generation guards.

### 3.2 Safe Developer Task Contract V1

- строгая схема manifest;
- `allowed_files`;
- `base_commit`;
- SHA-256 patch;
- protected paths;
- запрет unsafe path forms;
- запрет произвольных shell-check;
- типизированные checks;
- стабильный fingerprint.

### 3.3 Foundational Package Structure V1

Завершён минимальный фундаментальный пакетный срез:

- `modules/developer/`;
- `modules/core/`;
- `modules/runtime/`;
- `modules/learning/`;
- `modules/desktop/`.

`Desktop Package Structure V1` включал только:

- `screenshot.py`;
- `typing_service.py`;
- `window_context_service.py`.

Это **не полная доменная раскладка всех файлов из `modules/`**. Файлы audio, speech, health, commands, reminders и другие будут разложены отдельным этапом.

### 3.4 Stable Baseline

```text
skynet-runtime-foundation-v1
    ↓
09f8708
```

Тег остаётся неизменным как точка до появления developer-task runtime.

---

## 4. Почему пакетный рефакторинг был нужен

Переносы не были косметикой. Они создали стабильные границы вокруг компонентов, критичных для будущего саморазвития:

- `developer` — доверенная зона, которую нельзя разрешать обычной задаче изменять;
- `core` — фундамент без зависимостей на верхние слои;
- `runtime` — режимы и корректное завершение;
- `learning` — память и promotion-механизмы;
- `desktop` — ограниченный слой взаимодействия с рабочим столом.

Ошибка состояла не в переносах, а в отсутствии явного разделения:

1. **Foundational Package Structure V1** — минимальные безопасные границы, уже завершено.
2. **Domain Package Structure V2** — полная доменная раскладка оставшихся production-модулей, ещё впереди.
3. **Tools Package Structure V1** — раскладка eval/tooling после стабилизации production-пакетов, ещё впереди.

---

## 5. Зафиксированная последовательность дальнейшей разработки

# PHASE 0 — Roadmap Lock V1

**Статус:** текущий организационный шаг.

Результат:

- этот документ добавлен в репозиторий;
- дальнейшие этапы имеют фиксированный scope;
- любое изменение порядка оформляется как отдельное `Roadmap Change`.

Следующий программный этап после фиксации документа — `Developer Task Preflight V1`.

---

# PHASE 1 — Developer Safety Kernel V1

Назначение: построить безопасное ядро выполнения изменений. Это ещё не автономный код-ассистент.

## 1.1 Developer Task Preflight V1

Полностью read-only:

- проверка правильного Git-репозитория;
- совпадение project root;
- проверка `HEAD` против `base_commit`;
- проверка чистоты worktree/index;
- существование и тип patch-файла;
- пересчёт SHA-256;
- извлечение изменяемых путей;
- сравнение с `allowed_files`;
- защита от case-collision, symlink, gitlink/submodule и `.git`;
- `git apply --check`;
- структурированный immutable report.

**Запрещено:** применять patch, clean/reset/stash, менять индекс, запускать произвольные команды.

## 1.2 Developer Task Isolated Workspace V1

- временный `git worktree`;
- строго от `base_commit`;
- уникальная папка задачи;
- основной worktree не изменяется;
- гарантированная очистка после завершения.

## 1.3 Developer Task Patch Apply V1

- patch применяется только внутри isolated workspace;
- повторно вычисляется фактический Git diff;
- проверяется итоговый scope;
- частичное применение запрещено.

## 1.4 Developer Task Typed Check Runner V1

Разрешённые типы:

- `git_diff_check`;
- `py_compile`;
- `python_module`;
- `pipeline`.

Без `shell=True`, без произвольных строк команд и без установки зависимостей.

## 1.5 Developer Task Result & Evidence V1

- структурированный итог;
- stdout/stderr;
- duration;
- список изменённых файлов;
- результаты каждой проверки;
- fingerprint задачи;
- доказательство, что основной worktree не изменён.

## 1.6 Developer Task Manual Promotion V1

- только ручное подтверждение;
- никаких автоматических merge/commit/push;
- повторная проверка в основном репозитории;
- полный pipeline;
- rollback при расхождении.

## 1.7 Developer Safety Kernel Audit V1

- fault injection;
- cleanup failures;
- stale task;
- dirty worktree;
- patch substitution;
- path escape;
- interrupted checks;
- отсутствие изменений основного worktree.

**Критерий завершения PHASE 1:** задача проходит путь manifest → preflight → isolated apply → checks → report, при этом основной worktree остаётся неизменным.

---

# PHASE 2 — Domain Package Structure V2

Назначение: завершить доменную архитектуру production-кода уже с использованием Developer Safety Kernel как dogfooding.

## 2.1 Architecture Inventory V2

До любого `git mv` создаются:

- полный список модулей;
- dependency graph;
- владелец каждого файла;
- целевой пакет;
- допустимые направления зависимостей;
- список публичных стабильных фасадов;
- порядок переносов.

## 2.2 Предварительные доменные кандидаты

Точные границы утверждаются только после Inventory V2. Возможные зоны:

- `modules/audio/`;
- `modules/speech/`;
- `modules/health/`;
- `modules/reminders/`;
- `modules/understanding/`;
- `modules/interaction/` или `modules/commands/`;
- `modules/services/`.

Нельзя переносить файл только потому, что его имя кажется подходящим. Решение определяется ответственностью и зависимостями.

## 2.3 Правила переноса

- один доменный пакет за один этап;
- отдельный commit;
- guard на отсутствие legacy path/import;
- dependency-boundary eval;
- targeted eval;
- полный pipeline;
- основной `main.py` остаётся composition root;
- отсутствие циклических зависимостей.

**Критерий завершения PHASE 2:** верхний уровень `modules/` содержит только явно одобренные composition/facade-модули, а не случайный плоский набор.

---

# PHASE 3 — Tools Package Structure V1

Назначение: привести большой набор eval/tooling к той же доменной структуре после стабилизации production-пакетов.

## 3.1 Основные правила

- `tools/pipeline.py` остаётся стабильной точкой входа;
- сохраняется совместимый запуск из корня;
- production-код по-прежнему не импортирует `tools`;
- eval группируются по доменам;
- developer safety eval и package-boundary eval остаются protected;
- pipeline registry заменяет хаотичные прямые связи;
- перенос идёт по одному домену.

## 3.2 Возможная целевая форма

Точная форма утверждается отдельным Tools Inventory. Например:

```text
tools/
├── pipeline.py
├── evals/
│   ├── audio/
│   ├── speech/
│   ├── runtime/
│   ├── learning/
│   ├── desktop/
│   ├── developer/
│   └── ...
└── ...
```

При необходимости старые `python -m tools.<module>` сохраняются тонкими совместимыми фасадами до отдельного cleanup.

**Критерий завершения PHASE 3:** tooling отражает production-домены, но внешняя точка запуска pipeline остаётся стабильной.

---

# PHASE 4 — Voice Assistant Foundation Completion v1.x

Цель: надёжный персональный голосовой помощник для ежедневной работы.

Основные направления:

- устойчивые STT/NLU/TTS;
- TextNormalizer и понимание искажений распознавания;
- единый action contract;
- permissions и risk classes;
- безопасные действия Windows;
- режим диктовки и редактирование;
- таймеры и напоминания;
- аудиоустройства и media control;
- контекст диалога;
- health/telemetry;
- журналирование и воспроизводимость;
- plugin/capability registry без `if`-хаоса.

---

# PHASE 5 — Learning and Personal Memory v1.x–v2.x

- correction memory;
- feedback analysis;
- promotion engine;
- hard-case inbox;
- offline regression eval;
- персональная долговременная память;
- извлечение релевантного контекста;
- controlled learning;
- запрет promotion без метрик и регрессионных проверок;
- rollback обучающих изменений.

---

# PHASE 6 — Screen Understanding v2.x

- Windows UI Automation / accessibility tree как основной структурный источник;
- screenshot как визуальный источник;
- сменный OCR-слой;
- visual grounding;
- модель текущего окна, элементов и состояния;
- планирование действий по экрану;
- подтверждение опасных действий;
- журнал выполненных экранных операций.

---

# PHASE 7 — Code Assistant and Self-Review v3.x

На базе Developer Safety Kernel:

- индекс репозитория;
- архитектурная карта;
- декомпозиция задачи;
- генерация patch;
- тесты;
- статический анализ;
- self-review;
- critic pass;
- risk classification;
- isolated execution;
- сравнение результатов;
- ручной promotion на первых версиях;
- постепенное разрешение ограниченных автономных задач.

---

# PHASE 8 — Real-World Perception v4.x

- камера;
- объекты и сцены;
- пространственная память;
- привязка речи к реальному миру;
- безопасное планирование физических действий;
- многомодальный контекст.

---

# PHASE 9 — Controlled Self-Improvement

- поиск проблем по telemetry и learning data;
- формирование гипотез улучшения;
- эксперимент в sandbox;
- автоматические eval;
- сравнение с baseline;
- запрет promotion при ухудшении;
- rollback;
- аудит причин каждого изменения;
- постепенное расширение автономности только на доказанно безопасных классах задач.

---

## 6. Как SkynetVS должен «превзойти ChatGPT»

Цель не начинается с обучения собственного foundation model с нуля. Сначала SkynetVS должен стать сильнее обычного чата в персональной среде благодаря:

- постоянной памяти о пользователе и проектах;
- пониманию текущего экрана и программ;
- реальным действиям, а не только советам;
- голосовому взаимодействию без ручного копирования;
- безопасной разработке и самопроверке;
- накоплению локального опыта;
- воспроизводимым экспериментам;
- возможности использовать разные локальные и внешние модели как сменные reasoning-компоненты.

Общий интеллект модели является одним компонентом системы, а не всей системой.

---

## 7. Правила управления roadmap

Для каждого этапа до изменения кода фиксируются:

```text
Stage
Goal
Why now
In scope
Out of scope
Files expected to change
Threat model
Acceptance criteria
Targeted checks
Full pipeline
Commit name
Tag/snapshot policy
```

### Запрещено

- молча расширять scope;
- переносить «похожие» файлы без inventory;
- перескакивать к следующему этапу до acceptance;
- считать полный pipeline доказательством того, что реализовано то, чего eval не проверяет;
- менять стабильный тег без отдельной причины;
- смешивать архитектурный refactor и новую функцию в одном commit.

### Roadmap Change

Любое изменение порядка оформляется явно:

```text
Roadmap Change N
Причина
Что меняется
Что не меняется
Риски
Новые критерии
```

---

## 8. Текущая точка

```text
[LOCKED BASELINE] skynet-runtime-foundation-v1 → 09f8708

[NEXT ORGANIZATIONAL ACTION]
Добавить этот roadmap в репозиторий.

[NEXT CODE STAGE]
Developer Task Preflight V1.

[PLANNED AFTER SAFETY KERNEL]
Domain Package Structure V2.

[PLANNED AFTER PRODUCTION PACKAGES]
Tools Package Structure V1.
```

До начала `Developer Task Preflight V1` никакие дополнительные файлы по пакетам не переносятся.
