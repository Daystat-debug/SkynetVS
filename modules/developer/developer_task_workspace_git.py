from __future__ import annotations

"""Git isolation primitives for independent developer-task repositories."""

import hashlib
import ntpath
import os
import re
import stat
import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_preflight import _build_git_environment


CLONE_TIMEOUT_SECONDS = 120.0
GIT_TIMEOUT_SECONDS = 15.0
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_RESERVED_RE = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$",
    re.IGNORECASE,
)
_MAX_PATH_LENGTH = 240
_MAX_SEGMENT_LENGTH = 120
_ALLOWED_BASELINE_MODES = frozenset({"100644", "100755"})
_TREE_ENTRY_RE = re.compile(
    rb"^([0-7]{6}) ([a-z]+) ([0-9a-f]{40,64})\t(.*)$",
    re.DOTALL,
)
_GIT_ENVIRONMENT_KEYS_TO_CLEAR = frozenset({
    "GIT_ALLOW_PROTOCOL",
    "GIT_ASKPASS",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_PROTOCOL_FROM_USER",
    "GIT_PROXY_COMMAND",
    "GIT_SSH",
    "GIT_SSH_COMMAND",
    "GIT_TEMPLATE_DIR",
    "GIT_TERMINAL_PROMPT",
    "SSH_ASKPASS",
})
_GIT_ENVIRONMENT_PREFIXES_TO_CLEAR = (
    "GIT_HTTP_",
    "GIT_CONFIG_KEY_",
    "GIT_CONFIG_VALUE_",
    "GIT_TRACE",
)


@dataclass(frozen=True)
class DeveloperTaskWorkspaceGitRequest:
    source_repository_root: str
    repository_root: str
    home_root: str
    xdg_root: str
    hooks_path: str
    template_root: str
    global_config_path: str
    base_commit: str


@dataclass(frozen=True)
class DeveloperTaskWorkspaceGitEvidence:
    git_dir: str
    head_commit: str
    detached_head: bool
    shallow_repository: bool
    clean_worktree: bool
    remote_names: tuple[str, ...]
    ref_names: tuple[str, ...]
    alternate_object_directories: tuple[str, ...]
    hooks_path: str
    source_repository_unchanged: bool


@dataclass(frozen=True)
class _GitBytesResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class _SourceSnapshot:
    head_commit: str
    status: bytes
    refs: bytes
    index_sha256: str
    config_sha256: str


class DeveloperTaskWorkspaceGitError(RuntimeError):
    def __init__(self, code: str, message: str, actual: str = "") -> None:
        self.code = code
        self.actual = actual
        super().__init__(message)


def _absolute_path(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path))).casefold()


def _is_reparse_or_symlink(value: os.stat_result) -> bool:
    file_attributes = int(getattr(value, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(value.st_mode) or bool(file_attributes & reparse_flag)


def _directory_is_safe(path: Path) -> bool:
    metadata = os.lstat(path)
    return stat.S_ISDIR(metadata.st_mode) and not _is_reparse_or_symlink(metadata)


def _compact_bytes_error(stderr: bytes, stdout: bytes) -> str:
    payload = stderr or stdout

    if not payload:
        return "Git command failed without output."

    value = payload.decode("utf-8", errors="replace").replace("\x00", "\\0").strip()
    value = " ".join(value.split())
    return value[:497] + "..." if len(value) > 500 else value


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return ""


def build_probe_environment() -> dict[str, str]:
    environment = _build_git_environment()

    for key in _GIT_ENVIRONMENT_KEYS_TO_CLEAR:
        environment.pop(key, None)

    for key in tuple(environment):
        if any(key.startswith(prefix) for prefix in _GIT_ENVIRONMENT_PREFIXES_TO_CLEAR):
            environment.pop(key, None)

    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PROTOCOL_FROM_USER": "0",
        "GIT_ALLOW_PROTOCOL": "file",
        "GCM_INTERACTIVE": "never",
        "LC_ALL": "C",
        "LANG": "C",
    })
    return environment


