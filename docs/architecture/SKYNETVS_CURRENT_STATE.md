# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-15`
- Ветка: `main`
- Проверенный code baseline перед этим documentation commit: `e090f63`
- Название code baseline: `feat: add canonical host toolchain observation`
- `origin/main` на проверенной code-точке: `e090f63`
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

## 13. VERIFIED — Typed Check Runner V1B4 — Trusted Python Runtime

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
e6d00f2 docs: close signed boundary and start trusted runtime provenance
05e0e00 feat: add deterministic trusted runtime bundle
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

### V1B4 — COMPLETE / Trusted Python Runtime

V1B4 is split into four top-level evidence boundaries:

```text
V1B4A  Runtime Source Provenance Gate                 VERIFIED
V1B4B  Deterministic Runtime Bundle Gate              VERIFIED
V1B4C  Active Trusted Runtime Attestation             VERIFIED
V1B4D  Same-Run Runtime Capability Lease              VERIFIED
```

#### V1B4A — VERIFIED / Runtime source provenance

The host `.venv` was rejected as a trust source. Two official CPython embeddable archives were measured without executing either interpreter:

```text
CPython 3.12.10 AMD64  provenance reference   VERIFIED
CPython 3.13.15 AMD64  execution candidate    VERIFIED
```

Pinned CPython 3.13.15 identities:

```text
runtime ZIP SHA-256:         d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf
SPDX SHA-256:                ba428f93acb06764f0005246f8ca48bb1c04feef64ce7db0b177fb2fd371c423
outer manifest:              808b0be8715e1f5d61ef1802010a9d6cab23504a786405d7c490b223c96d3640
stdlib manifest:             89066e5e62decc5b0e96b2593e319fbc2338ef3b0e362ac107fa2b117a7480a2
source fingerprint:          6027ca87d35d94fa131d64c8210e5c6f5002f801274752421e480a9a180dba45
provenance policy:           232d65ce4fdb9d990e588f15133db3593cb69f31c5d4e3dfece28b79b827c503
interpreter_executed:        false
execution_authorized:        false
```

#### V1B4B — VERIFIED / Deterministic runtime bundle

Code closure:

```text
05e0e00 feat: add deterministic trusted runtime bundle
```

Verified derived identity:

```text
source files:                34
bundle files:                37
bundle bytes:                21 346 903
tree manifest:               ab35bf73bf387d28cd14bdcf85c545706ae7522212f466bf10afbaf1e14ac7ed
runtime manifest:            41503dc1b9c109b6cfb652e6ff320b5011c78f529f3559720ad1788f4787967d
bundle fingerprint:          1c98ad24ec3e4bb1b8b4bcd530ffedcf6ff62a6fee5b94cb795f6c84fb1c8c4b
locked python313._pth:       44b7d2b931284d125d88b833eaa28c711504aafd49415bd5bcc7c076a4d18006
trusted probe:               33b74a058990ae4f9f0077cb6cbfaa60ad266050d04cf670121d96db929e5c9d
trusted runner:              d03e21a1867914b87dec61de67bfd0f80637ab5b15948e8d8e6d73839a322de1
launch contract:             8fedb32153b6227a61b699dd5a34d610c430883b4ddafc96f931f0757138cef6
interpreter_executed:        false
execution_authorized:        false
```

Verification closure:

```text
portable runtime-bundle gate:                    31/31
real Windows exact-source bundle gate:            5/5
developer_task_execution_runtime_bundle flow:     completed successfully
full check:                                        completed successfully
runtime architecture audit:                        9/9
```

The builder re-verifies the exact CPython source, creates a fresh flat staging tree, rereads exact bytes from disk, rejects reparse/special entries, removes staging, and returns only a non-serialized exact-byte capability. It does not launch `python.exe`, Sandbox, worker code, patch code or dependency installation.

#### V1B4C — VERIFIED / Active Trusted Runtime Attestation

Architecture review now separates the verified payload, pure host verifier and first active interpreter run:

