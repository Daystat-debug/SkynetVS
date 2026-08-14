# SkynetVS Architecture Roadmap V1

**Дата фиксации:** 2026-07-30
**Последнее обновление:** 2026-08-13
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
13. **Repository isolation не равна OS sandbox.** Независимый Git-клон защищает Git-состояние проекта, но не даёт права запускать недоверенный код без отдельной process/OS isolation policy.

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

**Статус:** VERIFIED / завершён.

Результат:

- roadmap добавлен в репозиторий;
- `SKYNETVS_CURRENT_STATE.md` используется как оперативная точка handoff;
- дальнейшие этапы имеют фиксированный scope;
- любое изменение порядка оформляется как отдельное `Roadmap Change`.

---

# PHASE 1 — Developer Safety Kernel V1

Назначение: построить безопасное ядро выполнения изменений. Это ещё не автономный код-ассистент.

## 1.1 Developer Task Preflight V1

**Статус:** VERIFIED / завершён на `1035de4`.

Полностью read-only цепочка:

- V1A — Repository Gate;
- V1B — Patch Integrity Gate;
- V1C1 — Isolated Patch Index Gate;
- V1C2 — Patch Scope Policy Gate;
- V1D — Composition and Audit.

Подтверждено:

- правильный Git repository root;
- `HEAD == base_commit`;
- чистые worktree и index;
- точные immutable patch bytes и SHA-256;
- фактическая применимость patch во временном изолированном Git index;
- реальные changed paths и object modes;
- `allowed_files`, case-collision, symlink и gitlink policy;
- единый fail-closed immutable report;
- отсутствие изменений основного worktree, index и object store.

**Запрещено:** применять patch, clean/reset/stash, менять основной index или запускать команды из manifest.

## 1.2 Developer Task Isolated Repository Workspace V1

**Статус:** VERIFIED / завершён на `892e175`.

### V1A — Independent Repository Creation Gate

- отдельный локальный clone с самостоятельным `.git`;
- `--no-local`, `--no-hardlinks`, `--no-checkout`, `--no-tags`, `--single-branch`, `--depth=1`;
- shallow history boundary только от verified `base_commit`;
- detached `HEAD`;
- отсутствие remotes, branch/tag refs и alternate object directories;
- изолированные Git config, system attributes, HOME/XDG, hooks и template directory;
- deterministic line-ending and filesystem protection policy (`autocrlf=false`, LF, protectNTFS/protectHFS);
- запрет workspace parent внутри worktree/Git-dir/bare repository;
- запрет baseline symlink, gitlink, unsafe Windows paths и case-collision;
- immutable workspace evidence и canonical marker;
- доказательство неизменности source repository;
- cleanup частично созданного workspace при отказе;
- Windows `core.autocrlf=true` regression guard.

Подтверждено:

```text
4861934  feat: add isolated developer task repository workspace
workspace eval:                 39/39
developer_task_workspace flow:  completed successfully
full check:                     completed successfully
```

### V1B — Workspace Cleanup and Lifecycle Audit

Подтверждено:

```text
892e175  feat: add developer task workspace cleanup audit
workspace cleanup eval:         41/41
developer_task_workspace_cleanup flow: completed successfully
full check:                     completed successfully
```

- явный cleanup только по typed manifest, полному Preflight report, успешному Workspace report и explicit `workspace_parent`;
- non-serialized 32-byte cleanup capability в immutable workspace report;
- SHA-256 capability в canonical marker без раскрытия самого token;
- bounded binary marker read, TOCTOU, schema/hash/canonical JSON validation;
- запрет удаления source repository, task root, workspace parent, siblings и пересекающихся путей;
- no-follow проверка root, marker и всего descendant tree;
- запрет symlink, junction, reparse point и special-file traversal;
- ограниченные Windows retries, read-only handling и защита от подмены directory identity;
- идемпотентный повторный cleanup после успешного удаления;
- immutable structured cleanup report без capability;
- read-only source Git snapshots до и после cleanup;
- fault injection и доказательство неизменности source HEAD/status/refs/index/config;
- crash recovery и orphan cleanup после потери in-memory capability остаются отдельной будущей задачей.

Независимый clone создаёт **Git/repository isolation**, но не является OS sandbox. До запуска изменённого Python-кода или других проверок требуется отдельная execution isolation policy.

## Roadmap Change 001 — Linked worktree → independent repository clone

**Причина:** linked worktree имеет отдельные `HEAD` и index, но разделяет common Git directory, часть конфигурации, refs и object storage с основным repository. Для будущего developer-task runtime это недостаточная граница Git-изоляции.

**Что меняется:**

- механизм `Developer Task Isolated Workspace V1`;
- вместо `git worktree` используется независимый локальный clone с отдельным `.git`;
- этап получает уточнённое имя `Developer Task Isolated Repository Workspace V1`;
- создание и cleanup разделяются на V1A/V1B.

**Что не меняется:**

- порядок PHASE 1;
- verified Preflight V1;
- patch применяется только вне основного repository;
- checks остаются типизированными;
- promotion остаётся ручным;
- foundation-тег не переносится.

**Новая граница:** независимый clone защищает Git-состояние, но не даёт разрешения исполнять недоверенный код без будущего process/OS sandbox.

## 1.3 Developer Task Patch Apply V1

**Статус:** VERIFIED / завершён на `b8419f5`.

Подтверждено:

```text
b8419f5  feat: add verified developer task patch apply
patch apply eval:              30/30
developer_task_patch_apply:    completed successfully
full check:                    completed successfully
```

