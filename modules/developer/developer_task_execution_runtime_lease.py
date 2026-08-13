from __future__ import annotations

"""V1B4D host-only process-local same-run trusted runtime capability lease."""

import hashlib
import hmac
import json
import secrets
import threading
import time
import weakref

from dataclasses import dataclass, field
from typing import Any

from modules.developer.developer_task_execution_backend_host import (
    DeveloperTaskExecutionBackendHostReport,
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    DeveloperTaskPythonRuntimeBundle,
    DeveloperTaskPythonRuntimeBundleReport,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_HOST_BOOT_EPOCH_TOLERANCE_SECONDS,
    RUNTIME_LEASE_POLICY_FINGERPRINT,
    RUNTIME_LEASE_POLICY_ID,
    RUNTIME_LEASE_SECRET_BYTES,
    RUNTIME_LEASE_TTL_SECONDS,
    TRUSTED_PYTHON_RUNTIME_LEASE_POLICY_V1,
    validate_execution_runtime_lease_policy,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_ID,
    RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    RUNTIME_LOCKED_PTH_FILE_NAME,
    RUNTIME_LOCKED_PTH_SHA256,
    RUNTIME_MANIFEST_FILE_NAME,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PROBE_FILE_NAME,
    RUNTIME_PROBE_SHA256,
    RUNTIME_RUNNER_FILE_NAME,
    RUNTIME_RUNNER_SHA256,
    RUNTIME_SOURCE_ARCHITECTURE,
    RUNTIME_SOURCE_FINGERPRINT,
    RUNTIME_SOURCE_ID,
    RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
    RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    RUNTIME_SOURCE_PYTHON_DLL_SHA256,
    RUNTIME_SOURCE_PYTHON_EXE_SHA256,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
    RUNTIME_SOURCE_STDLIB_SHA256,
    RUNTIME_SOURCE_VERSION,
    RUNTIME_TREE_MANIFEST_SHA256,
)


LEASE_STATE_ISSUED = "issued"
LEASE_STATE_CLAIMED = "claimed"
LEASE_STATE_EXPIRED = "expired"
LEASE_STATE_INVALIDATED = "invalidated"

_CONSTRUCTOR_KEY = object()
_ISSUER_ID = object()
_ISSUER_SECRET = secrets.token_bytes(32)
_REGISTRY_LOCK = threading.RLock()
_REGISTRY: weakref.WeakKeyDictionary[DeveloperTaskExecutionRuntimeLease, _LeaseState] = weakref.WeakKeyDictionary()


class DeveloperTaskExecutionRuntimeLeaseError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        self.code = code
        self.message = message
        self.actual = actual
        super().__init__(message)


@dataclass(frozen=True)
class DeveloperTaskExecutionRuntimeLeaseStatus:
    state: str
    policy_id: str = RUNTIME_LEASE_POLICY_ID
    policy_fingerprint: str = RUNTIME_LEASE_POLICY_FINGERPRINT
    ttl_seconds: int = RUNTIME_LEASE_TTL_SECONDS
    execution_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "ttl_seconds": self.ttl_seconds,
            "execution_authorized": False,
        }


@dataclass(frozen=True)
class _HostIdentity:
    backend_id: str
    policy_fingerprint: str
    host_platform: str
    host_architecture: str
    process_bitness: int
    windows_build: int
    host_boot_epoch_seconds: int
    feature_state: str
    executable_path: str
    executable_version: str
    executable_size_bytes: int
    executable_mtime_ns: int
    executable_sha256: str

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "policy_fingerprint": self.policy_fingerprint,
            "host_platform": self.host_platform,
            "host_architecture": self.host_architecture,
            "process_bitness": self.process_bitness,
            "windows_build": self.windows_build,
            "host_boot_epoch_seconds": self.host_boot_epoch_seconds,
            "feature_state": self.feature_state,
            "executable": {
                "path": self.executable_path,
                "version": self.executable_version,
                "size_bytes": self.executable_size_bytes,
                "mtime_ns": self.executable_mtime_ns,
                "sha256": self.executable_sha256,
            },
        }


@dataclass
class _LeaseState:
    state: str
    host_identity: _HostIdentity | None
    runtime_bundle: DeveloperTaskPythonRuntimeBundle | None = field(repr=False)
    issued_at_ns: int
    expires_at_ns: int
    secret: bytes = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    issuer_id: object = field(repr=False)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class _RuntimeLeaseServices:
    def inspect_host(self) -> DeveloperTaskExecutionBackendHostReport:
        return inspect_developer_task_execution_backend_host()

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def token_bytes(self, size: int) -> bytes:
        return secrets.token_bytes(size)


