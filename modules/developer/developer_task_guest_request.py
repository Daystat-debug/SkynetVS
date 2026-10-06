from __future__ import annotations

"""Passive, manual-import V2 request envelope around the landed semantic binding.

Inputs are already obtained by a trusted caller. No filesystem/Git/provider or
execution API is used. Parsing requires a separately retained expected request;
a self-consistent untrusted fingerprint is not an authorization or a trust anchor.
Context bytes remain local in immutable DTOs; JSON contains their identities only.
Proposal/patch/manifest/preflight and executable admission are deliberately absent.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from modules.developer.developer_task_guest_profile_contract import (
    DeveloperTaskGuestCheck,
    DeveloperTaskGuestCheckSpecificationV2,
    DeveloperTaskGuestProfileError,
    build_developer_task_guest_check_specification_v2,
)
from modules.developer.developer_task_guest_request_binding import (
    DeveloperTaskGuestRequestBindingError,
    DeveloperTaskGuestRequestBindingV2,
    DeveloperTaskGuestTargetPreimageV2,
    build_developer_task_guest_request_binding_v2,
)

GUEST_REQUEST_KIND = "DTR_GUEST_REQUEST_V2"
GUEST_REQUEST_SCHEMA_VERSION = 2
GUEST_REQUEST_POLICY_ID = "skynetvs-v1c6-manual-guest-request-v2"
GUEST_REQUEST_TRANSPORT_MODE = "manual_import"
GUEST_REQUEST_ORIGIN = "manual"
GUEST_REQUEST_INSTALL_POLICY = "manual_confirmation"
GUEST_REQUEST_VALID_STATUS = "REQUEST_ENVELOPE_VALIDATED_NOT_AUTHORIZED"
GUEST_REQUEST_REJECTED_STATUS = "REQUEST_ENVELOPE_REJECTED"

# Preserve the first DTR request's bounded context/instruction profile. This
# independent V2 dispatcher does not coerce/drop fields or call the V1 producer.
GUEST_REQUEST_MAX_INSTRUCTION_BYTES = 16 * 1024
GUEST_REQUEST_MAX_CONTEXT_FILES = 4
GUEST_REQUEST_MAX_CONTEXT_FILE_BYTES = 64 * 1024
GUEST_REQUEST_MAX_CONTEXT_TOTAL_BYTES = 256 * 1024
GUEST_REQUEST_MAX_JSON_BYTES = 64 * 1024
GUEST_REQUEST_MAX_JSON_DEPTH = 8

_TASK_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,63}\Z")
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,95}\Z")
_GIT_OID_RE = re.compile(r"[0-9a-f]{40}\Z")
_READ_FORBIDDEN_EXACT = frozenset({
    ".env", "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "pipfile", "pipfile.lock", "poetry.lock",
})
_READ_FORBIDDEN_PREFIXES = (".git/", ".venv/", "venv/", "data/", "models/", "native/")
# Additional envelope-level path refusals. This does not broaden the landed
# binding's target policy. No Windows alias resolution or normalization is used.
_RESERVED_COMPONENTS = frozenset({"con", "prn", "aux", "nul", "conin$", "conout$"}) | frozenset(
    f"{prefix}{n}" for prefix in ("com", "lpt") for n in range(1, 10)
)


class DeveloperTaskGuestRequestError(ValueError):
    """Stable bounded error code; no source content/instruction in diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DeveloperTaskGuestRequestError(code)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise DeveloperTaskGuestRequestError("invalid_json_value") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _text(value: Any, *, code: str, maximum: int, trimmed: bool) -> str:
    _require(type(value) is str, code)
    _require(bool(value.strip()) and (not trimmed or value == value.strip()), code)
    _require("\x00" not in value, code)
    try:
        raw = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise DeveloperTaskGuestRequestError(code) from exc
    _require(len(raw) <= maximum, code)
    return value


