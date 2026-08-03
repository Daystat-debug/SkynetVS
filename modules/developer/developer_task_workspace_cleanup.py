from __future__ import annotations

"""Fail-closed lifecycle cleanup for verified developer-task workspaces."""

import hashlib

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_preflight_composition import DeveloperTaskPreflightReport
from modules.developer.developer_task_workspace import DeveloperTaskWorkspaceReport
from modules.developer.developer_task_workspace_cleanup_fs import (
    WORKSPACE_MARKER_NAME,
    DeveloperTaskWorkspaceCleanupFileSystemError,
    absolute_path,
    paths_overlap,
    read_workspace_marker,
    remove_verified_workspace,
    same_path,
    validate_canonical_marker,
    validate_workspace_parent,
    validate_workspace_root,
    workspace_id_matches,
)
from modules.developer.developer_task_workspace_git import DeveloperTaskWorkspaceGitError
from modules.developer.developer_task_workspace_source import (
    DeveloperTaskSourceRepositorySnapshot,
    snapshot_developer_task_source_repository,
)


@dataclass(frozen=True)
class DeveloperTaskWorkspaceCleanupReport:
    """Immutable evidence for one explicit workspace cleanup attempt."""

    manifest_fingerprint: str
    workspace_id: str
    source_repository_root: str
    task_root: str
    workspace_parent: str
    workspace_root: str
    marker_path: str
    marker_sha256: str
    base_commit: str
    removed: bool
    already_absent: bool
    attempts: int
    source_snapshot_before: str
    source_snapshot_after: str
    source_repository_unchanged: bool
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
            and bool(self.marker_path)
            and bool(self.marker_sha256)
            and bool(self.base_commit)
            and self.removed != self.already_absent
            and self.attempts >= 0
            and bool(self.source_snapshot_before)
            and self.source_snapshot_before == self.source_snapshot_after
            and self.source_repository_unchanged
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    @property
    def state(self) -> str:
        if self.removed:
            return "removed"
        if self.already_absent:
            return "already_absent"
        return "failed"

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
            "marker_path": self.marker_path,
            "marker_sha256": self.marker_sha256,
            "base_commit": self.base_commit,
            "removed": self.removed,
            "already_absent": self.already_absent,
            "attempts": self.attempts,
            "source_snapshot_before": self.source_snapshot_before,
            "source_snapshot_after": self.source_snapshot_after,
            "source_repository_unchanged": self.source_repository_unchanged,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


class _CleanupContext:
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
        self.marker_path = absolute_path(
            workspace_report.marker_path
            or self.workspace_root / WORKSPACE_MARKER_NAME
        )
        self.marker_sha256 = workspace_report.marker_sha256
        self.base_commit = workspace_report.base_commit
        self.removed = False
        self.already_absent = False
        self.attempts = 0
        self.source_before: DeveloperTaskSourceRepositorySnapshot | None = None
        self.source_after: DeveloperTaskSourceRepositorySnapshot | None = None
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

    def report(self) -> DeveloperTaskWorkspaceCleanupReport:
        before = self.source_before.fingerprint if self.source_before else ""
        after = self.source_after.fingerprint if self.source_after else ""
        return DeveloperTaskWorkspaceCleanupReport(
            manifest_fingerprint=self.manifest_fingerprint,
            workspace_id=self.workspace_id,
            source_repository_root=self.source_repository_root,
            task_root=self.task_root,
            workspace_parent=str(self.workspace_parent),
            workspace_root=str(self.workspace_root),
            marker_path=str(self.marker_path),
            marker_sha256=self.marker_sha256,
            base_commit=self.base_commit,
            removed=self.removed,
            already_absent=self.already_absent,
            attempts=self.attempts,
            source_snapshot_before=before,
            source_snapshot_after=after,
            source_repository_unchanged=bool(before and before == after),
            issues=tuple(self.issues),
        )