_SERVICES = _RuntimeLeaseServices()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _host_identity(report: DeveloperTaskExecutionBackendHostReport) -> _HostIdentity:
    executable = report.executable
    if executable is None:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_host_executable_missing",
            "Windows Sandbox executable evidence is missing.",
        )
    return _HostIdentity(
        backend_id=report.backend_id,
        policy_fingerprint=report.policy_fingerprint,
        host_platform=report.host_platform,
        host_architecture=report.host_architecture,
        process_bitness=report.process_bitness,
        windows_build=report.windows_build,
        host_boot_epoch_seconds=report.host_boot_epoch_seconds,
        feature_state=report.feature_state,
        executable_path=executable.path,
        executable_version=executable.version,
        executable_size_bytes=executable.size_bytes,
        executable_mtime_ns=executable.mtime_ns,
        executable_sha256=executable.sha256,
    )


def _host_identity_differences(expected: _HostIdentity, actual: _HostIdentity) -> tuple[str, ...]:
    differences: list[str] = []
    if abs(expected.host_boot_epoch_seconds - actual.host_boot_epoch_seconds) > RUNTIME_LEASE_HOST_BOOT_EPOCH_TOLERANCE_SECONDS:
        differences.append(
            "host_boot_epoch_seconds:"
            f"{expected.host_boot_epoch_seconds}->{actual.host_boot_epoch_seconds}"
        )
    exact_fields = (
        "backend_id",
        "policy_fingerprint",
        "host_platform",
        "host_architecture",
        "process_bitness",
        "windows_build",
        "feature_state",
        "executable_path",
        "executable_version",
        "executable_size_bytes",
        "executable_mtime_ns",
        "executable_sha256",
    )
    for name in exact_fields:
        expected_value = getattr(expected, name)
        actual_value = getattr(actual, name)
        if expected_value != actual_value:
            differences.append(f"{name}:{expected_value!r}->{actual_value!r}")
    return tuple(differences)


def _validate_typed_host_report(report: DeveloperTaskExecutionBackendHostReport) -> _HostIdentity:
    if type(report) is not DeveloperTaskExecutionBackendHostReport:
        raise TypeError("host_report must be DeveloperTaskExecutionBackendHostReport")
    if not report.ok:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_host_report_failed",
            "Successful V1B1 host evidence is required before lease issuance.",
            actual=",".join(report.issue_codes),
        )
    if (
        report.policy != WINDOWS_SANDBOX_EXECUTION_POLICY_V1
        or report.policy_fingerprint != WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint
    ):
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_host_report_invalid",
            "Host report does not match the canonical Windows Sandbox backend policy.",
        )
    if report.running_sandbox_processes:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_sandbox_process_running",
            "A Windows Sandbox process is already running.",
            actual=",".join(report.running_sandbox_processes),
        )
    return _host_identity(report)


def _runtime_bundle_differences(bundle: DeveloperTaskPythonRuntimeBundle) -> tuple[str, ...]:
    if type(bundle) is not DeveloperTaskPythonRuntimeBundle:
        return ("runtime_bundle_type",)
    if type(bundle.report) is not DeveloperTaskPythonRuntimeBundleReport:
        return ("runtime_bundle_report_type",)
    if not bundle.ok:
        return ("runtime_bundle_self_check",)
    report = bundle.report
    expected = {
        "bundle_id": RUNTIME_BUNDLE_ID,
        "source_id": RUNTIME_SOURCE_ID,
        "source_version": RUNTIME_SOURCE_VERSION,
        "source_architecture": RUNTIME_SOURCE_ARCHITECTURE,
        "source_sha256": RUNTIME_SOURCE_SHA256,
        "source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
        "source_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
        "bundle_policy_fingerprint": RUNTIME_BUNDLE_POLICY_FINGERPRINT,
        "source_outer_manifest_sha256": RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
        "source_stdlib_manifest_sha256": RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
        "bundle_file_count": RUNTIME_BUNDLE_FILE_COUNT,
        "bundle_total_bytes": RUNTIME_BUNDLE_TOTAL_BYTES,
        "tree_manifest_sha256": RUNTIME_TREE_MANIFEST_SHA256,
        "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
        "python_executable_sha256": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
        "python_dll_sha256": RUNTIME_SOURCE_PYTHON_DLL_SHA256,
        "python_pth_sha256": RUNTIME_LOCKED_PTH_SHA256,
        "stdlib_sha256": RUNTIME_SOURCE_STDLIB_SHA256,
        "runtime_probe_sha256": RUNTIME_PROBE_SHA256,
        "runtime_runner_sha256": RUNTIME_RUNNER_SHA256,
        "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
        "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
    }
    differences: list[str] = []
    for name, expected_value in expected.items():
        actual_value = getattr(report, name)
        if actual_value != expected_value:
            differences.append(f"{name}:{actual_value!r}")
    exact_file_hashes = {
        "python.exe": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
        "python313.dll": RUNTIME_SOURCE_PYTHON_DLL_SHA256,
        "python313.zip": RUNTIME_SOURCE_STDLIB_SHA256,
        RUNTIME_LOCKED_PTH_FILE_NAME: RUNTIME_LOCKED_PTH_SHA256,
        RUNTIME_PROBE_FILE_NAME: RUNTIME_PROBE_SHA256,
        RUNTIME_RUNNER_FILE_NAME: RUNTIME_RUNNER_SHA256,
        RUNTIME_MANIFEST_FILE_NAME: RUNTIME_MANIFEST_SHA256,
    }
    try:
        for path, expected_sha256 in exact_file_hashes.items():
            if _sha256(bundle.exact_file_bytes(path)) != expected_sha256:
                differences.append(f"file_sha256:{path}")
    except (KeyError, TypeError, ValueError):
        differences.append("runtime_bundle_exact_file_access")
    return tuple(differences)


