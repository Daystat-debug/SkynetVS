from __future__ import annotations

"""Trusted host-side Python compilation without imports or bytecode writes."""

import hashlib
import os
import stat

from dataclasses import dataclass
from pathlib import Path
from typing import Any


STATIC_PYTHON_MAX_FILE_BYTES = 2 * 1024 * 1024
STATIC_PYTHON_MAX_TOTAL_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class DeveloperTaskStaticPythonFileEvidence:
    """Immutable evidence for one compiled Python source file."""

    path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskStaticPythonEvidence:
    """Immutable compilation evidence for changed Python files."""

    compiled_files: tuple[DeveloperTaskStaticPythonFileEvidence, ...]
    deleted_files: tuple[str, ...]
    total_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiled_files": [item.to_dict() for item in self.compiled_files],
            "deleted_files": list(self.deleted_files),
            "total_bytes": self.total_bytes,
        }


class DeveloperTaskStaticPythonError(RuntimeError):
    """Structured trusted compilation failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: str = "",
        actual: str = "",
    ) -> None:
        self.code = code
        self.path = path
        self.actual = actual
        super().__init__(message)


def _is_reparse_or_symlink(value: os.stat_result) -> bool:
    file_attributes = int(getattr(value, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(value.st_mode) or bool(file_attributes & reparse_flag)


def _path_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        int(getattr(value, "st_dev", 0)),
        int(getattr(value, "st_ino", 0)),
        int(value.st_size),
        int(getattr(value, "st_mtime_ns", 0)),
    )


def _validate_relative_path(path: str) -> tuple[str, ...]:
    if not isinstance(path, str):
        raise TypeError("Python path must be a string")

    if not path or path != path.strip() or "\\" in path or path.startswith("/"):
        raise DeveloperTaskStaticPythonError(
            "static_python_path_invalid",
            "Python path must be a trimmed repository-relative POSIX path.",
            path=path,
        )

    parts = tuple(path.split("/"))

    if any(part in {"", ".", ".."} for part in parts):
        raise DeveloperTaskStaticPythonError(
            "static_python_path_invalid",
            "Python path contains an unsafe segment.",
            path=path,
        )

    return parts


def _validate_repository_root(root: Path) -> Path:
    absolute = Path(os.path.abspath(root))

    try:
        metadata = os.lstat(absolute)
    except FileNotFoundError as exc:
        raise DeveloperTaskStaticPythonError(
            "static_repository_missing",
            "Workspace repository root is missing.",
            actual=str(absolute),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskStaticPythonError(
            "static_repository_metadata_failed",
            "Workspace repository metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISDIR(metadata.st_mode) or _is_reparse_or_symlink(metadata):
        raise DeveloperTaskStaticPythonError(
            "static_repository_unsafe",
            "Workspace repository root must be a regular non-reparse directory.",
            actual=str(absolute),
        )

    return absolute


def _validate_parent_chain(root: Path, parts: tuple[str, ...], relative: str) -> Path:
    current = root

    for part in parts[:-1]:
        current = current / part

        try:
            metadata = os.lstat(current)
        except FileNotFoundError as exc:
            raise DeveloperTaskStaticPythonError(
                "static_python_path_missing",
                "A parent directory for a changed Python file is missing.",
                path=relative,
                actual=str(current),
            ) from exc
        except OSError as exc:
            raise DeveloperTaskStaticPythonError(
                "static_python_path_metadata_failed",
                "A parent directory for a changed Python file could not be inspected.",
                path=relative,
                actual=f"{type(exc).__name__}: {exc}",
            ) from exc

        if not stat.S_ISDIR(metadata.st_mode):
            raise DeveloperTaskStaticPythonError(
                "static_python_parent_not_directory",
                "A changed Python path traverses a non-directory entry.",
                path=relative,
                actual=str(current),
            )

        if _is_reparse_or_symlink(metadata):
            raise DeveloperTaskStaticPythonError(
                "static_python_reparse_point",
                "Changed Python files must not traverse symlinks, junctions, or reparse points.",
                path=relative,
                actual=str(current),
            )

    return root.joinpath(*parts)


def _read_regular_file(
    root: Path,
    relative: str,
    *,
    max_file_bytes: int,
) -> bytes:
    parts = _validate_relative_path(relative)
    path = _validate_parent_chain(root, parts, relative)

    try:
        before = os.lstat(path)
    except FileNotFoundError as exc:
        raise DeveloperTaskStaticPythonError(
            "static_python_file_missing",
            "Changed Python file is missing from the applied workspace.",
            path=relative,
        ) from exc
    except OSError as exc:
        raise DeveloperTaskStaticPythonError(
            "static_python_file_metadata_failed",
            "Changed Python file metadata could not be read.",
            path=relative,
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if _is_reparse_or_symlink(before):
        raise DeveloperTaskStaticPythonError(
            "static_python_reparse_point",
            "Changed Python input must not be a symlink or reparse point.",
            path=relative,
        )

    if not stat.S_ISREG(before.st_mode):
        raise DeveloperTaskStaticPythonError(
            "static_python_file_not_regular",
            "Changed Python input must be a regular file.",
            path=relative,
        )

    if before.st_size < 0 or before.st_size > max_file_bytes:
        raise DeveloperTaskStaticPythonError(
            "static_python_file_too_large",
            "Changed Python file exceeds the static compilation size limit.",
            path=relative,
            actual=str(before.st_size),
        )

    flags = os.O_RDONLY
    flags |= int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))

    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DeveloperTaskStaticPythonError(
            "static_python_file_open_failed",
            "Changed Python file could not be opened safely.",
            path=relative,
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    try:
        opened = os.fstat(descriptor)

        if _path_identity(before) != _path_identity(opened):
            raise DeveloperTaskStaticPythonError(
                "static_python_file_changed_during_read",
                "Changed Python file changed before it was read.",
                path=relative,
            )

        chunks: list[bytes] = []
        remaining = int(before.st_size)

        while remaining:
            try:
                chunk = os.read(descriptor, min(65536, remaining))
            except OSError as exc:
                raise DeveloperTaskStaticPythonError(
                    "static_python_file_read_failed",
                    "Changed Python file could not be read.",
                    path=relative,
                    actual=f"{type(exc).__name__}: {exc}",
                ) from exc

            if not chunk:
                raise DeveloperTaskStaticPythonError(
                    "static_python_file_changed_during_read",
                    "Changed Python file became shorter while it was read.",
                    path=relative,
                )

            chunks.append(chunk)
            remaining -= len(chunk)

        if os.read(descriptor, 1):
            raise DeveloperTaskStaticPythonError(
                "static_python_file_changed_during_read",
                "Changed Python file became larger while it was read.",
                path=relative,
            )

        after = os.fstat(descriptor)

        if _path_identity(opened) != _path_identity(after):
            raise DeveloperTaskStaticPythonError(
                "static_python_file_changed_during_read",
                "Changed Python file changed while it was read.",
                path=relative,
            )

        return b"".join(chunks)
    finally:
        os.close(descriptor)


def compile_changed_python_files(
    repository_root: Path,
    *,
    changed_files: tuple[str, ...],
    result_index_paths: tuple[str, ...],
    max_file_bytes: int = STATIC_PYTHON_MAX_FILE_BYTES,
    max_total_bytes: int = STATIC_PYTHON_MAX_TOTAL_BYTES,
) -> DeveloperTaskStaticPythonEvidence:
    """Compile changed Python bytes in memory without importing or writing `.pyc` files."""

    if not isinstance(repository_root, Path):
        raise TypeError("repository_root must be pathlib.Path")

    if not isinstance(changed_files, tuple) or not all(
        isinstance(path, str)
        for path in changed_files
    ):
        raise TypeError("changed_files must be tuple[str, ...]")

    if not isinstance(result_index_paths, tuple) or not all(
        isinstance(path, str)
        for path in result_index_paths
    ):
        raise TypeError("result_index_paths must be tuple[str, ...]")

    if (
        isinstance(max_file_bytes, bool)
        or not isinstance(max_file_bytes, int)
        or max_file_bytes <= 0
        or isinstance(max_total_bytes, bool)
        or not isinstance(max_total_bytes, int)
        or max_total_bytes <= 0
    ):
        raise ValueError("static Python size limits must be positive integers")

    root = _validate_repository_root(repository_root)
    result_paths = set(result_index_paths)
    python_paths = tuple(
        path
        for path in changed_files
        if path.casefold().endswith(".py")
    )
    deleted_files = tuple(
        path
        for path in python_paths
        if path not in result_paths
    )
    present_files = tuple(
        path
        for path in python_paths
        if path in result_paths
    )

    compiled: list[DeveloperTaskStaticPythonFileEvidence] = []
    total_bytes = 0

    for path in present_files:
        content = _read_regular_file(
            root,
            path,
            max_file_bytes=max_file_bytes,
        )
        total_bytes += len(content)

        if total_bytes > max_total_bytes:
            raise DeveloperTaskStaticPythonError(
                "static_python_total_too_large",
                "Changed Python inputs exceed the total static compilation size limit.",
                path=path,
                actual=str(total_bytes),
            )

        try:
            compile(
                content,
                path,
                "exec",
                flags=0,
                dont_inherit=True,
                optimize=0,
            )
        except SyntaxError as exc:
            location = ":".join(
                str(value)
                for value in (exc.lineno or 0, exc.offset or 0)
            )
            raise DeveloperTaskStaticPythonError(
                "static_python_syntax_error",
                "Changed Python file does not compile.",
                path=path,
                actual=f"{location}:{exc.msg}"[:500],
            ) from exc
        except (MemoryError, RecursionError, UnicodeError, ValueError) as exc:
            raise DeveloperTaskStaticPythonError(
                "static_python_compile_failed",
                "Changed Python file could not be compiled safely.",
                path=path,
                actual=f"{type(exc).__name__}: {exc}"[:500],
            ) from exc

        compiled.append(
            DeveloperTaskStaticPythonFileEvidence(
                path=path,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )

    return DeveloperTaskStaticPythonEvidence(
        compiled_files=tuple(compiled),
        deleted_files=deleted_files,
        total_bytes=total_bytes,
    )
