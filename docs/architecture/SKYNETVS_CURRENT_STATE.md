# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-19`
- Ветка: `main`
- Проверенный code baseline перед этим documentation commit: `aa97b779441196b1586d317344f3a82d05411874`
- Название code baseline: `feat: add fixed compile ast controller worker bundle`
- `origin/main` на проверенной code-точке: `aa97b779441196b1586d317344f3a82d05411874`
- Documentation HEAD после сохранения этого файла определяется фактическим `git log -1`; self-referential commit SHA в содержимом не фиксируется.
- Исторический foundation-тег: `skynet-runtime-foundation-v1` → `09f8708`
- Стабильный trusted-runtime тег: `skynet-trusted-runtime-v1b4` → `91d8c37fc4afe7ef138e36063e7bc22014da8a2c`
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

V1B3A–V1B3D and V1B4A–V1B4D are VERIFIED; V1B4 is COMPLETE and tagged. V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1 are VERIFIED through `aa97b77`. Roadmap Changes 013–018 lock V1C0B2, V1C1, V1C2 and the V1C2C split. V1C2C2 active compile/AST Sandbox composition is CURRENT in **Pro Standard**; V1C2C3 remains blocked.

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
V1C1B  Typed Compile/AST Plan Capability                     VERIFIED
V1C2A1 Canonical Compile/AST Request, Result and Terminal Contract VERIFIED
V1C2A2 Fixed Guest Runner and Payload Bundle                 VERIFIED / NON-AUTHORIZING
V1C2B  Signed Compile/AST Transcript Verifier                VERIFIED / NON-AUTHORIZING
V1C2C0 Process-Local Plan/Runtime Claim Transaction          VERIFIED / NON-AUTHORIZING
V1C2C1 Fixed SYSTEM Controller and Worker Payload Bundle       VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2 Active Compile/AST Sandbox Composition                  CURRENT / PRO ACTIVE SECURITY IMPLEMENTATION
V1C2C3 Live Pass/Syntax/Boundary Acceptance                    BLOCKED / PRO REQUIRED
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

### V1C1B verification closure and V1C2 architecture lock

```text
V1C1B code closure:                  70fc763 feat: add typed compile ast plan capability
V1C1B portable evaluator:            35/35
V1C1B real Windows smoke:             1/1
pre-commit full check:                completed successfully
post-commit V1C0A Windows smoke:      1/1
post-commit V1C1B Windows smoke:      1/1
tracked files / Python files:         260 / 242
Python bytes:                         3,453,149
pipeline flows / all steps:           93 / 474
check steps:                          88
process-launch call sites:            40
host-sensitive files:                 27
inventory fingerprint:                4c4316c3fdfa59ab5fc2e72e76364ae457a12c3545022300b30a486b4357d716
```

V1C1B again selected only exact `module.py` bytes, left deleted/non-Python paths as evidence, consumed the plan once and preserved all repository/workspace evidence. Every network/download/install/Sandbox/runtime-lease/interpreter/changed-code/reusable-authority flag remained false. V1C1B is VERIFIED.

Roadmap Change 015 locks:

```text
V1C2A1  Canonical Compile/AST Request, Result and Terminal Contract
V1C2A2  Fixed Guest Runner and Payload Bundle
V1C2B   Signed Compile/AST Transcript Verifier
V1C2C   Active Compile/AST Sandbox Composition

decision: 5382249191bcc8388d6b44862cabe7c24a586a6628814266461c0830e7dec08c
A1 policy: a3e7d50e92de8aa0799953874a71ce60b2d141e52791282e5fd38814aa9507bf
```

Authentic syntax failure is valid signed evidence and is distinct from a broken boundary. Original source paths are never guest filesystem paths; source bytes use flat fixed ordinal names. The runner may parse/compile import statements but never executes imports, top-level code or code objects. V1C2C remains blocked until A1/A2/B are independently verified.

### V1C2A1 verification closure

