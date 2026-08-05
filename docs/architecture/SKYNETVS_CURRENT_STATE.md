# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-04`
- Ветка: `main`
- Проверенный code baseline перед этим documentation commit: `6a7b08e`
- Название code baseline: `feat: add developer task static check evidence gate`
- `origin/main` на проверенной code-точке: `6a7b08e`
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

## 12. VERIFIED — Typed Check Runner V1A — Static Evidence Gate

### Commit

```text
6a7b08e feat: add developer task static check evidence gate
```

### Публичный API

```python
run_developer_task_static_checks(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    patch_apply_report: DeveloperTaskPatchApplyReport,
    workspace_parent: Path,
) -> DeveloperTaskStaticCheckReport
```

### Подтверждено

- принимаются только typed manifest и успешная evidence-chain `Preflight → Workspace → Patch Apply`;
- explicit `workspace_parent`, canonical markers, workspace identity и non-serialized check capability повторно сверяются до checks;
- `git_diff_check` read-only подтверждает detached `HEAD`, `base_commit`, shallow boundary, отсутствие remotes/refs/alternates и неизменность hardened Git config;
- changed paths, statuses, resulting index, result tree и staged diff SHA-256 повторно совпадают с Patch Apply evidence;
- trusted Python static compiler читает только изменённые существующие `*.py` и не импортирует workspace modules;
- module top-level не выполняется, `python -m`, `runpy`, `importlib`, `exec()` и `eval()` не используются;
- удалённые Python-файлы учитываются без попытки чтения;
- один Python-файл ограничен 2 MiB, общий compilation input — 8 MiB;
- symlink, junction, reparse point, special-file и TOCTOU-подмена блокируются fail-closed;
- syntax/read/compiler/Git failures возвращаются структурированно;
- `.pyc`, `__pycache__`, untracked files и изменения index/worktree не создаются;
- source repository и workspace Git object stores/status до и после совпадают;
- source mutation до или во время static checks обнаруживается fail-closed;
- `python_module` и `pipeline` остаются в `pending_executable_checks` и на host не запускаются;
- host fallback отсутствует.

### Проверки

```text
Package boundaries:               28/28
Preflight composition:            19/19
Workspace V1A:                    39/39
Workspace cleanup V1B:            41/41
Patch Apply V1:                   30/30
Static Evidence Gate V1A:         25/25
developer_task_check_static flow: completed successfully
full check:                       completed successfully
runtime architecture audit:       9/9
```

## 13. CURRENT — Typed Check Runner V1B — Execution Backend Capability and Evidence Gate

### Архитектурный аудит — VERIFIED решение

V1B разделён на четыре внутренних среза. Один commit не может одновременно доказать host capability, lifecycle traditional `.wsb`, result authenticity и trusted Python runtime.

```text
V1B1  Canonical Backend Policy and Host Capability
V1B2  Active Trusted Lifecycle
V1B3  Signed Result Authenticity and Privilege Separation
V1B4  Trusted Python Runtime Bundle
```

### Threat model

Доверенные компоненты:

- host-side SkynetVS Developer Safety Kernel;
- canonical backend policy;
- trusted PowerShell/SYSTEM controller из read-only input bundle;
- pinned Python runtime bundle после V1B4;
- Windows Sandbox / Hyper-V boundary.

Недоверенные компоненты:

- patch bytes после передачи в executable stage;
- код и процессы изменённого workspace;
- stdout/stderr worker;
- весь writable output mapping;
- любые unsigned guest markers;
- inherited host environment и PATH.

Out of scope текущей модели: kernel/hypervisor escape и эксплуатация неизвестной local privilege escalation внутри гостя. Такие события не могут быть безопасно компенсированы прикладным Python-кодом.

### V1B1 — VERIFIED

Зафиксированная code-точка:

```text
368c25f feat: add developer task execution backend host gate
```

Реальный Windows-прогон подтверждён:

```text
Host gate unit eval:                         30/30
Real Windows host smoke:                    ok=true
developer_task_execution_backend_host flow: completed successfully
full check:                                 completed successfully
git diff --check:                           exit code 0
```

Публичный API:

```python
inspect_developer_task_execution_backend_host(
) -> DeveloperTaskExecutionBackendHostReport
```

V1B1:

- не принимает developer-task manifest или workspace evidence;
- не запускает Sandbox и не исполняет код из patch;
- фиксирует canonical policy fingerprint `5c731d5f246929aa1b59f614d2a01371b086244cc09f2c5846d93531b194af21`;
- получает Windows/System directories через WinAPI, а не через inherited `PATH`;
- требует Windows build не ниже `26100`, AMD64 host и 64-bit Python process;
- проверяет `WindowsSandbox.exe` как regular non-reparse file с TOCTOU-safe SHA-256 и version resource;
- допускает `feature_state=unknown`, если обычный пользователь не может выполнить elevated DISM probe, но блокирует явные `disabled`/`pending` states;
- не требует `wsb` CLI;
- блокирует уже запущенный Sandbox и fail-closed реагирует на невозможность проверить process state;
- намеренно возвращает `execution_authorized=false`.

### V1B2 — CURRENT / Active Trusted Lifecycle

Публичный API:

```python
attest_developer_task_execution_backend_lifecycle(
    host_report: DeveloperTaskExecutionBackendHostReport,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionBackendLifecycleReport
```

До production patch выполняется один trusted active lifecycle experiment. Он не запускает manifest checks или код из patch и должен измерить:

- launcher PID/handle traditional `WindowsSandbox.exe`;
- реально появляющиеся Sandbox process names/PID;
- время появления guest result;
- результат IPv4 и IPv6 isolation probes;
- guest `shutdown.exe /s` request;
- исчезновение host Sandbox process/window tree;
- startup/result/shutdown durations;
- необходимость best-effort cleanup при failure.

Обязательные production-доказательства после эксперимента:

- fresh input/output roots;
- exact `.wsb` policy;
- trusted probe only;
- read-only input и writable output;
- отсутствие IPv4 default route и IPv4 external TCP;
- отсутствие IPv6 default route и IPv6 external TCP;
- request/result nonce и bounded strict JSON;
- guest self-shutdown;
- host process/window exit в bounded grace period;
- безопасный cleanup artifacts только после доказанного exit.

Traditional runtime без `wsb stop` считается пригодным только если self-shutdown и host-observed exit доказаны. Forced termination допускается лишь как best-effort cleanup после failure и никогда не делает report успешным. V1B2 всегда оставляет `execution_authorized=false`.

### V1B3 — Signed Result Authenticity and Privilege Separation

Writable output mapping нельзя считать доверенным после запуска кода из patch. Утверждена двухфазная модель:

1. trusted SYSTEM controller генерирует ephemeral ECDSA P-256 key только в памяти;
2. controller публикует `ready.json` с public key и host nonce;
3. host валидирует ready и создаёт `authorize.json`, связанный с public-key hash;
4. controller запускает standard non-admin worker в kill-on-close Job Object;
5. worker не наследует controller handles/environment и не имеет доступа к private key;
6. controller завершает весь worker process tree;
7. terminal canonical result подписывается по transcript `request + ready + authorize + payload`;
8. host доверяет только подписи по public key, сохранённому до authorization.

Подмена, replay, unsigned marker, early/late result или background writer приводят к fail-closed failure. V1B3 выполняет только benign trusted worker probe.

### V1B4 — Trusted Python Runtime Bundle

```python
attest_developer_task_python_runtime(
    boundary_report: DeveloperTaskExecutionBoundaryReport,
    *,
    runtime_bundle_root: Path,
    artifact_parent: Path,
) -> DeveloperTaskExecutionCapabilityReport
```

