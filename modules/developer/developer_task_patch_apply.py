from __future__ import annotations

"""Fail-closed application of verified patch bytes inside an independent workspace."""

import hashlib
import json
import os
import secrets
import stat

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_patch_apply_git import (
    DeveloperTaskPatchApplyGitError,
    DeveloperTaskPatchApplyGitEvidence,
    DeveloperTaskPatchApplyGitRequest,
    DeveloperTaskPatchApplyRollbackResult,
    apply_patch_to_independent_workspace,
    restore_independent_workspace_base,
)
from modules.developer.developer_task_patch_index import DeveloperTaskPatchIndexChange
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_preflight_composition import DeveloperTaskPreflightReport
from modules.developer.developer_task_workspace import DeveloperTaskWorkspaceReport
from modules.developer.developer_task_workspace_cleanup_fs import (
    WORKSPACE_MARKER_NAME,
    DeveloperTaskWorkspaceCleanupFileSystemError,
    absolute_path,
    is_reparse_or_symlink,
    paths_overlap,
    read_workspace_marker,
    same_path,
    validate_canonical_marker,
    validate_workspace_parent,
    validate_workspace_root,
    workspace_id_matches,
)
from modules.developer.developer_task_workspace_git import DeveloperTaskWorkspaceGitRequest
from modules.developer.developer_task_workspace_source import (
    DeveloperTaskSourceRepositorySnapshot,
    snapshot_developer_task_source_repository,
)


PATCH_APPLY_MARKER_NAME = "patch_apply.json"
PATCH_APPLY_MARKER_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DeveloperTaskPatchApplyReport:
    """Immutable evidence for one verified workspace patch application."""

    manifest_fingerprint: str
    workspace_id: str
    source_repository_root: str
    task_root: str
    workspace_parent: str
    workspace_root: str
    repository_root: str
    apply_marker_path: str
    apply_marker_sha256: str
    base_commit: str
    head_commit: str
    patch_sha256: str
    changed_files: tuple[str, ...]
    changes: tuple[DeveloperTaskPatchIndexChange, ...]
    result_index_paths: tuple[str, ...]
    result_tree: str
    staged_diff_sha256: str
    workspace_config_sha256: str
    applied: bool
    rollback_attempted: bool
    rollback_succeeded: bool
    workspace_clean: bool
    source_snapshot_before: str
    source_snapshot_after: str
    source_repository_unchanged: bool
    check_token: bytes = field(repr=False)
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            bool(self.manifest_fingerprint)
            and bool(self.workspace_id)
            and bool(self.source_repository_root)
            and bool(self.task_root)
            and bool(self.workspace_parent)
            and bool(self.workspace_root)
            and bool(self.repository_root)
            and bool(self.apply_marker_path)
            and len(self.apply_marker_sha256) == 64
            and bool(self.base_commit)
            and self.head_commit == self.base_commit
            and len(self.patch_sha256) == 64
            and bool(self.changed_files)
            and self.changed_files == tuple(item.path for item in self.changes)
            and bool(self.result_tree)
            and len(self.staged_diff_sha256) == 64
            and len(self.workspace_config_sha256) == 64
            and self.applied
            and not self.rollback_attempted
            and not self.rollback_succeeded
            and not self.workspace_clean
            and bool(self.source_snapshot_before)
            and self.source_snapshot_before == self.source_snapshot_after
            and self.source_repository_unchanged
            and len(self.check_token) == 32
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    @property
    def state(self) -> str:
        if self.ok:
            return "applied"
        if self.rollback_succeeded and self.workspace_clean:
            return "rejected_clean"
        if self.rollback_attempted:
            return "failed_dirty"
        return "rejected"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "state": self.state,
            "manifest_fingerprint": self.manifest_fingerprint,
            "workspace_id": self.workspace_id,
            "source_repository_root": self.source_repository_root,
            "task_root": self.task_root,
            "workspace_parent": self.workspace_parent,
            "workspace_root": self.workspace_root,
            "repository_root": self.repository_root,
            "apply_marker_path": self.apply_marker_path,
            "apply_marker_sha256": self.apply_marker_sha256,
            "base_commit": self.base_commit,
            "head_commit": self.head_commit,
            "patch_sha256": self.patch_sha256,
            "changed_files": list(self.changed_files),
            "changes": [item.to_dict() for item in self.changes],
            "result_index_paths": list(self.result_index_paths),
            "result_tree": self.result_tree,
            "staged_diff_sha256": self.staged_diff_sha256,
            "workspace_config_sha256": self.workspace_config_sha256,
            "applied": self.applied,
            "rollback_attempted": self.rollback_attempted,
            "rollback_succeeded": self.rollback_succeeded,
            "workspace_clean": self.workspace_clean,
            "source_snapshot_before": self.source_snapshot_before,
            "source_snapshot_after": self.source_snapshot_after,
            "source_repository_unchanged": self.source_repository_unchanged,
            "check_capability_present": len(self.check_token) == 32,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


