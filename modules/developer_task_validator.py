from __future__ import annotations

import re

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from modules.developer_task_contract import (
    DEVELOPER_CHECK_GIT_DIFF,
    DEVELOPER_CHECK_PIPELINE,
    DEVELOPER_CHECK_PY_COMPILE,
    DEVELOPER_CHECK_PYTHON_MODULE,
    DEVELOPER_TASK_ALLOWED_ORIGINS,
    DEVELOPER_TASK_INSTALL_MANUAL_CONFIRMATION,
    DEVELOPER_TASK_KIND_PATCH,
    DEVELOPER_TASK_PROJECT,
    DEVELOPER_TASK_SCHEMA_VERSION,
    DeveloperTaskCheck,
    DeveloperTaskManifest,
    DeveloperTaskValidationError,
    DeveloperTaskValidationIssue,
    DeveloperTaskValidationResult,
)


_MAX_ALLOWED_FILES = 20
_MAX_CHECKS = 10
_MAX_TITLE_LENGTH = 160
_MAX_SOURCE_REF_LENGTH = 200
_MAX_PATH_LENGTH = 240
_MAX_SEGMENT_LENGTH = 120

_TOP_LEVEL_FIELDS = {
    "schema_version",
    "task_kind",
    "task_id",
    "title",
    "project",
    "origin",
    "source_ref",
    "source_sha256",
    "base_commit",
    "patch_file",
    "patch_sha256",
    "allowed_files",
    "checks",
    "install_policy",
}

_TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BASE_COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")
_PATCH_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.patch$")
_PYTHON_MODULE_RE = re.compile(r"^tools\.eval_[a-z0-9_]+$")
_PIPELINE_FLOW_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_WINDOWS_RESERVED_RE = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$",
    re.IGNORECASE,
)

_FORBIDDEN_EXACT_PATHS = {
    ".env",
    ".gitignore",
    "data/reminders.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
}

_FORBIDDEN_PATH_PREFIXES = (
    ".git/",
    ".venv/",
    "venv/",
    "models/",
    "data/logs/",
    "data/developer_tasks/",
)

_PROTECTED_EXACT_PATHS = {
    "tools/pipeline.py",
    "tools/eval_runtime_architecture_audit.py",
    "tools/eval_audio_control_windows.py",
}

_PROTECTED_PATH_PREFIXES = (
    "modules/developer_",
    "tools/developer_",
    "tools/eval_developer_",
    "browser_extension/",
)

_FORBIDDEN_EXTENSIONS = {
    ".exe",
    ".dll",
    ".pyd",
    ".pyc",
    ".bat",
    ".cmd",
    ".ps1",
    ".msi",
    ".zip",
    ".7z",
    ".rar",
    ".com",
    ".scr",
}


class _ValidationContext:
    def __init__(self) -> None:
        self.issues: list[DeveloperTaskValidationIssue] = []

    def add(
        self,
        code: str,
        field: str,
        message: str,
    ) -> None:
        self.issues.append(
            DeveloperTaskValidationIssue(
                code=code,
                field=field,
                message=message,
            )
        )

    def read_string(
        self,
        payload: Mapping[str, Any],
        field: str,
        *,
        max_length: int | None = None,
    ) -> str:
        if field not in payload:
            return ""

        value = payload[field]

        if not isinstance(value, str):
            self.add("invalid_type", field, "Value must be a string.")
            return ""

        if not value or value != value.strip():
            self.add(
                "invalid_string",
                field,
                "Value must be non-empty and trimmed.",
            )

        if max_length is not None and len(value) > max_length:
            self.add(
                "too_long",
                field,
                f"Value must contain at most {max_length} characters.",
            )

        if _contains_control_character(value):
            self.add(
                "control_character",
                field,
                "Value must not contain control characters.",
            )

        return value.strip()


def _contains_control_character(value: str) -> bool:
    return any(
        ord(char) < 32 or ord(char) == 127
        for char in value
    )