Runtime должен быть pinned, read-only и полностью связан canonical manifest/hash-chain. Download/install во время task запрещён. Final capability получает non-serialized single-use token, TTL `300` секунд и привязку к host boot, Windows build, Sandbox executable hash/version, policy fingerprint и runtime fingerprint.

### Текущий жёсткий scope

V1B может запускать только trusted probe/controller/benign worker. Он не запускает:

- `python_module` из manifest;
- `pipeline` из manifest;
- произвольный shell;
- код из изменённого workspace;
- установку или скачивание зависимостей;
- commit, merge, push или promotion.

### Mode decision

Security architecture V1B зафиксирована в Pro Standard. После documentation commit реализацию механического V1B1 можно вести в режиме **«Очень высокий»**. Перед V1B2/V1B3 требуется возврат на **Pro Standard**.

## 14. BLOCKED до V1C — Sandboxed Executable Checks

До завершения V1B запрещены:

```text
python_module
pipeline
host fallback
```

V1C сможет выполнять их только через успешно аттестованный production backend и отдельную result-evidence boundary.

## 15. Следующее точное действие

1. Зафиксировать V1B1 как `VERIFIED` и перевести `CURRENT` на V1B2.
2. Выполнить trusted active lifecycle experiment на реальном Windows-хосте.
3. Зафиксировать фактические process names/PID, startup/result/shutdown timings и self-shutdown behavior.
4. Только после результата эксперимента утвердить production state machine V1B2 и подготовить code patch.
5. Не разрешать `python_module`, `pipeline`, код из patch или host fallback.

## 16. Зафиксированные коммиты текущего перехода

```text
70e1813 docs: close patch apply and split typed check execution boundaries
97cd502 docs: record sandbox attestation and start static checks
6a7b08e feat: add developer task static check evidence gate
cb0e4f4 docs: close static checks and start sandbox capability gate
d67501c docs: split sandbox capability gate into verified boundaries
368c25f feat: add developer task execution backend host gate
```

Следующий documentation commit закрывает V1B1 и переводит `CURRENT` на V1B2 lifecycle experiment.

## 17. DEFERRED

- Typed Check Runner V1C — Sandboxed `python_module` and `pipeline`.
- Developer Task Result and Evidence V1.
- Developer Task Manual Promotion V1.
- Developer Safety Kernel Audit V1.
- Workspace crash recovery / orphan cleanup.
- Domain Package Structure V2.
- Tools Package Structure V1.

## 18. Решения, которые нельзя пересматривать молча

- `skynet-runtime-foundation-v1` остаётся на `09f8708`.
- Основной worktree никогда не используется как developer-task sandbox.
- Patch применяется только после полного Preflight V1 и Workspace V1 evidence.
- Изменённый код не запускается обычным host subprocess.
- Python isolated mode и Job Object не считаются достаточной OS sandbox boundary.
- Executable checks fail closed без production-attested backend.
- Static checks не могут молча перейти к `python_module` или `pipeline`.
- Active attestation trusted probe не считается разрешением запускать код из patch.
- Arbitrary shell, dependency installation, commit, merge, push и promotion запрещены.
- Package migration не смешивается с Developer Safety Kernel.

## 19. Режим модели

Threat model, result-authenticity model и четыре внутренних среза V1B утверждены в **Pro Standard**.

V1B1 является механическим read-only host gate, поэтому после documentation commit можно вернуться на **«Очень высокий»**. Перед V1B2/V1B3 и перед V1C требуется **Pro Standard**.

## 20. Файлы для будущего handoff

Обязательно:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
docs/architecture/SKYNETVS_WINDOWS_SANDBOX_ACTIVE_ATTESTATION_V1.md
```

Дополнительно приложить последние:

```text
data/logs/pipeline/*_developer_task_check_static.log
data/logs/pipeline/*_check.log
active Windows Sandbox attestation result
```

Новый чат должен продолжать с раздела **«Следующее точное действие»**, а не восстанавливать roadmap по памяти.
