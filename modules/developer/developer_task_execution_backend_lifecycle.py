from __future__ import annotations

"""Active trusted lifecycle gate for the traditional Windows Sandbox backend."""

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
from modules.developer.developer_task_execution_backend_lifecycle_payload import (
    LIFECYCLE_GUEST_SCRIPT_NAME,
    LIFECYCLE_REQUEST_NAME,
    LIFECYCLE_RESULT_NAME,
    LIFECYCLE_WSB_NAME,
    DeveloperTaskExecutionBackendLifecycleGuestEvidence,
    DeveloperTaskExecutionBackendLifecyclePayloadError,
    DeveloperTaskExecutionBackendLifecycleRequest,
    build_lifecycle_guest_script,
    build_lifecycle_request,
    build_lifecycle_wsb_config,
    read_lifecycle_result_bytes,
    validate_lifecycle_guest_result,
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
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_workspace_cleanup_fs import (
    DeveloperTaskWorkspaceCleanupFileSystemError,
    absolute_path,
    remove_verified_workspace,
    validate_workspace_parent,
)


LIFECYCLE_STATUS_ATTESTED = "lifecycle_attested"
LIFECYCLE_STATUS_FAILED = "failed"
LIFECYCLE_STATUS_FAILED_ACTIVE = "failed_active"
_ARTIFACT_PREFIX = "skynetvs-backend-lifecycle-"
_POLL_INTERVAL_SECONDS = 0.25
_PROCESS_APPEARANCE_GRACE_SECONDS = 5.0
_FORCE_CLEANUP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendLifecycleProcessSnapshot:
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
class DeveloperTaskExecutionBackendLifecycleArtifacts:
    root: str
    input_root: str
    output_root: str
    request_path: str
    guest_script_path: str
    wsb_path: str
    result_path: str
    request_sha256: str
    guest_script_sha256: str
    wsb_sha256: str
    result_sha256: str
    removed: bool
    cleanup_attempts: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "input_root": self.input_root,
            "output_root": self.output_root,
            "request_path": self.request_path,
            "guest_script_path": self.guest_script_path,
            "wsb_path": self.wsb_path,
            "result_path": self.result_path,
            "request_sha256": self.request_sha256,
            "guest_script_sha256": self.guest_script_sha256,
            "wsb_sha256": self.wsb_sha256,
            "result_sha256": self.result_sha256,
            "removed": self.removed,
            "cleanup_attempts": self.cleanup_attempts,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendLifecycleReport:
    status: str
    backend_id: str
    policy: DeveloperTaskExecutionBackendPolicy
    policy_fingerprint: str
    host_boot_epoch_seconds: int
    host_executable_sha256: str
    started_at_epoch_seconds: float
    completed_at_epoch_seconds: float
    attestation_expires_at_epoch_seconds: float
    request: DeveloperTaskExecutionBackendLifecycleRequest | None
    launcher_pid: int
    process_observed: bool
    all_processes_exited: bool
    termination: DeveloperTaskExecutionBackendTerminationResult
    result_received_ms: int | None
    all_processes_exited_ms: int | None
    total_ms: int
    process_timeline: tuple[DeveloperTaskExecutionBackendLifecycleProcessSnapshot, ...]
    guest_evidence: DeveloperTaskExecutionBackendLifecycleGuestEvidence | None
    artifacts: DeveloperTaskExecutionBackendLifecycleArtifacts | None
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            self.status == LIFECYCLE_STATUS_ATTESTED
            and self.backend_id == self.policy.backend_id
            and self.policy_fingerprint == self.policy.fingerprint
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
            and self.result_received_ms is not None
            and self.all_processes_exited_ms is not None
            and self.total_ms >= self.all_processes_exited_ms
            and self.guest_evidence is not None
            and self.guest_evidence.ok
            and self.artifacts is not None
            and self.artifacts.removed
            and not self.issues
        )

    @property
    def forced_cleanup_attempted(self) -> bool:
        return self.termination.attempted

    @property
    def forced_cleanup_succeeded(self) -> bool:
        return self.termination.attempted and self.termination.succeeded

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "backend_id": self.backend_id,
            "policy": self.policy.to_dict(),
            "policy_fingerprint": self.policy_fingerprint,
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
            "forced_cleanup_attempted": self.forced_cleanup_attempted,
            "forced_cleanup_succeeded": self.forced_cleanup_succeeded,
            "timing": {
                "result_received_ms": self.result_received_ms,
                "all_processes_exited_ms": self.all_processes_exited_ms,
                "total_ms": self.total_ms,
            },
            "process_timeline": [item.to_dict() for item in self.process_timeline],
            "guest_evidence": self.guest_evidence.to_dict() if self.guest_evidence is not None else None,
            "artifacts": self.artifacts.to_dict() if self.artifacts is not None else None,
            "execution_authorized": False,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


