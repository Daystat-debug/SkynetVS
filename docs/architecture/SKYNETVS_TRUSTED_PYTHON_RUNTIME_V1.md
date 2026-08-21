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
V1C0A  — VERIFIED / EXECUTION BLOCKED
V1C0B1 — VERIFIED / EXECUTION BLOCKED
V1C0B2 — SOURCE CLASSES LOCKED / ARTIFACTS UNPINNED
V1C1A  — VERIFIED / NON-AUTHORIZING
V1C1B  — VERIFIED / NON-AUTHORIZING
V1C2A1 — VERIFIED / NON-AUTHORIZING CONTRACT
V1C2A2 — VERIFIED / NON-AUTHORIZING FIXED RUNNER AND PAYLOAD
V1C2B  — VERIFIED / NON-AUTHORIZING VERIFIER
V1C2C0 — VERIFIED / NON-AUTHORIZING CLAIM TRANSACTION
V1C2C1 — VERIFIED / HISTORICAL HOST-ONLY CONTROLLER-WORKER BUNDLE
V1C2C1R1 — VERIFIED / HOST-ONLY / NON-AUTHORIZING
V1C2C1R2 — VERIFIED / HISTORICAL HOST-ONLY / NON-AUTHORIZING
V1C2C1R3 — CURRENT / HOST-ONLY GUEST-LOCAL RESULT RELAY CORRECTION / UNVERIFIED
V1C2C2 — BLOCKED / EXACT SEVEN-FILE CANDIDATE PRESERVED
V1C2C3 — BLOCKED / LIVE ACCEPTANCE
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
91d8c37 docs: close trusted runtime and prepare sandboxed checks
18e8619 feat: add same-run trusted runtime capability lease
stable tag: skynet-trusted-runtime-v1b4 -> 91d8c37
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
V1B4D    Same-Run Runtime Capability Lease                VERIFIED
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

V1B4 proves the exact minimal interpreter/runtime boundary with a benign probe and a process-local single-use lease. It does not prove the project dependency set, external check tools, workspace snapshot or a changed-code execution plan.

The stable-tag V1C context review measured:

```text
context archive SHA-256:             627dfb80d16c97d0a4ed8ce94fcbbbb4b671b40e4e0c3d8f792123334b07a84f
manifest payloads:                    47/47 verified
tracked Python files / parse errors:  226 / 0
pipeline flows / check steps:          89 / 84
import roots / third-party roots:      65 / 11
process-launch call sites:             32
direct ranged requirements:            11
installed host distributions:          61
host Python / trusted Python:          3.12.10 / 3.13.15
```

The host `.venv` is not an admissible guest bundle. It is mutable CPython 3.12 state, includes resolver/install tooling and ABI-specific native extensions, and is not derived from V1B4 provenance. Runtime acquisition still does not imply dependency acquisition.

The current pipeline `check` is not an initial guest allowlist. It includes host-hardware smoke, Git-dependent developer evals, child processes launched with `sys.executable`, and an inherited host environment/`PYTHONPATH`. A later V1C6 flow must be a new protected guest-safe flow with an exact reviewed step list.

Final V1C split:

```text
V1C0A  Canonical Executable Check Inventory Gate
V1C0B1 Canonical Host Toolchain Observation Gate
V1C0B2 External Source Authority Selection Lock
V1C1A  Canonical Patched Workspace Snapshot Bundle
V1C1B  Typed Compile/AST Plan Capability
V1C2A1 Canonical Compile/AST Request, Result and Terminal Contract
V1C2A2 Fixed Guest Runner and Payload Bundle
V1C2B  Signed Compile/AST Transcript Verifier
V1C2C  Active Compile/AST Sandbox Composition
V1C3A  Python Dependency Source Provenance
V1C3B  Deterministic Python Check Dependency Bundle
V1C3C  Portable Git Source Provenance and Bundle
V1C4A  Changed-Code Execution Contract and Guest Payload
V1C4B  Signed Changed-Code Transcript Verifier
V1C5   Active Sandboxed python_module Check
V1C6   Active Sandboxed Guest-Safe Pipeline Check
V1C7   Composite Typed Check Runner and Result Evidence
```

V1C0A and V1C0B1 are VERIFIED through `e090f63`. Their post-commit Windows smokes were `1/1` against the exact committed tree:

```text
tracked files / Python files: 252 / 234
pipeline flows / check steps:  91 / 86
process-launch call sites:      38
inventory fingerprint:          574cdc81c154c04ade6e26aec520cac243ddf5e15f1780037c57bf3ae88d1956
observation fingerprint:        aa2f63f41523480f4e423d57e15e02883b70709e34e1dd108c72e977b36e6035
source_authority_selected:       false
execution_authorized:            false
```

Locked rules after V1C0B2:

