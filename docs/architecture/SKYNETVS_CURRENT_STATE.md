# SkynetVS Current State

> **Оперативная запись #108 / 2026-09-22:** для закрытого модельного core выбран
> Source107 V2; пользователь разрешил 22 новых файла и два canonical docs после
> отдельного preflight. Runtime, commit и push не разрешены. Текущее описание —
> в разделе «Source107 V2 — согласование source-only переноса #108» в конце файла.
> Старые next-action записи сохраняются как история; факт применения подтверждает
> отдельный apply report, а не наличие этого текста.


> **Оперативная запись #98 / 2026-09-22:** SCM01-WSB01 согласован только как
> лабораторный дизайн с одной недоверенной writable Output-папкой. Runtime
> не разрешён. Актуальные границы и Next Exact Action — в разделе SCM01-WSB01
> в конце этого документа; прежние operational next-action записи исторические.

## 1. Метаданные

- Дата обновления: `2026-09-22`
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
- Roadmap Change 028 documentation commit: `b59dacedabca72b839d1f04f011613dae3045d4f` (`docs: record RC027 boundary failure and authorize terminal capture`); parent `a53065dc1b39af8e46720f1592cb4625c830aac3`.
- RC028 consumed marker SHA-256: `bc116ae32b67f9feb9b218eee6cff16aaf4a64065c330614ef6b92d4e210eefc`; status `completed / consumed / authenticated capture`; diagnostic log SHA-256 `601a9f3b65c472c1a26cd01cf2fcb4b2ee6e5e884bbb9dd60f6ce390e39f5d2b`; authenticated diagnostic SHA-256 `a0dce9e18dc2221331ebea30ab0fa9e7b7d8c9820cd1b56f99ace64e07a78ebd`.
- RC028 authenticated result: signed terminal/controller evidence is valid and stable; worker lifecycle is correct (`created_suspended=true`, `assigned_before_resume=true`, `resume_previous_count=1`, `worker_in_job=true`, `job_closed=true`, `sid_process_set_empty=true`, `account_deleted=true`), but `worker.exit_code=70`, `worker.result_received=false`, all check counters are zero and `changed_code_executed=false`.
- RC028 host-only root-cause proof: `SkynetVS_V1C2C2_RC028_HostOnlyRunnerShadowValidationV2_20260825_161623.txt` SHA-256 `cb6f0648f09fdbb32f7268fe5f01f78085054da3f4bf44469b074aa83b6298c9`. Exact materialization passes request/manifest loading and `_validate_request`, then deterministically fails in pinned V1C2A2 `_verify_payload` at `_require_fields(launch, _PAYLOAD_LAUNCH_FIELDS)` with `RunnerInputError("fields_invalid")`.
- Root cause: V1C2A2 `_payload_manifest_bytes` serializes recursively with `sort_keys=True`, while the unchanged pinned runner requires an exact non-sorted launch-object field order. Recursive sorting places `runner_path` before `runtime_executable`/`runtime_flags`, so the worker fails before source processing and `main()` collapses the exception to exit code `70`.
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

V1C2A2R1 is VERIFIED / COMMITTED at 13c136803982871be4df28229cf4988e598b9cf3 after RC032 exact three-file closure; V1C2BR1 is CURRENT / HOST-ONLY / NON-AUTHORIZING / SOURCE AUDIT FIRST. V1C2C1R5 remains BLOCKED until BR1 VERIFIED; V1C2C2 remains BLOCKED / AWAIT BR1 + R5 REBIND; V1C2C3 remains BLOCKED.

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
V1C2C2P3 R4 Signed Boundary Terminal Capture                   COMPLETED / CONSUMED / ROOT CAUSE LOCALIZED
V1C2A2R1 Fixed Payload Launch-Order Serialization Correction    VERIFIED / COMMITTED / HOST-ONLY / NON-AUTHORIZING
V1C2BR1 V1C2A2R1 Dependency Identity Rebind                   CURRENT / HOST-ONLY / NON-AUTHORIZING / SOURCE AUDIT FIRST
V1C2C1R5 V1C2A2R1/BR1 Controller-Worker Identity Rebind       PLANNED / BLOCKED UNTIL BR1 VERIFIED
V1C2C2 Active Compile/AST Sandbox Composition                  BLOCKED / AWAIT R1 + BR1 + R5 REBIND
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

### Roadmap Change 029 — V1C2A2 fixed payload launch-order correction

RC028 is COMPLETED / CONSUMED. Its authenticated capture proves that the R4 controller/worker lifecycle, signed transport and cleanup all succeed, but the fixed standard-user worker exits with code `70` before producing `result.json`. The pinned V1C2A2 runner source proves that `70` is the generic return for any exception in `main()`, so the exit code alone is not a semantic error class.

Host-only shadow validation then reproduced the exact failure without Sandbox or guest execution: exact V1C2C2 materialization passed canonical `request.json`, canonical `source_manifest.json` and `_validate_request`, then failed in `_verify_payload` at `_require_fields(launch, _PAYLOAD_LAUNCH_FIELDS)` with `RunnerInputError("fields_invalid")`. The report SHA-256 is `cb6f0648f09fdbb32f7268fe5f01f78085054da3f4bf44469b074aa83b6298c9`.

The defect is in the V1C2A2 host-side payload serializer, not in the guest runner algorithm. `_payload_manifest_bytes` uses recursive `json.dumps(..., sort_keys=True, ...)`, while the exact runner intentionally requires the launch object in this order: `caller_arguments`, `caller_environment`, `runtime_executable`, `runtime_flags`, `runner_path`, `shell`, `working_directory`. Recursive sorting instead serializes `runner_path` before `runtime_executable` and `runtime_flags`, so `_require_fields` fails before source processing.

Roadmap Change 029 inserts `V1C2A2R1 — Fixed Payload Launch-Order Serialization Correction` before any further V1C2C2 activity. The correction is host-only and non-authorizing. It must preserve the exact generated guest runner bytes and runner SHA-256 `6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9`, preserve the V1C2A1 contract-policy bytes/fingerprint and V1C2A2 runner-policy fingerprint, and change only host payload serialization so the existing `_launch_contract()` insertion order is retained. The corrected payload SHA-256 and runner-bundle fingerprint must be measured from final bytes and pinned; they must not be guessed.

The locked implementation scope for V1C2A2R1 is exactly two tracked files: `modules/developer/developer_task_execution_compile_ast_runner.py` and `tools/eval_developer_task_execution_compile_ast_runner.py`. The existing Windows bundle smoke, package-boundary registry and pipeline flow may be executed but are not modified by this correction. Any need to widen that two-file implementation scope requires another explicit Roadmap Change.

V1C2A2R1 acceptance requires: exact guest runner SHA unchanged; exact payload launch order regression coverage; corrected bundle self-validation; unchanged V1C2A1 and V1C2B dependency gates; package boundaries; existing V1C2A2 Windows bundle smoke with no Sandbox launch; full `check`; Runtime Architecture Audit; exact two-file commit scope; post-commit repeat of the host-only payload-order proof; and all active flags false. No transaction/lease claim, source/runtime active composition, Sandbox launch, guest interpreter execution or changed-source processing is permitted while V1C2A2R1 is open.

The preserved seven-file V1C2C2 candidate remains byte-for-byte unchanged at SHA-256 `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05` during RC029 implementation. Its current runner dependency identities will become historical/stale once V1C2A2R1 is verified, so V1C2C2 remains BLOCKED. A later explicit Roadmap Change must rebind the seven-file candidate to the measured V1C2A2R1 payload/bundle identities before any new active retry can be considered. RC027 and RC028 must never be rerun.

Operational state after Roadmap Change 029:

```text
RC027       FAILED / CONSUMED / MUST NOT BE RERUN
RC028       COMPLETED / CONSUMED / ROOT CAUSE LOCALIZED
V1C2C2P3   COMPLETED / CONSUMED
V1C2A2     VERIFIED / HISTORICAL ORIGINAL PAYLOAD BUNDLE
V1C2A2R1   CURRENT / HOST-ONLY / NON-AUTHORIZING
V1C2C1R4   VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2      BLOCKED / R4 CANDIDATE PRESERVED / AWAIT R1 REBIND
V1C2C3      BLOCKED
R4 candidate SHA-256: dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05
fixed guest runner SHA-256: 6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

### Roadmap Change 030 — downstream identity-cascade closure

V1C2A2R1 implementation is now an exact two-file pre-commit candidate at patch SHA-256 `b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2`. Its generated guest runner SHA remains `6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9`; corrected payload SHA is `501ed90023f8f8afc75c7676a8acba3d1497334e398f929d0a8d1d96b9ee9249`; corrected runner-bundle fingerprint is `9179cf51614dc3c43dc4189d5dc2835cb4ed3ba781811dbe0050cea4470ee9bf`. Portable V1C2A2R1 coverage is `41/41`, package boundaries are green and no Sandbox has been launched.

Pipeline proof `17898746de49d8e0e769b44148f668ba407e41a96b654840e4266010096c51bc` proves targeted runner flow wiring is exact and full `check` contains no active V1C2C2 Windows composition. It also proves current downstream imports are not self-consistent after the R1 identity change: importing V1C2C2 composition policy reaches preserved V1C2C1R4 controller-worker policy and raises `V1C2C1 controller-worker policy self-check failed`. This occurs before any pipeline flow or Sandbox launch.

The cause is deterministic. The V1C2C1R4 policy semantic payload binds the V1C2A2 runner bundle fingerprint and payload SHA, while its verified policy fingerprint/bytes pins still describe the historical V1C2A2 bundle. The R4 controller bytes and controller-worker bundle also derive from those runner/policy identities. V1C2C2 then binds both runner and controller-worker identities. Therefore RC029's exact two-file scope and its pre-commit green full-`check` requirement cannot both hold.

Roadmap Change 030 resolves only that acceptance cycle. It preserves the exact V1C2A2R1 two-file implementation scope and permits its commit after scoped host-only gates that do not require stale downstream imports. Full `check` and Runtime Architecture Audit are deferred until an exact four-file host-only `V1C2C1R5` identity rebind and subsequent portable seven-file V1C2C2 rebind restore downstream self-consistency. RC030 authorizes no active V1C2C2 run.

```text
RC027       FAILED / CONSUMED / MUST NOT BE RERUN
RC028       COMPLETED / CONSUMED / MUST NOT BE RERUN
V1C2A2R1   CURRENT / EXACT TWO-FILE PRE-COMMIT CANDIDATE / HOST-ONLY
V1C2C1R5   PLANNED / BLOCKED UNTIL R1 COMMIT
V1C2C2      BLOCKED / R4 CANDIDATE PRESERVED / AWAIT R1 + R5 REBIND
V1C2C3      BLOCKED
R1 patch SHA-256: b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2
R4 candidate SHA-256: dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

### Roadmap Change 031 — V1C2B downstream verifier identity rebind

RC030 scoped pre-commit execution on exact documentation HEAD `146b2133c1a05d983e398d6139cd6383f7de1b5e` stopped before Windows bundle smoke, targeted flow or commit because V1C2B is stale under the R1 worktree. Independent gates remained green: package boundaries `28/28`, V1C2A1 `45/45`, V1C2A2R1 `41/41`. V1C2B failed `19/44`; historical policy fingerprint `cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf` recomputed as `d7fc8c5011e6dd353202ebd04567d1e7f59d7af523c8c9b20769afc6b38d45a2`. No Sandbox or pipeline flow launched.

Historical V1C2B explicitly pins exact V1C2A2 policy/runner/payload identities. It is therefore a downstream identity consumer, not an R1-independent prerequisite. RC031 removes V1C2B from R1 scoped gates, inserts host-only `V1C2BR1` after R1 commit, and blocks R5 until BR1 is verified.