class _PatchApplyContext:
    def __init__(
        self,
        manifest: DeveloperTaskManifest,
        preflight_report: DeveloperTaskPreflightReport,
        workspace_report: DeveloperTaskWorkspaceReport,
        workspace_parent: Path,
    ) -> None:
        self.manifest = manifest
        self.preflight_report = preflight_report
        self.workspace_report = workspace_report
        self.workspace_parent = absolute_path(workspace_parent)
        self.manifest_fingerprint = ""
        self.workspace_id = workspace_report.workspace_id
        self.source_repository_root = workspace_report.source_repository_root
        self.task_root = workspace_report.task_root
        self.workspace_root = absolute_path(
            workspace_report.workspace_root or workspace_parent / "invalid"
        )
        self.repository_root = absolute_path(
            workspace_report.repository_root or self.workspace_root / "repository"
        )
        self.control_root = absolute_path(
            workspace_report.control_root or self.workspace_root / "control"
        )
        self.marker_path = absolute_path(
            workspace_report.marker_path or self.workspace_root / WORKSPACE_MARKER_NAME
        )
        self.apply_marker_path = self.control_root / PATCH_APPLY_MARKER_NAME
        self.base_commit = workspace_report.base_commit
        self.patch_sha256 = manifest.patch_sha256
        self.git_request: DeveloperTaskWorkspaceGitRequest | None = None
        self.git_evidence: DeveloperTaskPatchApplyGitEvidence | None = None
        self.apply_marker_sha256 = ""
        self.applied = False
        self.rollback_attempted = False
        self.rollback_succeeded = False
        self.workspace_clean = False
        self.check_token = b""
        self.source_before: DeveloperTaskSourceRepositorySnapshot | None = None
        self.source_after: DeveloperTaskSourceRepositorySnapshot | None = None
        self.workspace_metadata: os.stat_result | None = None
        self.repository_metadata: os.stat_result | None = None
        self.issues: list[DeveloperTaskPreflightIssue] = []

    def add(
        self,
        code: str,
        check: str,
        message: str,
        *,
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

    def report(self) -> DeveloperTaskPatchApplyReport:
        evidence = self.git_evidence
        before = self.source_before.fingerprint if self.source_before else ""
        after = self.source_after.fingerprint if self.source_after else ""
        return DeveloperTaskPatchApplyReport(
            manifest_fingerprint=self.manifest_fingerprint,
            workspace_id=self.workspace_id,
            source_repository_root=self.source_repository_root,
            task_root=self.task_root,
            workspace_parent=str(self.workspace_parent),
            workspace_root=str(self.workspace_root),
            repository_root=str(self.repository_root),
            apply_marker_path=str(self.apply_marker_path),
            apply_marker_sha256=self.apply_marker_sha256,
            base_commit=self.base_commit,
            head_commit=evidence.head_commit if evidence else "",
            patch_sha256=self.patch_sha256,
            changed_files=evidence.changed_files if evidence else (),
            changes=evidence.changes if evidence else (),
            result_index_paths=evidence.result_index_paths if evidence else (),
            result_tree=evidence.result_tree if evidence else "",
            staged_diff_sha256=evidence.staged_diff_sha256 if evidence else "",
            workspace_config_sha256=evidence.workspace_config_sha256 if evidence else "",
            applied=self.applied,
            rollback_attempted=self.rollback_attempted,
            rollback_succeeded=self.rollback_succeeded,
            workspace_clean=self.workspace_clean,
            source_snapshot_before=before,
            source_snapshot_after=after,
            source_repository_unchanged=bool(before and before == after),
            check_token=self.check_token,
            issues=tuple(self.issues),
        )


def _path_identity(value: os.stat_result) -> tuple[int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        int(getattr(value, "st_dev", 0)),
        int(getattr(value, "st_ino", 0)),
    )


def _safe_directory(path: Path) -> os.stat_result:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_path_missing",
            "Workspace path is missing.",
            actual=str(path),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_path_metadata_failed",
            "Workspace path metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISDIR(metadata.st_mode):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_path_not_directory",
            "Workspace path must be a directory.",
            actual=str(path),
        )

    if is_reparse_or_symlink(metadata):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_path_reparse_point",
            "Workspace path must not be a symlink, junction, or reparse point.",
            actual=str(path),
        )

    return metadata


