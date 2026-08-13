from __future__ import annotations

"""Fail-closed host filesystem boundary for V1B4C2B active runtime composition."""

import hashlib
import json
import os
import secrets
import stat

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from modules.developer.developer_task_execution_runtime_attestation import (
    DeveloperTaskRuntimeAttestationPayloadBundle,
)
from modules.developer.developer_task_execution_runtime_attestation_contract import (
    DeveloperTaskRuntimeAttestationDocument,
    RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES,
    RUNTIME_ATTESTATION_READY_MAX_BYTES,
    RUNTIME_ATTESTATION_REQUEST_MAX_BYTES,
    RUNTIME_ATTESTATION_RESULT_MAX_BYTES,
    RUNTIME_ATTESTATION_SIGNATURE_BYTES,
    RUNTIME_ATTESTATION_TERMINAL_MAX_BYTES,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME,
    RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME,
    RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME,
    RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME,
    RUNTIME_ATTESTATION_CONTROLLER_FAILURE_FILE_NAME,
    RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME,
    RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME,
    RUNTIME_ATTESTATION_POLICY_FILE_NAME,
    RUNTIME_ATTESTATION_READY_FILE_NAME,
    RUNTIME_ATTESTATION_REQUEST_FILE_NAME,
    RUNTIME_ATTESTATION_RESULT_FILE_NAME,
    RUNTIME_ATTESTATION_SIGNATURE_FILE_NAME,
    RUNTIME_ATTESTATION_TERMINAL_FILE_NAME,
    RUNTIME_ATTESTATION_WSB_FILE_NAME,
    build_runtime_attestation_request,
    build_runtime_attestation_wsb_config,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    DeveloperTaskPythonRuntimeBundle,
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


RUNTIME_COMPOSITION_ARTIFACT_PREFIX = "skynetvs-runtime-composition-"
RUNTIME_COMPOSITION_FAILURE_MAX_BYTES = 64 * 1024
RUNTIME_COMPOSITION_READ_CHUNK_BYTES = 64 * 1024
RUNTIME_COMPOSITION_ROOT_ALLOCATION_ATTEMPTS = 16

RUNTIME_COMPOSITION_ARTIFACT_LIMITS: dict[str, int] = {
    RUNTIME_ATTESTATION_REQUEST_FILE_NAME: RUNTIME_ATTESTATION_REQUEST_MAX_BYTES,
    RUNTIME_ATTESTATION_READY_FILE_NAME: RUNTIME_ATTESTATION_READY_MAX_BYTES,
    RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME: RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES,
    RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME: 64,
    RUNTIME_ATTESTATION_RESULT_FILE_NAME: RUNTIME_ATTESTATION_RESULT_MAX_BYTES,
    RUNTIME_ATTESTATION_TERMINAL_FILE_NAME: RUNTIME_ATTESTATION_TERMINAL_MAX_BYTES,
    RUNTIME_ATTESTATION_SIGNATURE_FILE_NAME: RUNTIME_ATTESTATION_SIGNATURE_BYTES,
    RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME: RUNTIME_COMPOSITION_FAILURE_MAX_BYTES,
    RUNTIME_ATTESTATION_CONTROLLER_FAILURE_FILE_NAME: RUNTIME_COMPOSITION_FAILURE_MAX_BYTES,
}


class DeveloperTaskExecutionRuntimeCompositionFileSystemError(RuntimeError):
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
class DeveloperTaskExecutionRuntimeCompositionFileEvidence:
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
class DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts:
    root: Path
    root_metadata: os.stat_result = field(repr=False, compare=False)
    input_root: Path
    runtime_root: Path
    control_root: Path
    output_root: Path
    request_path: Path
    ready_path: Path
    authorize_path: Path
    authorize_commit_path: Path
    runtime_result_path: Path
    terminal_payload_path: Path
    terminal_signature_path: Path
    bootstrap_failure_path: Path
    controller_failure_path: Path
    policy_path: Path
    bootstrap_path: Path
    controller_path: Path
    native_helper_path: Path
    wsb_path: Path
    request: DeveloperTaskRuntimeAttestationDocument
    runtime_files: tuple[DeveloperTaskExecutionRuntimeCompositionFileEvidence, ...]
    input_files: tuple[DeveloperTaskExecutionRuntimeCompositionFileEvidence, ...]
    runtime_bundle: DeveloperTaskPythonRuntimeBundle = field(repr=False, compare=False)
    payload_bundle: DeveloperTaskRuntimeAttestationPayloadBundle = field(repr=False, compare=False)
    wsb_bytes: bytes = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "input_root": str(self.input_root),
            "runtime_root": str(self.runtime_root),
            "control_root": str(self.control_root),
            "output_root": str(self.output_root),
            "paths": {
                "request": str(self.request_path),
                "ready": str(self.ready_path),
                "authorize": str(self.authorize_path),
                "authorize_commit": str(self.authorize_commit_path),
                "runtime_result": str(self.runtime_result_path),
                "terminal_payload": str(self.terminal_payload_path),
                "terminal_signature": str(self.terminal_signature_path),
                "bootstrap_failure": str(self.bootstrap_failure_path),
                "controller_failure": str(self.controller_failure_path),
                "wsb": str(self.wsb_path),
            },
            "runtime_files": [item.to_dict() for item in self.runtime_files],
            "input_files": [item.to_dict() for item in self.input_files],
            "runtime_bundle_fingerprint": self.runtime_bundle.report.bundle_fingerprint,
            "payload_bundle_fingerprint": self.payload_bundle.payload_fingerprint,
            "request_sha256": self.request.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence:
    runtime_file_count: int
    runtime_total_bytes: int
    runtime_tree_manifest_sha256: str
    runtime_manifest_sha256: str
    input_file_count: int
    input_manifest_sha256: str
    regular_files_verified: bool
    reparse_points_absent: bool

    @property
    def ok(self) -> bool:
        return (
            self.runtime_file_count == RUNTIME_BUNDLE_FILE_COUNT
            and self.runtime_total_bytes == RUNTIME_BUNDLE_TOTAL_BYTES
            and self.runtime_tree_manifest_sha256 == RUNTIME_TREE_MANIFEST_SHA256
            and self.runtime_manifest_sha256 == RUNTIME_MANIFEST_SHA256
            and self.input_file_count == 6
            and len(self.input_manifest_sha256) == 64
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
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_file_name_invalid",
            "Runtime-composition file name is not a safe flat Windows name.",
            actual=repr(name),
        )
    return name


def _validate_path_chain(path: Path, *, code_prefix: str) -> None:
    absolute = absolute_path(path)
    parts = absolute.parts
    if not parts:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
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
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                f"{code_prefix}_metadata_failed",
                "Filesystem path metadata could not be read.",
                actual=f"{current}:{type(exc).__name__}:{exc}",
            ) from exc
        if is_reparse_or_symlink(metadata):
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                f"{code_prefix}_reparse_point",
                "Filesystem path must not traverse a symlink or reparse point.",
                actual=str(current),
            )