```text
V1B4C1   Runtime Attestation Contract and Payload Gate   VERIFIED
V1B4C2A  Signed Runtime Transcript Verifier              VERIFIED
V1B4C2B  Active Trusted Runtime Composition              VERIFIED
```

##### V1B4C1 — VERIFIED

Code closure:

```text
9a85bb1 feat: add trusted runtime attestation contract payload
```

Verification closure:

```text
portable contract/payload gate:                 33/33
real Windows compile/parse-only smoke:            3/3
mapped folders:                                     4
read-only mappings:                                 3
writable mappings:                                  1
native helper compiled:                          true
bootstrap/controller/WSB parsed:                 true
Windows Sandbox launched:                       false
candidate interpreter executed:                 false
targeted flow:                    completed successfully
full check:                       completed successfully
runtime architecture audit:                       9/9
execution_authorized:                            false
```

The exact policy fingerprint is `31c4f8de17e999db2d064a8aca4e95d3e2400f21a229317e83b1d5700d1e3c48`; after the true-ephemeral-key hardening the exact payload fingerprint is `47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13`. Historical V1B3 fingerprints remain unchanged.

##### V1B4C2A — VERIFIED / Signed Runtime Transcript Verifier

Code closure:

```text
4a68c3c feat: add signed runtime transcript verifier
```

Verification closure:

```text
portable verifier gate:                          46/46
real Windows CNG verification:                    3/3
exact signed transcript:                     accepted
mutated terminal message/signature:          rejected
targeted flow:                    completed successfully
full check:                       completed successfully
runtime architecture audit:                       9/9
Windows Sandbox launched:                       false
candidate interpreter executed:                 false
execution_authorized:                           false
```

The verifier independently binds request ID, host nonce, authorization nonce, timing windows, C1 policy/payload, every V1B4B runtime identity, public key, request/ready/authorize/runtime-result hashes and exact terminal bytes. Windows CNG is the production final signature path. The verifier has no filesystem, process, Sandbox, runtime-builder or workspace execution surface.

##### V1B4C2B — VERIFIED / Active Trusted Runtime Composition

Code closure:

```text
049e4ca feat: add active trusted runtime composition
```

Verification closure:

```text
V1B4C1 portable gate:                         33/33
V1B4C2A portable verifier:                    46/46
V1B4C2B portable state/failure gate:           42/42
V1B4C1 Windows compile-only smoke:              3/3
V1B4C2A Windows CNG smoke:                      3/3
V1B4C2B active Windows composition:             3/3
status:                   active_trusted_runtime_attested
payload fingerprint:      47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13
ready received:                              18 250 ms
authorization published:                     18 297 ms
runtime result detected:                     23 875 ms
terminal detected:                           26 172 ms
all Sandbox processes exited:                37 860 ms
total:                                       39 641 ms
pin/signature/runtime/terminal verified:         true
forced cleanup attempted:                        false
artifacts removed:                                true
interpreter_executed:                             true
reusable_lease_issued:                            false
execution_authorized:                             false
targeted flow:                    completed successfully
full check:                       completed successfully
runtime architecture audit:                       9/9
```

The run rebuilt and materialized the exact 37-file CPython 3.13.15 capability, used a true-ephemeral ECDSA P-256 key, preserved subsecond authorization timing, executed only the fixed benign probe as the fresh standard user inside the Job Object, trusted writable output only after full Sandbox exit, verified the exact signed transcript through Windows CNG and removed every private artifact without forced cleanup.

It accepts no developer-task manifest, workspace, patch, module, pipeline flow, caller argv/environment or shell command. The successful report is evidence only and does not create a reusable lease or execution authority.

Full contract: `docs/architecture/SKYNETVS_TRUSTED_PYTHON_RUNTIME_V1.md`.

#### V1B4D — VERIFIED / Same-Run Runtime Capability Lease

Code closure:

```text
18e8619 feat: add same-run trusted runtime capability lease
```

Verification closure:

