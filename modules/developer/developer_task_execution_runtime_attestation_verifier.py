from __future__ import annotations

"""Pure host-side pinning and signed transcript verification for V1B4C2A."""

import base64
import hashlib

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from modules.developer.developer_task_execution_boundary_crypto import (
    DeveloperTaskExecutionBoundaryCryptoError,
    validate_ecdsa_p256_public_blob,
    validate_ecdsa_p256_signature,
    verify_ecdsa_p256_sha256_cng,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
    DeveloperTaskRuntimeAttestationPayloadBundle,
    build_developer_task_execution_runtime_attestation_payload,
)
from modules.developer.developer_task_execution_runtime_attestation_contract import (
    DeveloperTaskRuntimeAttestationContractError,
    DeveloperTaskRuntimeAttestationDocument,
    parse_runtime_attestation_authorize,
    parse_runtime_attestation_ready,
    parse_runtime_attestation_request,
    parse_runtime_attestation_result,
    parse_runtime_attestation_terminal,
    validate_runtime_attestation_signature_bytes,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS,
    TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1,
    validate_trusted_python_runtime_attestation_policy,
)


RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_PINNED = "runtime_attestation_transcript_pinned"
RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_VERIFIED = "runtime_attestation_transcript_verified"
RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_FAILED = "failed"

