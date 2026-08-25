# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-25`
- Ветка: `main`
- Проверенный code baseline перед этим documentation commit: `f0a2da9bf96d9010b6df42ae79104e58c15a9838`
- Название code baseline: `fix: verify signed controller evidence over untrusted WSB transport`
- `origin/main` на проверенной code-точке: `f0a2da9bf96d9010b6df42ae79104e58c15a9838`
- Точный documentation baseline перед Roadmap Change 021: `9a3f227685c6fd7e1097c371ce54137eb0a1c663`, tree `4e6ff04c3f1ce2ca30b8e77e6d74be0c708ef073`.
- Roadmap Change 021 documentation commit: `b3cfad02c99aa283d9516a0d35c93d3edff21324` (`docs: record R2 guest failure and authorize diagnostic capture`).
- Roadmap Change 022 documentation commit: `bdd23feacfba4032f8bf9be76dae94a5d670bf68` (`docs: close guest failure capture and authorize suspended worker localization`).
- Roadmap Change 023 documentation commit: `030a2adba5185a57c3e2f3c56ad3f5d8319652c7` (`docs: record mapped output ACL defect and start guest-local relay correction`).
- V1C2C1R3 implementation commit: `7a73e97aad1bf333bd495f5755fbc14aa0885536` (`fix: relay compile ast worker result through guest-local output`).
- Roadmap Change 024 documentation commit: `7bff0da8b7b6bca1487389135f16080a797a15c6` (`docs: close guest-local relay correction and reopen active composition`).
- Roadmap Change 025 documentation commit: `7de532e2d4251b1552d509ecf4c86ec742ea693e` (`docs: record failed R3 active retry and authorize checkpoint capture`).
- RC024 R3-rebound candidate SHA-256: `e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc`; policy fingerprint `e1fb0fcaa556370dadfcea24371a312c7fa7f0719af33e2359ada51aafcc83eb`; policy bytes SHA-256 `1265599779b7a94091e6588dc516128ed46dc9cb2679287e84885ff5470f0f04`.
- RC024 consumed marker SHA-256: `829024cc48856caeaf144b5946222ff21a72fd793bcd99f925dd8b761d4c7d64`; status `failed / consumed / must not be rerun`.
- RC024 targeted log SHA-256: `63c99f1369d08b8a1fc25fdbcb74f0251af9ad042751578342bc7b9d953c7baf`; manual acceptance log SHA-256: `e41029414f3430ab2e5e7acc9c91dd960c5a193a55395ca49fa0f7fc2d853012`.
- RC025 consumed marker SHA-256: `a918600722e2c00f0e47b550a09e84a1ea5e3ae27d3a2fe0de0940a8b2693c48`; status `completed / consumed`; `capture_ok=true`.
- RC025 evidence SHA-256: `6a06bf69466d776f30c97b1601ed755521f9badfb6c4be3496acfe85fdf41bb2`; summary SHA-256: `7f898a9235a760e659a2c9a43ee83162ad701f276b52220ac68b3728b8ac0ff0`.
- RC025 checkpoint failure SHA-256: `e7283c26c03180d200a06a469853fafff21150068c1243ce52394e24dc3c9213`; checkpoint progress SHA-256: `2b5940e6e70a66d613f9562472fe4a8338f9b4a216f6a74b439f3ab3d1dccbcf`.
- RC025 result: `localized_failure` at `host_mapping_write_denial`; last successful checkpoint `worker_account_token_creation`; exact error `Compile AST worker token can write the host-observed mapping.`
- RC021 evidence SHA-256: `96d2d4c797dd375d269e538558b5a5f9156a47bf80cc2f165b0d29b237b850dd`; marker: `completed / consumed`.
- RC022 evidence SHA-256: `4ee751d7dfbe7467e26b921fae981bd0e65c1275ca10dacac6342fb9ac9219bb`; marker SHA-256: `4320b13cd9021967c80370a4dc13936455d291622f97a15897234e8a970bb85c`; result: `localized_failure` at `prepare_shared_worker_output_directory`.
- Roadmap Change 026 architecture decision: `skynetvs-v1c2c1r4-untrusted-wsb-transport-signed-controller-evidence-lock-v1` → `8ccd984bb6b92d9ad5a6091168efaf902d3ec6524593c89437acd16ad2cdb955`.
- V1C2C1R4 implementation commit: `f0a2da9bf96d9010b6df42ae79104e58c15a9838` (`fix: verify signed controller evidence over untrusted WSB transport`); exact four-file patch SHA-256 `65596d2f3a5067e770c755979c3ba0562c7f7d2ec486b41598abf13d5a388079`.
- V1C2C1R4 verified identities: policy `ad14229bad416194d64f21684309cb842af1abaed9e0d2fa05a28a59b3a2e19e`, policy bytes `6f06c46f729655747f06400055dcc31f79b09372563ef63f551fcd95ec9cf15a`, controller `5a3d4e49348fc97c473cd53ee2035c154fe96273b94b4a7a7684907b8a29c2f5`, bundle `0562d3033e61bd6177c833a9026aac63ab19b3aa4551a4325451708aa14bbd26`.
- Roadmap Change 027 documentation commit: `a53065dc1b39af8e46720f1592cb4625c830aac3` (`docs: close signed WSB transport correction and reopen active composition`); parent `f0a2da9bf96d9010b6df42ae79104e58c15a9838`.
- RC027 R4-rebound seven-file candidate SHA-256: `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05`; exact diff bytes `225629`; composition policy fingerprint `4062935bd211fccc6e0b5c31cb086f28d32350d0e08bf2027f2f280959d3fa71`; policy bytes SHA-256 `127afed174dc034cdfd7b4b46471aebb7083055ace702806047df8488ba91e44`.
- RC027 consumed marker SHA-256: `7d3d2b670c878ae9e6b38e0c90f30ba9ca3f20904b03f8a1eab518c239a9a354`; status `failed / consumed / must not be rerun`; targeted active log SHA-256 `8d161de30ad32b431f09d9399c9c35105af4e61e3510a518c84db80498a0822c`.
- RC027 result: controller evidence is authentic and stable (`controller_signed_success`, signature valid, legacy terminal signature valid, ready/evidence/result stability valid) but the signed terminal status is `compile_ast_boundary_failed`; no accepted result/verifier evidence exists. Sandbox/process cleanup passed, `changed_code_executed=false`, `reusable_lease_issued=false`, `execution_authorized=false`.
- Documentation HEAD после сохранения этого файла определяется фактическим `git log -1`; self-referential commit SHA в содержимом не фиксируется.
- Исторический foundation-тег: `skynet-runtime-foundation-v1` → `09f8708`.
- Стабильный trusted-runtime тег: `skynet-trusted-runtime-v1b4` → `91d8c37fc4afe7ef138e36063e7bc22014da8a2c`.
- Рабочее дерево после documentation commit намеренно содержит только exact seven-file R4-rebound V1C2C2 candidate SHA-256 `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05`; cached diff должен быть пустым.

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

