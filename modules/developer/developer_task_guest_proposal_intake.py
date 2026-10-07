from __future__ import annotations

"""Passive V2 proposal intake and derived manifest-data binding.

The caller supplies its separately retained expected request and the exact raw
response. No provider, filesystem, Git, patch parser/applicator or execution API
is called. Patch text is bounded opaque data: acceptance here does NOT establish
patch syntax, scope, applicability, source membership or behavioral correctness.
The V2 manifest is independently versioned and is NOT a V1 task/manifest adapter.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from modules.developer.developer_task_guest_request import (
    DeveloperTaskGuestRequestError,
    DeveloperTaskGuestRequestV2,
    canonical_developer_task_guest_request_v2,
    parse_developer_task_guest_request_v2,
)

GUEST_PROPOSAL_KIND = "DTR_GUEST_PATCH_PROPOSAL_V2"
GUEST_MANIFEST_KIND = "DTR_GUEST_TASK_MANIFEST_V2"
GUEST_PROPOSAL_SCHEMA_VERSION = 2
GUEST_MANIFEST_SCHEMA_VERSION = 2
GUEST_PROPOSAL_POLICY_ID = "skynetvs-v1c6-manual-guest-proposal-v2"
GUEST_PROPOSAL_PATCH_FILE = "changes.patch"
GUEST_PROPOSAL_VALID_STATUS = "PROPOSAL_AND_MANIFEST_BOUND_NOT_AUTHORIZED"
GUEST_PROPOSAL_REJECTED_STATUS = "GUEST_PROPOSAL_REJECTED"
GUEST_MANIFEST_VALID_STATUS = "MANIFEST_DATA_BOUND_NOT_AUTHORIZED"
GUEST_MANIFEST_REJECTED_STATUS = "GUEST_MANIFEST_REJECTED"

# Preserve V1's size bounds, not its dispatcher, DTOs, manifest or check flow.
GUEST_PROPOSAL_MAX_RESPONSE_BYTES = 256 * 1024
GUEST_PROPOSAL_MAX_PATCH_BYTES = 128 * 1024
GUEST_PROPOSAL_MAX_EXPLANATION_BYTES = 8 * 1024
GUEST_MANIFEST_MAX_JSON_BYTES = 64 * 1024
GUEST_PROPOSAL_MAX_JSON_DEPTH = 8
_PROPOSAL_FIELDS = frozenset({
    "kind", "schema_version", "request_id", "request_fingerprint", "binding",
    "check_specification", "patch_text", "explanation",
})


class DeveloperTaskGuestProposalError(ValueError):
    """Stable code only; raw content is never placed in a diagnostic."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DeveloperTaskGuestProposalError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8", "strict")
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise DeveloperTaskGuestProposalError("invalid_json_value") from exc


def _object(raw: bytes, *, maximum: int) -> dict[str, Any]:
    _require(type(raw) is bytes, "raw_bytes_required")
    _require(0 < len(raw) <= maximum, "json_size_invalid")
    _require(not raw.startswith(b"\xef\xbb\xbf"), "utf8_bom_forbidden")

    def pairs(items):
        out = {}
        for key, value in items:
            _require(key not in out, "duplicate_json_key")
            out[key] = value
        return out

    def number(_value):
        raise DeveloperTaskGuestProposalError("json_noninteger_number_forbidden")

    try:
        data = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                          parse_constant=number, parse_float=number)
    except DeveloperTaskGuestProposalError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DeveloperTaskGuestProposalError("invalid_json") from exc
    _require(type(data) is dict, "json_object_required")
    todo = [(data, 1)]
    while todo:
        item, depth = todo.pop()
        _require(depth <= GUEST_PROPOSAL_MAX_JSON_DEPTH, "json_depth_exceeded")
        if type(item) is dict:
            todo.extend((x, depth + 1) for x in item.values())
        elif type(item) is list:
            todo.extend((x, depth + 1) for x in item)
    # Also rejects escaped unpaired surrogates in unknown keys/values.
    _canonical(data)
    return data