def _build_workspace_environment(request: DeveloperTaskWorkspaceGitRequest) -> dict[str, str]:
    environment = build_probe_environment()
    environment.update({
        "HOME": request.home_root,
        "USERPROFILE": request.home_root,
        "XDG_CONFIG_HOME": request.xdg_root,
        "GIT_CONFIG_GLOBAL": request.global_config_path,
        "GIT_TEMPLATE_DIR": request.template_root,
    })
    return environment


def _build_source_probe_environment() -> dict[str, str]:
    environment = _build_git_environment()
    environment.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "never",
        "LC_ALL": "C",
        "LANG": "C",
    })
    return environment


def _source_git_command_prefix() -> tuple[str, ...]:
    return (
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
    )


def _git_command_prefix(request: DeveloperTaskWorkspaceGitRequest) -> tuple[str, ...]:
    return (
        "-c",
        f"core.hooksPath={request.hooks_path}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.eol=lf",
        "-c",
        "core.safecrlf=true",
        "-c",
        "core.protectNTFS=true",
        "-c",
        "core.protectHFS=true",
        "-c",
        "maintenance.auto=false",
        "-c",
        "gc.auto=0",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.file.allow=always",
        "-c",
        "submodule.recurse=false",
        "-c",
        "fetch.recurseSubmodules=false",
    )


def _run_git_bytes(
    request: DeveloperTaskWorkspaceGitRequest,
    *args: str,
    cwd: Path | None = None,
    timeout_seconds: float = GIT_TIMEOUT_SECONDS,
) -> _GitBytesResult:
    command = ["git", *_git_command_prefix(request), *args]

    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            env=_build_workspace_environment(request),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_command_timeout",
            "Git command timed out.",
            actual=" ".join(command[:8]),
        ) from exc
    except FileNotFoundError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_unavailable",
            "Git executable is unavailable.",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_command_failed",
            "Git command could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    return _GitBytesResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _run_source_git_bytes(
    *args: str,
    timeout_seconds: float = GIT_TIMEOUT_SECONDS,
) -> _GitBytesResult:
    command = ["git", *_source_git_command_prefix(), *args]

    try:
        completed = subprocess.run(
            command,
            env=_build_source_probe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_command_timeout",
            "Git command timed out.",
            actual=" ".join(command[:8]),
        ) from exc
    except FileNotFoundError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_unavailable",
            "Git executable is unavailable.",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskWorkspaceGitError(
            "git_command_failed",
            "Git command could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    return _GitBytesResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _run_source_git_checked(
    *args: str,
    timeout_seconds: float = GIT_TIMEOUT_SECONDS,
    code: str = "git_command_failed",
    message: str = "Git command failed.",
) -> bytes:
    result = _run_source_git_bytes(
        *args,
        timeout_seconds=timeout_seconds,
    )

    if result.returncode:
        raise DeveloperTaskWorkspaceGitError(
            code,
            message,
            actual=_compact_bytes_error(result.stderr, result.stdout),
        )

    return result.stdout


def _run_git_checked(
    request: DeveloperTaskWorkspaceGitRequest,
    *args: str,
    cwd: Path | None = None,
    timeout_seconds: float = GIT_TIMEOUT_SECONDS,
    code: str = "git_command_failed",
    message: str = "Git command failed.",
) -> bytes:
    result = _run_git_bytes(
        request,
        *args,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )

    if result.returncode:
        raise DeveloperTaskWorkspaceGitError(
            code,
            message,
            actual=_compact_bytes_error(result.stderr, result.stdout),
        )

    return result.stdout


def _single_line(payload: bytes) -> str:
    try:
        value = payload.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("Git output is not valid UTF-8") from exc

    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("Git output is not one non-empty line")

    return value


def _decode_lines(payload: bytes) -> tuple[str, ...]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Git output is not valid UTF-8") from exc

    values = tuple(item.strip() for item in text.splitlines() if item.strip())

    if any("\x00" in item for item in values):
        raise ValueError("Git output contains a NUL byte")

    return values


