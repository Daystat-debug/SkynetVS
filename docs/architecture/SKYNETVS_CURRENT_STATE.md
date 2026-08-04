# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-04`
- Ветка: `main`
- Проверенный code baseline перед этим documentation commit: `b8419f5`
- Название code baseline: `feat: add verified developer task patch apply`
- `origin/main` на проверенной code-точке: `b8419f5`
- Documentation HEAD после сохранения этого файла определяется фактическим `git log -1`; self-referential commit SHA в содержимом не фиксируется.
- Стабильный foundation-тег: `skynet-runtime-foundation-v1` → `09f8708`
- Рабочее дерево после documentation commit должно быть чистым.

## 2. Приоритет источников истины

1. Текущее состояние Git, кода и свежих проверок.
2. Этот файл `SKYNETVS_CURRENT_STATE.md`.
3. `SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`.
4. Память старых чатов и предположения.

Нельзя объявлять `PLANNED` или `UNVERIFIED` завершёнными без подтверждения Git/eval.

## 3. Общая цель проекта

Создать персонального голосового ассистента, который станет сильнее обычного чат-интерфейса в среде пользователя благодаря постоянному контексту, голосу, управлению компьютером, пониманию экрана, безопасной разработке кода, воспроизводимым проверкам, контролируемому обучению и rollback.

Автономность не должна развиваться быстрее безопасности, наблюдаемости и доказательной базы.

## 4. VERIFIED — стабильный фундамент

### Runtime и сервисная база

- явное владение сервисами через composition root;
- fault boundaries и независимый shutdown;
- runtime health и мониторинг;
- lifecycle и generation guards для STT/TTS;
- регрессионное покрытие audio, reminders, timers и command runtime.

### Foundational Package Structure V1

- `modules/developer/`;
- `modules/core/`;
- `modules/runtime/`;
- `modules/learning/`;
- `modules/desktop/`.

### Roadmap Lock V1

- roadmap и оперативный handoff-документ хранятся в Git;
- скрытое расширение scope запрещено;
- изменение порядка оформляется как Roadmap Change.

## 5. VERIFIED — Developer Task Preflight V1

Последовательность code-коммитов:

```text
6e2aa78  V1A Repository Gate
cb7c6c5  V1B Patch Integrity Gate
b14486a  V1C1 Isolated Patch Index Gate
eeb50ce  V1C2 Patch Scope Policy Gate
1035de4  V1D Composition and Audit
```

Финальный публичный API:

```python
run_developer_task_preflight(
    manifest: DeveloperTaskManifest,
    *,
    project_root: Path,
    task_root: Path,
) -> DeveloperTaskPreflightReport
```

Подтверждено:

- canonical validation manifest;
- правильный repository root;
- `HEAD == base_commit`;
- чистые worktree и index;
- immutable snapshot точных байтов patch и SHA-256;
- применимость patch во временном изолированном Git index/object store;
- фактические changed paths и object modes;
- `allowed_files`, Windows case policy, запрет symlink и gitlink;
- фиксированный fail-closed порядок gates;
- отсутствие verified patch/changed-files evidence при частичном отказе;
- отсутствие изменений основного worktree, index и object store.

Финальный targeted flow:

```text
package boundaries:             28/28
contract:                       18/18
repository preflight V1A:       22/22
patch integrity V1B:            29/29
isolated patch index V1C1:      35/35
patch scope policy V1C2:        36/36
composition and audit V1D:      19/19
developer_task_preflight flow:  completed successfully
```

Полный `check` после V1D завершён успешно.

## 6. Roadmap Change 001 — VERIFIED решение

### Решение

Использовать независимый локальный clone репозитория вместо linked `git worktree`.

Этап называется:

```text
Developer Task Isolated Repository Workspace V1
```

### Причина

Linked worktree имеет отдельные `HEAD` и index, но разделяет common Git administration, refs/config/object data с основным репозиторием. Для будущего developer-task runtime это недостаточно независимая Git-граница.

### Критичное ограничение

Независимый clone обеспечивает только Git/repository isolation. Он не является OS/process sandbox и не разрешает исполнение недоверенного изменённого кода. Execution isolation должна быть утверждена до checks, которые импортируют или запускают изменённый код.

## 7. VERIFIED — Isolated Repository Workspace V1A

### Commit

```text
4861934 feat: add isolated developer task repository workspace
```

### Публичный API

```python
create_developer_task_workspace(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceReport
```

### Подтверждено

