from __future__ import annotations

"""Passive V2 request semantic binding for the reviewed guest-source contract.

This module binds only the fields that are already knowable before proposal/
patch/preflight creation: schema/check contract/profile identity, task base
commit/tree and one exact target preimage. It does not create a complete DTR
request, proposal, manifest, patch, preflight, execution plan, capability,
runtime authorization or promotion authorization. It performs no filesystem,
Git, process, network or Sandbox access.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from modules.developer.developer_task_guest_profile_contract import (
    DeveloperTaskGuestProfileError,
    build_developer_task_guest_check_specification_v2,
)
from modules.developer.developer_task_guest_profile_policy import (
    GUEST_CHECK_CONTRACT_ID,
    GUEST_CHECK_SCHEMA_VERSION,
    GUEST_PROFILE_DOCUMENT_SHA256,
    GUEST_PROFILE_ID,
    GUEST_PROFILE_REVISION,
)

GUEST_REQUEST_BINDING_KIND = "DTR_GUEST_REQUEST_BINDING_V2"
GUEST_REQUEST_BINDING_SCHEMA_VERSION = 2
GUEST_REQUEST_BINDING_MAX_BYTES = 16 * 1024
GUEST_REQUEST_BINDING_MAX_DEPTH = 8
GUEST_REQUEST_TARGET_MAX_BYTES = 64 * 1024
GUEST_REQUEST_TARGET_MODE = "100644"
GUEST_REQUEST_BINDING_VALID_STATUS = "REQUEST_BINDING_VALIDATED_NOT_AUTHORIZED"
GUEST_REQUEST_BINDING_REJECTED_STATUS = "REQUEST_BINDING_REJECTED"

_GIT_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Independent V2 target policy. It intentionally preserves the current V1
# first-task protected surface without dispatching through the V1 DTO/validator.
GUEST_REQUEST_PROTECTED_EXACT = frozenset({
    "main.py",
    "test.py",
    "modules/action_contract.py",
    "modules/action_authority.py",
    "modules/action_broker.py",
    "modules/timer_action_runtime.py",
    "modules/volume_action_runtime.py",
})
GUEST_REQUEST_PROTECTED_PREFIXES = (
    "modules/developer/",
    "modules/core/",
    "modules/runtime/",
    "native/",
    "tools/",
    "tests/",
    "browser_extension/",
    "docs/",
    "data/",
    "train/",
)


class DeveloperTaskGuestRequestBindingError(ValueError):
    """Bounded machine-readable rejection; untrusted payload bytes are omitted."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DeveloperTaskGuestRequestBindingError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def _constant(_value: str) -> None:
    raise DeveloperTaskGuestRequestBindingError("nonfinite_json_number")


def _json_object(raw: bytes) -> dict[str, Any]:
    _require(type(raw) is bytes, "bytes_required")
    _require(0 < len(raw) <= GUEST_REQUEST_BINDING_MAX_BYTES, "json_size_invalid")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except DeveloperTaskGuestRequestBindingError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DeveloperTaskGuestRequestBindingError("invalid_json") from exc
    _require(type(value) is dict, "json_object_required")

    todo = [(value, 1)]
    while todo:
        item, depth = todo.pop()
        _require(depth <= GUEST_REQUEST_BINDING_MAX_DEPTH, "json_depth_exceeded")
        if type(item) is dict:
            todo.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            todo.extend((child, depth + 1) for child in item)
    return value


def _git_blob_oid(content: bytes) -> str:
    return hashlib.sha1(f"blob {len(content)}\0".encode("ascii") + content).hexdigest()


