from __future__ import annotations

"""Isolated Git-index analysis for validated developer-task patch bytes."""

import hashlib
import json
import ntpath
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_patch_integrity import (
    DeveloperTaskPatchIntegrityPreflightReport,
)
from modules.developer.developer_task_preflight import (
    DeveloperTaskPreflightIssue,
    DeveloperTaskRepositoryPreflightReport,
    _build_git_environment,
)


_GIT_TIMEOUT_SECONDS = 10.0
_RAW_DIFF_HEADER_RE = re.compile(
    rb"^:([0-7]{6}) ([0-7]{6}) ([0-9a-f]{40,64}) ([0-9a-f]{40,64}) ([A-Z])(?:[0-9]{1,3})?$"
)
_INDEX_ENTRY_RE = re.compile(
    rb"^([0-7]{6}) ([0-9a-f]{40,64}) ([0-3])\t(.*)$",
    re.DOTALL,
)
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_RESERVED_RE = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$",
    re.IGNORECASE,
)
_MAX_PATH_LENGTH = 240
_MAX_SEGMENT_LENGTH = 120
_TEMP_WORKSPACE_PREFIX = "skynetvs_developer_patch_index_"
_TEMP_CLEANUP_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2, 0.4)
_ALLOWED_CHANGE_STATUSES = frozenset({"A", "D", "M", "T"})
_ALLOWED_FILE_MODES = frozenset({"000000", "100644", "100755", "120000", "160000"})


@dataclass(frozen=True)
class DeveloperTaskPatchIndexChange:
    """One repository-relative change observed in the isolated index."""

    path: str
    status: str
    old_mode: str
    new_mode: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "status": self.status,
            "old_mode": self.old_mode,
            "new_mode": self.new_mode,
        }


@dataclass(frozen=True)
class DeveloperTaskPatchIndexPreflightReport:
    """Immutable evidence produced by the V1C1 isolated-index gate."""

    manifest_fingerprint: str
    repository_root: str
    base_commit: str
    changed_files: tuple[str, ...]
    changes: tuple[DeveloperTaskPatchIndexChange, ...]
    result_index_paths: tuple[str, ...]
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return bool(self.changes) and not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest_fingerprint": self.manifest_fingerprint,
            "repository_root": self.repository_root,
            "base_commit": self.base_commit,
            "changed_files": list(self.changed_files),
            "changes": [item.to_dict() for item in self.changes],
            "result_index_paths": list(self.result_index_paths),
            "issues": [item.to_dict() for item in self.issues],
        }


@dataclass(frozen=True)
class _GitBytesResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class _PatchIndexGitError(RuntimeError):
    def __init__(self, code: str, message: str, actual: str = "") -> None:
        self.code = code
        self.actual = actual
        super().__init__(message)


class _PatchIndexContext:
    def __init__(
        self,
        manifest: DeveloperTaskManifest,
        repository_report: DeveloperTaskRepositoryPreflightReport,
        patch_integrity_report: DeveloperTaskPatchIntegrityPreflightReport,
    ) -> None:
        self.manifest = manifest
        self.manifest_fingerprint = developer_task_manifest_fingerprint(manifest)
        self.repository_report = repository_report
        self.patch_integrity_report = patch_integrity_report
        self.repository_root = ""
        self.base_commit = ""
        self.changes: tuple[DeveloperTaskPatchIndexChange, ...] = ()
        self.changed_files: tuple[str, ...] = ()
        self.result_index_paths: tuple[str, ...] = ()
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

    def report(self) -> DeveloperTaskPatchIndexPreflightReport:
        return DeveloperTaskPatchIndexPreflightReport(
            manifest_fingerprint=self.manifest_fingerprint,
            repository_root=self.repository_root,
            base_commit=self.base_commit,
            changed_files=self.changed_files,
            changes=self.changes,
            result_index_paths=self.result_index_paths,
            issues=tuple(self.issues),
        )


def _path_key(value: str) -> str:
    return ntpath.normcase(value.replace("/", "\\"))