- принимаются только успешные typed-доказательства Preflight V1 и Workspace V1;
- применяются точные immutable patch bytes из Preflight V1, а не повторно прочитанный файл;
- patch применяется через Git только внутри независимого repository workspace;
- index и worktree изменяются вместе, а `HEAD` остаётся detached на `base_commit`;
- фактические changed paths, modes и resulting index повторно сравниваются с Preflight V1;
- Git принудительно привязывается к ожидаемым `--git-dir` и `--work-tree`;
- local config проверяется без includes: запрещены redirection/execution keys, критичные значения совпадают с isolated policy;
- remotes, refs, alternates, hooks boundary, config fingerprint и source repository повторно проверяются;
- при любом apply/postcondition failure выполняется bounded rollback к чистому `base_commit`;
- rollback failure делает workspace непригодным для дальнейшего использования;
- успешный результат получает canonical apply marker и non-serialized capability для Typed Check Runner;
- source mutation во время apply обнаруживается, включая Windows `core.autocrlf=true` regression;
- исполнение Python-кода, commit, merge, push и promotion в этот этап не входят.

## Roadmap Change 002 — Static Checks и Executable Checks разделены

**Причина:** independent repository clone защищает Git, но не является OS/process sandbox. Обычный host subprocess, Python isolated mode и Job Object не дают достаточной filesystem/network isolation для изменённого кода.

**Что меняется:**

```text
Typed Check Runner V1A — Static Evidence Gate
Typed Check Runner V1B — Execution Backend Capability and Evidence
Typed Check Runner V1C — Sandboxed Executable Checks
```

**Что не меняется:**

- разрешённые manifest check types;
- `git_diff_check` первый;
- full `pipeline check` последний;
- arbitrary shell и dependency installation запрещены;
- основной repository не используется для checks;
- promotion остаётся ручным.

## 1.4 Developer Task Typed Check Runner V1

### V1A — Static Evidence Gate

**Статус:** VERIFIED / завершён на `6a7b08e`.

Подтверждено:

```text
6a7b08e  feat: add developer task static check evidence gate
static check eval:               25/25
developer_task_check_static:     completed successfully
full check:                      completed successfully
runtime architecture audit:      9/9
```

- `git_diff_check` повторно подтверждает immutable Patch Apply evidence;
- trusted host-side Python compilation не импортирует и не исполняет workspace modules;
- `.pyc` и `__pycache__` не создаются;
- changed/deleted Python paths обрабатываются по verified Git facts;
- size, no-follow и TOCTOU guards работают fail-closed;
- source repository и workspace Git state/object stores не изменяются;
- `python_module` и `pipeline` остаются pending и не запускаются на host.

### V1B — Execution Backend Capability and Evidence

**Статус:** V1B1–V1B4 VERIFIED; trusted-runtime foundation COMPLETE. CURRENT — V1C0A Executable Check Inventory.

Windows Sandbox поддерживает только один активный экземпляр на пользователя, а traditional `.wsb` runtime не предоставляет идентификатор сеанса и команду `stop`. Поэтому V1B нельзя безопасно реализовать одним неделимым commit.

#### V1B1 — Canonical Backend Policy and Host Capability Gate

**Статус:** VERIFIED.

Зафиксированная code-точка:

```text
368c25f feat: add developer task execution backend host gate
```

Подтверждено на реальном Windows-хосте:

```text
Host gate unit eval:                         30/30
Real Windows host smoke:                    ok=true
execution_authorized:                       false
developer_task_execution_backend_host flow: completed successfully
full check:                                 completed successfully
git diff --check:                           exit code 0
```

Публичный API:

```python
inspect_developer_task_execution_backend_host(
) -> DeveloperTaskExecutionBackendHostReport
```

Свойства:

- не принимает manifest, workspace или patch;
- не запускает Windows Sandbox;
- использует только фиксированный `%SystemRoot%\System32\WindowsSandbox.exe`;
- проверяет Windows build, AMD64/x64 process, executable version, exact SHA-256 и отсутствие reparse/TOCTOU;
- optional feature state является advisory, если обычный пользователь не может прочитать его без elevation;
- отсутствие `wsb` CLI разрешено для `traditional_wsb_logoncommand_v1`;
- уже запущенный Sandbox или невозможность проверить process state блокирует gate;
- report всегда содержит `execution_authorized = false`.

#### V1B2 — Active Trusted Lifecycle Gate

**Статус:** VERIFIED / production gate `eb2a476`; launch-environment hardening `4ea2e0c`.

Публичный API:

```python
attest_developer_task_execution_backend_lifecycle(
    host_report: DeveloperTaskExecutionBackendHostReport,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionBackendLifecycleReport
```

Trusted active experiment от `2026-08-05` подтвердил traditional `.wsb` lifecycle:

```text
status:                       lifecycle_attested
launcher PID:                 21544
WindowsSandbox.exe observed:  yes
RemoteSession observed:       yes
result received:              13 514 ms
all Sandbox processes exited: 23 157 ms
result → exit:                9 643 ms
forced cleanup attempted:     no
execution_authorized:         false
```

Фактическая process-модель:

```text
WindowsSandbox.exe
    transient launcher; завершился вскоре после старта
        ↓
WindowsSandboxRemoteSession.exe
    удерживал активную host-сессию до guest self-shutdown
        ↓
empty known Sandbox process set
    единственное допустимое доказательство полного exit
```

Эксперимент также подтвердил strict request/result evidence, read-only input, writable output, отсутствие IPv4/IPv6 default routes, недоступность внешнего TCP для обеих семейств и успешный `shutdown.exe /s /t 5 /f`. Полный evidence зафиксирован в `SKYNETVS_WINDOWS_SANDBOX_LIFECYCLE_ATTESTATION_V1.md`.

Production V1B2 реализован и подтверждён:

```text
eb2a476  feat: add trusted Windows Sandbox lifecycle gate
4ea2e0c  fix: isolate Windows Sandbox launch environment

Lifecycle unit eval:                         39/39
Real Windows active lifecycle smoke:        3/3
developer_task_execution_backend_lifecycle: completed successfully
full check:                                 completed successfully
execution_authorized:                       false
```

