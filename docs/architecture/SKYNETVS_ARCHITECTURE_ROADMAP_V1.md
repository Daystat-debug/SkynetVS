# SkynetVS Architecture Roadmap V1

**Дата фиксации:** 2026-07-30
**Последнее обновление:** 2026-08-25
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

**Статус:** V1B1–V1B4 VERIFIED; trusted-runtime foundation COMPLETE. V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2/V1C2C1R3/V1C2C1R4 VERIFIED; V1C0B2, V1C1 and V1C2 architecture LOCKED; Roadmap Changes 021, 022 and 025 diagnostics COMPLETED / CONSUMED; Roadmap Change 024 active retry FAILED / CONSUMED; Roadmap Change 027 CURRENT — exact V1C2C2 R4 rebind plus one fresh active attested-pass retry only; V1C2C3 BLOCKED.

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



## Roadmap Change 016 — V1C2C requires a process-local claim transaction before fixed payload and active composition

**Причина:** exact source audit at `b527f93` found a missing one-run identity boundary. V1C2A1 requires `runtime_lease_fingerprint`, but V1B4D exposes no public per-instance lease identity; its private binding hash contains the host/runtime snapshot but no per-issuance nonce or secret and therefore is not a unique transcript identity. Reusing it directly would permit two same-host leases to share the same serialized fingerprint even though their one-time secrets and object identities differ. The same audit also confirms that the V1B4C helper cannot be reused unchanged because V1C2A1 requires active-process and memory Job limits in addition to kill-on-close.

**Что меняется:** V1C2C is split into four measured slices. V1C2C0 issues a process-local, single-use claim transaction bound by exact object identity to one V1C1B plan and one V1B4D lease and publishes a fresh non-secret `runtime_lease_fingerprint`; it claims nothing at issuance and later claims plan first and runtime lease second with no fallible filesystem operation between the two claims. V1C2C1 builds the exact fixed SYSTEM-controller/native-helper/bootstrap/WSB-template bundle with a standard-user worker, sanitized environment, no inherited handles, `CREATE_SUSPENDED`, assign-before-resume and Job limits `1 / 512 MiB / 768 MiB`. V1C2C2 alone materializes exact sources/runtime, launches one fresh Sandbox, pins authorization before publication and accepts signed evidence only after all known Sandbox processes exit and exact artifacts remain stable. V1C2C3 closes the live pass, authentic syntax-failure and signed post-ready boundary-failure matrix with three fresh capabilities and three fresh Sandbox instances.

**Что не меняется:** V1C2A1/V1C2A2/V1C2B identities remain immutable; the stable V1B4 tag is not moved; workspace, `.git`, host `.venv` and host Git are never mapped; no guest network/install, `exec`, `eval`, import execution, top-level execution or bytecode write is allowed; every outcome keeps `changed_code_executed=false`, `execution_authorized=false` and `reusable_lease_issued=false`. An authentic syntax failure is a successful security composition with `check_passed=false`; an authentic `compile_ast_boundary_failed` terminal is verified evidence but the active composition remains unsuccessful.

Locked identities:

```text
decision ID:          skynetvs-v1c2c-active-compile-ast-composition-split-v1
decision fingerprint: 56bfd2ca196ca2b6d8f6ad426ea06141fe1535a28a281f0d7661bc8e32ee8ff6
V1C2C0 policy:        092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa
V1C2C1 architecture slice identity: db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec
V1C2C2 architecture slice identity: d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484
V1C2C3 evidence:      b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
context archive:      f5883188e4aa2119c849f2adbc449b73072ede208f742f6ededb42ae783aa08d
context fingerprint:  8cd54944d3e9873f8af267adf86d4e0d220c947dc3578d88140849ba8366e63c
```

## Roadmap Change 017 — V1C2C1 architecture slice identity and implementation policy fingerprint are separate claims

**Причина:** the exact verified V1C2C context archive with SHA-256 `f5883188e4aa2119c849f2adbc449b73072ede208f742f6ededb42ae783aa08d` contains the Roadmap Change 016 value `db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec` only as a locked documentation identity. It contains no canonical V1C2C1 policy JSON, schema or preimage whose SHA-256 can be recomputed to that value. Treating it as the hash of newly invented bytes would create an unverifiable or false cryptographic claim.

**Что меняется:** `db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec` remains immutable as the V1C2C1 architecture-slice identity. The concrete deterministic implementation introduces a separate canonical policy ID, a reproducible semantic policy fingerprint, an exact policy-document SHA-256 and exact payload/bundle identities. The policy self-check binds the architecture decision and slice identity but never claims that the unavailable historical preimage was reconstructed.

**Что не меняется:** the V1C2C0 → V1C2C1 → V1C2C2 → V1C2C3 order, threat model, fixed scope, Job limits, LocalSystem/standard-user boundary, historical V1B4/V1C2A1/V1C2A2/V1C2B/V1C2C0 identities and stable V1B4 tag remain unchanged. V1C2C1 stays host-only and non-authorizing; claim consumption, materialization, Sandbox launch, interpreter execution and changed-source processing remain V1C2C2-only.

Locked V1C2C1 implementation identities:

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

Acceptance remains fail-closed and requires:

```text
package boundaries:                           28/28
V1C2C1 portable adversarial gate:              33/33
V1C2C1 Windows compile/parse-only smoke:         3/3
targeted flow:                   completed successfully
full check:                      completed successfully
Runtime Architecture Audit:                       9/9
Windows Sandbox launched:                       false
candidate interpreter executed:                 false
changed-source processing:                     false
execution_authorized:                           false
```

Those conditions are satisfied by the exact implementation commit and evidence recorded below. V1C2C1 is VERIFIED only as a deterministic host-only, non-authorizing payload bundle; it grants no active execution authority.

## Roadmap Change 019 — V1C2C1 transcript policy-hash integration correction precedes V1C2C2

**Причина:** exact-source integration review at current documentation HEAD `3331577835dd4344c42772ba4dde141bf0055749` found a fail-closed incompatibility that no V1C2C2 orchestration can safely work around. The fixed V1C2A2 runner requires canonical `request.policy_sha256` to equal the SHA-256 of `compile_ast_contract_policy.json` (`f280f9c564dd1cfd780cd5465a3ecd98244e0f00f10827a295b3709b2d8b0ed2`), and V1C2B independently pins and re-verifies that same field against the exact V1C2A2 `contract_policy` payload. The verified V1C2C1 controller instead requires the same single field to equal its distinct controller-worker policy SHA-256 (`1d9b1c66bf3971a3fdedfb077ef8deb08467e29acbc4f725d7050e3ae1342091`) and emits that value in `ready` and `terminal`. Because those hashes differ, either host-side V1C2B pinning or guest-side V1C2C1 request validation must fail before an active composition can be accepted.

**Что меняется:** a measured host-only corrective revision `V1C2C1R1 — Transcript Policy-Hash Integration Correction` is inserted before V1C2C2. The canonical transcript field `policy_sha256` retains the already VERIFIED V1C2A1/V1C2A2/V1C2B meaning: exact V1C2A1 contract-policy bytes. The controller-worker policy remains independently verified by the fixed controller through its embedded exact SHA-256 and by the corrected deterministic bundle identity; it is no longer overloaded into the canonical V1C2A1 transcript field. `ready` and `terminal` echo the request contract-policy SHA-256. The original `aa97b77` V1C2C1 bundle remains preserved as historical host-only evidence but is superseded for active composition by the corrected revision.

**Что не меняется:** V1C2A1, V1C2A2, V1C2B and V1C2C0 source, policies, public APIs and fingerprints remain unchanged. The LocalSystem controller, fresh standard-user worker, `CREATE_SUSPENDED`, assign-before-resume, no inherited handles, Job limits `1 / 512 MiB / 768 MiB`, four-folder mapping, network denial, post-exit trust model and stable V1B4 tag remain unchanged. No Sandbox or interpreter run is permitted during V1C2C1R1. V1C2C2 returns to `BLOCKED` until the corrective bundle is independently VERIFIED; V1C2C3 remains BLOCKED.

Corrected deterministic identities prepared for verification:

```text
policy ID:          skynetvs-v1c2c1r1-fixed-system-controller-standard-user-worker-bundle-v2
semantic policy fp: a1c9e95421ffe9755acc13028b05c3b45b960ad5d2ee750685bf56db1d44d03a
policy bytes SHA:   3d5405a603030d79a18ef31a3f5a5cd4f03b40c7115842a0d75974ecb26db3b3
bootstrap SHA:      7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d
native helper SHA:  901373a63df349e245a0c90887779b2cdb7f204dee98535c95bdc235844bb7a1
controller SHA:     776e4c07c533a44d54a57b5ecd0d38bf92cf6b7fc4aece1d4a211d85594049f4
WSB template SHA:   81861905167211b29fbff7179878b6b671c31b731af482166913b5e20416375f
bundle fingerprint: 12714af317444e481967af2ca063ec1fe0f3a4e83a8f750332aa667ba6155303
```

Locked corrective implementation scope:

```text
M modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
M modules/developer/developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
```

Acceptance requires package boundaries `28/28`, V1C2C1R1 portable `35/35`, Windows compile/parse-only `3/3`, unchanged V1C2A2/V1C2B dependency gates, targeted flow, full `check`, Runtime Architecture Audit `9/9`, exact four-file commit scope, post-commit Windows evidence and all active flags false. Commit subject: `fix: align compile ast transcript policy hash`.

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

No Sandbox was launched, no transaction was consumed, no runtime lease was claimed, no interpreter ran and no changed source was processed. `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false` remained invariant. V1C2C1R1 is therefore VERIFIED / HOST-ONLY / NON-AUTHORIZING. Roadmap Change 020 subsequently inserted and independently verified V1C2C1R2 and historically reopened V1C2C2 for exact R2 rebinding and one fresh active retry. Roadmap Changes 021 and 022 are now COMPLETED / CONSUMED and localize the active defect to non-persistent worker-ACE mutation on the real writable Sandbox mapping. Roadmap Change 023 inserted V1C2C1R3; Roadmap Change 024 closed it as VERIFIED / HOST-ONLY / NON-AUTHORIZING and authorized one exact V1C2C2 R3 rebind plus one fresh active attested-pass retry. That retry is now FAILED / CONSUMED; Roadmap Change 025 is now COMPLETED / CONSUMED and localizes the next defect to worker write access on the writable host-observed mapping. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.


## Roadmap Change 020 — V1C2C1R2 preserves host-observable shared-output ACL before V1C2C2 retry

**Причина:** the first measured V1C2C2 active run reached trusted `ready.json`, successfully pinned the pre-authorization transcript and published exact authorization, but then produced no host-observable `result.json`, terminal payload, terminal signature or controller-failure artifact before the Sandbox process set exited. Exact source review found that the fixed V1C2C1R1 controller calls `PrepareWorkerResultDirectory` on the writable mapped root `C:\SkynetVSOutput`. The inherited helper replaces that shared directory's ACL with a protected DACL owned by LocalSystem and containing only LocalSystem plus the fresh guest worker SID. That helper was safe for private guest-local result directories in V1B3/V1B4, but it is not admissible for a host-observed mapped output boundary.

Measured diagnostic evidence:

```text
report SHA-256:                       bd35bd7315cf8d9646a29e9af6593cd6098fd34e31d93eeaaa1efbf1b2f08122
request ID:                           b2784ab28b0ead772eda064a876566f9
ready received:                       17 265 ms
authorization published:              17 311 ms
result detected:                       false
terminal detected:                     false
all Sandbox processes exited:          38 578 ms
forced cleanup attempted:               false
artifacts removed:                       true
issue code: compile_ast_composition_sandbox_exited_before_terminal
changed_code_executed:                  false
execution_authorized:                    false
```

**Что меняется:** a host-only corrective slice `V1C2C1R2 — Shared Output ACL Preservation Correction` is inserted before another V1C2C2 active run. The compile-specific helper must preserve the mapped output directory's existing owner, inheritance/protection state and pre-existing access rules, add only the exact fresh worker write ACE required for `result.json`, and re-read the ACL to prove the worker ACE without deleting pre-existing host-observation rights. The shared-output path must not use `SetAccessRuleProtection(true, false)`, must not replace the owner, and must not create a SYSTEM+worker-only DACL. Historical private guest-local ACL hardening in V1B3/V1B4 remains unchanged.

**Что не меняется:** V1C2A1, V1C2A2, V1C2B, V1C2C0, V1C2C1 and V1C2C1R1 remain immutable historical evidence. The LocalSystem controller, fresh standard-user worker, `CREATE_SUSPENDED`, assign-before-resume, no inherited handles, Job limits `1 / 512 MiB / 768 MiB`, four-folder mapping, network denial, post-exit signature trust model and stable V1B4 tag remain unchanged. The uncommitted V1C2C2 seven-file implementation is preserved but remains non-accepted and must not be committed while V1C2C1R2 is open. V1C2C2 and V1C2C3 are BLOCKED.

Locked V1C2C1R2 code scope:

```text
M modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
M modules/developer/developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
```

The correction is host-only. Its acceptance must prove deterministic policy/helper/controller/bundle identities, preservation of the shared-output ACL contract, package boundaries, all V1C2 dependency gates, portable adversarial coverage, Windows compile/parse-only evidence, targeted flow, full `check`, Runtime Architecture Audit `9/9`, exact four-file commit scope and post-commit Windows evidence. It may not launch Sandbox, consume a transaction, claim a runtime lease, execute the candidate interpreter or process changed source. Commit subject: `fix: preserve shared output ACL for compile ast worker`.

### V1C2C1R2 verification closure

The shared-output ACL correction is VERIFIED at exact code commit:

```text
implementation commit:                  d200c49bc5868a50ae6c83c45d4e7ed8724f332a
parent documentation commit:            f2593b931bc8b9ed05d4535b27e62c72d2af1b58
commit message:                          fix: preserve shared output ACL for compile ast worker
committed R2 patch SHA-256:              dcc77e8a5e0920b7a4c90cfd8c6703e4d20c4ebbeb7451de12efe673fd8b6cf6
package boundaries:                      28/28
portable controller-worker evaluator:    41/41
Windows ACL compile/behavior smoke:        3/3
targeted controller-worker flow:         completed successfully
isolated NLU evaluation:                 124/124
isolated full check:                     completed successfully
Runtime Architecture Audit:                9/9
post-commit V1C0A Windows inventory:       1/1
post-commit Windows ACL smoke:              3/3
post-commit targeted flow:               completed successfully
tracked files / Python files:             280 / 262
Python bytes:                             4,052,586
pipeline flows / total steps:              98 / 504
pipeline check steps:                       93
process-launch call sites:                  41
host-sensitive files:                       34
Python tree fingerprint:                 39a6cfef822925048019f5bd58b8c12ea2c255f1f504e7d24181511e49308233
inventory fingerprint:                   30ef2e1be731af6fd58834abb13cd2d3269ce89488e8d406079f1c36f4e35736
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

Verified corrected bundle identities:

```text
policy ID:          skynetvs-v1c2c1r2-fixed-system-controller-standard-user-worker-bundle-v3
semantic policy fp: 65d0dbdd1cf03095f35f3bd322b3ef8a1f0e9139c163266fefd1664218e21a0a
policy bytes SHA:   ece583455d0813154e9bd8e14a84822614b20d3f38a8276358d77d7e75e7d014
bootstrap SHA:      7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d
native helper SHA:  550c1d009ffcbb0ea25ad609d215237f2e5a66a20f48edc7278c314e84d7677a
controller SHA:     335fbed28b001bcd4f11975b520d9d1e5feaec698a7a5836d946c132bebe5e23
WSB template SHA:   81861905167211b29fbff7179878b6b671c31b731af482166913b5e20416375f
bundle fingerprint: 449240db944a60ed51a1914f36d6c981a9579cd72e9c0e3802b6b9f3382c458c
```

The verified helper preserves the shared mapped output root's existing owner, access-rule protection/inheritance state and complete pre-existing ACL multiset, adds exactly one fresh-worker write ACE, re-reads the ACL and rejects owner replacement, DACL replacement or `SetAccessRuleProtection(true, false)` on the shared root. All host-only and non-authorizing flags remained false: no Sandbox launch, transaction consumption, runtime-lease claim, candidate-interpreter execution, changed-source processing, changed-code execution, reusable lease or execution authorization occurred.

The existing uncommitted seven-file V1C2C2 implementation was rebound to the exact V1C2C1R2 identities without scope growth and temporary failure-only diagnostics were removed. The resulting candidate is fixed at SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`, with policy fingerprint `1cc5a4aedb348f9cb669f2317c3a0a7b24bd11b7bbbd6eadd02907b2b1a8b1e5` and policy-document SHA-256 `71aa6a3228836740411d4c042d12b825cda8337b958771bc8e9ec4579299a5e1`. It remains unaccepted: the one Roadmap Change 020 active retry failed closed with trusted guest-failure evidence; Roadmap Change 021 historically permitted one diagnostic capture, and Roadmap Change 022 historically permitted one stage-localization probe. Both are now COMPLETED / CONSUMED.

Operational state after V1C2C1R2 closure:

```text
V1C2C1   VERIFIED / HISTORICAL HOST-ONLY BUNDLE
V1C2C1R1 VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C1R2 VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2   HISTORICAL STATE AT R2 CLOSURE / RC021 DIAGNOSTIC CAPTURE ONLY
V1C2C3   BLOCKED
```

## Roadmap Change 021 — one-shot capture of the R2 guest-failure artifact diagnostic

Roadmap Change 021 is generated from the exact committed documentation export at `HEAD 9a3f227685c6fd7e1097c371ce54137eb0a1c663`, tree `4e6ff04c3f1ce2ca30b8e77e6d74be0c708ef073`, archive SHA-256 `42bfb8e589da5fdd7947594b2e7ab296bc4505cd86dd0592d14ef9e513a9102d`; the three source blob IDs are `a0f8e3a4d1b8ecacf7bfb5ca907bdc152c924e2c`, `318c41956c4770c9e4f1ca3549a70e472fcad5ae` and `b23462bd5852799fd6713a5fae8350cc88c094a5`.

**Причина:** exact R2 rebinding completed without scope growth and produced seven-file candidate SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`; package boundaries passed `28/28` and the portable V1C2C2 gate passed `45/45`. The one fresh active retry authorized by Roadmap Change 020 consumed a fresh claim transaction and runtime lease and launched one Sandbox. The guest then emitted a bounded failure artifact before any candidate interpreter or changed source was accepted. The host report recorded `compile_ast_composition_guest_failure_reported` and `compile_ast_composition_guest_failure_artifact`, proved all Sandbox processes exited, removed all private artifacts and preserved source/workspace Git. `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false` remained invariant.

The exact `stage`, `error_type` and `error_code` remain unavailable in the retained log because the R2 rebind removed the temporary full-report print and the Windows evaluator exposed only `issue_codes`, while the report's `issues[].actual` field was not persisted. Selecting a production fix from the issue-code pair alone would be an unverified inference.

**Что менялось в RC021:** the Roadmap Change 020 retry was recorded as consumed and failed closed. At that roadmap state V1C2C2 was CURRENT only for one fresh, non-invasive diagnostic capture. A temporary external host harness could wrap the Windows evaluator's imported attestation function solely to serialize the immutable returned `report.to_dict()` and print its issue details. That authority is now COMPLETED / CONSUMED.

**Что не меняется:** the locked V1C2A1/A2/B/C0 and verified V1C2C1/R1/R2 identities remain immutable; the exact seven-file V1C2C2 candidate remains uncommitted; the stable V1B4 tag does not move; imports/top-level code are not executed; `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false` remain mandatory. V1C2C3 stays BLOCKED.

The diagnostic run was single-use and terminal for Roadmap Change 021 and is now COMPLETED / CONSUMED. Its evidence was reviewed before Roadmap Change 022; no authority from RC021 remains reusable.

Operational state:

```text
V1C2C1R2 VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2   HISTORICAL RC021 STATE / DIAGNOSTIC CAPTURE ONLY (NOW COMPLETED / CONSUMED)
V1C2C3   BLOCKED
R2 candidate patch SHA-256: 9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```


## Roadmap Change 022 — one-shot suspended-worker stage localization after the RC021 capture

Roadmap Change 021 is closed from exact documentation `HEAD b3cfad02c99aa283d9516a0d35c93d3edff21324` (`docs: record R2 guest failure and authorize diagnostic capture`). Its one-shot marker is `status=completed`, the immutable capture completed with `capture_ok=true`, and the full evidence file is bound by SHA-256 `96d2d4c797dd375d269e538558b5a5f9156a47bf80cc2f165b0d29b237b850dd`. The exact uncommitted seven-file candidate remains SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`.

The captured active report remained fail-closed:

```text
report status:                         failed
failure artifact:                      controller_failure.json
failure artifact SHA-256:             74a0eba664c757660c21a4311eb4d62ae541913f4e6140109503deb7d141cdee
stage:                                 compile_ast_worker
error type:                            MethodInvocationException
error code:                            compile_ast_controller_worker_stage_failed
ready received:                        17 750 ms
authorization published:               17 797 ms
all Sandbox processes exited:          36 890 ms
total:                                 37 640 ms
candidate interpreter executed:        false
changed source processed / parsed:     false / false
changed source compiled:               false
changed code executed:                 false
reusable lease issued:                 false
execution authorized:                  false
artifacts removed:                     true
source / workspace unchanged:          true / true
```

**Причина:** `MethodInvocationException` is only the outer PowerShell wrapper. The retained artifact does not identify whether the exact failure occurred while preserving the shared-output ACL, validating worker-token access to the fixed runtime/runner, calling `CreateProcessAsUserW`, assigning the suspended process to the Job Object, or validating the returned launch state. Choosing a production correction from that wrapper alone would remain an unverified inference.

**Что менялось в RC022:** Roadmap Change 021 diagnostic authority was marked COMPLETED / CONSUMED. At that roadmap state V1C2C2 was CURRENT only for one external `V1C2C2P1 — Suspended-Worker Stage-Localization Probe`. The probe could launch at most one fresh Windows Sandbox and use the exact committed V1C2C1R2 native-helper bytes plus exact read-only runtime and runner mappings solely to localize the failing transition. That probe is now COMPLETED / CONSUMED and never resumed the primary thread.

The completed probe was required to emit an ordered, durable checkpoint report for:

```text
controller LocalSystem identity
exact native-helper compile and hash binding
fresh worker account/token creation
worker token SID, integrity and non-admin state
worker-token access to C:\SkynetVSRuntime\python.exe
worker-token access to C:\SkynetVSInput\SkynetVS_V1C2A2_runner.py
PrepareSharedWorkerOutputDirectory
CreateProcessAsUserW with CREATE_SUSPENDED
AssignProcessToJobObject
IsProcessInJob and exact 1 / 512 MiB / 768 MiB limits
no primary-thread resume
Job close / suspended-process termination
worker SID quiescence
fresh-account deletion
Sandbox self-shutdown and host cleanup
```