_PIN_CAPABILITY = object()


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationVerificationIssue:
    code: str
    check: str
    message: str
    expected: str = ""
    actual: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "check": self.check,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationTranscriptExpectation:
    backend_id: str
    backend_policy_fingerprint: str
    runtime_attestation_id: str
    runtime_attestation_policy_fingerprint: str
    payload_bundle_fingerprint: str
    request_id: str
    host_nonce: str = field(repr=False)
    authorization_nonce: str = field(repr=False)
    authorization_deadline_epoch: int
    authorization_observed_epoch: int
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    public_key_sha256: str
    policy_sha256: str
    bootstrap_sha256: str
    controller_sha256: str
    native_helper_sha256: str
    wsb_sha256: str
    runtime_source_sha256: str
    runtime_source_fingerprint: str
    runtime_source_provenance_policy_fingerprint: str
    runtime_bundle_policy_fingerprint: str
    runtime_tree_manifest_sha256: str
    runtime_manifest_sha256: str
    runtime_bundle_fingerprint: str
    runtime_file_count: int
    runtime_total_bytes: int
    python_executable_sha256: str
    python_dll_sha256: str
    python_pth_sha256: str
    stdlib_sha256: str
    runtime_probe_sha256: str
    runtime_runner_sha256: str
    launch_contract_fingerprint: str
    public_key_blob: bytes = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "backend_policy_fingerprint": self.backend_policy_fingerprint,
            "runtime_attestation_id": self.runtime_attestation_id,
            "runtime_attestation_policy_fingerprint": self.runtime_attestation_policy_fingerprint,
            "payload_bundle_fingerprint": self.payload_bundle_fingerprint,
            "request_id": self.request_id,
            "authorization_deadline_epoch": self.authorization_deadline_epoch,
            "authorization_observed_epoch": self.authorization_observed_epoch,
            "request_sha256": self.request_sha256,
            "ready_sha256": self.ready_sha256,
            "authorize_sha256": self.authorize_sha256,
            "public_key_sha256": self.public_key_sha256,
            "policy_sha256": self.policy_sha256,
            "bootstrap_sha256": self.bootstrap_sha256,
            "controller_sha256": self.controller_sha256,
            "native_helper_sha256": self.native_helper_sha256,
            "wsb_sha256": self.wsb_sha256,
            "runtime_source_sha256": self.runtime_source_sha256,
            "runtime_source_fingerprint": self.runtime_source_fingerprint,
            "runtime_source_provenance_policy_fingerprint": self.runtime_source_provenance_policy_fingerprint,
            "runtime_bundle_policy_fingerprint": self.runtime_bundle_policy_fingerprint,
            "runtime_tree_manifest_sha256": self.runtime_tree_manifest_sha256,
            "runtime_manifest_sha256": self.runtime_manifest_sha256,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "runtime_file_count": self.runtime_file_count,
            "runtime_total_bytes": self.runtime_total_bytes,
            "python_executable_sha256": self.python_executable_sha256,
            "python_dll_sha256": self.python_dll_sha256,
            "python_pth_sha256": self.python_pth_sha256,
            "stdlib_sha256": self.stdlib_sha256,
            "runtime_probe_sha256": self.runtime_probe_sha256,
            "runtime_runner_sha256": self.runtime_runner_sha256,
            "launch_contract_fingerprint": self.launch_contract_fingerprint,
        }


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationTranscriptPinReport:
    status: str
    expectation: DeveloperTaskRuntimeAttestationTranscriptExpectation | None
    request: DeveloperTaskRuntimeAttestationDocument | None = field(repr=False)
    ready: DeveloperTaskRuntimeAttestationDocument | None = field(repr=False)
    authorize: DeveloperTaskRuntimeAttestationDocument | None = field(repr=False)
    issues: tuple[DeveloperTaskRuntimeAttestationVerificationIssue, ...]
    _pin_capability: object | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def ok(self) -> bool:
        return (
            self._pin_capability is _PIN_CAPABILITY
            and self.status == RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_PINNED
            and self.expectation is not None
            and self.request is not None
            and self.ready is not None
            and self.authorize is not None
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "runtime_attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
            "payload_bundle_fingerprint": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
            "expectation": self.expectation.to_dict() if self.expectation is not None else None,
            "request_sha256": self.request.sha256 if self.request is not None else "",
            "ready_sha256": self.ready.sha256 if self.ready is not None else "",
            "authorize_sha256": self.authorize.sha256 if self.authorize is not None else "",
            "execution_authorized": False,
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_codes": list(self.issue_codes),
        }


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationTranscriptReport:
    status: str
    expectation: DeveloperTaskRuntimeAttestationTranscriptExpectation | None
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    runtime_result_sha256: str
    terminal_payload_sha256: str
    terminal_signature_sha256: str
    public_key_sha256: str
    signature_valid: bool
    runtime_result_verified: bool
    terminal_verified: bool
    issues: tuple[DeveloperTaskRuntimeAttestationVerificationIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            self.status == RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_VERIFIED
            and self.expectation is not None
            and len(self.request_sha256) == 64
            and len(self.ready_sha256) == 64
            and len(self.authorize_sha256) == 64
            and len(self.runtime_result_sha256) == 64
            and len(self.terminal_payload_sha256) == 64
            and len(self.terminal_signature_sha256) == 64
            and self.public_key_sha256 == self.expectation.public_key_sha256
            and self.signature_valid
            and self.runtime_result_verified
            and self.terminal_verified
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "runtime_attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
            "payload_bundle_fingerprint": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
            "expectation": self.expectation.to_dict() if self.expectation is not None else None,
            "hashes": {
                "request_sha256": self.request_sha256,
                "ready_sha256": self.ready_sha256,
                "authorize_sha256": self.authorize_sha256,
                "runtime_result_sha256": self.runtime_result_sha256,
                "terminal_payload_sha256": self.terminal_payload_sha256,
                "terminal_signature_sha256": self.terminal_signature_sha256,
                "public_key_sha256": self.public_key_sha256,
            },
            "signature_valid": self.signature_valid,
            "runtime_result_verified": self.runtime_result_verified,
            "terminal_verified": self.terminal_verified,
            "execution_authorized": False,
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_codes": list(self.issue_codes),
        }