- принимается только успешный полный отчёт Preflight V1;
- source repository повторно проверяется перед clone;
- `workspace_parent` должен быть внешним обычным каталогом без symlink/junction/reparse в цепочке;
- parent не может пересекаться с source repository или task root;
- parent не может находиться внутри worktree, Git administration directory или bare repository;
- создаётся уникальный workspace-контейнер;
- repository создаётся через независимый clone с `--no-local`, `--no-hardlinks`, `--no-checkout`, `--no-tags`, `--single-branch`, `--depth=1`;
- HOME, USERPROFILE, XDG, global Git config, hooks и template directory изолированы;
- workspace использует deterministic Git policy и filesystem guards;
- baseline symlink, gitlink, `.git` control paths, Windows-unsafe paths и case-collision блокируются;
- `HEAD` detached и равен verified `base_commit`;
- workspace shallow и чистый;
- remotes, обычные refs и alternate object directories отсутствуют;
- marker записывается canonical JSON;
- cleanup уже частично созданного неуспешного workspace выполняется только внутренним creation-lifecycle;
- source HEAD/status/refs/index/config не меняются;
- частично созданный workspace очищается с ограниченными Windows retries.

### Проверки

```text
repository workspace eval:      39/39
developer_task_workspace flow:  completed successfully
full check:                     completed successfully
```

Подтверждена Windows-регрессия `core.autocrlf=true`: source line-ending policy больше не создаёт ложный `source_repository_stale`.

## 8. VERIFIED — Isolated Repository Workspace V1B

### Commit

```text
892e175 feat: add developer task workspace cleanup audit
```

### Публичный API

```python
cleanup_developer_task_workspace(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceCleanupReport
```

### Подтверждено

- cleanup принимает только typed manifest, успешный полный Preflight report и успешный Workspace report;
- explicit `workspace_parent`, fixed layout, workspace ID и marker evidence сверяются до удаления;
- non-serialized cleanup capability связана с canonical marker через SHA-256;
- marker читается как bounded immutable binary snapshot с TOCTOU-проверками;
- source repository, task root, workspace parent, sibling paths и пересекающиеся пути не удаляются;
- root/marker/descendants с symlink, junction, reparse point или special-file блокируются;
- transient Windows filesystem failures повторяются ограниченно;
- permanent failure и directory identity change возвращаются структурированно;
- повторный cleanup после успеха идемпотентен;
- source HEAD/status/refs/index/config до и после cleanup совпадают;
- уже существовавшие source changes сохраняются;
- cleanup capability отсутствует в `repr()` и `to_dict()`;
- applied или staged workspace может быть удалён тем же verified cleanup lifecycle.

### Проверки

```text
Workspace V1A:                     39/39
Workspace Cleanup V1B:             41/41
developer_task_workspace_cleanup:  completed successfully
full check:                        completed successfully
```

## 9. VERIFIED — Developer Task Patch Apply V1

### Commit

```text
b8419f5 feat: add verified developer task patch apply
```

### Публичный API

```python
apply_developer_task_patch(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    workspace_parent: Path,
) -> DeveloperTaskPatchApplyReport
```

### Подтверждено

- принимаются только typed manifest, успешный полный Preflight report и успешный Workspace report;
- explicit `workspace_parent`, fixed layout, workspace marker, cleanup capability и directory identity сверяются до mutation;
- применяются только immutable patch bytes из Preflight V1;
- patch передаётся Git через stdin и применяется только к независимому workspace;
- mutating Git-команды явно привязаны к ожидаемым `--git-dir` и `--work-tree`;
- запрещены `--3way`, `--reject`, `--unsafe-paths`, remotes, alternates, attached HEAD и повторный apply;
- local Git config проверяется без includes; `core.worktree`, filters и execution/redirection keys блокируются;
- фактические changed paths, statuses, modes и resulting index повторно совпадают с Preflight evidence;
- после apply разрешено только staged-only состояние без unstaged, untracked, conflicts и submodule changes;
- `HEAD` остаётся detached на verified `base_commit`;
- canonical staged diff, result tree и config fingerprint привязаны к `control/patch_apply.json`;
- non-serialized check capability не раскрывается через `repr()` и `to_dict()`;
- apply/postcondition/marker/source failure выполняет bounded rollback к чистому base;
- rollback failure возвращает `failed_dirty` и запрещает reuse workspace;
- patch, удаляющий последний tracked file, корректно поддерживает пустой resulting index;
- applied workspace остаётся совместим с verified cleanup lifecycle;
- source mutation во время apply обнаруживается даже при Windows `core.autocrlf=true`, а workspace откатывается к чистой базе;
- основной repository, его index, refs, objects, files и status не изменяются.