For every failed checkpoint it was required to persist the complete exception chain, concrete type, `HResult`, Win32 `NativeErrorCode` when present, message and the immediately preceding successful checkpoint. For ACL preparation it also recorded owner/protection state and canonical before/after access-rule multiset fingerprints. Process creation was not reached, so no process/thread handle or Job-assignment state existed.

**Что не меняется:** this is not an active-composition acceptance retry and is not a production correction. It must not modify or commit the seven V1C2C2 files, must not widen the production API, must not use a V1C2C0 claim transaction, must not claim a runtime lease, must not materialize or process changed source, must not publish normal compile authorization, must not produce accepted result/terminal evidence and must not run the full pipeline. The stable V1B4 tag and all verified V1C2A1/A2/B/C0/C1/R1/R2 identities remain immutable. V1C2C3 remains BLOCKED.

The probe was single-use and terminal for Roadmap Change 022 and is now COMPLETED / CONSUMED. It captured exact stage evidence and cleanup only; Roadmap Change 023 is the subsequent explicit correction decision grounded in that evidence.

Operational state:

```text
V1C2C1R2 VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
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

## Roadmap Change 023 — mapped-output ACL non-persistence requires a guest-local worker-result relay

Roadmap Change 022 is closed from exact documentation `HEAD bdd23feacfba4032f8bf9be76dae94a5d670bf68` (`docs: close guest failure capture and authorize suspended worker localization`). Its permanent one-shot marker has `status=completed` and SHA-256 `4320b13cd9021967c80370a4dc13936455d291622f97a15897234e8a970bb85c`; the immutable full evidence has SHA-256 `4ee751d7dfbe7467e26b921fae981bd0e65c1275ca10dacac6342fb9ac9219bb`; the compact summary has SHA-256 `0334e3c5730f1563ab01648635ff1f6408ade4e24f0e383bc93c2905861ec967`. The exact uncommitted seven-file V1C2C2 candidate remains SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`.

The one-shot probe completed with `capture_ok=true`, `guest_status=localized_failure` and exact checkpoint `prepare_shared_worker_output_directory`. It proved the following chain before the defect:

```text
request boundary validation:              passed
controller identity:                      LocalSystem / S-1-5-18 / integrity 0x4000
exact R2 native helper:                    550c1d009ffcbb0ea25ad609d215237f2e5a66a20f48edc7278c314e84d7677a
fresh worker account/token:                created
worker token:                              primary / non-admin / integrity 0x2000
worker read C:\SkynetVSRuntime\python.exe: passed
worker read fixed V1C2A2 runner:           passed
PrepareSharedWorkerOutputDirectory:        failed
CreateProcessAsUserW / CREATE_SUSPENDED:   not reached
Job assignment / limit verification:       not reached
primary thread resumed:                    false
```

The exact exception chain is:

```text
System.Management.Automation.MethodInvocationException / 0x80131501
  -> System.InvalidOperationException / 0x80131509
     "Exact shared-output worker ACE was not observed after ACL write."
```

The real writable mapping `C:\SkynetVSOutput` had the same ACL state before the call and after the failed re-read:

```text
owner SID:                     S-1-5-21-3677456875-1600494081-873325803-1003
access rules protected:        true
rule count:                    3
rule multiset SHA-256:         4a67566837a9aca1cfe5ff32f47056d1640b4bf640ab3633bdb01ea986580162
rules:
  S-1-3-4|2032127|3|0|0|0
  S-1-5-18|2032127|3|0|0|0
  S-1-5-32-544|2032127|3|0|0|0
fresh-worker ACE observed:     false
```

The probe subsequently proved three empty worker-SID process scans, deleted the fresh account, scheduled Sandbox self-shutdown, observed all Sandbox processes exit and removed the temporary root. It did not consume a V1C2C0 transaction, did not claim a runtime lease, did not publish normal compile authorization, did not materialize or process changed source, did not resume the primary thread and did not execute the candidate interpreter or changed code. `reusable_lease_issued=false` and `execution_authorized=false` remained invariant.

**Доказанный дефект:** the R2 helper behaves correctly on the ordinary NTFS directory used by the host-only smoke, but the RC022 evidence proves that its worker ACE is not persisted or re-observed on the actual writable Windows Sandbox mapped folder. Therefore V1C2C1R2 remains VERIFIED only for its historical host-only / non-authorizing claim; it is insufficient for active mapped-output composition. The failure is not in account/token creation, worker integrity, runtime/runner access, `CreateProcessAsUserW` or Job assignment because the first four passed and the latter process boundaries were never reached.

**Что меняется:** `V1C2C1R3 — Guest-Local Worker Result Relay Correction` is inserted before V1C2C2. R3 must keep the fixed V1C2A2 runner bytes and its fixed `C:\SkynetVSOutput\result.json` path unchanged while separating two trust domains:

```text
C:\SkynetVSOutput      private guest-local NTFS worker result directory; not a WSB mapping
C:\SkynetVSHostOutput  writable WSB mapping observed by the host; controller-only publication channel
```

R3 must:

- map the host output folder only to `C:\SkynetVSHostOutput`;
- create `C:\SkynetVSOutput` inside the guest and harden it with the existing private-directory SYSTEM + exact worker SID ACL model;
- place `ready.json`, `controller_failure.json`, relayed `result.json`, `terminal_payload.json` and `terminal_signature.bin` only in `C:\SkynetVSHostOutput`;
- let the fixed standard-user worker write only the private local `C:\SkynetVSOutput\result.json`;
- prove the worker token cannot write the host-observed mapping;
- after worker exit, Job closure, worker-SID quiescence and account deletion, validate the exact local result and relay those exact bytes through the trusted LocalSystem controller to the host-observed mapping before terminal signing;
- bind the signed terminal to the exact relayed result bytes and preserve post-exit byte stability;
- never call `SetAccessControl`, `SetAccessRuleProtection`, `SetOwner` or any equivalent DACL mutation on a WSB mapped folder;
- preserve the mapped folder's owner, protection state and complete ACL multiset unchanged.

Locked V1C2C1R3 implementation scope:

```text
M modules/developer/developer_task_execution_compile_ast_controller_worker.py
M modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
M tools/eval_developer_task_execution_compile_ast_controller_worker.py
M tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
```

V1C2C1R3 is a host-only, non-authorizing correction. Its acceptance may compile the exact native helper, parse the fixed PowerShell/WSB payloads, exercise ordinary local NTFS ACL/relay behavior and run targeted/full host checks, but it must not launch Windows Sandbox, consume a claim transaction, claim a runtime lease, run the candidate interpreter or process changed source. The final R3 bytes are independently VERIFIED at `7a73e97aad1bf333bd495f5755fbc14aa0885536`.

**Что не меняется:** V1C2A1, V1C2A2, V1C2B, V1C2C0 and historical V1C2C1/R1/R2 evidence remain immutable; the fixed runner is not modified; stable V1B4 does not move. Roadmap Change 024 preserves the exact seven-file V1C2C2 scope while reopening it only for exact R3 identity rebinding and at most one fresh active attested-pass retry. V1C2C3 remains BLOCKED.

Operational state after Roadmap Change 024:

```text
RC021       COMPLETED / CONSUMED
RC022       COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C1R2    VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R3    VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2      CURRENT / R3 REBIND + ONE FRESH ACTIVE ATTESTED-PASS RETRY
V1C2C3      BLOCKED
candidate SHA-256: 9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

## Roadmap Change 024 — close V1C2C1R3 and reopen exact V1C2C2 R3 composition

**Причина:** exact four-file V1C2C1R3 bytes are committed at `7a73e97aad1bf333bd495f5755fbc14aa0885536` and have complete host-only pre-commit and post-commit evidence. The verified controller now separates the unchanged runner's private guest-local result path from the trusted LocalSystem host-publication mapping, so the mapped-folder ACL defect localized by RC022 is removed without modifying the fixed V1C2A2 runner.

Verified implementation evidence:

```text
implementation commit:                  7a73e97aad1bf333bd495f5755fbc14aa0885536
parent documentation commit:            030a2adba5185a57c3e2f3c56ad3f5d8319652c7
commit message:                          fix: relay compile ast worker result through guest-local output
exact four-file patch SHA-256:           daca5a58e1f62f61a7155fe0f4862322218d05c9f178445d7d1ed5172e9b2ebe
package boundaries:                      28/28
portable evaluator:                      41/41
Windows host-only relay smoke:            3/3
targeted flow:                           completed successfully
isolated full check:                     completed successfully
Runtime Architecture Audit:               9/9
post-commit inventory:                   PASS
post-commit Windows smoke:                3/3
post-commit targeted flow:               41/41 + 3/3 / completed successfully
HEAD == origin/main:                     true
known Sandbox process set:               empty
```

Verified R3 identities:

```text
policy ID:          skynetvs-v1c2c1r3-fixed-system-controller-standard-user-worker-bundle-v4
semantic policy fp: 3683f525c3ef037817e0fda4addccb1f7ed82d7e01c34e9e248494644fa4f3c9
policy bytes SHA:   add4992b096cc4ee50fbcc5a898348995277b4c2facb8a4dc8f370f04dd566ea
bootstrap SHA:      7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d
native helper SHA:  f05437852c9204bcdb0cce70e30989544251070a836f55d748d559f289ddd8e8
controller SHA:     11ccf69016fe0aceead56a9d07ac0f054e99d759207630b114922e4791553827
WSB template SHA:   3de7527400c576ce9ce75ef58f616622ab52a57426811b193270e292d641c281
bundle fingerprint: 62854e85a916f67f24453e3c64c3212a5ae722da8fbc0e275f59c738144dde98
```

**Что меняется:** V1C2C1R3 becomes VERIFIED / HOST-ONLY / NON-AUTHORIZING. V1C2C2 becomes CURRENT only for exact rebinding of the already preserved seven-file candidate SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1` to the verified R3 identities and one fresh active attested-pass retry. The retry must use a fresh host report, snapshot, plan, runtime bundle, runtime lease, claim transaction and Sandbox. A failed retry is terminal for RC024.

**Что не меняется:** the immutable V1C2C2 architecture-slice identity, public API, seven-file scope, fixed V1C2A2 runner, V1C2A1/A2/B/C0 contracts, source/runtime materialization model, post-exit verification model and stable V1B4 tag remain unchanged. RC021 and RC022 remain COMPLETED / CONSUMED. V1C2C3 remains BLOCKED and no syntax-failure or boundary-failure acceptance run is authorized.


## Roadmap Change 025 — failed RC024 active retry requires one exact R3 guest-checkpoint capture

**Причина:** Roadmap Change 024 was consumed exactly once on documentation `HEAD / origin/main 7bff0da8b7b6bca1487389135f16080a797a15c6` and the exact R3-rebound seven-file candidate. The rebind, Python compilation, package boundaries `28/28` and portable evaluator `45/45` passed. The fresh active run consumed one fresh V1C2C0 transaction and one fresh runtime lease, launched one Windows Sandbox and then failed closed before candidate-interpreter execution or changed-source processing. The retained evaluator output contains only the bounded guest-failure issue codes and does not retain the exact R3 controller checkpoint or recursive exception chain needed to choose a production correction.

Exact RC024 evidence binding:

```text
documentation HEAD / origin:          7bff0da8b7b6bca1487389135f16080a797a15c6
parent:                               7a73e97aad1bf333bd495f5755fbc14aa0885536
commit:                               docs: close guest-local relay correction and reopen active composition
original candidate SHA-256:           9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1
R3-rebound candidate SHA-256:         e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc
composition policy fingerprint:       e1fb0fcaa556370dadfcea24371a312c7fa7f0719af33e2359ada51aafcc83eb
composition policy bytes SHA-256:     1265599779b7a94091e6588dc516128ed46dc9cb2679287e84885ff5470f0f04
RC024 consumed marker SHA-256:         829024cc48856caeaf144b5946222ff21a72fd793bcd99f925dd8b761d4c7d64
targeted log SHA-256:                 63c99f1369d08b8a1fc25fdbcb74f0251af9ad042751578342bc7b9d953c7baf
manual acceptance log SHA-256:        e41029414f3430ab2e5e7acc9c91dd960c5a193a55395ca49fa0f7fc2d853012
marker status:                        failed / consumed / must not be rerun
issue codes:
  compile_ast_composition_guest_failure_reported
  compile_ast_composition_guest_failure_artifact
```

The failed run also proved the fail-closed invariants: `candidate_interpreter_executed=false`, no changed-source processing/parsing/compilation, `changed_code_executed=false`, no reusable lease, `execution_authorized=false`, complete Sandbox exit, no forced cleanup, artifact removal and unchanged source/workspace state. Full `check` and Runtime Architecture Audit were not run for this candidate because the active gate failed first.

**Что меняется:** a temporary external diagnostic slice `V1C2C2P2 — R3 Active Guest Checkpoint Capture` is inserted before any further V1C2C2 correction or acceptance attempt. It may perform exactly one fresh active diagnostic run using a new host report, workspace snapshot, plan, runtime bundle, runtime lease, V1C2C0 transaction and Windows Sandbox. Before launch it must persist a permanent consumed marker. During the run the trusted guest controller must atomically publish ordered checkpoint progress and, at the first failure, the full recursive exception chain including concrete type, message, `HResult`, native error code when available, PowerShell invocation position/line and the immediately preceding successful checkpoint.

Required durable checkpoints:

```text
post-authorization static/runtime revalidation
host result path absence
private worker-result root absence
fresh worker account/token creation
host-mapping write-denial probe
host-mapping ACL snapshot revalidation
private result-root creation
private result-root ACL apply and exact re-read
CreateProcessAsUserW return
CREATE_SUSPENDED / no inherited handles
Job limits and assign-before-resume
primary-thread resume
worker wait and exit-code read
Job close
worker-SID quiescence
fresh-account deletion
private result validation
exact result relay
post-relay host-mapping ACL revalidation
private result-root removal
terminal/signature publication or exact failure boundary
Sandbox self-shutdown and host cleanup
```

**Diagnostic scope:** the harness is external and one-shot. It must bind the exact committed V1C2C1R3 identities and exact candidate SHA-256 `e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc`; it must not modify any tracked production or candidate file, widen the production API, modify the fixed V1C2A2 runner, run the normal pipeline, accept V1C2C2, authorize V1C2C3 or create reusable execution authority. Its success means only that exact diagnostic evidence and cleanup were captured.

**Что не меняется:** RC021 and RC022 remain COMPLETED / CONSUMED; RC024 remains FAILED / CONSUMED and must never be rerun. V1C2C1R3 remains VERIFIED / HOST-ONLY / NON-AUTHORIZING. V1C2C2 remains NOT VERIFIED and its exact seven-file candidate is preserved uncommitted. The immutable V1C2C2 architecture identity, public API, fixed V1C2A2 runner, source/runtime materialization model, signature trust model, stable V1B4 tag and all historical verified identities remain unchanged. V1C2C3 remains BLOCKED.

Operational state after Roadmap Change 025:

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

## Roadmap Change 018 — V1C2C2 architecture slice identity and active-composition implementation policy are separate claims

**Причина:** the exact current committed-tree context at `e2621ca5094eb7140323dcecb97b27ab9605ae65` (tree `369f8364df27898cb86a4754147d769ba0070bb0`, archive SHA-256 `7cda253ce704cc028900e7b3d7da59340dd3da6f2b5cb60305cdc00fa4ccb50b`) and the historical V1C2C architecture context with SHA-256 `f5883188e4aa2119c849f2adbc449b73072ede208f742f6ededb42ae783aa08d` preserve `d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484` only as the locked Roadmap Change 016 identity for the V1C2C2 slice. Neither archive contains a canonical V1C2C2 policy JSON, schema or preimage whose SHA-256 can be recomputed to that value. Treating newly created active-composition policy bytes as though they reproduced the unavailable historical preimage would be an unverifiable or false cryptographic claim.

**Что меняется:** `d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484` remains immutable as the V1C2C2 architecture-slice identity. The concrete active-composition implementation introduces the separate canonical policy ID `skynetvs-v1c2c2-active-compile-ast-sandbox-composition-v1`, a reproducible semantic policy fingerprint and an exact canonical policy-document SHA-256 after the implementation bytes are fixed. The policy self-check must bind the Roadmap Change 016 decision, the V1C2C2 slice identity and every accepted V1C2A1/A2/B/C0/C1/runtime/backend identity without claiming that the historical preimage was reconstructed.

**Что не меняется:** the V1C2C0 → V1C2C1 → V1C2C2 → V1C2C3 order, one-fresh-transaction/one-fresh-Sandbox model, LocalSystem-controller/standard-user-worker boundary, Job limits, four-folder mapping, post-exit trust model, stable V1B4 tag and all historical V1B4/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1 identities remain immutable. V1C2C2 remains the only slice allowed to consume the transaction, materialize the retained runtime and selected exact source bytes, launch Sandbox and process changed sources. V1C2C3 remains blocked and owns the three-run pass/syntax/boundary acceptance matrix.

Locked production API:

```python
attest_developer_task_execution_compile_ast_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionCompileAstCompositionReport
```

The public production API accepts no runtime ZIP/path, workspace, manifest, source path/list, executable, argv, environment addition, timeout override, Job limit, WSB setting, signature verifier or fault-injection hook. Portable evaluation may exercise a private test runtime, but V1C2C3 fault injection must not widen the public production API.

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

Acceptance remains fail-closed and requires:

```text
exact Roadmap Change 018 policy self-check        green
package boundaries                                28/28
V1C2A1 / V1C2A2 / V1C2B dependencies             green
V1C2C0 / V1C2C1 dependencies                     green
V1C2C2 portable state/failure gate                green
one active Windows attested-pass composition      green
all known Sandbox processes exited                true
post-exit exact-byte and V1C2B/CNG verification   true
forced cleanup attempted on success               false
private artifacts removed                         true
targeted flow                                      completed successfully
full check                                         completed successfully
Runtime Architecture Audit                         9/9
changed_code_executed                              false
reusable_lease_issued                              false
execution_authorized                               false
```

## Roadmap Change 026 — writable WSB mapping is untrusted transport; signed controller evidence becomes the trust boundary

**Причина:** the one-shot V1C2C2P2 capture authorized by Roadmap Change 025 completed successfully as a diagnostic and is permanently consumed. It bound exact documentation `HEAD / origin/main 7de532e2d4251b1552d509ecf4c86ec742ea693e`, the exact R3-bound seven-file candidate and one fresh process-local transaction/lease/Sandbox run. The guest reached a valid fresh standard-user primary token, then failed at `host_mapping_write_denial` because that token could write the host-observed writable mapping. The previous checkpoint, `worker_account_token_creation`, passed with a non-admin medium-integrity token.

Exact RC025 evidence binding:

```text
documentation HEAD / origin:          7de532e2d4251b1552d509ecf4c86ec742ea693e
parent:                               7bff0da8b7b6bca1487389135f16080a797a15c6
commit:                               docs: record failed R3 active retry and authorize checkpoint capture
R3-bound candidate SHA-256:          e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc
RC025 consumed marker SHA-256:         a918600722e2c00f0e47b550a09e84a1ea5e3ae27d3a2fe0de0940a8b2693c48
full evidence SHA-256:                6a06bf69466d776f30c97b1601ed755521f9badfb6c4be3496acfe85fdf41bb2
summary SHA-256:                      7f898a9235a760e659a2c9a43ee83162ad701f276b52220ac68b3728b8ac0ff0
checkpoint failure SHA-256:           e7283c26c03180d200a06a469853fafff21150068c1243ce52394e24dc3c9213
checkpoint progress SHA-256:          2b5940e6e70a66d613f9562472fe4a8338f9b4a216f6a74b439f3ab3d1dccbcf
marker status:                        completed / consumed
capture status:                       localized_failure
last successful checkpoint:           worker_account_token_creation
failed checkpoint:                    host_mapping_write_denial
exception:                            System.Management.Automation.RuntimeException
HResult:                               0x80131501
message:                               Compile AST worker token can write the host-observed mapping.
controller position:                   C:\SkynetVSInput\controller.ps1:839
```

The measured worker token was primary, non-administrator and medium integrity (`RID 8192`). The capture nevertheless observed successful write capability against `C:\SkynetVSHostOutput`. Therefore, for `traditional_wsb_logoncommand_v1`, a writable mapped folder cannot be treated as a LocalSystem-versus-worker ACL trust boundary. Absence of an explicit worker ACE and a host-only NTFS denial test are not sufficient acceptance evidence for the real mapping.

The failure remained fail-closed: the candidate interpreter did not execute, changed source was not processed, parsed or compiled, changed code was not executed, no reusable lease was issued, `execution_authorized=false`, every Sandbox process exited, no forced cleanup was required, artifacts were removed and the exact seven-file candidate remained unchanged.

**Architecture decision:** insert `V1C2C1R4 — Signed Controller Evidence over Untrusted Writable WSB Transport` before any further V1C2C2 run. The writable host-observed mapping is classified as an untrusted mutable transport after worker creation. Trust moves to the existing ephemeral controller signing key, whose exact public key and `ready` bytes must be pinned by the host before authorization and before the worker account exists.

```text
decision ID:          skynetvs-v1c2c1r4-untrusted-wsb-transport-signed-controller-evidence-lock-v1
decision fingerprint: 8ccd984bb6b92d9ad5a6091168efaf902d3ec6524593c89437acd16ad2cdb955
policy lineage:       skynetvs-v1c2c1r4-fixed-system-controller-standard-user-worker-bundle-v5
```

Canonical decision preimage:

```json
{"architecture_slice":"V1C2C1","backend_id":"traditional_wsb_logoncommand_v1","controller_evidence_key":"ephemeral_controller_ecc_key","decision_id":"skynetvs-v1c2c1r4-untrusted-wsb-transport-signed-controller-evidence-lock-v1","failure_artifact_authority":"signed_controller_terminal_only","fixed_runner_unchanged":true,"host_output_transport":"untrusted_writable_wsb_mapping","implementation_revision":"V1C2C1R4","ready_pinned_before_worker_creation":true,"schema_version":1,"terminal_bindings":["request_id","host_nonce","request_sha256","ready_sha256","authorize_sha256","public_key_sha256","runtime_bundle_fingerprint","runtime_lease_fingerprint","plan_fingerprint","source_manifest_sha256","private_result_sha256","relayed_result_sha256","terminal_status"],"terminal_failure_signed":true,"terminal_success_signed":true,"unsigned_guest_artifacts_authoritative":false,"worker_direct_mapping_write_may_succeed":true,"worker_may_only_cause_dos":true}
```

**Required R4 trust rules:**