def _normalize_target_path(raw: Any) -> str:
    _require(type(raw) is str, "target_path_type_invalid")
    _require(bool(raw) and raw == raw.strip(), "target_path_invalid")
    _require(len(raw) <= 240, "target_path_too_long")
    _require("\\" not in raw, "target_backslash_forbidden")
    _require(not raw.startswith("/") and re.match(r"^[A-Za-z]:", raw) is None,
             "target_absolute_path_forbidden")
    _require("\x00" not in raw, "target_nul_forbidden")
    path = PurePosixPath(raw)
    parts = path.parts
    _require(bool(parts) and all(part not in ("", ".", "..") for part in parts),
             "target_path_traversal")
    _require(all(len(part) <= 120 for part in parts), "target_path_segment_too_long")
    _require(all(not part.startswith(".") for part in parts), "target_hidden_path_forbidden")
    normalized = path.as_posix()
    _require(normalized == raw, "target_path_noncanonical")
    _require(normalized.startswith("modules/") and normalized.casefold().endswith(".py"),
             "unsupported_target")
    lower = normalized.casefold()
    name = PurePosixPath(lower).name
    protected = (
        lower in GUEST_REQUEST_PROTECTED_EXACT
        or any(lower.startswith(prefix) for prefix in GUEST_REQUEST_PROTECTED_PREFIXES)
        or name == "__init__.py"
        or name.startswith("test_")
        or name.startswith("eval_")
        or name.endswith("_test.py")
    )
    _require(not protected, "protected_target")
    return normalized


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestTargetPreimageV2:
    path: str
    mode: str
    git_blob_oid: str
    content_sha256: str
    content_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "mode": self.mode,
            "git_blob_oid": self.git_blob_oid,
            "content_sha256": self.content_sha256,
            "content_bytes": self.content_bytes,
        }


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestRequestBindingV2:
    """Pre-proposal semantic binding only; never a complete DTR request."""

    schema_version: int
    check_contract_id: str
    profile_id: str
    profile_revision: int
    profile_sha256: str
    task_base_commit: str
    task_base_tree: str
    target_preimage: DeveloperTaskGuestTargetPreimageV2

    def binding_payload(self) -> dict[str, Any]:
        # Exactly the fields named by the reviewed C03M021 stage-binding design.
        return {
            "schema_version": self.schema_version,
            "check_contract_id": self.check_contract_id,
            "profile_id": self.profile_id,
            "profile_revision": self.profile_revision,
            "profile_sha256": self.profile_sha256,
            "task_base_commit": self.task_base_commit,
            "task_base_tree": self.task_base_tree,
            "target_preimage": self.target_preimage.to_dict(),
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.binding_payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": GUEST_REQUEST_BINDING_KIND,
            **self.binding_payload(),
            "request_binding_fingerprint": self.fingerprint,
        }


def build_developer_task_guest_request_binding_v2(
    *,
    profile_document: bytes,
    task_base_commit: str,
    task_base_tree: str,
    target_path: str,
    target_mode: str,
    target_git_blob_oid: str,
    target_content: bytes,
) -> DeveloperTaskGuestRequestBindingV2:
    """Bind exact trusted bytes without reading the repository or granting authority."""
    try:
        check_spec = build_developer_task_guest_check_specification_v2(
            profile_document=profile_document,
        )
    except DeveloperTaskGuestProfileError as exc:
        raise DeveloperTaskGuestRequestBindingError(exc.code) from exc

    _require(
        check_spec.schema_version == GUEST_CHECK_SCHEMA_VERSION
        and check_spec.check_contract_id == GUEST_CHECK_CONTRACT_ID
        and check_spec.profile_id == GUEST_PROFILE_ID
        and check_spec.profile_revision == GUEST_PROFILE_REVISION
        and check_spec.profile_sha256 == GUEST_PROFILE_DOCUMENT_SHA256,
        "guest_check_contract_reference_invalid",
    )
    _require(
        type(task_base_commit) is str and _GIT_SHA1_RE.fullmatch(task_base_commit) is not None,
        "task_base_commit_invalid",
    )
    _require(
        type(task_base_tree) is str and _GIT_SHA1_RE.fullmatch(task_base_tree) is not None,
        "task_base_tree_invalid",
    )
    path = _normalize_target_path(target_path)
    _require(type(target_mode) is str and target_mode == GUEST_REQUEST_TARGET_MODE,
             "target_mode_invalid")
    _require(
        type(target_git_blob_oid) is str
        and _GIT_SHA1_RE.fullmatch(target_git_blob_oid) is not None,
        "target_blob_oid_invalid",
    )
    _require(type(target_content) is bytes, "target_content_bytes_required")
    _require(0 <= len(target_content) <= GUEST_REQUEST_TARGET_MAX_BYTES,
             "target_content_size_invalid")
    _require(_git_blob_oid(target_content) == target_git_blob_oid,
             "target_blob_content_mismatch")
    preimage = DeveloperTaskGuestTargetPreimageV2(
        path=path,
        mode=target_mode,
        git_blob_oid=target_git_blob_oid,
        content_sha256=hashlib.sha256(target_content).hexdigest(),
        content_bytes=len(target_content),
    )
    return DeveloperTaskGuestRequestBindingV2(
        schema_version=GUEST_REQUEST_BINDING_SCHEMA_VERSION,
        check_contract_id=check_spec.check_contract_id,
        profile_id=check_spec.profile_id,
        profile_revision=check_spec.profile_revision,
        profile_sha256=check_spec.profile_sha256,
        task_base_commit=task_base_commit,
        task_base_tree=task_base_tree,
        target_preimage=preimage,
    )


def canonical_developer_task_guest_request_binding_v2(
    binding: DeveloperTaskGuestRequestBindingV2,
) -> bytes:
    _require(type(binding) is DeveloperTaskGuestRequestBindingV2,
             "request_binding_type_invalid")
    return _canonical(binding.to_dict()) + b"\n"