def _bounded_text(value: Any, *, field_name: str, maximum: int) -> bytes:
    _require(type(value) is str, field_name + "_string_required")
    _require(bool(value.strip()) and "\x00" not in value, field_name + "_invalid")
    try:
        raw = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise DeveloperTaskGuestProposalError(field_name + "_invalid_utf8") from exc
    _require(len(raw) <= maximum, field_name + "_too_large")
    return raw


def _trusted_request(
    expected_request: DeveloperTaskGuestRequestV2, profile_document: bytes,
) -> DeveloperTaskGuestRequestV2:
    # Public envelope APIs rebuild every field and its nested binding/spec/context.
    # A frozen DTO or a self-consistent untrusted fingerprint is not a trust anchor.
    try:
        raw = canonical_developer_task_guest_request_v2(
            expected_request, profile_document=profile_document,
        )
        return parse_developer_task_guest_request_v2(
            raw, expected_request=expected_request, profile_document=profile_document,
        )
    except DeveloperTaskGuestRequestError as exc:
        raise DeveloperTaskGuestProposalError("expected_request_" + exc.code) from exc


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestPatchProposalV2:
    request_id: str
    request_fingerprint: str
    raw_response: bytes = field(repr=False)
    patch_bytes: bytes = field(repr=False)
    explanation: str = field(repr=False)

    @property
    def raw_response_sha256(self) -> str:
        return _sha(self.raw_response)

    @property
    def patch_sha256(self) -> str:
        return _sha(self.patch_bytes)

    def evidence_dict(self) -> dict[str, Any]:
        return {
            "kind": GUEST_PROPOSAL_KIND, "schema_version": GUEST_PROPOSAL_SCHEMA_VERSION,
            "request_id": self.request_id, "request_fingerprint": self.request_fingerprint,
            "raw_response_sha256": self.raw_response_sha256,
            "raw_response_bytes": len(self.raw_response),
            "patch_sha256": self.patch_sha256, "patch_bytes": len(self.patch_bytes),
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestManifestV2:
    """Derived manifest data. It is not accepted by existing V1 preflight/runtime."""

    request: DeveloperTaskGuestRequestV2 = field(repr=False)
    source_sha256: str
    source_bytes: int
    patch_sha256: str
    patch_bytes: int

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        r = self.request
        data = {
            "kind": GUEST_MANIFEST_KIND, "schema_version": GUEST_MANIFEST_SCHEMA_VERSION,
            "policy_id": GUEST_PROPOSAL_POLICY_ID, "task_kind": "patch", "project": "SkynetVS",
            "origin": "manual", "transport_mode": "manual_import",
            "task_id": r.task_id, "title": r.title, "request_id": r.request_id,
            "request_fingerprint": r.fingerprint, "context_digest": r.context_digest,
            "binding": r.binding.to_dict(),
            "check_specification": r.check_specification.to_dict(),
            "source_ref": "dtr-guest-proposal:" + r.request_id,
            "source_sha256": self.source_sha256, "source_bytes": self.source_bytes,
            "patch_file": GUEST_PROPOSAL_PATCH_FILE,
            "patch_sha256": self.patch_sha256, "patch_bytes": self.patch_bytes,
            "allowed_files": [r.binding.target_preimage.path],
            "install_policy": "manual_confirmation",
        }
        if include_fingerprint:
            data["manifest_fingerprint"] = self.fingerprint
        return data

    @property
    def fingerprint(self) -> str:
        return _sha(_canonical(self.to_dict(include_fingerprint=False)))


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestProposalPlanV2:
    request: DeveloperTaskGuestRequestV2 = field(repr=False)
    proposal: DeveloperTaskGuestPatchProposalV2 = field(repr=False)
    manifest: DeveloperTaskGuestManifestV2

    def evidence_dict(self) -> dict[str, Any]:
        # Deliberately omits instruction, explanation, context bytes and patch text.
        return {"proposal": self.proposal.evidence_dict(), "manifest": self.manifest.to_dict()}


def parse_developer_task_guest_proposal_v2(
    raw_response: bytes, *, expected_request: DeveloperTaskGuestRequestV2, profile_document: bytes,
) -> DeveloperTaskGuestProposalPlanV2:
    """Bind one untrusted response to the separately retained trusted V2 request.

    Only response JSON and byte identities are validated; no diff syntax, target
    applicability, Git observations or provider authenticity are established.
    """
    data = _object(raw_response, maximum=GUEST_PROPOSAL_MAX_RESPONSE_BYTES)
    _require(type(data.get("schema_version")) is int
             and data["schema_version"] == GUEST_PROPOSAL_SCHEMA_VERSION, "proposal_schema_unsupported")
    _require(data.get("kind") == GUEST_PROPOSAL_KIND, "proposal_kind_mismatch")
    _require(set(data) == _PROPOSAL_FIELDS, "proposal_fields_invalid")
    request = _trusted_request(expected_request, profile_document)
    for key, trusted in (
        ("request_id", request.request_id), ("request_fingerprint", request.fingerprint),
        ("binding", request.binding.to_dict()),
        ("check_specification", request.check_specification.to_dict()),
    ):
        _require(_canonical(data[key]) == _canonical(trusted), key + "_mismatch")
    patch_bytes = _bounded_text(data["patch_text"], field_name="patch", maximum=GUEST_PROPOSAL_MAX_PATCH_BYTES)
    _bounded_text(data["explanation"], field_name="explanation", maximum=GUEST_PROPOSAL_MAX_EXPLANATION_BYTES)
    proposal = DeveloperTaskGuestPatchProposalV2(
        request.request_id, request.fingerprint, raw_response, patch_bytes, data["explanation"],
    )
    manifest = DeveloperTaskGuestManifestV2(
        request, proposal.raw_response_sha256, len(raw_response), proposal.patch_sha256, len(patch_bytes),
    )
    return DeveloperTaskGuestProposalPlanV2(request, proposal, manifest)


def encode_developer_task_guest_proposal_v2(
    *, expected_request: DeveloperTaskGuestRequestV2, patch_text: str,
    explanation: str, profile_document: bytes,
) -> bytes:
    """Local manual-import serializer, not a provider call or an admission grant."""
    request = _trusted_request(expected_request, profile_document)
    _bounded_text(patch_text, field_name="patch", maximum=GUEST_PROPOSAL_MAX_PATCH_BYTES)
    _bounded_text(explanation, field_name="explanation", maximum=GUEST_PROPOSAL_MAX_EXPLANATION_BYTES)
    raw = _canonical({
        "kind": GUEST_PROPOSAL_KIND, "schema_version": GUEST_PROPOSAL_SCHEMA_VERSION,
        "request_id": request.request_id, "request_fingerprint": request.fingerprint,
        "binding": request.binding.to_dict(),
        "check_specification": request.check_specification.to_dict(),
        "patch_text": patch_text, "explanation": explanation,
    }) + b"\n"
    parse_developer_task_guest_proposal_v2(
        raw, expected_request=request, profile_document=profile_document,
    )
    return raw


def canonical_developer_task_guest_manifest_v2(
    manifest: DeveloperTaskGuestManifestV2, *, expected_request: DeveloperTaskGuestRequestV2,
    raw_response: bytes, profile_document: bytes,
) -> bytes:
    """Re-derive against caller-retained inputs before emitting a manifest."""
    _require(type(manifest) is DeveloperTaskGuestManifestV2, "manifest_type_invalid")
    plan = parse_developer_task_guest_proposal_v2(
        raw_response, expected_request=expected_request, profile_document=profile_document,
    )
    # Check attached request bytes too, not merely its serialized identities.
    attached = _trusted_request(manifest.request, profile_document)
    _require(attached == plan.request, "manifest_request_mismatch")
    _require(_canonical(manifest.to_dict()) == _canonical(plan.manifest.to_dict()), "manifest_binding_mismatch")
    raw = _canonical(plan.manifest.to_dict()) + b"\n"
    _require(len(raw) <= GUEST_MANIFEST_MAX_JSON_BYTES, "manifest_json_size_invalid")
    return raw


def parse_developer_task_guest_manifest_v2(
    raw_manifest: bytes, *, expected_request: DeveloperTaskGuestRequestV2,
    raw_response: bytes, profile_document: bytes,
) -> DeveloperTaskGuestManifestV2:
    """Verify manifest against exact retained response AND trusted expected request.

    The caller, not this parser, must retain/select those inputs. Equality and
    fingerprints provide consistency, not authentication, provenance or replay protection.
    """
    data = _object(raw_manifest, maximum=GUEST_MANIFEST_MAX_JSON_BYTES)
    _require(type(data.get("schema_version")) is int
             and data["schema_version"] == GUEST_MANIFEST_SCHEMA_VERSION, "manifest_schema_unsupported")
    _require(data.get("kind") == GUEST_MANIFEST_KIND, "manifest_kind_mismatch")
    plan = parse_developer_task_guest_proposal_v2(
        raw_response, expected_request=expected_request, profile_document=profile_document,
    )
    trusted = plan.manifest.to_dict()
    _require(set(data) == set(trusted), "manifest_fields_invalid")
    _require(_canonical(data) == _canonical(trusted), "manifest_binding_mismatch")
    return plan.manifest


def _non_authority() -> dict[str, Any]:
    return {
        "task_validated": False, "patch_validated": False, "patch_scope_validated": False,
        "patch_applicability_verified": False, "preflight_validated": False,
        "execution_plan_validated": False, "repository_observed": False,
        "source_membership_verified": False, "provider_authenticated": False,
        "model_provider_called": False, "capability_issued": False, "authority_granted": False,
        "candidate_tree_computed": False, "guest_profile_executed": False,
        "changed_task_code_executed": False, "required_profile_checks_passed": False,
        "all_required_checks_passed": False, "ready_to_promote": False,
        "runtime_authorized": False, "promotion_authorized": False,
        "behavioral_correctness": "NOT_EVALUATED",
    }


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestProposalIntakeResult:
    plan: DeveloperTaskGuestProposalPlanV2 | None
    issue_codes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return type(self.plan) is DeveloperTaskGuestProposalPlanV2 and not self.issue_codes

    @property
    def status(self) -> str:
        return GUEST_PROPOSAL_VALID_STATUS if self.ok else GUEST_PROPOSAL_REJECTED_STATUS

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok, "status": self.status, "issue_codes": list(self.issue_codes),
            "validation_scope": "V2_PROPOSAL_AND_DERIVED_MANIFEST_DATA_ONLY",
            "proposal_data_bound": self.ok, "manifest_data_bound": self.ok,
            "plan": self.plan.evidence_dict() if self.ok else None,
            **_non_authority(),
        }