def _validate_evidence(context: _CleanupContext) -> bool:
    try:
        context.manifest_fingerprint = developer_task_manifest_fingerprint(context.manifest)
    except (AttributeError, TypeError, ValueError) as exc:
        context.add(
            "manifest_invalid",
            "workspace_cleanup_evidence",
            "Developer task manifest could not be fingerprinted.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    preflight = context.preflight_report
    workspace = context.workspace_report

    if not preflight.ok:
        context.add(
            "preflight_report_failed",
            "workspace_cleanup_evidence",
            "Complete developer task preflight must be successful.",
            actual=", ".join(preflight.issue_codes),
        )
        return False

    if not workspace.ok:
        context.add(
            "workspace_report_failed",
            "workspace_cleanup_evidence",
            "Workspace creation report must be successful.",
            actual=", ".join(workspace.issue_codes),
        )
        return False

    integrity = preflight.patch_integrity_report

    if (
        preflight.manifest_fingerprint != context.manifest_fingerprint
        or not preflight.repository_root
        or not preflight.base_commit
        or integrity is None
        or not integrity.ok
        or not integrity.task_root
    ):
        context.add(
            "preflight_report_invalid",
            "workspace_cleanup_evidence",
            "Complete developer task preflight evidence is inconsistent.",
        )
        return False

    if (
        workspace.manifest_fingerprint != context.manifest_fingerprint
        or workspace.source_repository_root != preflight.repository_root
        or workspace.task_root != integrity.task_root
        or workspace.base_commit != preflight.base_commit
        or workspace.head_commit != preflight.base_commit
        or not workspace.source_repository_unchanged
        or len(workspace.cleanup_token) != 32
        or len(workspace.marker_sha256) != 64
    ):
        context.add(
            "workspace_report_invalid",
            "workspace_cleanup_evidence",
            "Workspace creation evidence is inconsistent with successful preflight.",
        )
        return False

    if not same_path(workspace.workspace_parent, context.workspace_parent):
        context.add(
            "workspace_parent_mismatch",
            "workspace_cleanup_evidence",
            "Explicit workspace parent does not match workspace evidence.",
            expected=workspace.workspace_parent,
            actual=str(context.workspace_parent),
        )
        return False

    if not workspace_id_matches(
        context.manifest.task_id,
        context.manifest_fingerprint,
        context.workspace_id,
    ):
        context.add(
            "workspace_id_invalid",
            "workspace_cleanup_evidence",
            "Workspace ID does not match manifest and fingerprint evidence.",
            actual=context.workspace_id,
        )
        return False

    expected_root = context.workspace_parent / workspace.workspace_id
    expected_repository = expected_root / "repository"
    expected_control = expected_root / "control"
    expected_marker = expected_root / WORKSPACE_MARKER_NAME
    expected_git_dir = expected_repository / ".git"

    if (
        not same_path(workspace.workspace_root, expected_root)
        or not same_path(workspace.repository_root, expected_repository)
        or not same_path(workspace.control_root, expected_control)
        or not same_path(workspace.marker_path, expected_marker)
        or not same_path(workspace.git_dir, expected_git_dir)
    ):
        context.add(
            "workspace_report_paths_invalid",
            "workspace_cleanup_evidence",
            "Workspace paths do not match the dedicated workspace layout.",
        )
        return False

    source = absolute_path(context.source_repository_root)
    task_root = absolute_path(context.task_root)

    if (
        paths_overlap(context.workspace_parent, source)
        or paths_overlap(context.workspace_parent, task_root)
        or paths_overlap(context.workspace_root, source)
        or paths_overlap(context.workspace_root, task_root)
    ):
        context.add(
            "workspace_cleanup_path_overlap",
            "workspace_cleanup_evidence",
            "Workspace cleanup target must not overlap source or task roots.",
            actual=str(context.workspace_root),
        )
        return False

    return True


def _capture_source_before(context: _CleanupContext) -> bool:
    try:
        context.source_before = snapshot_developer_task_source_repository(
            Path(context.source_repository_root)
        )
    except DeveloperTaskWorkspaceGitError as exc:
        context.add(exc.code, "workspace_cleanup_source", str(exc), actual=exc.actual)
        return False
    except OSError as exc:
        context.add(
            "source_repository_snapshot_failed",
            "workspace_cleanup_source",
            "Source repository snapshot failed.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    return True


def _capture_source_after(context: _CleanupContext) -> None:
    try:
        context.source_after = snapshot_developer_task_source_repository(
            Path(context.source_repository_root)
        )
    except DeveloperTaskWorkspaceGitError as exc:
        context.add(exc.code, "workspace_cleanup_source", str(exc), actual=exc.actual)
        return
    except OSError as exc:
        context.add(
            "source_repository_snapshot_failed",
            "workspace_cleanup_source",
            "Source repository snapshot failed after cleanup.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return

    if context.source_before != context.source_after:
        context.add(
            "source_repository_changed",
            "workspace_cleanup_source",
            "Source repository changed during workspace cleanup.",
        )


def _expected_marker_payload(context: _CleanupContext) -> dict[str, Any]:
    workspace = context.workspace_report
    return {
        "schema_version": 1,
        "workspace_id": workspace.workspace_id,
        "manifest_fingerprint": workspace.manifest_fingerprint,
        "source_repository_root": workspace.source_repository_root,
        "task_root": workspace.task_root,
        "workspace_root": workspace.workspace_root,
        "repository_root": workspace.repository_root,
        "git_dir": workspace.git_dir,
        "control_root": workspace.control_root,
        "base_commit": workspace.base_commit,
        "head_commit": workspace.head_commit,
        "cleanup_token_sha256": hashlib.sha256(workspace.cleanup_token).hexdigest(),
    }


def _add_fs_issue(
    context: _CleanupContext,
    error: DeveloperTaskWorkspaceCleanupFileSystemError,
    check: str,
) -> None:
    context.attempts = max(context.attempts, error.attempts)
    context.add(error.code, check, str(error), actual=error.actual)


def cleanup_developer_task_workspace(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceCleanupReport:
    """Remove only the workspace proven by capability, marker, and evidence."""

    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(preflight_report, DeveloperTaskPreflightReport):
        raise TypeError("preflight_report must be DeveloperTaskPreflightReport")

    if not isinstance(workspace_report, DeveloperTaskWorkspaceReport):
        raise TypeError("workspace_report must be DeveloperTaskWorkspaceReport")

    if not isinstance(workspace_parent, Path):
        raise TypeError("workspace_parent must be pathlib.Path")

    context = _CleanupContext(
        manifest,
        preflight_report,
        workspace_report,
        workspace_parent,
    )

    if not _validate_evidence(context):
        return context.report()

    try:
        validate_workspace_parent(context.workspace_parent)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        _add_fs_issue(context, exc, "workspace_cleanup_parent")
        return context.report()

    if not _capture_source_before(context):
        return context.report()

    try:
        root_metadata = validate_workspace_root(context.workspace_root)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        _add_fs_issue(context, exc, "workspace_cleanup_target")
        _capture_source_after(context)
        return context.report()

    if root_metadata is None:
        context.already_absent = True
        _capture_source_after(context)
        return context.report()

    try:
        marker = read_workspace_marker(
            context.marker_path,
            context.marker_sha256,
        )
        validate_canonical_marker(marker, _expected_marker_payload(context))
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        _add_fs_issue(context, exc, "workspace_cleanup_marker")
        _capture_source_after(context)
        return context.report()

    try:
        removal = remove_verified_workspace(context.workspace_root, root_metadata)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        _add_fs_issue(context, exc, "workspace_cleanup_remove")
    else:
        context.removed = removal.removed
        context.already_absent = removal.already_absent
        context.attempts = removal.attempts

    _capture_source_after(context)
    return context.report()
