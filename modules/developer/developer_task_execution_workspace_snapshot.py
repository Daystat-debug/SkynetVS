from __future__ import annotations

"""V1C1A host-only exact-byte snapshot of a verified patched workspace result tree."""

import hashlib
import hmac
import json
import ntpath
import os
import re
import secrets
import stat
import subprocess
import threading
import time
import unicodedata
import weakref

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modules.developer.developer_task_check_static import DeveloperTaskStaticCheckReport
from modules.developer.developer_task_check_static_git import (
    DeveloperTaskStaticGitError,
    DeveloperTaskStaticGitEvidence,
    verify_developer_task_static_git,
)
from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_execution_workspace_snapshot_policy import (
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_ALLOWED_FILE_MODES,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_CLOCK_ID,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_FORMAT,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_FILE_COUNT,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_MANIFEST_BYTES,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_DEPTH,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_LENGTH,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SEGMENT_LENGTH,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_TOTAL_BYTES,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_PATH_UNICODE_NORMALIZATION,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SECRET_BYTES,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SOURCE_AUTHORITY,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TREE_MANIFEST_ALGORITHM,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TTL_SECONDS,
    validate_developer_task_execution_workspace_snapshot_policy,
)
from modules.developer.developer_task_patch_apply import DeveloperTaskPatchApplyReport
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
    GIT_TIMEOUT_SECONDS,
    DeveloperTaskWorkspaceGitRequest,
    build_workspace_git_environment,
    workspace_git_command_prefix,
)
from modules.developer.developer_task_workspace_source import (
    DeveloperTaskSourceRepositorySnapshot,
    snapshot_developer_task_source_repository,
)


SNAPSHOT_STATE_ISSUED = "issued"
SNAPSHOT_STATE_CLAIMED_FOR_PLAN = "claimed_for_plan"
SNAPSHOT_STATE_EXPIRED = "expired"
SNAPSHOT_STATE_INVALIDATED = "invalidated"

_CONSTRUCTOR_KEY = object()
_MATERIAL_CONSTRUCTOR_KEY = object()
_ISSUER_ID = object()
_ISSUER_SECRET = secrets.token_bytes(32)
_REGISTRY_LOCK = threading.RLock()
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_RESERVED_RE = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$",
    re.IGNORECASE,
)
_TREE_ENTRY_RE = re.compile(
    rb"^([0-7]{6}) ([a-z]+) ([0-9a-f]{40,64}) +([0-9]+|-)\t(.*)$",
    re.DOTALL,
)
_OBJECT_ID_RE = re.compile(r"^[0-9a-f]{40,64}$")


class DeveloperTaskExecutionWorkspaceSnapshotError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        self.code = code
        self.message = message
        self.actual = actual
        super().__init__(message)


@dataclass(frozen=True)
class DeveloperTaskExecutionWorkspaceSnapshotEntry:
    path: str
    mode: str
    object_id: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "mode": self.mode,
            "object_id": self.object_id,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionWorkspaceSnapshotReport:
    policy_id: str
    policy_fingerprint: str
    snapshot_format: str
    source_authority: str
    manifest_fingerprint: str
    workspace_id: str
    base_commit: str
    patch_sha256: str
    result_tree: str
    staged_diff_sha256: str
    workspace_config_sha256: str
    changed_files: tuple[str, ...]
    deleted_files: tuple[str, ...]
    result_index_paths: tuple[str, ...]
    file_count: int
    total_bytes: int
    manifest_bytes: int
    files: tuple[DeveloperTaskExecutionWorkspaceSnapshotEntry, ...]
    tree_manifest_sha256: str
    snapshot_fingerprint: str
    source_repository_unchanged: bool
    workspace_unchanged: bool
    repository_mutated: bool = False
    network_attempted: bool = False
    artifact_download_attempted: bool = False
    dependency_install_attempted: bool = False
    sandbox_launched: bool = False
    runtime_lease_issued: bool = False
    runtime_lease_claimed: bool = False
    candidate_interpreter_executed: bool = False
    changed_code_executed: bool = False
    reusable_lease_issued: bool = False
    execution_authorized: bool = False

    @property
    def ok(self) -> bool:
        return (
            self.policy_id == DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID
            and self.policy_fingerprint == DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT
            and self.snapshot_format == DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_FORMAT
            and self.source_authority == DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SOURCE_AUTHORITY
            and len(self.manifest_fingerprint) == 64
            and bool(self.workspace_id)
            and bool(self.base_commit)
            and len(self.patch_sha256) == 64
            and bool(_OBJECT_ID_RE.fullmatch(self.result_tree))
            and len(self.staged_diff_sha256) == 64
            and len(self.workspace_config_sha256) == 64
            and bool(self.changed_files)
            and 0 < self.file_count <= DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_FILE_COUNT
            and self.file_count == len(self.files)
            and 0 <= self.total_bytes <= DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_TOTAL_BYTES
            and 0 < self.manifest_bytes <= DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_MANIFEST_BYTES
            and len(self.tree_manifest_sha256) == 64
            and len(self.snapshot_fingerprint) == 64
            and self.source_repository_unchanged
            and self.workspace_unchanged
            and not any((
                self.repository_mutated,
                self.network_attempted,
                self.artifact_download_attempted,
                self.dependency_install_attempted,
                self.sandbox_launched,
                self.runtime_lease_issued,
                self.runtime_lease_claimed,
                self.candidate_interpreter_executed,
                self.changed_code_executed,
                self.reusable_lease_issued,
                self.execution_authorized,
            ))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "snapshot_format": self.snapshot_format,
            "source_authority": self.source_authority,
            "manifest_fingerprint": self.manifest_fingerprint,
            "workspace_id": self.workspace_id,
            "base_commit": self.base_commit,
            "patch_sha256": self.patch_sha256,
            "result_tree": self.result_tree,
            "staged_diff_sha256": self.staged_diff_sha256,
            "workspace_config_sha256": self.workspace_config_sha256,
            "changed_files": list(self.changed_files),
            "deleted_files": list(self.deleted_files),
            "result_index_paths": list(self.result_index_paths),
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "manifest_bytes": self.manifest_bytes,
            "files": [item.to_dict() for item in self.files],
            "tree_manifest_sha256": self.tree_manifest_sha256,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "source_repository_unchanged": self.source_repository_unchanged,
            "workspace_unchanged": self.workspace_unchanged,
            "repository_mutated": False,
            "network_attempted": False,
            "artifact_download_attempted": False,
            "dependency_install_attempted": False,
            "sandbox_launched": False,
            "runtime_lease_issued": False,
            "runtime_lease_claimed": False,
            "candidate_interpreter_executed": False,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionWorkspaceSnapshotStatus:
    state: str
    snapshot_fingerprint: str
    file_count: int
    total_bytes: int
    policy_id: str = DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID
    policy_fingerprint: str = DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT
    ttl_seconds: int = DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TTL_SECONDS
    execution_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "ttl_seconds": self.ttl_seconds,
            "execution_authorized": False,
        }