1. `C:\SkynetVSHostOutput` remains the single host-observed writable mapping, but its ACL, owner and file contents are never used as proof that the worker lacked write access.
2. `ready.json` and the controller public key are accepted only from the pre-worker phase. The host pins exact `ready` bytes/hash and `public_key_sha256` before it publishes authorization. Later mutations of the mapping cannot replace that pinned trust anchor.
3. The worker continues to write only the unchanged fixed-runner result to guest-local `C:\SkynetVSOutput\result.json`. LocalSystem validates those private bytes and may relay exact bytes into the mapped transport.
4. A successful result is authoritative only when a stable post-exit terminal payload verifies under the pinned controller public key and binds request ID, host nonce, request/ready/authorization hashes, runtime bundle, runtime lease, plan, source manifest, private-result hash, relayed-result hash and terminal status.
5. A controller failure is authoritative only through a separately typed controller-signed terminal failure envelope under the same pinned key. Unsigned `controller_failure.json`, bootstrap-failure files and arbitrary worker-created files are diagnostic hints only and can never satisfy acceptance.
6. Worker pre-creation, overwrite, deletion, replay, substitution or between-read mutation of `result`, terminal, signature or failure artifacts may cause only fail-closed rejection/DoS. It must never produce an accepted transcript.
7. Host acceptance occurs only after every known Sandbox process exits and the exact payload/signature/result bytes remain stable across bounded re-reads.

**R4 tamper matrix:** host-only evidence must model pre-created result, relayed-result substitution, ready mutation after authorization, forged terminal payload, forged signature, request/nonce replay, unsigned failure injection, payload/signature pair swapping and between-read mutation. Every attack must fail closed without Sandbox launch or candidate execution.

**Implementation scope:** R4 may change only the existing four controller-worker bundle/evaluator files:

```text
modules/developer/developer_task_execution_compile_ast_controller_worker.py
modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
tools/eval_developer_task_execution_compile_ast_controller_worker.py
tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
```

The implementation must remove `host_mapping_write_denial` as a required security invariant, retain host-mapping ACL non-mutation as a hygiene invariant, add signed success/failure transport semantics and bind the new architecture decision fingerprint. New implementation bytes, policy fingerprint and bundle fingerprint must be measured from code; this roadmap change does not invent them.

**Что не меняется:** V1C2A1, V1C2A2, V1C2B, V1C2C0 and the fixed runner remain byte-for-byte immutable. The LocalSystem controller, fresh standard-user worker, sanitized environment, no inherited handles, `CREATE_SUSPENDED`, assign-before-resume, Job limits `1 / 512 MiB / 768 MiB`, guest-local private result root, source/runtime materialization, post-exit verification and stable V1B4 tag remain unchanged. V1C2C1R4 is host-only and non-authorizing: no transaction or lease claim, source/runtime materialization, Sandbox launch, interpreter execution or changed-source processing is permitted during its implementation or verification.

The exact seven-file V1C2C2 candidate SHA-256 `e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc` remains uncommitted and must not be modified or committed while R4 is open. A later explicit roadmap change is required to close verified R4, rebind V1C2C2 and authorize any fresh active run. V1C2C3 remains BLOCKED.

Operational state after Roadmap Change 026:

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

## Roadmap Change 027 — close V1C2C1R4 and reopen exact V1C2C2 R4 composition

**Причина:** the exact four-file V1C2C1R4 implementation is committed at `f0a2da9bf96d9010b6df42ae79104e58c15a9838` and has complete pre-commit and post-commit host-only evidence. The correction removes writable-mapping ACL denial from the trust boundary, pins the controller `ready` bytes/public key before worker creation and makes only controller-signed success or typed failure terminal evidence authoritative over the untrusted writable WSB transport. The fixed V1C2A2 runner remains unchanged.

Verified implementation evidence:

```text
implementation commit:                  f0a2da9bf96d9010b6df42ae79104e58c15a9838
parent documentation commit:            8a9c9f93b33eb8d1aadd0773bcaebd5e00b7d9d1
commit message:                          fix: verify signed controller evidence over untrusted WSB transport
exact four-file patch SHA-256:           65596d2f3a5067e770c755979c3ba0562c7f7d2ec486b41598abf13d5a388079
architecture decision fingerprint:       8ccd984bb6b92d9ad5a6091168efaf902d3ec6524593c89437acd16ad2cdb955
package boundaries:                      28/28
portable controller-worker evaluator:    46/46
Windows host-only CNG smoke:               5/5
targeted controller-worker flow:         completed successfully
isolated full check:                     completed successfully
Runtime Architecture Audit:               9/9
post-commit inventory:                   PASS
post-commit Windows smoke:                5/5
post-commit targeted flow:               46/46 + 5/5 / completed successfully
HEAD == origin/main:                     true
known Sandbox process set:               empty
preserved V1C2C2 candidate SHA-256:      e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc
```

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

The verified R4 evidence keeps the writable host-observed mapping explicitly untrusted, preserves its ACL/owner/protection state as hygiene only, requires signed success and signed typed failure evidence, rejects unsigned failure authority and exercises the nine-case tamper matrix fail-closed. No Sandbox was launched during R4 verification, no transaction or runtime lease was claimed, candidate Python did not execute, changed source was not processed, changed code was not executed, no reusable lease was issued and `execution_authorized=false`.

**Что меняется:** V1C2C1R4 becomes VERIFIED / HOST-ONLY / NON-AUTHORIZING. V1C2C2 becomes CURRENT only for exact rebinding of the already preserved seven-file starting candidate SHA-256 `e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc` to the verified R4 identities and exactly one fresh active attested-pass retry. The rebind must preserve the immutable V1C2C2 architecture identity, public production API, seven-file scope and fixed V1C2A2 runner. The retry must use a fresh host report, workspace snapshot, plan, runtime bundle, runtime lease, V1C2C0 transaction and Windows Sandbox. A permanent RC027 consumed marker must be reserved before launch; any failed retry is terminal for RC027 and must not be rerun.

**Что не меняется:** RC021/RC022/RC025 remain COMPLETED / CONSUMED; RC024 remains FAILED / CONSUMED / MUST NOT BE RERUN; V1C2C1R3 remains VERIFIED historical host-only evidence. The stable V1B4 tag, V1C2A1/A2/B/C0 contracts, LocalSystem/standard-user boundary, guest-local result root, Job limits, source/runtime materialization model and post-exit signed-evidence model remain unchanged. V1C2C3 remains BLOCKED; no syntax-failure or boundary-failure acceptance run is authorized by RC027.

Operational state after Roadmap Change 027:

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

## Roadmap Change 028 — failed RC027 retry requires one exact R4 signed-boundary terminal capture

**Причина:** RC027 was consumed exactly once on documentation `HEAD / origin/main a53065dc1b39af8e46720f1592cb4625c830aac3` and the exact R4-rebound seven-file candidate. Pre-active Python compilation, package boundaries `28/28` and portable V1C2C2 evaluator `48/48` passed. The active run consumed one fresh V1C2C0 transaction and runtime lease, launched one fresh Windows Sandbox and failed closed with an authentic stable controller-signed terminal status `compile_ast_boundary_failed`.

Exact RC027 evidence binding:

```text
documentation HEAD / origin:          a53065dc1b39af8e46720f1592cb4625c830aac3
parent:                               f0a2da9bf96d9010b6df42ae79104e58c15a9838
commit:                               docs: close signed WSB transport correction and reopen active composition
starting candidate SHA-256:           e4733892327b53c327f418fcffd129041bab109e56752bb4dd3cd657e72115bc
R4-rebound candidate SHA-256:         dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05
R4-rebound candidate bytes:           225629
composition policy fingerprint:       4062935bd211fccc6e0b5c31cb086f28d32350d0e08bf2027f2f280959d3fa71
composition policy bytes SHA-256:     127afed174dc034cdfd7b4b46471aebb7083055ace702806047df8488ba91e44
RC027 consumed marker SHA-256:        7d3d2b670c878ae9e6b38e0c90f30ba9ca3f20904b03f8a1eab518c239a9a354
targeted log SHA-256:                 8d161de30ad32b431f09d9399c9c35105af4e61e3510a518c84db80498a0822c
marker status:                        failed / consumed / must not be rerun
controller evidence status:           controller_signed_success
controller terminal status:           compile_ast_boundary_failed
controller evidence signature:        valid
legacy terminal signature:            valid
ready/evidence/result stability:      valid
all Sandbox processes exited:         true
forced cleanup attempted:             false
artifacts removed:                     true
changed_code_executed:                false
reusable_lease_issued:                false
execution_authorized:                 false
```

R4's transport/trust correction therefore worked: the host accepted a stable post-exit controller signature under the pinned pre-worker ready/public key. The failure is narrower, at the worker-result boundary. The exact controller defines that boundary as `resultReceived && workerExitCode == 0`; however the retained evaluator log and consumed marker do not preserve the signed terminal fields `worker.exit_code`, `worker.result_received`, worker lifecycle details or `check` counters. The current evidence cannot distinguish a non-zero worker exit from a zero-exit missing/invalid private result or relay rejection. A production correction must not be selected from this ambiguity.

**Что меняется:** insert temporary external diagnostic slice `V1C2C2P3 — R4 Signed Boundary Terminal Capture`. It may perform exactly one fresh diagnostic run using the unchanged exact R4-rebound candidate and one fresh host report, snapshot, plan, runtime bundle, runtime lease, V1C2C0 transaction and Windows Sandbox. A permanent RC028 consumed marker must exist before launch. The harness must copy the exact stable post-exit `terminal_payload.json`, `terminal_signature.bin`, controller-evidence payload and controller-evidence signature before normal artifact cleanup, then prove the copied bytes match the exact hashes verified by the unchanged R4 composition and verify the signatures under the pinned pre-worker controller public key.

The diagnostic may extract only evidence needed to localize the existing boundary: `worker.exit_code`, `worker.result_received`, worker account/token/suspend/Job/resume/wait/quiescence/delete state, result/check counts and exact result-hash presence. It must not alter tracked production or candidate files, modify the fixed V1C2A2 runner, widen the public production API, run the normal pipeline, accept V1C2C2, authorize V1C2C3 or create reusable execution authority. Its success means only that exact authenticated diagnostic evidence and cleanup were captured.

**Что не меняется:** RC021/RC022/RC025 remain COMPLETED / CONSUMED; RC024 and RC027 remain FAILED / CONSUMED / MUST NOT BE RERUN. V1C2C1R4 remains VERIFIED / HOST-ONLY / NON-AUTHORIZING. The exact R4-rebound seven-file candidate SHA-256 `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05`, immutable V1C2C2 architecture identity, public API, fixed V1C2A2 runner, source/runtime materialization model, signed-evidence trust model and stable V1B4 tag remain unchanged. V1C2C2 remains NOT VERIFIED and V1C2C3 remains BLOCKED.

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

### Roadmap Change 029 — V1C2A2 fixed payload launch-order serialization correction

**Причина:** RC028 completed its one-shot authenticated terminal capture. The signed R4 terminal proves the standard-user worker was created suspended, assigned to the Job before resume, resumed exactly once, remained non-admin/medium-integrity, exited, quiesced and was deleted cleanly; controller signatures and post-exit stability are valid. The worker nevertheless exited `70` with `result_received=false` before any source was processed. RC028 marker SHA-256 is `bc116ae32b67f9feb9b218eee6cff16aaf4a64065c330614ef6b92d4e210eefc`; authenticated diagnostic SHA-256 is `a0dce9e18dc2221331ebea30ab0fa9e7b7d8c9820cd1b56f99ace64e07a78ebd`.

Exact pinned-runner inspection proves `main()` converts every exception in `_verify_runtime → request/manifest/payload validation → source parse/compile → result write` into generic exit code `70`. A host-only shadow using the exact V1C2C2 materializer and exact pinned runner bytes reproduced the failure without Sandbox: request/manifest canonical loading and `_validate_request` pass, while `_verify_payload` fails at `_require_fields(launch, _PAYLOAD_LAUNCH_FIELDS)` with `RunnerInputError("fields_invalid")`. Root-cause proof SHA-256: `cb6f0648f09fdbb32f7268fe5f01f78085054da3f4bf44469b074aa83b6298c9`.

The host-side V1C2A2 `_payload_manifest_bytes` uses recursive `json.dumps(..., sort_keys=True, ...)`. The unchanged guest runner intentionally requires launch-object key order `caller_arguments → caller_environment → runtime_executable → runtime_flags → runner_path → shell → working_directory`; recursive sorting instead places `runner_path` before `runtime_executable`/`runtime_flags`. Thus the exact verified host payload bundle and exact verified guest parser are individually deterministic but mutually incompatible at the nested launch-object order boundary.

**Что меняется:** insert `V1C2A2R1 — Fixed Payload Launch-Order Serialization Correction` before V1C2C2. Change only host-side payload-manifest serialization so it preserves the deliberate insertion order already produced by `_launch_contract()`. Preserve exact generated guest runner bytes and SHA-256 `6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9`; preserve V1C2A1 contract-policy bytes/fingerprint, V1C2A2 runner-policy fingerprint, fixed paths, runtime flags, no-shell/no-argv/no-environment policy and all execution prohibitions. Measure and pin the new payload SHA-256 and runner-bundle fingerprint from final bytes.

The implementation scope is exactly two tracked files: `modules/developer/developer_task_execution_compile_ast_runner.py` and `tools/eval_developer_task_execution_compile_ast_runner.py`. The evaluator must add an explicit exact-order regression for all payload object levels, with special coverage for `launch`, and prove the generated runner SHA remains unchanged. Existing Windows bundle smoke and pipeline/package-boundary wiring are verification dependencies only and are not modified. Any scope growth requires another Roadmap Change.

**Что не меняется:** historical V1C2A2 at `b83d2966960a23ebf6930b8ba7ea4bd100cef0b3` remains preserved evidence; V1C2A1/V1C2B/V1C2C0/V1C2C1R4 sources and public APIs remain unchanged; stable V1B4 does not move. RC027 remains FAILED / CONSUMED and RC028 becomes COMPLETED / CONSUMED; neither may be rerun. The exact seven-file V1C2C2 R4 candidate stays uncommitted and byte-for-byte preserved at SHA-256 `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05` while V1C2A2R1 is implemented and verified. No V1C2C2 Sandbox run is authorized by RC029.

Acceptance requires exact guest runner SHA unchanged; corrected payload/bundle identities measured from final bytes; explicit nested field-order regression; package boundaries; unchanged V1C2A1 and V1C2B dependency gates; complete V1C2A2 evaluator; existing Windows bundle smoke without active Sandbox; targeted flow; full `check`; Runtime Architecture Audit; exact two-file implementation commit; post-commit repetition of the host-only payload-order proof; and all active flags false. Commit subject: `fix: preserve compile ast payload launch field order`.

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


### Roadmap Change 030 — V1C2A2R1 downstream identity-cascade closure

**Причина:** final V1C2A2R1 two-file candidate is exact SHA-256 `b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2`. Host-only acceptance already proves guest runner SHA-256 remains `6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9`, corrected payload SHA-256 is `501ed90023f8f8afc75c7676a8acba3d1497334e398f929d0a8d1d96b9ee9249`, corrected runner-bundle fingerprint is `9179cf51614dc3c43dc4189d5dc2835cb4ed3ba781811dbe0050cea4470ee9bf`, portable coverage is `41/41`, package boundaries are green and no Sandbox was launched.

Pipeline wiring proof SHA-256 `17898746de49d8e0e769b44148f668ba407e41a96b654840e4266010096c51bc` proves the targeted `developer_task_execution_compile_ast_runner` flow is exactly package boundaries → V1C2A1 contract → V1C2A2 runner → V1C2A2 Windows bundle smoke. It also proves full `check` contains the portable V1C2C2 composition evaluator but not the active V1C2C2 Windows composition evaluator. The same proof then fails deterministically while importing the preserved V1C2C1R4 controller-worker policy: `RuntimeError("V1C2C1 controller-worker policy self-check failed.")`. No pipeline flow, Sandbox or guest worker was launched.

The failure is an expected pinned-identity cascade, not a new behavioral defect. V1C2C1R4 policy semantics include the V1C2A2 runner `bundle_fingerprint` and `payload_sha256`; its verified policy fingerprint/bytes pins therefore become stale as soon as V1C2A2R1 changes those two identities. The R4 controller script also embeds the controller-worker policy SHA, runner payload SHA and runner bundle fingerprint, so the derived controller SHA and controller-worker bundle fingerprint must be remeasured before downstream imports can be self-consistent. The preserved V1C2C2 policy in turn binds both the runner identities and the controller-worker policy/bundle/controller identities.

**Что меняется:** RC030 resolves the acceptance-cycle contradiction discovered in RC029 without widening the V1C2A2R1 implementation itself. Full `check` and Runtime Architecture Audit are no longer prerequisites for the exact two-file V1C2A2R1 commit because they transitively import deliberately stale downstream pins. V1C2A2R1 may close only after its own host-only/non-authorizing gates pass: Python syntax, package boundaries, V1C2A1/V1C2A2/V1C2B dependency gates, complete V1C2A2 evaluator, existing Windows bundle smoke without Sandbox launch, exact targeted runner flow, exact two-file scope and all active flags false. The commit subject remains `fix: preserve compile ast payload launch field order`.

After that exact R1 commit and post-commit repetition of the same scoped gates, RC030 opens `V1C2C1R5 — V1C2A2R1 Dependency Identity Rebind`, host-only and non-authorizing. Its implementation scope is exactly the existing four controller-worker files: `modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py`, `modules/developer/developer_task_execution_compile_ast_controller_worker.py`, `tools/eval_developer_task_execution_compile_ast_controller_worker.py` and `tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py`. R5 may change only identities transitively derived from the corrected runner payload/bundle. R4 signed-transport semantics, LocalSystem controller, fresh standard-user worker, Job/ACL/lifecycle rules, native-helper behavior, public APIs and architecture decision remain unchanged. All new policy/controller/bundle hashes must be measured from final bytes, never guessed.

After verified R5 is committed, the preserved seven-file V1C2C2 candidate may be rebound in place to the measured V1C2A2R1/R5 identities. That rebind remains non-active: no V1C2C0 claim, runtime lease, source/runtime active materialization, Sandbox launch or guest interpreter run is authorized by RC030. Only after the R1 commit, verified R5 rebind and portable seven-file V1C2C2 rebind are self-consistent must full `check` and Runtime Architecture Audit return green. Any new active V1C2C2 retry requires a later explicit Roadmap Change and a new permanent consumed marker.

**Что не меняется:** RC027 remains FAILED / CONSUMED and RC028 remains COMPLETED / CONSUMED; neither may ever be rerun. Stable V1B4 does not move. Historical V1C2A2 and verified V1C2C1R4 evidence remain immutable historical facts. Until R1 is committed and downstream rebinding is completed, the exact seven-file R4 candidate stays byte-for-byte `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05`. V1C2C3 remains BLOCKED.

Operational state after Roadmap Change 030:

```text
RC027       FAILED / CONSUMED / MUST NOT BE RERUN
RC028       COMPLETED / CONSUMED / MUST NOT BE RERUN
V1C2A2R1   CURRENT / EXACT TWO-FILE PRE-COMMIT CANDIDATE / HOST-ONLY
V1C2C1R4   VERIFIED / HISTORICAL / DOWNSTREAM PINS STALE AGAINST R1
V1C2C1R5   PLANNED / BLOCKED UNTIL V1C2A2R1 COMMIT
V1C2C2      BLOCKED / EXACT R4 CANDIDATE PRESERVED / AWAIT R1 + R5 REBIND
V1C2C3      BLOCKED
V1C2A2R1 patch SHA-256: b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2
R4 candidate SHA-256: dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

### Roadmap Change 031 — V1C2B verifier identity rebind precedes controller-worker R5

**Причина:** scoped V1C2A2R1 pre-commit acceptance on documentation HEAD `146b2133c1a05d983e398d6139cd6383f7de1b5e` proved package boundaries `28/28`, V1C2A1 `45/45` and corrected V1C2A2R1 `41/41` green, but V1C2B failed `19/44` before Windows bundle smoke, targeted flow, commit, pipeline or Sandbox launch. Historical V1C2B policy fingerprint `cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf` recomputes as `d7fc8c5011e6dd353202ebd04567d1e7f59d7af523c8c9b20769afc6b38d45a2` against corrected V1C2A2R1 runner payload/bundle identities. The verifier then correctly rejects its trusted-bundle pin; the other failed cases are downstream consequences of that failed pin report, not nineteen independent defects.

Historical V1C2B is explicitly host-only/non-authorizing and binds exact V1C2A2 policy/runner/payload identities. RC030 therefore contained a second acceptance cycle: it said R1 scoped gates must avoid stale downstream imports but still listed V1C2B as an R1 prerequisite. V1C2B cannot remain unchanged and green while also cryptographically pinning identities that R1 intentionally changes.

**Что меняется:** remove V1C2B from V1C2A2R1 pre/post-commit scoped gates. R1 may close after Python syntax, package boundaries, V1C2A1, V1C2A2R1 `41/41`, existing V1C2A2 Windows bundle smoke, exact targeted `developer_task_execution_compile_ast_runner` flow, exact two-file patch/commit identity and empty Sandbox process set are green. Full `check`, Runtime Architecture Audit and all stale downstream verifier/controller/composition imports remain deferred.

After exact R1 commit, insert `V1C2BR1 — V1C2A2R1 Dependency Identity Rebind` before `V1C2C1R5`. BR1 is host-only and non-authorizing. It may change only verifier identities transitively derived from committed R1 and must preserve V1C2B public APIs, transcript/hash-chain semantics, Windows CNG ECDSA-P256 verification, fail-closed behavior and every execution prohibition. Before mutation, a host-only source audit must lock the exact changed subset inside the existing four-file verifier boundary: `modules/developer/developer_task_execution_compile_ast_verifier_policy.py`, `modules/developer/developer_task_execution_compile_ast_verifier.py`, `tools/eval_developer_task_execution_compile_ast_verifier.py`, `tools/eval_developer_task_execution_compile_ast_verifier_windows.py`. Package-boundary and pipeline registries are not modified by BR1. New verifier identities are measured from final bytes, never guessed.

BR1 acceptance requires committed R1 identities, package boundaries, V1C2A1, V1C2A2R1, V1C2B portable `44/44`, existing real-Windows CNG smoke `1/1`, exact targeted `developer_task_execution_compile_ast_verifier` flow, exact locked rebind scope and all active flags false. No Sandbox, runtime-lease claim, candidate interpreter, changed-source processing or changed-code execution belongs to BR1.

Only after verified BR1 may `V1C2C1R5` rebind R4 controller-worker identities. After verified R5, the preserved seven-file V1C2C2 candidate must be rebound to committed R1/BR1/R5 identities. Full `check` and Runtime Architecture Audit return only after that portable cascade is self-consistent. RC031 authorizes no active V1C2C2 retry.

Operational state after Roadmap Change 031:

```text
V1C2A2R1   CURRENT / EXACT TWO-FILE PRE-COMMIT CANDIDATE / HOST-ONLY
V1C2BR1    PLANNED / BLOCKED UNTIL V1C2A2R1 COMMIT
V1C2C1R5   PLANNED / BLOCKED UNTIL V1C2BR1 VERIFIED
V1C2C2      BLOCKED / R4 CANDIDATE PRESERVED / AWAIT R1 + BR1 + R5 REBIND
V1C2C3      BLOCKED
R1 patch SHA-256: b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2
R4 candidate SHA-256: dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05
V1C2B historical policy fp: cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf
V1C2B R1-dependent recomputation: d7fc8c5011e6dd353202ebd04567d1e7f59d7af523c8c9b20769afc6b38d45a2
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