```text
decision ID:          skynetvs-v1c0b2-external-source-authority-lock-v1
decision fingerprint: 80da155e8de0ce9f6d17565541173b701c2d5c9c8a8c13f1fcab9a57dbdb3d5e
```

- V1C0A is host-only inventory and grants no capability.
- V1C0B1 observes host Python/pip, Git and fixed Windows PowerShell but grants no authority. Host installations are never copied into a guest bundle.
- Python metadata authority is the PyPI Simple Repository API JSON v1 with a supported `1.x` response at API `1.4` or newer; Python byte authority is the exact `files.pythonhosted.org` wheel URL named by that response.
- Every direct and transitive wheel must be bound to normalized name, exact version, filename/tag, size, SHA-256, `Requires-Python`, yanked state and exact CPython 3.13 AMD64 compatibility. No extra index, direct URL, pre-release, yanked file, runtime resolver, `pip install`, sdist, local build or host-cache fallback is permitted by default.
- A version-pinned resolver can propose candidates but is not authority. Final closure is independently rebuilt from verified metadata and bytes.
- PyPI core-metadata hashes and provenance are verified when present. Attestation is supplemental publishing-identity evidence, not a package-safety guarantee; absence is recorded.
- Portable Git authority is an immutable official Git for Windows release tag plus the standard 64-bit MinGit ZIP, release-published SHA-256, exact archive bytes and deterministic extracted-tree manifest. `latest`, BusyBox MinGit, PortableGit, installers, host Git and a single launcher hash are not authority.
- The measured review candidate `v2.55.0.windows.4` / `MinGit-2.55.0.4-64-bit.zip` / SHA-256 `4e03f94c2ffbf70be337e005cee02661c732dbfc81031a078bda9299b9a7d644` is not yet the production V1C3C pin.
- Network is restricted to future dedicated host acquisition gates with exact origin/redirect allowlists and scrubbed credential/index/proxy environment; guest/runtime network remains forbidden.
- The first active changed-workspace boundary is V1C2 compile/AST only, without imports, top-level execution, Git or project dependencies.
- No portable PowerShell bundle is selected for the initial V1C2 compile/AST gate; the fixed guest Windows PowerShell controller remains the only PowerShell boundary.
- `python_module` and pipeline flow names require semantic explicit allowlists bound to exact protected baseline-owned entrypoints; regex validation is not authorization.
- Each executable check consumes one fresh V1B4D lease, one immutable snapshot and one fresh Sandbox.
- A successful report remains historical evidence only: `execution_authorized=false`, `reusable_lease_issued=false`.

Locked V1C1 decision:

```text
context archive SHA-256: fdc0ea63f8765b97c63c68d55c85bbb0cce6994bd0f0cc83036cb6febbf37d0d
context payloads:          49/49
tree files / bytes:        252 / 3,528,329
Python files / bytes:      234 / 3,257,957
tree manifest SHA-256:     b1e82bf0a3fb8a901c0ac37825d74c8de426f34d02f67d0b05a710be2b4962ba
decision fingerprint:      20f26ef8728a77ea87b22d791ebf4da5940312c48e589cf6c17a89765428ad30
snapshot policy:           601c727e9b725f1f868a144fa7b975bbb7a35a878c74c2d25bda0a7677a6cd55
plan policy:               f017f401254647002347802c5deba6397bdddf27eaa08d02640dc8389fe80865
```

- V1C1A reads exact blobs from the verified patch-result tree, independently SHA-256-binds them and never trusts mutable worktree bytes.
- Snapshot V1 permits only regular `100644` blobs and enforces `4096` files, `8 MiB` per blob, `16 MiB` total, `4 MiB` manifest and `240/120/32` path limits with NFC/Windows collision rejection.
- Snapshot exact bytes are private, process-local, non-serializable, single-use, `300` seconds, `32`-byte secret; V1C1 accepts no runtime lease.
- V1C1B consumes one snapshot and derives only `compile_ast_changed_python_v1`: present changed `.py`, `1..20`, `2 MiB` each, `8 MiB` total, mode `100644`, UTF-8, LF/empty, no NUL.
- Deleted Python and non-Python changes remain evidence only. Caller-controlled executable, argv, paths, environment, encoding, limits, module, flow and runner are forbidden.
- V1C2C claims the plan capability first and a fresh V1B4D lease second. The original workspace and `.git` are never mapped.

V1C1A implementation is VERIFIED at `7b174610e6dde4e1e28a6ae5fb1f357ac0ad93e2`. The post-commit committed-tree inventory is `256` files / `238` Python files, `92` pipeline flows / `459` total steps / `87` check steps, with inventory fingerprint `1d6df3788467909e758c172bee1289ac0fda65915c1646304b257e69ae17f96b`. The V1C1A Windows smoke is `1/1` and proves issued→`claimed_for_plan` exact-byte snapshot semantics while repository mutation, network/download/install, Sandbox, runtime-lease issue/claim, candidate interpreter, changed-code execution, reusable lease and authorization remain false.