class _LifecycleRuntime:
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

    def result_exists(self, path: Path) -> bool:
        return os.path.lexists(path)

    def read_result(self, path: Path, max_bytes: int) -> tuple[bytes, str]:
        return read_lifecycle_result_bytes(path, max_bytes)

    def monotonic(self) -> float:
        return time.monotonic()

    def epoch(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class _LifecycleContext:
    def __init__(self, policy: DeveloperTaskExecutionBackendPolicy, started_at: float) -> None:
        self.policy = policy
        self.started_at = started_at
        self.status = LIFECYCLE_STATUS_FAILED
        self.host_boot_epoch_seconds = 0
        self.host_executable_sha256 = ""
        self.request: DeveloperTaskExecutionBackendLifecycleRequest | None = None
        self.launcher_pid = 0
        self.process_observed = False
        self.all_processes_exited = False
        self.termination = _empty_termination()
        self.result_received_ms: int | None = None
        self.all_processes_exited_ms: int | None = None
        self.timeline: list[DeveloperTaskExecutionBackendLifecycleProcessSnapshot] = []
        self.observed_processes: dict[tuple[str, int, int], DeveloperTaskExecutionBackendProcessEvidence] = {}
        self.guest_evidence: DeveloperTaskExecutionBackendLifecycleGuestEvidence | None = None
        self.artifacts: DeveloperTaskExecutionBackendLifecycleArtifacts | None = None
        self.issues: list[DeveloperTaskPreflightIssue] = []

    def add(self, code: str, check: str, message: str, *, expected: str = "", actual: str = "") -> None:
        self.issues.append(
            DeveloperTaskPreflightIssue(
                code=code,
                check=check,
                message=message,
                expected=expected,
                actual=actual,
            )
        )

    def report(self, *, completed_at: float, total_ms: int) -> DeveloperTaskExecutionBackendLifecycleReport:
        expires = completed_at + self.policy.attestation_ttl_seconds if self.status == LIFECYCLE_STATUS_ATTESTED else 0.0
        return DeveloperTaskExecutionBackendLifecycleReport(
            status=self.status,
            backend_id=self.policy.backend_id,
            policy=self.policy,
            policy_fingerprint=self.policy.fingerprint,
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
            result_received_ms=self.result_received_ms,
            all_processes_exited_ms=self.all_processes_exited_ms,
            total_ms=total_ms,
            process_timeline=tuple(self.timeline),
            guest_evidence=self.guest_evidence,
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
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            exc.code.replace("workspace_parent", "lifecycle_artifact_parent"),
            "Lifecycle artifact parent is unsafe.",
            actual=exc.actual,
        ) from exc

    for ancestor in (resolved, *resolved.parents):
        try:
            git_entry = os.lstat(ancestor / ".git")
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise DeveloperTaskExecutionBackendLifecyclePayloadError(
                "lifecycle_artifact_parent_metadata_failed",
                "Lifecycle artifact parent Git boundary could not be inspected.",
                actual=f"{type(exc).__name__}: {exc}",
            ) from exc
        if stat.S_ISDIR(git_entry.st_mode) or stat.S_ISREG(git_entry.st_mode):
            raise DeveloperTaskExecutionBackendLifecyclePayloadError(
                "lifecycle_artifact_parent_inside_git_repository",
                "Lifecycle artifacts must not be created inside a Git repository.",
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
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_artifact_write_failed",
            "Lifecycle artifact could not be written.",
            actual=f"{path}: {type(exc).__name__}: {exc}",
        ) from exc


def _create_artifacts(
    policy: DeveloperTaskExecutionBackendPolicy,
    *,
    parent: Path,
    request_id: str,
    nonce: str,
    generated_at_epoch: int,
) -> tuple[Path, os.stat_result, Path, Path, Path, DeveloperTaskExecutionBackendLifecycleRequest]:
    root: Path | None = None
    for _ in range(16):
        candidate = parent / f"{_ARTIFACT_PREFIX}{request_id[:8]}-{secrets.token_hex(8)}"
        try:
            candidate.mkdir(mode=0o700, exist_ok=False)
            root = candidate
            break
        except FileExistsError:
            continue
        except OSError as exc:
            raise DeveloperTaskExecutionBackendLifecyclePayloadError(
                "lifecycle_artifact_root_create_failed",
                "Lifecycle artifact root could not be created.",
                actual=f"{type(exc).__name__}: {exc}",
            ) from exc
    if root is None:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_artifact_root_collision",
            "A unique lifecycle artifact root could not be allocated.",
        )

    try:
        input_root = root / "input"
        output_root = root / "output"
        input_root.mkdir(mode=0o700)
        output_root.mkdir(mode=0o700)

        guest_path = input_root / LIFECYCLE_GUEST_SCRIPT_NAME
        guest_bytes = build_lifecycle_guest_script(policy)
        _write_new_file(guest_path, guest_bytes)
        guest_sha256 = __import__("hashlib").sha256(guest_bytes).hexdigest()

        wsb_path = input_root / LIFECYCLE_WSB_NAME
        wsb_bytes = build_lifecycle_wsb_config(policy, input_root=input_root, output_root=output_root)
        _write_new_file(wsb_path, wsb_bytes)
        wsb_sha256 = __import__("hashlib").sha256(wsb_bytes).hexdigest()

        request = build_lifecycle_request(
            policy,
            request_id=request_id,
            nonce=nonce,
            generated_at_epoch=generated_at_epoch,
            guest_script_sha256=guest_sha256,
            wsb_sha256=wsb_sha256,
        )
        request_path = input_root / LIFECYCLE_REQUEST_NAME
        _write_new_file(request_path, request.canonical_bytes())
        return root, os.lstat(root), input_root, output_root, wsb_path, request
    except Exception as original:
        try:
            initial_metadata = os.lstat(root)
            _cleanup_artifacts(
                root,
                parent=parent,
                initial_metadata=initial_metadata,
            )
        except Exception as cleanup_error:
            raise DeveloperTaskExecutionBackendLifecyclePayloadError(
                "lifecycle_artifact_preparation_cleanup_failed",
                "Partially prepared lifecycle artifacts could not be removed safely.",
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
    if (
        root_resolved.parent != parent_resolved
        or not root_resolved.name.startswith(_ARTIFACT_PREFIX)
    ):
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_artifact_cleanup_scope_invalid",
            "Lifecycle artifact cleanup target is outside the verified scope.",
            actual=str(root_resolved),
        )

    try:
        removal = remove_verified_workspace(root_resolved, initial_metadata)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_artifact_cleanup_failed",
            "Lifecycle artifact cleanup failed.",
            actual=f"{exc.code}:{exc.actual};attempts={exc.attempts}",
        ) from exc
    return removal.attempts