### Roadmap Change 032 — V1C2A2R1 Windows-smoke expectation joins R1 scope

**Причина:** after RC031 documentation HEAD `46ce8f1c3263d78133ae0e6b649f4f0c9c89671f`, the R1-independent Windows bundle smoke fails `0/1` only because its expected payload/bundle identities remain historical. Actual corrected payload SHA-256 is `501ed90023f8f8afc75c7676a8acba3d1497334e398f929d0a8d1d96b9ee9249`; actual corrected bundle fingerprint is `9179cf51614dc3c43dc4189d5dc2835cb4ed3ba781811dbe0050cea4470ee9bf`; guest runner SHA remains `6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9`. The smoke reports all active flags false and launches no Sandbox.

**Что меняется:** widen V1C2A2R1 from exact two-file to exact three-file scope by adding only `tools/eval_developer_task_execution_compile_ast_runner_windows.py`. That file may rebind only its expected corrected payload/bundle identities and directly necessary test bookkeeping. Production semantics and runner bytes do not change. Historical two-file patch SHA `b7024d18c8d000271240bf3a662dde612260de330b0c3ae1ab540ef813e18eb2` remains pre-RC032 evidence; acceptance must measure a new exact three-file candidate SHA.

**Acceptance:** syntax over all three files; package boundaries; V1C2A1 `45/45`; V1C2A2R1 `41/41`; Windows bundle smoke `1/1`; exact targeted runner flow; exact three-file diff; preserved seven-file V1C2C2 candidate; empty Sandbox process set. Commit exactly the three R1 files with subject `fix: preserve compile ast payload launch field order`, push and repeat the same gates post-commit. V1C2B/full `check`/Runtime Architecture Audit/downstream imports/active composition remain deferred to BR1/R5/portable V1C2C2 rebind.

Operational state after Roadmap Change 032:

```text
V1C2A2R1   CURRENT / EXACT THREE-FILE PRE-COMMIT CANDIDATE / HOST-ONLY
V1C2BR1    PLANNED / BLOCKED UNTIL V1C2A2R1 COMMIT
V1C2C1R5   PLANNED / BLOCKED UNTIL V1C2BR1 VERIFIED
V1C2C2     BLOCKED / AWAIT R1 + BR1 + R5 REBIND
V1C2C3     BLOCKED
```


### Roadmap Change 033 — rebound V1C2C2 closure authorizes one fresh active attested-pass retry

**Причина:** the exact V1C2A2R1 -> V1C2BR1 -> V1C2C1R5 downstream identity cascade is now complete on committed code, and the preserved seven-file V1C2C2 implementation has been rebound in place to those committed identities without architecture or public-API growth. The rebound candidate is exact `225629` Git-diff bytes with SHA-256 `296d1c94a884f065d27e65cb312618576c8f7ce4e60c7a3ee2fa84c7f4a2ff2e`, semantic composition-policy fingerprint `b4d254963b38caaf1031e85d304eda186eeb784c46ce42af97f0eb3c8c215976` and exact policy-document SHA-256 `fb34f1e7d41f8c5f2ef79a39b8a833c7eb4981769bf1b894f14e7b19b7eddd16`.

Committed dependency closure is exact:

```text
V1C2A2R1 commit:                  13c136803982871be4df28229cf4988e598b9cf3
guest runner SHA-256:             6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9
corrected payload SHA-256:        501ed90023f8f8afc75c7676a8acba3d1497334e398f929d0a8d1d96b9ee9249
runner bundle fingerprint:        9179cf51614dc3c43dc4189d5dc2835cb4ed3ba781811dbe0050cea4470ee9bf

V1C2BR1 commit:                   1280fc816316255762b913fe2fd085738c1a8b83
verifier policy fingerprint:      d7fc8c5011e6dd353202ebd04567d1e7f59d7af523c8c9b20769afc6b38d45a2

V1C2C1R5 commit:                  b0bf07015b001499c48c8fc334472993cc83bdb1
controller-worker policy fp:      2dc6aaba3384a072524053a90adbdbf394332a8d83c10b6863dd62f1a6365f2f
controller-worker policy SHA:     04102be389be5624c34fcc12c88d998c57840633e9f349d1e59fc0ba03e1eb17
controller SHA-256:               75ebefd7c3d6fa06f9176ba4f1c75424940b7e92e3f2cfb4901c656da4326653
controller-worker bundle fp:      6e09456eb4d0c76eef136dd7f1d0c40510932dba6887f738529d19481fb5ead0
```

Host-only closure after the portable rebind is green: seven-file AST parsing passed, package boundaries passed `28/28`, portable V1C2C2 coverage passed `48/48`, full `check` completed successfully and Runtime Architecture Audit passed `9/9`. Full `check` contains exactly one portable V1C2C2 evaluator and no active Windows V1C2C2 evaluator. No V1C2C0 transaction or runtime lease was claimed, no Sandbox was launched and no real candidate interpreter was executed during the rebind/closure cascade. The global-closure report SHA-256 is `ef530ff345870f86fdb2ec0878476507181c2e58c4fd509c35226b39b9ff8b23`; its full-check log SHA-256 is `930efb0fb69146d00660dd03d889d4588395a526a73d5ff1b44215883532af96`. The final roadmap-transition source audit is SHA-256 `64f021d309f7cb9507d8b79d3051fd9ca64beba9663ecf6bc91818e50bbf93b8`.

**Что меняется:** RC033 supersedes the earlier operational labels that left V1C2C2 blocked only for the R1/BR1/R5 cascade. V1C2C2 becomes CURRENT solely for exactly one fresh active attested-pass attempt against the exact rebound candidate above. The attempt must use one fresh host report, one fresh workspace snapshot and compile/AST plan, one exact rebuilt runtime capability and fresh runtime lease, one fresh V1C2C0 claim transaction and one fresh Windows Sandbox instance. No past transaction, lease, Sandbox or active report is reusable authority.

Before the first active launch, a permanent RC033 one-shot marker must be persisted. Its path/format must first be confirmed against the current evaluator and historical marker convention by a read-only host audit. The marker must bind at minimum the committed RC033 documentation HEAD, exact candidate SHA-256, composition policy fingerprint and policy-document SHA-256, committed R1/BR1/R5 identities and one-shot attempt identity. Once that marker reserves the attempt, RC033 is consumed regardless of success or failure. It must never be deleted or reset to manufacture another retry.

**Что не меняется:** RC024 and RC027 remain FAILED / CONSUMED / MUST NOT BE RERUN. RC021/RC022/RC025/RC028 remain COMPLETED / CONSUMED. Stable `skynet-trusted-runtime-v1b4` remains at `91d8c37fc4afe7ef138e36063e7bc22014da8a2c`. The immutable V1C2C2 architecture-slice identity, active-composition architecture decision, public production API, exact seven-file implementation scope, fixed guest-runner bytes, LocalSystem-controller/standard-user-worker boundary, Job limits, source/runtime materialization model and post-exit signed-evidence trust model remain unchanged. The seven-file candidate remains uncommitted before active acceptance. V1C2C3 remains BLOCKED; RC033 does not authorize the V1C2C3 syntax-failure or boundary-failure acceptance runs.

The one active attested-pass attempt succeeds only if the real Windows report establishes the accepted pass boundary, including:

```text
ok=true
status=active_compile_ast_attested_passed
terminal_status=compile_ast_attested_passed
boundary_ok=true
check_passed=true
signature_valid=true
result_verified=true
relayed_result_hash_match=true

claim_transaction_consumed=true
runtime_lease_claimed=true
sandbox_launched=true
candidate_interpreter_executed=true
changed_source_processed=true
changed_source_ast_parsed=true
changed_source_compiled=true

changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false

all known Sandbox processes exited=true
forced_cleanup_attempted=false
artifacts_removed=true
```

Controller-signed terminal evidence, legacy terminal verification, ready/evidence/result stability and private-to-relayed-result hash binding must remain valid under the pinned pre-worker controller public key. No unsigned writable-mapping artifact may become authority.

A failed active attempt is terminal for RC033: preserve the failed/consumed marker and exact evidence, keep the seven-file candidate uncommitted, do not rerun, and stop for another explicit Roadmap Change.

A successful active attempt consumes RC033 as PASSED evidence but does not itself commit code. After exact evidence review, the same seven-file bytes may become eligible for one exact implementation commit; no second active acceptance run is authorized merely because the first passed. The intended implementation commit subject is `feat: add active compile ast sandbox composition`. V1C2C3 remains separately blocked after V1C2C2 closure.

Operational state after Roadmap Change 033:

```text
V1C2A2R1   VERIFIED / COMMITTED
V1C2BR1    VERIFIED / COMMITTED / HOST-ONLY / NON-AUTHORIZING
V1C2C1R5   VERIFIED / COMMITTED / HOST-ONLY / NON-AUTHORIZING

RC027       FAILED / CONSUMED / MUST NOT BE RERUN
RC028       COMPLETED / CONSUMED / MUST NOT BE RERUN
RC033       CURRENT / ONE FRESH ACTIVE ATTESTED-PASS RETRY ONLY

V1C2C2      CURRENT / EXACT REBOUND CANDIDATE / ONE FRESH ACTIVE RETRY ONLY
candidate bytes:                       225629
candidate SHA-256:                     296d1c94a884f065d27e65cb312618576c8f7ce4e60c7a3ee2fa84c7f4a2ff2e
composition policy fingerprint:        b4d254963b38caaf1031e85d304eda186eeb784c46ce42af97f0eb3c8c215976
composition policy-document SHA-256:   fb34f1e7d41f8c5f2ef79a39b8a833c7eb4981769bf1b894f14e7b19b7eddd16
candidate commit:                      NOT YET AUTHORIZED / UNCOMMITTED
RC033 consumed marker:                 NOT YET RESERVED
active RC033 attempt:                  NOT YET RUN
V1C2C3:                                BLOCKED
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

Next exact action after the RC033 documentation commit is a READ-ONLY / HOST-ONLY audit of the exact current Windows V1C2C2 evaluator and historical consumed-marker convention. That audit must lock the marker path/schema, exact one-shot harness topology, exact expected Windows case count and exact evidence retained on success/failure before any marker is created or Sandbox is launched.

## Roadmap Change 015 — Compile/AST contract, fixed runner, verifier and active Sandbox composition are separate boundaries

**Причина:** V1C1B now holds exact selected source bytes in a process-local one-shot plan, but the first interpreter run adds four independent failure domains: canonical changed-source documents, fixed guest runner behavior, host-side signature/transcript verification and live Windows Sandbox lifecycle/resource isolation. A syntax error is a valid check outcome and must not be confused with an invalid signature or broken isolation boundary. Original repository paths also cannot safely become guest filesystem paths because their length and directory structure are unrelated to the fixed guest mount root.

**Что меняется:** V1C2 is split into V1C2A1 canonical request/result/terminal contract, V1C2A2 fixed guest runner/payload, V1C2B signed transcript verifier and V1C2C active composition. Original paths remain signed metadata; exact source bytes are materialized as flat deterministic `source-{ordinal:04d}.py` files and diagnostics use `skynetvs://changed/<path>`. The fixed runner performs strict UTF-8 revalidation, `ast.parse` and `compile` under CPython 3.13.15, then discards every code object without `exec`, `eval`, import execution or bytecode write. Signed evidence separates `transcript_verified` from `check_passed`, so a contract-valid syntax failure is authentic evidence. V1C2C claims the V1C1B plan first and the fresh V1B4D runtime lease second, uses one fresh Sandbox, one standard-user worker and Job limits, and accepts output only after all known Sandbox processes exit and exact post-exit artifacts remain stable.

**Что не меняется:** source import statements may be parsed/compiled but are never executed; the workspace, `.git`, host `.venv` and host Git are never mapped; guest network, dependencies, `python_module`, `pipeline`, arbitrary shell, commit, merge, push and promotion remain blocked. Every result keeps `changed_code_executed=false`, `execution_authorized=false` and `reusable_lease_issued=false`.

Locked identity:

```text
decision ID:          skynetvs-v1c2-compile-ast-active-boundary-architecture-lock-v1
decision fingerprint: 5382249191bcc8388d6b44862cabe7c24a586a6628814266461c0830e7dec08c
V1C2A1 policy ID:     skynetvs-v1c2a1-compile-ast-contract-cpython-3.13.15-v1
V1C2A1 fingerprint:   a3e7d50e92de8aa0799953874a71ce60b2d141e52791282e5fd38814aa9507bf
```

## Roadmap Change 014 — Full result-tree snapshot and compile/AST plan are separate process-local capabilities

**Причина:** `DeveloperTaskPatchApplyReport.result_tree` is an immutable Git object identity, while the applied worktree is still mutable filesystem state. The exact HEAD measurement at `90d2bd5` proves that the current result tree is small enough for a bounded in-memory exact-byte snapshot, but the 5 MiB patch limit cannot bound a compressed Git binary patch's expanded result. A generic serializable plan or a direct workspace mapping would also allow stale bytes, caller-controlled paths or cross-run reuse to become execution input.

**Что меняется:** V1C1 is split into V1C1A `Canonical Patched Workspace Snapshot Bundle` and V1C1B `Typed Compile/AST Plan Capability`; V1C2 is split into guest contract/runner, signed verifier and active composition. V1C1A rebuilds exact bytes only from the verified applied `result_tree`, independently SHA-256-binds every regular blob, enforces fixed full-tree/path/mode limits and issues a process-local, non-copyable, non-pickleable, single-use 300-second snapshot capability. V1C1B atomically consumes that snapshot and derives the fixed `compile_ast_changed_python_v1` plan only from changed `.py` paths still present in the result tree. It retains only selected exact source bytes under the existing 2 MiB/file and 8 MiB/total limits. The future V1C2 active composition claims the plan capability first and a fresh V1B4D runtime lease second; either failed claim is terminal.

**Что не меняется:** V1C1 accepts no runtime lease, launches no Sandbox, runs no interpreter, imports no workspace module and performs no network, resolution or install. The original workspace and `.git` are never mapped. `python_module`, `pipeline`, arbitrary shell, guest Git/network, top-level execution, commit, merge, push and promotion remain blocked; serialized reports expose no source bytes or reusable token and keep `execution_authorized=false`.

## Roadmap Change 013 — External source authority is an exact metadata-and-bytes contract, never resolver output or mutable latest state

**Причина:** V1C0B1 at `e090f63` now proves the exact committed dependency declarations and canonical host Python/pip, Git and PowerShell observations, but those observations intentionally grant no source authority. A resolver result, an unversioned `latest` endpoint, a host cache or an installed toolchain can change independently of the protected repository and would reintroduce dependency confusion, ABI drift, cache poisoning and host fallback.

**Что меняется:** V1C0B2 locks the external source classes without downloading or authorizing artifacts. Python candidate metadata is accepted only from the PyPI Simple Repository API JSON v1 with a supported `1.x` response and at least API `1.4`; exact wheel bytes must be the `files.pythonhosted.org` artifact URLs named by that response and must match filename, size and SHA-256. Yanked, pre-release, source-distribution, local-build, direct-URL, extra-index and host-cache fallback are rejected by default. A version-pinned resolver may propose a CPython 3.13 AMD64 / `win_amd64` wheel closure, but it is never authority: the final direct and transitive manifest is independently rebuilt from verified metadata and bytes. PyPI provenance/attestation evidence is captured and cryptographically verified when present, but it proves publishing identity rather than package safety and its absence is recorded rather than silently invented. Portable Git authority is limited to an immutable Git for Windows release tag plus the standard `MinGit-<version>-64-bit.zip` asset, release-published SHA-256, exact archive bytes and a deterministic extracted-tree manifest; `latest`, BusyBox MinGit, PortableGit, installers and host Git remain non-authoritative. Network access exists only in a future dedicated host acquisition gate with exact origin/redirect allowlists and no inherited credentials, indexes or proxy variables.

**Что не меняется:** V1C0B2 is a documentation/source-policy lock only. It performs no resolution, download, install, extraction, Sandbox launch, lease claim, candidate interpreter execution or changed-code execution. Exact Python versions/wheels remain V1C3A work; exact MinGit archive/tree pinning remains V1C3C work; V1C1/V1C2 remain dependency-free snapshot/compile boundaries; `python_module`, `pipeline`, arbitrary shell, commit, merge, push and promotion remain blocked; every runtime report remains non-reusable and `execution_authorized=false`.

## Roadmap Change 012 — Host observation and external source authority are separate V1C0B boundaries

**Причина:** V1C0A at `b039ce1` now proves the exact committed dependency declarations, import/process topology and pipeline shape, but it intentionally does not prove where future Python wheels or Git bytes come from. The installed host `.venv`, host Git tree and host PowerShell are mutable observation surfaces. Treating host observation as source authority would silently reintroduce host fallback and ABI/configuration drift.

**Что меняется:** V1C0B is split into V1C0B1 `Canonical Host Toolchain Observation Gate` and V1C0B2 `External Source Authority Selection Lock`. V1C0B1 produces a canonical non-authorizing report over exact committed dependency declarations plus host Python/pip, Git distribution and fixed Windows PowerShell identities. V1C0B2 locks source classes independently: official PyPI APIs and exact PyPI-hosted wheel bytes for the future CPython 3.13 AMD64 dependency closure, and the official 64-bit Git for Windows MinGit release archive for the future portable Git bundle. Exact package versions, release asset names and artifact hashes remain future V1C3A/V1C3C provenance evidence, not V1C0B1 outputs.

**Что не меняется:** no host installation becomes authority; no package or Git artifact is downloaded, installed, resolved or copied during V1C0B1; source distributions and local wheel builds remain blocked by default; runtime network/resolver access, Sandbox launch, lease claim, candidate interpreter execution, changed-code execution, `python_module`, `pipeline`, arbitrary shell, commit, merge, push and promotion remain forbidden; every serialized report keeps `execution_authorized=false` and `reusable_lease_issued=false`.

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

**Статус:** V1B4A–V1B4D VERIFIED; V1B4 COMPLETE. V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2/V1C2C1R3/V1C2C1R4 VERIFIED; V1C0B2 and V1C1/V1C2/V1C2C architecture LOCKED; RC021/RC022/RC025 diagnostics COMPLETED / CONSUMED; RC024 FAILED / CONSUMED; RC027 CURRENT for exact V1C2C2 R4 rebind plus one fresh active retry; V1C2C3 BLOCKED; changed-code execution remains false.

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

**Статус:** V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2/V1C2C1R3/V1C2C1R4 are VERIFIED through `f0a2da9`; V1C0B2 external source authority and V1C1/V1C2/V1C2C architecture are LOCKED; RC021/RC022/RC025 diagnostics are COMPLETED / CONSUMED; RC024 is FAILED / CONSUMED; RC027 is CURRENT for exact V1C2C2 R4 rebind plus one fresh active retry; V1C2C3 remains BLOCKED; changed-code execution remains false.

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

The original V1C context collector captured exact bytes only for `requirements.txt`. V1C0A closed that gap and now binds all three tracked declarations: `requirements.txt`, `requirements-train.txt` and `requirements-whisper.txt`.

The current `check` flow is not guest-safe as one unit. It includes a real CoreAudio Windows smoke and Git-dependent Developer Safety Kernel evals, launches child Python processes through `sys.executable`, and inherits the host environment plus existing `PYTHONPATH`. Its current behavior is observation data only.

V1C0A and V1C0B1 production/post-commit evidence are now closed:

```text
V1C0A code closure:                 b039ce1 feat: add canonical executable check environment inventory
V1C0B1 code closure:                e090f63 feat: add canonical host toolchain observation
V1C0A portable evaluator:           27/27
V1C0B1 portable evaluator:          26/26
package boundaries:                 28/28
pre-commit full check:               completed successfully
V1C0A post-commit Windows smoke:     1/1
V1C0B1 post-commit Windows smoke:    1/1
tracked files / Python files:        252 / 234
Python bytes:                        3,257,957
pipeline flows / all steps:          91 / 445
check steps:                         86
process-launch call sites:           38
host-sensitive files:                25
inventory fingerprint:               574cdc81c154c04ade6e26aec520cac243ddf5e15f1780037c57bf3ae88d1956
observation fingerprint:             aa2f63f41523480f4e423d57e15e02883b70709e34e1dd108c72e977b36e6035
host Python / pip:                    3.12.10 / 25.3
host Git / tree:                      2.45.1.windows.1 / 6356 files / 419125157 bytes
host PowerShell:                      5.1.26100.9168
source_authority_selected:            false
execution_authorized:                 false
reusable_lease_issued:                false
```

The exact committed dependency declarations remain unchanged and are independently SHA-256 bound: `requirements.txt`, `requirements-train.txt` and `requirements-whisper.txt`. V1C0B1 proves only host observation; host `.venv`, host Git and host PowerShell remain non-authoritative.

#### Final V1C decomposition