def validate_developer_task_execution_runtime_composition_artifact_parent(
    artifact_parent: Path,
) -> Path:
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")
    parent = absolute_path(artifact_parent)
    try:
        validate_workspace_parent(parent)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            exc.code.replace("workspace_parent", "runtime_composition_artifact_parent"),
            "V1B4C2B artifact parent is unsafe.",
            actual=exc.actual,
            attempts=exc.attempts,
        ) from exc
    _validate_path_chain(parent, code_prefix="runtime_composition_artifact_parent")

    for ancestor in (parent, *parent.parents):
        git_path = ancestor / ".git"
        try:
            metadata = os.lstat(git_path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_artifact_parent_metadata_failed",
                "V1B4C2B artifact parent Git boundary could not be inspected.",
                actual=f"{git_path}:{type(exc).__name__}:{exc}",
            ) from exc
        if stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode) or is_reparse_or_symlink(metadata):
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_artifact_parent_inside_git_repository",
                "V1B4C2B artifacts must not be created inside a Git repository.",
                actual=str(parent),
            )
    return parent


def read_developer_task_execution_runtime_composition_artifact_bytes(
    path: Path,
    *,
    max_bytes: int,
    artifact_name: str,
    expected_size: int | None = None,
) -> tuple[bytes, str]:
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise TypeError("max_bytes must be a positive integer")
    if not isinstance(artifact_name, str) or not artifact_name:
        raise TypeError("artifact_name must be a non-empty string")
    if expected_size is not None and (type(expected_size) is not int or expected_size <= 0):
        raise TypeError("expected_size must be a positive integer or None")

    try:
        initial = os.lstat(path)
    except FileNotFoundError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_missing",
            "V1B4C2B artifact is missing.",
            actual=f"{artifact_name}:{path}",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_metadata_failed",
            "V1B4C2B artifact metadata could not be read.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc

    if not stat.S_ISREG(initial.st_mode):
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_not_regular",
            "V1B4C2B artifact must be a regular file.",
            actual=artifact_name,
        )
    if is_reparse_or_symlink(initial):
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_reparse_point",
            "V1B4C2B artifact must not be a symlink, junction, or reparse point.",
            actual=artifact_name,
        )
    if initial.st_size <= 0 or initial.st_size > max_bytes:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_size_invalid",
            "V1B4C2B artifact size is outside the accepted boundary.",
            actual=f"{artifact_name}:{initial.st_size}",
        )
    if expected_size is not None and initial.st_size != expected_size:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_size_invalid",
            "V1B4C2B artifact size does not match the exact expected size.",
            actual=f"{artifact_name}:{initial.st_size}!={expected_size}",
        )

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_open_failed",
            "V1B4C2B artifact could not be opened safely.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc

    content = bytearray()
    try:
        opened = os.fstat(descriptor)
        if _file_version(opened) != _file_version(initial):
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_artifact_changed_during_read",
                "V1B4C2B artifact changed before reading.",
                actual=artifact_name,
            )
        while True:
            remaining = max_bytes + 1 - len(content)
            if remaining <= 0:
                raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                    "runtime_composition_artifact_size_invalid",
                    "V1B4C2B artifact exceeded the accepted boundary while reading.",
                    actual=artifact_name,
                )
            chunk = os.read(descriptor, min(RUNTIME_COMPOSITION_READ_CHUNK_BYTES, remaining))
            if not chunk:
                break
            content.extend(chunk)
        completed = os.fstat(descriptor)
        if _file_version(completed) != _file_version(opened):
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_artifact_changed_during_read",
                "V1B4C2B artifact changed while reading.",
                actual=artifact_name,
            )
    except DeveloperTaskExecutionRuntimeCompositionFileSystemError:
        raise
    except OSError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_read_failed",
            "V1B4C2B artifact could not be read.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    finally:
        os.close(descriptor)

    try:
        final = os.lstat(path)
    except OSError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_changed_during_read",
            "V1B4C2B artifact disappeared after reading.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    if _file_version(final) != _file_version(initial):
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_changed_during_read",
            "V1B4C2B artifact changed after reading.",
            actual=artifact_name,
        )

    raw = bytes(content)
    return raw, _sha256(raw)


