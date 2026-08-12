from __future__ import annotations

"""V1B4B deterministic trusted CPython runtime-bundle builder."""

import hashlib
import io
import json
import os
import re
import secrets
import stat
import struct
import time
import zipfile

from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any

from modules.developer.developer_task_execution_runtime_policy import (
    MAX_RUNTIME_COMPRESSION_RATIO,
    MAX_RUNTIME_OUTER_ENTRIES,
    MAX_RUNTIME_OUTER_ENTRY_BYTES,
    MAX_RUNTIME_OUTER_TOTAL_BYTES,
    MAX_RUNTIME_SOURCE_BYTES,
    MAX_RUNTIME_STDLIB_ENTRIES,
    MAX_RUNTIME_STDLIB_ENTRY_BYTES,
    MAX_RUNTIME_STDLIB_TOTAL_BYTES,
    RUNTIME_ALLOWED_COMPRESSION,
    RUNTIME_APPROVED_STDLIB_PLACEHOLDER,
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_ID,
    RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_FORBIDDEN_COMPONENTS,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    RUNTIME_LOCKED_PTH_BYTES,
    RUNTIME_LOCKED_PTH_FILE_NAME,
    RUNTIME_LOCKED_PTH_SHA256,
    RUNTIME_MANIFEST_FILE_NAME,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PROBE_BYTES,
    RUNTIME_PROBE_FILE_NAME,
    RUNTIME_PROBE_SHA256,
    RUNTIME_REQUIRED_STDLIB_FILES,
    RUNTIME_RUNNER_BYTES,
    RUNTIME_RUNNER_FILE_NAME,
    RUNTIME_RUNNER_SHA256,
    RUNTIME_SOURCE_ARCHITECTURE,
    RUNTIME_SOURCE_FILE_NAME,
    RUNTIME_SOURCE_FINGERPRINT,
    RUNTIME_SOURCE_ID,
    RUNTIME_SOURCE_OUTER_ENTRY_COUNT,
    RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
    RUNTIME_SOURCE_OUTER_TOTAL_BYTES,
    RUNTIME_SOURCE_PE_FILE_COUNT,
    RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    RUNTIME_SOURCE_PTH_CRLF_COUNT,
    RUNTIME_SOURCE_PTH_NORMALIZED_LF_SHA256,
    RUNTIME_SOURCE_PTH_NORMALIZED_LF_SIZE_BYTES,
    RUNTIME_SOURCE_PTH_SHA256,
    RUNTIME_SOURCE_PTH_SIZE_BYTES,
    RUNTIME_SOURCE_PYTHON_DLL_SHA256,
    RUNTIME_SOURCE_PYTHON_EXE_SHA256,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_SOURCE_SIZE_BYTES,
    RUNTIME_SOURCE_STDLIB_ENTRY_COUNT,
    RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
    RUNTIME_SOURCE_STDLIB_SHA256,
    RUNTIME_SOURCE_STDLIB_SIZE_BYTES,
    RUNTIME_SOURCE_STDLIB_TOTAL_BYTES,
    RUNTIME_SOURCE_VERSION,
    RUNTIME_TREE_MANIFEST_SHA256,
    TRUSTED_PYTHON_RUNTIME_POLICY_V1,
    DeveloperTaskPythonRuntimePolicy,
    runtime_launch_contract_fingerprint,
    validate_trusted_python_runtime_policy,
)