V1C1B implementation is VERIFIED at `70fc763ddab74da501d4988a9a0fd8269e877ddb`. Its post-commit inventory is `260` files / `242` Python files, `93` flows / `474` total steps / `88` check steps, with inventory fingerprint `4c4316c3fdfa59ab5fc2e72e76364ae457a12c3545022300b30a486b4357d716`. The post-commit V1C1B Windows smoke is `1/1`, retains only exact selected bytes and keeps Sandbox, runtime-lease, interpreter, changed-code and authorization flags false.

Roadmap Change 015 locks the V1C2 lineage:

```text
decision ID:          skynetvs-v1c2-compile-ast-active-boundary-architecture-lock-v1
decision fingerprint: 5382249191bcc8388d6b44862cabe7c24a586a6628814266461c0830e7dec08c
V1C2A1 policy ID:     skynetvs-v1c2a1-compile-ast-contract-cpython-3.13.15-v1
V1C2A1 fingerprint:   a3e7d50e92de8aa0799953874a71ce60b2d141e52791282e5fd38814aa9507bf
```

- V1C2A1 owns strict canonical request/source-manifest/result/terminal schemas and distinguishes transcript authenticity from check pass/fail.
- V1C2A2 owns the exact fixed guest runner and payload bytes.
- V1C2B owns pinning, canonical parsing and post-exit ECDSA-P256 transcript verification without Sandbox launch.
- V1C2C alone may claim the plan first and runtime lease second, materialize flat fixed source files, launch one fresh Sandbox and run the pinned interpreter.
- Original repository paths remain metadata and virtual diagnostic filenames; they are never guest filesystem paths.
- The runner executes `ast.parse` and `compile` only. Source import statements may compile, but no import/top-level/code object is executed and no bytecode is written.
- A signed syntax failure is valid evidence with `check_passed=false`; it does not become a boundary-authenticity failure.
- Every outcome keeps `changed_code_executed=false`, `execution_authorized=false` and `reusable_lease_issued=false`.

V1C2A1 implementation is VERIFIED at `ec68dd4170bab82131dcf88f3aaa7b98ebaa75b8`. Pre-commit evidence passed package boundaries `28/28`, V1C1B `35/35`, V1C2A1 `45/45`, Windows contract smoke `1/1`, Runtime Architecture Audit `9/9` and the full `check` flow. Post-commit inventory is `264` files / `246` Python files, `94` flows / `479` total steps / `89` check steps, with inventory fingerprint `9f3bd41cdc379f126751e651dbcdd71cbc3380d7ac5bf57687b46dd48b5cd268`; post-commit V1C0A and V1C2A1 Windows smokes are both `1/1`. Canonical passed, authentic syntax-failed and boundary-failed result classes remain distinct, raw source is absent, and all Sandbox/runtime-lease/interpreter/changed-code/reusable-authority flags remain false.


V1C2A2 implementation is VERIFIED at `b83d2966960a23ebf6930b8ba7ea4bd100cef0b3`. Pre-commit evidence passed package boundaries `28/28`, V1C2A1 `45/45`, V1C2A2 `40/40`, Windows bundle smoke `1/1`, Runtime Architecture Audit `9/9` and the full `check` flow. Post-commit inventory is `268` files / `250` Python files, `95` flows / `484` total steps / `90` check steps, with Python tree fingerprint `358ecc4acdcd25163ac56e280c9c63e2d62c46f4f8ec89665bae12826e9cfb0a` and inventory fingerprint `a39d47b9e9041dbe276cc73648fd37b57f614e9f94fbd731368f8e80b15cd5b3`; post-commit V1C0A and V1C2A2 Windows smokes are both `1/1`. The verified fixed-runner identities are policy `825af298ba972e6c12ac0f85572935c7a8bd34ed4ee215cfa2af6e39a7e659c4`, bundle `b1f182ca4ee1a9e83cb6a32ca54e45d4511c81faa27d8dd4be7817883affb9f3`, runner SHA-256 `6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9` and payload SHA-256 `730d4108aab8246d1e6ff030a4d5a64ad25a89adf888e2b10c64ec63d56f60b6`. Sandbox/runtime-lease/interpreter/changed-source/changed-code/reusable-authority flags remain false; V1C2A2 grants no execution authority.