def _write_new_file(path: Path, data: bytes) -> None:
    if not isinstance(data, bytes) or not data:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_bytes_invalid",
            "V1B4C2B materialized bytes must be non-empty bytes.",
            actual=str(path),
        )
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_write_failed",
            "V1B4C2B artifact could not be written exclusively.",
            actual=f"{path}:{type(exc).__name__}:{exc}",
        ) from exc


def _exact_directory_names(root: Path) -> tuple[str, ...]:
    try:
        entries = tuple(sorted(os.listdir(root)))
    except OSError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_tree_scan_failed",
            "V1B4C2B materialized directory could not be scanned.",
            actual=f"{root}:{type(exc).__name__}:{exc}",
        ) from exc
    return entries


def _materialize_flat_exact_files(
    root: Path,
    files: Iterable[tuple[str, bytes]],
    *,
    code_prefix: str,
) -> tuple[DeveloperTaskExecutionRuntimeCompositionFileEvidence, ...]:
    prepared: list[tuple[str, bytes]] = []
    case_keys: dict[str, str] = {}
    for name, data in files:
        safe_name = _safe_flat_name(name)
        if not isinstance(data, bytes) or not data:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                f"{code_prefix}_bytes_invalid",
                "Materialized file bytes must be non-empty.",
                actual=safe_name,
            )
        case_key = safe_name.casefold()
        if case_key in case_keys:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                f"{code_prefix}_case_collision",
                "Materialized file names collide under Windows casing rules.",
                actual=f"{case_keys[case_key]}|{safe_name}",
            )
        case_keys[case_key] = safe_name
        prepared.append((safe_name, data))

    prepared.sort(key=lambda item: item[0])
    if _exact_directory_names(root):
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            f"{code_prefix}_root_not_empty",
            "Materialization root must be empty.",
            actual=str(root),
        )

    for name, data in prepared:
        _write_new_file(root / name, data)

    actual_names = _exact_directory_names(root)
    expected_names = tuple(name for name, _ in prepared)
    if actual_names != expected_names:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            f"{code_prefix}_file_set_mismatch",
            "Materialized directory file set does not match exact expected names.",
            actual=repr(actual_names),
        )

    evidence: list[DeveloperTaskExecutionRuntimeCompositionFileEvidence] = []
    for name, expected in prepared:
        raw, sha256 = read_developer_task_execution_runtime_composition_artifact_bytes(
            root / name,
            max_bytes=max(len(expected), 1),
            artifact_name=name,
            expected_size=len(expected),
        )
        if raw != expected or sha256 != _sha256(expected):
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                f"{code_prefix}_post_write_mismatch",
                "Materialized file bytes changed during disk round-trip.",
                actual=name,
            )
        evidence.append(
            DeveloperTaskExecutionRuntimeCompositionFileEvidence(
                path=name,
                size_bytes=len(raw),
                sha256=sha256,
            )
        )
    return tuple(evidence)