def _decode_repository_path(raw: bytes) -> str:
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

        if part.casefold() == ".git":
            raise ValueError("Git path contains the reserved .git control segment")

        if part.endswith((" ", ".")):
            raise ValueError("Git path contains a Windows-unsafe segment")

        if any(char in '<>:"|?*' for char in part):
            raise ValueError("Git path contains a Windows-invalid character")

        if _WINDOWS_RESERVED_RE.fullmatch(part):
            raise ValueError("Git path contains a reserved Windows name")

    return value


def parse_baseline_tree(payload: bytes) -> tuple[str, ...]:
    if not payload:
        return ()

    records = payload.split(b"\x00")

    if records[-1] != b"":
        raise ValueError("Git tree output is not NUL terminated")

    paths: list[str] = []
    path_keys: dict[str, str] = {}
    directory_keys: dict[str, str] = {}

    for record in records[:-1]:
        match = _TREE_ENTRY_RE.fullmatch(record)

        if match is None:
            raise ValueError("Git tree entry is malformed")

        mode = match.group(1).decode("ascii")
        object_type = match.group(2).decode("ascii")
        path = _decode_repository_path(match.group(4))

        if mode == "120000":
            raise DeveloperTaskWorkspaceGitError(
                "workspace_baseline_symlink",
                "Baseline commit contains a symbolic link.",
                actual=path,
            )

        if mode == "160000" or object_type == "commit":
            raise DeveloperTaskWorkspaceGitError(
                "workspace_baseline_gitlink",
                "Baseline commit contains a gitlink or submodule.",
                actual=path,
            )

        if mode not in _ALLOWED_BASELINE_MODES or object_type != "blob":
            raise DeveloperTaskWorkspaceGitError(
                "workspace_baseline_mode_unsupported",
                "Baseline commit contains an unsupported Git entry.",
                actual=f"{mode} {object_type} {path}",
            )

        parts = path.split("/")

        for index in range(1, len(parts)):
            directory = "/".join(parts[:index])
            directory_key = ntpath.normcase(directory).casefold()
            previous_file = path_keys.get(directory_key)
            previous_directory = directory_keys.get(directory_key)

            if previous_file is not None:
                raise DeveloperTaskWorkspaceGitError(
                    "workspace_baseline_case_collision",
                    "Baseline commit contains a Windows file/directory path collision.",
                    actual=f"{previous_file}; {path}",
                )

            if previous_directory is not None and previous_directory != directory:
                raise DeveloperTaskWorkspaceGitError(
                    "workspace_baseline_case_collision",
                    "Baseline commit contains a Windows directory case collision.",
                    actual=f"{previous_directory}; {directory}",
                )

            directory_keys[directory_key] = directory

        key = ntpath.normcase(path).casefold()
        previous = path_keys.get(key)
        previous_directory = directory_keys.get(key)

        if previous is not None and previous != path:
            raise DeveloperTaskWorkspaceGitError(
                "workspace_baseline_case_collision",
                "Baseline commit contains a Windows case-insensitive path collision.",
                actual=f"{previous}; {path}",
            )

        if previous_directory is not None:
            raise DeveloperTaskWorkspaceGitError(
                "workspace_baseline_case_collision",
                "Baseline commit contains a Windows directory/file path collision.",
                actual=f"{previous_directory}; {path}",
            )

        path_keys[key] = path
        paths.append(path)

    return tuple(sorted(paths, key=lambda item: (ntpath.normcase(item).casefold(), item)))


