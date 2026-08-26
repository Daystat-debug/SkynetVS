from __future__ import annotations

"""Fail-closed host filesystem boundary for V1C2C2 active compile/AST composition."""

import hashlib
import html
import json
import os
import secrets

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from modules.developer.developer_task_execution_compile_ast_claim_transaction import (
    DeveloperTaskExecutionCompileAstClaimTransactionMaterial,
)
from modules.developer.developer_task_execution_compile_ast_contract import (
    DeveloperTaskExecutionCompileAstDocument,
    build_compile_ast_source_manifest,
    encode_compile_ast_document,
    parse_compile_ast_request,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_FILE_PATTERN,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker import (
    DeveloperTaskExecutionCompileAstControllerWorkerBundle,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_CONTROL_TOKEN,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_INPUT_TOKEN,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_OUTPUT_TOKEN,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_RUNTIME_TOKEN,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DeveloperTaskExecutionCompileAstRunnerBundle,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME,
)
from modules.developer.developer_task_execution_compile_ast_composition_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARTIFACT_PREFIX,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_COMMIT_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_BOOTSTRAP_FAILURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_CONTROLLER_FAILURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_FAILURE_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SIGNATURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_TERMINAL_FILE_NAME,
)
from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_MANIFEST_FILE_NAME,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_TREE_MANIFEST_SHA256,
)
from modules.developer.developer_task_workspace_cleanup_fs import (
    DeveloperTaskWorkspaceCleanupFileSystemError,
    absolute_path,
    is_reparse_or_symlink,
    remove_verified_workspace,
    validate_workspace_parent,
)


COMPILE_AST_COMPOSITION_ROOT_ALLOCATION_ATTEMPTS = 16
COMPILE_AST_COMPOSITION_READ_CHUNK_BYTES = 64 * 1024
COMPILE_AST_COMPOSITION_READY_MAX_BYTES = 64 * 1024
COMPILE_AST_COMPOSITION_AUTHORIZE_MAX_BYTES = 16 * 1024
COMPILE_AST_COMPOSITION_RESULT_MAX_BYTES = 128 * 1024

