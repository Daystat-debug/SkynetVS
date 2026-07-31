from __future__ import annotations

"""Pure patch-scope policy for isolated developer-task Git facts."""

import ntpath
import re

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_patch_index import (
    DeveloperTaskPatchIndexChange,
    DeveloperTaskPatchIndexPreflightReport,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_validator import validate_developer_task_manifest


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_RESERVED_RE = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$",
    re.IGNORECASE,
)
_MAX_PATH_LENGTH = 240
_MAX_SEGMENT_LENGTH = 120
_KNOWN_CHANGE_STATUSES = frozenset({"A", "D", "M", "T"})
_KNOWN_FILE_MODES = frozenset({"000000", "100644", "100755", "120000", "160000"})
_COMMIT_ID_RE = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True)
class DeveloperTaskPatchScopeCollision:
    """One Windows case-insensitive collision group."""

    paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"paths": list(self.paths)}


@dataclass(frozen=True)
class DeveloperTaskPatchScopePreflightReport:
    """Immutable evidence produced by the V1C2 patch-scope policy gate."""

    manifest_fingerprint: str
    repository_root: str
    base_commit: str
    allowed_files: tuple[str, ...]
    changed_files: tuple[str, ...]
    unauthorized_files: tuple[str, ...]
    case_mismatch_files: tuple[str, ...]
    symlink_files: tuple[str, ...]
    gitlink_files: tuple[str, ...]
    type_change_files: tuple[str, ...]
    changed_path_collisions: tuple[DeveloperTaskPatchScopeCollision, ...]
    result_index_collisions: tuple[DeveloperTaskPatchScopeCollision, ...]
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return bool(self.changed_files) and not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest_fingerprint": self.manifest_fingerprint,
            "repository_root": self.repository_root,
            "base_commit": self.base_commit,
            "allowed_files": list(self.allowed_files),
            "changed_files": list(self.changed_files),
            "unauthorized_files": list(self.unauthorized_files),
            "case_mismatch_files": list(self.case_mismatch_files),
            "symlink_files": list(self.symlink_files),
            "gitlink_files": list(self.gitlink_files),
            "type_change_files": list(self.type_change_files),
            "changed_path_collisions": [item.to_dict() for item in self.changed_path_collisions],
            "result_index_collisions": [item.to_dict() for item in self.result_index_collisions],
            "issues": [item.to_dict() for item in self.issues],
        }


class _PatchScopeContext:
    def __init__(
        self,
        manifest: DeveloperTaskManifest,
        patch_index_report: DeveloperTaskPatchIndexPreflightReport,
    ) -> None:
        self.manifest = manifest

        try:
            self.manifest_fingerprint = developer_task_manifest_fingerprint(manifest)
        except (AttributeError, TypeError, ValueError):
            self.manifest_fingerprint = ""
        self.patch_index_report = patch_index_report
        self.repository_root = ""
        self.base_commit = ""
        self.allowed_files: tuple[str, ...] = ()
        self.changed_files: tuple[str, ...] = ()
        self.unauthorized_files: tuple[str, ...] = ()
        self.case_mismatch_files: tuple[str, ...] = ()
        self.symlink_files: tuple[str, ...] = ()
        self.gitlink_files: tuple[str, ...] = ()
        self.type_change_files: tuple[str, ...] = ()
        self.changed_path_collisions: tuple[DeveloperTaskPatchScopeCollision, ...] = ()
        self.result_index_collisions: tuple[DeveloperTaskPatchScopeCollision, ...] = ()
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

    def report(self) -> DeveloperTaskPatchScopePreflightReport:
        return DeveloperTaskPatchScopePreflightReport(
            manifest_fingerprint=self.manifest_fingerprint,
            repository_root=self.repository_root,
            base_commit=self.base_commit,
            allowed_files=self.allowed_files,
            changed_files=self.changed_files,
            unauthorized_files=self.unauthorized_files,
            case_mismatch_files=self.case_mismatch_files,
            symlink_files=self.symlink_files,
            gitlink_files=self.gitlink_files,
            type_change_files=self.type_change_files,
            changed_path_collisions=self.changed_path_collisions,
            result_index_collisions=self.result_index_collisions,
            issues=tuple(self.issues),
        )


def _path_key(value: str) -> str:
    return ntpath.normcase(value.replace("/", "\\"))


def _path_sort_key(value: str) -> tuple[str, str]:
    return _path_key(value), value