def _snapshot_source(request: DeveloperTaskWorkspaceGitRequest) -> _SourceSnapshot:
    source = Path(request.source_repository_root)
    head = _single_line(_run_source_git_checked(
        "-C",
        str(source),
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
        code="source_repository_invalid",
        message="Source repository HEAD could not be resolved.",
    ))
    status = _run_source_git_checked(
        "-C",
        str(source),
        "status",
        "--porcelain=v2",
        "-z",
        "--no-branch",
        "--untracked-files=all",
        "--ignore-submodules=none",
        code="source_repository_invalid",
        message="Source repository status could not be read.",
    )
    refs = _run_source_git_checked(
        "-C",
        str(source),
        "for-each-ref",
        "--format=%(objectname) %(refname)",
        code="source_repository_invalid",
        message="Source repository refs could not be read.",
    )
    git_dir_value = _single_line(_run_source_git_checked(
        "-C",
        str(source),
        "rev-parse",
        "--absolute-git-dir",
        code="source_repository_invalid",
        message="Source repository Git directory could not be resolved.",
    ))
    common_dir_value = _single_line(_run_source_git_checked(
        "-C",
        str(source),
        "rev-parse",
        "--git-common-dir",
        code="source_repository_invalid",
        message="Source repository common Git directory could not be resolved.",
    ))
    git_dir = _absolute_path(git_dir_value)
    common_dir = _absolute_path(
        common_dir_value
        if os.path.isabs(common_dir_value)
        else source / common_dir_value
    )
    expected_git_dir = _absolute_path(source / ".git")

    if (
        _path_key(git_dir) != _path_key(common_dir)
        or _path_key(git_dir) != _path_key(expected_git_dir)
        or not _directory_is_safe(git_dir)
    ):
        raise DeveloperTaskWorkspaceGitError(
            "source_repository_not_independent",
            "Source repository must be a main worktree with a regular .git directory.",
            actual=f"git_dir={git_dir}; common_dir={common_dir}",
        )

    return _SourceSnapshot(
        head_commit=head,
        status=status,
        refs=refs,
        index_sha256=_sha256_file(git_dir / "index"),
        config_sha256=_sha256_file(git_dir / "config"),
    )


def _clone_repository(request: DeveloperTaskWorkspaceGitRequest) -> None:
    _run_git_checked(
        request,
        "clone",
        "--no-local",
        "--no-hardlinks",
        "--no-checkout",
        "--no-tags",
        "--single-branch",
        "--depth=1",
        "--",
        request.source_repository_root,
        request.repository_root,
        timeout_seconds=CLONE_TIMEOUT_SECONDS,
        code="workspace_clone_failed",
        message="Independent repository clone failed.",
    )


def _set_local_config(request: DeveloperTaskWorkspaceGitRequest) -> None:
    values = (
        ("core.hooksPath", request.hooks_path),
        ("core.fsmonitor", "false"),
        ("core.untrackedCache", "false"),
        ("core.autocrlf", "false"),
        ("core.eol", "lf"),
        ("core.safecrlf", "true"),
        ("core.protectNTFS", "true"),
        ("core.protectHFS", "true"),
        ("maintenance.auto", "false"),
        ("gc.auto", "0"),
        ("submodule.recurse", "false"),
        ("fetch.recurseSubmodules", "false"),
        ("protocol.allow", "never"),
        ("protocol.file.allow", "never"),
    )

    if os.name == "nt":
        values += (("core.longpaths", "true"),)

    for key, value in values:
        _run_git_checked(
            request,
            "-C",
            request.repository_root,
            "config",
            "--local",
            "--replace-all",
            key,
            value,
            code="workspace_configuration_failed",
            message=f"Workspace Git configuration failed for {key}.",
        )


def _remove_all_remotes(request: DeveloperTaskWorkspaceGitRequest) -> None:
    payload = _run_git_checked(
        request,
        "-C",
        request.repository_root,
        "remote",
        code="workspace_remote_cleanup_failed",
        message="Workspace remotes could not be listed.",
    )

    for remote in _decode_lines(payload):
        _run_git_checked(
            request,
            "-C",
            request.repository_root,
            "remote",
            "remove",
            remote,
            code="workspace_remote_cleanup_failed",
            message=f"Workspace remote could not be removed: {remote}.",
        )


