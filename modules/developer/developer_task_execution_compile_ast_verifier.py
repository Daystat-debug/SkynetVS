from __future__ import annotations

"""Host-only pinning and signed transcript verification for V1C2B compile/AST evidence."""

import base64
import hashlib
import math

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from modules.developer.developer_task_execution_boundary_crypto import (
    DeveloperTaskExecutionBoundaryCryptoError,
    validate_ecdsa_p256_public_blob,
    validate_ecdsa_p256_signature,
    verify_ecdsa_p256_sha256_cng,
)
from modules.developer.developer_task_execution_compile_ast_contract import (
    DeveloperTaskExecutionCompileAstContractError,
    DeveloperTaskExecutionCompileAstDocument,
    parse_compile_ast_authorize,
    parse_compile_ast_ready,
    parse_compile_ast_request,
    parse_compile_ast_result,
    parse_compile_ast_source_manifest,
    parse_compile_ast_terminal,
    validate_compile_ast_document_chain,
    validate_compile_ast_signature_bytes,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DeveloperTaskExecutionCompileAstRunnerBundle,
    build_developer_task_execution_compile_ast_runner_bundle,
)
from modules.developer.developer_task_execution_compile_ast_verifier_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_READY_TOLERANCE_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_FAILED,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_PINNED,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_VERIFIED,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_TERMINAL_TOLERANCE_SECONDS,
    validate_developer_task_execution_compile_ast_verifier_policy,
)