def _manifest_sha256(
    files: tuple[DeveloperTaskExecutionRuntimeCompositionFileEvidence, ...],
) -> str:
    return _sha256(_canonical_json_bytes([item.to_dict() for item in files]))


def _allocate_run_root(parent: Path, request_id: str) -> Path:
    for _ in range(RUNTIME_COMPOSITION_ROOT_ALLOCATION_ATTEMPTS):
        candidate = parent / (
            f"{RUNTIME_COMPOSITION_ARTIFACT_PREFIX}{request_id[:8]}-{secrets.token_hex(8)}"
        )
        try:
            candidate.mkdir(mode=0o700, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
        except OSError as exc:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_artifact_root_create_failed",
                "V1B4C2B artifact root could not be created.",
                actual=f"{type(exc).__name__}:{exc}",
            ) from exc
    raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
        "runtime_composition_artifact_root_collision",
        "A unique V1B4C2B artifact root could not be allocated.",
    )


def _default_windows_host_path(path: Path) -> str:
    return str(path)


def prepare_developer_task_execution_runtime_composition_artifacts(
    *,
    artifact_parent: Path,
    runtime_bundle: DeveloperTaskPythonRuntimeBundle,
    payload_bundle: DeveloperTaskRuntimeAttestationPayloadBundle,
    request_id: str,
    host_nonce: str,
    created_at_epoch_seconds: float,
    host_path_mapper: Callable[[Path], str] = _default_windows_host_path,
) -> DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts:
    if not isinstance(runtime_bundle, DeveloperTaskPythonRuntimeBundle):
        raise TypeError("runtime_bundle must be DeveloperTaskPythonRuntimeBundle")
    if not isinstance(payload_bundle, DeveloperTaskRuntimeAttestationPayloadBundle):
        raise TypeError("payload_bundle must be DeveloperTaskRuntimeAttestationPayloadBundle")
    if not runtime_bundle.ok:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_runtime_bundle_invalid",
            "A genuine successful V1B4B runtime capability is required.",
        )
    if not payload_bundle.ok:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_payload_bundle_invalid",
            "A genuine successful V1B4C1 payload capability is required.",
        )
    if not callable(host_path_mapper):
        raise TypeError("host_path_mapper must be callable")

    parent = validate_developer_task_execution_runtime_composition_artifact_parent(
        artifact_parent
    )
    root = _allocate_run_root(parent, request_id)
    root_metadata = os.lstat(root)
    try:
        input_root = root / "input"
        runtime_root = root / "runtime"
        control_root = root / "control"
        output_root = root / "output"
        for directory in (input_root, runtime_root, control_root, output_root):
            directory.mkdir(mode=0o700, exist_ok=False)

        runtime_files = _materialize_flat_exact_files(
            runtime_root,
            (
                (name, runtime_bundle.exact_file_bytes(name))
                for name in runtime_bundle.file_names
            ),
            code_prefix="runtime_composition_runtime",
        )
        if (
            len(runtime_files) != RUNTIME_BUNDLE_FILE_COUNT
            or sum(item.size_bytes for item in runtime_files) != RUNTIME_BUNDLE_TOTAL_BYTES
            or _manifest_sha256(runtime_files) != RUNTIME_TREE_MANIFEST_SHA256
        ):
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_runtime_tree_mismatch",
                "Materialized V1B4B runtime tree identity changed.",
            )
        runtime_manifest = next(
            (item for item in runtime_files if item.path == RUNTIME_MANIFEST_FILE_NAME),
            None,
        )
        if runtime_manifest is None or runtime_manifest.sha256 != RUNTIME_MANIFEST_SHA256:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_runtime_manifest_mismatch",
                "Materialized V1B4B runtime manifest identity changed.",
            )

        wsb_bytes = build_runtime_attestation_wsb_config(
            input_host_path=host_path_mapper(input_root),
            runtime_host_path=host_path_mapper(runtime_root),
            control_host_path=host_path_mapper(control_root),
            output_host_path=host_path_mapper(output_root),
        )
        input_payloads = (
            (
                RUNTIME_ATTESTATION_POLICY_FILE_NAME,
                payload_bundle.exact_bytes(RUNTIME_ATTESTATION_POLICY_FILE_NAME),
            ),
            (
                RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME,
                payload_bundle.exact_bytes(RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME),
            ),
            (
                RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME,
                payload_bundle.exact_bytes(RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME),
            ),
            (
                RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME,
                payload_bundle.exact_bytes(RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME),
            ),
            (RUNTIME_ATTESTATION_WSB_FILE_NAME, wsb_bytes),
        )
        input_files_without_request = _materialize_flat_exact_files(
            input_root,
            input_payloads,
            code_prefix="runtime_composition_input",
        )

        payload_hashes = {item.path: item.sha256 for item in input_files_without_request}
        request = build_runtime_attestation_request(
            request_id=request_id,
            host_nonce=host_nonce,
            created_at_epoch_seconds=created_at_epoch_seconds,
            policy_sha256=payload_hashes[RUNTIME_ATTESTATION_POLICY_FILE_NAME],
            bootstrap_sha256=payload_hashes[RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME],
            controller_sha256=payload_hashes[RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME],
            native_helper_sha256=payload_hashes[RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME],
            wsb_sha256=payload_hashes[RUNTIME_ATTESTATION_WSB_FILE_NAME],
        )
        request_path = input_root / RUNTIME_ATTESTATION_REQUEST_FILE_NAME
        _write_new_file(request_path, request.canonical_bytes)
        request_raw, request_sha256 = read_developer_task_execution_runtime_composition_artifact_bytes(
            request_path,
            max_bytes=RUNTIME_ATTESTATION_REQUEST_MAX_BYTES,
            artifact_name=RUNTIME_ATTESTATION_REQUEST_FILE_NAME,
            expected_size=len(request.canonical_bytes),
        )
        if request_raw != request.canonical_bytes or request_sha256 != request.sha256:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_request_post_write_mismatch",
                "Materialized V1B4C request changed during disk round-trip.",
            )

        input_files = tuple(
            sorted(
                (
                    *input_files_without_request,
                    DeveloperTaskExecutionRuntimeCompositionFileEvidence(
                        path=RUNTIME_ATTESTATION_REQUEST_FILE_NAME,
                        size_bytes=len(request_raw),
                        sha256=request_sha256,
                    ),
                ),
                key=lambda item: item.path,
            )
        )
        if _exact_directory_names(control_root) or _exact_directory_names(output_root):
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_mutable_root_not_empty",
                "Control and output roots must be empty before Sandbox launch.",
            )

        return DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts(
            root=root,
            root_metadata=root_metadata,
            input_root=input_root,
            runtime_root=runtime_root,
            control_root=control_root,
            output_root=output_root,
            request_path=request_path,
            ready_path=output_root / RUNTIME_ATTESTATION_READY_FILE_NAME,
            authorize_path=control_root / RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME,
            authorize_commit_path=control_root / RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME,
            runtime_result_path=output_root / RUNTIME_ATTESTATION_RESULT_FILE_NAME,
            terminal_payload_path=output_root / RUNTIME_ATTESTATION_TERMINAL_FILE_NAME,
            terminal_signature_path=output_root / RUNTIME_ATTESTATION_SIGNATURE_FILE_NAME,
            bootstrap_failure_path=output_root / RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME,
            controller_failure_path=output_root / RUNTIME_ATTESTATION_CONTROLLER_FAILURE_FILE_NAME,
            policy_path=input_root / RUNTIME_ATTESTATION_POLICY_FILE_NAME,
            bootstrap_path=input_root / RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME,
            controller_path=input_root / RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME,
            native_helper_path=input_root / RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME,
            wsb_path=input_root / RUNTIME_ATTESTATION_WSB_FILE_NAME,
            request=request,
            runtime_files=runtime_files,
            input_files=input_files,
            runtime_bundle=runtime_bundle,
            payload_bundle=payload_bundle,
            wsb_bytes=wsb_bytes,
        )
    except Exception as original:
        try:
            remove_developer_task_execution_runtime_composition_artifacts(
                root,
                artifact_parent=parent,
                initial_metadata=root_metadata,
            )
        except Exception as cleanup_error:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_artifact_preparation_cleanup_failed",
                "Partially prepared V1B4C2B artifacts could not be removed safely.",
                actual=f"{type(cleanup_error).__name__}:{cleanup_error}",
            ) from original
        raise


