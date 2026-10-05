from __future__ import annotations

"""Pure data validation for the reviewed V1C6 profile and V2 check specification.

No files, processes, Git, networks, workspaces, tests or capabilities are created
by this module. A validated specification is NOT a validated task or execution
plan: base/preimage/patch/runtime admission belongs to subsequent slices. V1
DTOs and validators are deliberately not imported or adapted here.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_guest_profile_document import (
    GUEST_PROFILE_DOCUMENT,
)
from modules.developer.developer_task_guest_profile_policy import (
    GUEST_CHECK_CONTRACT_ID,
    GUEST_CHECK_SCHEMA_VERSION,
    GUEST_CHECK_SPECIFICATION_KIND,
    GUEST_CHECK_SPECIFICATION_MAX_BYTES,
    GUEST_CHECK_SPECIFICATION_MAX_DEPTH,
    GUEST_CHECK_VALID_STATUS,
    GUEST_CONTRACT_REJECTED_STATUS,
    GUEST_PROFILE_DOCUMENT_BYTES,
    GUEST_PROFILE_DOCUMENT_SHA256,
    GUEST_PROFILE_EXCLUDED_ORDINALS,
    GUEST_PROFILE_FLOW,
    GUEST_PROFILE_ID,
    GUEST_PROFILE_REQUIRED_ORDINALS,
    GUEST_PROFILE_REVISION,
    GUEST_PROFILE_VALID_STATUS,
)


class DeveloperTaskGuestProfileError(ValueError):
    """A bounded machine-readable rejection; never includes untrusted bytes."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DeveloperTaskGuestProfileError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def _constant(_value: str) -> None:
    raise DeveloperTaskGuestProfileError("nonfinite_json_number")


def _json_object(raw: bytes, *, limit: int) -> dict[str, Any]:
    _require(type(raw) is bytes, "bytes_required")
    _require(0 < len(raw) <= limit, "json_size_invalid")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant,
        )
    except DeveloperTaskGuestProfileError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DeveloperTaskGuestProfileError("invalid_json") from exc
    _require(type(value) is dict, "json_object_required")
    todo = [(value, 1)]
    while todo:
        item, depth = todo.pop()
        _require(depth <= GUEST_CHECK_SPECIFICATION_MAX_DEPTH, "json_depth_exceeded")
        if type(item) is dict:
            todo.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            todo.extend((v, depth + 1) for v in item)
    return value


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestProfileStep:
    source_ordinal: int
    path: str
    python_args: tuple[str, ...]
    git_mode: str
    git_blob_oid: str
    content_bytes: int
    content_sha256: str
    process_class: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ordinal": self.source_ordinal, "path": self.path,
            "python_args": list(self.python_args), "git_mode": self.git_mode,
            "git_blob_oid": self.git_blob_oid,
            "snapshot_entrypoint_identity": {
                "bytes": self.content_bytes, "sha256": self.content_sha256,
            },
            "process_class": self.process_class,
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestProfile:
    """Immutable data view; constructing this object confers no authority."""

    profile_id: str
    revision: int
    flow: str
    document_sha256: str
    steps: tuple[DeveloperTaskGuestProfileStep, ...]
    excluded_ordinals: tuple[int, ...]
    review_base_commit: str
    review_base_tree: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id, "profile_revision": self.revision,
            "flow": self.flow, "profile_sha256": self.document_sha256,
            "required_steps": [step.to_dict() for step in self.steps],
            "excluded_legacy_ordinals": list(self.excluded_ordinals),
            "review_origin": {
                "base_commit": self.review_base_commit,
                "base_tree": self.review_base_tree,
                "role": "REVIEW_ORIGIN_NOT_A_FUTURE_EXECUTION_BASE",
            },
            **_non_authorizing_fields(),
        }


def _non_authorizing_fields() -> dict[str, Any]:
    return {
        "validation_scope": "PROFILE_AND_CHECK_SPECIFICATION_DATA_ONLY",
        "task_validated": False,
        "execution_plan_validated": False,
        "runtime_authorized": False,
        "promotion_authorized": False,
        "capability_issued": False,
        "guest_profile_executed": False,
        "required_profile_checks_passed": False,
        "all_required_checks_passed": False,
        "ready_to_promote": False,
        "legacy_full_check_equivalent": False,
        "legacy_full_check_status": "NOT_SATISFIED_BY_GUEST_PROFILE",
        "behavioral_correctness": "NOT_EVALUATED",
    }