V1B3A–V1B3D and V1B4A–V1B4D are VERIFIED; V1B4 is COMPLETE and tagged. V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2/V1C2C1R3/V1C2C1R4 are VERIFIED through `f0a2da9`. Roadmap Changes 013–027 lock V1C0B2, V1C1, V1C2 and the V1C2C split. RC021/RC022/RC025 diagnostics are COMPLETED / CONSUMED; RC024 and RC027 are FAILED / CONSUMED and must not be rerun. Roadmap Change 028 is CURRENT for one exact R4 signed-boundary terminal capture; V1C2C2 remains NOT VERIFIED and V1C2C3 remains blocked.

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
V1C2C1 Fixed SYSTEM Controller and Worker Payload Bundle       VERIFIED / HISTORICAL HOST-ONLY BUNDLE
V1C2C1R1 Transcript Policy-Hash Integration Correction         VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C1R2 Shared Output ACL Preservation Correction              VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R3 Guest-Local Worker Result Relay Correction             VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R4 Signed Controller Evidence over Untrusted WSB Transport     VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2P2 R3 Active Guest Checkpoint Capture                   COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C2P3 R4 Signed Boundary Terminal Capture                   CURRENT / ONE FRESH DIAGNOSTIC CAPTURE ONLY
V1C2C2 Active Compile/AST Sandbox Composition                  BLOCKED / RC027 FAILED / R4 CANDIDATE PRESERVED
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

### Roadmap Change 019 — integration defect found before the first active run

The exact integration audit found that the single canonical `policy_sha256` field has incompatible meanings in the current committed components:

```text
V1C2A2 fixed runner:  request.policy_sha256 == SHA256(compile_ast_contract_policy.json)
V1C2B host verifier: request.policy_sha256 == V1C2A2 contract_policy.sha256
V1C2C1 controller:   request.policy_sha256 == SHA256(compile_ast_controller_worker_policy.json)
```

The first two require `f280f9c564dd1cfd780cd5465a3ecd98244e0f00f10827a295b3709b2d8b0ed2`; the current controller requires `1d9b1c66bf3971a3fdedfb077ef8deb08467e29acbc4f725d7050e3ae1342091`. A V1C2C2 run cannot satisfy both. No active run was attempted and no capability was consumed.

Roadmap Change 019 inserted `V1C2C1R1` as a host-only correction and temporarily returned V1C2C2 to BLOCKED. The corrected controller keeps the controller-worker policy independently self-verified but uses the exact V1C2A1 contract-policy hash in request/ready/terminal, matching both V1C2A2 and V1C2B. The correction is independently VERIFIED. Roadmap Change 020 then inserted and independently verified V1C2C1R2 and historically authorized exact R2 rebinding plus one fresh active retry. Roadmap Changes 021/022 are COMPLETED / CONSUMED and localize the defect to non-persistent worker-ACE mutation on the actual writable Sandbox mapping. Roadmap Change 023 inserted V1C2C1R3 without changing historical V1C2A1/A2/B/C0 sources or fingerprints. Roadmap Change 024 closed R3 and authorized one exact V1C2C2 R3 rebind plus one fresh active retry; that retry is now FAILED / CONSUMED. Roadmap Change 025 is COMPLETED / CONSUMED and localizes worker write access to the host mapping. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.

### Roadmap Change 020 — first active-run ACL integration defect

The measured V1C2C2 diagnostic received and pinned `ready.json`, published exact authorization, then observed neither `result.json` nor terminal/failure evidence before all Sandbox processes exited. Exact source review identified the incompatible transition: the fixed controller applies the private-directory `PrepareWorkerResultDirectory` helper directly to the host-observed mapped root `C:\SkynetVSOutput`. That helper replaces the DACL/owner instead of preserving the mapping's pre-existing host-observation access. The run failed closed with `compile_ast_composition_sandbox_exited_before_terminal`; cleanup succeeded and no changed source or candidate interpreter evidence was accepted.

```text
full diagnostic SHA-256:                bd35bd7315cf8d9646a29e9af6593cd6098fd34e31d93eeaaa1efbf1b2f08122
ready received:                          17 265 ms
authorization published:                 17 311 ms
result / terminal detected:              false / false
all Sandbox processes exited:            true
forced cleanup attempted:                false
artifacts removed:                        true
changed_code_executed:                    false
execution_authorized:                     false
```

Roadmap Change 020 inserted `V1C2C1R2 — Shared Output ACL Preservation Correction`. The correction is independently VERIFIED at code commit `d200c49bc5868a50ae6c83c45d4e7ed8724f332a` and historically reopened V1C2C2 for corrected-bundle rebind plus one fresh active attested retry. Roadmap Changes 021/022 are COMPLETED / CONSUMED and prove that the R2 ACE write does not persist on the actual writable Sandbox mapping. Roadmap Change 023 then inserted V1C2C1R3 and blocked V1C2C2/V1C2C3 until independent verification. Roadmap Change 024 closed R3 and authorized one exact R3 rebind plus one fresh active retry; that retry is now FAILED / CONSUMED. Roadmap Change 025 is COMPLETED / CONSUMED and localizes worker write access to the host mapping. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.

### V1C2C1R2 verification closure

