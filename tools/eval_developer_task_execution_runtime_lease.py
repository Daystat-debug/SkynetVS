from __future__ import annotations

import copy
import gc
import inspect
import json
import pickle
import threading
import weakref

from dataclasses import replace
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_runtime_lease as lease_module

from modules.developer.developer_task_execution_backend_host import (
    DeveloperTaskExecutionBackendExecutableEvidence,
    DeveloperTaskExecutionBackendHostReport,
)
from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    DeveloperTaskPythonRuntimeBundle,
)
from modules.developer.developer_task_execution_runtime_lease import (
    DeveloperTaskExecutionRuntimeLease,
    DeveloperTaskExecutionRuntimeLeaseError,
    LEASE_STATE_CLAIMED,
    LEASE_STATE_EXPIRED,
    LEASE_STATE_INVALIDATED,
    LEASE_STATE_ISSUED,
    issue_developer_task_execution_runtime_lease,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_CLOCK_ID,
    RUNTIME_LEASE_HOST_BOOT_EPOCH_TOLERANCE_SECONDS,
    RUNTIME_LEASE_POLICY_FINGERPRINT,
    RUNTIME_LEASE_POLICY_ID,
    RUNTIME_LEASE_SECRET_BYTES,
    RUNTIME_LEASE_TTL_SECONDS,
    TRUSTED_PYTHON_RUNTIME_LEASE_POLICY_V1,
    validate_execution_runtime_lease_policy,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue


class _FakeServices:
    def __init__(self, host: DeveloperTaskExecutionBackendHostReport, *, now_ns: int = 10_000_000_000) -> None:
        self.host = host
        self.now_ns = now_ns
        self.inspect_calls = 0
        self.token_calls = 0
        self.token_value: bytes | Exception = b"L" * RUNTIME_LEASE_SECRET_BYTES

    def inspect_host(self) -> DeveloperTaskExecutionBackendHostReport:
        self.inspect_calls += 1
        return self.host

    def monotonic_ns(self) -> int:
        return self.now_ns

    def token_bytes(self, size: int) -> bytes:
        self.token_calls += 1
        if isinstance(self.token_value, Exception):
            raise self.token_value
        return self.token_value


def _host(
    *,
    boot: int = 1_786_600_000,
    sha256: str = "a" * 64,
    windows_build: int = 26100,
    feature_state: str = "enabled",
    running: tuple[str, ...] = (),
    issues: tuple[DeveloperTaskPreflightIssue, ...] = (),
) -> DeveloperTaskExecutionBackendHostReport:
    executable = DeveloperTaskExecutionBackendExecutableEvidence(
        path=r"C:\Windows\System32\WindowsSandbox.exe",
        version="10.0.26100.1",
        size_bytes=1_234_567,
        mtime_ns=1_700_000_000_000_000_000,
        sha256=sha256,
    )
    return DeveloperTaskExecutionBackendHostReport(
        backend_id=WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id,
        policy=WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
        policy_fingerprint=WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
        host_platform="win32",
        host_architecture="AMD64",
        process_bitness=64,
        windows_build=windows_build,
        host_boot_epoch_seconds=boot,
        feature_state=feature_state,
        feature_probe_error="",
        executable=executable,
        wsb_cli_found=False,
        wsb_cli_path="",
        wsb_cli_probe_error="",
        running_sandbox_processes=running,
        issues=issues,
    )


def _bundle() -> DeveloperTaskPythonRuntimeBundle:
    return DeveloperTaskPythonRuntimeBundle(report=None, _files=())  # type: ignore[arg-type]


def _error_code(callable_: Any) -> str:
    try:
        callable_()
    except DeveloperTaskExecutionRuntimeLeaseError as exc:
        return exc.code
    except TypeError:
        return "TypeError"
    return ""


def _reset_registry() -> None:
    with lease_module._REGISTRY_LOCK:
        lease_module._REGISTRY.clear()


def _issue(
    host: DeveloperTaskExecutionBackendHostReport,
    bundle: DeveloperTaskPythonRuntimeBundle,
    services: _FakeServices,
) -> DeveloperTaskExecutionRuntimeLease:
    with patch.object(lease_module, "_SERVICES", services), patch.object(
        lease_module,
        "_runtime_bundle_differences",
        return_value=(),
    ):
        return issue_developer_task_execution_runtime_lease(host, bundle)


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        if not ok:
            fail_count += 1
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    _reset_registry()
    policy = TRUSTED_PYTHON_RUNTIME_LEASE_POLICY_V1
    check(
        "V1B4D PINNED LEASE POLICY SELF CHECKS",
        {
            "errors": list(validate_execution_runtime_lease_policy(policy)),
            "policy_id": policy.policy_id,
            "fingerprint": policy.fingerprint,
            "ttl": policy.ttl_seconds,
            "clock": policy.clock_id,
            "secret_bytes": policy.secret_bytes,
            "boot_tolerance": policy.host_boot_epoch_tolerance_seconds,
            "execution_authorized": policy.to_dict()["capability"]["execution_authorized"],
        },
        {
            "errors": [],
            "policy_id": RUNTIME_LEASE_POLICY_ID,
            "fingerprint": RUNTIME_LEASE_POLICY_FINGERPRINT,
            "ttl": 300,
            "clock": "time.monotonic_ns",
            "secret_bytes": 32,
            "boot_tolerance": 1,
            "execution_authorized": False,
        },
    )

    check(
        "V1B4D PUBLIC ISSUANCE API ACCEPTS ONLY HOST REPORT AND RUNTIME BUNDLE",
        {
            name: parameter.kind.name
            for name, parameter in inspect.signature(issue_developer_task_execution_runtime_lease).parameters.items()
        },
        {
            "host_report": "POSITIONAL_OR_KEYWORD",
            "runtime_bundle": "POSITIONAL_OR_KEYWORD",
        },
    )

    check(
        "V1B4D PUBLIC CLAIM API ACCEPTS NO CALLER CONTROLLED INPUT",
        list(inspect.signature(DeveloperTaskExecutionRuntimeLease.claim).parameters),
        ["self"],
    )

    check(
        "V1B4D TTL CLOCK AND BOOT QUANTIZATION ARE LOCKED",
        {
            "ttl": RUNTIME_LEASE_TTL_SECONDS,
            "clock": RUNTIME_LEASE_CLOCK_ID,
            "boot_tolerance": RUNTIME_LEASE_HOST_BOOT_EPOCH_TOLERANCE_SECONDS,
            "backend_ttl": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.attestation_ttl_seconds,
        },
        {
            "ttl": 300,
            "clock": "time.monotonic_ns",
            "boot_tolerance": 1,
            "backend_ttl": 300,
        },
    )

    check(
        "V1B4D RAW HOST AND RUNTIME INPUTS ARE REJECTED",
        {
            "host": _error_code(lambda: issue_developer_task_execution_runtime_lease({}, _bundle())),  # type: ignore[arg-type]
            "bundle": _error_code(lambda: issue_developer_task_execution_runtime_lease(_host(), {})),  # type: ignore[arg-type]
        },
        {"host": "TypeError", "bundle": "TypeError"},
    )

    bad_host = replace(
        _host(),
        issues=(DeveloperTaskPreflightIssue(code="synthetic", check="host", message="synthetic"),),
    )
    check(
        "V1B4D FAILED HOST REPORT IS REJECTED",
        _error_code(lambda: _issue(bad_host, _bundle(), _FakeServices(_host()))),
        "runtime_lease_host_report_failed",
    )

    check(
        "V1B4D INVALID RUNTIME BUNDLE SELF CHECK IS REJECTED",
        _error_code(lambda: issue_developer_task_execution_runtime_lease(_host(), _bundle())),
        "runtime_lease_runtime_bundle_invalid",
    )

    base_host = _host()
    services = _FakeServices(replace(base_host, executable=replace(base_host.executable, sha256="b" * 64)))
    check(
        "V1B4D FRESH HOST IDENTITY MISMATCH BLOCKS ISSUANCE",
        _error_code(lambda: _issue(base_host, _bundle(), services)),
        "runtime_lease_host_evidence_changed",
    )

    running_host = _host(running=("WindowsSandbox.exe:1234",))
    check(
        "V1B4D RUNNING SANDBOX PROCESS BLOCKS FRESH ISSUANCE",
        _error_code(lambda: _issue(base_host, _bundle(), _FakeServices(running_host))),
        "runtime_lease_fresh_host_report_failed",
    )

    services = _FakeServices(_host(boot=base_host.host_boot_epoch_seconds + 1))
    jitter_bundle = _bundle()
    lease = _issue(base_host, jitter_bundle, services)
    services.host = base_host
    with patch.object(lease_module, "_SERVICES", services), patch.object(
        lease_module,
        "_runtime_bundle_differences",
        return_value=(),
    ):
        jitter_claimed = lease.claim()
    check(
        "V1B4D ONE SECOND BOOT EPOCH QUANTIZATION JITTER IS ACCEPTED THROUGH CLAIM",
        {
            "same_object": jitter_claimed is jitter_bundle,
            "state": lease.status().state,
        },
        {
            "same_object": True,
            "state": LEASE_STATE_CLAIMED,
        },
    )

    _reset_registry()
    issuance_drift_services = _FakeServices(_host(boot=base_host.host_boot_epoch_seconds + 2))
    issuance_drift_code = _error_code(
        lambda: _issue(base_host, _bundle(), issuance_drift_services)
    )
    claim_drift_services = _FakeServices(base_host)
    drift_bundle = _bundle()
    drift_lease = _issue(base_host, drift_bundle, claim_drift_services)
    claim_drift_services.host = _host(boot=base_host.host_boot_epoch_seconds + 2)
    with patch.object(lease_module, "_SERVICES", claim_drift_services), patch.object(
        lease_module,
        "_runtime_bundle_differences",
        return_value=(),
    ):
        claim_drift_code = _error_code(drift_lease.claim)
    check(
        "V1B4D TWO SECOND BOOT EPOCH DRIFT IS REJECTED AT ISSUE AND CLAIM",
        {
            "issue_code": issuance_drift_code,
            "claim_code": claim_drift_code,
            "claim_state": drift_lease.status().state,
        },
        {
            "issue_code": "runtime_lease_host_evidence_changed",
            "claim_code": "runtime_lease_host_evidence_changed",
            "claim_state": LEASE_STATE_INVALIDATED,
        },
    )

    _reset_registry()
    services = _FakeServices(base_host, now_ns=123_000_000_000)
    bundle = _bundle()
    lease = _issue(base_host, bundle, services)
    with lease_module._REGISTRY_LOCK:
        state = lease_module._REGISTRY[lease]
    check(
        "V1B4D ISSUANCE BINDS EXACT 300 SECOND MONOTONIC WINDOW",
        {
            "state": state.state,
            "issued_at_ns": state.issued_at_ns,
            "duration_ns": state.expires_at_ns - state.issued_at_ns,
            "secret_size": len(state.secret),
            "binding_fingerprint_len": len(state.binding_fingerprint),
            "execution_authorized": lease.execution_authorized,
        },
        {
            "state": LEASE_STATE_ISSUED,
            "issued_at_ns": 123_000_000_000,
            "duration_ns": 300_000_000_000,
            "secret_size": 32,
            "binding_fingerprint_len": 64,
            "execution_authorized": False,
        },
    )

    services.now_ns = state.expires_at_ns - 1
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
        claimed = lease.claim()
    with lease_module._REGISTRY_LOCK:
        claimed_state = lease_module._REGISTRY[lease]
    check(
        "V1B4D CLAIM BEFORE EXPIRY RETURNS EXACT RETAINED RUNTIME CAPABILITY",
        {
            "same_object": claimed is bundle,
            "state": lease.status().state,
            "private_runtime_released": claimed_state.runtime_bundle is None,
            "private_secret_released": claimed_state.secret == b"",
            "monotonic_anchors_released": claimed_state.issued_at_ns == 0 and claimed_state.expires_at_ns == 0,
            "execution_authorized": lease.execution_authorized,
        },
        {
            "same_object": True,
            "state": LEASE_STATE_CLAIMED,
            "private_runtime_released": True,
            "private_secret_released": True,
            "monotonic_anchors_released": True,
            "execution_authorized": False,
        },
    )

    check(
        "V1B4D SECOND CLAIM AND REPLAY ARE REJECTED",
        _error_code(lambda: lease.claim()),
        "runtime_lease_already_claimed",
    )

    _reset_registry()
    services = _FakeServices(base_host, now_ns=1_000)
    lease = _issue(base_host, _bundle(), services)
    with lease_module._REGISTRY_LOCK:
        expires_at = lease_module._REGISTRY[lease].expires_at_ns
    services.now_ns = expires_at
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
        boundary_code = _error_code(lease.claim)
    check(
        "V1B4D CLAIM AT EXPIRY BOUNDARY IS REJECTED",
        {"code": boundary_code, "state": lease.status().state},
        {"code": "runtime_lease_expired", "state": LEASE_STATE_EXPIRED},
    )

    _reset_registry()
    services = _FakeServices(base_host, now_ns=10_000)
    lease = _issue(base_host, _bundle(), services)
    with lease_module._REGISTRY_LOCK:
        expires_at = lease_module._REGISTRY[lease].expires_at_ns
    services.now_ns = expires_at + 1
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
        after_code = _error_code(lease.claim)
    check(
        "V1B4D CLAIM AFTER EXPIRY IS REJECTED",
        {"code": after_code, "state": lease.status().state},
        {"code": "runtime_lease_expired", "state": LEASE_STATE_EXPIRED},
    )

    _reset_registry()
    services = _FakeServices(base_host, now_ns=1_000_000)
    lease = _issue(base_host, _bundle(), services)
    with lease_module._REGISTRY_LOCK:
        expires_at = lease_module._REGISTRY[lease].expires_at_ns
    services.now_ns = expires_at
    with patch.object(lease_module, "_SERVICES", services):
        status = lease.status()
    check(
        "V1B4D STATUS OBSERVATION CANNOT RETAIN EXPIRED AUTHORITY",
        status.to_dict(),
        {
            "state": LEASE_STATE_EXPIRED,
            "policy_id": RUNTIME_LEASE_POLICY_ID,
            "policy_fingerprint": RUNTIME_LEASE_POLICY_FINGERPRINT,
            "ttl_seconds": 300,
            "execution_authorized": False,
        },
    )

    _reset_registry()
    services = _FakeServices(base_host, now_ns=20_000_000_000)
    lease = _issue(base_host, _bundle(), services)
    services.host = replace(base_host, executable=replace(base_host.executable, sha256="c" * 64))
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
        drift_code = _error_code(lease.claim)
    check(
        "V1B4D HOST EXECUTABLE HASH DRIFT INVALIDATES LEASE",
        {"code": drift_code, "state": lease.status().state},
        {"code": "runtime_lease_host_evidence_changed", "state": LEASE_STATE_INVALIDATED},
    )

    services.host = base_host
    check(
        "V1B4D FAILED CLAIM IS TERMINAL EVEN AFTER HOST RECOVERS",
        _error_code(lease.claim),
        "runtime_lease_invalidated",
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    services.host = replace(base_host, windows_build=base_host.windows_build + 1)
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
        build_drift_code = _error_code(lease.claim)
    check(
        "V1B4D WINDOWS BUILD DRIFT INVALIDATES LEASE",
        {"code": build_drift_code, "state": lease.status().state},
        {"code": "runtime_lease_host_evidence_changed", "state": LEASE_STATE_INVALIDATED},
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    services.host = replace(base_host, feature_state="unknown")
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
        feature_drift_code = _error_code(lease.claim)
    check(
        "V1B4D SANDBOX FEATURE STATE DRIFT INVALIDATES LEASE",
        {"code": feature_drift_code, "state": lease.status().state},
        {"code": "runtime_lease_host_evidence_changed", "state": LEASE_STATE_INVALIDATED},
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=("synthetic_runtime_mutation",)):
        runtime_mutation_code = _error_code(lease.claim)
    check(
        "V1B4D RUNTIME IDENTITY MUTATION INVALIDATES LEASE",
        {"code": runtime_mutation_code, "state": lease.status().state},
        {"code": "runtime_lease_runtime_bundle_invalid", "state": LEASE_STATE_INVALIDATED},
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    original_guard = lease._guard
    object.__setattr__(lease, "_guard", b"Z" * len(original_guard))
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
        guard_code = _error_code(lease.claim)
    check(
        "V1B4D ISSUER SECRET GUARD SUBSTITUTION INVALIDATES LEASE",
        {"code": guard_code, "state": lease.status().state},
        {"code": "runtime_lease_issuer_binding_invalid", "state": LEASE_STATE_INVALIDATED},
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()), patch.object(
        lease_module,
        "RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT",
        "d" * 64,
    ):
        lineage_code = _error_code(lease.claim)
    check(
        "V1B4D RUNTIME ATTESTATION LINEAGE SUBSTITUTION INVALIDATES LEASE",
        {"code": lineage_code, "state": lease.status().state},
        {"code": "runtime_lease_binding_invalid", "state": LEASE_STATE_INVALIDATED},
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()), patch.object(
        lease_module,
        "RUNTIME_LEASE_POLICY_FINGERPRINT",
        "e" * 64,
    ):
        policy_binding_code = _error_code(lease.claim)
    check(
        "V1B4D LEASE POLICY FINGERPRINT SUBSTITUTION INVALIDATES LEASE",
        {"code": policy_binding_code, "state": lease.status().state},
        {"code": "runtime_lease_binding_invalid", "state": LEASE_STATE_INVALIDATED},
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    copied = object.__new__(DeveloperTaskExecutionRuntimeLease)
    object.__setattr__(copied, "_guard", lease._guard)
    check(
        "V1B4D CROSS ISSUER OR RESTORED OBJECT HAS NO PROCESS LOCAL AUTHORITY",
        _error_code(copied.claim),
        "runtime_lease_unregistered",
    )

    copy_results: dict[str, str] = {}
    for name, operation in (
        ("copy", lambda: copy.copy(lease)),
        ("deepcopy", lambda: copy.deepcopy(lease)),
        ("pickle", lambda: pickle.dumps(lease)),
    ):
        try:
            operation()
        except TypeError:
            copy_results[name] = "blocked"
        else:
            copy_results[name] = "allowed"
    check(
        "V1B4D COPY DEEPCOPY AND PICKLE ARE REJECTED",
        copy_results,
        {"copy": "blocked", "deepcopy": "blocked", "pickle": "blocked"},
    )

    status_dict = lease.status().to_dict()
    representation = repr(lease)
    check(
        "V1B4D REPR AND STATUS ARE REDACTED AND NON AUTHORIZING",
        {
            "status_keys": sorted(status_dict),
            "repr_has_windows_path": "C:\\Windows" in representation,
            "repr_has_runtime_bundle": RUNTIME_BUNDLE_FINGERPRINT in representation,
            "repr_has_guard": lease._guard.hex() in representation,
            "has_dict": hasattr(lease, "__dict__"),
            "execution_authorized": status_dict["execution_authorized"],
        },
        {
            "status_keys": ["execution_authorized", "policy_fingerprint", "policy_id", "state", "ttl_seconds"],
            "repr_has_windows_path": False,
            "repr_has_runtime_bundle": False,
            "repr_has_guard": False,
            "has_dict": False,
            "execution_authorized": False,
        },
    )

    _reset_registry()
    services = _FakeServices(base_host)
    bundle = _bundle()
    lease = _issue(base_host, bundle, services)
    results: list[str] = []
    result_lock = threading.Lock()
    barrier = threading.Barrier(3)

    def claimant() -> None:
        barrier.wait()
        with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
            try:
                value = lease.claim()
            except DeveloperTaskExecutionRuntimeLeaseError as exc:
                result = exc.code
            else:
                result = "claimed" if value is bundle else "wrong_bundle"
        with result_lock:
            results.append(result)

    threads = [threading.Thread(target=claimant) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)
    check(
        "V1B4D CONCURRENT DOUBLE CLAIM PERMITS EXACTLY ONE WINNER",
        sorted(results),
        ["claimed", "runtime_lease_already_claimed"],
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    before = len(lease_module._REGISTRY)
    reference = weakref.ref(lease)
    del lease
    gc.collect()
    after = len(lease_module._REGISTRY)
    check(
        "V1B4D GARBAGE COLLECTION RELEASES PROCESS LOCAL PRIVATE STATE",
        {"before": before, "after": after, "lease_alive": reference() is not None},
        {"before": 1, "after": 0, "lease_alive": False},
    )

    _reset_registry()
    services = _FakeServices(base_host)
    services.token_value = RuntimeError("synthetic RNG failure")
    check(
        "V1B4D SECRET GENERATION FAILURE CREATES NO PARTIAL AUTHORITY",
        {
            "code": _error_code(lambda: _issue(base_host, _bundle(), services)),
            "registry_size": len(lease_module._REGISTRY),
        },
        {"code": "runtime_lease_secret_generation_failed", "registry_size": 0},
    )

    _reset_registry()
    services = _FakeServices(base_host, now_ns=-1)
    check(
        "V1B4D INVALID MONOTONIC CLOCK BLOCKS ISSUANCE",
        {
            "code": _error_code(lambda: _issue(base_host, _bundle(), services)),
            "registry_size": len(lease_module._REGISTRY),
        },
        {"code": "runtime_lease_clock_invalid", "registry_size": 0},
    )

    _reset_registry()
    services = _FakeServices(base_host)
    lease = _issue(base_host, _bundle(), services)
    with lease_module._REGISTRY_LOCK:
        state = lease_module._REGISTRY[lease]
    state.issuer_id = object()
    with patch.object(lease_module, "_SERVICES", services), patch.object(lease_module, "_runtime_bundle_differences", return_value=()):
        issuer_code = _error_code(lease.claim)
    check(
        "V1B4D MODULE INSTANCE ISSUER IDENTITY IS VERIFIED AT CLAIM",
        {"code": issuer_code, "state": lease.status().state},
        {"code": "runtime_lease_issuer_binding_invalid", "state": LEASE_STATE_INVALIDATED},
    )

    source = inspect.getsource(lease_module)
    forbidden = (
        "import subprocess",
        "subprocess.",
        "Popen(",
        "WindowsSandbox.exe",
        "CreateProcess",
        "os.system(",
        "shell=True",
        "pip install",
        "python_module",
        "pipeline flow",
    )
    check(
        "V1B4D PRODUCTION LEASE HAS NO SANDBOX PYTHON INSTALL OR CHANGED CODE EXECUTION SURFACE",
        {marker: marker in source for marker in forbidden},
        {marker: False for marker in forbidden},
    )

    check(
        "V1B4D PRODUCTION CLOCK IS MONOTONIC ONLY",
        {
            "monotonic_ns": "time.monotonic_ns()" in source,
            "time_time": "time.time()" in source,
            "datetime": "datetime" in source,
            "caller_clock": "clock=" in str(inspect.signature(issue_developer_task_execution_runtime_lease)),
            "caller_ttl": "ttl" in inspect.signature(issue_developer_task_execution_runtime_lease).parameters,
        },
        {
            "monotonic_ns": True,
            "time_time": False,
            "datetime": False,
            "caller_clock": False,
            "caller_ttl": False,
        },
    )

    check(
        "V1B4D POLICY BINDS EXACT V1B4B AND V1B4C LINEAGE",
        {
            "bundle_fingerprint": policy.runtime_bundle_fingerprint,
            "attestation_policy": policy.runtime_attestation_policy_fingerprint,
            "attestation_payload": policy.runtime_attestation_payload_fingerprint,
        },
        {
            "bundle_fingerprint": "1c98ad24ec3e4bb1b8b4bcd530ffedcf6ff62a6fee5b94cb795f6c84fb1c8c4b",
            "attestation_policy": "31c4f8de17e999db2d064a8aca4e95d3e2400f21a229317e83b1d5700d1e3c48",
            "attestation_payload": "47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13",
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
