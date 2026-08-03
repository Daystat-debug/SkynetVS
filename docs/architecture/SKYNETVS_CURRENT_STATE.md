# SkynetVS Current State

**Дата обновления:** 2026-07-31
**Модель статусов:** `VERIFIED`, `PLANNED`, `DEFERRED`, `UNVERIFIED`

---

## 1. Источники истины

Использовать источники в следующем порядке:

1. Текущее состояние Git и текущий код проекта.
2. Последние успешно завершённые targeted checks и полные pipeline-логи.
3. Этот файл: `docs/architecture/SKYNETVS_CURRENT_STATE.md`.
4. `docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`.
5. История чата и предположения.

Если источники противоречат друг другу, нельзя молча объединять их. Нужно явно зафиксировать противоречие и отдать приоритет Git, коду и проверкам.

---

## 2. VERIFIED — текущее состояние репозитория

- Ветка: `main`.
- Проверенный code HEAD до следующего documentation update: `eeb50ce`.
- Название code HEAD: `feat: add developer task patch scope policy preflight`.
- `origin/main`: указывает на тот же commit `eeb50ce`.
- Предшествующий documentation commit: `94ecb2d docs: update SkynetVS state after isolated patch index preflight`.
- Рабочее дерево после commit и push: чистое; `git status --short` ничего не выводит.
- Стабильный foundation-тег: `skynet-runtime-foundation-v1`.
- Foundation-тег намеренно остаётся на `09f8708` как проверенная runtime-база до отдельного решения о новой developer-safety точке.
- Roadmap находится по каноническому пути:
  - `docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`.
- Current-state находится по каноническому пути:
  - `docs/architecture/SKYNETVS_CURRENT_STATE.md`.

После коммита этой обновлённой версии файла фактический `HEAD` станет новым documentation commit. Проверенный code commit `eeb50ce` останется непосредственно под ним. Git остаётся источником истины.

---

## 3. Общая цель проекта

Создать SkynetVS как персонального голосового ассистента, который со временем сможет превзойти обычный чат-ассистент в персональной среде пользователя за счёт сочетания:

- постоянного персонального и проектного контекста;
- естественного голосового взаимодействия;
- безопасного управления компьютером и приложениями;
- понимания экрана и текущей рабочей ситуации;
- контролируемой разработки и саморевью собственного кода;
- обучения на обратной связи с защитой от регрессий;
- наблюдаемости, воспроизводимости, доказательств и rollback;
- будущего мультимодального восприятия физического мира.

Автономность не должна развиваться быстрее безопасности, диагностики, изоляции, проверки и возможности отката.

---

## 4. VERIFIED — завершённые фундаментальные этапы

- Runtime Ownership and Fault Injection Audit.
- Safe Developer Task Contract V1.
- Developer Package Structure V1.
- Core Package Structure V1.
- Runtime Package Structure V1.
- Learning Package Structure V1.
- Desktop Package Structure V1.
- Roadmap Lock V1.
- Стабильный foundation-тег `skynet-runtime-foundation-v1` на `09f8708`.

`Desktop Package Structure V1` включал только:

- `modules/desktop/screenshot.py`;
- `modules/desktop/typing_service.py`;
- `modules/desktop/window_context_service.py`.

Полная доменная раскладка audio, speech, health, reminders, commands и остальных плоских модулей отложена до Domain Package Structure V2.

---

## 5. VERIFIED — Developer Task Preflight V1A

### Repository Gate

**Статус:** завершён, проверен, закоммичен и отправлен в `origin/main`.

Commit:

```text
6e2aa78 feat: add developer task repository preflight
```

V1A реализует read-only проверку:

- точного корня Git-репозитория;
- non-bare worktree;
- разрешения `HEAD` и `manifest.base_commit` в commit;
- совпадения `HEAD == base_commit`;
- чистоты index и worktree;
- staged, unstaged, untracked, conflict и dirty-submodule состояний;
- нейтрализации унаследованных Git redirection/trace переменных;
- Git timeout, отсутствия Git и ошибки запуска;
- immutable структурированного отчёта со стабильными issue codes.

---

## 6. VERIFIED — Developer Task Preflight V1B

### Patch Integrity Gate

**Статус:** завершён, проверен, закоммичен и отправлен в `origin/main`.

Commit:

```text
cb7c6c5 feat: add developer task patch integrity preflight
```

V1B реализует:

- обязательный успешный V1A-report;
- согласованность manifest fingerprint и repository root;
- отдельный `task_root`, не пересекающийся с project repository;
- запрет symlink, junction и Windows reparse point для `task_root` и patch;
- regular-file validation;
- ограничение patch размером `5 MiB`;
- точное бинарное чтение в immutable `bytes`;
- защиту от подмены между metadata check, `open`, чтением и финальным `fstat`;
- SHA-256 именно прочитанных байтов;
- immutable `DeveloperTaskPatchSnapshot`;
- исключение patch bytes из `repr` и `to_dict()`;
- переносимую file-version проверку без Windows `st_ctime`.

---

## 7. VERIFIED — Developer Task Preflight V1C1

### Isolated Patch Index Gate

**Статус:** завершён, проверен, закоммичен и отправлен в `origin/main`.

Commit:

```text
b14486a feat: add developer task isolated patch index preflight
```

V1C1 реализует:

- обязательные успешные V1A- и V1B-reports;
- повторную проверку fingerprints, repository root, base commit и snapshot bytes;
- отдельный временный `GIT_INDEX_FILE`;
- отдельный временный `GIT_OBJECT_DIRECTORY`;
- read-only baseline objects через `GIT_ALTERNATE_OBJECT_DIRECTORIES`;
- загрузку `base_commit` во временный index без обновления worktree;
- передачу Git только immutable patch bytes через stdin;
- отклонение explicit Git copy operation;
- фактическое применение patch только к временному index;
- machine-readable NUL-delimited raw diff и resulting index listing;
- нормализацию rename в `D old_path + A new_path` через `--no-renames`;
- поддержку SHA-1 и SHA-256 object IDs;
- фиксацию modes `100644`, `100755`, `120000`, `160000` как фактов;
- отклонение небезопасных repository-relative и Windows-unsafe путей;
- structured failures для Git, parsing, temporary workspace и cleanup;
- доказательство неизменности настоящего worktree, index и object store;
- immutable `DeveloperTaskPatchIndexChange` и `DeveloperTaskPatchIndexPreflightReport`.

### Решение по applicability

Успешное фактическое применение **точных immutable patch bytes** к временному index, инициализированному из `base_commit`, уже является более сильным доказательством применимости, чем отдельный повторный `git apply --check`.

Поэтому V1D не должен второй раз запускать Git только ради дублирующей проверки. Это implementation refinement внутри утверждённого read-only Preflight V1, а не расширение scope.

---

## 8. VERIFIED — Developer Task Preflight V1C2

### Patch Scope Policy Gate

**Статус:** завершён, проверен, закоммичен и отправлен в `origin/main`.

Commit:

```text
eeb50ce feat: add developer task patch scope policy preflight
```

Состав commit:

```text
A  modules/developer/developer_task_patch_scope.py
A  tools/eval_developer_task_patch_scope.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

V1C2 реализует pure policy без Git и filesystem execution:

- повторную canonical validation manifest;
- согласованность manifest fingerprint и V1C1 evidence;
- внутреннюю проверку `changes`, `changed_files` и resulting index;
- `allowed_files` как максимальную разрешённую область изменения;
- точное совпадение регистра пути с canonical allowlist;
- обязательное разрешение old и new paths для rename;
- блокировку case-only rename;
- блокировку Windows case-collisions среди changed paths и resulting index;
- блокировку symlink mode `120000` на old/new side;
- блокировку gitlink/submodule mode `160000` на old/new side;
- блокировку Git object type change status `T`;
- разрешение regular modes `100644` и `100755`;
- разрешение обычных add, modify, delete и executable-bit change при соблюдении allowlist;
- immutable `DeveloperTaskPatchScopeCollision` и `DeveloperTaskPatchScopePreflightReport`.

---

## 9. VERIFIED — проверки V1A + V1B + V1C1 + V1C2

Targeted flow `developer_task_preflight`:

- package boundaries: `28/28`, ошибок `0`;
- developer task contract: `18/18`, ошибок `0`;
- repository preflight V1A: `22/22`, ошибок `0`;
- patch integrity preflight V1B: `29/29`, ошибок `0`;
- isolated patch index preflight V1C1: `34/34`, ошибок `0`;
- patch scope policy preflight V1C2: `36/36`, ошибок `0`;
- финал: `Flow 'developer_task_preflight' completed successfully`.

Полный flow `check`:

- завершён успешно;
- V1A, V1B, V1C1 и V1C2 включены в общий pipeline;
- регрессий в NLU, STT, TTS, audio, reminders, runtime и package boundaries не обнаружено.

Подтверждающие логи:

```text
data/logs/pipeline/20260731_185503_developer_task_preflight.log
data/logs/pipeline/20260731_190152_check.log
```

---

## 10. PLANNED — текущий программный этап

# Developer Task Preflight V1D — Composition and Audit

**Статус:** архитектурная граница утверждена; патч подготовлен; в проект ещё не применён.

### Почему V1D выполняется сейчас

Отдельные gates уже доказали свои локальные свойства, но пока отсутствует один честный публичный API, который:

- сначала canonical-validates manifest;
- запускает V1A → V1B → V1C1 → V1C2 строго в фиксированном порядке;
- останавливается на первом отказе;
- не выдаёт patch bytes и changed files при частичном успехе;
- структурирует неожиданные исключения каждого gate;
- проверяет тип возвращаемого stage-report;
- финально сверяет всю цепочку evidence;
- возвращает единый immutable report;
- доказывает end-to-end отсутствие изменений настоящего worktree, index и object store.

---

## 11. In scope — V1D

- Новый composition-модуль внутри `modules/developer`.
- Общий публичный API:

```python
run_developer_task_preflight(
    manifest: DeveloperTaskManifest,
    *,
    project_root: Path,
    task_root: Path,
) -> DeveloperTaskPreflightReport
```

- Canonical manifest validation до любого Git/filesystem gate.
- Фиксированный порядок:

```text
manifest
repository
patch_integrity
patch_index
patch_scope
composition
```

- Fail-closed short-circuit после первого неуспешного gate.
- Structured boundary для неожиданных `Exception`, но не для `BaseException`.
- Проверка типа каждого stage-report.
- Final chain validation:
  - fingerprints;
  - repository roots;
  - `HEAD == resolved_base_commit`;
  - patch size/hash/content;
  - V1C1 changed files;
  - V1C2 changed files и allowlist;
  - отсутствие unauthorized/case/symlink/gitlink/type-change/collision evidence.
- Immutable `DeveloperTaskPreflightReport`.
- `report.patch`, `report.changed_files`, `report.repository_root` и `report.base_commit` доступны только при полном `report.ok`.
- `to_dict()` не содержит patch bytes.
- End-to-end eval с доказательством неизменности настоящих:
  - worktree;
  - Git index;
  - object store;
  - repository status.
- Fault injection:
  - invalid manifest;
  - validator exception;
  - failure каждого gate;
  - exception каждого gate;
  - неправильный report type;
  - stale/mismatched final evidence;
  - forged composite report;
  - overlapping `task_root`.
- Подключение composition eval в targeted flow и полный `check`.

---

## 12. Out of scope — V1D

- Новый отдельный `git apply --check`, дублирующий V1C1.
- Применение patch к основному worktree.
- Создание isolated `git worktree` для выполнения задачи.
- Применение patch внутри будущего isolated workspace.
- Запуск checks из manifest.
- Установка зависимостей.
- Commit, merge, promotion или push результата developer-task.
- Автоматическое исправление manifest или allowlist.
- Изменение существующих gates V1A–V1C2 без доказанной ошибки.

Следующий этап после полного Preflight V1 — `Developer Task Isolated Workspace V1`.

---

## 13. Принятый API V1D

Файл:

```text
modules/developer/developer_task_preflight_composition.py
```

Публичные immutable-типы и функции:

```python
DeveloperTaskPreflightReport
run_developer_task_preflight(...)
```

Report содержит:

```text
manifest_fingerprint
failed_stage
completed_stages
repository_report
patch_integrity_report
patch_index_report
patch_scope_report
issues
```

Безопасные derived properties:

```text
ok
issue_codes
repository_root
base_commit
changed_files
patch
```

При любом неполном или несогласованном результате безопасные derived properties возвращают пустые значения, а `ok == False`.

---

## 14. Ожидаемые файлы V1D

```text
A  modules/developer/developer_task_preflight_composition.py
A  tools/eval_developer_task_preflight_composition.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

Не изменяются:

```text
modules/developer/developer_task_contract.py
modules/developer/developer_task_validator.py
modules/developer/developer_task_preflight.py
modules/developer/developer_task_patch_integrity.py
modules/developer/developer_task_patch_index.py
modules/developer/developer_task_patch_scope.py
main.py
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
```

---

## 15. PLANNED — targeted checks V1D

