from __future__ import annotations

"""One-run V1B3D Windows Sandbox lifecycle and signed-boundary composition."""

import hashlib
import os
import secrets
import stat
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
from modules.developer.developer_task_execution_boundary_composition_payload import (
    COMPOSITION_ARTIFACT_LIMITS,
    COMPOSITION_ARTIFACT_PREFIX,
    COMPOSITION_AUTHORIZATION_TIMEOUT_SECONDS,
    COMPOSITION_AUTHORIZE_COMMIT_NAME,
    COMPOSITION_AUTHORIZE_NAME,
    COMPOSITION_BOOTSTRAP_FAILURE_NAME,
    COMPOSITION_BOOTSTRAP_NAME,
    COMPOSITION_CONTROLLER_FAILURE_NAME,
    COMPOSITION_CONTROLLER_NAME,
    COMPOSITION_POLICY_NAME,
    COMPOSITION_READY_NAME,
    COMPOSITION_REQUEST_NAME,
    COMPOSITION_SHUTDOWN_GRACE_SECONDS,
    COMPOSITION_TERMINAL_PAYLOAD_NAME,
    COMPOSITION_TERMINAL_SIGNATURE_NAME,
    COMPOSITION_WORKER_RESULT_NAME,
    COMPOSITION_WSB_NAME,
    DeveloperTaskExecutionBoundaryCompositionPayloadError,
    build_composition_authorize,
    build_composition_bootstrap_script,
    build_composition_controller_script,
    build_composition_request,
    build_composition_wsb_config,
    read_composition_artifact_bytes,
)
from modules.developer.developer_task_execution_boundary_contract import (
    DeveloperTaskExecutionBoundaryContractError,
    DeveloperTaskExecutionBoundaryDocument,
    parse_boundary_ready,
)
from modules.developer.developer_task_execution_boundary_policy import (
    DeveloperTaskExecutionBoundaryPolicy,
    WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
    validate_execution_boundary_policy,
)
from modules.developer.developer_task_execution_boundary_verifier import (
    DeveloperTaskExecutionSignedTranscriptPinReport,
    DeveloperTaskExecutionSignedTranscriptReport,
    pin_developer_task_execution_signed_transcript,
    verify_developer_task_execution_signed_transcript,
)
from modules.developer.developer_task_execution_boundary_worker import (
    DeveloperTaskExecutionBoundaryWorkerBundle,
    build_developer_task_execution_boundary_worker_bundle,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_workspace_cleanup_fs import (
    DeveloperTaskWorkspaceCleanupFileSystemError,
    absolute_path,
    remove_verified_workspace,
    validate_workspace_parent,
)


ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED = "active_signed_boundary_attested"
ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED = "failed"
ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED_ACTIVE = "failed_active"
_POLL_INTERVAL_SECONDS = 0.25
_PROCESS_APPEARANCE_GRACE_SECONDS = 5.0
_FORCE_CLEANUP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class DeveloperTaskExecutionBoundaryCompositionProcessSnapshot:
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
class DeveloperTaskExecutionBoundaryCompositionArtifacts:
    root: str
    input_root: str
    control_root: str
    output_root: str
    request_path: str
    ready_path: str
    authorize_path: str
    worker_result_path: str
    terminal_payload_path: str
    terminal_signature_path: str
    policy_sha256: str
    bootstrap_sha256: str
    controller_sha256: str
    native_helper_sha256: str
    worker_source_sha256: str
    wsb_sha256: str
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    worker_result_sha256: str
    terminal_payload_sha256: str
    terminal_signature_sha256: str
    failure_artifact_sha256: str
    removed: bool
    cleanup_attempts: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "input_root": self.input_root,
            "control_root": self.control_root,
            "output_root": self.output_root,
            "paths": {
                "request": self.request_path,
                "ready": self.ready_path,
                "authorize": self.authorize_path,
                "worker_result": self.worker_result_path,
                "terminal_payload": self.terminal_payload_path,
                "terminal_signature": self.terminal_signature_path,
            },
            "hashes": {
                "policy_sha256": self.policy_sha256,
                "bootstrap_sha256": self.bootstrap_sha256,
                "controller_sha256": self.controller_sha256,
                "native_helper_sha256": self.native_helper_sha256,
                "worker_source_sha256": self.worker_source_sha256,
                "wsb_sha256": self.wsb_sha256,
                "request_sha256": self.request_sha256,
                "ready_sha256": self.ready_sha256,
                "authorize_sha256": self.authorize_sha256,
                "worker_result_sha256": self.worker_result_sha256,
                "terminal_payload_sha256": self.terminal_payload_sha256,
                "terminal_signature_sha256": self.terminal_signature_sha256,
                "failure_artifact_sha256": self.failure_artifact_sha256,
            },
            "removed": self.removed,
            "cleanup_attempts": self.cleanup_attempts,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionBoundaryCompositionReport:
    status: str
    backend_policy: DeveloperTaskExecutionBackendPolicy
    boundary_policy: DeveloperTaskExecutionBoundaryPolicy
    worker_bundle_fingerprint: str
    host_boot_epoch_seconds: int
    host_executable_sha256: str
    started_at_epoch_seconds: float
    completed_at_epoch_seconds: float
    attestation_expires_at_epoch_seconds: float
    request: DeveloperTaskExecutionBoundaryDocument | None
    launcher_pid: int
    process_observed: bool
    all_processes_exited: bool
    termination: DeveloperTaskExecutionBackendTerminationResult
    ready_received_ms: int | None
    authorization_published_ms: int | None
    terminal_detected_ms: int | None
    all_processes_exited_ms: int | None
    total_ms: int
    process_timeline: tuple[DeveloperTaskExecutionBoundaryCompositionProcessSnapshot, ...]
    pin_report: DeveloperTaskExecutionSignedTranscriptPinReport | None
    signed_report: DeveloperTaskExecutionSignedTranscriptReport | None
    artifacts: DeveloperTaskExecutionBoundaryCompositionArtifacts | None
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            self.status == ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED
            and self.backend_policy == WINDOWS_SANDBOX_EXECUTION_POLICY_V1
            and self.boundary_policy == WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1
            and len(self.worker_bundle_fingerprint) == 64
            and self.host_boot_epoch_seconds > 0
            and len(self.host_executable_sha256) == 64
            and self.started_at_epoch_seconds > 0
            and self.completed_at_epoch_seconds >= self.started_at_epoch_seconds
            and self.attestation_expires_at_epoch_seconds > self.completed_at_epoch_seconds
            and self.request is not None
            and self.launcher_pid > 0
            and self.process_observed
            and self.all_processes_exited
            and not self.termination.attempted
            and self.ready_received_ms is not None
            and self.authorization_published_ms is not None
            and self.terminal_detected_ms is not None
            and self.all_processes_exited_ms is not None
            and self.total_ms >= self.all_processes_exited_ms
            and self.pin_report is not None
            and self.pin_report.ok
            and self.signed_report is not None
            and self.signed_report.ok
            and self.artifacts is not None
            and self.artifacts.removed
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    @property
    def execution_authorized(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "backend_id": self.backend_policy.backend_id,
            "backend_policy": self.backend_policy.to_dict(),
            "backend_policy_fingerprint": self.backend_policy.fingerprint,
            "boundary_policy": self.boundary_policy.to_dict(),
            "boundary_policy_fingerprint": self.boundary_policy.fingerprint,
            "worker_bundle_fingerprint": self.worker_bundle_fingerprint,
            "host_boot_epoch_seconds": self.host_boot_epoch_seconds,
            "host_executable_sha256": self.host_executable_sha256,
            "started_at_epoch_seconds": self.started_at_epoch_seconds,
            "completed_at_epoch_seconds": self.completed_at_epoch_seconds,
            "attestation_expires_at_epoch_seconds": self.attestation_expires_at_epoch_seconds,
            "request": self.request.to_dict() if self.request is not None else None,
            "launcher_pid": self.launcher_pid,
            "process_observed": self.process_observed,
            "all_processes_exited": self.all_processes_exited,
            "termination": self.termination.to_dict(),
            "timing": {
                "ready_received_ms": self.ready_received_ms,
                "authorization_published_ms": self.authorization_published_ms,
                "terminal_detected_ms": self.terminal_detected_ms,
                "all_processes_exited_ms": self.all_processes_exited_ms,
                "total_ms": self.total_ms,
            },
            "process_timeline": [item.to_dict() for item in self.process_timeline],
            "pin_report": self.pin_report.to_dict() if self.pin_report is not None else None,
            "signed_report": self.signed_report.to_dict() if self.signed_report is not None else None,
            "artifacts": self.artifacts.to_dict() if self.artifacts is not None else None,
            "execution_authorized": False,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


@dataclass(frozen=True)
class _PreparedArtifacts:
    root: Path
    root_metadata: os.stat_result
    input_root: Path
    control_root: Path
    output_root: Path
    policy_path: Path
    bootstrap_path: Path
    controller_path: Path
    native_helper_path: Path
    worker_source_path: Path
    wsb_path: Path
    request_path: Path
    ready_path: Path
    authorize_path: Path
    worker_result_path: Path
    terminal_payload_path: Path
    terminal_signature_path: Path
    bootstrap_failure_path: Path
    controller_failure_path: Path
    policy_bytes: bytes
    bootstrap_bytes: bytes
    controller_bytes: bytes
    native_helper_bytes: bytes
    worker_source_bytes: bytes
    wsb_bytes: bytes
    request: DeveloperTaskExecutionBoundaryDocument


class _CompositionRuntime:
    def inspect_host(self) -> DeveloperTaskExecutionBackendHostReport:
        return inspect_developer_task_execution_backend_host()

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
        return read_composition_artifact_bytes(
            path,
            max_bytes=max_bytes,
            artifact_name=artifact_name,
            expected_size=expected_size,
        )

    def publish_authorize(self, path: Path, data: bytes) -> None:
        _write_committed_authorization(path, data)

    def pin_transcript(self, **kwargs: Any) -> DeveloperTaskExecutionSignedTranscriptPinReport:
        return pin_developer_task_execution_signed_transcript(**kwargs)

    def verify_transcript(self, *args: Any, **kwargs: Any) -> DeveloperTaskExecutionSignedTranscriptReport:
        return verify_developer_task_execution_signed_transcript(*args, **kwargs)

    def monotonic(self) -> float:
        return time.monotonic()

    def epoch(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class _CompositionContext:
    def __init__(
        self,
        backend_policy: DeveloperTaskExecutionBackendPolicy,
        boundary_policy: DeveloperTaskExecutionBoundaryPolicy,
        worker_bundle: DeveloperTaskExecutionBoundaryWorkerBundle,
        started_at: float,
    ) -> None:
        self.backend_policy = backend_policy
        self.boundary_policy = boundary_policy
        self.worker_bundle = worker_bundle
        self.started_at = started_at
        self.status = ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED
        self.host_boot_epoch_seconds = 0
        self.host_executable_sha256 = ""
        self.request: DeveloperTaskExecutionBoundaryDocument | None = None
        self.launcher_pid = 0
        self.process_observed = False
        self.all_processes_exited = False
        self.termination = _empty_termination()
        self.ready_received_ms: int | None = None
        self.authorization_published_ms: int | None = None
        self.terminal_detected_ms: int | None = None
        self.all_processes_exited_ms: int | None = None
        self.timeline: list[DeveloperTaskExecutionBoundaryCompositionProcessSnapshot] = []
        self.observed_processes: dict[tuple[str, int, int], DeveloperTaskExecutionBackendProcessEvidence] = {}
        self.pin_report: DeveloperTaskExecutionSignedTranscriptPinReport | None = None
        self.signed_report: DeveloperTaskExecutionSignedTranscriptReport | None = None
        self.artifacts: DeveloperTaskExecutionBoundaryCompositionArtifacts | None = None
        self.issues: list[DeveloperTaskPreflightIssue] = []

    def add(
        self,
        code: str,
        message: str,
        *,
        check: str = "execution_boundary_composition",
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

    def report(self, *, completed_at: float, total_ms: int) -> DeveloperTaskExecutionBoundaryCompositionReport:
        expires = (
            completed_at + self.backend_policy.attestation_ttl_seconds
            if self.status == ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED
            else 0.0
        )
        return DeveloperTaskExecutionBoundaryCompositionReport(
            status=self.status,
            backend_policy=self.backend_policy,
            boundary_policy=self.boundary_policy,
            worker_bundle_fingerprint=self.worker_bundle.bundle_fingerprint,
            host_boot_epoch_seconds=self.host_boot_epoch_seconds,
            host_executable_sha256=self.host_executable_sha256,
            started_at_epoch_seconds=self.started_at,
            completed_at_epoch_seconds=completed_at,
            attestation_expires_at_epoch_seconds=expires,
            request=self.request,
            launcher_pid=self.launcher_pid,
            process_observed=self.process_observed,
            all_processes_exited=self.all_processes_exited,
            termination=self.termination,
            ready_received_ms=self.ready_received_ms,
            authorization_published_ms=self.authorization_published_ms,
            terminal_detected_ms=self.terminal_detected_ms,
            all_processes_exited_ms=self.all_processes_exited_ms,
            total_ms=total_ms,
            process_timeline=tuple(self.timeline),
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
        report.host_boot_epoch_seconds,
        executable.path if executable else "",
        executable.version if executable else "",
        executable.size_bytes if executable else 0,
        executable.mtime_ns if executable else 0,
        executable.sha256 if executable else "",
    )


def _validate_artifact_parent(parent: Path) -> Path:
    resolved = absolute_path(parent)
    try:
        validate_workspace_parent(resolved)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            exc.code.replace("workspace_parent", "boundary_composition_artifact_parent"),
            "V1B3D artifact parent is unsafe.",
            actual=exc.actual,
        ) from exc
    for ancestor in (resolved, *resolved.parents):
        try:
            git_entry = os.lstat(ancestor / ".git")
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                "boundary_composition_artifact_parent_metadata_failed",
                "V1B3D artifact parent Git boundary could not be inspected.",
                actual=f"{type(exc).__name__}: {exc}",
            ) from exc
        if stat.S_ISDIR(git_entry.st_mode) or stat.S_ISREG(git_entry.st_mode):
            raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                "boundary_composition_artifact_parent_inside_git_repository",
                "V1B3D artifacts must not be created inside a Git repository.",
                actual=str(resolved),
            )
    return resolved


def _write_new_file(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_write_failed",
            "V1B3D artifact could not be written.",
            actual=f"{path}:{type(exc).__name__}:{exc}",
        ) from exc


def _write_committed_authorization(path: Path, data: bytes) -> None:
    commit_path = path.with_name(COMPOSITION_AUTHORIZE_COMMIT_NAME)
    existing = [str(item) for item in (path, commit_path) if os.path.lexists(item)]
    if existing:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_authorization_already_exists",
            "V1B3D authorization data or commit marker already exists before publication.",
            actual=",".join(existing),
        )

    # Rename/move operations into an actively mapped Windows Sandbox folder can
    # remain blocked for the entire session. Publish with a two-file commit
    # protocol instead: direct-create the exact authorization bytes, verify them,
    # then direct-create a 64-byte SHA-256 marker. The guest waits for the marker
    # and accepts the authorization only when its exact bytes match that hash.
    expected_sha256 = _sha256(data)
    commit_bytes = expected_sha256.encode("ascii")
    try:
        _write_new_file(path, data)
        published, published_sha256 = read_composition_artifact_bytes(
            path,
            max_bytes=COMPOSITION_ARTIFACT_LIMITS[COMPOSITION_AUTHORIZE_NAME],
            artifact_name=COMPOSITION_AUTHORIZE_NAME,
            expected_size=len(data),
        )
        if published != data or published_sha256 != expected_sha256:
            raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                "boundary_composition_authorization_publish_verification_failed",
                "V1B3D authorization bytes do not match the pinned publication.",
                actual=str(path),
            )

        # Creating the exact hash marker is the publication linearization point.
        # Do not perform any fallible I/O after it: once the marker is visible,
        # the guest may consume the already verified authorization bytes.
        _write_new_file(commit_path, commit_bytes)
    except DeveloperTaskExecutionBoundaryCompositionPayloadError as exc:
        if exc.code.startswith("boundary_composition_authorization_"):
            raise
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_authorization_publish_failed",
            "V1B3D authorization could not be published with its hash commit marker.",
            actual=f"{exc.code}:{exc.actual}",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_authorization_publish_failed",
            "V1B3D authorization could not be published with its hash commit marker.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc


def _create_artifacts(
    *,
    parent: Path,
    backend_policy: DeveloperTaskExecutionBackendPolicy,
    boundary_policy: DeveloperTaskExecutionBoundaryPolicy,
    worker_bundle: DeveloperTaskExecutionBoundaryWorkerBundle,
    request_id: str,
    host_nonce: str,
    created_at: float,
) -> _PreparedArtifacts:
    root: Path | None = None
    for _ in range(16):
        candidate = parent / f"{COMPOSITION_ARTIFACT_PREFIX}{request_id[:8]}-{secrets.token_hex(8)}"
        try:
            candidate.mkdir(mode=0o700, exist_ok=False)
            root = candidate
            break
        except FileExistsError:
            continue
        except OSError as exc:
            raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                "boundary_composition_artifact_root_create_failed",
                "V1B3D artifact root could not be created.",
                actual=f"{type(exc).__name__}: {exc}",
            ) from exc
    if root is None:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_root_collision",
            "A unique V1B3D artifact root could not be allocated.",
        )

    try:
        input_root = root / "input"
        control_root = root / "control"
        output_root = root / "output"
        input_root.mkdir(mode=0o700)
        control_root.mkdir(mode=0o700)
        output_root.mkdir(mode=0o700)

        policy_bytes = boundary_policy.canonical_bytes()
        bootstrap_bytes = build_composition_bootstrap_script()
        controller_bytes = build_composition_controller_script(
            backend_policy=backend_policy,
            boundary_policy=boundary_policy,
            worker_bundle=worker_bundle,
        )
        native_helper_bytes = worker_bundle.native_helper.exact_bytes()
        worker_source_bytes = worker_bundle.worker_probe.exact_bytes()
        wsb_bytes = build_composition_wsb_config(
            backend_policy,
            input_root=input_root,
            control_root=control_root,
            output_root=output_root,
        )

        policy_path = input_root / COMPOSITION_POLICY_NAME
        bootstrap_path = input_root / COMPOSITION_BOOTSTRAP_NAME
        controller_path = input_root / COMPOSITION_CONTROLLER_NAME
        native_helper_path = input_root / worker_bundle.native_helper.file_name
        worker_source_path = input_root / worker_bundle.worker_probe.file_name
        wsb_path = input_root / COMPOSITION_WSB_NAME
        for path, data in (
            (policy_path, policy_bytes),
            (bootstrap_path, bootstrap_bytes),
            (controller_path, controller_bytes),
            (native_helper_path, native_helper_bytes),
            (worker_source_path, worker_source_bytes),
            (wsb_path, wsb_bytes),
        ):
            _write_new_file(path, data)

        request = build_composition_request(
            backend_policy=backend_policy,
            boundary_policy=boundary_policy,
            request_id=request_id,
            host_nonce=host_nonce,
            created_at_epoch_seconds=created_at,
            policy_sha256=_sha256(policy_bytes),
            bootstrap_sha256=_sha256(bootstrap_bytes),
            controller_sha256=_sha256(controller_bytes),
            worker_source_sha256=_sha256(worker_source_bytes),
            wsb_sha256=_sha256(wsb_bytes),
        )
        request_path = input_root / COMPOSITION_REQUEST_NAME
        _write_new_file(request_path, request.canonical_bytes)
        return _PreparedArtifacts(
            root=root,
            root_metadata=os.lstat(root),
            input_root=input_root,
            control_root=control_root,
            output_root=output_root,
            policy_path=policy_path,
            bootstrap_path=bootstrap_path,
            controller_path=controller_path,
            native_helper_path=native_helper_path,
            worker_source_path=worker_source_path,
            wsb_path=wsb_path,
            request_path=request_path,
            ready_path=output_root / COMPOSITION_READY_NAME,
            authorize_path=control_root / COMPOSITION_AUTHORIZE_NAME,
            worker_result_path=output_root / COMPOSITION_WORKER_RESULT_NAME,
            terminal_payload_path=output_root / COMPOSITION_TERMINAL_PAYLOAD_NAME,
            terminal_signature_path=output_root / COMPOSITION_TERMINAL_SIGNATURE_NAME,
            bootstrap_failure_path=output_root / COMPOSITION_BOOTSTRAP_FAILURE_NAME,
            controller_failure_path=output_root / COMPOSITION_CONTROLLER_FAILURE_NAME,
            policy_bytes=policy_bytes,
            bootstrap_bytes=bootstrap_bytes,
            controller_bytes=controller_bytes,
            native_helper_bytes=native_helper_bytes,
            worker_source_bytes=worker_source_bytes,
            wsb_bytes=wsb_bytes,
            request=request,
        )
    except Exception as original:
        try:
            metadata = os.lstat(root)
            _cleanup_artifacts(root, parent=parent, initial_metadata=metadata)
        except Exception as cleanup_error:
            raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                "boundary_composition_artifact_preparation_cleanup_failed",
                "Partially prepared V1B3D artifacts could not be removed safely.",
                actual=f"{type(cleanup_error).__name__}: {cleanup_error}",
            ) from original
        raise


