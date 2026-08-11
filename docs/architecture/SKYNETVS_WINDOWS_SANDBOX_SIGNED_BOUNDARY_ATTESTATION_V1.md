# SkynetVS Windows Sandbox Signed Boundary Attestation V1

## 1. Назначение

Документ фиксирует успешный active experiment:

```text
V1B3A — SYSTEM Controller Bootstrap Capability Experiment
```

Эксперимент использовал только trusted bootstrap, trusted SYSTEM controller и benign compiled worker probe. Developer-task patch, `python_module`, `pipeline`, arbitrary shell, dependency installation и host fallback не запускались.

Итоговый report во всех слоях сохраняет:

```text
execution_authorized = false
```

## 2. Source evidence

```text
Experiment date:          2026-08-06
Git HEAD:                 e18e3096ae3c7d3bc1683ecfd28568658ae5bc01
Evidence ZIP SHA-256:     a65c9f5a3e6b21a862e05417e17e205b2efb141f1a41f0ffef75d65616387cef
Host report SHA-256:      b9ab0600680d001d368731a3942e2867d3527e67ce21c1464543f56460083052
Report schema:            1
Status:                   signed_boundary_attested
Failure:                  empty
Backend:                  traditional_wsb_logoncommand_v1
Boundary ID:              v1b3a_system_controller_signed_boundary_experiment_v1
Base policy fingerprint:  5c731d5f246929aa1b59f614d2a01371b086244cc09f2c5846d93531b194af21
Boundary fingerprint:     9eb7a1373d1814eea37c8213dfeaeb4f4e7d40e7fdb5d8ec40f91f3e2fd8db72
Request ID:               e258f88734fd4d7f96c0075d2d19dd06
Execution authorized:     false
```

## 3. VERIFIED — Host lifecycle and terminal verification

```text
WindowsSandbox.exe PID:       30632
Known process observed:       true
All Sandbox processes exited: true
Ready received:               13 028 ms
Terminal received:            22 379 ms
All processes exited:         32 515 ms
Total duration:               32 558 ms
Signature before exit:        valid
Signature after exit:         valid
```

Measured host process model:

```text
WindowsSandbox.exe
    transient launcher
        ↓
WindowsSandboxRemoteSession.exe
    persistent host session
        ↓
empty known Sandbox process set
    required proof of complete exit
```

The host re-read `ready.json`, `terminal_payload.json` and `terminal_signature.bin` after complete Sandbox exit. Their bytes remained stable and the signature still verified.

## 4. VERIFIED — SYSTEM bootstrap

Trusted `.wsb LogonCommand` bootstrap ran as `WDAGUtilityAccount`, confirmed administrator membership, created a one-time Scheduled Task and started the controller as:

```text
SID:             S-1-5-18
Account:         NT AUTHORITY\СИСТЕМА
Administrator:   true
Integrity RID:   16384 / 0x4000
```

The one-time bootstrap task was deleted before `ready.json` was accepted.

## 5. VERIFIED — Ephemeral ECDSA P-256 key

```text
Algorithm:                  ECDSA P-256 / SHA-256
CNG public format:          EccPublicBlob
Key is ephemeral:           true
KeyName empty:              true
UniqueName empty:           true
Private-key export:         forbidden by policy
Public-key SHA-256:         974bb1b335bf20062db29f7d42826a9d3987786dc1c955c1dab459876fa51fc0
Terminal signature bytes:   64
Terminal signature SHA-256: 1f7f3878d9f02ccef03ad91c94c099ceff0d610f51a4107c5f4764b1f3d7ee11
```

The private key existed only in the SYSTEM controller process. Shared folders contained only the public `EccPublicBlob`.

## 6. VERIFIED — Ready/authorize/terminal transcript

Exact-byte hash chain:

```text
request.json SHA-256:          84dd68753d79c7cb3cd675ceee8af76d8567d276ca2c6d603a34a030e2e0266b
ready.json SHA-256:            72b0f8104d0c93347595eaf9a0540320e39f010aec513c54561cdbc224359c62
authorize.json SHA-256:        a23cf1d94aa43f98d49425cb5fde07f85a44e76a80d9b02ba48b762a77bd53a5
worker_result.json SHA-256:     256f9aabfb31911b9f84c53b6dfda4c47aa3e8636a18e9daa2a7a6d9c180c6ac
terminal_payload.json SHA-256:  7e80cb8fc02e2421a81af8f03270cd50be55bca29a2498795d082661e30a108b
```

Trusted input hashes:

```text
boundary_policy.json: 9eb7a1373d1814eea37c8213dfeaeb4f4e7d40e7fdb5d8ec40f91f3e2fd8db72
bootstrap.ps1:        b8a92d7e8c60cae09c8ca6d3649588eddb3801acd17c5e67191c291b45d8171c
controller.ps1:       a5887fa121b35a17e5c5a6f7e050ee92294946ee11c18e3e05266ce547cc5047
worker_probe.cs:      45ca2d394228f23fbb37e151938b9aa69f9c5fbcafe79844d0f8a829dc7deb46
SkynetVS_V1B3A.wsb:   ab7c3ab7654ede32229e6dff20a301b35ad67ba96edf08399273af5ebbd7b921
```