@dataclass(frozen=True)
class _TreeIdentityEntry:
    path: str
    mode: str
    object_type: str
    object_id: str
    size_bytes: int


@dataclass
class _SnapshotState:
    state: str
    entries: tuple[DeveloperTaskExecutionWorkspaceSnapshotEntry, ...] | None
    exact_files: dict[str, bytes] | None = field(repr=False)
    issued_at_ns: int
    expires_at_ns: int
    secret: bytes = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    issuer_id: object = field(repr=False)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class _SnapshotServices:
    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def token_bytes(self, size: int) -> bytes:
        return secrets.token_bytes(size)


_SERVICES = _SnapshotServices()
_REGISTRY: weakref.WeakKeyDictionary[DeveloperTaskExecutionWorkspaceSnapshot, _SnapshotState] = weakref.WeakKeyDictionary()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _compact_git_error(stderr: bytes, stdout: bytes) -> str:
    payload = stderr or stdout
    value = payload.decode("utf-8", errors="replace").replace("\x00", "\\0").strip()
    value = " ".join(value.split())
    return value[:497] + "..." if len(value) > 500 else value


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
        "schema_version": 1,
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


def _workspace_git_request(
    workspace: DeveloperTaskWorkspaceReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceGitRequest:
    expected_root = workspace_parent / workspace.workspace_id
    expected_control = expected_root / "control"
    return DeveloperTaskWorkspaceGitRequest(
        source_repository_root=workspace.source_repository_root,
        repository_root=workspace.repository_root,
        home_root=str(expected_control / "home"),
        xdg_root=str(expected_control / "xdg"),
        hooks_path=workspace.hooks_path,
        template_root=str(expected_control / "template"),
        global_config_path=str(expected_control / "gitconfig"),
        base_commit=workspace.base_commit,
    )


def _run_workspace_git(
    request: DeveloperTaskWorkspaceGitRequest,
    *args: str,
    timeout_seconds: float = GIT_TIMEOUT_SECONDS,
) -> bytes:
    repository_root = absolute_path(request.repository_root)
    command = [
        "git",
        f"--git-dir={repository_root / '.git'}",
        f"--work-tree={repository_root}",
        *workspace_git_command_prefix(request),
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.file.allow=never",
        *args,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(repository_root),
            env=build_workspace_git_environment(request),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_git_timeout",
            "Git snapshot transport timed out.",
        ) from exc
    except FileNotFoundError as exc:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_git_unavailable",
            "Git executable is unavailable for snapshot transport.",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_git_failed",
            "Git snapshot transport could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if completed.returncode:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_git_failed",
            "Git snapshot transport failed.",
            actual=_compact_git_error(completed.stderr, completed.stdout),
        )
    return bytes(completed.stdout)


def _single_ascii_line(payload: bytes, *, code: str) -> str:
    try:
        value = payload.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            code,
            "Git returned non-ASCII scalar output.",
        ) from exc
    if not value or "\n" in value or "\r" in value:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            code,
            "Git returned invalid scalar output.",
            actual=repr(value),
        )
    return value


def _validate_repository_path(path: str) -> None:
    if not path or len(path) > DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_LENGTH:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_path_invalid",
            "Snapshot path is empty or too long.",
            actual=path[:240],
        )
    if unicodedata.normalize(DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_PATH_UNICODE_NORMALIZATION, path) != path:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_path_not_normalized",
            "Snapshot path is not in canonical NFC form.",
            actual=path[:240],
        )
    if path.startswith(("/", "\\")) or _WINDOWS_DRIVE_RE.match(path) or "\\" in path:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_path_invalid",
            "Snapshot path must be repository-relative and use forward slashes.",
            actual=path[:240],
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_path_invalid",
            "Snapshot path contains a control character.",
            actual=repr(path[:240]),
        )
    parts = path.split("/")
    if (
        len(parts) > DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_DEPTH
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_path_invalid",
            "Snapshot path has invalid segments or depth.",
            actual=path[:240],
        )
    for part in parts:
        if len(part) > DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SEGMENT_LENGTH:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_path_invalid",
                "Snapshot path segment is too long.",
                actual=part[:120],
            )
        if part.endswith((" ", ".")) or any(char in '<>:"|?*' for char in part):
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_windows_path_invalid",
                "Snapshot path is unsafe on Windows.",
                actual=path[:240],
            )
        if _WINDOWS_RESERVED_RE.fullmatch(part):
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_windows_path_invalid",
                "Snapshot path contains a reserved Windows segment.",
                actual=path[:240],
            )