```text
implementation commit:                  d200c49bc5868a50ae6c83c45d4e7ed8724f332a
parent documentation commit:            f2593b931bc8b9ed05d4535b27e62c72d2af1b58
commit message:                          fix: preserve shared output ACL for compile ast worker
committed R2 patch SHA-256:              dcc77e8a5e0920b7a4c90cfd8c6703e4d20c4ebbeb7451de12efe673fd8b6cf6
package boundaries:                      28/28
portable controller-worker evaluator:    41/41
Windows ACL smoke:                         3/3
targeted controller-worker flow:         completed successfully
isolated NLU evaluation:                 124/124
isolated full check:                     completed successfully
Runtime Architecture Audit:                9/9
post-commit inventory / Windows / targeted: 1/1 / 3/3 / completed successfully
tracked files / Python files:             280 / 262
Python bytes:                             4,052,586
Python tree fingerprint:                 39a6cfef822925048019f5bd58b8c12ea2c255f1f504e7d24181511e49308233
inventory fingerprint:                   30ef2e1be731af6fd58834abb13cd2d3269ce89488e8d406079f1c36f4e35736
HEAD == origin/main:                     true
known Sandbox process set:               empty
stable V1B4:                             91d8c37fc4afe7ef138e36063e7bc22014da8a2c
```

The preserved uncommitted V1C2C2 seven-file implementation was rebound to the exact V1C2C1R2 identities without scope growth and temporary failure-only diagnostics were removed. Its candidate SHA-256 is `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`, its semantic policy fingerprint is `1cc5a4aedb348f9cb669f2317c3a0a7b24bd11b7bbbd6eadd02907b2b1a8b1e5`, and its canonical policy-document SHA-256 is `71aa6a3228836740411d4c042d12b825cda8337b958771bc8e9ec4579299a5e1`.


### Roadmap Change 021 — the R2 active retry produced trusted guest-failure evidence but not the guest stage

Roadmap Change 021 is generated from the exact committed documentation export at `HEAD 9a3f227685c6fd7e1097c371ce54137eb0a1c663`, tree `4e6ff04c3f1ce2ca30b8e77e6d74be0c708ef073`, archive SHA-256 `42bfb8e589da5fdd7947594b2e7ab296bc4505cd86dd0592d14ef9e513a9102d`; the three source blob IDs are `a0f8e3a4d1b8ecacf7bfb5ca907bdc152c924e2c`, `318c41956c4770c9e4f1ca3549a70e472fcad5ae` and `b23462bd5852799fd6713a5fae8350cc88c094a5`.

The exact seven-file V1C2C2 implementation was rebound to V1C2C1R2 without widening scope. Host-only checks completed before the active boundary:

```text
HEAD / origin/main:                     9a3f227685c6fd7e1097c371ce54137eb0a1c663
stable V1B4:                            91d8c37fc4afe7ef138e36063e7bc22014da8a2c
initial seven-file patch SHA-256:       90bc88930ce093c73ab6d3a5e5ef4bf016d14db46470c4ae62445f630134a657
R2-rebound seven-file patch SHA-256:    9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1
V1C2C2 policy fingerprint:              1cc5a4aedb348f9cb669f2317c3a0a7b24bd11b7bbbd6eadd02907b2b1a8b1e5
V1C2C2 policy-document SHA-256:          71aa6a3228836740411d4c042d12b825cda8337b958771bc8e9ec4579299a5e1
package boundaries:                     28/28
portable evaluator:                     45/45
```

The one fresh active retry authorized by Roadmap Change 020 then consumed a fresh transaction and runtime lease, launched one Sandbox and failed closed after the guest created a bounded failure artifact:

```text
claim transaction consumed:             true
runtime lease claimed:                  true
Sandbox launched:                       true
candidate interpreter executed:         false
changed source processed / parsed:      false / false
changed source compiled:                false
terminal status:                        <empty>
signature valid:                        false
all Sandbox processes exited:           true
forced cleanup attempted:               false
artifacts removed:                      true
source / workspace unchanged:           true / true
known Sandbox process set after run:     empty
active/runtime artifact parents:        empty / empty
issue: compile_ast_composition_guest_failure_reported
issue: compile_ast_composition_guest_failure_artifact
changed_code_executed:                   false
reusable_lease_issued:                  false
execution_authorized:                   false
```

The exact guest `stage`, `error_type` and `error_code` are **UNVERIFIED**. The R2 rebind intentionally removed the temporary full-report print before the active retry. The production report retained the failure artifact diagnostic in `issues[].actual`, but the Windows evaluator printed only `issue_codes`; cleanup then correctly removed the private artifact tree. No production correction may be selected from inference alone.

Roadmap Change 021 historically authorized exactly one additional fresh active run for **diagnostic capture only**. That harness completed, its evidence is immutable, and its authority is now COMPLETED / CONSUMED; no earlier capability may be reused.

The diagnostic run was terminal for RC021 and completed with preserved report plus Git/artifact/process cleanup. RC021 is consumed; the subsequent RC022 probe and current RC023 correction decision are grounded in its captured `file`, `stage`, `error_type` and `error_code` evidence.


### Roadmap Change 022 — RC021 capture closed; suspended-worker stage localization is next

The RC021 one-shot harness completed at documentation `HEAD b3cfad02c99aa283d9516a0d35c93d3edff21324`. Its permanent marker has `status=completed`, the immutable evidence SHA-256 is `96d2d4c797dd375d269e538558b5a5f9156a47bf80cc2f165b0d29b237b850dd`, and the exact seven-file candidate remains `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`.

Directly captured guest-failure evidence:

```text
capture_ok:                             true
report_ok / report_status:              false / failed
failure file:                           controller_failure.json
failure SHA-256:                        74a0eba664c757660c21a4311eb4d62ae541913f4e6140109503deb7d141cdee
stage:                                  compile_ast_worker
error type:                             MethodInvocationException
error code:                             compile_ast_controller_worker_stage_failed
ready received:                         17 750 ms
authorization published:                17 797 ms
all Sandbox processes exited:           36 890 ms
total:                                  37 640 ms
candidate interpreter executed:         false
changed source processed / parsed:      false / false
changed source compiled:                false
changed code executed:                  false
reusable lease issued:                  false
execution authorized:                   false
artifacts removed:                      true
source / workspace unchanged:           true / true
known Sandbox process set after run:     empty
```

`MethodInvocationException` is an outer PowerShell wrapper and does not localize the inner failing call. The remaining exact candidates are shared-output ACL preparation, token access to the fixed runtime/runner, `CreateProcessAsUserW`, Job assignment and returned launch-state validation.

Roadmap Change 022 historically authorized exactly one external `V1C2C2P1 — Suspended-Worker Stage-Localization Probe`. It used one fresh Sandbox and account/token, never resumed the primary thread, did not process changed source, did not consume a V1C2C0 transaction, did not claim a runtime lease and did not publish normal compile authorization. RC022 is now COMPLETED / CONSUMED.