def _path(value: Any) -> str:
    value = _text(value, code="context_path_invalid", maximum=960, trimmed=True)
    _require(len(value) <= 240 and not value.startswith("/"), "context_path_invalid")
    _require(not any(ord(c) < 32 or ord(c) == 127 or c in '\\:*?"<>|' for c in value),
             "context_path_invalid")
    parts = value.split("/")
    _require(all(p and len(p) <= 120 and not p.startswith(".")
                 and not p.endswith((" ", ".")) for p in parts), "context_path_invalid")
    _require(all(p.casefold().split(".", 1)[0] not in _RESERVED_COMPONENTS for p in parts),
             "context_path_invalid")
    lower = value.casefold()
    _require(lower not in _READ_FORBIDDEN_EXACT
             and not any(lower.startswith(prefix) for prefix in _READ_FORBIDDEN_PREFIXES),
             "context_disclosure_path_forbidden")
    return value


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestContextInputV2:
    path: str
    mode: str
    git_blob_oid: str
    content: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestBoundSourceV2:
    path: str
    mode: str
    git_blob_oid: str
    content_sha256: str
    content_bytes: int
    content: bytes = field(repr=False)

    def binding_dict(self) -> dict[str, Any]:
        return {"path": self.path, "mode": self.mode, "git_blob_oid": self.git_blob_oid,
                "content_sha256": self.content_sha256, "content_bytes": self.content_bytes}


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestRequestV2:
    """A complete request-data envelope, never a proposal or an execution lease."""

    schema_version: int
    policy_id: str
    transport_mode: str
    origin: str
    task_id: str
    title: str
    request_id: str
    instruction: str = field(repr=False)
    binding: DeveloperTaskGuestRequestBindingV2
    context: tuple[DeveloperTaskGuestBoundSourceV2, ...] = field(repr=False)
    context_digest: str
    check_specification: DeveloperTaskGuestCheckSpecificationV2
    install_policy: str

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        data = {
            "kind": GUEST_REQUEST_KIND, "schema_version": self.schema_version,
            "policy_id": self.policy_id, "transport_mode": self.transport_mode,
            "origin": self.origin, "task_id": self.task_id, "title": self.title,
            "request_id": self.request_id, "instruction": self.instruction,
            "binding": self.binding.to_dict(),
            "target_write_allowlist": [self.binding.target_preimage.path],
            "context": [entry.binding_dict() for entry in self.context],
            "context_digest": self.context_digest,
            "check_specification": self.check_specification.to_dict(),
            "install_policy": self.install_policy,
        }
        if include_fingerprint:
            data["request_fingerprint"] = self.fingerprint
        return data

    @property
    def fingerprint(self) -> str:
        return _sha(_canonical(self.to_dict(include_fingerprint=False)))