```text
portable lease gate:                         36/36
real Windows host-only lease smoke:            5/5
policy fingerprint: 76ceaaf139af10814a403d24fca7455a61db78f095e80d390b360417354e8c18
TTL:                                      300 seconds
clock:                              time.monotonic_ns()
same exact runtime capability claimed:          true
replay rejected:       runtime_lease_already_claimed
Sandbox processes after claim:                    []
interpreter_executed:                           false
execution_authorized:                          false
targeted flow:                   completed successfully
full check:                      completed successfully
runtime architecture audit:                      9/9
```

The first real Windows claim exposed a one-second boot-epoch quantization mismatch between fresh-host equivalence and the canonical binding check. The fix keeps exact issuance-snapshot binding while allowing only the already measured one-second fresh-host equivalence rule; two-second drift and every other bound host/runtime change remain fail-closed.

#### V1B4 — COMPLETE

The trusted-runtime chain is fully verified through the process-local single-use lease and is fixed by `skynet-trusted-runtime-v1b4` at `91d8c37`. This does not authorize changed-code execution. The Pro Standard V1C architecture review is now complete and starts with a non-executing inventory gate.

V1B4D is the verified host-only lease slice. It creates a process-local, non-serialized, non-copyable, single-use capability with a fixed monotonic `300`-second TTL. Issuance requires fresh successful host evidence, an empty Sandbox process set and the exact in-memory V1B4B bundle capability. A completed V1B4C2B report is not an input and cannot authorize a new run.

Locked implementation scope:

```text
A modules/developer/developer_task_execution_runtime_lease_policy.py
A modules/developer/developer_task_execution_runtime_lease.py
A tools/eval_developer_task_execution_runtime_lease.py
A tools/eval_developer_task_execution_runtime_lease_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

The lease binds exact backend, host, runtime and V1B4C identities plus a one-time secret; one atomic claim is allowed. Expiry, replay, concurrent second claim, host drift, runtime substitution or policy mismatch invalidates it. V1B4D itself launches neither Sandbox nor Python, accepts no changed-code input and returns `execution_authorized=false`.

### Текущий жёсткий scope

V1B может запускать только trusted probe/controller/benign worker. Он не запускает:

- `python_module` из manifest;
- `pipeline` из manifest;
- произвольный shell;
- код из изменённого workspace;
- установку или скачивание зависимостей;
- commit, merge, push или promotion.

### Mode decision

V1B3A–V1B3D and V1B4A–V1B4D are VERIFIED; V1B4 is COMPLETE and tagged. V1C0A and V1C0B1 are VERIFIED through `e090f63`. Roadmap Changes 013–014 lock V1C0B2 and the V1C1 snapshot/plan contract in **Pro Standard**. V1C1A/V1C1B are now bounded host-only implementation and may run on **Очень высокий**; return to **Pro Standard** before V1C2A/V1C2B/V1C2C active changed-source architecture.

## 14. VERIFIED V1C0A/V1C0B1 / LOCKED V1C0B2 — External Source Authority

V1C0A and V1C0B1 are closed at:

```text
b039ce1 feat: add canonical executable check environment inventory
e090f63 feat: add canonical host toolchain observation
HEAD == origin/main:                       true
stable V1B4 tag:                           91d8c37fc4afe7ef138e36063e7bc22014da8a2c
V1C0A portable evaluator:                  27/27
V1C0B1 portable evaluator:                 26/26
package boundaries:                        28/28
pre-commit targeted flow:                  completed successfully
pre-commit full check:                     completed successfully
post-commit V1C0A Windows smoke:           1/1
post-commit V1C0B1 Windows smoke:          1/1
```

Post-commit exact inventory and observation at `e090f63`:

```text
tracked files / Python files:              252 / 234
Python bytes:                              3,257,957
Python tree fingerprint:                   235fb61106d53245d4716eaf4aa1da2defa3d684b974a8a5801ebf0cd1016f38
pipeline flows / all steps:                91 / 445
check steps:                               86
process-launch call sites:                 38
host-sensitive files:                     25
inventory fingerprint:                    574cdc81c154c04ade6e26aec520cac243ddf5e15f1780037c57bf3ae88d1956
observation fingerprint:                  aa2f63f41523480f4e423d57e15e02883b70709e34e1dd108c72e977b36e6035
host Python / pip:                         3.12.10 / 25.3
host distributions:                       61
host Git:                                 2.45.1.windows.1
host Git tree:                            6356 files / 419125157 bytes
host Git tree SHA-256:                    41f001b961349b0e0e2e89b2843671a2052d176c3472de83c447919058c082d6
host PowerShell:                          5.1.26100.9168
```

Exact committed dependency declarations remain:

```text
requirements.txt          9e283f2050b97e229b4600ca2b1339184b96d1cebc8f90730547a4fb790142b4
requirements-train.txt    65052d0da1b23c12505497325e0064568dcd9c25b368e1cfe1e5be5a12b81ced
requirements-whisper.txt  c5bc4d0891d158b7e8ec5c26b6b68dfcb0b60e8414c9f1ba3040993ea390129d
```

All V1C0A/V1C0B1 non-authorizing flags remained false:

```text
source_authority_selected        false
artifact_download_attempted      false
dependency_install_attempted     false
sandbox_launched                 false
candidate_interpreter_executed   false
reusable_lease_issued            false
execution_authorized             false
```

Roadmap Change 013 closes V1C0B2 as a source-policy lock:

```text
V1C0A  Canonical Executable Check Inventory Gate             VERIFIED
V1C0B1 Canonical Host Toolchain Observation Gate             VERIFIED
V1C0B2 External Source Authority Selection Lock              LOCKED
V1C1A  Canonical Patched Workspace Snapshot Bundle           VERIFIED
V1C1B  Typed Compile/AST Plan Capability                     CURRENT / HOST-ONLY IMPLEMENTATION
V1C2A  Compile/AST Guest Contract and Fixed Runner           PLANNED
V1C2B  Signed Compile/AST Transcript Verifier                PLANNED
V1C2C  Active Compile/AST Sandbox Composition                BLOCKED / PRO REQUIRED
V1C3A  Python Dependency Source Provenance                   PLANNED
V1C3B  Deterministic Python Check Dependency Bundle          PLANNED
V1C3C  Portable Git Source Provenance and Bundle             PLANNED
V1C4A  Changed-Code Execution Contract and Guest Payload     PLANNED
V1C4B  Signed Changed-Code Transcript Verifier               PLANNED
V1C5   Active Sandboxed python_module Check                  BLOCKED
V1C6   Active Sandboxed Guest-Safe Pipeline Check            BLOCKED
V1C7   Composite Typed Check Runner and Result Evidence      BLOCKED
```

Locked V1C0B2 source authority:

```text
decision ID:          skynetvs-v1c0b2-external-source-authority-lock-v1
decision fingerprint: 80da155e8de0ce9f6d17565541173b701c2d5c9c8a8c13f1fcab9a57dbdb3d5e
```

- host `.venv`, host Git and host PowerShell are observation only;
- canonical Python index metadata is PyPI Simple API JSON v1 with a supported `1.x` response at API `1.4` or newer;
- canonical Python bytes are exact `files.pythonhosted.org` wheels named by that response and verified by filename, size and SHA-256;
- target is CPython 3.13 AMD64 / `win_amd64`; yanked, pre-release, sdist, local-build, direct-URL, extra-index and host-cache fallback are rejected by default;
- a version-pinned resolver can propose candidates but never becomes authority; final direct/transitive closure is independently rebuilt and fingerprinted;
- core-metadata hashes and PyPI provenance are verified when present; attestation proves publishing identity, not package safety, and absence is recorded explicitly;
- portable Git authority is an immutable official Git for Windows release tag plus the standard `MinGit-<version>-64-bit.zip`, release-published SHA-256, exact archive and deterministic extracted tree;
- current review candidate only: `v2.55.0.windows.4`, `MinGit-2.55.0.4-64-bit.zip`, SHA-256 `4e03f94c2ffbf70be337e005cee02661c732dbfc81031a078bda9299b9a7d644`;
- `latest`, BusyBox MinGit, PortableGit, installers, host Git and a single launcher hash are not authority;
- network is allowed only in future dedicated host acquisition gates with exact origin/redirect allowlists and scrubbed credential/index/proxy environment; guest/runtime network remains forbidden;
- exact Python wheel/version closure remains V1C3A; exact MinGit pin/tree remains V1C3C.

Verified V1C0B1 public API:

```python
observe_developer_task_execution_host_toolchain(
    inventory_report: DeveloperTaskExecutionEnvironmentInventoryReport,
    *,
    project_root: Path,
) -> DeveloperTaskExecutionHostToolchainReport
```

Verified V1C0B1 implementation scope:

```text
A modules/developer/developer_task_execution_toolchain_observation_policy.py
A modules/developer/developer_task_execution_toolchain_observation.py
A tools/eval_developer_task_execution_toolchain_observation.py
A tools/eval_developer_task_execution_toolchain_observation_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