_RUNTIME_BUNDLE_SCHEMA_VERSION = 1
_RUNTIME_MANIFEST_SCHEMA_VERSION = 1
_RUNTIME_STAGING_PREFIX = "skynetvs-runtime-bundle-"
_RUNTIME_STAGING_TOKEN_BYTES = 12
_RUNTIME_READ_CHUNK_BYTES = 1024 * 1024
_RUNTIME_CLEANUP_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2, 0.4)
_WINDOWS_REPARSE_POINT = 0x400
_PE_MACHINE_AMD64 = 0x8664
_PE_SUFFIXES = {".exe", ".dll", ".pyd"}
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class DeveloperTaskPythonRuntimeBundleFile:
    path: str
    kind: str
    size_bytes: int
    sha256: str
    _bytes: bytes = field(repr=False, compare=False)

    @property
    def ok(self) -> bool:
        return (
            bool(self.path)
            and bool(self.kind)
            and self.size_bytes == len(self._bytes)
            and self.sha256 == _sha256(self._bytes)
        )

    def exact_bytes(self) -> bytes:
        return self._bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskPythonRuntimeBundleReport:
    schema_version: int
    bundle_id: str
    source_id: str
    source_version: str
    source_architecture: str
    source_sha256: str
    source_fingerprint: str
    source_policy_fingerprint: str
    bundle_policy_fingerprint: str
    source_entry_count: int
    source_outer_manifest_sha256: str
    source_stdlib_manifest_sha256: str
    source_passthrough_file_count: int
    project_owned_file_count: int
    bundle_file_count: int
    bundle_total_bytes: int
    tree_manifest_sha256: str
    runtime_manifest_sha256: str
    python_executable_sha256: str
    python_dll_sha256: str
    python_pth_sha256: str
    stdlib_sha256: str
    runtime_probe_sha256: str
    runtime_runner_sha256: str
    launch_contract_fingerprint: str
    bundle_fingerprint: str
    post_write_regular_files_verified: bool
    post_write_reparse_points_absent: bool
    staging_cleaned: bool
    interpreter_executed: bool = False
    execution_authorized: bool = False

    @property
    def ok(self) -> bool:
        return (
            self.schema_version == _RUNTIME_BUNDLE_SCHEMA_VERSION
            and self.bundle_id == RUNTIME_BUNDLE_ID
            and self.source_id == RUNTIME_SOURCE_ID
            and self.source_version == RUNTIME_SOURCE_VERSION
            and self.source_architecture == RUNTIME_SOURCE_ARCHITECTURE
            and self.source_sha256 == RUNTIME_SOURCE_SHA256
            and self.source_fingerprint == RUNTIME_SOURCE_FINGERPRINT
            and self.source_policy_fingerprint == RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT
            and self.bundle_policy_fingerprint == RUNTIME_BUNDLE_POLICY_FINGERPRINT
            and self.source_entry_count == RUNTIME_SOURCE_OUTER_ENTRY_COUNT
            and self.source_outer_manifest_sha256 == RUNTIME_SOURCE_OUTER_MANIFEST_SHA256
            and self.source_stdlib_manifest_sha256 == RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256
            and self.source_passthrough_file_count == RUNTIME_SOURCE_OUTER_ENTRY_COUNT - 1
            and self.project_owned_file_count == 4
            and self.bundle_file_count == RUNTIME_BUNDLE_FILE_COUNT
            and self.bundle_total_bytes == RUNTIME_BUNDLE_TOTAL_BYTES
            and self.tree_manifest_sha256 == RUNTIME_TREE_MANIFEST_SHA256
            and self.runtime_manifest_sha256 == RUNTIME_MANIFEST_SHA256
            and self.python_executable_sha256 == RUNTIME_SOURCE_PYTHON_EXE_SHA256
            and self.python_dll_sha256 == RUNTIME_SOURCE_PYTHON_DLL_SHA256
            and self.python_pth_sha256 == RUNTIME_LOCKED_PTH_SHA256
            and self.stdlib_sha256 == RUNTIME_SOURCE_STDLIB_SHA256
            and self.runtime_probe_sha256 == RUNTIME_PROBE_SHA256
            and self.runtime_runner_sha256 == RUNTIME_RUNNER_SHA256
            and self.launch_contract_fingerprint == RUNTIME_LAUNCH_CONTRACT_FINGERPRINT
            and self.bundle_fingerprint == RUNTIME_BUNDLE_FINGERPRINT
            and self.post_write_regular_files_verified
            and self.post_write_reparse_points_absent
            and self.staging_cleaned
            and not self.interpreter_executed
            and not self.execution_authorized
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "source_architecture": self.source_architecture,
            "source_sha256": self.source_sha256,
            "source_fingerprint": self.source_fingerprint,
            "source_policy_fingerprint": self.source_policy_fingerprint,
            "bundle_policy_fingerprint": self.bundle_policy_fingerprint,
            "source_entry_count": self.source_entry_count,
            "source_outer_manifest_sha256": self.source_outer_manifest_sha256,
            "source_stdlib_manifest_sha256": self.source_stdlib_manifest_sha256,
            "source_passthrough_file_count": self.source_passthrough_file_count,
            "project_owned_file_count": self.project_owned_file_count,
            "bundle_file_count": self.bundle_file_count,
            "bundle_total_bytes": self.bundle_total_bytes,
            "tree_manifest_sha256": self.tree_manifest_sha256,
            "runtime_manifest_sha256": self.runtime_manifest_sha256,
            "python_executable_sha256": self.python_executable_sha256,
            "python_dll_sha256": self.python_dll_sha256,
            "python_pth_sha256": self.python_pth_sha256,
            "stdlib_sha256": self.stdlib_sha256,
            "runtime_probe_sha256": self.runtime_probe_sha256,
            "runtime_runner_sha256": self.runtime_runner_sha256,
            "launch_contract_fingerprint": self.launch_contract_fingerprint,
            "bundle_fingerprint": self.bundle_fingerprint,
            "post_write_regular_files_verified": self.post_write_regular_files_verified,
            "post_write_reparse_points_absent": self.post_write_reparse_points_absent,
            "staging_cleaned": self.staging_cleaned,
            "interpreter_executed": self.interpreter_executed,
            "execution_authorized": self.execution_authorized,
        }


@dataclass(frozen=True)
class DeveloperTaskPythonRuntimeBundle:
    report: DeveloperTaskPythonRuntimeBundleReport
    _files: tuple[DeveloperTaskPythonRuntimeBundleFile, ...] = field(repr=False, compare=False)

    @property
    def ok(self) -> bool:
        if not self.report.ok or len(self._files) != RUNTIME_BUNDLE_FILE_COUNT:
            return False
        names = tuple(item.path for item in self._files)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            return False
        tree = [item.to_dict() for item in self._files]
        tree_manifest = [
            {
                "path": item["path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
            }
            for item in tree
        ]
        return (
            all(item.ok for item in self._files)
            and _sha256(_canonical_json_bytes(tree_manifest)) == self.report.tree_manifest_sha256
            and _bundle_fingerprint(self.report) == self.report.bundle_fingerprint
        )

    @property
    def file_names(self) -> tuple[str, ...]:
        return tuple(item.path for item in self._files)

    def exact_file_bytes(self, path: str) -> bytes:
        if not isinstance(path, str) or not path:
            raise TypeError("path must be a non-empty string")
        for item in self._files:
            if item.path == path:
                return item.exact_bytes()
        raise KeyError(path)

    def to_dict(self) -> dict[str, Any]:
        return self.report.to_dict()


class DeveloperTaskPythonRuntimeBundleError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        self.code = code
        self.message = message
        self.actual = actual
        super().__init__(message)


@dataclass(frozen=True)
class _SourceEvidence:
    files: dict[str, bytes] = field(repr=False, compare=False)
    outer_manifest_sha256: str
    stdlib_manifest_sha256: str


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_reparse_or_symlink(value: os.stat_result) -> bool:
    attributes = int(getattr(value, "st_file_attributes", 0))
    return stat.S_ISLNK(value.st_mode) or bool(attributes & _WINDOWS_REPARSE_POINT)


def _file_version(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        int(getattr(value, "st_dev", 0)),
        int(getattr(value, "st_ino", 0)),
        int(value.st_size),
        int(getattr(value, "st_mtime_ns", int(value.st_mtime * 1_000_000_000))),
    )


def _validate_path_chain(path: Path, *, code_prefix: str) -> None:
    absolute = _absolute_path(path)
    parts = absolute.parts
    if not parts:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_path_invalid",
            "Path is empty.",
            actual=str(path),
        )

    current = Path(parts[0])
    for part in parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{code_prefix}_metadata_failed",
                "Path metadata could not be read.",
                actual=f"{current}: {type(exc).__name__}: {exc}",
            ) from exc
        if _is_reparse_or_symlink(metadata):
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{code_prefix}_indirect_reparse_point",
                "Path chain must not contain symlinks, junctions, or reparse points.",
                actual=str(current),
            )


