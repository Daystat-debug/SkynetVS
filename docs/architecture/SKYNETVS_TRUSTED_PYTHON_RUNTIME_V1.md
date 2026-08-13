# SkynetVS Trusted Python Runtime V1

## 1. Статус

```text
V1B3  — VERIFIED
V1B4A — VERIFIED
V1B4B — VERIFIED
V1B4C1 — VERIFIED
V1B4C2A — VERIFIED
V1B4C2B — VERIFIED
V1B4D — VERIFIED
V1B4   — COMPLETE
V1C    — NEXT / EXECUTION BLOCKED
```

Этот документ фиксирует threat model, source-provenance model, deterministic bundle model, active attestation и handoff-контракт для `Typed Check Runner V1B4 — Trusted Python Runtime`.

Документ не разрешает запуск кода из patch. До V1C обязательны:

```text
patched-code execution  BLOCKED
python_module           BLOCKED
pipeline                BLOCKED
host fallback           FORBIDDEN
dependency installation FORBIDDEN
execution_authorized    false
```

## 2. Проверенная стартовая точка

```text
18e8619 feat: add same-run trusted runtime capability lease
```

The active signed boundary beneath V1B4 remains the verified `f3f5607` composition. V1B4B adds the exact CPython 3.13.15 runtime capability, V1B4C1 locks the guest payload, and V1B4C2A independently verifies the signed runtime transcript without launching Sandbox or Python.

Подтверждено одним production Windows Sandbox run:

```text
V1B3D unit/failure gate: 40/40
V1B3D active Windows:     3/3
status:                   active_signed_boundary_attested
signature_valid:          true
all_processes_exited:     true
forced_cleanup_attempted: false
artifacts_removed:        true
execution_authorized:     false
```

V1B4 строится поверх уже подтверждённой цепочки `V1B1 + V1B2 + V1B3B + V1B3C + V1B3D`; ни один старый active report не используется как самостоятельное разрешение нового run.

## 3. Почему host `.venv` не является trusted runtime bundle

Текущий host runtime:

```text
CPython 3.12.10
AMD64 / 64-bit
C:\Project\SkynetVS\.venv\Scripts\python.exe
base runtime: C:\Users\User\AppData\Local\Programs\Python\Python312
```

Host `.venv` не принимается как V1B4 source, потому что он:

- зависит от абсолютного host path и установленного base interpreter;
- содержит mutable `site-packages` и `pip`;
- смешивает project dependencies, optional Whisper dependencies и host tooling;
- не является application-local deterministic distribution;
- может измениться независимо от task manifest;
- не имеет canonical archive provenance и exact extracted-tree contract;
- не должен целиком передаваться недоверенному worker.

V1B4 использует отдельный application-local runtime artifact, а не копию host virtual environment.

## 4. Runtime source provenance and selected execution candidate

V1B4A verified two official Windows embeddable distributions without executing either candidate:

```text
CPython 3.12.10 AMD64  provenance reference
CPython 3.13.15 AMD64  selected execution candidate
```

Pinned CPython 3.13.15 source:

```text
kind:            CPython Windows embeddable package
version:         3.13.15
architecture:    AMD64
file:            python-3.13.15-embed-amd64.zip
source SHA-256:  d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf
SPDX SHA-256:    ba428f93acb06764f0005246f8ca48bb1c04feef64ce7db0b177fb2fd371c423
source fingerprint:
6027ca87d35d94fa131d64c8210e5c6f5002f801274752421e480a9a180dba45
provenance policy fingerprint:
232d65ce4fdb9d990e588f15133db3593cb69f31c5d4e3dfece28b79b827c503
```

CPython 3.12.10 remains useful historical provenance evidence but is not the V1B4 execution candidate. No provenance run launched either interpreter, and every report retained `execution_authorized=false`.

## 5. V1B4 разделён на четыре evidence-среза

### V1B4A — Runtime Source Provenance Gate

**Status:** VERIFIED.