```text
V1C0A  Canonical Executable Check Inventory Gate             VERIFIED
V1C0B1 Canonical Host Toolchain Observation Gate             VERIFIED
V1C0B2 External Source Authority Selection Lock              LOCKED
V1C1A  Canonical Patched Workspace Snapshot Bundle           VERIFIED
V1C1B  Typed Compile/AST Plan Capability                     VERIFIED
V1C2A1 Canonical Compile/AST Request, Result and Terminal Contract VERIFIED
V1C2A2 Fixed Guest Runner and Payload Bundle                 VERIFIED / NON-AUTHORIZING
V1C2B  Signed Compile/AST Transcript Verifier                VERIFIED / NON-AUTHORIZING
V1C2C0 Process-Local Plan/Runtime Claim Transaction          VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C1 Fixed SYSTEM Controller and Worker Payload Bundle       VERIFIED / HISTORICAL HOST-ONLY BUNDLE
V1C2C1R1 Transcript Policy-Hash Integration Correction         VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C1R2 Shared Output ACL Preservation Correction              VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R3 Guest-Local Worker Result Relay Correction             VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R4 Signed Controller Evidence over Untrusted WSB Transport     VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2P2 R3 Active Guest Checkpoint Capture                   COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C2 Active Compile/AST Sandbox Composition                  CURRENT / R4 REBIND + ONE FRESH ACTIVE RETRY ONLY
V1C2C3 Live Pass/Syntax/Boundary Acceptance                  BLOCKED / PRO REQUIRED
V1C3A  Python Dependency Source Provenance                   PLANNED
V1C3B  Deterministic Python Check Dependency Bundle          PLANNED
V1C3C  Portable Git Source Provenance and Bundle             PLANNED
V1C4A  Changed-Code Execution Contract and Guest Payload     PLANNED
V1C4B  Signed Changed-Code Transcript Verifier               PLANNED
V1C5   Active Sandboxed python_module Check                  BLOCKED
V1C6   Active Sandboxed Guest-Safe Pipeline Check            BLOCKED
V1C7   Composite Typed Check Runner and Result Evidence      BLOCKED
```

`V1C0B1` observations are not authority. V1C0B2 now locks the reviewed source classes and acquisition semantics, but exact versions, source bytes, hashes, licenses, architecture compatibility and deterministic derived trees must still be proven independently in V1C3A/V1C3C before any dependency or external tool enters a guest boundary.

#### Locked V1C1 snapshot/plan architecture

The exact context archive `SkynetVS_V1C1_Snapshot_Plan_Context_20260815_105418.zip` was verified as `49/49` payloads with SHA-256 `fdc0ea63f8765b97c63c68d55c85bbb0cce6994bd0f0cc83036cb6febbf37d0d`. The committed tree at `90d2bd5` measured:

```text
files / total bytes:          252 / 3,528,329
Python files / bytes:         234 / 3,257,957
largest file / Python file:   83,256 / 71,872 bytes
Git modes:                    252 x 100644
non-blob / NUL files:         0 / 0
Python encodings:             234 x UTF-8
line endings:                 246 LF / 6 none
max path / segment / depth:   76 / 67 / 3
unsafe paths / collisions:    0 / 0
full tree manifest SHA-256:   b1e82bf0a3fb8a901c0ac37825d74c8de426f34d02f67d0b05a710be2b4962ba
```

Locked decision identity:

```text
decision ID:          skynetvs-v1c1-snapshot-plan-architecture-lock-v1
decision fingerprint: 20f26ef8728a77ea87b22d791ebf4da5940312c48e589cf6c17a89765428ad30
snapshot policy:      601c727e9b725f1f868a144fa7b975bbb7a35a878c74c2d25bda0a7677a6cd55
plan policy:          f017f401254647002347802c5deba6397bdddf27eaa08d02640dc8389fe80865
```

V1C1A locks `exact_git_result_tree_snapshot_v1`: regular `100644` blobs only, maximum `4096` files, `8 MiB` per blob, `16 MiB` total, `4 MiB` canonical manifest, paths `240/120/32`, NFC and Windows-safe collision rules. Exact bytes remain private in a process-local, non-serializable, single-use capability with a `300`-second `time.monotonic_ns()` TTL and `32`-byte secret. Arbitrary bounded binary blobs may be retained in the full snapshot but are never selectable by the initial compile/AST plan.

V1C1B atomically consumes one snapshot and derives only `compile_ast_changed_python_v1`. It selects `1..20` changed `.py` paths still present in the result tree, with `100644` mode, UTF-8, LF or empty input, no NUL, `2 MiB` per file and `8 MiB` total. Deleted Python and changed non-Python paths are evidence only. Caller-controlled executable, argv, path list, environment, encoding, limits, module, flow or runner are forbidden. V1C1B is also process-local, single-use and `300` seconds.

V1C1 accepts no V1B4D lease. After plan issuance, the future active V1C2C call claims the plan first and a fresh runtime lease second. The original workspace and `.git` are never mapped; only fixed runtime/runner/request/manifest and selected exact source bytes may cross read-only.

#### V1C1A verification closure

Implementation commit `7b17461` (`feat: add canonical patched workspace snapshot`) contains exactly four new V1C1A files plus `tools/eval_package_boundaries.py` and `tools/pipeline.py`. Pre-commit evidence passed the V1C1A portable adversarial gate `37/37`, real Windows snapshot smoke `1/1` and the full `check` flow. Post-commit Windows evidence at exact HEAD `7b174610e6dde4e1e28a6ae5fb1f357ac0ad93e2` re-established the committed-tree inventory and V1C1A snapshot boundary:

```text
tracked files / Python files:   256 / 238
Python bytes:                   3,371,260
pipeline flows / total steps:   92 / 459
pipeline check steps:            87
process-launch call sites:        40
host-sensitive files:             26
Python tree fingerprint:         05f3e251c1a483e24bb833537a3525ff8052e39cd8da6d68bf1977b287296a0b
inventory fingerprint:           1d6df3788467909e758c172bee1289ac0fda65915c1646304b257e69ae17f96b
V1C0A Windows smoke:             1/1
V1C1A Windows smoke:             1/1
```

The real V1C1A Windows smoke reissued and atomically claimed `exact_git_result_tree_snapshot_v1`, preserved exact `module.py` bytes `value = 2\n`, proved the deleted path absent, and kept source/workspace index, status and object state unchanged. `repository_mutated`, network/download/install, Sandbox, runtime-lease issue/claim, candidate interpreter, changed-code execution, reusable lease and `execution_authorized` all remained `false`. V1C1A is therefore VERIFIED; it grants only a one-shot process-local exact-byte snapshot capability to V1C1B and still grants no execution authority.

#### Locked toolchain decisions

- The host `.venv` is never copied, mapped or treated as trusted input. It is CPython 3.12 state while V1B4 is CPython 3.13.15, contains mutable resolver/install state and includes ABI-specific native extensions.
- Runtime `pip`, `ensurepip`, package resolution, download, sdist build and network acquisition are forbidden.
- Future Python dependency source authority is the PyPI Simple Repository API JSON v1 (`application/vnd.pypi.simple.v1+json`) with a supported `1.x` response at API `1.4` or newer, plus the exact `files.pythonhosted.org` wheel bytes named by that response. The target is CPython 3.13 AMD64 / `win_amd64`; every direct and transitive file must be bound to normalized project name, exact version, filename, size, SHA-256, `Requires-Python`, yanked state and exact wheel compatibility before offline bundle derivation.
- A version-pinned resolver is only a candidate generator. Final closure authority is an independently verified canonical source manifest. No extra index, direct URL, local cache authority, pre-release, yanked file, sdist or local build is accepted by default.
- PyPI core-metadata hashes are verified when published. Provenance/attestation is fetched and cryptographically verified when present, but is supplemental origin evidence rather than proof of package safety; absence is explicit evidence, not an implicit pass or fabricated signature.
- Absence of a compatible wheel blocks the affected check group. It never falls back to the host `.venv`, a source distribution or a local build.
- Future portable Git source authority is an immutable official Git for Windows release tag plus the standard 64-bit MinGit ZIP, release-published SHA-256, exact archive bytes, safe extraction policy and deterministic extracted-tree manifest. The installed host Git tree, `cmd/git.exe`, `latest`, BusyBox MinGit, PortableGit and installers remain non-authoritative.
- No portable PowerShell bundle is selected for the initial compile/AST gate. The fixed guest Windows PowerShell controller remains the only PowerShell boundary until a later explicit allowlist/transcript contract is approved.
#### V1C1B verification closure

Implementation commit `70fc763` (`feat: add typed compile ast plan capability`) contains exactly four new V1C1B files plus `tools/eval_package_boundaries.py` and `tools/pipeline.py`. Pre-commit evidence passed V1C1B portable `35/35`, real Windows plan smoke `1/1`, package boundaries `28/28` and the full `check` flow. Post-commit evidence at exact HEAD `70fc763ddab74da501d4988a9a0fd8269e877ddb` re-established:

```text
tracked files / Python files:       260 / 242
Python bytes:                       3,453,149
pipeline flows / all steps:         93 / 474
check steps:                        88
process-launch call sites:          40
host-sensitive files:               27
inventory fingerprint:              4c4316c3fdfa59ab5fc2e72e76364ae457a12c3545022300b30a486b4357d716
V1C0A post-commit Windows smoke:     1/1
V1C1B post-commit Windows smoke:     1/1
```

The V1C1B Windows smoke again derived only `module.py`, kept `delete.py` and `notes.txt` as non-materialized evidence, proved `issued -> claimed_for_compile_ast_gate`, preserved exact bytes `value = 2\n`, and left repository/workspace state unchanged. Network, download/install, Sandbox, runtime-lease issue/claim, interpreter execution, changed-code execution, reusable authority and `execution_authorized` all remained `false`. V1C1B is VERIFIED and grants only one typed plan to the future V1C2 active boundary.

#### Locked V1C2 compile/AST active-boundary architecture

```text
V1C2A1  Canonical Compile/AST Request, Result and Terminal Contract
V1C2A2  Fixed Guest Runner and Payload Bundle
V1C2B   Signed Compile/AST Transcript Verifier
V1C2C   Active Compile/AST Sandbox Composition
```

V1C2A1 locks strict canonical UTF-8/LF JSON, exact field order, duplicate/unknown/non-finite rejection, bounded request/manifest/ready/authorize/result/terminal sizes and 64-byte ECDSA-P256 signatures. Boundary authenticity and check success are separate: a signed syntax failure may be trusted evidence while `check_passed=false`.

Guest materialization is flat and deterministic: original repository paths are metadata only, while sorted exact sources become `source-0001.py` through `source-0020.py` beneath the fixed read-only source root. The runner uses `skynetvs://changed/<path>` only as the compile diagnostic filename. It performs `ast.parse(mode="exec", feature_version=(3, 13), type_comments=False, optimize=0)` and `compile(mode="exec", flags=0, dont_inherit=True, optimize=0)`, then discards the code object. Import statements may compile, but imports/top-level code are never executed and the workspace is never on `sys.path`.

V1C2C uses one standard-user worker assigned before resume to a kill-on-close Job with active-process limit `1`, process memory `512 MiB`, job memory `768 MiB` and a `60` second worker timeout. Success or authentic syntax failure requires the same Sandbox instance to prove runtime identity, source/request hashes, SYSTEM controller, standard-user worker, network isolation, empty worker process set, account deletion, shutdown, all host Sandbox processes exited and post-exit signature/artifact stability.

#### V1C2A1 verification closure

Implementation commit `ec68dd4` (`feat: add canonical compile ast transcript contract`) contains exactly four new V1C2A1 files plus `tools/eval_package_boundaries.py` and `tools/pipeline.py`. Pre-commit evidence passed package boundaries `28/28`, V1C1B portable `35/35`, V1C2A1 portable `45/45`, real Windows contract smoke `1/1`, Runtime Architecture Audit `9/9` and the full `check` flow. Post-commit evidence at exact HEAD `ec68dd4170bab82131dcf88f3aaa7b98ebaa75b8` re-established:

```text
tracked files / Python files:       264 / 246
Python bytes:                       3,597,286
pipeline flows / all steps:         94 / 479
check steps:                        89
process-launch call sites:          40
host-sensitive files:               28
Python tree fingerprint:            b9f780d9d9e1494d3ba968d239191cbd9199f3eeca8099dce79fb81a2298ef1b
inventory fingerprint:              9f3bd41cdc379f126751e651dbcdd71cbc3380d7ac5bf57687b46dd48b5cd268
V1C0A post-commit Windows smoke:     1/1
V1C2A1 post-commit Windows smoke:    1/1
```

The post-commit contract smoke revalidated policy `a3e7d50e92de8aa0799953874a71ce60b2d141e52791282e5fd38814aa9507bf`, flat files `source-0001.py` / `source-0002.py`, virtual diagnostic paths, all three terminal statuses and bounded `SyntaxError` evidence without raw source text. `sandbox_launched`, runtime-lease issue/claim, candidate-interpreter execution, changed-code execution, reusable authority and `execution_authorized` all remained `false`. V1C2A1 is VERIFIED and grants no execution capability; V1C2A2 is now the current host-only slice.


#### V1C2A2 verification closure

Implementation commit `b83d296` (`feat: add fixed compile ast guest runner bundle`) contains exactly four new V1C2A2 files plus `tools/eval_package_boundaries.py` and `tools/pipeline.py`. Pre-commit evidence passed package boundaries `28/28`, V1C2A1 portable `45/45`, V1C2A2 portable `40/40`, real Windows bundle smoke `1/1`, Runtime Architecture Audit `9/9` and the full `check` flow. Post-commit evidence at exact HEAD `b83d2966960a23ebf6930b8ba7ea4bd100cef0b3` re-established:

```text
tracked files / Python files:       268 / 250
Python bytes:                       3,682,203
pipeline flows / all steps:         95 / 484
check steps:                        90
process-launch call sites:          40
host-sensitive files:               29
Python tree fingerprint:            358ecc4acdcd25163ac56e280c9c63e2d62c46f4f8ec89665bae12826e9cfb0a
inventory fingerprint:              a39d47b9e9041dbe276cc73648fd37b57f614e9f94fbd731368f8e80b15cd5b3
V1C0A post-commit Windows smoke:     1/1
V1C2A2 post-commit Windows smoke:    1/1
```

The fixed bundle revalidated policy `825af298ba972e6c12ac0f85572935c7a8bd34ed4ee215cfa2af6e39a7e659c4`, bundle fingerprint `b1f182ca4ee1a9e83cb6a32ca54e45d4511c81faa27d8dd4be7817883affb9f3`, exact runner SHA-256 `6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9` and payload SHA-256 `730d4108aab8246d1e6ff030a4d5a64ad25a89adf888e2b10c64ec63d56f60b6`. The bundle is deterministic, caller-independent and bound to the exact V1C2A1 contract and trusted runtime. Its runner has fixed isolated CPython flags, rehashes all trusted/source inputs, performs only strict validation plus `ast.parse`/`compile`, discards code objects and has no import execution, `exec`, `eval`, subprocess, shell, network or install surface. Both pre/post-commit Windows evidence kept Sandbox, runtime-lease, interpreter, changed-source processing/parsing/compilation, changed-code execution, reusable authority and `execution_authorized` false. V1C2A2 is VERIFIED and remains non-authorizing.

#### V1C2B verification closure

Implementation commit `98f4cfe` (`feat: add signed compile ast transcript verifier`) contains exactly four new V1C2B files plus `tools/eval_package_boundaries.py` and `tools/pipeline.py`. Pre-commit evidence passed package boundaries `28/28`, V1C2A1 portable `45/45`, V1C2A2 portable `40/40`, V1C2B portable `44/44`, real Windows CNG smoke `1/1`, Runtime Architecture Audit `9/9` and the full `check` flow. Post-commit evidence at exact HEAD `98f4cfe0ee1a71c327b35670d786ab11b9485c6b` re-established:

```text
tracked files / Python files:       272 / 254
Python bytes:                       3,763,805
pipeline flows / all steps:         96 / 490
check steps:                        91
process-launch call sites:          40
host-sensitive files:               30
Python tree fingerprint:            f73125f2281ef44f15fc13a8520d64a2522bb020610b13480bcf72b0df5ea0a4
inventory fingerprint:              06f3794183eec0beede477f72eacc51ef5b991d81e69cbc3b3660daba3f7765f
V1C0A post-commit Windows smoke:     1/1
V1C2B post-commit Windows CNG smoke: 1/1
```

The verifier revalidated policy `cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf`, strict canonical document/hash-chain binding, the exact V1C2A2 runner identities and a 64-byte ECDSA-P256 signature through Windows CNG. The post-commit smoke proved `signature_valid`, `chain_verified`, `result_verified` and `terminal_verified` with public-key SHA-256 `0bc654178e6f3d5e4ab8b170722a7b7a388a76d58c97031fcad019cf4bdb5e91`. Authentic syntax failure remains verified evidence with `check_passed=false`, while malformed, substituted, replayed or forged evidence fails closed. The production verifier has no filesystem, process, Sandbox, network, `ast.parse`, `compile`, `exec` or `eval` surface and never grants reusable authority. Sandbox launch, runtime-lease issue/claim, candidate-interpreter execution, changed-source processing, changed-code execution, reusable authority and `execution_authorized` all remained `false`. V1C2B is VERIFIED; V1C2C0 and the original V1C2C1 bundle have since been verified. Roadmap Change 019 inserted and verified V1C2C1R1; Roadmap Change 020 inserted and verified V1C2C1R2. Roadmap Change 024 closed V1C2C1R3 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and authorized one exact R3 rebind plus one fresh active retry. That retry is FAILED / CONSUMED; Roadmap Change 025 is COMPLETED / CONSUMED. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.

#### V1C2C0 verification closure

Implementation commit `e6e355a` (`feat: add process-local compile ast claim transaction`) contains exactly four new V1C2C0 files plus `tools/eval_package_boundaries.py` and `tools/pipeline.py`. Pre-commit evidence passed package boundaries `28/28`, V1C1B plan `35/35`, V1B4D runtime lease `36/36`, V1C2C0 portable `38/38`, real Windows claim smoke `1/1`, Runtime Architecture Audit `9/9` and the full `check` flow. Post-commit evidence at exact HEAD `e6e355ab3238565bb9d685f503647da6a487c919` re-established:

```text
tracked files / Python files:        276 / 258
Python bytes:                        3,873,221
pipeline flows / all steps:          97 / 496
check steps:                         92
process-launch call sites:           40
host-sensitive files:                31
Python tree fingerprint:             f7af9a590320fb6a17178b8baa2785a0981ea83a22f9c8f393261ec38b599088
inventory fingerprint:               d10f6fb0c9a72419c0d63c1445253c692a90010a97ee834dfefe5015abf2289a
V1C0A post-commit Windows smoke:      1/1
V1C2C0 post-commit Windows smoke:     1/1
```

The committed transaction revalidated policy `092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa`, issued without consuming either input, then irreversibly claimed the exact V1C1B plan before the exact V1B4D lease. The Windows smoke proved `issued -> claimed`, `plan_state_after_claim=claimed_for_compile_ast_gate`, `lease_state_after_claim=claimed`, a unique 64-hex one-run `runtime_lease_fingerprint`, exact source bytes `value = 2\n` and the exact retained runtime bundle. Source/workspace Git evidence remained unchanged, no Sandbox process or artifact remained, and repository mutation, network/download/install, Sandbox launch, candidate-interpreter execution, changed-source processing, changed-code execution, reusable authority and `execution_authorized` all remained `false`. V1C2C0 is VERIFIED and non-authorizing; the V1C2C1 verification closure follows.

#### V1C2C1 verification closure

Implementation commit `aa97b779441196b1586d317344f3a82d05411874` (`feat: add fixed compile ast controller worker bundle`) has parent documentation commit `1ca04d6568e687d8addd956eb4f9b6b0926ccdbe` and contains exactly the locked six-file scope:

```text
A modules/developer/developer_task_execution_compile_ast_controller_worker_policy.py
A modules/developer/developer_task_execution_compile_ast_controller_worker.py
A tools/eval_developer_task_execution_compile_ast_controller_worker.py
A tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

Pre-commit evidence completed successfully:

```text
package boundaries:                           28/28
V1C2A1 dependency gate:                       45/45
V1C2A2 dependency gate:                       40/40
V1C2B dependency gate:                        44/44
V1C2C0 dependency gate:                       38/38
V1C2C1 portable adversarial gate:             33/33
V1C2C1 Windows compile/parse-only smoke:        3/3
targeted flow:                  completed successfully
full check:                     completed successfully
Runtime Architecture Audit:                      9/9
```

Post-commit evidence at exact `HEAD == origin/main == aa97b779441196b1586d317344f3a82d05411874` re-established:

```text
tracked files / Python files:       280 / 262
Python bytes:                       4,027,150
pipeline flows / all steps:         98 / 504
check steps:                        93
process-launch call sites:          41
host-sensitive files:              34
Python tree fingerprint:            5b58b6120524609c8f0d378d69bfa9316d65709f4ea2fe669f8c5334e1e59be3
inventory fingerprint:              3c7cae90bdcd2584676c6cb82203af43658236602f683b83b0c377b6d9a36cad
V1C0A post-commit Windows smoke:     1/1
V1C2C1 post-commit Windows smoke:    3/3
post-commit targeted flow:          completed successfully
working tree:                       clean
stable V1B4 tag:                    91d8c37fc4afe7ef138e36063e7bc22014da8a2c
```

The committed bundle revalidated the Roadmap Change 017 architecture identity and exact implementation identities:

```text
architecture decision: 56bfd2ca196ca2b6d8f6ad426ea06141fe1535a28a281f0d7661bc8e32ee8ff6
architecture slice:    db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec
semantic policy fp:    0a559e9a9bcac241a18b0e3cbe31263f4f01a5a94eaf70ee7d65382297a62baf
policy bytes SHA:      1d9b1c66bf3971a3fdedfb077ef8deb08467e29acbc4f725d7050e3ae1342091
bootstrap SHA:         7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d
native helper SHA:     901373a63df349e245a0c90887779b2cdb7f204dee98535c95bdc235844bb7a1
controller SHA:        f30d115d5a9dc2da2dd9e2d9dbeca3929b9497d35e700dec175d9399aac49996
WSB template SHA:      81861905167211b29fbff7179878b6b671c31b731af482166913b5e20416375f
bundle fingerprint:    bd30bec84c8cbdd37940c0e1bb4b34f3cd6c0aed72d05c326afef118f53cd50c
```

The fixed payload proves, without launching Sandbox, a LocalSystem controller contract, a fresh standard-user medium-integrity worker, `CreateEnvironmentBlock(..., false)`, sanitized `PYTHON*`/`PIP_*`/`PYLAUNCHER_*`/`VIRTUAL_ENV`, no inherited handles, `CREATE_SUSPENDED`, assign-before-resume, kill-on-close and Job limits `1 / 512 MiB / 768 MiB`. The builder accepts no caller executable, argv, environment, identity, limits, guest paths, runner path or WSB settings.

Every active flag remained false: no claim transaction was consumed, no runtime lease was claimed, no runtime or source was materialized, Windows Sandbox and the candidate interpreter were not launched, changed sources were not parsed or compiled, changed code was not executed, no reusable lease was issued and `execution_authorized=false`. V1C2C1 remains VERIFIED historical host-only evidence. V1C2C1R1 and V1C2C1R2 are independently VERIFIED. Roadmap Change 024 closed V1C2C1R3 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and authorized one exact R3 rebind plus one fresh active retry. That retry is FAILED / CONSUMED; Roadmap Change 025 is COMPLETED / CONSUMED. Roadmap Change 027 closes V1C2C1R4 as VERIFIED / HOST-ONLY / NON-AUTHORIZING and reopens V1C2C2 only for exact R4 rebinding plus one fresh active attested-pass retry; V1C2C3 remains BLOCKED.

- The first active changed-workspace boundary is V1C2 compile/AST only. It consumes one fresh V1C2C0 transaction, which irreversibly claims one V1C1B plan and one fresh V1B4D lease, and launches one fresh Sandbox; imports and top-level execution remain forbidden.
- Every `python_module` target must be selected by a semantic explicit allowlist and bound to an exact protected baseline-owned entrypoint. The existing name regex is validation only, not authorization.
- The existing `check` flow is not the initial pipeline allowlist. V1C6 must introduce a protected guest-safe flow with an exact reviewed step list; host-hardware smoke, outer Sandbox activation and interactive/promotion flows remain excluded.
- One executable check uses one fresh lease, one immutable workspace snapshot and one fresh Sandbox. A successful report never becomes authority for another check.

#### V1C0A — VERIFIED first production slice

**Closure:** `b039ce1`; post-commit Windows smoke `1/1`.

V1C0A is host-only and non-authorizing. It performs read-only inventory over a typed clean repository evidence chain and never imports tracked modules.

Verified public shape:

```python
inventory_developer_task_execution_environment(
    repository_report: DeveloperTaskRepositoryPreflightReport,
    *,
    project_root: Path,
) -> DeveloperTaskExecutionEnvironmentInventoryReport
```

Caller-supplied requirement lists, module allowlists, pipeline allowlists, executables, argv, environment additions and classification overrides are forbidden.

Verified implementation scope:

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

#### V1C0B1 — VERIFIED host-toolchain observation slice

V1C0B1 is host-only and non-authorizing. It consumes a typed successful V1C0A report and observes exact committed dependency declarations plus host Python/pip, Git distribution and fixed Windows PowerShell identities without importing project modules.

Verified public shape:

```python
observe_developer_task_execution_host_toolchain(
    inventory_report: DeveloperTaskExecutionEnvironmentInventoryReport,
    *,
    project_root: Path,
) -> DeveloperTaskExecutionHostToolchainReport
```

Caller-controlled executable, argv, environment addition, requirement list, package mapping, Git root, source URL and classification override are forbidden.

Verified implementation scope:

```text
A modules/developer/developer_task_execution_toolchain_observation_policy.py
A modules/developer/developer_task_execution_toolchain_observation.py
A tools/eval_developer_task_execution_toolchain_observation.py
A tools/eval_developer_task_execution_toolchain_observation_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