def _validate_repository_path(
    value: Any,
    field: str,
    context: _ValidationContext,
) -> str:
    if not isinstance(value, str):
        context.add(
            "invalid_type",
            field,
            "Repository path must be a string.",
        )
        return ""

    if not value or value != value.strip():
        context.add(
            "invalid_path",
            field,
            "Repository path must be non-empty and trimmed.",
        )

    path = value.strip()

    if len(path) > _MAX_PATH_LENGTH:
        context.add(
            "path_too_long",
            field,
            f"Repository path must contain at most {_MAX_PATH_LENGTH} characters.",
        )

    if _contains_control_character(path):
        context.add(
            "control_character",
            field,
            "Repository path must not contain control characters.",
        )

    if "\\" in path:
        context.add(
            "backslash_path",
            field,
            "Repository path must use forward slashes.",
        )

    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        context.add(
            "absolute_path",
            field,
            "Repository path must be relative to the project root.",
        )

    parts = path.split("/")

    if any(part in {"", ".", ".."} for part in parts):
        context.add(
            "path_traversal",
            field,
            "Repository path must not contain empty, dot, or parent segments.",
        )

    for part in parts:
        if len(part) > _MAX_SEGMENT_LENGTH:
            context.add(
                "path_segment_too_long",
                field,
                f"Path segment must contain at most {_MAX_SEGMENT_LENGTH} characters.",
            )
            break

        if part.endswith((" ", ".")):
            context.add(
                "windows_unsafe_path",
                field,
                "Path segments must not end with a space or dot.",
            )
            break

        if any(char in '<>:"|?*' for char in part):
            context.add(
                "windows_unsafe_path",
                field,
                "Repository path contains a Windows-invalid character.",
            )
            break

        if _WINDOWS_RESERVED_RE.fullmatch(part):
            context.add(
                "windows_reserved_path",
                field,
                "Repository path contains a reserved Windows name.",
            )
            break

    normalized = "/".join(parts)
    normalized_lower = normalized.casefold()
    lower_parts = [
        part.casefold()
        for part in parts
    ]

    if "__pycache__" in lower_parts:
        context.add(
            "forbidden_path",
            field,
            "__pycache__ paths are forbidden.",
        )

    if (
        any(part.startswith(".") for part in lower_parts)
        and normalized_lower != ".env.example"
    ):
        context.add(
            "forbidden_hidden_path",
            field,
            "Hidden files and directories are forbidden.",
        )

    if (
        normalized_lower in _FORBIDDEN_EXACT_PATHS
        or any(
            normalized_lower.startswith(prefix)
            for prefix in _FORBIDDEN_PATH_PREFIXES
        )
    ):
        context.add(
            "forbidden_path",
            field,
            "Repository path is forbidden by policy.",
        )

    if (
        normalized_lower in _PROTECTED_EXACT_PATHS
        or any(
            normalized_lower.startswith(prefix)
            for prefix in _PROTECTED_PATH_PREFIXES
        )
    ):
        context.add(
            "protected_path",
            field,
            "Developer safety files are protected.",
        )

    if PurePosixPath(normalized).suffix.casefold() in _FORBIDDEN_EXTENSIONS:
        context.add(
            "forbidden_file_type",
            field,
            "Executable, archive, and script file types are forbidden.",
        )

    return normalized


def _read_check_string(
    payload: Mapping[str, Any],
    key: str,
    field: str,
    context: _ValidationContext,
) -> str:
    nested_field = f"{field}.{key}"

    if key not in payload:
        context.add(
            "missing_check_field",
            nested_field,
            "Check field is required.",
        )
        return ""

    value = payload[key]

    if not isinstance(value, str):
        context.add(
            "invalid_type",
            nested_field,
            "Check field must be a string.",
        )
        return ""

    if not value or value != value.strip():
        context.add(
            "invalid_string",
            nested_field,
            "Check field must be non-empty and trimmed.",
        )

    return value.strip()


def _validate_check(
    payload: Any,
    index: int,
    context: _ValidationContext,
) -> DeveloperTaskCheck | None:
    field = f"checks[{index}]"

    if not isinstance(payload, Mapping):
        context.add(
            "invalid_type",
            field,
            "Check must be an object.",
        )
        return None

    check_type = _read_check_string(
        payload,
        "type",
        field,
        context,
    )

    if not check_type:
        return None

    if check_type == DEVELOPER_CHECK_GIT_DIFF:
        allowed_fields = {
            "type",
        }
        check = DeveloperTaskCheck(
            type=check_type,
        )
    elif check_type == DEVELOPER_CHECK_PY_COMPILE:
        allowed_fields = {
            "type",
            "scope",
        }
        scope = _read_check_string(
            payload,
            "scope",
            field,
            context,
        )

        if scope and scope != "changed_python_files":
            context.add(
                "invalid_check_scope",
                f"{field}.scope",
                "py_compile scope must be changed_python_files.",
            )

        check = DeveloperTaskCheck(
            type=check_type,
            scope=scope,
        )
    elif check_type == DEVELOPER_CHECK_PYTHON_MODULE:
        allowed_fields = {
            "type",
            "module",
        }
        module = _read_check_string(
            payload,
            "module",
            field,
            context,
        )

        if module and not _PYTHON_MODULE_RE.fullmatch(module):
            context.add(
                "invalid_python_module",
                f"{field}.module",
                "Python module must match tools.eval_*.",
            )

        check = DeveloperTaskCheck(
            type=check_type,
            module=module,
        )
    elif check_type == DEVELOPER_CHECK_PIPELINE:
        allowed_fields = {
            "type",
            "flow",
        }
        flow = _read_check_string(
            payload,
            "flow",
            field,
            context,
        )

        if flow and not _PIPELINE_FLOW_RE.fullmatch(flow):
            context.add(
                "invalid_pipeline_flow",
                f"{field}.flow",
                "Pipeline flow has an invalid format.",
            )

        check = DeveloperTaskCheck(
            type=check_type,
            flow=flow,
        )
    else:
        context.add(
            "unsupported_check_type",
            f"{field}.type",
            "Check type is not allowed.",
        )
        return None

    for key in sorted(set(payload) - allowed_fields):
        context.add(
            "unknown_check_field",
            f"{field}.{key}",
            "Check field is not allowed.",
        )

    return check


