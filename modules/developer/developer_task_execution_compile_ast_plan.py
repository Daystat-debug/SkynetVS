from __future__ import annotations

"""V1C1B host-only typed capability for a future compile/AST Sandbox gate."""

import hashlib
import hmac
import json
import secrets
import threading
import time
import weakref

from dataclasses import dataclass, field
from typing import Any

from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_ENCODINGS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_LINE_ENDINGS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_AST_MODE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_CLOCK_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_COMPILE_MODE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_REQUIRED_FILE_MODE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SECRET_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SNAPSHOT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_TTL_SECONDS,
    validate_developer_task_execution_compile_ast_plan_policy,
)
from modules.developer.developer_task_execution_workspace_snapshot import (
    DeveloperTaskExecutionWorkspaceSnapshot,
    DeveloperTaskExecutionWorkspaceSnapshotEntry,
    DeveloperTaskExecutionWorkspaceSnapshotError,
    DeveloperTaskExecutionWorkspaceSnapshotMaterial,
)


COMPILE_AST_PLAN_STATE_ISSUED = "issued"
COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE = "claimed_for_compile_ast_gate"
COMPILE_AST_PLAN_STATE_EXPIRED = "expired"
COMPILE_AST_PLAN_STATE_INVALIDATED = "invalidated"

_CONSTRUCTOR_KEY = object()
_MATERIAL_CONSTRUCTOR_KEY = object()
_ISSUER_ID = object()
_ISSUER_SECRET = secrets.token_bytes(32)
_REGISTRY_LOCK = threading.RLock()


class DeveloperTaskExecutionCompileAstPlanError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        self.code = code
        self.message = message
        self.actual = actual
        super().__init__(message)


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstPlanSource:
    path: str
    mode: str
    size_bytes: int
    sha256: str
    encoding: str
    line_endings: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "mode": self.mode,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "encoding": self.encoding,
            "line_endings": self.line_endings,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstPlanReport:
    policy_id: str
    policy_fingerprint: str
    operation: str
    snapshot_policy_fingerprint: str
    snapshot_fingerprint: str
    manifest_fingerprint: str
    workspace_id: str
    base_commit: str
    patch_sha256: str
    result_tree: str
    changed_files: tuple[str, ...]
    selected_python_files: tuple[str, ...]
    deleted_python_files: tuple[str, ...]
    changed_non_python_files: tuple[str, ...]
    selected_file_count: int
    selected_total_bytes: int
    sources: tuple[DeveloperTaskExecutionCompileAstPlanSource, ...]
    source_manifest_sha256: str
    plan_fingerprint: str
    snapshot_consumed: bool
    repository_mutated: bool = False
    network_attempted: bool = False
    artifact_download_attempted: bool = False
    dependency_install_attempted: bool = False
    sandbox_launched: bool = False
    runtime_lease_issued: bool = False
    runtime_lease_claimed: bool = False
    candidate_interpreter_executed: bool = False
    changed_code_executed: bool = False
    reusable_lease_issued: bool = False
    execution_authorized: bool = False

    @property
    def ok(self) -> bool:
        return (
            self.policy_id == DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID
            and self.policy_fingerprint == DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT
            and self.operation == DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION
            and self.snapshot_policy_fingerprint == DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SNAPSHOT_POLICY_FINGERPRINT
            and len(self.snapshot_fingerprint) == 64
            and len(self.manifest_fingerprint) == 64
            and bool(self.workspace_id)
            and bool(self.base_commit)
            and len(self.patch_sha256) == 64
            and bool(self.result_tree)
            and bool(self.changed_files)
            and self.selected_file_count == len(self.selected_python_files) == len(self.sources)
            and 1 <= self.selected_file_count <= DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT
            and 0 <= self.selected_total_bytes <= DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES
            and tuple(item.path for item in self.sources) == self.selected_python_files
            and all(item.mode == DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_REQUIRED_FILE_MODE for item in self.sources)
            and all(item.encoding in DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_ENCODINGS for item in self.sources)
            and all(item.line_endings in DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_LINE_ENDINGS for item in self.sources)
            and sum(item.size_bytes for item in self.sources) == self.selected_total_bytes
            and len(self.source_manifest_sha256) == 64
            and len(self.plan_fingerprint) == 64
            and self.snapshot_consumed
            and not any((
                self.repository_mutated,
                self.network_attempted,
                self.artifact_download_attempted,
                self.dependency_install_attempted,
                self.sandbox_launched,
                self.runtime_lease_issued,
                self.runtime_lease_claimed,
                self.candidate_interpreter_executed,
                self.changed_code_executed,
                self.reusable_lease_issued,
                self.execution_authorized,
            ))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "operation": self.operation,
            "snapshot_policy_fingerprint": self.snapshot_policy_fingerprint,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "manifest_fingerprint": self.manifest_fingerprint,
            "workspace_id": self.workspace_id,
            "base_commit": self.base_commit,
            "patch_sha256": self.patch_sha256,
            "result_tree": self.result_tree,
            "changed_files": list(self.changed_files),
            "selected_python_files": list(self.selected_python_files),
            "deleted_python_files": list(self.deleted_python_files),
            "changed_non_python_files": list(self.changed_non_python_files),
            "selected_file_count": self.selected_file_count,
            "selected_total_bytes": self.selected_total_bytes,
            "sources": [item.to_dict() for item in self.sources],
            "source_manifest_sha256": self.source_manifest_sha256,
            "plan_fingerprint": self.plan_fingerprint,
            "snapshot_consumed": self.snapshot_consumed,
            "repository_mutated": False,
            "network_attempted": False,
            "artifact_download_attempted": False,
            "dependency_install_attempted": False,
            "sandbox_launched": False,
            "runtime_lease_issued": False,
            "runtime_lease_claimed": False,
            "candidate_interpreter_executed": False,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstPlanStatus:
    state: str
    plan_fingerprint: str
    selected_file_count: int
    selected_total_bytes: int
    policy_id: str = DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID
    policy_fingerprint: str = DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT
    ttl_seconds: int = DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_TTL_SECONDS
    execution_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "plan_fingerprint": self.plan_fingerprint,
            "selected_file_count": self.selected_file_count,
            "selected_total_bytes": self.selected_total_bytes,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "ttl_seconds": self.ttl_seconds,
            "execution_authorized": False,
        }