## 15. LOCKED V1C1 — Immutable Snapshot and Typed Compile/AST Plan

The read-only V1C1 context archive is verified:

```text
archive SHA-256:                    fdc0ea63f8765b97c63c68d55c85bbb0cce6994bd0f0cc83036cb6febbf37d0d
manifest payloads:                   49/49
HEAD / origin/main:                  90d2bd51f57d07881725017cc92cb55cc4d7829b
stable V1B4 tag:                     91d8c37fc4afe7ef138e36063e7bc22014da8a2c
tree files / bytes:                  252 / 3,528,329
Python files / bytes:                234 / 3,257,957
largest file / Python file:          83,256 / 71,872
Git modes:                           252 x 100644
non-blob / NUL / unsafe / collision: 0 / 0 / 0 / 0
Python encodings:                    234 x UTF-8
line endings:                        246 LF / 6 none
tree manifest SHA-256:               b1e82bf0a3fb8a901c0ac37825d74c8de426f34d02f67d0b05a710be2b4962ba
```

Locked identity:

```text
decision:        skynetvs-v1c1-snapshot-plan-architecture-lock-v1
decision fp:     20f26ef8728a77ea87b22d791ebf4da5940312c48e589cf6c17a89765428ad30
V1C1A policy fp: 601c727e9b725f1f868a144fa7b975bbb7a35a878c74c2d25bda0a7677a6cd55
V1C1B policy fp: f017f401254647002347802c5deba6397bdddf27eaa08d02640dc8389fe80865
```

V1C1A snapshot rules:

- authority is exact `DeveloperTaskPatchApplyReport.result_tree`, never mutable worktree bytes;
- typed manifest/preflight/workspace/patch-apply/static-check evidence is cross-bound and freshly re-inspected before/after capture;
- only regular `100644` blobs; `4096` files, `8 MiB` per blob, `16 MiB` total, `4 MiB` manifest;
- paths `240/120/32`, NFC, Windows-safe; symlink/gitlink/non-blob/collision rejected;
- each blob is independently SHA-256 bound; exact bytes are private, process-local, non-copyable/non-pickleable, single-use, `300` seconds with a `32`-byte secret;
- no runtime lease, Sandbox, interpreter, network, install or changed-code execution.

V1C1A verification closure:

```text
implementation commit:             7b174610e6dde4e1e28a6ae5fb1f357ac0ad93e2
commit message:                     feat: add canonical patched workspace snapshot
pre-commit portable gate:           37/37
pre-commit Windows smoke:           1/1
pre-commit full check:              completed successfully
post-commit V1C0A Windows smoke:    1/1
post-commit V1C1A Windows smoke:    1/1
tracked files / Python files:       256 / 238
Python bytes:                       3,371,260
pipeline flows / total steps:       92 / 459
pipeline check steps:                87
process-launch call sites:            40
host-sensitive files:                 26
inventory fingerprint:               1d6df3788467909e758c172bee1289ac0fda65915c1646304b257e69ae17f96b
```