def _sha256(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("runtime-attestation transcript artifacts must be bytes")
    return hashlib.sha256(data).hexdigest()


def _add_issue(
    issues: list[DeveloperTaskRuntimeAttestationVerificationIssue],
    code: str,
    check: str,
    message: str,
    *,
    expected: str = "",
    actual: str = "",
) -> None:
    issues.append(
        DeveloperTaskRuntimeAttestationVerificationIssue(
            code=code,
            check=check,
            message=message,
            expected=expected,
            actual=actual,
        )
    )


def _require_equal(
    issues: list[DeveloperTaskRuntimeAttestationVerificationIssue],
    *,
    check: str,
    expected: Any,
    actual: Any,
    code: str = "runtime_attestation_transcript_mismatch",
) -> None:
    if actual != expected:
        _add_issue(
            issues,
            code,
            check,
            "Runtime-attestation transcript value does not match pinned evidence.",
            expected=repr(expected),
            actual=repr(actual),
        )


def _parse_timestamp_epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _contract_issue(
    issues: list[DeveloperTaskRuntimeAttestationVerificationIssue],
    check: str,
    exc: DeveloperTaskRuntimeAttestationContractError,
) -> None:
    _add_issue(
        issues,
        exc.code,
        check,
        str(exc),
        actual=exc.actual or exc.field_name,
    )


def _crypto_issue(
    issues: list[DeveloperTaskRuntimeAttestationVerificationIssue],
    check: str,
    exc: DeveloperTaskExecutionBoundaryCryptoError,
) -> None:
    _add_issue(issues, exc.code, check, str(exc), actual=exc.actual)


def _canonical_payload() -> DeveloperTaskRuntimeAttestationPayloadBundle:
    validate_trusted_python_runtime_attestation_policy()
    payload = build_developer_task_execution_runtime_attestation_payload()
    if not TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1.ok or not payload.ok:
        raise RuntimeError("Trusted V1B4C1 runtime-attestation payload is invalid.")
    if payload.payload_fingerprint != RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT:
        raise RuntimeError("Trusted V1B4C1 runtime-attestation payload fingerprint drifted.")
    return payload


def _payload_artifact_hashes(
    payload: DeveloperTaskRuntimeAttestationPayloadBundle,
    wsb_bytes: bytes,
) -> dict[str, str]:
    return {
        "policy_sha256": payload.policy.sha256,
        "bootstrap_sha256": payload.bootstrap.sha256,
        "controller_sha256": payload.controller.sha256,
        "native_helper_sha256": payload.native_helper.sha256,
        "wsb_sha256": _sha256(wsb_bytes),
    }


def _runtime_identity(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "runtime_source_sha256",
        "runtime_source_fingerprint",
        "runtime_source_provenance_policy_fingerprint",
        "runtime_bundle_policy_fingerprint",
        "runtime_tree_manifest_sha256",
        "runtime_manifest_sha256",
        "runtime_bundle_fingerprint",
        "runtime_file_count",
        "runtime_total_bytes",
        "python_executable_sha256",
        "python_dll_sha256",
        "python_pth_sha256",
        "stdlib_sha256",
        "runtime_probe_sha256",
        "runtime_runner_sha256",
        "launch_contract_fingerprint",
    )
    return {key: payload[key] for key in keys}


def _make_pin_report(
    *,
    status: str,
    expectation: DeveloperTaskRuntimeAttestationTranscriptExpectation | None,
    request: DeveloperTaskRuntimeAttestationDocument | None,
    ready: DeveloperTaskRuntimeAttestationDocument | None,
    authorize: DeveloperTaskRuntimeAttestationDocument | None,
    issues: list[DeveloperTaskRuntimeAttestationVerificationIssue],
    trusted: bool,
) -> DeveloperTaskRuntimeAttestationTranscriptPinReport:
    report = DeveloperTaskRuntimeAttestationTranscriptPinReport(
        status=status,
        expectation=expectation,
        request=request,
        ready=ready,
        authorize=authorize,
        issues=tuple(issues),
    )
    if trusted:
        object.__setattr__(report, "_pin_capability", _PIN_CAPABILITY)
    return report


def pin_developer_task_execution_runtime_attestation_transcript(
    *,
    expected_request_id: str,
    expected_host_nonce: str,
    expected_authorization_nonce: str,
    expected_request_sha256: str,
    authorization_observed_epoch: int,
    wsb_bytes: bytes,
    request_bytes: bytes,
    ready_bytes: bytes,
    authorize_bytes: bytes,
) -> DeveloperTaskRuntimeAttestationTranscriptPinReport:
    if type(authorization_observed_epoch) is not int or authorization_observed_epoch <= 0:
        raise TypeError("authorization_observed_epoch must be a positive integer")
    trusted_payload = _canonical_payload()
    artifact_hashes = _payload_artifact_hashes(trusted_payload, wsb_bytes)
    issues: list[DeveloperTaskRuntimeAttestationVerificationIssue] = []
    request: DeveloperTaskRuntimeAttestationDocument | None = None
    ready: DeveloperTaskRuntimeAttestationDocument | None = None
    authorize: DeveloperTaskRuntimeAttestationDocument | None = None

    try:
        request = parse_runtime_attestation_request(request_bytes)
    except DeveloperTaskRuntimeAttestationContractError as exc:
        _contract_issue(issues, "request", exc)
    try:
        ready = parse_runtime_attestation_ready(ready_bytes)
    except DeveloperTaskRuntimeAttestationContractError as exc:
        _contract_issue(issues, "ready", exc)
    try:
        authorize = parse_runtime_attestation_authorize(authorize_bytes)
    except DeveloperTaskRuntimeAttestationContractError as exc:
        _contract_issue(issues, "authorize", exc)

    expectation: DeveloperTaskRuntimeAttestationTranscriptExpectation | None = None
    if request is not None and ready is not None and authorize is not None and not issues:
        request_payload = request.to_dict()
        ready_payload = ready.to_dict()
        authorize_payload = authorize.to_dict()

        for key, expected in (
            ("request_id", expected_request_id),
            ("host_nonce", expected_host_nonce),
        ):
            _require_equal(
                issues,
                check=f"request.{key}",
                expected=expected,
                actual=request_payload[key],
                code="runtime_attestation_request_replay_or_substitution",
            )
        _require_equal(
            issues,
            check="request.sha256",
            expected=expected_request_sha256,
            actual=request.sha256,
            code="runtime_attestation_request_replay_or_substitution",
        )
        for key, expected_hash in artifact_hashes.items():
            _require_equal(
                issues,
                check=f"request.{key}",
                expected=expected_hash,
                actual=request_payload[key],
                code="runtime_attestation_payload_hash_mismatch",
            )

        for key in (
            "backend_id",
            "backend_policy_fingerprint",
            "runtime_attestation_id",
            "runtime_attestation_policy_fingerprint",
            "request_id",
            "host_nonce",
            "policy_sha256",
            "bootstrap_sha256",
            "controller_sha256",
            "native_helper_sha256",
            "wsb_sha256",
        ):
            _require_equal(
                issues,
                check=f"ready.{key}",
                expected=request_payload[key],
                actual=ready_payload[key],
            )
        for key, expected_value in _runtime_identity(request_payload).items():
            _require_equal(
                issues,
                check=f"ready.{key}",
                expected=expected_value,
                actual=ready_payload[key],
            )
        _require_equal(
            issues,
            check="ready.request_sha256",
            expected=request.sha256,
            actual=ready_payload["request_sha256"],
        )

        try:
            public_key_blob = base64.b64decode(ready_payload["public_key_blob_base64"], validate=True)
            validate_ecdsa_p256_public_blob(public_key_blob)
        except DeveloperTaskExecutionBoundaryCryptoError as exc:
            _crypto_issue(issues, "ready.public_key_blob_base64", exc)
            public_key_blob = b""

        for key, expected in (
            ("request_id", expected_request_id),
            ("host_nonce", expected_host_nonce),
            ("request_sha256", request.sha256),
            ("ready_sha256", ready.sha256),
            ("public_key_sha256", ready_payload["public_key_sha256"]),
            ("runtime_bundle_fingerprint", request_payload["runtime_bundle_fingerprint"]),
            ("launch_contract_fingerprint", request_payload["launch_contract_fingerprint"]),
            ("authorization_nonce", expected_authorization_nonce),
        ):
            _require_equal(
                issues,
                check=f"authorize.{key}",
                expected=expected,
                actual=authorize_payload[key],
                code=(
                    "runtime_attestation_authorization_nonce_mismatch"
                    if key == "authorization_nonce"
                    else "runtime_attestation_transcript_mismatch"
                ),
            )

        request_epoch = _parse_timestamp_epoch(request_payload["created_at_utc"])
        ready_epoch = _parse_timestamp_epoch(ready_payload["created_at_utc"])
        maximum_ready_epoch = request_epoch + RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS + 1.0
        if ready_epoch <= request_epoch or ready_epoch > maximum_ready_epoch:
            _add_issue(
                issues,
                "runtime_attestation_ready_window_invalid",
                "ready.created_at_utc",
                "Ready evidence is outside the request-defined ready window.",
                expected=f">{request_epoch} and <={maximum_ready_epoch}",
                actual=str(ready_epoch),
            )

        deadline = authorize_payload["authorization_deadline_epoch"]
        maximum_deadline = ready_epoch + RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS + 1.0
        if deadline <= ready_epoch or deadline > maximum_deadline:
            _add_issue(
                issues,
                "runtime_attestation_authorization_window_invalid",
                "authorize.authorization_deadline_epoch",
                "Authorization deadline is outside the request-defined authorization window.",
                expected=f">{ready_epoch} and <={maximum_deadline}",
                actual=str(deadline),
            )
        if authorization_observed_epoch < ready_epoch:
            _add_issue(
                issues,
                "runtime_attestation_authorization_temporal_inversion",
                "authorization_observed_epoch",
                "Authorization host timing evidence predates ready evidence.",
                expected=f">={ready_epoch}",
                actual=str(authorization_observed_epoch),
            )
        if authorization_observed_epoch > deadline:
            _add_issue(
                issues,
                "runtime_attestation_authorization_expired",
                "authorization_observed_epoch",
                "Authorization was observed after its deadline.",
                expected=f"<={deadline}",
                actual=str(authorization_observed_epoch),
            )

        if not issues:
            runtime_identity = _runtime_identity(request_payload)
            expectation = DeveloperTaskRuntimeAttestationTranscriptExpectation(
                backend_id=request_payload["backend_id"],
                backend_policy_fingerprint=request_payload["backend_policy_fingerprint"],
                runtime_attestation_id=request_payload["runtime_attestation_id"],
                runtime_attestation_policy_fingerprint=request_payload["runtime_attestation_policy_fingerprint"],
                payload_bundle_fingerprint=trusted_payload.payload_fingerprint,
                request_id=expected_request_id,
                host_nonce=expected_host_nonce,
                authorization_nonce=expected_authorization_nonce,
                authorization_deadline_epoch=deadline,
                authorization_observed_epoch=authorization_observed_epoch,
                request_sha256=request.sha256,
                ready_sha256=ready.sha256,
                authorize_sha256=authorize.sha256,
                public_key_sha256=ready_payload["public_key_sha256"],
                policy_sha256=artifact_hashes["policy_sha256"],
                bootstrap_sha256=artifact_hashes["bootstrap_sha256"],
                controller_sha256=artifact_hashes["controller_sha256"],
                native_helper_sha256=artifact_hashes["native_helper_sha256"],
                wsb_sha256=artifact_hashes["wsb_sha256"],
                runtime_source_sha256=runtime_identity["runtime_source_sha256"],
                runtime_source_fingerprint=runtime_identity["runtime_source_fingerprint"],
                runtime_source_provenance_policy_fingerprint=runtime_identity["runtime_source_provenance_policy_fingerprint"],
                runtime_bundle_policy_fingerprint=runtime_identity["runtime_bundle_policy_fingerprint"],
                runtime_tree_manifest_sha256=runtime_identity["runtime_tree_manifest_sha256"],
                runtime_manifest_sha256=runtime_identity["runtime_manifest_sha256"],
                runtime_bundle_fingerprint=runtime_identity["runtime_bundle_fingerprint"],
                runtime_file_count=runtime_identity["runtime_file_count"],
                runtime_total_bytes=runtime_identity["runtime_total_bytes"],
                python_executable_sha256=runtime_identity["python_executable_sha256"],
                python_dll_sha256=runtime_identity["python_dll_sha256"],
                python_pth_sha256=runtime_identity["python_pth_sha256"],
                stdlib_sha256=runtime_identity["stdlib_sha256"],
                runtime_probe_sha256=runtime_identity["runtime_probe_sha256"],
                runtime_runner_sha256=runtime_identity["runtime_runner_sha256"],
                launch_contract_fingerprint=runtime_identity["launch_contract_fingerprint"],
                public_key_blob=public_key_blob,
            )

    status = (
        RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_PINNED
        if expectation is not None and not issues
        else RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_FAILED
    )
    return _make_pin_report(
        status=status,
        expectation=expectation,
        request=request,
        ready=ready,
        authorize=authorize,
        issues=issues,
        trusted=expectation is not None and not issues,
    )


def verify_developer_task_execution_runtime_attestation_transcript(
    pin_report: DeveloperTaskRuntimeAttestationTranscriptPinReport,
    *,
    wsb_bytes: bytes,
    request_bytes: bytes,
    ready_bytes: bytes,
    authorize_bytes: bytes,
    runtime_result_bytes: bytes,
    terminal_payload_bytes: bytes,
    terminal_signature_bytes: bytes,
    signature_verifier: Callable[[bytes, bytes, bytes], bool] | None = None,
) -> DeveloperTaskRuntimeAttestationTranscriptReport:
    if not isinstance(pin_report, DeveloperTaskRuntimeAttestationTranscriptPinReport):
        raise TypeError("pin_report must be DeveloperTaskRuntimeAttestationTranscriptPinReport")

    trusted_payload = _canonical_payload()
    issues: list[DeveloperTaskRuntimeAttestationVerificationIssue] = []
    expectation = pin_report.expectation if pin_report.ok else None
    if expectation is None:
        _add_issue(
            issues,
            "runtime_attestation_pin_report_failed",
            "pin_report",
            "A genuine successful runtime-attestation pin report is required.",
            actual=repr(pin_report.issue_codes),
        )

    request_sha256 = _sha256(request_bytes)
    ready_sha256 = _sha256(ready_bytes)
    authorize_sha256 = _sha256(authorize_bytes)
    runtime_result_sha256 = _sha256(runtime_result_bytes)
    terminal_payload_sha256 = _sha256(terminal_payload_bytes)
    terminal_signature_sha256 = _sha256(terminal_signature_bytes)
    public_key_sha256 = expectation.public_key_sha256 if expectation is not None else ""
    runtime_result: DeveloperTaskRuntimeAttestationDocument | None = None
    terminal: DeveloperTaskRuntimeAttestationDocument | None = None
    signature_valid = False
    runtime_result_verified = False
    terminal_verified = False

    if expectation is not None:
        artifact_hashes = _payload_artifact_hashes(trusted_payload, wsb_bytes)
        pinned_hashes = {
            "payload_bundle": (expectation.payload_bundle_fingerprint, trusted_payload.payload_fingerprint),
            "policy": (expectation.policy_sha256, artifact_hashes["policy_sha256"]),
            "bootstrap": (expectation.bootstrap_sha256, artifact_hashes["bootstrap_sha256"]),
            "controller": (expectation.controller_sha256, artifact_hashes["controller_sha256"]),
            "native_helper": (expectation.native_helper_sha256, artifact_hashes["native_helper_sha256"]),
            "wsb": (expectation.wsb_sha256, artifact_hashes["wsb_sha256"]),
            "request": (expectation.request_sha256, request_sha256),
            "ready": (expectation.ready_sha256, ready_sha256),
            "authorize": (expectation.authorize_sha256, authorize_sha256),
        }
        for name, (expected, actual) in pinned_hashes.items():
            _require_equal(
                issues,
                check=f"pinned.{name}_sha256",
                expected=expected,
                actual=actual,
                code="runtime_attestation_pinned_artifact_changed",
            )

    parsed_request: DeveloperTaskRuntimeAttestationDocument | None = None
    parsed_ready: DeveloperTaskRuntimeAttestationDocument | None = None
    parsed_authorize: DeveloperTaskRuntimeAttestationDocument | None = None
    try:
        parsed_request = parse_runtime_attestation_request(request_bytes)
        parsed_ready = parse_runtime_attestation_ready(ready_bytes)
        parsed_authorize = parse_runtime_attestation_authorize(authorize_bytes)
    except DeveloperTaskRuntimeAttestationContractError as exc:
        _contract_issue(issues, "pinned_transcript_reparse", exc)
    try:
        runtime_result = parse_runtime_attestation_result(runtime_result_bytes)
    except DeveloperTaskRuntimeAttestationContractError as exc:
        _contract_issue(issues, "runtime_result", exc)
    try:
        terminal = parse_runtime_attestation_terminal(terminal_payload_bytes)
    except DeveloperTaskRuntimeAttestationContractError as exc:
        _contract_issue(issues, "terminal_payload", exc)
    try:
        validate_runtime_attestation_signature_bytes(terminal_signature_bytes)
        validate_ecdsa_p256_signature(terminal_signature_bytes)
    except DeveloperTaskRuntimeAttestationContractError as exc:
        _contract_issue(issues, "terminal_signature", exc)
    except DeveloperTaskExecutionBoundaryCryptoError as exc:
        _crypto_issue(issues, "terminal_signature", exc)

    if (
        expectation is not None
        and parsed_request is not None
        and parsed_ready is not None
        and parsed_authorize is not None
        and runtime_result is not None
        and terminal is not None
    ):
        request_payload = parsed_request.to_dict()
        ready_payload = parsed_ready.to_dict()
        authorize_payload = parsed_authorize.to_dict()
        runtime_payload = runtime_result.to_dict()
        terminal_payload = terminal.to_dict()

        expected_terminal = {
            "backend_id": expectation.backend_id,
            "backend_policy_fingerprint": expectation.backend_policy_fingerprint,
            "runtime_attestation_id": expectation.runtime_attestation_id,
            "runtime_attestation_policy_fingerprint": expectation.runtime_attestation_policy_fingerprint,
            "request_id": expectation.request_id,
            "host_nonce": expectation.host_nonce,
            "authorization_nonce": expectation.authorization_nonce,
            "request_sha256": expectation.request_sha256,
            "ready_sha256": expectation.ready_sha256,
            "authorize_sha256": expectation.authorize_sha256,
            "policy_sha256": expectation.policy_sha256,
            "bootstrap_sha256": expectation.bootstrap_sha256,
            "controller_sha256": expectation.controller_sha256,
            "native_helper_sha256": expectation.native_helper_sha256,
            "wsb_sha256": expectation.wsb_sha256,
            "runtime_result_sha256": runtime_result_sha256,
            "public_key_sha256": expectation.public_key_sha256,
            "runtime_bundle_fingerprint": expectation.runtime_bundle_fingerprint,
            "runtime_tree_manifest_sha256": expectation.runtime_tree_manifest_sha256,
            "runtime_manifest_sha256": expectation.runtime_manifest_sha256,
            "python_executable_sha256": expectation.python_executable_sha256,
            "python_pth_sha256": expectation.python_pth_sha256,
            "runtime_probe_sha256": expectation.runtime_probe_sha256,
            "runtime_runner_sha256": expectation.runtime_runner_sha256,
            "launch_contract_fingerprint": expectation.launch_contract_fingerprint,
        }
        for key, expected in expected_terminal.items():
            _require_equal(
                issues,
                check=f"terminal.{key}",
                expected=expected,
                actual=terminal_payload[key],
            )

        for key in ("request_id", "host_nonce"):
            _require_equal(
                issues,
                check=f"request.{key}.post_pin",
                expected=(expectation.request_id if key == "request_id" else expectation.host_nonce),
                actual=request_payload[key],
            )
        for key, expected in (
            ("request_sha256", expectation.request_sha256),
            ("public_key_sha256", expectation.public_key_sha256),
        ):
            _require_equal(
                issues,
                check=f"ready.{key}.post_pin",
                expected=expected,
                actual=ready_payload[key],
            )
        for key, expected in (
            ("authorization_nonce", expectation.authorization_nonce),
            ("request_sha256", expectation.request_sha256),
            ("ready_sha256", expectation.ready_sha256),
            ("public_key_sha256", expectation.public_key_sha256),
        ):
            _require_equal(
                issues,
                check=f"authorize.{key}.post_pin",
                expected=expected,
                actual=authorize_payload[key],
            )

        controller_pairs = {
            "sid": "controller_sid",
            "name": "controller_name",
            "is_system": "controller_is_system",
            "is_administrator": "controller_is_administrator",
            "integrity_rid": "controller_integrity_rid",
            "key_is_ephemeral": "key_is_ephemeral",
            "key_name_empty": "key_name_empty",
            "key_unique_name_empty": "key_unique_name_empty",
        }
        for terminal_key, ready_key in controller_pairs.items():
            _require_equal(
                issues,
                check=f"terminal.controller.{terminal_key}",
                expected=ready_payload[ready_key],
                actual=terminal_payload["controller"][terminal_key],
            )

        for key in ("input_write_blocked", "runtime_write_blocked", "control_write_blocked", "output_writable"):
            _require_equal(
                issues,
                check=f"terminal.controls.{key}",
                expected=ready_payload[key],
                actual=terminal_payload["controls"][key],
            )

        runtime_expected = {
            "result_ok": True,
            "probe_id": runtime_payload["probe_id"],
            "implementation": runtime_payload["implementation"],
            "version": runtime_payload["version_info"],
            "architecture_bits": runtime_payload["architecture_bits"],
            "machine": runtime_payload["machine"],
            "runtime_root_write_blocked": runtime_payload["runtime_root_write_blocked"],
            "environment_clean": not runtime_payload["python_environment_keys"],
            "pip_absent": not runtime_payload["pip_available"],
            "ensurepip_absent": not runtime_payload["ensurepip_available"],
            "site_absent": not runtime_payload["site_imported"],
            "sys_path_exact": True,
        }
        for key, expected in runtime_expected.items():
            _require_equal(
                issues,
                check=f"terminal.runtime.{key}",
                expected=expected,
                actual=terminal_payload["runtime"][key],
            )

        ready_epoch = _parse_timestamp_epoch(ready_payload["created_at_utc"])
        terminal_epoch = _parse_timestamp_epoch(terminal_payload["completed_at_utc"])
        if terminal_epoch <= ready_epoch or terminal_epoch <= expectation.authorization_observed_epoch:
            _add_issue(
                issues,
                "runtime_attestation_terminal_timing_invalid",
                "terminal.completed_at_utc",
                "Terminal evidence predates the pinned authorization phase.",
                expected=f">{max(ready_epoch, expectation.authorization_observed_epoch)}",
                actual=str(terminal_epoch),
            )
        maximum_terminal_epoch = (
            expectation.authorization_deadline_epoch
            + RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS
            + RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS
            + 1
        )
        if terminal_epoch > maximum_terminal_epoch:
            _add_issue(
                issues,
                "runtime_attestation_terminal_window_invalid",
                "terminal.completed_at_utc",
                "Terminal evidence is outside the bounded runtime/shutdown window.",
                expected=f"<={maximum_terminal_epoch}",
                actual=str(terminal_epoch),
            )

        runtime_result_verified = not any(
            issue.check.startswith("runtime_result") or issue.check.startswith("terminal.runtime")
            for issue in issues
        )
        terminal_verified = not any(
            issue.check.startswith("terminal")
            for issue in issues
        )

        if not issues:
            verifier = signature_verifier or verify_ecdsa_p256_sha256_cng
            try:
                result = verifier(
                    expectation.public_key_blob,
                    terminal_payload_bytes,
                    terminal_signature_bytes,
                )
                if type(result) is not bool:
                    _add_issue(
                        issues,
                        "runtime_attestation_signature_verifier_result_invalid",
                        "terminal_signature",
                        "Runtime-attestation signature verifier returned a non-boolean result.",
                        actual=type(result).__name__,
                    )
                else:
                    signature_valid = result
            except DeveloperTaskExecutionBoundaryCryptoError as exc:
                _crypto_issue(issues, "terminal_signature", exc)
            except Exception as exc:
                _add_issue(
                    issues,
                    "runtime_attestation_signature_verifier_failed",
                    "terminal_signature",
                    "Runtime-attestation signature verifier failed unexpectedly.",
                    actual=f"{type(exc).__name__}: {exc}",
                )
            if not signature_valid and not issues:
                _add_issue(
                    issues,
                    "runtime_attestation_signature_invalid",
                    "terminal_signature",
                    "ECDSA P-256 signature does not authenticate the terminal payload.",
                )

    if issues:
        runtime_result_verified = False
        terminal_verified = False

    status = (
        RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_VERIFIED
        if signature_valid and runtime_result_verified and terminal_verified and not issues
        else RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_FAILED
    )
    return DeveloperTaskRuntimeAttestationTranscriptReport(
        status=status,
        expectation=expectation,
        request_sha256=request_sha256,
        ready_sha256=ready_sha256,
        authorize_sha256=authorize_sha256,
        runtime_result_sha256=runtime_result_sha256,
        terminal_payload_sha256=terminal_payload_sha256,
        terminal_signature_sha256=terminal_signature_sha256,
        public_key_sha256=public_key_sha256,
        signature_valid=signature_valid,
        runtime_result_verified=runtime_result_verified,
        terminal_verified=terminal_verified,
        issues=tuple(issues),
    )