```text
RC030 docs commit HEAD:             146b2133c1a05d983e398d6139cd6383f7de1b5e
V1C2A2R1 patch SHA-256:             b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2
V1C2C2 candidate SHA-256:           dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05
V1C2B historical policy fp:         cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf
V1C2B R1-dependent recomputation:   d7fc8c5011e6dd353202ebd04567d1e7f59d7af523c8c9b20769afc6b38d45a2
V1C2A1:                              45/45 PASS
V1C2A2R1:                            41/41 PASS
package boundaries:                  28/28 PASS
V1C2B:                               19/44 FAIL / EXPECTED STALE PIN CASCADE
Sandbox launched:                    false
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

### Следующее точное действие

1. Commit Roadmap Change 031 in only the three architecture documents on exact `HEAD / origin/main == 146b2133c1a05d983e398d6139cd6383f7de1b5e`. Preserve empty cached diff, exact R1 patch SHA-256 `b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2`, exact seven-file V1C2C2 candidate SHA-256 `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05`, stable V1B4 and consumed evidence. No pipeline or Sandbox launch belongs to the docs transition.
2. After RC031 is committed and pushed, run only R1-independent scoped gates: Python syntax, package boundaries, V1C2A1, V1C2A2R1 `41/41`, existing V1C2A2 Windows bundle smoke, exact targeted `developer_task_execution_compile_ast_runner` flow, exact two-file patch verification and empty Sandbox process set. Do not run V1C2B, full `check` or Runtime Architecture Audit before downstream rebind.
3. If those gates pass, commit exactly `modules/developer/developer_task_execution_compile_ast_runner.py` and `tools/eval_developer_task_execution_compile_ast_runner.py` with subject `fix: preserve compile ast payload launch field order`, push, repeat the same R1-independent scoped gates post-commit and stop.
4. On committed R1, perform a host-only source audit of the four existing V1C2B verifier files, lock the exact changed subset, then implement and independently verify `V1C2BR1`. Required BR1 evidence includes V1C2B `44/44`, Windows CNG `1/1`, targeted verifier flow, package boundaries and zero active execution.

### Roadmap Change 032 — V1C2A2R1 Windows-smoke identity expectation rebind

RC031 R1-independent pre-commit execution on exact documentation HEAD `46ce8f1c3263d78133ae0e6b649f4f0c9c89671f` stopped before any commit, targeted runner flow or Sandbox launch. Package boundaries, V1C2A1 and corrected V1C2A2R1 remained green, but `tools/eval_developer_task_execution_compile_ast_runner_windows.py` failed its single host-only Windows bundle check because actual payload SHA-256 `501ed90023f8f8afc75c7676a8acba3d1497334e398f929d0a8d1d96b9ee9249` and bundle fingerprint `9179cf51614dc3c43dc4189d5dc2835cb4ed3ba781811dbe0050cea4470ee9bf` are correct while the smoke still expects historical `730d4108aab8246d1e6ff030a4d5a64ad25a89adf888e2b10c64ec63d56f60b6` / `b1f182ca4ee1a9e83cb6a32ca54e45d4511c81faa27d8dd4be7817883affb9f3`. The smoke itself reports every active flag false; this is stale evaluator evidence, not a production failure.

RC032 widens the still-uncommitted V1C2A2R1 scope by exactly one evaluator file. The locked R1 scope is now exactly three tracked files: `modules/developer/developer_task_execution_compile_ast_runner.py`, `tools/eval_developer_task_execution_compile_ast_runner.py`, and `tools/eval_developer_task_execution_compile_ast_runner_windows.py`. The Windows evaluator may change only the expected corrected payload SHA and runner-bundle fingerprint plus directly necessary test bookkeeping. Generated guest runner bytes/SHA, V1C2A1, runner-policy fingerprint, launch behavior and all execution prohibitions remain unchanged. Historical two-file patch SHA `b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2` remains evidence only; a new exact three-file candidate SHA must be measured before commit.

Next exact action after RC032 docs: rebind only the Windows-smoke expected identities, prove production identities unchanged, run Python syntax, package boundaries, V1C2A1 `45/45`, V1C2A2R1 `41/41`, Windows bundle smoke `1/1`, exact targeted runner flow and empty Sandbox process set; measure and commit exactly the three R1 files with subject `fix: preserve compile ast payload launch field order`; repeat the same gates post-commit and stop before V1C2BR1. Do not run V1C2B, full `check`, Runtime Architecture Audit, downstream controller/composition imports or Sandbox composition.

Operational state after Roadmap Change 032:

```text
V1C2A2R1   CURRENT / EXACT THREE-FILE PRE-COMMIT / HOST-ONLY / NON-AUTHORIZING
V1C2BR1    PLANNED / BLOCKED UNTIL V1C2A2R1 COMMIT
V1C2C1R5   PLANNED / BLOCKED UNTIL V1C2BR1 VERIFIED
V1C2C2     BLOCKED / AWAIT R1 + BR1 + R5 REBIND
V1C2C3     BLOCKED
```
5. After verified BR1 is committed, prepare `V1C2C1R5` as the exact four-file host-only/non-authorizing identity rebind of R4 to committed R1/BR1 identities. Preserve R4 semantics and measure every changed identity from final bytes.
6. After verified R5 is committed, rebind the preserved seven-file V1C2C2 candidate to committed R1/BR1/R5 identities, run portable gates, full `check` and Runtime Architecture Audit, then stop before any active retry. Any fresh active V1C2C2 attempt requires another explicit Roadmap Change and a new permanent consumed marker. V1C2C3 remains BLOCKED.

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

## Chat handoff snapshot after V1C2A2R1 closure - 2026-08-26

This snapshot supersedes earlier RC032 operational labels for the current execution state.

V1C2A2R1 implementation commit: 13c136803982871be4df28229cf4988e598b9cf3
parent RC032 docs commit: aa37c4bc57c3bf84b0d3ebe3b593bc209f4d7e1e
commit subject: fix: preserve compile ast payload launch field order
exact committed R1 scope: 3 files
exact R1 patch bytes: 5229
exact R1 patch SHA-256: e913d1d5866a6930769b2a8312e203735ce866304fcbc1cfb855f082cedef30d
guest runner SHA-256: 6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9
corrected payload SHA-256: 501ed90023f8f8afc75c7676a8acba3d1497334e398f929d0a8d1d96b9ee9249
corrected bundle fingerprint: 9179cf51614dc3c43dc4189d5dc2835cb4ed3ba781811dbe0050cea4470ee9bf
package boundaries post-commit: 28/28
V1C2A1 post-commit: 45/45
V1C2A2R1 portable post-commit: 41/41
V1C2A2 Windows bundle smoke: 1/1
targeted runner flow post-commit: PASS
Sandbox launched: false
changed code executed: false
execution authorized: false
full check: NOT RUN / DEFERRED
Runtime Architecture Audit: NOT RUN / DEFERRED
stable V1B4: 91d8c37fc4afe7ef138e36063e7bc22014da8a2c

Preserved V1C2C2 worktree candidate:
scope: exact seven files
bytes: 225629
SHA-256: dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05
cached diff: empty
untracked: empty
active Sandbox authorization: none

The earlier V1C2B run before BR1 is diagnostic stale-downstream evidence, not an R1 failure. Historical verifier policy fingerprint cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf recomputes as d7fc8c5011e6dd353202ebd04567d1e7f59d7af523c8c9b20769afc6b38d45a2 against the committed V1C2A2R1 runner identities. Do not treat the resulting V1C2B evaluator failures as independent defects.

### Next Exact Action

Start V1C2BR1 with a READ-ONLY / HOST-ONLY source audit of exactly these existing verifier files:

modules/developer/developer_task_execution_compile_ast_verifier.py
modules/developer/developer_task_execution_compile_ast_verifier_policy.py
tools/eval_developer_task_execution_compile_ast_verifier.py
tools/eval_developer_task_execution_compile_ast_verifier_windows.py

The audit must determine the exact minimal changed subset needed to bind committed V1C2A2R1 payload/bundle identities and measure every resulting V1C2B identity before any mutation.

Do NOT yet:
- modify V1C2C1R4/R5
- modify the preserved V1C2C2 candidate
- run full pipeline check
- run Runtime Architecture Audit
- launch Windows Sandbox
- consume any active composition retry
- start V1C2C3

Required order remains:

V1C2A2R1 VERIFIED
-> V1C2BR1 host-only identity rebind
-> V1C2C1R5 host-only identity rebind
-> preserved V1C2C2 portable rebind
-> full check + Runtime Architecture Audit
-> explicit Roadmap Change before any new active V1C2C2 attempt

## Chat handoff snapshot after V1C2C2 global closure / Roadmap Change 033 — 2026-08-26

This snapshot supersedes the earlier V1C2A2R1/BR1/R5 waiting-state labels for the current operational state.

```text
committed HEAD before RC033 docs:        b0bf07015b001499c48c8fc334472993cc83bdb1
origin/main:                             b0bf07015b001499c48c8fc334472993cc83bdb1
stable V1B4:                             91d8c37fc4afe7ef138e36063e7bc22014da8a2c

V1C2A2R1 implementation:                 13c136803982871be4df28229cf4988e598b9cf3
V1C2BR1 implementation:                  1280fc816316255762b913fe2fd085738c1a8b83
V1C2C1R5 implementation:                 b0bf07015b001499c48c8fc334472993cc83bdb1

R1 runner SHA-256:                       6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9
R1 payload SHA-256:                      501ed90023f8f8afc75c7676a8acba3d1497334e398f929d0a8d1d96b9ee9249
R1 runner bundle fingerprint:            9179cf51614dc3c43dc4189d5dc2835cb4ed3ba781811dbe0050cea4470ee9bf
BR1 verifier policy fingerprint:         d7fc8c5011e6dd353202ebd04567d1e7f59d7af523c8c9b20769afc6b38d45a2
R5 controller-worker policy fingerprint: 2dc6aaba3384a072524053a90adbdbf394332a8d83c10b6863dd62f1a6365f2f
R5 policy bytes SHA-256:                 04102be389be5624c34fcc12c88d998c57840633e9f349d1e59fc0ba03e1eb17
R5 controller SHA-256:                   75ebefd7c3d6fa06f9176ba4f1c75424940b7e92e3f2cfb4901c656da4326653
R5 bundle fingerprint:                   6e09456eb4d0c76eef136dd7f1d0c40510932dba6887f738529d19481fb5ead0

rebound V1C2C2 candidate bytes:          225629
rebound V1C2C2 candidate SHA-256:        296d1c94a884f065d27e65cb312618576c8f7ce4e60c7a3ee2fa84c7f4a2ff2e
composition policy fingerprint:          b4d254963b38caaf1031e85d304eda186eeb784c46ce42af97f0eb3c8c215976
composition policy bytes SHA-256:        fb34f1e7d41f8c5f2ef79a39b8a833c7eb4981769bf1b894f14e7b19b7eddd16

package boundaries:                      28/28 PASS
portable V1C2C2:                         48/48 PASS
full check:                              PASS
Runtime Architecture Audit:              9/9 PASS

global closure report SHA-256:           ef530ff345870f86fdb2ec0878476507181c2e58c4fd509c35226b39b9ff8b23
full check log SHA-256:                  930efb0fb69146d00660dd03d889d4588395a526a73d5ff1b44215883532af96
roadmap-transition audit SHA-256:         64f021d309f7cb9507d8b79d3051fd9ca64beba9663ecf6bc91818e50bbf93b8

real active V1C2C2 retry during rebind:   NOT RUN
real Sandbox launch during rebind:        false
candidate code commit:                    NOT PERFORMED
```

Roadmap Change 033 is the first authority after the R1/BR1/R5 cascade that may permit another real V1C2C2 run. It authorizes exactly one fresh active attested-pass attempt against the exact rebound candidate. A permanent RC033 consumed marker must be reserved before launch and makes the attempt single-use regardless of outcome. RC024 and RC027 remain failed/consumed and may never be rerun. V1C2C3 remains BLOCKED.

### Next Exact Action

Run a READ-ONLY / HOST-ONLY audit of:

```text
tools/eval_developer_task_execution_compile_ast_composition_windows.py
modules/developer/developer_task_execution_compile_ast_composition.py
historical RC024 / RC027 consumed-marker convention
current pipeline topology for developer_task_execution_compile_ast_composition
```

The audit must determine, before any active action:

1. exact current Windows evaluator case count and acceptance fields;
2. exact permanent RC033 marker path and canonical schema;
3. exact point at which the marker must be atomically persisted before Sandbox launch;
4. proof that the active path can launch at most one Sandbox;
5. exact report/log evidence retained after pass or failure;
6. exact cleanup and repository-preservation checks.

Do not yet create the RC033 consumed marker, launch Windows Sandbox, consume a V1C2C0 transaction/runtime lease, execute the candidate interpreter, commit the seven-file candidate or start V1C2C3.

## Chat handoff snapshot after V1C2C2 verification closure — 2026-08-27

This snapshot supersedes earlier V1C2C2 CURRENT / candidate / active-retry operational labels.

```text
HEAD / origin/main after implementation: c4ceb272898600a90be9db56c990e0c8d98a7bac
implementation parent:                  372fa7554a107226675b1d5c0d845b65d50b8a53
implementation subject:                 feat: add active compile ast sandbox composition
stable V1B4:                             91d8c37fc4afe7ef138e36063e7bc22014da8a2c

V1C2C2 committed patch bytes:            225629
V1C2C2 committed patch SHA-256:          296d1c94a884f065d27e65cb312618576c8f7ce4e60c7a3ee2fa84c7f4a2ff2e
composition policy fingerprint:         b4d254963b38caaf1031e85d304eda186eeb784c46ce42af97f0eb3c8c215976
composition policy-document SHA-256:    fb34f1e7d41f8c5f2ef79a39b8a833c7eb4981769bf1b894f14e7b19b7eddd16

RC033 consumed marker SHA-256:           5bffd4f5cbf204dbe3ee290cc733a7d4271a8f8789856e190bc869affb6666d9
RC033 terminal result SHA-256:           8e5d708f7385c8b8c1f8ca22bc0a641c3d1f67f41be63821fbb266338bb59af2
active evaluator log SHA-256:            18b5c73f79532c09db45a4966a5ac52d8f6b36f19559e96931bcfe9138f4bb65
parsed active evidence SHA-256:          51a48b62675ebd013abba96d1e6b97a37f35a87f39586572e396bf05331ef1d6
terminal recovery report SHA-256:        f3c9f1d27732ce8cdb7a4a69bd37647e30cc13d66d5d07f9a16847c7a117ae92
implementation closure report SHA-256:   ed5712c3496573eb7c0648f237511ec0b316805f3bb5e22dae67aa27612ceeb6

active Windows acceptance:               3/3 PASS
pre-commit full check:                   PASS
pre-commit Runtime Architecture Audit:   9/9 PASS
post-commit full check:                  PASS
post-commit Runtime Architecture Audit:  9/9 PASS

