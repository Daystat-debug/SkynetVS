from __future__ import annotations

import errno
import hashlib
import os
import re
import stat

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_preflight import (
    DeveloperTaskPreflightIssue,
    DeveloperTaskRepositoryPreflightReport,
)


_MAX_PATCH_BYTES = 5 * 1024 * 1024
_PATCH_READ_CHUNK_BYTES = 64 * 1024
_PATCH_FILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.patch$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class DeveloperTaskPatchSnapshot:
    path: str
    size_bytes: int
    sha256: str
    content: bytes = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskPatchIntegrityPreflightReport:
    manifest_fingerprint: str
    repository_root: str
    task_root: str
    patch_path: str
    patch_size_bytes: int
    actual_patch_sha256: str
    patch: DeveloperTaskPatchSnapshot | None
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return self.patch is not None and not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest_fingerprint": self.manifest_fingerprint,
            "repository_root": self.repository_root,
            "task_root": self.task_root,
            "patch_path": self.patch_path,
            "patch_size_bytes": self.patch_size_bytes,
            "actual_patch_sha256": self.actual_patch_sha256,
            "patch": self.patch.to_dict() if self.patch is not None else None,
            "issues": [item.to_dict() for item in self.issues],
        }


class _PatchIntegrityPreflightContext:
    def __init__(
        self,
        manifest: DeveloperTaskManifest,
        repository_report: DeveloperTaskRepositoryPreflightReport,
        task_root: Path,
    ) -> None:
        self.manifest = manifest
        self.manifest_fingerprint = developer_task_manifest_fingerprint(manifest)
        self.repository_report = repository_report
        self.repository_root = repository_report.repository_root
        self.task_root = _absolute_path(task_root)
        self.patch_path = ""
        self.patch_size_bytes = 0
        self.actual_patch_sha256 = ""
        self.patch_bytes: bytes | None = None
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

    def report(self) -> DeveloperTaskPatchIntegrityPreflightReport:
        snapshot = None

        if not self.issues and self.patch_bytes is not None:
            snapshot = DeveloperTaskPatchSnapshot(
                path=self.patch_path,
                size_bytes=self.patch_size_bytes,
                sha256=self.actual_patch_sha256,
                content=self.patch_bytes,
            )

        return DeveloperTaskPatchIntegrityPreflightReport(
            manifest_fingerprint=self.manifest_fingerprint,
            repository_root=self.repository_root,
            task_root=str(self.task_root),
            patch_path=self.patch_path,
            patch_size_bytes=self.patch_size_bytes,
            actual_patch_sha256=self.actual_patch_sha256,
            patch=snapshot,
            issues=tuple(self.issues),
        )


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _read_path_metadata(path: Path) -> os.stat_result:
    return os.lstat(path)


def _is_reparse_or_symlink(value: os.stat_result) -> bool:
    attributes = int(getattr(value, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse_flag)


def _stat_timestamp_ns(value: os.stat_result, name: str) -> int:
    direct = getattr(value, f"st_{name}_ns", None)

    if direct is not None:
        return int(direct)

    return int(float(getattr(value, f"st_{name}")) * 1_000_000_000)


def _file_version(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_size),
        _stat_timestamp_ns(value, "mtime"),
    )


def _same_file_version(first: os.stat_result, second: os.stat_result) -> bool:
    return _file_version(first) == _file_version(second)


def _paths_overlap(first: Path, second: Path) -> bool:
    try:
        common = Path(os.path.commonpath((os.fspath(first), os.fspath(second))))
    except ValueError:
        return False

    common_key = _path_key(common)
    return common_key in {_path_key(first), _path_key(second)}


def _valid_patch_file_name(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value == value.strip()
        and bool(_PATCH_FILE_NAME_RE.fullmatch(value))
    )