def _compact_bytes_error(stderr: bytes, stdout: bytes) -> str:
    raw = stderr or stdout
    value = raw.decode("utf-8", errors="replace").strip().replace("\x00", "\\0")

    if len(value) > 500:
        return value[:497] + "..."

    return value


def _build_patch_index_git_environment() -> dict[str, str]:
    env = _build_git_environment()

    for key in (
        "GIT_ATTR_SOURCE",
        "GIT_DIFF_OPTS",
        "GIT_EXTERNAL_DIFF",
        "GIT_INDEX_VERSION",
    ):
        env.pop(key, None)

    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_LITERAL_PATHSPECS"] = "1"
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def _run_git_bytes(
    repository_root: Path,
    *args: str,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
) -> _GitBytesResult:
    command = [
        "git",
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "apply.ignoreWhitespace=no",
        "-C",
        str(repository_root),
        *args,
    ]

    try:
        completed = subprocess.run(
            command,
            input=input_bytes,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            env=env or _build_patch_index_git_environment(),
            stdin=subprocess.DEVNULL if input_bytes is None else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise _PatchIndexGitError(
            "git_command_timeout",
            "Git command timed out.",
            actual=" ".join(command[1:]),
        ) from exc
    except FileNotFoundError as exc:
        raise _PatchIndexGitError(
            "git_unavailable",
            "Git executable is unavailable.",
            actual=str(exc),
        ) from exc
    except OSError as exc:
        raise _PatchIndexGitError(
            "git_command_failed",
            "Git command could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    return _GitBytesResult(
        returncode=int(completed.returncode),
        stdout=bytes(completed.stdout),
        stderr=bytes(completed.stderr),
    )


def _run_git_or_issue(
    context: _PatchIndexContext,
    check: str,
    failure_code: str,
    failure_message: str,
    repository_root: Path,
    *args: str,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
) -> _GitBytesResult | None:
    try:
        result = _run_git_bytes(
            repository_root,
            *args,
            input_bytes=input_bytes,
            env=env,
        )
    except _PatchIndexGitError as exc:
        context.add(
            exc.code,
            check,
            str(exc),
            actual=exc.actual,
        )
        return None

    if result.returncode != 0:
        context.add(
            failure_code,
            check,
            failure_message,
            actual=_compact_bytes_error(result.stderr, result.stdout),
        )
        return None

    return result


def _decode_single_path(raw: bytes) -> str:
    try:
        value = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Git path is not valid UTF-8") from exc

    if (
        not value
        or value != value.strip()
        or "\\" in value
        or value.startswith("/")
        or _WINDOWS_DRIVE_RE.match(value)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError("Git path is not a safe repository-relative path")

    if len(value) > _MAX_PATH_LENGTH:
        raise ValueError("Git path is too long")

    parts = value.split("/")

    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Git path contains an unsafe segment")

    for part in parts:
        if len(part) > _MAX_SEGMENT_LENGTH:
            raise ValueError("Git path contains an overlong segment")

        if part.endswith((" ", ".")):
            raise ValueError("Git path contains a Windows-unsafe segment")

        if any(char in '<>:"|?*' for char in part):
            raise ValueError("Git path contains a Windows-invalid character")

        if _WINDOWS_RESERVED_RE.fullmatch(part):
            raise ValueError("Git path contains a reserved Windows name")

    return value


def _parse_raw_diff(payload: bytes) -> tuple[DeveloperTaskPatchIndexChange, ...]:
    if not payload:
        return ()

    fields = payload.split(b"\x00")

    if not fields or fields[-1] != b"":
        raise ValueError("Raw Git diff is not NUL terminated")

    fields = fields[:-1]

    if len(fields) % 2:
        raise ValueError("Raw Git diff contains an incomplete record")

    changes: list[DeveloperTaskPatchIndexChange] = []
    seen_paths: set[str] = set()

    for index in range(0, len(fields), 2):
        header = fields[index]
        path_raw = fields[index + 1]
        match = _RAW_DIFF_HEADER_RE.fullmatch(header)

        if match is None:
            raise ValueError("Raw Git diff header is invalid")

        old_mode = match.group(1).decode("ascii")
        new_mode = match.group(2).decode("ascii")
        status = match.group(5).decode("ascii")

        if status not in _ALLOWED_CHANGE_STATUSES:
            raise ValueError(f"Raw Git diff status is unsupported: {status}")

        if old_mode not in _ALLOWED_FILE_MODES or new_mode not in _ALLOWED_FILE_MODES:
            raise ValueError("Raw Git diff contains an unsupported file mode")

        if status == "A" and (old_mode != "000000" or new_mode == "000000"):
            raise ValueError("Added path has inconsistent modes")

        if status == "D" and (old_mode == "000000" or new_mode != "000000"):
            raise ValueError("Deleted path has inconsistent modes")

        if status in {"M", "T"} and (old_mode == "000000" or new_mode == "000000"):
            raise ValueError("Modified path has inconsistent modes")

        path = _decode_single_path(path_raw)

        if path in seen_paths:
            raise ValueError("Raw Git diff contains a duplicate path")

        seen_paths.add(path)
        changes.append(
            DeveloperTaskPatchIndexChange(
                path=path,
                status=status,
                old_mode=old_mode,
                new_mode=new_mode,
            )
        )

    return tuple(sorted(changes, key=lambda item: (_path_key(item.path), item.path)))


def _parse_index_paths(payload: bytes) -> tuple[str, ...]:
    if not payload:
        return ()

    records = payload.split(b"\x00")

    if not records or records[-1] != b"":
        raise ValueError("Git index listing is not NUL terminated")

    paths: list[str] = []

    for record in records[:-1]:
        match = _INDEX_ENTRY_RE.fullmatch(record)

        if match is None:
            raise ValueError("Git index entry is invalid")

        if match.group(3) != b"0":
            raise ValueError("Git index contains an unmerged stage")

        mode = match.group(1).decode("ascii")

        if mode not in _ALLOWED_FILE_MODES - {"000000"}:
            raise ValueError("Git index contains an unsupported file mode")

        paths.append(_decode_single_path(match.group(4)))

    if len(set(paths)) != len(paths):
        raise ValueError("Git index contains a duplicate path")

    return tuple(paths)


def parse_developer_task_patch_changes(
    payload: bytes,
) -> tuple[DeveloperTaskPatchIndexChange, ...]:
    """Parse machine-readable staged diff facts using the V1C1 contract."""
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")

    return _parse_raw_diff(payload)


def parse_developer_task_result_index_paths(
    payload: bytes,
) -> tuple[str, ...]:
    """Parse and canonically sort machine-readable result-index paths."""
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")

    paths = _parse_index_paths(payload)
    return tuple(sorted(paths, key=lambda item: (_path_key(item), item)))


def _check_prerequisites(context: _PatchIndexContext) -> bool:
    repository_report = context.repository_report
    patch_report = context.patch_integrity_report

    if not repository_report.ok:
        context.add(
            "repository_preflight_failed",
            "prerequisites",
            "Repository preflight must pass before patch index is analyzed.",
            expected="ok",
            actual=",".join(repository_report.issue_codes) or "failed",
        )
        return False

    if not patch_report.ok:
        context.add(
            "patch_integrity_preflight_failed",
            "prerequisites",
            "Patch integrity preflight must pass before patch index is analyzed.",
            expected="ok",
            actual=",".join(patch_report.issue_codes) or "failed",
        )
        return False

    if (
        repository_report.manifest_fingerprint != context.manifest_fingerprint
        or patch_report.manifest_fingerprint != context.manifest_fingerprint
    ):
        context.add(
            "manifest_fingerprint_mismatch",
            "prerequisites",
            "Preflight reports were created for a different manifest.",
            expected=context.manifest_fingerprint,
            actual=(
                f"repository={repository_report.manifest_fingerprint};"
                f"patch={patch_report.manifest_fingerprint}"
            ),
        )
        return False

    if (
        not repository_report.repository_root
        or not repository_report.head_commit
        or not repository_report.resolved_base_commit
        or repository_report.head_commit != repository_report.resolved_base_commit
        or repository_report.dirty_categories
    ):
        context.add(
            "repository_preflight_invalid",
            "prerequisites",
            "Repository preflight report is internally inconsistent.",
            actual="incomplete or inconsistent repository proof",
        )
        return False

    if (
        not patch_report.repository_root
        or patch_report.repository_root != repository_report.repository_root
        or patch_report.patch is None
        or patch_report.patch_size_bytes != patch_report.patch.size_bytes
        or patch_report.actual_patch_sha256 != patch_report.patch.sha256
    ):
        context.add(
            "patch_integrity_preflight_invalid",
            "prerequisites",
            "Patch integrity preflight report is internally inconsistent.",
            actual="incomplete or inconsistent patch proof",
        )
        return False

    snapshot = patch_report.patch
    actual_sha256 = hashlib.sha256(snapshot.content).hexdigest()

    if (
        len(snapshot.content) != snapshot.size_bytes
        or actual_sha256 != snapshot.sha256
        or actual_sha256 != context.manifest.patch_sha256
    ):
        context.add(
            "patch_snapshot_invalid",
            "prerequisites",
            "Patch snapshot bytes do not match their recorded integrity proof.",
            expected=context.manifest.patch_sha256,
            actual=actual_sha256,
        )
        return False

    try:
        repository_root = Path(repository_report.repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        context.add(
            "repository_preflight_invalid",
            "prerequisites",
            "Repository root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    context.repository_root = str(repository_root)
    context.base_commit = repository_report.resolved_base_commit
    return True


def _resolve_real_object_directory(
    context: _PatchIndexContext,
    repository_root: Path,
) -> Path | None:
    result = _run_git_or_issue(
        context,
        "git_object_directory",
        "git_object_directory_unresolved",
        "Git object directory could not be resolved.",
        repository_root,
        "rev-parse",
        "--git-path",
        "objects",
        env=_build_patch_index_git_environment(),
    )

    if result is None:
        return None

    try:
        value = result.stdout.decode("utf-8", errors="strict").rstrip("\r\n")
    except UnicodeDecodeError as exc:
        context.add(
            "git_object_directory_unresolved",
            "git_object_directory",
            "Git object directory output is not valid UTF-8.",
            actual=str(exc),
        )
        return None

    if not value or "\n" in value or "\r" in value:
        context.add(
            "git_object_directory_unresolved",
            "git_object_directory",
            "Git object directory output is invalid.",
            actual=value,
        )
        return None

    path = Path(value)

    if not path.is_absolute():
        path = repository_root / path

    try:
        path = path.resolve(strict=True)
        metadata = os.lstat(path)
    except (OSError, RuntimeError) as exc:
        context.add(
            "git_object_directory_unresolved",
            "git_object_directory",
            "Git object directory could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return None

    if not stat.S_ISDIR(metadata.st_mode):
        context.add(
            "git_object_directory_unresolved",
            "git_object_directory",
            "Git object directory is not a directory.",
            actual=str(path),
        )
        return None

    return path


def _create_temporary_workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix=_TEMP_WORKSPACE_PREFIX))


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _paths_overlap(left: Path, right: Path) -> bool:
    return _path_is_within(left, right) or _path_is_within(right, left)


def _validate_temporary_workspace(
    context: _PatchIndexContext,
    candidate: Path,
    repository_root: Path,
) -> Path | None:
    try:
        metadata = os.lstat(candidate)
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        context.add(
            "temporary_workspace_failed",
            "temporary_workspace",
            "Temporary Git workspace could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return None

    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(attributes & reparse_flag)
    ):
        context.add(
            "temporary_workspace_failed",
            "temporary_workspace",
            "Temporary Git workspace is not a safe directory.",
            actual=str(candidate),
        )
        return None

    if _paths_overlap(resolved, repository_root):
        context.add(
            "temporary_workspace_overlap",
            "temporary_workspace",
            "Temporary Git workspace must not overlap the project repository.",
            expected="separate directory tree",
            actual=str(resolved),
        )
        return None

    return resolved


def _safe_temporary_cleanup_target(
    candidate: Path | None,
    repository_root: Path,
) -> Path | None:
    if candidate is None or not candidate.name.startswith(_TEMP_WORKSPACE_PREFIX):
        return None

    try:
        metadata = os.lstat(candidate)
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None

    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(attributes & reparse_flag)
        or resolved == repository_root
        or _path_is_within(repository_root, resolved)
    ):
        return None

    return candidate


def _rmtree_windows_readonly_handler(
    function: Any,
    path: str,
    exc_info: tuple[type[BaseException], BaseException, Any],
) -> None:
    error = exc_info[1]

    if os.name != "nt" or not isinstance(error, PermissionError):
        raise error

    metadata = os.lstat(path)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))

    if stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag):
        raise error

    os.chmod(path, stat.S_IWRITE)
    function(path)