The post-commit snapshot smoke preserved exact selected bytes and all source/workspace Git evidence while every mutation, network, install, Sandbox, runtime-lease, candidate-interpreter, changed-code, reusable-authority and `execution_authorized` flag remained `false`. V1C1A is VERIFIED.

V1C1B plan rules:

- atomically consumes one V1C1A snapshot;
- fixed operation `compile_ast_changed_python_v1`;
- selects only changed `.py` paths still present; deletion/non-Python facts are record-only;
- `1..20`, `2 MiB` per source, `8 MiB` total, mode `100644`, UTF-8, LF/empty, no NUL;
- caller cannot provide executable, argv, path list, environment, encoding, limits, module, flow or runner;
- private process-local single-use capability, `300` seconds; no runtime lease or execution.

Future V1C2C double claim is fixed: plan capability first, fresh V1B4D runtime lease second. Either failure is terminal. The workspace and `.git` are never mapped.

### Следующее точное действие

1. Commit only the three architecture-document changes that close V1C1A and mark V1C1B CURRENT.
2. Keep `skynet-trusted-runtime-v1b4` fixed at `91d8c37`.
3. Do not rerun the full pipeline after this docs-only transition; V1C1A pre-commit full check and both post-commit Windows smokes are already green.
4. Stay on **Очень высокий** and implement V1C1B as the bounded host-only typed `compile_ast_changed_python_v1` plan capability.
5. V1C1B must atomically consume exactly one V1C1A snapshot and must not accept caller paths, executable, argv, environment, encoding, limits, module, flow or runner.
6. Keep all V1C1 flags false: no runtime lease, Sandbox, candidate interpreter, changed-code execution or authorization.
7. After V1C1B implementation/evidence is committed, return to **Pro Standard** before V1C2A/V1C2B/V1C2C.

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
05e0e00 feat: add deterministic trusted runtime bundle
c63e519 docs: close runtime bundle and split active runtime attestation
9a85bb1 feat: add trusted runtime attestation contract payload
192cad3 docs: close runtime payload and start signed runtime verifier
4a68c3c feat: add signed runtime transcript verifier
c86d8eb docs: close signed runtime verifier and start active composition
049e4ca feat: add active trusted runtime composition
6500fee docs: close active runtime and start capability lease
18e8619 feat: add same-run trusted runtime capability lease
91d8c37 docs: close trusted runtime and prepare sandboxed checks
f36f92f docs: split sandboxed checks into inventory and execution gates
b039ce1 feat: add canonical executable check environment inventory
f069ca9 docs: close executable inventory and split toolchain source authority
e090f63 feat: add canonical host toolchain observation
90d2bd5 docs: lock external toolchain source authority
859be92 docs: lock immutable workspace snapshot and compile plan
7b17461 feat: add canonical patched workspace snapshot
tag skynet-trusted-runtime-v1b4 -> 91d8c37
```

V1C0A and V1C0B1 are VERIFIED through `e090f63`; V1C1A is VERIFIED through `7b17461`. Roadmap Change 013 locks V1C0B2 source classes and Roadmap Change 014 locks V1C1A/V1C1B snapshot/plan architecture. V1C1B host-only implementation is current and the stable V1B4 tag must not move.

## 17. DEFERRED

- Typed Check Runner V1C2–V1C7 — active compile/AST, toolchain provenance and sandboxed executable checks.
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

Threat model, result-authenticity model, V1B4 and Roadmap Changes 011–014 are approved in **Pro Standard**.

V1C0A/V1C0B1 are VERIFIED; V1C0B2 and V1C1 architecture are LOCKED. V1C1A/V1C1B are bounded host-only implementation and should run on **Очень высокий**. Return to **Pro Standard** before V1C2 active Sandbox composition, exact PyPI wheel closure or MinGit pinning.

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
data/logs/pipeline/*_developer_task_execution_runtime_bundle.log
data/logs/pipeline/*_developer_task_execution_runtime_attestation.log
data/logs/pipeline/*_check.log
latest signed-boundary and active-composition evidence
```

Новый чат должен продолжать с раздела **«Следующее точное действие»**, а не восстанавливать roadmap по памяти.
