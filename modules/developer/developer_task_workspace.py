from __future__ import annotations

"""Safe orchestration for independent developer-task repository workspaces."""

import hashlib
import json
import os
import secrets
import shutil
import stat
import subprocess
import time

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_preflight import (
    DeveloperTaskPreflightIssue,
    _build_git_environment,
    run_developer_task_repository_preflight,
)
from modules.developer.developer_task_preflight_composition import (
    DeveloperTaskPreflightReport,
)
from modules.developer.developer_task_workspace_git import (
    GIT_TIMEOUT_SECONDS,
    DeveloperTaskWorkspaceGitError,
    DeveloperTaskWorkspaceGitEvidence,
    DeveloperTaskWorkspaceGitRequest,
    build_probe_environment,
    create_independent_git_workspace,
)


_WORKSPACE_PREFIX = "skynetvs-task-"
_WORKSPACE_MARKER_NAME = "workspace.json"
_WORKSPACE_MARKER_SCHEMA_VERSION = 1
_CLEANUP_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2, 0.4)


@dataclass(frozen=True)
class DeveloperTaskWorkspaceReport:
    """Immutable evidence for one independent developer-task repository."""

    manifest_fingerprint: str
    workspace_id: str
    source_repository_root: str
    task_root: str
    workspace_parent: str
    workspace_root: str
    repository_root: str
    git_dir: str
    control_root: str
    marker_path: str
    marker_sha256: str
    base_commit: str
    head_commit: str
    detached_head: bool
    shallow_repository: bool
    clean_worktree: bool
    remote_names: tuple[str, ...]
    ref_names: tuple[str, ...]
    alternate_object_directories: tuple[str, ...]
    hooks_path: str
    source_repository_unchanged: bool
    cleanup_token: bytes = field(repr=False)
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            bool(self.workspace_id)
            and bool(self.source_repository_root)
            and bool(self.task_root)
            and bool(self.workspace_parent)
            and bool(self.workspace_root)
            and bool(self.repository_root)
            and bool(self.git_dir)
            and bool(self.control_root)
            and bool(self.marker_path)
            and bool(self.marker_sha256)
            and bool(self.base_commit)
            and self.head_commit == self.base_commit
            and self.detached_head
            and self.shallow_repository
            and self.clean_worktree
            and not self.remote_names
            and not self.ref_names
            and not self.alternate_object_directories
            and bool(self.hooks_path)
            and self.source_repository_unchanged
            and len(self.cleanup_token) == 32
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
            "git_dir": self.git_dir,
            "control_root": self.control_root,
            "marker_path": self.marker_path,
            "marker_sha256": self.marker_sha256,
            "base_commit": self.base_commit,
            "head_commit": self.head_commit,
            "detached_head": self.detached_head,
            "shallow_repository": self.shallow_repository,
            "clean_worktree": self.clean_worktree,
            "remote_names": list(self.remote_names),
            "ref_names": list(self.ref_names),
            "alternate_object_directories": list(self.alternate_object_directories),
            "hooks_path": self.hooks_path,
            "source_repository_unchanged": self.source_repository_unchanged,
            "cleanup_capability_present": len(self.cleanup_token) == 32,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


class _WorkspaceContext:
    def __init__(
        self,
        manifest: DeveloperTaskManifest,
        preflight_report: DeveloperTaskPreflightReport,
        workspace_parent: Path,
    ) -> None:
        self.manifest = manifest
        self.preflight_report = preflight_report
        self.manifest_fingerprint = ""
        self.source_repository_root = ""
        self.task_root = ""
        self.workspace_parent = _absolute_path(workspace_parent)
        self.workspace_id = ""
        self.workspace_root: Path | None = None
        self.repository_root: Path | None = None
        self.control_root: Path | None = None
        self.home_root: Path | None = None
        self.xdg_root: Path | None = None
        self.hooks_path: Path | None = None
        self.template_root: Path | None = None
        self.global_config_path: Path | None = None
        self.marker_path: Path | None = None
        self.marker_sha256 = ""
        self.cleanup_token = b""
        self.base_commit = ""
        self.git_evidence: DeveloperTaskWorkspaceGitEvidence | None = None
        self.issues: list[DeveloperTaskPreflightIssue] = []
        self.container_created = False

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

    def report(self) -> DeveloperTaskWorkspaceReport:
        evidence = self.git_evidence
        return DeveloperTaskWorkspaceReport(
            manifest_fingerprint=self.manifest_fingerprint,
            workspace_id=self.workspace_id,
            source_repository_root=self.source_repository_root,
            task_root=self.task_root,
            workspace_parent=str(self.workspace_parent),
            workspace_root=str(self.workspace_root) if self.workspace_root is not None else "",
            repository_root=str(self.repository_root) if self.repository_root is not None else "",
            git_dir=evidence.git_dir if evidence is not None else "",
            control_root=str(self.control_root) if self.control_root is not None else "",
            marker_path=str(self.marker_path) if self.marker_path is not None else "",
            marker_sha256=self.marker_sha256,
            base_commit=self.base_commit,
            head_commit=evidence.head_commit if evidence is not None else "",
            detached_head=evidence.detached_head if evidence is not None else False,
            shallow_repository=(
                evidence.shallow_repository if evidence is not None else False
            ),
            clean_worktree=evidence.clean_worktree if evidence is not None else False,
            remote_names=evidence.remote_names if evidence is not None else (),
            ref_names=evidence.ref_names if evidence is not None else (),
            alternate_object_directories=(
                evidence.alternate_object_directories if evidence is not None else ()
            ),
            hooks_path=evidence.hooks_path if evidence is not None else "",
            source_repository_unchanged=(
                evidence.source_repository_unchanged if evidence is not None else False
            ),
            cleanup_token=self.cleanup_token,
            issues=tuple(self.issues),
        )


