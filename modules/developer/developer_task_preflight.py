from __future__ import annotations

import os
import re
import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)


_GIT_TIMEOUT_SECONDS = 10.0
_COMMIT_ID_RE = re.compile(r"^[0-9a-f]{40,64}$")
_GIT_ENVIRONMENT_KEYS_TO_CLEAR = frozenset({
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_SYSTEM",
    "GIT_DIR",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_EXEC_PATH",
    "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_QUARANTINE_PATH",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_SUPER_PREFIX",
    "GIT_WORK_TREE",
})
_GIT_ENVIRONMENT_PREFIXES_TO_CLEAR = (
    "GIT_CONFIG_KEY_",
    "GIT_CONFIG_VALUE_",
    "GIT_TRACE",
)
_DIRTY_CATEGORY_ORDER = (
    "conflict",
    "staged",
    "unstaged",
    "untracked",
    "submodule",
    "other",
)


@dataclass(frozen=True)
class DeveloperTaskPreflightIssue:
    code: str
    check: str
    message: str
    expected: str = ""
    actual: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "check": self.check,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class DeveloperTaskRepositoryPreflightReport:
    manifest_fingerprint: str
    project_root: str
    repository_root: str
    head_commit: str
    resolved_base_commit: str
    dirty_categories: tuple[str, ...]
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest_fingerprint": self.manifest_fingerprint,
            "project_root": self.project_root,
            "repository_root": self.repository_root,
            "head_commit": self.head_commit,
            "resolved_base_commit": self.resolved_base_commit,
            "dirty_categories": list(self.dirty_categories),
            "issues": [item.to_dict() for item in self.issues],
        }


@dataclass(frozen=True)
class _GitResult:
    returncode: int
    stdout: str
    stderr: str


class _GitInvocationError(RuntimeError):
    def __init__(self, code: str, message: str, actual: str = "") -> None:
        self.code = code
        self.actual = actual
        super().__init__(message)


class _RepositoryPreflightContext:
    def __init__(self, manifest: DeveloperTaskManifest, project_root: Path) -> None:
        self.manifest = manifest
        self.project_root = _absolute_path(project_root)
        self.repository_root = ""
        self.head_commit = ""
        self.resolved_base_commit = ""
        self.dirty_categories: tuple[str, ...] = ()
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

    def report(self) -> DeveloperTaskRepositoryPreflightReport:
        return DeveloperTaskRepositoryPreflightReport(
            manifest_fingerprint=developer_task_manifest_fingerprint(self.manifest),
            project_root=str(self.project_root),
            repository_root=self.repository_root,
            head_commit=self.head_commit,
            resolved_base_commit=self.resolved_base_commit,
            dirty_categories=self.dirty_categories,
            issues=tuple(self.issues),
        )


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _compact_error(stderr: str, stdout: str) -> str:
    value = (stderr or stdout).strip().replace("\x00", "\\0")

    if len(value) > 500:
        return value[:497] + "..."

    return value


def _single_line_output(value: str) -> str:
    return value.rstrip("\r\n")