def _is_safe_repository_path(value: str) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\\" in value
        or value.startswith("/")
        or _WINDOWS_DRIVE_RE.match(value)
        or len(value) > _MAX_PATH_LENGTH
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        return False

    path = PurePosixPath(value)
    parts = value.split("/")

    if path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        return False

    for part in parts:
        if (
            len(part) > _MAX_SEGMENT_LENGTH
            or part.endswith((" ", "."))
            or any(char in '<>:"|?*' for char in part)
            or _WINDOWS_RESERVED_RE.fullmatch(part)
        ):
            return False

    return True


def _format_paths(paths: tuple[str, ...]) -> str:
    value = ",".join(paths)
    return value if len(value) <= 500 else value[:497] + "..."


def _collision_groups(paths: tuple[str, ...]) -> tuple[DeveloperTaskPatchScopeCollision, ...]:
    groups: dict[str, list[str]] = {}

    for path in paths:
        groups.setdefault(_path_key(path), []).append(path)

    collisions = [
        DeveloperTaskPatchScopeCollision(paths=tuple(sorted(set(group))))
        for group in groups.values()
        if len(set(group)) > 1
    ]
    return tuple(sorted(collisions, key=lambda item: _path_sort_key(item.paths[0])))


def _change_is_consistent(change: DeveloperTaskPatchIndexChange) -> bool:
    if (
        not isinstance(change.path, str)
        or not _is_safe_repository_path(change.path)
        or change.status not in _KNOWN_CHANGE_STATUSES
        or change.old_mode not in _KNOWN_FILE_MODES
        or change.new_mode not in _KNOWN_FILE_MODES
    ):
        return False

    if change.status == "A":
        return change.old_mode == "000000" and change.new_mode != "000000"

    if change.status == "D":
        return change.old_mode != "000000" and change.new_mode == "000000"

    return change.old_mode != "000000" and change.new_mode != "000000"


def _validate_manifest(context: _PatchScopeContext) -> bool:
    try:
        payload = context.manifest.to_dict()
    except (AttributeError, TypeError, ValueError) as exc:
        context.add(
            "manifest_invalid",
            "manifest",
            "Developer task manifest could not be serialized for contract validation.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    validation = validate_developer_task_manifest(payload)

    if validation.manifest is None:
        context.add(
            "manifest_invalid",
            "manifest",
            "Developer task manifest does not satisfy the validated contract.",
            actual=",".join(validation.issue_codes) or "invalid",
        )
        return False

    if (
        validation.manifest != context.manifest
        or developer_task_manifest_fingerprint(validation.manifest) != context.manifest_fingerprint
    ):
        context.add(
            "manifest_invalid",
            "manifest",
            "Developer task manifest changed during contract validation.",
            actual="canonical manifest mismatch",
        )
        return False

    context.allowed_files = context.manifest.allowed_files
    return True


def _validate_patch_index_report(context: _PatchScopeContext) -> bool:
    report = context.patch_index_report

    if not report.ok:
        context.add(
            "patch_index_preflight_failed",
            "prerequisites",
            "Patch index preflight must pass before scope policy is evaluated.",
            expected="ok",
            actual=",".join(report.issue_codes) or "failed",
        )
        return False

    if report.manifest_fingerprint != context.manifest_fingerprint:
        context.add(
            "manifest_fingerprint_mismatch",
            "prerequisites",
            "Patch index report was created for a different manifest.",
            expected=context.manifest_fingerprint,
            actual=report.manifest_fingerprint,
        )
        return False

    changes = report.changes
    changed_files = report.changed_files
    result_index_paths = report.result_index_paths

    if (
        not isinstance(report.repository_root, str)
        or not report.repository_root
        or report.repository_root != report.repository_root.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in report.repository_root)
        or not isinstance(report.base_commit, str)
        or not _COMMIT_ID_RE.fullmatch(report.base_commit)
        or report.issues
        or not isinstance(changes, tuple)
        or not changes
        or not isinstance(changed_files, tuple)
        or not isinstance(result_index_paths, tuple)
        or any(not isinstance(item, DeveloperTaskPatchIndexChange) for item in changes)
        or any(not isinstance(path, str) for path in changed_files)
        or any(not isinstance(path, str) for path in result_index_paths)
        or changed_files != tuple(item.path for item in changes)
        or changed_files != tuple(sorted(changed_files, key=_path_sort_key))
        or result_index_paths != tuple(sorted(result_index_paths, key=_path_sort_key))
        or len(set(changed_files)) != len(changed_files)
        or len(set(result_index_paths)) != len(result_index_paths)
        or any(not _change_is_consistent(item) for item in changes)
        or any(not _is_safe_repository_path(path) for path in result_index_paths)
    ):
        context.add(
            "patch_index_preflight_invalid",
            "prerequisites",
            "Patch index preflight report is internally inconsistent.",
            actual="incomplete or inconsistent patch index proof",
        )
        return False

    result_paths = set(result_index_paths)

    for change in changes:
        if change.status == "D":
            if change.path in result_paths:
                context.add(
                    "patch_index_preflight_invalid",
                    "prerequisites",
                    "Deleted path is still present in the resulting index.",
                    actual=change.path,
                )
                return False
        elif change.path not in result_paths:
            context.add(
                "patch_index_preflight_invalid",
                "prerequisites",
                "Non-deleted path is absent from the resulting index.",
                actual=change.path,
            )
            return False

    context.repository_root = report.repository_root
    context.base_commit = report.base_commit
    context.changed_files = changed_files
    return True