```text
implementation commit:                 ec68dd4170bab82131dcf88f3aaa7b98ebaa75b8
commit message:                         feat: add canonical compile ast transcript contract
package boundaries:                     28/28
V1C1B portable dependency gate:          35/35
V1C2A1 portable evaluator:               45/45
pre-commit Windows contract smoke:        1/1
pre-commit full check:                   completed successfully
Runtime Architecture Audit:               9/9
post-commit V1C0A Windows smoke:          1/1
post-commit V1C2A1 Windows smoke:         1/1
tracked files / Python files:            264 / 246
Python bytes:                            3,597,286
pipeline flows / all steps:              94 / 479
check steps:                             89
process-launch call sites:               40
host-sensitive files:                    28
inventory fingerprint:                   9f3bd41cdc379f126751e651dbcdd71cbc3380d7ac5bf57687b46dd48b5cd268
```

The committed contract binds canonical source-manifest/request/ready/authorize/result/terminal documents, exact field order and cross-document hashes. The Windows smoke again proved `compile_ast_attested_passed`, authentic bounded `compile_ast_attested_failed` and `compile_ast_boundary_failed`, while raw source text remained absent and every Sandbox/runtime-lease/interpreter/changed-code/reusable-authority/authorization flag remained `false`. V1C2A1 is VERIFIED.


### V1C2A2 verification closure

```text
implementation commit:                 b83d2966960a23ebf6930b8ba7ea4bd100cef0b3
commit message:                         feat: add fixed compile ast guest runner bundle
package boundaries:                     28/28
V1C2A1 portable dependency gate:        45/45
V1C2A2 portable evaluator:              40/40
pre-commit Windows bundle smoke:         1/1
pre-commit full check:                   completed successfully
Runtime Architecture Audit:               9/9
post-commit V1C0A Windows smoke:          1/1
post-commit V1C2A2 Windows smoke:         1/1
tracked files / Python files:            268 / 250
Python bytes:                            3,682,203
pipeline flows / all steps:              95 / 484
check steps:                             90
process-launch call sites:               40
host-sensitive files:                    29
Python tree fingerprint:                 358ecc4acdcd25163ac56e280c9c63e2d62c46f4f8ec89665bae12826e9cfb0a
inventory fingerprint:                   a39d47b9e9041dbe276cc73648fd37b57f614e9f94fbd731368f8e80b15cd5b3
V1C2A2 policy fingerprint:               825af298ba972e6c12ac0f85572935c7a8bd34ed4ee215cfa2af6e39a7e659c4
V1C2A2 bundle fingerprint:               b1f182ca4ee1a9e83cb6a32ca54e45d4511c81faa27d8dd4be7817883affb9f3
runner SHA-256:                           6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9
payload SHA-256:                          730d4108aab8246d1e6ff030a4d5a64ad25a89adf888e2b10c64ec63d56f60b6
```

The fixed bundle is deterministic and caller-independent, binds the exact V1C2A1 contract and trusted CPython runtime, and pins the isolated launch contract plus immutable runner/payload bytes. The runner rehashes request/payload/policy/manifest and every selected source, revalidates UTF-8/NUL/LF/runtime isolation, performs only `ast.parse` and `compile`, discards code objects and exposes no import execution, `exec`, `eval`, subprocess, shell, network or dependency-install surface. Both pre-commit and post-commit Windows evidence kept Sandbox launch, runtime-lease issue/claim, candidate-interpreter execution, changed-source processing/parsing/compilation, changed-code execution, reusable authority and `execution_authorized` false. V1C2A2 is VERIFIED and remains non-authorizing.

### V1C2B verification closure

```text
implementation commit:                  98f4cfe0ee1a71c327b35670d786ab11b9485c6b
commit message:                          feat: add signed compile ast transcript verifier
package boundaries:                      28/28
V1C2A1 portable dependency gate:         45/45
V1C2A2 portable dependency gate:         40/40
V1C2B portable evaluator:                44/44
pre-commit Windows CNG smoke:             1/1
pre-commit full check:                    completed successfully
Runtime Architecture Audit:                9/9
post-commit V1C0A Windows smoke:           1/1
post-commit V1C2B Windows CNG smoke:       1/1
tracked files / Python files:             272 / 254
Python bytes:                             3,763,805
pipeline flows / all steps:               96 / 490
check steps:                              91
process-launch call sites:                40
host-sensitive files:                     30
Python tree fingerprint:                  f73125f2281ef44f15fc13a8520d64a2522bb020610b13480bcf72b0df5ea0a4
inventory fingerprint:                    06f3794183eec0beede477f72eacc51ef5b991d81e69cbc3b3660daba3f7765f
V1C2B policy fingerprint:                 cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf
CNG smoke public-key SHA-256:              0bc654178e6f3d5e4ab8b170722a7b7a388a76d58c97031fcad019cf4bdb5e91
```