The host-only gate did not launch the candidate interpreter. It verified exact official archive/SPDX bytes, safe ZIP structure, required embeddable files, AMD64 PE identity, upstream `_pth`, outer and stdlib manifests, the sole inert `site-packages/README.txt` placeholder and absence of executable package-management surfaces.

Result:

```text
CPython 3.13.15 source fingerprint:
6027ca87d35d94fa131d64c8210e5c6f5002f801274752421e480a9a180dba45
interpreter_executed=false
execution_authorized=false
```

### V1B4B — Deterministic Runtime Bundle Gate

**Status:** VERIFIED / `05e0e00`.

Derived bundle contains:

```text
33 exact upstream passthrough files
1 project-owned locked python313._pth
1 fixed trusted runtime probe
1 fixed trusted runtime runner
1 canonical runtime_manifest.json
37 files total
```

Verified identity:

```text
tree manifest:          ab35bf73bf387d28cd14bdcf85c545706ae7522212f466bf10afbaf1e14ac7ed
bundle fingerprint:     1c98ad24ec3e4bb1b8b4bcd530ffedcf6ff62a6fee5b94cb795f6c84fb1c8c4b
runtime manifest:       41503dc1b9c109b6cfb652e6ff320b5011c78f529f3559720ad1788f4787967d
locked python313._pth:  44b7d2b931284d125d88b833eaa28c711504aafd49415bd5bcc7c076a4d18006
trusted probe:          33b74a058990ae4f9f0077cb6cbfaa60ad266050d04cf670121d96db929e5c9d
trusted runner:         d03e21a1867914b87dec61de67bfd0f80637ab5b15948e8d8e6d73839a322de1
launch contract:        8fedb32153b6227a61b699dd5a34d610c430883b4ddafc96f931f0757138cef6
```

The builder re-verifies source bytes, uses fresh exclusive staging, rereads exact disk bytes, rejects reparse/special entries, removes staging and returns a non-serialized exact-byte capability. It never accepts task/patch/workspace/command input and never launches Python, Sandbox or dependencies.

### V1B4C — Active Trusted Runtime Attestation

V1B4C is split into three independently reviewable claims:

```text
V1B4C1   Runtime Attestation Contract and Payload Gate   VERIFIED
V1B4C2A  Signed Runtime Transcript Verifier              VERIFIED
V1B4C2B  Active Trusted Runtime Composition              VERIFIED
V1B4D    Same-Run Runtime Capability Lease                CURRENT
```

#### V1B4C1 — Runtime Attestation Contract and Payload Gate

Verified code closure:

```text
9a85bb1 feat: add trusted runtime attestation contract payload
```

Verified evidence:

```text
portable contract/payload gate:       33/33
Windows compile/parse-only smoke:       3/3
targeted flow:          completed successfully
full check:             completed successfully
Sandbox launched:                     false
interpreter executed:                 false
execution_authorized:                 false
```

V1B4C1 introduced the immutable runtime-attestation policy/schema, strict canonical documents and exact SYSTEM-controller/native-helper/bootstrap/four-folder `.wsb` payload. It binds all V1B4B identities and preserves the standard-user/Job/SID cleanup boundary without performing an active run.

#### V1B4C2A — Signed Runtime Transcript Verifier

**Status:** VERIFIED / `4a68c3c`.

Verification closure:

```text
portable signed-runtime verifier:             46/46
Windows CNG signed-runtime verification:       3/3
targeted verifier flow:         completed successfully
full check:                      completed successfully
runtime architecture audit:                    9/9
Windows Sandbox launched:                     false
candidate interpreter executed:               false
execution_authorized:                         false
```

The verified host-only boundary enforces strict C1 contract types and canonical bytes, request/ready/authorize/runtime-result/terminal cross-document binding, anti-replay nonces, bounded phase windows, exact post-pin stability, P-256 public-key validation, exact runtime-result/terminal hash chains and Windows CNG verification of the raw 64-byte ECDSA signature.

