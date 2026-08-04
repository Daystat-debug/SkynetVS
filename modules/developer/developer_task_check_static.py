from __future__ import annotations

"""Fail-closed static checks for a verified applied developer-task workspace."""

import hashlib
import json
import os
import stat

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_check_static_git import (
    DeveloperTaskStaticGitError,
    DeveloperTaskStaticGitEvidence,
    verify_developer_task_static_git,
)
from modules.developer.developer_task_check_static_python import (
    DeveloperTaskStaticPythonError,
    DeveloperTaskStaticPythonEvidence,
    compile_changed_python_files,
)
from modules.developer.developer_task_contract import (
    DEVELOPER_CHECK_GIT_DIFF,
    DEVELOPER_CHECK_PIPELINE,
    DEVELOPER_CHECK_PY_COMPILE,
    DEVELOPER_CHECK_PYTHON_MODULE,
    DeveloperTaskCheck,
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_patch_apply import (
    PATCH_APPLY_MARKER_SCHEMA_VERSION,
    DeveloperTaskPatchApplyReport,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_preflight_composition import DeveloperTaskPreflightReport
from modules.developer.developer_task_validator import validate_developer_task_manifest
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
from modules.developer.developer_task_workspace_git import (
    DeveloperTaskWorkspaceGitError,
    DeveloperTaskWorkspaceGitRequest,
)
from modules.developer.developer_task_workspace_source import (
    DeveloperTaskSourceRepositorySnapshot,
    snapshot_developer_task_source_repository,
)


@dataclass(frozen=True)
class DeveloperTaskStaticCheckReport:
    """Immutable evidence for trusted static checks only."""

    manifest_fingerprint: str
    workspace_id: str
    source_repository_root: str
    task_root: str
    workspace_parent: str
    workspace_root: str
    repository_root: str
    base_commit: str
    changed_files: tuple[str, ...]
    changed_python_files: tuple[str, ...]
    completed_checks: tuple[str, ...]
    pending_executable_checks: tuple[DeveloperTaskCheck, ...]
    git_evidence_before: DeveloperTaskStaticGitEvidence | None
    git_evidence_after: DeveloperTaskStaticGitEvidence | None
    python_evidence: DeveloperTaskStaticPythonEvidence | None
    source_snapshot_before: str
    source_snapshot_after: str
    source_repository_unchanged: bool
    workspace_unchanged: bool
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        expected_static = {DEVELOPER_CHECK_GIT_DIFF}
        if self.changed_python_files or self.python_evidence is not None:
            expected_static.add(DEVELOPER_CHECK_PY_COMPILE)

        return (
            bool(self.manifest_fingerprint)
            and bool(self.workspace_id)
            and bool(self.source_repository_root)
            and bool(self.workspace_root)
            and bool(self.repository_root)
            and bool(self.base_commit)
            and bool(self.changed_files)
            and self.git_evidence_before is not None
            and self.git_evidence_before == self.git_evidence_after
            and self.workspace_unchanged
            and bool(self.source_snapshot_before)
            and self.source_snapshot_before == self.source_snapshot_after
            and self.source_repository_unchanged
            and expected_static.issubset(set(self.completed_checks))
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest_fingerprint": self.manifest_fingerprint,
            "workspace_id": self.workspace_id,
            "source_repository_root": self.source_repository_root,
            "task_root": self.task_root,
            "workspace_parent": self.workspace_parent,
            "workspace_root": self.workspace_root,
            "repository_root": self.repository_root,
            "base_commit": self.base_commit,
            "changed_files": list(self.changed_files),
            "changed_python_files": list(self.changed_python_files),
            "completed_checks": list(self.completed_checks),
            "pending_executable_checks": [
                item.to_dict()
                for item in self.pending_executable_checks
            ],
            "git_evidence_before": (
                self.git_evidence_before.to_dict()
                if self.git_evidence_before is not None
                else None
            ),
            "git_evidence_after": (
                self.git_evidence_after.to_dict()
                if self.git_evidence_after is not None
                else None
            ),
            "python_evidence": (
                self.python_evidence.to_dict()
                if self.python_evidence is not None
                else None
            ),
            "source_snapshot_before": self.source_snapshot_before,
            "source_snapshot_after": self.source_snapshot_after,
            "source_repository_unchanged": self.source_repository_unchanged,
            "workspace_unchanged": self.workspace_unchanged,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


class _StaticCheckContext:
    def __init__(
        self,
        manifest: DeveloperTaskManifest,
        preflight_report: DeveloperTaskPreflightReport,
        workspace_report: DeveloperTaskWorkspaceReport,
        patch_apply_report: DeveloperTaskPatchApplyReport,
        workspace_parent: Path,
    ) -> None:
        self.manifest = manifest
        self.preflight_report = preflight_report
        self.workspace_report = workspace_report
        self.patch_apply_report = patch_apply_report
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
        self.workspace_marker_path = absolute_path(
            workspace_report.marker_path or self.workspace_root / WORKSPACE_MARKER_NAME
        )
        self.apply_marker_path = absolute_path(
            patch_apply_report.apply_marker_path
            or self.control_root / "patch_apply.json"
        )
        self.base_commit = workspace_report.base_commit
        self.changed_files = patch_apply_report.changed_files
        self.changed_python_files = tuple(
            path
            for path in self.changed_files
            if path.casefold().endswith(".py")
        )
        self.completed_checks: list[str] = []
        self.pending_executable_checks = tuple(
            check
            for check in manifest.checks
            if check.type in {
                DEVELOPER_CHECK_PYTHON_MODULE,
                DEVELOPER_CHECK_PIPELINE,
            }
        )
        self.git_request: DeveloperTaskWorkspaceGitRequest | None = None
        self.git_before: DeveloperTaskStaticGitEvidence | None = None
        self.git_after: DeveloperTaskStaticGitEvidence | None = None
        self.python_evidence: DeveloperTaskStaticPythonEvidence | None = None
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

    def report(self) -> DeveloperTaskStaticCheckReport:
        before = self.source_before.fingerprint if self.source_before else ""
        after = self.source_after.fingerprint if self.source_after else ""
        return DeveloperTaskStaticCheckReport(
            manifest_fingerprint=self.manifest_fingerprint,
            workspace_id=self.workspace_id,
            source_repository_root=self.source_repository_root,
            task_root=self.task_root,
            workspace_parent=str(self.workspace_parent),
            workspace_root=str(self.workspace_root),
            repository_root=str(self.repository_root),
            base_commit=self.base_commit,
            changed_files=self.changed_files,
            changed_python_files=self.changed_python_files,
            completed_checks=tuple(self.completed_checks),
            pending_executable_checks=self.pending_executable_checks,
            git_evidence_before=self.git_before,
            git_evidence_after=self.git_after,
            python_evidence=self.python_evidence,
            source_snapshot_before=before,
            source_snapshot_after=after,
            source_repository_unchanged=bool(before and before == after),
            workspace_unchanged=bool(
                self.git_before is not None
                and self.git_before == self.git_after
            ),
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


def _apply_marker_payload(report: DeveloperTaskPatchApplyReport) -> dict[str, Any]:
    return {
        "schema_version": PATCH_APPLY_MARKER_SCHEMA_VERSION,
        "workspace_id": report.workspace_id,
        "manifest_fingerprint": report.manifest_fingerprint,
        "workspace_root": report.workspace_root,
        "repository_root": report.repository_root,
        "base_commit": report.base_commit,
        "head_commit": report.head_commit,
        "patch_sha256": report.patch_sha256,
        "changed_files": list(report.changed_files),
        "changes": [item.to_dict() for item in report.changes],
        "result_index_paths": list(report.result_index_paths),
        "result_tree": report.result_tree,
        "staged_diff_sha256": report.staged_diff_sha256,
        "workspace_config_sha256": report.workspace_config_sha256,
        "check_token_sha256": hashlib.sha256(report.check_token).hexdigest(),
    }


def _validate_manifest(context: _StaticCheckContext) -> bool:
    try:
        context.manifest_fingerprint = developer_task_manifest_fingerprint(
            context.manifest
        )
    except (AttributeError, TypeError, ValueError) as exc:
        context.add(
            "manifest_invalid",
            "static_manifest",
            "Developer task manifest could not be fingerprinted.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    validation = validate_developer_task_manifest(context.manifest.to_dict())

    if (
        not validation.ok
        or validation.manifest != context.manifest
    ):
        context.add(
            "manifest_invalid",
            "static_manifest",
            "Developer task manifest is not canonical.",
            actual=",".join(validation.issue_codes),
        )
        return False

    return True


def _validate_evidence(context: _StaticCheckContext) -> bool:
    preflight = context.preflight_report
    workspace = context.workspace_report
    apply_report = context.patch_apply_report

    if not preflight.ok:
        context.add(
            "preflight_report_failed",
            "static_evidence",
            "Complete developer task preflight must be successful.",
            actual=",".join(preflight.issue_codes),
        )
        return False

    if not workspace.ok:
        context.add(
            "workspace_report_failed",
            "static_evidence",
            "Workspace creation report must be successful.",
            actual=",".join(workspace.issue_codes),
        )
        return False

    if not apply_report.ok:
        context.add(
            "patch_apply_report_failed",
            "static_evidence",
            "Patch Apply V1 report must be successful.",
            actual=",".join(apply_report.issue_codes),
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
            "static_evidence",
            "Complete preflight evidence is internally inconsistent.",
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
            "static_evidence",
            "Workspace evidence is inconsistent with successful preflight.",
        )
        return False

    if (
        apply_report.manifest_fingerprint != context.manifest_fingerprint
        or apply_report.workspace_id != workspace.workspace_id
        or not same_path(apply_report.source_repository_root, workspace.source_repository_root)
        or not same_path(apply_report.task_root, workspace.task_root)
        or not same_path(apply_report.workspace_parent, workspace.workspace_parent)
        or not same_path(apply_report.workspace_root, workspace.workspace_root)
        or not same_path(apply_report.repository_root, workspace.repository_root)
        or apply_report.base_commit != workspace.base_commit
        or apply_report.head_commit != workspace.base_commit
        or apply_report.patch_sha256 != context.manifest.patch_sha256
        or apply_report.changed_files != patch_index.changed_files
        or apply_report.changes != patch_index.changes
        or apply_report.result_index_paths != patch_index.result_index_paths
        or not apply_report.source_repository_unchanged
        or apply_report.source_snapshot_before != apply_report.source_snapshot_after
        or len(apply_report.check_token) != 32
        or len(apply_report.apply_marker_sha256) != 64
    ):
        context.add(
            "patch_apply_report_invalid",
            "static_evidence",
            "Patch Apply V1 evidence is inconsistent with preflight and workspace reports.",
        )
        return False

    if not same_path(workspace.workspace_parent, context.workspace_parent):
        context.add(
            "workspace_parent_mismatch",
            "static_evidence",
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
            "static_evidence",
            "Workspace ID does not match manifest evidence.",
            actual=workspace.workspace_id,
        )
        return False

    expected_root = context.workspace_parent / workspace.workspace_id
    expected_repository = expected_root / "repository"
    expected_control = expected_root / "control"
    expected_workspace_marker = expected_root / WORKSPACE_MARKER_NAME
    expected_apply_marker = expected_control / "patch_apply.json"
    expected_git_dir = expected_repository / ".git"

    if not all((
        same_path(context.workspace_root, expected_root),
        same_path(context.repository_root, expected_repository),
        same_path(context.control_root, expected_control),
        same_path(context.workspace_marker_path, expected_workspace_marker),
        same_path(context.apply_marker_path, expected_apply_marker),
        same_path(workspace.git_dir, expected_git_dir),
        same_path(workspace.hooks_path, expected_control / "hooks"),
    )):
        context.add(
            "workspace_report_paths_invalid",
            "static_evidence",
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
            "static_evidence",
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


def _validate_filesystem_and_markers(context: _StaticCheckContext) -> bool:
    try:
        validate_workspace_parent(context.workspace_parent)
        workspace_metadata = validate_workspace_root(context.workspace_root)

        if workspace_metadata is None:
            raise DeveloperTaskWorkspaceCleanupFileSystemError(
                "workspace_root_missing",
                "Workspace root is missing.",
                actual=str(context.workspace_root),
            )

        _safe_directory(context.repository_root)
        _safe_directory(context.control_root)

        workspace_marker = read_workspace_marker(
            context.workspace_marker_path,
            context.workspace_report.marker_sha256,
        )
        validate_canonical_marker(
            workspace_marker,
            _workspace_marker_payload(context.workspace_report),
        )

        apply_marker = read_workspace_marker(
            context.apply_marker_path,
            context.patch_apply_report.apply_marker_sha256,
        )
        validate_canonical_marker(
            apply_marker,
            _apply_marker_payload(context.patch_apply_report),
        )
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        context.add(
            exc.code,
            "static_workspace",
            str(exc),
            actual=exc.actual,
        )
        return False

    return True


def _capture_source(
    context: _StaticCheckContext,
    *,
    after: bool,
) -> bool:
    try:
        snapshot = snapshot_developer_task_source_repository(
            Path(context.source_repository_root)
        )
    except (DeveloperTaskWorkspaceGitError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "source_repository_snapshot_failed")
        actual = getattr(exc, "actual", f"{type(exc).__name__}: {exc}")
        context.add(
            code,
            "static_source",
            "Source repository snapshot could not be captured.",
            actual=actual,
        )
        return False

    if after:
        context.source_after = snapshot
    else:
        context.source_before = snapshot

        if snapshot.fingerprint != context.patch_apply_report.source_snapshot_after:
            context.add(
                "source_repository_changed",
                "static_source",
                "Source repository changed after Patch Apply V1.",
                expected=context.patch_apply_report.source_snapshot_after,
                actual=snapshot.fingerprint,
            )
            return False

    return True


def _run_git_gate(
    context: _StaticCheckContext,
    *,
    after: bool,
) -> bool:
    assert context.git_request is not None

    try:
        evidence = verify_developer_task_static_git(
            context.git_request,
            patch_apply_report=context.patch_apply_report,
        )
    except DeveloperTaskStaticGitError as exc:
        context.add(
            exc.code,
            "static_git_diff",
            str(exc),
            actual=exc.actual,
        )
        return False

    if after:
        context.git_after = evidence
    else:
        context.git_before = evidence
        context.completed_checks.append(DEVELOPER_CHECK_GIT_DIFF)

    return True


def _run_python_gate(context: _StaticCheckContext) -> bool:
    has_py_compile = any(
        check.type == DEVELOPER_CHECK_PY_COMPILE
        and check.scope == "changed_python_files"
        for check in context.manifest.checks
    )

    if not has_py_compile:
        if context.changed_python_files:
            context.add(
                "py_compile_check_missing",
                "static_python",
                "Changed Python files require the typed py_compile check.",
            )
            return False

        return True

    try:
        context.python_evidence = compile_changed_python_files(
            context.repository_root,
            changed_files=context.changed_files,
            result_index_paths=context.patch_apply_report.result_index_paths,
        )
    except DeveloperTaskStaticPythonError as exc:
        context.add(
            exc.code,
            "static_python",
            str(exc),
            actual=(
                f"path={exc.path};{exc.actual}"
                if exc.path
                else exc.actual
            )[:500],
        )
        return False

    context.completed_checks.append(DEVELOPER_CHECK_PY_COMPILE)
    return True


def run_developer_task_static_checks(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    patch_apply_report: DeveloperTaskPatchApplyReport,
    workspace_parent: Path,
) -> DeveloperTaskStaticCheckReport:
    """Run trusted static checks without importing or executing changed workspace code."""

    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(preflight_report, DeveloperTaskPreflightReport):
        raise TypeError("preflight_report must be DeveloperTaskPreflightReport")

    if not isinstance(workspace_report, DeveloperTaskWorkspaceReport):
        raise TypeError("workspace_report must be DeveloperTaskWorkspaceReport")

    if not isinstance(patch_apply_report, DeveloperTaskPatchApplyReport):
        raise TypeError("patch_apply_report must be DeveloperTaskPatchApplyReport")

    if not isinstance(workspace_parent, Path):
        raise TypeError("workspace_parent must be pathlib.Path")

    context = _StaticCheckContext(
        manifest,
        preflight_report,
        workspace_report,
        patch_apply_report,
        workspace_parent,
    )

    if not _validate_manifest(context):
        return context.report()

    if not _validate_evidence(context):
        return context.report()

    if not _validate_filesystem_and_markers(context):
        return context.report()

    if not _capture_source(context, after=False):
        _capture_source(context, after=True)
        return context.report()

    if not _run_git_gate(context, after=False):
        _capture_source(context, after=True)
        return context.report()

    _run_python_gate(context)
    _run_git_gate(context, after=True)
    _capture_source(context, after=True)

    if (
        context.git_before is not None
        and context.git_after is not None
        and context.git_before != context.git_after
    ):
        context.add(
            "workspace_changed_during_static_checks",
            "static_postconditions",
            "Workspace Git evidence changed during trusted static checks.",
        )

    if (
        context.source_before is not None
        and context.source_after is not None
        and context.source_before.fingerprint != context.source_after.fingerprint
    ):
        context.add(
            "source_repository_changed",
            "static_postconditions",
            "Source repository changed during trusted static checks.",
            expected=context.source_before.fingerprint,
            actual=context.source_after.fingerprint,
        )

    return context.report()