RC033:                                   PASSED / CONSUMED / MUST NOT BE RERUN
V1C2C2:                                  VERIFIED / COMMITTED / ACTIVE ATTESTED-PASS CLOSED
V1C2C3:                                  BLOCKED
```

Important permanent rules from this closure:

- Never rerun RC033 or `tools/eval_developer_task_execution_compile_ast_composition_windows.py` as part of V1C2C2 closure.
- Never delete, reset or overwrite the RC033 consumed marker.
- Preserve the append-only terminal result as the terminal truth for the successful one-shot attempt.
- The normal targeted V1C2C2 composition flow is not a post-closure check because it contains the already-consumed active Windows evaluator.
- Full `check` remains non-active with respect to V1C2C2 Windows composition.
- Stable `skynet-trusted-runtime-v1b4` remains unchanged.

### Next Exact Action

Start the next chat from a READ-ONLY / HOST-ONLY V1C2C3 roadmap-and-source transition audit.

The audit must:

1. verify the exact committed V1C2C2 closure state at current `HEAD / origin/main`;
2. read the current roadmap/trusted-runtime V1C2C3 contract and historical locked identity;
3. inventory existing V1C2C3 production/evaluator files and pipeline wiring;
4. determine whether current docs already authorize any V1C2C3 action or whether an explicit Roadmap Change 034 is required;
5. classify each possible V1C2C3 gate as portable, host-only or active;
6. stop before any V1C2C3 mutation, capability claim, Sandbox launch or interpreter run.

Do not yet create Roadmap Change 034, modify V1C2C3 code, run a V1C2C3 active acceptance, launch Sandbox or widen the roadmap. The transition audit decides the next authorized step.

## Roadmap Change 034 — V1C2C3 evaluator-only implementation authority

Roadmap Change 034 is CURRENT after the read-only V1C2C3 transition audit.

```text
HEAD before RC034:                        e30a1df8ad3b403e52bd4c84668b9e02f44ec7eb
V1C2C2 implementation commit:             c4ceb272898600a90be9db56c990e0c8d98a7bac
stable V1B4:                              91d8c37fc4afe7ef138e36063e7bc22014da8a2c
V1C2C3 locked evidence identity:          b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
V1C2C3 transition-audit SHA-256:          2b6a468b8c262b082e78f399634dd7a78badb7bfa07432240ea66a801c7a01e1
```

RC034 authorizes exactly one evaluator-only four-file candidate:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
tools/eval_package_boundaries.py
tools/pipeline.py
```

There is no authorized V1C2C3 production-module change. The public V1C2C2 composition API must not gain fault-injection or caller-controlled execution inputs.

The portable evaluator owns non-active proof of the three-row acceptance contract. The Windows evaluator may be written but is intentionally not wired into `check` or any targeted flow and MUST NOT be executed under RC034.

Future live matrix, still BLOCKED:

```text
1. fresh live pass
2. fresh authentic syntax failure
3. fresh signed post-ready boundary failure

three fresh capability chains
three fresh V1C2C0 transactions
three fresh runtime leases
three fresh Sandbox instances
no cross-row reuse
```

Permanent outcome invariants:

```text
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

Current operational state:

```text
RC033:   PASSED / CONSUMED / MUST NOT BE RERUN
V1C2C2:  VERIFIED / COMMITTED / ACTIVE ATTESTED-PASS CLOSED
RC034:   CURRENT / NON-ACTIVE IMPLEMENTATION AUTHORITY ONLY
V1C2C3:  CURRENT / EVALUATOR-ONLY IMPLEMENTATION CANDIDATE
         ACTIVE THREE-RUN MATRIX BLOCKED
Sandbox: NOT AUTHORIZED
```

### Next Exact Action

Create exactly the four RC034 candidate files and stop after non-active verification. The allowed gates are Python syntax/AST checks, package boundaries, portable V1C2C3 evaluator, source-only pipeline topology verification, full `check` only with proven V1C2C3 Windows-evaluator count `0`, Runtime Architecture Audit, candidate identity measurement and Sandbox-process-set empty verification.

Do not run `tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py`.
Do not launch Windows Sandbox.
Do not consume a V1C2C0 transaction or claim a runtime lease.
Do not execute the candidate interpreter.
Do not commit the candidate before exact evidence review.
Do not create the later active-authorization Roadmap Change yet.

## Roadmap Change 034 implementation closure — 2026-08-27

RC034 evaluator-only implementation is now committed and NON-ACTIVE VERIFIED.

```text
HEAD / origin after implementation:      a2a4be24e2507d70312ab363853a6dd578380568
implementation parent:                  3abd91ebb3c3d24e99ed756e6f8b5cd3cda0149d
implementation subject:                 feat: add compile ast live acceptance evaluators
patch bytes:                            51956
patch SHA-256:                          dca08c8e9cee29e0e45e7ac5b6a7459d82eea2cc3c356d5794260b56c43caacf
candidate evidence SHA-256:             754c80b97a630d58c61e795ca836f58c6046f73b0f91ed3aeb45a97146799ea5
implementation closure SHA-256:         aa7391d3b4e655c54881f59dc193fe2fa5c783824fdca622780b6505a4f1611f
historical V1C2C3 evidence identity:    b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

Exact committed source identities:

```text
portable live acceptance:
6ce0c1e8322153dc24df0e372a024a1adcbb199760a68c4014f13b3792b91a0b

Windows future live acceptance:
d928155bff1679d71509a110af4a46615d42cd2ab75a249d4d8f410237b65027

package boundaries:
717b3da8fc48a36ea4cb5048a248b95d1e24757c6f76fe994f0e3ba0f0546652

pipeline:
4c42f1bea0fef653e8f58a9cfb39c6980bd16caceb1038f983e6e24e54cff188
```

Verification:

```text
pre/post package boundaries:             PASS
pre/post portable V1C2C3 evaluator:      PASS
pre/post full check:                     PASS
pre/post Runtime Architecture Audit:     PASS
Windows evaluator pipeline references:  0
Windows evaluator executed:              false
Sandbox launched:                        false
```

Current state:

```text
RC033:   PASSED / CONSUMED / MUST NOT BE RERUN
V1C2C2:  VERIFIED / COMMITTED / ACTIVE ATTESTED-PASS CLOSED

RC034:   COMPLETED / NON-ACTIVE IMPLEMENTATION VERIFIED
V1C2C3:  IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED
         ACTIVE THREE-RUN MATRIX BLOCKED

next active authority: NOT CREATED
```

### Next Exact Action

Perform a READ-ONLY / HOST-ONLY V1C2C3 active-authority transition audit only.

The audit must decide the irreversible active-attempt model before any live run:

1. exact binding to committed implementation `a2a4be24e2507d70312ab363853a6dd578380568`;
2. exact pass / authentic syntax-failure / signed boundary-failure expected evidence;
3. permanent pre-run consumed marker design for each future row;
4. whether one roadmap grant may authorize all three independently consumed rows or each row needs its own roadmap grant;
5. failure / partial-matrix / no-rerun semantics;
6. three fresh capability chains, transactions, runtime leases and Sandbox instances with no reuse;
7. source/workspace/evidence cleanup requirements after every row;
8. exact later pipeline wiring, if any, without making active execution part of normal `check`.

Do not create the next Roadmap Change yet.
Do not wire or run the V1C2C3 Windows evaluator.
Do not set `SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1`.
Do not launch Sandbox.

## Roadmap Change 035 — V1C2C3 non-active row-isolation hardening

The V1C2C3 active-authority transition audit completed read-only and proved the committed Windows evaluator is not yet active-authority ready.

```text
HEAD / origin before RC035:                  811c542e4cb706f07176defed442e260bfc7466f
V1C2C3 evaluator implementation commit:      a2a4be24e2507d70312ab363853a6dd578380568
V1C2C3 implementation patch SHA-256:         dca08c8e9cee29e0e45e7ac5b6a7459d82eea2cc3c356d5794260b56c43caacf
active-authority transition audit SHA-256:   547891c2a9880e03403253e1cea130f58d947e8dc657625270c493344cb68b51
historical V1C2C3 evidence identity:         b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

Audit decision:

```text
current main() full-matrix authority:    REJECTED
direct _run_case authority path:         REJECTED
current Windows evaluator ready:         NO
preferred future authority:
    one matrix grant
    three independent permanent row consumed markers
```

RC035 is CURRENT only for an exact two-file evaluator hardening:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
```

No production, package-boundary or pipeline change is authorized.

Required hardening:

```text
required --row selector
one row per process
host env guard before all active work
private in-process authority capability minted only after guard
_run_case requires genuine capability
_run_case rejects missing/forged capability before active calls
no automatic for row in ROWS active loop
portable evaluator proves all row-isolation and guard properties statically
Windows evaluator remains unwired
```

Current state:

```text
RC034:   COMPLETED / NON-ACTIVE IMPLEMENTATION VERIFIED
RC035:   CURRENT / NON-ACTIVE ROW-ISOLATION HARDENING ONLY

V1C2C3:  IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED
         ROW-ISOLATION HARDENING CURRENT
         ACTIVE THREE-RUN MATRIX BLOCKED

active authority:             NONE
Windows evaluator execution: FORBIDDEN
Windows pipeline references: 0
Sandbox:                      NOT AUTHORIZED
```

### Next Exact Action

Create exactly the two RC035 evaluator changes and perform non-active verification only: syntax/AST, `git diff --check`, portable evaluator, unchanged package boundaries, source-only pipeline topology, full `check` only after Windows count remains `0`, Runtime Architecture Audit, exact candidate identity and empty Sandbox-process verification.

Stop before candidate commit for evidence review.

Do not run the Windows evaluator.
Do not set `SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1`.
Do not create row consumed markers.
Do not create the later active-authority Roadmap Change.

## Roadmap Change 035 implementation closure — 2026-08-27

RC035 row-isolation hardening is now committed and NON-ACTIVE VERIFIED.

```text
implementation commit:                  1693e3e8fdac6026c5b48735c0b2539a7cc2f246
implementation parent:                  800b4403d998a4a85d80bf8df538779e42ad2d99
implementation subject:                 fix: isolate V1C2C3 live acceptance rows
patch bytes:                            35183
patch SHA-256:                          99c4a10675ac19c5e88ceb46325b8c27513c79405c19797061386c4056b1b02f
candidate evidence SHA-256:             d941ab1bd9dcb85ac410ba1eb7b7f48cd9e57d3041bad6ec5367e607608ddd7b
implementation closure SHA-256:         6db703b9a4549ffa9c0e6a8b8c41aa394b7b4bd9de3c98f122ed88812f163783
portable evaluator SHA-256:             281c75d9237baacb7f3631069c1af0d95a1eecc052dae78587a2b6367e08abbb
Windows evaluator SHA-256:              d7135796b2cbb29d68a41ee3c391c3f0579c6b570da30ac3cd41d9a09fb849dd
historical V1C2C3 evidence identity:    b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

Verified hardening:

```text
required --row selector:                 present
exactly one row per process:             enforced
full automatic ROWS active loop:         removed
host authority guard:                    preserved before active work
private row authority capability:        required
missing/forged/replayed capability:      fails before active calls
Windows evaluator pipeline refs:         0
Windows evaluator executed:              false
consumed/result markers:                 0 / 0
Sandbox launched:                        false
```

Pre/post package boundaries, portable evaluator, full `check` and Runtime Architecture Audit all passed.

Current state:

```text
RC034:   COMPLETED / NON-ACTIVE IMPLEMENTATION VERIFIED
RC035:   COMPLETED / NON-ACTIVE ROW-ISOLATION HARDENING VERIFIED

V1C2C3:  IMPLEMENTED / COMMITTED / ROW-ISOLATED / NON-ACTIVE VERIFIED
         ACTIVE THREE-RUN MATRIX BLOCKED

active authority:             NONE
Windows evaluator execution: NOT AUTHORIZED / NOT RUN
Windows pipeline references: 0
V1C2C3 markers:              0 / 0
Sandbox:                      NOT AUTHORIZED
next Roadmap Change:          NOT CREATED
```

### Next Exact Action

Perform only a fresh READ-ONLY / HOST-ONLY active-authority readiness audit against the committed hardened evaluator.

The audit must prove, from exact committed source:

1. `--row` is required and has exactly the three locked choices;
2. no full-matrix row loop remains in `main()`;
3. authority guard executes before runtime lookup and active work;
4. private row capability is minted only after the guard;
5. `_run_case` requires the capability;
6. invalid, forged and replayed capability paths fail before every active call;
7. exactly one selected row reaches `_run_case`;
8. pipeline references to Windows evaluator remain `0`;
9. no V1C2C3 active marker/result exists;
10. future marker/no-rerun semantics can be bound safely to the hardened implementation.

Do not create the next Roadmap Change yet.
Do not run the Windows evaluator.
Do not set `SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1`.
Do not create V1C2C3 consumed/result markers.
Do not launch Sandbox.

## Roadmap Change 036 — V1C2C3 one-shot active matrix authority contract

The committed hardened evaluator passed the fresh active-authority readiness audit.

```text
baseline HEAD / origin:                    49d6bbfb1c0520a0e4eaa160885736618e25b98c
readiness-audit SHA-256:                  c8313da61f53aafa39a6530ae3f3448f7f80c20a57539e174b1bcd6323da0186
RC035 implementation commit:             1693e3e8fdac6026c5b48735c0b2539a7cc2f246
portable evaluator SHA-256:              281c75d9237baacb7f3631069c1af0d95a1eecc052dae78587a2b6367e08abbb
Windows evaluator SHA-256:               d7135796b2cbb29d68a41ee3c391c3f0579c6b570da30ac3cd41d9a09fb849dd
historical V1C2C3 evidence identity:     b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

RC036 defines one matrix grant with three independently consumed rows:

```text
1. live_pass
2. authentic_syntax_failure
3. signed_post_ready_boundary_failure
```

Permanent marker/result names:

```text
V1C2C3_RC036_LIVE_PASS_CONSUMED.json
V1C2C3_RC036_LIVE_PASS_RESULT.json

V1C2C3_RC036_SYNTAX_FAILURE_CONSUMED.json
V1C2C3_RC036_SYNTAX_FAILURE_RESULT.json

V1C2C3_RC036_BOUNDARY_FAILURE_CONSUMED.json
V1C2C3_RC036_BOUNDARY_FAILURE_RESULT.json

V1C2C3_RC036_MATRIX_RESULT.json
```