def _validate_runtime_bundle(bundle: DeveloperTaskPythonRuntimeBundle) -> None:
    if type(bundle) is not DeveloperTaskPythonRuntimeBundle:
        raise TypeError("runtime_bundle must be DeveloperTaskPythonRuntimeBundle")
    differences = _runtime_bundle_differences(bundle)
    if differences:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_runtime_bundle_invalid",
            "Trusted runtime bundle does not match the canonical V1B4B capability.",
            actual=";".join(differences),
        )


def _binding_fingerprint(host_identity: _HostIdentity) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "lease_policy_fingerprint": RUNTIME_LEASE_POLICY_FINGERPRINT,
                "host": host_identity.canonical_dict(),
                "runtime": {
                    "source_sha256": RUNTIME_SOURCE_SHA256,
                    "source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
                    "source_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
                    "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
                    "tree_manifest_sha256": RUNTIME_TREE_MANIFEST_SHA256,
                    "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
                    "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
                },
                "attestation": {
                    "policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
                    "payload_fingerprint": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
                },
            }
        )
    )


def _claim_guard(secret: bytes, binding_fingerprint: str) -> bytes:
    return hmac.new(
        _ISSUER_SECRET,
        secret + binding_fingerprint.encode("ascii"),
        hashlib.sha256,
    ).digest()


def _invalidate_state(state: _LeaseState, terminal_state: str) -> None:
    state.state = terminal_state
    state.host_identity = None
    state.runtime_bundle = None
    state.issued_at_ns = 0
    state.expires_at_ns = 0
    state.secret = b""
    state.binding_fingerprint = ""
    state.issuer_id = object()