V1C2B implementation is VERIFIED at `98f4cfe0ee1a71c327b35670d786ab11b9485c6b`. Pre-commit evidence passed package boundaries `28/28`, V1C2A1 `45/45`, V1C2A2 `40/40`, V1C2B `44/44`, Windows CNG smoke `1/1`, Runtime Architecture Audit `9/9` and the full `check` flow. Post-commit inventory is `272` files / `254` Python files, `96` flows / `490` total steps / `91` check steps, with Python tree fingerprint `f73125f2281ef44f15fc13a8520d64a2522bb020610b13480bcf72b0df5ea0a4` and inventory fingerprint `06f3794183eec0beede477f72eacc51ef5b991d81e69cbc3b3660daba3f7765f`; post-commit V1C0A and V1C2B Windows smokes are both `1/1`. The verified policy is `cd2fa5fc2c74a5fb683a6d65348468c926f6bbb4311b0d32e3f397555e8edfaf`; Windows CNG verified a 64-byte P1363 ECDSA-P256 signature and public-key SHA-256 `0bc654178e6f3d5e4ab8b170722a7b7a388a76d58c97031fcad019cf4bdb5e91`. The verifier distinguishes authentic syntax failure from boundary failure, rejects replay/substitution/forgery and has no filesystem/process/Sandbox/network/source-processing surface. Sandbox/runtime-lease/interpreter/changed-source/changed-code/reusable-authority flags remain false; V1C2B grants no execution authority.

V1C2C0 implementation is VERIFIED at `e6e355ab3238565bb9d685f503647da6a487c919`. Pre-commit evidence passed package boundaries `28/28`, V1C1B `35/35`, V1B4D `36/36`, V1C2C0 `38/38`, Windows transaction smoke `1/1`, Runtime Architecture Audit `9/9` and the full `check` flow. Post-commit inventory is `276` files / `258` Python files, `97` flows / `496` total steps / `92` check steps, with Python tree fingerprint `f7af9a590320fb6a17178b8baa2785a0981ea83a22f9c8f393261ec38b599088` and inventory fingerprint `d10f6fb0c9a72419c0d63c1445253c692a90010a97ee834dfefe5015abf2289a`; post-commit V1C0A and V1C2C0 Windows smokes are both `1/1`. The verified transaction policy is `092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa`. It binds exact process-local plan/lease objects, exposes only a fresh non-secret one-run fingerprint, claims plan before runtime lease, rejects replay/duplicate reservations/tamper, and has no filesystem/process/Sandbox/network/source-processing surface. Sandbox/interpreter/changed-source/changed-code/reusable-authority flags remain false; V1C2C0 grants no execution authority.

Before the first source parse/compile instruction, the same Sandbox instance must re-prove runtime, snapshot, execution-plan, network, worker privilege, Job, handle/environment and signed-handshake evidence. No candidate code object may be executed.

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

Threat model, runtime provenance, V1C toolchain separation and Roadmap Changes 011–022 require **Pro Standard**.

V1C0A/V1C0B1/V1C1A/V1C1B/V1C2A1/V1C2A2/V1C2B/V1C2C0/V1C2C1/V1C2C1R1/V1C2C1R2 are VERIFIED; V1C0B2, V1C1, V1C2 and the V1C2C split are LOCKED. RC021/RC022 diagnostics are COMPLETED / CONSUMED. V1C2C1R3 is CURRENT in Pro Standard. V1C2C2/V1C2C3 remain BLOCKED; exact PyPI wheel closure and MinGit pinning also require Pro Standard.

## V1C2C active composition split — Roadmap Change 016

The exact `b527f93` source audit locks V1C2C as four boundaries rather than one large active commit:

```text
V1C2C0 claim transaction: 092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa
V1C2C1 architecture slice identity: db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec
V1C2C2 architecture slice identity: d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484
V1C2C3 live evidence:     b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8
Decision:                 56bfd2ca196ca2b6d8f6ad426ea06141fe1535a28a281f0d7661bc8e32ee8ff6
```

The transaction wrapper is required because V1C2A1 needs a one-run `runtime_lease_fingerprint`, while the current V1B4D public status intentionally exposes no per-instance identity. V1C2C0 exclusively reserves and privately binds the exact lease object and exact plan object, generates a fresh public binding fingerprint, and later performs the irreversible `plan -> runtime lease` claim sequence without a fallible operation between claims. This does not modify the stable V1B4D claim API or turn a lease into serializable authority.

V1C2C1 must use a new compile-specific helper: the V1B4C helper proves kill-on-close for a benign runtime probe, but the compile contract additionally requires active-process limit `1`, process memory `512 MiB` and Job memory `768 MiB`. V1C2C2 remains the only active slice. V1C2C3 closes pass, syntax-failure and signed boundary-failure evidence with fresh capabilities and fresh Sandbox instances.

All outcomes remain non-reusable and non-authorizing. `changed_code_executed`, `execution_authorized` and `reusable_lease_issued` stay `false`.

## V1C2C1R3 guest-local worker result relay — Roadmap Change 023