Every row is a separate child process and separate permanent one-shot reservation. The marker is created before active entry and consumes that row regardless of outcome. The marker is immutable; the terminal result is a separate append-only file. No `File.Replace` or overwrite finalization is permitted.

A failed or uncertain row stops RC036 immediately. Remaining rows are not run under that grant. Passed/consumed rows are never repeated. Any recovery or authorization of failed/unstarted rows requires a later explicit Roadmap Change with new grant-specific marker names.

Current state:

```text
RC034:   COMPLETED / NON-ACTIVE IMPLEMENTATION VERIFIED
RC035:   COMPLETED / NON-ACTIVE ROW-ISOLATION HARDENING VERIFIED
RC036:   CURRENT / ONE-SHOT MATRIX AUTHORITY CONTRACT
         PRE-EXECUTION HARNESS AUDIT REQUIRED

V1C2C3:  IMPLEMENTED / COMMITTED / ROW-ISOLATED
         ACTIVE MATRIX CONTRACT OPEN
         0 OF 3 ROWS CONSUMED
         NO ROW EXECUTED

active environment:             ABSENT
Windows evaluator execution:   NOT RUN
Windows pipeline references:   0
consumed/result markers:       0 / 0
Sandbox:                       NOT LAUNCHED
```

### Next Exact Action

Create and source-audit the external RC036 one-shot authority harness only.

Required pre-execution proofs:

1. exact evaluator CLI/output and row evidence parsing;
2. no import of the Windows evaluator by the authority harness;
3. exact committed evaluator/runtime/harness identities;
4. parent environment has no active variable;
5. child-only active environment and exactly one `--row`;
6. disposable self-test of the exact exclusive-create JSON primitive;
7. immutable marker and append-only result schemas;
8. fixed row ordering and previous-result SHA bindings;
9. stop-on-first-failure/no-rerun behavior;
10. pipeline references remain zero, markers/results remain absent and Sandbox remains empty.

Stop before creating any permanent RC036 marker or invoking an active row.

## Roadmap Change 037 — V1C2C3 non-active path-budget hardening

The read-only RC036 root-cause audit completed and fixed the irreversible state:

```text
HEAD / origin before RC037:             a0a352fe19e843a4f7b80c0e26a6b938520a9056
root-cause audit bytes:                 30591
root-cause audit SHA-256:               6e3269faf9ade9bbde51e5b123ffec87ed65590dd7c5cfd64f6bb2d82d309b25
historical V1C2C3 evidence identity:    b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

RC036 permanent state:

```text
live_pass:                    PASSED / CONSUMED / IMMUTABLE
syntax_failure:               INFRASTRUCTURE-FAILED / CONSUMED / IMMUTABLE
boundary_failure:             NOT STARTED / NOT AUTHORIZED UNDER RC036
RC036 MATRIX_RESULT:          ABSENT / MUST REMAIN ABSENT
RC036 rerun:                  FORBIDDEN
```

Root cause:

```text
evaluator-private repeated row names produced a 274-character Git object path
classic Windows limit = 260
over limit = 14
failure occurred in _prepare / git clone
before plan / lease / transaction / composition / Sandbox
```

RC037 exact mutable scope:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
```

Required private path recipe:

```text
live_pass                          -> p
authentic_syntax_failure           -> s
signed_post_ready_boundary_failure -> b
TEMP prefix                        -> sv3-
row directory                      -> p / s / b
task id                            -> v3-p / v3-s / v3-b
```

Canonical row names and all public/production contracts remain unchanged. Proposed worst-row loose-object path is `194`, with `66` characters of headroom.

Current state:

```text
RC036:   FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN
RC037:   CURRENT / NON-ACTIVE PATH-BUDGET HARDENING ONLY

V1C2C3:  LIVE PASS ACCEPTED FROM RC036
         SYNTAX ROW INFRASTRUCTURE-FAILED / CONSUMED IN RC036
         BOUNDARY ROW NOT STARTED
         PATH-BUDGET HARDENING CURRENT
         ACTIVE RECOVERY BLOCKED

active authority:             NONE
Windows evaluator execution: FORBIDDEN
Windows pipeline references: 0
Sandbox:                      NOT AUTHORIZED
recovery Roadmap Change:      NOT CREATED
```

### Next Exact Action

Create exactly the two RC037 evaluator changes and perform non-active verification only: AST/syntax, `git diff --check`, portable evaluator, unchanged package boundaries, source-only topology, full `check` only with Windows references `0`, Runtime Architecture Audit, exact candidate/patch identities and immutable RC036 evidence verification.

Stop before candidate commit for evidence review.

Do not rerun RC036.
Do not run any active V1C2C3 row.
Do not set `SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1`.
Do not modify/delete/rewrite RC036 markers/results.
Do not create RC036 MATRIX_RESULT.
Do not create the later recovery Roadmap Change yet.
## V1C2C3 RC037 IMPLEMENTATION CLOSURE — NON-ACTIVE VERIFIED

```text
HEAD / origin/main:
7eddbb1614d726a8267eca2f57851ae384293616

implementation parent:
3bee5567a2a02b907af7422e503abad1e37db567

implementation subject:
fix: shorten V1C2C3 evaluator private paths

RC036:
FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN

RC037:
COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED
```

RC037 permanently closes the evaluator-private Windows path-amplification defect without widening production scope. The exact two-file implementation has patch SHA-256 `fcf035632798e0561c78a3d5d1438ac5b45735bf8afabb127fe10f0150ab3690`. Private labels `p / s / b` reduce the simulated worst Git loose-object path from the failed RC036 value `274` to `194`, leaving `66` characters of classic Windows headroom.

Verification is complete and non-active:

```text
package boundaries                    PASS pre/post commit
portable V1C2C3 evaluator             PASS pre/post commit
full check                            PASS pre/post commit
Runtime Architecture Audit            PASS pre/post commit

Windows evaluator execution           NOT RUN / FORBIDDEN
Windows evaluator pipeline references 0
active authority                      NONE
Sandbox launch by RC037 closure       false
```

RC036 immutable evidence is preserved byte-for-byte. Never rerun RC036, never repeat its accepted `live_pass`, never reuse its consumed syntax marker, never create the missing RC036 boundary evidence, and never create `V1C2C3_RC036_MATRIX_RESULT.json`.

### Следующее точное действие

Run one **fresh read-only V1C2C3 recovery-readiness audit** from the exact committed RC037 state. It must not create a new Roadmap Change, marker, result or active environment and must not run the Windows evaluator or Sandbox.

The audit must determine whether a later recovery grant can safely:

1. bind and reuse only the already accepted immutable RC036 `live_pass` result without rerunning that row;
2. issue exactly one fresh grant-specific syntax-failure retry;
3. issue exactly one fresh grant-specific signed post-ready boundary-failure attempt;
4. stop permanently on the first failed/uncertain fresh attempt;
5. create a new recovery matrix result only after binding RC036 live-pass evidence plus both independently accepted fresh recovery rows;
6. keep every RC036 marker/result immutable and leave the absent RC036 matrix result absent.

Until that audit is reviewed:

```text
RC038            ABSENT / NOT CREATED
active recovery  BLOCKED
```
## Roadmap Change 038 — V1C2C3 split-provenance two-row recovery authority

```text
HEAD / origin entering transition:
abd97f5dd69581a706a4c609f17b123a44d2a80c

RC036:
FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN

RC037:
COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED

RC038:
CURRENT / SPLIT-PROVENANCE TWO-ROW RECOVERY CONTRACT
PRE-EXECUTION RECOVERY HARNESS AUDIT REQUIRED
```

Historical accepted evidence remains:

```text
RC036 live marker:
d944ae6b96a644563992b4f5354837b00be6156dbe90f989ac15bd5f39020f0c

RC036 live result:
30f1938b23febce463c17c5104d8d5b509b9b549322b2c81e7f03d4514cd85fc

terminal:
compile_ast_attested_passed

production composition:
748431106ed01d9898546c55799a4948424aa3e2eaed67181fce8110bbaea992

historical Windows evaluator:
d7135796b2cbb29d68a41ee3c391c3f0579c6b570da30ac3cd41d9a09fb849dd
```

That historical row is reused only as immutable evidence. It is never rerun.

Fresh RC038 execution, once separately harness-audited, is limited to:

```text
1. authentic_syntax_failure
2. signed_post_ready_boundary_failure
```

Exact future evidence:

```text
V1C2C3_RC038_SYNTAX_FAILURE_RETRY_CONSUMED.json
V1C2C3_RC038_SYNTAX_FAILURE_RETRY_RESULT.json

V1C2C3_RC038_BOUNDARY_FAILURE_CONSUMED.json
V1C2C3_RC038_BOUNDARY_FAILURE_RESULT.json

V1C2C3_RC038_RECOVERY_MATRIX_RESULT.json
```

The recovery matrix must explicitly record split evaluator provenance:

```text
RC036 historical live:
  evaluator d7135796b2cbb29d68a41ee3c391c3f0579c6b570da30ac3cd41d9a09fb849dd

RC038 fresh syntax/boundary:
  evaluator fdc8fdb4a52bf030c7486180db759ccb0a9a70490578881b6c12aa4fa620b1cb
```

It must not claim a single common evaluator identity for all three logical rows.

### Current prohibitions

Until the external RC038 harness and host-only preflight are reviewed:

```text
do not create RC038 markers/results
do not set active authority
do not invoke the Windows evaluator
do not launch Sandbox
do not rerun RC036
do not create missing RC036 boundary evidence
do not create RC036 MATRIX_RESULT
```

### Next Exact Action

Create the exact external RC038 split-provenance recovery harness and an independent source audit. The audit may run host-only/non-active gates, but must stop before the first RC038 permanent marker and before either active child row.
## Roadmap Change 039 — V1C1A durable-report sentinel determinism hardening

Current state:

```text
HEAD / origin entering RC039:
6d684c3700ffa39746ee0efa4fdbb3686fea34b4

RC038:
CURRENT / SPLIT-PROVENANCE TWO-ROW RECOVERY CONTRACT
ACTIVE EXECUTION BLOCKED

RC039:
CURRENT / V1C1A SENTINEL DETERMINISM HARDENING
```

Root cause:

```text
fixture raw binary prefix: abc
legacy check:            "abc" not in entire durable JSON
durable JSON contains:   SHA-256 / fingerprint identities
abc is valid hex:        true
false-positive capable:  true
```

The same evaluator at the same HEAD produced an isolated full-check failure and then a targeted `37/37 PASS`, confirming nondeterministic collision behavior rather than a demonstrated production privacy regression.

Exact mutable scope:

```text
tools/eval_developer_task_execution_workspace_snapshot.py
```

Exact intended replacement:

```text
b"abc\x00def"
->
b"__V1C1A_RAW_BINARY_SENTINEL__\x00def"

"abc" not in serialized
->
"__V1C1A_RAW_BINARY_SENTINEL__" not in serialized
```

Until RC039 is verified and closed:

```text
RC038 permanent evidence = 0
RC038 active authority = NONE
Windows active evaluator = DO NOT RUN
Sandbox = DO NOT LAUNCH
```

### Next Exact Action

Implement and verify the single evaluator-only correction. Stop before any RC038 marker.
## RC039 IMPLEMENTATION CLOSURE — VERIFIED / COMMITTED

```text
HEAD / origin entering RC039 closure:
f773a86b4ddde760f7a10f4722b316ebfd2115a5

RC039:
COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED

V1C1A evaluator:
bytes   31066
SHA-256 bcd0de47311064067ccce246dc897d9503d266734fb52dd229b58257a6d1c4ad

RC038:
CURRENT / SPLIT-PROVENANCE TWO-ROW RECOVERY CONTRACT
ACTIVE EXECUTION STILL BLOCKED
```

The V1C1A durable-report privacy test is now deterministic with respect to SHA-256/fingerprint identities. No production/runtime behavior changed.

Verified implementation result:

```text
targeted V1C1A evaluator       PASS pre/post commit
package boundaries             PASS pre/post commit
portable V1C2C3 evaluator      PASS pre/post commit
full check                     PASS pre/post commit
Runtime Architecture Audit     PASS pre/post commit
```

Safety state:

```text
RC038 permanent evidence       0
Windows active evaluator       NOT RUN
Windows evaluator pipeline refs 0
Sandbox                        EMPTY
active environment             ABSENT
```

### Next Exact Action

Run a fresh post-RC039 RC038 recovery-harness source/host-only preflight. It must bind this exact HEAD and current V1C1A evaluator identity and stop before any RC038 marker, child active authority or Sandbox launch.
## Roadmap Change 040 — V1C2C3 evaluator-private syntax-fixture reachability correction

```text
HEAD / origin entering RC040:
6dd329a788a64c713d86ad4de27a365d6dd363f6

RC038:
FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN

RC038 syntax retry:
CONSUMED / FAILED / IMMUTABLE

RC038 boundary row:
NOT STARTED / FORBIDDEN UNDER RC038

RC038 recovery matrix:
ABSENT / MUST REMAIN ABSENT

RC039:
COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED

RC040:
CURRENT / NON-ACTIVE EVALUATOR-ONLY REACHABILITY CORRECTION
```

Direct source review proved that the existing syntax fixture is placed into the workspace before the mandatory host static gate. The gate correctly rejects it, so the fixture cannot reach the trusted runtime through ordinary workspace ingress.

Locked correction:

```text
valid placeholder -> static PASS -> production snapshot
-> syntax-row-only scoped snapshot-material substitution
-> real public plan issuance
-> patch methods restored
-> ordinary transaction/materialization/runner/verifier chain
-> genuine signed runtime SyntaxError
```

