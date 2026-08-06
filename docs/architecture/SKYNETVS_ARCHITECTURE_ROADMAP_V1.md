# SkynetVS Architecture Roadmap V1

**Дата фиксации:** 2026-07-30
**Последнее обновление:** 2026-08-06
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

**Статус:** CURRENT / V1B1 и V1B2 VERIFIED; следующий срез — V1B3.

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

**Статус:** CURRENT / security architecture reviewed; implementation split into four evidence slices.

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

- proves WDAGUtilityAccount administrator bootstrap;
- proves one-time Scheduled Task execution as `S-1-5-18`;
- proves SYSTEM access to the three mapped roots;
- proves ephemeral ECDSA P-256 key generation and public-only export;
- proves local standard-user token creation and suspended worker launch;
- proves Job Object membership, kill-on-close and worker-SID process sweep;
- returns `execution_authorized=false`.

##### V1B3B — Canonical Transcript and Host Signature Verifier

- immutable schemas for `request`, `ready`, `authorize` and signed terminal payload;
- exact-byte pinning and hash-chain validation;
- ECDSA P-256/SHA-256 verification with the public key pinned before authorization;
- replay, substitution, duplicate/unknown field and post-exit mutation guards.

##### V1B3C — Standard-User Worker Isolation Gate

- fresh local standard account per run;
- non-inherited environment and handles;
- suspended `CreateProcessAsUserW` launch;
- kill-on-close Job Object with no breakaway;
- worker-SID process sweep and account cleanup;
- benign worker only.

##### V1B3D — Active Signed Boundary Composition

- composes V1B2 lifecycle, V1B3B transcript verification and V1B3C worker isolation in one Sandbox instance;
- signs only after worker tree termination and worker-SID process absence are proven;
- preserves `execution_authorized=false` until V1B4 and V1C.

The V1B2 policy fingerprint remains the historical lifecycle baseline. A production V1B3 policy schema/fingerprint is not changed until V1B3A experiment evidence is reviewed.

## Roadmap Change 003 — V1B3 split into measured security slices

**Причина:** traditional `.wsb` proves the container lifecycle but does not directly provide a SYSTEM controller, authenticated writable output or a standard-user worker boundary. Those properties must be independently measured before production composition.

**Что меняется:** V1B3 is implemented as V1B3A/V1B3B/V1B3C/V1B3D.

**Что не меняется:** V1B4 and V1C remain blocked; patched code is not executed; host fallback, arbitrary shell and dependency installation remain forbidden; `execution_authorized=false`.

#### V1B4 — Trusted Python Runtime Bundle Gate

- принимает только pinned read-only runtime bundle;
- проверяет canonical file manifest и aggregate SHA-256;
- не скачивает и не устанавливает зависимости;
- аттестует Python version, stdlib и разрешённые dependency imports внутри guest;
- связывает runtime fingerprint с host/policy/lifecycle/result-boundary evidence;
- создаёт immutable final capability report и non-serialized single-use token для V1C.

#### Freshness и использование capability

Final execution capability действителен не более 300 секунд и только при совпадении:

- host boot identity;
- Windows build;
- Sandbox executable path/version/SHA-256;
- canonical backend policy fingerprint;
- runtime bundle fingerprint;
- one-time capability token.

V1C всё равно повторяет network, privilege и signed-result checks в том же Sandbox instance до исполнения изменённого кода. Старый active-attestation JSON или documentation evidence самостоятельно не разрешает executable checks.

**Аттестованный backend-кандидат на текущем Windows-хосте:**

```text
traditional_wsb_logoncommand_v1
WindowsSandbox.exe 10.0.26100.8875
.wsb + LogonCommand
read-only input mapping
dedicated writable result mapping
network disabled
wsb CLI отсутствует
```

### V1C — Sandboxed Executable Checks

**Статус:** PLANNED / BLOCKED до V1B.

Только через production-attested backend:

- `python_module`;
- `pipeline`.

Без `shell=True`, без произвольных строк команд, без сети по умолчанию, без установки зависимостей и без host fallback.

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

[CURRENT ARCHITECTURE STAGE]
Typed Check Runner V1B3 — Signed Result Authenticity and Privilege Separation Gate.

[NEXT]
V1B3 Signed Result Boundary → V1B4 Trusted Runtime → V1C Sandboxed Checks → Result and Evidence V1.

[PLANNED AFTER SAFETY KERNEL]
Domain Package Structure V2.

[PLANNED AFTER PRODUCTION PACKAGES]
Tools Package Structure V1.
```

До завершения Developer Safety Kernel дополнительные production-файлы по пакетам не переносятся.