def _windows_path_key(path: str) -> str:
    return ntpath.normcase(path.replace("/", "\\")).casefold()


def _validate_tree_identity_entries(entries: tuple[_TreeIdentityEntry, ...]) -> None:
    if not entries:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_tree_empty",
            "Patched result tree is empty.",
        )
    if len(entries) > DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_FILE_COUNT:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_file_count_exceeded",
            "Patched result tree exceeds the snapshot file-count limit.",
            actual=str(len(entries)),
        )

    exact_paths: set[str] = set()
    windows_keys: set[str] = set()
    total_bytes = 0
    for entry in entries:
        _validate_repository_path(entry.path)
        if entry.path in exact_paths:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_duplicate_path",
                "Patched result tree contains a duplicate path.",
                actual=entry.path,
            )
        exact_paths.add(entry.path)
        key = _windows_path_key(entry.path)
        if key in windows_keys:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_windows_case_collision",
                "Patched result tree contains a Windows case-folding collision.",
                actual=entry.path,
            )
        windows_keys.add(key)
        if entry.object_type != "blob":
            code = (
                "workspace_snapshot_gitlink_rejected"
                if entry.object_type == "commit" or entry.mode == "160000"
                else "workspace_snapshot_non_blob_rejected"
            )
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                code,
                "Patched result tree contains a non-blob entry.",
                actual=f"{entry.mode} {entry.object_type} {entry.path}",
            )
        if entry.mode not in DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_ALLOWED_FILE_MODES:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_mode_rejected",
                "Patched result tree contains an unsupported file mode.",
                actual=f"{entry.mode} {entry.path}",
            )
        if entry.size_bytes < 0 or entry.size_bytes > DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_blob_too_large",
                "Patched result tree contains a blob outside the size boundary.",
                actual=f"{entry.path}:{entry.size_bytes}",
            )
        if total_bytes > DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_TOTAL_BYTES - entry.size_bytes:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_total_bytes_exceeded",
                "Patched result tree exceeds the total snapshot byte limit.",
            )
        total_bytes += entry.size_bytes

    for key in windows_keys:
        parts = key.split("\\")
        for index in range(1, len(parts)):
            if "\\".join(parts[:index]) in windows_keys:
                raise DeveloperTaskExecutionWorkspaceSnapshotError(
                    "workspace_snapshot_directory_file_collision",
                    "Patched result tree contains a directory/file collision on Windows.",
                    actual=key,
                )


def _parse_tree_identity(payload: bytes) -> tuple[_TreeIdentityEntry, ...]:
    entries: list[_TreeIdentityEntry] = []
    for record in payload.split(b"\x00"):
        if not record:
            continue
        match = _TREE_ENTRY_RE.fullmatch(record)
        if match is None:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_tree_output_invalid",
                "Git returned malformed result-tree identity output.",
            )
        raw_mode, raw_type, raw_object_id, raw_size, raw_path = match.groups()
        try:
            mode = raw_mode.decode("ascii", errors="strict")
            object_type = raw_type.decode("ascii", errors="strict")
            object_id = raw_object_id.decode("ascii", errors="strict").casefold()
            path = raw_path.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_tree_output_invalid",
                "Git returned invalid result-tree text.",
            ) from exc
        if raw_size == b"-":
            size_bytes = -1
        else:
            try:
                size_bytes = int(raw_size.decode("ascii", errors="strict"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise DeveloperTaskExecutionWorkspaceSnapshotError(
                    "workspace_snapshot_tree_output_invalid",
                    "Git returned invalid result-tree size evidence.",
                ) from exc
        entries.append(_TreeIdentityEntry(
            path=path,
            mode=mode,
            object_type=object_type,
            object_id=object_id,
            size_bytes=size_bytes,
        ))
    result = tuple(sorted(entries, key=lambda item: item.path))
    _validate_tree_identity_entries(result)
    return result


def _capture_result_tree(
    request: DeveloperTaskWorkspaceGitRequest,
    result_tree: str,
) -> tuple[
    tuple[DeveloperTaskExecutionWorkspaceSnapshotEntry, ...],
    dict[str, bytes],
    int,
    int,
    str,
]:
    if not _OBJECT_ID_RE.fullmatch(result_tree):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_result_tree_invalid",
            "Patch Apply result_tree is not a valid Git object identifier.",
            actual=result_tree,
        )
    object_type = _single_ascii_line(
        _run_workspace_git(request, "cat-file", "-t", result_tree),
        code="workspace_snapshot_result_tree_invalid",
    )
    if object_type != "tree":
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_result_tree_invalid",
            "Patch Apply result_tree does not identify a Git tree.",
            actual=object_type,
        )
    identity_payload = _run_workspace_git(
        request,
        "ls-tree",
        "-r",
        "-z",
        "-l",
        "--full-tree",
        result_tree,
    )
    identities = _parse_tree_identity(identity_payload)
    files: list[DeveloperTaskExecutionWorkspaceSnapshotEntry] = []
    exact_files: dict[str, bytes] = {}
    total_bytes = 0
    for identity in identities:
        content = _run_workspace_git(request, "cat-file", "blob", identity.object_id)
        if len(content) != identity.size_bytes:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_blob_size_mismatch",
                "Git blob bytes do not match the measured result-tree size.",
                actual=f"{identity.path}:{identity.size_bytes}->{len(content)}",
            )
        digest = _sha256(content)
        files.append(DeveloperTaskExecutionWorkspaceSnapshotEntry(
            path=identity.path,
            mode=identity.mode,
            object_id=identity.object_id,
            size_bytes=identity.size_bytes,
            sha256=digest,
        ))
        exact_files[identity.path] = content
        total_bytes += len(content)

    entry_manifest = {
        "algorithm": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TREE_MANIFEST_ALGORITHM,
        "files": [item.to_dict() for item in files],
    }
    manifest_payload = _canonical_json_bytes(entry_manifest)
    if len(manifest_payload) > DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_MANIFEST_BYTES:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_manifest_too_large",
            "Canonical snapshot manifest exceeds the manifest size boundary.",
            actual=str(len(manifest_payload)),
        )
    return tuple(files), exact_files, total_bytes, len(manifest_payload), _sha256(manifest_payload)


