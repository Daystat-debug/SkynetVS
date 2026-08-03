from __future__ import annotations

"""Hardened Git mutation boundary for verified developer-task patch application."""

import hashlib
import os
import re
import subprocess
import stat

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_patch_index import (
    DeveloperTaskPatchIndexChange,
    parse_developer_task_patch_changes,
    parse_developer_task_result_index_paths,
)
from modules.developer.developer_task_workspace_git import (
    GIT_TIMEOUT_SECONDS,
    DeveloperTaskWorkspaceGitRequest,
    build_workspace_git_environment,
    workspace_git_command_prefix,
)


_PATCH_APPLY_TIMEOUT_SECONDS = 30.0
_COMMIT_ID_RE = re.compile(r"^[0-9a-f]{40,64}$")
_TREE_ID_RE = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True)
class DeveloperTaskPatchApplyGitRequest:
    """Immutable inputs for one isolated workspace patch mutation."""

    workspace_git_request: DeveloperTaskWorkspaceGitRequest
    patch_bytes: bytes
    patch_sha256: str
    expected_changes: tuple[DeveloperTaskPatchIndexChange, ...]
    expected_result_index_paths: tuple[str, ...]


@dataclass(frozen=True)
class DeveloperTaskPatchApplyGitEvidence:
    """Verified staged Git state after exact patch application."""

    head_commit: str
    detached_head: bool
    shallow_repository: bool
    hooks_path: str
    remote_names: tuple[str, ...]
    ref_names: tuple[str, ...]
    alternate_object_directories: tuple[str, ...]
    changed_files: tuple[str, ...]
    changes: tuple[DeveloperTaskPatchIndexChange, ...]
    result_index_paths: tuple[str, ...]
    result_tree: str
    staged_diff_sha256: str
    workspace_config_sha256: str
    index_matches_worktree: bool
    staged_only: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "head_commit": self.head_commit,
            "detached_head": self.detached_head,
            "shallow_repository": self.shallow_repository,
            "hooks_path": self.hooks_path,
            "remote_names": list(self.remote_names),
            "ref_names": list(self.ref_names),
            "alternate_object_directories": list(self.alternate_object_directories),
            "changed_files": list(self.changed_files),
            "changes": [item.to_dict() for item in self.changes],
            "result_index_paths": list(self.result_index_paths),
            "result_tree": self.result_tree,
            "staged_diff_sha256": self.staged_diff_sha256,
            "workspace_config_sha256": self.workspace_config_sha256,
            "index_matches_worktree": self.index_matches_worktree,
            "staged_only": self.staged_only,
        }


@dataclass(frozen=True)
class DeveloperTaskPatchApplyRollbackResult:
    attempted: bool
    succeeded: bool
    workspace_clean: bool
    actual: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "workspace_clean": self.workspace_clean,
            "actual": self.actual,
        }


class DeveloperTaskPatchApplyGitError(RuntimeError):
    """Structured Git mutation failure, including rollback evidence."""

    def __init__(
        self,
        code: str,
        message: str,
        actual: str = "",
        *,
        mutation_started: bool = False,
        rollback_attempted: bool = False,
        rollback_succeeded: bool = False,
        workspace_clean: bool = False,
    ) -> None:
        self.code = code
        self.actual = actual
        self.mutation_started = mutation_started
        self.rollback_attempted = rollback_attempted
        self.rollback_succeeded = rollback_succeeded
        self.workspace_clean = workspace_clean
        super().__init__(message)


@dataclass(frozen=True)
class _GitResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class _RepositoryState:
    repository_root: str
    git_dir: str
    common_dir: str
    local_config_sha256: str
    head_commit: str
    detached_head: bool
    shallow_repository: bool
    hooks_path: str
    remote_names: tuple[str, ...]
    ref_names: tuple[str, ...]
    alternate_object_directories: tuple[str, ...]
    status: bytes
    index_tree: str
    base_tree: str
    index_matches_worktree: bool