Acceptance includes:

- exact HEAD/project-root/V1C0A report binding;
- exact committed requirement bytes and strict declaration parsing;
- host Python/pip identity, ABI/tag and installed-distribution observation without authority;
- import-root to host-distribution observation;
- host Git executable/build/exec-path plus full installation-tree manifest fingerprint;
- fixed Windows PowerShell executable/version identity;
- no serialization of user/global Git configuration values or credentials;
- no network, download, install, source resolution, Sandbox, lease, candidate Python, project-module import or changed-code execution;
- `source_authority_selected=false`, `execution_authorized=false` and `reusable_lease_issued=false`.

Closure evidence:

```text
commit:                              e090f63 feat: add canonical host toolchain observation
portable evaluator:                  26/26
pre-commit targeted Windows flow:    completed successfully
pre-commit full check:               completed successfully
post-commit V1C0A Windows smoke:     1/1
post-commit V1C0B1 Windows smoke:    1/1
inventory fingerprint:               574cdc81c154c04ade6e26aec520cac243ddf5e15f1780037c57bf3ae88d1956
observation fingerprint:             aa2f63f41523480f4e423d57e15e02883b70709e34e1dd108c72e977b36e6035
source_authority_selected:            false
execution_authorized:                 false
```

#### V1C0B2 — LOCKED external source authority

V1C0B2 is a Pro Standard architecture/source-policy lock and performs no network operation.

```text
decision ID:          skynetvs-v1c0b2-external-source-authority-lock-v1
decision fingerprint: 80da155e8de0ce9f6d17565541173b701c2d5c9c8a8c13f1fcab9a57dbdb3d5e
```

It fixes the only admissible future acquisition boundaries:

- Python index metadata: normalized project pages from `https://pypi.org/simple/` requested as Simple API JSON v1; supported major `1`, minimum minor `4`.
- Python artifact bytes: exact HTTPS wheel URLs under `files.pythonhosted.org` returned by the verified project response.
- Required Python evidence: response/body identity, API version, project status, normalized name, exact version, wheel filename/tag, file size, SHA-256, `Requires-Python`, yanked state, core-metadata identity when present, and provenance identity when present.
- Resolver role: a version-pinned isolated host resolver may propose a closure, but cannot authorize it. The final manifest is independently rebuilt from verified direct/transitive metadata and bytes.
- PyPI attestation role: verify when present and bind it to the exact wheel; record absence. An attestation proves publishing identity, not package safety.
- Git metadata/artifact: immutable `git-for-windows/git` release tag plus the standard `MinGit-<version>-64-bit.zip` asset, release-published SHA-256, exact archive bytes and deterministic extracted-tree manifest.
- Current review candidate only, not a production pin: `v2.55.0.windows.4` / `MinGit-2.55.0.4-64-bit.zip` / `4e03f94c2ffbf70be337e005cee02661c732dbfc81031a078bda9299b9a7d644`.
- Network is allowed only in future dedicated host acquisition gates with exact origin/redirect allowlists, serial bounded requests and a scrubbed credential/index/proxy environment. Guest/runtime network remains forbidden.
- Standard lock/interchange formats may be emitted as derived output, but the SkynetVS canonical source manifest and fingerprint remain authority.

No package, Git archive or resolver is selected as executable capability by this lock. Exact Python artifact closure remains V1C3A; exact MinGit pin and tree remain V1C3C.

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

[VERIFIED V1C0A]
b039ce1 — Canonical Executable Check Inventory Gate; current-tree post-commit Windows smoke 1/1.

[VERIFIED V1C0B1]
e090f63 — Canonical Host Toolchain Observation Gate; post-commit Windows smoke 1/1.

[LOCKED SOURCE AUTHORITY]
V1C0B2 — PyPI Simple API + exact hosted wheels; immutable standard 64-bit MinGit release asset.

[LOCKED V1C1 ARCHITECTURE]
V1C1A snapshot policy → V1C1B typed compile/AST plan capability.

[VERIFIED]
V1C1A — Canonical Patched Workspace Snapshot Bundle (host-only, non-authorizing).
V1C1B — Typed Compile/AST Plan Capability (host-only, non-authorizing).
V1C2A1 — Canonical Compile/AST Request, Result and Terminal Contract (host-only, non-authorizing).
V1C2A2 — Fixed Guest Runner and Payload Bundle (host-only, non-authorizing).

[VERIFIED]
V1C2B — Signed Compile/AST Transcript Verifier (host-only, non-authorizing).

[LOCKED V1C2C ARCHITECTURE]
Roadmap Change 016 → V1C2C0 claim transaction → V1C2C1 fixed controller/worker bundle → V1C2C2 active composition → V1C2C3 live acceptance.

[VERIFIED]
V1C2C0 — Process-Local Plan/Runtime Claim Transaction Capability (host-only, single-use, non-authorizing).
V1C2C1 — Fixed SYSTEM Controller and Standard-User Worker Payload Bundle (`aa97b77`; host-only, non-authorizing).

[VERIFIED HOST-ONLY CORRECTION]
V1C2C1R3 — Guest-Local Worker Result Relay Correction (`7a73e97`; host-only / non-authorizing; fixed runner unchanged).

[VERIFIED HOST-ONLY CORRECTION]
V1C2C1R4 — Signed Controller Evidence over Untrusted Writable WSB Transport (`f0a2da9`; host-only / non-authorizing; fixed runner unchanged).

[CURRENT DIAGNOSTIC / ONE FRESH CAPTURE ONLY]
V1C2C2P3 — R4 Signed Boundary Terminal Capture (external, one-shot, non-accepting; exact R4 candidate SHA-256 `dfd84a366db41fa718b59ca91437a7e2f03746d025373690176667530ef92d05`).

[BLOCKED / RC027 FAILED]
V1C2C2 — Active Compile/AST Sandbox Composition (exact seven-file R4-rebound candidate preserved uncommitted; RC027 failed/consumed and must not be rerun).

[BLOCKED]
V1C2C3 — Live Pass / Syntax-Failure / Boundary-Failure Acceptance.

[PLANNED AFTER SAFETY KERNEL]
Domain Package Structure V2.

[PLANNED AFTER PRODUCTION PACKAGES]
Tools Package Structure V1.
```

До завершения Developer Safety Kernel дополнительные production-файлы по пакетам не переносятся.

## Current operational override after Roadmap Change 033 — 2026-08-26

This section supersedes all earlier CURRENT/BLOCKED operational labels in this document where they conflict with Roadmap Change 033. Historical evidence and historical Roadmap Change states remain immutable.

```text
HEAD before RC033 docs transition:       b0bf07015b001499c48c8fc334472993cc83bdb1

V1C2A2R1:                                 VERIFIED / COMMITTED
V1C2BR1:                                  VERIFIED / COMMITTED / HOST-ONLY
V1C2C1R5:                                 VERIFIED / COMMITTED / HOST-ONLY

V1C2C2 portable rebind:                   PASS
V1C2C2 candidate bytes:                   225629
V1C2C2 candidate SHA-256:                 296d1c94a884f065d27e65cb312618576c8f7ce4e60c7a3ee2fa84c7f4a2ff2e
V1C2C2 policy fingerprint:                b4d254963b38caaf1031e85d304eda186eeb784c46ce42af97f0eb3c8c215976
V1C2C2 policy-document SHA-256:            fb34f1e7d41f8c5f2ef79a39b8a833c7eb4981769bf1b894f14e7b19b7eddd16

package boundaries:                       28/28
portable V1C2C2:                          48/48
full check:                               PASS
Runtime Architecture Audit:               9/9

RC033:                                    CURRENT / ONE FRESH ACTIVE ATTESTED-PASS RETRY ONLY
RC033 consumed marker:                    NOT YET RESERVED
V1C2C2 active attempt:                    NOT YET RUN
V1C2C2 candidate commit:                  NOT YET AUTHORIZED / UNCOMMITTED
V1C2C3:                                   BLOCKED
```

No active authority exists until the permanent RC033 one-shot marker is created under the exact convention confirmed by the next read-only audit. Creating that marker consumes the sole RC033 active attempt. No Sandbox launch belongs to this documentation transition.

## V1C2C2 verification closure after Roadmap Change 033 — 2026-08-27

This closure records the completed outcome already authorized by Roadmap Change 033; it does not create a new Roadmap Change and does not authorize a second active run.

The exact seven-file V1C2C2 implementation is VERIFIED / COMMITTED at:

```text
implementation commit:                  c4ceb272898600a90be9db56c990e0c8d98a7bac
parent RC033 documentation commit:      372fa7554a107226675b1d5c0d845b65d50b8a53
commit subject:                         feat: add active compile ast sandbox composition
exact committed patch bytes:            225629
exact committed patch SHA-256:          296d1c94a884f065d27e65cb312618576c8f7ce4e60c7a3ee2fa84c7f4a2ff2e
composition policy fingerprint:         b4d254963b38caaf1031e85d304eda186eeb784c46ce42af97f0eb3c8c215976
composition policy-document SHA-256:    fb34f1e7d41f8c5f2ef79a39b8a833c7eb4981769bf1b894f14e7b19b7eddd16
```

RC033 active evidence is permanently consumed and immutable. The one real active Windows evaluator run passed exactly `3/3`, with evaluator exit code `0`, status `active_compile_ast_attested_passed`, signed terminal status `compile_ast_attested_passed`, valid controller and legacy-terminal signatures, stable ready/evidence/result bytes, private-to-relayed-result hash binding, `boundary_ok=true`, `check_passed=true`, `result_verified=true`, no issue codes and full cleanup.

```text
RC033 consumed marker SHA-256:           5bffd4f5cbf204dbe3ee290cc733a7d4271a8f8789856e190bc869affb6666d9
append-only terminal result SHA-256:     8e5d708f7385c8b8c1f8ca22bc0a641c3d1f67f41be63821fbb266338bb59af2
active evaluator log SHA-256:            18b5c73f79532c09db45a4966a5ac52d8f6b36f19559e96931bcfe9138f4bb65
parsed active evidence SHA-256:          51a48b62675ebd013abba96d1e6b97a37f35a87f39586572e396bf05331ef1d6
terminal recovery report SHA-256:        f3c9f1d27732ce8cdb7a4a69bd37647e30cc13d66d5d07f9a16847c7a117ae92
implementation closure report SHA-256:   ed5712c3496573eb7c0648f237511ec0b316805f3bb5e22dae67aa27612ceeb6
```

The marker-finalizer incident was harness-only: the active product run had already passed `3/3`; the immutable reservation marker remained byte-for-byte unchanged and the terminal outcome was safely recorded in a separate append-only CreateNew result. No active evaluator was reexecuted during recovery or commit closure.

Pre-commit and post-commit non-active acceptance are green:

```text
pre-commit full check:                   PASS
pre-commit full check stdout SHA-256:    368b854f570f14754388602e712bdec62187baaea30ada76d2ce460eab869520
pre-commit Runtime Architecture Audit:   9/9 PASS
post-commit full check:                  PASS
post-commit full check stdout SHA-256:   39863604dad5f0472c4d6d125c3232ef89d381bda349397139d52b09f0a9fa0d
post-commit Runtime Architecture Audit:  9/9 PASS
HEAD == origin/main:                     true
working tree:                            clean
known Sandbox process set:               empty
stable V1B4:                             91d8c37fc4afe7ef138e36063e7bc22014da8a2c
```

Security invariants at closure remain:

```text
claim_transaction_consumed=true
runtime_lease_claimed=true
sandbox_launched=true
candidate_interpreter_executed=true
changed_source_processed=true
changed_source_ast_parsed=true
changed_source_compiled=true

changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
artifacts_removed=true
all_processes_exited=true
forced_cleanup_attempted=false
```

Operational state after this closure:

```text
V1C2A2R1   VERIFIED / COMMITTED
V1C2BR1    VERIFIED / COMMITTED / HOST-ONLY / NON-AUTHORIZING
V1C2C1R5   VERIFIED / COMMITTED / HOST-ONLY / NON-AUTHORIZING
RC033       PASSED / CONSUMED / MUST NOT BE RERUN
V1C2C2      VERIFIED / COMMITTED / ACTIVE ATTESTED-PASS CLOSED
V1C2C3      BLOCKED
```

The targeted `developer_task_execution_compile_ast_composition` flow must not be run for V1C2C2 closure because it contains the already-consumed active Windows evaluator. A second RC033 active run is forbidden.

This closure does not create Roadmap Change 034 and does not authorize V1C2C3. The next exact action is a READ-ONLY / HOST-ONLY V1C2C3 roadmap-and-source transition audit. That audit must determine the exact locked V1C2C3 acceptance surface, existing evaluator/policy files, required immutable identities, whether a new explicit Roadmap Change is required before any V1C2C3 run, and the exact non-active/active boundaries. Until that audit is reviewed, V1C2C3 remains BLOCKED.

## Roadmap Change 034 — open evaluator-only V1C2C3 live acceptance implementation without authorizing active matrix execution

**Причина:** the read-only / host-only V1C2C3 roadmap-and-source transition audit at committed documentation `HEAD / origin/main e30a1df8ad3b403e52bd4c84668b9e02f44ec7eb` completed with repository mutation `NONE`, empty Sandbox process set and exact audit SHA-256 `2b6a468b8c262b082e78f399634dd7a78badb7bfa07432240ea66a801c7a01e1`. It confirmed that V1C2C3 is still explicitly BLOCKED, Roadmap Change 034 was absent, the locked historical V1C2C3 evidence identity remains `b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8`, and no V1C2C3-specific production/evaluator file or pipeline wiring currently exists. The locked architecture requires a three-run live acceptance matrix — pass, authentic syntax failure and signed post-ready boundary failure — with fresh capabilities and fresh Sandbox instances, while the public V1C2C2 production API must not gain fault-injection hooks.

**Что меняется:** V1C2C3 becomes CURRENT only for one measured evaluator-only implementation candidate. This Roadmap Change authorizes creation/modification of exactly these four tracked files and no others:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
tools/eval_package_boundaries.py
tools/pipeline.py
```

No new `modules/developer` production module is authorized. The portable evaluator is the policy/state-machine and source-topology acceptance surface. The Windows evaluator may be authored as the future live harness but MUST NOT be executed under RC034.

The candidate must preserve the existing V1C2C2 public production API byte-for-byte outside ordinary dependency imports required by the evaluator; no runtime ZIP/path, workspace, manifest, source path/list, executable, argv, environment addition, timeout override, Job limit, WSB setting, signature verifier or fault-injection hook may be added to the public composition API.

The portable evaluator must prove at minimum:

1. the locked three-row matrix exists in the evaluator contract: live pass / authentic syntax failure / signed post-ready boundary failure;
2. every row requires a distinct fresh capability chain and future fresh Sandbox instance;
3. live pass expects signed terminal `compile_ast_attested_passed`, `boundary_ok=true` and `check_passed=true`;
4. authentic syntax failure expects signed terminal `compile_ast_attested_failed`, `boundary_ok=true` and `check_passed=false`;
5. signed post-ready boundary failure expects signed terminal `compile_ast_boundary_failed`, `boundary_ok=false`, `check_passed=false` and no accepted result hash;
6. all rows preserve `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false`;
7. fault injection is evaluator-private and absent from the public production API;
8. the historical value `b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8` remains a locked documentation/evidence identity and is not claimed to be the SHA-256 or policy fingerprint of newly created evaluator bytes.

The future Windows evaluator must be structured for three separate fresh runs:

```text
RUN 1: live pass
RUN 2: authentic syntax failure using genuinely invalid selected Python source bytes
RUN 3: signed post-ready / pre-authorization boundary failure using evaluator-private source substitution
```

Each future active row must obtain fresh host snapshot/report, fresh plan capability, fresh retained runtime capability/lease, fresh V1C2C0 claim transaction and a fresh Windows Sandbox instance. No transaction, lease, capability, Sandbox or terminal evidence may be reused across matrix rows.

**RC034 active prohibition:** this Roadmap Change does NOT authorize execution of `tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py`, does NOT authorize any of the three V1C2C3 live rows, and does NOT authorize any Sandbox launch, V1C2C0 transaction consumption, runtime-lease claim or candidate-interpreter execution for V1C2C3.

Pipeline wiring under RC034 is intentionally non-active:

```text
full check:
    portable V1C2C3 evaluator may be wired exactly once
    V1C2C3 Windows active evaluator count must remain 0

developer_task_execution_compile_ast_live_acceptance targeted flow:
    may contain portable / host-only non-active dependencies and the portable V1C2C3 evaluator
    must contain V1C2C3 Windows active evaluator count 0
```

The Windows evaluator file therefore remains deliberately unwired from every pipeline flow during RC034. A later explicit Roadmap Change is required before it may be wired or launched.

**Что не меняется:** V1C2C2 remains VERIFIED / COMMITTED / ACTIVE ATTESTED-PASS CLOSED at exact implementation commit `c4ceb272898600a90be9db56c990e0c8d98a7bac`. RC033 remains PASSED / CONSUMED / MUST NOT BE RERUN. The consumed RC033 marker and append-only terminal result remain immutable. The stable tag `skynet-trusted-runtime-v1b4` remains `91d8c37fc4afe7ef138e36063e7bc22014da8a2c`. The LocalSystem-controller / standard-user-worker boundary, Job limits `1 / 512 MiB / 768 MiB`, four-folder mapping, network denial, fixed V1C2A2 runner, signed-evidence trust model and all verified V1C2A1/A2/B/C0/C1/R1/R2/R3/R4/R5 identities remain unchanged.

Operational state after Roadmap Change 034:

```text
RC033       PASSED / CONSUMED / MUST NOT BE RERUN
V1C2C2      VERIFIED / COMMITTED / ACTIVE ATTESTED-PASS CLOSED
V1C2C3      CURRENT / EVALUATOR-ONLY IMPLEMENTATION CANDIDATE
            ACTIVE THREE-RUN MATRIX BLOCKED
RC034       CURRENT / NON-ACTIVE IMPLEMENTATION AUTHORITY ONLY
Sandbox     NOT AUTHORIZED
```

**Next Exact Action:** create the exact four-file V1C2C3 evaluator-only candidate, then perform only Python syntax/AST checks, package-boundary verification, portable V1C2C3 evaluation, source-only pipeline topology verification, full `check` only after proving the V1C2C3 Windows evaluator count is `0`, Runtime Architecture Audit, exact candidate identity measurement and an empty Sandbox-process check. Stop before any V1C2C3 Windows evaluator execution, Sandbox launch, capability/lease/transaction claim or active acceptance. The candidate must be reviewed before any implementation commit. A separate later Roadmap Change is required to authorize the live three-run matrix.

## Roadmap Change 034 implementation closure — V1C2C3 evaluator candidate committed / active matrix still blocked

Roadmap Change 034 implementation authority is now COMPLETED / NON-ACTIVE IMPLEMENTATION VERIFIED.

The exact evaluator-only implementation authorized by RC034 is committed and pushed at:

```text
implementation commit:                a2a4be24e2507d70312ab363853a6dd578380568
parent RC034 docs commit:             3abd91ebb3c3d24e99ed756e6f8b5cd3cda0149d
commit subject:                       feat: add compile ast live acceptance evaluators
exact committed patch bytes:          51956
exact committed patch SHA-256:        dca08c8e9cee29e0e45e7ac5b6a7459d82eea2cc3c356d5794260b56c43caacf
candidate precommit evidence SHA-256: 754c80b97a630d58c61e795ca836f58c6046f73b0f91ed3aeb45a97146799ea5
implementation closure SHA-256:       aa7391d3b4e655c54881f59dc193fe2fa5c783824fdca622780b6505a4f1611f
```

Exact committed scope:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
tools/eval_package_boundaries.py
tools/pipeline.py
```

The implementation is NON-ACTIVE VERIFIED. Before and after commit:

```text
package boundaries:                    PASS
V1C2C3 portable evaluator:             PASS
full check:                             PASS
Runtime Architecture Audit:            PASS
V1C2C3 Windows evaluator references:   0
known Sandbox process set:             empty
Windows live evaluator executed:       false
active V1C2C3 matrix executed:         false
```

The portable evaluator proves the locked three-row matrix and the existing V1C2B signed-evidence semantics:

```text
live pass:
    terminal=compile_ast_attested_passed
    boundary_ok=true
    check_passed=true
    result required