def _find_unsafe_tree_entry(root: Path) -> tuple[str, str] | None:
    stack = [root]

    while stack:
        current = stack.pop()

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        metadata = entry.stat(follow_symlinks=False)
                    except FileNotFoundError:
                        continue

                    path = Path(entry.path)

                    if is_reparse_or_symlink(metadata):
                        return "workspace_tree_reparse_point", str(path)

                    if stat.S_ISDIR(metadata.st_mode):
                        stack.append(path)
                    elif not stat.S_ISREG(metadata.st_mode):
                        return "workspace_tree_special_file", str(path)
        except FileNotFoundError:
            return "workspace_tree_changed", str(current)
        except OSError as exc:
            return "workspace_tree_scan_failed", f"{type(exc).__name__}: {exc}"

    return None


def _workspace_marker_payload(report: DeveloperTaskWorkspaceReport) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workspace_id": report.workspace_id,
        "manifest_fingerprint": report.manifest_fingerprint,
        "source_repository_root": report.source_repository_root,
        "task_root": report.task_root,
        "workspace_root": report.workspace_root,
        "repository_root": report.repository_root,
        "git_dir": report.git_dir,
        "control_root": report.control_root,
        "base_commit": report.base_commit,
        "head_commit": report.head_commit,
        "cleanup_token_sha256": hashlib.sha256(report.cleanup_token).hexdigest(),
    }


