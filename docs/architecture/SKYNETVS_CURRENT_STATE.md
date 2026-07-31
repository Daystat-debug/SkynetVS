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
- Проверенный code HEAD до следующего documentation update: `b14486a`.
- Название code HEAD: `feat: add developer task isolated patch index preflight`.
- `origin/main`: указывает на тот же commit `b14486a`.
- Предшествующий documentation commit: `388409b docs: update SkynetVS state after patch integrity preflight`.
- Рабочее дерево после commit и push: чистое; `git status --short` ничего не выводит.
- Стабильный foundation-тег: `skynet-runtime-foundation-v1`.
- Foundation-тег намеренно остаётся на `09f8708` как проверенная runtime-база до завершения Developer Safety Kernel.
- Roadmap находится по каноническому пути:
  - `docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`.
- Current-state находится по каноническому пути:
  - `docs/architecture/SKYNETVS_CURRENT_STATE.md`.

После коммита этой обновлённой версии файла фактический `HEAD` станет новым documentation commit. Проверенный code commit `b14486a` при этом останется в истории непосредственно под documentation commit. Git остаётся источником истины.

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

## 4. VERIFIED — завершённые архитектурные этапы

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

Состав commit:

```text
A  modules/developer/developer_task_patch_index.py
A  tools/eval_developer_task_patch_index.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
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
- применение patch только к временному index;
- machine-readable NUL-delimited raw diff и resulting index listing;
- нормализацию rename в `D old_path + A new_path` через `--no-renames`;
- поддержку SHA-1 и SHA-256 object IDs;
- фиксацию modes `100644`, `100755`, `120000`, `160000` как фактов;
- отклонение небезопасных repository-relative и Windows-unsafe путей;
- structured failures для Git, parsing, temporary workspace и cleanup;
- доказательство неизменности настоящего worktree, index и object store;
- immutable `DeveloperTaskPatchIndexChange` и `DeveloperTaskPatchIndexPreflightReport`.

---

## 8. VERIFIED — проверки V1A + V1B + V1C1

Targeted flow `developer_task_preflight`:

- package boundaries: `28/28`, ошибок `0`;
- developer task contract: `18/18`, ошибок `0`;
- repository preflight V1A: `22/22`, ошибок `0`;
- patch integrity preflight V1B: `29/29`, ошибок `0`;
- isolated patch index preflight V1C1: `34/34`, ошибок `0`;
- финал: `Flow 'developer_task_preflight' completed successfully`.

Полный flow `check`:

- завершён успешно;
- V1A, V1B и V1C1 включены в общий pipeline;
- регрессий в NLU, STT, TTS, audio, reminders, runtime и package boundaries не обнаружено.

Подтверждающие логи:

```text
data/logs/pipeline/20260731_142801_developer_task_preflight.log
data/logs/pipeline/20260731_142820_check.log
```

---

## 9. PLANNED — текущий программный этап

# Developer Task Preflight V1C2 — Patch Scope Policy Gate

**Статус:** архитектурная граница и threat model утверждены; патч подготовлен; в проект ещё не применён.

### Почему V1C2 выполняется сейчас

V1C1 безопасно получил факты Git, но намеренно не принял security-решение. До V1C2 ещё не доказано:

- что каждый фактически изменяемый путь входит в `manifest.allowed_files`;
- что регистр пути точно совпадает с allowlist;
- что rename разрешён и для source, и для destination;
- что patch не содержит case-only rename;
- что resulting index не содержит Windows case-collisions;
- что patch не добавляет, не меняет и не удаляет symlink;
- что patch не добавляет, не меняет и не удаляет gitlink/submodule;
- что patch не выполняет Git object type change.

V1C2 является чистым policy-слоем. Он не запускает Git, не читает файлы и не создаёт временные каталоги.

---

## 10. In scope — V1C2

- Принимать уже валидированный `DeveloperTaskManifest`.
- Принимать успешный immutable `DeveloperTaskPatchIndexPreflightReport` из V1C1.
- Повторно валидировать manifest contract для защиты от вручную сконструированного dataclass.
- Проверять manifest fingerprint.
- Проверять внутреннюю согласованность V1C1-report:
  - типы records;
  - deterministic ordering;
  - `changed_files == changes[*].path`;
  - exact duplicates;
  - safe paths;
  - known statuses;
  - known modes;
  - mode/status consistency;
  - presence/absence changed paths в resulting index;
  - полный base commit при полном `manifest.base_commit`.
- Сравнивать каждый changed path с `manifest.allowed_files` по Windows path key.
- Требовать точного совпадения регистра с canonical allowlist path.
- Для rename требовать allowlist и для old path, и для new path.
- Отклонять case-only rename и другие case-collisions среди changed paths.
- Отклонять case-collisions во всём resulting index.
- Отклонять любое появление mode `120000` в old/new side изменения.
- Отклонять любое появление mode `160000` в old/new side изменения.
- Отклонять status `T` как Git object type change.
- Разрешать обычные modes `100644` и `100755`.
- Разрешать add, delete, content change и regular-file executable-bit change при соблюдении allowlist.
- Возвращать immutable structured policy report и collision records.
- Не дублировать hidden-path policy: текущий manifest validator уже запрещает hidden files/directories, кроме специально разрешённого `.env.example`.

---

## 11. Out of scope — V1C2

- Любой запуск Git.
- Любой доступ к filesystem.
- Повторное применение patch.
- `git apply --check` против будущего isolated worktree.
- Создание isolated worktree.
- Запуск checks из manifest.
- Установка зависимостей.
- Commit, merge, promotion или push результата developer-task.
- Автоматическое расширение `allowed_files`.
- Автоматическое исправление регистра путей.

Финальная applicability/audit boundary остаётся V1D.

---

## 12. Принятый API V1C2

Файл:

```text
modules/developer/developer_task_patch_scope.py
```

Публичная функция:

```python
run_developer_task_patch_scope_preflight(
    manifest: DeveloperTaskManifest,
    *,
    patch_index_report: DeveloperTaskPatchIndexPreflightReport,
) -> DeveloperTaskPatchScopePreflightReport
```

Публичные immutable-типы:

```python
DeveloperTaskPatchScopeCollision
DeveloperTaskPatchScopePreflightReport
```

Report содержит:

```text
manifest_fingerprint
repository_root
base_commit
allowed_files
changed_files
unauthorized_files
case_mismatch_files
symlink_files
gitlink_files
type_change_files
changed_path_collisions
result_index_collisions
issues
```

---

## 13. Ожидаемые файлы V1C2

```text
A  modules/developer/developer_task_patch_scope.py
A  tools/eval_developer_task_patch_scope.py
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
main.py
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
```

---

## 14. PLANNED — targeted checks V1C2

```text
python -m py_compile \
    modules/developer/developer_task_patch_scope.py \
    tools/eval_developer_task_patch_scope.py \
    tools/eval_package_boundaries.py \
    tools/pipeline.py