def parse_developer_task_guest_request_binding_v2(
    raw: bytes,
    *,
    profile_document: bytes,
    target_content: bytes,
) -> DeveloperTaskGuestRequestBindingV2:
    """Strict V2-only parser. No V1 fallback, field dropping or type coercion."""
    data = _json_object(raw)
    expected_top = {
        "kind",
        "schema_version",
        "check_contract_id",
        "profile_id",
        "profile_revision",
        "profile_sha256",
        "task_base_commit",
        "task_base_tree",
        "target_preimage",
        "request_binding_fingerprint",
    }
    _require(set(data) == expected_top, "request_binding_fields_invalid")
    _require(data["kind"] == GUEST_REQUEST_BINDING_KIND, "request_binding_kind_mismatch")
    _require(
        type(data["schema_version"]) is int
        and data["schema_version"] == GUEST_REQUEST_BINDING_SCHEMA_VERSION,
        "request_binding_schema_version_unsupported",
    )
    _require(
        type(data["profile_revision"]) is int
        and data["profile_revision"] == GUEST_PROFILE_REVISION,
        "request_binding_profile_revision_unsupported",
    )
    _require(
        data["check_contract_id"] == GUEST_CHECK_CONTRACT_ID
        and data["profile_id"] == GUEST_PROFILE_ID
        and data["profile_sha256"] == GUEST_PROFILE_DOCUMENT_SHA256,
        "request_binding_guest_contract_reference_mismatch",
    )
    _require(type(data["target_preimage"]) is dict, "target_preimage_object_required")
    preimage = data["target_preimage"]
    _require(
        set(preimage)
        == {"path", "mode", "git_blob_oid", "content_sha256", "content_bytes"},
        "target_preimage_fields_invalid",
    )
    _require(type(preimage["content_sha256"]) is str
             and _SHA256_RE.fullmatch(preimage["content_sha256"]) is not None,
             "target_content_sha256_invalid")
    _require(type(preimage["content_bytes"]) is int and not isinstance(preimage["content_bytes"], bool),
             "target_content_bytes_invalid")
    binding = build_developer_task_guest_request_binding_v2(
        profile_document=profile_document,
        task_base_commit=data["task_base_commit"],
        task_base_tree=data["task_base_tree"],
        target_path=preimage["path"],
        target_mode=preimage["mode"],
        target_git_blob_oid=preimage["git_blob_oid"],
        target_content=target_content,
    )
    _require(preimage == binding.target_preimage.to_dict(),
             "target_preimage_content_mismatch")
    _require(
        type(data["request_binding_fingerprint"]) is str
        and data["request_binding_fingerprint"] == binding.fingerprint,
        "request_binding_fingerprint_mismatch",
    )
    _require(_canonical(data) == _canonical(binding.to_dict()),
             "request_binding_content_mismatch")
    return binding


def _non_authorizing_fields() -> dict[str, Any]:
    return {
        "validation_scope": "V2_REQUEST_SEMANTIC_BINDING_DATA_ONLY",
        "task_validated": False,
        "proposal_validated": False,
        "manifest_validated": False,
        "patch_validated": False,
        "preflight_validated": False,
        "execution_plan_validated": False,
        "capability_issued": False,
        "guest_profile_executed": False,
        "required_profile_checks_passed": False,
        "all_required_checks_passed": False,
        "ready_to_promote": False,
        "runtime_authorized": False,
        "promotion_authorized": False,
        "behavioral_correctness": "NOT_EVALUATED",
    }


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestRequestBindingValidation:
    status: str
    issue_codes: tuple[str, ...]
    binding: DeveloperTaskGuestRequestBindingV2 | None = None

    @property
    def ok(self) -> bool:
        return (
            self.status == GUEST_REQUEST_BINDING_VALID_STATUS
            and not self.issue_codes
            and self.binding is not None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "issue_codes": list(self.issue_codes),
            "request_binding_fingerprint": (
                self.binding.fingerprint if self.binding is not None else ""
            ),
            "profile_sha256": (
                self.binding.profile_sha256 if self.binding is not None else ""
            ),
            **_non_authorizing_fields(),
            "request_binding_validated": self.ok,
        }


def validate_developer_task_guest_request_binding_v2(
    raw: bytes,
    *,
    profile_document: bytes,
    target_content: bytes,
) -> DeveloperTaskGuestRequestBindingValidation:
    try:
        binding = parse_developer_task_guest_request_binding_v2(
            raw,
            profile_document=profile_document,
            target_content=target_content,
        )
    except DeveloperTaskGuestRequestBindingError as exc:
        return DeveloperTaskGuestRequestBindingValidation(
            GUEST_REQUEST_BINDING_REJECTED_STATUS,
            (exc.code,),
        )
    return DeveloperTaskGuestRequestBindingValidation(
        GUEST_REQUEST_BINDING_VALID_STATUS,
        (),
        binding=binding,
    )