def _read_regular_file(path: Path, *, max_bytes: int, code_prefix: str) -> bytes:
    absolute = _absolute_path(path)
    _validate_path_chain(absolute.parent, code_prefix=code_prefix)

    try:
        initial = os.lstat(absolute)
    except FileNotFoundError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_missing",
            "Required file does not exist.",
            actual=str(absolute),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_metadata_failed",
            "File metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISREG(initial.st_mode):
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_not_regular",
            "File must be regular.",
            actual=str(absolute),
        )
    if _is_reparse_or_symlink(initial):
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_reparse_point",
            "File must not be a symlink or reparse point.",
            actual=str(absolute),
        )
    if initial.st_size <= 0 or initial.st_size > max_bytes:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_size_invalid",
            "File size is outside the accepted boundary.",
            actual=str(initial.st_size),
        )

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_open_failed",
            "File could not be opened.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    try:
        opened = os.fstat(descriptor)
        if _file_version(initial) != _file_version(opened):
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{code_prefix}_changed_during_read",
                "File changed before it could be read.",
            )

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(_RUNTIME_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise DeveloperTaskPythonRuntimeBundleError(
                    f"{code_prefix}_size_invalid",
                    "File exceeded the accepted boundary while reading.",
                    actual=str(total),
                )
        final = os.fstat(descriptor)
    except DeveloperTaskPythonRuntimeBundleError:
        raise
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_read_failed",
            "File could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    finally:
        os.close(descriptor)

    data = b"".join(chunks)
    try:
        after = os.lstat(absolute)
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_changed_during_read",
            "File metadata disappeared after read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if (
        _file_version(opened) != _file_version(final)
        or _file_version(initial) != _file_version(after)
        or len(data) != final.st_size
    ):
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{code_prefix}_changed_during_read",
            "File changed while it was being read.",
        )
    return data


def _validate_artifact_parent(artifact_parent: Path) -> Path:
    parent = _absolute_path(artifact_parent)

    try:
        metadata = os.lstat(parent)
    except FileNotFoundError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_artifact_parent_missing",
            "Runtime artifact parent does not exist.",
            actual=str(parent),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_artifact_parent_metadata_failed",
            "Runtime artifact parent metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISDIR(metadata.st_mode):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_artifact_parent_not_directory",
            "Runtime artifact parent must be a directory.",
            actual=str(parent),
        )
    _validate_path_chain(parent.parent, code_prefix="runtime_artifact_parent")
    if _is_reparse_or_symlink(metadata):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_artifact_parent_reparse_point",
            "Runtime artifact parent must not be a reparse point.",
            actual=str(parent),
        )
    return parent


def _windows_component_key(component: str) -> str:
    trimmed = component.rstrip(" .")
    return trimmed.upper().split(".", 1)[0]


def _validate_zip_path(name: str, *, label: str, allow_nested: bool) -> str:
    if not name or "\x00" in name:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_path_invalid",
            "ZIP path is empty or contains NUL.",
            actual=repr(name),
        )
    if "\\" in name:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_backslash_path",
            "Backslash ZIP paths are forbidden.",
            actual=name,
        )
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_absolute_path",
            "Absolute ZIP paths are forbidden.",
            actual=name,
        )

    raw = name[:-1] if name.endswith("/") else name
    path = PurePosixPath(raw)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_path_traversal",
            "Unsafe ZIP traversal path is forbidden.",
            actual=name,
        )
    if len(path.parts) > 16:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_path_depth",
            "ZIP path is too deep.",
            actual=name,
        )
    if not allow_nested and len(path.parts) != 1:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_nested_path",
            "Nested outer runtime ZIP paths are forbidden.",
            actual=name,
        )

    for component in path.parts:
        if component.endswith((" ", ".")):
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_windows_unsafe_path",
                "Windows trailing dot/space is forbidden.",
                actual=name,
            )
        if _windows_component_key(component) in _WINDOWS_RESERVED:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_windows_reserved_path",
                "Windows reserved path is forbidden.",
                actual=name,
            )
        if ":" in component:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_alternate_stream_path",
                "Alternate data stream syntax is forbidden.",
                actual=name,
            )
    return path.as_posix()


def _zip_entry_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_IFMT(mode) == stat.S_IFLNK