Production gate:

- повторно проверяет свежесть typed V1B1 host report;
- создаёт fresh per-run input/output roots и canonical `.wsb`;
- запускает только доверенный PowerShell probe;
- подтверждает read-only input, writable output, IPv4 и IPv6 isolation;
- проверяет request/result nonce, bounded strict JSON и policy fingerprint;
- требует successful guest self-shutdown;
- требует host-observed завершение всего известного Sandbox process set в bounded grace period;
- повторно читает result после доказанного exit и отклоняет изменение bytes/hash;
- принудительное завершение использует только exact process identity как best-effort cleanup и никогда не превращает run в успешный;
- не удаляет mapped artifacts, пока отсутствие активного Sandbox не доказано;
- явно передаёт `SystemDrive` в изолированное launch environment;
- использует фиксированный trusted working directory `C:\Windows\System32`, а не project root или удаляемый lifecycle artifact root;
- возвращает `execution_authorized = false` и не запускает код из patch.
#### V1B3 — Signed Result Authenticity and Privilege Separation Gate

**Статус:** VERIFIED / V1B3A–V1B3D completed; production closure `f3f5607`.

Output mapping считается недоверенным: будущий код из patch сможет видеть и изменять его. Поэтому простого `request_id` недостаточно.

Зафиксированная модель:

```text
WDAGUtilityAccount trusted bootstrap
        ↓ starts one-time SYSTEM scheduled task
SYSTEM trusted controller
        ↓ generates ephemeral ECDSA P-256 key in memory
ready.json with public key + host nonce
        ↓ host pins exact ready bytes and writes authorize.json
standard non-admin worker created suspended
        ↓ assigned to kill-on-close Job Object
        ↓ resumed only after job membership is proven
SYSTEM controller terminates worker tree and proves worker-SID process set empty
        ↓ signs canonical terminal payload
host verifies signature and original handshake transcript after Sandbox exit
```

Security corrections fixed before implementation:

- `.wsb LogonCommand` runs under the container account, not under SYSTEM;
- SYSTEM bootstrap is a measured capability, not an assumed property;
- `CreateProcessWithLogonW` is forbidden from LocalSystem;
- worker launch uses `NetUserAdd → LogonUserW → CreateEnvironmentBlock(false) → CreateProcessAsUserW`;
- worker is created with `CREATE_SUSPENDED`, assigned to the Job Object, checked with `IsProcessInJob`, and only then resumed;
- Job Object uses `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` without breakaway flags;
- private key and signing secret are never written to mapped folders;
- worker inherits neither controller environment nor handles;
- worker has no administrative token and cannot read controller process memory under the declared threat model;
- worker Job Object is empty and the worker-SID process set is empty before terminal signing;
- unsigned, replaced, replayed, early, late or post-exit-mutated results fail closed;
- V1B3 uses only trusted benign probes and does not execute code from patch.

V1B3 is divided into:

##### V1B3A — SYSTEM Controller Bootstrap Capability Experiment

**Статус:** VERIFIED / active experiment `2026-08-06`.

Подтверждено на реальном Windows Sandbox:

```text
status:                         signed_boundary_attested
SYSTEM controller SID:          S-1-5-18
SYSTEM integrity RID:           0x4000
ECDSA P-256 key ephemeral:      true
ready → authorize handshake:    verified
standard worker administrator:  false
standard worker integrity RID:  0x2000
worker assigned before resume:  true
Job kill-on-close:              verified
worker-SID process set empty:   true
worker account deleted:         true
signature valid after exit:     true
all Sandbox processes exited:   true
execution_authorized:           false
```

Evidence: `SKYNETVS_WINDOWS_SANDBOX_SIGNED_BOUNDARY_ATTESTATION_V1.md`.

##### V1B3B — Canonical Transcript and Host Signature Verifier

**Статус:** VERIFIED / production host verifier `674dd5f`.

Подтверждено:

```text
674dd5f feat: add signed execution transcript verifier
verifier unit eval:                         45/45
Windows CNG smoke:                          3/3
real V1B3A evidence:                        signed_transcript_verified
developer_task_execution_boundary_verifier: completed successfully
full check:                                 completed successfully
execution_authorized:                       false
```

- immutable schemas for `request`, `ready`, `authorize` and signed terminal payload;
- exact-byte pinning and hash-chain validation;
- ECDSA P-256/SHA-256 verification with the public key pinned before authorization;
- replay, substitution, duplicate/unknown field and post-exit mutation guards.

##### V1B3C — Standard-User Worker Isolation Gate

**Статус:** VERIFIED / production bundle `74f543a`.

V1B3C productionized the trusted guest worker boundary without duplicating the V1B2 lifecycle or V1B3B signature verifier. The first active one-Sandbox execution of those exact bytes was performed exclusively by V1B3D.