def prepare_developer_task_guest_request_v2(
    *, task_id: str, title: str, request_id: str, instruction: str,
    task_base_commit: str, task_base_tree: str, target_path: str,
    context_entries: tuple[DeveloperTaskGuestContextInputV2, ...],
    profile_document: bytes,
) -> DeveloperTaskGuestRequestV2:
    """Build from trusted caller inputs only. Does not observe a live repository."""
    _text(task_id, code="task_id_invalid", maximum=64, trimmed=True)
    _require(_TASK_ID_RE.fullmatch(task_id) is not None, "task_id_invalid")
    _text(request_id, code="request_id_invalid", maximum=96, trimmed=True)
    _require(_REQUEST_ID_RE.fullmatch(request_id) is not None, "request_id_invalid")
    _text(title, code="title_invalid", maximum=640, trimmed=True)
    _require(len(title) <= 160 and not any(ord(c) < 32 or ord(c) == 127 for c in title),
             "title_invalid")
    _text(instruction, code="instruction_invalid",
          maximum=GUEST_REQUEST_MAX_INSTRUCTION_BYTES, trimmed=False)
    target_path = _path(target_path)
    _require(type(context_entries) is tuple, "context_tuple_required")
    _require(1 <= len(context_entries) <= GUEST_REQUEST_MAX_CONTEXT_FILES, "context_count_invalid")
    bound = []
    seen: set[str] = set()
    total = 0
    for entry in context_entries:
        _require(type(entry) is DeveloperTaskGuestContextInputV2, "context_input_type_invalid")
        path = _path(entry.path)
        _require(path.casefold() not in seen, "duplicate_context_path")
        seen.add(path.casefold())
        _require(type(entry.mode) is str and entry.mode == "100644", "context_mode_invalid")
        _require(type(entry.git_blob_oid) is str and _GIT_OID_RE.fullmatch(entry.git_blob_oid) is not None,
                 "context_blob_oid_invalid")
        _require(type(entry.content) is bytes, "context_bytes_required")
        _require(len(entry.content) <= GUEST_REQUEST_MAX_CONTEXT_FILE_BYTES, "context_file_too_large")
        total += len(entry.content)
        expected_blob = hashlib.sha1(f"blob {len(entry.content)}\0".encode("ascii") + entry.content).hexdigest()
        _require(entry.git_blob_oid == expected_blob, "context_blob_content_mismatch")
        bound.append(DeveloperTaskGuestBoundSourceV2(
            path, entry.mode, entry.git_blob_oid, _sha(entry.content), len(entry.content), entry.content,
        ))
    _require(total <= GUEST_REQUEST_MAX_CONTEXT_TOTAL_BYTES, "context_total_too_large")
    context = tuple(sorted(bound, key=lambda item: item.path.casefold()))
    targets = tuple(item for item in context if item.path == target_path)
    _require(len(targets) == 1, "target_not_bound")
    target = targets[0]
    try:
        binding = build_developer_task_guest_request_binding_v2(
            profile_document=profile_document, task_base_commit=task_base_commit,
            task_base_tree=task_base_tree, target_path=target.path, target_mode=target.mode,
            target_git_blob_oid=target.git_blob_oid, target_content=target.content,
        )
        spec = build_developer_task_guest_check_specification_v2(profile_document=profile_document)
    except (DeveloperTaskGuestRequestBindingError, DeveloperTaskGuestProfileError) as exc:
        raise DeveloperTaskGuestRequestError(exc.code) from exc
    return DeveloperTaskGuestRequestV2(
        GUEST_REQUEST_SCHEMA_VERSION, GUEST_REQUEST_POLICY_ID, GUEST_REQUEST_TRANSPORT_MODE,
        GUEST_REQUEST_ORIGIN, task_id, title, request_id, instruction, binding, context,
        _sha(_canonical([item.binding_dict() for item in context])), spec, GUEST_REQUEST_INSTALL_POLICY,
    )


def _validated_expected(
    request: DeveloperTaskGuestRequestV2, *, profile_document: bytes,
) -> DeveloperTaskGuestRequestV2:
    _require(type(request) is DeveloperTaskGuestRequestV2, "expected_request_type_invalid")
    _require(type(request.binding) is DeveloperTaskGuestRequestBindingV2
             and type(request.check_specification) is DeveloperTaskGuestCheckSpecificationV2,
             "expected_request_nested_type_invalid")
    _require(type(request.binding.target_preimage) is DeveloperTaskGuestTargetPreimageV2,
             "expected_request_nested_type_invalid")
    _require(type(request.check_specification.checks) is tuple
             and len(request.check_specification.checks) == 3
             and all(type(x) is DeveloperTaskGuestCheck for x in request.check_specification.checks),
             "expected_request_nested_type_invalid")
    _require(type(request.context) is tuple
             and 1 <= len(request.context) <= GUEST_REQUEST_MAX_CONTEXT_FILES
             and all(type(x) is DeveloperTaskGuestBoundSourceV2 for x in request.context),
             "expected_context_invalid")
    # Shape before field access; all values are subsequently rebuilt and compared.
    try:
        target_path = request.binding.target_preimage.path
        rebuilt = prepare_developer_task_guest_request_v2(
            task_id=request.task_id, title=request.title, request_id=request.request_id,
            instruction=request.instruction, task_base_commit=request.binding.task_base_commit,
            task_base_tree=request.binding.task_base_tree, target_path=target_path,
            context_entries=tuple(DeveloperTaskGuestContextInputV2(x.path, x.mode, x.git_blob_oid, x.content)
                                  for x in request.context),
            profile_document=profile_document,
        )
        _require(_canonical(request.to_dict()) == _canonical(rebuilt.to_dict()),
                 "expected_request_inconsistent")
    except DeveloperTaskGuestRequestError:
        raise
    except (AttributeError, TypeError, ValueError, RecursionError) as exc:
        raise DeveloperTaskGuestRequestError("expected_request_inconsistent") from exc
    return rebuilt