def _inspect_zip_infos(
    archive: zipfile.ZipFile,
    *,
    label: str,
    max_entries: int,
    max_total_bytes: int,
    max_entry_bytes: int,
    allow_nested: bool,
) -> tuple[list[tuple[str, zipfile.ZipInfo]], int]:
    infos = archive.infolist()
    if not infos or len(infos) > max_entries:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_entry_count_invalid",
            "ZIP entry count is outside the accepted boundary.",
            actual=str(len(infos)),
        )

    exact: set[str] = set()
    windows_keys: dict[str, str] = {}
    files: list[tuple[str, zipfile.ZipInfo]] = []
    total = 0

    for info in infos:
        normalized = _validate_zip_path(info.filename, label=label, allow_nested=allow_nested)
        key = normalized.casefold()
        if normalized in exact:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_duplicate_path",
                "Duplicate ZIP path is forbidden.",
                actual=normalized,
            )
        if key in windows_keys and windows_keys[key] != normalized:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_case_collision",
                "Windows case-colliding ZIP paths are forbidden.",
                actual=f"{windows_keys[key]} / {normalized}",
            )
        exact.add(normalized)
        windows_keys[key] = normalized

        if info.flag_bits & 0x1:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_encrypted_entry",
                "Encrypted ZIP entries are forbidden.",
                actual=normalized,
            )
        if _zip_entry_is_symlink(info):
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_symlink_entry",
                "Symlink ZIP entries are forbidden.",
                actual=normalized,
            )
        if info.compress_type not in RUNTIME_ALLOWED_COMPRESSION:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_compression_invalid",
                "Unsupported ZIP compression method.",
                actual=f"{normalized}: {info.compress_type}",
            )
        if info.is_dir():
            if not allow_nested:
                raise DeveloperTaskPythonRuntimeBundleError(
                    f"{label}_directory_entry",
                    "Outer runtime ZIP directories are forbidden.",
                    actual=normalized,
                )
            continue
        if info.file_size < 0 or info.file_size > max_entry_bytes:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_entry_size_invalid",
                "ZIP entry size is outside the accepted boundary.",
                actual=f"{normalized}: {info.file_size}",
            )
        if info.compress_size == 0 and info.file_size > 0:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_compression_ratio_invalid",
                "Compressed size is invalid.",
                actual=normalized,
            )
        if info.file_size > 1024 * 1024 and info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > MAX_RUNTIME_COMPRESSION_RATIO:
                raise DeveloperTaskPythonRuntimeBundleError(
                    f"{label}_compression_ratio_invalid",
                    "ZIP entry compression ratio exceeds the accepted boundary.",
                    actual=f"{normalized}: {ratio:.1f}",
                )
        total += info.file_size
        if total > max_total_bytes:
            raise DeveloperTaskPythonRuntimeBundleError(
                f"{label}_expanded_size_invalid",
                "Expanded ZIP size exceeds the accepted boundary.",
                actual=str(total),
            )
        files.append((normalized, info))

    return files, total


def _read_zip_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo, *, label: str) -> bytes:
    try:
        data = archive.read(info)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_entry_read_failed",
            "ZIP entry could not be read.",
            actual=f"{info.filename}: {type(exc).__name__}: {exc}",
        ) from exc
    if len(data) != info.file_size:
        raise DeveloperTaskPythonRuntimeBundleError(
            f"{label}_entry_size_changed",
            "ZIP entry size changed while reading.",
            actual=info.filename,
        )
    return data


def _validate_forbidden_stdlib_path(path: str) -> None:
    approved = path == RUNTIME_APPROVED_STDLIB_PLACEHOLDER["path"]
    parts = [part.casefold() for part in PurePosixPath(path).parts]
    if not approved and any(part in RUNTIME_FORBIDDEN_COMPONENTS for part in parts):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_stdlib_forbidden_surface",
            "Forbidden package-management/runtime surface is present.",
            actual=path,
        )
    lower = path.casefold()
    if lower.endswith(".pth"):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_stdlib_arbitrary_pth",
            "Unexpected .pth entry is forbidden.",
            actual=path,
        )
    if lower.endswith(("sitecustomize.py", "sitecustomize.pyc")):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_stdlib_sitecustomize",
            "sitecustomize is forbidden.",
            actual=path,
        )
    if lower.endswith(("usercustomize.py", "usercustomize.pyc")):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_stdlib_usercustomize",
            "usercustomize is forbidden.",
            actual=path,
        )


def _validate_upstream_pth(data: bytes) -> None:
    if len(data) != RUNTIME_SOURCE_PTH_SIZE_BYTES or _sha256(data) != RUNTIME_SOURCE_PTH_SHA256:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_pth_mismatch",
            "Upstream python313._pth does not match the pinned source contract.",
        )
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_pth_utf8_invalid",
            "Upstream python313._pth is not strict UTF-8.",
        ) from exc

    active: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.casefold() == "import site":
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_source_pth_import_site",
                "Upstream python313._pth unexpectedly enables site.",
            )
        active.append(line)
    if active != ["python313.zip", "."]:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_pth_contract_mismatch",
            "Upstream python313._pth active paths changed.",
            actual=repr(active),
        )

    crlf_count = data.count(b"\r\n")
    bare_lf_count = data.count(b"\n") - crlf_count
    bare_cr_count = data.count(b"\r") - crlf_count
    normalized_lf = data.replace(b"\r\n", b"\n")
    if (
        crlf_count != RUNTIME_SOURCE_PTH_CRLF_COUNT
        or bare_lf_count
        or bare_cr_count
        or not data.endswith(b"\r\n")
        or len(normalized_lf) != RUNTIME_SOURCE_PTH_NORMALIZED_LF_SIZE_BYTES
        or _sha256(normalized_lf) != RUNTIME_SOURCE_PTH_NORMALIZED_LF_SHA256
    ):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_pth_line_endings_mismatch",
            "Upstream python313._pth line endings changed.",
        )


def _validate_stdlib_placeholder(data: bytes) -> None:
    expected = RUNTIME_APPROVED_STDLIB_PLACEHOLDER
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_stdlib_placeholder_mismatch",
            "Approved stdlib placeholder is not strict UTF-8.",
        ) from exc

    crlf_count = data.count(b"\r\n")
    bare_lf_count = data.count(b"\n") - crlf_count
    bare_cr_count = data.count(b"\r") - crlf_count
    normalized_lf = data.replace(b"\r\n", b"\n")
    actual = {
        "size_bytes": len(data),
        "sha256": _sha256(data),
        "strict_utf8": True,
        "crlf_count": crlf_count,
        "bare_lf_count": bare_lf_count,
        "bare_cr_count": bare_cr_count,
        "ends_with_crlf": data.endswith(b"\r\n"),
        "normalized_lf_size_bytes": len(normalized_lf),
        "normalized_lf_sha256": _sha256(normalized_lf),
    }
    for key, expected_value in expected.items():
        if key == "path":
            continue
        if actual.get(key) != expected_value:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_stdlib_placeholder_mismatch",
                "Approved stdlib placeholder does not match the pinned contract.",
                actual=json.dumps(actual, ensure_ascii=False, sort_keys=True),
            )


