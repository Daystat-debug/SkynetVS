from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import subprocess
import tokenize

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from modules.developer.developer_task_execution_environment_inventory_policy import (
    DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY,
    DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID,
    DeveloperTaskExecutionEnvironmentInventoryPolicy,
    developer_task_execution_environment_inventory_policy_fingerprint,
    validate_developer_task_execution_environment_inventory_policy,
)
from modules.developer.developer_task_preflight import DeveloperTaskRepositoryPreflightReport


_HEX_OBJECT_RE = re.compile(r"^[0-9a-f]{40,64}$")
_WINDOWS_RESERVED_NAMES = frozenset({
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
})
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


@dataclass(frozen=True)
class DeveloperTaskExecutionEnvironmentInventoryIssue:
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
class DeveloperTaskExecutionEnvironmentFileEvidence:
    path: str
    git_mode: str
    git_object_id: str
    size_bytes: int
    sha256: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "git_mode": self.git_mode,
            "git_object_id": self.git_object_id,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionEnvironmentImportEvidence:
    root: str
    files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "files": list(self.files),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionEnvironmentProcessCallEvidence:
    path: str
    line: int
    call: str
    literal_args: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "call": self.call,
            "literal_args": list(self.literal_args),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionEnvironmentPipelineStepEvidence:
    flow: str
    index: int
    name: str
    python_args: tuple[str, ...]
    interactive: bool
    direct_host_sensitive: bool
    host_sensitive_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow": self.flow,
            "index": self.index,
            "name": self.name,
            "python_args": list(self.python_args),
            "interactive": self.interactive,
            "direct_host_sensitive": self.direct_host_sensitive,
            "host_sensitive_reasons": list(self.host_sensitive_reasons),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionEnvironmentHostSensitiveFileEvidence:
    path: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionEnvironmentInventoryReport:
    policy_id: str
    policy_fingerprint: str
    repository_root: str
    head_commit: str
    tracked_file_count: int
    tracked_python_file_count: int
    python_total_bytes: int
    python_tree_fingerprint: str
    dependency_files: tuple[DeveloperTaskExecutionEnvironmentFileEvidence, ...]
    import_roots: tuple[DeveloperTaskExecutionEnvironmentImportEvidence, ...]
    process_calls: tuple[DeveloperTaskExecutionEnvironmentProcessCallEvidence, ...]
    pipeline_flow_count: int
    pipeline_step_count: int
    pipeline_steps: tuple[DeveloperTaskExecutionEnvironmentPipelineStepEvidence, ...]
    host_sensitive_files: tuple[DeveloperTaskExecutionEnvironmentHostSensitiveFileEvidence, ...]
    inventory_fingerprint: str
    issues: tuple[DeveloperTaskExecutionEnvironmentInventoryIssue, ...]
    sandbox_launched: bool = False
    candidate_interpreter_executed: bool = False
    dependency_install_attempted: bool = False
    reusable_lease_issued: bool = False
    execution_authorized: bool = False

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "repository_root": self.repository_root,
            "head_commit": self.head_commit,
            "tracked_file_count": self.tracked_file_count,
            "tracked_python_file_count": self.tracked_python_file_count,
            "python_total_bytes": self.python_total_bytes,
            "python_tree_fingerprint": self.python_tree_fingerprint,
            "dependency_files": [item.to_dict() for item in self.dependency_files],
            "import_roots": [item.to_dict() for item in self.import_roots],
            "process_calls": [item.to_dict() for item in self.process_calls],
            "pipeline_flow_count": self.pipeline_flow_count,
            "pipeline_step_count": self.pipeline_step_count,
            "pipeline_steps": [item.to_dict() for item in self.pipeline_steps],
            "host_sensitive_files": [item.to_dict() for item in self.host_sensitive_files],
            "inventory_fingerprint": self.inventory_fingerprint,
            "issues": [item.to_dict() for item in self.issues],
            "sandbox_launched": self.sandbox_launched,
            "candidate_interpreter_executed": self.candidate_interpreter_executed,
            "dependency_install_attempted": self.dependency_install_attempted,
            "reusable_lease_issued": self.reusable_lease_issued,
            "execution_authorized": self.execution_authorized,
        }