def _cleanup_artifacts(
    root: Path,
    *,
    parent: Path,
    initial_metadata: os.stat_result,
) -> int:
    root_resolved = absolute_path(root)
    parent_resolved = absolute_path(parent)
    if root_resolved.parent != parent_resolved or not root_resolved.name.startswith(
        COMPOSITION_ARTIFACT_PREFIX
    ):
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_cleanup_scope_invalid",
            "V1B3D artifact cleanup target is outside the verified scope.",
            actual=str(root_resolved),
        )
    try:
        removal = remove_verified_workspace(root_resolved, initial_metadata)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_cleanup_failed",
            "V1B3D artifact cleanup failed.",
            actual=f"{exc.code}:{exc.actual};attempts={exc.attempts}",
        ) from exc
    return removal.attempts


def _append_snapshot(
    context: _CompositionContext,
    *,
    phase: str,
    elapsed_ms: int,
    launcher: Any | None,
    processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...],
    runtime: _CompositionRuntime,
    force: bool = False,
) -> None:
    for item in processes:
        context.observed_processes[item.identity_key] = item
    key = tuple(item.identity_key for item in processes)
    previous = tuple(item.identity_key for item in context.timeline[-1].processes) if context.timeline else None
    if force or key != previous:
        exited: bool | None = None
        if launcher is not None:
            try:
                exited = runtime.launcher_exited(launcher)
            except Exception:
                exited = None
        context.timeline.append(
            DeveloperTaskExecutionBoundaryCompositionProcessSnapshot(
                phase=phase,
                elapsed_ms=max(0, int(elapsed_ms)),
                launcher_exited=exited,
                processes=processes,
            )
        )