### Проверки

```text
Package boundaries:             28/28
Preflight composition:          19/19
Workspace V1A:                  39/39
Workspace cleanup V1B:          41/41
Patch Apply V1:                 30/30
developer_task_patch_apply:     completed successfully
full check:                     completed successfully
```

## 10. Roadmap Change 002 — Static Checks и Executable Checks разделены

### Причина

Независимый repository clone защищает Git-состояние основного проекта, но не является OS/process sandbox. Обычный `subprocess`, Python isolated mode и Windows Job Object сами по себе не создают полноценную filesystem/network boundary для кода из patch.

Поэтому `python_module` и `pipeline` нельзя запускать на host только потому, что workspace является отдельным clone.

### Что меняется

`Developer Task Typed Check Runner V1` делится на три внутренних среза:

```text
V1A — Static Evidence Gate
V1B — Execution Backend Capability and Evidence Gate
V1C — Sandboxed Executable Checks
```

#### V1A — Static Evidence Gate

Разрешает только проверки, которые не исполняют изменённый код:

- `git_diff_check`;
- `py_compile` как trusted host-side compilation/parsing без imports, без `python -m` из workspace и без записи `.pyc` в workspace.

#### V1B — Execution Backend Capability and Evidence Gate

- обнаруживает и аттестует доступный OS sandbox backend;
- фиксирует backend version/capabilities/policy fingerprint;
- fail-closed блокирует executable checks при отсутствии подходящей изоляции;
- не запускает изменённый код.

#### V1C — Sandboxed Executable Checks

Только через аттестованный backend выполняет:

- `python_module`;
- `pipeline`.

### Что не меняется

- manifest по-прежнему использует только типизированные check types;
- `git_diff_check` остаётся первым;
- `pipeline` flow `check` остаётся последним;
- arbitrary shell запрещён;
- установка зависимостей запрещена;
- основной worktree не используется для checks;
- commit, merge, push и promotion остаются запрещены.

## 11. VERIFIED — Windows Sandbox Active Attestation V1

На фактическом хосте подтверждён backend-кандидат:

```text
traditional_wsb_logoncommand_v1
WindowsSandbox.exe 10.0.26100.8875
wsb CLI отсутствует
```

Активный trusted probe подтвердил:

- `.wsb + LogonCommand` запускается;
- guest выполняется как `WDAGUtilityAccount`;
- input mapping присутствует и реально read-only;
- отдельный output mapping writable;
- IPv4 default route отсутствует;
- TCP к `1.1.1.1:443` недоступен;
- host-side schema и `request_id` validation успешны.

Доказательство хранится в `docs/architecture/SKYNETVS_WINDOWS_SANDBOX_ACTIVE_ATTESTATION_V1.md`.

Это capability evidence, но не разрешение исполнять изменённый код: `python_module` и `pipeline` остаются заблокированы до V1B/V1C.

## 12. CURRENT — Typed Check Runner V1A — Static Evidence Gate

### Назначение

Сначала закрыть безопасную статическую часть check runner и доказательно определить, доступен ли на текущем Windows-хосте backend, пригодный для запуска изменённого кода.

### In scope V1A

- повторно проверить typed manifest, полный Preflight report, успешный Workspace report и успешный Patch Apply report;
- проверить apply marker, check capability, workspace identity и source snapshot freshness;
- выполнить read-only `git_diff_check` и точно сверить Git evidence с Patch Apply report;
- определить изменённые Python-файлы по verified changed-file facts;
- читать только обычные файлы внутри workspace без symlink/junction/reparse traversal;
- ограничить размер одного Python-файла и общий объём compilation input;
- компилировать trusted host-side через встроенный Python parser/compiler без imports и без исполнения module top-level;
- не писать `.pyc` и не изменять index/worktree;
- вернуть immutable structured static-check report;
- проверить, что source repository и apply evidence не изменились;
- использовать уже сохранённую активную аттестацию Windows Sandbox как подтверждённый вход для будущего V1B.

### Out of scope V1A

- запуск `python_module`;
- запуск `pipeline`;
- любой child process из изменённого workspace;
- произвольный shell;
- сеть;
- установка или скачивание зависимостей;
- commit, branch, merge, push, promotion;
- изменение source repository;
- объявление всего Typed Check Runner завершённым.