def _build_git_environment() -> dict[str, str]:
    env = dict(os.environ)

    for key in tuple(env):
        if (
            key in _GIT_ENVIRONMENT_KEYS_TO_CLEAR
            or key.startswith(_GIT_ENVIRONMENT_PREFIXES_TO_CLEAR)
        ):
            env.pop(key, None)

    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_PAGER"] = "cat"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _run_git(project_root: Path, *args: str) -> _GitResult:
    command = [
        "git",
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(project_root),
        *args,
    ]
    env = _build_git_environment()

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise _GitInvocationError(
            "git_command_timeout",
            "Git command timed out.",
            actual=" ".join(command[1:]),
        ) from exc
    except FileNotFoundError as exc:
        raise _GitInvocationError(
            "git_unavailable",
            "Git executable is unavailable.",
            actual=str(exc),
        ) from exc
    except OSError as exc:
        raise _GitInvocationError(
            "git_command_failed",
            "Git command could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    return _GitResult(
        returncode=int(completed.returncode),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _run_git_checked(
    context: _RepositoryPreflightContext,
    check: str,
    *args: str,
) -> _GitResult | None:
    try:
        return _run_git(context.project_root, *args)
    except _GitInvocationError as exc:
        context.add(
            exc.code,
            check,
            str(exc),
            actual=exc.actual,
        )
        return None


def _valid_commit_id(value: str) -> bool:
    return bool(_COMMIT_ID_RE.fullmatch(value))


def _dirty_categories(status: str) -> tuple[str, ...]:
    categories: set[str] = set()
    fields = status.split("\x00")
    index = 0

    while index < len(fields):
        record = fields[index]
        index += 1

        if not record:
            continue

        kind = record[0]

        if kind in {"#", "!"}:
            continue

        if kind == "?":
            categories.add("untracked")
            continue

        if kind == "u":
            categories.add("conflict")
            continue

        if kind not in {"1", "2"}:
            categories.add("other")
            continue

        parts = record.split(" ", 3)

        if len(parts) < 3:
            categories.add("other")
            continue

        xy = parts[1]
        submodule = parts[2]

        if len(xy) != 2:
            categories.add("other")
        else:
            if xy[0] != ".":
                categories.add("staged")

            if xy[1] != ".":
                categories.add("unstaged")

        if submodule != "N...":
            categories.add("submodule")

        if kind == "2" and index < len(fields):
            index += 1

    return tuple(
        category
        for category in _DIRTY_CATEGORY_ORDER
        if category in categories
    )


def _check_repository(context: _RepositoryPreflightContext) -> bool:
    if not context.project_root.exists():
        context.add(
            "project_root_missing",
            "project_root",
            "Project root does not exist.",
            actual=str(context.project_root),
        )
        return False

    if not context.project_root.is_dir():
        context.add(
            "project_root_not_directory",
            "project_root",
            "Project root must be a directory.",
            actual=str(context.project_root),
        )
        return False

    try:
        context.project_root = context.project_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        context.add(
            "project_root_unresolved",
            "project_root",
            "Project root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    result = _run_git_checked(context, "repository", "rev-parse", "--git-dir")

    if result is None:
        return False

    if result.returncode != 0:
        context.add(
            "not_git_repository",
            "repository",
            "Project root is not inside a Git repository.",
            actual=_compact_error(result.stderr, result.stdout),
        )
        return False

    result = _run_git_checked(context, "repository", "rev-parse", "--is-bare-repository")

    if result is None:
        return False

    if result.returncode != 0:
        context.add(
            "git_command_failed",
            "repository",
            "Git could not determine whether the repository is bare.",
            actual=_compact_error(result.stderr, result.stdout),
        )
        return False

    bare_state = _single_line_output(result.stdout).casefold()

    if bare_state == "true":
        context.add(
            "bare_repository",
            "repository",
            "Bare repositories are not supported.",
            expected="false",
            actual="true",
        )
        return False

    if bare_state != "false":
        context.add(
            "git_output_invalid",
            "repository",
            "Git returned an invalid bare-repository state.",
            expected="true or false",
            actual=bare_state,
        )
        return False

    result = _run_git_checked(context, "repository", "rev-parse", "--is-inside-work-tree")

    if result is None:
        return False

    if result.returncode != 0:
        context.add(
            "git_command_failed",
            "repository",
            "Git could not determine the worktree state.",
            actual=_compact_error(result.stderr, result.stdout),
        )
        return False

    worktree_state = _single_line_output(result.stdout).casefold()

    if worktree_state != "true":
        context.add(
            "not_git_worktree",
            "repository",
            "Project root must belong to a non-bare Git worktree.",
            expected="true",
            actual=worktree_state,
        )
        return False

    result = _run_git_checked(context, "repository_root", "rev-parse", "--show-toplevel")

    if result is None:
        return False

    repository_root_text = _single_line_output(result.stdout)

    if result.returncode != 0 or not repository_root_text:
        context.add(
            "repository_root_unresolved",
            "repository_root",
            "Git repository root could not be resolved.",
            actual=_compact_error(result.stderr, result.stdout),
        )
        return False

    try:
        repository_root = Path(repository_root_text).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        context.add(
            "repository_root_unresolved",
            "repository_root",
            "Git repository root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        )
        return False

    context.repository_root = str(repository_root)

    if _path_key(repository_root) != _path_key(context.project_root):
        context.add(
            "repository_root_mismatch",
            "repository_root",
            "project_root must be the exact Git repository root.",
            expected=str(repository_root),
            actual=str(context.project_root),
        )
        return False

    return True


def _resolve_commit(
    context: _RepositoryPreflightContext,
    revision: str,
    *,
    check: str,
    issue_code: str,
) -> str:
    result = _run_git_checked(
        context,
        check,
        "rev-parse",
        "--verify",
        f"{revision}^{{commit}}",
    )

    if result is None:
        return ""

    value = _single_line_output(result.stdout).casefold()

    if result.returncode != 0:
        context.add(
            issue_code,
            check,
            "Git revision could not be resolved to a commit.",
            expected=revision,
            actual=_compact_error(result.stderr, result.stdout),
        )
        return ""

    if not _valid_commit_id(value):
        context.add(
            "git_output_invalid",
            check,
            "Git returned an invalid commit identifier.",
            expected="40 to 64 lowercase hexadecimal characters",
            actual=value,
        )
        return ""

    return value


def _check_commits(context: _RepositoryPreflightContext) -> None:
    context.head_commit = _resolve_commit(
        context,
        "HEAD",
        check="head_commit",
        issue_code="head_commit_unresolved",
    )
    context.resolved_base_commit = _resolve_commit(
        context,
        context.manifest.base_commit,
        check="base_commit",
        issue_code="base_commit_unresolved",
    )

    if (
        context.head_commit
        and context.resolved_base_commit
        and context.head_commit != context.resolved_base_commit
    ):
        context.add(
            "base_commit_mismatch",
            "base_commit",
            "Current HEAD does not match the task base commit.",
            expected=context.resolved_base_commit,
            actual=context.head_commit,
        )


def _check_clean_worktree(context: _RepositoryPreflightContext) -> None:
    result = _run_git_checked(
        context,
        "worktree_cleanliness",
        "status",
        "--porcelain=v2",
        "-z",
        "--no-branch",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )

    if result is None:
        return

    if result.returncode != 0:
        context.add(
            "git_command_failed",
            "worktree_cleanliness",
            "Git status failed.",
            actual=_compact_error(result.stderr, result.stdout),
        )
        return

    if result.stdout:
        context.dirty_categories = _dirty_categories(result.stdout)
        context.add(
            "dirty_worktree",
            "worktree_cleanliness",
            "Git index and worktree must be clean.",
            expected="clean",
            actual=",".join(context.dirty_categories) or "dirty",
        )


def run_developer_task_repository_preflight(
    manifest: DeveloperTaskManifest,
    *,
    project_root: Path,
) -> DeveloperTaskRepositoryPreflightReport:
    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(project_root, Path):
        raise TypeError("project_root must be pathlib.Path")

    context = _RepositoryPreflightContext(manifest, project_root)

    if not _check_repository(context):
        return context.report()

    _check_commits(context)
    _check_clean_worktree(context)
    return context.report()