def _record_all_processes_exited(context: _CompositionContext, *, elapsed_ms: int) -> None:
    context.all_processes_exited = True
    if context.all_processes_exited_ms is None:
        context.all_processes_exited_ms = max(0, int(elapsed_ms))


def _add_verifier_issues(
    context: _CompositionContext,
    report: DeveloperTaskExecutionSignedTranscriptPinReport | DeveloperTaskExecutionSignedTranscriptReport,
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


def _read_exact(
    runtime: _CompositionRuntime,
    path: Path,
    *,
    name: str,
    expected: bytes | None = None,
) -> tuple[bytes, str]:
    max_bytes = COMPOSITION_ARTIFACT_LIMITS.get(name)
    if max_bytes is None:
        max_bytes = max(len(expected or b""), 1)
    expected_size = len(expected) if expected is not None else None
    raw, sha256 = runtime.read_artifact(
        path,
        max_bytes=max_bytes,
        artifact_name=name,
        expected_size=expected_size,
    )
    if expected is not None and raw != expected:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_pinned_artifact_changed",
            "V1B3D pinned artifact bytes changed.",
            actual=name,
        )
    return raw, sha256


def _failure_artifact(
    runtime: _CompositionRuntime,
    prepared: _PreparedArtifacts,
) -> tuple[str, str]:
    for name, path in (
        (COMPOSITION_BOOTSTRAP_FAILURE_NAME, prepared.bootstrap_failure_path),
        (COMPOSITION_CONTROLLER_FAILURE_NAME, prepared.controller_failure_path),
    ):
        if runtime.artifact_exists(path):
            try:
                _, sha256 = runtime.read_artifact(
                    path,
                    max_bytes=COMPOSITION_ARTIFACT_LIMITS[name],
                    artifact_name=name,
                )
            except Exception:
                return name, ""
            return name, sha256
    return "", ""