def verify_developer_task_execution_runtime_composition_materialization(
    prepared: DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts,
) -> DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence:
    if not isinstance(prepared, DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts):
        raise TypeError(
            "prepared must be DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts"
        )
    if prepared.runtime_bundle.report.bundle_fingerprint != RUNTIME_BUNDLE_FINGERPRINT:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_runtime_bundle_mismatch",
            "Prepared runtime capability does not match the pinned V1B4B identity.",
        )

    actual_runtime_names = _exact_directory_names(prepared.runtime_root)
    if actual_runtime_names != prepared.runtime_bundle.file_names:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_runtime_file_set_mismatch",
            "Prepared runtime file set changed.",
            actual=repr(actual_runtime_names),
        )
    runtime_evidence: list[DeveloperTaskExecutionRuntimeCompositionFileEvidence] = []
    for name in prepared.runtime_bundle.file_names:
        expected = prepared.runtime_bundle.exact_file_bytes(name)
        raw, sha256 = read_developer_task_execution_runtime_composition_artifact_bytes(
            prepared.runtime_root / name,
            max_bytes=max(len(expected), 1),
            artifact_name=name,
            expected_size=len(expected),
        )
        if raw != expected:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_runtime_file_changed",
                "Prepared runtime file bytes changed.",
                actual=name,
            )
        runtime_evidence.append(
            DeveloperTaskExecutionRuntimeCompositionFileEvidence(
                path=name,
                size_bytes=len(raw),
                sha256=sha256,
            )
        )
    runtime_files = tuple(runtime_evidence)
    runtime_tree_manifest_sha256 = _manifest_sha256(runtime_files)
    runtime_manifest_sha256 = next(
        item.sha256 for item in runtime_files if item.path == RUNTIME_MANIFEST_FILE_NAME
    )

    expected_input: dict[str, bytes] = {
        RUNTIME_ATTESTATION_POLICY_FILE_NAME: prepared.payload_bundle.exact_bytes(
            RUNTIME_ATTESTATION_POLICY_FILE_NAME
        ),
        RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME: prepared.payload_bundle.exact_bytes(
            RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME
        ),
        RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME: prepared.payload_bundle.exact_bytes(
            RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME
        ),
        RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME: prepared.payload_bundle.exact_bytes(
            RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME
        ),
        RUNTIME_ATTESTATION_WSB_FILE_NAME: prepared.wsb_bytes,
        RUNTIME_ATTESTATION_REQUEST_FILE_NAME: prepared.request.canonical_bytes,
    }
    actual_input_names = _exact_directory_names(prepared.input_root)
    expected_input_names = tuple(sorted(expected_input))
    if actual_input_names != expected_input_names:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_input_file_set_mismatch",
            "Prepared trusted input file set changed.",
            actual=repr(actual_input_names),
        )
    input_evidence: list[DeveloperTaskExecutionRuntimeCompositionFileEvidence] = []
    for name in expected_input_names:
        expected = expected_input[name]
        raw, sha256 = read_developer_task_execution_runtime_composition_artifact_bytes(
            prepared.input_root / name,
            max_bytes=max(len(expected), 1),
            artifact_name=name,
            expected_size=len(expected),
        )
        if raw != expected:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_input_file_changed",
                "Prepared trusted input bytes changed.",
                actual=name,
            )
        input_evidence.append(
            DeveloperTaskExecutionRuntimeCompositionFileEvidence(
                path=name,
                size_bytes=len(raw),
                sha256=sha256,
            )
        )

    evidence = DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence(
        runtime_file_count=len(runtime_files),
        runtime_total_bytes=sum(item.size_bytes for item in runtime_files),
        runtime_tree_manifest_sha256=runtime_tree_manifest_sha256,
        runtime_manifest_sha256=runtime_manifest_sha256,
        input_file_count=len(input_evidence),
        input_manifest_sha256=_manifest_sha256(tuple(input_evidence)),
        regular_files_verified=True,
        reparse_points_absent=True,
    )
    if not evidence.ok:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_materialization_identity_mismatch",
            "Prepared V1B4C2B materialization no longer matches pinned identities.",
            actual=json.dumps(evidence.to_dict(), ensure_ascii=False, sort_keys=True),
        )
    return evidence


