from __future__ import annotations

import hashlib
import os
import stat

from pathlib import Path

from modules.developer.developer_task_rehearsal_contract import (
    DeveloperTaskRehearsalArtifactLayout,
)
from modules.developer.developer_task_workspace_cleanup_fs import (
    DeveloperTaskWorkspaceCleanupFileSystemError,
    absolute_path,
    is_reparse_or_symlink,
    paths_overlap,
    validate_workspace_parent,
)


DTRB_RUN_PREFIX = "dtrb-"
DTRB_RESULT_FILE = "result.json"


class DeveloperTaskRehearsalFileSystemError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        self.code = code
        self.actual = actual
        super().__init__(message)


def _raise(code: str, message: str, *, actual: str = "") -> None:
    raise DeveloperTaskRehearsalFileSystemError(code, message, actual=actual)


def _safe_directory(path: Path, *, code: str) -> os.stat_result:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        _raise(code, "Directory metadata could not be read.", actual=f"{type(exc).__name__}: {exc}")

    if not stat.S_ISDIR(metadata.st_mode) or is_reparse_or_symlink(metadata):
        _raise(code, "Directory must be a regular non-reparse directory.", actual=str(path))

    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _raise(code, "Directory could not be resolved.", actual=f"{type(exc).__name__}: {exc}")

    if os.path.normcase(os.path.normpath(os.fspath(resolved))).casefold() != os.path.normcase(
        os.path.normpath(os.fspath(path))
    ).casefold():
        _raise(code, "Directory must resolve directly to itself.", actual=f"{path} -> {resolved}")

    return metadata


def _inside_git_tree(path: Path) -> bool:
    current = path
    while True:
        candidate = current / ".git"
        try:
            os.lstat(candidate)
        except FileNotFoundError:
            pass
        except OSError as exc:
            _raise(
                "artifact_parent_git_probe_failed",
                "Could not inspect an ancestor for Git administration metadata.",
                actual=f"{candidate}: {type(exc).__name__}: {exc}",
            )
        else:
            return True

        if current.parent == current:
            return False
        current = current.parent


def validate_rehearsal_artifact_parent(
    artifact_parent: Path,
    *,
    project_root: Path,
) -> Path:
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")
    if not isinstance(project_root, Path):
        raise TypeError("project_root must be pathlib.Path")

    parent = absolute_path(artifact_parent)
    project = absolute_path(project_root)

    try:
        validate_workspace_parent(parent)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        _raise(exc.code, str(exc), actual=exc.actual)

    _safe_directory(parent, code="artifact_parent_invalid")

    if paths_overlap(parent, project):
        _raise(
            "artifact_parent_overlaps_repository",
            "Artifact parent must not overlap the source repository.",
            actual=str(parent),
        )

    if _inside_git_tree(parent):
        _raise(
            "artifact_parent_inside_git_repository",
            "Artifact parent must not be inside another Git repository.",
            actual=str(parent),
        )

    return parent


def create_rehearsal_artifact_layout(
    artifact_parent: Path,
    *,
    project_root: Path,
    run_id: str,
    patch_file: str,
) -> DeveloperTaskRehearsalArtifactLayout:
    parent = validate_rehearsal_artifact_parent(
        artifact_parent,
        project_root=project_root,
    )

    if type(run_id) is not str or len(run_id) != 32 or any(char not in "0123456789abcdef" for char in run_id):
        _raise("invalid_run_id", "run_id must be 32 lowercase hexadecimal characters.")

    if type(patch_file) is not str or not patch_file or Path(patch_file).name != patch_file:
        _raise("invalid_patch_file", "patch_file must be a simple basename.", actual=str(patch_file))

    run_root = parent / f"{DTRB_RUN_PREFIX}{run_id}"
    task_root = run_root / "task"
    workspace_parent = run_root / "workspaces"
    patch_path = task_root / patch_file
    result_path = run_root / DTRB_RESULT_FILE

    try:
        os.mkdir(run_root)
        os.mkdir(task_root)
        os.mkdir(workspace_parent)
    except FileExistsError as exc:
        _raise("artifact_path_exists", "Rehearsal artifact path already exists.", actual=str(exc.filename))
    except OSError as exc:
        _raise("artifact_create_failed", "Could not create rehearsal artifact directories.", actual=f"{type(exc).__name__}: {exc}")

    for path in (run_root, task_root, workspace_parent):
        _safe_directory(path, code="artifact_directory_invalid")

    return DeveloperTaskRehearsalArtifactLayout(
        run_id=run_id,
        artifact_root=str(run_root),
        task_root=str(task_root),
        workspace_parent=str(workspace_parent),
        patch_path=str(patch_path),
        result_path=str(result_path),
    )


def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_CLOEXEC", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))

    try:
        descriptor = os.open(os.fspath(path), flags, 0o600)
    except OSError as exc:
        _raise("artifact_file_create_failed", "Could not exclusively create artifact file.", actual=f"{path}: {type(exc).__name__}: {exc}")

    try:
        view = memoryview(payload)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                _raise("artifact_file_write_failed", "Artifact write made no forward progress.", actual=str(path))
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _verify_regular_file(path: Path, expected: bytes) -> None:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        _raise("artifact_file_verify_failed", "Artifact file metadata could not be read.", actual=f"{type(exc).__name__}: {exc}")

    if not stat.S_ISREG(metadata.st_mode) or is_reparse_or_symlink(metadata):
        _raise("artifact_file_invalid", "Artifact file must be a regular non-reparse file.", actual=str(path))

    try:
        actual = path.read_bytes()
    except OSError as exc:
        _raise("artifact_file_verify_failed", "Artifact file could not be read back.", actual=f"{type(exc).__name__}: {exc}")

    if actual != expected:
        _raise(
            "artifact_file_identity_mismatch",
            "Artifact bytes changed after materialization.",
            actual=f"expected_sha256={hashlib.sha256(expected).hexdigest()};actual_sha256={hashlib.sha256(actual).hexdigest()}",
        )


def materialize_rehearsal_patch(
    layout: DeveloperTaskRehearsalArtifactLayout,
    patch_bytes: bytes,
) -> dict[str, object]:
    if type(layout) is not DeveloperTaskRehearsalArtifactLayout:
        raise TypeError("layout must be DeveloperTaskRehearsalArtifactLayout")
    if type(patch_bytes) is not bytes or not patch_bytes:
        _raise("invalid_patch_bytes", "patch_bytes must be non-empty immutable bytes.")

    patch_path = Path(layout.patch_path)
    _write_exclusive(patch_path, patch_bytes)
    _verify_regular_file(patch_path, patch_bytes)

    return {
        "patch_path": str(patch_path),
        "patch_bytes": len(patch_bytes),
        "patch_sha256": hashlib.sha256(patch_bytes).hexdigest(),
        "materialized": True,
    }


def write_rehearsal_result(
    layout: DeveloperTaskRehearsalArtifactLayout,
    result_bytes: bytes,
) -> dict[str, object]:
    if type(layout) is not DeveloperTaskRehearsalArtifactLayout:
        raise TypeError("layout must be DeveloperTaskRehearsalArtifactLayout")
    if type(result_bytes) is not bytes or not result_bytes:
        _raise("invalid_result_bytes", "result_bytes must be non-empty immutable bytes.")

    result_path = Path(layout.result_path)
    _write_exclusive(result_path, result_bytes)
    _verify_regular_file(result_path, result_bytes)

    return {
        "result_path": str(result_path),
        "result_bytes": len(result_bytes),
        "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "recorded": True,
    }