- deterministic immutable bundle containing the trusted native helper and fixed benign worker probe;
- fresh local standard account per run with pre-creation collision check, exact SID binding and exact-account deletion guard;
- password exists only in controller memory, is never serialized, logged, placed in environment or command line, and is cleared after logon;
- controller-owned staging paths use protected ACLs: worker receives only the fixed read/execute and designated result-write access required by the benign probe;
- `LogonUserW` primary-token validation: exact worker SID, non-administrator token and medium integrity;
- `CreateEnvironmentBlock(..., false)` and `CreateProcessAsUserW(..., bInheritHandles=false)`;
- explicit application path, fixed arguments and fixed working directory; arbitrary commands and shell resolution are absent;
- worker is created with `CREATE_SUSPENDED`, assigned to an unnamed Job Object, verified with `IsProcessInJob`, and only then resumed;
- Job Object uses `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and never enables breakaway flags;
- process-set verification is based on the primary-token SID returned by `WTSEnumerateProcessesEx`; probe failure is fail-closed and bounded quiescence is required before exact account cleanup;
- only a fixed benign self-child probe is allowed; patch/workspace code is not accepted as input;
- V1B3C Windows smoke compiles the exact C# payloads but does not launch Sandbox or execute the worker;
- the first active run of the exact production payload was completed in V1B3D.

Verification closure:

```text
74f543a  feat: add standard-user worker isolation bundle
worker bundle unit/static eval:                28/28
exact Windows helper/worker compile smoke:     2/2
worker executable created:                     true
worker executable executed:                    false
developer_task_execution_boundary_worker:      completed successfully
full check:                                    completed successfully
execution_authorized:                          false
```

##### V1B3D — Active Signed Boundary Composition

**Статус:** VERIFIED / production closure `f3f5607`; active evidence `2026-08-11`.

- composes V1B1 host evidence, V1B2 process lifecycle, V1B3B transcript pinning/verification and the exact V1B3C worker bundle in one Sandbox instance;
- receives `ready.json`, constructs canonical authorization in host memory, pins `request + ready + authorize`, and publishes `authorize.json` followed by the verified `authorize.sha256` commit marker;
- treats mapped output as untrusted while Sandbox is active and accepts success only after every known Sandbox process exits;
- re-reads trusted input, control and output artifacts after proven exit and requires exact byte/hash stability before V1B3B post-exit verification;
- binds the V1B3C bundle fingerprint in pinned controller bytes and verifies locked native-helper and worker-source hashes inside the trusted controller;
- compiles and executes only the fixed benign V1B3C worker in a protected local guest staging tree; patch/workspace bytes are never mapped or accepted;
- closes the Job Object, proves worker-SID process quiescence, deletes the exact worker account, and only then signs the terminal payload;
- removes host artifacts only after Sandbox process absence is proven; forced cleanup is always failure-only;
- preserves `execution_authorized=false` until V1B4 and V1C.

Verification closure:

```text
f3f5607 feat: add active signed boundary composition
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
developer_task_execution_boundary_composition: completed successfully
full check:                                 completed successfully
execution_authorized:                       false
```

## Roadmap Change 006 — V1B4 source, derived bundle, active attestation and V1C lease are separate boundaries

**Причина:** source archive provenance, deterministic runtime bytes, active interpreter behavior and permission to enter a future same-run V1C state machine are different claims. Combining them would let an old active report or mutable host environment masquerade as current execution authority.

**Что меняется:** V1B4 is implemented as V1B4A/V1B4B/V1B4C/V1B4D. Historical V1B3 policy fingerprints remain immutable. The first active runtime run executes only a fixed benign probe; a non-serialized lease never carries active trust across Sandbox runs.

**Что не меняется:** patch/workspace execution, `python_module`, `pipeline`, arbitrary shell, dependency installation and host fallback remain forbidden; `execution_authorized=false` until V1C same-run gates explicitly succeed.

## Roadmap Change 005 — V1B3D authorization is pinned before publication and success is post-exit only

**Причина:** `ready.json`, `worker_result.json`, `terminal_payload.json` and the signature reside in writable shared output. Their existence while Sandbox is active is only a progress signal, not trusted evidence.

**Что меняется:** the host builds canonical authorization bytes in memory, successfully pins the exact `request + ready + authorize` transcript before writing `authorize.json`, then defers terminal trust until all Sandbox processes have exited and all pinned artifacts have been re-read as exact unchanged bytes.

**Что не меняется:** only the fixed benign V1B3C worker is executed; patch/workspace execution, `python_module`, `pipeline`, dependency installation and host fallback remain forbidden; `execution_authorized=false`.

## Roadmap Change 011 — Executable-check inventory, compile gate and toolchain provenance are separate V1C boundaries

**Причина:** V1B4 proves an exact minimal CPython 3.13.15 runtime, but the current executable-check environment is a different trust claim. The stable-tag context uses host Python 3.12.10 from `.venv`, declares 11 ranged direct requirements, contains 61 installed distributions, exposes 11 third-party import roots and 32 process-launch call sites, and defines an 84-step `check` flow that includes both host-hardware smoke and Git-dependent developer checks. The host `.venv`, inherited environment and current `check` flow therefore cannot become guest execution authority.

**Что меняется:** V1C starts with host-only V1C0A canonical inventory. The first active processing of changed workspace bytes is a separate V1C2 compile/AST gate that uses only the verified V1B4 runtime and does not import or execute workspace modules. Python dependencies and portable Git are separate provenance/bundle boundaries. The existing `check` flow is not the initial guest allowlist; a later protected guest-safe flow must be built from an exact reviewed step list.

**Что не меняется:** `skynet-trusted-runtime-v1b4` remains fixed at `91d8c37`; V1B4 fingerprints and evidence remain immutable; `python_module`, `pipeline`, arbitrary shell, runtime dependency installation, host `.venv` reuse, host fallback, commit, merge, push and promotion remain blocked; every serialized report keeps `execution_authorized=false` and `reusable_lease_issued=false`.

## Roadmap Change 010 — Runtime lease is a process-local entry capability, not past-run authority

**Причина:** a completed V1B4C2B report is durable evidence that the benign runtime boundary worked, but it cannot authorize a later Sandbox instance. A serializable or reusable token would silently convert post-exit evidence into cross-run execution authority.

**Что меняется:** V1B4D issues a process-local, non-serialized, non-copyable, single-use lease with a fixed `300`-second TTL from fresh host evidence and the exact in-memory V1B4B runtime capability. TTL is enforced with a monotonic clock. The lease binds the backend identity, runtime source/bundle identities, V1B4C policy/payload identities and a one-time secret, and may be atomically claimed only once by the future V1C combined-run orchestrator. The claim carries no proof about a guest and does not authorize changed code; V1C must re-establish the runtime preflight and signed handshake inside the same Sandbox instance before its first changed-code instruction.

**Что не меняется:** V1B4C2B reports are not accepted as lease inputs; no active Sandbox or Python execution occurs in V1B4D; cross-run trust, patch/workspace execution, `python_module`, `pipeline`, arbitrary shell, dependency installation and host fallback remain forbidden; every serialized report keeps `execution_authorized=false`.

## Roadmap Change 009 — Active runtime trust is post-exit, same-run and non-authorizing

**Причина:** the first CPython execution introduces writable shared output and a live process boundary. Ready/result/terminal files observed while Sandbox is active cannot become trusted evidence, and a successful benign runtime attestation must not silently become reusable authority for a later V1C run.

**Что меняется:** V1B4C2B performs exactly one benign production Sandbox run. The host rebuilds and materializes the exact V1B4B capability, pins request/ready/authorize through the verified V1B4C2A verifier before authorization commit, trusts terminal evidence only after every Sandbox process exits, revalidates host evidence and removes all private artifacts. Success is `active_trusted_runtime_attested` with `execution_authorized=false`.

**Что не меняется:** V1B4C1 and V1B4C2A exact fingerprints remain immutable; task/patch/workspace execution, `python_module`, `pipeline`, arbitrary shell, dependency installation and host fallback remain forbidden; V1B4D remains a separate future same-run lease boundary.

## Roadmap Change 008 — V1B4C2 verifier separated from the first active Python run

**Причина:** V1B4C1 фиксирует canonical documents и exact guest payload, но следующий этап всё ещё содержит два независимых доказательства: корректность host-side transcript pinning/CNG verification и корректность первого active Windows Sandbox запуска pinned CPython. Если вводить их одним commit, дефект verifier и дефект lifecycle/materialization невозможно локализовать независимо.

**Что меняется:** V1B4C2 is split into V1B4C2A and V1B4C2B. V1B4C2A implements a pure host-side signed-runtime transcript verifier and Windows CNG evidence without launching Sandbox or Python. V1B4C2B performs the first active production run only after the verifier is independently VERIFIED.

**Что не меняется:** V1B4C1 policy/contract/payload fingerprints remain immutable; V1B4B remains the only accepted runtime capability; patch/workspace code, `python_module`, `pipeline`, arbitrary shell, dependency installation and host fallback remain forbidden; every report keeps `execution_authorized=false`.

## Roadmap Change 007 — V1B4C contract/payload gate separated from the active runtime run

**Причина:** one commit must not simultaneously introduce a new signed transcript lineage, a new fixed native launch helper, a fourth read-only runtime mapping and the first execution of the pinned Python interpreter. That would make review and failure attribution too broad.

**Что меняется:** V1B4C1 locks and verifies the canonical runtime-attestation contracts and exact guest payload without launching Sandbox or Python. V1B4C2 performs the first active production run of those exact bytes inside the already verified lifecycle, privilege and signature boundary.

**Что не меняется:** V1B3 fingerprints remain immutable; V1B4B bytes remain the only accepted runtime; patch/workspace code, `python_module`, `pipeline`, arbitrary shell, dependency installation and host fallback remain forbidden; `execution_authorized=false`.

## Roadmap Change 004 — V1B3C payload gate separated from V1B3D active composition

**Причина:** a standalone active V1B3C run would either trust writable unsigned output or duplicate the lifecycle/signature composition that belongs to V1B3D. Both options weaken the evidence model.

**Что меняется:** V1B3C builds and statically/compile-verifies the exact trusted worker-isolation payload and immutable bundle; V1B3D performs the first active production run of those exact bytes together with V1B2 lifecycle and V1B3B transcript verification.

**Что не меняется:** V1B3A remains capability evidence; V1B3B remains the host verifier; V1B4 and V1C remain blocked; no patch code, arbitrary shell, dependency installation or host fallback is allowed; `execution_authorized=false`.

The V1B2 policy fingerprint remains the historical lifecycle baseline. A production V1B3 policy schema/fingerprint is not changed until V1B3A experiment evidence is reviewed.

## Roadmap Change 003 — V1B3 split into measured security slices

**Причина:** traditional `.wsb` proves the container lifecycle but does not directly provide a SYSTEM controller, authenticated writable output or a standard-user worker boundary. Those properties must be independently measured before production composition.

**Что меняется:** V1B3 is implemented as V1B3A/V1B3B/V1B3C/V1B3D.

**Что не меняется:** V1B4 and V1C remain blocked; patched code is not executed; host fallback, arbitrary shell and dependency installation remain forbidden; `execution_authorized=false`.

#### V1B4 — Trusted Python Runtime Bundle Gate

**Статус:** V1B4A–V1B4D VERIFIED; V1B4 COMPLETE. V1C0A CURRENT; changed-code execution remains BLOCKED.

Host `.venv` is not a trusted runtime bundle. V1B4 uses a separate application-local CPython distribution with exact source provenance, deterministic derived bytes, a fixed launch contract and active same-boundary evidence.

##### V1B4A — Runtime Source Provenance Gate

**Статус:** VERIFIED / CPython 3.12.10 reference and CPython 3.13.15 execution candidate.

- host-only; candidate interpreters were not executed;
- exact official archive and SPDX bytes were verified;
- unsafe ZIP paths, duplicate/case collisions, symlinks, encryption, unbounded expansion and mutable/reparse input are rejected;
- required embeddable files, AMD64 PE machine, upstream `_pth`, stdlib manifest and absence of executable package-management surfaces are pinned;
- the accepted execution candidate is `python-3.13.15-embed-amd64.zip` with SHA-256 `d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf`;
- source fingerprint is `6027ca87d35d94fa131d64c8210e5c6f5002f801274752421e480a9a180dba45`;
- strict provenance policy fingerprint is `232d65ce4fdb9d990e588f15133db3593cb69f31c5d4e3dfece28b79b827c503`;
- every report keeps `interpreter_executed=false` and `execution_authorized=false`.

CPython 3.12.10 remains a verified provenance reference only. CPython 3.13.15 is the pinned execution candidate for V1B4B–V1B4D.

##### V1B4B — Deterministic Runtime Bundle Gate

**Статус:** VERIFIED / production closure `05e0e00`.

- derives an application-local runtime only from exact CPython 3.13.15 source bytes;
- replaces upstream `python313._pth` with a project-owned locked site-free file;
- adds only a fixed trusted probe, fixed trusted runner and canonical `runtime_manifest.json`;
- rejects extra/missing files, path collisions, reparse points, ADS, arbitrary `.pth`, `import site`, `sitecustomize`, `usercustomize`, pip and mutable package roots;
- verifies exact bytes again after disk staging and removes staging before returning;
- exposes exact bytes only through a non-serialized capability and accepts no manifest/workspace/patch/command input;
- verified bundle identity: 37 files, 21,346,903 bytes, tree manifest `ab35bf73bf387d28cd14bdcf85c545706ae7522212f466bf10afbaf1e14ac7ed`, bundle fingerprint `1c98ad24ec3e4bb1b8b4bcd530ffedcf6ff62a6fee5b94cb795f6c84fb1c8c4b`;
- portable gate `31/31`, real Windows source gate `5/5`, targeted flow and full `check` completed successfully;
- candidate interpreter was not executed and `execution_authorized=false`.

##### V1B4C — Active Trusted Runtime Attestation

V1B4C is internally split so the new signed runtime schema and exact guest payload are reviewed before any active Sandbox launch.

###### V1B4C1 — Runtime Attestation Contract and Payload Gate

**Статус:** VERIFIED / production closure `9a85bb1`.

- introduced a separate immutable V1B4 runtime-attestation policy/schema lineage without mutating historical V1B3 fingerprints;
- defined strict canonical request, ready, authorize, runtime-result and terminal documents;
- bound the exact V1B4B source, tree, bundle, runtime-manifest, `_pth`, probe, runner and launch-contract identities;
- locked the exact SYSTEM-controller/native-helper/bootstrap/four-folder `.wsb` payload;
- preserved fresh standard-user, medium-integrity, Job-before-resume, no-breakaway, SID-quiescence and exact-account-deletion controls;
- portable contract/payload gate completed `33/33`;
- real Windows compile/parse-only smoke completed `3/3`;
- targeted flow and full `check` completed successfully;
- Windows Sandbox and candidate `python.exe` were not launched; `execution_authorized=false`.

Verified identities:

```text
runtime-attestation policy: 31c4f8de17e999db2d064a8aca4e95d3e2400f21a229317e83b1d5700d1e3c48
payload bundle:             47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13
historical V1B3 boundary:   9eb7a1373d1814eea37c8213dfeaeb4f4e7d40e7fdb5d8ec40f91f3e2fd8db72
```

###### V1B4C2 — Signed Verification and Active Trusted Runtime Composition

V1B4C2 is split again so a new verifier is independently proven before the first interpreter execution:

```text
V1B4C2A  Signed Runtime Transcript Verifier   VERIFIED
V1B4C2B  Active Trusted Runtime Composition   VERIFIED
```

####### V1B4C2A — Signed Runtime Transcript Verifier

**Статус:** VERIFIED / production closure `4a68c3c`.

- implements pure cross-document and temporal verification for exact V1B4C1 request/ready/authorize/runtime-result/terminal bytes;
- binds request ID, host nonce, authorization nonce, C1 policy/payload, every V1B4B runtime identity, public key and exact hash chain;
- rejects replay, substitution, post-pin mutation, temporal inversion, invalid P-256 points, forged pin reports and invalid/non-boolean signature-verifier results;
- verifies exact raw 64-byte ECDSA P-256 signatures through Windows CNG;
- has no filesystem, process, Sandbox, runtime-builder, workspace or candidate-Python launch surface;
- portable gate completed `46/46`, Windows CNG smoke completed `3/3`, targeted flow and full `check` completed successfully, Runtime Architecture Audit completed `9/9`;
- every report remains immutable, redacted and `execution_authorized=false`.

####### V1B4C2B — Active Trusted Runtime Composition

**Статус:** VERIFIED / production closure `049e4ca`.

- one production Windows Sandbox run completed with the exact V1B4B runtime mapped read-only;
- the fixed CPython 3.13.15 runner/probe executed under the SYSTEM-controller → standard-user → Job Object boundary;
- request/ready/authorize pinning, runtime-result binding and terminal ECDSA P-256 verification succeeded;
- all Sandbox processes exited without forced cleanup and all private artifacts were removed;
- exact payload fingerprint is `47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13`;
- portable gate completed `42/42`, active Windows gate completed `3/3`, targeted flow and full `check` completed successfully, Runtime Architecture Audit completed `9/9`;
- `interpreter_executed=true`, `reusable_lease_issued=false`, `execution_authorized=false`.

##### V1B4D — Same-Run Runtime Capability Lease

**Статус:** VERIFIED / production closure `18e8619`.

Verification closure:

```text
portable lease gate:                         36/36
real Windows host-only lease smoke:            5/5
policy fingerprint: 76ceaaf139af10814a403d24fca7455a61db78f095e80d390b360417354e8c18
TTL:                                      300 seconds
clock:                              time.monotonic_ns()
claim returns exact runtime capability:         true
second/replay claim rejected:                   true
concurrent double claim:                one winner
Sandbox process set after claim:                 []
candidate interpreter executed:                false
execution_authorized:                          false
targeted flow:                   completed successfully
full check:                      completed successfully
runtime architecture audit:                      9/9
```

The Windows-specific boot-epoch quantization defect found during the first real claim was fixed without weakening the host boundary: fresh-host equivalence retains the measured one-second tolerance, while the lease fingerprint continues to bind the exact issuance snapshot. Drift of two seconds or any other bound host/runtime identity remains fail-closed.

V1B4D is a host-only capability gate. It does not launch Windows Sandbox, does not execute `python.exe`, does not inspect a past C2B report and does not accept any developer-task, patch, workspace, module, pipeline, command or environment input.

The lease is:

```text
process-local
non-serialized
non-copyable / non-pickleable
single-use
thread-safe
TTL: exactly 300 seconds
trust clock: monotonic
execution_authorized: false
```

It is issued only from fresh successful host evidence with an empty Sandbox process set and the exact in-memory `DeveloperTaskPythonRuntimeBundle` capability. It binds:

- backend ID and backend policy fingerprint;
- host boot identity with the already measured one-second quantization rule;
- Windows build and process architecture;
- Sandbox executable path/version/size/mtime/SHA-256;
- runtime source SHA-256/source fingerprint/source-provenance policy;
- runtime bundle policy, tree manifest, runtime manifest and bundle fingerprint;
- Python executable/DLL/`._pth`/stdlib/probe/runner/launch-contract identities;
- V1B4C attestation policy fingerprint;
- exact V1B4C payload fingerprint `47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13`;
- one-time cryptographically random secret and issuer-instance identity.

A future V1C orchestrator may atomically claim the lease once. Expiry, replay, concurrent second claim, host drift, runtime substitution, policy mismatch or failed claim invalidates the capability. The lease retains the exact runtime capability in memory; it never serializes runtime bytes, a host path, the secret, monotonic anchors or an execution grant.

Locked implementation scope:

```text
A modules/developer/developer_task_execution_runtime_lease_policy.py
A modules/developer/developer_task_execution_runtime_lease.py
A tools/eval_developer_task_execution_runtime_lease.py
A tools/eval_developer_task_execution_runtime_lease_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