Provenance must remain explicit:

```text
fixture_provenance = eval_private_scoped_snapshot_material_substitution_v1
ordinary_production_ingress = false
snapshot attests invalid bytes = false
public production plan API used = true
runtime SyntaxError genuine = true
```

Exact mutable scope:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_plan.py
```

Current safety state:

```text
RC038 syntax marker/result  immutable
RC038 boundary/matrix       absent
active authority            NONE
Windows active evaluator    DO NOT RUN
Windows evaluator pipeline refs 0
Sandbox                     DO NOT LAUNCH
production source changes   NOT AUTHORIZED
```

### Next Exact Action

Create and non-actively verify the exact three-file RC040 candidate. Stop before commit and before any active Windows/Sandbox execution.
## RC040 CLOSURE — IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED

```text
RC040 implementation commit:
cda355c76f47bac8775072a1e13075c211c3cda0

RC040 implementation parent:
00c779b706babf8341b3e418a5772471bf5ec01d

RC040 status:
COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED

exact mutable scope:
3 evaluator files

production/runtime source changes:
NONE
```

All post-commit non-active gates passed:

```text
V1C1B plan evaluator       PASS
portable V1C2C3 evaluator PASS
package boundaries        PASS
full check                PASS
Runtime Architecture Audit PASS
```

Safety state remains:

```text
Windows active evaluator pipeline references  0
Windows active evaluator execution             false
Sandbox launch                                 false
active environment                             ABSENT

RC038 syntax marker/result                     IMMUTABLE / PRESERVED
RC038 boundary marker/result                   ABSENT
RC038 recovery matrix                          ABSENT
```

The corrected syntax fixture is now runtime-reachable only through the explicitly evaluator-private plan-issuance substitution provenance:

```text
eval_private_scoped_snapshot_material_substitution_v1
```

Active recovery remains blocked.

### Next Exact Action

Run a fresh non-active recovery-readiness review against the RC040 implementation commit. If and only if that review passes, define a separate RC041 active grant with new marker/result names. Do not reuse any RC038 launcher, harness, marker, result, or row authority.
## Roadmap Change 041 — V1C2C3 post-RC040 split-provenance two-row recovery authority

```text
HEAD / origin entering RC041 docs transition:
de7704b2c804eb92b96537edbbd4b1feaa55849f

RC036:
live_pass ACCEPTED / IMMUTABLE / NO RERUN

RC038:
FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN

RC040:
COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED

RC041:
CURRENT / SPLIT-PROVENANCE TWO-ROW RECOVERY CONTRACT
PRE-EXECUTION HARNESS SOURCE AUDIT REQUIRED
```

Fresh RC041 rows are:

```text
1. authentic_syntax_failure
2. signed_post_ready_boundary_failure
```

Future evidence:

```text
V1C2C3_RC041_SYNTAX_FAILURE_CONSUMED.json
V1C2C3_RC041_SYNTAX_FAILURE_RESULT.json
V1C2C3_RC041_BOUNDARY_FAILURE_CONSUMED.json
V1C2C3_RC041_BOUNDARY_FAILURE_RESULT.json
V1C2C3_RC041_RECOVERY_MATRIX_RESULT.json
```

Current evaluator identities:

```text
Windows:
dc45fbf529684fde4625050afbb512dfaefcf140109fe859a6ebe98378917002

portable:
b20514efebe1c7a9e7277ea45fc0fbdd67be5b6e8aa9547ac291861a1c3b2ed8

plan evaluator:
b24a3fdd237993d26e6023b325c4a6de0de68575ba64ad92dec85f9821a9f644

production composition:
748431106ed01d9898546c55799a4948424aa3e2eaed67181fce8110bbaea992
```

Syntax provenance:

```text
eval_private_scoped_snapshot_material_substitution_v1
```

Historical `RC036 live_pass` remains bound under its historical evaluator
identity and is never rerun. Failed RC038 evidence remains immutable historical
failure evidence and is never reused as accepted RC041 evidence.

The exact production composition identity is pinned directly to
`748431106ed01d9898546c55799a4948424aa3e2eaed67181fce8110bbaea992`. A null/empty historical binding is forbidden.

### Current prohibitions

```text
do not create RC041 marker/result/matrix files
do not set active authority
do not invoke the Windows active evaluator
do not launch Sandbox
do not rerun RC036 or RC038
do not execute either RC041 row manually
do not reuse any earlier launcher/harness
```

### Next Exact Action

Create and source-audit a new RC041 external one-shot harness. Run its host-only
preflight only. Stop before the first permanent RC041 marker and before either
active child row.
## RC041 ACTIVE RECOVERY CLOSURE — PASSED / CONSUMED / IMMUTABLE

```text
RC041 recovery attempt:
rc041-recovery-20260831_230654-402a73ae8ae749a3b8e009f313887d94

RC041 status:
PASSED / CONSUMED / IMMUTABLE / CLOSED

V1C2C3:
VERIFIED / LIVE-SYNTAX-BOUNDARY MATRIX COMPLETE

V1C2:
COMPLETE

HEAD bound by active evidence:
7e3451499a18e7a9f6b53f657a9fa3c9ec470d47
```

Accepted rows:

```text
historical RC036 live_pass                 BOUND / NOT RERUN
fresh RC041 authentic_syntax_failure       ACCEPTED
fresh RC041 boundary failure               ACCEPTED
RC041 matrix                               CREATED / PASS
```

Permanent evidence:

```text
syntax marker   8a7868c2b2ca306d86c97a41d2c0434a52fc41a038f5aaba796683cb2b29b424
syntax result   a922751af6e82b756c8764ba0e1ebccf1e850dbc654477b5ab9d10182b28932d
boundary marker f1cda750ea5b3fc77a1c3ddcb6d87b8737ddf864e5e21ecefb3774c52d0ed8de
boundary result b7a0d9a5247d5efd13a04934090120fc6bba7f6e9bf1f22e2493ac42222c4a24
matrix result   e37f0a69d7ffc5bebf36c156d251b49853967e0ed8ee07401bacf6e7308b9b35
```

Final safety state:

```text
changed_code_executed  false
reusable_lease_issued  false
execution_authorized   false
repository/index       clean
active environment     absent
Sandbox                empty
```

The RC041 launcher and harness must never be run again. All five RC041 evidence
files are immutable and must never be deleted, rewritten, replaced or reused.

### Next Exact Action

Perform a read-only V1C3A transition audit. Do not acquire/download/install
Python dependencies, do not launch Sandbox and do not open RC042 until that
audit is reviewed.

## Roadmap Change 042 — V1C3A dependency-profile architecture lock

Current state:

```text
HEAD / origin/main entering RC042:
a250a9730291982d1a5512b121947e63e42fe002

RC041:
PASSED / CONSUMED / IMMUTABLE / CLOSED

V1C2:
COMPLETE

V1C3A:
CURRENT / ARCHITECTURE LOCK / NO ACQUISITION

RC042:
CURRENT / DOCS-ONLY / NON-AUTHORIZING
```

Exact transition context:

```text
SkynetVS_V1C3A_RC042_ExactProfileTopologyContext_20260901_131209.txt
bytes   5027022
SHA256  f3777bb9346258e944915c3b3e391de844e426653a6683432f71fd6150ecfefa
result  PASS
```

The verified profile graph is:

```text
skynetvs-python-base-v1
  roots = requirements.txt
  composition = standalone
  initial V1C3A acquisition = selected
  initial V1C3B consumer = selected

skynetvs-nlu-training-minimal-v1
  roots = requirements-train.txt
  composition = standalone minimal
  inherits base = false
  initial acquisition = blocked

skynetvs-python-base-whisper-v1
  roots = requirements.txt + requirements-whisper.txt
  composition = base plus optional overlay
  overlay standalone = false
  default enabled = false
  initial acquisition = blocked
```

This replaces the earlier provisional assumption that all three declaration
files should automatically become three independent closures.

The declaration files are root authority. Import topology may validate the
profile graph but may not silently remove `pydub`, inject
`faster-whisper`, union profiles or infer inheritance.

V1C3A is internally ordered as:

```text
V1C3A0 profile/target contract
V1C3A1 candidate resolver/acquisition
V1C3A2 offline artifact/metadata/graph verification
V1C3A3 manual immutable closure acceptance
```

Only V1C3A0 is open for implementation. It performs no network access and
accepts no wheel, metadata response or resolver output.

Exact V1C3A0 mutable scope:

```text
modules/developer/developer_task_execution_dependency_profile.py
modules/developer/developer_task_execution_dependency_profile_policy.py
tools/eval_developer_task_execution_dependency_profile.py
tools/eval_developer_task_execution_dependency_profile_windows.py
tools/pipeline.py
tools/eval_package_boundaries.py
```

Current prohibitions:

```text
do not resolve dependencies
do not download metadata or wheels
do not install dependencies
do not import or execute candidate dependencies
do not launch Sandbox
do not create reusable leases
do not create permanent V1C3A acquisition evidence
do not expand acquisition beyond requirements.txt
```

### Next Exact Action

Implement and verify the non-network V1C3A0 profile and target contract.
Stop before V1C3A1.

## V1C3A0 implementation closure — verified and pushed

V1C3A0 is complete as a non-network, non-authorizing profile/target contract.

Implementation:

```text
commit:
b7bd0b9ad449b0f10def37e27d9f93f272e996a1

parent:
3ef32e30a97ad56e67c851ba562f689f5e9ea864

tree:
cdf7591e242696a9976362801c6f200f26c71ded

subject:
feat: add V1C3A0 dependency profile target contract
```

Exact changed scope:

```text
A  modules/developer/developer_task_execution_dependency_profile.py
A  modules/developer/developer_task_execution_dependency_profile_policy.py
A  tools/eval_developer_task_execution_dependency_profile.py
A  tools/eval_developer_task_execution_dependency_profile_windows.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

Verified policy identity:

```text
policy:
skynetvs-v1c3a0-dependency-profile-target-contract-v1

fingerprint:
370e5d2c246be240b9d1a47fdebcc1250302155ea0e6128b6580079d5691748a
```

The final contract fixes:

```text
initial profile:
skynetvs-python-base-v1

declaration:
requirements.txt

target:
CPython 3.13.15 / Windows / AMD64

requested extras:
[]
```

The training profile and optional Whisper overlay remain topology-bound but are
not selected by the initial V1C3A/V1C3B scope.

The source review added two explicit fail-closed protections before commit:

1. pinned V1C0B1 policy ID/fingerprint/parser lineage must match the imported
   current V1C0B1 constants;
2. committed declaration identity independently requires Git mode `100644`,
   object type `blob`, pinned object ID, exact bytes and SHA-256.

Regression coverage confirms both lineage drift and Git tree-mode drift fail
closed.

Evidence:

```text
hardening:
SkynetVS_V1C3A0_HardeningRepair_20260902_141550.txt
SHA256 bd6dfc7eb6c27b0d9dbd18ebfea6be9c1732438fefad99e89bc6504f34d775fc

final preflight:
SkynetVS_V1C3A0_FinalCommitPreflight_20260902_162359.json
SHA256 e76c98bbd6e2de45cd437ace8d83c7b5d4a501f2b21767bdd1a2a85df45220fc

commit/push:
SkynetVS_V1C3A0_FinalCommitPush_20260902_173836_ed90fd3595c6.json
SHA256 b7ec7432d8b4ef08400b2df2463dd96742da0a8cee14906b61046e2fdf0e1343

docs source:
SkynetVS_V1C3A0_DocsClosureSource_20260902_174838.json
SHA256 ca74c4b18d11884d3cb0d48ccc8ef2c80d35b5d92fa0b67842ec14616855bdd3
```

Verification summary:

```text
generic V1C3A0 evaluator      10 / 10 PASS
Windows host-only smoke        1 / 1  PASS
package boundaries            28 / 28 PASS
dedicated pre-commit flow      PASS
dedicated post-commit flow     PASS
full pipeline hardening check  PASS

HEAD:
b7bd0b9ad449b0f10def37e27d9f93f272e996a1

origin/main:
b7bd0b9ad449b0f10def37e27d9f93f272e996a1

remote refs/heads/main:
b7bd0b9ad449b0f10def37e27d9f93f272e996a1

repository/index:
clean
```

No dependency authority was opened:

```text
dependency network            false
artifact download             false
dependency install            false
dependency execution          false
Sandbox                       false
candidate interpreter         false
reusable lease                false
execution authorization       false
```

Current state:

```text
RC041   PASSED / CONSUMED / IMMUTABLE / CLOSED
V1C2    COMPLETE
RC042   ARCHITECTURE LOCK RECORDED
V1C3A0  IMPLEMENTED / VERIFIED / PUSHED / NON-AUTHORIZING
V1C3A1  NOT OPEN
```

The final V1C3A0 commit/push launcher is consumed and must not be rerun.

### Next Exact Action

Perform a read-only V1C3A1 architecture/security audit. Do not select or run a
resolver, access PyPI, download metadata or wheels, install dependencies,
execute a candidate dependency, launch Sandbox or open any reusable capability
until the V1C3A1 resolver/acquisition contract is reviewed.

## Roadmap Change 043 — V1C3A1 architecture/security lock

RC043 records the target-matched resolver and mediated acquisition contract
without opening resolver or network authority.

```text
baseline:
aa01155fb5b015faabc4aaf297c6cd7906334d9d

tree:
a2b8a22df5015976e269e006c9a33dfb5d60512d

decision:
skynetvs-v1c3a1-target-matched-resolver-mediated-acquisition-lock-v1

fingerprint:
65649ffa282db0b625c58f687adb16e1b41d5f5ada679985ee7dde4d77e61d73
```