def _snapshot_fingerprint(
    *,
    manifest_fingerprint: str,
    workspace_id: str,
    base_commit: str,
    patch_sha256: str,
    result_tree: str,
    staged_diff_sha256: str,
    workspace_config_sha256: str,
    changed_files: tuple[str, ...],
    deleted_files: tuple[str, ...],
    changes: tuple[Any, ...],
    result_index_paths: tuple[str, ...],
    file_count: int,
    total_bytes: int,
    manifest_bytes: int,
    tree_manifest_sha256: str,
) -> str:
    return _sha256(_canonical_json_bytes({
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT,
        "snapshot_format": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_FORMAT,
        "manifest_fingerprint": manifest_fingerprint,
        "workspace_id": workspace_id,
        "base_commit": base_commit,
        "patch_sha256": patch_sha256,
        "result_tree": result_tree,
        "staged_diff_sha256": staged_diff_sha256,
        "workspace_config_sha256": workspace_config_sha256,
        "changed_files": list(changed_files),
        "deleted_files": list(deleted_files),
        "changes": [item.to_dict() for item in changes],
        "result_index_paths": list(result_index_paths),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "manifest_bytes": manifest_bytes,
        "tree_manifest_sha256": tree_manifest_sha256,
    }))


def _binding_fingerprint(report: DeveloperTaskExecutionWorkspaceSnapshotReport) -> str:
    return _sha256(_canonical_json_bytes({
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT,
        "snapshot_fingerprint": report.snapshot_fingerprint,
        "tree_manifest_sha256": report.tree_manifest_sha256,
        "file_count": report.file_count,
        "total_bytes": report.total_bytes,
    }))


def _claim_guard(secret: bytes, binding_fingerprint: str) -> bytes:
    return hmac.new(
        _ISSUER_SECRET,
        secret + binding_fingerprint.encode("ascii"),
        hashlib.sha256,
    ).digest()


def _invalidate_state(state: _SnapshotState, terminal_state: str) -> None:
    state.state = terminal_state
    state.entries = None
    state.exact_files = None
    state.issued_at_ns = 0
    state.expires_at_ns = 0
    state.secret = b""
    state.binding_fingerprint = ""
    state.issuer_id = object()


class DeveloperTaskExecutionWorkspaceSnapshotMaterial:
    __slots__ = ("report", "_entries", "_exact_files")

    def __init__(
        self,
        constructor_key: object,
        report: DeveloperTaskExecutionWorkspaceSnapshotReport,
        entries: tuple[DeveloperTaskExecutionWorkspaceSnapshotEntry, ...],
        exact_files: dict[str, bytes],
    ) -> None:
        if constructor_key is not _MATERIAL_CONSTRUCTOR_KEY:
            raise TypeError("DeveloperTaskExecutionWorkspaceSnapshotMaterial cannot be constructed directly")
        self.report = report
        self._entries = entries
        self._exact_files = exact_files

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self._entries)

    @property
    def file_count(self) -> int:
        return len(self._entries)

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self._entries)

    def entry(self, path: str) -> DeveloperTaskExecutionWorkspaceSnapshotEntry:
        if not isinstance(path, str):
            raise TypeError("path must be str")
        for item in self._entries:
            if item.path == path:
                return item
        raise KeyError(path)

    def exact_file_bytes(self, path: str) -> bytes:
        if not isinstance(path, str):
            raise TypeError("path must be str")
        try:
            return self._exact_files[path]
        except KeyError as exc:
            raise KeyError(path) from exc

    def __copy__(self):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshotMaterial is non-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshotMaterial is non-copyable")

    def __reduce__(self):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshotMaterial is non-serializable")

    def __reduce_ex__(self, protocol):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshotMaterial is non-serializable")

    def __getstate__(self):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshotMaterial is non-serializable")