def _delete_all_refs(request: DeveloperTaskWorkspaceGitRequest) -> None:
    payload = _run_git_checked(
        request,
        "-C",
        request.repository_root,
        "for-each-ref",
        "--format=%(refname)",
        code="workspace_refs_cleanup_failed",
        message="Workspace refs could not be listed.",
    )

    for ref_name in _decode_lines(payload):
        _run_git_checked(
            request,
            "-C",
            request.repository_root,
            "update-ref",
            "-d",
            ref_name,
            code="workspace_refs_cleanup_failed",
            message=f"Workspace ref could not be removed: {ref_name}.",
        )


def _prepare_repository(request: DeveloperTaskWorkspaceGitRequest) -> None:
    _set_local_config(request)
    _remove_all_remotes(request)
    tree = _run_git_checked(
        request,
        "-C",
        request.repository_root,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        request.base_commit,
        code="workspace_baseline_read_failed",
        message="Workspace baseline tree could not be read.",
    )
    parse_baseline_tree(tree)
    _run_git_checked(
        request,
        "-C",
        request.repository_root,
        "checkout",
        "--detach",
        "--force",
        request.base_commit,
        code="workspace_checkout_failed",
        message="Workspace baseline checkout failed.",
    )
    _delete_all_refs(request)


def _resolve_git_path(repository_root: Path, value: str) -> Path:
    path = Path(value)
    return _absolute_path(path if path.is_absolute() else repository_root / path)


def _read_alternates(git_dir: Path) -> tuple[str, ...]:
    values: list[str] = []

    for name in ("alternates", "http-alternates"):
        path = git_dir / "objects" / "info" / name

        if not path.exists():
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"Could not read {name}: {exc}") from exc

        for line in content.splitlines():
            if line.strip():
                values.append(line.strip())

    return tuple(values)