COMPILE_AST_COMPOSITION_ARTIFACT_LIMITS: dict[str, int] = {
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME: (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME: (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME: (
        COMPILE_AST_COMPOSITION_READY_MAX_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_FILE_NAME: (
        COMPILE_AST_COMPOSITION_AUTHORIZE_MAX_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_COMMIT_FILE_NAME: 64,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME: (
        COMPILE_AST_COMPOSITION_RESULT_MAX_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_TERMINAL_FILE_NAME: (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SIGNATURE_FILE_NAME: (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME: (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME: (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_BOOTSTRAP_FAILURE_FILE_NAME: (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_FAILURE_MAX_BYTES
    ),
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_CONTROLLER_FAILURE_FILE_NAME: (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_FAILURE_MAX_BYTES
    ),
}


class DeveloperTaskExecutionCompileAstCompositionFileSystemError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        actual: str = "",
        attempts: int = 0,
    ) -> None:
        self.code = code
        self.message = message
        self.actual = actual
        self.attempts = attempts
        super().__init__(message)


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstCompositionFileEvidence:
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
class DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts:
    root: Path
    root_metadata: os.stat_result = field(repr=False, compare=False)
    input_root: Path
    source_root: Path
    runtime_root: Path
    control_root: Path
    output_root: Path
    request_path: Path
    source_manifest_path: Path
    ready_path: Path
    authorize_path: Path
    authorize_commit_path: Path
    result_path: Path
    terminal_payload_path: Path
    terminal_signature_path: Path
    controller_evidence_payload_path: Path
    controller_evidence_signature_path: Path
    bootstrap_failure_path: Path
    controller_failure_path: Path
    wsb_path: Path
    request: DeveloperTaskExecutionCompileAstDocument
    source_manifest: DeveloperTaskExecutionCompileAstDocument
    runtime_files: tuple[DeveloperTaskExecutionCompileAstCompositionFileEvidence, ...]
    input_files: tuple[DeveloperTaskExecutionCompileAstCompositionFileEvidence, ...]
    source_files: tuple[DeveloperTaskExecutionCompileAstCompositionFileEvidence, ...]
    transaction_material: DeveloperTaskExecutionCompileAstClaimTransactionMaterial = field(
        repr=False, compare=False
    )
    runner_bundle: DeveloperTaskExecutionCompileAstRunnerBundle = field(
        repr=False, compare=False
    )
    controller_worker_bundle: DeveloperTaskExecutionCompileAstControllerWorkerBundle = field(
        repr=False, compare=False
    )
    wsb_bytes: bytes = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "input_root": str(self.input_root),
            "source_root": str(self.source_root),
            "runtime_root": str(self.runtime_root),
            "control_root": str(self.control_root),
            "output_root": str(self.output_root),
            "paths": {
                "request": str(self.request_path),
                "source_manifest": str(self.source_manifest_path),
                "ready": str(self.ready_path),
                "authorize": str(self.authorize_path),
                "authorize_commit": str(self.authorize_commit_path),
                "result": str(self.result_path),
                "terminal_payload": str(self.terminal_payload_path),
                "terminal_signature": str(self.terminal_signature_path),
                "controller_evidence_payload": str(
                    self.controller_evidence_payload_path
                ),
                "controller_evidence_signature": str(
                    self.controller_evidence_signature_path
                ),
                "bootstrap_failure": str(self.bootstrap_failure_path),
                "controller_failure": str(self.controller_failure_path),
                "wsb": str(self.wsb_path),
            },
            "runtime_files": [item.to_dict() for item in self.runtime_files],
            "input_files": [item.to_dict() for item in self.input_files],
            "source_files": [item.to_dict() for item in self.source_files],
            "runtime_bundle_fingerprint": (
                self.transaction_material.runtime_bundle.report.bundle_fingerprint
            ),
            "runner_bundle_fingerprint": self.runner_bundle.bundle_fingerprint,
            "controller_worker_bundle_fingerprint": (
                self.controller_worker_bundle.bundle_fingerprint
            ),
            "request_sha256": self.request.sha256,
            "source_manifest_sha256": self.source_manifest.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence:
    runtime_file_count: int
    runtime_total_bytes: int
    runtime_tree_manifest_sha256: str
    runtime_manifest_sha256: str
    input_file_count: int
    input_manifest_sha256: str
    source_file_count: int
    source_total_bytes: int
    source_manifest_sha256: str
    regular_files_verified: bool
    reparse_points_absent: bool

    @property
    def ok(self) -> bool:
        return (
            self.runtime_file_count == RUNTIME_BUNDLE_FILE_COUNT
            and self.runtime_total_bytes == RUNTIME_BUNDLE_TOTAL_BYTES
            and self.runtime_tree_manifest_sha256 == RUNTIME_TREE_MANIFEST_SHA256
            and self.runtime_manifest_sha256 == RUNTIME_MANIFEST_SHA256
            and self.input_file_count == 10
            and len(self.input_manifest_sha256) == 64
            and 1 <= self.source_file_count <= 20
            and 0 <= self.source_total_bytes <= 8 * 1024 * 1024
            and len(self.source_manifest_sha256) == 64
            and self.regular_files_verified
            and self.reparse_points_absent
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "runtime_file_count": self.runtime_file_count,
            "runtime_total_bytes": self.runtime_total_bytes,
            "runtime_tree_manifest_sha256": self.runtime_tree_manifest_sha256,
            "runtime_manifest_sha256": self.runtime_manifest_sha256,
            "input_file_count": self.input_file_count,
            "input_manifest_sha256": self.input_manifest_sha256,
            "source_file_count": self.source_file_count,
            "source_total_bytes": self.source_total_bytes,
            "source_manifest_sha256": self.source_manifest_sha256,
            "regular_files_verified": self.regular_files_verified,
            "reparse_points_absent": self.reparse_points_absent,
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _file_version(value: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


def _safe_flat_name(name: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "\x00" in name
        or "/" in name
        or "\\" in name
        or ":" in name
        or name[-1] in {" ", "."}
    ):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_file_name_invalid",
            "Compile/AST composition file name is not a safe flat Windows name.",
            actual=repr(name),
        )
    return name


def _validate_path_chain(path: Path, *, code_prefix: str) -> None:
    absolute = absolute_path(path)
    parts = absolute.parts
    if not parts:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            f"{code_prefix}_path_invalid",
            "Filesystem path is invalid.",
            actual=str(absolute),
        )
    current = Path(parts[0])
    for part in parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                f"{code_prefix}_metadata_failed",
                "Filesystem path metadata could not be read.",
                actual=f"{current}:{type(exc).__name__}:{exc}",
            ) from exc
        if is_reparse_or_symlink(metadata):
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                f"{code_prefix}_reparse_forbidden",
                "Filesystem path chain contains a reparse point or symlink.",
                actual=str(current),
            )


def validate_developer_task_execution_compile_ast_composition_artifact_parent(
    artifact_parent: Path,
) -> Path:
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")
    parent = absolute_path(artifact_parent)
    try:
        validate_workspace_parent(parent)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_parent_invalid",
            "V1C2C2 artifact parent is not a verified ordinary directory.",
            actual=f"{exc.code}:{exc.actual}",
        ) from exc
    _validate_path_chain(parent, code_prefix="compile_ast_composition_artifact_parent")
    return parent


def read_developer_task_execution_compile_ast_composition_artifact_bytes(
    path: Path,
    *,
    max_bytes: int,
    artifact_name: str,
    expected_size: int | None = None,
    allow_empty: bool = False,
) -> tuple[bytes, str]:
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 0:
        raise TypeError("max_bytes must be a non-negative int")
    if expected_size is not None and (
        not isinstance(expected_size, int)
        or isinstance(expected_size, bool)
        or expected_size < 0
    ):
        raise TypeError("expected_size must be a non-negative int or None")
    _validate_path_chain(path.parent, code_prefix="compile_ast_composition_artifact")
    try:
        initial = os.lstat(path)
    except OSError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_read_failed",
            "V1C2C2 artifact metadata could not be read.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    if is_reparse_or_symlink(initial) or not os.path.isfile(path):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_not_regular",
            "V1C2C2 artifact must be a regular non-reparse file.",
            actual=artifact_name,
        )
    size = int(initial.st_size)
    if (size == 0 and not allow_empty) or size > max_bytes:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_size_invalid",
            "V1C2C2 artifact size is outside the bounded contract.",
            actual=f"{artifact_name}:{size}",
        )
    if expected_size is not None and size != expected_size:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_size_mismatch",
            "V1C2C2 artifact size does not match the expected exact bytes.",
            actual=f"{artifact_name}:{size}!={expected_size}",
        )
    content = bytearray()
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(COMPILE_AST_COMPOSITION_READ_CHUNK_BYTES)
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                        "compile_ast_composition_artifact_size_invalid",
                        "V1C2C2 artifact exceeded the bounded read limit.",
                        actual=artifact_name,
                    )
    except DeveloperTaskExecutionCompileAstCompositionFileSystemError:
        raise
    except OSError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_read_failed",
            "V1C2C2 artifact bytes could not be read.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    try:
        final = os.lstat(path)
    except OSError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_changed_during_read",
            "V1C2C2 artifact metadata disappeared after reading.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    if _file_version(final) != _file_version(initial):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_changed_during_read",
            "V1C2C2 artifact changed during reading.",
            actual=artifact_name,
        )
    raw = bytes(content)
    return raw, _sha256(raw)