def canonical_developer_task_guest_profile_document() -> bytes:
    """Return the exact embedded review document, without filesystem access."""
    return GUEST_PROFILE_DOCUMENT


def parse_developer_task_guest_profile(raw: bytes) -> DeveloperTaskGuestProfile:
    """Pin the entire descriptor, not merely its caller-controlled shape."""
    _require(type(raw) is bytes, "profile_bytes_required")
    _require(len(raw) == GUEST_PROFILE_DOCUMENT_BYTES, "profile_size_mismatch")
    _require(hashlib.sha256(raw).hexdigest() == GUEST_PROFILE_DOCUMENT_SHA256,
             "profile_digest_mismatch")
    data = _json_object(raw, limit=GUEST_PROFILE_DOCUMENT_BYTES)
    _require(_canonical(data) + b"\n" == raw, "profile_not_canonical")
    _require(data["profile_id"] == GUEST_PROFILE_ID, "profile_id_mismatch")
    _require(type(data["profile_revision"]) is int
             and data["profile_revision"] == GUEST_PROFILE_REVISION,
             "profile_revision_mismatch")
    _require(data["flow_id"] == GUEST_PROFILE_FLOW, "profile_flow_mismatch")
    _require(data["runtime_authorized"] is False
             and data["promotion_authorized"] is False,
             "profile_authority_invalid")
    _require(data["coverage"]["legacy_full_check_equivalent"] is False,
             "legacy_equivalence_forbidden")
    steps = tuple(
        DeveloperTaskGuestProfileStep(
            source_ordinal=s["source_ordinal"], path=s["path"],
            python_args=tuple(s["python_args"]), git_mode=s["git_mode"],
            git_blob_oid=s["git_blob_oid"],
            content_bytes=s["snapshot_entrypoint_identity"]["bytes"],
            content_sha256=s["snapshot_entrypoint_identity"]["sha256"],
            process_class=s["process_class"],
        ) for s in data["steps"]
    )
    _require(tuple(s.source_ordinal for s in steps) == GUEST_PROFILE_REQUIRED_ORDINALS,
             "profile_order_mismatch")
    _require(len({s.path for s in steps}) == len(steps), "profile_duplicate_path")
    excluded = tuple(s["source_ordinal"] for s in data["excluded_steps"])
    _require(excluded == GUEST_PROFILE_EXCLUDED_ORDINALS, "profile_exclusions_mismatch")
    return DeveloperTaskGuestProfile(
        GUEST_PROFILE_ID, GUEST_PROFILE_REVISION, GUEST_PROFILE_FLOW,
        GUEST_PROFILE_DOCUMENT_SHA256, steps, excluded,
        data["source_baseline"]["head"], data["source_baseline"]["tree"],
    )


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestCheck:
    type: str
    scope: str = ""
    flow: str = ""
    profile_sha256: str = ""

    def to_dict(self) -> dict[str, str]:
        value = {"type": self.type}
        for name in ("scope", "flow", "profile_sha256"):
            field = getattr(self, name)
            if field:
                value[name] = field
        return value


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestCheckSpecificationV2:
    """Only the nested check specification. NOT a full V2 request/manifest."""

    schema_version: int
    check_contract_id: str
    profile_id: str
    profile_revision: int
    profile_sha256: str
    checks: tuple[DeveloperTaskGuestCheck, ...]

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "kind": GUEST_CHECK_SPECIFICATION_KIND,
            "schema_version": self.schema_version,
            "check_contract_id": self.check_contract_id,
            "profile_id": self.profile_id,
            "profile_revision": self.profile_revision,
            "profile_sha256": self.profile_sha256,
            "checks": [check.to_dict() for check in self.checks],
        }
        if include_fingerprint:
            value["contract_fingerprint"] = self.fingerprint
        return value

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict(include_fingerprint=False))).hexdigest()


def build_developer_task_guest_check_specification_v2(
    *, profile_document: bytes,
) -> DeveloperTaskGuestCheckSpecificationV2:
    # Always re-validate bytes; do not accept a caller-constructed profile as a lease.
    profile = parse_developer_task_guest_profile(profile_document)
    return DeveloperTaskGuestCheckSpecificationV2(
        GUEST_CHECK_SCHEMA_VERSION, GUEST_CHECK_CONTRACT_ID,
        profile.profile_id, profile.revision, profile.document_sha256,
        (
            DeveloperTaskGuestCheck("git_diff_check"),
            DeveloperTaskGuestCheck("py_compile", scope="changed_python_files"),
            DeveloperTaskGuestCheck("pipeline", flow=profile.flow,
                                    profile_sha256=profile.document_sha256),
        ),
    )