class _ApplyFailure(RuntimeError):
    def __init__(self, code: str, message: str, actual: str = "") -> None:
        self.code = code
        self.actual = actual
        super().__init__(message)


def _path_key(value: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(value))).casefold()


def _absolute_git_path(value: str, repository_root: str) -> Path:
    path = Path(value)

    if not path.is_absolute():
        path = Path(repository_root) / path

    return Path(os.path.abspath(path))


def _compact_bytes_error(stderr: bytes, stdout: bytes) -> str:
    raw = stderr or stdout
    value = raw.decode("utf-8", errors="replace").strip().replace("\x00", "\\0")
    return value if len(value) <= 500 else value[:497] + "..."


def _single_line(payload: bytes) -> str:
    try:
        text = payload.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise _ApplyFailure(
            "workspace_git_output_invalid",
            "Git returned non-ASCII identifier output.",
        ) from exc

    if not text or "\n" in text or "\r" in text:
        raise _ApplyFailure(
            "workspace_git_output_invalid",
            "Git returned an invalid single-line result.",
            actual=repr(text),
        )

    return text


def _decode_lines(payload: bytes) -> tuple[str, ...]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _ApplyFailure(
            "workspace_git_output_invalid",
            "Git returned invalid UTF-8 line output.",
        ) from exc

    return tuple(item.strip() for item in text.splitlines() if item.strip())