def _write_new_file(path: Path, data: bytes, *, allow_empty: bool = False) -> None:
    if not isinstance(data, bytes) or (not data and not allow_empty):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_bytes_invalid",
            "V1C2C2 materialized bytes are invalid.",
            actual=str(path),
        )
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_write_failed",
            "V1C2C2 artifact could not be written exclusively.",
            actual=f"{path}:{type(exc).__name__}:{exc}",
        ) from exc


def _exact_directory_names(root: Path) -> tuple[str, ...]:
    try:
        return tuple(sorted(os.listdir(root)))
    except OSError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_tree_scan_failed",
            "V1C2C2 materialized directory could not be scanned.",
            actual=f"{root}:{type(exc).__name__}:{exc}",
        ) from exc


def _materialize_flat_exact_files(
    root: Path,
    files: Iterable[tuple[str, bytes]],
    *,
    code_prefix: str,
    allow_empty: bool = False,
) -> tuple[DeveloperTaskExecutionCompileAstCompositionFileEvidence, ...]:
    prepared: list[tuple[str, bytes]] = []
    case_keys: dict[str, str] = {}
    for name, data in files:
        safe_name = _safe_flat_name(name)
        if not isinstance(data, bytes) or (not data and not allow_empty):
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                f"{code_prefix}_bytes_invalid",
                "Materialized exact bytes are invalid.",
                actual=safe_name,
            )
        key = safe_name.casefold()
        if key in case_keys:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                f"{code_prefix}_case_collision",
                "Materialized file names collide under Windows casing.",
                actual=f"{case_keys[key]}|{safe_name}",
            )
        case_keys[key] = safe_name
        prepared.append((safe_name, data))
    prepared.sort(key=lambda item: item[0])
    if _exact_directory_names(root):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            f"{code_prefix}_root_not_empty",
            "Materialization root must be empty.",
            actual=str(root),
        )
    for name, data in prepared:
        _write_new_file(root / name, data, allow_empty=allow_empty)
    actual_names = _exact_directory_names(root)
    expected_names = tuple(name for name, _ in prepared)
    if actual_names != expected_names:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            f"{code_prefix}_file_set_mismatch",
            "Materialized file set does not match expected names.",
            actual=repr(actual_names),
        )
    evidence: list[DeveloperTaskExecutionCompileAstCompositionFileEvidence] = []
    for name, expected in prepared:
        raw, sha256 = read_developer_task_execution_compile_ast_composition_artifact_bytes(
            root / name,
            max_bytes=max(len(expected), 0),
            artifact_name=name,
            expected_size=len(expected),
            allow_empty=allow_empty,
        )
        if raw != expected or sha256 != _sha256(expected):
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                f"{code_prefix}_post_write_mismatch",
                "Materialized exact bytes changed during disk round-trip.",
                actual=name,
            )
        evidence.append(
            DeveloperTaskExecutionCompileAstCompositionFileEvidence(
                path=name,
                size_bytes=len(raw),
                sha256=sha256,
            )
        )
    return tuple(evidence)


