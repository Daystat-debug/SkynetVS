from __future__ import annotations

"""Filesystem safety primitives for developer-task workspace cleanup."""

import hashlib
import json
import os
import re
import shutil
import stat
import time

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


WORKSPACE_PREFIX = "skynetvs-task-"
WORKSPACE_MARKER_NAME = "workspace.json"
WORKSPACE_MARKER_SCHEMA_VERSION = 1
MARKER_MAX_BYTES = 64 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_CLEANUP_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2, 0.4)


@dataclass(frozen=True)
class DeveloperTaskWorkspaceMarkerSnapshot:
    content: bytes = field(repr=False)
    sha256: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class DeveloperTaskWorkspaceRemovalResult:
    removed: bool
    already_absent: bool
    attempts: int


class DeveloperTaskWorkspaceCleanupFileSystemError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        actual: str = "",
        *,
        attempts: int = 0,
    ) -> None:
        self.code = code
        self.actual = actual
        self.attempts = attempts
        super().__init__(message)


def absolute_path(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path))).casefold()


def same_path(first: Path | str, second: Path | str) -> bool:
    return path_key(first) == path_key(second)


def paths_overlap(first: Path, second: Path) -> bool:
    first_key = path_key(first)
    second_key = path_key(second)
    separator = os.sep.casefold()
    return (
        first_key == second_key
        or first_key.startswith(second_key + separator)
        or second_key.startswith(first_key + separator)
    )


def is_reparse_or_symlink(value: os.stat_result) -> bool:
    file_attributes = int(getattr(value, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(value.st_mode) or bool(file_attributes & reparse_flag)


def workspace_id_matches(
    task_id: str,
    manifest_fingerprint: str,
    workspace_id: str,
) -> bool:
    task_part = re.escape(task_id[:24])
    fingerprint_part = re.escape(manifest_fingerprint[:12])
    pattern = re.compile(
        rf"^{re.escape(WORKSPACE_PREFIX)}{task_part}-{fingerprint_part}-[0-9a-f]{{24}}$"
    )
    return bool(pattern.fullmatch(workspace_id))


def _path_chain_has_reparse(path: Path) -> bool:
    parts = absolute_path(path).parts

    if not parts:
        return True

    current = Path(parts[0])

    for part in parts[1:]:
        current /= part

        if is_reparse_or_symlink(os.lstat(current)):
            return True

    return False


def validate_workspace_parent(workspace_parent: Path) -> None:
    try:
        metadata = os.lstat(workspace_parent)
    except FileNotFoundError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_parent_missing",
            "Workspace parent directory does not exist.",
            actual=str(workspace_parent),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_parent_metadata_failed",
            "Workspace parent metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISDIR(metadata.st_mode):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_parent_not_directory",
            "Workspace parent must be a directory.",
            actual=str(workspace_parent),
        )

    if is_reparse_or_symlink(metadata):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_parent_reparse_point",
            "Workspace parent must not be a symlink, junction, or reparse point.",
            actual=str(workspace_parent),
        )

    try:
        indirect = _path_chain_has_reparse(workspace_parent)
    except OSError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_parent_metadata_failed",
            "Workspace parent path chain could not be validated.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if indirect:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_parent_indirect",
            "Workspace parent path chain must not contain reparse points.",
            actual=str(workspace_parent),
        )


def validate_workspace_root(workspace_root: Path) -> os.stat_result | None:
    try:
        metadata = os.lstat(workspace_root)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_root_metadata_failed",
            "Workspace root metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISDIR(metadata.st_mode):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_root_not_directory",
            "Workspace root must be a directory.",
            actual=str(workspace_root),
        )

    if is_reparse_or_symlink(metadata):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_root_reparse_point",
            "Workspace root must not be a symlink, junction, or reparse point.",
            actual=str(workspace_root),
        )

    return metadata


def _file_version(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        int(getattr(value, "st_dev", 0)),
        int(getattr(value, "st_ino", 0)),
        int(value.st_size),
        int(getattr(value, "st_mtime_ns", int(value.st_mtime * 1_000_000_000))),
    )


def _read_file_descriptor(descriptor: int, size: int) -> bytes:
    return os.read(descriptor, size)