class DeveloperTaskExecutionWorkspaceSnapshot:
    __slots__ = ("_guard", "report", "__weakref__")

    def __init__(
        self,
        constructor_key: object,
        guard: bytes,
        report: DeveloperTaskExecutionWorkspaceSnapshotReport,
    ) -> None:
        if constructor_key is not _CONSTRUCTOR_KEY:
            raise TypeError("DeveloperTaskExecutionWorkspaceSnapshot cannot be constructed directly")
        if not isinstance(guard, bytes) or len(guard) != hashlib.sha256().digest_size:
            raise TypeError("invalid snapshot guard")
        if type(report) is not DeveloperTaskExecutionWorkspaceSnapshotReport or not report.ok:
            raise TypeError("invalid snapshot report")
        self._guard = guard
        self.report = report

    @property
    def execution_authorized(self) -> bool:
        return False

    def status(self) -> DeveloperTaskExecutionWorkspaceSnapshotStatus:
        return _workspace_snapshot_status(self)

    def claim_for_plan(self) -> DeveloperTaskExecutionWorkspaceSnapshotMaterial:
        return _claim_developer_task_execution_workspace_snapshot_for_plan(self)

    def __repr__(self) -> str:
        status = self.status()
        return (
            "DeveloperTaskExecutionWorkspaceSnapshot("
            f"state={status.state!r}, snapshot_fingerprint={status.snapshot_fingerprint!r}, "
            "execution_authorized=False)"
        )

    def __copy__(self):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshot is non-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshot is non-copyable")

    def __reduce__(self):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshot is non-serializable")

    def __reduce_ex__(self, protocol):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshot is non-serializable")

    def __getstate__(self):
        raise TypeError("DeveloperTaskExecutionWorkspaceSnapshot is non-serializable")


def _workspace_snapshot_status(
    snapshot: DeveloperTaskExecutionWorkspaceSnapshot,
) -> DeveloperTaskExecutionWorkspaceSnapshotStatus:
    if type(snapshot) is not DeveloperTaskExecutionWorkspaceSnapshot:
        raise TypeError("snapshot must be DeveloperTaskExecutionWorkspaceSnapshot")
    with _REGISTRY_LOCK:
        state = _REGISTRY.get(snapshot)
    if state is None:
        return DeveloperTaskExecutionWorkspaceSnapshotStatus(
            state=SNAPSHOT_STATE_INVALIDATED,
            snapshot_fingerprint=snapshot.report.snapshot_fingerprint,
            file_count=snapshot.report.file_count,
            total_bytes=snapshot.report.total_bytes,
        )
    with state.lock:
        if state.state == SNAPSHOT_STATE_ISSUED:
            now_ns = _SERVICES.monotonic_ns()
            if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
                _invalidate_state(state, SNAPSHOT_STATE_INVALIDATED)
            elif now_ns >= state.expires_at_ns:
                _invalidate_state(state, SNAPSHOT_STATE_EXPIRED)
        return DeveloperTaskExecutionWorkspaceSnapshotStatus(
            state=state.state,
            snapshot_fingerprint=snapshot.report.snapshot_fingerprint,
            file_count=snapshot.report.file_count,
            total_bytes=snapshot.report.total_bytes,
        )