def _manifest_sha256(
    files: tuple[DeveloperTaskExecutionCompileAstCompositionFileEvidence, ...],
) -> str:
    return _sha256(_canonical_json_bytes([item.to_dict() for item in files]))


def _allocate_run_root(parent: Path, request_id: str) -> Path:
    for _ in range(COMPILE_AST_COMPOSITION_ROOT_ALLOCATION_ATTEMPTS):
        candidate = parent / (
            f"{DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARTIFACT_PREFIX}"
            f"{request_id[:8]}-{secrets.token_hex(8)}"
        )
        try:
            candidate.mkdir(mode=0o700, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
        except OSError as exc:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_artifact_root_create_failed",
                "V1C2C2 artifact root could not be created.",
                actual=f"{type(exc).__name__}:{exc}",
            ) from exc
    raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
        "compile_ast_composition_artifact_root_collision",
        "A unique V1C2C2 artifact root could not be allocated.",
    )


def _default_windows_host_path(path: Path) -> str:
    return str(path)


def _render_wsb_template(
    template_bytes: bytes,
    *,
    input_root: Path,
    runtime_root: Path,
    control_root: Path,
    output_root: Path,
    host_path_mapper: Callable[[Path], str],
) -> bytes:
    try:
        text = template_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_wsb_template_invalid",
            "V1C2C2 WSB template is not strict UTF-8.",
        ) from exc
    replacements = {
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_INPUT_TOKEN: html.escape(
            host_path_mapper(input_root), quote=True
        ),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_RUNTIME_TOKEN: html.escape(
            host_path_mapper(runtime_root), quote=True
        ),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_CONTROL_TOKEN: html.escape(
            host_path_mapper(control_root), quote=True
        ),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_OUTPUT_TOKEN: html.escape(
            host_path_mapper(output_root), quote=True
        ),
    }
    for token, value in replacements.items():
        if not value or "\x00" in value:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_wsb_host_path_invalid",
                "Mapped host path is empty or contains NUL.",
                actual=token,
            )
        if text.count(token) != 1:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_wsb_template_invalid",
                "WSB template token count is not exactly one.",
                actual=token,
            )
        text = text.replace(token, value)
    if "@@SKYNETVS_" in text:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_wsb_template_invalid",
            "WSB template contains unresolved mapping tokens.",
        )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