@dataclass
class _PlanState:
    state: str
    sources: tuple[DeveloperTaskExecutionCompileAstPlanSource, ...] | None
    exact_sources: dict[str, bytes] | None
    issued_at_ns: int
    expires_at_ns: int
    secret: bytes
    binding_fingerprint: str
    issuer_id: object
    lock: threading.RLock = field(default_factory=threading.RLock)


@dataclass(frozen=True)
class _PlanServices:
    monotonic_ns: Any = time.monotonic_ns
    token_bytes: Any = secrets.token_bytes


_SERVICES = _PlanServices()
_REGISTRY: weakref.WeakKeyDictionary[
    DeveloperTaskExecutionCompileAstPlan,
    _PlanState,
] = weakref.WeakKeyDictionary()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_python_path(path: str) -> bool:
    return path.casefold().endswith(".py")


def _source_manifest_bytes(
    sources: tuple[DeveloperTaskExecutionCompileAstPlanSource, ...],
) -> bytes:
    return _canonical_json_bytes([item.to_dict() for item in sources])


def _plan_fingerprint(
    snapshot_report: Any,
    *,
    selected_python_files: tuple[str, ...],
    deleted_python_files: tuple[str, ...],
    changed_non_python_files: tuple[str, ...],
    source_manifest_sha256: str,
) -> str:
    return _sha256(_canonical_json_bytes({
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
        "snapshot_policy_fingerprint": snapshot_report.policy_fingerprint,
        "snapshot_fingerprint": snapshot_report.snapshot_fingerprint,
        "manifest_fingerprint": snapshot_report.manifest_fingerprint,
        "workspace_id": snapshot_report.workspace_id,
        "base_commit": snapshot_report.base_commit,
        "patch_sha256": snapshot_report.patch_sha256,
        "result_tree": snapshot_report.result_tree,
        "changed_files": list(snapshot_report.changed_files),
        "selected_python_files": list(selected_python_files),
        "deleted_python_files": list(deleted_python_files),
        "changed_non_python_files": list(changed_non_python_files),
        "source_manifest_sha256": source_manifest_sha256,
    }))


def _binding_fingerprint(report: DeveloperTaskExecutionCompileAstPlanReport) -> str:
    return _sha256(_canonical_json_bytes({
        "policy_fingerprint": report.policy_fingerprint,
        "operation": report.operation,
        "snapshot_fingerprint": report.snapshot_fingerprint,
        "plan_fingerprint": report.plan_fingerprint,
        "source_manifest_sha256": report.source_manifest_sha256,
        "selected_file_count": report.selected_file_count,
        "selected_total_bytes": report.selected_total_bytes,
    }))