def _validate_typed_chain(
    manifest: DeveloperTaskManifest,
    preflight: DeveloperTaskPreflightReport,
    workspace: DeveloperTaskWorkspaceReport,
    patch_apply: DeveloperTaskPatchApplyReport,
    static_check: DeveloperTaskStaticCheckReport,
    workspace_parent: Path,
) -> tuple[str, Path, Path, Path, DeveloperTaskWorkspaceGitRequest]:
    if type(manifest) is not DeveloperTaskManifest:
        raise TypeError("manifest must be DeveloperTaskManifest")
    if type(preflight) is not DeveloperTaskPreflightReport:
        raise TypeError("preflight_report must be DeveloperTaskPreflightReport")
    if type(workspace) is not DeveloperTaskWorkspaceReport:
        raise TypeError("workspace_report must be DeveloperTaskWorkspaceReport")
    if type(patch_apply) is not DeveloperTaskPatchApplyReport:
        raise TypeError("patch_apply_report must be DeveloperTaskPatchApplyReport")
    if type(static_check) is not DeveloperTaskStaticCheckReport:
        raise TypeError("static_check_report must be DeveloperTaskStaticCheckReport")
    if not isinstance(workspace_parent, Path):
        raise TypeError("workspace_parent must be pathlib.Path")

    validation = validate_developer_task_manifest(manifest.to_dict())
    if not validation.ok or validation.manifest != manifest:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_manifest_invalid",
            "Canonical developer task manifest validation failed.",
            actual=",".join(validation.issue_codes),
        )
    manifest_fingerprint = developer_task_manifest_fingerprint(manifest)
    if not preflight.ok:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_preflight_failed",
            "Successful complete preflight evidence is required.",
            actual=",".join(preflight.issue_codes),
        )
    if not workspace.ok:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_workspace_failed",
            "Successful independent workspace evidence is required.",
            actual=",".join(workspace.issue_codes),
        )
    if not patch_apply.ok:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_patch_apply_failed",
            "Successful Patch Apply evidence is required.",
            actual=",".join(patch_apply.issue_codes),
        )
    if not static_check.ok:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_static_check_failed",
            "Successful host static-check evidence is required.",
            actual=",".join(static_check.issue_codes),
        )
    if (
        preflight.manifest_fingerprint != manifest_fingerprint
        or workspace.manifest_fingerprint != manifest_fingerprint
        or patch_apply.manifest_fingerprint != manifest_fingerprint
        or static_check.manifest_fingerprint != manifest_fingerprint
        or preflight.base_commit != manifest.base_commit
        or workspace.base_commit != manifest.base_commit
        or patch_apply.base_commit != manifest.base_commit
        or static_check.base_commit != manifest.base_commit
        or patch_apply.patch_sha256 != manifest.patch_sha256
        or patch_apply.changed_files != preflight.changed_files
        or static_check.changed_files != patch_apply.changed_files
        or patch_apply.workspace_id != workspace.workspace_id
        or static_check.workspace_id != workspace.workspace_id
        or patch_apply.source_repository_root != workspace.source_repository_root
        or static_check.source_repository_root != workspace.source_repository_root
        or patch_apply.task_root != workspace.task_root
        or static_check.task_root != workspace.task_root
        or patch_apply.workspace_root != workspace.workspace_root
        or static_check.workspace_root != workspace.workspace_root
        or patch_apply.repository_root != workspace.repository_root
        or static_check.repository_root != workspace.repository_root
    ):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_chain_mismatch",
            "Typed developer-task evidence chain is inconsistent.",
        )
    patch_index = preflight.patch_index_report
    if (
        patch_index is None
        or patch_apply.changes != patch_index.changes
        or patch_apply.result_index_paths != patch_index.result_index_paths
    ):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_patch_evidence_mismatch",
            "Patch Apply facts do not match canonical preflight patch evidence.",
        )
    static_git = static_check.git_evidence_after
    if (
        static_check.git_evidence_before is None
        or static_git is None
        or static_check.git_evidence_before != static_git
        or static_git.head_commit != patch_apply.head_commit
        or static_git.changed_files != patch_apply.changed_files
        or static_git.result_index_paths != patch_apply.result_index_paths
        or static_git.result_tree != patch_apply.result_tree
        or static_git.staged_diff_sha256 != patch_apply.staged_diff_sha256
        or static_git.workspace_config_sha256 != patch_apply.workspace_config_sha256
        or not static_git.staged_only
        or not static_git.index_matches_worktree
        or static_check.source_snapshot_before != patch_apply.source_snapshot_after
        or static_check.source_snapshot_after != patch_apply.source_snapshot_after
        or not static_check.source_repository_unchanged
        or not static_check.workspace_unchanged
    ):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_static_evidence_mismatch",
            "Static-check evidence does not match exact Patch Apply state.",
        )

    parent = absolute_path(workspace_parent)
    if not same_path(parent, workspace.workspace_parent) or not same_path(parent, patch_apply.workspace_parent):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_parent_mismatch",
            "Explicit workspace parent does not match retained evidence.",
        )
    if not workspace_id_matches(manifest.task_id, manifest_fingerprint, workspace.workspace_id):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_workspace_id_invalid",
            "Workspace ID does not match manifest evidence.",
            actual=workspace.workspace_id,
        )
    workspace_root = parent / workspace.workspace_id
    repository_root = workspace_root / "repository"
    control_root = workspace_root / "control"
    if not all((
        same_path(workspace.workspace_root, workspace_root),
        same_path(patch_apply.workspace_root, workspace_root),
        same_path(static_check.workspace_root, workspace_root),
        same_path(workspace.repository_root, repository_root),
        same_path(patch_apply.repository_root, repository_root),
        same_path(static_check.repository_root, repository_root),
        same_path(workspace.control_root, control_root),
        same_path(workspace.git_dir, repository_root / ".git"),
        same_path(workspace.hooks_path, control_root / "hooks"),
        same_path(workspace.marker_path, workspace_root / WORKSPACE_MARKER_NAME),
        same_path(patch_apply.apply_marker_path, control_root / "patch_apply.json"),
    )):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_layout_invalid",
            "Workspace paths do not match the fixed independent layout.",
        )
    source_root = absolute_path(workspace.source_repository_root)
    task_root = absolute_path(workspace.task_root)
    if (
        paths_overlap(workspace_root, source_root)
        or paths_overlap(workspace_root, task_root)
        or paths_overlap(parent, source_root)
        or paths_overlap(parent, task_root)
    ):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_paths_overlap",
            "Workspace paths overlap source or task roots.",
        )
    return manifest_fingerprint, parent, workspace_root, repository_root, _workspace_git_request(workspace, parent)


def _validate_workspace_filesystem(
    workspace: DeveloperTaskWorkspaceReport,
    patch_apply: DeveloperTaskPatchApplyReport,
    parent: Path,
    workspace_root: Path,
    repository_root: Path,
) -> None:
    try:
        validate_workspace_parent(parent)
        metadata = validate_workspace_root(workspace_root)
        if metadata is None:
            raise DeveloperTaskWorkspaceCleanupFileSystemError(
                "workspace_root_missing",
                "Workspace root is missing.",
                actual=str(workspace_root),
            )
        for path in (repository_root, workspace_root / "control"):
            item = os.lstat(path)
            if not stat.S_ISDIR(item.st_mode) or is_reparse_or_symlink(item):
                raise DeveloperTaskWorkspaceCleanupFileSystemError(
                    "workspace_path_invalid",
                    "Workspace directory is not a regular directory.",
                    actual=str(path),
                )
        workspace_marker = read_workspace_marker(Path(workspace.marker_path), workspace.marker_sha256)
        validate_canonical_marker(workspace_marker, _workspace_marker_payload(workspace))
        apply_marker = read_workspace_marker(Path(patch_apply.apply_marker_path), patch_apply.apply_marker_sha256)
        validate_canonical_marker(apply_marker, _apply_marker_payload(patch_apply))
    except (OSError, DeveloperTaskWorkspaceCleanupFileSystemError) as exc:
        actual = exc.actual if isinstance(exc, DeveloperTaskWorkspaceCleanupFileSystemError) else f"{type(exc).__name__}: {exc}"
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_filesystem_invalid",
            "Workspace filesystem or marker evidence is invalid.",
            actual=actual,
        ) from exc


def _source_snapshot_matches(
    snapshot: DeveloperTaskSourceRepositorySnapshot,
    expected_fingerprint: str,
) -> bool:
    return snapshot.fingerprint == expected_fingerprint