def _utc_timestamp(epoch_seconds: float) -> str:
    if isinstance(epoch_seconds, bool) or not isinstance(epoch_seconds, (int, float)):
        raise TypeError("created_at_epoch_seconds must be a positive number")
    if epoch_seconds <= 0:
        raise TypeError("created_at_epoch_seconds must be a positive number")
    return datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def prepare_developer_task_execution_compile_ast_composition_artifacts(
    *,
    artifact_parent: Path,
    transaction_material: DeveloperTaskExecutionCompileAstClaimTransactionMaterial,
    runner_bundle: DeveloperTaskExecutionCompileAstRunnerBundle,
    controller_worker_bundle: DeveloperTaskExecutionCompileAstControllerWorkerBundle,
    request_id: str,
    host_nonce: str,
    created_at_epoch_seconds: float,
    host_path_mapper: Callable[[Path], str] = _default_windows_host_path,
) -> DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts:
    if type(transaction_material) is not DeveloperTaskExecutionCompileAstClaimTransactionMaterial:
        raise TypeError(
            "transaction_material must be DeveloperTaskExecutionCompileAstClaimTransactionMaterial"
        )
    if type(runner_bundle) is not DeveloperTaskExecutionCompileAstRunnerBundle:
        raise TypeError("runner_bundle must be DeveloperTaskExecutionCompileAstRunnerBundle")
    if type(controller_worker_bundle) is not DeveloperTaskExecutionCompileAstControllerWorkerBundle:
        raise TypeError(
            "controller_worker_bundle must be DeveloperTaskExecutionCompileAstControllerWorkerBundle"
        )
    if not runner_bundle.ok or not controller_worker_bundle.ok:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_payload_bundle_invalid",
            "Canonical V1C2A2/V1C2C1R4 bundles are required.",
        )
    runtime_bundle = transaction_material.runtime_bundle
    plan_material = transaction_material.plan_material
    if not runtime_bundle.ok or runtime_bundle.report.bundle_fingerprint != RUNTIME_BUNDLE_FINGERPRINT:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_runtime_bundle_invalid",
            "Claimed runtime bundle does not match V1B4B.",
        )
    if (
        plan_material.report.policy_fingerprint
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT
        or not plan_material.report.ok
    ):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_plan_material_invalid",
            "Claimed compile/AST plan material is not canonical.",
        )
    if not callable(host_path_mapper):
        raise TypeError("host_path_mapper must be callable")

    parent = validate_developer_task_execution_compile_ast_composition_artifact_parent(
        artifact_parent
    )
    root = _allocate_run_root(parent, request_id)
    root_metadata = os.lstat(root)
    try:
        input_root = root / "input"
        source_root = input_root / "sources"
        runtime_root = root / "runtime"
        control_root = root / "control"
        output_root = root / "output"
        for directory in (
            input_root,
            runtime_root,
            control_root,
            output_root,
        ):
            directory.mkdir(mode=0o700, exist_ok=False)

        runtime_files = _materialize_flat_exact_files(
            runtime_root,
            (
                (name, runtime_bundle.exact_file_bytes(name))
                for name in runtime_bundle.file_names
            ),
            code_prefix="compile_ast_composition_runtime",
        )
        if (
            len(runtime_files) != RUNTIME_BUNDLE_FILE_COUNT
            or sum(item.size_bytes for item in runtime_files) != RUNTIME_BUNDLE_TOTAL_BYTES
            or _manifest_sha256(runtime_files) != RUNTIME_TREE_MANIFEST_SHA256
        ):
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_runtime_tree_mismatch",
                "Materialized runtime tree identity changed.",
            )
        runtime_manifest = next(
            (item for item in runtime_files if item.path == RUNTIME_MANIFEST_FILE_NAME),
            None,
        )
        if runtime_manifest is None or runtime_manifest.sha256 != RUNTIME_MANIFEST_SHA256:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_runtime_manifest_mismatch",
                "Materialized runtime manifest identity changed.",
            )

        source_manifest = build_compile_ast_source_manifest(
            plan_material.report,
            request_id=request_id,
            host_nonce=host_nonce,
        )
        manifest_sources = source_manifest.to_dict()["sources"]
        source_payloads: list[tuple[str, bytes]] = []
        for item in manifest_sources:
            original_path = item["original_path"]
            exact = plan_material.exact_source_bytes(original_path)
            if len(exact) != item["size_bytes"] or _sha256(exact) != item["sha256"]:
                raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                    "compile_ast_composition_source_material_mismatch",
                    "Claimed source bytes do not match the canonical manifest.",
                    actual=original_path,
                )
            source_payloads.append((item["guest_file_name"], exact))
        wsb_bytes = _render_wsb_template(
            controller_worker_bundle.wsb_template.exact_bytes(),
            input_root=input_root,
            runtime_root=runtime_root,
            control_root=control_root,
            output_root=output_root,
            host_path_mapper=host_path_mapper,
        )
        input_payloads = (
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
                controller_worker_bundle.policy.exact_bytes(),
            ),
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
                controller_worker_bundle.bootstrap.exact_bytes(),
            ),
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
                controller_worker_bundle.controller.exact_bytes(),
            ),
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
                controller_worker_bundle.native_helper.exact_bytes(),
            ),
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
                runner_bundle.contract_policy.exact_bytes(),
            ),
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
                runner_bundle.runner.exact_bytes(),
            ),
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
                runner_bundle.payload_manifest.exact_bytes(),
            ),
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
                wsb_bytes,
            ),
            (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME,
                source_manifest.canonical_bytes,
            ),
        )
        input_files_without_request = _materialize_flat_exact_files(
            input_root,
            input_payloads,
            code_prefix="compile_ast_composition_input",
        )
        payload_hashes = {item.path: item.sha256 for item in input_files_without_request}
        request_payload = {
            "schema_version": 1,
            "backend_id": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id,
            "backend_policy_fingerprint": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
            "contract_policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
            "contract_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
            "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
            "request_id": request_id,
            "host_nonce": host_nonce,
            "created_at_utc": _utc_timestamp(created_at_epoch_seconds),
            "ready_timeout_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
            "authorization_timeout_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
            "worker_timeout_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
            "shutdown_grace_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
            "policy_sha256": payload_hashes[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME
            ],
            "bootstrap_sha256": payload_hashes[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME
            ],
            "controller_sha256": payload_hashes[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME
            ],
            "native_helper_sha256": payload_hashes[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME
            ],
            "runner_sha256": payload_hashes[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME
            ],
            "payload_sha256": payload_hashes[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME
            ],
            "wsb_sha256": payload_hashes[
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME
            ],
            "runtime_attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
            "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
            "runtime_lease_policy_fingerprint": RUNTIME_LEASE_POLICY_FINGERPRINT,
            "runtime_lease_fingerprint": transaction_material.runtime_lease_fingerprint,
            "plan_policy_fingerprint": plan_material.report.policy_fingerprint,
            "plan_fingerprint": plan_material.report.plan_fingerprint,
            "source_manifest_sha256": source_manifest.sha256,
            "selected_file_count": plan_material.report.selected_file_count,
            "selected_total_bytes": plan_material.report.selected_total_bytes,
            "trusted_scope": "compile_ast_changed_python_only_v1",
            "execution_authorized": False,
        }
        request_bytes = encode_compile_ast_document("request", request_payload)
        request = parse_compile_ast_request(request_bytes)
        request_path = input_root / DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME
        _write_new_file(request_path, request.canonical_bytes)
        request_raw, request_sha256 = read_developer_task_execution_compile_ast_composition_artifact_bytes(
            request_path,
            max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES,
            artifact_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
            expected_size=len(request.canonical_bytes),
        )
        if request_raw != request.canonical_bytes or request_sha256 != request.sha256:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_request_post_write_mismatch",
                "Materialized request changed during disk round-trip.",
            )
        input_files = tuple(
            sorted(
                (
                    *input_files_without_request,
                    DeveloperTaskExecutionCompileAstCompositionFileEvidence(
                        path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
                        size_bytes=len(request_raw),
                        sha256=request_sha256,
                    ),
                ),
                key=lambda item: item.path,
            )
        )

        # Keep the trusted input root flat until every exact input file has
        # completed its exclusive write and disk round-trip.  The nested
        # read-only source directory is created only after that flat-input
        # boundary is complete.
        source_root.mkdir(mode=0o700, exist_ok=False)
        source_files = _materialize_flat_exact_files(
            source_root,
            source_payloads,
            code_prefix="compile_ast_composition_source",
            allow_empty=True,
        )

        if _exact_directory_names(control_root) or _exact_directory_names(output_root):
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_mutable_root_not_empty",
                "Control and output roots must be empty before Sandbox launch.",
            )
        return DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts(
            root=root,
            root_metadata=root_metadata,
            input_root=input_root,
            source_root=source_root,
            runtime_root=runtime_root,
            control_root=control_root,
            output_root=output_root,
            request_path=request_path,
            source_manifest_path=(
                input_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME
            ),
            ready_path=(
                output_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME
            ),
            authorize_path=(
                control_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_FILE_NAME
            ),
            authorize_commit_path=(
                control_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_COMMIT_FILE_NAME
            ),
            result_path=output_root / DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
            terminal_payload_path=(
                output_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_TERMINAL_FILE_NAME
            ),
            terminal_signature_path=(
                output_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SIGNATURE_FILE_NAME
            ),
            controller_evidence_payload_path=(
                output_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME
            ),
            controller_evidence_signature_path=(
                output_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME
            ),
            bootstrap_failure_path=(
                output_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_BOOTSTRAP_FAILURE_FILE_NAME
            ),
            controller_failure_path=(
                output_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_CONTROLLER_FAILURE_FILE_NAME
            ),
            wsb_path=(
                input_root
                / DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME
            ),
            request=request,
            source_manifest=source_manifest,
            runtime_files=runtime_files,
            input_files=input_files,
            source_files=source_files,
            transaction_material=transaction_material,
            runner_bundle=runner_bundle,
            controller_worker_bundle=controller_worker_bundle,
            wsb_bytes=wsb_bytes,
        )
    except Exception as original:
        try:
            remove_developer_task_execution_compile_ast_composition_artifacts(
                root,
                artifact_parent=parent,
                initial_metadata=root_metadata,
            )
        except Exception as cleanup_error:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_artifact_preparation_cleanup_failed",
                "Partially prepared V1C2C2 artifacts could not be removed safely.",
                actual=f"{type(cleanup_error).__name__}:{cleanup_error}",
            ) from original
        raise