Evidence:

```text
architecture source
2b253ba8792f62eb96ef7568584b1baeb8a6b72c67340fd2c4aa325e7cbe804d

pip 25.3 identity
0dbfa21e4ed2a5f23394c74a15008bbe5e54fcaec1f133ac44fce4c3719f304a

marker semantics
df57117b18af5a0fa0fc0962741ff3af3e90dc5816553f7179a1130f1726af26
```

The measured project `.venv` pip 25.3 runs under CPython 3.12.10 and is
rejected as the target resolver. Exact local source proves its root and
transitive PEP 508 markers use the running interpreter environment; the fixed
target is CPython 3.13.15. `--python-version` does not repair this boundary.
There is no host-3.12 fallback.

The no-extras scope is graph-wide. Non-empty extras on any root or transitive
requirement fail closed; `extra` markers are evaluated only with the empty value.

The fixed target does not pin `platform_release` or `platform_version`, even
though pip's running marker environment contains both. RC043 therefore rejects
root or transitive markers that reference either value, `dependency_groups` or
any unknown/unsupported marker variable. Bound marker values must match the
fixed target; Core Metadata may additionally use only the empty `extra` for the
initial no-extras profile.

V1C3A1 is internally sequenced without expanding the top-level roadmap:

```text
V1C3A1A  non-network policy/report contract
V1C3A1B  target-matched resolver capsule bootstrap and offline verification
V1C3A1C  bounded mediated candidate acquisition
```

A future resolver capsule must be a fresh external CPython 3.13.15 Windows
AMD64 copy, separate from `.venv`, the repository and stable V1B4. The exact
CPython source ZIP remains:

```text
bytes   11009825
SHA256  d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf
```

The measured project `.venv` `pip==25.3` identity is rejection/observation
evidence only. RC043 selects the `pip` family but no exact resolver-tool
version. Before first use, a separately accepted exact version requires
authoritative pip Simple metadata/wheel bytes, offline wheel/RECORD and tree
verification, deterministic non-executing extraction, exact capsule/entry
point/argv/environment/output identities and a proven OS egress guard.

The resolver has no direct external network. It can use only a numeric
loopback project broker. Raw authoritative Simple bytes are retained. A
canonical logical resolver view and stable route-map projection are closure
material; the actually served JSON, port/token and raw resolver report are
attempt-specific run-envelope evidence only. A canonical proposal projection
maps every resolver-report URL back to source authority and removes unpinned or
attempt-local fields before closure hashing.

Resolver, broker and archive-metadata parsing workers require independently
proven restricted-token, no-child-process, no-inherited-handle, job-object and
attempt-root-only write confinement before first use. Resolver and broker also
require separate OS default-deny egress proofs. Exact committed code/import and
interpreter identities are required for every active component. RC043 does not
choose the Windows mechanisms.

The broker is the sole external actor and may access only exact allowlisted
HTTPS origins:

```text
pypi.org:443
files.pythonhosted.org:443
```

Initial provenance is limited to `pypi.org:443`; any other secure provenance
origin requires a separate roadmap review. Redirects and retries are zero.
Proxy/index/credential/custom-CA/client-certificate/netrc/keyring/user-config
fallback is forbidden.

Authority remains:

```text
PyPI Simple API JSON v1, major 1, minor >= 4
raw required project keys: meta/name/files/versions
optional project-status: explicit absent/present evidence
selection requires filename/url/hashes/size and hashes.sha256
optional file fields: explicit absent/present evidence
strict duplicate-key/UTF-8/API-version/name/bounds validation
graph-wide non-empty extras rejected
exact files.pythonhosted.org wheel URL from verified Simple response
external Core Metadata when advertised
otherwise bounded exact-wheel METADATA candidate, reverified in V1C3A2
exact provenance bytes when present
declared and actual wheel SHA-256 equality
```

Resolver output is proposal-only. V1C3A1 candidate evidence is non-executable
and cannot enter V1C3B before V1C3A2 offline verification and V1C3A3 manual
immutable acceptance. Volatile DNS/TLS/peer/header/timing evidence is bound in
the run envelope but excluded from the deterministic closure fingerprint;
selection-critical URLs, status/media/encoding and raw body hashes remain in
the closure.

Active attempts are serial, bounded and create-once. The fixed limits include
128 projects/nodes, 1024 graph edges, 2048 upstream and 8192 loopback requests,
16 MiB per Simple response, 4 MiB per Core Metadata/provenance object, 256 MiB
per wheel, 2 GiB total wheel bytes, bounded JSON/Core Metadata/marker parsing,
16384 archive entries and a 100:1 candidate-METADATA ratio. Limit exhaustion
fails closed.

### Final lineage and resolver-tool gates

```text
V1C0B2
skynetvs-v1c0b2-external-source-authority-lock-v1
80da155e8de0ce9f6d17565541173b701c2d5c9c8a8c13f1fcab9a57dbdb3d5e

V1C3A0
skynetvs-v1c3a0-dependency-profile-target-contract-v1
370e5d2c246be240b9d1a47fdebcc1250302155ea0e6128b6580079d5691748a
policy blob c383035a4363b0943aa25c53ac1ee3b0757e930b
```

V1C3A1A must fail closed on missing, duplicate or changed V1C0B2 identity; on
current/imported V1C3A0 policy drift; on dependency-profile report lineage
drift; or when copied profile/declaration/extras/target values differ from the
bound V1C3A0 contract.

RC043 selects the pip family but no executable version. Project `.venv` pip
25.3 remains rejected observation evidence. An exact version may be selected
only in V1C3A1B after a fresh release/security review and exact acquired-wheel
source audit; automatic latest/range/fallback semantics are forbidden.

Before any pip import or execution, the resolver-tool wheel requires exact
`METADATA`/`WHEEL`/`RECORD` verification, complete SHA-256 RECORD-to-archive
set equality, deterministic extraction, valid SPDX `License-Expression`, every
`License-File` byte and a create-once manual tool-acceptance result. The wheel
must be pure `py3-none-any`, dependency-free and target-compatible; failed or
partial acceptance cannot be promoted.

Current transition target:

```text
RC043   ARCHITECTURE LOCK RECORDED
V1C3A1  CURRENT / V1C3A1A NON-NETWORK CONTRACT ONLY
         ACTIVE ACQUISITION BLOCKED

resolver selected          false
resolver executed          false
network authority opened   false
metadata/wheel download    false
dependency install/execute false
Sandbox                    false
reusable lease             false
execution authorization    false
```

Exact V1C3A1A mutable scope:

```text
modules/developer/developer_task_execution_dependency_acquisition.py
modules/developer/developer_task_execution_dependency_acquisition_policy.py
tools/eval_developer_task_execution_dependency_acquisition.py
tools/eval_developer_task_execution_dependency_acquisition_windows.py
tools/pipeline.py
tools/eval_package_boundaries.py
```

### Next Exact Action

Implement only the non-network V1C3A1A policy/report contract. No resolver-tool
download, capsule construction, egress guard, broker network, resolver
execution, dependency metadata/wheel acquisition, installation or execution.

## V1C3A1A implementation closure — 2026-09-07

This append-only operational closure supersedes the earlier RC043
`Implement only V1C3A1A` next-action text without rewriting historical RC043
evidence.

Exact implementation baseline:

```text
HEAD / origin/main / remote main:
875669d81caf7c91347fe6b532926803aca3153c

parent:
8bdce8742f6114b6b203066ecb9abb603ad1e798

tree:
f522f22c09a1679d191c2679021439c1cb03e769

subject:
feat: add V1C3A1A non-network dependency acquisition contract
```

Contract identity:

```text
policy ID:
skynetvs-v1c3a1a-non-network-dependency-acquisition-contract-v1

policy fingerprint:
5ed6c7bd3e1c3b180fc7344fb5078d3279ad9b597553fe25bf75cd5d45964dac

RC043:
skynetvs-v1c3a1-target-matched-resolver-mediated-acquisition-lock-v1
65649ffa282db0b625c58f687adb16e1b41d5f5ada679985ee7dde4d77e61d73
```

The committed implementation is the exact six-file V1C3A1A scope. The final
dedicated flow passed both before and after commit, the preflighted future tree
equals the committed tree, the implementation was pushed normally to
`origin/main`, and the repository/index were clean after push.

Exact primary closure evidence:

```text
candidate V2.3:
4a1b8b5678324d6502ee3945387f9547d1fcabc408dbc14c4e8ff87fd7b051b0

final implementation preflight:
944121a2ae0ef4f6f49aecf449941e9b24ca7c49ba0abbae102f65b6cc28ed23

final commit/push result:
276ba53d163552165b7aeef9ced3c5b09f24c67851f360383784d434ff7b4897

docs-closure exact-source audit:
26bde49177841742837d0ad0ac860942a60e597c34aafa9690297c51673a30bd
```

Operational safety state:

```text
source_authority_bound          true
source_authority_selected       false
resolver_selected               false
resolver_executed               false
resolver_tool_version_selected  false
resolver_tool_imported          false
dependency_network_used         false
metadata_downloaded             false
wheel_downloaded                false
dependency_installed            false
dependency_executed             false
Sandbox                         false
candidate_interpreter_executed  false
reusable_lease_issued           false
execution_authorized            false
active_acquisition              BLOCKED
```

The only network use in the implementation closure was the normal GitHub
repository push. It did not open dependency-source, resolver, broker or runtime
network authority.

Current operational state after this docs closure:

```text
RC041    PASSED / CONSUMED / IMMUTABLE / CLOSED
V1C2     COMPLETE

RC042    ARCHITECTURE LOCK RECORDED
V1C3A0   IMPLEMENTED / VERIFIED / PUSHED / DOCS CLOSED / NON-AUTHORIZING

RC043    ARCHITECTURE LOCK RECORDED
V1C3A1A  IMPLEMENTED / VERIFIED / PUSHED / DOCS CLOSED
          NON-NETWORK / NON-AUTHORIZING

V1C3A1B  NOT OPEN
V1C3A1C  NOT OPEN
ACTIVE ACQUISITION BLOCKED
```

### Next Exact Action

Run a fresh READ-ONLY / HOST-ONLY V1C3A1B transition/source audit. It must
review the exact committed V1C3A1A policy and implementation together with
RC043's resolver-tool wheel/RECORD/license/source-security acceptance,
target-matched capsule, broker, OS egress and worker-confinement requirements.

Until that audit is reviewed:

```text
exact pip version selection     FORBIDDEN
PyPI access                     FORBIDDEN
resolver-tool metadata/wheel    FORBIDDEN
resolver capsule construction   FORBIDDEN
resolver import/execution       FORBIDDEN
broker external network         FORBIDDEN
egress-guard activation         FORBIDDEN
dependency acquisition          FORBIDDEN
V1C3A1B                         NOT OPEN
```

## Оперативная сверка 2026-09-22 — актуальное состояние native prerequisites

Этот раздел восстанавливает оперативную точку handoff после документационного
разрыва, возникшего после V1C3A1A closure. Он не создаёт RC044 и не выдаёт
нового runtime/acquisition authority.

### Актуальный checkpoint

Read-only capture `6f0121a9ec93499c8901aa931547ae9e` подтвердил:

```text
branch           main
HEAD             b4783b056ab7c8de4023de8147f31511be1d41d3
tree             059a07fd8a3be8707e805c655b387c4db8f463cc
parent           26126296aed8179d27c3b4d37f99f2add62f9891
status           clean
staging          empty
index bytes      50590
index SHA-256    7fca409a7870e262339139e477fed58850eaa2f329fda192b1ee63603321d235
repository write false
network          false
tests            false
Sandbox          false
real SCM         false
Guard            false
```

Capture локальный: fresh remote query не выполнялся. Последнее проверенное
`origin/main == HEAD` остаётся из
`SkynetVS_SCM01ControllerCommitPushV1_ca32993387e746b6ac2c1dc9dc2fe865.json`.

Шесть architecture docs и 148 последующих source/doc/support files сверены с
committed objects. Три historical Sandbox docs отличаются от review copies
только LF/CRLF; их текст совпадает и они не требуют переписывания.

### Восстановленная причинная линия

V1C3A1A закрыл non-network contract, после чего V1C3A1B source audit подтвердил,
что RC043 требует отдельного host confinement / OS egress prerequisite.
Измеренный ordinary-user WFP write path получил `ACCESS_DENIED`, после чего
проектирование продолжилось через узкий bootstrap-first `SkynetVSGuard`
control plane, P00 trusted-start/epoch basis, SP01/LP01 start/loader profiles,
Guard callback boundary и SCM01.

Это продолжение security prerequisites RC043, а не открытие resolver/network
authority. `V1C3A1B` и `V1C3A1C` по-прежнему не открыты.

Repository lineage после docs closure:

```text
2194e7a  docs: close V1C3A1A non-network acquisition contract
20c2af9  chore: add trusted host diagnostic source baseline
ad9aea1  chore: add installed root reader source baseline
8910de1  chore: add live root epoch bridge source baseline
1eb699b  chore: add p00 enrollment expectation source baseline
b77f560  chore: add guard start candidate source baselines
50c9f07  chore: add guard service refusal source baseline
811431d  chore: add service callback harness v2 source baseline
2612629  docs: record service callback harness r05 evidence
b4783b0  chore: add scm01 controller source baseline
```

### Acceptance boundaries

