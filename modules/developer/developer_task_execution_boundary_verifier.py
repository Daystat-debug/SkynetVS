from __future__ import annotations

"""Pure transcript pinning and final signature verification for V1B3B."""

import base64
import hashlib

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from modules.developer.developer_task_execution_boundary_contract import (
    DeveloperTaskExecutionBoundaryContractError,
    DeveloperTaskExecutionBoundaryDocument,
    parse_boundary_authorize,
    parse_boundary_ready,
    parse_boundary_request,
    parse_boundary_terminal_payload,
    parse_boundary_worker_result,
    validate_boundary_signature_bytes,
)
from modules.developer.developer_task_execution_boundary_crypto import (
    DeveloperTaskExecutionBoundaryCryptoError,
    verify_ecdsa_p256_sha256_cng,
)
from modules.developer.developer_task_execution_boundary_policy import (
    DeveloperTaskExecutionBoundaryPolicy,
    validate_execution_boundary_policy,
)


SIGNED_TRANSCRIPT_STATUS_PINNED = "transcript_pinned"
SIGNED_TRANSCRIPT_STATUS_VERIFIED = "signed_transcript_verified"
SIGNED_TRANSCRIPT_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class DeveloperTaskExecutionBoundaryIssue:
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
class DeveloperTaskExecutionSignedTranscriptExpectation:
    backend_id: str
    base_policy_fingerprint: str
    boundary_id: str
    boundary_fingerprint: str
    request_id: str
    host_nonce: str = field(repr=False)
    authorization_nonce: str = field(repr=False)
    authorization_deadline_epoch: int
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    public_key_sha256: str
    worker_source_sha256: str
    policy_sha256: str
    bootstrap_sha256: str
    controller_sha256: str
    wsb_sha256: str
    public_key_blob: bytes = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "base_policy_fingerprint": self.base_policy_fingerprint,
            "boundary_id": self.boundary_id,
            "boundary_fingerprint": self.boundary_fingerprint,
            "request_id": self.request_id,
            "authorization_deadline_epoch": self.authorization_deadline_epoch,
            "request_sha256": self.request_sha256,
            "ready_sha256": self.ready_sha256,
            "authorize_sha256": self.authorize_sha256,
            "public_key_sha256": self.public_key_sha256,
            "worker_source_sha256": self.worker_source_sha256,
            "policy_sha256": self.policy_sha256,
            "bootstrap_sha256": self.bootstrap_sha256,
            "controller_sha256": self.controller_sha256,
            "wsb_sha256": self.wsb_sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionSignedTranscriptPinReport:
    status: str
    policy: DeveloperTaskExecutionBoundaryPolicy
    expectation: DeveloperTaskExecutionSignedTranscriptExpectation | None
    request: DeveloperTaskExecutionBoundaryDocument | None
    ready: DeveloperTaskExecutionBoundaryDocument | None
    authorize: DeveloperTaskExecutionBoundaryDocument | None
    issues: tuple[DeveloperTaskExecutionBoundaryIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            self.status == SIGNED_TRANSCRIPT_STATUS_PINNED
            and self.policy.ok
            and self.expectation is not None
            and self.request is not None
            and self.ready is not None
            and self.authorize is not None
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "policy": self.policy.to_dict(),
            "policy_fingerprint": self.policy.fingerprint,
            "expectation": self.expectation.to_dict() if self.expectation is not None else None,
            "request_sha256": self.request.sha256 if self.request is not None else "",
            "ready_sha256": self.ready.sha256 if self.ready is not None else "",
            "authorize_sha256": self.authorize.sha256 if self.authorize is not None else "",
            "execution_authorized": False,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionSignedTranscriptReport:
    status: str
    policy: DeveloperTaskExecutionBoundaryPolicy
    expectation: DeveloperTaskExecutionSignedTranscriptExpectation | None
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    worker_result_sha256: str
    terminal_payload_sha256: str
    terminal_signature_sha256: str
    public_key_sha256: str
    signature_valid: bool
    terminal_payload: DeveloperTaskExecutionBoundaryDocument | None
    worker_result: DeveloperTaskExecutionBoundaryDocument | None
    issues: tuple[DeveloperTaskExecutionBoundaryIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            self.status == SIGNED_TRANSCRIPT_STATUS_VERIFIED
            and self.policy.ok
            and self.expectation is not None
            and len(self.request_sha256) == 64
            and len(self.ready_sha256) == 64
            and len(self.authorize_sha256) == 64
            and len(self.worker_result_sha256) == 64
            and len(self.terminal_payload_sha256) == 64
            and len(self.terminal_signature_sha256) == 64
            and self.public_key_sha256 == self.expectation.public_key_sha256
            and self.signature_valid
            and self.terminal_payload is not None
            and self.worker_result is not None
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "policy": self.policy.to_dict(),
            "policy_fingerprint": self.policy.fingerprint,
            "expectation": self.expectation.to_dict() if self.expectation is not None else None,
            "hashes": {
                "request_sha256": self.request_sha256,
                "ready_sha256": self.ready_sha256,
                "authorize_sha256": self.authorize_sha256,
                "worker_result_sha256": self.worker_result_sha256,
                "terminal_payload_sha256": self.terminal_payload_sha256,
                "terminal_signature_sha256": self.terminal_signature_sha256,
                "public_key_sha256": self.public_key_sha256,
            },
            "signature_valid": self.signature_valid,
            "terminal_payload": (
                self.terminal_payload.to_dict()
                if self.terminal_payload is not None
                else None
            ),
            "worker_result": (
                self.worker_result.to_dict()
                if self.worker_result is not None
                else None
            ),
            "execution_authorized": False,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


def _sha256(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("transcript artifacts must be bytes")
    return hashlib.sha256(data).hexdigest()


def _add_issue(
    issues: list[DeveloperTaskExecutionBoundaryIssue],
    code: str,
    check: str,
    message: str,
    *,
    expected: str = "",
    actual: str = "",
) -> None:
    issues.append(
        DeveloperTaskExecutionBoundaryIssue(
            code=code,
            check=check,
            message=message,
            expected=expected,
            actual=actual,
        )
    )


def _require_equal(
    issues: list[DeveloperTaskExecutionBoundaryIssue],
    *,
    check: str,
    expected: Any,
    actual: Any,
    code: str = "boundary_transcript_mismatch",
) -> None:
    if actual != expected:
        _add_issue(
            issues,
            code,
            check,
            "Signed-boundary transcript value does not match pinned evidence.",
            expected=repr(expected),
            actual=repr(actual),
        )


def _parse_timestamp_epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _contract_issue(
    issues: list[DeveloperTaskExecutionBoundaryIssue],
    check: str,
    exc: DeveloperTaskExecutionBoundaryContractError,
) -> None:
    _add_issue(
        issues,
        exc.code,
        check,
        str(exc),
        actual=exc.actual or exc.field_name,
    )


def pin_developer_task_execution_signed_transcript(
    *,
    policy: DeveloperTaskExecutionBoundaryPolicy,
    expected_request_id: str,
    expected_host_nonce: str,
    expected_request_sha256: str,
    policy_bytes: bytes,
    bootstrap_bytes: bytes,
    controller_bytes: bytes,
    worker_source_bytes: bytes,
    wsb_bytes: bytes,
    request_bytes: bytes,
    ready_bytes: bytes,
    authorize_bytes: bytes,
    authorization_observed_epoch: int | None = None,
) -> DeveloperTaskExecutionSignedTranscriptPinReport:
    if not isinstance(policy, DeveloperTaskExecutionBoundaryPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionBoundaryPolicy")
    issues: list[DeveloperTaskExecutionBoundaryIssue] = []
    request: DeveloperTaskExecutionBoundaryDocument | None = None
    ready: DeveloperTaskExecutionBoundaryDocument | None = None
    authorize: DeveloperTaskExecutionBoundaryDocument | None = None
    try:
        validate_execution_boundary_policy(policy)
    except (TypeError, ValueError) as exc:
        _add_issue(
            issues,
            "boundary_policy_invalid",
            "policy",
            "Signed-boundary policy is invalid.",
            actual=f"{type(exc).__name__}: {exc}",
        )
    if _sha256(policy_bytes) != policy.fingerprint or policy_bytes != policy.canonical_bytes():
        _add_issue(
            issues,
            "boundary_policy_bytes_mismatch",
            "policy_bytes",
            "Signed-boundary policy bytes are not the canonical pinned policy.",
            expected=policy.fingerprint,
            actual=_sha256(policy_bytes),
        )
    try:
        request = parse_boundary_request(request_bytes)
    except DeveloperTaskExecutionBoundaryContractError as exc:
        _contract_issue(issues, "request", exc)
    try:
        ready = parse_boundary_ready(ready_bytes)
    except DeveloperTaskExecutionBoundaryContractError as exc:
        _contract_issue(issues, "ready", exc)
    try:
        authorize = parse_boundary_authorize(authorize_bytes)
    except DeveloperTaskExecutionBoundaryContractError as exc:
        _contract_issue(issues, "authorize", exc)

    expectation: DeveloperTaskExecutionSignedTranscriptExpectation | None = None
    if not issues and request is not None and ready is not None and authorize is not None:
        request_payload = request.to_dict()
        ready_payload = ready.to_dict()
        authorize_payload = authorize.to_dict()
        artifact_hashes = {
            "policy_sha256": _sha256(policy_bytes),
            "bootstrap_sha256": _sha256(bootstrap_bytes),
            "controller_sha256": _sha256(controller_bytes),
            "worker_source_sha256": _sha256(worker_source_bytes),
            "wsb_sha256": _sha256(wsb_bytes),
        }
        for key, expected in (
            ("backend_id", policy.backend_id),
            ("base_policy_fingerprint", policy.base_policy_fingerprint),
            ("boundary_id", policy.boundary_id),
            ("boundary_fingerprint", policy.fingerprint),
            ("request_id", expected_request_id),
            ("host_nonce", expected_host_nonce),
        ):
            _require_equal(
                issues,
                check=f"request.{key}",
                expected=expected,
                actual=request_payload[key],
            )
        _require_equal(
            issues,
            check="request.sha256",
            expected=expected_request_sha256,
            actual=request.sha256,
            code="boundary_request_replay_or_substitution",
        )
        for key, actual_hash in artifact_hashes.items():
            _require_equal(
                issues,
                check=f"request.{key}",
                expected=actual_hash,
                actual=request_payload[key],
                code="boundary_artifact_hash_mismatch",
            )
        for key in (
            "backend_id",
            "base_policy_fingerprint",
            "boundary_id",
            "boundary_fingerprint",
            "request_id",
            "host_nonce",
            "policy_sha256",
            "bootstrap_sha256",
            "controller_sha256",
            "worker_source_sha256",
            "wsb_sha256",
        ):
            _require_equal(
                issues,
                check=f"ready.{key}",
                expected=request_payload[key],
                actual=ready_payload[key],
            )
        _require_equal(
            issues,
            check="ready.request_sha256",
            expected=request.sha256,
            actual=ready_payload["request_sha256"],
        )
        for key in ("request_id", "host_nonce", "request_sha256", "worker_source_sha256"):
            expected = (
                request.sha256
                if key == "request_sha256"
                else request_payload[key]
            )
            _require_equal(
                issues,
                check=f"authorize.{key}",
                expected=expected,
                actual=authorize_payload[key],
            )
        _require_equal(
            issues,
            check="authorize.ready_sha256",
            expected=ready.sha256,
            actual=authorize_payload["ready_sha256"],
        )
        _require_equal(
            issues,
            check="authorize.public_key_sha256",
            expected=ready_payload["public_key_sha256"],
            actual=authorize_payload["public_key_sha256"],
        )
        request_epoch = _parse_timestamp_epoch(request_payload["created_at_utc"])
        ready_epoch = _parse_timestamp_epoch(ready_payload["created_at_utc"])
        maximum_ready_epoch = request_epoch + request_payload["ready_timeout_seconds"] + 1.0
        if ready_epoch <= request_epoch or ready_epoch > maximum_ready_epoch:
            _add_issue(
                issues,
                "boundary_ready_window_invalid",
                "ready.created_at_utc",
                "Ready evidence is outside the request-defined ready window.",
                expected=f">{request_epoch} and <={maximum_ready_epoch}",
                actual=str(ready_epoch),
            )
        deadline = authorize_payload["authorization_deadline_epoch"]
        maximum_deadline = ready_epoch + request_payload["authorization_timeout_seconds"] + 1.0
        if deadline <= ready_epoch or deadline > maximum_deadline:
            _add_issue(
                issues,
                "boundary_authorization_window_invalid",
                "authorize.authorization_deadline_epoch",
                "Authorization deadline is outside the request-defined window.",
                expected=f">{ready_epoch} and <={maximum_deadline}",
                actual=str(deadline),
            )
        if authorization_observed_epoch is not None and authorization_observed_epoch > deadline:
            _add_issue(
                issues,
                "boundary_authorization_expired",
                "authorize.authorization_deadline_epoch",
                "Authorization was observed after its deadline.",
                expected=f"<={deadline}",
                actual=str(authorization_observed_epoch),
            )
        if not issues:
            expectation = DeveloperTaskExecutionSignedTranscriptExpectation(
                backend_id=policy.backend_id,
                base_policy_fingerprint=policy.base_policy_fingerprint,
                boundary_id=policy.boundary_id,
                boundary_fingerprint=policy.fingerprint,
                request_id=expected_request_id,
                host_nonce=expected_host_nonce,
                authorization_nonce=authorize_payload["authorization_nonce"],
                authorization_deadline_epoch=deadline,
                request_sha256=request.sha256,
                ready_sha256=ready.sha256,
                authorize_sha256=authorize.sha256,
                public_key_sha256=ready_payload["public_key_sha256"],
                worker_source_sha256=artifact_hashes["worker_source_sha256"],
                policy_sha256=artifact_hashes["policy_sha256"],
                bootstrap_sha256=artifact_hashes["bootstrap_sha256"],
                controller_sha256=artifact_hashes["controller_sha256"],
                wsb_sha256=artifact_hashes["wsb_sha256"],
                public_key_blob=base64.b64decode(
                    ready_payload["public_key_blob_base64"],
                    validate=True,
                ),
            )
    status = SIGNED_TRANSCRIPT_STATUS_PINNED if expectation is not None and not issues else SIGNED_TRANSCRIPT_STATUS_FAILED
    return DeveloperTaskExecutionSignedTranscriptPinReport(
        status=status,
        policy=policy,
        expectation=expectation,
        request=request,
        ready=ready,
        authorize=authorize,
        issues=tuple(issues),
    )


def verify_developer_task_execution_signed_transcript(
    pin_report: DeveloperTaskExecutionSignedTranscriptPinReport,
    *,
    policy_bytes: bytes,
    bootstrap_bytes: bytes,
    controller_bytes: bytes,
    worker_source_bytes: bytes,
    wsb_bytes: bytes,
    request_bytes: bytes,
    ready_bytes: bytes,
    authorize_bytes: bytes,
    worker_result_bytes: bytes,
    terminal_payload_bytes: bytes,
    terminal_signature_bytes: bytes,
    signature_verifier: Callable[[bytes, bytes, bytes], bool] | None = None,
) -> DeveloperTaskExecutionSignedTranscriptReport:
    if not isinstance(pin_report, DeveloperTaskExecutionSignedTranscriptPinReport):
        raise TypeError("pin_report must be DeveloperTaskExecutionSignedTranscriptPinReport")
    issues: list[DeveloperTaskExecutionBoundaryIssue] = []
    expectation = pin_report.expectation if pin_report.ok else None
    if expectation is None:
        _add_issue(
            issues,
            "boundary_pin_report_failed",
            "pin_report",
            "Successful pinned transcript evidence is required.",
            actual=repr(pin_report.issue_codes),
        )
    request_sha256 = _sha256(request_bytes)
    ready_sha256 = _sha256(ready_bytes)
    authorize_sha256 = _sha256(authorize_bytes)
    worker_result_sha256 = _sha256(worker_result_bytes)
    terminal_payload_sha256 = _sha256(terminal_payload_bytes)
    terminal_signature_sha256 = _sha256(terminal_signature_bytes)
    public_key_sha256 = expectation.public_key_sha256 if expectation is not None else ""
    worker_result: DeveloperTaskExecutionBoundaryDocument | None = None
    terminal: DeveloperTaskExecutionBoundaryDocument | None = None
    signature_valid = False

    if expectation is not None:
        pinned_hashes = {
            "policy": (expectation.policy_sha256, _sha256(policy_bytes)),
            "bootstrap": (expectation.bootstrap_sha256, _sha256(bootstrap_bytes)),
            "controller": (expectation.controller_sha256, _sha256(controller_bytes)),
            "worker_source": (expectation.worker_source_sha256, _sha256(worker_source_bytes)),
            "wsb": (expectation.wsb_sha256, _sha256(wsb_bytes)),
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
                code="boundary_pinned_artifact_changed",
            )
        if policy_bytes != pin_report.policy.canonical_bytes():
            _add_issue(
                issues,
                "boundary_policy_bytes_mismatch",
                "policy_bytes",
                "Boundary policy bytes changed after pinning.",
            )

    try:
        parsed_request = parse_boundary_request(request_bytes)
        parsed_ready = parse_boundary_ready(ready_bytes)
        parsed_authorize = parse_boundary_authorize(authorize_bytes)
    except DeveloperTaskExecutionBoundaryContractError as exc:
        _contract_issue(issues, "pinned_transcript_reparse", exc)
        parsed_request = None
        parsed_ready = None
        parsed_authorize = None
    try:
        worker_result = parse_boundary_worker_result(worker_result_bytes)
    except DeveloperTaskExecutionBoundaryContractError as exc:
        _contract_issue(issues, "worker_result", exc)
    try:
        terminal = parse_boundary_terminal_payload(terminal_payload_bytes)
    except DeveloperTaskExecutionBoundaryContractError as exc:
        _contract_issue(issues, "terminal_payload", exc)
    try:
        validate_boundary_signature_bytes(terminal_signature_bytes)
    except DeveloperTaskExecutionBoundaryContractError as exc:
        _contract_issue(issues, "terminal_signature", exc)

    if (
        expectation is not None
        and parsed_request is not None
        and parsed_ready is not None
        and parsed_authorize is not None
        and worker_result is not None
        and terminal is not None
    ):
        request_payload = parsed_request.to_dict()
        ready_payload = parsed_ready.to_dict()
        authorize_payload = parsed_authorize.to_dict()
        worker_payload = worker_result.to_dict()
        terminal_payload = terminal.to_dict()
        expected_terminal = {
            "backend_id": expectation.backend_id,
            "base_policy_fingerprint": expectation.base_policy_fingerprint,
            "boundary_id": expectation.boundary_id,
            "boundary_fingerprint": expectation.boundary_fingerprint,
            "request_id": expectation.request_id,
            "host_nonce": expectation.host_nonce,
            "authorization_nonce": expectation.authorization_nonce,
            "request_sha256": expectation.request_sha256,
            "ready_sha256": expectation.ready_sha256,
            "authorize_sha256": expectation.authorize_sha256,
            "policy_sha256": expectation.policy_sha256,
            "bootstrap_sha256": expectation.bootstrap_sha256,
            "controller_sha256": expectation.controller_sha256,
            "worker_source_sha256": expectation.worker_source_sha256,
            "wsb_sha256": expectation.wsb_sha256,
            "worker_result_sha256": worker_result_sha256,
            "public_key_sha256": expectation.public_key_sha256,
        }
        for key, expected in expected_terminal.items():
            _require_equal(
                issues,
                check=f"terminal.{key}",
                expected=expected,
                actual=terminal_payload[key],
            )
        _require_equal(
            issues,
            check="worker_result.request_id",
            expected=expectation.request_id,
            actual=worker_payload["request_id"],
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
        worker_pairs = {
            "sid": "worker_sid",
            "is_administrator": "worker_is_administrator",
            "integrity_rid": "worker_integrity_rid",
            "controller_secret_absent": "controller_secret_absent",
            "sentinel_handle_inherited": "sentinel_handle_inherited",
            "controller_vm_read_blocked": "controller_vm_read_blocked",
            "worker_in_job": "worker_in_job",
            "child_pid": "child_pid",
            "child_in_job": "child_in_job",
        }
        for terminal_key, worker_key in worker_pairs.items():
            _require_equal(
                issues,
                check=f"terminal.worker.{terminal_key}",
                expected=worker_payload[worker_key],
                actual=terminal_payload["worker"][terminal_key],
            )
        _require_equal(
            issues,
            check="terminal.worker.result_ok",
            expected=worker_payload["overall_ok"],
            actual=terminal_payload["worker"]["result_ok"],
        )
        for key in ("input_write_blocked", "control_write_blocked", "output_writable"):
            _require_equal(
                issues,
                check=f"terminal.controls.{key}.ready",
                expected=ready_payload[key],
                actual=terminal_payload["controls"][key],
            )
            _require_equal(
                issues,
                check=f"terminal.controls.{key}.worker",
                expected=worker_payload[key],
                actual=terminal_payload["controls"][key],
            )
        _require_equal(
            issues,
            check="authorize.authorization_nonce",
            expected=expectation.authorization_nonce,
            actual=authorize_payload["authorization_nonce"],
        )
        _require_equal(
            issues,
            check="request.request_id",
            expected=expectation.request_id,
            actual=request_payload["request_id"],
        )
        ready_completed_epoch = _parse_timestamp_epoch(ready_payload["created_at_utc"])
        terminal_completed_epoch = _parse_timestamp_epoch(terminal_payload["completed_at_utc"])
        if terminal_completed_epoch <= ready_completed_epoch:
            _add_issue(
                issues,
                "boundary_terminal_timing_invalid",
                "terminal.completed_at_utc",
                "Terminal payload was completed before the ready phase.",
                expected=f">{ready_completed_epoch}",
                actual=str(terminal_completed_epoch),
            )
        if terminal_completed_epoch > expectation.authorization_deadline_epoch:
            _add_issue(
                issues,
                "boundary_terminal_late",
                "terminal.completed_at_utc",
                "Terminal payload was completed after the authorization deadline.",
                expected=f"<={expectation.authorization_deadline_epoch}",
                actual=str(terminal_completed_epoch),
            )
        if not issues:
            verifier = signature_verifier or verify_ecdsa_p256_sha256_cng
            try:
                verification_result = verifier(
                    expectation.public_key_blob,
                    terminal_payload_bytes,
                    terminal_signature_bytes,
                )
                if type(verification_result) is not bool:
                    _add_issue(
                        issues,
                        "boundary_signature_verifier_result_invalid",
                        "terminal_signature",
                        "Signed-boundary signature verifier returned a non-boolean result.",
                        actual=type(verification_result).__name__,
                    )
                else:
                    signature_valid = verification_result
            except DeveloperTaskExecutionBoundaryCryptoError as exc:
                _add_issue(
                    issues,
                    exc.code,
                    "terminal_signature",
                    str(exc),
                    actual=exc.actual,
                )
            except Exception as exc:
                _add_issue(
                    issues,
                    "boundary_signature_verifier_failed",
                    "terminal_signature",
                    "Signed-boundary signature verifier failed unexpectedly.",
                    actual=f"{type(exc).__name__}: {exc}",
                )
            if not signature_valid and not issues:
                _add_issue(
                    issues,
                    "boundary_signature_invalid",
                    "terminal_signature",
                    "ECDSA signature does not authenticate the terminal payload.",
                )

    status = SIGNED_TRANSCRIPT_STATUS_VERIFIED if signature_valid and not issues else SIGNED_TRANSCRIPT_STATUS_FAILED
    return DeveloperTaskExecutionSignedTranscriptReport(
        status=status,
        policy=pin_report.policy,
        expectation=expectation,
        request_sha256=request_sha256,
        ready_sha256=ready_sha256,
        authorize_sha256=authorize_sha256,
        worker_result_sha256=worker_result_sha256,
        terminal_payload_sha256=terminal_payload_sha256,
        terminal_signature_sha256=terminal_signature_sha256,
        public_key_sha256=public_key_sha256,
        signature_valid=signature_valid,
        terminal_payload=terminal,
        worker_result=worker_result,
        issues=tuple(issues),
    )