def _remove_temporary_workspace(
    candidate: Path | None,
    repository_root: Path,
) -> OSError | None:
    cleanup_target = _safe_temporary_cleanup_target(
        candidate,
        repository_root,
    )

    if cleanup_target is None:
        return None

    last_error: OSError | None = None
    attempt_count = len(_TEMP_CLEANUP_RETRY_DELAYS_SECONDS) + 1

    for attempt in range(attempt_count):
        try:
            shutil.rmtree(
                cleanup_target,
                onerror=_rmtree_windows_readonly_handler,
            )
            return None
        except FileNotFoundError:
            return None
        except OSError as exc:
            last_error = exc

        if attempt >= len(_TEMP_CLEANUP_RETRY_DELAYS_SECONDS):
            break

        try:
            os.lstat(cleanup_target)
        except FileNotFoundError:
            return None
        except OSError as exc:
            return exc

        cleanup_target = _safe_temporary_cleanup_target(
            cleanup_target,
            repository_root,
        )

        if cleanup_target is None:
            return OSError(
                "Temporary workspace is no longer a safe cleanup target"
            )

        time.sleep(_TEMP_CLEANUP_RETRY_DELAYS_SECONDS[attempt])

    return last_error or OSError("Temporary workspace cleanup failed")


def _prepare_temporary_git_environment(
    scratch_root: Path,
    real_object_directory: Path,
) -> tuple[Path, dict[str, str]]:
    metadata = os.lstat(scratch_root)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))

    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(attributes & reparse_flag)
    ):
        raise OSError("Temporary workspace is not a safe directory")

    index_path = scratch_root / "index"
    object_directory = scratch_root / "objects"
    object_directory.mkdir()
    env = _build_patch_index_git_environment()
    env["GIT_INDEX_FILE"] = str(index_path)
    env["GIT_OBJECT_DIRECTORY"] = str(object_directory)
    env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = json.dumps(
        str(real_object_directory),
        ensure_ascii=False,
    )
    return index_path, env