def _claim_guard(secret: bytes, binding_fingerprint: str) -> bytes:
    return hmac.new(
        _ISSUER_SECRET,
        secret + binding_fingerprint.encode("ascii"),
        hashlib.sha256,
    ).digest()


def _invalidate_state(state: _PlanState, terminal_state: str) -> None:
    state.state = terminal_state
    state.sources = None
    state.exact_sources = None
    state.issued_at_ns = 0
    state.expires_at_ns = 0
    state.secret = b""
    state.binding_fingerprint = ""
    state.issuer_id = object()


def _validate_snapshot_before_claim(snapshot: DeveloperTaskExecutionWorkspaceSnapshot) -> None:
    if type(snapshot) is not DeveloperTaskExecutionWorkspaceSnapshot:
        raise TypeError("snapshot must be DeveloperTaskExecutionWorkspaceSnapshot")
    report = snapshot.report
    if not report.ok:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_snapshot_invalid",
            "V1C1A snapshot report is not canonical and successful.",
        )
    if report.policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SNAPSHOT_POLICY_FINGERPRINT:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_snapshot_policy_mismatch",
            "V1C1A snapshot policy fingerprint does not match V1C1B.",
            actual=report.policy_fingerprint,
        )


def _validate_material_binding(
    material: DeveloperTaskExecutionWorkspaceSnapshotMaterial,
    snapshot: DeveloperTaskExecutionWorkspaceSnapshot,
) -> None:
    if type(material) is not DeveloperTaskExecutionWorkspaceSnapshotMaterial:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_snapshot_material_invalid",
            "V1C1A snapshot claim returned an invalid material type.",
        )
    if material.report is not snapshot.report:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_snapshot_material_invalid",
            "V1C1A snapshot material is not bound to the supplied snapshot report.",
        )
    if material.paths != tuple(item.path for item in snapshot.report.files):
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_snapshot_material_invalid",
            "V1C1A snapshot material path manifest changed during handoff.",
        )


