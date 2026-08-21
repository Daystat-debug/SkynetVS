# SkynetVS Architecture Roadmap V1

**Дата фиксации:** 2026-07-30
**Последнее обновление:** 2026-08-21
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

**Статус:** V1B1–V1B4 VERIFIED; trusted-runtime foundation COMPLETE. V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2 VERIFIED; V1C0B2, V1C1 and V1C2 architecture LOCKED; Roadmap Change 021 diagnostic capture COMPLETED / CONSUMED; CURRENT — exactly one V1C2C2 RC022 suspended-worker stage-localization probe in Pro Standard; V1C2C3 BLOCKED.

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

No Sandbox was launched, no transaction was consumed, no runtime lease was claimed, no interpreter ran and no changed source was processed. `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false` remained invariant. V1C2C1R1 is therefore VERIFIED / HOST-ONLY / NON-AUTHORIZING. Roadmap Change 020 subsequently inserted and independently verified V1C2C1R2 and historically reopened V1C2C2 for exact R2 rebinding and one fresh active retry. Roadmap Change 021 records that retry as consumed and failed closed and its one-shot diagnostic capture is now COMPLETED / CONSUMED. Roadmap Change 022 permits exactly one suspended-worker stage-localization probe; V1C2C3 remains BLOCKED.


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

The existing uncommitted seven-file V1C2C2 implementation was rebound to the exact V1C2C1R2 identities without scope growth and temporary failure-only diagnostics were removed. The resulting candidate is fixed at SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`, with policy fingerprint `1cc5a4aedb348f9cb669f2317c3a0a7b24bd11b7bbbd6eadd02907b2b1a8b1e5` and policy-document SHA-256 `71aa6a3228836740411d4c042d12b825cda8337b958771bc8e9ec4579299a5e1`. It remains unaccepted: the one Roadmap Change 020 active retry failed closed with trusted guest-failure evidence, and Roadmap Change 021 permits only one diagnostic capture.

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

**Что меняется:** the Roadmap Change 020 retry is recorded as consumed and failed closed. V1C2C2 remains CURRENT only for one fresh, non-invasive diagnostic capture. A temporary external host harness may wrap the Windows evaluator's imported attestation function solely to serialize the immutable returned `report.to_dict()` and print its issue details. The harness is not production code, is not committed, injects no fault, changes no payload or policy bytes and accepts no new caller-controlled execution surface. It must use fresh host/snapshot/plan/runtime/lease/transaction objects and one fresh Sandbox.

**Что не меняется:** the locked V1C2A1/A2/B/C0 and verified V1C2C1/R1/R2 identities remain immutable; the exact seven-file V1C2C2 candidate remains uncommitted; the stable V1B4 tag does not move; imports/top-level code are not executed; `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false` remain mandatory. V1C2C3 stays BLOCKED.

The diagnostic run is single-use and terminal for Roadmap Change 021. After the report is captured, no full pipeline, code correction, commit or additional Sandbox launch is allowed until the evidence is reviewed. Any next production correction or active retry requires a new explicit Roadmap Change.

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

**Что меняется:** Roadmap Change 021 diagnostic authority is marked COMPLETED / CONSUMED. V1C2C2 remains CURRENT only for one external `V1C2C2P1 — Suspended-Worker Stage-Localization Probe`. The probe may launch at most one fresh Windows Sandbox and may use the exact committed V1C2C1R2 native-helper bytes plus exact read-only runtime and runner mappings solely to localize the failing transition. It may create one fresh standard-user account/token and may create the fixed worker process with `CREATE_SUSPENDED`, assign it to the exact Job Object and inspect the returned state. It must never call `ResumeCompileAstWorker` or otherwise resume the primary thread.

The probe must emit an ordered, durable checkpoint report for:

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

For every failed checkpoint it must persist the complete exception chain, concrete type, `HResult`, Win32 `NativeErrorCode` when present, message and the immediately preceding successful checkpoint. For ACL preparation it must also record owner/protection state and canonical before/after access-rule multiset fingerprints. For process creation it must record whether a process/thread handle was returned, whether the process was assigned to the expected Job Object and whether the primary thread remained unresumed.

**Что не меняется:** this is not an active-composition acceptance retry and is not a production correction. It must not modify or commit the seven V1C2C2 files, must not widen the production API, must not use a V1C2C0 claim transaction, must not claim a runtime lease, must not materialize or process changed source, must not publish normal compile authorization, must not produce accepted result/terminal evidence and must not run the full pipeline. The stable V1B4 tag and all verified V1C2A1/A2/B/C0/C1/R1/R2 identities remain immutable. V1C2C3 remains BLOCKED.

The probe is single-use and terminal for Roadmap Change 022. Success means only that exact stage evidence and cleanup were captured. After the probe, stop. Any production correction or active acceptance run requires a subsequent explicit Roadmap Change grounded in the captured inner exception and checkpoint evidence.

Operational state:

```text
V1C2C1R2 VERIFIED / HOST-ONLY / NON-AUTHORIZING
RC021       COMPLETED / CONSUMED
V1C2C2      CURRENT / RC022 SUSPENDED-WORKER STAGE-LOCALIZATION PROBE ONLY
V1C2C3      BLOCKED
candidate SHA-256: 9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1
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