The completed probe persisted ordered checkpoints and the complete exception chain, proved worker-SID quiescence, deleted the fresh account, shut down the Sandbox and proved host cleanup. Its success means only that localization evidence was captured; it does not accept V1C2C2.

### Roadmap Change 023 — mapped-output ACL non-persistence; guest-local relay correction is next

The RC022 one-shot probe is COMPLETED / CONSUMED at exact documentation `HEAD bdd23feacfba4032f8bf9be76dae94a5d670bf68`. Its permanent marker SHA-256 is `4320b13cd9021967c80370a4dc13936455d291622f97a15897234e8a970bb85c`, full evidence SHA-256 is `4ee751d7dfbe7467e26b921fae981bd0e65c1275ca10dacac6342fb9ac9219bb`, summary SHA-256 is `0334e3c5730f1563ab01648635ff1f6408ade4e24f0e383bc93c2905861ec967`, and the exact seven-file candidate remains `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`.

Exact localization result:

```text
capture_ok:                              true
guest_status:                            localized_failure
localized checkpoint:                   prepare_shared_worker_output_directory
outer exception:                         MethodInvocationException / 0x80131501
inner exception:                         InvalidOperationException / 0x80131509
inner message:                           Exact shared-output worker ACE was not observed after ACL write.
controller:                              LocalSystem / S-1-5-18 / integrity 0x4000
worker account/token:                    created
worker token:                            primary / non-admin / integrity 0x2000
worker read runtime python:              passed
worker read fixed runner:                passed
CreateProcessAsUserW:                    not reached
Job assignment / limit verification:    not reached
primary thread resumed:                  false
```

The exact `C:\SkynetVSOutput` ACL snapshot before and after the failed helper call is identical:

```text
owner SID:                     S-1-5-21-3677456875-1600494081-873325803-1003
access rules protected:        true
rule count:                    3
rule multiset SHA-256:         4a67566837a9aca1cfe5ff32f47056d1640b4bf640ab3633bdb01ea986580162
fresh worker ACE present:      false
```

Cleanup succeeded after localization: no worker process was launched, the worker SID was quiescent across three scans, the account was deleted, Sandbox self-shutdown completed, all known Sandbox processes exited and the temporary root was removed. No V1C2C0 transaction was consumed, no runtime lease was claimed, no changed source was materialized or processed, the candidate interpreter did not run, changed code did not execute, no reusable lease was issued and `execution_authorized=false`.

This evidence disproves the active assumption behind V1C2C1R2: an ACE that is correctly added and re-read on an ordinary NTFS test directory is not persisted/re-observed on the actual writable WSB mapping. R2 remains VERIFIED for its historical host-only claim, but it is not an accepted active-output solution.

Roadmap Change 023 inserts `V1C2C1R3 — Guest-Local Worker Result Relay Correction` with exact four-file scope:

```text
M modules/developer/developer_task_execution_compile_ast_controller_worker.py
M modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
M tools/eval_developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
```

Required R3 architecture:

```text
host-observed writable mapping: C:\SkynetVSHostOutput
private guest-local worker root: C:\SkynetVSOutput
fixed runner result path:       C:\SkynetVSOutput\result.json (unchanged)
```

The LocalSystem controller must create and privately ACL the guest-local root for SYSTEM plus the exact worker SID, keep the worker unable to write the host-observed mapping, validate the local result after worker exit / Job closure / SID quiescence / account deletion, relay the exact bytes to `C:\SkynetVSHostOutput\result.json`, and sign the terminal against the exact relayed bytes. Ready, failure and terminal artifacts use the host-observed root. No mapped-folder owner/DACL/protection mutation is allowed.

At the Roadmap Change 023 state, R3 was host-only and non-authorizing and had to be independently verified without launching Sandbox, consuming a transaction, claiming a runtime lease, processing changed source or running candidate Python. At that state the R3 identities were UNVERIFIED and the seven-file V1C2C2 candidate remained byte-preserved and BLOCKED. Roadmap Change 024 below records the completed R3 evidence and controls the only newly authorized rebind/retry scope.

### Roadmap Change 024 — V1C2C1R3 closure and exact V1C2C2 R3 rebind

V1C2C1R3 is independently VERIFIED at exact code commit:

```text
implementation commit:                  7a73e97aad1bf333bd495f5755fbc14aa0885536
parent documentation commit:            030a2adba5185a57c3e2f3c56ad3f5d8319652c7
commit message:                          fix: relay compile ast worker result through guest-local output
exact four-file patch SHA-256:           daca5a58e1f62f61a7155fe0f4862322218d05c9f178445d7d1ed5172e9b2ebe
package boundaries:                      28/28
portable evaluator:                      41/41
Windows host-only relay smoke:            3/3
targeted controller-worker flow:         completed successfully
isolated full check:                     completed successfully
Runtime Architecture Audit:               9/9
post-commit inventory:                   PASS
post-commit Windows relay smoke:          3/3
post-commit targeted flow:               41/41 + 3/3 / completed successfully
HEAD == origin/main:                     true
known Sandbox process set:               empty
stable V1B4:                             91d8c37fc4afe7ef138e36063e7bc22014da8a2c
```

Exact committed scope:

```text
M modules/developer/developer_task_execution_compile_ast_controller_worker.py
M modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
M tools/eval_developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
```

Verified R3 identities:

```text
policy ID:          skynetvs-v1c2c1r3-fixed-system-controller-standard-user-worker-bundle-v4
architecture slice: db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec
semantic policy fp: 3683f525c3ef037817e0fda4addccb1f7ed82d7e01c34e9e248494644fa4f3c9
policy bytes SHA:   add4992b096cc4ee50fbcc5a898348995277b4c2facb8a4dc8f370f04dd566ea
bootstrap SHA:      7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d
native helper SHA:  f05437852c9204bcdb0cce70e30989544251070a836f55d748d559f289ddd8e8
controller SHA:     11ccf69016fe0aceead56a9d07ac0f054e99d759207630b114922e4791553827
WSB template SHA:   3de7527400c576ce9ce75ef58f616622ab52a57426811b193270e292d641c281
bundle fingerprint: 62854e85a916f67f24453e3c64c3212a5ae722da8fbc0e275f59c738144dde98
```

