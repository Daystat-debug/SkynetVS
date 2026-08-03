from __future__ import annotations

"""Read-only source-repository snapshots for developer-task lifecycle audits."""

import hashlib
import os
import stat
import subprocess

from dataclasses import dataclass, field
from pathlib import Path

from modules.developer.developer_task_workspace_git import (
    GIT_TIMEOUT_SECONDS,
    DeveloperTaskWorkspaceGitError,
    build_probe_environment,
)


@dataclass(frozen=True)
class DeveloperTaskSourceRepositorySnapshot:
    """Immutable source Git evidence captured without optional locks."""

    repository_root: str
    head_commit: str
    status: bytes = field(repr=False)
    refs: bytes = field(repr=False)
    index_sha256: str
    config_sha256: str

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()

        for payload in (
            self.repository_root.encode("utf-8"),
            self.head_commit.encode("ascii"),
            self.status,
            self.refs,
            self.index_sha256.encode("ascii"),
            self.config_sha256.encode("ascii"),
        ):
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)

        return digest.hexdigest()

    @property
    def clean_worktree(self) -> bool:
        return not self.status


def _absolute_path(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path))).casefold()


def _same_path(first: Path | str, second: Path | str) -> bool:
    return _path_key(first) == _path_key(second)


def _is_reparse_or_symlink(value: os.stat_result) -> bool:
    file_attributes = int(getattr(value, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(value.st_mode) or bool(file_attributes & reparse_flag)


def _compact_git_error(stderr: bytes, stdout: bytes) -> str:
    payload = stderr or stdout

    if not payload:
        return "Git command failed without output."

    value = payload.decode("utf-8", errors="replace").replace("\x00", "\\0").strip()
    value = " ".join(value.split())
    return value[:497] + "..." if len(value) > 500 else value


def _run_source_git(root: Path, *args: str) -> bytes:
    command = [
        "git",
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(root),
        *args,
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
            "Source repository snapshot timed out.",
        ) from exc
    except FileNotFoundError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_unavailable",
            "Git executable is unavailable.",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_command_failed",
            "Source repository snapshot command could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if completed.returncode:
        raise DeveloperTaskWorkspaceGitError(
            "source_repository_snapshot_failed",
            "Source repository snapshot command failed.",
            actual=_compact_git_error(completed.stderr, completed.stdout),
        )

    return completed.stdout


def _single_line(payload: bytes) -> str:
    try:
        value = payload.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_output_invalid",
            "Git returned non-ASCII scalar output.",
        ) from exc

    if not value or "\n" in value or "\r" in value:
        raise DeveloperTaskWorkspaceGitError(
            "git_output_invalid",
            "Git returned an invalid scalar output.",
            actual=repr(value),
        )

    return value


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return ""


def snapshot_developer_task_source_repository(
    repository_root: Path,
) -> DeveloperTaskSourceRepositorySnapshot:
    """Capture source HEAD/status/refs/index/config without mutating Git state."""

    if not isinstance(repository_root, Path):
        raise TypeError("repository_root must be pathlib.Path")

    root = _absolute_path(repository_root)
    head = _single_line(_run_source_git(
        root,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
    ))
    status = _run_source_git(
        root,
        "status",
        "--porcelain=v2",
        "-z",
        "--no-branch",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    refs = _run_source_git(
        root,
        "for-each-ref",
        "--format=%(objectname) %(refname)",
    )
    git_dir_value = _single_line(_run_source_git(
        root,
        "rev-parse",
        "--absolute-git-dir",
    ))
    common_dir_value = _single_line(_run_source_git(
        root,
        "rev-parse",
        "--git-common-dir",
    ))
    git_dir = _absolute_path(git_dir_value)
    common_dir = _absolute_path(
        common_dir_value
        if os.path.isabs(common_dir_value)
        else root / common_dir_value
    )
    expected_git_dir = _absolute_path(root / ".git")

    try:
        git_dir_metadata = os.lstat(git_dir)
    except OSError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "source_repository_snapshot_failed",
            "Source repository Git directory metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if (
        not _same_path(git_dir, common_dir)
        or not _same_path(git_dir, expected_git_dir)
        or not stat.S_ISDIR(git_dir_metadata.st_mode)
        or _is_reparse_or_symlink(git_dir_metadata)
    ):
        raise DeveloperTaskWorkspaceGitError(
            "source_repository_not_independent",
            "Source repository must be a main worktree with a regular .git directory.",
            actual=f"git_dir={git_dir}; common_dir={common_dir}",
        )

    return DeveloperTaskSourceRepositorySnapshot(
        repository_root=str(root),
        head_commit=head,
        status=status,
        refs=refs,
        index_sha256=_sha256_file(git_dir / "index"),
        config_sha256=_sha256_file(git_dir / "config"),
    )