_PIN_CAPABILITY = object()


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstVerificationIssue:
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
class DeveloperTaskExecutionCompileAstTranscriptExpectation:
    verifier_policy_fingerprint: str
    contract_policy_fingerprint: str
    runner_policy_fingerprint: str
    runner_bundle_fingerprint: str
    request_id: str
    host_nonce: str = field(repr=False)
    authorization_nonce: str = field(repr=False)
    authorization_deadline_epoch: int
    authorization_observed_epoch: float
    source_manifest_sha256: str
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    public_key_sha256: str
    policy_sha256: str
    bootstrap_sha256: str
    controller_sha256: str
    native_helper_sha256: str
    runner_sha256: str
    payload_sha256: str
    wsb_sha256: str
    runtime_attestation_policy_fingerprint: str
    runtime_bundle_fingerprint: str
    runtime_lease_policy_fingerprint: str
    runtime_lease_fingerprint: str
    plan_policy_fingerprint: str
    plan_fingerprint: str
    selected_file_count: int
    selected_total_bytes: int
    public_key_blob: bytes = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier_policy_fingerprint": self.verifier_policy_fingerprint,
            "contract_policy_fingerprint": self.contract_policy_fingerprint,
            "runner_policy_fingerprint": self.runner_policy_fingerprint,
            "runner_bundle_fingerprint": self.runner_bundle_fingerprint,
            "request_id": self.request_id,
            "authorization_deadline_epoch": self.authorization_deadline_epoch,
            "authorization_observed_epoch": self.authorization_observed_epoch,
            "source_manifest_sha256": self.source_manifest_sha256,
            "request_sha256": self.request_sha256,
            "ready_sha256": self.ready_sha256,
            "authorize_sha256": self.authorize_sha256,
            "public_key_sha256": self.public_key_sha256,
            "policy_sha256": self.policy_sha256,
            "bootstrap_sha256": self.bootstrap_sha256,
            "controller_sha256": self.controller_sha256,
            "native_helper_sha256": self.native_helper_sha256,
            "runner_sha256": self.runner_sha256,
            "payload_sha256": self.payload_sha256,
            "wsb_sha256": self.wsb_sha256,
            "runtime_attestation_policy_fingerprint": self.runtime_attestation_policy_fingerprint,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "runtime_lease_policy_fingerprint": self.runtime_lease_policy_fingerprint,
            "runtime_lease_fingerprint": self.runtime_lease_fingerprint,
            "plan_policy_fingerprint": self.plan_policy_fingerprint,
            "plan_fingerprint": self.plan_fingerprint,
            "selected_file_count": self.selected_file_count,
            "selected_total_bytes": self.selected_total_bytes,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstTranscriptPinReport:
    status: str
    expectation: DeveloperTaskExecutionCompileAstTranscriptExpectation | None
    source_manifest: DeveloperTaskExecutionCompileAstDocument | None = field(repr=False)
    request: DeveloperTaskExecutionCompileAstDocument | None = field(repr=False)
    ready: DeveloperTaskExecutionCompileAstDocument | None = field(repr=False)
    authorize: DeveloperTaskExecutionCompileAstDocument | None = field(repr=False)
    issues: tuple[DeveloperTaskExecutionCompileAstVerificationIssue, ...]
    _pin_capability: object | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def ok(self) -> bool:
        return (
            self._pin_capability is _PIN_CAPABILITY
            and self.status == DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_PINNED
            and self.expectation is not None
            and self.source_manifest is not None
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
            "verifier_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
            "expectation": self.expectation.to_dict() if self.expectation is not None else None,
            "hashes": {
                "source_manifest_sha256": self.source_manifest.sha256 if self.source_manifest is not None else "",
                "request_sha256": self.request.sha256 if self.request is not None else "",
                "ready_sha256": self.ready.sha256 if self.ready is not None else "",
                "authorize_sha256": self.authorize.sha256 if self.authorize is not None else "",
            },
            "sandbox_launched": False,
            "candidate_interpreter_executed": False,
            "changed_source_processed": False,
            "execution_authorized": False,
            "reusable_lease_issued": False,
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_codes": list(self.issue_codes),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstTranscriptReport:
    status: str
    expectation: DeveloperTaskExecutionCompileAstTranscriptExpectation | None
    source_manifest_sha256: str
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    result_sha256: str | None
    terminal_payload_sha256: str
    terminal_signature_sha256: str
    public_key_sha256: str
    signature_valid: bool
    chain_verified: bool
    result_verified: bool
    terminal_verified: bool
    terminal_status: str
    boundary_ok: bool
    check_passed: bool
    issues: tuple[DeveloperTaskExecutionCompileAstVerificationIssue, ...]

    @property
    def ok(self) -> bool:
        if (
            self.status != DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_VERIFIED
            or self.expectation is None
            or self.public_key_sha256 != self.expectation.public_key_sha256
            or not self.signature_valid
            or not self.chain_verified
            or not self.terminal_verified
            or self.issues
        ):
            return False
        if self.boundary_ok and not self.result_verified:
            return False
        if not self.boundary_ok and self.result_sha256 is not None:
            return False
        return self.terminal_status in {
            "compile_ast_attested_passed",
            "compile_ast_attested_failed",
            "compile_ast_boundary_failed",
        }

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "verifier_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
            "expectation": self.expectation.to_dict() if self.expectation is not None else None,
            "hashes": {
                "source_manifest_sha256": self.source_manifest_sha256,
                "request_sha256": self.request_sha256,
                "ready_sha256": self.ready_sha256,
                "authorize_sha256": self.authorize_sha256,
                "result_sha256": self.result_sha256,
                "terminal_payload_sha256": self.terminal_payload_sha256,
                "terminal_signature_sha256": self.terminal_signature_sha256,
                "public_key_sha256": self.public_key_sha256,
            },
            "signature_valid": self.signature_valid,
            "chain_verified": self.chain_verified,
            "result_verified": self.result_verified,
            "terminal_verified": self.terminal_verified,
            "terminal_status": self.terminal_status,
            "boundary_ok": self.boundary_ok,
            "check_passed": self.check_passed,
            "changed_code_executed": False,
            "execution_authorized": False,
            "reusable_lease_issued": False,
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_codes": list(self.issue_codes),
        }