def canonical_developer_task_guest_check_specification_v2(
    specification: DeveloperTaskGuestCheckSpecificationV2,
) -> bytes:
    """Serialization is not admission; validate resulting bytes before use."""
    _require(type(specification) is DeveloperTaskGuestCheckSpecificationV2,
             "check_specification_type_invalid")
    return _canonical(specification.to_dict()) + b"\n"


def parse_developer_task_guest_check_specification_v2(
    raw: bytes, *, profile_document: bytes,
) -> DeveloperTaskGuestCheckSpecificationV2:
    """Strict standalone V2 decoder; no V1 dispatch, coercion or field dropping."""
    expected = build_developer_task_guest_check_specification_v2(
        profile_document=profile_document,
    )
    data = _json_object(raw, limit=GUEST_CHECK_SPECIFICATION_MAX_BYTES)
    _require(set(data) == set(expected.to_dict()), "check_specification_fields_invalid")
    _require(type(data["schema_version"]) is int
             and data["schema_version"] == GUEST_CHECK_SCHEMA_VERSION,
             "unsupported_check_schema_version")
    _require(type(data["profile_revision"]) is int
             and data["profile_revision"] == GUEST_PROFILE_REVISION,
             "unsupported_profile_revision")
    _require(data["kind"] == GUEST_CHECK_SPECIFICATION_KIND,
             "check_specification_kind_mismatch")
    _require(data["check_contract_id"] == GUEST_CHECK_CONTRACT_ID,
             "check_contract_id_mismatch")
    _require(data["profile_id"] == GUEST_PROFILE_ID
             and data["profile_sha256"] == GUEST_PROFILE_DOCUMENT_SHA256,
             "check_profile_reference_mismatch")
    _require(data["checks"] == [c.to_dict() for c in expected.checks],
             "check_sequence_mismatch")
    _require(type(data["contract_fingerprint"]) is str
             and data["contract_fingerprint"] == expected.fingerprint,
             "check_specification_fingerprint_mismatch")
    # Pin field set and types via canonical bytes, not Python's True == 1 coercion.
    _require(_canonical(data) == _canonical(expected.to_dict()),
             "check_specification_fingerprint_or_content_mismatch")
    return expected


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestContractValidation:
    status: str
    issue_codes: tuple[str, ...]
    profile: DeveloperTaskGuestProfile | None = None
    specification: DeveloperTaskGuestCheckSpecificationV2 | None = None

    @property
    def ok(self) -> bool:
        return (
            not self.issue_codes
            and ((self.status == GUEST_PROFILE_VALID_STATUS and self.profile is not None)
                 or (self.status == GUEST_CHECK_VALID_STATUS and self.specification is not None))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok, "status": self.status,
            "issue_codes": list(self.issue_codes),
            "profile_sha256": (self.profile.document_sha256 if self.profile else
                               self.specification.profile_sha256 if self.specification else ""),
            "contract_fingerprint": self.specification.fingerprint if self.specification else "",
            **_non_authorizing_fields(),
        }


def validate_developer_task_guest_profile(raw: bytes) -> DeveloperTaskGuestContractValidation:
    try:
        profile = parse_developer_task_guest_profile(raw)
    except DeveloperTaskGuestProfileError as exc:
        return DeveloperTaskGuestContractValidation(GUEST_CONTRACT_REJECTED_STATUS, (exc.code,))
    return DeveloperTaskGuestContractValidation(GUEST_PROFILE_VALID_STATUS, (), profile=profile)


def validate_developer_task_guest_check_specification_v2(
    raw: bytes, *, profile_document: bytes,
) -> DeveloperTaskGuestContractValidation:
    try:
        specification = parse_developer_task_guest_check_specification_v2(
            raw, profile_document=profile_document,
        )
    except DeveloperTaskGuestProfileError as exc:
        return DeveloperTaskGuestContractValidation(GUEST_CONTRACT_REJECTED_STATUS, (exc.code,))
    return DeveloperTaskGuestContractValidation(
        GUEST_CHECK_VALID_STATUS, (), specification=specification,
    )