Roadmap Change 022 is COMPLETED / CONSUMED at documentation `HEAD bdd23feacfba4032f8bf9be76dae94a5d670bf68`. Its permanent marker SHA-256 is `4320b13cd9021967c80370a4dc13936455d291622f97a15897234e8a970bb85c`, evidence SHA-256 is `4ee751d7dfbe7467e26b921fae981bd0e65c1275ca10dacac6342fb9ac9219bb`, summary SHA-256 is `0334e3c5730f1563ab01648635ff1f6408ade4e24f0e383bc93c2905861ec967`, and the preserved seven-file candidate remains SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`.

The probe proved that LocalSystem, exact R2 helper binding, fresh medium-integrity non-admin worker token, runtime access and fixed-runner access all pass. The first failed checkpoint is `prepare_shared_worker_output_directory`, with inner `System.InvalidOperationException / 0x80131509`: `Exact shared-output worker ACE was not observed after ACL write.` The actual `C:\SkynetVSOutput` mapped root retained the same owner, protected state, three-rule multiset and multiset SHA-256 `4a67566837a9aca1cfe5ff32f47056d1640b4bf640ab3633bdb01ea986580162` before and after the failed write. Process creation and Job assignment were not reached.

The worker SID became quiescent, the fresh account was deleted, Sandbox self-shutdown completed and host cleanup removed the temporary root. The primary thread was never resumed; no transaction or runtime lease was consumed/claimed; no changed source was materialized/processed; candidate Python and changed code did not run; no reusable authority was issued; `execution_authorized=false`.

R2 remains valid only as historical host-only evidence. R3 replaces the active mapped-output design with two distinct roots:

```text
C:\SkynetVSOutput      private guest-local NTFS root used by the unchanged V1C2A2 runner
C:\SkynetVSHostOutput  writable WSB mapping used only by the trusted LocalSystem publication path
```

The worker receives a private SYSTEM + exact worker SID ACL only on the non-mapped local root. It must not be able to write the host mapping. After worker exit, Job closure, SID quiescence and account deletion, LocalSystem validates `C:\SkynetVSOutput\result.json`, relays the exact bytes to `C:\SkynetVSHostOutput\result.json`, and signs terminal evidence against the relayed bytes. Ready/failure/terminal publication also uses `C:\SkynetVSHostOutput`. No WSB mapped-folder ACL, owner or protection state may be mutated.

R3 changes only the four controller-worker bundle/evaluator files. The fixed runner and V1C2A1/A2/B/C0 identities remain immutable. R3 is host-only and non-authorizing; no Sandbox run is allowed during its implementation/verification. V1C2C2 remains BLOCKED and byte-preserved until R3 is independently VERIFIED and a later Roadmap Change authorizes rebinding and a fresh active attempt.

Operational state:

```text
RC021:                              COMPLETED / CONSUMED
RC022:                              COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C1R2:                           VERIFIED / HISTORICAL HOST-ONLY
V1C2C1R3:                           CURRENT / HOST-ONLY / UNVERIFIED
V1C2C2:                             BLOCKED / CANDIDATE PRESERVED
V1C2C3:                             BLOCKED
candidate interpreter executed:     false
changed source processed:           false
changed code executed:              false
reusable lease issued:              false
execution authorized:               false
```

## V1C2C1R1 transcript policy-hash integration correction — Roadmap Change 019

Exact-source integration review found that V1C2A2 and V1C2B require `request.policy_sha256` to identify the exact V1C2A1 contract-policy file, while the first V1C2C1 controller bundle required the same field to identify its different controller-worker policy. The two SHA-256 values are distinct, so no authentic active transcript could satisfy both boundaries.

V1C2C1R1 corrects only the newer controller-worker bundle: request/ready/terminal `policy_sha256` binds the exact contract-policy bytes, and the controller-worker policy remains separately verified through an embedded exact SHA-256 plus the corrected bundle identity. V1C2A1, V1C2A2, V1C2B and V1C2C0 remain byte-for-byte unchanged. No Sandbox launch or interpreter execution belongs to this correction.

```text
policy ID:          skynetvs-v1c2c1r1-fixed-system-controller-standard-user-worker-bundle-v2
semantic policy fp: a1c9e95421ffe9755acc13028b05c3b45b960ad5d2ee750685bf56db1d44d03a
policy bytes SHA:   3d5405a603030d79a18ef31a3f5a5cd4f03b40c7115842a0d75974ecb26db3b3
controller SHA:     776e4c07c533a44d54a57b5ecd0d38bf92cf6b7fc4aece1d4a211d85594049f4
bundle fingerprint: 12714af317444e481967af2ca063ec1fe0f3a4e83a8f750332aa667ba6155303
```


## V1C2C1R2 shared-output ACL preservation — Roadmap Change 020

The first V1C2C2 active diagnostic received trusted ready evidence and published pinned authorization, but the host observed no result, terminal signature or controller-failure artifact before clean Sandbox exit. The exact controller then applies `PrepareWorkerResultDirectory` to `C:\SkynetVSOutput`. The inherited helper protects/replaces the DACL and sets a new owner, behavior designed for private guest-local result directories rather than a host-observed writable mapping.

V1C2C1R2 changes only the compile-specific controller-worker bundle. Its shared-output ACL method must:

- preserve the existing mapped-directory owner;
- preserve the existing access-rule protection/inheritance state;
- preserve all pre-existing access rules needed by the host mapping;
- add an inheritable fresh-worker write ACE with no broader rights;
- re-read and verify the exact worker ACE;
- reject any attempt to use `SetAccessRuleProtection(true, false)` or owner replacement on the shared output root.

Historical V1B3/V1B4 private-directory ACL helpers and V1C2A1/A2/B/C0/C1/C1R1 identities remain unchanged. V1C2C1R2 is VERIFIED / HOST-ONLY / NON-AUTHORIZING at `d200c49bc5868a50ae6c83c45d4e7ed8724f332a`.

```text
policy ID:          skynetvs-v1c2c1r2-fixed-system-controller-standard-user-worker-bundle-v3
semantic policy fp: 65d0dbdd1cf03095f35f3bd322b3ef8a1f0e9139c163266fefd1664218e21a0a
policy bytes SHA:   ece583455d0813154e9bd8e14a84822614b20d3f38a8276358d77d7e75e7d014
native helper SHA:  550c1d009ffcbb0ea25ad609d215237f2e5a66a20f48edc7278c314e84d7677a
controller SHA:     335fbed28b001bcd4f11975b520d9d1e5feaec698a7a5836d946c132bebe5e23
bundle fingerprint: 449240db944a60ed51a1914f36d6c981a9579cd72e9c0e3802b6b9f3382c458c
```

Acceptance and post-commit evidence proved package boundaries `28/28`, portable coverage `41/41`, Windows ACL behavior `3/3`, targeted flow success, isolated full `check`, Runtime Architecture Audit `9/9`, exact four-file commit scope and committed-tree inventory. The helper preserved owner, protection/inheritance and every pre-existing ACL rule, added exactly one worker ACE and left Sandbox launch, transaction consumption, runtime-lease claim, interpreter execution, changed-source processing, changed-code execution, reusable lease and execution authorization false.

The preserved V1C2C2 seven-file implementation was rebound to the exact R2 identities without scope growth and stripped of temporary failure-only diagnostics. It remains uncommitted with exact candidate SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`, semantic policy fingerprint `1cc5a4aedb348f9cb669f2317c3a0a7b24bd11b7bbbd6eadd02907b2b1a8b1e5` and policy-document SHA-256 `71aa6a3228836740411d4c042d12b825cda8337b958771bc8e9ec4579299a5e1`. The one fresh active retry failed closed; the RC021 capture and RC022 localization probe are both COMPLETED / CONSUMED, and no further active run is permitted while R3 is open.