class DeveloperTaskExecutionCompileAstPlanMaterial:
    __slots__ = ("report", "_sources", "_exact_sources")

    def __init__(
        self,
        constructor_key: object,
        report: DeveloperTaskExecutionCompileAstPlanReport,
        sources: tuple[DeveloperTaskExecutionCompileAstPlanSource, ...],
        exact_sources: dict[str, bytes],
    ) -> None:
        if constructor_key is not _MATERIAL_CONSTRUCTOR_KEY:
            raise TypeError("DeveloperTaskExecutionCompileAstPlanMaterial cannot be constructed directly")
        self.report = report
        self._sources = sources
        self._exact_sources = exact_sources

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self._sources)

    @property
    def sources(self) -> tuple[DeveloperTaskExecutionCompileAstPlanSource, ...]:
        return self._sources

    @property
    def selected_file_count(self) -> int:
        return len(self._sources)

    @property
    def selected_total_bytes(self) -> int:
        return sum(item.size_bytes for item in self._sources)

    @property
    def operation(self) -> str:
        return DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION

    def source(self, path: str) -> DeveloperTaskExecutionCompileAstPlanSource:
        if not isinstance(path, str):
            raise TypeError("path must be str")
        for item in self._sources:
            if item.path == path:
                return item
        raise KeyError(path)

    def exact_source_bytes(self, path: str) -> bytes:
        if not isinstance(path, str):
            raise TypeError("path must be str")
        try:
            return self._exact_sources[path]
        except KeyError as exc:
            raise KeyError(path) from exc

    def __copy__(self):
        raise TypeError("DeveloperTaskExecutionCompileAstPlanMaterial is non-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("DeveloperTaskExecutionCompileAstPlanMaterial is non-copyable")

    def __reduce__(self):
        raise TypeError("DeveloperTaskExecutionCompileAstPlanMaterial is non-serializable")

    def __reduce_ex__(self, protocol):
        raise TypeError("DeveloperTaskExecutionCompileAstPlanMaterial is non-serializable")

    def __getstate__(self):
        raise TypeError("DeveloperTaskExecutionCompileAstPlanMaterial is non-serializable")


class DeveloperTaskExecutionCompileAstPlan:
    __slots__ = ("_guard", "report", "__weakref__")

    def __init__(
        self,
        constructor_key: object,
        guard: bytes,
        report: DeveloperTaskExecutionCompileAstPlanReport,
    ) -> None:
        if constructor_key is not _CONSTRUCTOR_KEY:
            raise TypeError("DeveloperTaskExecutionCompileAstPlan cannot be constructed directly")
        if not isinstance(guard, bytes) or len(guard) != hashlib.sha256().digest_size:
            raise TypeError("invalid compile/AST plan guard")
        if type(report) is not DeveloperTaskExecutionCompileAstPlanReport or not report.ok:
            raise TypeError("invalid compile/AST plan report")
        self._guard = guard
        self.report = report

    @property
    def execution_authorized(self) -> bool:
        return False

    def status(self) -> DeveloperTaskExecutionCompileAstPlanStatus:
        return _compile_ast_plan_status(self)

    def claim_for_compile_ast_gate(self) -> DeveloperTaskExecutionCompileAstPlanMaterial:
        return _claim_developer_task_execution_compile_ast_plan(self)

    def __repr__(self) -> str:
        status = self.status()
        return (
            "DeveloperTaskExecutionCompileAstPlan("
            f"state={status.state!r}, plan_fingerprint={status.plan_fingerprint!r}, "
            "execution_authorized=False)"
        )

    def __copy__(self):
        raise TypeError("DeveloperTaskExecutionCompileAstPlan is non-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("DeveloperTaskExecutionCompileAstPlan is non-copyable")

    def __reduce__(self):
        raise TypeError("DeveloperTaskExecutionCompileAstPlan is non-serializable")

    def __reduce_ex__(self, protocol):
        raise TypeError("DeveloperTaskExecutionCompileAstPlan is non-serializable")

    def __getstate__(self):
        raise TypeError("DeveloperTaskExecutionCompileAstPlan is non-serializable")


def _compile_ast_plan_status(
    plan: DeveloperTaskExecutionCompileAstPlan,
) -> DeveloperTaskExecutionCompileAstPlanStatus:
    if type(plan) is not DeveloperTaskExecutionCompileAstPlan:
        raise TypeError("plan must be DeveloperTaskExecutionCompileAstPlan")
    with _REGISTRY_LOCK:
        state = _REGISTRY.get(plan)
    if state is None:
        return DeveloperTaskExecutionCompileAstPlanStatus(
            state=COMPILE_AST_PLAN_STATE_INVALIDATED,
            plan_fingerprint=plan.report.plan_fingerprint,
            selected_file_count=plan.report.selected_file_count,
            selected_total_bytes=plan.report.selected_total_bytes,
        )
    with state.lock:
        if state.state == COMPILE_AST_PLAN_STATE_ISSUED:
            now_ns = _SERVICES.monotonic_ns()
            if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
                _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            elif now_ns >= state.expires_at_ns:
                _invalidate_state(state, COMPILE_AST_PLAN_STATE_EXPIRED)
        return DeveloperTaskExecutionCompileAstPlanStatus(
            state=state.state,
            plan_fingerprint=plan.report.plan_fingerprint,
            selected_file_count=plan.report.selected_file_count,
            selected_total_bytes=plan.report.selected_total_bytes,
        )


def issue_developer_task_execution_compile_ast_plan(
    snapshot: DeveloperTaskExecutionWorkspaceSnapshot,
) -> DeveloperTaskExecutionCompileAstPlan:
    """Consume one V1C1A snapshot and issue a non-authorizing typed compile/AST plan."""
    _validate_snapshot_before_claim(snapshot)
    policy_errors = validate_developer_task_execution_compile_ast_plan_policy(
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY
    )
    if policy_errors:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_policy_invalid",
            "Canonical V1C1B policy is invalid.",
            actual=",".join(policy_errors),
        )

    try:
        material = snapshot.claim_for_plan()
    except DeveloperTaskExecutionWorkspaceSnapshotError as exc:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_snapshot_claim_failed",
            "V1C1A snapshot could not be atomically claimed for plan issuance.",
            actual=exc.code,
        ) from exc

    _validate_material_binding(material, snapshot)
    report = snapshot.report
    changed_files = tuple(report.changed_files)
    deleted_set = set(report.deleted_files)
    present_paths = set(material.paths)

    deleted_python_files = tuple(
        path for path in changed_files
        if _is_python_path(path) and path in deleted_set
    )
    changed_non_python_files = tuple(
        path for path in changed_files
        if not _is_python_path(path)
    )
    selected_python_files = tuple(
        path for path in changed_files
        if _is_python_path(path) and path not in deleted_set
    )

    if not selected_python_files:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_no_changed_python",
            "Compile/AST plan requires at least one changed Python path present in the result tree.",
        )
    if len(selected_python_files) > DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_file_count_exceeded",
            "Compile/AST plan selected too many Python files.",
            actual=str(len(selected_python_files)),
        )

    sources: list[DeveloperTaskExecutionCompileAstPlanSource] = []
    exact_sources: dict[str, bytes] = {}
    total_bytes = 0
    for path in selected_python_files:
        if path not in present_paths:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_selected_path_missing",
                "Changed Python path is missing from the exact V1C1A result tree.",
                actual=path,
            )
        snapshot_entry: DeveloperTaskExecutionWorkspaceSnapshotEntry = material.entry(path)
        if snapshot_entry.mode != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_REQUIRED_FILE_MODE:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_mode_rejected",
                "Selected Python source has a Git mode forbidden by V1C1B.",
                actual=f"{path}:{snapshot_entry.mode}",
            )
        if snapshot_entry.size_bytes > DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_BYTES:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_file_too_large",
                "Selected Python source exceeds the V1C1B per-file size limit.",
                actual=path,
            )
        content = material.exact_file_bytes(path)
        if len(content) != snapshot_entry.size_bytes or _sha256(content) != snapshot_entry.sha256:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_source_identity_mismatch",
                "Selected Python exact bytes do not match V1C1A file identity.",
                actual=path,
            )
        if b"\x00" in content:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_nul_rejected",
                "Selected Python source contains NUL bytes.",
                actual=path,
            )
        try:
            content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_encoding_rejected",
                "Selected Python source is not strict UTF-8.",
                actual=path,
            ) from exc
        if b"\r" in content:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_line_endings_rejected",
                "Selected Python source uses line endings outside the LF/none contract.",
                actual=path,
            )
        line_endings = "lf" if b"\n" in content else "none"
        total_bytes += len(content)
        if total_bytes > DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_total_bytes_exceeded",
                "Selected Python sources exceed the V1C1B total-byte limit.",
                actual=str(total_bytes),
            )
        sources.append(DeveloperTaskExecutionCompileAstPlanSource(
            path=path,
            mode=snapshot_entry.mode,
            size_bytes=len(content),
            sha256=snapshot_entry.sha256,
            encoding="utf-8",
            line_endings=line_endings,
        ))
        exact_sources[path] = content

    source_tuple = tuple(sources)
    source_manifest_sha256 = _sha256(_source_manifest_bytes(source_tuple))
    plan_fingerprint = _plan_fingerprint(
        report,
        selected_python_files=selected_python_files,
        deleted_python_files=deleted_python_files,
        changed_non_python_files=changed_non_python_files,
        source_manifest_sha256=source_manifest_sha256,
    )
    plan_report = DeveloperTaskExecutionCompileAstPlanReport(
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
        snapshot_policy_fingerprint=report.policy_fingerprint,
        snapshot_fingerprint=report.snapshot_fingerprint,
        manifest_fingerprint=report.manifest_fingerprint,
        workspace_id=report.workspace_id,
        base_commit=report.base_commit,
        patch_sha256=report.patch_sha256,
        result_tree=report.result_tree,
        changed_files=changed_files,
        selected_python_files=selected_python_files,
        deleted_python_files=deleted_python_files,
        changed_non_python_files=changed_non_python_files,
        selected_file_count=len(source_tuple),
        selected_total_bytes=total_bytes,
        sources=source_tuple,
        source_manifest_sha256=source_manifest_sha256,
        plan_fingerprint=plan_fingerprint,
        snapshot_consumed=True,
    )
    if not plan_report.ok:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_report_invalid",
            "Derived V1C1B report failed canonical validation.",
        )

    secret = _SERVICES.token_bytes(DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SECRET_BYTES)
    if type(secret) is not bytes or len(secret) != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SECRET_BYTES:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_secret_generation_failed",
            "V1C1B one-time capability secret generator returned invalid bytes.",
        )
    now_ns = _SERVICES.monotonic_ns()
    if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_clock_invalid",
            "Monotonic V1C1B clock returned an invalid value during issuance.",
        )
    expires_at_ns = now_ns + DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_TTL_SECONDS * 1_000_000_000
    binding_fingerprint = _binding_fingerprint(plan_report)
    guard = _claim_guard(secret, binding_fingerprint)
    plan = DeveloperTaskExecutionCompileAstPlan(_CONSTRUCTOR_KEY, guard, plan_report)
    state = _PlanState(
        state=COMPILE_AST_PLAN_STATE_ISSUED,
        sources=source_tuple,
        exact_sources=exact_sources,
        issued_at_ns=now_ns,
        expires_at_ns=expires_at_ns,
        secret=secret,
        binding_fingerprint=binding_fingerprint,
        issuer_id=_ISSUER_ID,
    )
    with _REGISTRY_LOCK:
        _REGISTRY[plan] = state
    return plan