def capture_developer_task_execution_workspace_snapshot(
    manifest: DeveloperTaskManifest,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    patch_apply_report: DeveloperTaskPatchApplyReport,
    static_check_report: DeveloperTaskStaticCheckReport,
    *,
    workspace_parent: Path,
) -> DeveloperTaskExecutionWorkspaceSnapshot:
    """Capture exact result-tree bytes and issue one short-lived host-only plan capability."""

    policy_errors = validate_developer_task_execution_workspace_snapshot_policy(
        DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY
    )
    if policy_errors:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_policy_invalid",
            "Canonical V1C1A snapshot policy is invalid.",
            actual=",".join(policy_errors),
        )

    (
        manifest_fingerprint,
        parent,
        workspace_root,
        repository_root,
        git_request,
    ) = _validate_typed_chain(
        manifest,
        preflight_report,
        workspace_report,
        patch_apply_report,
        static_check_report,
        workspace_parent,
    )
    _validate_workspace_filesystem(
        workspace_report,
        patch_apply_report,
        parent,
        workspace_root,
        repository_root,
    )

    source_root = Path(workspace_report.source_repository_root)
    try:
        source_before = snapshot_developer_task_source_repository(source_root)
    except Exception as exc:
        actual = getattr(exc, "actual", "") or type(exc).__name__
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_source_probe_failed",
            "Fresh source repository evidence could not be captured before snapshot.",
            actual=actual,
        ) from exc
    if not _source_snapshot_matches(source_before, static_check_report.source_snapshot_after):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_source_repository_changed",
            "Source repository changed after the successful static gate.",
        )

    try:
        git_before = verify_developer_task_static_git(
            git_request,
            patch_apply_report=patch_apply_report,
        )
    except DeveloperTaskStaticGitError as exc:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_workspace_probe_failed",
            "Fresh workspace evidence failed before result-tree capture.",
            actual=f"{exc.code}:{exc.actual}",
        ) from exc
    if git_before != static_check_report.git_evidence_after:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_workspace_changed",
            "Fresh workspace evidence differs from successful static-check evidence.",
        )

    files, exact_files, total_bytes, manifest_bytes, tree_manifest_sha256 = _capture_result_tree(
        git_request,
        patch_apply_report.result_tree,
    )

    try:
        git_after = verify_developer_task_static_git(
            git_request,
            patch_apply_report=patch_apply_report,
        )
        source_after = snapshot_developer_task_source_repository(source_root)
    except DeveloperTaskStaticGitError as exc:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_workspace_probe_failed",
            "Fresh workspace evidence failed after result-tree capture.",
            actual=f"{exc.code}:{exc.actual}",
        ) from exc
    except Exception as exc:
        actual = getattr(exc, "actual", "") or type(exc).__name__
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_source_probe_failed",
            "Fresh source repository evidence failed after result-tree capture.",
            actual=actual,
        ) from exc

    if git_after != git_before or git_after != static_check_report.git_evidence_after:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_workspace_changed",
            "Workspace evidence changed during exact result-tree capture.",
        )
    if source_after.fingerprint != source_before.fingerprint or not _source_snapshot_matches(
        source_after,
        static_check_report.source_snapshot_after,
    ):
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_source_repository_changed",
            "Source repository changed during exact result-tree capture.",
        )

    deleted_files = tuple(
        item.path
        for item in patch_apply_report.changes
        if item.status == "D"
    )
    snapshot_fingerprint = _snapshot_fingerprint(
        manifest_fingerprint=manifest_fingerprint,
        workspace_id=workspace_report.workspace_id,
        base_commit=patch_apply_report.base_commit,
        patch_sha256=patch_apply_report.patch_sha256,
        result_tree=patch_apply_report.result_tree,
        staged_diff_sha256=patch_apply_report.staged_diff_sha256,
        workspace_config_sha256=patch_apply_report.workspace_config_sha256,
        changed_files=patch_apply_report.changed_files,
        deleted_files=deleted_files,
        changes=patch_apply_report.changes,
        result_index_paths=patch_apply_report.result_index_paths,
        file_count=len(files),
        total_bytes=total_bytes,
        manifest_bytes=manifest_bytes,
        tree_manifest_sha256=tree_manifest_sha256,
    )
    report = DeveloperTaskExecutionWorkspaceSnapshotReport(
        policy_id=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT,
        snapshot_format=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_FORMAT,
        source_authority=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SOURCE_AUTHORITY,
        manifest_fingerprint=manifest_fingerprint,
        workspace_id=workspace_report.workspace_id,
        base_commit=patch_apply_report.base_commit,
        patch_sha256=patch_apply_report.patch_sha256,
        result_tree=patch_apply_report.result_tree,
        staged_diff_sha256=patch_apply_report.staged_diff_sha256,
        workspace_config_sha256=patch_apply_report.workspace_config_sha256,
        changed_files=patch_apply_report.changed_files,
        deleted_files=deleted_files,
        result_index_paths=patch_apply_report.result_index_paths,
        file_count=len(files),
        total_bytes=total_bytes,
        manifest_bytes=manifest_bytes,
        files=files,
        tree_manifest_sha256=tree_manifest_sha256,
        snapshot_fingerprint=snapshot_fingerprint,
        source_repository_unchanged=True,
        workspace_unchanged=True,
    )
    if not report.ok:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_report_invalid",
            "Canonical V1C1A report failed its own invariants.",
        )

    issued_at_ns = _SERVICES.monotonic_ns()
    if not isinstance(issued_at_ns, int) or isinstance(issued_at_ns, bool) or issued_at_ns < 0:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_clock_invalid",
            "Monotonic snapshot clock returned an invalid value.",
        )
    try:
        secret = _SERVICES.token_bytes(DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SECRET_BYTES)
    except Exception as exc:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_secret_generation_failed",
            "Snapshot capability secret generation failed.",
            actual=type(exc).__name__,
        ) from exc
    if type(secret) is not bytes or len(secret) != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SECRET_BYTES:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_secret_generation_failed",
            "Snapshot capability secret generator returned invalid bytes.",
        )
    binding_fingerprint = _binding_fingerprint(report)
    guard = _claim_guard(secret, binding_fingerprint)
    snapshot = DeveloperTaskExecutionWorkspaceSnapshot(_CONSTRUCTOR_KEY, guard, report)
    state = _SnapshotState(
        state=SNAPSHOT_STATE_ISSUED,
        entries=files,
        exact_files=exact_files,
        issued_at_ns=issued_at_ns,
        expires_at_ns=(
            issued_at_ns
            + DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TTL_SECONDS * 1_000_000_000
        ),
        secret=secret,
        binding_fingerprint=binding_fingerprint,
        issuer_id=_ISSUER_ID,
    )
    with _REGISTRY_LOCK:
        _REGISTRY[snapshot] = state
    return snapshot