```text
V1C2C1R2 VERIFIED
V1C2C2   HISTORICAL STATE AT R2 CLOSURE / RC021 DIAGNOSTIC CAPTURE ONLY
V1C2C3   BLOCKED
changed_code_executed=false
reusable_lease_issued=false
execution_authorized=false
```



## V1C2C2 R2 guest-failure evidence capture — Roadmap Change 021

Roadmap Change 021 is generated from the exact committed documentation export at `HEAD 9a3f227685c6fd7e1097c371ce54137eb0a1c663`, tree `4e6ff04c3f1ce2ca30b8e77e6d74be0c708ef073`, archive SHA-256 `42bfb8e589da5fdd7947594b2e7ab296bc4505cd86dd0592d14ef9e513a9102d`; the three source blob IDs are `a0f8e3a4d1b8ecacf7bfb5ca907bdc152c924e2c`, `318c41956c4770c9e4f1ca3549a70e472fcad5ae` and `b23462bd5852799fd6713a5fae8350cc88c094a5`.

The R2-rebound seven-file candidate is fixed at SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`, with V1C2C2 policy fingerprint `1cc5a4aedb348f9cb669f2317c3a0a7b24bd11b7bbbd6eadd02907b2b1a8b1e5` and policy-document SHA-256 `71aa6a3228836740411d4c042d12b825cda8337b958771bc8e9ec4579299a5e1`. Package boundaries passed `28/28` and portable coverage passed `45/45`.

The Roadmap Change 020 active retry consumed one fresh transaction and lease, launched one Sandbox and failed closed with a guest failure artifact. The candidate interpreter did not execute, changed source was not processed, all Sandbox processes exited, no forced cleanup was required, private artifacts were removed and the host repository/workspace remained unchanged. The retained issue codes are:

```text
compile_ast_composition_guest_failure_reported
compile_ast_composition_guest_failure_artifact
```

The report's bounded failure diagnostic carries `file`, `sha256`, `stage`, `error_type` and `error_code` in `issues[].actual`, but that field was not printed by the acceptance evaluator and the artifact tree was correctly removed after exit. Those values are therefore UNVERIFIED.

Roadmap Change 021 historically authorized one fresh diagnostic capture only. That capture is COMPLETED / CONSUMED; its immutable evidence was persisted without changing production or candidate bytes, and no RC021 authority is reusable.

```text
V1C2C2 historical RC021 status:   DIAGNOSTIC CAPTURE ONLY (NOW COMPLETED / CONSUMED)
additional acceptance retry:     not authorized
full check after diagnostic:     not authorized
candidate code commit:           not authorized
V1C2C3:                          BLOCKED
changed_code_executed:           false
reusable_lease_issued:           false
execution_authorized:            false
```

After the one report is captured, stop. A production correction or any further active run requires another explicit Roadmap Change based on the exact guest failure stage and error evidence.


## V1C2C2 suspended-worker stage localization — Roadmap Change 022

The Roadmap Change 021 one-shot capture is COMPLETED / CONSUMED at documentation `HEAD b3cfad02c99aa283d9516a0d35c93d3edff21324`. The consumed marker has `status=completed`; evidence SHA-256 is `96d2d4c797dd375d269e538558b5a5f9156a47bf80cc2f165b0d29b237b850dd`; the exact uncommitted seven-file candidate remains SHA-256 `9e4c4fa1d81af471b6f778ec9fabf3b71334742d09b646e07976dac42158e2a1`.

The guest failure is now verified only to the following bounded form:

```text
file:        controller_failure.json
sha256:      74a0eba664c757660c21a4311eb4d62ae541913f4e6140109503deb7d141cdee
stage:       compile_ast_worker
error_type:  MethodInvocationException
error_code:  compile_ast_controller_worker_stage_failed
```

The capture proved `candidate_interpreter_executed=false`, no changed source processing/parsing/compilation, `changed_code_executed=false`, no reusable lease, no execution authorization, complete Sandbox exit, artifact removal and unchanged source/workspace. The outer exception does not identify the inner native or ACL checkpoint.

Roadmap Change 022 historically authorized one external, single-use suspended-worker localization probe. That probe is COMPLETED / CONSUMED: it never called `ResumeCompileAstWorker`, never consumed a V1C2C0 transaction or runtime lease, never materialized changed source and never accepted result/terminal evidence.

Required durable checkpoints:

```text
fresh account/token
runtime executable token access
runner token access
shared-output ACL before/after binding
CreateProcessAsUserW
CREATE_SUSPENDED state
AssignProcessToJobObject
IsProcessInJob and exact Job limits
no resume call
Job close and process exit
worker SID quiescence
account deletion
Sandbox and host artifact cleanup
```

At the first failure the completed probe persisted the full exception and inner-exception chain, `HResult` and the immediately preceding successful checkpoint. It was diagnostic only and did not verify or authorize V1C2C2. RC022 is consumed; Roadmap Change 023 owns the production correction decision.

```text
RC021:                              COMPLETED / CONSUMED
RC022:                              COMPLETED / CONSUMED / LOCALIZED_FAILURE
V1C2C1R3:                           CURRENT / HOST-ONLY GUEST-LOCAL RELAY CORRECTION
V1C2C2:                             BLOCKED / EXACT SEVEN-FILE CANDIDATE PRESERVED
active acceptance retry:            not authorized
primary-thread resume:              forbidden
V1C2C0 transaction consumption:     forbidden
runtime-lease claim:                forbidden
candidate code commit:              forbidden
V1C2C3:                              BLOCKED
changed_code_executed:               false
reusable_lease_issued:               false
execution_authorized:                false
```

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

No Sandbox was launched, no transaction was consumed, no runtime lease was claimed, no interpreter ran and no changed source was processed. `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false` remained invariant. V1C2C1R1 is therefore VERIFIED / HOST-ONLY / NON-AUTHORIZING. Roadmap Change 020 subsequently inserted and verified V1C2C1R2. Roadmap Changes 021/022 are COMPLETED / CONSUMED and prove mapped-output ACL non-persistence before process creation. V1C2C1R3 is CURRENT; V1C2C2/V1C2C3 remain BLOCKED.

## V1C2C1 implementation identity — Roadmap Change 017

The exact V1C2C source-context archive with SHA-256 `f5883188e4aa2119c849f2adbc449b73072ede208f742f6ededb42ae783aa08d` preserves `db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec` only as the locked V1C2C1 architecture-slice identity. Because the archive contains no canonical policy preimage for that value, the implementation does not misrepresent it as a recomputed SHA-256 of new bytes.

The deterministic implementation introduces separate exact identities:

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

The implementation scope is exactly two production modules, two evaluator modules and the existing package-boundary/pipeline registries. It remains host-only: no transaction claim, source/runtime materialization, Sandbox launch, interpreter execution or changed-source processing occurs. The stable V1B4 tag and all historical V1B4/V1C2A1/V1C2A2/V1C2B/V1C2C0 identities remain immutable.

## V1C2C2 implementation identity — Roadmap Change 018

The exact current source context at `e2621ca5094eb7140323dcecb97b27ab9605ae65` has SHA-256 `7cda253ce704cc028900e7b3d7da59340dd3da6f2b5cb60305cdc00fa4ccb50b` and contains `d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484` only as the locked V1C2C2 architecture-slice identity. The historical V1C2C architecture context with SHA-256 `f5883188e4aa2119c849f2adbc449b73072ede208f742f6ededb42ae783aa08d` also contains no canonical V1C2C2 policy JSON, schema or hash preimage for that value. The active-composition implementation must therefore never claim that newly created policy bytes reproduce the historical identity.

The concrete implementation uses the separate canonical policy ID:

```text
skynetvs-v1c2c2-active-compile-ast-sandbox-composition-v1
```

Its semantic policy fingerprint and exact policy-document SHA-256 are reproducible identities derived from the final implementation policy bytes. They bind, but do not replace or reinterpret, the immutable Roadmap Change 016 architecture-slice identity.

The only public active API is:

```python
attest_developer_task_execution_compile_ast_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionCompileAstCompositionReport
```

The API accepts no caller command, runtime/source/workspace path, environment addition, timeout, Job limit, WSB setting, signature verifier or fault hook. It consumes one fresh process-local transaction, materializes only exact retained capabilities, launches one fresh Sandbox and accepts signed evidence only after full process exit and exact post-exit revalidation. All outcomes keep `changed_code_executed=false`, `reusable_lease_issued=false` and `execution_authorized=false`.

The locked implementation scope is three production modules, two evaluator modules and the existing package-boundary/pipeline registries. V1C2C3 remains a separate future three-run acceptance boundary and may not widen the V1C2C2 public production API.

## V1C2C1 verification closure

The fixed controller-worker payload bundle is VERIFIED at:

```text
commit:                   aa97b779441196b1586d317344f3a82d05411874
message:                  feat: add fixed compile ast controller worker bundle
parent docs commit:       1ca04d6568e687d8addd956eb4f9b6b0926ccdbe
portable evaluator:       33/33
Windows compile smoke:     3/3
full check:               completed successfully
Runtime Architecture Audit: 9/9
post-commit V1C0A:         1/1
post-commit V1C2C1:        3/3
post-commit targeted flow: completed successfully
```

Post-commit inventory at exact `HEAD == origin/main` is `280` tracked files / `262` Python files / `4,027,150` Python bytes, with `98` pipeline flows / `504` total steps / `93` check steps. Python tree fingerprint is `5b58b6120524609c8f0d378d69bfa9316d65709f4ea2fe669f8c5334e1e59be3`; inventory fingerprint is `3c7cae90bdcd2584676c6cb82203af43658236602f683b83b0c377b6d9a36cad`.

The exact bundle identities remain:

```text
architecture slice: db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec
semantic policy fp: 0a559e9a9bcac241a18b0e3cbe31263f4f01a5a94eaf70ee7d65382297a62baf
policy bytes SHA:   1d9b1c66bf3971a3fdedfb077ef8deb08467e29acbc4f725d7050e3ae1342091
bootstrap SHA:      7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d
native helper SHA:  901373a63df349e245a0c90887779b2cdb7f204dee98535c95bdc235844bb7a1
controller SHA:     f30d115d5a9dc2da2dd9e2d9dbeca3929b9497d35e700dec175d9399aac49996
WSB template SHA:   81861905167211b29fbff7179878b6b671c31b731af482166913b5e20416375f
bundle fingerprint: bd30bec84c8cbdd37940c0e1bb4b34f3cd6c0aed72d05c326afef118f53cd50c
```

The closure proves only deterministic host-side payload construction and compile/parse evidence. No claim transaction was consumed, no runtime lease was claimed, no source/runtime was materialized, Sandbox and candidate Python were not launched, no changed source was processed and `execution_authorized=false`. V1C2C1 remains VERIFIED / HOST-ONLY / NON-AUTHORIZING historical evidence. V1C2C1R1 and V1C2C1R2 are independently VERIFIED. Roadmap Changes 021/022 are COMPLETED / CONSUMED and prove mapped-output ACL non-persistence before process creation. V1C2C1R3 is CURRENT; V1C2C2/V1C2C3 remain BLOCKED.