The committed verifier independently pins and reparses the V1C2A1 pre-authorization chain, binds the exact V1C2A2 policy/runner/payload identities, rejects forged typed reports and verifies the terminal P1363 ECDSA-P256 signature through Windows CNG. It preserves the distinction between authentic `compile_ast_attested_failed` evidence and `compile_ast_boundary_failed`, and it rejects replay, post-pin substitution, off-curve keys, malformed/noncanonical JSON, result/terminal mismatch and invalid timing. The verifier exposes no filesystem/process/Sandbox/network/source-processing surface and never authorizes changed code. Post-commit evidence kept Sandbox launch, runtime-lease issue/claim, candidate-interpreter execution, changed-source processing, changed-code execution, reusable authority and `execution_authorized` false. V1C2B is VERIFIED.

### Следующее точное действие

1. Commit only the three architecture-document changes for Roadmap Change 018: retain `d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484` as the immutable V1C2C2 architecture-slice identity and separate it from the future canonical active-composition implementation policy fingerprint and exact policy-document SHA-256.
2. Keep stable tag `skynet-trusted-runtime-v1b4` at `91d8c37fc4afe7ef138e36063e7bc22014da8a2c`; do not modify historical V1B4/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1 policies, payloads or fingerprints.
3. Do not run the full pipeline after this docs-only identity clarification. The documentation transition must change exactly `SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`, `SKYNETVS_CURRENT_STATE.md` and `SKYNETVS_TRUSTED_PYTHON_RUNTIME_V1.md`.
4. Implement V1C2C2 only in the locked seven-file scope: three compile-AST composition production modules, two evaluator modules, `tools/eval_package_boundaries.py` and `tools/pipeline.py`.
5. Expose only `attest_developer_task_execution_compile_ast_composition(host_report, transaction, *, artifact_parent)`; reject caller-controlled runtime paths, workspace/source paths, executable/argv/environment, timeouts, Job limits, WSB settings, signature verifier and fault-injection hooks.
6. Consume exactly one fresh V1C2C0 transaction inside composition, then materialize the exact retained runtime and selected flat source bytes, launch one fresh Sandbox, preserve the fixed four-folder mapping and LocalSystem → standard-user → Job boundary, and keep `CREATE_SUSPENDED`, assign-before-resume, no inherited handles and limits `1 / 512 MiB / 768 MiB`.
7. Pin request/ready/authorize before publication; trust result/terminal only after every known Sandbox process exits, all exact artifacts remain stable, V1C2B/CNG verification succeeds, fresh host evidence is unchanged and private artifacts are safely removed.
8. Keep `exec`, `eval`, import execution, top-level execution, bytecode writes, guest network/install, `python_module`, `pipeline`, commit/merge/push/promotion and reusable authority blocked. V1C2C3 remains BLOCKED until V1C2C2 is independently VERIFIED.

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
d19b85c docs: close workspace snapshot and start typed compile plan
70fc763 feat: add typed compile ast plan capability
8cd67ae docs: close typed compile plan and lock active compile boundary
ec68dd4 feat: add canonical compile ast transcript contract
c182f1e docs: close compile ast contract and start fixed guest runner
b83d296 feat: add fixed compile ast guest runner bundle
0c4ba9a docs: close fixed guest runner and start signed compile verifier
98f4cfe feat: add signed compile ast transcript verifier
b527f93 docs: close signed compile verifier and start active compile composition
b8057d1 docs: split active compile composition into claim payload and live gates
e6e355a feat: add process-local compile ast claim transaction
1ca04d6 docs: separate compile payload architecture and implementation identities
aa97b77 feat: add fixed compile ast controller worker bundle
tag skynet-trusted-runtime-v1b4 -> 91d8c37
```

V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1 are VERIFIED through `aa97b77`. Roadmap Changes 013–018 lock V1C0B2, V1C1, V1C2 and the V1C2C split. V1C2C2 active composition is current in Pro Standard and the stable V1B4 tag must not move.

## 17. DEFERRED

- Typed Check Runner V1C2C3–V1C7 — live acceptance, toolchain provenance and later sandboxed executable checks.
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

Threat model, result-authenticity model, V1B4 and Roadmap Changes 011–018 are approved in **Pro Standard**.

V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1 are VERIFIED; V1C0B2, V1C1, V1C2 and the V1C2C split are LOCKED. V1C2C2 active composition is CURRENT and requires **Pro Standard** because it consumes the one-run capability boundary and launches the first changed-source Sandbox composition. V1C2C3, exact PyPI wheel closure and MinGit pinning also require Pro Standard.

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
data/logs/pipeline/*_developer_task_execution_compile_ast_claim_transaction.log
data/logs/pipeline/*_developer_task_execution_compile_ast_controller_worker.log
data/logs/pipeline/*_v1c2c1_postcommit_windows_evidence.txt
data/logs/pipeline/*_check.log
latest signed-boundary and active-composition evidence
```