The verifier contains no filesystem staging, process launch, Sandbox lifecycle, runtime-builder, workspace or candidate-Python execution surface. Its successful pin and final reports remain immutable, redacted and non-authorizing.

#### V1B4C2B — Active Trusted Runtime Composition

**Status:** VERIFIED / `049e4ca`.

Verification evidence:

```text
portable state/failure gate:                   42/42
active Windows composition:                     3/3
status:                    active_trusted_runtime_attested
runtime bundle fingerprint: 1c98ad24ec3e4bb1b8b4bcd530ffedcf6ff62a6fee5b94cb795f6c84fb1c8c4b
payload fingerprint:        47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13
pin/signature/runtime/terminal verified:          true
all Sandbox processes exited:                    true
forced cleanup attempted:                        false
artifacts removed:                                true
interpreter_executed:                             true
reusable_lease_issued:                            false
execution_authorized:                             false
targeted flow:                     completed successfully
full check:                        completed successfully
runtime architecture audit:                        9/9
```

The verified production run performed:

```text
fresh host/backend evidence
    ↓
rebuild exact V1B4B capability from pinned source ZIP
    ↓
materialize and reread exactly 37 runtime files
    ↓
materialize exact V1B4C1 Input/Control payload bytes
    ↓
prepare private Input/Runtime/Control/Output roots
    ↓
launch one Windows Sandbox instance
    ↓
SYSTEM controller verifies every runtime and payload byte
    ↓
V1B4C2A pins request + ready + authorize in memory
    ↓
host re-reads pinned bytes before publishing authorize.sha256
    ↓
fresh standard-user token with sanitized environment
    ↓
explicit C:\SkynetVSRuntime\python.exe
    ↓
CREATE_SUSPENDED → Job Object → ResumeThread
    ↓
fixed trusted runner/probe only
    ↓
Job close + worker-SID quiescence + exact account deletion
    ↓
signed terminal transcript
    ↓
all Sandbox processes exited
    ↓
post-exit exact-byte reread + V1B4C2A/CNG verification
    ↓
fresh host evidence revalidation + safe artifact cleanup
```

The production API is limited to:

```python
attest_developer_task_execution_runtime_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    runtime_zip: Path,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionRuntimeCompositionReport
```

It accepts no task, patch, workspace, module, pipeline, arbitrary executable, argv, environment additions or shell commands.

The exact implementation scope is locked to:

```text
A modules/developer/developer_task_execution_runtime_composition.py
A modules/developer/developer_task_execution_runtime_composition_fs.py
A tools/eval_developer_task_execution_runtime_composition.py
A tools/eval_developer_task_execution_runtime_composition_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

`developer_task_execution_runtime_composition_fs.py` owns no-follow path validation, exclusive materialization, exact disk reread and bounded cleanup. `developer_task_execution_runtime_composition.py` owns only typed orchestration, state transitions, transcript pinning/verification and immutable evidence. Existing V1B4C1 payload, V1B4C2A verifier and V1B2 Windows Sandbox process primitives remain unchanged and are reused.

Writable Output is untrusted while Sandbox is active. `ready.json`, `runtime_result.json`, `terminal_payload.json` and `terminal_signature.bin` are progress signals only until every known Sandbox process has exited and the exact bytes have been read again and accepted by V1B4C2A.

Success requires all of the following:

```text
fresh host capability                           true
pre-existing Sandbox process set                empty
exact CPython source and V1B4B capability       verified
37-file runtime materialization and reread      exact
C1 payload materialization and reread           exact
Input/Runtime/Control mappings                  read-only
Output mapping                                  writable
request/ready/authorize pin                      valid before commit
fixed CPython probe process                     standard-user + Job
runtime result                                  canonical and bound
all Sandbox processes exited                    true
post-exit pinned bytes unchanged                true
Windows CNG signature verification              true
post-run host evidence unchanged                true
forced cleanup attempted                        false
all private artifacts removed                   true
execution_authorized                            false
```

Failure-only forced cleanup can never convert a run into success. Unproven process state, pre-existing output, host drift, byte mutation, authorization publication failure, invalid runtime evidence, signature failure, account/SID cleanup failure or host artifact cleanup failure is terminal.

V1B4C2B produces benign capability evidence only. It does not create the V1B4D lease and cannot authorize a later Sandbox run.

#### V1B4C threat model

In scope:

- forged/stale host evidence and pre-existing Sandbox processes;
- writable-output substitution, replay and post-pin mutation;
- inherited environment, registry, user-site, pip and path poisoning;
- wrong runtime/payload bytes, unsafe artifact roots and observable TOCTOU changes;
- Sandbox launcher/remote-session handoff races, timeouts and cleanup failures;
- worker process escape attempts within the measured Job/SID controls.

Trusted assumptions:

- the Windows kernel, Windows Sandbox/hypervisor boundary and current host process/session are trusted;
- the pinned CPython source ZIP and repository code at the verified commits are trusted inputs after exact verification.

Out of scope:

- compromised host kernel or administrator;
- a hostile host-local process with an equivalent user token that can mutate private host artifacts during the run;
- hypervisor/Sandbox escape and unknown guest privilege-escalation vulnerabilities.

### V1B4D — Same-Run Runtime Capability Lease

**Status:** VERIFIED / `18e8619`.

Verification evidence:

```text
portable lease gate:                         36/36
real Windows host-only lease smoke:            5/5
policy fingerprint: 76ceaaf139af10814a403d24fca7455a61db78f095e80d390b360417354e8c18
TTL:                                      300 seconds
clock:                              time.monotonic_ns()
claim exact retained runtime capability:       true
replay rejected:       runtime_lease_already_claimed
concurrent double claim:                one winner
runtime staging cleaned:                       true
Sandbox processes after claim:                    []
interpreter_executed:                           false
execution_authorized:                          false
targeted flow:                   completed successfully
full check:                      completed successfully
runtime architecture audit:                      9/9
```

The production Windows smoke confirmed that issuance and claim remain completely host-only. The boot-epoch claim fix preserves the one-second measured quantization rule only for fresh-host equivalence; the canonical lease fingerprint remains bound to the exact issuance snapshot. Any two-second boot drift or other bound host/runtime change invalidates the lease.

V1B4D is deliberately host-only. It does not use the completed C2B report as authority, does not launch Sandbox or Python and does not accept changed-code inputs.

Planned public issuance API:

```python
issue_developer_task_execution_runtime_lease(
    host_report: DeveloperTaskExecutionBackendHostReport,
    runtime_bundle: DeveloperTaskPythonRuntimeBundle,
) -> DeveloperTaskExecutionRuntimeLease
```

The returned capability is process-local, non-serialized, non-copyable/non-pickleable, thread-safe and single-use. Its fixed TTL is exactly `300` seconds and is enforced only with a monotonic clock. Caller-controlled TTL, clock, token, policy, runtime identity or execution mode is forbidden.

The lease privately retains the exact V1B4B capability and binds:

- full backend/host executable identity and boot identity;
- runtime source, provenance policy, bundle policy, tree/runtime manifests and bundle fingerprint;
- Python executable/DLL/`._pth`/stdlib/probe/runner/launch contract;
- V1B4C policy fingerprint and exact payload fingerprint `47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13`;
- issuer instance and a one-time 32-byte cryptographic secret.

The state machine is atomic:

```text
issued
  ├─ first valid claim ─→ claimed/consumed
  ├─ TTL elapsed ───────→ expired
  ├─ host/runtime drift ─→ invalidated
  └─ concurrent/replay ─→ rejected