All report validation fields were `true`, including exact request/nonce linkage, pinned public-key hash, transcript hashes and signature verification before and after exit.

## 7. VERIFIED — Standard-user worker separation

```text
Fresh local account created:       true
Worker administrator:              false
Worker integrity RID:              8192 / 0x2000
Created suspended:                 true
Assigned to Job before resume:     true
Worker in Job Object:              true
Child in same specific Job:        true
Controller secret absent:          true
Sentinel handle inherited:         false
Controller memory read blocked:    true
Job closed:                        true
Child killed by Job close:         true
Worker-SID process set empty:       true
Worker account deleted:            true
```

This evidence proves the declared benign worker boundary. It does not yet authorize arbitrary or patched code.

## 8. VERIFIED — Mappings and network

```text
Input mapping write blocked:     true
Control mapping write blocked:   true
Output mapping writable:         true
IPv4 default route present:      false
IPv4 external TCP reachable:     false
IPv6 default route present:      false
IPv6 external TCP reachable:     false
```

## 9. Independent offline evidence audit

The preserved ZIP was independently inspected after the run:

- every artifact SHA-256 referenced by the report matched the preserved bytes;
- `boundary_policy.json` canonical bytes produced the recorded boundary fingerprint;
- the public blob had the expected P-256 `ECS1` CNG header and valid curve point;
- the 64-byte P1363 signature verified over the exact `terminal_payload.json` bytes with ECDSA P-256/SHA-256;
- no private-key material was present in the preserved bundle.

This offline audit is evidence review only. Production verification is implemented separately in V1B3B through the Windows CNG host verifier.

## 10. Security interpretation and limits

V1B3A proves that the selected Windows Sandbox backend can provide:

```text
WDAG administrator bootstrap
    ↓
SYSTEM trusted controller
    ↓
ephemeral ECDSA key
    ↓
pinned ready → authorize handshake
    ↓
standard-user suspended worker
    ↓
kill-on-close Job Object and SID process sweep
    ↓
signed terminal transcript
    ↓
post-exit host verification
```

It does not yet prove the full production boundary implementation or patched-code execution.

Until V1B4 and V1C are complete:

```text
python_module          BLOCKED
pipeline               BLOCKED
patched-code execution BLOCKED
host fallback          FORBIDDEN
execution_authorized   false
```

## 11. VERIFIED — Production V1B3B host verifier closure

```text
674dd5f feat: add signed execution transcript verifier
verifier unit eval:                         45/45
Windows CNG smoke:                          3/3
real preserved evidence:                    signed_transcript_verified
developer_task_execution_boundary_verifier: completed successfully
full check:                                 completed successfully
execution_authorized:                       false
```

The production verifier pinned the exact pre-authorization public key and transcript bytes, verified the preserved V1B3A signature through Windows CNG and retained fail-closed replay/substitution/post-pin mutation guards. It does not launch Sandbox or run a worker.

## 12. VERIFIED — Production V1B3C worker isolation bundle closure

```text
74f543a feat: add standard-user worker isolation bundle
worker bundle unit/static eval:                28/28
exact Windows helper/worker compile smoke:     2/2
worker executable created:                     true
worker executable executed:                    false
developer_task_execution_boundary_worker:      completed successfully
full check:                                    completed successfully
execution_authorized:                          false
```

The production V1B3C bundle locks the exact native helper, fixed benign worker source and bundle fingerprint. Its public builder accepts no manifest, workspace, patch, executable or command input. The Windows smoke compiled the exact source bytes but deliberately did not execute the worker.

## 13. VERIFIED — Production V1B3D active signed composition closure

```text
f3f5607 feat: add active signed boundary composition
V1B3D unit/failure gate:                  40/40
active Windows composition:                3/3
status:                    active_signed_boundary_attested
signature valid:                           true
all Sandbox processes exited:              true
forced cleanup attempted:                  false
artifacts removed:                          true
developer_task_execution_boundary_composition: completed successfully
full check:                                 completed successfully
execution_authorized:                       false
```

The production one-Sandbox run used pre-authorization transcript pinning, direct `authorize.json` plus verified `authorize.sha256` commit, exact V1B3C worker bytes, standard-user/Job/SID cleanup, signed terminal output and post-exit exact-byte verification. The full Signed Result Authenticity and Privilege Separation boundary is now verified.

## 14. Next stage

```text
V1B4A — Runtime Source Provenance Gate
```

V1B4A is host-only and does not execute the candidate interpreter. It establishes exact official archive/SPDX provenance before any deterministic runtime bundle or active Python attestation is built. `execution_authorized=false` remains mandatory.