def _validate_stdlib_zip(data: bytes) -> str:
    if len(data) != RUNTIME_SOURCE_STDLIB_SIZE_BYTES or _sha256(data) != RUNTIME_SOURCE_STDLIB_SHA256:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_stdlib_zip_mismatch",
            "python313.zip does not match the pinned source contract.",
        )

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_stdlib_zip_invalid",
            "python313.zip is not a valid ZIP archive.",
        ) from exc

    with archive:
        files, total = _inspect_zip_infos(
            archive,
            label="runtime_stdlib_zip",
            max_entries=MAX_RUNTIME_STDLIB_ENTRIES,
            max_total_bytes=MAX_RUNTIME_STDLIB_TOTAL_BYTES,
            max_entry_bytes=MAX_RUNTIME_STDLIB_ENTRY_BYTES,
            allow_nested=True,
        )
        if len(files) != RUNTIME_SOURCE_STDLIB_ENTRY_COUNT or total != RUNTIME_SOURCE_STDLIB_TOTAL_BYTES:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_stdlib_measurement_mismatch",
                "python313.zip entry count or expanded size changed.",
                actual=f"entries={len(files)} total={total}",
            )

        names: set[str] = set()
        manifest: list[dict[str, Any]] = []
        placeholder_seen = False
        for path, info in files:
            _validate_forbidden_stdlib_path(path)
            entry_bytes = _read_zip_entry(archive, info, label="runtime_stdlib_zip")
            entry_sha256 = _sha256(entry_bytes)
            names.add(path)
            if path == RUNTIME_APPROVED_STDLIB_PLACEHOLDER["path"]:
                _validate_stdlib_placeholder(entry_bytes)
                placeholder_seen = True
            manifest.append(
                {
                    "path": path,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "compression": info.compress_type,
                    "sha256": entry_sha256,
                }
            )

        missing = sorted(set(RUNTIME_REQUIRED_STDLIB_FILES) - names)
        if missing:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_stdlib_required_files_missing",
                "Required stdlib entries are missing.",
                actual=", ".join(missing),
            )
        if not placeholder_seen:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_stdlib_placeholder_missing",
                "Pinned stdlib placeholder is missing.",
            )

        manifest.sort(key=lambda item: item["path"])
        manifest_sha256 = _sha256(_canonical_json_bytes(manifest))
        if manifest_sha256 != RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_stdlib_manifest_mismatch",
                "python313.zip manifest does not match the pinned measurement contract.",
                actual=manifest_sha256,
            )
        return manifest_sha256


def _pe_machine(data: bytes, *, path: str) -> int:
    if len(data) < 64 or data[:2] != b"MZ":
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_pe_invalid",
            "PE file has no MZ header.",
            actual=path,
        )
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if (
        pe_offset < 0x40
        or pe_offset + 6 > len(data)
        or data[pe_offset : pe_offset + 4] != b"PE\x00\x00"
    ):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_pe_invalid",
            "PE header is invalid.",
            actual=path,
        )
    return struct.unpack_from("<H", data, pe_offset + 4)[0]


def _verify_source_archive(source_bytes: bytes, policy: DeveloperTaskPythonRuntimePolicy) -> _SourceEvidence:
    if len(source_bytes) != RUNTIME_SOURCE_SIZE_BYTES or _sha256(source_bytes) != RUNTIME_SOURCE_SHA256:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_identity_mismatch",
            "Runtime source ZIP does not match the pinned official CPython archive.",
        )

    try:
        archive = zipfile.ZipFile(io.BytesIO(source_bytes))
    except zipfile.BadZipFile as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_zip_invalid",
            "Runtime source is not a valid ZIP archive.",
        ) from exc

    expected = {item.path: item for item in policy.source_files}
    with archive:
        files, total = _inspect_zip_infos(
            archive,
            label="runtime_source_zip",
            max_entries=MAX_RUNTIME_OUTER_ENTRIES,
            max_total_bytes=MAX_RUNTIME_OUTER_TOTAL_BYTES,
            max_entry_bytes=MAX_RUNTIME_OUTER_ENTRY_BYTES,
            allow_nested=False,
        )
        if len(files) != RUNTIME_SOURCE_OUTER_ENTRY_COUNT or total != RUNTIME_SOURCE_OUTER_TOTAL_BYTES:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_source_measurement_mismatch",
                "Outer runtime ZIP entry count or expanded size changed.",
                actual=f"entries={len(files)} total={total}",
            )

        actual_names = {path for path, _ in files}
        if actual_names != set(expected):
            missing = sorted(set(expected) - actual_names)
            extra = sorted(actual_names - set(expected))
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_source_file_set_mismatch",
                "Outer runtime ZIP file set changed.",
                actual=f"missing={missing}; extra={extra}",
            )

        manifest: list[dict[str, Any]] = []
        source_files: dict[str, bytes] = {}
        pe_count = 0
        for path, info in files:
            contract = expected[path]
            if (
                info.file_size != contract.size_bytes
                or info.compress_size != contract.compressed_size
                or info.compress_type != contract.compression
            ):
                raise DeveloperTaskPythonRuntimeBundleError(
                    "runtime_source_entry_metadata_mismatch",
                    "Outer runtime ZIP entry metadata changed.",
                    actual=path,
                )
            entry_bytes = _read_zip_entry(archive, info, label="runtime_source_zip")
            entry_sha256 = _sha256(entry_bytes)
            if entry_sha256 != contract.sha256:
                raise DeveloperTaskPythonRuntimeBundleError(
                    "runtime_source_entry_hash_mismatch",
                    "Outer runtime ZIP entry hash changed.",
                    actual=path,
                )
            source_files[path] = entry_bytes
            manifest.append(
                {
                    "path": path,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "compression": info.compress_type,
                    "sha256": entry_sha256,
                }
            )

            if PurePosixPath(path).suffix.casefold() in _PE_SUFFIXES:
                machine = _pe_machine(entry_bytes, path=path)
                if machine != _PE_MACHINE_AMD64:
                    raise DeveloperTaskPythonRuntimeBundleError(
                        "runtime_source_pe_architecture_mismatch",
                        "Runtime PE file is not AMD64.",
                        actual=f"{path}: 0x{machine:04x}",
                    )
                pe_count += 1

    manifest.sort(key=lambda item: item["path"])
    outer_manifest_sha256 = _sha256(_canonical_json_bytes(manifest))
    if outer_manifest_sha256 != RUNTIME_SOURCE_OUTER_MANIFEST_SHA256:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_outer_manifest_mismatch",
            "Outer runtime ZIP manifest does not match the pinned measurement contract.",
            actual=outer_manifest_sha256,
        )
    if pe_count != RUNTIME_SOURCE_PE_FILE_COUNT:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_pe_count_mismatch",
            "Runtime PE file count changed.",
            actual=str(pe_count),
        )
    if _sha256(source_files["python.exe"]) != RUNTIME_SOURCE_PYTHON_EXE_SHA256:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_python_executable_mismatch",
            "python.exe hash changed.",
        )
    if _sha256(source_files["python313.dll"]) != RUNTIME_SOURCE_PYTHON_DLL_SHA256:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_python_dll_mismatch",
            "python313.dll hash changed.",
        )

    _validate_upstream_pth(source_files["python313._pth"])
    stdlib_manifest_sha256 = _validate_stdlib_zip(source_files["python313.zip"])

    source_fingerprint_payload = {
        "schema_version": 1,
        "source_id": RUNTIME_SOURCE_ID,
        "source_kind": "cpython_windows_embeddable",
        "version": RUNTIME_SOURCE_VERSION,
        "architecture": RUNTIME_SOURCE_ARCHITECTURE,
        "source_sha256": RUNTIME_SOURCE_SHA256,
        "file_manifest_sha256": outer_manifest_sha256,
        "python313_pth_sha256": RUNTIME_SOURCE_PTH_SHA256,
        "stdlib_zip_sha256": RUNTIME_SOURCE_STDLIB_SHA256,
    }
    source_fingerprint = _sha256(_canonical_json_bytes(source_fingerprint_payload))
    if source_fingerprint != RUNTIME_SOURCE_FINGERPRINT:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_fingerprint_mismatch",
            "Runtime source fingerprint changed.",
            actual=source_fingerprint,
        )

    return _SourceEvidence(
        files=source_files,
        outer_manifest_sha256=outer_manifest_sha256,
        stdlib_manifest_sha256=stdlib_manifest_sha256,
    )