def _claim_developer_task_execution_workspace_snapshot_for_plan(
    snapshot: DeveloperTaskExecutionWorkspaceSnapshot,
) -> DeveloperTaskExecutionWorkspaceSnapshotMaterial:
    if type(snapshot) is not DeveloperTaskExecutionWorkspaceSnapshot:
        raise TypeError("snapshot must be DeveloperTaskExecutionWorkspaceSnapshot")
    with _REGISTRY_LOCK:
        state = _REGISTRY.get(snapshot)
    if state is None:
        raise DeveloperTaskExecutionWorkspaceSnapshotError(
            "workspace_snapshot_unregistered",
            "Snapshot capability is not registered in this process issuer.",
        )
    with state.lock:
        if state.state == SNAPSHOT_STATE_CLAIMED_FOR_PLAN:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_already_claimed",
                "Snapshot capability has already been claimed for plan issuance.",
            )
        if state.state == SNAPSHOT_STATE_EXPIRED:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_expired",
                "Snapshot capability has expired.",
            )
        if state.state != SNAPSHOT_STATE_ISSUED:
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_invalidated",
                "Snapshot capability is permanently invalidated.",
            )
        now_ns = _SERVICES.monotonic_ns()
        if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
            _invalidate_state(state, SNAPSHOT_STATE_INVALIDATED)
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_clock_invalid",
                "Monotonic snapshot clock returned an invalid value during claim.",
            )
        if now_ns >= state.expires_at_ns:
            _invalidate_state(state, SNAPSHOT_STATE_EXPIRED)
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_expired",
                "Snapshot capability has expired.",
            )
        entries = state.entries
        exact_files = state.exact_files
        if entries is None or exact_files is None:
            _invalidate_state(state, SNAPSHOT_STATE_INVALIDATED)
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_material_missing",
                "Snapshot capability no longer retains exact result-tree bytes.",
            )
        if (
            state.issuer_id is not _ISSUER_ID
            or len(state.secret) != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SECRET_BYTES
            or len(state.binding_fingerprint) != 64
            or state.binding_fingerprint != _binding_fingerprint(snapshot.report)
            or not hmac.compare_digest(
                snapshot._guard,
                _claim_guard(state.secret, state.binding_fingerprint),
            )
        ):
            _invalidate_state(state, SNAPSHOT_STATE_INVALIDATED)
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_issuer_binding_invalid",
                "Snapshot capability issuer/secret binding is invalid.",
            )
        policy_errors = validate_developer_task_execution_workspace_snapshot_policy(
            DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY
        )
        if policy_errors:
            _invalidate_state(state, SNAPSHOT_STATE_INVALIDATED)
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_policy_invalid",
                "Canonical V1C1A policy changed before claim.",
                actual=",".join(policy_errors),
            )
        if (
            tuple(item.path for item in entries) != tuple(sorted(exact_files))
            or len(entries) != snapshot.report.file_count
            or sum(item.size_bytes for item in entries) != snapshot.report.total_bytes
        ):
            _invalidate_state(state, SNAPSHOT_STATE_INVALIDATED)
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_material_invalid",
                "Retained exact snapshot material is inconsistent.",
            )
        for entry in entries:
            content = exact_files.get(entry.path)
            if content is None or len(content) != entry.size_bytes or _sha256(content) != entry.sha256:
                _invalidate_state(state, SNAPSHOT_STATE_INVALIDATED)
                raise DeveloperTaskExecutionWorkspaceSnapshotError(
                    "workspace_snapshot_material_invalid",
                    "Retained exact snapshot bytes changed before claim.",
                    actual=entry.path,
                )
        final_now_ns = _SERVICES.monotonic_ns()
        if not isinstance(final_now_ns, int) or isinstance(final_now_ns, bool) or final_now_ns < 0:
            _invalidate_state(state, SNAPSHOT_STATE_INVALIDATED)
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_clock_invalid",
                "Monotonic snapshot clock returned an invalid final claim value.",
            )
        if final_now_ns >= state.expires_at_ns:
            _invalidate_state(state, SNAPSHOT_STATE_EXPIRED)
            raise DeveloperTaskExecutionWorkspaceSnapshotError(
                "workspace_snapshot_expired",
                "Snapshot capability expired during atomic claim validation.",
            )
        material = DeveloperTaskExecutionWorkspaceSnapshotMaterial(
            _MATERIAL_CONSTRUCTOR_KEY,
            snapshot.report,
            entries,
            exact_files,
        )
        _invalidate_state(state, SNAPSHOT_STATE_CLAIMED_FOR_PLAN)
        return material
