# SkynetVS Windows Sandbox Lifecycle Attestation V1

## 1. Назначение

Документ фиксирует benign active lifecycle experiment для backend:

```text
traditional_wsb_logoncommand_v1
```

Эксперимент не запускал developer-task manifest checks, код из patch, `python_module`, `pipeline`, dependency installation или host fallback. Итоговый report содержит `execution_authorized=false`.

## 2. Source evidence

```text
Experiment date:        2026-08-05
Report file:            SkynetVS_Windows_Sandbox_Lifecycle_Result_20260805_201319_24fc3d60.json
Report SHA-256:         681a184254bb98663fe0d7830edd323da337ba86724bde2f116919ad5d5d1252
Report schema:          1
Status:                 lifecycle_attested
Failure:                empty
Backend:                traditional_wsb_logoncommand_v1
Policy fingerprint:     5c731d5f246929aa1b59f614d2a01371b086244cc09f2c5846d93531b194af21
Execution authorized:   false
```

Request evidence:

```text
request_id:             24fc3d6012974f7d95ecaccf45bc09af
request SHA-256:        9bac9556b0218a8a52d4d642ce05f10b2716ceb28dbecebe81c735f9a4386039
guest script SHA-256:   efe35f1df67628f9ed4ec080b61adc25caeea8c2ac7cae00152fc762a1d888c3
WSB SHA-256:            7b47b8b0bade76426a77d81b90c897b0376103c0f82b5998611f6304ff89896e
guest result SHA-256:   6fe22dc3e87d78985b9f1eae80a094053033b170274370977bb66af5b764e01e
```

## 3. VERIFIED — Host lifecycle

```text
WindowsSandbox.exe launcher PID: 21544
Known Sandbox process observed:  true
All known processes exited:      true
Forced cleanup attempted:        false
Result received:                 13 514 ms
All processes exited:            23 157 ms
Result-to-exit duration:         9 643 ms
Total experiment duration:       23 164 ms
Launch timeout:                  180 s
Shutdown grace:                  30 s
```

Measured process timeline:

```text
31 ms     before_launch
          process set empty

88 ms     after_launch
          WindowsSandbox.exe PID 21544 present

392 ms    waiting_for_result
          launcher exited
          WindowsSandboxRemoteSession.exe PID 15548 present

13 521 ms result_detected
          WindowsSandboxRemoteSession.exe PID 15548 still present

23 157 ms waiting_for_shutdown
          process set empty

23 163 ms shutdown_wait_complete
          process set empty
```

Архитектурный вывод:

- `WindowsSandbox.exe` является transient launcher;
- launcher PID нельзя использовать как lifetime/session handle;
- persistent host session в этом run представлял `WindowsSandboxRemoteSession.exe`;
- успешный lifecycle должен определяться по всему известному Sandbox process set;
- отсутствие процессов после guest self-shutdown было доказано без forced cleanup.

## 4. VERIFIED — Guest identity and self-shutdown

```text
Guest account:          WDAGUtilityAccount
Guest architecture:     X64
Guest Windows build:    26100
Guest PowerShell:       5.1.26100.8875
Shutdown command:       shutdown.exe /s /t 5 /f
Shutdown scheduled:     true
Shutdown exit code:     0
```

## 5. VERIFIED — Mapping and network controls

Все host validation fields равны `true`, включая:

- strict UTF-8;
- exact top-level/result control fields;
- schema/backend/policy/request/nonce/hash matches;
- trusted guest result;
- guest self-shutdown;
- input mapping read-only;
- output mapping writable;
- IPv4 isolation;
- IPv6 isolation.

Guest evidence:

```text
IPv4 default route present:       false
IPv4 external TCP reachable:      false
IPv6 default route present:       false
IPv6 external TCP reachable:      false
Input write attempt:              access denied
Output write probe:               success
```

## 6. Production state machine derived from evidence

```text
host_verified
    ↓
artifacts_prepared
    ↓
sandbox_launched
    ↓
known_process_observed
    ↓
trusted_result_received_and_validated
    ↓
guest_self_shutdown_scheduled
    ↓
all_known_sandbox_processes_exited
    ↓
result_bytes_reverified_after_exit
    ↓
host_evidence_reverified
    ↓
artifacts_removed
    ↓
lifecycle_attested
```

Failure rules:

- result timeout, invalid evidence or shutdown timeout never authorizes execution;
- forced termination is best-effort cleanup only;
- forced termination can never convert a failed run into success;
- artifacts are not removed until process absence is proven;
- unproven process state returns `failed_active`;
- `execution_authorized` remains `false` throughout V1B2.

## 7. Limits of this attestation

This experiment proves the trusted lifecycle probe only. It does not prove result authenticity after untrusted patched code can write to the output mapping. That boundary remains V1B3:

```text
Signed Result Authenticity and Privilege Separation
```

Until V1B3/V1B4/V1C are complete, the following remain blocked:

```text
python_module
pipeline
host fallback
arbitrary shell
dependency installation
patched-code execution
```

## 8. Production closure — V1B2

Экспериментальная state machine была реализована в production:

```text
eb2a476 feat: add trusted Windows Sandbox lifecycle gate
4ea2e0c fix: isolate Windows Sandbox launch environment
```

Финальная проверенная точка:

```text
Lifecycle unit eval:                         39/39
Real Windows active lifecycle smoke:        3/3
developer_task_execution_backend_lifecycle: completed successfully
full check:                                 completed successfully
execution_authorized:                       false
```

Production hardening после первого запуска:

- `SystemDrive` передаётся явно и не остаётся буквальным `%SystemDrive%`;
- `WindowsSandbox.exe` запускается с фиксированным trusted working directory
  `C:\Windows\System32`;
- project root не используется как current working directory Sandbox-процесса;
- удаляемый lifecycle artifact root не используется как process working directory;
- временные lifecycle-каталоги удаляются после успешного exit без
  `TemporaryDirectory` cleanup race;
- успешный run по-прежнему требует полного исчезновения известного Sandbox
  process set;
- patched-code execution, `python_module`, `pipeline` и host fallback остаются
  заблокированы.

Текущий следующий этап:

```text
V1B3 — Signed Result Authenticity and Privilege Separation
```