def _verify_workspace(request: DeveloperTaskWorkspaceGitRequest) -> DeveloperTaskWorkspaceGitEvidence:
    repository = Path(request.repository_root)
    top_level = _absolute_path(_single_line(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "rev-parse",
        "--show-toplevel",
        code="workspace_repository_invalid",
        message="Workspace top-level directory could not be resolved.",
    )))
    git_dir = _resolve_git_path(repository, _single_line(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "rev-parse",
        "--git-dir",
        code="workspace_repository_invalid",
        message="Workspace Git directory could not be resolved.",
    )))
    common_dir = _resolve_git_path(repository, _single_line(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "rev-parse",
        "--git-common-dir",
        code="workspace_repository_invalid",
        message="Workspace common Git directory could not be resolved.",
    )))
    expected_git_dir = _absolute_path(repository / ".git")

    if (
        _path_key(top_level) != _path_key(repository)
        or _path_key(git_dir) != _path_key(expected_git_dir)
        or _path_key(common_dir) != _path_key(expected_git_dir)
        or not _directory_is_safe(git_dir)
    ):
        raise DeveloperTaskWorkspaceGitError(
            "workspace_repository_not_independent",
            "Workspace must use one independent regular .git directory.",
            actual=f"top={top_level}; git_dir={git_dir}; common_dir={common_dir}",
        )

    head_commit = _single_line(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
        code="workspace_head_unresolved",
        message="Workspace HEAD could not be resolved.",
    ))
    symbolic = _run_git_bytes(
        request,
        "-C",
        request.repository_root,
        "symbolic-ref",
        "-q",
        "HEAD",
    )
    detached_head = symbolic.returncode == 1 and not symbolic.stdout
    shallow_value = _single_line(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "rev-parse",
        "--is-shallow-repository",
        code="workspace_history_check_failed",
        message="Workspace shallow-repository state could not be verified.",
    ))
    history_count = _single_line(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "rev-list",
        "--count",
        "HEAD",
        code="workspace_history_check_failed",
        message="Workspace history depth could not be verified.",
    ))
    shallow_repository = shallow_value == "true" and history_count == "1"
    status = _run_git_checked(
        request,
        "-C",
        request.repository_root,
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
        code="workspace_status_failed",
        message="Workspace status could not be read.",
    )
    remote_names = _decode_lines(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "remote",
        code="workspace_remote_check_failed",
        message="Workspace remotes could not be verified.",
    ))
    ref_names = _decode_lines(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "for-each-ref",
        "--format=%(refname)",
        code="workspace_ref_check_failed",
        message="Workspace refs could not be verified.",
    ))
    alternate_object_directories = _read_alternates(git_dir)
    hooks_path = _single_line(_run_git_checked(
        request,
        "-C",
        request.repository_root,
        "config",
        "--local",
        "--get",
        "core.hooksPath",
        code="workspace_hooks_check_failed",
        message="Workspace hooks path could not be verified.",
    ))

    if _path_key(hooks_path) != _path_key(request.hooks_path):
        raise DeveloperTaskWorkspaceGitError(
            "workspace_hooks_path_mismatch",
            "Workspace hooks path does not match the isolated hooks directory.",
            actual=hooks_path,
        )

    if head_commit != request.base_commit:
        raise DeveloperTaskWorkspaceGitError(
            "workspace_head_mismatch",
            "Workspace HEAD does not match the validated base commit.",
            actual=head_commit,
        )

    if not detached_head:
        raise DeveloperTaskWorkspaceGitError(
            "workspace_not_detached",
            "Workspace HEAD must be detached.",
        )

    if not shallow_repository:
        raise DeveloperTaskWorkspaceGitError(
            "workspace_history_not_minimal",
            "Workspace must contain only the shallow base-commit history boundary.",
            actual=f"shallow={shallow_value}; commit_count={history_count}",
        )

    if status:
        raise DeveloperTaskWorkspaceGitError(
            "workspace_dirty",
            "New workspace must be clean.",
        )

    if remote_names:
        raise DeveloperTaskWorkspaceGitError(
            "workspace_remote_present",
            "New workspace must not retain remotes.",
            actual=", ".join(remote_names),
        )

    if ref_names:
        raise DeveloperTaskWorkspaceGitError(
            "workspace_ref_present",
            "New workspace must not retain branch, remote, or tag refs.",
            actual=", ".join(ref_names),
        )

    if alternate_object_directories:
        raise DeveloperTaskWorkspaceGitError(
            "workspace_alternates_present",
            "New workspace must not share alternate object directories.",
            actual=", ".join(alternate_object_directories),
        )

    return DeveloperTaskWorkspaceGitEvidence(
        git_dir=str(git_dir),
        head_commit=head_commit,
        detached_head=detached_head,
        shallow_repository=shallow_repository,
        clean_worktree=True,
        remote_names=remote_names,
        ref_names=ref_names,
        alternate_object_directories=alternate_object_directories,
        hooks_path=hooks_path,
        source_repository_unchanged=False,
    )


def create_independent_git_workspace(
    request: DeveloperTaskWorkspaceGitRequest,
) -> DeveloperTaskWorkspaceGitEvidence:
    source_before = _snapshot_source(request)

    if source_before.head_commit != request.base_commit or source_before.status:
        status = (
            _compact_bytes_error(b"", source_before.status)
            if source_before.status
            else "clean"
        )
        raise DeveloperTaskWorkspaceGitError(
            "source_repository_stale",
            "Source repository changed after preflight.",
            actual=f"head={source_before.head_commit}; status={status}",
        )

    _clone_repository(request)
    _prepare_repository(request)
    evidence = _verify_workspace(request)
    source_after = _snapshot_source(request)
    unchanged = source_before == source_after

    if not unchanged:
        raise DeveloperTaskWorkspaceGitError(
            "source_repository_changed",
            "Source repository changed during workspace creation.",
        )

    return DeveloperTaskWorkspaceGitEvidence(
        git_dir=evidence.git_dir,
        head_commit=evidence.head_commit,
        detached_head=evidence.detached_head,
        shallow_repository=evidence.shallow_repository,
        clean_worktree=evidence.clean_worktree,
        remote_names=evidence.remote_names,
        ref_names=evidence.ref_names,
        alternate_object_directories=evidence.alternate_object_directories,
        hooks_path=evidence.hooks_path,
        source_repository_unchanged=True,
    )
