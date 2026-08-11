# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-11`
- Ветка: `main`
- Проверенный code baseline перед этим documentation commit: `f3f5607`
- Название code baseline: `feat: add active signed boundary composition`
- `origin/main` на проверенной code-точке: `f3f5607`
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

## 13. CURRENT — Typed Check Runner V1B4 — Trusted Python Runtime

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

### V1B2 — VERIFIED / Production Active Trusted Lifecycle

Code-точки:

```text
eb2a476 feat: add trusted Windows Sandbox lifecycle gate
4ea2e0c fix: isolate Windows Sandbox launch environment
```

Trusted lifecycle experiment от `2026-08-05` завершён:

```text
status:                       lifecycle_attested
failure:                      empty
backend:                      traditional_wsb_logoncommand_v1
policy fingerprint:           5c731d5f246929aa1b59f614d2a01371b086244cc09f2c5846d93531b194af21
launcher PID:                 21544
process observed:             true
all Sandbox processes exited: true
forced cleanup attempted:     false
result received:              13 514 ms
all processes exited:         23 157 ms
result → exit:                9 643 ms
execution_authorized:         false
```

Все validation fields подтверждены: strict UTF-8, exact schemas, backend/policy/request/nonce/hash chain, trusted guest identity, self-shutdown, read-only input, writable output, IPv4 isolation и IPv6 isolation.

Измеренная host process-модель:

```text
before_launch
    no known Sandbox processes
        ↓
after_launch
    WindowsSandbox.exe PID 21544
        ↓
waiting_for_result
    launcher already exited
    WindowsSandboxRemoteSession.exe PID 15548 remains
        ↓
result_detected at 13 514 ms
    RemoteSession still active
        ↓
waiting_for_shutdown at 23 157 ms
    no known Sandbox processes
```

Следствие: `launcher_pid` не является session handle. Production success требует наблюдения хотя бы одного известного Sandbox process, валидного trusted result, successful guest self-shutdown и доказанного исчезновения всего известного process set в bounded grace period.

Публичный API:

```python
attest_developer_task_execution_backend_lifecycle(
    host_report: DeveloperTaskExecutionBackendHostReport,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionBackendLifecycleReport
```

Production gate:

- повторно проверяет свежесть typed V1B1 host report до и после run;
- создаёт fresh per-run input/output roots и exact canonical `.wsb`;
- запускает только trusted PowerShell probe;
- валидирует request/result nonce, bounded strict JSON и полный hash-chain;
- требует read-only input, writable output, IPv4 и IPv6 isolation;
- ждёт guest self-shutdown и исчезновения всего известного Sandbox process set;
- повторно читает result после доказанного exit и отклоняет изменение bytes/hash;
- удаляет artifacts только после доказанного exit;
- при failure использует только exact-identity best-effort termination;
- никогда не превращает forced cleanup в success;
- явно передаёт `SystemDrive=C:` в изолированное launch environment;
- запускает `WindowsSandbox.exe` с фиксированным trusted `cwd=C:\Windows\System32`;
- не использует project root или удаляемый lifecycle artifact root как process working directory;
- всегда возвращает `execution_authorized=false`.

Финальные проверки после hardening:

```text
Lifecycle unit eval:                         39/39
Real Windows active lifecycle smoke:        3/3
developer_task_execution_backend_lifecycle: completed successfully
full check:                                 completed successfully
```

Полный experiment evidence и production closure: `docs/architecture/SKYNETVS_WINDOWS_SANDBOX_LIFECYCLE_ATTESTATION_V1.md`.
### V1B3 — VERIFIED / Signed Result Authenticity and Privilege Separation

Writable output mapping нельзя считать доверенным после запуска кода из patch. Архитектурный аудит текущего `HEAD 7efcf76` уточнил boundary:

1. `.wsb LogonCommand` запускает trusted bootstrap под `WDAGUtilityAccount`, а не под SYSTEM;
2. bootstrap должен доказать возможность одноразового запуска controller через Scheduled Task с `S-1-5-18`;
3. SYSTEM controller создаёт ephemeral ECDSA P-256 key без имени и сохраняет private key только в памяти;
4. controller публикует `ready.json` с public key, host nonce и identity evidence;
5. host фиксирует exact ready bytes/public-key hash и создаёт read-only для guest `authorize.json`;
6. controller создаёт fresh local standard user через `NetUserAdd` и получает primary token через `LogonUserW`;
7. worker запускается через `CreateProcessAsUserW` с `CREATE_SUSPENDED`, без inherited environment/handles;
8. worker помещается в kill-on-close Job Object и возобновляется только после `IsProcessInJob=true`;
9. controller завершает worker tree, доказывает пустой worker-SID process set и удаляет account;
10. terminal payload подписывается только после этих доказательств;
11. host повторно читает bytes после полного Sandbox exit и проверяет ECDSA signature по public key, закреплённому до authorization.

`CreateProcessWithLogonW` для SYSTEM-controller не используется. Подмена, replay, unsigned marker, early/late result, worker escape или background writer приводят к fail-closed failure.

V1B3 разделён на четыре среза:

```text
V1B3A  SYSTEM Controller Bootstrap Capability Experiment
V1B3B  Canonical Transcript and Host Signature Verifier
V1B3C  Standard-User Worker Isolation Gate
V1B3D  Active Signed Boundary Composition
```

### V1B3A — VERIFIED / Active Signed Boundary Experiment

Active experiment от `2026-08-06` завершён:

```text
Git HEAD:                       e18e309
status:                         signed_boundary_attested
SYSTEM controller SID:          S-1-5-18
SYSTEM integrity RID:           16384 / 0x4000
ECDSA P-256 key ephemeral:      true
ready → authorize handshake:    verified
standard worker administrator:  false
standard worker integrity RID:  8192 / 0x2000
worker assigned before resume:  true
Job Object kill-on-close:       verified
worker-SID process set empty:   true
worker account deleted:         true
signature valid after exit:     true
all Sandbox processes exited:   true
execution_authorized:           false
```

Evidence ZIP SHA-256:

```text
a65c9f5a3e6b21a862e05417e17e205b2efb141f1a41f0ffef75d65616387cef
```

Полный evidence: `docs/architecture/SKYNETVS_WINDOWS_SANDBOX_SIGNED_BOUNDARY_ATTESTATION_V1.md`.

### V1B3B — VERIFIED / Canonical Transcript and Host Signature Verifier

Code-точка:

```text
674dd5f feat: add signed execution transcript verifier
```

Production scope:

- canonical immutable boundary policy with fingerprint `9eb7a1373d1814eea37c8213dfeaeb4f4e7d40e7fdb5d8ec40f91f3e2fd8db72`;
- strict UTF-8 canonical JSON contracts with exact field order and duplicate/unknown-field rejection;
- exact-byte pinning for request, ready and authorize evidence;
- trusted input and full transcript SHA-256 chain validation;
- replay, substitution, authorization-window and post-pin mutation guards;
- ECDSA P-256/SHA-256 verification through Windows CNG;
- worker/controller/control evidence consistency validation;
- `execution_authorized=false` in every report.

Подтверждено:

```text
verifier unit eval:                         45/45
Windows CNG smoke:                          3/3
real V1B3A evidence:                        signed_transcript_verified
developer_task_execution_boundary_verifier: completed successfully
full check:                                 completed successfully
```

V1B3B does not launch Sandbox, create users, run workers or execute code from patch. Active composition was implemented separately in V1B3D.

### V1B3C — VERIFIED / Standard-User Worker Isolation Production Gate

Code-point:

```text
74f543a feat: add standard-user worker isolation bundle
```

V1B3C created the exact deterministic trusted payload that V1B3D later executed in the verified production composition. It does not duplicate lifecycle or signature orchestration and does not launch Windows Sandbox.

Verified production properties:

- immutable worker bundle built only from canonical V1B3 policy;
- fixed trusted native helper and fixed benign worker probe;
- fresh local account with collision rejection and exact SID binding;
- memory-only password cleared after `LogonUserW`;
- protected SYSTEM-owned staging ACLs and least-privilege worker access;
- validated primary token, non-administrator membership and exact medium integrity;
- non-inherited environment and handles;
- suspended `CreateProcessAsUserW`, Job assignment before resume and no breakaway;
- fail-closed `WTSEnumerateProcessesEx` process sweep by primary-token SID, bounded quiescence and exact account cleanup;
- no manifest, workspace, patch bytes, arbitrary executable or shell command accepted as input;
- every report and bundle keeps `execution_authorized=false`.

Verification closure:

```text
worker bundle unit/static eval:                28/28
exact Windows helper/worker compile smoke:     2/2
worker executable created:                     true
worker executable executed:                    false
developer_task_execution_boundary_worker:      completed successfully
full check:                                    completed successfully
runtime architecture audit:                    9/9
```

### V1B3D — VERIFIED / Active Signed Boundary Composition

Code closure:

```text
f3f5607 feat: add active signed boundary composition
```

One production Windows Sandbox run composed:

```text
V1B1 host capability
    ↓
V1B2 Sandbox process lifecycle
    ↓
V1B3B request/ready/authorize pinning and post-exit signature verification
    ↓
V1B3C exact benign worker bundle
```

Verified evidence:

```text
V1B3D unit/failure gate:                  40/40
active Windows composition:                3/3
status:                    active_signed_boundary_attested
ready received:                         14 516 ms
authorization published:                14 530 ms
terminal detected:                      23 438 ms
all Sandbox processes exited:           34 375 ms
total:                                  35 047 ms
signature valid:                           true
forced cleanup attempted:                  false
artifacts removed:                          true
execution_authorized:                       false
developer_task_execution_boundary_composition: completed successfully
full check:                                 completed successfully
runtime architecture audit:                  9/9
```

The production boundary publishes `authorize.json` only after pinning and commits it with verified `authorize.sha256`; closes the Job Object, proves worker-SID quiescence and exact account deletion before signing; trusts output only after full Sandbox exit; and removes artifacts without forced cleanup.

Signed Result Authenticity and Privilege Separation is complete. Patch/workspace Python execution remains blocked until V1B4 and V1C.

### V1B4 — CURRENT / Trusted Python Runtime

V1B4 is split into four evidence boundaries:

```text
V1B4A  Runtime Source Provenance Gate
V1B4B  Deterministic Runtime Bundle Gate
V1B4C  Active Trusted Runtime Attestation
V1B4D  Same-Run Runtime Capability Lease
```

The current host `.venv` is not accepted as the trusted bundle: it depends on a host-installed base interpreter, contains mutable `site-packages` and pip, and has no canonical archive provenance.

Initial V1B4A compatibility candidate:

```text
CPython 3.12.10 Windows embeddable AMD64
python-3.12.10-embed-amd64.zip
SHA-256 4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3
```

V1B4A is host-only and does not execute that interpreter. It verifies the exact archive/SPDX pair, safe ZIP structure, required embeddable files, AMD64 PE identity, upstream `_pth` isolation and absence of pip/site-package surfaces.

V1B4B derives exact application-local bytes. V1B4C executes only a fixed benign probe through explicit `python.exe -I -S -B -E -s -P -X utf8` inside the existing signed standard-user/Job boundary. V1B4D creates a non-serialized single-use lease with TTL `300` seconds but does not carry active trust across Sandbox runs.

Full contract: `docs/architecture/SKYNETVS_TRUSTED_PYTHON_RUNTIME_V1.md`.

### Текущий жёсткий scope

V1B может запускать только trusted probe/controller/benign worker. Он не запускает:

- `python_module` из manifest;
- `pipeline` из manifest;
- произвольный shell;
- код из изменённого workspace;
- установку или скачивание зависимостей;
- commit, merge, push или promotion.