The Windows smoke is host-only: it builds the real pinned V1B4B capability, issues and claims one lease, proves replay rejection and removes all staging. The portable gate proves exact TTL expiry with a controlled internal clock. Neither path may launch Sandbox or the candidate interpreter. Ordinary `check` runs only the portable gate.

Lease claim is only permission for the future V1C orchestrator to begin one combined run. Inside that same Sandbox instance, before the first changed-code instruction, V1C must repeat:

```text
runtime manifest verification
runtime benign preflight
network evidence
worker privilege evidence
Job membership evidence
signed transcript handshake
```

If the combined run fails, exits or consumes the capability, no retry is permitted with the same lease. A new task requires a newly issued lease and a new same-run attestation.

Detailed contract: `docs/architecture/SKYNETVS_TRUSTED_PYTHON_RUNTIME_V1.md`.

#### V1B4 closure

V1B4 is complete only as a trusted-runtime foundation. It does **not** authorize changed-code execution. The verified chain is now source provenance → deterministic runtime bundle → active signed benign runtime attestation → process-local single-use runtime lease.

The Pro Standard V1C architecture review is complete against stable tag `skynet-trusted-runtime-v1b4` at `91d8c37`. It inserts a non-executing V1C0A inventory gate before workspace snapshot, toolchain provenance or any changed-code boundary. `python_module`, `pipeline`, patch/workspace execution, arbitrary shell, dependency installation and host fallback remain blocked.