def verify_developer_task_execution_compile_ast_composition_materialization(
    prepared: DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts,
) -> DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence:
    if type(prepared) is not DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts:
        raise TypeError(
            "prepared must be DeveloperTaskExecutionCompileAstCompositionPreparedArtifacts"
        )
    runtime_bundle = prepared.transaction_material.runtime_bundle
    actual_runtime_names = _exact_directory_names(prepared.runtime_root)
    if actual_runtime_names != runtime_bundle.file_names:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_runtime_file_set_mismatch",
            "Prepared runtime file set changed.",
            actual=repr(actual_runtime_names),
        )
    runtime_evidence: list[DeveloperTaskExecutionCompileAstCompositionFileEvidence] = []
    for name in runtime_bundle.file_names:
        expected = runtime_bundle.exact_file_bytes(name)
        raw, sha256 = read_developer_task_execution_compile_ast_composition_artifact_bytes(
            prepared.runtime_root / name,
            max_bytes=len(expected),
            artifact_name=name,
            expected_size=len(expected),
        )
        if raw != expected:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_runtime_file_changed",
                "Prepared runtime bytes changed.",
                actual=name,
            )
        runtime_evidence.append(
            DeveloperTaskExecutionCompileAstCompositionFileEvidence(
                path=name,
                size_bytes=len(raw),
                sha256=sha256,
            )
        )
    runtime_files = tuple(runtime_evidence)
    runtime_manifest_sha256 = next(
        item.sha256 for item in runtime_files if item.path == RUNTIME_MANIFEST_FILE_NAME
    )

    expected_input: dict[str, bytes] = {
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME: prepared.controller_worker_bundle.policy.exact_bytes(),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME: prepared.controller_worker_bundle.bootstrap.exact_bytes(),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME: prepared.controller_worker_bundle.controller.exact_bytes(),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME: prepared.controller_worker_bundle.native_helper.exact_bytes(),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME: prepared.runner_bundle.contract_policy.exact_bytes(),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME: prepared.runner_bundle.runner.exact_bytes(),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME: prepared.runner_bundle.payload_manifest.exact_bytes(),
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME: prepared.wsb_bytes,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME: prepared.source_manifest.canonical_bytes,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME: prepared.request.canonical_bytes,
    }
    actual_input_names = tuple(
        name for name in _exact_directory_names(prepared.input_root) if name != "sources"
    )
    if tuple(sorted(expected_input)) != actual_input_names:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_input_file_set_mismatch",
            "Prepared trusted input file set changed.",
            actual=repr(actual_input_names),
        )
    input_evidence: list[DeveloperTaskExecutionCompileAstCompositionFileEvidence] = []
    for name in sorted(expected_input):
        expected = expected_input[name]
        raw, sha256 = read_developer_task_execution_compile_ast_composition_artifact_bytes(
            prepared.input_root / name,
            max_bytes=len(expected),
            artifact_name=name,
            expected_size=len(expected),
        )
        if raw != expected:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_input_file_changed",
                "Prepared trusted input bytes changed.",
                actual=name,
            )
        input_evidence.append(
            DeveloperTaskExecutionCompileAstCompositionFileEvidence(
                path=name,
                size_bytes=len(raw),
                sha256=sha256,
            )
        )

    manifest_sources = prepared.source_manifest.to_dict()["sources"]
    expected_source_names = tuple(item["guest_file_name"] for item in manifest_sources)
    if _exact_directory_names(prepared.source_root) != expected_source_names:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_source_file_set_mismatch",
            "Prepared flat source file set changed.",
        )
    source_evidence: list[DeveloperTaskExecutionCompileAstCompositionFileEvidence] = []
    for item in manifest_sources:
        name = item["guest_file_name"]
        expected = prepared.transaction_material.plan_material.exact_source_bytes(
            item["original_path"]
        )
        raw, sha256 = read_developer_task_execution_compile_ast_composition_artifact_bytes(
            prepared.source_root / name,
            max_bytes=len(expected),
            artifact_name=name,
            expected_size=len(expected),
            allow_empty=True,
        )
        if raw != expected or sha256 != item["sha256"]:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_source_file_changed",
                "Prepared source bytes changed.",
                actual=name,
            )
        source_evidence.append(
            DeveloperTaskExecutionCompileAstCompositionFileEvidence(
                path=name,
                size_bytes=len(raw),
                sha256=sha256,
            )
        )

    evidence = DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence(
        runtime_file_count=len(runtime_files),
        runtime_total_bytes=sum(item.size_bytes for item in runtime_files),
        runtime_tree_manifest_sha256=_manifest_sha256(runtime_files),
        runtime_manifest_sha256=runtime_manifest_sha256,
        input_file_count=len(input_evidence),
        input_manifest_sha256=_manifest_sha256(tuple(input_evidence)),
        source_file_count=len(source_evidence),
        source_total_bytes=sum(item.size_bytes for item in source_evidence),
        source_manifest_sha256=prepared.source_manifest.sha256,
        regular_files_verified=True,
        reparse_points_absent=True,
    )
    if (
        not evidence.ok
        or evidence.source_file_count
        != prepared.transaction_material.plan_material.report.selected_file_count
        or evidence.source_total_bytes
        != prepared.transaction_material.plan_material.report.selected_total_bytes
    ):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_materialization_identity_mismatch",
            "Prepared V1C2C2 materialization does not match pinned identities.",
            actual=json.dumps(evidence.to_dict(), sort_keys=True),
        )
    return evidence