def read_workspace_marker(
    marker_path: Path,
    expected_sha256: str,
) -> DeveloperTaskWorkspaceMarkerSnapshot:
    try:
        initial = os.lstat(marker_path)
    except FileNotFoundError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_missing",
            "Workspace marker is missing.",
            actual=str(marker_path),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_metadata_failed",
            "Workspace marker metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISREG(initial.st_mode):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_not_regular",
            "Workspace marker must be a regular file.",
            actual=str(marker_path),
        )

    if is_reparse_or_symlink(initial):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_reparse_point",
            "Workspace marker must not be a symlink or reparse point.",
            actual=str(marker_path),
        )

    if initial.st_size <= 0 or initial.st_size > MARKER_MAX_BYTES:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_size_invalid",
            "Workspace marker size is outside the accepted boundary.",
            actual=str(initial.st_size),
        )

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))

    try:
        descriptor = os.open(marker_path, flags)
    except OSError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_open_failed",
            "Workspace marker could not be opened.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    try:
        opened = os.fstat(descriptor)

        if _file_version(initial) != _file_version(opened):
            raise DeveloperTaskWorkspaceCleanupFileSystemError(
                "workspace_marker_changed_during_read",
                "Workspace marker changed before it could be read.",
            )

        chunks: list[bytes] = []
        total = 0

        while True:
            chunk = _read_file_descriptor(
                descriptor,
                min(_READ_CHUNK_BYTES, MARKER_MAX_BYTES + 1 - total),
            )

            if not chunk:
                break

            chunks.append(chunk)
            total += len(chunk)

            if total > MARKER_MAX_BYTES:
                raise DeveloperTaskWorkspaceCleanupFileSystemError(
                    "workspace_marker_size_invalid",
                    "Workspace marker exceeded the accepted boundary while reading.",
                    actual=str(total),
                )

        final = os.fstat(descriptor)
    except DeveloperTaskWorkspaceCleanupFileSystemError:
        raise
    except OSError as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_read_failed",
            "Workspace marker could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    finally:
        os.close(descriptor)

    content = b"".join(chunks)

    if _file_version(opened) != _file_version(final) or len(content) != final.st_size:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_changed_during_read",
            "Workspace marker changed while it was being read.",
        )

    actual_sha256 = hashlib.sha256(content).hexdigest()

    if actual_sha256 != expected_sha256:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_hash_mismatch",
            "Workspace marker SHA-256 does not match workspace evidence.",
            actual=actual_sha256,
        )

    try:
        text = content.decode("utf-8", errors="strict")
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_invalid",
            "Workspace marker is not valid canonical UTF-8 JSON.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not isinstance(payload, dict):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_fields_invalid",
            "Workspace marker must contain one JSON object.",
            actual=type(payload).__name__,
        )

    return DeveloperTaskWorkspaceMarkerSnapshot(
        content=content,
        sha256=actual_sha256,
        payload=payload,
    )


def validate_canonical_marker(
    marker: DeveloperTaskWorkspaceMarkerSnapshot,
    expected_payload: dict[str, Any],
) -> None:
    if frozenset(marker.payload) != frozenset(expected_payload):
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_fields_invalid",
            "Workspace marker fields do not match the cleanup contract.",
            actual=", ".join(sorted(str(item) for item in marker.payload)),
        )

    canonical = json.dumps(
        expected_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    if marker.payload != expected_payload or marker.content != canonical:
        raise DeveloperTaskWorkspaceCleanupFileSystemError(
            "workspace_marker_evidence_mismatch",
            "Workspace marker does not match canonical immutable workspace evidence.",
        )


def _same_directory_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (
        stat.S_ISDIR(second.st_mode)
        and not is_reparse_or_symlink(second)
        and int(getattr(first, "st_dev", 0)) == int(getattr(second, "st_dev", 0))
        and int(getattr(first, "st_ino", 0)) == int(getattr(second, "st_ino", 0))
    )


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
            continue

    return None


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


def remove_verified_workspace(
    workspace_root: Path,
    initial_metadata: os.stat_result,
) -> DeveloperTaskWorkspaceRemovalResult:
    delays = (0.0, *_CLEANUP_RETRY_DELAYS_SECONDS)
    last_error = ""
    attempts = 0

    for index, delay in enumerate(delays):
        if delay:
            time.sleep(delay)

        attempts += 1

        try:
            current = os.lstat(workspace_root)
        except FileNotFoundError:
            return DeveloperTaskWorkspaceRemovalResult(True, False, attempts)
        except OSError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            break

        if not _same_directory_identity(initial_metadata, current):
            raise DeveloperTaskWorkspaceCleanupFileSystemError(
                "workspace_cleanup_target_changed",
                "Workspace cleanup target identity changed before removal.",
                actual=str(workspace_root),
                attempts=attempts,
            )

        try:
            unsafe = _find_unsafe_tree_entry(workspace_root)
        except OSError as exc:
            raise DeveloperTaskWorkspaceCleanupFileSystemError(
                "workspace_tree_scan_failed",
                "Workspace tree could not be scanned safely.",
                actual=f"{type(exc).__name__}: {exc}",
                attempts=attempts,
            ) from exc

        if unsafe is not None:
            code, path = unsafe
            raise DeveloperTaskWorkspaceCleanupFileSystemError(
                code,
                "Workspace tree contains an entry that cleanup will not traverse.",
                actual=path,
                attempts=attempts,
            )

        try:
            shutil.rmtree(
                workspace_root,
                onerror=_rmtree_windows_readonly_handler,
            )
        except FileNotFoundError:
            return DeveloperTaskWorkspaceRemovalResult(True, False, attempts)
        except OSError as exc:
            last_error = f"{type(exc).__name__}: {exc}"

            if index != len(delays) - 1:
                continue
        else:
            try:
                os.lstat(workspace_root)
            except FileNotFoundError:
                return DeveloperTaskWorkspaceRemovalResult(True, False, attempts)
            except OSError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                last_error = "Workspace root still exists after shutil.rmtree."

        if index == len(delays) - 1:
            break

    raise DeveloperTaskWorkspaceCleanupFileSystemError(
        "workspace_cleanup_failed",
        "Verified workspace could not be removed safely.",
        actual=last_error or str(workspace_root),
        attempts=attempts,
    )