### Mode decision

V1B3A–V1B3D are VERIFIED. V1B4 threat model, runtime version/provenance choice, active runtime composition and same-run V1C handoff require **Pro Standard**. Bounded host-only V1B4A/V1B4B implementation may return to **«Очень высокий»** only after the architecture/provenance decision is recorded.

## 14. BLOCKED до V1C — Sandboxed Executable Checks

До завершения V1B запрещены:

```text
python_module
pipeline
host fallback
```

V1C сможет выполнять их только через успешно аттестованный production backend и отдельную result-evidence boundary.

## 15. Следующее точное действие

Выполнить `V1B4A — Runtime Source Provenance Gate`:

1. Зафиксировать V1B3 closure и V1B4 four-slice architecture отдельным documentation commit.
2. Скачать только официальный `python-3.12.10-embed-amd64.zip` и matching SPDX document.
3. Проверить exact source SHA-256 `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`.
4. Запустить standalone host-only provenance experiment; candidate interpreter не исполнять.
5. Проверить official SPDX identity/hash, safe ZIP/path model, required files, AMD64 PE headers, `_pth` contract and forbidden package-management surfaces.
6. Получить structured report with source fingerprint, `interpreter_executed=false` and `execution_authorized=false`.
7. Провести Pro-review lifecycle-risk: 3.12.10 is the final 3.12 binary release while later security releases are source-only.
8. Only after that decision begin bounded production V1B4A/V1B4B modules.
9. Do not create V1B4C active code, map workspace, or execute patch/Python checks in this slice.

## 16. Зафиксированные коммиты текущего перехода

```text
70e1813 docs: close patch apply and split typed check execution boundaries
97cd502 docs: record sandbox attestation and start static checks
6a7b08e feat: add developer task static check evidence gate
cb0e4f4 docs: close static checks and start sandbox capability gate
d67501c docs: split sandbox capability gate into verified boundaries
368c25f feat: add developer task execution backend host gate
54c2673 docs: close host gate and start sandbox lifecycle experiment
54ac331 docs: record sandbox lifecycle attestation and start production gate
eb2a476 feat: add trusted Windows Sandbox lifecycle gate
4ea2e0c fix: isolate Windows Sandbox launch environment
7efcf76 docs: close sandbox lifecycle gate and start signed result boundary
e18e309 docs: split signed result boundary into measured security slices
61de548 docs: record signed boundary attestation and start transcript verifier
674dd5f feat: add signed execution transcript verifier
e53a8e5 docs: close transcript verifier and start worker isolation gate
74f543a feat: add standard-user worker isolation bundle
be7470f docs: close worker isolation gate and start active signed composition
f3f5607 feat: add active signed boundary composition
```

Следующий documentation commit закрывает V1B3 и переводит `CURRENT` на V1B4A.

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

V1B3A–V1B3D are VERIFIED. V1B4 runtime provenance/version choice and V1C active execution boundaries require **Pro Standard**.

## 20. Файлы для будущего handoff

Обязательно:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
docs/architecture/SKYNETVS_WINDOWS_SANDBOX_ACTIVE_ATTESTATION_V1.md
docs/architecture/SKYNETVS_WINDOWS_SANDBOX_LIFECYCLE_ATTESTATION_V1.md
docs/architecture/SKYNETVS_WINDOWS_SANDBOX_SIGNED_BOUNDARY_ATTESTATION_V1.md
docs/architecture/SKYNETVS_TRUSTED_PYTHON_RUNTIME_V1.md
```

Дополнительно приложить последние:

```text
data/logs/pipeline/*_developer_task_execution_boundary_verifier.log
data/logs/pipeline/*_developer_task_execution_boundary_worker.log
data/logs/pipeline/*_developer_task_execution_boundary_composition.log
data/logs/pipeline/*_check.log
latest signed-boundary and active-composition evidence
```

Новый чат должен продолжать с раздела **«Следующее точное действие»**, а не восстанавливать roadmap по памяти.