**Статус:** V1B4A–V1B4D VERIFIED; V1B4 COMPLETE. V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2 VERIFIED; V1C0B2 and V1C1/V1C2/V1C2C architecture LOCKED; RC021 capture COMPLETED / CONSUMED; V1C2C2 CURRENT only for one RC022 suspended-worker stage-localization probe; V1C2C3 BLOCKED; changed-code execution remains false.

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

**Статус:** V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2 VERIFIED through `d200c49`; V1C0B2 external source authority and V1C1/V1C2/V1C2C architecture are LOCKED; RC021 capture is COMPLETED / CONSUMED; exactly one V1C2C2 RC022 suspended-worker stage-localization probe is CURRENT in Pro Standard; V1C2C3 remains BLOCKED and changed-code execution remains false.

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
V1C2C1R2 Shared Output ACL Preservation Correction              VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C2 Active Compile/AST Sandbox Composition                  CURRENT / RC022 SUSPENDED-WORKER STAGE-LOCALIZATION PROBE ONLY
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

The verifier revalidated policy `cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf`, strict canonical document/hash-chain binding, the exact V1C2A2 runner identities and a 64-byte ECDSA-P256 signature through Windows CNG. The post-commit smoke proved `signature_valid`, `chain_verified`, `result_verified` and `terminal_verified` with public-key SHA-256 `0bc654178e6f3d5e4ab8b170722a7b7a388a76d58c97031fcad019cf4bdb5e91`. Authentic syntax failure remains verified evidence with `check_passed=false`, while malformed, substituted, replayed or forged evidence fails closed. The production verifier has no filesystem, process, Sandbox, network, `ast.parse`, `compile`, `exec` or `eval` surface and never grants reusable authority. Sandbox launch, runtime-lease issue/claim, candidate-interpreter execution, changed-source processing, changed-code execution, reusable authority and `execution_authorized` all remained `false`. V1C2B is VERIFIED; V1C2C0 and the original V1C2C1 bundle have since been verified. Roadmap Change 019 inserted and verified V1C2C1R1; Roadmap Change 020 inserted and verified V1C2C1R2 and historically authorized the R2 rebind plus one fresh retry. Roadmap Change 021 capture is COMPLETED / CONSUMED; one RC022 suspended-worker stage-localization probe is CURRENT and V1C2C3 remains BLOCKED.

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

Every active flag remained false: no claim transaction was consumed, no runtime lease was claimed, no runtime or source was materialized, Windows Sandbox and the candidate interpreter were not launched, changed sources were not parsed or compiled, changed code was not executed, no reusable lease was issued and `execution_authorized=false`. V1C2C1 remains VERIFIED historical host-only evidence. V1C2C1R1 and V1C2C1R2 are independently VERIFIED. Roadmap Change 020 historically authorized exact R2 rebinding and one fresh active retry; Roadmap Change 021 records that retry as consumed and failed closed and its diagnostic capture is COMPLETED / CONSUMED. Exactly one RC022 suspended-worker stage-localization probe is CURRENT and V1C2C3 remains BLOCKED.

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

[CURRENT IMPLEMENTATION STAGE]
V1C2C2 — Active Compile/AST Sandbox Composition (R2 candidate preserved; Roadmap Change 021 diagnostic capture completed and consumed; exactly one Roadmap Change 022 suspended-worker stage-localization probe is authorized; no acceptance retry is authorized).

[BLOCKED]
V1C2C3 — Live Pass / Syntax-Failure / Boundary-Failure Acceptance.

[PLANNED AFTER SAFETY KERNEL]
Domain Package Structure V2.

[PLANNED AFTER PRODUCTION PACKAGES]
Tools Package Structure V1.
```

До завершения Developer Safety Kernel дополнительные production-файлы по пакетам не переносятся.