```text
python -m py_compile \
    modules/developer/developer_task_preflight_composition.py \
    tools/eval_developer_task_preflight_composition.py \
    tools/eval_package_boundaries.py \
    tools/pipeline.py

python -m tools.eval_package_boundaries
python -m tools.eval_developer_task_contract
python -m tools.eval_developer_task_preflight
python -m tools.eval_developer_task_patch_integrity
python -m tools.eval_developer_task_patch_index
python -m tools.eval_developer_task_patch_scope
python -m tools.eval_developer_task_preflight_composition
python tools/pipeline.py developer_task_preflight
```

Ожидаемые summaries:

```text
package boundaries:                 28/28
contract:                           18/18
V1A repository:                     22/22
V1B integrity:                      29/29
V1C1 index:                         34/34
V1C2 scope policy:                  36/36
V1D composition and audit:          19/19
developer_task_preflight flow:      completed successfully
```

После targeted checks:

```text
git diff --check
python tools/pipeline.py check
```

---

## 16. Критерии завершения V1D и полного Preflight V1

V1D и `Developer Task Preflight V1` считаются завершёнными только если:

1. общий API canonical-validates manifest до runtime gates;
2. gates выполняются строго в утверждённом порядке;
3. первый отказ останавливает цепочку;
4. unexpected gate errors структурированы;
5. неверные stage report types блокируются;
6. final evidence chain повторно проверяется;
7. partial report не раскрывает verified patch/changed files как разрешённый результат;
8. end-to-end audit подтверждает неизменность реального repository state;
9. V1D eval проходит полностью;
10. V1A–V1C2 не регрессируют;
11. package boundaries проходят;
12. targeted flow проходит;
13. полный `check` проходит;
14. `git diff --check` не сообщает ошибок;
15. code commit содержит только четыре ожидаемых файла;
16. code commit отправлен в `origin/main`;
17. `SKYNETVS_CURRENT_STATE.md` обновлён отдельным documentation commit.

Предлагаемое имя code commit:

```text
feat: add complete developer task preflight composition
```

После закрытия V1D отдельно решается вопрос о создании нового тега, например `skynet-developer-preflight-v1`. Foundation-тег `skynet-runtime-foundation-v1` не переносится.

---

## 17. DEFERRED — после полного Preflight V1

- Developer Task Isolated Workspace V1.
- Developer Task Patch Apply V1.
- Developer Task Typed Check Runner V1.
- Developer Task Result & Evidence V1.
- Developer Task Manual Promotion V1.
- Developer Safety Kernel Audit V1.
- Domain Package Structure V2.
- Tools Package Structure V1.

---

## 18. Архитектурные решения, которые нельзя молча пересматривать

- Foundation-тег остаётся на `09f8708` до отдельного решения.
- V1A, V1B, V1C1 и V1C2 сохраняют отдельные ответственности.
- V1D является orchestrating/composition boundary, а не новым монолитным Git gate.
- V1D не дублирует уже доказанную V1C1 applicability отдельным Git-запуском.
- Patch и changed files считаются verified только при полном `DeveloperTaskPreflightReport.ok`.
- Partial success не является разрешением на выполнение задачи.
- `task_root` остаётся вне project repository.
- Основной worktree никогда не используется как песочница.
- Нельзя молча расширять scope без Roadmap Change или явно зафиксированного implementation refinement.
- Зелёный полный pipeline доказывает только реально подключённые eval и guards.

---

## 19. Следующее точное действие

1. Сохранить эту версию как:

```text
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

2. Создать отдельный documentation commit:

```text
docs: update SkynetVS state after patch scope preflight
```

3. Убедиться, что рабочее дерево чистое.
4. Проверить SHA-256 подготовленного V1D patch.
5. Выполнить стандартный `git apply --check`.
6. При Windows CRLF context mismatch использовать только утверждённый `--ignore-space-change` fallback.
7. Применить V1D patch.
8. Запустить targeted checks.
9. Запустить полный `check`.
10. До успешных проверок не создавать V1D code commit.

---

## 20. Режим модели

Текущий рекомендуемый режим: **Pro Standard**.

Причина: V1D фиксирует общий fail-closed security boundary и доказательство всей цепочки. После успешного V1D code commit, полного pipeline и обновления current-state можно вернуться на режим **«Очень высокий»** для механической реализации `Developer Task Isolated Workspace V1`, пока не появится новая архитектурная развилка.

---

## 21. Файлы для нового чата при необходимости handoff

Обязательно:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Дополнительно:

```text
data/logs/pipeline/20260731_185503_developer_task_preflight.log
data/logs/pipeline/20260731_190152_check.log
```

В новом чате сначала читать документы и логи, затем продолжать с раздела **«Следующее точное действие»**, не восстанавливая roadmap заново по памяти.