class DeveloperTaskExecutionRuntimeLease:
    __slots__ = ("_guard", "__weakref__")

    def __init__(self, constructor_key: object, guard: bytes) -> None:
        if constructor_key is not _CONSTRUCTOR_KEY:
            raise TypeError("DeveloperTaskExecutionRuntimeLease cannot be constructed directly")
        if not isinstance(guard, bytes) or len(guard) != hashlib.sha256().digest_size:
            raise TypeError("invalid lease guard")
        self._guard = guard

    @property
    def execution_authorized(self) -> bool:
        return False

    def status(self) -> DeveloperTaskExecutionRuntimeLeaseStatus:
        return _runtime_lease_status(self)

    def claim(self) -> DeveloperTaskPythonRuntimeBundle:
        return _claim_developer_task_execution_runtime_lease(self)

    def __repr__(self) -> str:
        status = self.status()
        return (
            "DeveloperTaskExecutionRuntimeLease("
            f"state={status.state!r}, policy_id={status.policy_id!r}, "
            "execution_authorized=False)"
        )

    def __copy__(self):
        raise TypeError("DeveloperTaskExecutionRuntimeLease is non-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("DeveloperTaskExecutionRuntimeLease is non-copyable")

    def __reduce__(self):
        raise TypeError("DeveloperTaskExecutionRuntimeLease is non-serializable")

    def __reduce_ex__(self, protocol):
        raise TypeError("DeveloperTaskExecutionRuntimeLease is non-serializable")

    def __getstate__(self):
        raise TypeError("DeveloperTaskExecutionRuntimeLease is non-serializable")


def _runtime_lease_status(lease: DeveloperTaskExecutionRuntimeLease) -> DeveloperTaskExecutionRuntimeLeaseStatus:
    if type(lease) is not DeveloperTaskExecutionRuntimeLease:
        raise TypeError("lease must be DeveloperTaskExecutionRuntimeLease")
    with _REGISTRY_LOCK:
        state = _REGISTRY.get(lease)
    if state is None:
        return DeveloperTaskExecutionRuntimeLeaseStatus(state=LEASE_STATE_INVALIDATED)
    with state.lock:
        if state.state == LEASE_STATE_ISSUED:
            now_ns = _SERVICES.monotonic_ns()
            if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
                _invalidate_state(state, LEASE_STATE_INVALIDATED)
            elif now_ns >= state.expires_at_ns:
                _invalidate_state(state, LEASE_STATE_EXPIRED)
        return DeveloperTaskExecutionRuntimeLeaseStatus(state=state.state)


def issue_developer_task_execution_runtime_lease(
    host_report: DeveloperTaskExecutionBackendHostReport,
    runtime_bundle: DeveloperTaskPythonRuntimeBundle,
) -> DeveloperTaskExecutionRuntimeLease:
    """Issue one short-lived process-local capability without launching Sandbox or Python."""

    if type(host_report) is not DeveloperTaskExecutionBackendHostReport:
        raise TypeError("host_report must be DeveloperTaskExecutionBackendHostReport")
    if type(runtime_bundle) is not DeveloperTaskPythonRuntimeBundle:
        raise TypeError("runtime_bundle must be DeveloperTaskPythonRuntimeBundle")

    policy_errors = validate_execution_runtime_lease_policy(
        TRUSTED_PYTHON_RUNTIME_LEASE_POLICY_V1
    )
    if policy_errors:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_policy_invalid",
            "Canonical V1B4D runtime lease policy is invalid.",
            actual=",".join(policy_errors),
        )

    expected_host = _validate_typed_host_report(host_report)
    _validate_runtime_bundle(runtime_bundle)

    fresh_report = _SERVICES.inspect_host()
    if type(fresh_report) is not DeveloperTaskExecutionBackendHostReport:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_fresh_host_report_invalid",
            "Fresh host inspection returned an invalid report type.",
        )
    try:
        fresh_host = _validate_typed_host_report(fresh_report)
    except (DeveloperTaskExecutionRuntimeLeaseError, TypeError) as exc:
        actual = exc.actual if isinstance(exc, DeveloperTaskExecutionRuntimeLeaseError) else type(exc).__name__
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_fresh_host_report_failed",
            "Fresh host inspection failed before lease issuance.",
            actual=actual,
        ) from exc

    differences = _host_identity_differences(expected_host, fresh_host)
    if differences:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_host_evidence_changed",
            "Host capability evidence changed before lease issuance.",
            actual=";".join(differences),
        )

    issued_at_ns = _SERVICES.monotonic_ns()
    if not isinstance(issued_at_ns, int) or isinstance(issued_at_ns, bool) or issued_at_ns < 0:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_clock_invalid",
            "Monotonic lease clock returned an invalid value.",
        )
    try:
        secret = _SERVICES.token_bytes(RUNTIME_LEASE_SECRET_BYTES)
    except Exception as exc:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_secret_generation_failed",
            "Lease secret generation failed.",
            actual=type(exc).__name__,
        ) from exc
    if type(secret) is not bytes or len(secret) != RUNTIME_LEASE_SECRET_BYTES:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_secret_generation_failed",
            "Lease secret generator returned invalid bytes.",
        )

    binding_fingerprint = _binding_fingerprint(fresh_host)
    guard = _claim_guard(secret, binding_fingerprint)
    lease = DeveloperTaskExecutionRuntimeLease(_CONSTRUCTOR_KEY, guard)
    state = _LeaseState(
        state=LEASE_STATE_ISSUED,
        host_identity=fresh_host,
        runtime_bundle=runtime_bundle,
        issued_at_ns=issued_at_ns,
        expires_at_ns=issued_at_ns + RUNTIME_LEASE_TTL_SECONDS * 1_000_000_000,
        secret=secret,
        binding_fingerprint=binding_fingerprint,
        issuer_id=_ISSUER_ID,
    )
    with _REGISTRY_LOCK:
        _REGISTRY[lease] = state
    return lease


