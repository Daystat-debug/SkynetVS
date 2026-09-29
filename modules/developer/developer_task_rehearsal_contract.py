from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_contract import DeveloperTaskCheck


DTRB_POLICY_ID = "skynetvs-dtrb-static-rehearsal-orchestrator-v1"
DTRB_SUCCESS_STATUS = "STATIC_REHEARSAL_RECORDED_NOT_PROMOTABLE"
DTRB_REJECTED_CLEAN_STATUS = "REHEARSAL_REJECTED_CLEAN"
DTRB_FAILED_CLEAN_STATUS = "REHEARSAL_FAILED_CLEAN"
DTRB_STOP_REVIEW_STATUS = "REHEARSAL_STOP_REVIEW_REQUIRED"
DTRB_BEHAVIORAL_NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class DeveloperTaskRehearsalIssue:
    code: str
    stage: str
    message: str
    actual: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {
            "code": self.code,
            "stage": self.stage,
            "message": self.message,
        }
        if self.actual:
            payload["actual"] = self.actual
        return payload


@dataclass(frozen=True, slots=True)
class DeveloperTaskRehearsalArtifactLayout:
    run_id: str
    artifact_root: str
    task_root: str
    workspace_parent: str
    patch_path: str
    result_path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "artifact_root": self.artifact_root,
            "task_root": self.task_root,
            "workspace_parent": self.workspace_parent,
            "patch_path": self.patch_path,
            "result_path": self.result_path,
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskRehearsalStageEvidence:
    stage: str
    ok: bool
    payload_sha256: str
    payload_json: str

    def payload_dict(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("stage evidence payload must decode to an object")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "payload_sha256": self.payload_sha256,
            "payload": self.payload_dict(),
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskStaticRehearsalReport:
    policy_id: str
    run_id: str
    status: str
    terminal_stage: str
    task_fingerprint: str
    request_fingerprint: str
    raw_response_sha256: str
    patch_sha256: str
    manifest_fingerprint: str
    base_commit: str
    target_path: str
    artifact: DeveloperTaskRehearsalArtifactLayout | None
    stage_evidence: tuple[DeveloperTaskRehearsalStageEvidence, ...]
    completed_checks: tuple[str, ...]
    pending_executable_checks: tuple[DeveloperTaskCheck, ...]
    source_snapshot_before: str
    source_snapshot_after: str
    source_repository_unchanged: bool
    workspace_removed: bool
    patch_materialized: bool
    patch_applied_in_isolated_workspace: bool
    result_recorded: bool
    all_required_checks_passed: bool
    behavioral_correctness: str
    ready_to_promote: bool
    authority_granted: bool
    runtime_authorized: bool
    promotion_authorized: bool
    model_provider_called: bool
    network: bool
    sandbox: bool
    native_worker_launched: bool
    changed_code_executed: bool
    issues: tuple[DeveloperTaskRehearsalIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            self.policy_id == DTRB_POLICY_ID
            and self.status == DTRB_SUCCESS_STATUS
            and bool(self.run_id)
            and bool(self.task_fingerprint)
            and bool(self.request_fingerprint)
            and bool(self.raw_response_sha256)
            and bool(self.patch_sha256)
            and bool(self.manifest_fingerprint)
            and bool(self.base_commit)
            and bool(self.target_path)
            and self.artifact is not None
            and self.patch_materialized
            and self.patch_applied_in_isolated_workspace
            and self.result_recorded
            and self.source_repository_unchanged
            and self.workspace_removed
            and "git_diff_check" in self.completed_checks
            and "py_compile" in self.completed_checks
            and len(self.pending_executable_checks) == 1
            and self.pending_executable_checks[0].type == "pipeline"
            and self.pending_executable_checks[0].flow == "check"
            and not self.all_required_checks_passed
            and self.behavioral_correctness == DTRB_BEHAVIORAL_NOT_EVALUATED
            and not self.ready_to_promote
            and not self.authority_granted
            and not self.runtime_authorized
            and not self.promotion_authorized
            and not self.model_provider_called
            and not self.network
            and not self.sandbox
            and not self.native_worker_launched
            and not self.changed_code_executed
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "policy_id": self.policy_id,
            "run_id": self.run_id,
            "status": self.status,
            "terminal_stage": self.terminal_stage,
            "task_fingerprint": self.task_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "raw_response_sha256": self.raw_response_sha256,
            "patch_sha256": self.patch_sha256,
            "manifest_fingerprint": self.manifest_fingerprint,
            "base_commit": self.base_commit,
            "target_path": self.target_path,
            "artifact": self.artifact.to_dict() if self.artifact is not None else None,
            "stage_evidence": [item.to_dict() for item in self.stage_evidence],
            "completed_checks": list(self.completed_checks),
            "pending_executable_checks": [item.to_dict() for item in self.pending_executable_checks],
            "source_snapshot_before": self.source_snapshot_before,
            "source_snapshot_after": self.source_snapshot_after,
            "source_repository_unchanged": self.source_repository_unchanged,
            "workspace_removed": self.workspace_removed,
            "patch_materialized": self.patch_materialized,
            "patch_applied_in_isolated_workspace": self.patch_applied_in_isolated_workspace,
            "result_recorded": self.result_recorded,
            "all_required_checks_passed": self.all_required_checks_passed,
            "behavioral_correctness": self.behavioral_correctness,
            "ready_to_promote": self.ready_to_promote,
            "authority_granted": self.authority_granted,
            "runtime_authorized": self.runtime_authorized,
            "promotion_authorized": self.promotion_authorized,
            "model_provider_called": self.model_provider_called,
            "network": self.network,
            "sandbox": self.sandbox,
            "native_worker_launched": self.native_worker_launched,
            "changed_code_executed": self.changed_code_executed,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


def canonical_rehearsal_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", "strict")


def rehearsal_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stage_evidence(
    stage: str,
    *,
    ok: bool,
    payload: dict[str, Any],
) -> DeveloperTaskRehearsalStageEvidence:
    raw = canonical_rehearsal_json_bytes(payload)
    return DeveloperTaskRehearsalStageEvidence(
        stage=stage,
        ok=ok,
        payload_sha256=rehearsal_sha256(raw),
        payload_json=raw.decode("utf-8"),
    )