### V1C — Sandboxed Executable Checks

**Статус:** V1C0A CURRENT; all changed-code execution remains BLOCKED.

#### V1C architecture context closure

The exact context archive collected from `skynet-trusted-runtime-v1b4` was verified before this roadmap change:

```text
archive SHA-256:                     627dfb80d16c97d0a4ed8ce94fcbbbb4b671b40e4e0c3d8f792123334b07a84f
manifest payloads verified:          47/47
HEAD / origin/main / stable tag:     91d8c37fc4afe7ef138e36063e7bc22014da8a2c
tracked Python files:                226
AST parse failures:                  0
pipeline flows:                      89
current check steps:                 84
import roots:                        65
third-party import roots:            11
process-launch call sites:           32
direct ranged requirements:          11
installed host distributions:        61
host Python:                         3.12.10
trusted runtime Python:              3.13.15
```

The 11 third-party roots are `colorama`, `comtypes`, `dotenv`, `edge_tts`, `faster_whisper`, `joblib`, `numpy`, `pycaw`, `sklearn`, `sounddevice` and `vosk`.

Git tracks `requirements.txt`, `requirements-train.txt` and `requirements-whisper.txt`, but the context collector captured exact bytes only for `requirements.txt`. This is a collector/inventory gap, not permission to infer the other files. V1C0A must discover and bind every tracked `requirements*.txt` and lock candidate itself.