authentic syntax failure:
    terminal=compile_ast_attested_failed
    boundary_ok=true
    check_passed=false
    result required

signed post-ready boundary failure:
    terminal=compile_ast_boundary_failed
    boundary_ok=false
    check_passed=false
    result absent
```

The committed Windows evaluator remains future active harness source only. It contains an explicit host-side authority guard and is deliberately unwired from every pipeline flow. RC034 never authorized its execution.

The historical locked V1C2C3 evidence identity remains documentation/evidence identity only:

```text
b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

The new evaluator bytes have their own measured identities and do not claim to reproduce that historical identity.

Permanent invariants remain:

```text
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

Operational state after this implementation closure:

```text
RC033       PASSED / CONSUMED / MUST NOT BE RERUN
V1C2C2      VERIFIED / COMMITTED / ACTIVE ATTESTED-PASS CLOSED

RC034       COMPLETED / NON-ACTIVE IMPLEMENTATION VERIFIED
V1C2C3      IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED
            ACTIVE THREE-RUN MATRIX BLOCKED

future Windows evaluator execution       NOT AUTHORIZED
future active matrix                     NOT AUTHORIZED
next Roadmap Change                      NOT CREATED
```

This closure does not authorize any V1C2C3 active row, does not set or permit `SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1`, does not wire the Windows evaluator into a pipeline flow, and does not create reusable active authority.

**Next Exact Action:** perform a READ-ONLY / HOST-ONLY V1C2C3 active-authority transition audit. The audit must bind the exact committed four-file implementation, historical evidence identity and locked three-row matrix; design permanent consumed evidence for future active attempts; determine whether the three rows require one common authority with three independently consumed row markers or separate roadmap grants; define failure/no-rerun semantics for every row; define the exact success evidence expected for pass, syntax and boundary rows; confirm fresh capability/transaction/runtime-lease/Sandbox requirements and no cross-row reuse; and stop before creating the next Roadmap Change or running the Windows evaluator.

## Roadmap Change 035 — V1C2C3 non-active row-isolation hardening before active authority

**Причина:** the read-only / host-only V1C2C3 active-authority transition audit completed at committed `HEAD / origin/main 811c542e4cb706f07176defed442e260bfc7466f` with repository mutation `NONE`, no Sandbox launch and no active evaluator execution. Exact audit SHA-256 is `547891c2a9880e03403253e1cea130f58d947e8dc657625270c493344cb68b51`.

The audit proved that the committed V1C2C3 Windows evaluator is not yet safe to receive irreversible active authority. Its current `main()` executes the complete fixed three-row matrix in one process, while private `_run_case()` contains the real active capability/Sandbox path but does not independently enforce the committed authority guard. There is no `--row` selector. A partial matrix failure would therefore make a whole-program retry repeat an already consumed successful row, while direct external `_run_case()` use would bypass the intended guard.

**Что меняется:** RC035 opens exactly one NON-ACTIVE row-isolation hardening candidate over exactly two evaluator files:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
```

No production module, package-boundary registry or pipeline file may change under RC035.

The Windows evaluator hardening must:

1. add an explicit required `--row` selector whose only allowed values are exactly:
   - `live_pass`;
   - `authentic_syntax_failure`;
   - `signed_post_ready_boundary_failure`;
2. execute exactly one selected row per process invocation;
3. preserve the existing host-side `SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1` guard before any runtime lookup, host inspection, capability issue/claim or Sandbox path;
4. introduce a private in-process row authority capability/token created only after the host-side authority guard succeeds;
5. require that exact private capability in `_run_case(...)`;
6. reject `_run_case(...)` without the genuine in-process capability before `snapshot_windows_sandbox_processes`, host inspection, plan issue, runtime bundle/lease issue, V1C2C0 transaction issue/claim or either composition attestation call;
7. remove the automatic complete `for row in ROWS` active loop from `main()`;
8. keep the locked row names/order available as static contract data but never automatically consume more than one row;
9. preserve exact future row semantics, cleanup assertions and fresh-capability evidence requirements;
10. preserve the evaluator-private boundary fault and authentic invalid-syntax fixture;
11. keep the Windows evaluator completely unwired from all normal and targeted pipeline flows.

The portable evaluator hardening must statically prove at minimum:

```text
explicit --row selector exists
selector choices are exactly the three locked rows
main no longer loops over all ROWS for active execution
main creates/mints row authority only after the host guard
_run_case requires an authority parameter/capability
invalid or absent capability fails before every active call
exactly one selected row is dispatched
Windows evaluator remains pipeline references = 0
V1C2C2 public production API remains unchanged
locked pass/syntax/boundary transcript semantics remain unchanged
```

RC035 is host-only / non-active implementation authority. It does NOT authorize setting `SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1`, does NOT authorize executing the Windows evaluator, does NOT authorize any row marker creation and does NOT authorize any Sandbox launch, runtime-lease claim, V1C2C0 transaction consumption or candidate-interpreter execution.

Allowed RC035 verification only:

```text
Python parse / compile of the exact two-file candidate
git diff --check
portable V1C2C3 evaluator
package-boundary evaluator without modifying it
source-only pipeline topology verification
full check only after proving V1C2C3 Windows evaluator references remain 0
Runtime Architecture Audit
exact two-file candidate identity measurement
Sandbox process set empty
```

No Windows V1C2C3 evaluator invocation is allowed, including a guard-only invocation.

The historical V1C2C3 evidence identity remains unchanged and historical only:

```text
b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

The closed RC034 implementation remains:

```text
implementation commit: a2a4be24e2507d70312ab363853a6dd578380568
patch SHA-256:        dca08c8e9cee29e0e45e7ac5b6a7459d82eea2cc3c356d5794260b56c43caacf
```

**Future active-authority model locked by the audit but NOT authorized by RC035:**

```text
one future matrix grant
three independently consumed row markers
fixed row order:
  1. live_pass
  2. authentic_syntax_failure
  3. signed_post_ready_boundary_failure

every row marker reserved with FileMode.CreateNew before that row enters active execution
every row marker consumes that row regardless of outcome
row terminal result stored separately with append-only FileMode.CreateNew
no File.Replace finalization
stop entire matrix grant on first failed row
never rerun any already passed/consumed row
remaining rows after a failure require a new explicit Roadmap Change
matrix PASS requires all three independently verified row results
```

RC035 does not create those markers and does not create active matrix authority.

Operational state under RC035:

```text
RC034       COMPLETED / NON-ACTIVE IMPLEMENTATION VERIFIED
RC035       CURRENT / NON-ACTIVE ROW-ISOLATION HARDENING ONLY

V1C2C3      IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED
            ROW-ISOLATION HARDENING CURRENT
            ACTIVE THREE-RUN MATRIX BLOCKED

Windows evaluator execution      FORBIDDEN
Windows evaluator pipeline refs  0
active authority                  NONE
Sandbox                           NOT AUTHORIZED
```

**Next Exact Action:** create the exact two-file RC035 row-isolation hardening candidate and perform only the allowed non-active verification. Stop before commit for evidence review. Do not create the next active-authority Roadmap Change.

## Roadmap Change 035 implementation closure — V1C2C3 row isolation hardened / active authority still absent

Roadmap Change 035 is now COMPLETED / NON-ACTIVE ROW-ISOLATION HARDENING VERIFIED.

The exact RC035 implementation is committed and pushed at:

```text
implementation commit:                1693e3e8fdac6026c5b48735c0b2539a7cc2f246
parent RC035 docs commit:             800b4403d998a4a85d80bf8df538779e42ad2d99
commit subject:                       fix: isolate V1C2C3 live acceptance rows
exact committed patch bytes:          35183
exact committed patch SHA-256:        99c4a10675ac19c5e88ceb46325b8c27513c79405c19797061386c4056b1b02f
candidate precommit evidence SHA-256: d941ab1bd9dcb85ac410ba1eb7b7f48cd9e57d3041bad6ec5367e607608ddd7b
implementation closure SHA-256:       6db703b9a4549ffa9c0e6a8b8c41aa394b7b4bd9de3c98f122ed88812f163783
```

Exact committed scope:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
```

The hardened identities are:

```text
portable evaluator:
281c75d9237baacb7f3631069c1af0d95a1eecc052dae78587a2b6367e08abbb

Windows evaluator:
d7135796b2cbb29d68a41ee3c391c3f0579c6b570da30ac3cd41d9a09fb849dd
```

`tools/pipeline.py` and `tools/eval_package_boundaries.py` remained byte-for-byte unchanged.

The RC035 row-isolation contract is now implemented:

```text
required --row selector
exact selector choices:
  live_pass
  authentic_syntax_failure
  signed_post_ready_boundary_failure

one process invocation selects exactly one row
main no longer automatically loops over all ROWS
host-side active-authority env guard remains before active work
private in-process row authority is minted only after that guard
_run_case requires and consumes the genuine row-bound capability before active calls
missing/forged/replayed capability fails before active work
```

The non-active acceptance before and after commit passed:

```text
package boundaries:                         PASS
portable V1C2C3 row-isolation evaluator:    PASS
full check:                                  PASS
Runtime Architecture Audit:                  PASS
Windows evaluator pipeline references:      0
V1C2C3 consumed/result marker count:         0 / 0
Sandbox process set:                         empty
Windows evaluator executed:                  false
```

RC035 did not create active authority. It did not create any consumed marker or terminal result, and it did not execute the Windows evaluator.

The future matrix-authority model remains only a design decision from the prior read-only audit:

```text
one future matrix grant
three independent consumed row markers
fixed row order:
  1. live_pass
  2. authentic_syntax_failure
  3. signed_post_ready_boundary_failure

reserve each row marker with FileMode.CreateNew before that row enters active execution
terminal row result stored separately with FileMode.CreateNew
row marker consumes that row regardless of outcome
stop the matrix grant on first failed row
never rerun a passed/consumed row
remaining rows after failure require new explicit roadmap authority
```

None of those active semantics are authorized by RC035.

Operational state after this closure:

```text
RC034       COMPLETED / NON-ACTIVE IMPLEMENTATION VERIFIED
RC035       COMPLETED / NON-ACTIVE ROW-ISOLATION HARDENING VERIFIED

V1C2C3      IMPLEMENTED / COMMITTED / ROW-ISOLATED / NON-ACTIVE VERIFIED
            ACTIVE THREE-RUN MATRIX BLOCKED

active authority                  NONE
Windows evaluator pipeline refs   0
Windows evaluator execution       NOT AUTHORIZED / NOT RUN
V1C2C3 consumed/result markers    0 / 0
Sandbox                           NOT AUTHORIZED
next Roadmap Change               NOT CREATED
```

The historical V1C2C3 identity remains historical evidence identity only:

```text
b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

**Next Exact Action:** perform a fresh READ-ONLY / HOST-ONLY V1C2C3 active-authority readiness audit against committed hardened evaluator `1693e3e8fdac6026c5b48735c0b2539a7cc2f246`. The audit must prove row selector/capability enforcement from exact committed source, verify no bypass to `_run_case`, revalidate marker absence and pipeline refs `0`, bind the future row-consumption model to the hardened bytes, and determine whether a later explicit active-authority Roadmap Change may now be safely drafted. Stop before creating that Roadmap Change or running any active row.

## Roadmap Change 036 — V1C2C3 one-shot three-row active authority contract

**Основание:** the fresh read-only / host-only active-authority readiness audit completed at `HEAD / origin/main 49d6bbfb1c0520a0e4eaa160885736618e25b98c` with repository mutation `NONE`, Windows evaluator import/execution `false`, Sandbox launch `false`, V1C2C3 marker/result count `0 / 0`, Windows pipeline references `0` and exact audit SHA-256 `c8313da61f53aafa39a6530ae3f3448f7f80c20a57539e174b1bcd6323da0186`.

The audit bound the hardened evaluator source:

```text
RC035 implementation commit:
1693e3e8fdac6026c5b48735c0b2539a7cc2f246

portable evaluator SHA-256:
281c75d9237baacb7f3631069c1af0d95a1eecc052dae78587a2b6367e08abbb

Windows evaluator SHA-256:
d7135796b2cbb29d68a41ee3c391c3f0579c6b570da30ac3cd41d9a09fb849dd
```

It proved from committed AST/source that:

```text
--row is required
choices are exactly:
  live_pass
  authentic_syntax_failure
  signed_post_ready_boundary_failure

main selects exactly one row
main has no full ROWS loop
host authority guard precedes runtime lookup and active work
row authority is minted only after the host guard
_run_case requires a keyword-only row-bound capability
the capability is consumed as the first effective statement
capability consumption precedes every host/plan/lease/transaction/Sandbox/attestation call
only main calls _mint_row_authority and _run_case inside the committed module
```

**Authority created by RC036:** one matrix grant containing exactly three independent one-shot row authorities in this fixed order:

```text
1. live_pass
2. authentic_syntax_failure
3. signed_post_ready_boundary_failure
```

RC036 does not authorize a full-matrix invocation. Each row must run in a separate fresh child Python process with exactly one `--row` value.

Permanent row reservation markers:

```text
V1C2C3_RC036_LIVE_PASS_CONSUMED.json
V1C2C3_RC036_SYNTAX_FAILURE_CONSUMED.json
V1C2C3_RC036_BOUNDARY_FAILURE_CONSUMED.json
```

Append-only row terminal results:

```text
V1C2C3_RC036_LIVE_PASS_RESULT.json
V1C2C3_RC036_SYNTAX_FAILURE_RESULT.json
V1C2C3_RC036_BOUNDARY_FAILURE_RESULT.json
```

The matrix may become PASSED only through:

```text
V1C2C3_RC036_MATRIX_RESULT.json
```

created after all three row results are independently accepted.

### Irreversible per-row sequence

For every row, the future external authority harness must:

1. run host-only prechecks while no active environment variable is present;
2. verify exact `HEAD / origin`, implementation/evaluator/runtime/input/harness identities, required prior accepted row results and an empty Sandbox process set;
3. self-test the same exclusive-create JSON primitive on disposable files before any permanent marker;
4. reserve the row marker with exclusive `FileMode.CreateNew`;
5. treat successful marker creation as permanent row consumption regardless of every later outcome;
6. spawn a new child Python process with child-only `SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1`;
7. invoke the exact committed Windows evaluator source with exactly one selected `--row`;
8. capture stdout/stderr without importing the evaluator into the authority harness;
9. verify exact row-specific signed evidence and cleanup;
10. create the row terminal result with exclusive `FileMode.CreateNew`;
11. prove the active/runtime artifact parents are empty and all Sandbox processes exited before the next row may be considered.

The parent, user and machine environments must never persist the active variable.

### Row ordering and binding

The live-pass marker may be reserved only when no RC036 row marker/result exists.

The syntax-failure marker may be reserved only after a PASS result for `live_pass`; its marker must bind the SHA-256 of the live-pass marker and result.

The boundary-failure marker may be reserved only after PASS results for both previous rows; its marker must bind all previous marker/result SHA-256 values.

Each row marker must bind at minimum:

```text
schema / status=reserved / consumed=true
grant=RC036
row / ordinal
reserved_at_utc
HEAD / origin / stable tag
RC035 implementation commit and patch SHA-256
portable and Windows evaluator SHA-256
runtime source path and SHA-256
external harness path and SHA-256
pre-execution audit/report path and SHA-256
selected --row value
required prior marker/result SHA-256 bindings
```

Markers are immutable and are never rewritten.

Each row result must bind its marker SHA-256, child command identity, exit code, stdout/stderr hashes, parsed evidence hash, signed transcript/controller evidence, security flags, cleanup evidence and source/workspace preservation.

No `File.Replace`, overwrite, delete, reset or marker-finalization mutation is permitted. If terminal-result creation fails after marker reservation, the row remains consumed; do not rerun it. Preserve all evidence and require a separate recovery decision.

### Failure and no-rerun semantics

On the first failed, uncertain or incompletely terminalized row:

```text
stop immediately
preserve every existing marker/result/log byte-for-byte
do not execute any remaining RC036 row
never rerun a row that already passed or was consumed
do not delete or reset a marker
do not create MATRIX_RESULT
```

A failed-row retry or authorization of unstarted rows requires a new explicit Roadmap Change with new grant-specific marker identities. Previous passed rows remain permanently accepted and must not be repeated.

### Required row acceptance

`live_pass`:

```text
terminal_status=compile_ast_attested_passed
boundary_ok=true
check_passed=true
result_sha256 present
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```

`authentic_syntax_failure`:

```text
terminal_status=compile_ast_attested_failed
boundary_ok=true
check_passed=false
result_sha256 present
genuine bounded SyntaxError evidence
trusted_interpreter_executed=true
changed_source_processed=true
changed_source_ast_parsed=false
changed_source_compiled=false
changed_code_executed=false
execution_authorized=false
```

`signed_post_ready_boundary_failure`:

```text
terminal_status=compile_ast_boundary_failed
boundary_ok=false
check_passed=false
result_sha256=null
valid signed controller evidence
evaluator-private post-ready/pre-authorization source substitution proven
changed_code_executed=false
execution_authorized=false
```

Every accepted row additionally requires fresh snapshot/plan, runtime bundle/lease, V1C2C0 transaction, request ID, plan fingerprint, lease fingerprint, controller public key and Windows Sandbox instance; no cross-row reuse; unchanged source/workspace; all processes exited; artifacts removed; no forced cleanup.

### Pipeline and implementation invariants

The Windows evaluator remains unwired from normal `check` and all targeted pipeline flows. Active rows may only be entered by the exact external one-shot authority harness. No tracked source mutation is authorized by RC036. V1C2C2 production code and public API remain immutable.

The historical V1C2C3 identity remains historical evidence identity only:

```text
b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
```

### RC036 execution gate

This docs commit defines the grant contract but does not itself start or arm a row.

```text
RC036       CURRENT / ONE-SHOT MATRIX AUTHORITY CONTRACT
            PRE-EXECUTION HARNESS AUDIT REQUIRED

V1C2C3      IMPLEMENTED / COMMITTED / ROW-ISOLATED
            ACTIVE MATRIX CONTRACT OPEN
            0 OF 3 ROWS CONSUMED
            NO ROW EXECUTED

active env                         ABSENT
row markers/results                0 / 0
Windows evaluator pipeline refs   0
Sandbox                            NOT LAUNCHED
```

**Next Exact Action:** perform a READ-ONLY / HOST-ONLY audit of the exact committed evaluator CLI/output and build an external one-shot RC036 authority harness. The harness may undergo parser/source review, disposable exclusive-create self-tests, child-environment/argv construction tests, marker/result schema tests and exact SHA measurement only. Stop before creating any permanent RC036 marker, setting child active authority or invoking the Windows evaluator.

## Roadmap Change 037 — V1C2C3 non-active evaluator path-budget hardening after partial RC036 consumption

**Причина:** the exact read-only RC036 path-length root-cause audit completed at `HEAD / origin/main a0a352fe19e843a4f7b80c0e26a6b938520a9056` with repository mutation `NONE`, active environment absent and Sandbox process set empty. The report is fixed at `30591` bytes and SHA-256 `6e3269faf9ade9bbde51e5b123ffec87ed65590dd7c5cfd64f6bb2d82d309b25`.

The audit proved that RC036 is irreversibly PARTIALLY CONSUMED / FAILED and MUST NOT BE RERUN:

```text
live_pass:
    PASSED / CONSUMED / IMMUTABLE / MUST NOT BE RERUN

authentic_syntax_failure:
    INFRASTRUCTURE-FAILED / CONSUMED / IMMUTABLE
    no authentic compile/AST syntax evidence was reached

signed_post_ready_boundary_failure:
    NOT STARTED / NOT CONSUMED
    NOT AUTHORIZED UNDER FAILED RC036

RC036 MATRIX_RESULT:
    ABSENT / MUST REMAIN ABSENT
```

The accepted live-pass marker/result and the failed syntax marker/result remain permanent byte-for-byte evidence. No RC036 marker/result may be deleted, rewritten, replaced, renamed, finalized in place or reused.

The root cause is evaluator-private workspace path amplification before any plan, runtime lease, claim transaction, composition attestation or Sandbox launch:

```text
repository_root length:               219
failing Git loose-object path length: 274
classic Windows path limit:           260
over limit by:                        14
```

The long path was produced by repeating the canonical row name in the temporary prefix, row directory and task/workspace identity. The production compile/AST composition, workspace production implementation, package-boundary registry and pipeline are not the defect.

**Что меняется:** RC037 opens exactly one NON-ACTIVE two-file evaluator path-budget hardening candidate:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
```

No other tracked file may change under RC037.

The Windows evaluator candidate must introduce the exact evaluator-private mapping:

```python
ROW_PATH_LABELS = {
    "live_pass": "p",
    "authentic_syntax_failure": "s",
    "signed_post_ready_boundary_failure": "b",
}
```

and must use the shortened private fixture recipe:

```text
TemporaryDirectory prefix = sv3-
row_root                  = parent / ROW_PATH_LABELS[row]
task_id                   = v3-<row label>
```

The canonical row strings remain unchanged in CLI choices, signed evidence, output sections, consumed markers and terminal results. The mapping is only for evaluator-private fixture paths.

The portable evaluator candidate must statically prove at minimum:

```text
exact ROW_PATH_LABELS mapping
all three canonical row names remain unchanged
short temporary prefix is exactly sv3-
row_root uses only the private label
fixture task_id uses only v3-<label>
no production API or caller path override is introduced
simulated worst-row loose-object path length <= 210
classic MAX_PATH headroom >= 50
Windows evaluator remains absent from every pipeline flow
RC036 permanent evidence remains immutable
```

The audited proposed path is `194` characters for every row, leaving `66` characters of classic Windows path headroom.

RC037 verification is strictly non-active and may perform only:

```text
Python AST/syntax/compile checks for the exact two-file candidate
git diff --check
portable V1C2C3 evaluator
unchanged package-boundary evaluator
source-only pipeline topology verification
full check only after Windows evaluator pipeline references remain 0
Runtime Architecture Audit
exact two-file candidate identity and patch measurement
RC036 immutable evidence re-verification
Sandbox process set empty verification
```

RC037 does NOT authorize:

```text
running the Windows evaluator, including guard-only invocation
setting SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED=1
launching Windows Sandbox
creating any RC037 or RC038 consumed/result marker
retrying RC036 live_pass
retrying RC036 authentic_syntax_failure
running the unstarted RC036 boundary row
creating RC036 MATRIX_RESULT
modifying production/workspace modules, pipeline.py or package boundaries
```

The future recovery model is not active authority under RC037. After exact candidate implementation, commit, docs closure and a fresh readiness audit, a separate later Roadmap Change may define recovery authority. The intended later model is:

```text
preserve and bind accepted RC036 live-pass RESULT; never rerun live_pass
one fresh grant-specific syntax-failure retry
one fresh grant-specific boundary-failure run
new recovery matrix result binds:
    RC036 live-pass result
    + future accepted syntax result
    + future accepted boundary result
```