```

A valid claim is only an entry capability for one future V1C combined run. It is not guest evidence and does not set `execution_authorized=true`. Before any changed-code instruction, that same Sandbox instance must repeat:

```text
runtime manifest verification
runtime benign preflight
network evidence
worker privilege evidence
Job membership evidence
signed transcript handshake
```

Locked code scope:

```text
A modules/developer/developer_task_execution_runtime_lease_policy.py
A modules/developer/developer_task_execution_runtime_lease.py
A tools/eval_developer_task_execution_runtime_lease.py
A tools/eval_developer_task_execution_runtime_lease_windows.py
M tools/eval_package_boundaries.py
M tools/pipeline.py
```

The targeted Windows smoke may inspect the real host and build/claim the pinned runtime capability, but it must not launch Windows Sandbox or `python.exe`. Full `check` remains portable and non-active.

## 6. Canonical derived bundle layout

Предварительный layout:

```text
runtime/
    python.exe
    pythonw.exe
    python3.dll
    python313.dll
    python313.zip
    python313._pth
    *.pyd
    required runtime DLLs
    LICENSE.txt
    skynetvs_runtime_probe.py
    skynetvs_runtime_runner.py
    runtime_manifest.json
```

`python313._pth` — project-owned locked file. Допустимые active path entries ограничены runtime-local paths; `import site` запрещён.

`runtime_manifest.json` не является источником доверия сам по себе. Host policy и source report определяют expected entries/hashes; manifest лишь сериализует уже проверенное canonical evidence.

## 7. Launch contract

Production launch принимает только typed mode:

```text
runtime_probe
```

V1B4 не принимает:

```text
module name from manifest
pipeline flow from manifest
arbitrary script path
arbitrary argv
environment additions
working-directory override
shell command
```

Controller задаёт:

- exact `lpApplicationName`;
- fixed command line;
- protected local runtime root;
- fixed trusted working directory;
- non-inherited handles;
- environment built with `CreateEnvironmentBlock(..., false)` and explicit removal of all `PYTHON*`, `PIP_*`, `VIRTUAL_ENV` and launcher variables;
- worker-writable temp/result paths outside runtime root;
- read/execute-only worker ACL on runtime files.

## 8. Result authenticity

V1B4 introduces a new policy/schema lineage. Historical V1B3 fingerprints are immutable.

Signed request/ready/authorize/terminal chain must bind:

```text
runtime source SHA-256
runtime source fingerprint
runtime bundle fingerprint
runtime file-manifest SHA-256
python313._pth SHA-256
runtime probe SHA-256
runtime runner SHA-256
launch-contract fingerprint
runtime evidence SHA-256
```

Writable runtime output is never trusted while Sandbox is active. Success is accepted only after all known Sandbox processes exit and exact artifacts are re-read and signature-verified.

## 9. V1B4/V1C boundary

V1B4 proves the exact interpreter and runtime boundary with a benign probe.

V1C is the first stage allowed to add typed changed-code modes. V1C must be split at least into:

```text
V1C1  sandboxed py_compile over verified workspace bytes
V1C2  sandboxed python_module with explicit module allowlist
V1C3  sandboxed pipeline flow with explicit flow allowlist
```

Dependency bundles, if needed, are separate pinned application artifacts. Runtime acquisition does not imply dependency acquisition, and no task may run `pip install`.

## 10. Acceptance criteria

V1B4 is complete only when all are true:

```text
source provenance gate                     green
source archive exact hash                  verified
safe ZIP/file manifest                     verified
deterministic derived bundle               verified
host/non-exec bundle eval                  green
host signed-runtime verifier               green
active benign runtime attestation          green
post-exit signed verification              green
process-local single-use lease gate         green
runtime root write attempt                 blocked
PYTHON*/site/user-site injection           blocked
pip/ensurepip                              absent
all Sandbox processes exited               true
artifacts removed                          true
execution_authorized                       false
full check                                 green
```

## 11. Mode decision

Threat model, runtime version/provenance choice, active runtime state machine and same-run V1C handoff require **Pro Standard**.

V1B4 is COMPLETE through the verified process-local single-use lease. Documentation closure and stable-tag preparation may remain on **Очень высокий**. Switch to **Pro Standard** before V1C architecture or changed-code implementation.