def _absolute_path(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path))).casefold()


def _paths_overlap(first: Path, second: Path) -> bool:
    first_key = _path_key(first)
    second_key = _path_key(second)
    separator = os.sep.casefold()
    return (
        first_key == second_key
        or first_key.startswith(second_key + separator)
        or second_key.startswith(first_key + separator)
    )


def _is_reparse_or_symlink(value: os.stat_result) -> bool:
    file_attributes = int(getattr(value, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(value.st_mode) or bool(file_attributes & reparse_flag)


def _directory_metadata(path: Path) -> os.stat_result:
    return os.lstat(path)


def _directory_is_safe(path: Path) -> bool:
    metadata = _directory_metadata(path)
    return stat.S_ISDIR(metadata.st_mode) and not _is_reparse_or_symlink(metadata)


def _path_chain_has_reparse(path: Path) -> bool:
    absolute = _absolute_path(path)
    parts = absolute.parts

    if not parts:
        return True

    current = Path(parts[0])

    for part in parts[1:]:
        current /= part

        if _is_reparse_or_symlink(os.lstat(current)):
            return True

    return False


def _parent_is_inside_git_repository(path: Path) -> bool:
    command = [
        "git",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "maintenance.auto=false",
        "-C",
        str(path),
        "rev-parse",
        "--is-inside-work-tree",
        "--is-inside-git-dir",
        "--is-bare-repository",
    ]

    try:
        completed = subprocess.run(
            command,
            env=build_probe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_command_timeout",
            "Git parent-directory probe timed out.",
        ) from exc
    except FileNotFoundError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_unavailable",
            "Git executable is unavailable.",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_command_failed",
            "Git parent-directory probe could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if completed.returncode != 0:
        return False

    try:
        values = tuple(
            item.strip().lower()
            for item in completed.stdout.decode("ascii", errors="strict").splitlines()
            if item.strip()
        )
    except UnicodeDecodeError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_output_invalid",
            "Git parent-directory probe returned invalid output.",
        ) from exc

    if len(values) != 3 or any(item not in {"true", "false"} for item in values):
        raise DeveloperTaskWorkspaceGitError(
            "git_output_invalid",
            "Git parent-directory probe returned inconsistent output.",
            actual=repr(values),
        )

    return any(item == "true" for item in values)


def _validate_preflight(context: _WorkspaceContext) -> bool:
    try:
        context.manifest_fingerprint = developer_task_manifest_fingerprint(context.manifest)
    except (AttributeError, TypeError, ValueError) as exc:
        context.add(
            "manifest_invalid",
            "workspace_preflight",
            "Developer task manifest could not be fingerprinted.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    report = context.preflight_report

    if not report.ok:
        context.add(
            "preflight_report_failed",
            "workspace_preflight",
            "Complete developer task preflight must pass before workspace creation.",
            actual=", ".join(report.issue_codes),
        )
        return False

    integrity = report.patch_integrity_report

    if (
        report.manifest_fingerprint != context.manifest_fingerprint
        or not report.repository_root
        or not report.base_commit
        or integrity is None
        or not integrity.ok
        or not integrity.task_root
        or report.patch is None
    ):
        context.add(
            "preflight_report_invalid",
            "workspace_preflight",
            "Complete developer task preflight evidence is inconsistent.",
        )
        return False

    context.source_repository_root = report.repository_root
    context.task_root = integrity.task_root
    context.base_commit = report.base_commit
    fresh = run_developer_task_repository_preflight(
        context.manifest,
        project_root=Path(context.source_repository_root),
    )

    if (
        not fresh.ok
        or fresh.manifest_fingerprint != context.manifest_fingerprint
        or fresh.repository_root != context.source_repository_root
        or fresh.head_commit != context.base_commit
        or fresh.resolved_base_commit != context.base_commit
        or fresh.dirty_categories
    ):
        context.add(
            "source_repository_stale",
            "workspace_preflight",
            "Source repository no longer matches successful preflight evidence.",
            expected=context.base_commit,
            actual=f"head={fresh.head_commit}; issues={','.join(fresh.issue_codes)}",
        )
        return False

    return True


def _validate_workspace_parent(context: _WorkspaceContext) -> bool:
    parent = context.workspace_parent

    try:
        metadata = _directory_metadata(parent)
    except FileNotFoundError:
        context.add(
            "workspace_parent_missing",
            "workspace_parent",
            "Workspace parent directory does not exist.",
            actual=str(parent),
        )
        return False
    except OSError as exc:
        context.add(
            "workspace_parent_metadata_failed",
            "workspace_parent",
            "Workspace parent metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    if not stat.S_ISDIR(metadata.st_mode):
        context.add(
            "workspace_parent_not_directory",
            "workspace_parent",
            "Workspace parent must be a directory.",
            actual=str(parent),
        )
        return False

    if _is_reparse_or_symlink(metadata):
        context.add(
            "workspace_parent_reparse_point",
            "workspace_parent",
            "Workspace parent must not be a symlink, junction, or reparse point.",
            actual=str(parent),
        )
        return False

    try:
        if _path_chain_has_reparse(parent):
            context.add(
                "workspace_parent_indirect",
                "workspace_parent",
                "Workspace parent path must not traverse a reparse point.",
                actual=str(parent),
            )
            return False

        resolved = parent.resolve(strict=True)
    except OSError as exc:
        context.add(
            "workspace_parent_metadata_failed",
            "workspace_parent",
            "Workspace parent path could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    if _path_key(resolved) != _path_key(parent):
        context.add(
            "workspace_parent_indirect",
            "workspace_parent",
            "Workspace parent path must resolve to itself.",
            expected=str(parent),
            actual=str(resolved),
        )
        return False

    if _paths_overlap(parent, Path(context.source_repository_root)):
        context.add(
            "workspace_parent_overlaps_repository",
            "workspace_parent",
            "Workspace parent must not overlap the source repository.",
            actual=str(parent),
        )
        return False

    if _paths_overlap(parent, Path(context.task_root)):
        context.add(
            "workspace_parent_overlaps_task_root",
            "workspace_parent",
            "Workspace parent must not overlap the developer task root.",
            actual=str(parent),
        )
        return False

    try:
        if _parent_is_inside_git_repository(parent):
            context.add(
                "workspace_parent_inside_git_repository",
                "workspace_parent",
                "Workspace parent must not be inside a Git worktree or Git administration directory.",
                actual=str(parent),
            )
            return False
    except DeveloperTaskWorkspaceGitError as exc:
        context.add(exc.code, "workspace_parent", str(exc), actual=exc.actual)
        return False

    return True


def _workspace_name(context: _WorkspaceContext) -> str:
    task_part = context.manifest.task_id[:24]
    return (
        f"{_WORKSPACE_PREFIX}{task_part}-"
        f"{context.manifest_fingerprint[:12]}-{secrets.token_hex(12)}"
    )


def _create_workspace_container(context: _WorkspaceContext) -> bool:
    context.workspace_id = _workspace_name(context)
    context.workspace_root = context.workspace_parent / context.workspace_id
    context.repository_root = context.workspace_root / "repository"
    context.control_root = context.workspace_root / "control"
    context.home_root = context.control_root / "home"
    context.xdg_root = context.control_root / "xdg"
    context.hooks_path = context.control_root / "hooks"
    context.template_root = context.control_root / "template"
    context.global_config_path = context.control_root / "gitconfig"
    context.marker_path = context.workspace_root / _WORKSPACE_MARKER_NAME

    try:
        os.mkdir(context.workspace_root, 0o700)
        context.container_created = True
        os.mkdir(context.control_root, 0o700)

        for path in (
            context.home_root,
            context.xdg_root,
            context.hooks_path,
            context.template_root,
        ):
            os.mkdir(path, 0o700)

        descriptor = os.open(
            context.global_config_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        os.close(descriptor)
    except FileExistsError:
        context.add(
            "workspace_path_exists",
            "workspace_create",
            "Generated workspace path already exists.",
            actual=str(context.workspace_root),
        )
        return False
    except OSError as exc:
        context.add(
            "workspace_container_create_failed",
            "workspace_create",
            "Workspace container could not be created.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    try:
        if any(
            not _directory_is_safe(path)
            for path in (
                context.workspace_root,
                context.control_root,
                context.home_root,
                context.xdg_root,
                context.hooks_path,
                context.template_root,
            )
        ):
            raise OSError("Created workspace control directory is unsafe")
    except OSError as exc:
        context.add(
            "workspace_container_invalid",
            "workspace_create",
            "Created workspace container failed safety validation.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    context.cleanup_token = secrets.token_bytes(32)
    return True


def _git_request(context: _WorkspaceContext) -> DeveloperTaskWorkspaceGitRequest:
    assert context.repository_root is not None
    assert context.home_root is not None
    assert context.xdg_root is not None
    assert context.hooks_path is not None
    assert context.template_root is not None
    assert context.global_config_path is not None
    return DeveloperTaskWorkspaceGitRequest(
        source_repository_root=context.source_repository_root,
        repository_root=str(context.repository_root),
        home_root=str(context.home_root),
        xdg_root=str(context.xdg_root),
        hooks_path=str(context.hooks_path),
        template_root=str(context.template_root),
        global_config_path=str(context.global_config_path),
        base_commit=context.base_commit,
    )


def _write_marker(context: _WorkspaceContext) -> bool:
    assert context.workspace_root is not None
    assert context.repository_root is not None
    assert context.control_root is not None
    assert context.marker_path is not None
    assert context.git_evidence is not None
    payload = {
        "schema_version": _WORKSPACE_MARKER_SCHEMA_VERSION,
        "workspace_id": context.workspace_id,
        "manifest_fingerprint": context.manifest_fingerprint,
        "source_repository_root": context.source_repository_root,
        "task_root": context.task_root,
        "workspace_root": str(context.workspace_root),
        "repository_root": str(context.repository_root),
        "git_dir": context.git_evidence.git_dir,
        "control_root": str(context.control_root),
        "base_commit": context.base_commit,
        "head_commit": context.git_evidence.head_commit,
        "cleanup_token_sha256": hashlib.sha256(context.cleanup_token).hexdigest(),
    }
    data = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    try:
        descriptor = os.open(
            context.marker_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )

        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        context.add(
            "workspace_marker_write_failed",
            "workspace_marker",
            "Workspace marker could not be written.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    context.marker_sha256 = hashlib.sha256(data).hexdigest()
    return True


def _rmtree_windows_readonly_handler(
    function: Any,
    path: str,
    exc_info: tuple[type[BaseException], BaseException, Any],
) -> None:
    error = exc_info[1]

    if not isinstance(error, PermissionError):
        raise error

    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        function(path)
    except FileNotFoundError:
        return


def _remove_workspace_container(context: _WorkspaceContext) -> bool:
    if (
        not context.container_created
        or context.workspace_root is None
        or not context.workspace_id
    ):
        return True

    target = context.workspace_root

    if (
        target.parent != context.workspace_parent
        or not target.name.startswith(_WORKSPACE_PREFIX)
        or _paths_overlap(target, Path(context.source_repository_root))
        or _paths_overlap(target, Path(context.task_root))
    ):
        return False

    delays = (0.0, *_CLEANUP_RETRY_DELAYS_SECONDS)

    for index, delay in enumerate(delays):
        if delay:
            time.sleep(delay)

        try:
            shutil.rmtree(target, onerror=_rmtree_windows_readonly_handler)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if index == len(delays) - 1:
                return False

    return False


def _cleanup_failed_workspace(context: _WorkspaceContext) -> None:
    if not _remove_workspace_container(context):
        context.add(
            "workspace_cleanup_failed",
            "workspace_cleanup",
            "Failed workspace could not be removed safely.",
            actual=str(context.workspace_root or ""),
        )


def create_developer_task_workspace(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceReport:
    """Create one independent, detached, remote-free repository workspace."""

    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(preflight_report, DeveloperTaskPreflightReport):
        raise TypeError("preflight_report must be DeveloperTaskPreflightReport")

    if not isinstance(workspace_parent, Path):
        raise TypeError("workspace_parent must be pathlib.Path")

    context = _WorkspaceContext(manifest, preflight_report, workspace_parent)

    if not _validate_preflight(context):
        return context.report()

    if not _validate_workspace_parent(context):
        return context.report()

    if not _create_workspace_container(context):
        _cleanup_failed_workspace(context)
        return context.report()

    try:
        context.git_evidence = create_independent_git_workspace(_git_request(context))
    except DeveloperTaskWorkspaceGitError as exc:
        context.add(exc.code, "workspace_git", str(exc), actual=exc.actual)
        _cleanup_failed_workspace(context)
        return context.report()
    except (OSError, ValueError) as exc:
        context.add(
            "workspace_repository_invalid",
            "workspace_git",
            "Independent workspace repository validation failed.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        _cleanup_failed_workspace(context)
        return context.report()

    if not _write_marker(context):
        _cleanup_failed_workspace(context)
        return context.report()

    return context.report()