The current `check` flow is not guest-safe as one unit. It includes a real CoreAudio Windows smoke and Git-dependent Developer Safety Kernel evals, launches child Python processes through `sys.executable`, and inherits the host environment plus existing `PYTHONPATH`. Its current behavior is observation data only.

#### Final V1C decomposition

```text
V1C0A  Canonical Executable Check Inventory Gate             CURRENT
V1C0B  Host Toolchain Observation and Source Selection       PLANNED
V1C1   Immutable Workspace Snapshot and Typed Execution Plan PLANNED
V1C2   Active Sandboxed Compile/AST Gate                     PLANNED
V1C3A  Python Dependency Source Provenance                   PLANNED
V1C3B  Deterministic Python Check Dependency Bundle          PLANNED
V1C3C  Portable Git Source Provenance and Bundle             PLANNED
V1C4A  Changed-Code Execution Contract and Guest Payload     PLANNED
V1C4B  Signed Changed-Code Transcript Verifier               PLANNED
V1C5   Active Sandboxed python_module Check                  BLOCKED
V1C6   Active Sandboxed Guest-Safe Pipeline Check            BLOCKED
V1C7   Composite Typed Check Runner and Result Evidence      BLOCKED
```

`V1C0B` observations are not authority. Exact source bytes, hashes, licenses, architecture compatibility and deterministic derived trees must be proven independently before any dependency or external tool enters a guest boundary.