The host-only evidence proves that the mapped publication root is never ACL/owner/protection-mutated, the worker is denied direct host-mapping writes, the unchanged runner writes only to private guest-local `C:\SkynetVSOutput\result.json`, and trusted LocalSystem validates and relays exact result bytes to `C:\SkynetVSHostOutput\result.json` before terminal publication. No Sandbox was launched during R3 acceptance, no claim transaction or runtime lease was consumed, no candidate interpreter ran and no changed source was processed. `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false` remained invariant.

Roadmap Change 024 reopens V1C2C2 only for an exact rebind of the preserved seven-file candidate to the verified R3 identities and at most one fresh active attested-pass retry. The public API, immutable V1C2C2 architecture-slice identity, fixed V1C2A2 runner, source/runtime materialization model, post-exit signature trust model and seven-file scope remain unchanged. Any failed active retry is terminal for RC024 and requires another explicit Roadmap Change; V1C2C3 remains BLOCKED.


### Roadmap Change 025 — diagnostic capture closure

Roadmap Change 025 is COMPLETED / CONSUMED. Its one-shot harness ran exactly once on documentation `HEAD / origin/main 7de532e2d4251b1552d509ecf4c86ec742ea693e` and exact R3-bound candidate SHA-256 `e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc`.

```text
RC025 marker SHA-256:              a918600722e2c00f0e47b550a09e84a1ea5e3ae27d3a2fe0de0940a8b2693c48
marker status:                     completed / consumed
capture_ok:                        true
evidence SHA-256:                 6a06bf69466d776f30c97b1601ed755521f9badfb6c4be3496acfe85fdf41bb2
summary SHA-256:                  7f898a9235a760e659a2c9a43ee83162ad701f276b52220ac68b3728b8ac0ff0
checkpoint failure SHA-256:       e7283c26c03180d200a06a469853fafff21150068c1243ce52394e24dc3c9213
checkpoint progress SHA-256:      2b5940e6e70a66d613f9562472fe4a8338f9b4a216f6a74b439f3ab3d1dccbcf
localized checkpoint:             host_mapping_write_denial
last successful checkpoint:       worker_account_token_creation
event count:                      16
```

The worker account/token checkpoint proved a fresh primary non-admin token at medium integrity (`RID 8192`). The next checkpoint failed with:

```text
type:       System.Management.Automation.RuntimeException
HResult:    0x80131501
message:    Compile AST worker token can write the host-observed mapping.
position:   C:\SkynetVSInput\controller.ps1:839
```

The capture consumed one fresh transaction and runtime lease and launched one Sandbox, but the candidate interpreter never executed, changed source was not processed, parsed or compiled, changed code was not executed, no reusable lease was issued and `execution_authorized=false`. Every Sandbox process exited, no forced cleanup was required, artifacts were removed and the exact seven-file candidate remained unchanged.

### Roadmap Change 026 — start V1C2C1R4 signed-controller-evidence correction

The measured `traditional_wsb_logoncommand_v1` writable mapping admitted writes under the standard-user worker token. Therefore `C:\SkynetVSHostOutput` is now classified as an untrusted mutable transport after worker creation. R3 remains valid historical host-only evidence for guest-local relay mechanics, but its worker-write-denial requirement cannot be an active Sandbox trust invariant.

New architecture decision:

```text
V1C2C1R4:           Signed Controller Evidence over Untrusted Writable WSB Transport
decision ID:        skynetvs-v1c2c1r4-untrusted-wsb-transport-signed-controller-evidence-lock-v1
decision fingerprint: 8ccd984bb6b92d9ad5a6091168efaf902d3ec6524593c89437acd16ad2cdb955
policy lineage:     skynetvs-v1c2c1r4-fixed-system-controller-standard-user-worker-bundle-v5
```

```json
{"architecture_slice":"V1C2C1","backend_id":"traditional_wsb_logoncommand_v1","controller_evidence_key":"ephemeral_controller_ecc_key","decision_id":"skynetvs-v1c2c1r4-untrusted-wsb-transport-signed-controller-evidence-lock-v1","failure_artifact_authority":"signed_controller_terminal_only","fixed_runner_unchanged":true,"host_output_transport":"untrusted_writable_wsb_mapping","implementation_revision":"V1C2C1R4","ready_pinned_before_worker_creation":true,"schema_version":1,"terminal_bindings":["request_id","host_nonce","request_sha256","ready_sha256","authorize_sha256","public_key_sha256","runtime_bundle_fingerprint","runtime_lease_fingerprint","plan_fingerprint","source_manifest_sha256","private_result_sha256","relayed_result_sha256","terminal_status"],"terminal_failure_signed":true,"terminal_success_signed":true,"unsigned_guest_artifacts_authoritative":false,"worker_direct_mapping_write_may_succeed":true,"worker_may_only_cause_dos":true}
```

R4 keeps the ready/public-key trust anchor in the pre-worker phase, removes host-mapping write denial as an acceptance requirement and makes controller signatures—not mapped-folder ACLs—the authority. Success requires a stable post-exit signed terminal bound to the pinned ready/public key, exact authorization, runtime/lease/plan/source identities and private/relayed result hashes. Failure is authoritative only through a typed controller-signed failure terminal. Unsigned guest artifacts are never authoritative. Worker mutation of the mapping may cause fail-closed rejection/DoS only.

Exact R4 implementation scope:

```text
M modules/developer/developer_task_execution_compile_ast_controller_worker.py
M modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
M tools/eval_developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
```

The fixed V1C2A2 runner, V1C2A1/A2/B/C0 contracts, public V1C2C2 API, guest-local result root, LocalSystem/standard-user boundary, `CREATE_SUSPENDED`, assign-before-resume, Job limits and stable V1B4 tag remain unchanged. R4 is host-only and non-authorizing. No transaction/lease claim, source/runtime materialization, Sandbox launch, candidate interpreter or changed-source processing is allowed while R4 is open.

Operational state:

```text
RC021       COMPLETED / CONSUMED
RC022       COMPLETED / CONSUMED / LOCALIZED_FAILURE
RC024       FAILED / CONSUMED / MUST NOT BE RERUN
RC025       COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C1R3   VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R4   CURRENT / HOST-ONLY / UNVERIFIED
V1C2C2P2   COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C2      BLOCKED / EXACT SEVEN-FILE CANDIDATE PRESERVED
V1C2C3      BLOCKED
candidate SHA-256: e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

### Roadmap Change 027 — close V1C2C1R4 and reopen exact V1C2C2 R4 composition

V1C2C1R4 is independently VERIFIED / HOST-ONLY / NON-AUTHORIZING at exact code commit `f0a2da9bf96d9010b6df42ae79104e58c15a9838`. The exact four-file patch is `65596d2f3a5067e770c755979c3ba0562c7f7d2ec486b41598abf13d5a388079` and the verified architecture decision fingerprint remains `8ccd984bb6b92d9ad5a6091168efaf902d3ec6524593c89437acd16ad2cdb955`. Pre-commit and post-commit evidence passed package boundaries `28/28`, portable controller-worker coverage `46/46`, Windows host-only CNG smoke `5/5`, targeted flow, isolated full `check`, Runtime Architecture Audit `9/9`, committed-tree inventory, post-commit Windows smoke `5/5` and post-commit targeted flow. `HEAD == origin/main`, the known Sandbox process set is empty and the seven-file V1C2C2 starting candidate remains exact SHA-256 `e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc`.

Verified R4 identities:

```text
policy ID:          skynetvs-v1c2c1r4-fixed-system-controller-standard-user-worker-bundle-v5
semantic policy fp: ad14229bad416194d64f21684309cb842af1abaed9e0d2fa05a28a59b3a2e19e
policy bytes SHA:   6f06c46f729655747f06400055dcc31f79b09372563ef63f551fcd95ec9cf15a
bootstrap SHA:      7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d
native helper SHA:  f05437852c9204bcdb0cce70e30989544251070a836f55d748d559f289ddd8e8
controller SHA:     5a3d4e49348fc97c473cd53ee2035c154fe96273b94b4a7a7684907b8a29c2f5
WSB template SHA:   3de7527400c576ce9ce75ef58f616622ab52a57426811b193270e292d641c281
bundle fingerprint: 0562d3033e61bd6177c833a9026aac63ab19b3aa4551a4325451708aa14bbd26
```

The writable WSB mapping remains explicitly untrusted. Mapped ACL state is hygiene only, while the pre-worker pinned ready/public key and controller-signed success or typed failure terminal are the authority. R4 verification launched no Sandbox and granted no execution authority.

Operational state:

```text
RC021       COMPLETED / CONSUMED
RC022       COMPLETED / CONSUMED / LOCALIZED_FAILURE
RC024       FAILED / CONSUMED / MUST NOT BE RERUN
RC025       COMPLETED / CONSUMED / LOCALIZED_FAILURE
RC027       CURRENT / EXACT R4 REBIND + ONE FRESH ACTIVE RETRY ONLY
V1C2C1R3   VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R4   VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2P2   COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C2      CURRENT / R4 REBIND + ONE FRESH ACTIVE ATTESTED-PASS RETRY ONLY
V1C2C3      BLOCKED
starting candidate SHA-256: e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

### Roadmap Change 028 — RC027 signed boundary failure requires one exact terminal capture

RC027 is permanently FAILED / CONSUMED and must not be rerun. The exact active run was bound to documentation `HEAD / origin/main a53065dc1b39af8e46720f1592cb4625c830aac3` and R4-rebound candidate SHA-256 `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05`. The one-shot marker SHA-256 is `7d3d2b670c878ae9e6b38e0c90f30ba9ca3f20904b03f8a1eab518c239a9a354`; the targeted log SHA-256 is `8d161de30ad32b431f09d9399c9c35105af4e61e3510a518c84db80498a0822c`.

The trusted R4 transport itself succeeded: the post-exit controller evidence is signed and stable, the legacy terminal signature is valid, the pinned ready/public-key anchor remained stable, and the controller terminal status is `compile_ast_boundary_failed`. Host/source/workspace cleanup passed and no reusable or changed-code execution authority was accepted.

The exact controller computes the boundary as `resultReceived && workerExitCode == 0`. The retained RC027 evaluator output does not preserve the signed terminal's `worker.exit_code`, `worker.result_received`, worker lifecycle fields or `check` counters, so the current evidence cannot distinguish a non-zero worker exit from a zero-exit private-result absence/validation/relay rejection. Choosing a production correction without that evidence would be speculative.

Roadmap Change 028 therefore inserts temporary external diagnostic slice `V1C2C2P3 — R4 Signed Boundary Terminal Capture`. It may perform exactly one fresh diagnostic run with the unchanged R4-rebound seven-file candidate. Before launch it must persist a permanent RC028 consumed marker. It must capture the exact post-exit terminal payload/signature and controller-evidence payload/signature before normal artifact cleanup, prove the copied bytes match the hashes that the normal R4 composition verified, and extract only signed terminal fields needed to localize the boundary: worker exit/result state, worker lifecycle/Job cleanup state, result/check counters and exact result hash presence. The diagnostic must not accept V1C2C2, run the normal pipeline, widen the production API, modify tracked production/candidate files, modify the fixed V1C2A2 runner, authorize V1C2C3 or issue reusable execution authority.

Operational state after Roadmap Change 028:

```text
RC021       COMPLETED / CONSUMED
RC022       COMPLETED / CONSUMED / LOCALIZED_FAILURE
RC024       FAILED / CONSUMED / MUST NOT BE RERUN
RC025       COMPLETED / CONSUMED / LOCALIZED_FAILURE
RC027       FAILED / CONSUMED / MUST NOT BE RERUN
RC028       CURRENT / ONE EXACT SIGNED-BOUNDARY TERMINAL CAPTURE ONLY
V1C2C1R4   VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2P3   CURRENT / ONE FRESH DIAGNOSTIC CAPTURE ONLY
V1C2C2      BLOCKED / RC027 FAILED / R4 CANDIDATE PRESERVED
V1C2C3      BLOCKED
R4 candidate SHA-256: dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

### Следующее точное действие

1. Commit Roadmap Change 028 in only the three architecture documents on exact `HEAD / origin/main == a53065dc1b39af8e46720f1592cb4625c830aac3`; preserve exact R4-rebound seven-file candidate SHA-256 `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05`, empty cached diff, RC027 marker/log evidence and stable V1B4. No pipeline or Windows Sandbox run belongs to the docs transition.
2. After RC028 is committed and pushed, build an external one-shot V1C2C2P3 diagnostic harness without modifying tracked production/candidate files. The harness must bind the exact candidate/policy/R4 identities, reserve a permanent RC028 consumed marker before launch, use one fresh host report/snapshot/plan/runtime bundle/runtime lease/V1C2C0 transaction/Sandbox, and copy the stable post-exit signed terminal/controller-evidence bytes before cleanup.
3. Accept the diagnostic capture only if all Sandbox processes exit, no forced cleanup is required, the copied terminal/evidence hashes equal the hashes verified by the normal R4 composition, the signatures validate under the pinned pre-worker public key, repository/workspace/candidate bytes remain unchanged, artifacts are removed, `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false`.
4. If the diagnostic capture fails, stop and preserve its permanent marker/evidence. If it succeeds, use only the authenticated `worker.exit_code`, `worker.result_received`, worker lifecycle and `check` fields to choose the next explicit Roadmap Change. Do not rerun RC027 or RC028 automatically.
5. V1C2C2 remains NOT VERIFIED and V1C2C3 remains BLOCKED. Do not move `skynet-trusted-runtime-v1b4`, delete consumed markers, widen the public API or modify the fixed V1C2A2 runner.


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
e2621ca docs: close fixed compile ast controller worker bundle and start active composition
3331577 docs: separate active compile composition architecture and implementation identities
a4cfc3a docs: insert compile ast transcript policy hash correction
56e46b5 docs: fix stale active composition status after roadmap change 019
7ffefba fix: align compile ast transcript policy hash
f2593b9 docs: insert compile ast shared output ACL correction
d200c49 fix: preserve shared output ACL for compile ast worker
9a3f227 docs: close shared output ACL correction and reopen active composition
b3cfad0 docs: record R2 guest failure and authorize diagnostic capture
bdd23fe docs: close guest failure capture and authorize suspended worker localization
030a2ad docs: record mapped output ACL defect and start guest-local relay correction
7a73e97 fix: relay compile ast worker result through guest-local output
7bff0da docs: close guest-local relay correction and reopen active composition
tag skynet-trusted-runtime-v1b4 -> 91d8c37
```

V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2/V1C2C1R3/V1C2C1R4 are VERIFIED through `f0a2da9`. Roadmap Changes 013–027 lock V1C0B2, V1C1, V1C2 and the V1C2C split. RC021/RC022/RC025 diagnostics are COMPLETED / CONSUMED; RC024 is FAILED / CONSUMED; V1C2C2P2 is COMPLETED / CONSUMED; RC027 is FAILED / CONSUMED / MUST NOT BE RERUN; Roadmap Change 028 is CURRENT for one exact R4 signed-boundary terminal capture; V1C2C2 remains NOT VERIFIED, V1C2C3 remains blocked and the stable V1B4 tag must not move.

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

Threat model, result-authenticity model, V1B4 and Roadmap Changes 011–025 are approved in **Pro Standard**.

V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2/V1C2C1R3/V1C2C1R4 are VERIFIED. V1C0B2, V1C1, V1C2 and the V1C2C split are LOCKED. RC021/RC022/RC025 diagnostics are COMPLETED / CONSUMED; RC024 is FAILED / CONSUMED. V1C2C2P2 is COMPLETED / CONSUMED. RC027 is FAILED / CONSUMED / MUST NOT BE RERUN. Roadmap Change 028 is CURRENT for one exact R4 signed-boundary terminal capture. V1C2C2 remains NOT VERIFIED; V1C2C3, exact PyPI wheel closure and MinGit pinning remain BLOCKED.

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
V1C2C1  Fixed SYSTEM Controller and Standard-User Worker Bundle     VERIFIED / HISTORICAL HOST-ONLY BUNDLE
V1C2C1R1 Transcript Policy-Hash Integration Correction              VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C1R2 Shared Output ACL Preservation Correction                   VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R3 Guest-Local Worker Result Relay Correction                  VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C1R4 Signed Controller Evidence over Untrusted WSB Transport       VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2P2 R3 Active Guest Checkpoint Capture                         COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C2  Active Compile/AST Sandbox Composition                      CURRENT / R4 REBIND + ONE FRESH ACTIVE RETRY ONLY
V1C2C3  Live Pass / Syntax-Failure / Boundary-Failure Acceptance    BLOCKED
```

Locked identities:

```text
decision fingerprint:  56bfd2ca196ca2b6d8f6ad426ea06141fe1535a28a281f0d7661bc8e32ee8ff6
V1C2C0 policy:         092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa
V1C2C1 architecture slice identity: db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec
V1C2C1R4 decision fingerprint: 8ccd984bb6b92d9ad5a6091168efaf902d3ec6524593c89437acd16ad2cdb955
V1C2C2 architecture slice identity: d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484
V1C2C3 evidence:       b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

The V1C2C0 transaction reserves one exact plan and one exact runtime lease and is issued without claiming either capability. Its irreversible path is plan claim first and runtime-lease claim second, with no fallible filesystem/materialization operation between them. If the second claim fails, the plan remains consumed and no retry may reuse the transaction. V1C2C1 remains deterministic and host-only. V1C2C2 is the only slice allowed to materialize exact sources/runtime and launch Sandbox. V1C2C3 requires three fresh runs: attested pass, authentic syntax failure, and an eval-only post-ready/pre-authorization source substitution producing a signed boundary failure.

V1C2C1 is independently VERIFIED. Roadmap Change 020's one fresh active retry has been consumed and failed closed. Roadmap Changes 021/022 are COMPLETED / CONSUMED and localize mapped-output ACL non-persistence before process creation. Roadmap Change 024 closed V1C2C1R3 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and consumed one exact V1C2C2 R3 retry, which failed closed. Roadmap Change 025 is COMPLETED / CONSUMED. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.

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

This clarification did not authorize an active run by itself. Roadmap Change 019 subsequently inserted and verified V1C2C1R1. Roadmap Change 020 inserted and verified V1C2C1R2 and historically authorized exact R2 rebinding plus one fresh active retry. Roadmap Changes 021/022 are COMPLETED / CONSUMED and localize the mapped-output ACL defect. Roadmap Change 023 inserted V1C2C1R3; Roadmap Change 024 closed R3 and consumed one exact active retry, which failed closed. Roadmap Change 025 is COMPLETED / CONSUMED and localizes worker write access to the host-observed mapping. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.

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