def publish_developer_task_execution_runtime_composition_authorization(
    authorize_path: Path,
    authorize_bytes: bytes,
) -> tuple[str, str]:
    if not isinstance(authorize_path, Path):
        raise TypeError("authorize_path must be pathlib.Path")
    if not isinstance(authorize_bytes, bytes) or not authorize_bytes:
        raise TypeError("authorize_bytes must be non-empty bytes")
    commit_path = authorize_path.with_name(RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME)
    existing = tuple(
        str(path) for path in (authorize_path, commit_path) if os.path.lexists(path)
    )
    if existing:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_authorization_already_exists",
            "Authorization data or commit marker already exists before publication.",
            actual=",".join(existing),
        )

    authorize_sha256 = _sha256(authorize_bytes)
    commit_bytes = authorize_sha256.encode("ascii")
    try:
        _write_new_file(authorize_path, authorize_bytes)
        published, published_sha256 = (
            read_developer_task_execution_runtime_composition_artifact_bytes(
                authorize_path,
                max_bytes=RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES,
                artifact_name=RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME,
                expected_size=len(authorize_bytes),
            )
        )
        if published != authorize_bytes or published_sha256 != authorize_sha256:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_authorization_publish_verification_failed",
                "Published authorization bytes do not match the pinned bytes.",
                actual=str(authorize_path),
            )
        # The exact 64-byte hash marker is the publication linearization point.
        # Do not perform fallible filesystem I/O after this exclusive create.
        _write_new_file(commit_path, commit_bytes)
    except DeveloperTaskExecutionRuntimeCompositionFileSystemError as exc:
        if exc.code.startswith("runtime_composition_authorization_"):
            raise
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_authorization_publish_failed",
            "Authorization could not be published with its hash commit marker.",
            actual=f"{exc.code}:{exc.actual}",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_authorization_publish_failed",
            "Authorization could not be published with its hash commit marker.",
            actual=f"{type(exc).__name__}:{exc}",
        ) from exc
    return authorize_sha256, _sha256(commit_bytes)


def remove_developer_task_execution_runtime_composition_artifacts(
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
        or not root_resolved.name.startswith(RUNTIME_COMPOSITION_ARTIFACT_PREFIX)
    ):
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_cleanup_scope_invalid",
            "V1B4C2B artifact cleanup target is outside the verified scope.",
            actual=str(root_resolved),
        )
    try:
        removal = remove_verified_workspace(root_resolved, initial_metadata)
    except DeveloperTaskWorkspaceCleanupFileSystemError as exc:
        raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
            "runtime_composition_artifact_cleanup_failed",
            "V1B4C2B artifact cleanup failed.",
            actual=f"{exc.code}:{exc.actual};attempts={exc.attempts}",
            attempts=exc.attempts,
        ) from exc
    return removal.attempts