def intake_developer_task_guest_proposal_v2(
    raw_response: bytes, *, expected_request: DeveloperTaskGuestRequestV2, profile_document: bytes,
) -> DeveloperTaskGuestProposalIntakeResult:
    try:
        plan = parse_developer_task_guest_proposal_v2(
            raw_response, expected_request=expected_request, profile_document=profile_document,
        )
    except DeveloperTaskGuestProposalError as exc:
        return DeveloperTaskGuestProposalIntakeResult(None, (exc.code,))
    return DeveloperTaskGuestProposalIntakeResult(plan, ())


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestManifestValidation:
    manifest: DeveloperTaskGuestManifestV2 | None
    issue_codes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return type(self.manifest) is DeveloperTaskGuestManifestV2 and not self.issue_codes

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": GUEST_MANIFEST_VALID_STATUS if self.ok else GUEST_MANIFEST_REJECTED_STATUS,
            "issue_codes": list(self.issue_codes),
            "validation_scope": "V2_MANIFEST_DATA_AGAINST_RETAINED_REQUEST_AND_RESPONSE",
            "manifest_data_bound": self.ok,
            "manifest_fingerprint": self.manifest.fingerprint if self.ok else "",
            **_non_authority(),
        }


def validate_developer_task_guest_manifest_v2(
    raw_manifest: bytes, *, expected_request: DeveloperTaskGuestRequestV2,
    raw_response: bytes, profile_document: bytes,
) -> DeveloperTaskGuestManifestValidation:
    try:
        manifest = parse_developer_task_guest_manifest_v2(
            raw_manifest, expected_request=expected_request, raw_response=raw_response,
            profile_document=profile_document,
        )
    except DeveloperTaskGuestProposalError as exc:
        return DeveloperTaskGuestManifestValidation(None, (exc.code,))
    return DeveloperTaskGuestManifestValidation(manifest, ())