def _payload(kind: str, path: str, data: bytes) -> DeveloperTaskPythonRuntimeBundleFile:
    return DeveloperTaskPythonRuntimeBundleFile(
        path=path,
        kind=kind,
        size_bytes=len(data),
        sha256=_sha256(data),
        _bytes=data,
    )


def _build_runtime_manifest_bytes(
    payloads: tuple[DeveloperTaskPythonRuntimeBundleFile, ...],
    policy: DeveloperTaskPythonRuntimePolicy,
) -> bytes:
    payload = {
        "schema_version": _RUNTIME_MANIFEST_SCHEMA_VERSION,
        "bundle_id": RUNTIME_BUNDLE_ID,
        "source_id": RUNTIME_SOURCE_ID,
        "source_sha256": RUNTIME_SOURCE_SHA256,
        "source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
        "source_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
        "bundle_policy_fingerprint": policy.fingerprint,
        "launch_contract_fingerprint": runtime_launch_contract_fingerprint(),
        "payload_files": [item.to_dict() for item in payloads],
        "execution_authorized": False,
    }
    return _canonical_json_bytes(payload) + b"\n"


def _derive_payloads(
    source: _SourceEvidence,
    policy: DeveloperTaskPythonRuntimePolicy,
) -> tuple[DeveloperTaskPythonRuntimeBundleFile, ...]:
    payloads: list[DeveloperTaskPythonRuntimeBundleFile] = []
    for path in sorted(source.files):
        if path == RUNTIME_LOCKED_PTH_FILE_NAME:
            continue
        payloads.append(_payload("source", path, source.files[path]))

    payloads.extend(
        (
            _payload("locked_runtime_path", RUNTIME_LOCKED_PTH_FILE_NAME, RUNTIME_LOCKED_PTH_BYTES),
            _payload("trusted_probe", RUNTIME_PROBE_FILE_NAME, RUNTIME_PROBE_BYTES),
            _payload("trusted_runner", RUNTIME_RUNNER_FILE_NAME, RUNTIME_RUNNER_BYTES),
        )
    )
    payloads.sort(key=lambda item: item.path)

    runtime_manifest = _build_runtime_manifest_bytes(tuple(payloads), policy)
    if _sha256(runtime_manifest) != RUNTIME_MANIFEST_SHA256:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_manifest_fingerprint_mismatch",
            "Derived runtime_manifest.json changed unexpectedly.",
            actual=_sha256(runtime_manifest),
        )
    payloads.append(_payload("runtime_manifest", RUNTIME_MANIFEST_FILE_NAME, runtime_manifest))
    payloads.sort(key=lambda item: item.path)

    tree_manifest = [
        {
            "path": item.path,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
        }
        for item in payloads
    ]
    tree_manifest_sha256 = _sha256(_canonical_json_bytes(tree_manifest))
    total_bytes = sum(item.size_bytes for item in payloads)
    if (
        len(payloads) != RUNTIME_BUNDLE_FILE_COUNT
        or total_bytes != RUNTIME_BUNDLE_TOTAL_BYTES
        or tree_manifest_sha256 != RUNTIME_TREE_MANIFEST_SHA256
    ):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_layout_mismatch",
            "Derived runtime bundle layout changed unexpectedly.",
            actual=(
                f"files={len(payloads)} total={total_bytes} "
                f"tree={tree_manifest_sha256}"
            ),
        )
    return tuple(payloads)


