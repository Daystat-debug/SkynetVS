from __future__ import annotations

"""V1B4C2B one-run active trusted CPython runtime composition."""

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
from modules.developer.developer_task_execution_runtime_attestation import (
    DeveloperTaskRuntimeAttestationPayloadBundle,
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
    build_developer_task_execution_runtime_attestation_payload,
)
from modules.developer.developer_task_execution_runtime_attestation_contract import (
    DeveloperTaskRuntimeAttestationContractError,
    DeveloperTaskRuntimeAttestationDocument,
    RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES,
    RUNTIME_ATTESTATION_READY_MAX_BYTES,
    RUNTIME_ATTESTATION_RESULT_MAX_BYTES,
    RUNTIME_ATTESTATION_SIGNATURE_BYTES,
    RUNTIME_ATTESTATION_TERMINAL_MAX_BYTES,
    parse_runtime_attestation_ready,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    DeveloperTaskRuntimeAttestationPayloadError,
    RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME,
    RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME,
    RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME,
    RUNTIME_ATTESTATION_CONTROLLER_FAILURE_FILE_NAME,
    RUNTIME_ATTESTATION_READY_FILE_NAME,
    RUNTIME_ATTESTATION_RESULT_FILE_NAME,
    RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS,
    RUNTIME_ATTESTATION_SIGNATURE_FILE_NAME,
    RUNTIME_ATTESTATION_TERMINAL_FILE_NAME,
    build_runtime_attestation_authorize,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    DeveloperTaskRuntimeAttestationPolicy,
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS,
    TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1,
    validate_trusted_python_runtime_attestation_policy,
)
from modules.developer.developer_task_execution_runtime_attestation_verifier import (
    DeveloperTaskRuntimeAttestationTranscriptPinReport,
    DeveloperTaskRuntimeAttestationTranscriptReport,
    pin_developer_task_execution_runtime_attestation_transcript,
    verify_developer_task_execution_runtime_attestation_transcript,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    DeveloperTaskPythonRuntimeBundle,
    DeveloperTaskPythonRuntimeBundleError,
    build_developer_task_execution_runtime_bundle,
)
from modules.developer.developer_task_execution_runtime_composition_fs import (
    RUNTIME_COMPOSITION_ARTIFACT_LIMITS,
    DeveloperTaskExecutionRuntimeCompositionFileSystemError,
    DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence,
    DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts,
    prepare_developer_task_execution_runtime_composition_artifacts,
    publish_developer_task_execution_runtime_composition_authorization,
    read_developer_task_execution_runtime_composition_artifact_bytes,
    remove_developer_task_execution_runtime_composition_artifacts,
    validate_developer_task_execution_runtime_composition_artifact_parent,
    verify_developer_task_execution_runtime_composition_materialization,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_TREE_MANIFEST_SHA256,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue


ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED = "active_trusted_runtime_attested"
ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED = "failed"
ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE = "failed_active"
_POLL_INTERVAL_SECONDS = 0.25
_PROCESS_APPEARANCE_GRACE_SECONDS = 5.0
_FORCE_CLEANUP_TIMEOUT_SECONDS = 10.0
_PROCESS_EXIT_CONSECUTIVE_EMPTY_SCANS = 3
_HOST_BOOT_EPOCH_QUANTIZATION_TOLERANCE_SECONDS = 1


@dataclass(frozen=True)
class _RuntimeCompositionFailureArtifact:
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
class DeveloperTaskExecutionRuntimeCompositionProcessSnapshot:
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
class DeveloperTaskExecutionRuntimeCompositionArtifacts:
    root: str
    input_root: str
    runtime_root: str
    control_root: str
    output_root: str
    request_path: str
    ready_path: str
    authorize_path: str
    authorize_commit_path: str
    runtime_result_path: str
    terminal_payload_path: str
    terminal_signature_path: str
    runtime_source_sha256: str
    runtime_bundle_fingerprint: str
    runtime_tree_manifest_sha256: str
    runtime_file_count: int
    runtime_total_bytes: int
    payload_bundle_fingerprint: str
    materialization_input_manifest_sha256: str
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    authorize_commit_sha256: str
    runtime_result_sha256: str
    terminal_payload_sha256: str
    terminal_signature_sha256: str
    failure_artifact_sha256: str
    removed: bool
    cleanup_attempts: int

    @property
    def ok(self) -> bool:
        return (
            self.runtime_source_sha256 == RUNTIME_SOURCE_SHA256
            and self.runtime_bundle_fingerprint == RUNTIME_BUNDLE_FINGERPRINT
            and self.runtime_tree_manifest_sha256 == RUNTIME_TREE_MANIFEST_SHA256
            and self.runtime_file_count == RUNTIME_BUNDLE_FILE_COUNT
            and self.runtime_total_bytes == RUNTIME_BUNDLE_TOTAL_BYTES
            and self.payload_bundle_fingerprint == RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT
            and len(self.materialization_input_manifest_sha256) == 64
            and len(self.request_sha256) == 64
            and len(self.ready_sha256) == 64
            and len(self.authorize_sha256) == 64
            and len(self.authorize_commit_sha256) == 64
            and len(self.runtime_result_sha256) == 64
            and len(self.terminal_payload_sha256) == 64
            and len(self.terminal_signature_sha256) == 64
            and not self.failure_artifact_sha256
            and self.removed
            and self.cleanup_attempts >= 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "input_root": self.input_root,
            "runtime_root": self.runtime_root,
            "control_root": self.control_root,
            "output_root": self.output_root,
            "paths": {
                "request": self.request_path,
                "ready": self.ready_path,
                "authorize": self.authorize_path,
                "authorize_commit": self.authorize_commit_path,
                "runtime_result": self.runtime_result_path,
                "terminal_payload": self.terminal_payload_path,
                "terminal_signature": self.terminal_signature_path,
            },
            "runtime": {
                "source_sha256": self.runtime_source_sha256,
                "bundle_fingerprint": self.runtime_bundle_fingerprint,
                "tree_manifest_sha256": self.runtime_tree_manifest_sha256,
                "file_count": self.runtime_file_count,
                "total_bytes": self.runtime_total_bytes,
            },
            "payload_bundle_fingerprint": self.payload_bundle_fingerprint,
            "materialization_input_manifest_sha256": self.materialization_input_manifest_sha256,
            "hashes": {
                "request_sha256": self.request_sha256,
                "ready_sha256": self.ready_sha256,
                "authorize_sha256": self.authorize_sha256,
                "authorize_commit_sha256": self.authorize_commit_sha256,
                "runtime_result_sha256": self.runtime_result_sha256,
                "terminal_payload_sha256": self.terminal_payload_sha256,
                "terminal_signature_sha256": self.terminal_signature_sha256,
                "failure_artifact_sha256": self.failure_artifact_sha256,
            },
            "removed": self.removed,
            "cleanup_attempts": self.cleanup_attempts,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionRuntimeCompositionReport:
    status: str
    backend_policy: DeveloperTaskExecutionBackendPolicy
    runtime_attestation_policy: DeveloperTaskRuntimeAttestationPolicy
    runtime_bundle_fingerprint: str
    payload_bundle_fingerprint: str
    host_boot_epoch_seconds: int
    host_executable_sha256: str
    started_at_epoch_seconds: float
    completed_at_epoch_seconds: float
    request: DeveloperTaskRuntimeAttestationDocument | None
    launcher_pid: int
    process_observed: bool
    all_processes_exited: bool
    termination: DeveloperTaskExecutionBackendTerminationResult
    ready_received_ms: int | None
    authorization_published_ms: int | None
    runtime_result_detected_ms: int | None
    terminal_detected_ms: int | None
    all_processes_exited_ms: int | None
    total_ms: int
    process_timeline: tuple[DeveloperTaskExecutionRuntimeCompositionProcessSnapshot, ...]
    materialization: DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence | None
    pin_report: DeveloperTaskRuntimeAttestationTranscriptPinReport | None
    signed_report: DeveloperTaskRuntimeAttestationTranscriptReport | None
    artifacts: DeveloperTaskExecutionRuntimeCompositionArtifacts | None
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            self.status == ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED
            and self.backend_policy == WINDOWS_SANDBOX_EXECUTION_POLICY_V1
            and self.runtime_attestation_policy
            == TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1
            and self.runtime_bundle_fingerprint == RUNTIME_BUNDLE_FINGERPRINT
            and self.payload_bundle_fingerprint
            == RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT
            and self.host_boot_epoch_seconds > 0
            and len(self.host_executable_sha256) == 64
            and self.started_at_epoch_seconds > 0
            and self.completed_at_epoch_seconds >= self.started_at_epoch_seconds
            and self.request is not None
            and self.launcher_pid > 0
            and self.process_observed
            and self.all_processes_exited
            and not self.termination.attempted
            and self.ready_received_ms is not None
            and self.authorization_published_ms is not None
            and self.runtime_result_detected_ms is not None
            and self.terminal_detected_ms is not None
            and self.all_processes_exited_ms is not None
            and self.total_ms >= self.all_processes_exited_ms
            and self.materialization is not None
            and self.materialization.ok
            and self.pin_report is not None
            and self.pin_report.ok
            and self.signed_report is not None
            and self.signed_report.ok
            and self.signed_report.runtime_result_verified
            and self.signed_report.terminal_verified
            and self.signed_report.signature_valid
            and self.artifacts is not None
            and self.artifacts.ok
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    @property
    def sandbox_launched(self) -> bool:
        return self.launcher_pid > 0

    @property
    def interpreter_executed(self) -> bool:
        return bool(
            self.signed_report is not None
            and self.signed_report.ok
            and self.signed_report.runtime_result_verified
        )

    @property
    def reusable_lease_issued(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "backend_id": self.backend_policy.backend_id,
            "backend_policy_fingerprint": self.backend_policy.fingerprint,
            "runtime_attestation_policy_fingerprint": self.runtime_attestation_policy.fingerprint,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "payload_bundle_fingerprint": self.payload_bundle_fingerprint,
            "host_boot_epoch_seconds": self.host_boot_epoch_seconds,
            "host_executable_sha256": self.host_executable_sha256,
            "started_at_epoch_seconds": self.started_at_epoch_seconds,
            "completed_at_epoch_seconds": self.completed_at_epoch_seconds,
            "request": self.request.to_dict() if self.request is not None else None,
            "launcher_pid": self.launcher_pid,
            "process_observed": self.process_observed,
            "all_processes_exited": self.all_processes_exited,
            "termination": self.termination.to_dict(),
            "timing": {
                "ready_received_ms": self.ready_received_ms,
                "authorization_published_ms": self.authorization_published_ms,
                "runtime_result_detected_ms": self.runtime_result_detected_ms,
                "terminal_detected_ms": self.terminal_detected_ms,
                "all_processes_exited_ms": self.all_processes_exited_ms,
                "total_ms": self.total_ms,
            },
            "process_timeline": [item.to_dict() for item in self.process_timeline],
            "materialization": (
                self.materialization.to_dict()
                if self.materialization is not None
                else None
            ),
            "pin_report": self.pin_report.to_dict() if self.pin_report is not None else None,
            "signed_report": (
                self.signed_report.to_dict() if self.signed_report is not None else None
            ),
            "artifacts": self.artifacts.to_dict() if self.artifacts is not None else None,
            "sandbox_launched": self.sandbox_launched,
            "interpreter_executed": self.interpreter_executed,
            "reusable_lease_issued": False,
            "execution_authorized": False,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


class _RuntimeCompositionRuntime:
    def inspect_host(self) -> DeveloperTaskExecutionBackendHostReport:
        return inspect_developer_task_execution_backend_host()

    def build_runtime_bundle(
        self,
        runtime_zip: Path,
        *,
        artifact_parent: Path,
    ) -> DeveloperTaskPythonRuntimeBundle:
        return build_developer_task_execution_runtime_bundle(
            runtime_zip,
            artifact_parent=artifact_parent,
        )

    def build_payload_bundle(self) -> DeveloperTaskRuntimeAttestationPayloadBundle:
        return build_developer_task_execution_runtime_attestation_payload()

    def prepare_artifacts(self, **kwargs: Any) -> DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts:
        return prepare_developer_task_execution_runtime_composition_artifacts(**kwargs)

    def verify_materialization(
        self,
        prepared: DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts,
    ) -> DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence:
        return verify_developer_task_execution_runtime_composition_materialization(prepared)

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
            timeout_seconds=_FORCE_CLEANUP_TIMEOUT_SECONDS,
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
        return read_developer_task_execution_runtime_composition_artifact_bytes(
            path,
            max_bytes=max_bytes,
            artifact_name=artifact_name,
            expected_size=expected_size,
        )

    def publish_authorize(self, path: Path, data: bytes) -> tuple[str, str]:
        return publish_developer_task_execution_runtime_composition_authorization(path, data)

    def pin_transcript(self, **kwargs: Any) -> DeveloperTaskRuntimeAttestationTranscriptPinReport:
        return pin_developer_task_execution_runtime_attestation_transcript(**kwargs)

    def verify_transcript(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> DeveloperTaskRuntimeAttestationTranscriptReport:
        return verify_developer_task_execution_runtime_attestation_transcript(*args, **kwargs)

    def cleanup(
        self,
        prepared: DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts,
        *,
        artifact_parent: Path,
    ) -> int:
        return remove_developer_task_execution_runtime_composition_artifacts(
            prepared.root,
            artifact_parent=artifact_parent,
            initial_metadata=prepared.root_metadata,
        )

    def monotonic(self) -> float:
        return time.monotonic()

    def epoch(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class _RuntimeCompositionContext:
    def __init__(self, *, started_at: float) -> None:
        self.started_at = started_at
        self.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED
        self.runtime_bundle_fingerprint = ""
        self.payload_bundle_fingerprint = ""
        self.host_boot_epoch_seconds = 0
        self.host_executable_sha256 = ""
        self.request: DeveloperTaskRuntimeAttestationDocument | None = None
        self.launcher_pid = 0
        self.process_observed = False
        self.all_processes_exited = False
        self.termination = _empty_termination()
        self.ready_received_ms: int | None = None
        self.authorization_published_ms: int | None = None
        self.runtime_result_detected_ms: int | None = None
        self.terminal_detected_ms: int | None = None
        self.all_processes_exited_ms: int | None = None
        self.timeline: list[DeveloperTaskExecutionRuntimeCompositionProcessSnapshot] = []
        self.observed_processes: dict[
            tuple[str, int, int], DeveloperTaskExecutionBackendProcessEvidence
        ] = {}
        self.materialization: DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence | None = None
        self.pin_report: DeveloperTaskRuntimeAttestationTranscriptPinReport | None = None
        self.signed_report: DeveloperTaskRuntimeAttestationTranscriptReport | None = None
        self.artifacts: DeveloperTaskExecutionRuntimeCompositionArtifacts | None = None
        self.issues: list[DeveloperTaskPreflightIssue] = []

    def add(
        self,
        code: str,
        message: str,
        *,
        check: str = "execution_runtime_composition",
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

    def report(
        self,
        *,
        completed_at: float,
        total_ms: int,
    ) -> DeveloperTaskExecutionRuntimeCompositionReport:
        return DeveloperTaskExecutionRuntimeCompositionReport(
            status=self.status,
            backend_policy=WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
            runtime_attestation_policy=TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1,
            runtime_bundle_fingerprint=self.runtime_bundle_fingerprint,
            payload_bundle_fingerprint=self.payload_bundle_fingerprint,
            host_boot_epoch_seconds=self.host_boot_epoch_seconds,
            host_executable_sha256=self.host_executable_sha256,
            started_at_epoch_seconds=self.started_at,
            completed_at_epoch_seconds=completed_at,
            request=self.request,
            launcher_pid=self.launcher_pid,
            process_observed=self.process_observed,
            all_processes_exited=self.all_processes_exited,
            termination=self.termination,
            ready_received_ms=self.ready_received_ms,
            authorization_published_ms=self.authorization_published_ms,
            runtime_result_detected_ms=self.runtime_result_detected_ms,
            terminal_detected_ms=self.terminal_detected_ms,
            all_processes_exited_ms=self.all_processes_exited_ms,
            total_ms=total_ms,
            process_timeline=tuple(self.timeline),
            materialization=self.materialization,
            pin_report=self.pin_report,
            signed_report=self.signed_report,
            artifacts=self.artifacts,
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
        executable.path if executable is not None else "",
        executable.version if executable is not None else "",
        executable.size_bytes if executable is not None else 0,
        executable.mtime_ns if executable is not None else 0,
        executable.sha256 if executable is not None else "",
    )


def _host_evidence_differences(
    expected: DeveloperTaskExecutionBackendHostReport,
    actual: DeveloperTaskExecutionBackendHostReport,
) -> tuple[str, ...]:
    differences: list[str] = []
    boot_delta = abs(
        int(expected.host_boot_epoch_seconds)
        - int(actual.host_boot_epoch_seconds)
    )
    if boot_delta > _HOST_BOOT_EPOCH_QUANTIZATION_TOLERANCE_SECONDS:
        differences.append(
            "host_boot_epoch_seconds:"
            f"{expected.host_boot_epoch_seconds}->"
            f"{actual.host_boot_epoch_seconds}"
        )

    expected_key = _host_key(expected)
    actual_key = _host_key(actual)
    labels = (
        "backend_id",
        "policy_fingerprint",
        "host_platform",
        "host_architecture",
        "process_bitness",
        "windows_build",
        "executable_path",
        "executable_version",
        "executable_size_bytes",
        "executable_mtime_ns",
        "executable_sha256",
    )
    for label, expected_value, actual_value in zip(
        labels,
        expected_key,
        actual_key,
        strict=True,
    ):
        if expected_value != actual_value:
            differences.append(
                f"{label}:{expected_value!r}->{actual_value!r}"
            )
    return tuple(differences)


def _append_snapshot(
    context: _RuntimeCompositionContext,
    *,
    phase: str,
    elapsed_ms: int,
    launcher: Any | None,
    processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...],
    runtime: _RuntimeCompositionRuntime,
    force: bool = False,
) -> None:
    for item in processes:
        context.observed_processes[item.identity_key] = item
    key = tuple(item.identity_key for item in processes)
    previous = (
        tuple(item.identity_key for item in context.timeline[-1].processes)
        if context.timeline
        else None
    )
    if force or key != previous:
        exited: bool | None = None
        if launcher is not None:
            try:
                exited = runtime.launcher_exited(launcher)
            except Exception:
                exited = None
        context.timeline.append(
            DeveloperTaskExecutionRuntimeCompositionProcessSnapshot(
                phase=phase,
                elapsed_ms=max(0, int(elapsed_ms)),
                launcher_exited=exited,
                processes=processes,
            )
        )


def _record_all_processes_exited(
    context: _RuntimeCompositionContext,
    *,
    elapsed_ms: int,
) -> None:
    context.all_processes_exited = True
    if context.all_processes_exited_ms is None:
        context.all_processes_exited_ms = max(0, int(elapsed_ms))


def _add_verifier_issues(
    context: _RuntimeCompositionContext,
    report: DeveloperTaskRuntimeAttestationTranscriptPinReport
    | DeveloperTaskRuntimeAttestationTranscriptReport,
    *,
    prefix: str,
) -> None:
    for issue in report.issues:
        context.add(
            issue.code,
            issue.message,
            check=f"{prefix}.{issue.check}",
            expected=issue.expected,
            actual=issue.actual,
        )


def _read_expected(
    runtime: _RuntimeCompositionRuntime,
    path: Path,
    *,
    name: str,
    expected: bytes,
    max_bytes: int | None = None,
) -> tuple[bytes, str]:
    raw, sha256 = runtime.read_artifact(
        path,
        max_bytes=max_bytes or max(len(expected), 1),
        artifact_name=name,
        expected_size=len(expected),
    )
    if raw != expected:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_pinned_artifact_changed",
            "Pinned V1B4C2B artifact bytes changed.",
            actual=name,
        )
    return raw, sha256


def _failure_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate failure field: {key}")
        result[key] = value
    return result


def _failure_text(value: Any, *, name: str, max_length: int) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValueError(f"invalid {name}")
    if any(
        not character.isascii()
        or not (character.isalnum() or character in "._-")
        for character in value
    ):
        raise ValueError(f"invalid {name}")
    return value


def _failure_artifact(
    runtime: _RuntimeCompositionRuntime,
    prepared: DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts,
) -> _RuntimeCompositionFailureArtifact:
    for name, path in (
        (
            RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME,
            prepared.bootstrap_failure_path,
        ),
        (
            RUNTIME_ATTESTATION_CONTROLLER_FAILURE_FILE_NAME,
            prepared.controller_failure_path,
        ),
    ):
        if not runtime.artifact_exists(path):
            continue
        try:
            raw, sha256 = runtime.read_artifact(
                path,
                max_bytes=RUNTIME_COMPOSITION_ARTIFACT_LIMITS[name],
                artifact_name=name,
            )
        except Exception as exc:
            return _RuntimeCompositionFailureArtifact(
                file_name=name,
                diagnostic_error=f"read:{type(exc).__name__}",
            )
        try:
            payload = json.loads(
                raw.decode("utf-8", errors="strict"),
                object_pairs_hook=_failure_json_object,
            )
            if not isinstance(payload, dict):
                raise ValueError("failure artifact is not an object")
            if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
                raise ValueError("failure schema mismatch")
            if payload.get("execution_authorized") is not False:
                raise ValueError("failure authorization mismatch")
            expected_request_id = (
                ""
                if name == RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME
                else str(prepared.request.field("request_id"))
            )
            if payload.get("request_id") != expected_request_id:
                raise ValueError("failure request mismatch")
            stage = _failure_text(
                payload.get("stage"),
                name="failure stage",
                max_length=64,
            )
            error_type = _failure_text(
                payload.get("error_type"),
                name="failure error type",
                max_length=128,
            )
            error_code = _failure_text(
                payload.get("error_code"),
                name="failure error code",
                max_length=128,
            )
        except Exception as exc:
            return _RuntimeCompositionFailureArtifact(
                file_name=name,
                sha256=sha256,
                diagnostic_error=f"parse:{type(exc).__name__}",
            )
        return _RuntimeCompositionFailureArtifact(
            file_name=name,
            sha256=sha256,
            stage=stage,
            error_type=error_type,
            error_code=error_code,
        )
    return _RuntimeCompositionFailureArtifact()


def _record_failure_artifact(
    context: _RuntimeCompositionContext,
    failure: _RuntimeCompositionFailureArtifact,
) -> None:
    if not failure.present:
        return
    actual = failure.diagnostic
    for index, issue in enumerate(context.issues):
        if issue.code != "runtime_composition_guest_failure_reported":
            continue
        context.issues[index] = DeveloperTaskPreflightIssue(
            code=issue.code,
            check=issue.check,
            message=issue.message,
            expected=issue.expected,
            actual=actual,
        )
        return
    context.add(
        "runtime_composition_guest_failure_reported",
        "Trusted guest emitted a failure artifact.",
        actual=actual,
    )


def _build_artifacts_report(
    prepared: DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts,
    *,
    materialization: DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence | None,
    ready_sha256: str,
    authorize_sha256: str,
    authorize_commit_sha256: str,
    runtime_result_sha256: str,
    terminal_payload_sha256: str,
    terminal_signature_sha256: str,
    failure_artifact_sha256: str,
    removed: bool,
    cleanup_attempts: int,
) -> DeveloperTaskExecutionRuntimeCompositionArtifacts:
    return DeveloperTaskExecutionRuntimeCompositionArtifacts(
        root=str(prepared.root),
        input_root=str(prepared.input_root),
        runtime_root=str(prepared.runtime_root),
        control_root=str(prepared.control_root),
        output_root=str(prepared.output_root),
        request_path=str(prepared.request_path),
        ready_path=str(prepared.ready_path),
        authorize_path=str(prepared.authorize_path),
        authorize_commit_path=str(prepared.authorize_commit_path),
        runtime_result_path=str(prepared.runtime_result_path),
        terminal_payload_path=str(prepared.terminal_payload_path),
        terminal_signature_path=str(prepared.terminal_signature_path),
        runtime_source_sha256=prepared.runtime_bundle.report.source_sha256,
        runtime_bundle_fingerprint=prepared.runtime_bundle.report.bundle_fingerprint,
        runtime_tree_manifest_sha256=(
            materialization.runtime_tree_manifest_sha256
            if materialization is not None
            else ""
        ),
        runtime_file_count=(
            materialization.runtime_file_count if materialization is not None else 0
        ),
        runtime_total_bytes=(
            materialization.runtime_total_bytes if materialization is not None else 0
        ),
        payload_bundle_fingerprint=prepared.payload_bundle.payload_fingerprint,
        materialization_input_manifest_sha256=(
            materialization.input_manifest_sha256 if materialization is not None else ""
        ),
        request_sha256=prepared.request.sha256,
        ready_sha256=ready_sha256,
        authorize_sha256=authorize_sha256,
        authorize_commit_sha256=authorize_commit_sha256,
        runtime_result_sha256=runtime_result_sha256,
        terminal_payload_sha256=terminal_payload_sha256,
        terminal_signature_sha256=terminal_signature_sha256,
        failure_artifact_sha256=failure_artifact_sha256,
        removed=removed,
        cleanup_attempts=cleanup_attempts,
    )


def _attest_developer_task_execution_runtime_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    runtime_zip: Path,
    *,
    artifact_parent: Path,
    runtime: _RuntimeCompositionRuntime,
) -> DeveloperTaskExecutionRuntimeCompositionReport:
    started_at = runtime.epoch()
    started_monotonic = runtime.monotonic()
    context = _RuntimeCompositionContext(started_at=started_at)
    artifact_parent_resolved: Path | None = None
    runtime_bundle: DeveloperTaskPythonRuntimeBundle | None = None
    payload_bundle: DeveloperTaskRuntimeAttestationPayloadBundle | None = None
    prepared: DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts | None = None
    fresh_host: DeveloperTaskExecutionBackendHostReport | None = None
    executable_path: Path | None = None
    launcher: Any | None = None
    launch_attempted = False
    process_state_proven = True
    cleanup_attempts = 0
    artifacts_removed = False

    ready_bytes: bytes | None = None
    ready_sha256 = ""
    authorize_bytes: bytes | None = None
    authorize_sha256 = ""
    authorize_commit_sha256 = ""
    runtime_result_sha256 = ""
    terminal_payload_sha256 = ""
    terminal_signature_sha256 = ""
    failure_artifact_sha256 = ""

    try:
        backend_errors = validate_execution_backend_policy(
            WINDOWS_SANDBOX_EXECUTION_POLICY_V1
        )
        if backend_errors:
            context.add(
                "runtime_composition_backend_policy_invalid",
                "Canonical Windows Sandbox backend policy is invalid.",
                actual=",".join(backend_errors),
            )
            raise RuntimeError("invalid backend policy")
        validate_trusted_python_runtime_attestation_policy(
            TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1
        )

        if not host_report.ok:
            context.add(
                "execution_backend_host_report_failed",
                "Successful V1B1 host evidence is required.",
                actual=",".join(host_report.issue_codes),
            )
            raise RuntimeError("failed host report")
        if (
            host_report.policy != WINDOWS_SANDBOX_EXECUTION_POLICY_V1
            or host_report.policy_fingerprint
            != WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint
        ):
            context.add(
                "execution_backend_host_report_invalid",
                "Host report does not match the canonical backend policy.",
            )
            raise RuntimeError("invalid host report")

        artifact_parent_resolved = (
            validate_developer_task_execution_runtime_composition_artifact_parent(
                artifact_parent
            )
        )
        fresh_host = runtime.inspect_host()
        if not fresh_host.ok:
            context.add(
                "execution_backend_host_report_failed",
                "Fresh V1B1 host inspection failed.",
                actual=",".join(fresh_host.issue_codes),
            )
            raise RuntimeError("fresh host inspection failed")
        host_differences = _host_evidence_differences(host_report, fresh_host)
        if host_differences:
            context.add(
                "execution_backend_host_evidence_changed",
                "Host capability evidence changed before V1B4C2B preparation.",
                actual=";".join(host_differences),
            )
            raise RuntimeError("host evidence changed")

        context.host_boot_epoch_seconds = fresh_host.host_boot_epoch_seconds
        context.host_executable_sha256 = (
            fresh_host.executable.sha256 if fresh_host.executable is not None else ""
        )
        executable_path = (
            Path(fresh_host.executable.path)
            if fresh_host.executable is not None
            else None
        )

        baseline = runtime.snapshot_processes()
        _append_snapshot(
            context,
            phase="before_materialization",
            elapsed_ms=0,
            launcher=None,
            processes=baseline,
            runtime=runtime,
            force=True,
        )
        if baseline:
            context.add(
                "runtime_composition_sandbox_instance_running",
                "A Windows Sandbox instance is already running.",
                actual=",".join(f"{item.name}:{item.pid}" for item in baseline),
            )
            raise RuntimeError("sandbox already running")

        runtime_bundle = runtime.build_runtime_bundle(
            runtime_zip,
            artifact_parent=artifact_parent_resolved,
        )
        if not runtime_bundle.ok:
            context.add(
                "runtime_composition_runtime_bundle_invalid",
                "Canonical V1B4B runtime capability is invalid.",
            )
            raise RuntimeError("invalid runtime bundle")
        context.runtime_bundle_fingerprint = runtime_bundle.report.bundle_fingerprint

        payload_bundle = runtime.build_payload_bundle()
        if not payload_bundle.ok:
            context.add(
                "runtime_composition_payload_bundle_invalid",
                "Canonical V1B4C1 payload capability is invalid.",
            )
            raise RuntimeError("invalid payload bundle")
        context.payload_bundle_fingerprint = payload_bundle.payload_fingerprint

        request_id = secrets.token_hex(16)
        host_nonce = secrets.token_hex(32)
        request_created_at = runtime.epoch()
        prepared = runtime.prepare_artifacts(
            artifact_parent=artifact_parent_resolved,
            runtime_bundle=runtime_bundle,
            payload_bundle=payload_bundle,
            request_id=request_id,
            host_nonce=host_nonce,
            created_at_epoch_seconds=request_created_at,
        )
        context.request = prepared.request
        context.materialization = runtime.verify_materialization(prepared)

        prelaunch_host = runtime.inspect_host()
        prelaunch_differences = _host_evidence_differences(
            fresh_host,
            prelaunch_host,
        )
        if not prelaunch_host.ok or prelaunch_differences:
            details = [*prelaunch_differences]
            details.extend(
                f"issue_code:{code}" for code in prelaunch_host.issue_codes
            )
            context.add(
                "execution_backend_host_evidence_changed",
                "Host capability evidence changed before V1B4C2B launch.",
                actual=";".join(details),
            )
            raise RuntimeError("host evidence changed before launch")
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
                "runtime_composition_sandbox_instance_running",
                "A Windows Sandbox instance appeared before V1B4C2B launch.",
                actual=",".join(
                    f"{item.name}:{item.pid}" for item in prelaunch_processes
                ),
            )
            raise RuntimeError("sandbox appeared before launch")
        context.materialization = runtime.verify_materialization(prepared)

        if executable_path is None:
            context.add(
                "runtime_composition_executable_missing",
                "Sandbox executable evidence is missing.",
            )
            raise RuntimeError("missing sandbox executable")
        launch_attempted = True
        launcher = runtime.launch(executable_path, prepared.wsb_path)
        context.launcher_pid = int(getattr(launcher, "pid", 0))
        if context.launcher_pid <= 0:
            context.add(
                "runtime_composition_launcher_pid_invalid",
                "Windows Sandbox launcher PID is invalid.",
            )
            raise RuntimeError("invalid launcher PID")

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

        ready_deadline = runtime.monotonic() + RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS
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
                for path in (
                    prepared.runtime_result_path,
                    prepared.terminal_payload_path,
                    prepared.terminal_signature_path,
                )
            ):
                context.add(
                    "runtime_composition_terminal_before_authorization",
                    "Runtime or terminal evidence appeared before host authorization.",
                )
                raise RuntimeError("early terminal evidence")
            if runtime.artifact_exists(prepared.bootstrap_failure_path) or runtime.artifact_exists(
                prepared.controller_failure_path
            ):
                context.add(
                    "runtime_composition_guest_failure_reported",
                    "Trusted guest reported failure before ready evidence.",
                )
                break
            if runtime.artifact_exists(prepared.ready_path):
                context.ready_received_ms = elapsed_ms
                break
            if runtime.launcher_exited(launcher) and not current:
                elapsed_seconds = max(0.0, runtime.monotonic() - started_monotonic)
                if context.process_observed or elapsed_seconds >= _PROCESS_APPEARANCE_GRACE_SECONDS:
                    context.add(
                        "runtime_composition_sandbox_exited_before_ready",
                        "Windows Sandbox exited before producing ready evidence.",
                    )
                    break
            runtime.sleep(_POLL_INTERVAL_SECONDS)

        if context.ready_received_ms is None:
            if not context.issues:
                context.add(
                    "runtime_composition_ready_timeout",
                    "Windows Sandbox did not produce ready evidence before timeout.",
                    actual=str(RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS),
                )
            raise RuntimeError("ready unavailable")

        ready_bytes, ready_sha256 = runtime.read_artifact(
            prepared.ready_path,
            max_bytes=RUNTIME_ATTESTATION_READY_MAX_BYTES,
            artifact_name=RUNTIME_ATTESTATION_READY_FILE_NAME,
        )
        ready = parse_runtime_attestation_ready(ready_bytes)
        authorization_nonce = secrets.token_hex(32)
        authorization_observed_epoch = runtime.epoch()
        authorization_deadline_epoch = (
            int(authorization_observed_epoch)
            + RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS
        )
        authorize = build_runtime_attestation_authorize(
            request=prepared.request,
            ready=ready,
            authorization_nonce=authorization_nonce,
            authorization_deadline_epoch=authorization_deadline_epoch,
        )
        authorize_bytes = authorize.canonical_bytes
        authorize_sha256 = authorize.sha256
        context.pin_report = runtime.pin_transcript(
            expected_request_id=request_id,
            expected_host_nonce=host_nonce,
            expected_authorization_nonce=authorization_nonce,
            expected_request_sha256=prepared.request.sha256,
            authorization_observed_epoch=authorization_observed_epoch,
            wsb_bytes=prepared.wsb_bytes,
            request_bytes=prepared.request.canonical_bytes,
            ready_bytes=ready_bytes,
            authorize_bytes=authorize_bytes,
        )
        if not context.pin_report.ok:
            _add_verifier_issues(context, context.pin_report, prefix="pin")
            raise RuntimeError("runtime transcript pinning failed")

        context.materialization = runtime.verify_materialization(prepared)
        current_ready, current_ready_sha256 = runtime.read_artifact(
            prepared.ready_path,
            max_bytes=RUNTIME_ATTESTATION_READY_MAX_BYTES,
            artifact_name=RUNTIME_ATTESTATION_READY_FILE_NAME,
            expected_size=len(ready_bytes),
        )
        if current_ready != ready_bytes or current_ready_sha256 != ready_sha256:
            context.add(
                "runtime_composition_ready_changed_before_authorization",
                "Ready evidence changed before authorization publication.",
            )
            raise RuntimeError("ready changed")
        if any(
            runtime.artifact_exists(path)
            for path in (
                prepared.runtime_result_path,
                prepared.terminal_payload_path,
                prepared.terminal_signature_path,
            )
        ):
            context.add(
                "runtime_composition_terminal_before_authorization",
                "Runtime or terminal evidence appeared before authorization publication.",
            )
            raise RuntimeError("early terminal evidence after pin")

        authorize_sha256, authorize_commit_sha256 = runtime.publish_authorize(
            prepared.authorize_path,
            authorize_bytes,
        )
        context.authorization_published_ms = int(
            (runtime.monotonic() - started_monotonic) * 1000
        )

        terminal_deadline = runtime.monotonic() + RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS
        while runtime.monotonic() < terminal_deadline:
            current = runtime.snapshot_processes()
            elapsed_ms = int((runtime.monotonic() - started_monotonic) * 1000)
            _append_snapshot(
                context,
                phase="waiting_for_runtime_terminal",
                elapsed_ms=elapsed_ms,
                launcher=launcher,
                processes=current,
                runtime=runtime,
            )
            if current:
                context.process_observed = True
            if runtime.artifact_exists(prepared.runtime_result_path):
                if context.runtime_result_detected_ms is None:
                    context.runtime_result_detected_ms = elapsed_ms
            if runtime.artifact_exists(prepared.bootstrap_failure_path) or runtime.artifact_exists(
                prepared.controller_failure_path
            ):
                context.add(
                    "runtime_composition_guest_failure_reported",
                    "Trusted guest reported failure after authorization.",
                )
                break
            if (
                runtime.artifact_exists(prepared.runtime_result_path)
                and runtime.artifact_exists(prepared.terminal_payload_path)
                and runtime.artifact_exists(prepared.terminal_signature_path)
            ):
                context.runtime_result_detected_ms = (
                    context.runtime_result_detected_ms or elapsed_ms
                )
                context.terminal_detected_ms = elapsed_ms
                break
            if runtime.launcher_exited(launcher) and not current:
                context.add(
                    "runtime_composition_sandbox_exited_before_terminal",
                    "Windows Sandbox exited before producing complete terminal evidence.",
                )
                break
            runtime.sleep(_POLL_INTERVAL_SECONDS)

        if context.terminal_detected_ms is None and not context.issues:
            context.add(
                "runtime_composition_terminal_timeout",
                "Windows Sandbox did not produce complete runtime terminal evidence before timeout.",
                actual=str(RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS),
            )

        shutdown_deadline = runtime.monotonic() + RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS
        consecutive_empty_scans = 0
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
                context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE
                context.add(
                    "runtime_composition_launcher_state_unproven",
                    "Windows Sandbox launcher state could not be proven during shutdown.",
                    actual=f"{type(exc).__name__}:{exc}",
                )
                raise RuntimeError("launcher state unproven") from exc
            if not current and launcher_exited_now:
                consecutive_empty_scans += 1
                if (
                    consecutive_empty_scans
                    >= _PROCESS_EXIT_CONSECUTIVE_EMPTY_SCANS
                ):
                    _record_all_processes_exited(context, elapsed_ms=elapsed_ms)
                    break
            else:
                consecutive_empty_scans = 0
            runtime.sleep(_POLL_INTERVAL_SECONDS)

        current = runtime.snapshot_processes()
        try:
            launcher_exited_after_wait = bool(
                launcher is None or runtime.launcher_exited(launcher)
            )
        except Exception as exc:
            context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE
            context.add(
                "runtime_composition_launcher_state_unproven",
                "Windows Sandbox launcher state could not be proven after shutdown wait.",
                actual=f"{type(exc).__name__}:{exc}",
            )
            launcher_exited_after_wait = False
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
            context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE
            context.add(
                "runtime_composition_shutdown_timeout",
                "Windows Sandbox processes did not exit within the V1B4C2B grace period.",
                actual=",".join(f"{item.name}:{item.pid}" for item in current),
            )
            raise RuntimeError("sandbox remains active")
        if not context.process_observed:
            context.add(
                "runtime_composition_process_not_observed",
                "No known Windows Sandbox process was observed.",
            )

        failure_artifact = _failure_artifact(runtime, prepared)
        if failure_artifact.present:
            failure_artifact_sha256 = failure_artifact.sha256
            _record_failure_artifact(context, failure_artifact)

        if context.terminal_detected_ms is not None:
            context.materialization = runtime.verify_materialization(prepared)
            final_ready, final_ready_sha256 = _read_expected(
                runtime,
                prepared.ready_path,
                name=RUNTIME_ATTESTATION_READY_FILE_NAME,
                expected=ready_bytes,
                max_bytes=RUNTIME_ATTESTATION_READY_MAX_BYTES,
            )
            final_authorize, final_authorize_sha256 = _read_expected(
                runtime,
                prepared.authorize_path,
                name=RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME,
                expected=authorize_bytes,
                max_bytes=RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES,
            )
            commit_expected = _sha256(authorize_bytes).encode("ascii")
            _, final_commit_sha256 = _read_expected(
                runtime,
                prepared.authorize_commit_path,
                name=RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME,
                expected=commit_expected,
                max_bytes=64,
            )
            runtime_result_bytes, runtime_result_sha256 = runtime.read_artifact(
                prepared.runtime_result_path,
                max_bytes=RUNTIME_ATTESTATION_RESULT_MAX_BYTES,
                artifact_name=RUNTIME_ATTESTATION_RESULT_FILE_NAME,
            )
            terminal_payload_bytes, terminal_payload_sha256 = runtime.read_artifact(
                prepared.terminal_payload_path,
                max_bytes=RUNTIME_ATTESTATION_TERMINAL_MAX_BYTES,
                artifact_name=RUNTIME_ATTESTATION_TERMINAL_FILE_NAME,
            )
            terminal_signature_bytes, terminal_signature_sha256 = runtime.read_artifact(
                prepared.terminal_signature_path,
                max_bytes=RUNTIME_ATTESTATION_SIGNATURE_BYTES,
                artifact_name=RUNTIME_ATTESTATION_SIGNATURE_FILE_NAME,
                expected_size=RUNTIME_ATTESTATION_SIGNATURE_BYTES,
            )
            if final_ready_sha256 != ready_sha256:
                context.add(
                    "runtime_composition_pinned_artifact_changed",
                    "Pinned ready hash changed after Sandbox exit.",
                )
            if final_authorize_sha256 != authorize_sha256:
                context.add(
                    "runtime_composition_pinned_artifact_changed",
                    "Pinned authorization hash changed after Sandbox exit.",
                )
            if final_commit_sha256 != authorize_commit_sha256:
                context.add(
                    "runtime_composition_authorization_commit_changed",
                    "Authorization commit marker changed after publication.",
                )

            context.signed_report = runtime.verify_transcript(
                context.pin_report,
                wsb_bytes=prepared.wsb_bytes,
                request_bytes=prepared.request.canonical_bytes,
                ready_bytes=final_ready,
                authorize_bytes=final_authorize,
                runtime_result_bytes=runtime_result_bytes,
                terminal_payload_bytes=terminal_payload_bytes,
                terminal_signature_bytes=terminal_signature_bytes,
            )
            if not context.signed_report.ok:
                _add_verifier_issues(context, context.signed_report, prefix="verify")

        post_host = runtime.inspect_host()
        post_host_differences = (
            ("fresh_host_missing",)
            if fresh_host is None
            else _host_evidence_differences(fresh_host, post_host)
        )
        if not post_host.ok or post_host_differences:
            details = [*post_host_differences]
            details.extend(f"issue_code:{code}" for code in post_host.issue_codes)
            context.add(
                "execution_backend_host_evidence_changed",
                "Host capability evidence changed during V1B4C2B.",
                actual=";".join(details),
            )

        context.status = (
            ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED
            if not context.issues
            and context.materialization is not None
            and context.materialization.ok
            and context.pin_report is not None
            and context.pin_report.ok
            and context.signed_report is not None
            and context.signed_report.ok
            else ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED
        )
    except (
        DeveloperTaskExecutionRuntimeCompositionFileSystemError,
        DeveloperTaskRuntimeAttestationPayloadError,
        DeveloperTaskRuntimeAttestationContractError,
        DeveloperTaskPythonRuntimeBundleError,
        DeveloperTaskExecutionBackendLifecycleWindowsError,
    ) as exc:
        context.add(
            getattr(exc, "code", "runtime_composition_structured_error"),
            str(exc),
            actual=getattr(exc, "actual", ""),
        )
    except Exception as exc:
        if not context.issues:
            context.add(
                "runtime_composition_unexpected_error",
                "Unexpected V1B4C2B active composition failure.",
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
                process_state_proven = False
                context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE
                context.add(
                    "runtime_composition_process_state_unproven",
                    "Sandbox process state could not be proven during finalization.",
                    actual=f"{type(exc).__name__}:{exc}",
                )
            try:
                launcher_exited_final = bool(
                    launcher is None or runtime.launcher_exited(launcher)
                )
                launcher_state_proven = True
            except Exception as exc:
                launcher_state_proven = False
                context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE
                context.add(
                    "runtime_composition_launcher_state_unproven",
                    "Sandbox launcher state could not be proven during finalization.",
                    actual=f"{type(exc).__name__}:{exc}",
                )

        if (
            launch_attempted
            and process_state_proven
            and launcher_state_proven
            and context.issues
            and not context.all_processes_exited
        ):
            graceful_deadline = (
                runtime.monotonic() + RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS
            )
            consecutive_empty_scans = 0
            while runtime.monotonic() < graceful_deadline:
                runtime.sleep(_POLL_INTERVAL_SECONDS)
                try:
                    remaining = runtime.snapshot_processes()
                except Exception as exc:
                    process_state_proven = False
                    context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE
                    context.add(
                        "runtime_composition_process_state_unproven",
                        "Sandbox process state could not be proven during bounded failure shutdown.",
                        actual=f"{type(exc).__name__}:{exc}",
                    )
                    break
                try:
                    launcher_exited_final = bool(
                        launcher is None or runtime.launcher_exited(launcher)
                    )
                except Exception as exc:
                    launcher_state_proven = False
                    context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE
                    context.add(
                        "runtime_composition_launcher_state_unproven",
                        "Sandbox launcher state could not be proven during bounded failure shutdown.",
                        actual=f"{type(exc).__name__}:{exc}",
                    )
                    break
                _append_snapshot(
                    context,
                    phase="waiting_for_failure_shutdown",
                    elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000),
                    launcher=launcher,
                    processes=remaining,
                    runtime=runtime,
                )
                if not remaining and launcher_exited_final:
                    consecutive_empty_scans += 1
                    if (
                        consecutive_empty_scans
                        >= _PROCESS_EXIT_CONSECUTIVE_EMPTY_SCANS
                    ):
                        _record_all_processes_exited(
                            context,
                            elapsed_ms=int(
                                (runtime.monotonic() - started_monotonic) * 1000
                            ),
                        )
                        if context.status == ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE:
                            context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED
                        break
                else:
                    consecutive_empty_scans = 0

        if (
            process_state_proven
            and launcher_state_proven
            and (remaining or not launcher_exited_final)
        ):
            context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE
            if remaining and executable_path is not None and context.observed_processes:
                try:
                    context.termination = runtime.terminate(
                        tuple(context.observed_processes.values()),
                        executable=executable_path,
                    )
                except Exception as exc:
                    context.add(
                        "runtime_composition_forced_cleanup_failed",
                        "Best-effort Sandbox cleanup failed.",
                        actual=f"{type(exc).__name__}:{exc}",
                    )
                else:
                    confirmation_deadline = runtime.monotonic() + _FORCE_CLEANUP_TIMEOUT_SECONDS
                    consecutive_empty_scans = 0
                    while runtime.monotonic() < confirmation_deadline:
                        try:
                            remaining = runtime.snapshot_processes()
                            launcher_exited_final = bool(
                                launcher is None or runtime.launcher_exited(launcher)
                            )
                        except Exception as exc:
                            process_state_proven = False
                            launcher_state_proven = False
                            context.add(
                                "runtime_composition_process_state_unproven",
                                "Sandbox exit could not be proven after forced cleanup.",
                                actual=f"{type(exc).__name__}:{exc}",
                            )
                            break
                        if not remaining and launcher_exited_final:
                            consecutive_empty_scans += 1
                            if (
                                consecutive_empty_scans
                                >= _PROCESS_EXIT_CONSECUTIVE_EMPTY_SCANS
                            ):
                                _record_all_processes_exited(
                                    context,
                                    elapsed_ms=int(
                                        (runtime.monotonic() - started_monotonic) * 1000
                                    ),
                                )
                                context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED
                                break
                        else:
                            consecutive_empty_scans = 0
                        runtime.sleep(_POLL_INTERVAL_SECONDS)
            elif not launcher_exited_final:
                context.add(
                    "runtime_composition_launcher_still_active",
                    "Windows Sandbox launcher remained active without a fully proven process set.",
                )
            else:
                context.add(
                    "runtime_composition_forced_cleanup_unavailable",
                    "Active Sandbox processes were not bound to observed identities.",
                    actual=",".join(f"{item.name}:{item.pid}" for item in remaining),
                )

        if (
            prepared is not None
            and process_state_proven
            and launcher_state_proven
            and (not launch_attempted or context.all_processes_exited)
        ):
            failure_artifact = _failure_artifact(runtime, prepared)
            if failure_artifact.present:
                failure_artifact_sha256 = failure_artifact.sha256
                _record_failure_artifact(context, failure_artifact)

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
            except DeveloperTaskExecutionRuntimeCompositionFileSystemError as exc:
                if exc.code not in {item.code for item in context.issues}:
                    context.add(exc.code, str(exc), actual=exc.actual)
                if context.status == ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED:
                    context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED
            except Exception as exc:
                context.add(
                    "runtime_composition_artifact_cleanup_failed",
                    "V1B4C2B artifact cleanup failed unexpectedly.",
                    actual=f"{type(exc).__name__}:{exc}",
                )
                if context.status == ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED:
                    context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED

        if prepared is not None:
            context.artifacts = _build_artifacts_report(
                prepared,
                materialization=context.materialization,
                ready_sha256=ready_sha256,
                authorize_sha256=authorize_sha256,
                authorize_commit_sha256=authorize_commit_sha256,
                runtime_result_sha256=runtime_result_sha256,
                terminal_payload_sha256=terminal_payload_sha256,
                terminal_signature_sha256=terminal_signature_sha256,
                failure_artifact_sha256=failure_artifact_sha256,
                removed=artifacts_removed,
                cleanup_attempts=cleanup_attempts,
            )
            if (
                context.status == ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED
                and not context.artifacts.ok
            ):
                context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED
                context.add(
                    "runtime_composition_artifact_evidence_invalid",
                    "Final V1B4C2B artifact evidence is incomplete or inconsistent.",
                )

        if context.termination.attempted and context.status == ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED:
            context.status = ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED
            context.add(
                "runtime_composition_forced_cleanup_invalidates_success",
                "Forced Sandbox cleanup cannot become a successful attestation path.",
            )

        completed_at = runtime.epoch()
        total_ms = max(0, int((runtime.monotonic() - started_monotonic) * 1000))
        return context.report(completed_at=completed_at, total_ms=total_ms)


def attest_developer_task_execution_runtime_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    runtime_zip: Path,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionRuntimeCompositionReport:
    """Actively attest only the fixed benign pinned CPython runtime probe."""

    if not isinstance(host_report, DeveloperTaskExecutionBackendHostReport):
        raise TypeError("host_report must be DeveloperTaskExecutionBackendHostReport")
    if not isinstance(runtime_zip, Path):
        raise TypeError("runtime_zip must be pathlib.Path")
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")
    return _attest_developer_task_execution_runtime_composition(
        host_report,
        runtime_zip,
        artifact_parent=artifact_parent,
        runtime=_RuntimeCompositionRuntime(),
    )
