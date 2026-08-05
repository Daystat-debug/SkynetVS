# SkynetVS Windows Sandbox Active Attestation V1

> **Historical precursor evidence.** This document records the `2026-08-04`
> pre-production capability attestation. It is preserved as evidence of the
> original `.wsb + LogonCommand` experiment. Current project status is defined
> by `SKYNETVS_CURRENT_STATE.md`; production V1B2 was later verified on
> `eb2a476` and hardened on `4ea2e0c`.

## Metadata

- Attestation date: `2026-08-04`
- Attestation request ID: `08904ed7b75d4716b25e137a0bf188fb`
- Host report status: `attested`
- Host report SHA-256: `6cdc600e9d5a0a16c6080132f243e5953742dc654dad0462db41ef8b1fdad9ae`
- Backend candidate: `traditional_wsb_logoncommand_v1`
- Backend implementation status at attestation time: `PLANNED`
- Executable checks status at attestation time: `BLOCKED until production capability gate is implemented`

## VERIFIED — Host-side result validation

The host received `result.json` and verified:

- the result exists;
- the result is a regular file;
- the result size is within the configured limit;
- schema version matches;
- request ID matches;
- the guest reported `overall_ok = true`.

All host validation fields were `true`.

## VERIFIED — Sandbox runtime

- Executable: `C:\WINDOWS\system32\WindowsSandbox.exe`
- Executable version: `10.0.26100.8875`
- `wsb` CLI available: `false`
- Guest account: `WDAGUtilityAccount`
- Guest process architecture: `X64`
- Guest PowerShell: `5.1.26100.8875`

The supported backend path for this host is therefore:

```text
WindowsSandbox.exe
    + .wsb configuration
    + LogonCommand
    + read-only input mapping
    + dedicated writable result mapping
    + canonical result marker
```

## VERIFIED — Actively measured guest controls

The guest probe confirmed:

- input mapping is present;
- input mapping is enforced read-only;
- output mapping is present;
- output mapping is writable;
- no IPv4 default route is present;
- a TCP connection to `1.1.1.1:443` is not reachable.

The input write attempt failed with access denied, as expected.

## VERIFIED — Declared `.wsb` controls

The generated `.wsb` configuration declared:

- vGPU disabled;
- networking disabled;
- audio input disabled;
- video input disabled;
- Protected Client enabled;
- printer redirection disabled;
- clipboard redirection disabled;
- input mapping read-only;
- output mapping writable.

These values are configuration evidence. Except where explicitly listed under actively measured controls, they were not independently measured by the guest probe.

## Evidence hashes

- Request JSON SHA-256: `6a0b8572ee7937a75be8a6fb0fd127fe277d2f524a379f8ed7307563e14a5756`
- Guest probe SHA-256: `17b3844f962f71953e0980fd3f50c1999717a1a10b4cfe0ec721176c1f27aa53`
- `.wsb` configuration SHA-256: `a028ff8eea5bd2e863dc0f9aed816f5b6b3391dc28759b51c0310809d8274716`
- Guest result SHA-256: `71b8016b5f674ddaa6b89a48da5df8a2a09f846376b511f583749003915ed820`

## Security interpretation

The active attestation proves that the traditional `.wsb` path works on this host and that the tested input/output and IPv4 network controls behaved as intended during this run.

It does **not** yet make executable developer-task checks production-ready.

At the time of this attestation, the following gaps still had to be implemented and evaluated before `python_module` or `pipeline` could run:

1. per-run request/result evidence;
2. strict host-side schema and path validation;
3. a fresh dedicated output directory for every run;
4. bounded result size and canonical JSON validation;
5. timeout handling;
6. deterministic Sandbox termination or fail-closed lifecycle handling;
7. IPv6 network-route and connectivity probes;
8. prevention of host fallback;
9. a trusted Python runtime strategy inside Sandbox;
10. proof that the source repository and task workspace remain unchanged except for explicitly permitted result artifacts.

## Current policy

```text
git_diff_check  -> allowed through trusted static runner
py_compile      -> allowed only through trusted non-importing static runner
python_module   -> blocked
pipeline        -> blocked
host fallback   -> forbidden
dependency installation -> forbidden
```

## Architectural verdict

```text
Hardware capability:                   VERIFIED
Windows Sandbox optional feature:      VERIFIED
Traditional WindowsSandbox.exe:        VERIFIED
Active .wsb + LogonCommand execution:  VERIFIED
Read-only input mapping:               VERIFIED
Writable result mapping:               VERIFIED
IPv4 network isolation probe:          VERIFIED
Production backend module at this run: PLANNED
Executable checks:                     BLOCKED
```

## Historical next stage and current follow-up

At the time of this attestation, the next stages were V1A and V1B.

Those stages later progressed as follows:

```text
V1A Static Evidence Gate:                 VERIFIED
V1B1 Host Capability Gate:                VERIFIED
V1B2 Active Trusted Lifecycle Gate:       VERIFIED
V1B2 launch-environment hardening:        VERIFIED
Current stage:                            V1B3 Signed Result Authenticity
```

This historical document alone never authorizes executable checks.
`python_module`, `pipeline` and patched-code execution remain blocked until
V1B3, V1B4 and V1C are complete.
