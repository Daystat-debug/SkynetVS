from __future__ import annotations

import hashlib
import json

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_contract import (
    DeveloperTaskCheck,
    DeveloperTaskManifest,
)


DTR_PROPOSAL_REQUEST_SCHEMA_VERSION = 1
DTR_PROPOSAL_KIND = "DTR_PATCH_PROPOSAL_V1"
DTR_PROPOSAL_SCHEMA_VERSION = 1
DTR_PROPOSAL_POLICY_ID = "skynetvs-dtra-proposal-rehearsal-bridge-v1"
DTR_PROPOSAL_PROFILE_ID = "DTR_ONE_PYTHON_MODIFY_V1"
DTR_PROPOSAL_TRANSPORT_MODE = "manual_import"
DTR_PROPOSAL_ORIGIN = "manual"
DTR_PROPOSAL_PATCH_FILE = "changes.patch"
DTR_PROPOSAL_SUCCESS_STATUS = "PROPOSAL_BOUND_NOT_AUTHORIZED"
DTR_PROPOSAL_REJECTED_STATUS = "PROPOSAL_REJECTED"

DTR_MAX_INSTRUCTION_UTF8_BYTES = 16 * 1024
DTR_MAX_CONTEXT_FILES = 4
DTR_MAX_CONTEXT_FILE_BYTES = 64 * 1024
DTR_MAX_CONTEXT_TOTAL_BYTES = 256 * 1024
DTR_MAX_TARGET_FILE_BYTES = 64 * 1024
DTR_MAX_RAW_RESPONSE_BYTES = 256 * 1024
DTR_MAX_PATCH_UTF8_BYTES = 128 * 1024
DTR_MAX_EXPLANATION_UTF8_BYTES = 8 * 1024
DTR_MAX_JSON_DEPTH = 8


@dataclass(frozen=True, slots=True)
class DeveloperTaskProposalContextInput:
    path: str
    mode: str
    git_blob_oid: str
    content: bytes | bytearray


@dataclass(frozen=True, slots=True)
class DeveloperTaskProposalBoundSource:
    path: str
    mode: str
    git_blob_oid: str
    content_sha256: str
    content_bytes: int
    content: bytes

    def binding_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "mode": self.mode,
            "git_blob_oid": self.git_blob_oid,
            "content_sha256": self.content_sha256,
            "content_bytes": self.content_bytes,
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskProposalRequest:
    schema_version: int
    policy_id: str
    profile_id: str
    transport_mode: str
    origin: str
    task_id: str
    title: str
    request_id: str
    instruction: str
    base_commit: str
    base_tree: str
    target_path: str
    context: tuple[DeveloperTaskProposalBoundSource, ...]
    context_digest: str
    checks: tuple[DeveloperTaskCheck, ...]
    install_policy: str
    request_fingerprint: str

    def binding_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        target = next(item for item in self.context if item.path == self.target_path)
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "profile_id": self.profile_id,
            "transport_mode": self.transport_mode,
            "origin": self.origin,
            "task_id": self.task_id,
            "title": self.title,
            "request_id": self.request_id,
            "instruction": self.instruction,
            "base_commit": self.base_commit,
            "base_tree": self.base_tree,
            "target_write_allowlist": [self.target_path],
            "context_digest": self.context_digest,
            "context": [item.binding_dict() for item in self.context],
            "target_preimage": target.binding_dict(),
            "checks": [item.to_dict() for item in self.checks],
            "install_policy": self.install_policy,
        }

        if include_fingerprint:
            payload["request_fingerprint"] = self.request_fingerprint

        return payload


@dataclass(frozen=True, slots=True)
class DeveloperTaskPatchProposal:
    kind: str
    schema_version: int
    request_id: str
    request_fingerprint: str
    raw_response_sha256: str
    raw_response_bytes: bytes
    patch_text: str
    patch_sha256: str
    patch_bytes: bytes
    explanation: str

    def evidence_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "request_fingerprint": self.request_fingerprint,
            "raw_response_sha256": self.raw_response_sha256,
            "raw_response_bytes": len(self.raw_response_bytes),
            "patch_sha256": self.patch_sha256,
            "patch_bytes": len(self.patch_bytes),
            "explanation": self.explanation,
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskProposalIssue:
    code: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskProposalPlan:
    request: DeveloperTaskProposalRequest
    proposal: DeveloperTaskPatchProposal
    manifest: DeveloperTaskManifest
    manifest_fingerprint: str
    status: str = DTR_PROPOSAL_SUCCESS_STATUS
    provider_authenticated: bool = False
    authority_granted: bool = False
    runtime_authorized: bool = False
    promotion_authorized: bool = False

    def evidence_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "request": self.request.binding_dict(),
            "proposal": self.proposal.evidence_dict(),
            "manifest": self.manifest.to_dict(),
            "manifest_fingerprint": self.manifest_fingerprint,
            "provider_authenticated": self.provider_authenticated,
            "authority_granted": self.authority_granted,
            "runtime_authorized": self.runtime_authorized,
            "promotion_authorized": self.promotion_authorized,
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskProposalIntakeResult:
    plan: DeveloperTaskProposalPlan | None
    issues: tuple[DeveloperTaskProposalIssue, ...]

    @property
    def ok(self) -> bool:
        return self.plan is not None and not self.issues

    @property
    def status(self) -> str:
        return (
            DTR_PROPOSAL_SUCCESS_STATUS
            if self.ok
            else DTR_PROPOSAL_REJECTED_STATUS
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "issues": [item.to_dict() for item in self.issues],
            "plan": self.plan.evidence_dict() if self.plan is not None else None,
        }


class DeveloperTaskProposalRequestError(ValueError):
    def __init__(self, issues: Sequence[DeveloperTaskProposalIssue]) -> None:
        self.issues = tuple(issues)
        preview = "; ".join(
            f"{item.field}: {item.code}"
            for item in self.issues[:5]
        )
        if len(self.issues) > 5:
            preview = f"{preview}; +{len(self.issues) - 5} more"
        super().__init__(
            f"Developer task proposal request is invalid: {preview or 'unknown error'}"
        )


def canonical_dtr_json_bytes(payload: Any) -> bytes:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8", "strict")


def dtr_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