Any future recovery markers/results must use new grant-specific names and must never overwrite or impersonate RC036 evidence.

Operational state under RC037:

```text
RC036       FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN
RC037       CURRENT / NON-ACTIVE PATH-BUDGET HARDENING ONLY

V1C2C3      LIVE PASS ACCEPTED FROM RC036
            SYNTAX ROW INFRASTRUCTURE-FAILED / CONSUMED IN RC036
            BOUNDARY ROW NOT STARTED
            PATH-BUDGET HARDENING CURRENT
            ACTIVE RECOVERY BLOCKED

Windows evaluator execution      FORBIDDEN
Windows evaluator pipeline refs  0
active authority                  NONE
Sandbox                           NOT AUTHORIZED
future recovery Roadmap Change   NOT CREATED
```

**Next Exact Action:** create the exact two-file RC037 path-budget hardening candidate and perform only the allowed non-active verification. Stop before candidate commit for exact evidence review. Do not create a recovery harness or later active-authority Roadmap Change yet.
## V1C2C3 RC037 IMPLEMENTATION CLOSURE — NON-ACTIVE VERIFIED

**Статус:** RC037 `COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED`.

Exact implementation closure:

```text
implementation commit:   7eddbb1614d726a8267eca2f57851ae384293616
implementation parent:   3bee5567a2a02b907af7422e503abad1e37db567
subject:                 fix: shorten V1C2C3 evaluator private paths
exact scope:             2 evaluator files
patch bytes:             9431
patch SHA-256:           fcf035632798e0561c78a3d5d1438ac5b45735bf8afabb127fe10f0150ab3690

portable evaluator:
  bytes:                 35288
  SHA-256:               68372cd661166d4c34dad050ef73b8d118022aa93c8013e68a0bad5941f9961b

Windows evaluator:
  bytes:                 28758
  SHA-256:               fdc8fdb4a52bf030c7486180db759ccb0a9a70490578881b6c12aa4fa620b1cb

private path mapping:
  live_pass                           -> p
  authentic_syntax_failure            -> s
  signed_post_ready_boundary_failure  -> b

simulated worst Git object path: 194
classic Windows path headroom:   66
```

Pre- and post-commit package boundaries, portable V1C2C3 evaluator, full `check` and Runtime Architecture Audit all passed. The Windows evaluator remained unwired (`0` pipeline references) and was not executed. No production, workspace, pipeline or package-boundary file changed.

RC036 evidence remains immutable: `live_pass` is PASSED / CONSUMED / IMMUTABLE; the RC036 syntax attempt is INFRASTRUCTURE-FAILED / CONSUMED / IMMUTABLE; the RC036 boundary row was never started; `V1C2C3_RC036_MATRIX_RESULT.json` remains absent and must remain absent.

Operational state after RC037 closure:

```text
RC036  FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN
RC037  COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED

V1C2C3 live-pass evidence            ACCEPTED FROM RC036 / IMMUTABLE
V1C2C3 syntax recovery               BLOCKED PENDING NEW ROADMAP AUTHORITY
V1C2C3 boundary recovery             BLOCKED PENDING NEW ROADMAP AUTHORITY
V1C2C3 active recovery               BLOCKED

Windows evaluator pipeline refs      0
active authority                     NONE
RC038                                ABSENT / NOT CREATED
```

**Следующее решение не выдаётся этой записью.** Сначала требуется отдельный fresh read-only recovery-readiness audit, который должен доказать безопасную связку существующего accepted RC036 `live_pass` с одной новой syntax-retry authority и одной новой boundary authority. Только после отдельного review такого audit может быть спроектирован новый Roadmap Change; RC037 не предоставляет active authority.
## Roadmap Change 038 — V1C2C3 split-provenance two-row recovery authority

**Причина:** RC036 завершился как `FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN`. Его `live_pass` принят и остаётся immutable historical evidence; RC036 syntax-marker consumed, но результат не принят из-за evaluator-private path infrastructure failure; RC036 boundary row не запускался. RC037 устранил только evaluator-private path amplification и закрыт как non-active verified.

Fresh recovery-readiness audit:

```text
report SHA-256:
6e58cc14dd4e1047b556ae8ae6ca8372ce83bef2904ff114e573bcec18ee9ace

decision:
RC038 recovery authority may be drafted = TRUE
active recovery authorized now = FALSE
```

### Split provenance

RC038 не повторяет `live_pass`. Recovery matrix обязана явно связывать две разные provenance-ветви:

```text
historical accepted branch:
  grant:                         RC036
  row:                           live_pass
  historical HEAD:               a0a352fe19e843a4f7b80c0e26a6b938520a9056
  historical Windows evaluator:  d7135796b2cbb29d68a41ee3c391c3f0579c6b570da30ac3cd41d9a09fb849dd
  historical portable evaluator: 281c75d9237baacb7f3631069c1af0d95a1eecc052dae78587a2b6367e08abbb
  production composition:        748431106ed01d9898546c55799a4948424aa3e2eaed67181fce8110bbaea992
  marker SHA-256:                 d944ae6b96a644563992b4f5354837b00be6156dbe90f989ac15bd5f39020f0c
  result SHA-256:                 30f1938b23febce463c17c5104d8d5b509b9b549322b2c81e7f03d4514cd85fc
  request_id:                     e7185cc61aecaae11cdb6480a976dc8a
  plan fingerprint:               ee623f0157b04d2a8e9846f2c5c00db9a4852ba1a0d7d5071922c86eadb24bf3
  runtime lease fingerprint:      2d6b6b1d549d5eddc90e84c69c593c03e6b5c0aede2ce1c1dca395319d13744f
  controller public key SHA-256:  7b1d46f608f0f43a34b3934179d7e77b5d55cd3e88e4b49782ba94a26fb6a466
  rerun:                          FORBIDDEN

fresh recovery branch:
  current Windows evaluator:      fdc8fdb4a52bf030c7486180db759ccb0a9a70490578881b6c12aa4fa620b1cb
  current production composition: 748431106ed01d9898546c55799a4948424aa3e2eaed67181fce8110bbaea992
  row order:
    1. authentic_syntax_failure
    2. signed_post_ready_boundary_failure
```

The final recovery result must preserve split provenance and MUST NOT claim that all three rows were executed under one evaluator identity.

### Exact future RC038 permanent evidence

Fresh row markers:

```text
V1C2C3_RC038_SYNTAX_FAILURE_RETRY_CONSUMED.json
V1C2C3_RC038_BOUNDARY_FAILURE_CONSUMED.json
```

Fresh row results:

```text
V1C2C3_RC038_SYNTAX_FAILURE_RETRY_RESULT.json
V1C2C3_RC038_BOUNDARY_FAILURE_RESULT.json
```

Recovery matrix:

```text
V1C2C3_RC038_RECOVERY_MATRIX_RESULT.json
```

Schemas:

```text
row marker:   skynetvs-v1c2c3-rc038-recovery-row-consumed-v1
row result:   skynetvs-v1c2c3-rc038-recovery-row-result-v1
matrix result:skynetvs-v1c2c3-rc038-recovery-matrix-result-v1
```

Every row marker must be reserved through exclusive create before the child receives active authority. The marker permanently consumes that grant-specific attempt regardless of child/result outcome. Each row result is written separately through exclusive create after child completion and evidence verification. No marker is ever rewritten, replaced, finalized in place, deleted or reused.

### Fresh recovery order and fail-stop semantics

1. Revalidate exact immutable RC036 live marker/result and its signed accepted payload. Do not execute `live_pass`.
2. Reserve the RC038 syntax-retry marker.
3. Launch one fresh child process for exactly `authentic_syntax_failure`.
4. Accept only the locked genuine syntax-failure contract.
5. Revalidate cleanup and fresh evidence before proceeding.
6. Reserve the RC038 boundary marker.
7. Launch a second fresh child process for exactly `signed_post_ready_boundary_failure`.
8. Accept only the locked signed boundary-failure contract.
9. Prove syntax/boundary cross-row freshness.
10. Create the recovery matrix result only after all previous conditions pass.

If a fresh row fails or is uncertain:

```text
stop immediately
do not launch the next fresh row
keep all markers/results immutable
do not create the recovery matrix
do not rerun accepted historical live_pass
do not reuse the RC036 syntax marker
require a new explicit Roadmap Change
```

If failure occurs before the first RC038 marker, authority is not consumed, but no automatic retry is allowed; the report must be reviewed first. Once any RC038 marker exists, the RC038 harness MUST NOT be rerun.

### Required fresh evidence

Each fresh row requires its own:

```text
host inspection / workspace snapshot / compile-AST plan
runtime bundle / runtime lease
V1C2C0 claim transaction
request_id
plan fingerprint
runtime lease fingerprint
controller public key
Windows Sandbox instance
child process
cleanup proof
```

The two fresh rows must have pairwise-distinct request/plan/lease/public-key identities. Historical RC036 live evidence is immutable historical provenance and is not part of the fresh cross-row execution set.

### External recovery harness requirements

Before any marker or active row, a separate external recovery harness must be created, SHA-pinned and source-audited. It must:

```text
not import the Windows evaluator
invoke exactly one selected evaluator row per child process
set active authority only in the child environment
keep parent/user active environment absent
pin the resulting RC038 docs commit
pin current evaluator/production/runtime/host identities
verify immutable RC036 evidence before every irreversible boundary
use exclusive create + fsync for markers/results
never use File.Replace / os.replace / rename finalization
remain unwired from normal pipeline flows
stop on first failed or uncertain fresh row
```

RC038 transition state:

```text
RC036       FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN
RC037       COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED
RC038       CURRENT / SPLIT-PROVENANCE TWO-ROW RECOVERY CONTRACT
            PRE-EXECUTION RECOVERY HARNESS AUDIT REQUIRED

historical live_pass               ACCEPTED / IMMUTABLE / NO RERUN
fresh syntax retry                 NOT CONSUMED / NOT EXECUTED
fresh boundary attempt             NOT CONSUMED / NOT EXECUTED
recovery matrix                    ABSENT
active environment                 ABSENT
Windows evaluator pipeline refs    0
Sandbox                            NOT LAUNCHED
```

**Next Exact Action:** create and source-audit the exact external RC038 recovery harness, then run host-only preflight. Stop before creating either RC038 marker or invoking either active row.
## Roadmap Change 039 — V1C1A durable-report sentinel determinism hardening

**Причина:** RC038 host-only preflight остановился на non-active full `check`. Единственным product/evaluator failure оказался V1C1A privacy sentinel `nul_payload_absent`; RC038 permanent evidence не создавалась, Windows evaluator не запускался, active authority отсутствовала.

Fresh targeted recheck на том же HEAD и с тем же evaluator:

```text
V1C1A targeted recheck = PASS
case_count = 37
fail_count = 0
nul_payload_absent = true
```

Fresh source audit:

```text
report bytes:   8492
report SHA-256: 98eb6453312be2acfc9f85567eefe6816f5d5f074af01680f57abbe5e7867a33

fixture:
"binary.dat": b"abc\x00def"

legacy durable-report assertion:
"nul_payload_absent": "abc" not in serialized

serialized scope:
json.dumps(report.to_dict(), ensure_ascii=False)

single 64-hex digest probability of containing "abc":
~1.5025%

false-positive capability:
PROVEN BY CONSTRUCTION
```

The check is therefore flaky: `"abc"` belongs entirely to the SHA-256 hexadecimal alphabet while the durable report intentionally exposes hashed identities. A legal digest may contain that substring even when no raw source bytes or host paths are present.

### Exact RC039 mutable scope

Only:

```text
tools/eval_developer_task_execution_workspace_snapshot.py
```

No production module, workspace implementation, policy, pipeline, package-boundary file, RC038 harness or Windows active evaluator may change.

### Exact intended correction

Within the existing successful V1C1A fixture only:

```text
OLD:
"binary.dat": b"abc\x00def"
"nul_payload_absent": "abc" not in serialized

NEW:
"binary.dat": b"__V1C1A_RAW_BINARY_SENTINEL__\x00def"
"nul_payload_absent": "__V1C1A_RAW_BINARY_SENTINEL__" not in serialized
```

The sentinel contains characters outside the lowercase hexadecimal alphabet (`_`, uppercase letters), so a SHA-256 digest cannot satisfy it by collision. The test continues to assert that recognizable raw fixture bytes do not appear in the durable JSON.

Do not rename the existing result key `nul_payload_absent`; keep the correction minimal and compatibility-preserving.

### Required RC039 verification

Before commit:

```text
exact one-file diff
git diff --check
targeted V1C1A evaluator = 37/37 PASS
package boundaries = PASS
portable V1C2C3 evaluator = PASS
full check = PASS
Runtime Architecture Audit = PASS
RC038 permanent evidence count = 0
Windows evaluator pipeline refs = 0
Sandbox = empty
active authority = absent
```

Repeat the same non-active gates after commit. Push only after exact scope and patch identity are verified.

### RC038 relationship

RC038 remains open but blocked:

```text
RC038 contract                    PRESERVED
RC038 fresh syntax marker         ABSENT / NOT CONSUMED
RC038 fresh boundary marker       ABSENT / NOT CONSUMED
RC038 recovery matrix             ABSENT
RC038 active execution            BLOCKED BY RC039
```

After RC039 implementation + docs closure, rerun a fresh RC038 recovery-harness source/host-only preflight. Only a clean PASS may return the flow to the pre-execution launcher review.

**Next Exact Action:** implement the exact two-line evaluator-only sentinel correction above, run non-active verification, commit/push exact one-file scope, then close RC039. No active RC038 action.
## RC039 IMPLEMENTATION CLOSURE — VERIFIED / COMMITTED

RC039 is closed as:

```text
COMPLETED / IMPLEMENTED / COMMITTED / NON-ACTIVE VERIFIED
```

Exact implementation:

```text
commit:
f773a86b4ddde760f7a10f4722b316ebfd2115a5

parent:
a46aa900c8d077d7f65aab7625b0e7227b1da210

subject:
fix: harden V1C1A raw payload sentinel

scope:
tools/eval_developer_task_execution_workspace_snapshot.py

evaluator bytes:
31066

evaluator SHA-256:
bcd0de47311064067ccce246dc897d9503d266734fb52dd229b58257a6d1c4ad
```

The only semantic change is the replacement of the collision-prone raw privacy sentinel:

```text
OLD raw fixture:
abc\x00def

NEW raw fixture:
__V1C1A_RAW_BINARY_SENTINEL__\x00def

OLD durable-report sentinel:
abc

NEW durable-report sentinel:
__V1C1A_RAW_BINARY_SENTINEL__
```

The previous `abc` sentinel belonged entirely to the lowercase SHA-256 hexadecimal alphabet and could therefore appear accidentally inside a legitimate durable hash identity. The new recognizable sentinel contains characters outside that alphabet and eliminates the false-positive construction while preserving the privacy assertion.

Implementation verification:

```text
pre/post V1C1A targeted evaluator       PASS
pre/post package boundaries             PASS
pre/post portable V1C2C3 evaluator      PASS
pre/post full check                     PASS
pre/post Runtime Architecture Audit     PASS
production/runtime changes              NONE
Windows active evaluator execution      false
Windows evaluator pipeline references   0
RC038 permanent evidence count          0
Sandbox launch                          false
active environment                      ABSENT
```

RC038 relationship:

```text
RC038 contract                          PRESERVED
RC038 historical RC036 live binding     PRESERVED
RC038 syntax retry marker               ABSENT / NOT CONSUMED
RC038 boundary marker                   ABSENT / NOT CONSUMED
RC038 recovery matrix                   ABSENT
```

RC038 active execution remains blocked until a **fresh post-RC039 external recovery-harness source/host-only preflight** passes against this exact committed state.

**Next Exact Action:** rerun a fresh source/host-only audit of the exact RC038 external recovery harness from this post-RC039 HEAD. Stop before the first RC038 permanent marker and before any Windows active evaluator row.
## Roadmap Change 040 — V1C2C3 evaluator-private syntax-fixture reachability correction

**Основание:** точный review двух source bundles на commit `6dd329a788a64c713d86ad4de27a365d6dd363f6`:

```text
SkynetVS_RC040_ExactSourceBundle_20260829_133959.zip
bytes:   58344
SHA-256: b61f26868aca67a5da222c12d32a4f877fd00ef3cbd9dcc67d32a006595dd42d

SkynetVS_RC040_DownstreamAndDocsSourceBundle_20260829_141122.zip
bytes:   282441
SHA-256: 48acc459d73bb964b5cff5276332dcf639bc17e925b9754364747103bb23b26b
```

### Terminal state RC038

RC038 завершён как:

```text
FAILED / PARTIALLY CONSUMED / MUST NOT BE RERUN
```

Его fresh syntax-attempt имеет immutable consumed marker и отдельный failed result. Он был остановлен production static gate до snapshot/plan/runtime:

```text
row:              authentic_syntax_failure
marker consumed:  true
result status:    failed
acceptance_ok:    false
parsed_evidence:  null
root failure:     static_python_syntax_error
actual:           path=module.py;1:12:invalid syntax
```

RC038 boundary row не запускался. RC038 boundary marker/result и RC038 recovery matrix отсутствуют и должны оставаться отсутствующими. Ни launcher, ни harness RC038 нельзя запускать повторно.

### Exact source-derived root cause

Текущий Windows evaluator помещает `b"def broken(:\n"` в workspace **до** `_prepare()`. `_prepare()` запускает настоящий host static check и требует `static_report.ok`. Production workspace snapshot также fail-closed отвергает failed static report.

При этом public Compile/AST plan API:

```python
issue_developer_task_execution_compile_ast_plan(snapshot)
```

не анализирует Python syntax. После атомарного `snapshot.claim_for_plan()` он проверяет mode, size/SHA, отсутствие NUL, strict UTF-8 и LF-only, затем сохраняет exact selected bytes в одноразовый plan material.

Downstream review подтвердил:

```text
claim transaction:
  возвращает exact plan_material и trusted runtime_bundle без преобразования

composition filesystem:
  читает plan_material.exact_source_bytes(...)
  повторно проверяет size/SHA
  записывает exact bytes в private input/sources
  повторно сверяет materialization identity

trusted guest runner:
  проверяет exact source identity
  выполняет ast.parse(...) и compile(...)
  ловит genuine SyntaxError
  не выполняет exec/eval/import/top-level code
  возвращает bounded error evidence

contract/controller/verifier:
  принимают signed compile_ast_attested_failed
  boundary_ok = true
  check_passed = false
  changed_code_executed = false
  reusable_lease_issued = false
  execution_authorized = false
```

Production behavior исправлять не требуется. Противоречие находится только в evaluator fixture reachability.

### Locked RC040 architecture

RC040 выбирает evaluator-private scoped substitution **только во время настоящего public plan issuance**:

```text
1. Создать ordinary workspace с синтаксически валидным placeholder Python.
2. Успешно пройти настоящий static check.
3. Создать настоящий production workspace snapshot.
4. Только для syntax row открыть узкий unittest.mock.patch.object context:
   - DeveloperTaskExecutionWorkspaceSnapshotMaterial.entry
   - DeveloperTaskExecutionWorkspaceSnapshotMaterial.exact_file_bytes
5. Только для module.py вернуть genuine invalid bytes:
   b"def broken(:\n"
   и согласованные size/SHA при сохранённом mode.
6. Внутри этого context ровно один раз вызвать настоящий public
   issue_developer_task_execution_compile_ast_plan(snapshot).
7. Немедленно закрыть context.
8. Доказать восстановление обоих class methods до runtime bundle, lease,
   claim transaction, composition и Sandbox.
9. Продолжить обычную production chain без дальнейших substitutions.
```

Snapshot остаётся честным attestation валидного placeholder workspace. Он **не** объявляется attestation invalid source. Invalid plan bytes имеют отдельную явную evaluator-only provenance:

```text
fixture_provenance =
eval_private_scoped_snapshot_material_substitution_v1

ordinary_production_ingress = false
production_public_plan_api_used = true
snapshot_capability_consumed = true
plan_material_contains_exact_invalid_source = true
substitution_scope = plan_issuance_only
snapshot_material_methods_restored_before_runtime = true
```

Runtime SyntaxError, signed terminal, claim transaction, materialization, runner и verifier остаются настоящими. Только происхождение invalid test bytes является evaluator-private и должно быть явно отражено в evidence.

### Exact RC040 mutable scope

Только:

```text
tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py
tools/eval_developer_task_execution_compile_ast_live_acceptance.py
tools/eval_developer_task_execution_compile_ast_plan.py
```

Назначение:

```text
Windows live evaluator:
  реализовать syntax-only scoped plan-material substitution и provenance evidence

portable V1C2C3 evaluator:
  зафиксировать structural/provenance boundaries и неизменность pass/boundary flows

V1C1B plan evaluator:
  non-active positive proof, что syntax-invalid, но UTF-8/LF/NUL-safe bytes
  запечатываются настоящим public plan API без выполнения кода
```

### Explicit prohibitions

RC040 не разрешает изменять:

```text
modules/developer/**
tools/pipeline.py
tools/eval_package_boundaries.py
RC038 launcher/harness
RC036/RC038 permanent evidence
```

Запрещено:

```text
ослаблять static_check.ok или production snapshot validation
добавлять public raw-source/fault-injection arguments
обращаться к private plan/snapshot registry или constructor keys
создавать synthetic production plan вручную
оставлять patch context активным после plan issuance
применять syntax substitution к live_pass или boundary row
запускать Windows active evaluator или Sandbox под RC040
```

### Required non-active verification

До и после implementation commit:

```text
exact three-file scope
Python syntax/AST
git diff --check
targeted V1C1B plan evaluator
portable V1C2C3 evaluator
package boundaries
full check
Runtime Architecture Audit
Windows evaluator pipeline references = 0
RC036/RC038 immutable evidence preserved
RC038 boundary/matrix evidence absent
active environment absent
Sandbox empty
```

RC040 не предоставляет active recovery authority. После implementation + docs closure требуется fresh readiness review и отдельный новый Roadmap Change, ожидаемо RC041, с новыми grant-specific marker/result names. Он не может повторять или переиспользовать RC038 syntax evidence.

RC040 transition state:

```text
RC036  historical live-pass accepted / immutable
RC038  failed / partially consumed / must not be rerun
RC039  completed / non-active verified
RC040  CURRENT / NON-ACTIVE EVALUATOR-ONLY REACHABILITY CORRECTION

active recovery  BLOCKED
Windows evaluator pipeline refs  0
Sandbox  NOT AUTHORIZED
```

**Next Exact Action:** создать exact three-file RC040 candidate, выполнить только non-active verification и остановиться до commit для review.