#### Locked toolchain decisions

- The host `.venv` is never copied, mapped or treated as trusted input. It is CPython 3.12 state while V1B4 is CPython 3.13.15, contains mutable resolver/install state and includes ABI-specific native extensions.
- Runtime `pip`, `ensurepip`, package resolution, download, sdist build and network acquisition are forbidden.
- Python check dependencies require a separate exact offline wheel/source provenance boundary and a deterministic CPython 3.13 AMD64 bundle.
- Portable Git is required before any guest flow containing Git-dependent checks. It is a separate provenance/bundle from CPython and Python dependencies. Hashing only `cmd/git.exe` is insufficient to identify the Git distribution.
- The first active changed-workspace boundary is V1C2 compile/AST only. It consumes one fresh V1B4D lease and one fresh Sandbox, but imports and top-level execution remain forbidden.
- Every `python_module` target must be selected by a semantic explicit allowlist and bound to an exact protected baseline-owned entrypoint. The existing name regex is validation only, not authorization.
- The existing `check` flow is not the initial pipeline allowlist. V1C6 must introduce a protected guest-safe flow with an exact reviewed step list; host-hardware smoke, outer Sandbox activation and interactive/promotion flows remain excluded.
- One executable check uses one fresh lease, one immutable workspace snapshot and one fresh Sandbox. A successful report never becomes authority for another check.

#### V1C0A — first production slice

V1C0A is host-only and non-authorizing. It performs read-only inventory over a typed clean repository evidence chain and never imports tracked modules.

Planned public shape:

```python
inventory_developer_task_execution_environment(
    repository_report: DeveloperTaskRepositoryPreflightReport,
    *,
    project_root: Path,
) -> DeveloperTaskExecutionEnvironmentInventoryReport
```

Caller-supplied requirement lists, module allowlists, pipeline allowlists, executables, argv, environment additions and classification overrides are forbidden.

Locked implementation scope:

```text
A modules/developer/developer_task_execution_environment_inventory_policy.py
A modules/developer/developer_task_execution_environment_inventory.py
A tools/eval_developer_task_execution_environment_inventory.py
A tools/eval_developer_task_execution_environment_inventory_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

Acceptance includes:

- exact discovery/hash of every tracked requirements/constraint/lock candidate;
- AST-only inventory of all tracked Python imports and process surfaces;
- exact pipeline flow/step topology and fixed child-command shapes;
- external-tool and host/hardware dependency classification;
- detection of missing collector inputs and noncanonical/duplicate evidence;
- stable canonical report fingerprint without host absolute paths as authority;
- no repository mutation, Sandbox launch, lease claim, candidate interpreter execution, module import or changed-code execution;
- `execution_authorized=false` and `reusable_lease_issued=false`.

`python_module` and `pipeline` remain blocked until the later same-run contracts, toolchain bundles and signed post-exit evidence are independently VERIFIED.

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

**Критерий завершения PHASE 1:** задача проходит путь manifest → preflight → independent repository workspace → isolated apply → typed checks → report, при этом основной repository остаётся неизменным и исполнение изменённого кода не выходит за утверждённую execution isolation policy.

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

[VERIFIED CODE] 1035de4 — complete Developer Task Preflight V1

[VERIFIED CODE] 4861934 — Isolated Repository Workspace V1A

[VERIFIED CODE] 892e175 — Workspace Cleanup and Lifecycle Audit V1B

[VERIFIED CODE] b8419f5 — Developer Task Patch Apply V1

[VERIFIED CODE] 6a7b08e — Typed Check Runner V1A Static Evidence Gate

[VERIFIED CODE] 368c25f — Typed Check Runner V1B1 Host Capability Gate

[VERIFIED CODE] eb2a476 — Typed Check Runner V1B2 Active Trusted Lifecycle Gate

[VERIFIED CODE] 4ea2e0c — Windows Sandbox launch environment hardening

[VERIFIED ACTIVE EVIDENCE] V1B3A — SYSTEM Controller Bootstrap Capability Experiment

[VERIFIED CODE] 674dd5f — V1B3B Canonical Transcript and Host Signature Verifier

[VERIFIED CODE] 74f543a — V1B3C Standard-User Worker Isolation Bundle

[VERIFIED CODE] f3f5607 — V1B3D Active Signed Boundary Composition

[VERIFIED STABLE FOUNDATION]
skynet-trusted-runtime-v1b4 → 91d8c37
V1B4A provenance → V1B4B deterministic bundle → V1B4C active runtime → V1B4D same-run lease.

[CURRENT ARCHITECTURE STAGE]
Typed Check Runner V1C0A — Canonical Executable Check Inventory Gate.

[NEXT AFTER V1C0A]
V1C0B toolchain source selection → V1C1 snapshot/plan → V1C2 active compile gate.

[PLANNED AFTER SAFETY KERNEL]
Domain Package Structure V2.

[PLANNED AFTER PRODUCTION PACKAGES]
Tools Package Structure V1.
```

До завершения Developer Safety Kernel дополнительные production-файлы по пакетам не переносятся.