def _run_git(
    request: DeveloperTaskWorkspaceGitRequest,
    *args: str,
    input_bytes: bytes | None = None,
    timeout_seconds: float = GIT_TIMEOUT_SECONDS,
) -> _GitResult:
    repository_root = os.path.abspath(request.repository_root)
    git_dir = os.path.join(repository_root, ".git")
    command = [
        "git",
        f"--git-dir={git_dir}",
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
            cwd=request.repository_root,
            env=build_workspace_git_environment(request),
            input=input_bytes,
            stdin=subprocess.DEVNULL if input_bytes is None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise _ApplyFailure(
            "git_command_timeout",
            "Git command timed out.",
            actual=" ".join(command[:10]),
        ) from exc
    except FileNotFoundError as exc:
        raise _ApplyFailure(
            "git_unavailable",
            "Git executable is unavailable.",
        ) from exc
    except OSError as exc:
        raise _ApplyFailure(
            "git_command_failed",
            "Git command could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    return _GitResult(
        returncode=int(completed.returncode),
        stdout=bytes(completed.stdout),
        stderr=bytes(completed.stderr),
    )


def _run_checked(
    request: DeveloperTaskWorkspaceGitRequest,
    *args: str,
    input_bytes: bytes | None = None,
    timeout_seconds: float = GIT_TIMEOUT_SECONDS,
    code: str = "git_command_failed",
    message: str = "Git command failed.",
) -> bytes:
    result = _run_git(
        request,
        *args,
        input_bytes=input_bytes,
        timeout_seconds=timeout_seconds,
    )

    if result.returncode:
        raise _ApplyFailure(
            code,
            message,
            actual=_compact_bytes_error(result.stderr, result.stdout),
        )

    return result.stdout


def _read_alternates(request: DeveloperTaskWorkspaceGitRequest) -> tuple[str, ...]:
    git_dir_raw = _run_checked(
        request,
        "rev-parse",
        "--absolute-git-dir",
        code="workspace_git_dir_unresolved",
        message="Workspace Git directory could not be resolved.",
    )
    git_dir = Path(_single_line(git_dir_raw))
    path = git_dir / "objects" / "info" / "alternates"

    try:
        payload = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ()
    except (OSError, UnicodeDecodeError) as exc:
        raise _ApplyFailure(
            "workspace_alternates_invalid",
            "Workspace alternate object directories could not be inspected.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    return tuple(item.strip() for item in payload.splitlines() if item.strip())


def _is_detached(request: DeveloperTaskWorkspaceGitRequest) -> bool:
    result = _run_git(request, "symbolic-ref", "-q", "HEAD")

    if result.returncode == 1:
        return True

    if result.returncode == 0:
        return False

    raise _ApplyFailure(
        "workspace_head_state_invalid",
        "Workspace HEAD state could not be determined.",
        actual=_compact_bytes_error(result.stderr, result.stdout),
    )


def _quiet_result(
    request: DeveloperTaskWorkspaceGitRequest,
    *args: str,
) -> bool:
    result = _run_git(request, *args)

    if result.returncode == 0:
        return True

    if result.returncode == 1:
        return False

    raise _ApplyFailure(
        "git_command_failed",
        "Git quiet comparison failed.",
        actual=_compact_bytes_error(result.stderr, result.stdout),
    )



def _is_reparse_or_symlink(value: os.stat_result) -> bool:
    file_attributes = int(getattr(value, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(value.st_mode) or bool(file_attributes & reparse_flag)


def _local_config_snapshot(
    request: DeveloperTaskWorkspaceGitRequest,
) -> tuple[tuple[tuple[str, str], ...], str]:
    config_path = Path(request.repository_root) / ".git" / "config"

    try:
        before_metadata = os.lstat(config_path)
        before_content = config_path.read_bytes()
    except (OSError, ValueError) as exc:
        raise _ApplyFailure(
            "workspace_configuration_invalid",
            "Workspace local Git configuration could not be read safely.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISREG(before_metadata.st_mode) or _is_reparse_or_symlink(before_metadata):
        raise _ApplyFailure(
            "workspace_configuration_invalid",
            "Workspace local Git configuration must be a regular non-reparse file.",
            actual=str(config_path),
        )

    payload = _run_checked(
        request,
        "config",
        "--file",
        str(config_path),
        "--null",
        "--list",
        "--no-includes",
        code="workspace_configuration_invalid",
        message="Workspace local Git configuration could not be parsed.",
    )

    entries: list[tuple[str, str]] = []

    for record in payload.split(b"\x00"):
        if not record:
            continue

        if b"\n" not in record:
            raise _ApplyFailure(
                "workspace_configuration_invalid",
                "Workspace local Git configuration output is malformed.",
            )

        raw_key, raw_value = record.split(b"\n", 1)

        try:
            key = raw_key.decode("ascii", errors="strict").strip().casefold()
            value = raw_value.decode("utf-8", errors="strict").strip()
        except UnicodeDecodeError as exc:
            raise _ApplyFailure(
                "workspace_configuration_invalid",
                "Workspace local Git configuration contains invalid text.",
            ) from exc

        if not key:
            raise _ApplyFailure(
                "workspace_configuration_invalid",
                "Workspace local Git configuration contains an empty key.",
            )

        entries.append((key, value))

    try:
        after_metadata = os.lstat(config_path)
        after_content = config_path.read_bytes()
    except OSError as exc:
        raise _ApplyFailure(
            "workspace_configuration_invalid",
            "Workspace local Git configuration changed while it was inspected.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    before_identity = (
        stat.S_IFMT(before_metadata.st_mode),
        int(getattr(before_metadata, "st_dev", 0)),
        int(getattr(before_metadata, "st_ino", 0)),
        int(before_metadata.st_size),
        int(getattr(before_metadata, "st_mtime_ns", 0)),
    )
    after_identity = (
        stat.S_IFMT(after_metadata.st_mode),
        int(getattr(after_metadata, "st_dev", 0)),
        int(getattr(after_metadata, "st_ino", 0)),
        int(after_metadata.st_size),
        int(getattr(after_metadata, "st_mtime_ns", 0)),
    )

    if before_identity != after_identity or before_content != after_content:
        raise _ApplyFailure(
            "workspace_configuration_invalid",
            "Workspace local Git configuration changed while it was inspected.",
        )

    return tuple(entries), hashlib.sha256(before_content).hexdigest()


def _validate_local_config(
    request: DeveloperTaskWorkspaceGitRequest,
    entries: tuple[tuple[str, str], ...],
) -> None:
    values: dict[str, list[str]] = {}

    for key, value in entries:
        values.setdefault(key, []).append(value)

        if (
            key.startswith(("include.", "includeif.", "filter.", "url.", "alias."))
            or key in {
                "core.worktree",
                "core.attributesfile",
                "core.sshcommand",
                "core.gitproxy",
                "core.editor",
                "core.pager",
                "diff.external",
                "credential.helper",
                "sequence.editor",
            }
            or key.endswith((".command", ".driver"))
        ):
            raise _ApplyFailure(
                "workspace_configuration_invalid",
                "Workspace local Git configuration contains a forbidden execution or redirection key.",
                actual=key,
            )

    expected = {
        "core.repositoryformatversion": "0",
        "core.bare": "false",
        "core.logallrefupdates": "true",
        "core.fsmonitor": "false",
        "core.untrackedcache": "false",
        "core.autocrlf": "false",
        "core.eol": "lf",
        "core.safecrlf": "true",
        "core.protectntfs": "true",
        "core.protecthfs": "true",
        "maintenance.auto": "false",
        "gc.auto": "0",
        "submodule.recurse": "false",
        "fetch.recursesubmodules": "false",
        "protocol.allow": "never",
        "protocol.file.allow": "never",
    }

    for key, expected_value in expected.items():
        actual_values = values.get(key, [])

        if len(actual_values) != 1 or actual_values[0].casefold() != expected_value:
            raise _ApplyFailure(
                "workspace_configuration_invalid",
                "Workspace local Git configuration no longer matches the isolated policy.",
                actual=f"{key}={actual_values}",
            )

    hooks_values = values.get("core.hookspath", [])

    if (
        len(hooks_values) != 1
        or _path_key(hooks_values[0]) != _path_key(request.hooks_path)
    ):
        raise _ApplyFailure(
            "workspace_configuration_invalid",
            "Workspace local Git hooks path no longer matches isolated workspace evidence.",
            actual=repr(hooks_values),
        )


def _repository_state(
    request: DeveloperTaskWorkspaceGitRequest,
) -> _RepositoryState:
    repository_root = _single_line(_run_checked(
        request,
        "rev-parse",
        "--show-toplevel",
        code="workspace_repository_layout_invalid",
        message="Workspace repository root could not be resolved.",
    ))
    git_dir_value = _single_line(_run_checked(
        request,
        "rev-parse",
        "--absolute-git-dir",
        code="workspace_repository_layout_invalid",
        message="Workspace Git directory could not be resolved.",
    ))
    common_dir_value = _single_line(_run_checked(
        request,
        "rev-parse",
        "--git-common-dir",
        code="workspace_repository_layout_invalid",
        message="Workspace common Git directory could not be resolved.",
    ))
    inside_worktree = _single_line(_run_checked(
        request,
        "rev-parse",
        "--is-inside-work-tree",
        code="workspace_repository_layout_invalid",
        message="Workspace worktree state could not be resolved.",
    )).casefold()
    bare_repository = _single_line(_run_checked(
        request,
        "rev-parse",
        "--is-bare-repository",
        code="workspace_repository_layout_invalid",
        message="Workspace bare-repository state could not be resolved.",
    )).casefold()

    expected_root = Path(os.path.abspath(request.repository_root))
    expected_git_dir = expected_root / ".git"
    git_dir = _absolute_git_path(git_dir_value, request.repository_root)
    common_dir = _absolute_git_path(common_dir_value, request.repository_root)

    if (
        _path_key(repository_root) != _path_key(expected_root)
        or _path_key(git_dir) != _path_key(expected_git_dir)
        or _path_key(common_dir) != _path_key(expected_git_dir)
        or inside_worktree != "true"
        or bare_repository != "false"
    ):
        raise _ApplyFailure(
            "workspace_repository_layout_invalid",
            "Workspace Git administration is no longer bound to the independent repository root.",
            actual=(
                f"root={repository_root};git_dir={git_dir};common_dir={common_dir};"
                f"inside={inside_worktree};bare={bare_repository}"
            )[:500],
        )

    config_entries, local_config_sha256 = _local_config_snapshot(request)
    _validate_local_config(request, config_entries)

    head_commit = _single_line(_run_checked(
        request,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
        code="workspace_head_unresolved",
        message="Workspace HEAD could not be resolved.",
    )).casefold()

    if not _COMMIT_ID_RE.fullmatch(head_commit):
        raise _ApplyFailure(
            "workspace_git_output_invalid",
            "Workspace HEAD is not a valid commit identifier.",
            actual=head_commit,
        )

    shallow_value = _single_line(_run_checked(
        request,
        "rev-parse",
        "--is-shallow-repository",
        code="workspace_shallow_state_unresolved",
        message="Workspace shallow state could not be resolved.",
    )).casefold()

    if shallow_value not in {"true", "false"}:
        raise _ApplyFailure(
            "workspace_git_output_invalid",
            "Workspace shallow state is invalid.",
            actual=shallow_value,
        )

    hooks_result = _run_git(request, "config", "--local", "--get", "core.hooksPath")

    if hooks_result.returncode not in {0, 1}:
        raise _ApplyFailure(
            "workspace_hooks_path_unresolved",
            "Workspace hooks path could not be resolved.",
            actual=_compact_bytes_error(hooks_result.stderr, hooks_result.stdout),
        )

    hooks_path = hooks_result.stdout.decode("utf-8", errors="replace").strip()
    remote_names = _decode_lines(_run_checked(
        request,
        "remote",
        code="workspace_remotes_unresolved",
        message="Workspace remotes could not be inspected.",
    ))
    ref_names = _decode_lines(_run_checked(
        request,
        "for-each-ref",
        "--format=%(refname)",
        code="workspace_refs_unresolved",
        message="Workspace refs could not be inspected.",
    ))
    status = _run_checked(
        request,
        "status",
        "--porcelain=v2",
        "-z",
        "--no-branch",
        "--untracked-files=all",
        "--ignore-submodules=none",
        code="workspace_status_failed",
        message="Workspace status could not be inspected.",
    )
    index_tree = _single_line(_run_checked(
        request,
        "write-tree",
        code="workspace_index_tree_failed",
        message="Workspace index tree could not be written.",
    )).casefold()
    base_tree = _single_line(_run_checked(
        request,
        "rev-parse",
        "--verify",
        f"{request.base_commit}^{{tree}}",
        code="workspace_base_tree_unresolved",
        message="Workspace base tree could not be resolved.",
    )).casefold()

    if not _TREE_ID_RE.fullmatch(index_tree) or not _TREE_ID_RE.fullmatch(base_tree):
        raise _ApplyFailure(
            "workspace_git_output_invalid",
            "Workspace tree identifier is invalid.",
            actual=f"index={index_tree};base={base_tree}",
        )

    return _RepositoryState(
        repository_root=str(expected_root),
        git_dir=str(git_dir),
        common_dir=str(common_dir),
        local_config_sha256=local_config_sha256,
        head_commit=head_commit,
        detached_head=_is_detached(request),
        shallow_repository=shallow_value == "true",
        hooks_path=hooks_path,
        remote_names=remote_names,
        ref_names=ref_names,
        alternate_object_directories=_read_alternates(request),
        status=status,
        index_tree=index_tree,
        base_tree=base_tree,
        index_matches_worktree=_quiet_result(request, "diff", "--quiet", "--"),
    )


def _validate_clean_baseline(
    request: DeveloperTaskWorkspaceGitRequest,
    state: _RepositoryState,
) -> None:
    expected_hooks = os.path.normcase(os.path.normpath(request.hooks_path)).casefold()
    actual_hooks = os.path.normcase(os.path.normpath(state.hooks_path)).casefold()

    if state.head_commit != request.base_commit:
        raise _ApplyFailure(
            "workspace_head_mismatch",
            "Workspace HEAD no longer matches the verified base commit.",
            actual=state.head_commit,
        )

    if not state.detached_head:
        raise _ApplyFailure(
            "workspace_head_not_detached",
            "Workspace HEAD must remain detached before patch application.",
        )

    if not state.shallow_repository:
        raise _ApplyFailure(
            "workspace_not_shallow",
            "Workspace must remain a shallow repository.",
        )

    if state.remote_names or state.ref_names or state.alternate_object_directories:
        raise _ApplyFailure(
            "workspace_repository_links_present",
            "Workspace must remain remote-free, ref-free, and alternate-free.",
            actual=(
                f"remotes={state.remote_names};refs={state.ref_names};"
                f"alternates={state.alternate_object_directories}"
            ),
        )

    if not state.hooks_path or actual_hooks != expected_hooks:
        raise _ApplyFailure(
            "workspace_hooks_path_mismatch",
            "Workspace hooks path no longer matches isolated workspace evidence.",
            actual=state.hooks_path,
        )

    if state.status or state.index_tree != state.base_tree or not state.index_matches_worktree:
        raise _ApplyFailure(
            "workspace_not_clean",
            "Workspace index and worktree must match the verified base tree before apply.",
            actual=(
                f"status_bytes={len(state.status)};"
                f"index_tree={state.index_tree};base_tree={state.base_tree};"
                f"index_matches_worktree={state.index_matches_worktree}"
            ),
        )


def _status_is_staged_only(payload: bytes) -> bool:
    fields = payload.split(b"\x00")
    index = 0
    saw_change = False

    while index < len(fields):
        record = fields[index]
        index += 1

        if not record:
            continue

        kind = record[:1]

        if kind in {b"#", b"!"}:
            continue

        if kind in {b"?", b"u"}:
            return False

        if kind not in {b"1", b"2"}:
            return False

        parts = record.split(b" ", 3)

        if len(parts) < 3:
            return False

        xy = parts[1]
        submodule = parts[2]

        if len(xy) != 2 or xy[:1] == b"." or xy[1:] != b"." or submodule != b"N...":
            return False

        saw_change = True

        if kind == b"2":
            if index >= len(fields) or not fields[index]:
                return False
            index += 1

    return saw_change


def _rollback_to_base(
    request: DeveloperTaskWorkspaceGitRequest,
) -> tuple[bool, bool, str]:
    errors: list[str] = []

    try:
        _repository_state(request)
    except _ApplyFailure as exc:
        return True, False, f"{exc.code}:{exc.actual or str(exc)}"[:500]

    for args in (
        ("reset", "--hard", "--quiet", "--no-recurse-submodules", request.base_commit),
        ("clean", "-ffd", "-x"),
    ):
        try:
            result = _run_git(request, *args, timeout_seconds=_PATCH_APPLY_TIMEOUT_SECONDS)
        except _ApplyFailure as exc:
            errors.append(f"{exc.code}:{exc.actual or str(exc)}")
            continue

        if result.returncode:
            errors.append(_compact_bytes_error(result.stderr, result.stdout))

    try:
        state = _repository_state(request)
        clean = (
            state.head_commit == request.base_commit
            and state.detached_head
            and not state.status
            and state.index_tree == state.base_tree
            and state.index_matches_worktree
            and not state.remote_names
            and not state.ref_names
            and not state.alternate_object_directories
        )
    except _ApplyFailure as exc:
        errors.append(f"{exc.code}:{exc.actual or str(exc)}")
        clean = False

    return True, clean and not errors, ";".join(item for item in errors if item)[:500]


def restore_independent_workspace_base(
    request: DeveloperTaskWorkspaceGitRequest,
) -> DeveloperTaskPatchApplyRollbackResult:
    """Restore a verified independent workspace to its clean base commit."""
    if not isinstance(request, DeveloperTaskWorkspaceGitRequest):
        raise TypeError("request must be DeveloperTaskWorkspaceGitRequest")

    attempted, succeeded, actual = _rollback_to_base(request)
    return DeveloperTaskPatchApplyRollbackResult(
        attempted=attempted,
        succeeded=succeeded,
        workspace_clean=succeeded,
        actual=actual,
    )


def _raise_with_rollback(
    request: DeveloperTaskWorkspaceGitRequest,
    failure: _ApplyFailure,
    *,
    mutation_started: bool,
) -> None:
    attempted = False
    succeeded = False
    workspace_clean = False
    rollback_actual = ""

    if mutation_started:
        attempted, succeeded, rollback_actual = _rollback_to_base(request)
        workspace_clean = succeeded

    if mutation_started and not succeeded:
        raise DeveloperTaskPatchApplyGitError(
            "workspace_patch_rollback_failed",
            "Workspace patch operation failed and the base state could not be restored.",
            actual=(
                f"cause={failure.code}:{failure.actual or str(failure)};"
                f"rollback={rollback_actual}"
            )[:500],
            mutation_started=True,
            rollback_attempted=attempted,
            rollback_succeeded=False,
            workspace_clean=False,
        ) from failure

    raise DeveloperTaskPatchApplyGitError(
        failure.code,
        str(failure),
        actual=failure.actual,
        mutation_started=mutation_started,
        rollback_attempted=attempted,
        rollback_succeeded=succeeded,
        workspace_clean=workspace_clean,
    ) from failure


def apply_patch_to_independent_workspace(
    request: DeveloperTaskPatchApplyGitRequest,
) -> DeveloperTaskPatchApplyGitEvidence:
    """Apply exact patch bytes to index and worktree, or restore the clean base state."""

    if not isinstance(request, DeveloperTaskPatchApplyGitRequest):
        raise TypeError("request must be DeveloperTaskPatchApplyGitRequest")

    if not isinstance(request.workspace_git_request, DeveloperTaskWorkspaceGitRequest):
        raise TypeError("workspace_git_request must be DeveloperTaskWorkspaceGitRequest")

    if not isinstance(request.patch_bytes, bytes):
        raise TypeError("patch_bytes must be bytes")

    actual_sha256 = hashlib.sha256(request.patch_bytes).hexdigest()

    if not request.patch_bytes or actual_sha256 != request.patch_sha256:
        raise DeveloperTaskPatchApplyGitError(
            "patch_snapshot_invalid",
            "Patch bytes do not match the verified patch SHA-256.",
            actual=actual_sha256,
        )

    git_request = request.workspace_git_request
    mutation_started = False

    try:
        baseline = _repository_state(git_request)
        _validate_clean_baseline(git_request, baseline)

        mutation_started = True
        apply_result = _run_git(
            git_request,
            "apply",
            "--index",
            "--allow-empty",
            "--whitespace=nowarn",
            "-",
            input_bytes=request.patch_bytes,
            timeout_seconds=_PATCH_APPLY_TIMEOUT_SECONDS,
        )

        if apply_result.returncode:
            raise _ApplyFailure(
                "workspace_patch_apply_failed",
                "Patch could not be applied to the independent workspace.",
                actual=_compact_bytes_error(apply_result.stderr, apply_result.stdout),
            )

        raw_diff = _run_checked(
            git_request,
            "diff",
            "--cached",
            "--raw",
            "-z",
            "--no-renames",
            "--no-abbrev",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=none",
            git_request.base_commit,
            "--",
            code="workspace_patch_diff_failed",
            message="Applied workspace diff could not be inspected.",
        )
        index_listing = _run_checked(
            git_request,
            "ls-files",
            "--stage",
            "-z",
            code="workspace_patch_index_failed",
            message="Applied workspace index could not be inspected.",
        )

        try:
            changes = parse_developer_task_patch_changes(raw_diff)
            result_index_paths = parse_developer_task_result_index_paths(index_listing)
        except (TypeError, ValueError) as exc:
            raise _ApplyFailure(
                "workspace_patch_facts_invalid",
                "Applied workspace Git facts are invalid.",
                actual=str(exc),
            ) from exc

        if changes != request.expected_changes:
            raise _ApplyFailure(
                "workspace_patch_facts_mismatch",
                "Applied workspace changes differ from preflight evidence.",
                actual=(
                    f"expected={[item.to_dict() for item in request.expected_changes]};"
                    f"actual={[item.to_dict() for item in changes]}"
                )[:500],
            )

        if result_index_paths != request.expected_result_index_paths:
            raise _ApplyFailure(
                "workspace_patch_index_paths_mismatch",
                "Applied workspace index differs from preflight evidence.",
                actual=(
                    f"expected={request.expected_result_index_paths};"
                    f"actual={result_index_paths}"
                )[:500],
            )

        status = _run_checked(
            git_request,
            "status",
            "--porcelain=v2",
            "-z",
            "--no-branch",
            "--untracked-files=all",
            "--ignore-submodules=none",
            code="workspace_status_failed",
            message="Applied workspace status could not be inspected.",
        )
        index_matches_worktree = _quiet_result(git_request, "diff", "--quiet", "--")
        staged_only = _status_is_staged_only(status)

        if not index_matches_worktree or not staged_only:
            raise _ApplyFailure(
                "workspace_patch_state_invalid",
                "Applied patch must leave only exact staged changes with no unstaged state.",
                actual=(
                    f"status_bytes={len(status)};"
                    f"index_matches_worktree={index_matches_worktree};"
                    f"staged_only={staged_only}"
                ),
            )

        post = _repository_state(git_request)

        if (
            post.repository_root != baseline.repository_root
            or post.git_dir != baseline.git_dir
            or post.common_dir != baseline.common_dir
            or post.local_config_sha256 != baseline.local_config_sha256
            or post.head_commit != baseline.head_commit
            or not post.detached_head
            or not post.shallow_repository
            or post.remote_names
            or post.ref_names
            or post.alternate_object_directories
            or os.path.normcase(os.path.normpath(post.hooks_path)).casefold()
            != os.path.normcase(os.path.normpath(git_request.hooks_path)).casefold()
        ):
            raise _ApplyFailure(
                "workspace_repository_state_changed",
                "Patch application changed protected workspace repository state.",
            )

        result_tree = post.index_tree
        staged_diff = _run_checked(
            git_request,
            "diff",
            "--cached",
            "--binary",
            "--full-index",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            git_request.base_commit,
            "--",
            code="workspace_staged_diff_failed",
            message="Applied staged diff could not be captured.",
        )
        staged_diff_sha256 = hashlib.sha256(staged_diff).hexdigest()

        return DeveloperTaskPatchApplyGitEvidence(
            head_commit=post.head_commit,
            detached_head=post.detached_head,
            shallow_repository=post.shallow_repository,
            hooks_path=post.hooks_path,
            remote_names=post.remote_names,
            ref_names=post.ref_names,
            alternate_object_directories=post.alternate_object_directories,
            changed_files=tuple(item.path for item in changes),
            changes=changes,
            result_index_paths=result_index_paths,
            result_tree=result_tree,
            staged_diff_sha256=staged_diff_sha256,
            workspace_config_sha256=post.local_config_sha256,
            index_matches_worktree=index_matches_worktree,
            staged_only=staged_only,
        )
    except _ApplyFailure as exc:
        _raise_with_rollback(
            git_request,
            exc,
            mutation_started=mutation_started,
        )

    raise AssertionError("unreachable")