def publish_developer_task_execution_compile_ast_composition_authorization(
    authorize_path: Path,
    authorize_bytes: bytes,
) -> tuple[str, str]:
    if not isinstance(authorize_path, Path):
        raise TypeError("authorize_path must be pathlib.Path")
    if not isinstance(authorize_bytes, bytes) or not authorize_bytes:
        raise TypeError("authorize_bytes must be non-empty bytes")
    commit_path = authorize_path.with_name(
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_COMMIT_FILE_NAME
    )
    existing = tuple(
        str(path) for path in (authorize_path, commit_path) if os.path.lexists(path)
    )
    if existing:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_authorization_already_exists",
            "Authorization or commit marker already exists.",
            actual=",".join(existing),
        )
    authorize_sha256 = _sha256(authorize_bytes)
    commit_bytes = authorize_sha256.encode("ascii")
    try:
        _write_new_file(authorize_path, authorize_bytes)
        published, published_sha256 = read_developer_task_execution_compile_ast_composition_artifact_bytes(
            authorize_path,
            max_bytes=COMPILE_AST_COMPOSITION_AUTHORIZE_MAX_BYTES,
            artifact_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_FILE_NAME,
            expected_size=len(authorize_bytes),
        )
        if published != authorize_bytes or published_sha256 != authorize_sha256:
            raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
                "compile_ast_composition_authorization_publish_verification_failed",
                "Published authorization differs from pinned bytes.",
            )
        _write_new_file(commit_path, commit_bytes)
    except DeveloperTaskExecutionCompileAstCompositionFileSystemError:
        raise
    except OSError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_authorization_publish_failed",
            "Authorization publication failed.",
            actual=f"{type(exc).__name__}:{exc}",
        ) from exc
    return authorize_sha256, _sha256(commit_bytes)


def remove_developer_task_execution_compile_ast_composition_artifacts(
    root: Path,
    *,
    artifact_parent: Path,
    initial_metadata: os.stat_result,
) -> int:
    if not isinstance(root, Path) or not isinstance(artifact_parent, Path):
        raise TypeError("root and artifact_parent must be pathlib.Path")
    root_resolved = absolute_path(root)
    parent_resolved = absolute_path(artifact_parent)
    if (
        root_resolved.parent != parent_resolved
        or not root_resolved.name.startswith(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARTIFACT_PREFIX
        )
    ):
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_cleanup_scope_invalid",
            "V1C2C2 cleanup target is outside the verified scope.",
            actual=str(root_resolved),
        )
    try:
        removal = remove_verified_workspace(root_resolved, initial_metadata)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        raise DeveloperTaskExecutionCompileAstCompositionFileSystemError(
            "compile_ast_composition_artifact_cleanup_failed",
            "V1C2C2 artifact cleanup failed.",
            actual=f"{exc.code}:{exc.actual};attempts={exc.attempts}",
            attempts=exc.attempts,
        ) from exc
    return removal.attempts