def _claim_developer_task_execution_runtime_lease(
    lease: DeveloperTaskExecutionRuntimeLease,
) -> DeveloperTaskPythonRuntimeBundle:
    if type(lease) is not DeveloperTaskExecutionRuntimeLease:
        raise TypeError("lease must be DeveloperTaskExecutionRuntimeLease")
    with _REGISTRY_LOCK:
        state = _REGISTRY.get(lease)
    if state is None:
        raise DeveloperTaskExecutionRuntimeLeaseError(
            "runtime_lease_unregistered",
            "Runtime lease is not registered in this process issuer.",
        )

    with state.lock:
        if state.state == LEASE_STATE_CLAIMED:
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_already_claimed",
                "Runtime lease has already been claimed.",
            )
        if state.state == LEASE_STATE_EXPIRED:
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_expired",
                "Runtime lease has expired.",
            )
        if state.state != LEASE_STATE_ISSUED:
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_invalidated",
                "Runtime lease is permanently invalidated.",
            )

        now_ns = _SERVICES.monotonic_ns()
        if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_clock_invalid",
                "Monotonic lease clock returned an invalid value.",
            )
        if now_ns >= state.expires_at_ns:
            _invalidate_state(state, LEASE_STATE_EXPIRED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_expired",
                "Runtime lease has expired.",
            )

        fresh_report = _SERVICES.inspect_host()
        if type(fresh_report) is not DeveloperTaskExecutionBackendHostReport:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_fresh_host_report_invalid",
                "Fresh host inspection returned an invalid report type during claim.",
            )
        try:
            fresh_host = _validate_typed_host_report(fresh_report)
        except (DeveloperTaskExecutionRuntimeLeaseError, TypeError) as exc:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            actual = exc.actual if isinstance(exc, DeveloperTaskExecutionRuntimeLeaseError) else type(exc).__name__
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_claim_host_failed",
                "Fresh host inspection failed during runtime lease claim.",
                actual=actual,
            ) from exc

        bound_host = state.host_identity
        if bound_host is None:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_binding_invalid",
                "Runtime lease host binding is missing.",
            )
        differences = _host_identity_differences(bound_host, fresh_host)
        if differences:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_host_evidence_changed",
                "Host capability evidence changed before runtime lease claim.",
                actual=";".join(differences),
            )

        bundle = state.runtime_bundle
        if bundle is None:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_runtime_bundle_missing",
                "Runtime lease no longer retains the trusted runtime capability.",
            )
        differences = _runtime_bundle_differences(bundle)
        if differences:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_runtime_bundle_invalid",
                "Retained runtime capability changed before lease claim.",
                actual=";".join(differences),
            )

        if (
            state.issuer_id is not _ISSUER_ID
            or len(state.secret) != RUNTIME_LEASE_SECRET_BYTES
            or len(state.binding_fingerprint) != 64
            or not hmac.compare_digest(
                lease._guard,
                _claim_guard(state.secret, state.binding_fingerprint),
            )
        ):
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_issuer_binding_invalid",
                "Runtime lease issuer/secret binding is invalid.",
            )
        # The fingerprint binds the immutable issuance snapshot. Fresh host
        # evidence is validated separately above with the policy's one-second
        # boot-epoch quantization tolerance. Re-fingerprinting fresh_host here
        # would turn an explicitly accepted one-second measurement jitter into
        # a false binding failure.
        if state.binding_fingerprint != _binding_fingerprint(bound_host):
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_binding_invalid",
                "Runtime lease canonical issuance binding changed.",
            )
        policy_errors = validate_execution_runtime_lease_policy(
            TRUSTED_PYTHON_RUNTIME_LEASE_POLICY_V1
        )
        if policy_errors:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_policy_invalid",
                "Canonical V1B4D policy changed before lease claim.",
                actual=",".join(policy_errors),
            )

        final_now_ns = _SERVICES.monotonic_ns()
        if not isinstance(final_now_ns, int) or isinstance(final_now_ns, bool) or final_now_ns < 0:
            _invalidate_state(state, LEASE_STATE_INVALIDATED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_clock_invalid",
                "Monotonic lease clock returned an invalid value.",
            )
        if final_now_ns >= state.expires_at_ns:
            _invalidate_state(state, LEASE_STATE_EXPIRED)
            raise DeveloperTaskExecutionRuntimeLeaseError(
                "runtime_lease_expired",
                "Runtime lease expired during atomic claim validation.",
            )

        retained_bundle = bundle
        _invalidate_state(state, LEASE_STATE_CLAIMED)
        return retained_bundle
