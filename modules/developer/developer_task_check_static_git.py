from __future__ import annotations

"""Read-only Git evidence gate for an already-applied developer-task workspace."""

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_patch_apply import DeveloperTaskPatchApplyReport
from modules.developer.developer_task_patch_apply_git import (
    DeveloperTaskPatchApplyGitError,
    DeveloperTaskPatchApplyGitEvidence,
    inspect_applied_independent_workspace,
)
from modules.developer.developer_task_workspace_git import DeveloperTaskWorkspaceGitRequest


@dataclass(frozen=True)
class DeveloperTaskStaticGitEvidence:
    """Immutable proof that current workspace Git state still matches Patch Apply V1."""

    head_commit: str
    changed_files: tuple[str, ...]
    result_index_paths: tuple[str, ...]
    result_tree: str
    staged_diff_sha256: str
    workspace_config_sha256: str
    staged_only: bool
    index_matches_worktree: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "head_commit": self.head_commit,
            "changed_files": list(self.changed_files),
            "result_index_paths": list(self.result_index_paths),
            "result_tree": self.result_tree,
            "staged_diff_sha256": self.staged_diff_sha256,
            "workspace_config_sha256": self.workspace_config_sha256,
            "staged_only": self.staged_only,
            "index_matches_worktree": self.index_matches_worktree,
        }


class DeveloperTaskStaticGitError(RuntimeError):
    """Structured static Git evidence failure."""

    def __init__(self, code: str, message: str, actual: str = "") -> None:
        self.code = code
        self.actual = actual
        super().__init__(message)


def _evidence_matches_apply_report(
    evidence: DeveloperTaskPatchApplyGitEvidence,
    report: DeveloperTaskPatchApplyReport,
) -> bool:
    return (
        evidence.head_commit == report.head_commit
        and evidence.detached_head
        and evidence.shallow_repository
        and not evidence.remote_names
        and not evidence.ref_names
        and not evidence.alternate_object_directories
        and evidence.changed_files == report.changed_files
        and evidence.changes == report.changes
        and evidence.result_index_paths == report.result_index_paths
        and evidence.result_tree == report.result_tree
        and evidence.staged_diff_sha256 == report.staged_diff_sha256
        and evidence.workspace_config_sha256 == report.workspace_config_sha256
        and evidence.index_matches_worktree
        and evidence.staged_only
    )


def verify_developer_task_static_git(
    request: DeveloperTaskWorkspaceGitRequest,
    *,
    patch_apply_report: DeveloperTaskPatchApplyReport,
) -> DeveloperTaskStaticGitEvidence:
    """Re-read applied Git facts and require an exact match with immutable apply evidence."""

    if not isinstance(request, DeveloperTaskWorkspaceGitRequest):
        raise TypeError("request must be DeveloperTaskWorkspaceGitRequest")

    if not isinstance(patch_apply_report, DeveloperTaskPatchApplyReport):
        raise TypeError("patch_apply_report must be DeveloperTaskPatchApplyReport")

    if not patch_apply_report.ok:
        raise DeveloperTaskStaticGitError(
            "patch_apply_report_failed",
            "Patch Apply V1 report must be successful before static checks.",
            actual=",".join(patch_apply_report.issue_codes),
        )

    try:
        evidence = inspect_applied_independent_workspace(
            request,
            expected_changes=patch_apply_report.changes,
            expected_result_index_paths=patch_apply_report.result_index_paths,
        )
    except DeveloperTaskPatchApplyGitError as exc:
        raise DeveloperTaskStaticGitError(
            exc.code,
            str(exc),
            actual=exc.actual,
        ) from exc

    if not _evidence_matches_apply_report(evidence, patch_apply_report):
        raise DeveloperTaskStaticGitError(
            "static_git_evidence_mismatch",
            "Current workspace Git evidence differs from Patch Apply V1 evidence.",
            actual=(
                f"head={evidence.head_commit};"
                f"tree={evidence.result_tree};"
                f"diff={evidence.staged_diff_sha256};"
                f"config={evidence.workspace_config_sha256}"
            ),
        )

    return DeveloperTaskStaticGitEvidence(
        head_commit=evidence.head_commit,
        changed_files=evidence.changed_files,
        result_index_paths=evidence.result_index_paths,
        result_tree=evidence.result_tree,
        staged_diff_sha256=evidence.staged_diff_sha256,
        workspace_config_sha256=evidence.workspace_config_sha256,
        staged_only=evidence.staged_only,
        index_matches_worktree=evidence.index_matches_worktree,
    )