def _record_all_processes_exited(
    context: _LifecycleContext,
    *,
    elapsed_ms: int,
) -> None:
    context.all_processes_exited = True
    if context.all_processes_exited_ms is None:
        context.all_processes_exited_ms = max(0, int(elapsed_ms))


def _append_snapshot(
    context: _LifecycleContext,
    *,
    phase: str,
    elapsed_ms: int,
    launcher: Any | None,
    processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...],
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
                exited = launcher_has_exited(launcher)
            except Exception:
                exited = None
        context.timeline.append(
            DeveloperTaskExecutionBackendLifecycleProcessSnapshot(
                phase=phase,
                elapsed_ms=elapsed_ms,
                launcher_exited=exited,
                processes=processes,
            )
        )


def _add_error(context: _LifecycleContext, code: str, message: str, *, actual: str = "") -> None:
    context.add(code, "execution_backend_lifecycle", message, actual=actual)


def attest_developer_task_execution_backend_lifecycle(
    host_report: DeveloperTaskExecutionBackendHostReport,
    *,
    artifact_parent: Path,
) -> DeveloperTaskExecutionBackendLifecycleReport:
    if not isinstance(host_report, DeveloperTaskExecutionBackendHostReport):
        raise TypeError("host_report must be DeveloperTaskExecutionBackendHostReport")
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")

    policy = WINDOWS_SANDBOX_EXECUTION_POLICY_V1
    runtime = _LifecycleRuntime()
    started_at = runtime.epoch()
    started_monotonic = runtime.monotonic()
    context = _LifecycleContext(policy, started_at)
    artifact_parent_resolved: Path | None = None
    artifact_root: Path | None = None
    artifact_root_metadata: os.stat_result | None = None
    input_root: Path | None = None
    output_root: Path | None = None
    result_path: Path | None = None
    result_sha256 = ""
    raw_result: bytes | None = None
    cleanup_attempts = 0
    launcher: Any | None = None
    executable_path: Path | None = None
    launch_attempted = False

    try:
        policy_errors = validate_execution_backend_policy(policy)
        if policy_errors:
            _add_error(context, "lifecycle_policy_invalid", "Canonical lifecycle policy is invalid.", actual=",".join(policy_errors))
            raise RuntimeError("invalid lifecycle policy")
        if not host_report.ok:
            _add_error(context, "execution_backend_host_report_failed", "Successful host capability evidence is required.", actual=",".join(host_report.issue_codes))
            raise RuntimeError("failed host report")
        if host_report.policy != policy or host_report.policy_fingerprint != policy.fingerprint:
            _add_error(context, "execution_backend_host_report_invalid", "Host report does not match canonical backend policy.")
            raise RuntimeError("invalid host policy evidence")

        fresh_host = runtime.inspect_host()
        if not fresh_host.ok:
            _add_error(context, "execution_backend_host_stale", "Fresh host capability inspection failed.", actual=",".join(fresh_host.issue_codes))
            raise RuntimeError("fresh host inspection failed")
        if _host_key(host_report) != _host_key(fresh_host):
            _add_error(context, "execution_backend_host_evidence_changed", "Host capability evidence changed before lifecycle attestation.")
            raise RuntimeError("host evidence changed")

        context.host_boot_epoch_seconds = fresh_host.host_boot_epoch_seconds
        context.host_executable_sha256 = fresh_host.executable.sha256 if fresh_host.executable else ""
        executable_path = Path(fresh_host.executable.path) if fresh_host.executable else None
        artifact_parent_resolved = _validate_artifact_parent(artifact_parent)

        baseline = runtime.snapshot_processes()
        _append_snapshot(context, phase="before_launch", elapsed_ms=0, launcher=None, processes=baseline, force=True)
        if baseline:
            _add_error(context, "lifecycle_sandbox_instance_running", "A Windows Sandbox instance is already running.", actual=",".join(f"{item.name}:{item.pid}" for item in baseline))
            raise RuntimeError("sandbox already running")

        request_id = secrets.token_hex(16)
        nonce = secrets.token_hex(32)
        artifact_root, artifact_root_metadata, input_root, output_root, wsb_path, request = _create_artifacts(
            policy,
            parent=artifact_parent_resolved,
            request_id=request_id,
            nonce=nonce,
            generated_at_epoch=int(started_at),
        )
        context.request = request
        result_path = output_root / LIFECYCLE_RESULT_NAME

        if executable_path is None:
            _add_error(context, "lifecycle_executable_missing", "Sandbox executable evidence is missing.")
            raise RuntimeError("missing executable")
        launch_attempted = True
        launcher = runtime.launch(executable_path, wsb_path)
        context.launcher_pid = int(getattr(launcher, "pid", 0))
        if context.launcher_pid <= 0:
            _add_error(context, "lifecycle_launcher_pid_invalid", "Windows Sandbox launcher PID is invalid.")
            raise RuntimeError("invalid launcher PID")

        current = runtime.snapshot_processes()
        _append_snapshot(context, phase="after_launch", elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000), launcher=launcher, processes=current, force=True)
        context.process_observed = bool(current)

        deadline = runtime.monotonic() + policy.launch_timeout_seconds
        while runtime.monotonic() < deadline:
            current = runtime.snapshot_processes()
            elapsed_ms = int((runtime.monotonic() - started_monotonic) * 1000)
            _append_snapshot(context, phase="waiting_for_result", elapsed_ms=elapsed_ms, launcher=launcher, processes=current)
            if current:
                context.process_observed = True
            if runtime.result_exists(result_path):
                context.result_received_ms = elapsed_ms
                break
            if runtime.launcher_exited(launcher) and not current:
                elapsed_seconds = max(0.0, runtime.monotonic() - started_monotonic)
                if context.process_observed or elapsed_seconds >= _PROCESS_APPEARANCE_GRACE_SECONDS:
                    _add_error(
                        context,
                        "lifecycle_sandbox_exited_before_result",
                        "Windows Sandbox exited before producing result.json.",
                    )
                    break
            runtime.sleep(_POLL_INTERVAL_SECONDS)

        if context.result_received_ms is None:
            if not context.issues:
                _add_error(context, "lifecycle_result_timeout", "Windows Sandbox did not produce result.json before timeout.", actual=str(policy.launch_timeout_seconds))
            raise RuntimeError("result unavailable")

        current = runtime.snapshot_processes()
        _append_snapshot(context, phase="result_detected", elapsed_ms=context.result_received_ms, launcher=launcher, processes=current, force=True)
        try:
            raw_result, result_sha256 = runtime.read_result(
                result_path,
                policy.max_result_bytes,
            )
            context.guest_evidence = validate_lifecycle_guest_result(
                raw_result,
                result_sha256=result_sha256,
                request=request,
                request_sha256=request.sha256,
            )
        except (
            DeveloperTaskExecutionBackendLifecyclePayloadError,
            DeveloperTaskExecutionBackendLifecycleWindowsError,
        ) as exc:
            _add_error(context, exc.code, str(exc), actual=exc.actual)

        shutdown_deadline = runtime.monotonic() + policy.shutdown_grace_seconds
        while runtime.monotonic() < shutdown_deadline:
            current = runtime.snapshot_processes()
            elapsed_ms = int((runtime.monotonic() - started_monotonic) * 1000)
            _append_snapshot(context, phase="waiting_for_shutdown", elapsed_ms=elapsed_ms, launcher=launcher, processes=current)
            if not current:
                _record_all_processes_exited(
                    context,
                    elapsed_ms=elapsed_ms,
                )
                break
            runtime.sleep(_POLL_INTERVAL_SECONDS)

        current = runtime.snapshot_processes()
        _append_snapshot(context, phase="shutdown_wait_complete", elapsed_ms=int((runtime.monotonic() - started_monotonic) * 1000), launcher=launcher, processes=current, force=True)
        if not context.all_processes_exited:
            context.status = LIFECYCLE_STATUS_FAILED_ACTIVE
            _add_error(context, "lifecycle_shutdown_timeout", "Windows Sandbox processes did not exit within the shutdown grace period.", actual=",".join(f"{item.name}:{item.pid}" for item in current))
            raise RuntimeError("sandbox remains active")
        if not context.process_observed:
            _add_error(
                context,
                "lifecycle_process_not_observed",
                "No known Windows Sandbox process was observed.",
            )

        if raw_result is not None:
            try:
                final_result, final_sha256 = runtime.read_result(
                    result_path,
                    policy.max_result_bytes,
                )
                if final_result != raw_result or final_sha256 != result_sha256:
                    _add_error(
                        context,
                        "lifecycle_result_changed_before_exit",
                        "Lifecycle result changed before Sandbox exit was proven.",
                    )
            except (
                DeveloperTaskExecutionBackendLifecyclePayloadError,
                DeveloperTaskExecutionBackendLifecycleWindowsError,
            ) as exc:
                _add_error(context, exc.code, str(exc), actual=exc.actual)

        post_host = runtime.inspect_host()
        if not post_host.ok or _host_key(fresh_host) != _host_key(post_host):
            _add_error(
                context,
                "execution_backend_host_evidence_changed",
                "Host capability evidence changed during lifecycle attestation.",
                actual=",".join(post_host.issue_codes),
            )

        context.status = (
            LIFECYCLE_STATUS_ATTESTED
            if not context.issues
            else LIFECYCLE_STATUS_FAILED
        )
    except (DeveloperTaskExecutionBackendLifecyclePayloadError, DeveloperTaskExecutionBackendLifecycleWindowsError) as exc:
        _add_error(context, exc.code, str(exc), actual=exc.actual)
    except Exception as exc:
        if not context.issues:
            _add_error(context, "lifecycle_unexpected_error", "Unexpected lifecycle attestation failure.", actual=f"{type(exc).__name__}: {exc}")
    finally:
        process_state_proven = not launch_attempted
        remaining: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...] = ()

        if launch_attempted:
            try:
                remaining = runtime.snapshot_processes()
                process_state_proven = True
            except Exception as exc:
                process_state_proven = False
                context.status = LIFECYCLE_STATUS_FAILED_ACTIVE
                _add_error(
                    context,
                    "lifecycle_process_state_unproven",
                    "Sandbox process state could not be proven during finalization.",
                    actual=f"{type(exc).__name__}: {exc}",
                )

        if process_state_proven and remaining:
            context.status = LIFECYCLE_STATUS_FAILED_ACTIVE
            if executable_path is not None and context.observed_processes:
                try:
                    context.termination = runtime.terminate(
                        tuple(context.observed_processes.values()),
                        executable=executable_path,
                    )
                except Exception as exc:
                    _add_error(
                        context,
                        "lifecycle_forced_cleanup_failed",
                        "Best-effort Sandbox cleanup failed.",
                        actual=f"{type(exc).__name__}: {exc}",
                    )
                else:
                    try:
                        remaining = runtime.snapshot_processes()
                    except Exception as exc:
                        process_state_proven = False
                        _add_error(
                            context,
                            "lifecycle_process_state_unproven",
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
                            context.status = LIFECYCLE_STATUS_FAILED
            elif remaining:
                _add_error(
                    context,
                    "lifecycle_forced_cleanup_unavailable",
                    "Active Sandbox processes were not bound to observed identities.",
                    actual=",".join(f"{item.name}:{item.pid}" for item in remaining),
                )

        if launch_attempted and process_state_proven and not remaining:
            _record_all_processes_exited(
                context,
                elapsed_ms=int(
                    (runtime.monotonic() - started_monotonic) * 1000
                ),
            )

        if (
            artifact_root is not None
            and artifact_root_metadata is not None
            and artifact_parent_resolved is not None
            and process_state_proven
            and not remaining
        ):
            try:
                cleanup_attempts = _cleanup_artifacts(
                    artifact_root,
                    parent=artifact_parent_resolved,
                    initial_metadata=artifact_root_metadata,
                )
            except DeveloperTaskExecutionBackendLifecyclePayloadError as exc:
                if exc.code not in {item.code for item in context.issues}:
                    _add_error(context, exc.code, str(exc), actual=exc.actual)
                if context.status == LIFECYCLE_STATUS_ATTESTED:
                    context.status = LIFECYCLE_STATUS_FAILED

        completed_at = runtime.epoch()
        total_ms = max(0, int((runtime.monotonic() - started_monotonic) * 1000))
        if artifact_root is not None and input_root is not None and output_root is not None and result_path is not None and context.request is not None:
            context.artifacts = DeveloperTaskExecutionBackendLifecycleArtifacts(
                root=str(artifact_root),
                input_root=str(input_root),
                output_root=str(output_root),
                request_path=str(input_root / LIFECYCLE_REQUEST_NAME),
                guest_script_path=str(input_root / LIFECYCLE_GUEST_SCRIPT_NAME),
                wsb_path=str(input_root / LIFECYCLE_WSB_NAME),
                result_path=str(result_path),
                request_sha256=context.request.sha256,
                guest_script_sha256=context.request.guest_script_sha256,
                wsb_sha256=context.request.wsb_sha256,
                result_sha256=result_sha256,
                removed=not os.path.lexists(artifact_root),
                cleanup_attempts=cleanup_attempts,
            )

    return context.report(completed_at=completed_at, total_ms=total_ms)