def _evaluate_scope_policy(context: _PatchScopeContext) -> None:
    report = context.patch_index_report
    allowed_by_key = {_path_key(path): path for path in context.allowed_files}
    unauthorized: list[str] = []
    case_mismatch: list[str] = []

    for path in context.changed_files:
        allowed_path = allowed_by_key.get(_path_key(path))

        if allowed_path is None:
            unauthorized.append(path)
        elif allowed_path != path:
            case_mismatch.append(path)

    context.unauthorized_files = tuple(sorted(unauthorized, key=_path_sort_key))
    context.case_mismatch_files = tuple(sorted(case_mismatch, key=_path_sort_key))
    context.changed_path_collisions = _collision_groups(context.changed_files)
    context.result_index_collisions = _collision_groups(report.result_index_paths)
    context.symlink_files = tuple(
        sorted(
            {
                item.path
                for item in report.changes
                if "120000" in {item.old_mode, item.new_mode}
            },
            key=_path_sort_key,
        )
    )
    context.gitlink_files = tuple(
        sorted(
            {
                item.path
                for item in report.changes
                if "160000" in {item.old_mode, item.new_mode}
            },
            key=_path_sort_key,
        )
    )
    context.type_change_files = tuple(
        sorted(
            (item.path for item in report.changes if item.status == "T"),
            key=_path_sort_key,
        )
    )

    if context.unauthorized_files:
        context.add(
            "patch_scope_violation",
            "allowed_files",
            "Patch changes paths outside manifest.allowed_files.",
            expected=_format_paths(tuple(sorted(context.allowed_files, key=_path_sort_key))),
            actual=_format_paths(context.unauthorized_files),
        )

    if context.case_mismatch_files:
        context.add(
            "patch_scope_case_mismatch",
            "allowed_files",
            "Patch path casing does not exactly match manifest.allowed_files.",
            actual=_format_paths(context.case_mismatch_files),
        )

    if context.changed_path_collisions:
        context.add(
            "patch_changed_path_collision",
            "changed_files",
            "Patch contains paths that collide on Windows.",
            actual=";".join(",".join(item.paths) for item in context.changed_path_collisions),
        )

    if context.result_index_collisions:
        context.add(
            "patch_result_index_collision",
            "result_index_paths",
            "Resulting Git index contains paths that collide on Windows.",
            actual=";".join(",".join(item.paths) for item in context.result_index_collisions),
        )

    if context.symlink_files:
        context.add(
            "patch_symlink_unsupported",
            "file_modes",
            "Developer-task patches must not add, modify, or delete symlink entries.",
            actual=_format_paths(context.symlink_files),
        )

    if context.gitlink_files:
        context.add(
            "patch_gitlink_unsupported",
            "file_modes",
            "Developer-task patches must not add, modify, or delete gitlink/submodule entries.",
            actual=_format_paths(context.gitlink_files),
        )

    if context.type_change_files:
        context.add(
            "patch_type_change_unsupported",
            "change_status",
            "Developer-task patches must not perform Git object type changes.",
            actual=_format_paths(context.type_change_files),
        )


def run_developer_task_patch_scope_preflight(
    manifest: DeveloperTaskManifest,
    *,
    patch_index_report: DeveloperTaskPatchIndexPreflightReport,
) -> DeveloperTaskPatchScopePreflightReport:
    """Apply pure allowlist and Windows-safe scope policy to V1C1 facts."""
    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(patch_index_report, DeveloperTaskPatchIndexPreflightReport):
        raise TypeError("patch_index_report must be DeveloperTaskPatchIndexPreflightReport")

    context = _PatchScopeContext(manifest, patch_index_report)

    if not _validate_manifest(context):
        return context.report()

    if not _validate_patch_index_report(context):
        return context.report()

    _evaluate_scope_policy(context)
    return context.report()