def _write_exclusive_file(path: Path, data: bytes) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | int(getattr(os, "O_BINARY", 0))
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_output_exists",
            "Runtime bundle output file already exists.",
            actual=str(path),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_output_open_failed",
            "Runtime bundle output file could not be created.",
            actual=f"{path}: {type(exc).__name__}: {exc}",
        ) from exc

    try:
        total = 0
        while total < len(data):
            written = os.write(descriptor, data[total:])
            if written <= 0:
                raise DeveloperTaskPythonRuntimeBundleError(
                    "runtime_bundle_output_write_failed",
                    "Runtime bundle output write returned zero bytes.",
                    actual=str(path),
                )
            total += written
        os.fsync(descriptor)
    except DeveloperTaskPythonRuntimeBundleError:
        raise
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_output_write_failed",
            "Runtime bundle output file could not be written.",
            actual=f"{path}: {type(exc).__name__}: {exc}",
        ) from exc
    finally:
        os.close(descriptor)


def _create_staging_root(parent: Path) -> Path:
    token = secrets.token_hex(_RUNTIME_STAGING_TOKEN_BYTES)
    root = parent / f"{_RUNTIME_STAGING_PREFIX}{token}"
    try:
        os.mkdir(root, 0o700)
    except FileExistsError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_root_exists",
            "Fresh runtime bundle staging root already exists.",
            actual=str(root),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_root_create_failed",
            "Runtime bundle staging root could not be created.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    return root


def _scan_flat_regular_files(root: Path) -> tuple[str, ...]:
    try:
        root_metadata = os.lstat(root)
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_root_metadata_failed",
            "Runtime bundle staging root metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if not stat.S_ISDIR(root_metadata.st_mode) or _is_reparse_or_symlink(root_metadata):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_root_invalid",
            "Runtime bundle staging root must remain a regular directory.",
            actual=str(root),
        )

    names: list[str] = []
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_scan_failed",
            "Runtime bundle staging root could not be enumerated.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    for entry in entries:
        path = root / entry.name
        try:
            metadata = os.lstat(path)
        except OSError as exc:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_bundle_entry_metadata_failed",
                "Runtime bundle entry metadata could not be read.",
                actual=f"{entry.name}: {type(exc).__name__}: {exc}",
            ) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_bundle_non_regular_entry",
                "Runtime bundle staging root must contain only regular files.",
                actual=entry.name,
            )
        if _is_reparse_or_symlink(metadata):
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_bundle_reparse_point",
                "Runtime bundle staging entry must not be a reparse point.",
                actual=entry.name,
            )
        names.append(entry.name)
    return tuple(sorted(names))


def _verify_staging_tree(
    root: Path,
    expected: tuple[DeveloperTaskPythonRuntimeBundleFile, ...],
) -> tuple[DeveloperTaskPythonRuntimeBundleFile, ...]:
    expected_names = tuple(item.path for item in expected)
    if _scan_flat_regular_files(root) != expected_names:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_file_set_mismatch",
            "Runtime bundle staging file set does not match the canonical bundle.",
        )

    readback: list[DeveloperTaskPythonRuntimeBundleFile] = []
    for item in expected:
        data = _read_regular_file(
            root / item.path,
            max_bytes=max(item.size_bytes, 1),
            code_prefix="runtime_bundle_entry",
        )
        if data != item.exact_bytes():
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_bundle_post_write_mismatch",
                "Runtime bundle bytes changed after write.",
                actual=item.path,
            )
        readback.append(_payload(item.kind, item.path, data))

    if _scan_flat_regular_files(root) != expected_names:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_file_set_changed",
            "Runtime bundle staging file set changed during verification.",
        )
    return tuple(readback)


def _remove_file_with_retries(path: Path) -> None:
    last_error: OSError | None = None
    for attempt in range(len(_RUNTIME_CLEANUP_RETRY_DELAYS_SECONDS) + 1):
        try:
            os.unlink(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
            if attempt >= len(_RUNTIME_CLEANUP_RETRY_DELAYS_SECONDS):
                break
            time.sleep(_RUNTIME_CLEANUP_RETRY_DELAYS_SECONDS[attempt])
    assert last_error is not None
    raise last_error


def _cleanup_staging_root(root: Path) -> None:
    try:
        metadata = os.lstat(root)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_cleanup_failed",
            "Runtime bundle staging root metadata could not be read during cleanup.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISDIR(metadata.st_mode) or _is_reparse_or_symlink(metadata):
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_cleanup_failed",
            "Runtime bundle staging root changed type before cleanup.",
            actual=str(root),
        )

    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_cleanup_failed",
            "Runtime bundle staging root could not be enumerated during cleanup.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    for entry in entries:
        path = root / entry.name
        try:
            item_metadata = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_bundle_cleanup_failed",
                "Runtime bundle entry metadata could not be read during cleanup.",
                actual=f"{entry.name}: {type(exc).__name__}: {exc}",
            ) from exc
        if not stat.S_ISREG(item_metadata.st_mode) or _is_reparse_or_symlink(item_metadata):
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_bundle_cleanup_failed",
                "Runtime bundle cleanup refuses non-regular/reparse entries.",
                actual=entry.name,
            )
        try:
            _remove_file_with_retries(path)
        except OSError as exc:
            raise DeveloperTaskPythonRuntimeBundleError(
                "runtime_bundle_cleanup_failed",
                "Runtime bundle staging file could not be removed.",
                actual=f"{entry.name}: {type(exc).__name__}: {exc}",
            ) from exc

    try:
        os.rmdir(root)
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_cleanup_failed",
            "Runtime bundle staging root could not be removed.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc


def _stage_and_verify_payloads(
    parent: Path,
    payloads: tuple[DeveloperTaskPythonRuntimeBundleFile, ...],
) -> tuple[DeveloperTaskPythonRuntimeBundleFile, ...]:
    staging_root = _create_staging_root(parent)

    try:
        for item in payloads:
            _write_exclusive_file(staging_root / item.path, item.exact_bytes())
        readback = _verify_staging_tree(staging_root, payloads)
    except Exception as original:
        try:
            _cleanup_staging_root(staging_root)
        except DeveloperTaskPythonRuntimeBundleError as cleanup_error:
            raise cleanup_error from original
        raise

    _cleanup_staging_root(staging_root)
    try:
        os.lstat(staging_root)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_cleanup_failed",
            "Runtime bundle staging root absence could not be verified after cleanup.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    else:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_cleanup_failed",
            "Runtime bundle staging root still exists after cleanup.",
            actual=str(staging_root),
        )
    return readback