def validate_developer_task_manifest(
    payload: Any,
) -> DeveloperTaskValidationResult:
    context = _ValidationContext()

    if not isinstance(payload, Mapping):
        return DeveloperTaskValidationResult(
            manifest=None,
            issues=(
                DeveloperTaskValidationIssue(
                    code="invalid_type",
                    field="$",
                    message="Developer task manifest must be an object.",
                ),
            ),
        )

    for field in sorted(set(payload) - _TOP_LEVEL_FIELDS):
        context.add(
            "unknown_field",
            field,
            "Manifest field is not allowed.",
        )

    for field in sorted(_TOP_LEVEL_FIELDS - set(payload)):
        context.add(
            "missing_field",
            field,
            "Manifest field is required.",
        )

    schema_version = payload.get("schema_version")

    if (
        "schema_version" in payload
        and (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != DEVELOPER_TASK_SCHEMA_VERSION
        )
    ):
        context.add(
            "unsupported_schema_version",
            "schema_version",
            f"schema_version must be {DEVELOPER_TASK_SCHEMA_VERSION}.",
        )

    task_kind = context.read_string(
        payload,
        "task_kind",
    )

    if task_kind and task_kind != DEVELOPER_TASK_KIND_PATCH:
        context.add(
            "unsupported_task_kind",
            "task_kind",
            "Only patch tasks are supported in V1.",
        )

    task_id = context.read_string(
        payload,
        "task_id",
        max_length=64,
    )

    if task_id and not _TASK_ID_RE.fullmatch(task_id):
        context.add(
            "invalid_task_id",
            "task_id",
            "task_id must use lowercase letters, digits, underscores, or hyphens.",
        )

    title = context.read_string(
        payload,
        "title",
        max_length=_MAX_TITLE_LENGTH,
    )
    project = context.read_string(
        payload,
        "project",
    )

    if project and project != DEVELOPER_TASK_PROJECT:
        context.add(
            "invalid_project",
            "project",
            f"project must be {DEVELOPER_TASK_PROJECT}.",
        )

    origin = context.read_string(
        payload,
        "origin",
    )

    if origin and origin not in DEVELOPER_TASK_ALLOWED_ORIGINS:
        context.add(
            "unsupported_origin",
            "origin",
            "origin must be manual or browser_bridge.",
        )

    source_ref = context.read_string(
        payload,
        "source_ref",
        max_length=_MAX_SOURCE_REF_LENGTH,
    )
    source_sha256 = context.read_string(
        payload,
        "source_sha256",
    )

    if source_sha256 and not _SHA256_RE.fullmatch(source_sha256):
        context.add(
            "invalid_sha256",
            "source_sha256",
            "source_sha256 must contain 64 lowercase hexadecimal characters.",
        )

    base_commit = context.read_string(
        payload,
        "base_commit",
    )

    if base_commit and not _BASE_COMMIT_RE.fullmatch(base_commit):
        context.add(
            "invalid_base_commit",
            "base_commit",
            "base_commit must contain 7 to 64 lowercase hexadecimal characters.",
        )

    patch_file = context.read_string(
        payload,
        "patch_file",
    )

    if patch_file and not _PATCH_FILE_RE.fullmatch(patch_file):
        context.add(
            "invalid_patch_file",
            "patch_file",
            "patch_file must be a simple .patch filename.",
        )

    patch_sha256 = context.read_string(
        payload,
        "patch_sha256",
    )

    if patch_sha256 and not _SHA256_RE.fullmatch(patch_sha256):
        context.add(
            "invalid_sha256",
            "patch_sha256",
            "patch_sha256 must contain 64 lowercase hexadecimal characters.",
        )

    install_policy = context.read_string(
        payload,
        "install_policy",
    )

    if (
        install_policy
        and install_policy != DEVELOPER_TASK_INSTALL_MANUAL_CONFIRMATION
    ):
        context.add(
            "invalid_install_policy",
            "install_policy",
            "install_policy must be manual_confirmation.",
        )

    allowed_files: list[str] = []
    allowed_files_payload = payload.get("allowed_files")

    if "allowed_files" in payload:
        if not isinstance(allowed_files_payload, list):
            context.add(
                "invalid_type",
                "allowed_files",
                "allowed_files must be an array.",
            )
        else:
            if not 1 <= len(allowed_files_payload) <= _MAX_ALLOWED_FILES:
                context.add(
                    "invalid_allowed_file_count",
                    "allowed_files",
                    f"allowed_files must contain 1 to {_MAX_ALLOWED_FILES} paths.",
                )

            seen_paths: set[str] = set()

            for index, raw_path in enumerate(allowed_files_payload):
                path = _validate_repository_path(
                    raw_path,
                    f"allowed_files[{index}]",
                    context,
                )

                if not path:
                    continue

                path_key = path.casefold()

                if path_key in seen_paths:
                    context.add(
                        "duplicate_allowed_file",
                        f"allowed_files[{index}]",
                        "Repository path duplicates another path on Windows.",
                    )
                    continue

                seen_paths.add(path_key)
                allowed_files.append(path)

    checks: list[DeveloperTaskCheck] = []
    checks_payload = payload.get("checks")

    if "checks" in payload:
        if not isinstance(checks_payload, list):
            context.add(
                "invalid_type",
                "checks",
                "checks must be an array.",
            )
        else:
            if not 1 <= len(checks_payload) <= _MAX_CHECKS:
                context.add(
                    "invalid_check_count",
                    "checks",
                    f"checks must contain 1 to {_MAX_CHECKS} entries.",
                )

            seen_checks: set[tuple[str, str, str, str]] = set()

            for index, raw_check in enumerate(checks_payload):
                check = _validate_check(
                    raw_check,
                    index,
                    context,
                )

                if check is None:
                    continue

                signature = (
                    check.type,
                    check.scope,
                    check.module,
                    check.flow,
                )

                if signature in seen_checks:
                    context.add(
                        "duplicate_check",
                        f"checks[{index}]",
                        "Check duplicates another check.",
                    )
                    continue

                seen_checks.add(signature)
                checks.append(check)

            git_diff_indices = [
                index
                for index, check in enumerate(checks)
                if check.type == DEVELOPER_CHECK_GIT_DIFF
            ]

            if not git_diff_indices:
                context.add(
                    "missing_git_diff_check",
                    "checks",
                    "git_diff_check is required.",
                )
            elif git_diff_indices[0] != 0:
                context.add(
                    "git_diff_check_not_first",
                    "checks",
                    "git_diff_check must be the first check.",
                )

            has_python_files = any(
                path.casefold().endswith(".py")
                for path in allowed_files
            )
            has_py_compile = any(
                check.type == DEVELOPER_CHECK_PY_COMPILE
                and check.scope == "changed_python_files"
                for check in checks
            )

            if has_python_files and not has_py_compile:
                context.add(
                    "missing_py_compile_check",
                    "checks",
                    "py_compile for changed Python files is required.",
                )

            full_check_indices = [
                index
                for index, check in enumerate(checks)
                if (
                    check.type == DEVELOPER_CHECK_PIPELINE
                    and check.flow == "check"
                )
            ]

            if not full_check_indices:
                context.add(
                    "missing_full_pipeline_check",
                    "checks",
                    "The final pipeline flow check is required.",
                )
            elif len(full_check_indices) > 1:
                context.add(
                    "duplicate_full_pipeline_check",
                    "checks",
                    "The full pipeline flow check must appear once.",
                )
            elif full_check_indices[0] != len(checks) - 1:
                context.add(
                    "full_pipeline_check_not_last",
                    "checks",
                    "The full pipeline flow check must be the last check.",
                )

    if context.issues:
        return DeveloperTaskValidationResult(
            manifest=None,
            issues=tuple(context.issues),
        )

    manifest = DeveloperTaskManifest(
        schema_version=schema_version,
        task_kind=task_kind,
        task_id=task_id,
        title=title,
        project=project,
        origin=origin,
        source_ref=source_ref,
        source_sha256=source_sha256,
        base_commit=base_commit,
        patch_file=patch_file,
        patch_sha256=patch_sha256,
        allowed_files=tuple(allowed_files),
        checks=tuple(checks),
        install_policy=install_policy,
    )

    return DeveloperTaskValidationResult(
        manifest=manifest,
        issues=(),
    )


def require_valid_developer_task_manifest(
    payload: Any,
) -> DeveloperTaskManifest:
    result = validate_developer_task_manifest(payload)

    if result.manifest is None:
        raise DeveloperTaskValidationError(result.issues)

    return result.manifest