def _claim_developer_task_execution_compile_ast_plan(
    plan: DeveloperTaskExecutionCompileAstPlan,
) -> DeveloperTaskExecutionCompileAstPlanMaterial:
    if type(plan) is not DeveloperTaskExecutionCompileAstPlan:
        raise TypeError("plan must be DeveloperTaskExecutionCompileAstPlan")
    with _REGISTRY_LOCK:
        state = _REGISTRY.get(plan)
    if state is None:
        raise DeveloperTaskExecutionCompileAstPlanError(
            "compile_ast_plan_unregistered",
            "Compile/AST plan capability is not registered in this process issuer.",
        )
    with state.lock:
        if state.state == COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_already_claimed",
                "Compile/AST plan capability has already been claimed.",
            )
        if state.state == COMPILE_AST_PLAN_STATE_EXPIRED:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_expired",
                "Compile/AST plan capability has expired.",
            )
        if state.state != COMPILE_AST_PLAN_STATE_ISSUED:
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_invalidated",
                "Compile/AST plan capability is permanently invalidated.",
            )
        now_ns = _SERVICES.monotonic_ns()
        if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_clock_invalid",
                "Monotonic V1C1B clock returned an invalid value during claim.",
            )
        if now_ns >= state.expires_at_ns:
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_EXPIRED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_expired",
                "Compile/AST plan capability has expired.",
            )
        sources = state.sources
        exact_sources = state.exact_sources
        if sources is None or exact_sources is None:
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_material_missing",
                "Compile/AST plan capability no longer retains selected exact source bytes.",
            )
        if (
            state.issuer_id is not _ISSUER_ID
            or len(state.secret) != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SECRET_BYTES
            or len(state.binding_fingerprint) != 64
            or state.binding_fingerprint != _binding_fingerprint(plan.report)
            or not hmac.compare_digest(plan._guard, _claim_guard(state.secret, state.binding_fingerprint))
        ):
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_issuer_binding_invalid",
                "Compile/AST plan issuer/secret binding is invalid.",
            )
        policy_errors = validate_developer_task_execution_compile_ast_plan_policy(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY
        )
        if policy_errors:
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_policy_invalid",
                "Canonical V1C1B policy changed before claim.",
                actual=",".join(policy_errors),
            )
        if tuple(item.path for item in sources) != tuple(sorted(exact_sources)):
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_material_invalid",
                "Retained V1C1B source manifest is inconsistent.",
            )
        if len(sources) != plan.report.selected_file_count:
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_material_invalid",
                "Retained V1C1B selected source count changed.",
            )
        for source in sources:
            content = exact_sources.get(source.path)
            if content is None or len(content) != source.size_bytes or _sha256(content) != source.sha256:
                _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
                raise DeveloperTaskExecutionCompileAstPlanError(
                    "compile_ast_plan_material_invalid",
                    "Retained V1C1B exact source bytes changed before claim.",
                    actual=source.path,
                )
        if _sha256(_source_manifest_bytes(sources)) != plan.report.source_manifest_sha256:
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_material_invalid",
                "Retained V1C1B source manifest fingerprint changed before claim.",
            )
        final_now_ns = _SERVICES.monotonic_ns()
        if not isinstance(final_now_ns, int) or isinstance(final_now_ns, bool) or final_now_ns < 0:
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_INVALIDATED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_clock_invalid",
                "Monotonic V1C1B clock returned an invalid final claim value.",
            )
        if final_now_ns >= state.expires_at_ns:
            _invalidate_state(state, COMPILE_AST_PLAN_STATE_EXPIRED)
            raise DeveloperTaskExecutionCompileAstPlanError(
                "compile_ast_plan_expired",
                "Compile/AST plan capability expired during atomic claim validation.",
            )
        material = DeveloperTaskExecutionCompileAstPlanMaterial(
            _MATERIAL_CONSTRUCTOR_KEY,
            plan.report,
            sources,
            exact_sources,
        )
        _invalidate_state(state, COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE)
        return material