def _bundle_fingerprint(report: DeveloperTaskPythonRuntimeBundleReport) -> str:
    payload = {
        "schema_version": report.schema_version,
        "bundle_id": report.bundle_id,
        "source_id": report.source_id,
        "source_sha256": report.source_sha256,
        "source_fingerprint": report.source_fingerprint,
        "source_policy_fingerprint": report.source_policy_fingerprint,
        "bundle_policy_fingerprint": report.bundle_policy_fingerprint,
        "tree_manifest_sha256": report.tree_manifest_sha256,
        "runtime_manifest_sha256": report.runtime_manifest_sha256,
        "python_executable_sha256": report.python_executable_sha256,
        "python_dll_sha256": report.python_dll_sha256,
        "python_pth_sha256": report.python_pth_sha256,
        "stdlib_sha256": report.stdlib_sha256,
        "runtime_probe_sha256": report.runtime_probe_sha256,
        "runtime_runner_sha256": report.runtime_runner_sha256,
        "launch_contract_fingerprint": report.launch_contract_fingerprint,
        "execution_authorized": report.execution_authorized,
    }
    return _sha256(_canonical_json_bytes(payload))


def _build_report(
    source: _SourceEvidence,
    files: tuple[DeveloperTaskPythonRuntimeBundleFile, ...],
    policy: DeveloperTaskPythonRuntimePolicy,
) -> DeveloperTaskPythonRuntimeBundleReport:
    tree_manifest = [
        {
            "path": item.path,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
        }
        for item in files
    ]
    report = DeveloperTaskPythonRuntimeBundleReport(
        schema_version=_RUNTIME_BUNDLE_SCHEMA_VERSION,
        bundle_id=RUNTIME_BUNDLE_ID,
        source_id=RUNTIME_SOURCE_ID,
        source_version=RUNTIME_SOURCE_VERSION,
        source_architecture=RUNTIME_SOURCE_ARCHITECTURE,
        source_sha256=RUNTIME_SOURCE_SHA256,
        source_fingerprint=RUNTIME_SOURCE_FINGERPRINT,
        source_policy_fingerprint=RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
        bundle_policy_fingerprint=policy.fingerprint,
        source_entry_count=len(source.files),
        source_outer_manifest_sha256=source.outer_manifest_sha256,
        source_stdlib_manifest_sha256=source.stdlib_manifest_sha256,
        source_passthrough_file_count=RUNTIME_SOURCE_OUTER_ENTRY_COUNT - 1,
        project_owned_file_count=4,
        bundle_file_count=len(files),
        bundle_total_bytes=sum(item.size_bytes for item in files),
        tree_manifest_sha256=_sha256(_canonical_json_bytes(tree_manifest)),
        runtime_manifest_sha256=_sha256(
            next(item.exact_bytes() for item in files if item.path == RUNTIME_MANIFEST_FILE_NAME)
        ),
        python_executable_sha256=_sha256(
            next(item.exact_bytes() for item in files if item.path == "python.exe")
        ),
        python_dll_sha256=_sha256(
            next(item.exact_bytes() for item in files if item.path == "python313.dll")
        ),
        python_pth_sha256=_sha256(
            next(item.exact_bytes() for item in files if item.path == RUNTIME_LOCKED_PTH_FILE_NAME)
        ),
        stdlib_sha256=_sha256(
            next(item.exact_bytes() for item in files if item.path == "python313.zip")
        ),
        runtime_probe_sha256=_sha256(
            next(item.exact_bytes() for item in files if item.path == RUNTIME_PROBE_FILE_NAME)
        ),
        runtime_runner_sha256=_sha256(
            next(item.exact_bytes() for item in files if item.path == RUNTIME_RUNNER_FILE_NAME)
        ),
        launch_contract_fingerprint=runtime_launch_contract_fingerprint(),
        bundle_fingerprint="",
        post_write_regular_files_verified=True,
        post_write_reparse_points_absent=True,
        staging_cleaned=True,
        interpreter_executed=False,
        execution_authorized=False,
    )
    fingerprint = _bundle_fingerprint(report)
    report = replace(report, bundle_fingerprint=fingerprint)
    if fingerprint != RUNTIME_BUNDLE_FINGERPRINT or not report.ok:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_fingerprint_mismatch",
            "Runtime bundle fingerprint changed unexpectedly.",
            actual=fingerprint,
        )
    return report


def build_developer_task_execution_runtime_bundle(
    runtime_zip: Path,
    *,
    artifact_parent: Path,
) -> DeveloperTaskPythonRuntimeBundle:
    """Build, post-write verify, and erase a canonical in-memory trusted runtime capability."""

    if not isinstance(runtime_zip, Path):
        raise TypeError("runtime_zip must be pathlib.Path")
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")

    policy = TRUSTED_PYTHON_RUNTIME_POLICY_V1
    validate_trusted_python_runtime_policy(policy)
    if runtime_zip.name != RUNTIME_SOURCE_FILE_NAME:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_source_name_mismatch",
            "Runtime source ZIP filename does not match the pinned CPython source.",
            actual=runtime_zip.name,
        )

    parent = _validate_artifact_parent(artifact_parent)
    source_bytes = _read_regular_file(
        runtime_zip,
        max_bytes=MAX_RUNTIME_SOURCE_BYTES,
        code_prefix="runtime_source",
    )
    source = _verify_source_archive(source_bytes, policy)
    payloads = _derive_payloads(source, policy)
    readback = _stage_and_verify_payloads(parent, payloads)

    report = _build_report(source, readback, policy)
    bundle = DeveloperTaskPythonRuntimeBundle(report=report, _files=readback)
    if not bundle.ok:
        raise DeveloperTaskPythonRuntimeBundleError(
            "runtime_bundle_self_check_failed",
            "Trusted runtime bundle failed its canonical in-memory self-check.",
        )
    return bundle
