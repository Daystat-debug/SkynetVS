# SkynetVS Trusted Python Runtime V1

## 1. Статус

```text
V1B3  — VERIFIED
V1B4A — VERIFIED
V1B4B — VERIFIED
V1B4C — CURRENT
V1B4D — PLANNED
V1C   — BLOCKED
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
05e0e00 feat: add deterministic trusted runtime bundle
```

The active signed boundary beneath V1B4 remains the verified `f3f5607` composition. V1B4B adds exact CPython 3.13.15 source verification and deterministic bundle construction without executing the interpreter.

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

V1B4C is split internally:

```text
V1B4C1  Runtime Attestation Contract and Payload Gate   CURRENT
V1B4C2  Active Trusted Runtime Composition              PLANNED
```

#### V1B4C1 — Runtime Attestation Contract and Payload Gate

This non-active slice:

- introduces a new immutable V1B4C policy/schema lineage while historical V1B3 fingerprints remain unchanged;
- defines strict canonical request, ready, authorize, runtime-result and terminal documents;
- binds source, provenance, tree, bundle, runtime-manifest, `_pth`, probe, runner and launch-contract identities;
- builds exact SYSTEM-controller/native-helper/bootstrap/`.wsb` payload bytes;
- locks four mapped roots: Input read-only, Runtime read-only, Control read-only and Output writable;
- statically audits and compile-checks the payload without launching Windows Sandbox or `python.exe`;
- accepts no manifest, workspace, patch, module, pipeline, caller argv, caller environment or arbitrary executable;
- keeps `execution_authorized=false`.

#### V1B4C2 — Active Trusted Runtime Composition

One production Windows Sandbox run will:

```text
fresh host/backend evidence
    ↓
exact V1B4B capability materialized and mapped read-only
    ↓
SYSTEM controller verifies every runtime byte and manifest
    ↓
fresh standard-user token with sanitized environment
    ↓
explicit runtime\python.exe
    ↓
CREATE_SUSPENDED → Job Object → ResumeThread
    ↓
fixed trusted runtime runner/probe only
    ↓
Job close + worker-SID quiescence + exact account deletion
    ↓
signed terminal transcript
    ↓
all Sandbox processes exited
    ↓
post-exit exact-byte and CNG signature verification
```

Probe attests at minimum:

```text
CPython 3.13.15 / AMD64
sys.flags.isolated == 1
sys.flags.ignore_environment == 1
sys.flags.no_user_site == 1
sys.flags.safe_path == true
sys.flags.dont_write_bytecode == 1
sys.flags.utf8_mode == 1
site not imported
exact runtime-local sys.path
no PYTHON*/PIP_*/VIRTUAL_ENV variables
pip/ensurepip absent
runtime root not writable
standard-user/Job/SID cleanup evidence
network isolation evidence
```

V1B4C2 remains benign capability evidence. It does not execute patch/workspace code and returns `execution_authorized=false`.

### V1B4D — Same-Run Runtime Capability Lease

Создаёт non-serialized single-use lease с TTL `300` секунд, связанный с:

- host boot identity;
- Windows build;
- Sandbox executable path/version/SHA-256;
- backend policy fingerprint;
- signed-boundary policy fingerprint;
- runtime source fingerprint;
- runtime bundle fingerprint;
- one-time random token.

Lease не доказывает прошлый Sandbox run и не разрешает cross-run execution. Он только разрешает V1C orchestrator начать один combined run с exact runtime bundle.

Внутри этого же V1C Sandbox instance до первого changed-code instruction повторно выполняются:

```text
runtime manifest verification
runtime benign preflight
network evidence
worker privilege evidence
Job membership evidence
signed transcript handshake
```

Если Sandbox завершился после runtime attestation, lease считается использованным/недействительным; новый task требует нового lease и нового same-run attestation.

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
active benign runtime attestation          green
post-exit signed verification              green
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

V1B4C1 bounded contract/payload implementation may run on **«Очень высокий»** after this split is committed. V1B4C2 active Windows composition, V1B4D lease design and the V1C handoff require **Pro Standard**.