python -m tools.eval_package_boundaries
python -m tools.eval_developer_task_contract
python -m tools.eval_developer_task_preflight
python -m tools.eval_developer_task_patch_integrity
python -m tools.eval_developer_task_patch_index
python -m tools.eval_developer_task_patch_scope
python tools/pipeline.py developer_task_preflight
```

Ожидаемые summaries:

```text
package boundaries:             28/28
contract:                       18/18
V1A repository:                 22/22
V1B integrity:                  29/29
V1C1 index:                     34/34
V1C2 scope policy:              36/36
developer_task_preflight flow:  completed successfully
```

После targeted checks:

```text
git diff --check
python tools/pipeline.py check
```

---

## 15. Критерии завершения V1C2

V1C2 считается завершённым только если:

1. production-модуль остаётся pure policy без Git/filesystem execution;
2. eval V1C2 проходит полностью;
3. V1A, V1B и V1C1 не регрессируют;
4. package boundaries проходят;
5. targeted flow проходит;
6. полный `check` проходит;
7. `git diff --check` не сообщает ошибок;
8. commit содержит только четыре ожидаемых файла;
9. commit отправлен в `origin/main`;
10. `SKYNETVS_CURRENT_STATE.md` после commit обновлён отдельным documentation commit.

Предлагаемое имя code commit:

```text
feat: add developer task patch scope policy
```

---

## 16. PLANNED — следующий этап после V1C2

# Developer Task Preflight V1D — Applicability and Audit

Предварительная граница:

- композиция успешных V1A/V1B/V1C1/V1C2 доказательств;
- финальная read-only applicability-проверка;
- проверка неизменности настоящего repository state;
- fault injection для stale/mismatched evidence;
- cleanup guarantees;
- общий immutable preflight report;
- появление общего публичного `run_developer_task_preflight(...)` только после полной композиции gates.

V1D не должен применять patch к основному worktree и не должен автоматически выполнять promotion.

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

- Foundation-тег остаётся на `09f8708` до отдельного решения о новой стабильной developer-safety точке.
- V1C1 получает факты Git; V1C2 применяет policy. Эти ответственности не объединяются обратно в монолит.
- V1C2 не запускает Git и не касается filesystem.
- Allowlist — максимальная область изменения; неиспользованные allowlist entries допустимы.
- Rename разрешён только если old и new paths оба перечислены в allowlist.
- Exact casing обязателен; case-insensitive совпадение не даёт разрешения на другой регистр.
- Case-only rename блокируется.
- Symlink и gitlink add/modify/delete блокируются полностью в V1.
- Status `T` блокируется полностью в V1.
- Modes `100644` и `100755` разрешены при соблюдении остальных правил.
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
docs: update SkynetVS state after isolated patch index preflight
```

3. Убедиться, что рабочее дерево чистое.
4. Проверить SHA-256 подготовленного V1C2 patch.
5. Выполнить `git apply --check`.
6. Применить V1C2 patch.
7. Запустить targeted checks.
8. Запустить полный `check`.
9. До успешных проверок не создавать V1C2 code commit.

---

## 20. Режим модели

Текущий рекомендуемый режим: **Pro Standard**.

Причина: V1C2 фиксирует security policy для allowlist, Windows case semantics, rename и Git object modes. После завершения архитектурного проектирования V1D и фиксации его интерфейса для механической реализации можно вернуться на режим **«Очень высокий»**.

---

## 21. Файлы для нового чата при необходимости handoff

Обязательно:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Дополнительно:

```text
data/logs/pipeline/20260731_142801_developer_task_preflight.log
data/logs/pipeline/20260731_142820_check.log
```

В новом чате сначала читать документы и логи, затем продолжать с раздела **«Следующее точное действие»**, не восстанавливая roadmap заново по памяти.