def _sha256(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("compile/AST transcript artifacts must be bytes")
    return hashlib.sha256(data).hexdigest()


def _add_issue(
    issues: list[DeveloperTaskExecutionCompileAstVerificationIssue],
    code: str,
    check: str,
    message: str,
    *,
    expected: str = "",
    actual: str = "",
) -> None:
    issues.append(
        DeveloperTaskExecutionCompileAstVerificationIssue(
            code=code,
            check=check,
            message=message,
            expected=expected,
            actual=actual,
        )
    )


def _require_equal(
    issues: list[DeveloperTaskExecutionCompileAstVerificationIssue],
    *,
    check: str,
    expected: Any,
    actual: Any,
    code: str = "compile_ast_verifier_transcript_mismatch",
) -> None:
    if actual != expected:
        _add_issue(
            issues,
            code,
            check,
            "Compile/AST transcript value does not match pinned evidence.",
            expected=repr(expected),
            actual=repr(actual),
        )


def _parse_timestamp_epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _contract_issue(
    issues: list[DeveloperTaskExecutionCompileAstVerificationIssue],
    check: str,
    exc: DeveloperTaskExecutionCompileAstContractError,
) -> None:
    _add_issue(issues, exc.code, check, str(exc), actual=exc.actual or exc.field_name)


def _crypto_issue(
    issues: list[DeveloperTaskExecutionCompileAstVerificationIssue],
    check: str,
    exc: DeveloperTaskExecutionBoundaryCryptoError,
) -> None:
    _add_issue(issues, exc.code, check, str(exc), actual=exc.actual)


def _trusted_runner_bundle() -> DeveloperTaskExecutionCompileAstRunnerBundle:
    errors = validate_developer_task_execution_compile_ast_verifier_policy()
    if errors:
        raise ValueError("compile_ast_verifier_policy_invalid:" + ",".join(errors))
    bundle = build_developer_task_execution_compile_ast_runner_bundle()
    if not bundle.ok:
        raise ValueError("compile_ast_runner_bundle_invalid")
    return bundle


def _validate_pre_authorization_chain(
    issues: list[DeveloperTaskExecutionCompileAstVerificationIssue],
    source_manifest: DeveloperTaskExecutionCompileAstDocument,
    request: DeveloperTaskExecutionCompileAstDocument,
    ready: DeveloperTaskExecutionCompileAstDocument,
    authorize: DeveloperTaskExecutionCompileAstDocument,
) -> None:
    sm = source_manifest.to_dict()
    rq = request.to_dict()
    rd = ready.to_dict()
    az = authorize.to_dict()
    for field_name in ("request_id", "host_nonce"):
        _require_equal(issues, check=f"source_manifest.{field_name}", expected=rq[field_name], actual=sm[field_name])
        _require_equal(issues, check=f"ready.{field_name}", expected=rq[field_name], actual=rd[field_name])
        _require_equal(issues, check=f"authorize.{field_name}", expected=rq[field_name], actual=az[field_name])
    _require_equal(issues, check="source_manifest.plan_fingerprint", expected=rq["plan_fingerprint"], actual=sm["plan_fingerprint"])
    _require_equal(issues, check="request.plan_policy_fingerprint", expected=sm["plan_policy_fingerprint"], actual=rq["plan_policy_fingerprint"])
    _require_equal(issues, check="request.source_manifest_sha256", expected=source_manifest.sha256, actual=rq["source_manifest_sha256"])
    _require_equal(issues, check="request.selected_file_count", expected=sm["selected_file_count"], actual=rq["selected_file_count"])
    _require_equal(issues, check="request.selected_total_bytes", expected=sm["selected_total_bytes"], actual=rq["selected_total_bytes"])
    _require_equal(issues, check="ready.request_sha256", expected=request.sha256, actual=rd["request_sha256"])
    _require_equal(issues, check="ready.source_manifest_sha256", expected=source_manifest.sha256, actual=rd["source_manifest_sha256"])
    _require_equal(issues, check="authorize.request_sha256", expected=request.sha256, actual=az["request_sha256"])
    _require_equal(issues, check="authorize.ready_sha256", expected=ready.sha256, actual=az["ready_sha256"])
    _require_equal(issues, check="authorize.public_key_sha256", expected=rd["public_key_sha256"], actual=az["public_key_sha256"])
    _require_equal(issues, check="authorize.source_manifest_sha256", expected=source_manifest.sha256, actual=az["source_manifest_sha256"])
    _require_equal(issues, check="authorize.runtime_lease_fingerprint", expected=rq["runtime_lease_fingerprint"], actual=az["runtime_lease_fingerprint"])
    _require_equal(issues, check="authorize.plan_fingerprint", expected=rq["plan_fingerprint"], actual=az["plan_fingerprint"])
    artifact_fields = (
        "policy_sha256",
        "bootstrap_sha256",
        "controller_sha256",
        "native_helper_sha256",
        "runner_sha256",
        "payload_sha256",
        "wsb_sha256",
        "runtime_attestation_policy_fingerprint",
        "runtime_bundle_fingerprint",
        "runtime_lease_policy_fingerprint",
        "runtime_lease_fingerprint",
        "plan_policy_fingerprint",
        "plan_fingerprint",
    )
    for field_name in artifact_fields:
        _require_equal(issues, check=f"ready.{field_name}", expected=rq[field_name], actual=rd[field_name])


def _make_pin_report(
    *,
    status: str,
    expectation: DeveloperTaskExecutionCompileAstTranscriptExpectation | None,
    source_manifest: DeveloperTaskExecutionCompileAstDocument | None,
    request: DeveloperTaskExecutionCompileAstDocument | None,
    ready: DeveloperTaskExecutionCompileAstDocument | None,
    authorize: DeveloperTaskExecutionCompileAstDocument | None,
    issues: list[DeveloperTaskExecutionCompileAstVerificationIssue],
    trusted: bool,
) -> DeveloperTaskExecutionCompileAstTranscriptPinReport:
    report = DeveloperTaskExecutionCompileAstTranscriptPinReport(
        status=status,
        expectation=expectation,
        source_manifest=source_manifest,
        request=request,
        ready=ready,
        authorize=authorize,
        issues=tuple(issues),
    )
    if trusted:
        object.__setattr__(report, "_pin_capability", _PIN_CAPABILITY)
    return report


def pin_developer_task_execution_compile_ast_transcript(
    *,
    expected_request_id: str,
    expected_host_nonce: str,
    expected_authorization_nonce: str,
    expected_source_manifest_sha256: str,
    expected_request_sha256: str,
    expected_plan_fingerprint: str,
    expected_runtime_lease_fingerprint: str,
    authorization_observed_epoch: float,
    source_manifest_bytes: bytes,
    request_bytes: bytes,
    ready_bytes: bytes,
    authorize_bytes: bytes,
) -> DeveloperTaskExecutionCompileAstTranscriptPinReport:
    if isinstance(authorization_observed_epoch, bool) or not isinstance(authorization_observed_epoch, (int, float)):
        raise TypeError("authorization_observed_epoch must be a positive finite number")
    authorization_observed_epoch = float(authorization_observed_epoch)
    if not math.isfinite(authorization_observed_epoch) or authorization_observed_epoch <= 0.0:
        raise TypeError("authorization_observed_epoch must be a positive finite number")

    issues: list[DeveloperTaskExecutionCompileAstVerificationIssue] = []
    source_manifest: DeveloperTaskExecutionCompileAstDocument | None = None
    request: DeveloperTaskExecutionCompileAstDocument | None = None
    ready: DeveloperTaskExecutionCompileAstDocument | None = None
    authorize: DeveloperTaskExecutionCompileAstDocument | None = None
    bundle: DeveloperTaskExecutionCompileAstRunnerBundle | None = None
    try:
        bundle = _trusted_runner_bundle()
    except Exception as exc:
        _add_issue(
            issues,
            "compile_ast_verifier_trusted_bundle_invalid",
            "runner_bundle",
            "Trusted V1C2A2 runner bundle could not be reconstructed.",
            actual=f"{type(exc).__name__}: {exc}",
        )
    for check, parser, data in (
        ("source_manifest", parse_compile_ast_source_manifest, source_manifest_bytes),
        ("request", parse_compile_ast_request, request_bytes),
        ("ready", parse_compile_ast_ready, ready_bytes),
        ("authorize", parse_compile_ast_authorize, authorize_bytes),
    ):
        try:
            document = parser(data)
        except DeveloperTaskExecutionCompileAstContractError as exc:
            _contract_issue(issues, check, exc)
            continue
        if check == "source_manifest":
            source_manifest = document
        elif check == "request":
            request = document
        elif check == "ready":
            ready = document
        else:
            authorize = document

    expectation: DeveloperTaskExecutionCompileAstTranscriptExpectation | None = None
    if source_manifest is not None and request is not None and ready is not None and authorize is not None:
        _validate_pre_authorization_chain(issues, source_manifest, request, ready, authorize)
        sm = source_manifest.to_dict()
        rq = request.to_dict()
        rd = ready.to_dict()
        az = authorize.to_dict()
        for check, expected, actual, code in (
            ("source_manifest.sha256", expected_source_manifest_sha256, source_manifest.sha256, "compile_ast_verifier_source_manifest_substitution"),
            ("request.sha256", expected_request_sha256, request.sha256, "compile_ast_verifier_request_replay_or_substitution"),
            ("request.request_id", expected_request_id, rq["request_id"], "compile_ast_verifier_run_identity_mismatch"),
            ("request.host_nonce", expected_host_nonce, rq["host_nonce"], "compile_ast_verifier_run_identity_mismatch"),
            ("authorize.authorization_nonce", expected_authorization_nonce, az["authorization_nonce"], "compile_ast_verifier_authorization_identity_mismatch"),
            ("request.plan_fingerprint", expected_plan_fingerprint, rq["plan_fingerprint"], "compile_ast_verifier_plan_identity_mismatch"),
            ("request.runtime_lease_fingerprint", expected_runtime_lease_fingerprint, rq["runtime_lease_fingerprint"], "compile_ast_verifier_runtime_lease_identity_mismatch"),
        ):
            _require_equal(issues, check=check, expected=expected, actual=actual, code=code)
        if bundle is not None:
            for check, expected, actual in (
                ("request.policy_sha256", bundle.contract_policy.sha256, rq["policy_sha256"]),
                ("request.runner_sha256", bundle.runner.sha256, rq["runner_sha256"]),
                ("request.payload_sha256", bundle.payload_manifest.sha256, rq["payload_sha256"]),
            ):
                _require_equal(
                    issues,
                    check=check,
                    expected=expected,
                    actual=actual,
                    code="compile_ast_verifier_runner_bundle_identity_mismatch",
                )
        public_key_blob = b""
        try:
            public_key_blob = base64.b64decode(rd["public_key_blob_base64"], validate=True)
            public_key = validate_ecdsa_p256_public_blob(public_key_blob)
            _require_equal(
                issues,
                check="ready.public_key_sha256.crypto",
                expected=rd["public_key_sha256"],
                actual=public_key.blob_sha256,
                code="compile_ast_verifier_public_key_identity_mismatch",
            )
        except (ValueError, TypeError) as exc:
            _add_issue(issues, "compile_ast_verifier_public_key_decode_failed", "ready.public_key_blob_base64", "Compile/AST public key could not be decoded.", actual=f"{type(exc).__name__}: {exc}")
        except DeveloperTaskExecutionBoundaryCryptoError as exc:
            _crypto_issue(issues, "ready.public_key_blob", exc)
        request_epoch = _parse_timestamp_epoch(rq["created_at_utc"])
        ready_epoch = _parse_timestamp_epoch(rd["created_at_utc"])
        maximum_ready_epoch = request_epoch + rq["ready_timeout_seconds"] + DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_READY_TOLERANCE_SECONDS
        if ready_epoch <= request_epoch or ready_epoch > maximum_ready_epoch:
            _add_issue(issues, "compile_ast_verifier_ready_window_invalid", "ready.created_at_utc", "Ready evidence is outside the request-defined ready window.", expected=f">{request_epoch} and <={maximum_ready_epoch}", actual=str(ready_epoch))
        deadline = az["authorization_deadline_epoch"]
        maximum_deadline = ready_epoch + rq["authorization_timeout_seconds"] + DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_READY_TOLERANCE_SECONDS
        if deadline <= ready_epoch or deadline > maximum_deadline:
            _add_issue(issues, "compile_ast_verifier_authorization_window_invalid", "authorize.authorization_deadline_epoch", "Authorization deadline is outside the request-defined window.", expected=f">{ready_epoch} and <={maximum_deadline}", actual=str(deadline))
        if authorization_observed_epoch < ready_epoch:
            _add_issue(issues, "compile_ast_verifier_authorization_temporal_inversion", "authorization_observed_epoch", "Authorization host timing evidence predates ready evidence.", expected=f">={ready_epoch}", actual=str(authorization_observed_epoch))
        if authorization_observed_epoch > deadline:
            _add_issue(issues, "compile_ast_verifier_authorization_expired", "authorization_observed_epoch", "Authorization was observed after its deadline.", expected=f"<={deadline}", actual=str(authorization_observed_epoch))
        if not issues and bundle is not None and public_key_blob:
            expectation = DeveloperTaskExecutionCompileAstTranscriptExpectation(
                verifier_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
                contract_policy_fingerprint=rq["contract_policy_fingerprint"],
                runner_policy_fingerprint=bundle.policy_fingerprint,
                runner_bundle_fingerprint=bundle.bundle_fingerprint,
                request_id=expected_request_id,
                host_nonce=expected_host_nonce,
                authorization_nonce=expected_authorization_nonce,
                authorization_deadline_epoch=deadline,
                authorization_observed_epoch=authorization_observed_epoch,
                source_manifest_sha256=source_manifest.sha256,
                request_sha256=request.sha256,
                ready_sha256=ready.sha256,
                authorize_sha256=authorize.sha256,
                public_key_sha256=rd["public_key_sha256"],
                policy_sha256=rq["policy_sha256"],
                bootstrap_sha256=rq["bootstrap_sha256"],
                controller_sha256=rq["controller_sha256"],
                native_helper_sha256=rq["native_helper_sha256"],
                runner_sha256=rq["runner_sha256"],
                payload_sha256=rq["payload_sha256"],
                wsb_sha256=rq["wsb_sha256"],
                runtime_attestation_policy_fingerprint=rq["runtime_attestation_policy_fingerprint"],
                runtime_bundle_fingerprint=rq["runtime_bundle_fingerprint"],
                runtime_lease_policy_fingerprint=rq["runtime_lease_policy_fingerprint"],
                runtime_lease_fingerprint=rq["runtime_lease_fingerprint"],
                plan_policy_fingerprint=rq["plan_policy_fingerprint"],
                plan_fingerprint=rq["plan_fingerprint"],
                selected_file_count=sm["selected_file_count"],
                selected_total_bytes=sm["selected_total_bytes"],
                public_key_blob=public_key_blob,
            )

    status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_PINNED if expectation is not None and not issues else DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_FAILED
    return _make_pin_report(
        status=status,
        expectation=expectation,
        source_manifest=source_manifest,
        request=request,
        ready=ready,
        authorize=authorize,
        issues=issues,
        trusted=expectation is not None and not issues,
    )


def verify_developer_task_execution_compile_ast_transcript(
    pin_report: DeveloperTaskExecutionCompileAstTranscriptPinReport,
    *,
    source_manifest_bytes: bytes,
    request_bytes: bytes,
    ready_bytes: bytes,
    authorize_bytes: bytes,
    result_bytes: bytes | None,
    terminal_payload_bytes: bytes,
    terminal_signature_bytes: bytes,
    signature_verifier: Callable[[bytes, bytes, bytes], bool] | None = None,
) -> DeveloperTaskExecutionCompileAstTranscriptReport:
    if not isinstance(pin_report, DeveloperTaskExecutionCompileAstTranscriptPinReport):
        raise TypeError("pin_report must be DeveloperTaskExecutionCompileAstTranscriptPinReport")
    if result_bytes is not None and not isinstance(result_bytes, bytes):
        raise TypeError("result_bytes must be bytes or None")

    issues: list[DeveloperTaskExecutionCompileAstVerificationIssue] = []
    expectation = pin_report.expectation if pin_report.ok else None
    if expectation is None:
        _add_issue(issues, "compile_ast_verifier_pin_report_failed", "pin_report", "A genuine successful compile/AST pin report is required.", actual=repr(pin_report.issue_codes))

    source_manifest_sha256 = _sha256(source_manifest_bytes)
    request_sha256 = _sha256(request_bytes)
    ready_sha256 = _sha256(ready_bytes)
    authorize_sha256 = _sha256(authorize_bytes)
    result_sha256 = _sha256(result_bytes) if result_bytes is not None else None
    terminal_payload_sha256 = _sha256(terminal_payload_bytes)
    terminal_signature_sha256 = _sha256(terminal_signature_bytes)
    public_key_sha256 = expectation.public_key_sha256 if expectation is not None else ""

    if expectation is not None:
        for check, expected, actual in (
            ("pinned.source_manifest_sha256", expectation.source_manifest_sha256, source_manifest_sha256),
            ("pinned.request_sha256", expectation.request_sha256, request_sha256),
            ("pinned.ready_sha256", expectation.ready_sha256, ready_sha256),
            ("pinned.authorize_sha256", expectation.authorize_sha256, authorize_sha256),
        ):
            _require_equal(issues, check=check, expected=expected, actual=actual, code="compile_ast_verifier_pinned_artifact_changed")
        try:
            bundle = _trusted_runner_bundle()
            for check, expected, actual in (
                ("pinned.runner_policy_fingerprint", expectation.runner_policy_fingerprint, bundle.policy_fingerprint),
                ("pinned.runner_bundle_fingerprint", expectation.runner_bundle_fingerprint, bundle.bundle_fingerprint),
                ("pinned.policy_sha256", expectation.policy_sha256, bundle.contract_policy.sha256),
                ("pinned.runner_sha256", expectation.runner_sha256, bundle.runner.sha256),
                ("pinned.payload_sha256", expectation.payload_sha256, bundle.payload_manifest.sha256),
            ):
                _require_equal(issues, check=check, expected=expected, actual=actual, code="compile_ast_verifier_trusted_bundle_changed")
        except Exception as exc:
            _add_issue(issues, "compile_ast_verifier_trusted_bundle_invalid", "runner_bundle", "Trusted V1C2A2 runner bundle could not be reconstructed during verification.", actual=f"{type(exc).__name__}: {exc}")

    source_manifest: DeveloperTaskExecutionCompileAstDocument | None = None
    request: DeveloperTaskExecutionCompileAstDocument | None = None
    ready: DeveloperTaskExecutionCompileAstDocument | None = None
    authorize: DeveloperTaskExecutionCompileAstDocument | None = None
    result: DeveloperTaskExecutionCompileAstDocument | None = None
    terminal: DeveloperTaskExecutionCompileAstDocument | None = None
    for check, parser, data in (
        ("source_manifest", parse_compile_ast_source_manifest, source_manifest_bytes),
        ("request", parse_compile_ast_request, request_bytes),
        ("ready", parse_compile_ast_ready, ready_bytes),
        ("authorize", parse_compile_ast_authorize, authorize_bytes),
    ):
        try:
            document = parser(data)
        except DeveloperTaskExecutionCompileAstContractError as exc:
            _contract_issue(issues, check, exc)
            continue
        if check == "source_manifest":
            source_manifest = document
        elif check == "request":
            request = document
        elif check == "ready":
            ready = document
        else:
            authorize = document
    if result_bytes is not None:
        try:
            result = parse_compile_ast_result(result_bytes)
        except DeveloperTaskExecutionCompileAstContractError as exc:
            _contract_issue(issues, "result", exc)
    try:
        terminal = parse_compile_ast_terminal(terminal_payload_bytes)
    except DeveloperTaskExecutionCompileAstContractError as exc:
        _contract_issue(issues, "terminal", exc)
    try:
        validate_compile_ast_signature_bytes(terminal_signature_bytes)
        validate_ecdsa_p256_signature(terminal_signature_bytes)
    except DeveloperTaskExecutionCompileAstContractError as exc:
        _contract_issue(issues, "terminal_signature", exc)
    except DeveloperTaskExecutionBoundaryCryptoError as exc:
        _crypto_issue(issues, "terminal_signature", exc)

    chain_verified = False
    result_verified = False
    terminal_verified = False
    signature_valid = False
    trusted_terminal_status = ""
    trusted_boundary_ok = False
    trusted_check_passed = False

    if (
        expectation is not None
        and source_manifest is not None
        and request is not None
        and ready is not None
        and authorize is not None
        and terminal is not None
    ):
        try:
            validate_compile_ast_document_chain(source_manifest, request, ready, authorize, result, terminal)
        except DeveloperTaskExecutionCompileAstContractError as exc:
            _contract_issue(issues, "document_chain", exc)
        rq = request.to_dict()
        rd = ready.to_dict()
        az = authorize.to_dict()
        tm = terminal.to_dict()
        for check, expected, actual in (
            ("request.request_id.post_pin", expectation.request_id, rq["request_id"]),
            ("request.host_nonce.post_pin", expectation.host_nonce, rq["host_nonce"]),
            ("authorize.authorization_nonce.post_pin", expectation.authorization_nonce, az["authorization_nonce"]),
            ("request.runtime_lease_fingerprint.post_pin", expectation.runtime_lease_fingerprint, rq["runtime_lease_fingerprint"]),
            ("request.plan_fingerprint.post_pin", expectation.plan_fingerprint, rq["plan_fingerprint"]),
            ("terminal.public_key_sha256", expectation.public_key_sha256, tm["public_key_sha256"]),
            ("terminal.policy_sha256", expectation.policy_sha256, tm["policy_sha256"]),
            ("terminal.bootstrap_sha256", expectation.bootstrap_sha256, tm["bootstrap_sha256"]),
            ("terminal.controller_sha256", expectation.controller_sha256, tm["controller_sha256"]),
            ("terminal.native_helper_sha256", expectation.native_helper_sha256, tm["native_helper_sha256"]),
            ("terminal.runner_sha256", expectation.runner_sha256, tm["runner_sha256"]),
            ("terminal.payload_sha256", expectation.payload_sha256, tm["payload_sha256"]),
            ("terminal.wsb_sha256", expectation.wsb_sha256, tm["wsb_sha256"]),
        ):
            _require_equal(issues, check=check, expected=expected, actual=actual)
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
            _require_equal(issues, check=f"terminal.controller.{terminal_key}", expected=rd[ready_key], actual=tm["controller"][terminal_key])
        for field_name in ("input_write_blocked", "source_write_blocked", "runtime_write_blocked", "control_write_blocked", "output_writable"):
            _require_equal(issues, check=f"terminal.controls.{field_name}", expected=rd[field_name], actual=tm["controls"][field_name])
        ready_epoch = _parse_timestamp_epoch(rd["created_at_utc"])
        terminal_epoch = _parse_timestamp_epoch(tm["completed_at_utc"])
        minimum_terminal_epoch = max(ready_epoch, expectation.authorization_observed_epoch)
        if terminal_epoch <= minimum_terminal_epoch:
            _add_issue(issues, "compile_ast_verifier_terminal_timing_invalid", "terminal.completed_at_utc", "Terminal evidence predates the pinned authorization phase.", expected=f">{minimum_terminal_epoch}", actual=str(terminal_epoch))
        maximum_terminal_epoch = expectation.authorization_deadline_epoch + rq["worker_timeout_seconds"] + rq["shutdown_grace_seconds"] + DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_TERMINAL_TOLERANCE_SECONDS
        if terminal_epoch > maximum_terminal_epoch:
            _add_issue(issues, "compile_ast_verifier_terminal_window_invalid", "terminal.completed_at_utc", "Terminal evidence is outside the bounded worker/shutdown window.", expected=f"<={maximum_terminal_epoch}", actual=str(terminal_epoch))
        chain_verified = not issues
        terminal_verified = not issues
        if tm["boundary_ok"]:
            result_verified = result is not None and not issues
        else:
            result_verified = result is None and tm["status"] == "compile_ast_boundary_failed" and not issues

        if not issues:
            verifier = signature_verifier or verify_ecdsa_p256_sha256_cng
            try:
                verifier_result = verifier(expectation.public_key_blob, terminal_payload_bytes, terminal_signature_bytes)
                if type(verifier_result) is not bool:
                    _add_issue(issues, "compile_ast_verifier_signature_verifier_result_invalid", "terminal_signature", "Compile/AST signature verifier returned a non-boolean result.", actual=type(verifier_result).__name__)
                else:
                    signature_valid = verifier_result
            except DeveloperTaskExecutionBoundaryCryptoError as exc:
                _crypto_issue(issues, "terminal_signature", exc)
            except Exception as exc:
                _add_issue(issues, "compile_ast_verifier_signature_verifier_failed", "terminal_signature", "Compile/AST signature verifier failed unexpectedly.", actual=f"{type(exc).__name__}: {exc}")
            if not signature_valid and not issues:
                _add_issue(issues, "compile_ast_verifier_signature_invalid", "terminal_signature", "ECDSA P-256 signature does not authenticate the terminal payload.")
        if not issues and signature_valid:
            trusted_terminal_status = tm["status"]
            trusted_boundary_ok = tm["boundary_ok"]
            trusted_check_passed = tm["check_passed"]

    if issues:
        chain_verified = False
        result_verified = False
        terminal_verified = False
        trusted_terminal_status = ""
        trusted_boundary_ok = False
        trusted_check_passed = False

    status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_VERIFIED if signature_valid and chain_verified and terminal_verified and not issues else DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_FAILED
    return DeveloperTaskExecutionCompileAstTranscriptReport(
        status=status,
        expectation=expectation,
        source_manifest_sha256=source_manifest_sha256,
        request_sha256=request_sha256,
        ready_sha256=ready_sha256,
        authorize_sha256=authorize_sha256,
        result_sha256=result_sha256,
        terminal_payload_sha256=terminal_payload_sha256,
        terminal_signature_sha256=terminal_signature_sha256,
        public_key_sha256=public_key_sha256,
        signature_valid=signature_valid,
        chain_verified=chain_verified,
        result_verified=result_verified,
        terminal_verified=terminal_verified,
        terminal_status=trusted_terminal_status,
        boundary_ok=trusted_boundary_ok,
        check_passed=trusted_check_passed,
        issues=tuple(issues),
    )