The committed process-local transaction is single-use and non-serializable, reserves exact plan/lease objects without claiming them, publishes a unique non-secret one-run fingerprint, and consumes plan first and runtime lease second. Portable evidence proves duplicate-reservation rejection, terminal expiry, fail-closed guard/nonce/policy tamper handling, plan-preserving behavior when an already-consumed lease is detected before claim, and irreversible plan consumption if the lease claim fails after plan claim. The Windows smoke retained exact source bytes and the exact runtime bundle, left source/workspace Git evidence unchanged, found no running Sandbox processes or residual artifacts, and kept repository mutation, network/download/install, Sandbox launch, candidate-interpreter execution, changed-source processing, changed-code execution, reusable authority and `execution_authorized` false. V1C2C0 is VERIFIED; the original V1C2C1 bundle remains VERIFIED historical host-only evidence; V1C2C1R1 and V1C2C1R2 are VERIFIED. RC021/RC022/RC025 diagnostics are COMPLETED / CONSUMED; V1C2C1R3 and V1C2C1R4 are VERIFIED / HOST-ONLY / NON-AUTHORIZING; RC024 is FAILED / CONSUMED; V1C2C2P2 is COMPLETED / CONSUMED; RC027 is CURRENT for exact V1C2C2 R4 rebind plus one fresh active retry; V1C2C3 is BLOCKED.

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

The Windows smoke compiled the exact native helper and parsed the fixed bootstrap/controller/policy/WSB payloads only. Sandbox launch, transaction consumption, runtime-lease claim, candidate-interpreter execution, changed-source processing, changed-code execution, reusable authority and `execution_authorized` all remained false. The original V1C2C1 bundle remains VERIFIED historical host-only evidence; V1C2C1R1 and V1C2C1R2 are independently VERIFIED. Roadmap Changes 021/022 are COMPLETED / CONSUMED and prove mapped-output ACL non-persistence before process creation. Roadmap Change 024 closed V1C2C1R3 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and consumed one exact R3-bound active retry, which failed closed. Roadmap Change 025 is COMPLETED / CONSUMED. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.


## V1C2C1R2 shared-output ACL preservation correction — Roadmap Change 020

The first active V1C2C2 diagnostic proved the pre-authorization chain but failed before host-observable result/terminal evidence:

```text
request ID:                           b2784ab28b0ead772eda064a876566f9
ready SHA-256:                        dd2d0c1614b07e8f7fc8684ba28236b3ef28b1d9add04a985362c743541cbc39
authorize SHA-256:                    4713b733cce2f82068ca68244b32ad190e5a61395df5da1afad3c1c8e40d6bee
ready received:                       17 265 ms
authorization published:              17 311 ms
result detected:                       false
terminal detected:                     false
all processes exited:                   true
artifacts removed:                       true
issue: compile_ast_composition_sandbox_exited_before_terminal
```

The controller's compile-worker transition applied a private-directory ACL helper to the shared mapped output root. The helper protected and replaced the DACL and owner, which was incompatible with the host-observed output channel. V1C2C1R2 now preserves the mapped root's existing ACL/owner/inheritance and adds only a verifiable fresh-worker write ACE. This correction is host-only and supersedes V1C2C1R1 only for future active composition. The exact seven-file V1C2C2 implementation is now rebound to R2, remains uncommitted and is fixed at SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`.

## V1C2C1R1 verification closure

The transcript policy-hash integration correction is VERIFIED at:

```text
implementation commit:                  7ffefba02306f06f53a72038ab18a94f580ba421
parent documentation commit:            56e46b5beef3683f1bc144180369e0aa56a29fc2
commit message:                          fix: align compile ast transcript policy hash
package boundaries:                      28/28
V1C2A1 dependency gate:                  45/45
V1C2A2 dependency gate:                  40/40
V1C2B dependency gate:                   44/44
V1C2C0 dependency gate:                  38/38
V1C2C1R1 portable evaluator:             35/35
pre-commit Windows compile smoke:         3/3
pre-commit full check:                   completed successfully
Runtime Architecture Audit:               9/9
post-commit V1C0A Windows smoke:          1/1
post-commit V1C2C1R1 Windows smoke:       3/3
post-commit targeted flow:               completed successfully
tracked files / Python files:            280 / 262
Python bytes:                            4,029,561
pipeline flows / all steps:              98 / 504
check steps:                             93
process-launch call sites:               41
host-sensitive files:                    34
Python tree fingerprint:                 b06f1bd4eaf42c350323f7f14bd65ac57798fae36bbe50c50b421709532f07d7
inventory fingerprint:                   ada6d4e5eb856d5a416f2b4662c13f1e1202249d8a5bbde03ebcbbb8ac19488b
HEAD == origin/main:                     true
working tree:                            clean
known Sandbox process set:               empty
stable V1B4:                             91d8c37fc4afe7ef138e36063e7bc22014da8a2c
```

Exact committed scope:

```text
M modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
M modules/developer/developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
```

The corrected bundle keeps canonical request/ready/terminal `policy_sha256` bound to the exact V1C2A1 contract-policy bytes while independently self-verifying the controller-worker policy. The corrected identities are policy `a1c9e95421ffe9755acc13028b05c3b45b960ad5d2ee750685bf56db1d44d03a`, policy-document SHA-256 `3d5405a603030d79a18ef31a3f5a5cd4f03b40c7115842a0d75974ecb26db3b3`, controller SHA-256 `776e4c07c533a44d54a57b5ecd0d38bf92cf6b7fc4aece1d4a211d85594049f4` and bundle fingerprint `12714af317444e481967af2ca063ec1fe0f3a4e83a8f750332aa667ba6155303`.

No Sandbox was launched, no transaction was consumed, no runtime lease was claimed, no interpreter ran and no changed source was processed. `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false` remained invariant. V1C2C1R1 is therefore VERIFIED / HOST-ONLY / NON-AUTHORIZING. Roadmap Change 020 subsequently inserted and verified V1C2C1R2. Roadmap Changes 021/022 are COMPLETED / CONSUMED and prove mapped-output ACL non-persistence before process creation. Roadmap Change 024 closed V1C2C1R3 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and consumed one exact R3-bound active retry, which failed closed. Roadmap Change 025 is COMPLETED / CONSUMED. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.