```text
RC041 / V1C2       historical closure preserved
RC043              architecture lock preserved
V1C3A1A            IMPLEMENTED / VERIFIED / DOCS CLOSED
V1C3A1B            NOT OPEN
V1C3A1C            NOT OPEN
RC044              NOT CREATED

B02                NOT_ACCEPTED
P00                NOT_ACCEPTED
P01                NOT_IMPLEMENTED
active acquisition BLOCKED
native factory      CLOSED

R01                ERROR / immutable
R02 / R03          REVIEW_REQUIRED / immutable
R04                DIAGNOSTIC_ONLY
R05                18/18 SYNTHETIC_PROVIDER_ONLY / consumed
SCM01               source/build baseline only
SCM01 runtime       CLOSED
```

R05 не является real-SCM evidence. SCM01 source/build PASS не выполнял
controller runtime, `CreateServiceW`, `StartServiceW`, Guard, ACL/enrollment или
production factory.

### Windows Sandbox

Windows Sandbox уже существует в проекте как verified
`traditional_wsb_logoncommand_v1`; спрашивать о наличии новой VM с нуля не
нужно. Historical lifecycle/signed-boundary/trusted-runtime evidence сохраняется.

Для SCM01 ещё требуется отдельная compatibility decision. Текущий SCM01
contract запрещает writable host shares during test, а старый Sandbox output
mapping writable. Нельзя скрыто перенести прежний `.wsb` transport в SCM01 или
ослабить contract только ради запуска.

### Next Exact Action

Подготовить и отдельно review-нуть SCM01-on-Windows-Sandbox compatibility
contract: guest-local image/staging, evidence export, guest retirement /
external stop-reset, absence of host secrets, one-shot service-object semantics
и точные границы writable mappings.

До этого:

```text
CreateService/StartService/DeleteService  NOT AUTHORIZED
Guard real SCM execution                  NOT AUTHORIZED
dependency acquisition                    BLOCKED
RC044                                     NOT CREATED
```

## SCM01-WSB01 — оперативная фиксация согласования #98

**2026-09-22: DESIGN ACCEPTED / DOCS ONLY / NO RUNTIME AUTHORITY.**
Этот блок заменяет прежний Next Exact Action о необходимости согласовать
SCM01/Sandbox compatibility в части лабораторного дизайна. Исторические
контракты, статусы ошибок и consumed evidence остаются неизменными.

### Baseline этого решения

```text
a05b28b95cab6eacb4b92ef8079206ee6939873b
parent: b4783b056ab7c8de4023de8147f31511be1d41d3
tree:   df0cfd69969d97f7f5ed66902e5cc079672a02af
subject: docs: reconcile native prerequisite roadmap
```

Это принятая точка до текущего изменения документации, не hash будущего
commit. Основание: commit/push report
`SkynetVS_DocsReconciliation95CommitPushV1_b247c7015d6f4585a0ddfa823332258c.json`.

### Что именно принято

Пользователь #98 принял лабораторный SCM01-WSB01 для **неизменного Guard V3**:
одна свежая выделенная недоверенная writable Output-папка, без заявления о
защите хостового диска от злонамеренного гостя. Разрешена только docs-only
фиксация. Sandbox, guest bootstrap, реальный SCM, Guard, install/ACL/enrollment
этим согласованием не разрешены.

Windows Sandbox сохраняется первым существующим кандидатом стенда:
`traditional_wsb_logoncommand_v1`. Input и Control read-only для гостя;
Output — единственная guest-writable host mapping, недоверенная с начала
сессии. Repository, `.git`, host `.venv`, весь Downloads, credentials и
production enrollment не отображаются в гостя; сеть/clipboard выключены.

Это **явное исключение** из старого `host_writeable_shares = "none during test"`,
не эквивалент запрета и не изменение старого
`native/scm01_controller_v1/SCM01_CONTRACT.json`. V1 entrypoint/native
constructor остаются CLOSED; bypass через monkeypatch/test backend/JSON
`approved=true` запрещён. Guard не пересобирается:

```text
Guard.exe: 882176 bytes
SHA-256: 66736793b396c1c5682ce149df199db34d63499c916d299aa6106f11b3f68fdb
```

Будущий адаптер должен обеспечить guest-local delivery, exact hashes,
host-consumed marker до guest launch, ephemeral key и pin ready до service
mutation, one-shot Control authorization, signed raw journal/terminal и
повторную host-проверку после normal session retirement. Это требования к
будущей реализации, а не измеренный результат.

Подпись, ограничения чтения и allowlist не ограничивают объём записей гостя
в Output. Защита от disk-fill/DoS злонамеренного guest-writer не заявляется.
Числовые parser/размерные пределы и 300 s host deadline из #97 остаются
предварительными до отдельной фиксации; они не являются runtime grant.

Служба сохраняет `SkynetVSGuard`, `NT SERVICE\SkynetVSGuard`, OWN_PROCESS,
DEMAND_START; будущий grant может предусматривать не более одной попытки
Create/Start/Delete. Сейчас ни одна попытка не разрешена. Existing service
не принимается под управление; LocalSystem fallback и automatic ACL repair
нет. Ожидаемый tuple `16 / 1 / 0 / 1066 / 78 / 0 / 0` ещё не измерен на SCM.

STOPPED/удаление записи не доказывают process exit или guest retirement.
Внешний stop/session binding ещё требует свежей проверки, не зависит от
зависшего guest RPC и не подменяется transient launcher PID. Forced cleanup
не даёт PASS; UNKNOWN retirement закрывает дальнейшие запуски.

### Текущие границы

```text
SCM01-WSB01 design             ACCEPTED FOR LAB / DOCS ONLY
SCM01-WSB01 adapter            NOT IMPLEMENTED
SCM01 runtime gate            CLOSED
Sandbox / guest bootstrap     NOT AUTHORIZED
real SCM / Guard              NOT AUTHORIZED
install / ACL / enrollment    NOT AUTHORIZED
B02 / P00                     NOT_ACCEPTED
P01                           NOT_IMPLEMENTED
R05                           18/18 SYNTHETIC_PROVIDER_ONLY / historical
V1C3A1B / V1C3A1C             NOT OPEN
RC044                         NOT CREATED
active acquisition            BLOCKED
native factory                CLOSED
```

### Next Exact Action

Завершить эту docs-only фиксацию проверенным отдельным commit/push. После
closure определить exact source-only scope нового versioned Sandbox adapter
и отдельно согласовать его реализацию/проверки; не открывать старый V1.

Дальнейшие active шаги разделены: сначала отдельно разрешённая benign Sandbox
integration без Guard/SCM, затем review evidence, и только после этого —
отдельный one-shot real-SCM refusal grant. Документационное согласование не
разрешает даже benign launch, scheduled bootstrap task или guest interpreter.

Подробное согласованное решение — раздел SCM01-WSB01 / сообщение #98 в
`SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`; основание — исторический разбор #97 и
согласование пользователя #98. Старые Sandbox attestations не переписываются.

## Source107 V2 — согласование source-only переноса #108

**2026-09-22: условное разрешение source landing получено; runtime CLOSED.**
Этот раздел заменяет прежний Next Exact Action в части выбора/согласования source
scope. Он не изменяет исторические статусы и не удостоверяет успех apply сам по себе.

### Подтверждённая исходная точка

```text
HEAD   a666c5a1f9c2bb53f75cf36715913f419f1c6ca7
tree   4119691020466bdda62594f852707274345d5ce2
parent a05b28b95cab6eacb4b92ef8079206ee6939873b
branch main
```

Local clean/staging-empty snapshot: SourceClosure103
`4a9a815c519746a8940d33565e40b96a`; последнее remote equality: Docs100
`5ffcaebaa53f450c8b131a9ce900644c`. Это baseline до нового source landing, не
выдуманный future commit и не новое измерение пользовательского компьютера.

### Разрешение и исходники

#106 разрешил scope #105: подготовку закрытого core и offline-тесты вне repository.
Review #107 заменил Source106 V1 как кандидат на **Source107 V2**, исправив
немедленный sticky failure после failure terminal и учёт позднего retirement
без отмены deadline failure. Все 22 файла остаются в одном новом каталоге:

```text
native/scm01_wsb01_adapter_v1/
SkynetVS_SCM01_WSB01_ClosedCore107_Source_V2.zip
52915 bytes
80abd6b7276667175129c9e0ee1d3f71af82343d67a89d8e0f4b3083f65f22be
```

Пользователь #108 разрешил добавление этих 22 файлов и обновление двух canonical
docs **после отдельного preflight**. Git add/commit/push и любые runtime-полномочия
не разрешены. Повторного согласования этого source-only scope не требуется.

Source107 metadata не редактируется при переносе: исторические поля
`NOT_APPLIED` / `repository_apply_authorized=false` описывают момент подготовки.
Разрешение #108 и фактический apply report — отдельные, более поздние records.
До такого отчёта наличие candidate package не является доказательством применения.

### Проверки и их предел

Сохранённый Review107 сообщает **65/65 дважды**: исходная копия и final ZIP;
44 scope105 + 21 regression case; 288 wrong-order и 52 late-retirement checks.
Среда — CPython 3.13.5 / Linux. Python 3.12 AST only; Windows/Python3.12 execution
пока отсутствует. В source-landing preflight новые core-тесты и старые evaluators
не запускаются.

Core — модель, не runtime adapter. Все результаты `OFFLINE_MODEL`,
`runtime_authorized=false`, `crypto_verified=false`; entrypoint CLOSED/92.
`MODEL_FAILURE_TRACE_VALID` — корректно описанная неудача, не успех.
Нет native provider, effect executor, .wsb/.ps1, CNG, guest bootstrap или SCM calls.

### Неизменные решения и статусы

Windows Sandbox уже выбран: `traditional_wsb_logoncommand_v1`. Не выбирать новую VM
с нуля. SCM01-WSB01 с одной недоверенной writable Output уже согласован; защита диска
от malicious guest-writer не заявляется. Старые SCM01/Guard/source pins не менять,
test-only backend не использовать для обхода закрытого gate.

```text
Source scope #105 / source landing #108  APPROVED (landing after preflight)
Source107 V2                            corrected / offline validated
User source apply                      requires separate successful report
Commit/push                             NOT AUTHORIZED by #108
Sandbox / guest bootstrap               NOT AUTHORIZED
real SCM / Guard / install              NOT AUTHORIZED
ACL / enrollment                        NOT AUTHORIZED
SCM01 runtime                           CLOSED
B02 / P00                               NOT_ACCEPTED
P01                                     NOT_IMPLEMENTED
V1C3A1B / V1C3A1C                       NOT OPEN
RC044                                   NOT CREATED
R05                                     SYNTHETIC_PROVIDER_ONLY / consumed
acquisition                             BLOCKED
native factory                          CLOSED
```

### Next Exact Action

Выполнить отдельный read-only preflight для Source107 V2 + этих двух docs.
После PASS — отдельный apply-only с 22 additions и 2 modifications, без staging.
Затем проверить apply report и обновить Handoff достигнутым состоянием. Не
запрашивать повторно разрешение #108; не выдавать commit/push или runtime команды
без отдельного согласования. Не повторять SourceAudit102/Closure103 и Docs100.

Windows offline suite, native/platform integration, session/stop proof, guest runtime,
CNG и persistent host ledger пока не закрыты. Benign integration без Guard/SCM и
real-SCM эксперимент остаются двумя отдельными будущими разрешениями.

## Source-only дополнение #116 — BEN01: source-кандидат подготовлен, приёмка открыта

Архитектура SCM01-WSB01-BEN01 и scope #115 согласованы пользователем в #116.
Подготовлены 32 новых файла отдельно от репозитория. В этом сообщении нет разрешения
на применение в Git, native smoke, Sandbox, guest bootstrap, SCM/Guard, install,
изменение ACL/enrollment или runtime grant. Public entrypoints остаются CLOSED / 92.

Выполнены 64 offline/fake/static-case метода плана #115 и 9 regression-методов:
73/73 на подготовленных байтах и 73/73 из окончательного ZIP, CPython 3.13.5 / Linux.
Windows native ABI, PowerShell parser и guest bootstrap не исполнялись.
Существующий WindowsOffline113 относится к прежнему closed core, НЕ к Source116.

Кандидат НЕ закрывает весь implementation scope: B116-01 — admitted native IPC
peer-to-receipt/context assembly; B116-02 — проверенный guest capsule loader/entry routing.
R116-03 — review точной supervisor-incarnation привязки вместо OS boot GUID.
Нельзя удалить gates, заменить домен fake receipt или принять JSON-флаг за разрешение.

Последний подтверждённый HEAD остаётся 0fc3e19a6fe8f59f3b71b9d682630cfb1b7c0427,
tree 206c105decec0190f2e29a5090999389f79e28c3. Source116 в Git НЕ применён.
Следующий шаг: review/достройка отмеченных source-стыков в рамках уже согласованного
source-only scope; только потом отдельно согласованное source/docs landing.
Sandbox backend traditional_wsb_logoncommand_v1 и одна недоверенная Output mapping
не переоткрываются. B02/P00 NOT_ACCEPTED, P01 NOT_IMPLEMENTED, RC044 NOT CREATED,
V1C3A1B/V1C3A1C NOT OPEN, acquisition BLOCKED; native/runtime gate CLOSED.


## Source117 V2 — BEN01 source-only review, 2026-09-23

Архитектура/scope #115 приняты пользователем в #116. По разрешению подготовки вне Git
создан новый 32-file Source117 V2: 13 файлов изменены, 19 сохранены относительно Source116.
108 offline/fake/static methods (64 baseline + REG01–REG44) прошли на prepared source
и на final ZIP; 0 failures/errors/skips. Среда Linux/CPython3.13.5. Guest/PS/native
код не импортировался/не выполнялся; audit guarded suite не наблюдал writes/subprocess/
sockets/ctypes.dlopen. Это не Windows/guest/native acceptance.