def _validate_evidence(context: _PatchApplyContext) -> bool:
    try:
        context.manifest_fingerprint = developer_task_manifest_fingerprint(context.manifest)
    except (AttributeError, TypeError, ValueError) as exc:
        context.add(
            "manifest_invalid",
            "patch_apply_evidence",
            "Developer task manifest could not be fingerprinted.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    preflight = context.preflight_report
    workspace = context.workspace_report

    if not preflight.ok:
        context.add(
            "preflight_report_failed",
            "patch_apply_evidence",
            "Complete developer task preflight must be successful.",
            actual=",".join(preflight.issue_codes),
        )
        return False

    if not workspace.ok:
        context.add(
            "workspace_report_failed",
            "patch_apply_evidence",
            "Workspace creation report must be successful.",
            actual=",".join(workspace.issue_codes),
        )
        return False

    integrity = preflight.patch_integrity_report
    patch_index = preflight.patch_index_report
    patch_scope = preflight.patch_scope_report

    if (
        preflight.manifest_fingerprint != context.manifest_fingerprint
        or integrity is None
        or patch_index is None
        or patch_scope is None
        or not integrity.ok
        or not patch_index.ok
        or not patch_scope.ok
        or integrity.patch is None
        or preflight.changed_files != patch_index.changed_files
        or patch_scope.changed_files != patch_index.changed_files
    ):
        context.add(
            "preflight_report_invalid",
            "patch_apply_evidence",
            "Complete preflight evidence is internally inconsistent.",
        )
        return False

    patch = integrity.patch

    if (
        hashlib.sha256(patch.content).hexdigest() != context.manifest.patch_sha256
        or patch.sha256 != context.manifest.patch_sha256
        or len(patch.content) != patch.size_bytes
    ):
        context.add(
            "patch_snapshot_invalid",
            "patch_apply_evidence",
            "Preflight patch bytes do not match the manifest SHA-256.",
        )
        return False

    if (
        workspace.manifest_fingerprint != context.manifest_fingerprint
        or not same_path(workspace.source_repository_root, preflight.repository_root)
        or not same_path(workspace.task_root, integrity.task_root)
        or workspace.base_commit != preflight.base_commit
        or workspace.head_commit != preflight.base_commit
        or not workspace.source_repository_unchanged
        or len(workspace.cleanup_token) != 32
        or len(workspace.marker_sha256) != 64
    ):
        context.add(
            "workspace_report_invalid",
            "patch_apply_evidence",
            "Workspace evidence is inconsistent with successful preflight.",
        )
        return False

    if not same_path(workspace.workspace_parent, context.workspace_parent):
        context.add(
            "workspace_parent_mismatch",
            "patch_apply_evidence",
            "Explicit workspace parent does not match workspace evidence.",
            expected=workspace.workspace_parent,
            actual=str(context.workspace_parent),
        )
        return False

    if not workspace_id_matches(
        context.manifest.task_id,
        context.manifest_fingerprint,
        workspace.workspace_id,
    ):
        context.add(
            "workspace_id_invalid",
            "patch_apply_evidence",
            "Workspace ID does not match manifest evidence.",
            actual=workspace.workspace_id,
        )
        return False

    expected_root = context.workspace_parent / workspace.workspace_id
    expected_repository = expected_root / "repository"
    expected_control = expected_root / "control"
    expected_marker = expected_root / WORKSPACE_MARKER_NAME
    expected_git_dir = expected_repository / ".git"

    if not all((
        same_path(context.workspace_root, expected_root),
        same_path(context.repository_root, expected_repository),
        same_path(context.control_root, expected_control),
        same_path(context.marker_path, expected_marker),
        same_path(workspace.git_dir, expected_git_dir),
        same_path(workspace.hooks_path, expected_control / "hooks"),
    )):
        context.add(
            "workspace_report_paths_invalid",
            "patch_apply_evidence",
            "Workspace paths do not match the fixed layout.",
        )
        return False

    source = absolute_path(workspace.source_repository_root)
    task = absolute_path(workspace.task_root)

    if (
        paths_overlap(context.workspace_root, source)
        or paths_overlap(context.workspace_root, task)
        or paths_overlap(context.workspace_parent, source)
        or paths_overlap(context.workspace_parent, task)
    ):
        context.add(
            "workspace_paths_overlap",
            "patch_apply_evidence",
            "Workspace paths must remain isolated from source and task roots.",
        )
        return False

    context.git_request = DeveloperTaskWorkspaceGitRequest(
        source_repository_root=workspace.source_repository_root,
        repository_root=workspace.repository_root,
        home_root=str(expected_control / "home"),
        xdg_root=str(expected_control / "xdg"),
        hooks_path=workspace.hooks_path,
        template_root=str(expected_control / "template"),
        global_config_path=str(expected_control / "gitconfig"),
        base_commit=workspace.base_commit,
    )
    return True


def _validate_workspace_filesystem(context: _PatchApplyContext) -> bool:
    try:
        validate_workspace_parent(context.workspace_parent)
        context.workspace_metadata = validate_workspace_root(context.workspace_root)

        if context.workspace_metadata is None:
            raise DeveloperTaskWorkspaceCleanupFileSystemError(
                "workspace_root_missing",
                "Workspace root is missing.",
                actual=str(context.workspace_root),
            )

        context.repository_metadata = _safe_directory(context.repository_root)
        _safe_directory(context.control_root)
        marker = read_workspace_marker(
            context.marker_path,
            context.workspace_report.marker_sha256,
        )
        validate_canonical_marker(
            marker,
            _workspace_marker_payload(context.workspace_report),
        )
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        context.add(exc.code, "patch_apply_workspace", str(exc), actual=exc.actual)
        return False

    try:
        apply_marker_metadata = os.lstat(context.apply_marker_path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        context.add(
            "patch_apply_marker_metadata_failed",
            "patch_apply_workspace",
            "Patch apply marker metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False
    else:
        context.add(
            "patch_already_applied",
            "patch_apply_workspace",
            "Patch apply marker already exists for this workspace.",
            actual=(
                "reparse" if is_reparse_or_symlink(apply_marker_metadata)
                else str(context.apply_marker_path)
            ),
        )
        return False

    unsafe = _find_unsafe_tree_entry(context.workspace_root)

    if unsafe is not None:
        code, actual = unsafe
        context.add(
            code,
            "patch_apply_workspace",
            "Workspace tree contains an unsafe entry before patch application.",
            actual=actual,
        )
        return False

    return True


def _capture_source_before(context: _PatchApplyContext) -> bool:
    try:
        context.source_before = snapshot_developer_task_source_repository(
            Path(context.source_repository_root)
        )
    except Exception as exc:
        code = getattr(exc, "code", "source_snapshot_failed")
        actual = getattr(exc, "actual", f"{type(exc).__name__}: {exc}")
        context.add(code, "patch_apply_source", str(exc), actual=actual)
        return False

    return True


def _capture_source_after(context: _PatchApplyContext) -> None:
    try:
        context.source_after = snapshot_developer_task_source_repository(
            Path(context.source_repository_root)
        )
    except Exception as exc:
        code = getattr(exc, "code", "source_snapshot_failed")
        actual = getattr(exc, "actual", f"{type(exc).__name__}: {exc}")
        context.add(code, "patch_apply_source", str(exc), actual=actual)
        return

    if (
        context.source_before is not None
        and context.source_after.fingerprint != context.source_before.fingerprint
    ):
        context.add(
            "source_repository_changed",
            "patch_apply_source",
            "Source repository changed during isolated patch application.",
        )


def _same_directory_identity(
    initial: os.stat_result | None,
    path: Path,
) -> bool:
    if initial is None:
        return False

    try:
        current = os.lstat(path)
    except OSError:
        return False

    return (
        stat.S_ISDIR(current.st_mode)
        and not is_reparse_or_symlink(current)
        and _path_identity(initial) == _path_identity(current)
    )


def _apply_marker_payload(
    context: _PatchApplyContext,
    evidence: DeveloperTaskPatchApplyGitEvidence,
) -> dict[str, Any]:
    return {
        "schema_version": PATCH_APPLY_MARKER_SCHEMA_VERSION,
        "workspace_id": context.workspace_id,
        "manifest_fingerprint": context.manifest_fingerprint,
        "workspace_root": str(context.workspace_root),
        "repository_root": str(context.repository_root),
        "base_commit": context.base_commit,
        "head_commit": evidence.head_commit,
        "patch_sha256": context.patch_sha256,
        "changed_files": list(evidence.changed_files),
        "changes": [item.to_dict() for item in evidence.changes],
        "result_index_paths": list(evidence.result_index_paths),
        "result_tree": evidence.result_tree,
        "staged_diff_sha256": evidence.staged_diff_sha256,
        "workspace_config_sha256": evidence.workspace_config_sha256,
        "check_token_sha256": hashlib.sha256(context.check_token).hexdigest(),
    }


def _remove_partial_apply_marker(context: _PatchApplyContext) -> None:
    try:
        metadata = os.lstat(context.apply_marker_path)
    except FileNotFoundError:
        return
    except OSError:
        return

    if stat.S_ISREG(metadata.st_mode) and not is_reparse_or_symlink(metadata):
        try:
            os.unlink(context.apply_marker_path)
        except OSError:
            return


def _write_apply_marker(context: _PatchApplyContext) -> bool:
    assert context.git_evidence is not None
    context.check_token = secrets.token_bytes(32)
    payload = _apply_marker_payload(context, context.git_evidence)
    data = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    try:
        descriptor = os.open(
            context.apply_marker_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )

        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        _remove_partial_apply_marker(context)
        context.add(
            "patch_apply_marker_write_failed",
            "patch_apply_marker",
            "Patch apply marker could not be written.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        context.check_token = b""
        return False

    context.apply_marker_sha256 = hashlib.sha256(data).hexdigest()
    return True


def _verify_apply_marker(context: _PatchApplyContext) -> bool:
    assert context.git_evidence is not None

    try:
        marker = read_workspace_marker(
            context.apply_marker_path,
            context.apply_marker_sha256,
        )
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        context.add(
            "patch_apply_marker_invalid",
            "patch_apply_marker",
            "Patch apply marker could not be verified after writing.",
            actual=f"{exc.code}:{exc.actual or str(exc)}",
        )
        return False

    expected = _apply_marker_payload(context, context.git_evidence)
    canonical = json.dumps(
        expected,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    if marker.payload != expected or marker.content != canonical:
        context.add(
            "patch_apply_marker_invalid",
            "patch_apply_marker",
            "Patch apply marker does not match canonical apply evidence.",
        )
        return False

    return True


def _record_rollback(
    context: _PatchApplyContext,
    result: DeveloperTaskPatchApplyRollbackResult,
) -> None:
    context.rollback_attempted = result.attempted
    context.rollback_succeeded = result.succeeded
    context.workspace_clean = result.workspace_clean

    if not result.succeeded:
        context.add(
            "workspace_patch_rollback_failed",
            "patch_apply_rollback",
            "Applied workspace could not be restored to the clean base state.",
            actual=result.actual,
        )


def _rollback_after_orchestration_failure(context: _PatchApplyContext) -> None:
    _remove_partial_apply_marker(context)
    context.apply_marker_sha256 = ""
    context.check_token = b""

    if context.git_request is None:
        return

    try:
        result = restore_independent_workspace_base(context.git_request)
    except Exception as exc:
        context.rollback_attempted = True
        context.rollback_succeeded = False
        context.workspace_clean = False
        context.add(
            "workspace_patch_rollback_failed",
            "patch_apply_rollback",
            "Applied workspace rollback could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return

    _record_rollback(context, result)


def apply_developer_task_patch(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    workspace_parent: Path,
) -> DeveloperTaskPatchApplyReport:
    """Apply exact verified patch bytes only inside the independent workspace."""

    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(preflight_report, DeveloperTaskPreflightReport):
        raise TypeError("preflight_report must be DeveloperTaskPreflightReport")

    if not isinstance(workspace_report, DeveloperTaskWorkspaceReport):
        raise TypeError("workspace_report must be DeveloperTaskWorkspaceReport")

    if not isinstance(workspace_parent, Path):
        raise TypeError("workspace_parent must be pathlib.Path")

    context = _PatchApplyContext(
        manifest,
        preflight_report,
        workspace_report,
        workspace_parent,
    )

    if not _validate_evidence(context):
        return context.report()

    if not _validate_workspace_filesystem(context):
        return context.report()

    if not _capture_source_before(context):
        return context.report()

    integrity = preflight_report.patch_integrity_report
    patch_index = preflight_report.patch_index_report
    assert integrity is not None and integrity.patch is not None
    assert patch_index is not None
    assert context.git_request is not None

    request = DeveloperTaskPatchApplyGitRequest(
        workspace_git_request=context.git_request,
        patch_bytes=integrity.patch.content,
        patch_sha256=manifest.patch_sha256,
        expected_changes=patch_index.changes,
        expected_result_index_paths=patch_index.result_index_paths,
    )

    try:
        context.git_evidence = apply_patch_to_independent_workspace(request)
    except DeveloperTaskPatchApplyGitError as exc:
        context.rollback_attempted = exc.rollback_attempted
        context.rollback_succeeded = exc.rollback_succeeded
        context.workspace_clean = exc.workspace_clean
        context.add(exc.code, "patch_apply_git", str(exc), actual=exc.actual)
        _capture_source_after(context)
        return context.report()
    except Exception as exc:
        context.add(
            "patch_apply_unexpected_error",
            "patch_apply_git",
            "Unexpected patch apply error was contained.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        _rollback_after_orchestration_failure(context)
        _capture_source_after(context)
        return context.report()

    context.applied = True

    unsafe = _find_unsafe_tree_entry(context.workspace_root)

    if unsafe is not None:
        code, actual = unsafe
        context.add(
            code,
            "patch_apply_postcondition",
            "Workspace tree became unsafe after patch application.",
            actual=actual,
        )

    if (
        not _same_directory_identity(context.workspace_metadata, context.workspace_root)
        or not _same_directory_identity(context.repository_metadata, context.repository_root)
    ):
        context.add(
            "workspace_identity_changed",
            "patch_apply_postcondition",
            "Workspace directory identity changed during patch application.",
        )

    try:
        marker = read_workspace_marker(
            context.marker_path,
            workspace_report.marker_sha256,
        )
        validate_canonical_marker(marker, _workspace_marker_payload(workspace_report))
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        context.add(exc.code, "patch_apply_postcondition", str(exc), actual=exc.actual)

    _capture_source_after(context)

    if context.issues:
        context.applied = False
        _rollback_after_orchestration_failure(context)
        return context.report()

    if not _write_apply_marker(context):
        context.applied = False
        _rollback_after_orchestration_failure(context)
        return context.report()

    if not _verify_apply_marker(context):
        context.applied = False
        _rollback_after_orchestration_failure(context)
        return context.report()

    return context.report()