def _analyze_patch_index(
    context: _PatchIndexContext,
    repository_root: Path,
    real_object_directory: Path,
    scratch_root: Path,
) -> None:
    try:
        _, git_env = _prepare_temporary_git_environment(
            scratch_root,
            real_object_directory,
        )
    except (OSError, UnicodeError) as exc:
        context.add(
            "temporary_workspace_failed",
            "temporary_workspace",
            "Temporary Git workspace could not be prepared.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return

    read_tree = _run_git_or_issue(
        context,
        "temporary_index_init",
        "temporary_index_init_failed",
        "Temporary Git index could not be initialized from base_commit.",
        repository_root,
        "read-tree",
        "--reset",
        "-i",
        "--no-sparse-checkout",
        context.base_commit,
        env=git_env,
    )

    if read_tree is None:
        return

    snapshot = context.patch_integrity_report.patch
    assert snapshot is not None
    summary_result = _run_git_or_issue(
        context,
        "patch_index_summary",
        "patch_index_summary_failed",
        "Patch summary could not be inspected.",
        repository_root,
        "apply",
        "--cached",
        "--summary",
        "--allow-empty",
        "-",
        input_bytes=snapshot.content,
        env=git_env,
    )

    if summary_result is None:
        return

    copy_lines = tuple(
        line
        for line in summary_result.stdout.splitlines()
        if line.startswith(b" copy ")
    )

    if copy_lines:
        context.add(
            "patch_copy_unsupported",
            "patch_index_summary",
            "Explicit Git copy operations are not allowed in developer-task patches.",
            actual=_compact_bytes_error(b"\n".join(copy_lines), b""),
        )
        return

    apply_result = _run_git_or_issue(
        context,
        "patch_index_apply",
        "patch_index_apply_failed",
        "Patch could not be applied to the isolated base_commit index.",
        repository_root,
        "apply",
        "--cached",
        "--allow-empty",
        "--whitespace=nowarn",
        "-",
        input_bytes=snapshot.content,
        env=git_env,
    )

    if apply_result is None:
        return

    diff_result = _run_git_or_issue(
        context,
        "patch_index_diff",
        "patch_index_diff_failed",
        "Isolated patch diff could not be inspected.",
        repository_root,
        "diff",
        "--cached",
        "--raw",
        "-z",
        "--no-renames",
        "--no-abbrev",
        "--no-ext-diff",
        "--no-textconv",
        "--ignore-submodules=none",
        context.base_commit,
        "--",
        env=git_env,
    )

    if diff_result is None:
        return

    index_result = _run_git_or_issue(
        context,
        "patch_index_index",
        "patch_index_index_failed",
        "Isolated Git index could not be inspected.",
        repository_root,
        "ls-files",
        "--stage",
        "-z",
        env=git_env,
    )

    if index_result is None:
        return

    try:
        changes = _parse_raw_diff(diff_result.stdout)
        index_paths = _parse_index_paths(index_result.stdout)
    except ValueError as exc:
        context.add(
            "patch_index_output_invalid",
            "patch_index_parse",
            "Git returned an invalid machine-readable patch index result.",
            actual=str(exc),
        )
        return

    context.changes = changes
    context.changed_files = tuple(item.path for item in changes)
    context.result_index_paths = tuple(sorted(index_paths, key=lambda item: (_path_key(item), item)))

    if not changes:
        context.add(
            "patch_no_changes",
            "patch_index",
            "Patch produces no changes relative to base_commit.",
        )


def run_developer_task_patch_index_preflight(
    manifest: DeveloperTaskManifest,
    *,
    repository_report: DeveloperTaskRepositoryPreflightReport,
    patch_integrity_report: DeveloperTaskPatchIntegrityPreflightReport,
) -> DeveloperTaskPatchIndexPreflightReport:
    """Analyze verified patch bytes without touching the real index or worktree."""
    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(repository_report, DeveloperTaskRepositoryPreflightReport):
        raise TypeError("repository_report must be DeveloperTaskRepositoryPreflightReport")

    if not isinstance(
        patch_integrity_report,
        DeveloperTaskPatchIntegrityPreflightReport,
    ):
        raise TypeError(
            "patch_integrity_report must be DeveloperTaskPatchIntegrityPreflightReport"
        )

    context = _PatchIndexContext(
        manifest,
        repository_report,
        patch_integrity_report,
    )

    if not _check_prerequisites(context):
        return context.report()

    repository_root = Path(context.repository_root)
    real_object_directory = _resolve_real_object_directory(context, repository_root)

    if real_object_directory is None:
        return context.report()

    scratch_candidate: Path | None = None
    scratch_root: Path | None = None

    try:
        try:
            scratch_candidate = _create_temporary_workspace()
        except OSError as exc:
            context.add(
                "temporary_workspace_failed",
                "temporary_workspace",
                "Temporary Git workspace could not be created.",
                actual=f"{type(exc).__name__}: {exc}",
            )
        else:
            scratch_root = _validate_temporary_workspace(
                context,
                scratch_candidate,
                repository_root,
            )

            if scratch_root is not None:
                _analyze_patch_index(
                    context,
                    repository_root,
                    real_object_directory,
                    scratch_root,
                )
    finally:
        cleanup_error = _remove_temporary_workspace(
            scratch_candidate,
            repository_root,
        )

        if cleanup_error is not None:
            context.add(
                "temporary_workspace_cleanup_failed",
                "temporary_workspace_cleanup",
                "Temporary Git workspace could not be removed.",
                actual=f"{type(cleanup_error).__name__}: {cleanup_error}",
            )

    return context.report()