Добавлены gated own-worker channel/pump/context source и guest eight-member byte loader.
Исправлены fragmented-frame handling, раннее retirement при delayed terminal IPC,
попытка publication после позднего READY и возврат failure при ошибке persistence.
Native first-process worker ingress и bootstrap-to-loader/permit handoff всё ещё
REVIEW REQUIRED; scope acceptance не закрыт. Live issuer отсутствует намеренно.

32 new source и этот документальный кандидат НЕ применены. Canonical user HEAD
остаётся 0fc3e19a6fe8f59f3b71b9d682630cfb1b7c0427 по последним имеющимся evidence.
Source111/WindowsOffline113 относятся к старому closed core и не повторяются.
B02/P00 NOT_ACCEPTED, P01 NOT_IMPLEMENTED, V1C3A1B/C NOT OPEN, RC044 NOT CREATED,
acquisition BLOCKED; Sandbox/guest bootstrap/SCM/Guard/install/ACL/enrollment/native smoke
и Git apply не разрешены. Public gates CLOSED/92.

Следующий exact action: source review новой assembly и завершение first-process
entry-admission по уже разрешённому source-only scope. Никакого нового запуска.


## BEN01 source review #118 — first-process routes prepared; runtime remains CLOSED

**Дата:** 2026-09-23. **Статус записи:** неприменённый documentation candidate.

В рамках разрешения #116 на 32 source-файла вне пользовательского Git подготовлен
Source118 V3 в `native/scm01_wsb01_benign_v1/`. Относительно Source117 V2 изменены
10 файлов, 22 побайтово сохранены. Source117 и предыдущие evidence сохранены.

Worker first-process source теперь описывает фиксированный INIT envelope, bounded
inherited-pipe чтение, проверку pinned byte graph и собственной ProcessIdentity,
exact INIT_ACK до Sandbox launch и отдельный BIND (sequence 1). Guest route описывает
четыре фиксированных startup args, чтение request/capsule/bootstrap hashes, retained
runtime inventory, eight-member byte graph и явный loader_plan отдельно от permit.
INIT/ACK, JSON, CLI hashes и data plans НЕ являются authority.

Public host/worker/guest/PowerShell gates остаются CLOSED/92. Оба process-local issuer
отсутствуют намеренно; их закрытые барьеры проверяются до I/O. Native/guest вызовы,
PowerShell parser, actual byte-loader и pipe pump не выполнялись. Нельзя заменить
admission удалением exit92, передачей approved=true или переносом Python permit
между процессами как JSON.

Prepared-source и final-ZIP guarded suite дали по 140/140: 64 baseline methods +
76 regression methods, включая REG45–REG76 (32 новых). Failures/errors/skipped=0;
154 subtests; 90 wrong-order и 2000 mutation probes на каждый запуск. Из mutations
1945 rejected, 55 schema-valid, 0 unexpected; schema-valid != evidence acceptance.
Предыдущие 108 test methods сохранены структурно (AST comparison) и входят в 140;
отдельного нового запуска старого Source117 suite на этом шаге не заявляется.

Проверены 32 source identities до/после и 98 сохранённых reference bytes. Среда:
Linux / CPython 3.13.5; Python 3.12 только AST feature_version, не исполнение нового
кандидата на Windows. Audit counts writes/fs_mutation/subprocess/socket/ctypes.dlopen=0.
Audit hook — контроль доверенной test phase, не OS isolation against hostile code.

B116-01/B116-02: FIRST-PROCESS SOURCE ROUTES PREPARED / SOURCE REVIEW REQUIRED.
Scope acceptance остаётся OPEN; native/live admission не приняты. R116-03 остаётся
SUPERVISOR_PROCESS_INCARNATION_V1, не OS boot GUID или Microsoft VM identity.
Никакой новый Sandbox/SCM/Guard/production grant из этой поставки не следует.

Source ZIP: `SkynetVS_SCM01_WSB01_Benign118_Source_V3.zip`, 126638 bytes,
SHA-256 `2e2711624dcb0ad22806fbfda046eaf921d1d67773e9527c7e661a2c0fbeba9f`.

Последний подтверждённый user HEAD остаётся `0fc3e19a6fe8f59f3b71b9d682630cfb1b7c0427`,
tree `206c105decec0190f2e29a5090999389f79e28c3`. Это сохранённое наблюдение, не новая
проверка текущего ПК. Source118 и данный draft не применены, новых Git commits нет.

**Next Exact Action:** focused source review Source118 first-process data/authority
маршрутов и bounded framing. То же разрешение на source-only подготовку не запрашивать
повторно. Будущие Git landing, host-native smoke, benign Sandbox и real SCM требуют
раздельных разрешений. Не повторять consumed Source109/110/111/WindowsOffline113.


## Source119 V4 — focused first-process corrections (C02, сообщение #3)

Дата: 2026-09-23. UNAPPLIED documentation candidate, не запись в пользовательский Git.
Source119 — номер поставки после Source118; новое основное сообщение #3, не #119.

По точным Source118 bytes закрыты три конкретных source finding: eager guest helper
import (capsule/layout до возврата byte-loader), early initial run_id binding до
worker byte-loader/own-process observation с сохранённым поздним recheck, единый
source-member cap 262144 в NativeContextSpec и worker ingress. Local issuers не добавлены.

Source119 V4: 32 файла, 8 изменены, 24 сохранены. Старые 140 test method AST неизменны,
добавлены REG77–REG92. Prepared-source и final-ZIP guarded suite: по 156/156, 0/0/0,
191 subtests; 90 wrong-order и 2000 seeded mutation probes на run (1945 rejected,
55 schema-valid, 0 unexpected). Linux/CPython3.13.5, -I -S -B. Python3.12 — только
AST feature_version. Guest/PS/byte-loaders/native bodies не исполнялись; test-phase
writes/fs_mutation/subprocess/socket/ctypes.dlopen/guest-exec counts=0. Не OS sandbox.

Source118 отдельно воспроизведён 140/140 на unmodified bytes/harness в isolated/no-site
процессе. Предшествующий обычный container-run с preloaded ctypes и 1 assertion failure
сохранён как NOT_ACCEPTANCE; это не ошибка user Windows-run и не скрытый PASS.
98 saved reference bytes проверены; текущий пользовательский Git/remote не опрашивались.

Public host/worker/guest/PS gates CLOSED/92; local issuers NOT_IMPLEMENTED_BY_DESIGN;
scope acceptance OPEN по native/local admission. Full live transport не принят.
Backend traditional_wsb_logoncommand_v1, одна Output RW, retained runtime pins и
supervisor-incarnation limitations сохранены. Native wrappers, PS, wire protocol,
SOURCE_BINDINGS, старые core/SCM01/Guard/modules/tools не менялись.

Source ZIP: SkynetVS_SCM01_WSB01_Benign119_Source_V4.zip; 131662 bytes;
SHA-256 bc26906c4125f37b1f541f42c9fcd79eb57972dba14b47908d5997d3aabbf0be.
Saved user HEAD: 0fc3e19a6fe8f59f3b71b9d682630cfb1b7c0427;
tree 206c105decec0190f2e29a5090999389f79e28c3. Source/doc candidates NOT APPLIED.
Следующее действие: отдельное разрешение на read-only source/docs landing preflight;
apply/commit/push, native smoke, Sandbox/BEN01 и real SCM — раздельные grants.

## HWA01 host-only worker — Windows happy path verified; source landing prepared (C02 #22–#29)

**Дата:** 2026-09-24. **Статус:** Windows happy path VERIFIED / repository landing candidate PREPARED / runtime authority CLOSED.

Эта запись является новой reconciliation-точкой. Исторический раздел Source119 выше сохраняется
без переписывания, однако read-only capture #29 подтвердил фактический текущий Git checkpoint:

```text
branch  main
HEAD    e3bedde8f946d96b8685be2716ea523d5c0d6e31
tree    1e428aaac377edd68fdf615e90f1c4b29c0104ca
status  clean
staging empty
```

Таким образом, Source119 уже committed в пользовательском Git; формулировка `UNAPPLIED` в
исторической записи Source119 описывает состояние на момент подготовки того документа и не
является актуальным operational status. Read-only capture также подтвердил, что оба canonical
docs равны HEAD и `native/scm01_host_worker_v1/` ещё отсутствует.

### HWA01: что проверено

После NS01 host-primitives diagnostics подготовлен отдельный production host-worker core с
узким process-local admission. Он не открывает общий Source119/BEN01 native gate. Один
разрешённый Windows one-shot `783c4e94687f4335820a6f1cb88920b1` завершился
`HWA01_HOST_ONLY_FIXED_WORKER_PASS_OBSERVED`. Report: 74223 bytes, SHA-256
`7c7c680644c629e969a6f27cb5dc445fcedb7267b4dfd2d902f3aa57bb2fea68`; supervisor once:
276 bytes, SHA-256 `5747a11ebf6a5d45f5d4945bb46a1fe345a0705153bee539d5729677cb6740fb`.

Наблюдалась exact цепочка: один CPython 3.12.10 worker создан `CREATE_SUSPENDED` уже с
`PROC_THREAD_ATTRIBUTE_JOB_LIST`; до resume проверены retained identity, Job membership,
неизменность program pins, закрытие parent copies child ends и non-inheritance остальных
parent handles. `ResumeThread` вернул previous suspend count 1. Verifier проверил 6 fixed
protocol frames и воспроизвёл 17 lifecycle observations. Worker завершился exit code 0, Job
стал пустым, pending I/O=0, stderr=0; 53 resource acquisitions/53 releases, uncertain=0,
unreleased=0, forced cleanup=false. Controller завершился самостоятельно без watchdog stop.
Repository snapshot before/after совпал; network/Sandbox/guest/Git writes не выполнялись.

Граница результата сохраняется:

```text
source119_native_admission = false
runtime_authorized         = false
native_acceptance          = false
Sandbox / guest            CLOSED
arbitrary/model code       NOT AUTHORIZED
```

Это принимает exact fixed-worker **happy path**, но не все fault/crash сценарии и не BEN01.
Consumed HWA01/NS01 one-shot markers не удаляются и не переиспользуются.

### Repository landing candidate

Подготовлен `SkynetVS_HWA01_Source_V1.zip`: 55289 bytes, SHA-256
`6fe8485a954a28898e301880b156748f2000e4e31696be0d1204e96df7c506a1`. Целевой
`native/scm01_host_worker_v1/` содержит 24 файла: 14 production Python modules, 6 test files
и README/SCOPE/TEST_PLAN/SOURCE_MANIFEST. Все 14 production-файлов побайтово совпадают с
Windows-tested HWA01-C; только три test imports адаптированы к repo package layout. Repo-like
source/fake suite: 114/114 PASS, 0 failures/errors/skips; новый Windows/native run не выполнялся.
Public operator-facing entrypoint остаётся CLOSED/92.

Для штатной регрессии landing candidate добавляет `tools/eval_scm01_host_worker.py`, отдельный
pipeline flow `scm01_host_worker` и шаг того же evaluator в общем `check`. Evaluator выполняет
114 source/fake tests в четырёх isolated `-I -S -B` Python-процессах; он не выдаёт native
authority и не запускает Windows worker.
One-shot launcher остаётся evidence tooling и в production repository не переносится.

### Next Exact Action

Следующий шаг — отдельный **read-only future-tree preflight** exact landing candidate: 24 новых
файла host-worker package, новый evaluator, изменённый `tools/pipeline.py` и два canonical docs.
Preflight должен подтвердить текущий checkpoint/clean state, exact baseline bytes, отсутствие
target, Git attributes и вычислить future tree без записи в object store/index/worktree. Только
после его PASS допускается отдельный source/docs apply с staging пустым. Commit/push и новый
native/fault run остаются отдельными последующими действиями.

## HWA01 landing V1 — Windows evaluator portability correction (C02 #31–#32)

**Дата:** 2026-09-25. **Статус:** landing V1 worktree bytes WRITTEN / dedicated evaluator FAILED / repair candidate V2 PREPARED / staging EMPTY.

Первый разрешённый source/docs landing run `070b7c48fdaa4fa5abd5372007e6ccf0` записал весь
28-path candidate V1 в worktree, после чего остановился на `dedicated_eval_failed`. Failure
snapshot подтвердил неизменные HEAD `e3bedde8f946d96b8685be2716ea523d5c0d6e31`, tree
`1e428aaac377edd68fdf615e90f1c4b29c0104ca`, index/config и пустой staging. Native worker,
Sandbox/guest, network, commit/push не запускались.

Exact-source review локализовал ошибку в **двух source/fake regression assertions**, а не в
14 production HWA01 modules. `test_native_api_source.py` содержал Linux-host assumptions:
один тест требовал `sys.platform != 'win32'`, второй ожидал `fixed_child_environment` только
потому, что preparation выполнялась на non-Windows. На реальном Windows evaluator эти условия
не являются валидными тестовыми предусловиями.

V2 не меняет ни одного production HWA01 Python-файла, `tools/pipeline.py` или evaluator.
Исправление делает два negative regression tests host-portable: они временно устанавливают
non-Windows platform fixture, проверяют отказ **до ctypes/native**, затем обязательно
восстанавливают исходное значение. `README_RU.md`, `TEST_PLAN.json`, `SOURCE_MANIFEST.json`
и canonical docs обновляются для фиксации причины. Число методов остаётся 114.

Следующий шаг — read-only repair preflight над текущим dirty worktree: он обязан доказать,
что все 28 текущих путей побайтово равны V1 landing candidate, staging пуст, HEAD/index/config
не изменены, production14 V1==V2, и вычислить новый future tree V2 без записи в Git/worktree.
Только после такого PASS допустима отдельная узкая repair-запись. Runtime authority, Source119
native admission, Sandbox/guest и новый native run остаются CLOSED / NOT AUTHORIZED.