Новый чат должен продолжать с раздела **«Следующее точное действие»**, а не восстанавливать roadmap по памяти.

### V1C2C exact source-context closure and Roadmap Change 016

```text
context HEAD / origin:                b527f93037595ccac0cfe731c46c5012663fc3d1
stable V1B4 target:                   91d8c37fc4afe7ef138e36063e7bc22014da8a2c
context archive SHA-256:              f5883188e4aa2119c849f2adbc449b73072ede208f742f6ededb42ae783aa08d
context fingerprint:                  8cd54944d3e9873f8af267adf86d4e0d220c947dc3578d88140849ba8366e63c
manifest files / bytes:               70 / 1,984,377
payload size/hash mismatches:         0 / 0
repository_mutated:                   false
sandbox_launched:                     false
runtime_lease_claimed:                false
changed_source_processed:             false
execution_authorized:                 false
```

The exact audit found that `V1C2A1` serializes `runtime_lease_fingerprint`, while the current V1B4D status has no public per-instance identity and its private binding hash is stable for the same host/runtime snapshot. V1C2C therefore cannot safely serialize that private hash as a one-run lease identity. Roadmap Change 016 introduces a separate process-local transaction that reserves and stores the exact plan and lease objects privately and publishes a fresh one-run binding fingerprint without changing the stable V1B4D claim return type.

Final split:

```text
V1C2C0  Process-Local Plan/Runtime Claim Transaction Capability     VERIFIED
V1C2C1  Fixed SYSTEM Controller and Standard-User Worker Bundle     VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2  Active Compile/AST Sandbox Composition                      CURRENT / PRO ACTIVE SECURITY IMPLEMENTATION
V1C2C3  Live Pass / Syntax-Failure / Boundary-Failure Acceptance    BLOCKED
```

Locked identities:

```text
decision fingerprint:  56bfd2ca196ca2b6d8f6ad426ea06141fe1535a28a281f0d7661bc8e32ee8ff6
V1C2C0 policy:         092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa
V1C2C1 architecture slice identity: db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec
V1C2C2 architecture slice identity: d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484
V1C2C3 evidence:       b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

The V1C2C0 transaction reserves one exact plan and one exact runtime lease and is issued without claiming either capability. Its irreversible path is plan claim first and runtime-lease claim second, with no fallible filesystem/materialization operation between them. If the second claim fails, the plan remains consumed and no retry may reuse the transaction. V1C2C1 remains deterministic and host-only. V1C2C2 is the only slice allowed to materialize exact sources/runtime and launch Sandbox. V1C2C3 requires three fresh runs: attested pass, authentic syntax failure, and an eval-only post-ready/pre-authorization source substitution producing a signed boundary failure.

V1C2C1 is independently VERIFIED. Active changed-source processing remains blocked until the V1C2C2 portable pre-commit gate is green and V1C2C2 performs the one fresh Sandbox composition.

### V1C2C1 implementation identity clarification — Roadmap Change 017

The exact verified V1C2C context archive contains no canonical policy JSON or preimage for the Roadmap Change 016 value `db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec`. That value therefore remains the immutable architecture-slice identity and is not represented as the SHA-256 of newly invented implementation bytes.

The concrete host-only implementation is separately self-verifying:

```text
policy ID:          skynetvs-v1c2c1-fixed-system-controller-standard-user-worker-bundle-v1
semantic policy fp: 0a559e9a9bcac241a18b0e3cbe31263f4f01a5a94eaf70ee7d65382297a62baf
policy bytes SHA:   1d9b1c66bf3971a3fdedfb077ef8deb08467e29acbc4f725d7050e3ae1342091
bootstrap SHA:      7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d
native helper SHA:  901373a63df349e245a0c90887779b2cdb7f204dee98535c95bdc235844bb7a1
controller SHA:     f30d115d5a9dc2da2dd9e2d9dbeca3929b9497d35e700dec175d9399aac49996
WSB template SHA:   81861905167211b29fbff7179878b6b671c31b731af482166913b5e20416375f
bundle fingerprint: bd30bec84c8cbdd37940c0e1bb4b34f3cd6c0aed72d05c326afef118f53cd50c
```

Locked implementation scope:

```text
A modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
A modules/developer/developer_task_execution_compile_ast_controller_worker.py
A tools/eval_developer_task_execution_compile_ast_controller_worker.py
A tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

This clarification changes no stage order, threat model, active boundary or stable tag. The exact implementation and required Windows/full-pipeline evidence are now independently verified; V1C2C1 remains non-authorizing and its identities are immutable.

### V1C2C2 implementation identity clarification — Roadmap Change 018

The exact current source-context archive was collected from documentation HEAD `e2621ca5094eb7140323dcecb97b27ab9605ae65` / tree `369f8364df27898cb86a4754147d769ba0070bb0` and independently matched the committed tree:

```text
HEAD / origin/main:                  e2621ca5094eb7140323dcecb97b27ab9605ae65
stable V1B4:                         91d8c37fc4afe7ef138e36063e7bc22014da8a2c
tracked files / Python files:        280 / 262
archive files:                       280
archive SHA-256:                     7cda253ce704cc028900e7b3d7da59340dd3da6f2b5cb60305cdc00fa4ccb50b
working tree:                        clean
repository_mutated:                  false
```

The current archive and the historical V1C2C architecture context contain `d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484` only as the locked Roadmap Change 016 identity. Neither contains a canonical V1C2C2 policy document or preimage for that value. Roadmap Change 018 therefore keeps it as the immutable architecture-slice identity and requires the concrete implementation to use the separate policy ID `skynetvs-v1c2c2-active-compile-ast-sandbox-composition-v1`, a reproducible semantic policy fingerprint and an exact canonical policy-document SHA-256.

Locked public API:

```python
attest_developer_task_execution_compile_ast_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionCompileAstCompositionReport
```

Locked implementation scope:

```text
A modules/developer/developer_task_execution_compile_ast_composition_policy.py
A modules/developer/developer_task_execution_compile_ast_composition_fs.py
A modules/developer/developer_task_execution_compile_ast_composition.py
A tools/eval_developer_task_execution_compile_ast_composition.py
A tools/eval_developer_task_execution_compile_ast_composition_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

This clarification does not authorize an active run by itself. V1C2C2 remains CURRENT; V1C2C3 remains BLOCKED. The stable tag and every historical implementation identity remain unchanged.

### V1C2C0 verification closure

```text
implementation commit:                    e6e355ab3238565bb9d685f503647da6a487c919
commit message:                            feat: add process-local compile ast claim transaction
package boundaries:                        28/28
V1C1B typed plan dependency gate:           35/35
V1B4D runtime lease dependency gate:        36/36
V1C2C0 portable evaluator:                  38/38
pre-commit Windows transaction smoke:        1/1
pre-commit full check:                      completed successfully
Runtime Architecture Audit:                  9/9
post-commit V1C0A Windows smoke:             1/1
post-commit V1C2C0 Windows smoke:            1/1
tracked files / Python files:               276 / 258
Python bytes:                               3,873,221
pipeline flows / all steps:                 97 / 496
check steps:                                92
process-launch call sites:                  40
host-sensitive files:                       31
Python tree fingerprint:                    f7af9a590320fb6a17178b8baa2785a0981ea83a22f9c8f393261ec38b599088
inventory fingerprint:                      d10f6fb0c9a72419c0d63c1445253c692a90010a97ee834dfefe5015abf2289a
```

The committed process-local transaction is single-use and non-serializable, reserves exact plan/lease objects without claiming them, publishes a unique non-secret one-run fingerprint, and consumes plan first and runtime lease second. Portable evidence proves duplicate-reservation rejection, terminal expiry, fail-closed guard/nonce/policy tamper handling, plan-preserving behavior when an already-consumed lease is detected before claim, and irreversible plan consumption if the lease claim fails after plan claim. The Windows smoke retained exact source bytes and the exact runtime bundle, left source/workspace Git evidence unchanged, found no running Sandbox processes or residual artifacts, and kept repository mutation, network/download/install, Sandbox launch, candidate-interpreter execution, changed-source processing, changed-code execution, reusable authority and `execution_authorized` false. V1C2C0 is VERIFIED; V1C2C1 is VERIFIED / HOST-ONLY / NON-AUTHORIZING; V1C2C2 is CURRENT.

### V1C2C1 verification closure

```text
implementation commit:                  aa97b779441196b1586d317344f3a82d05411874
parent documentation commit:            1ca04d6568e687d8addd956eb4f9b6b0926ccdbe
commit message:                          feat: add fixed compile ast controller worker bundle
package boundaries:                      28/28
V1C2A1 dependency gate:                  45/45
V1C2A2 dependency gate:                  40/40
V1C2B dependency gate:                   44/44
V1C2C0 dependency gate:                  38/38
V1C2C1 portable evaluator:               33/33
pre-commit Windows compile smoke:         3/3
pre-commit full check:                   completed successfully
Runtime Architecture Audit:               9/9
post-commit V1C0A Windows smoke:          1/1
post-commit V1C2C1 Windows smoke:         3/3
post-commit targeted flow:               completed successfully
tracked files / Python files:            280 / 262
Python bytes:                            4,027,150
pipeline flows / all steps:              98 / 504
check steps:                             93
process-launch call sites:               41
host-sensitive files:                    34
Python tree fingerprint:                 5b58b6120524609c8f0d378d69bfa9316d65709f4ea2fe669f8c5334e1e59be3
inventory fingerprint:                   3c7cae90bdcd2584676c6cb82203af43658236602f683b83b0c377b6d9a36cad
HEAD == origin/main:                     true
working tree:                            clean
stable V1B4:                             91d8c37fc4afe7ef138e36063e7bc22014da8a2c
```

Exact committed scope:

```text
A modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
A modules/developer/developer_task_execution_compile_ast_controller_worker.py
A tools/eval_developer_task_execution_compile_ast_controller_worker.py
A tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

The committed deterministic bundle binds the architecture decision `56bfd2ca196ca2b6d8f6ad426ea06141fe1535a28a281f0d7661bc8e32ee8ff6`, architecture slice `db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec`, semantic policy `0a559e9a9bcac241a18b0e3cbe31263f4f01a5a94eaf70ee7d65382297a62baf` and bundle `bd30bec84c8cbdd37940c0e1bb4b34f3cd6c0aed72d05c326afef118f53cd50c`. It fixes a LocalSystem controller contract, fresh standard-user medium-integrity worker, sanitized environment, no inherited handles, `CREATE_SUSPENDED`, assign-before-resume and Job limits `1 / 512 MiB / 768 MiB`.

The Windows smoke compiled the exact native helper and parsed the fixed bootstrap/controller/policy/WSB payloads only. Sandbox launch, transaction consumption, runtime-lease claim, candidate-interpreter execution, changed-source processing, changed-code execution, reusable authority and `execution_authorized` all remained false. V1C2C1 is VERIFIED / HOST-ONLY / NON-AUTHORIZING; V1C2C2 is CURRENT in Pro Standard and V1C2C3 remains BLOCKED.