## 13. Требования к будущему execution backend

Backend для V1C должен доказать:

- отдельную OS/kernel boundary, а не только отдельный каталог или Git clone;
- отключённую сеть по умолчанию;
- отсутствие доступа к host clipboard, audio/video input, printers и пользовательским секретам;
- read-only input boundary;
- отдельный пустой output boundary без данных пользователя;
- bounded timeout, memory и process-tree termination;
- отсутствие доступа к source repository и task artifacts вне явно переданного input;
- trusted Python/runtime bundle с проверенным hash;
- structured result marker и полный cleanup;
- fail-closed поведение при недоступности или несовместимости backend.

Windows Sandbox рассматривается как основной кандидат, но его доступность, версия CLI и возможности должны быть проверены на фактическом компьютере до фиксации реализации V1B/V1C.

## 14. Файлы Typed Check Runner V1A

```text
A  modules/developer/developer_task_check_static.py
A  modules/developer/developer_task_check_static_git.py
A  modules/developer/developer_task_check_static_python.py
M  modules/developer/developer_task_patch_apply_git.py
A  tools/eval_developer_task_check_static.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

Окончательный состав утверждается после capability audit и проверки актуальных API.

## 15. Критерии завершения V1A

1. raw/failed/forged reports не инициируют checks;
2. static checks работают только на successful `applied` workspace;
3. `git_diff_check` повторно подтверждает apply evidence и отсутствие post-apply mutation;
4. `py_compile` не импортирует и не исполняет код из workspace;
5. deleted Python files обрабатываются без попытки чтения;
6. unsafe/reparse/special paths блокируются;
7. input size limits fail closed;
8. syntax/encoding errors возвращаются структурированно;
9. no `.pyc`, untracked files или index changes не появляются;
10. source repository snapshot до и после совпадает;
11. report immutable и не раскрывает capabilities;
12. targeted eval и полный `check` проходят;
13. capability audit Windows Sandbox сохранён и разобран;
14. executable checks остаются blocked до V1B/V1C.

## 16. Следующее точное действие

1. Добавить `SKYNETVS_WINDOWS_SANDBOX_ACTIVE_ATTESTATION_V1.md` отдельным documentation commit.
2. Применить хирургический patch `Typed Check Runner V1A — Static Evidence Gate`.
3. Запустить targeted eval `tools.eval_developer_task_check_static`.
4. Запустить flow `developer_task_check_static`.
5. После зелёного targeted-flow запустить полный `check`.
6. Не разрешать `python_module` и `pipeline`: они остаются pending executable checks до V1B/V1C.

## 17. Планируемые коммиты

Документация:

```text
docs: close patch apply and split typed check execution boundaries
```

V1A code:

```text
feat: add developer task static check evidence gate
```

## 18. DEFERRED

- Typed Check Runner V1B — Execution Backend Capability and Evidence.
- Typed Check Runner V1C — Sandboxed `python_module` and `pipeline`.
- Developer Task Result and Evidence V1.
- Developer Task Manual Promotion V1.
- Developer Safety Kernel Audit V1.
- Workspace crash recovery / orphan cleanup.
- Domain Package Structure V2.
- Tools Package Structure V1.

## 19. Решения, которые нельзя пересматривать молча

- `skynet-runtime-foundation-v1` остаётся на `09f8708`.
- Основной worktree никогда не используется как developer-task sandbox.
- Patch применяется только после полного Preflight V1 и Workspace V1 evidence.
- Изменённый код не запускается обычным host subprocess.
- Python isolated mode и Job Object не считаются достаточной OS sandbox boundary.
- Executable checks fail closed без аттестованного backend.
- Static checks не могут молча перейти к `python_module` или `pipeline`.
- Arbitrary shell, dependency installation, commit, merge, push и promotion запрещены.
- Package migration не смешивается с Developer Safety Kernel.

## 19. Режим модели

До фиксации execution backend остаёмся на **Pro Standard**, потому что определяется новая OS/process security boundary.

После утверждения backend policy и интерфейса V1A/V1B механическую реализацию отдельных срезов можно вести в режиме **«Очень высокий»**.

## 20. Файлы для будущего handoff

Обязательно:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Дополнительно приложить последние:

```text
data/logs/pipeline/*_developer_task_patch_apply.log
data/logs/pipeline/*_check.log
execution backend capability audit
```

Новый чат должен продолжать с раздела **«Следующее точное действие»**, а не восстанавливать roadmap по памяти.