def _attest_developer_task_execution_boundary_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    *,
    artifact_parent: Path,
    runtime: _CompositionRuntime,
) -> DeveloperTaskExecutionBoundaryCompositionReport:
    backend_policy = WINDOWS_SANDBOX_EXECUTION_POLICY_V1
    boundary_policy = WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1
    worker_bundle = build_developer_task_execution_boundary_worker_bundle()
    started_at = runtime.epoch()
    started_monotonic = runtime.monotonic()
    context = _CompositionContext(
        backend_policy,
        boundary_policy,
        worker_bundle,
        started_at,
    )
    artifact_parent_resolved: Path | None = None
    prepared: _PreparedArtifacts | None = None
    cleanup_attempts = 0
    launcher: Any | None = None
    executable_path: Path | None = None
    launch_attempted = False
    ready_bytes: bytes | None = None
    authorize_bytes: bytes | None = None
    ready_sha256 = ""
    authorize_sha256 = ""
    worker_result_sha256 = ""
    terminal_payload_sha256 = ""
    terminal_signature_sha256 = ""
    failure_sha256 = ""

    try:
        backend_errors = validate_execution_backend_policy(backend_policy)
        if backend_errors:
            context.add(
                "boundary_composition_backend_policy_invalid",
                "Canonical Windows Sandbox backend policy is invalid.",
                actual=",".join(backend_errors),
            )
            raise RuntimeError("invalid backend policy")
        validate_execution_boundary_policy(boundary_policy)
        if not worker_bundle.ok:
            context.add(
                "boundary_composition_worker_bundle_invalid",
                "Canonical V1B3C worker bundle is invalid.",
            )
            raise RuntimeError("invalid worker bundle")
        if not host_report.ok:
            context.add(
                "execution_backend_host_report_failed",
                "Successful V1B1 host evidence is required.",
                actual=",".join(host_report.issue_codes),
            )
            raise RuntimeError("failed host report")
        if host_report.policy != backend_policy or host_report.policy_fingerprint != backend_policy.fingerprint:
            context.add(
                "execution_backend_host_report_invalid",
                "Host report does not match the canonical backend policy.",
            )
            raise RuntimeError("invalid host policy evidence")

        fresh_host = runtime.inspect_host()
        if not fresh_host.ok:
            context.add(
                "execution_backend_host_report_failed",
                "Fresh V1B1 host inspection failed.",
                actual=",".join(fresh_host.issue_codes),
            )
            raise RuntimeError("fresh host inspection failed")
        if _host_key(host_report) != _host_key(fresh_host):
            context.add(
                "execution_backend_host_evidence_changed",
                "Host capability evidence changed before V1B3D launch.",
            )
            raise RuntimeError("host evidence changed")

        context.host_boot_epoch_seconds = fresh_host.host_boot_epoch_seconds
        context.host_executable_sha256 = fresh_host.executable.sha256 if fresh_host.executable else ""
        executable_path = Path(fresh_host.executable.path) if fresh_host.executable else None
        artifact_parent_resolved = _validate_artifact_parent(artifact_parent)

        baseline = runtime.snapshot_processes()
        _append_snapshot(
            context,
            phase="before_launch",
            elapsed_ms=0,
            launcher=None,
            processes=baseline,
            runtime=runtime,
            force=True,
        )
        if baseline:
            context.add(
                "boundary_composition_sandbox_instance_running",
                "A Windows Sandbox instance is already running.",
                actual=",".join(f"{item.name}:{item.pid}" for item in baseline),
            )
            raise RuntimeError("sandbox already running")

        request_id = secrets.token_hex(16)
        host_nonce = secrets.token_hex(32)
        prepared = _create_artifacts(
            parent=artifact_parent_resolved,
            backend_policy=backend_policy,
            boundary_policy=boundary_policy,
            worker_bundle=worker_bundle,
            request_id=request_id,
            host_nonce=host_nonce,
            created_at=started_at,
        )
        context.request = prepared.request
        if executable_path is None:
            context.add(
                "boundary_composition_executable_missing",
                "Sandbox executable evidence is missing.",
            )
            raise RuntimeError("missing executable")

        launch_attempted = True
        launcher = runtime.launch(executable_path, prepared.wsb_path)
        context.launcher_pid = int(getattr(launcher, "pid", 0))
        if context.launcher_pid <= 0:
            context.add(
                "boundary_composition_launcher_pid_invalid",
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

        ready_deadline = runtime.monotonic() + prepared.request.field("ready_timeout_seconds")
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
            if runtime.artifact_exists(prepared.terminal_payload_path) or runtime.artifact_exists(
                prepared.terminal_signature_path
            ):
                context.add(
                    "boundary_composition_terminal_before_authorization",
                    "Terminal evidence appeared before host authorization.",
                )
                raise RuntimeError("early terminal evidence")
            if runtime.artifact_exists(prepared.bootstrap_failure_path) or runtime.artifact_exists(
                prepared.controller_failure_path
            ):
                context.add(
                    "boundary_composition_guest_failure_reported",
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
                        "boundary_composition_sandbox_exited_before_ready",
                        "Windows Sandbox exited before producing ready evidence.",
                    )
                    break
            runtime.sleep(_POLL_INTERVAL_SECONDS)

        if context.ready_received_ms is None:
            if not context.issues:
                context.add(
                    "boundary_composition_ready_timeout",
                    "Windows Sandbox did not produce ready evidence before timeout.",
                    actual=str(prepared.request.field("ready_timeout_seconds")),
                )
            raise RuntimeError("ready unavailable")

        ready_bytes, ready_sha256 = runtime.read_artifact(
            prepared.ready_path,
            max_bytes=COMPOSITION_ARTIFACT_LIMITS[COMPOSITION_READY_NAME],
            artifact_name=COMPOSITION_READY_NAME,
        )
        ready = parse_boundary_ready(ready_bytes)
        authorization_nonce = secrets.token_hex(32)
        authorization_deadline_epoch = int(runtime.epoch()) + COMPOSITION_AUTHORIZATION_TIMEOUT_SECONDS
        authorize = build_composition_authorize(
            request=prepared.request,
            ready=ready,
            authorization_nonce=authorization_nonce,
            authorization_deadline_epoch=authorization_deadline_epoch,
        )
        authorize_bytes = authorize.canonical_bytes
        authorize_sha256 = authorize.sha256
        context.pin_report = runtime.pin_transcript(
            policy=boundary_policy,
            expected_request_id=request_id,
            expected_host_nonce=host_nonce,
            expected_request_sha256=prepared.request.sha256,
            policy_bytes=prepared.policy_bytes,
            bootstrap_bytes=prepared.bootstrap_bytes,
            controller_bytes=prepared.controller_bytes,
            worker_source_bytes=prepared.worker_source_bytes,
            wsb_bytes=prepared.wsb_bytes,
            request_bytes=prepared.request.canonical_bytes,
            ready_bytes=ready_bytes,
            authorize_bytes=authorize_bytes,
            authorization_observed_epoch=int(runtime.epoch()),
        )
        if not context.pin_report.ok:
            _add_verifier_issues(context, context.pin_report, prefix="pin")
            raise RuntimeError("transcript pinning failed")

        current_ready, current_ready_sha256 = runtime.read_artifact(
            prepared.ready_path,
            max_bytes=COMPOSITION_ARTIFACT_LIMITS[COMPOSITION_READY_NAME],
            artifact_name=COMPOSITION_READY_NAME,
            expected_size=len(ready_bytes),
        )
        if current_ready != ready_bytes or current_ready_sha256 != ready_sha256:
            context.add(
                "boundary_composition_ready_changed_before_authorization",
                "Ready evidence changed before authorization publication.",
            )
            raise RuntimeError("ready changed")

        runtime.publish_authorize(prepared.authorize_path, authorize_bytes)
        context.authorization_published_ms = int(
            (runtime.monotonic() - started_monotonic) * 1000
        )

        terminal_deadline = started_monotonic + backend_policy.launch_timeout_seconds
        while runtime.monotonic() < terminal_deadline:
            current = runtime.snapshot_processes()
            elapsed_ms = int((runtime.monotonic() - started_monotonic) * 1000)
            _append_snapshot(
                context,
                phase="waiting_for_terminal",
                elapsed_ms=elapsed_ms,
                launcher=launcher,
                processes=current,
                runtime=runtime,
            )
            if current:
                context.process_observed = True
            if runtime.artifact_exists(prepared.bootstrap_failure_path) or runtime.artifact_exists(
                prepared.controller_failure_path
            ):
                context.add(
                    "boundary_composition_guest_failure_reported",
                    "Trusted guest reported failure after authorization.",
                )
                break
            if runtime.artifact_exists(prepared.terminal_payload_path) and runtime.artifact_exists(
                prepared.terminal_signature_path
            ):
                context.terminal_detected_ms = elapsed_ms
                break
            if runtime.launcher_exited(launcher) and not current:
                context.add(
                    "boundary_composition_sandbox_exited_before_terminal",
                    "Windows Sandbox exited before producing terminal evidence.",
                )
                break
            runtime.sleep(_POLL_INTERVAL_SECONDS)

        if context.terminal_detected_ms is None and not context.issues:
            context.add(
                "boundary_composition_terminal_timeout",
                "Windows Sandbox did not produce terminal evidence before timeout.",
                actual=str(backend_policy.launch_timeout_seconds),
            )

        shutdown_deadline = runtime.monotonic() + COMPOSITION_SHUTDOWN_GRACE_SECONDS
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
            if not current:
                _record_all_processes_exited(context, elapsed_ms=elapsed_ms)
                break
            runtime.sleep(_POLL_INTERVAL_SECONDS)

        current = runtime.snapshot_processes()
        _append_snapshot(
            context,
            phase="shutdown_wait_complete",
            elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000),
            launcher=launcher,
            processes=current,
            runtime=runtime,
            force=True,
        )
        if not context.all_processes_exited:
            context.status = ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED_ACTIVE
            context.add(
                "boundary_composition_shutdown_timeout",
                "Windows Sandbox processes did not exit within the V1B3D grace period.",
                actual=",".join(f"{item.name}:{item.pid}" for item in current),
            )
            raise RuntimeError("sandbox remains active")
        if not context.process_observed:
            context.add(
                "boundary_composition_process_not_observed",
                "No known Windows Sandbox process was observed.",
            )

        failure_name, failure_sha256 = _failure_artifact(runtime, prepared)
        if failure_name and "boundary_composition_guest_failure_reported" not in {
            item.code for item in context.issues
        }:
            context.add(
                "boundary_composition_guest_failure_reported",
                "Trusted guest emitted a failure artifact.",
                actual=f"{failure_name}:{failure_sha256}",
            )

        if context.terminal_detected_ms is not None:
            final_policy, _ = _read_exact(
                runtime,
                prepared.policy_path,
                name=COMPOSITION_POLICY_NAME,
                expected=prepared.policy_bytes,
            )
            final_bootstrap, _ = _read_exact(
                runtime,
                prepared.bootstrap_path,
                name=COMPOSITION_BOOTSTRAP_NAME,
                expected=prepared.bootstrap_bytes,
            )
            final_controller, _ = _read_exact(
                runtime,
                prepared.controller_path,
                name=COMPOSITION_CONTROLLER_NAME,
                expected=prepared.controller_bytes,
            )
            final_native, _ = _read_exact(
                runtime,
                prepared.native_helper_path,
                name=worker_bundle.native_helper.file_name,
                expected=prepared.native_helper_bytes,
            )
            final_worker_source, _ = _read_exact(
                runtime,
                prepared.worker_source_path,
                name=worker_bundle.worker_probe.file_name,
                expected=prepared.worker_source_bytes,
            )
            final_wsb, _ = _read_exact(
                runtime,
                prepared.wsb_path,
                name=COMPOSITION_WSB_NAME,
                expected=prepared.wsb_bytes,
            )
            final_request, _ = _read_exact(
                runtime,
                prepared.request_path,
                name=COMPOSITION_REQUEST_NAME,
                expected=prepared.request.canonical_bytes,
            )
            final_ready, final_ready_sha256 = _read_exact(
                runtime,
                prepared.ready_path,
                name=COMPOSITION_READY_NAME,
                expected=ready_bytes,
            )
            final_authorize, final_authorize_sha256 = _read_exact(
                runtime,
                prepared.authorize_path,
                name=COMPOSITION_AUTHORIZE_NAME,
                expected=authorize_bytes,
            )
            worker_result_bytes, worker_result_sha256 = runtime.read_artifact(
                prepared.worker_result_path,
                max_bytes=COMPOSITION_ARTIFACT_LIMITS[COMPOSITION_WORKER_RESULT_NAME],
                artifact_name=COMPOSITION_WORKER_RESULT_NAME,
            )
            terminal_payload_bytes, terminal_payload_sha256 = runtime.read_artifact(
                prepared.terminal_payload_path,
                max_bytes=COMPOSITION_ARTIFACT_LIMITS[COMPOSITION_TERMINAL_PAYLOAD_NAME],
                artifact_name=COMPOSITION_TERMINAL_PAYLOAD_NAME,
            )
            terminal_signature_bytes, terminal_signature_sha256 = runtime.read_artifact(
                prepared.terminal_signature_path,
                max_bytes=COMPOSITION_ARTIFACT_LIMITS[COMPOSITION_TERMINAL_SIGNATURE_NAME],
                artifact_name=COMPOSITION_TERMINAL_SIGNATURE_NAME,
                expected_size=COMPOSITION_ARTIFACT_LIMITS[COMPOSITION_TERMINAL_SIGNATURE_NAME],
            )
            if final_ready_sha256 != ready_sha256 or final_authorize_sha256 != authorize_sha256:
                context.add(
                    "boundary_composition_pinned_artifact_changed",
                    "Pinned ready or authorization hash changed after Sandbox exit.",
                )
            if final_native != worker_bundle.native_helper.exact_bytes():
                context.add(
                    "boundary_composition_worker_bundle_changed",
                    "V1B3C native-helper bytes changed during V1B3D.",
                )
            context.signed_report = runtime.verify_transcript(
                context.pin_report,
                policy_bytes=final_policy,
                bootstrap_bytes=final_bootstrap,
                controller_bytes=final_controller,
                worker_source_bytes=final_worker_source,
                wsb_bytes=final_wsb,
                request_bytes=final_request,
                ready_bytes=final_ready,
                authorize_bytes=final_authorize,
                worker_result_bytes=worker_result_bytes,
                terminal_payload_bytes=terminal_payload_bytes,
                terminal_signature_bytes=terminal_signature_bytes,
            )
            if not context.signed_report.ok:
                _add_verifier_issues(context, context.signed_report, prefix="verify")

        post_host = runtime.inspect_host()
        if not post_host.ok or _host_key(fresh_host) != _host_key(post_host):
            context.add(
                "execution_backend_host_evidence_changed",
                "Host capability evidence changed during V1B3D.",
                actual=",".join(post_host.issue_codes),
            )

        context.status = (
            ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED
            if not context.issues
            and context.pin_report is not None
            and context.pin_report.ok
            and context.signed_report is not None
            and context.signed_report.ok
            else ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED
        )
    except (
        DeveloperTaskExecutionBoundaryCompositionPayloadError,
        DeveloperTaskExecutionBoundaryContractError,
        DeveloperTaskExecutionBackendLifecycleWindowsError,
    ) as exc:
        context.add(
            getattr(exc, "code", "boundary_composition_structured_error"),
            str(exc),
            actual=getattr(exc, "actual", ""),
        )
    except Exception as exc:
        if not context.issues:
            context.add(
                "boundary_composition_unexpected_error",
                "Unexpected V1B3D composition failure.",
                actual=f"{type(exc).__name__}: {exc}",
            )
    finally:
        process_state_proven = not launch_attempted
        remaining: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...] = ()
        if launch_attempted:
            try:
                remaining = runtime.snapshot_processes()
                process_state_proven = True
            except Exception as exc:
                process_state_proven = False
                context.status = ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED_ACTIVE
                context.add(
                    "boundary_composition_process_state_unproven",
                    "Sandbox process state could not be proven during finalization.",
                    actual=f"{type(exc).__name__}: {exc}",
                )
        if process_state_proven and remaining and context.issues:
            graceful_deadline = runtime.monotonic() + COMPOSITION_SHUTDOWN_GRACE_SECONDS
            while remaining and runtime.monotonic() < graceful_deadline:
                runtime.sleep(_POLL_INTERVAL_SECONDS)
                try:
                    remaining = runtime.snapshot_processes()
                except Exception as exc:
                    process_state_proven = False
                    context.status = ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED_ACTIVE
                    context.add(
                        "boundary_composition_process_state_unproven",
                        "Sandbox process state could not be proven during bounded failure shutdown.",
                        actual=f"{type(exc).__name__}: {exc}",
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
            if process_state_proven and not remaining:
                _record_all_processes_exited(
                    context,
                    elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000),
                )

        if process_state_proven and remaining:
            context.status = ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED_ACTIVE
            if executable_path is not None and context.observed_processes:
                try:
                    context.termination = runtime.terminate(
                        tuple(context.observed_processes.values()),
                        executable=executable_path,
                    )
                except Exception as exc:
                    context.add(
                        "boundary_composition_forced_cleanup_failed",
                        "Best-effort Sandbox cleanup failed.",
                        actual=f"{type(exc).__name__}: {exc}",
                    )
                else:
                    try:
                        remaining = runtime.snapshot_processes()
                    except Exception as exc:
                        process_state_proven = False
                        context.add(
                            "boundary_composition_process_state_unproven",
                            "Sandbox exit could not be proven after forced cleanup.",
                            actual=f"{type(exc).__name__}: {exc}",
                        )
                    else:
                        if not remaining:
                            _record_all_processes_exited(
                                context,
                                elapsed_ms=int(
                                    (runtime.monotonic() - started_monotonic) * 1000
                                ),
                            )
                            context.status = ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED
            else:
                context.add(
                    "boundary_composition_forced_cleanup_unavailable",
                    "Active Sandbox processes were not bound to observed identities.",
                    actual=",".join(f"{item.name}:{item.pid}" for item in remaining),
                )
        if launch_attempted and process_state_proven and not remaining:
            _record_all_processes_exited(
                context,
                elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000),
            )

        if (
            prepared is not None
            and artifact_parent_resolved is not None
            and process_state_proven
            and not remaining
        ):
            try:
                cleanup_attempts = _cleanup_artifacts(
                    prepared.root,
                    parent=artifact_parent_resolved,
                    initial_metadata=prepared.root_metadata,
                )
            except DeveloperTaskExecutionBoundaryCompositionPayloadError as exc:
                if exc.code not in {item.code for item in context.issues}:
                    context.add(exc.code, str(exc), actual=exc.actual)
                if context.status == ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED:
                    context.status = ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED

        completed_at = runtime.epoch()
        total_ms = max(0, int((runtime.monotonic() - started_monotonic) * 1000))
        if prepared is not None:
            context.artifacts = DeveloperTaskExecutionBoundaryCompositionArtifacts(
                root=str(prepared.root),
                input_root=str(prepared.input_root),
                control_root=str(prepared.control_root),
                output_root=str(prepared.output_root),
                request_path=str(prepared.request_path),
                ready_path=str(prepared.ready_path),
                authorize_path=str(prepared.authorize_path),
                worker_result_path=str(prepared.worker_result_path),
                terminal_payload_path=str(prepared.terminal_payload_path),
                terminal_signature_path=str(prepared.terminal_signature_path),
                policy_sha256=_sha256(prepared.policy_bytes),
                bootstrap_sha256=_sha256(prepared.bootstrap_bytes),
                controller_sha256=_sha256(prepared.controller_bytes),
                native_helper_sha256=_sha256(prepared.native_helper_bytes),
                worker_source_sha256=_sha256(prepared.worker_source_bytes),
                wsb_sha256=_sha256(prepared.wsb_bytes),
                request_sha256=prepared.request.sha256,
                ready_sha256=ready_sha256,
                authorize_sha256=authorize_sha256,
                worker_result_sha256=worker_result_sha256,
                terminal_payload_sha256=terminal_payload_sha256,
                terminal_signature_sha256=terminal_signature_sha256,
                failure_artifact_sha256=failure_sha256,
                removed=not os.path.lexists(prepared.root),
                cleanup_attempts=cleanup_attempts,
            )

    return context.report(completed_at=completed_at, total_ms=total_ms)


def attest_developer_task_execution_boundary_composition(
    host_report: DeveloperTaskExecutionBackendHostReport,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionBoundaryCompositionReport:
    if not isinstance(host_report, DeveloperTaskExecutionBackendHostReport):
        raise TypeError("host_report must be DeveloperTaskExecutionBackendHostReport")
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")
    return _attest_developer_task_execution_boundary_composition(
        host_report,
        artifact_parent=artifact_parent,
        runtime=_CompositionRuntime(),
    )
