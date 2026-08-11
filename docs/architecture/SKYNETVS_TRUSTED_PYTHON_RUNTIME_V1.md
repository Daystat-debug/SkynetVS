# SkynetVS Trusted Python Runtime V1

## 1. Статус

```text
V1B3 — VERIFIED
V1B4 — CURRENT
V1C  — BLOCKED
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
f3f5607 feat: add active signed boundary composition
```

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

## 4. Runtime source candidate и нерешённый lifecycle-риск

Первый совместимый candidate для V1B4A:

```text
kind:            CPython Windows embeddable package
version:         3.12.10
architecture:    AMD64
file:            python-3.12.10-embed-amd64.zip
source SHA-256:  4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3
```

Причина выбора candidate — exact patch-version parity с текущим SkynetVS host interpreter.

Это ещё не окончательное разрешение для V1C. Python `3.12.10` был последним regular bugfix release серии 3.12 с Windows binaries; последующие 3.12 security releases являются source-only. Поэтому V1B4A сначала фиксирует exact provenance и compatibility evidence, а отдельный Pro-review решает один из вариантов:

1. принять `3.12.10` только как benign-attestation runtime и оставить patched-code execution заблокированным;
2. перевести SkynetVS baseline на поддерживаемую binary line и построить новый runtime bundle;
3. воспроизводимо собрать более новый security release 3.12 из source и отдельно аттестовать toolchain/provenance.

Ни один вариант не выбирается молча.

## 5. V1B4 разделён на четыре evidence-среза

### V1B4A — Runtime Source Provenance Gate

Host-only gate, который не запускает `python.exe` из bundle.

Он проверяет:

- exact source archive filename, regular-file/no-reparse state и bounded size;
- exact source archive SHA-256;
- official SPDX document, CPython package name/version/filename и matching SHA-256;
- ZIP path safety, duplicate/case-collision guards, encryption/symlink rejection и bounded expansion;
- mandatory embeddable files;
- отсутствие `pip`, `ensurepip`, `site-packages`, `Scripts` и `pyvenv.cfg`;
- AMD64 PE machine for executable/DLL/PYD entries;
- upstream `python312._pth` без active `import site`;
- deterministic source-manifest fingerprint.

Результат:

```text
DeveloperTaskPythonRuntimeSourceReport
execution_authorized=false
```

### V1B4B — Deterministic Runtime Bundle Gate

Строит derived application-local bundle только из успешно проверенного V1B4A source.

Derived bundle содержит:

```text
exact CPython embeddable files
locked python312._pth
fixed trusted runtime probe
fixed trusted runtime launcher/runner
canonical file manifest
canonical launch contract
```

Правила:

- download/install во время task отсутствуют;
- `pip` и `ensurepip` отсутствуют;
- `import site` отсутствует;
- нет arbitrary `.pth`, `sitecustomize.py`, `usercustomize.py` или writable package directory;
- extra/missing file, case collision, reparse point, ADS или hash mismatch fail closed;
- source fingerprint и derived bundle fingerprint хранятся раздельно;
- exact bytes доступны только через non-serialized capability внутри процесса;
- public builder не принимает manifest, workspace, patch, shell command или arbitrary executable.

Результат:

```text
DeveloperTaskPythonRuntimeBundle
DeveloperTaskPythonRuntimeBundleReport
execution_authorized=false
```

### V1B4C — Active Trusted Runtime Attestation

Один production Windows Sandbox run выполняет только fixed benign Python probe.

State machine:

```text
fresh host/backend evidence
    ↓
exact V1B4B bundle staged read-only
    ↓
SYSTEM controller verifies source + bundle manifest
    ↓
fresh standard-user token
    ↓
explicit runtime\python.exe
    ↓
CREATE_SUSPENDED → Job Object → ResumeThread
    ↓
fixed trusted runtime probe
    ↓
Job close + worker-SID process quiescence + account deletion
    ↓
signed terminal transcript
    ↓
all Sandbox processes exited
    ↓
post-exit exact-byte + CNG signature verification
```

Probe attests at minimum:

```text
CPython identity/version/AMD64
sys.flags.isolated == 1
sys.flags.ignore_environment == 1
sys.flags.no_user_site == 1
sys.flags.safe_path == true
sys.flags.dont_write_bytecode == 1
site not imported
exact sys.path
PYTHONHOME/PYTHONPATH poison ignored
user site absent
pip/ensurepip absent
runtime root not writable by worker
fixed probe/result schema
network disabled
standard-user/Job/SID cleanup evidence
```

Locked interpreter invocation begins with an explicit executable path and fixed flags:

```text
python.exe -I -S -B -E -s -P -X utf8
```

Redundant flags are intentional evidence; no `-m`, `-c`, stdin program, shell resolution or caller-supplied argument is accepted in V1B4C.

Standalone active attestation is capability evidence only:

```text
execution_authorized=false
```

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
    python312.dll
    python312.zip
    python312._pth
    *.pyd
    required runtime DLLs
    LICENSE.txt
    skynetvs_runtime_probe.py
    skynetvs_runtime_runner.py
    runtime_manifest.json
```

`python312._pth` — project-owned locked file. Допустимые active path entries ограничены runtime-local paths; `import site` запрещён.

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
python312._pth SHA-256
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

После фиксации архитектуры bounded host-only implementation V1B4A/V1B4B может выполняться на **«Очень высокий»**. Перед V1B4C active Windows composition нужно вернуться на **Pro Standard**.
