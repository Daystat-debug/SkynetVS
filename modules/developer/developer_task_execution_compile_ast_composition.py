from __future__ import annotations

"""V1C2C2 one-run active compile/AST Windows Sandbox composition."""

import base64
import hashlib
import json
import os
import secrets
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_backend_host import (
    DeveloperTaskExecutionBackendHostReport,
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_backend_lifecycle_windows import (
    DeveloperTaskExecutionBackendLifecycleWindowsError,
    DeveloperTaskExecutionBackendProcessEvidence,
    DeveloperTaskExecutionBackendTerminationResult,
    launch_windows_sandbox,
    launcher_has_exited,
    snapshot_windows_sandbox_processes,
    terminate_observed_windows_sandbox_processes,
)
from modules.developer.developer_task_execution_backend_policy import (
    DeveloperTaskExecutionBackendPolicy,
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
    validate_execution_backend_policy,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction import (
    COMPILE_AST_CLAIM_TRANSACTION_STATE_ISSUED,
    DeveloperTaskExecutionCompileAstClaimTransaction,
    DeveloperTaskExecutionCompileAstClaimTransactionError,
    DeveloperTaskExecutionCompileAstClaimTransactionMaterial,
    DeveloperTaskExecutionCompileAstClaimTransactionReport,
)
from modules.developer.developer_task_execution_compile_ast_composition_fs import (
    COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS,
    DeveloperTaskExecutionCompileAstCompositionFileSystemError,
    DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence,
    DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts,
    prepare_developer_task_execution_compile_ast_composition_artifacts,
    publish_developer_task_execution_compile_ast_composition_authorization,
    read_developer_task_execution_compile_ast_composition_artifact_bytes,
    remove_developer_task_execution_compile_ast_composition_artifacts,
    validate_developer_task_execution_compile_ast_composition_artifact_parent,
    verify_developer_task_execution_compile_ast_composition_materialization,
)
from modules.developer.developer_task_execution_compile_ast_composition_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_COMMIT_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_BOOTSTRAP_FAILURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_CONTROLLER_FAILURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_EXIT_EMPTY_SCANS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_FORCE_CLEANUP_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_HOST_BOOT_TOLERANCE_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLL_INTERVAL_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_PROCESS_APPEARANCE_GRACE_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SIGNATURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED_ACTIVE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_TERMINAL_FILE_NAME,
    DeveloperTaskExecutionCompileAstCompositionPolicy,
    validate_developer_task_execution_compile_ast_composition_policy,
)
from modules.developer.developer_task_execution_compile_ast_contract import (
    DeveloperTaskExecutionCompileAstContractError,
    DeveloperTaskExecutionCompileAstDocument,
    encode_compile_ast_document,
    parse_compile_ast_ready,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker import (
    DeveloperTaskExecutionCompileAstControllerEvidenceExpectation,
    DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport,
    DeveloperTaskExecutionCompileAstControllerWorkerBundle,
    DeveloperTaskExecutionCompileAstControllerWorkerBundleError,
    build_developer_task_execution_compile_ast_controller_worker_bundle,
    verify_developer_task_execution_compile_ast_controller_evidence_transport,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DeveloperTaskExecutionCompileAstRunnerBundle,
    DeveloperTaskExecutionCompileAstRunnerBundleError,
    build_developer_task_execution_compile_ast_runner_bundle,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
)
from modules.developer.developer_task_execution_compile_ast_verifier import (
    DeveloperTaskExecutionCompileAstTranscriptPinReport,
    DeveloperTaskExecutionCompileAstTranscriptReport,
    pin_developer_task_execution_compile_ast_transcript,
    verify_developer_task_execution_compile_ast_transcript,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_TREE_MANIFEST_SHA256,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue


@dataclass(frozen=True)
class _CompileAstCompositionFailureArtifact:
    file_name: str = ""
    sha256: str = ""
    stage: str = ""
    error_type: str = ""
    error_code: str = ""
    diagnostic_error: str = ""

    @property
    def present(self) -> bool:
        return bool(self.file_name)

    @property
    def diagnostic(self) -> str:
        rows = (
            ("file", self.file_name),
            ("sha256", self.sha256),
            ("stage", self.stage),
            ("error_type", self.error_type),
            ("error_code", self.error_code),
            ("diagnostic_error", self.diagnostic_error),
        )
        return ";".join(f"{key}={value}" for key, value in rows if value)


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstCompositionProcessSnapshot:
    phase: str
    elapsed_ms: int
    launcher_exited: bool | None
    processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "elapsed_ms": self.elapsed_ms,
            "launcher_exited": self.launcher_exited,
            "processes": [item.to_dict() for item in self.processes],
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstCompositionArtifacts:
    root: str
    input_root: str
    source_root: str
    runtime_root: str
    control_root: str
    output_root: str
    request_sha256: str
    source_manifest_sha256: str
    ready_sha256: str
    authorize_sha256: str
    authorize_commit_sha256: str
    result_sha256: str
    terminal_payload_sha256: str
    terminal_signature_sha256: str
    controller_evidence_payload_sha256: str
    controller_evidence_signature_sha256: str
    failure_artifact_sha256: str
    runtime_tree_manifest_sha256: str
    runtime_file_count: int
    runtime_total_bytes: int
    input_manifest_sha256: str
    source_file_count: int
    source_total_bytes: int
    removed: bool
    cleanup_attempts: int

    @property
    def ok(self) -> bool:
        return (
            len(self.request_sha256) == 64
            and len(self.source_manifest_sha256) == 64
            and len(self.ready_sha256) == 64
            and len(self.authorize_sha256) == 64
            and len(self.authorize_commit_sha256) == 64
            and len(self.result_sha256) == 64
            and len(self.terminal_payload_sha256) == 64
            and len(self.terminal_signature_sha256) == 64
            and len(self.controller_evidence_payload_sha256) == 64
            and len(self.controller_evidence_signature_sha256) == 64
            and not self.failure_artifact_sha256
            and self.runtime_tree_manifest_sha256 == RUNTIME_TREE_MANIFEST_SHA256
            and self.runtime_file_count == RUNTIME_BUNDLE_FILE_COUNT
            and self.runtime_total_bytes == RUNTIME_BUNDLE_TOTAL_BYTES
            and len(self.input_manifest_sha256) == 64
            and 1 <= self.source_file_count <= 20
            and 0 <= self.source_total_bytes <= 8 * 1024 * 1024
            and self.removed
            and self.cleanup_attempts >= 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "input_root": self.input_root,
            "source_root": self.source_root,
            "runtime_root": self.runtime_root,
            "control_root": self.control_root,
            "output_root": self.output_root,
            "hashes": {
                "request_sha256": self.request_sha256,
                "source_manifest_sha256": self.source_manifest_sha256,
                "ready_sha256": self.ready_sha256,
                "authorize_sha256": self.authorize_sha256,
                "authorize_commit_sha256": self.authorize_commit_sha256,
                "result_sha256": self.result_sha256,
                "terminal_payload_sha256": self.terminal_payload_sha256,
                "terminal_signature_sha256": self.terminal_signature_sha256,
                "controller_evidence_payload_sha256": (
                    self.controller_evidence_payload_sha256
                ),
                "controller_evidence_signature_sha256": (
                    self.controller_evidence_signature_sha256
                ),
                "failure_artifact_sha256": self.failure_artifact_sha256,
            },
            "runtime": {
                "tree_manifest_sha256": self.runtime_tree_manifest_sha256,
                "file_count": self.runtime_file_count,
                "total_bytes": self.runtime_total_bytes,
            },
            "input_manifest_sha256": self.input_manifest_sha256,
            "source_file_count": self.source_file_count,
            "source_total_bytes": self.source_total_bytes,
            "removed": self.removed,
            "cleanup_attempts": self.cleanup_attempts,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstCompositionReport:
    status: str
    policy: DeveloperTaskExecutionCompileAstCompositionPolicy
    backend_policy: DeveloperTaskExecutionBackendPolicy
    transaction_report: DeveloperTaskExecutionCompileAstClaimTransactionReport | None
    host_boot_epoch_seconds: int
    host_executable_sha256: str
    started_at_epoch_seconds: float
    completed_at_epoch_seconds: float
    launcher_pid: int
    process_observed: bool
    all_processes_exited: bool
    termination: DeveloperTaskExecutionBackendTerminationResult
    ready_received_ms: int | None
    authorization_published_ms: int | None
    result_detected_ms: int | None
    terminal_detected_ms: int | None
    all_processes_exited_ms: int | None
    total_ms: int
    process_timeline: tuple[DeveloperTaskExecutionCompileAstCompositionProcessSnapshot, ...]
    materialization: DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence | None
    pin_report: DeveloperTaskExecutionCompileAstTranscriptPinReport | None
    controller_evidence_report: DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport | None
    signed_report: DeveloperTaskExecutionCompileAstTranscriptReport | None
    artifacts: DeveloperTaskExecutionCompileAstCompositionArtifacts | None
    claim_transaction_consumed: bool
    runtime_lease_claimed: bool
    sandbox_launched: bool
    candidate_interpreter_executed: bool
    changed_source_processed: bool
    changed_source_ast_parsed: bool
    changed_source_compiled: bool
    issues: tuple[DeveloperTaskPreflightIssue, ...]
    changed_code_executed: bool = False
    reusable_lease_issued: bool = False
    execution_authorized: bool = False

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    @property
    def ok(self) -> bool:
        return (
            self.status
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED
            and self.policy
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1
            and self.backend_policy == WINDOWS_SANDBOX_EXECUTION_POLICY_V1
            and self.transaction_report is not None
            and self.transaction_report.ok
            and self.host_boot_epoch_seconds > 0
            and len(self.host_executable_sha256) == 64
            and self.launcher_pid > 0
            and self.process_observed
            and self.all_processes_exited
            and not self.termination.attempted
            and self.materialization is not None
            and self.materialization.ok
            and self.pin_report is not None
            and self.pin_report.ok
            and self.controller_evidence_report is not None
            and self.controller_evidence_report.ok
            and self.controller_evidence_report.status == "controller_signed_success"
            and self.controller_evidence_report.terminal_status
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS
            and self.controller_evidence_report.signature_valid
            and self.controller_evidence_report.legacy_terminal_signature_valid
            and self.controller_evidence_report.ready_stable
            and self.controller_evidence_report.evidence_stable
            and self.controller_evidence_report.result_stable
            and self.controller_evidence_report.private_relay_hash_bound
            and self.signed_report is not None
            and self.signed_report.ok
            and self.signed_report.terminal_status
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS
            and self.signed_report.boundary_ok
            and self.signed_report.check_passed
            and self.artifacts is not None
            and self.artifacts.ok
            and self.claim_transaction_consumed
            and self.runtime_lease_claimed
            and self.sandbox_launched
            and self.candidate_interpreter_executed
            and self.changed_source_processed
            and self.changed_source_ast_parsed
            and self.changed_source_compiled
            and not self.changed_code_executed
            and not self.reusable_lease_issued
            and not self.execution_authorized
            and not self.issues
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "policy_id": self.policy.policy_id,
            "policy_fingerprint": self.policy.policy_fingerprint,
            "backend_id": self.backend_policy.backend_id,
            "backend_policy_fingerprint": self.backend_policy.fingerprint,
            "transaction": (
                self.transaction_report.to_dict()
                if self.transaction_report is not None
                else None
            ),
            "host": {
                "boot_epoch_seconds": self.host_boot_epoch_seconds,
                "sandbox_executable_sha256": self.host_executable_sha256,
            },
            "timing": {
                "started_at_epoch_seconds": self.started_at_epoch_seconds,
                "completed_at_epoch_seconds": self.completed_at_epoch_seconds,
                "ready_received_ms": self.ready_received_ms,
                "authorization_published_ms": self.authorization_published_ms,
                "result_detected_ms": self.result_detected_ms,
                "terminal_detected_ms": self.terminal_detected_ms,
                "all_processes_exited_ms": self.all_processes_exited_ms,
                "total_ms": self.total_ms,
            },
            "launcher_pid": self.launcher_pid,
            "process_observed": self.process_observed,
            "all_processes_exited": self.all_processes_exited,
            "termination": self.termination.to_dict(),
            "process_timeline": [item.to_dict() for item in self.process_timeline],
            "materialization": (
                self.materialization.to_dict()
                if self.materialization is not None
                else None
            ),
            "pin_report": self.pin_report.to_dict() if self.pin_report else None,
            "controller_evidence_report": (
                self.controller_evidence_report.to_dict()
                if self.controller_evidence_report
                else None
            ),
            "signed_report": (
                self.signed_report.to_dict() if self.signed_report else None
            ),
            "artifacts": self.artifacts.to_dict() if self.artifacts else None,
            "claim_transaction_consumed": self.claim_transaction_consumed,
            "runtime_lease_claimed": self.runtime_lease_claimed,
            "sandbox_launched": self.sandbox_launched,
            "candidate_interpreter_executed": self.candidate_interpreter_executed,
            "changed_source_processed": self.changed_source_processed,
            "changed_source_ast_parsed": self.changed_source_ast_parsed,
            "changed_source_compiled": self.changed_source_compiled,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


class _CompileAstCompositionRuntime:
    def inspect_host(self) -> DeveloperTaskExecutionBackendHostReport:
        return inspect_developer_task_execution_backend_host()

    def build_runner_bundle(self) -> DeveloperTaskExecutionCompileAstRunnerBundle:
        return build_developer_task_execution_compile_ast_runner_bundle()

    def build_controller_worker_bundle(
        self,
    ) -> DeveloperTaskExecutionCompileAstControllerWorkerBundle:
        return build_developer_task_execution_compile_ast_controller_worker_bundle()

    def claim_transaction(
        self,
        transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
    ) -> DeveloperTaskExecutionCompileAstClaimTransactionMaterial:
        return transaction.claim()

    def prepare_artifacts(self, **kwargs: Any) -> DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts:
        return prepare_developer_task_execution_compile_ast_composition_artifacts(**kwargs)

    def verify_materialization(
        self,
        prepared: DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts,
    ) -> DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence:
        return verify_developer_task_execution_compile_ast_composition_materialization(
            prepared
        )

    def snapshot_processes(self) -> tuple[DeveloperTaskExecutionBackendProcessEvidence, ...]:
        return snapshot_windows_sandbox_processes()

    def launch(self, executable: Path, config_path: Path):
        return launch_windows_sandbox(executable, config_path)

    def launcher_exited(self, launcher: Any) -> bool:
        return launcher_has_exited(launcher)

    def terminate(
        self,
        observed: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...],
        *,
        executable: Path,
    ) -> DeveloperTaskExecutionBackendTerminationResult:
        return terminate_observed_windows_sandbox_processes(
            observed,
            sandbox_executable=executable,
            timeout_seconds=(
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_FORCE_CLEANUP_TIMEOUT_SECONDS
            ),
        )

    def artifact_exists(self, path: Path) -> bool:
        return os.path.lexists(path)

    def read_artifact(
        self,
        path: Path,
        *,
        max_bytes: int,
        artifact_name: str,
        expected_size: int | None = None,
    ) -> tuple[bytes, str]:
        return read_developer_task_execution_compile_ast_composition_artifact_bytes(
            path,
            max_bytes=max_bytes,
            artifact_name=artifact_name,
            expected_size=expected_size,
        )

    def publish_authorize(self, path: Path, data: bytes) -> tuple[str, str]:
        return publish_developer_task_execution_compile_ast_composition_authorization(
            path, data
        )

    def pin_transcript(self, **kwargs: Any) -> DeveloperTaskExecutionCompileAstTranscriptPinReport:
        return pin_developer_task_execution_compile_ast_transcript(**kwargs)

    def verify_transcript(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> DeveloperTaskExecutionCompileAstTranscriptReport:
        return verify_developer_task_execution_compile_ast_transcript(*args, **kwargs)

    def verify_controller_evidence(
        self,
        expectation: DeveloperTaskExecutionCompileAstControllerEvidenceExpectation,
        **kwargs: Any,
    ) -> DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport:
        return verify_developer_task_execution_compile_ast_controller_evidence_transport(
            expectation,
            **kwargs,
        )

    def cleanup(
        self,
        prepared: DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts,
        *,
        artifact_parent: Path,
    ) -> int:
        return remove_developer_task_execution_compile_ast_composition_artifacts(
            prepared.root,
            artifact_parent=artifact_parent,
            initial_metadata=prepared.root_metadata,
        )

    def token_hex(self, bytes_count: int) -> str:
        return secrets.token_hex(bytes_count)

    def monotonic(self) -> float:
        return time.monotonic()

    def epoch(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class _CompileAstCompositionContext:
    def __init__(self, *, started_at: float) -> None:
        self.started_at = started_at
        self.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED
        self.transaction_report: DeveloperTaskExecutionCompileAstClaimTransactionReport | None = None
        self.host_boot_epoch_seconds = 0
        self.host_executable_sha256 = ""
        self.launcher_pid = 0
        self.process_observed = False
        self.all_processes_exited = False
        self.termination = _empty_termination()
        self.ready_received_ms: int | None = None
        self.authorization_published_ms: int | None = None
        self.result_detected_ms: int | None = None
        self.terminal_detected_ms: int | None = None
        self.all_processes_exited_ms: int | None = None
        self.timeline: list[DeveloperTaskExecutionCompileAstCompositionProcessSnapshot] = []
        self.observed_processes: dict[
            tuple[str, int, int], DeveloperTaskExecutionBackendProcessEvidence
        ] = {}
        self.materialization: DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence | None = None
        self.pin_report: DeveloperTaskExecutionCompileAstTranscriptPinReport | None = None
        self.controller_evidence_report: DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport | None = None
        self.signed_report: DeveloperTaskExecutionCompileAstTranscriptReport | None = None
        self.artifacts: DeveloperTaskExecutionCompileAstCompositionArtifacts | None = None
        self.claim_transaction_consumed = False
        self.runtime_lease_claimed = False
        self.sandbox_launched = False
        self.candidate_interpreter_executed = False
        self.changed_source_processed = False
        self.changed_source_ast_parsed = False
        self.changed_source_compiled = False
        self.issues: list[DeveloperTaskPreflightIssue] = []

    def add(
        self,
        code: str,
        message: str,
        *,
        check: str = "execution_compile_ast_composition",
        expected: str = "",
        actual: str = "",
    ) -> None:
        self.issues.append(
            DeveloperTaskPreflightIssue(
                code=code,
                check=check,
                message=message,
                expected=expected,
                actual=actual,
            )
        )

    def report(self, *, completed_at: float, total_ms: int) -> DeveloperTaskExecutionCompileAstCompositionReport:
        return DeveloperTaskExecutionCompileAstCompositionReport(
            status=self.status,
            policy=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1,
            backend_policy=WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
            transaction_report=self.transaction_report,
            host_boot_epoch_seconds=self.host_boot_epoch_seconds,
            host_executable_sha256=self.host_executable_sha256,
            started_at_epoch_seconds=self.started_at,
            completed_at_epoch_seconds=completed_at,
            launcher_pid=self.launcher_pid,
            process_observed=self.process_observed,
            all_processes_exited=self.all_processes_exited,
            termination=self.termination,
            ready_received_ms=self.ready_received_ms,
            authorization_published_ms=self.authorization_published_ms,
            result_detected_ms=self.result_detected_ms,
            terminal_detected_ms=self.terminal_detected_ms,
            all_processes_exited_ms=self.all_processes_exited_ms,
            total_ms=total_ms,
            process_timeline=tuple(self.timeline),
            materialization=self.materialization,
            pin_report=self.pin_report,
            controller_evidence_report=self.controller_evidence_report,
            signed_report=self.signed_report,
            artifacts=self.artifacts,
            claim_transaction_consumed=self.claim_transaction_consumed,
            runtime_lease_claimed=self.runtime_lease_claimed,
            sandbox_launched=self.sandbox_launched,
            candidate_interpreter_executed=self.candidate_interpreter_executed,
            changed_source_processed=self.changed_source_processed,
            changed_source_ast_parsed=self.changed_source_ast_parsed,
            changed_source_compiled=self.changed_source_compiled,
            issues=tuple(self.issues),
        )


def _empty_termination() -> DeveloperTaskExecutionBackendTerminationResult:
    return DeveloperTaskExecutionBackendTerminationResult(
        attempted=False,
        succeeded=False,
        targeted_processes=(),
        remaining_processes=(),
        errors=(),
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _host_key(report: DeveloperTaskExecutionBackendHostReport) -> tuple[Any, ...]:
    executable = report.executable
    return (
        report.backend_id,
        report.policy_fingerprint,
        report.host_platform,
        report.host_architecture,
        report.process_bitness,
        report.windows_build,
        executable.path if executable else "",
        executable.version if executable else "",
        executable.size_bytes if executable else 0,
        executable.mtime_ns if executable else 0,
        executable.sha256 if executable else "",
    )


def _host_evidence_differences(
    expected: DeveloperTaskExecutionBackendHostReport,
    actual: DeveloperTaskExecutionBackendHostReport,
) -> tuple[str, ...]:
    differences: list[str] = []
    if abs(
        int(expected.host_boot_epoch_seconds) - int(actual.host_boot_epoch_seconds)
    ) > DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_HOST_BOOT_TOLERANCE_SECONDS:
        differences.append(
            "host_boot_epoch_seconds:"
            f"{expected.host_boot_epoch_seconds}->{actual.host_boot_epoch_seconds}"
        )
    if _host_key(expected) != _host_key(actual):
        differences.append("host_identity_changed")
    return tuple(differences)


def _append_snapshot(
    context: _CompileAstCompositionContext,
    *,
    phase: str,
    elapsed_ms: int,
    launcher: Any | None,
    processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...],
    runtime: _CompileAstCompositionRuntime,
    force: bool = False,
) -> None:
    for item in processes:
        context.observed_processes[item.identity_key] = item
    launcher_exited: bool | None = None
    if launcher is not None:
        try:
            launcher_exited = runtime.launcher_exited(launcher)
        except Exception:
            launcher_exited = None
    snapshot = DeveloperTaskExecutionCompileAstCompositionProcessSnapshot(
        phase=phase,
        elapsed_ms=elapsed_ms,
        launcher_exited=launcher_exited,
        processes=processes,
    )
    if force or not context.timeline or context.timeline[-1] != snapshot:
        context.timeline.append(snapshot)


def _record_all_processes_exited(
    context: _CompileAstCompositionContext,
    *,
    elapsed_ms: int,
) -> None:
    context.all_processes_exited = True
    context.all_processes_exited_ms = elapsed_ms


def _add_verifier_issues(
    context: _CompileAstCompositionContext,
    report: DeveloperTaskExecutionCompileAstTranscriptPinReport
    | DeveloperTaskExecutionCompileAstTranscriptReport,
    *,
    prefix: str,
) -> None:
    for issue in report.issues:
        context.add(
            f"compile_ast_composition_{prefix}_{issue.code}",
            issue.message,
            check=issue.check,
            expected=issue.expected,
            actual=issue.actual,
        )


def _add_controller_evidence_issues(
    context: _CompileAstCompositionContext,
    report: DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport,
) -> None:
    for code in report.issue_codes:
        context.add(
            f"compile_ast_composition_{code}",
            "R4 controller-signed transport evidence failed verification.",
            check="execution_compile_ast_controller_evidence",
        )


def _read_expected(
    runtime: _CompileAstCompositionRuntime,
    path: Path,
    *,
    name: str,
    expected: bytes,
    max_bytes: int,
) -> tuple[bytes, str]:
    raw, sha256 = runtime.read_artifact(
        path,
        max_bytes=max_bytes,
        artifact_name=name,
        expected_size=len(expected),
    )
    if raw != expected or sha256 != _sha256(expected):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_pinned_artifact_changed",
            "Pinned artifact changed before post-exit verification.",
            actual=name,
        )
    return raw, sha256


def _read_stable_pair(
    runtime: _CompileAstCompositionRuntime,
    path: Path,
    *,
    name: str,
    max_bytes: int,
    expected_size: int | None = None,
) -> tuple[tuple[bytes, bytes], str]:
    first, first_sha256 = runtime.read_artifact(
        path,
        max_bytes=max_bytes,
        artifact_name=name,
        expected_size=expected_size,
    )
    second, _ = runtime.read_artifact(
        path,
        max_bytes=max_bytes,
        artifact_name=name,
        expected_size=expected_size,
    )
    return (first, second), first_sha256


def _failure_text(value: Any, *, name: str, max_length: int) -> str:
    if not isinstance(value, str) or len(value) > max_length:
        raise ValueError(f"{name} invalid")
    return value


def _failure_artifact(
    runtime: _CompileAstCompositionRuntime,
    prepared: DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts,
) -> _CompileAstCompositionFailureArtifact:
    for path, name in (
        (
            prepared.controller_failure_path,
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_CONTROLLER_FAILURE_FILE_NAME,
        ),
        (
            prepared.bootstrap_failure_path,
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_BOOTSTRAP_FAILURE_FILE_NAME,
        ),
    ):
        if not runtime.artifact_exists(path):
            continue
        try:
            raw, sha256 = runtime.read_artifact(
                path,
                max_bytes=COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS[name],
                artifact_name=name,
            )
            payload = json.loads(raw.decode("utf-8", errors="strict"))
            if not isinstance(payload, dict):
                raise ValueError("root invalid")
            return _CompileAstCompositionFailureArtifact(
                file_name=name,
                sha256=sha256,
                stage=_failure_text(payload.get("stage", ""), name="stage", max_length=128),
                error_type=_failure_text(
                    payload.get("error_type", ""),
                    name="error_type",
                    max_length=128,
                ),
                error_code=_failure_text(
                    payload.get("error_code", ""),
                    name="error_code",
                    max_length=128,
                ),
            )
        except Exception as exc:
            return _CompileAstCompositionFailureArtifact(
                file_name=name,
                diagnostic_error=f"{type(exc).__name__}:{exc}",
            )
    return _CompileAstCompositionFailureArtifact()


def _controller_transport_reserved_artifacts(
    prepared: DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts,
) -> tuple[tuple[Path, str], ...]:
    return (
        (
            prepared.result_path,
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
        ),
        (
            prepared.terminal_payload_path,
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_TERMINAL_FILE_NAME,
        ),
        (
            prepared.terminal_signature_path,
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SIGNATURE_FILE_NAME,
        ),
        (
            prepared.controller_evidence_payload_path,
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
        ),
        (
            prepared.controller_evidence_signature_path,
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
        ),
    )


def _build_artifacts_report(
    prepared: DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts,
    *,
    materialization: DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence | None,
    ready_sha256: str,
    authorize_sha256: str,
    authorize_commit_sha256: str,
    result_sha256: str,
    terminal_payload_sha256: str,
    terminal_signature_sha256: str,
    controller_evidence_payload_sha256: str,
    controller_evidence_signature_sha256: str,
    failure_artifact_sha256: str,
    removed: bool,
    cleanup_attempts: int,
) -> DeveloperTaskExecutionCompileAstCompositionArtifacts:
    return DeveloperTaskExecutionCompileAstCompositionArtifacts(
        root=str(prepared.root),
        input_root=str(prepared.input_root),
        source_root=str(prepared.source_root),
        runtime_root=str(prepared.runtime_root),
        control_root=str(prepared.control_root),
        output_root=str(prepared.output_root),
        request_sha256=prepared.request.sha256,
        source_manifest_sha256=prepared.source_manifest.sha256,
        ready_sha256=ready_sha256,
        authorize_sha256=authorize_sha256,
        authorize_commit_sha256=authorize_commit_sha256,
        result_sha256=result_sha256,
        terminal_payload_sha256=terminal_payload_sha256,
        terminal_signature_sha256=terminal_signature_sha256,
        controller_evidence_payload_sha256=controller_evidence_payload_sha256,
        controller_evidence_signature_sha256=controller_evidence_signature_sha256,
        failure_artifact_sha256=failure_artifact_sha256,
        runtime_tree_manifest_sha256=(
            materialization.runtime_tree_manifest_sha256 if materialization else ""
        ),
        runtime_file_count=materialization.runtime_file_count if materialization else 0,
        runtime_total_bytes=materialization.runtime_total_bytes if materialization else 0,
        input_manifest_sha256=materialization.input_manifest_sha256 if materialization else "",
        source_file_count=materialization.source_file_count if materialization else 0,
        source_total_bytes=materialization.source_total_bytes if materialization else 0,
        removed=removed,
        cleanup_attempts=cleanup_attempts,
    )


def _attest_developer_task_execution_compile_ast_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
    *,
    artifact_parent: Path,
    runtime: _CompileAstCompositionRuntime,
) -> DeveloperTaskExecutionCompileAstCompositionReport:
    started_at = runtime.epoch()
    started_monotonic = runtime.monotonic()
    context = _CompileAstCompositionContext(started_at=started_at)
    context.transaction_report = transaction.report
    artifact_parent_resolved: Path | None = None
    prepared: DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts | None = None
    fresh_host: DeveloperTaskExecutionBackendHostReport | None = None
    executable_path: Path | None = None
    launcher: Any | None = None
    launch_attempted = False
    process_state_proven = True
    launcher_state_proven = True
    cleanup_attempts = 0
    artifacts_removed = False
    ready_bytes: bytes | None = None
    authorize_bytes: bytes | None = None
    ready_sha256 = ""
    authorize_sha256 = ""
    authorize_commit_sha256 = ""
    result_sha256 = ""
    terminal_payload_sha256 = ""
    terminal_signature_sha256 = ""
    controller_evidence_payload_sha256 = ""
    controller_evidence_signature_sha256 = ""
    failure_artifact_sha256 = ""
    public_key_blob = b""
    pre_worker_reserved_artifacts: tuple[str, ...] = ()

    try:
        if validate_execution_backend_policy(WINDOWS_SANDBOX_EXECUTION_POLICY_V1):
            context.add(
                "compile_ast_composition_backend_policy_invalid",
                "Canonical Windows Sandbox policy is invalid.",
            )
            raise RuntimeError("backend policy invalid")
        policy_errors = validate_developer_task_execution_compile_ast_composition_policy(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1
        )
        if policy_errors:
            context.add(
                "compile_ast_composition_policy_invalid",
                "Canonical V1C2C2 policy is invalid.",
                actual=",".join(policy_errors),
            )
            raise RuntimeError("composition policy invalid")
        if not host_report.ok or (
            host_report.policy != WINDOWS_SANDBOX_EXECUTION_POLICY_V1
            or host_report.policy_fingerprint
            != WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint
        ):
            context.add(
                "execution_backend_host_report_invalid",
                "Successful canonical V1B1 host evidence is required.",
                actual=",".join(host_report.issue_codes),
            )
            raise RuntimeError("host report invalid")
        if not transaction.report.ok or transaction.status().state != COMPILE_AST_CLAIM_TRANSACTION_STATE_ISSUED:
            context.add(
                "compile_ast_composition_transaction_invalid",
                "A fresh issued V1C2C0 transaction is required.",
                actual=transaction.status().state,
            )
            raise RuntimeError("transaction invalid")

        artifact_parent_resolved = validate_developer_task_execution_compile_ast_composition_artifact_parent(
            artifact_parent
        )
        runner_bundle = runtime.build_runner_bundle()
        controller_worker_bundle = runtime.build_controller_worker_bundle()
        if not runner_bundle.ok or not controller_worker_bundle.ok:
            context.add(
                "compile_ast_composition_payload_bundle_invalid",
                "Canonical V1C2A2/V1C2C1R4 bundles could not be reconstructed.",
            )
            raise RuntimeError("bundle invalid")

        fresh_host = runtime.inspect_host()
        if not fresh_host.ok:
            context.add(
                "execution_backend_host_report_failed",
                "Fresh host inspection failed before transaction claim.",
                actual=",".join(fresh_host.issue_codes),
            )
            raise RuntimeError("fresh host failed")
        host_differences = _host_evidence_differences(host_report, fresh_host)
        if host_differences:
            context.add(
                "execution_backend_host_evidence_changed",
                "Host capability evidence changed before transaction claim.",
                actual=";".join(host_differences),
            )
            raise RuntimeError("host changed")
        context.host_boot_epoch_seconds = fresh_host.host_boot_epoch_seconds
        context.host_executable_sha256 = (
            fresh_host.executable.sha256 if fresh_host.executable else ""
        )
        executable_path = Path(fresh_host.executable.path) if fresh_host.executable else None

        baseline = runtime.snapshot_processes()
        _append_snapshot(
            context,
            phase="before_claim",
            elapsed_ms=0,
            launcher=None,
            processes=baseline,
            runtime=runtime,
            force=True,
        )
        if baseline:
            context.add(
                "compile_ast_composition_sandbox_instance_running",
                "A Windows Sandbox instance is already running.",
                actual=",".join(f"{item.name}:{item.pid}" for item in baseline),
            )
            raise RuntimeError("sandbox already running")

        transaction_material = runtime.claim_transaction(transaction)
        context.claim_transaction_consumed = True
        context.runtime_lease_claimed = transaction_material.runtime_lease_claimed
        request_id = runtime.token_hex(16)
        host_nonce = runtime.token_hex(32)
        prepared = runtime.prepare_artifacts(
            artifact_parent=artifact_parent_resolved,
            transaction_material=transaction_material,
            runner_bundle=runner_bundle,
            controller_worker_bundle=controller_worker_bundle,
            request_id=request_id,
            host_nonce=host_nonce,
            created_at_epoch_seconds=runtime.epoch(),
        )
        context.materialization = runtime.verify_materialization(prepared)

        prelaunch_host = runtime.inspect_host()
        differences = _host_evidence_differences(fresh_host, prelaunch_host)
        if not prelaunch_host.ok or differences:
            context.add(
                "execution_backend_host_evidence_changed",
                "Host evidence changed before Sandbox launch.",
                actual=";".join((*differences, *prelaunch_host.issue_codes)),
            )
            raise RuntimeError("host changed before launch")
        prelaunch_processes = runtime.snapshot_processes()
        _append_snapshot(
            context,
            phase="before_launch",
            elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000),
            launcher=None,
            processes=prelaunch_processes,
            runtime=runtime,
            force=True,
        )
        if prelaunch_processes:
            context.add(
                "compile_ast_composition_sandbox_instance_running",
                "A Sandbox instance appeared before launch.",
            )
            raise RuntimeError("sandbox appeared")
        context.materialization = runtime.verify_materialization(prepared)
        if executable_path is None:
            context.add(
                "compile_ast_composition_executable_missing",
                "Sandbox executable evidence is missing.",
            )
            raise RuntimeError("missing executable")

        launch_attempted = True
        launcher = runtime.launch(executable_path, prepared.wsb_path)
        context.sandbox_launched = True
        context.launcher_pid = int(getattr(launcher, "pid", 0))
        if context.launcher_pid <= 0:
            context.add(
                "compile_ast_composition_launcher_pid_invalid",
                "Windows Sandbox launcher PID is invalid.",
            )
            raise RuntimeError("launcher pid invalid")
        current = runtime.snapshot_processes()
        _append_snapshot(
            context,
            phase="after_launch",
            elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000),
            launcher=launcher,
            processes=current,
            runtime=runtime,
            force=True,
        )
        context.process_observed = bool(current)

        ready_deadline = runtime.monotonic() + DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS
        while runtime.monotonic() < ready_deadline:
            current = runtime.snapshot_processes()
            elapsed_ms = int((runtime.monotonic() - started_monotonic) * 1000)
            _append_snapshot(
                context,
                phase="waiting_for_ready",
                elapsed_ms=elapsed_ms,
                launcher=launcher,
                processes=current,
                runtime=runtime,
            )
            if current:
                context.process_observed = True
            if any(
                runtime.artifact_exists(path)
                for path, _ in _controller_transport_reserved_artifacts(prepared)
            ):
                context.add(
                    "compile_ast_composition_terminal_before_authorization",
                    "Reserved R4 transport evidence appeared before host authorization.",
                )
                raise RuntimeError("early terminal")
            if runtime.artifact_exists(prepared.bootstrap_failure_path) or runtime.artifact_exists(
                prepared.controller_failure_path
            ):
                context.add(
                    "compile_ast_composition_guest_failure_reported",
                    "An unsigned guest failure hint appeared before ready; it is non-authoritative.",
                )
                break
            if runtime.artifact_exists(prepared.ready_path):
                context.ready_received_ms = elapsed_ms
                break
            if runtime.launcher_exited(launcher) and not current:
                elapsed_seconds = max(0.0, runtime.monotonic() - started_monotonic)
                if context.process_observed or elapsed_seconds >= DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_PROCESS_APPEARANCE_GRACE_SECONDS:
                    context.add(
                        "compile_ast_composition_sandbox_exited_before_ready",
                        "Sandbox exited before ready evidence.",
                    )
                    break
            runtime.sleep(DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLL_INTERVAL_SECONDS)
        if context.ready_received_ms is None:
            if not context.issues:
                context.add(
                    "compile_ast_composition_ready_timeout",
                    "Sandbox did not produce ready evidence before timeout.",
                )
            raise RuntimeError("ready unavailable")

        ready_bytes, ready_sha256 = runtime.read_artifact(
            prepared.ready_path,
            max_bytes=COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME
            ],
            artifact_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME,
        )
        ready = parse_compile_ast_ready(ready_bytes)
        ready_payload = ready.to_dict()
        try:
            public_key_blob = base64.b64decode(
                ready_payload["public_key_blob_base64"],
                validate=True,
            )
        except (KeyError, TypeError, ValueError) as exc:
            context.add(
                "compile_ast_composition_ready_public_key_invalid",
                "Pinned R4 ready evidence does not contain a valid controller public key.",
                actual=f"{type(exc).__name__}:{exc}",
            )
            raise RuntimeError("ready public key invalid") from exc
        if _sha256(public_key_blob) != ready_payload["public_key_sha256"]:
            context.add(
                "compile_ast_composition_ready_public_key_hash_mismatch",
                "Pinned R4 ready public-key hash does not match its exact bytes.",
            )
            raise RuntimeError("ready public key hash mismatch")
        authorization_nonce = runtime.token_hex(32)
        authorization_observed_epoch = runtime.epoch()
        authorization_deadline_epoch = (
            int(authorization_observed_epoch)
            + DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS
        )
        authorize_payload = {
            "schema_version": 1,
            "request_id": request_id,
            "host_nonce": host_nonce,
            "request_sha256": prepared.request.sha256,
            "ready_sha256": ready.sha256,
            "public_key_sha256": ready_payload["public_key_sha256"],
            "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
            "runtime_lease_fingerprint": transaction_material.runtime_lease_fingerprint,
            "plan_fingerprint": transaction_material.plan_material.report.plan_fingerprint,
            "source_manifest_sha256": prepared.source_manifest.sha256,
            "authorization_nonce": authorization_nonce,
            "authorization_deadline_epoch": authorization_deadline_epoch,
            "allow_compile_ast": True,
            "execution_authorized": False,
        }
        authorize_bytes = encode_compile_ast_document("authorize", authorize_payload)
        context.pin_report = runtime.pin_transcript(
            expected_request_id=request_id,
            expected_host_nonce=host_nonce,
            expected_authorization_nonce=authorization_nonce,
            expected_source_manifest_sha256=prepared.source_manifest.sha256,
            expected_request_sha256=prepared.request.sha256,
            expected_plan_fingerprint=(
                transaction_material.plan_material.report.plan_fingerprint
            ),
            expected_runtime_lease_fingerprint=(
                transaction_material.runtime_lease_fingerprint
            ),
            authorization_observed_epoch=authorization_observed_epoch,
            source_manifest_bytes=prepared.source_manifest.canonical_bytes,
            request_bytes=prepared.request.canonical_bytes,
            ready_bytes=ready_bytes,
            authorize_bytes=authorize_bytes,
        )
        if not context.pin_report.ok:
            _add_verifier_issues(context, context.pin_report, prefix="pin")
            raise RuntimeError("pin failed")

        context.materialization = runtime.verify_materialization(prepared)
        current_ready, current_ready_sha256 = runtime.read_artifact(
            prepared.ready_path,
            max_bytes=COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME
            ],
            artifact_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME,
            expected_size=len(ready_bytes),
        )
        if current_ready != ready_bytes or current_ready_sha256 != ready_sha256:
            context.add(
                "compile_ast_composition_ready_changed_before_authorization",
                "Ready evidence changed before authorization publication.",
            )
            raise RuntimeError("ready changed")
        pre_worker_reserved_artifacts = tuple(
            name
            for path, name in _controller_transport_reserved_artifacts(prepared)
            if runtime.artifact_exists(path)
        )
        if pre_worker_reserved_artifacts:
            context.add(
                "compile_ast_composition_terminal_before_authorization",
                "Reserved R4 transport evidence appeared after pin but before publication.",
                actual=",".join(pre_worker_reserved_artifacts),
            )
            raise RuntimeError("early terminal after pin")

        authorize_sha256, authorize_commit_sha256 = runtime.publish_authorize(
            prepared.authorize_path,
            authorize_bytes,
        )
        context.authorization_published_ms = int(
            (runtime.monotonic() - started_monotonic) * 1000
        )

        terminal_timeout = (
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS
            + DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS
            + 30
        )
        terminal_deadline = runtime.monotonic() + terminal_timeout
        while runtime.monotonic() < terminal_deadline:
            current = runtime.snapshot_processes()
            elapsed_ms = int((runtime.monotonic() - started_monotonic) * 1000)
            _append_snapshot(
                context,
                phase="waiting_for_compile_ast_terminal",
                elapsed_ms=elapsed_ms,
                launcher=launcher,
                processes=current,
                runtime=runtime,
            )
            if current:
                context.process_observed = True
            if runtime.artifact_exists(prepared.result_path) and context.result_detected_ms is None:
                context.result_detected_ms = elapsed_ms
            if (
                runtime.artifact_exists(prepared.controller_evidence_payload_path)
                and runtime.artifact_exists(prepared.controller_evidence_signature_path)
            ):
                context.terminal_detected_ms = elapsed_ms
                break
            if runtime.launcher_exited(launcher) and not current:
                context.add(
                    "compile_ast_composition_sandbox_exited_before_terminal",
                    "Sandbox exited before complete terminal evidence.",
                )
                break
            runtime.sleep(DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLL_INTERVAL_SECONDS)
        if context.terminal_detected_ms is None and not context.issues:
            context.add(
                "compile_ast_composition_terminal_timeout",
                "Sandbox did not produce complete controller-signed R4 terminal evidence.",
            )

        shutdown_deadline = runtime.monotonic() + DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS
        consecutive_empty = 0
        while runtime.monotonic() < shutdown_deadline:
            current = runtime.snapshot_processes()
            elapsed_ms = int((runtime.monotonic() - started_monotonic) * 1000)
            _append_snapshot(
                context,
                phase="waiting_for_shutdown",
                elapsed_ms=elapsed_ms,
                launcher=launcher,
                processes=current,
                runtime=runtime,
            )
            try:
                launcher_exited_now = bool(
                    launcher is None or runtime.launcher_exited(launcher)
                )
            except Exception as exc:
                context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED_ACTIVE
                context.add(
                    "compile_ast_composition_launcher_state_unproven",
                    "Launcher state could not be proven during shutdown.",
                    actual=f"{type(exc).__name__}:{exc}",
                )
                raise RuntimeError("launcher state unproven") from exc
            if not current and launcher_exited_now:
                consecutive_empty += 1
                if consecutive_empty >= DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_EXIT_EMPTY_SCANS:
                    _record_all_processes_exited(context, elapsed_ms=elapsed_ms)
                    break
            else:
                consecutive_empty = 0
            runtime.sleep(DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLL_INTERVAL_SECONDS)
        current = runtime.snapshot_processes()
        launcher_exited_after_wait = bool(
            launcher is None or runtime.launcher_exited(launcher)
        )
        _append_snapshot(
            context,
            phase="shutdown_wait_complete",
            elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000),
            launcher=launcher,
            processes=current,
            runtime=runtime,
            force=True,
        )
        if current or not launcher_exited_after_wait:
            context.all_processes_exited = False
            context.all_processes_exited_ms = None
        if not context.all_processes_exited:
            context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED_ACTIVE
            context.add(
                "compile_ast_composition_shutdown_timeout",
                "Sandbox processes did not exit within grace period.",
                actual=",".join(f"{item.name}:{item.pid}" for item in current),
            )
            raise RuntimeError("sandbox remains active")
        if not context.process_observed:
            context.add(
                "compile_ast_composition_process_not_observed",
                "No known Sandbox process was observed.",
            )

        failure = _failure_artifact(runtime, prepared)
        if failure.present:
            failure_artifact_sha256 = failure.sha256
            context.add(
                "compile_ast_composition_guest_failure_artifact",
                "An unsigned guest failure artifact appeared; it is diagnostic only.",
                actual=failure.diagnostic,
            )

        if context.terminal_detected_ms is not None:
            context.materialization = runtime.verify_materialization(prepared)
            final_source_manifest, _ = _read_expected(
                runtime,
                prepared.source_manifest_path,
                name="source_manifest.json",
                expected=prepared.source_manifest.canonical_bytes,
                max_bytes=COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS[
                    "source_manifest.json"
                ],
            )
            final_request, _ = _read_expected(
                runtime,
                prepared.request_path,
                name="request.json",
                expected=prepared.request.canonical_bytes,
                max_bytes=COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS["request.json"],
            )
            ready_reads, final_ready_sha256 = _read_stable_pair(
                runtime,
                prepared.ready_path,
                name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME,
                max_bytes=COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS[
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME
                ],
                expected_size=len(ready_bytes),
            )
            final_authorize, final_authorize_sha256 = _read_expected(
                runtime,
                prepared.authorize_path,
                name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_FILE_NAME,
                expected=authorize_bytes,
                max_bytes=COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS[
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_FILE_NAME
                ],
            )
            commit_expected = _sha256(authorize_bytes).encode("ascii")
            _, final_commit_sha256 = _read_expected(
                runtime,
                prepared.authorize_commit_path,
                name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_COMMIT_FILE_NAME,
                expected=commit_expected,
                max_bytes=64,
            )
            evidence_payload_reads, controller_evidence_payload_sha256 = (
                _read_stable_pair(
                    runtime,
                    prepared.controller_evidence_payload_path,
                    name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
                    max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES,
                )
            )
            evidence_signature_reads, controller_evidence_signature_sha256 = (
                _read_stable_pair(
                    runtime,
                    prepared.controller_evidence_signature_path,
                    name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
                    max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
                    expected_size=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
                )
            )

            result_reads: tuple[bytes, bytes] | None = None
            terminal_payload_reads: tuple[bytes, bytes] | None = None
            terminal_signature_reads: tuple[bytes, bytes] | None = None
            if runtime.artifact_exists(prepared.result_path):
                result_reads, result_sha256 = _read_stable_pair(
                    runtime,
                    prepared.result_path,
                    name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
                    max_bytes=COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS[
                        DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME
                    ],
                )
            if runtime.artifact_exists(prepared.terminal_payload_path):
                terminal_payload_reads, terminal_payload_sha256 = _read_stable_pair(
                    runtime,
                    prepared.terminal_payload_path,
                    name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_TERMINAL_FILE_NAME,
                    max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES,
                )
            if runtime.artifact_exists(prepared.terminal_signature_path):
                terminal_signature_reads, terminal_signature_sha256 = _read_stable_pair(
                    runtime,
                    prepared.terminal_signature_path,
                    name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SIGNATURE_FILE_NAME,
                    max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
                    expected_size=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
                )

            if final_ready_sha256 != ready_sha256:
                context.add(
                    "compile_ast_composition_pinned_artifact_changed",
                    "Ready hash changed after exit.",
                )
            if final_authorize_sha256 != authorize_sha256:
                context.add(
                    "compile_ast_composition_pinned_artifact_changed",
                    "Authorization hash changed after exit.",
                )
            if final_commit_sha256 != authorize_commit_sha256:
                context.add(
                    "compile_ast_composition_authorization_commit_changed",
                    "Authorization commit marker changed after exit.",
                )

            context.controller_evidence_report = runtime.verify_controller_evidence(
                DeveloperTaskExecutionCompileAstControllerEvidenceExpectation(
                    request_id=request_id,
                    host_nonce=host_nonce,
                    request_sha256=prepared.request.sha256,
                    ready_sha256=ready_sha256,
                    authorize_sha256=authorize_sha256,
                    public_key_sha256=ready_payload["public_key_sha256"],
                    runtime_bundle_fingerprint=RUNTIME_BUNDLE_FINGERPRINT,
                    runtime_lease_fingerprint=(
                        transaction_material.runtime_lease_fingerprint
                    ),
                    plan_fingerprint=(
                        transaction_material.plan_material.report.plan_fingerprint
                    ),
                    source_manifest_sha256=prepared.source_manifest.sha256,
                ),
                public_key_blob=public_key_blob,
                pinned_ready_bytes=ready_bytes,
                post_exit_ready_reads=ready_reads,
                evidence_payload_reads=evidence_payload_reads,
                evidence_signature_reads=evidence_signature_reads,
                pre_worker_reserved_artifacts=pre_worker_reserved_artifacts,
                relayed_result_reads=result_reads,
                terminal_payload_reads=terminal_payload_reads,
                terminal_signature_reads=terminal_signature_reads,
            )
            if not context.controller_evidence_report.ok:
                _add_controller_evidence_issues(
                    context,
                    context.controller_evidence_report,
                )
            elif context.controller_evidence_report.status != "controller_signed_success":
                context.add(
                    "compile_ast_composition_controller_signed_failure",
                    "R4 controller produced an authoritative signed failure terminal.",
                    actual=context.controller_evidence_report.terminal_status,
                )
            elif (
                context.controller_evidence_report.terminal_status
                != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS
            ):
                context.add(
                    "compile_ast_composition_attested_pass_required",
                    "V1C2C2 accepts only the one-run attested-pass composition.",
                    actual=context.controller_evidence_report.terminal_status,
                )
            elif (
                result_reads is None
                or terminal_payload_reads is None
                or terminal_signature_reads is None
            ):
                context.add(
                    "compile_ast_composition_legacy_transcript_missing",
                    "Accepted R4 success requires the exact legacy V1C2B transcript artifacts.",
                )
            else:
                context.signed_report = runtime.verify_transcript(
                    context.pin_report,
                    source_manifest_bytes=final_source_manifest,
                    request_bytes=final_request,
                    ready_bytes=ready_reads[0],
                    authorize_bytes=final_authorize,
                    result_bytes=result_reads[0],
                    terminal_payload_bytes=terminal_payload_reads[0],
                    terminal_signature_bytes=terminal_signature_reads[0],
                )
                if not context.signed_report.ok:
                    _add_verifier_issues(context, context.signed_report, prefix="verify")
                elif (
                    context.signed_report.terminal_status
                    != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS
                    or not context.signed_report.boundary_ok
                    or not context.signed_report.check_passed
                ):
                    context.add(
                        "compile_ast_composition_attested_pass_required",
                        "V1C2C2 accepts only the one-run attested-pass composition.",
                        actual=(
                            f"{context.signed_report.terminal_status}:"
                            f"boundary={context.signed_report.boundary_ok}:"
                            f"check={context.signed_report.check_passed}"
                        ),
                    )
                else:
                    context.candidate_interpreter_executed = True
                    context.changed_source_processed = True
                    context.changed_source_ast_parsed = True
                    context.changed_source_compiled = True

        post_host = runtime.inspect_host()
        post_differences = _host_evidence_differences(fresh_host, post_host)
        if not post_host.ok or post_differences:
            context.add(
                "execution_backend_host_evidence_changed",
                "Host evidence changed during V1C2C2.",
                actual=";".join((*post_differences, *post_host.issue_codes)),
            )
        context.status = (
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED
            if not context.issues
            and context.materialization is not None
            and context.materialization.ok
            and context.pin_report is not None
            and context.pin_report.ok
            and context.controller_evidence_report is not None
            and context.controller_evidence_report.ok
            and context.controller_evidence_report.status == "controller_signed_success"
            and context.controller_evidence_report.terminal_status
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS
            and context.signed_report is not None
            and context.signed_report.ok
            and context.signed_report.terminal_status
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS
            and context.signed_report.boundary_ok
            and context.signed_report.check_passed
            else DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED
        )
    except (
        DeveloperTaskExecutionCompileAstCompositionFileSystemError,
        DeveloperTaskExecutionCompileAstContractError,
        DeveloperTaskExecutionCompileAstClaimTransactionError,
        DeveloperTaskExecutionCompileAstRunnerBundleError,
        DeveloperTaskExecutionCompileAstControllerWorkerBundleError,
        DeveloperTaskExecutionBackendLifecycleWindowsError,
    ) as exc:
        context.add(
            getattr(exc, "code", "compile_ast_composition_structured_error"),
            str(exc),
            actual=getattr(exc, "actual", ""),
        )
    except Exception as exc:
        if not context.issues:
            context.add(
                "compile_ast_composition_unexpected_error",
                "Unexpected V1C2C2 active composition failure.",
                actual=f"{type(exc).__name__}:{exc}",
            )
    finally:
        remaining: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...] = ()
        process_state_proven = not launch_attempted
        launcher_state_proven = not launch_attempted
        launcher_exited_final = not launch_attempted
        if launch_attempted:
            try:
                remaining = runtime.snapshot_processes()
                process_state_proven = True
            except Exception as exc:
                context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED_ACTIVE
                context.add(
                    "compile_ast_composition_process_state_unproven",
                    "Sandbox process state could not be proven during finalization.",
                    actual=f"{type(exc).__name__}:{exc}",
                )
            try:
                launcher_exited_final = bool(
                    launcher is None or runtime.launcher_exited(launcher)
                )
                launcher_state_proven = True
            except Exception as exc:
                context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED_ACTIVE
                context.add(
                    "compile_ast_composition_launcher_state_unproven",
                    "Launcher state could not be proven during finalization.",
                    actual=f"{type(exc).__name__}:{exc}",
                )
            if process_state_proven and launcher_state_proven and (
                remaining or not launcher_exited_final
            ):
                context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED_ACTIVE
                if remaining and executable_path is not None and context.observed_processes:
                    try:
                        context.termination = runtime.terminate(
                            tuple(context.observed_processes.values()),
                            executable=executable_path,
                        )
                    except Exception as exc:
                        context.add(
                            "compile_ast_composition_forced_cleanup_failed",
                            "Best-effort Sandbox cleanup failed.",
                            actual=f"{type(exc).__name__}:{exc}",
                        )
                    else:
                        deadline = runtime.monotonic() + DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_FORCE_CLEANUP_TIMEOUT_SECONDS
                        consecutive_empty = 0
                        while runtime.monotonic() < deadline:
                            try:
                                remaining = runtime.snapshot_processes()
                                launcher_exited_final = bool(
                                    launcher is None or runtime.launcher_exited(launcher)
                                )
                            except Exception as exc:
                                process_state_proven = False
                                launcher_state_proven = False
                                context.add(
                                    "compile_ast_composition_process_state_unproven",
                                    "Sandbox exit could not be proven after forced cleanup.",
                                    actual=f"{type(exc).__name__}:{exc}",
                                )
                                break
                            if not remaining and launcher_exited_final:
                                consecutive_empty += 1
                                if consecutive_empty >= DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_EXIT_EMPTY_SCANS:
                                    _record_all_processes_exited(
                                        context,
                                        elapsed_ms=int(
                                            (runtime.monotonic() - started_monotonic)
                                            * 1000
                                        ),
                                    )
                                    context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED
                                    break
                            else:
                                consecutive_empty = 0
                            runtime.sleep(DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLL_INTERVAL_SECONDS)

        if (
            prepared is not None
            and process_state_proven
            and launcher_state_proven
            and (not launch_attempted or context.all_processes_exited)
        ):
            failure = _failure_artifact(runtime, prepared)
            if failure.present and not failure_artifact_sha256:
                failure_artifact_sha256 = failure.sha256
                context.add(
                    "compile_ast_composition_guest_failure_artifact",
                    "An unsigned guest failure artifact appeared; it is diagnostic only.",
                    actual=failure.diagnostic,
                )

        if (
            prepared is not None
            and artifact_parent_resolved is not None
            and process_state_proven
            and launcher_state_proven
            and (not launch_attempted or context.all_processes_exited)
        ):
            try:
                cleanup_attempts = runtime.cleanup(
                    prepared,
                    artifact_parent=artifact_parent_resolved,
                )
                artifacts_removed = not os.path.lexists(prepared.root)
            except DeveloperTaskExecutionCompileAstCompositionFileSystemError as exc:
                context.add(exc.code, str(exc), actual=exc.actual)
                if context.status == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED:
                    context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED
            except Exception as exc:
                context.add(
                    "compile_ast_composition_artifact_cleanup_failed",
                    "V1C2C2 artifact cleanup failed unexpectedly.",
                    actual=f"{type(exc).__name__}:{exc}",
                )
                if context.status == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED:
                    context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED

        if prepared is not None:
            context.artifacts = _build_artifacts_report(
                prepared,
                materialization=context.materialization,
                ready_sha256=ready_sha256,
                authorize_sha256=authorize_sha256,
                authorize_commit_sha256=authorize_commit_sha256,
                result_sha256=result_sha256,
                terminal_payload_sha256=terminal_payload_sha256,
                terminal_signature_sha256=terminal_signature_sha256,
                controller_evidence_payload_sha256=(
                    controller_evidence_payload_sha256
                ),
                controller_evidence_signature_sha256=(
                    controller_evidence_signature_sha256
                ),
                failure_artifact_sha256=failure_artifact_sha256,
                removed=artifacts_removed,
                cleanup_attempts=cleanup_attempts,
            )
            if (
                context.status
                == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED
                and not context.artifacts.ok
            ):
                context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED
                context.add(
                    "compile_ast_composition_artifact_evidence_invalid",
                    "Final V1C2C2 artifact evidence is incomplete.",
                )
        if context.termination.attempted and context.status == DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED:
            context.status = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED
            context.add(
                "compile_ast_composition_forced_cleanup_invalidates_success",
                "Forced cleanup cannot become successful composition evidence.",
            )
        completed_at = runtime.epoch()
        total_ms = max(0, int((runtime.monotonic() - started_monotonic) * 1000))
        return context.report(completed_at=completed_at, total_ms=total_ms)


def attest_developer_task_execution_compile_ast_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionCompileAstCompositionReport:
    """Consume one fresh transaction and attest one active compile/AST pass."""

    if type(host_report) is not DeveloperTaskExecutionBackendHostReport:
        raise TypeError("host_report must be DeveloperTaskExecutionBackendHostReport")
    if type(transaction) is not DeveloperTaskExecutionCompileAstClaimTransaction:
        raise TypeError(
            "transaction must be DeveloperTaskExecutionCompileAstClaimTransaction"
        )
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")
    return _attest_developer_task_execution_compile_ast_composition(
        host_report,
        transaction,
        artifact_parent=artifact_parent,
        runtime=_CompileAstCompositionRuntime(),
    )