def _check_repository_report(context: _PatchIntegrityPreflightContext) -> bool:
    report = context.repository_report

    if not report.ok:
        context.add(
            "repository_preflight_failed",
            "repository_preflight",
            "Repository preflight must pass before patch integrity is checked.",
            expected="ok",
            actual=",".join(report.issue_codes) or "failed",
        )
        return False

    if report.manifest_fingerprint != context.manifest_fingerprint:
        context.add(
            "manifest_fingerprint_mismatch",
            "repository_preflight",
            "Repository preflight was created for a different manifest.",
            expected=context.manifest_fingerprint,
            actual=report.manifest_fingerprint,
        )
        return False

    if (
        not report.project_root
        or not report.repository_root
        or not report.head_commit
        or not report.resolved_base_commit
        or report.head_commit != report.resolved_base_commit
        or report.dirty_categories
    ):
        context.add(
            "repository_preflight_invalid",
            "repository_preflight",
            "Repository preflight report is internally inconsistent.",
            actual="incomplete or inconsistent repository proof",
        )
        return False

    try:
        project_root = Path(report.project_root).resolve(strict=True)
        repository_root = Path(report.repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        context.add(
            "repository_preflight_invalid",
            "repository_preflight",
            "Repository preflight paths could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    if _path_key(project_root) != _path_key(repository_root):
        context.add(
            "repository_preflight_invalid",
            "repository_preflight",
            "Repository preflight paths do not identify the same root.",
            expected=str(repository_root),
            actual=str(project_root),
        )
        return False

    context.repository_root = str(repository_root)
    return True


def _check_task_root(context: _PatchIntegrityPreflightContext) -> bool:
    try:
        metadata = _read_path_metadata(context.task_root)
    except FileNotFoundError:
        context.add(
            "task_root_missing",
            "task_root",
            "Task root does not exist.",
            actual=str(context.task_root),
        )
        return False
    except OSError as exc:
        context.add(
            "task_root_metadata_failed",
            "task_root",
            "Task root metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    if _is_reparse_or_symlink(metadata):
        context.add(
            "task_root_reparse_point",
            "task_root",
            "Task root must not be a symlink, junction, or reparse point.",
            actual=str(context.task_root),
        )
        return False

    if not stat.S_ISDIR(metadata.st_mode):
        context.add(
            "task_root_not_directory",
            "task_root",
            "Task root must be a directory.",
            actual=str(context.task_root),
        )
        return False

    try:
        context.task_root = context.task_root.resolve(strict=True)
        repository_root = Path(context.repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        context.add(
            "task_root_unresolved",
            "task_root",
            "Task root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    if _paths_overlap(context.task_root, repository_root):
        context.add(
            "task_root_overlaps_project",
            "task_root",
            "Task root and project repository must be disjoint directory trees.",
            expected=f"outside {repository_root}",
            actual=str(context.task_root),
        )
        return False

    return True


def _read_patch_bytes(
    context: _PatchIntegrityPreflightContext,
    patch_path: Path,
    initial_metadata: os.stat_result,
) -> bytes | None:
    flags = os.O_RDONLY

    for name in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW"):
        flags |= int(getattr(os, name, 0))

    try:
        descriptor = os.open(os.fspath(patch_path), flags)
    except FileNotFoundError:
        context.add(
            "patch_file_missing",
            "patch_file",
            "Patch file disappeared before it could be opened.",
            actual=str(patch_path),
        )
        return None
    except OSError as exc:
        code = "patch_file_reparse_point" if exc.errno == errno.ELOOP else "patch_file_open_failed"
        message = (
            "Patch file must not be a symlink or reparse point."
            if code == "patch_file_reparse_point"
            else "Patch file could not be opened for binary reading."
        )
        context.add(
            code,
            "patch_file",
            message,
            actual=f"{type(exc).__name__}: {exc}",
        )
        return None

    chunks: list[bytes] = []
    total = 0

    try:
        opened_metadata = os.fstat(descriptor)

        if (
            _is_reparse_or_symlink(opened_metadata)
            or not stat.S_ISREG(opened_metadata.st_mode)
            or not _same_file_version(initial_metadata, opened_metadata)
        ):
            context.add(
                "patch_file_changed_during_read",
                "patch_file",
                "Patch file identity changed between metadata validation and open.",
                actual=str(patch_path),
            )
            return None

        while True:
            chunk = os.read(descriptor, _PATCH_READ_CHUNK_BYTES)

            if not chunk:
                break

            total += len(chunk)

            if total > _MAX_PATCH_BYTES:
                context.patch_size_bytes = total
                context.add(
                    "patch_file_too_large",
                    "patch_file",
                    "Patch file exceeds the maximum allowed size.",
                    expected=str(_MAX_PATCH_BYTES),
                    actual=str(total),
                )
                return None

            chunks.append(chunk)

        final_metadata = os.fstat(descriptor)

        if (
            not _same_file_version(opened_metadata, final_metadata)
            or total != int(final_metadata.st_size)
        ):
            context.patch_size_bytes = total
            context.add(
                "patch_file_changed_during_read",
                "patch_file",
                "Patch file changed while it was being read.",
                expected=str(opened_metadata.st_size),
                actual=str(final_metadata.st_size),
            )
            return None
    except OSError as exc:
        context.add(
            "patch_file_read_failed",
            "patch_file",
            "Patch file could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return None
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass

    content = b"".join(chunks)
    context.patch_size_bytes = len(content)
    return content


def _check_patch_file(context: _PatchIntegrityPreflightContext) -> None:
    if not _valid_patch_file_name(context.manifest.patch_file):
        context.add(
            "patch_file_invalid",
            "patch_file",
            "Patch file must be a validated basename ending in .patch.",
            actual=str(context.manifest.patch_file),
        )
        return

    if not isinstance(context.manifest.patch_sha256, str) or not _SHA256_RE.fullmatch(
        context.manifest.patch_sha256
    ):
        context.add(
            "patch_hash_invalid",
            "patch_sha256",
            "Patch SHA-256 must contain exactly 64 lowercase hexadecimal characters.",
            actual=str(context.manifest.patch_sha256),
        )
        return

    patch_path = context.task_root / context.manifest.patch_file
    context.patch_path = str(patch_path)

    try:
        metadata = _read_path_metadata(patch_path)
    except FileNotFoundError:
        context.add(
            "patch_file_missing",
            "patch_file",
            "Patch file does not exist.",
            actual=str(patch_path),
        )
        return
    except OSError as exc:
        context.add(
            "patch_file_metadata_failed",
            "patch_file",
            "Patch file metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return

    if _is_reparse_or_symlink(metadata):
        context.add(
            "patch_file_reparse_point",
            "patch_file",
            "Patch file must not be a symlink or reparse point.",
            actual=str(patch_path),
        )
        return

    if not stat.S_ISREG(metadata.st_mode):
        context.add(
            "patch_file_not_regular",
            "patch_file",
            "Patch file must be a regular file.",
            actual=str(patch_path),
        )
        return

    context.patch_size_bytes = int(metadata.st_size)

    if context.patch_size_bytes == 0:
        context.add(
            "patch_file_empty",
            "patch_file",
            "Patch file must not be empty.",
            actual="0",
        )
        return

    if context.patch_size_bytes > _MAX_PATCH_BYTES:
        context.add(
            "patch_file_too_large",
            "patch_file",
            "Patch file exceeds the maximum allowed size.",
            expected=str(_MAX_PATCH_BYTES),
            actual=str(context.patch_size_bytes),
        )
        return

    content = _read_patch_bytes(context, patch_path, metadata)

    if content is None:
        return

    if not content:
        context.add(
            "patch_file_empty",
            "patch_file",
            "Patch file must not be empty.",
            actual="0",
        )
        return

    context.actual_patch_sha256 = hashlib.sha256(content).hexdigest()

    if context.actual_patch_sha256 != context.manifest.patch_sha256:
        context.add(
            "patch_hash_mismatch",
            "patch_sha256",
            "Patch bytes do not match the manifest SHA-256.",
            expected=context.manifest.patch_sha256,
            actual=context.actual_patch_sha256,
        )
        return

    context.patch_bytes = content


def run_developer_task_patch_integrity_preflight(
    manifest: DeveloperTaskManifest,
    *,
    repository_report: DeveloperTaskRepositoryPreflightReport,
    task_root: Path,
) -> DeveloperTaskPatchIntegrityPreflightReport:
    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(repository_report, DeveloperTaskRepositoryPreflightReport):
        raise TypeError("repository_report must be DeveloperTaskRepositoryPreflightReport")

    if not isinstance(task_root, Path):
        raise TypeError("task_root must be pathlib.Path")

    context = _PatchIntegrityPreflightContext(manifest, repository_report, task_root)

    if not _check_repository_report(context):
        return context.report()

    if not _check_task_root(context):
        return context.report()

    _check_patch_file(context)
    return context.report()