def canonical_developer_task_guest_request_v2(
    request: DeveloperTaskGuestRequestV2, *, profile_document: bytes,
) -> bytes:
    rebuilt = _validated_expected(request, profile_document=profile_document)
    raw = _canonical(rebuilt.to_dict()) + b"\n"
    _require(len(raw) <= GUEST_REQUEST_MAX_JSON_BYTES, "request_json_size_invalid")
    return raw


def _json_object(raw: bytes) -> dict[str, Any]:
    _require(type(raw) is bytes, "request_bytes_required")
    _require(0 < len(raw) <= GUEST_REQUEST_MAX_JSON_BYTES, "request_json_size_invalid")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in items:
            _require(k not in out, "duplicate_json_key")
            out[k] = v
        return out

    def constant(_value: str) -> None:
        raise DeveloperTaskGuestRequestError("nonfinite_json_number")

    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs, parse_constant=constant)
    except DeveloperTaskGuestRequestError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DeveloperTaskGuestRequestError("invalid_request_json") from exc
    _require(type(value) is dict, "request_object_required")
    todo = [(value, 1)]
    while todo:
        item, depth = todo.pop()
        _require(depth <= GUEST_REQUEST_MAX_JSON_DEPTH, "request_json_depth_exceeded")
        if type(item) is dict:
            todo.extend((x, depth + 1) for x in item.values())
        elif type(item) is list:
            todo.extend((x, depth + 1) for x in item)
    return value


def parse_developer_task_guest_request_v2(
    raw: bytes, *, expected_request: DeveloperTaskGuestRequestV2, profile_document: bytes,
) -> DeveloperTaskGuestRequestV2:
    """Require equality to the separately retained trusted request, not just hashes.

    This function cannot establish that base commit/tree or source blobs were
    actually read from a repository. That observation is an upstream obligation.
    """
    data = _json_object(raw)
    _require(type(data.get("schema_version")) is int
             and data["schema_version"] == GUEST_REQUEST_SCHEMA_VERSION, "request_schema_unsupported")
    _require(data.get("kind") == GUEST_REQUEST_KIND, "request_kind_mismatch")
    expected = _validated_expected(expected_request, profile_document=profile_document)
    trusted = expected.to_dict()
    _require(set(data) == set(trusted), "request_fields_invalid")
    # Canonical-byte comparison preserves scalar types (True is not 1), exact
    # check order, base/preimage/profile binding, instruction and context digest.
    _require(_canonical(data) == _canonical(trusted), "request_binding_mismatch")
    return expected


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestRequestValidation:
    status: str
    issue_codes: tuple[str, ...]
    request: DeveloperTaskGuestRequestV2 | None = None

    @property
    def ok(self) -> bool:
        return (self.status == GUEST_REQUEST_VALID_STATUS and not self.issue_codes
                and type(self.request) is DeveloperTaskGuestRequestV2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok, "status": self.status, "issue_codes": list(self.issue_codes),
            "validation_scope": "V2_MANUAL_REQUEST_ENVELOPE_DATA_ONLY",
            "request_envelope_validated": self.ok,
            "request_binding_validated": self.ok,
            "request_fingerprint": self.request.fingerprint if self.ok else "",
            "task_validated": False, "proposal_validated": False, "manifest_validated": False,
            "patch_validated": False, "preflight_validated": False, "execution_plan_validated": False,
            "repository_observed": False, "source_membership_verified": False,
            "model_provider_called": False, "capability_issued": False,
            "guest_profile_executed": False, "required_profile_checks_passed": False,
            "all_required_checks_passed": False, "ready_to_promote": False,
            "runtime_authorized": False, "promotion_authorized": False,
            "behavioral_correctness": "NOT_EVALUATED",
        }


def validate_developer_task_guest_request_v2(
    raw: bytes, *, expected_request: DeveloperTaskGuestRequestV2, profile_document: bytes,
) -> DeveloperTaskGuestRequestValidation:
    try:
        request = parse_developer_task_guest_request_v2(
            raw, expected_request=expected_request, profile_document=profile_document,
        )
    except DeveloperTaskGuestRequestError as exc:
        return DeveloperTaskGuestRequestValidation(GUEST_REQUEST_REJECTED_STATUS, (exc.code,))
    return DeveloperTaskGuestRequestValidation(GUEST_REQUEST_VALID_STATUS, (), request)