@dataclass(frozen=True)
class _GitTreeEntry:
    mode: str
    object_type: str
    object_id: str
    size_bytes: int
    path: str


class _InventoryFailure(RuntimeError):
    def __init__(self, code: str, check: str, message: str, *, expected: str = "", actual: str = "") -> None:
        self.code = code
        self.check = check
        self.expected = expected
        self.actual = actual
        super().__init__(message)


class _InventoryContext:
    def __init__(self, repository_root: Path, head_commit: str) -> None:
        self.repository_root = repository_root
        self.head_commit = head_commit
        self.issues: list[DeveloperTaskExecutionEnvironmentInventoryIssue] = []

    def add_failure(self, failure: _InventoryFailure) -> None:
        self.issues.append(
            DeveloperTaskExecutionEnvironmentInventoryIssue(
                code=failure.code,
                check=failure.check,
                message=str(failure),
                expected=failure.expected,
                actual=failure.actual,
            )
        )


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_git_environment() -> dict[str, str]:
    env = dict(os.environ)
    for key in tuple(env):
        if key in _GIT_ENVIRONMENT_KEYS_TO_CLEAR or key.startswith(_GIT_ENVIRONMENT_PREFIXES_TO_CLEAR):
            env.pop(key, None)
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_PAGER"] = "cat"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _run_git(
    repository_root: Path,
    *args: str,
    input_bytes: bytes | None = None,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    timeout = (
        DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY.git_timeout_seconds
        if timeout_seconds is None
        else timeout_seconds
    )
    command = [
        "git",
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(repository_root),
        *args,
    ]
    try:
        return subprocess.run(
            command,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=_build_git_environment(),
            stdin=None if input_bytes is not None else subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise _InventoryFailure(
            "environment_inventory_git_timeout",
            "git",
            "Git inventory command timed out.",
            actual=" ".join(command[1:]),
        ) from exc
    except FileNotFoundError as exc:
        raise _InventoryFailure(
            "environment_inventory_git_unavailable",
            "git",
            "Git executable is unavailable.",
            actual=str(exc),
        ) from exc
    except OSError as exc:
        raise _InventoryFailure(
            "environment_inventory_git_failed",
            "git",
            "Git inventory command could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc


def _decode_git_text(result: subprocess.CompletedProcess[bytes], *, check: str) -> str:
    if result.returncode != 0:
        error = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        if len(error) > 500:
            error = error[:497] + "..."
        raise _InventoryFailure(
            "environment_inventory_git_command_failed",
            check,
            "Git inventory command failed.",
            actual=error,
        )
    try:
        return result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _InventoryFailure(
            "environment_inventory_git_output_invalid",
            check,
            "Git returned non-UTF-8 machine output.",
            actual=str(exc),
        ) from exc


def _require_current_head(repository_root: Path, expected_head: str, *, check: str) -> None:
    text = _decode_git_text(
        _run_git(repository_root, "rev-parse", "--verify", "HEAD^{commit}"),
        check=check,
    ).strip().casefold()
    if text != expected_head:
        raise _InventoryFailure(
            "environment_inventory_repository_changed",
            check,
            "Repository HEAD changed relative to the pinned repository report.",
            expected=expected_head,
            actual=text,
        )


def _validate_repository_report(
    repository_report: DeveloperTaskRepositoryPreflightReport,
    project_root: Path,
) -> tuple[Path, str]:
    if not isinstance(repository_report, DeveloperTaskRepositoryPreflightReport):
        raise TypeError("repository_report must be DeveloperTaskRepositoryPreflightReport")
    if not isinstance(project_root, Path):
        raise TypeError("project_root must be pathlib.Path")

    if not repository_report.ok:
        raise _InventoryFailure(
            "environment_inventory_repository_report_failed",
            "repository_report",
            "Repository preflight report is not successful.",
            actual=",".join(repository_report.issue_codes),
        )
    if repository_report.dirty_categories:
        raise _InventoryFailure(
            "environment_inventory_repository_report_invalid",
            "repository_report",
            "Successful repository report contains dirty-worktree evidence.",
            expected="no dirty categories",
            actual=",".join(repository_report.dirty_categories),
        )
    if not _HEX_OBJECT_RE.fullmatch(repository_report.head_commit):
        raise _InventoryFailure(
            "environment_inventory_repository_report_invalid",
            "repository_report",
            "Repository report contains an invalid HEAD commit identifier.",
            actual=repository_report.head_commit,
        )
    if repository_report.head_commit != repository_report.resolved_base_commit:
        raise _InventoryFailure(
            "environment_inventory_repository_report_invalid",
            "repository_report",
            "Repository report HEAD and resolved base commit differ.",
            expected=repository_report.head_commit,
            actual=repository_report.resolved_base_commit,
        )

    root = _absolute_path(project_root)
    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _InventoryFailure(
            "environment_inventory_project_root_invalid",
            "project_root",
            "Project root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if not resolved_root.is_dir():
        raise _InventoryFailure(
            "environment_inventory_project_root_invalid",
            "project_root",
            "Project root must be a directory.",
            actual=str(resolved_root),
        )

    try:
        report_project = Path(repository_report.project_root).resolve(strict=True)
        report_repository = Path(repository_report.repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _InventoryFailure(
            "environment_inventory_repository_report_invalid",
            "repository_report",
            "Repository report paths could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if _path_key(resolved_root) != _path_key(report_project) or _path_key(resolved_root) != _path_key(report_repository):
        raise _InventoryFailure(
            "environment_inventory_repository_root_mismatch",
            "repository_report",
            "Project root must match both repository paths in the pinned report.",
            expected=str(resolved_root),
            actual=f"project={report_project};repository={report_repository}",
        )

    return resolved_root, repository_report.head_commit


def _valid_repository_path(value: str) -> bool:
    if not value or "\\" in value or "\x00" in value or value.startswith("/") or ":" in value:
        return False
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        return False
    for part in pure.parts:
        trimmed = part.rstrip(" .")
        if trimmed != part or not trimmed:
            return False
        stem = trimmed.split(".", 1)[0].casefold()
        if stem in _WINDOWS_RESERVED_NAMES:
            return False
    return True


def _parse_git_tree(repository_root: Path, head_commit: str) -> tuple[_GitTreeEntry, ...]:
    result = _run_git(
        repository_root,
        "ls-tree",
        "-r",
        "-z",
        "-l",
        "--full-tree",
        head_commit,
    )
    if result.returncode != 0:
        _decode_git_text(result, check="git_tree")

    records = result.stdout.split(b"\x00")
    entries: list[_GitTreeEntry] = []
    seen_windows: dict[str, str] = {}

    for raw in records:
        if not raw:
            continue
        try:
            meta, path_bytes = raw.split(b"\t", 1)
            fields = meta.split()
            if len(fields) != 4:
                raise ValueError("unexpected metadata field count")
            mode = fields[0].decode("ascii")
            object_type = fields[1].decode("ascii")
            object_id = fields[2].decode("ascii").casefold()
            size_text = fields[3].decode("ascii")
            path = path_bytes.decode("utf-8", errors="strict")
            size_bytes = -1 if size_text == "-" else int(size_text)
        except (ValueError, UnicodeDecodeError) as exc:
            raise _InventoryFailure(
                "environment_inventory_git_tree_invalid",
                "git_tree",
                "Git tree output is malformed.",
                actual=str(exc),
            ) from exc

        if not _HEX_OBJECT_RE.fullmatch(object_id) or size_bytes < -1 or not _valid_repository_path(path):
            raise _InventoryFailure(
                "environment_inventory_git_tree_invalid",
                "git_tree",
                "Git tree entry contains invalid identity, size, or path evidence.",
                actual=f"{mode} {object_type} {object_id} {size_text} {path}",
            )

        key = path.casefold()
        previous = seen_windows.get(key)
        if previous is not None and previous != path:
            raise _InventoryFailure(
                "environment_inventory_windows_path_collision",
                "git_tree",
                "Git tree contains a Windows case-insensitive path collision.",
                expected=previous,
                actual=path,
            )
        seen_windows[key] = path
        entries.append(_GitTreeEntry(mode, object_type, object_id, size_bytes, path))

    policy = DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY
    if len(entries) > policy.max_tracked_files:
        raise _InventoryFailure(
            "environment_inventory_tracked_file_limit_exceeded",
            "git_tree",
            "Tracked file count exceeds the inventory policy limit.",
            expected=str(policy.max_tracked_files),
            actual=str(len(entries)),
        )

    return tuple(entries)


def _dependency_kind(path: str, policy: DeveloperTaskExecutionEnvironmentInventoryPolicy) -> str:
    name = PurePosixPath(path).name.casefold()
    if name.startswith("requirements") and name.endswith(".txt"):
        return "requirements"
    if name.startswith("constraints") and name.endswith(".txt"):
        return "constraints"
    if name in policy.lock_file_names:
        return "lock"
    for suffix in policy.archive_suffixes:
        if name.endswith(suffix):
            return "package_archive"
    return ""


def _candidate_blob_entries(
    entries: tuple[_GitTreeEntry, ...],
    policy: DeveloperTaskExecutionEnvironmentInventoryPolicy,
) -> tuple[tuple[_GitTreeEntry, str], ...]:
    selected: list[tuple[_GitTreeEntry, str]] = []
    python_total = 0
    batch_total = 0

    for entry in entries:
        kind = "python" if entry.path.casefold().endswith(".py") else _dependency_kind(entry.path, policy)
        if not kind:
            continue
        if entry.object_type != "blob" or entry.mode not in policy.allowed_regular_modes or entry.size_bytes < 0:
            raise _InventoryFailure(
                "environment_inventory_candidate_not_regular",
                "git_tree",
                "Python and dependency inventory candidates must be regular Git blobs.",
                expected="regular blob mode 100644 or 100755",
                actual=f"{entry.path}:{entry.mode}:{entry.object_type}",
            )
        if kind == "python":
            if entry.size_bytes > policy.max_python_file_bytes:
                raise _InventoryFailure(
                    "environment_inventory_python_file_too_large",
                    "python_inventory",
                    "Tracked Python file exceeds the inventory size limit.",
                    expected=str(policy.max_python_file_bytes),
                    actual=f"{entry.path}:{entry.size_bytes}",
                )
            python_total += entry.size_bytes
            if python_total > policy.max_python_total_bytes:
                raise _InventoryFailure(
                    "environment_inventory_python_total_too_large",
                    "python_inventory",
                    "Tracked Python source total exceeds the inventory size limit.",
                    expected=str(policy.max_python_total_bytes),
                    actual=str(python_total),
                )
        elif entry.size_bytes > policy.max_dependency_file_bytes:
            raise _InventoryFailure(
                "environment_inventory_dependency_file_too_large",
                "dependency_inventory",
                "Tracked dependency metadata file exceeds the inventory size limit.",
                expected=str(policy.max_dependency_file_bytes),
                actual=f"{entry.path}:{entry.size_bytes}",
            )
        batch_total += entry.size_bytes
        if batch_total > policy.max_batch_bytes:
            raise _InventoryFailure(
                "environment_inventory_batch_too_large",
                "blob_inventory",
                "Exact Git blob inventory exceeds the batch size limit.",
                expected=str(policy.max_batch_bytes),
                actual=str(batch_total),
            )
        selected.append((entry, kind))

    return tuple(selected)


def _read_git_blobs(
    repository_root: Path,
    candidates: tuple[tuple[_GitTreeEntry, str], ...],
) -> dict[str, bytes]:
    if not candidates:
        return {}
    request = b"".join(entry.object_id.encode("ascii") + b"\n" for entry, _ in candidates)
    result = _run_git(repository_root, "cat-file", "--batch", input_bytes=request)
    if result.returncode != 0:
        _decode_git_text(result, check="git_cat_file")

    stream = io.BytesIO(result.stdout)
    payloads: dict[str, bytes] = {}
    for entry, _kind in candidates:
        header = stream.readline()
        try:
            header_text = header.rstrip(b"\n").decode("ascii")
            object_id, object_type, size_text = header_text.split(" ")
            size = int(size_text)
        except (ValueError, UnicodeDecodeError) as exc:
            raise _InventoryFailure(
                "environment_inventory_git_batch_invalid",
                "git_cat_file",
                "Git cat-file batch header is malformed.",
                actual=repr(header[:200]),
            ) from exc
        if object_id.casefold() != entry.object_id or object_type != "blob" or size != entry.size_bytes:
            raise _InventoryFailure(
                "environment_inventory_git_batch_mismatch",
                "git_cat_file",
                "Git cat-file output does not match pinned tree evidence.",
                expected=f"{entry.object_id} blob {entry.size_bytes}",
                actual=header_text,
            )
        data = stream.read(size)
        terminator = stream.read(1)
        if len(data) != size or terminator != b"\n":
            raise _InventoryFailure(
                "environment_inventory_git_batch_invalid",
                "git_cat_file",
                "Git cat-file batch payload is truncated or malformed.",
                actual=entry.path,
            )
        payloads[entry.path] = data
    if stream.read(1):
        raise _InventoryFailure(
            "environment_inventory_git_batch_invalid",
            "git_cat_file",
            "Git cat-file returned unexpected trailing bytes.",
        )
    return payloads


def _decode_python_source(path: str, data: bytes) -> str:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
        return data.decode(encoding, errors="strict")
    except (SyntaxError, UnicodeDecodeError, LookupError) as exc:
        raise _InventoryFailure(
            "environment_inventory_python_encoding_invalid",
            "python_inventory",
            "Tracked Python source encoding could not be decoded safely.",
            actual=f"{path}:{type(exc).__name__}:{exc}",
        ) from exc


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def _literal_json(node: ast.AST) -> str:
    try:
        value = ast.literal_eval(node)
    except Exception:
        value = None
    try:
        return _canonical_json(value)
    except (TypeError, ValueError):
        return "null"


def _analyze_python_sources(
    python_candidates: tuple[_GitTreeEntry, ...],
    payloads: dict[str, bytes],
    policy: DeveloperTaskExecutionEnvironmentInventoryPolicy,
) -> tuple[
    tuple[DeveloperTaskExecutionEnvironmentImportEvidence, ...],
    tuple[DeveloperTaskExecutionEnvironmentProcessCallEvidence, ...],
    tuple[DeveloperTaskExecutionEnvironmentHostSensitiveFileEvidence, ...],
    dict[str, ast.Module],
]:
    imports: dict[str, set[str]] = {}
    process_calls: list[DeveloperTaskExecutionEnvironmentProcessCallEvidence] = []
    host_sensitive: list[DeveloperTaskExecutionEnvironmentHostSensitiveFileEvidence] = []
    parsed: dict[str, ast.Module] = {}
    process_names = set(policy.process_calls)
    sensitive_roots = set(policy.host_sensitive_import_roots)

    for entry in python_candidates:
        data = payloads[entry.path]
        source = _decode_python_source(entry.path, data)
        try:
            tree = ast.parse(source, filename=entry.path)
        except (SyntaxError, ValueError, TypeError, MemoryError) as exc:
            raise _InventoryFailure(
                "environment_inventory_python_parse_failed",
                "python_inventory",
                "Tracked Python source could not be parsed into an AST.",
                actual=f"{entry.path}:{type(exc).__name__}:{exc}",
            ) from exc
        parsed[entry.path] = tree
        file_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_roots.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                file_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in process_names:
                    process_calls.append(
                        DeveloperTaskExecutionEnvironmentProcessCallEvidence(
                            path=entry.path,
                            line=int(getattr(node, "lineno", 0) or 0),
                            call=name,
                            literal_args=tuple(_literal_json(item) for item in node.args[:3]),
                        )
                    )
        for root in sorted(file_roots):
            imports.setdefault(root, set()).add(entry.path)

        reasons: list[str] = []
        for root in sorted(file_roots.intersection(sensitive_roots)):
            reasons.append(f"import:{root}")
        for marker in policy.host_sensitive_text_markers:
            if marker in source:
                reasons.append(f"text:{marker}")
        if reasons:
            host_sensitive.append(
                DeveloperTaskExecutionEnvironmentHostSensitiveFileEvidence(
                    path=entry.path,
                    reasons=tuple(sorted(set(reasons))),
                )
            )

    import_evidence = tuple(
        DeveloperTaskExecutionEnvironmentImportEvidence(root=root, files=tuple(sorted(files)))
        for root, files in sorted(imports.items())
    )
    return (
        import_evidence,
        tuple(sorted(process_calls, key=lambda item: (item.path, item.line, item.call, item.literal_args))),
        tuple(sorted(host_sensitive, key=lambda item: item.path)),
        parsed,
    )


def _literal_string(node: ast.AST, *, field: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise _InventoryFailure(
        "environment_inventory_pipeline_contract_invalid",
        "pipeline_inventory",
        f"Pipeline {field} must be a literal string.",
        actual=ast.dump(node, include_attributes=False)[:300],
    )


def _extract_pipeline_steps(
    pipeline_tree: ast.Module,
    host_sensitive_files: tuple[DeveloperTaskExecutionEnvironmentHostSensitiveFileEvidence, ...],
) -> tuple[DeveloperTaskExecutionEnvironmentPipelineStepEvidence, ...]:
    function = next(
        (
            node
            for node in pipeline_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "available_flows"
        ),
        None,
    )
    if not isinstance(function, ast.FunctionDef):
        raise _InventoryFailure(
            "environment_inventory_pipeline_contract_invalid",
            "pipeline_inventory",
            "tools/pipeline.py must define available_flows as a synchronous function.",
        )
    returns = [node for node in function.body if isinstance(node, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Dict):
        raise _InventoryFailure(
            "environment_inventory_pipeline_contract_invalid",
            "pipeline_inventory",
            "available_flows must return exactly one literal dictionary.",
        )

    sensitive_map = {item.path: item.reasons for item in host_sensitive_files}
    result: list[DeveloperTaskExecutionEnvironmentPipelineStepEvidence] = []
    flow_names: set[str] = set()
    mapping = returns[0].value

    for key_node, value_node in zip(mapping.keys, mapping.values):
        if key_node is None:
            raise _InventoryFailure(
                "environment_inventory_pipeline_contract_invalid",
                "pipeline_inventory",
                "Pipeline dictionary unpacking is forbidden in the canonical inventory.",
            )
        flow = _literal_string(key_node, field="flow name")
        if flow in flow_names or not flow:
            raise _InventoryFailure(
                "environment_inventory_pipeline_contract_invalid",
                "pipeline_inventory",
                "Pipeline flow names must be non-empty and unique.",
                actual=flow,
            )
        flow_names.add(flow)
        if not isinstance(value_node, ast.List):
            raise _InventoryFailure(
                "environment_inventory_pipeline_contract_invalid",
                "pipeline_inventory",
                "Each pipeline flow must be a literal Step list.",
                actual=flow,
            )
        for index, step_node in enumerate(value_node.elts):
            if not (
                isinstance(step_node, ast.Call)
                and isinstance(step_node.func, ast.Name)
                and step_node.func.id == "Step"
                and len(step_node.args) >= 2
            ):
                raise _InventoryFailure(
                    "environment_inventory_pipeline_contract_invalid",
                    "pipeline_inventory",
                    "Pipeline steps must be literal Step calls.",
                    actual=f"{flow}:{index}",
                )
            name = _literal_string(step_node.args[0], field="step name")
            command_node = step_node.args[1]
            if not (
                isinstance(command_node, ast.Call)
                and isinstance(command_node.func, ast.Name)
                and command_node.func.id == "_python_cmd"
            ):
                raise _InventoryFailure(
                    "environment_inventory_pipeline_contract_invalid",
                    "pipeline_inventory",
                    "Canonical pipeline inventory only accepts _python_cmd step commands.",
                    actual=f"{flow}:{index}:{name}",
                )
            python_args = tuple(_literal_string(item, field="python argument") for item in command_node.args)
            interactive = False
            for keyword in step_node.keywords:
                if keyword.arg != "interactive" or not (
                    isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, bool)
                ):
                    raise _InventoryFailure(
                        "environment_inventory_pipeline_contract_invalid",
                        "pipeline_inventory",
                        "Step keywords must be a literal interactive boolean only.",
                        actual=f"{flow}:{index}:{name}",
                    )
                interactive = bool(keyword.value.value)

            target = python_args[0] if python_args and python_args[0].endswith(".py") else ""
            reasons = sensitive_map.get(target, ())
            result.append(
                DeveloperTaskExecutionEnvironmentPipelineStepEvidence(
                    flow=flow,
                    index=index,
                    name=name,
                    python_args=python_args,
                    interactive=interactive,
                    direct_host_sensitive=bool(reasons),
                    host_sensitive_reasons=tuple(reasons),
                )
            )

    return tuple(result)


def _python_tree_fingerprint(
    python_candidates: tuple[_GitTreeEntry, ...],
    payloads: dict[str, bytes],
) -> str:
    rows = [
        {
            "path": entry.path,
            "git_mode": entry.mode,
            "git_object_id": entry.object_id,
            "size_bytes": entry.size_bytes,
            "sha256": _sha256(payloads[entry.path]),
        }
        for entry in python_candidates
    ]
    return _sha256(_canonical_json(rows).encode("utf-8"))


def _inventory_fingerprint_payload(report: DeveloperTaskExecutionEnvironmentInventoryReport) -> dict[str, Any]:
    return {
        "policy_id": report.policy_id,
        "policy_fingerprint": report.policy_fingerprint,
        "repository_root": report.repository_root,
        "head_commit": report.head_commit,
        "tracked_file_count": report.tracked_file_count,
        "tracked_python_file_count": report.tracked_python_file_count,
        "python_total_bytes": report.python_total_bytes,
        "python_tree_fingerprint": report.python_tree_fingerprint,
        "dependency_files": [item.to_dict() for item in report.dependency_files],
        "import_roots": [item.to_dict() for item in report.import_roots],
        "process_calls": [item.to_dict() for item in report.process_calls],
        "pipeline_flow_count": report.pipeline_flow_count,
        "pipeline_step_count": report.pipeline_step_count,
        "pipeline_steps": [item.to_dict() for item in report.pipeline_steps],
        "host_sensitive_files": [item.to_dict() for item in report.host_sensitive_files],
        "sandbox_launched": False,
        "candidate_interpreter_executed": False,
        "dependency_install_attempted": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }


def _build_report(
    *,
    repository_root: Path,
    head_commit: str,
    entries: tuple[_GitTreeEntry, ...] = (),
    python_candidates: tuple[_GitTreeEntry, ...] = (),
    payloads: dict[str, bytes] | None = None,
    dependency_files: tuple[DeveloperTaskExecutionEnvironmentFileEvidence, ...] = (),
    import_roots: tuple[DeveloperTaskExecutionEnvironmentImportEvidence, ...] = (),
    process_calls: tuple[DeveloperTaskExecutionEnvironmentProcessCallEvidence, ...] = (),
    pipeline_steps: tuple[DeveloperTaskExecutionEnvironmentPipelineStepEvidence, ...] = (),
    host_sensitive_files: tuple[DeveloperTaskExecutionEnvironmentHostSensitiveFileEvidence, ...] = (),
    issues: tuple[DeveloperTaskExecutionEnvironmentInventoryIssue, ...] = (),
) -> DeveloperTaskExecutionEnvironmentInventoryReport:
    payload_map = payloads or {}
    python_total = sum(entry.size_bytes for entry in python_candidates)
    python_fingerprint = (
        _python_tree_fingerprint(python_candidates, payload_map)
        if python_candidates and all(entry.path in payload_map for entry in python_candidates)
        else ""
    )
    flow_count = len({item.flow for item in pipeline_steps})
    provisional = DeveloperTaskExecutionEnvironmentInventoryReport(
        policy_id=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID,
        policy_fingerprint=developer_task_execution_environment_inventory_policy_fingerprint(),
        repository_root=str(repository_root),
        head_commit=head_commit,
        tracked_file_count=len(entries),
        tracked_python_file_count=len(python_candidates),
        python_total_bytes=python_total,
        python_tree_fingerprint=python_fingerprint,
        dependency_files=dependency_files,
        import_roots=import_roots,
        process_calls=process_calls,
        pipeline_flow_count=flow_count,
        pipeline_step_count=len(pipeline_steps),
        pipeline_steps=pipeline_steps,
        host_sensitive_files=host_sensitive_files,
        inventory_fingerprint="",
        issues=issues,
    )
    fingerprint = _sha256(_canonical_json(_inventory_fingerprint_payload(provisional)).encode("utf-8"))
    return DeveloperTaskExecutionEnvironmentInventoryReport(
        **{
            **provisional.__dict__,
            "inventory_fingerprint": fingerprint,
        }
    )


def inventory_developer_task_execution_environment(
    repository_report: DeveloperTaskRepositoryPreflightReport,
    *,
    project_root: Path,
) -> DeveloperTaskExecutionEnvironmentInventoryReport:
    policy_errors = validate_developer_task_execution_environment_inventory_policy()
    if policy_errors:
        raise RuntimeError(
            "Developer task execution environment inventory policy is invalid: "
            + ",".join(policy_errors)
        )

    repository_root = _absolute_path(project_root) if isinstance(project_root, Path) else Path(".")
    head_commit = ""
    context: _InventoryContext | None = None

    try:
        repository_root, head_commit = _validate_repository_report(repository_report, project_root)
        context = _InventoryContext(repository_root, head_commit)
        _require_current_head(repository_root, head_commit, check="head_before_inventory")
        entries = _parse_git_tree(repository_root, head_commit)
        policy = DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY
        candidates_with_kind = _candidate_blob_entries(entries, policy)
        payloads = _read_git_blobs(repository_root, candidates_with_kind)
        python_candidates = tuple(entry for entry, kind in candidates_with_kind if kind == "python")
        dependency_candidates = tuple((entry, kind) for entry, kind in candidates_with_kind if kind != "python")

        dependency_files = tuple(
            DeveloperTaskExecutionEnvironmentFileEvidence(
                path=entry.path,
                git_mode=entry.mode,
                git_object_id=entry.object_id,
                size_bytes=entry.size_bytes,
                sha256=_sha256(payloads[entry.path]),
                kind=kind,
            )
            for entry, kind in dependency_candidates
        )
        import_roots, process_calls, host_sensitive_files, parsed = _analyze_python_sources(
            python_candidates,
            payloads,
            policy,
        )
        pipeline_tree = parsed.get(policy.pipeline_path)
        if pipeline_tree is None:
            raise _InventoryFailure(
                "environment_inventory_pipeline_missing",
                "pipeline_inventory",
                "Canonical pipeline source is not present in the pinned Python tree.",
                expected=policy.pipeline_path,
            )
        pipeline_steps = _extract_pipeline_steps(pipeline_tree, host_sensitive_files)
        _require_current_head(repository_root, head_commit, check="head_after_inventory")
        return _build_report(
            repository_root=repository_root,
            head_commit=head_commit,
            entries=entries,
            python_candidates=python_candidates,
            payloads=payloads,
            dependency_files=dependency_files,
            import_roots=import_roots,
            process_calls=process_calls,
            pipeline_steps=pipeline_steps,
            host_sensitive_files=host_sensitive_files,
        )
    except _InventoryFailure as failure:
        if context is None:
            context = _InventoryContext(repository_root, head_commit)
        context.add_failure(failure)
        return _build_report(
            repository_root=context.repository_root,
            head_commit=context.head_commit,
            issues=tuple(context.issues),
        )
