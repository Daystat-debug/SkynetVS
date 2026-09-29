from __future__ import annotations

import hashlib
import json
import re

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from modules.developer.developer_task_contract import (
    DEVELOPER_CHECK_GIT_DIFF,
    DEVELOPER_CHECK_PIPELINE,
    DEVELOPER_CHECK_PY_COMPILE,
    DEVELOPER_TASK_INSTALL_MANUAL_CONFIRMATION,
    DeveloperTaskCheck,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_proposal_contract import (
    DTR_MAX_CONTEXT_FILE_BYTES,
    DTR_MAX_CONTEXT_FILES,
    DTR_MAX_CONTEXT_TOTAL_BYTES,
    DTR_MAX_EXPLANATION_UTF8_BYTES,
    DTR_MAX_INSTRUCTION_UTF8_BYTES,
    DTR_MAX_JSON_DEPTH,
    DTR_MAX_PATCH_UTF8_BYTES,
    DTR_MAX_RAW_RESPONSE_BYTES,
    DTR_MAX_TARGET_FILE_BYTES,
    DTR_PROPOSAL_KIND,
    DTR_PROPOSAL_ORIGIN,
    DTR_PROPOSAL_PATCH_FILE,
    DTR_PROPOSAL_POLICY_ID,
    DTR_PROPOSAL_PROFILE_ID,
    DTR_PROPOSAL_REQUEST_SCHEMA_VERSION,
    DTR_PROPOSAL_SCHEMA_VERSION,
    DTR_PROPOSAL_TRANSPORT_MODE,
    DeveloperTaskPatchProposal,
    DeveloperTaskProposalBoundSource,
    DeveloperTaskProposalContextInput,
    DeveloperTaskProposalIntakeResult,
    DeveloperTaskProposalIssue,
    DeveloperTaskProposalPlan,
    DeveloperTaskProposalRequest,
    DeveloperTaskProposalRequestError,
    canonical_dtr_json_bytes,
    dtr_sha256,
)
from modules.developer.developer_task_validator import (
    validate_developer_task_manifest,
)


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,95}$")
_TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_GIT_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")

_PROPOSAL_FIELDS = frozenset({
    "kind",
    "schema_version",
    "request_id",
    "request_fingerprint",
    "patch_text",
    "explanation",
})

_READ_FORBIDDEN_EXACT = frozenset({
    ".env",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
})
_READ_FORBIDDEN_PREFIXES = (
    ".git/",
    ".venv/",
    "venv/",
    "data/",
    "models/",
    "native/",
)
_TARGET_PROTECTED_EXACT = frozenset({
    "main.py",
    "test.py",
    "modules/action_contract.py",
    "modules/action_authority.py",
    "modules/action_broker.py",
    "modules/timer_action_runtime.py",
    "modules/volume_action_runtime.py",
})
_TARGET_PROTECTED_PREFIXES = (
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


def _issue(code: str, field: str, message: str) -> DeveloperTaskProposalIssue:
    return DeveloperTaskProposalIssue(code=code, field=field, message=message)


def _encode_text(
    value: Any,
    *,
    field: str,
    max_bytes: int,
    trimmed: bool,
    issues: list[DeveloperTaskProposalIssue],
) -> bytes:
    if not isinstance(value, str):
        issues.append(_issue("invalid_type", field, "Value must be a string."))
        return b""

    if not value or (trimmed and value != value.strip()):
        issues.append(_issue("invalid_string", field, "Value must be non-empty and valid for this field."))

    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeEncodeError:
        issues.append(_issue("invalid_unicode", field, "Value must encode as strict UTF-8."))
        return b""

    if len(encoded) > max_bytes:
        issues.append(_issue("too_large", field, f"Value exceeds {max_bytes} UTF-8 bytes."))

    if "\x00" in value:
        issues.append(_issue("control_character", field, "NUL is forbidden."))

    return encoded


def _normalize_repo_path(
    raw: Any,
    *,
    field: str,
    issues: list[DeveloperTaskProposalIssue],
) -> str:
    if not isinstance(raw, str):
        issues.append(_issue("invalid_type", field, "Repository path must be a string."))
        return ""

    if not raw or raw != raw.strip():
        issues.append(_issue("invalid_path", field, "Repository path must be non-empty and trimmed."))
        return ""

    if len(raw) > 240:
        issues.append(_issue("path_too_long", field, "Repository path exceeds 240 characters."))

    if "\\" in raw:
        issues.append(_issue("backslash_path", field, "Repository paths must use forward slashes."))

    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        issues.append(_issue("absolute_path", field, "Absolute repository paths are forbidden."))

    if "\x00" in raw:
        issues.append(_issue("control_character", field, "NUL is forbidden in repository paths."))

    path = PurePosixPath(raw)
    parts = path.parts

    if not parts or any(part in {"", ".", ".."} for part in parts):
        issues.append(_issue("path_traversal", field, "Relative traversal and empty path segments are forbidden."))

    if any(len(part) > 120 for part in parts):
        issues.append(_issue("path_segment_too_long", field, "Repository path segment exceeds 120 characters."))

    if any(part.startswith(".") for part in parts):
        issues.append(_issue("hidden_path", field, "Hidden repository paths are forbidden in DTR source context."))

    normalized = path.as_posix()
    if normalized != raw:
        issues.append(_issue("noncanonical_path", field, "Repository path must already be canonical POSIX form."))

    return normalized


def _git_blob_oid(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _read_context_forbidden(path: str) -> bool:
    lower = path.casefold()
    return (
        lower in _READ_FORBIDDEN_EXACT
        or any(lower.startswith(prefix) for prefix in _READ_FORBIDDEN_PREFIXES)
    )


def _target_protected(path: str) -> bool:
    lower = path.casefold()
    name = PurePosixPath(lower).name
    return (
        lower in _TARGET_PROTECTED_EXACT
        or any(lower.startswith(prefix) for prefix in _TARGET_PROTECTED_PREFIXES)
        or name == "__init__.py"
        or name.startswith("test_")
        or name.startswith("eval_")
        or name.endswith("_test.py")
    )


def _fixed_checks() -> tuple[DeveloperTaskCheck, ...]:
    return (
        DeveloperTaskCheck(type=DEVELOPER_CHECK_GIT_DIFF),
        DeveloperTaskCheck(
            type=DEVELOPER_CHECK_PY_COMPILE,
            scope="changed_python_files",
        ),
        DeveloperTaskCheck(
            type=DEVELOPER_CHECK_PIPELINE,
            flow="check",
        ),
    )


def _context_digest(context: tuple[DeveloperTaskProposalBoundSource, ...]) -> str:
    payload = [item.binding_dict() for item in context]
    return dtr_sha256(canonical_dtr_json_bytes(payload))


def _request_fingerprint_payload(request: DeveloperTaskProposalRequest) -> dict[str, Any]:
    return request.binding_dict(include_fingerprint=False)


def developer_task_proposal_request_fingerprint(
    request: DeveloperTaskProposalRequest,
) -> str:
    if type(request) is not DeveloperTaskProposalRequest:
        raise TypeError("request must be DeveloperTaskProposalRequest")
    return dtr_sha256(canonical_dtr_json_bytes(_request_fingerprint_payload(request)))


def prepare_developer_task_proposal_request(
    *,
    task_id: str,
    title: str,
    request_id: str,
    instruction: str,
    base_commit: str,
    base_tree: str,
    target_path: str,
    context_entries: Sequence[DeveloperTaskProposalContextInput],
    origin: str = DTR_PROPOSAL_ORIGIN,
) -> DeveloperTaskProposalRequest:
    """Bind trusted task/context data without reading files or granting execution authority."""
    issues: list[DeveloperTaskProposalIssue] = []

    _encode_text(task_id, field="task_id", max_bytes=64, trimmed=True, issues=issues)
    if isinstance(task_id, str) and task_id and not _TASK_ID_RE.fullmatch(task_id):
        issues.append(_issue("invalid_task_id", "task_id", "task_id must match the existing manifest contract."))

    _encode_text(title, field="title", max_bytes=160 * 4, trimmed=True, issues=issues)
    if isinstance(title, str):
        if len(title) > 160:
            issues.append(_issue("title_too_long", "title", "title exceeds the existing 160-character manifest limit."))
        if any(ord(char) < 32 or ord(char) == 127 for char in title):
            issues.append(_issue("control_character", "title", "Control characters are forbidden in title."))

    _encode_text(request_id, field="request_id", max_bytes=96, trimmed=True, issues=issues)
    if isinstance(request_id, str) and request_id and not _REQUEST_ID_RE.fullmatch(request_id):
        issues.append(_issue("invalid_request_id", "request_id", "request_id has an invalid format."))

    _encode_text(
        instruction,
        field="instruction",
        max_bytes=DTR_MAX_INSTRUCTION_UTF8_BYTES,
        trimmed=False,
        issues=issues,
    )
    if isinstance(instruction, str) and not instruction.strip():
        issues.append(_issue("invalid_string", "instruction", "Instruction must contain non-whitespace text."))

    if type(origin) is not str or origin != DTR_PROPOSAL_ORIGIN:
        issues.append(_issue("unsupported_origin", "origin", "Initial DTR intake admits manual origin only."))

    if type(base_commit) is not str or not _GIT_SHA1_RE.fullmatch(base_commit):
        issues.append(_issue("invalid_base_commit", "base_commit", "base_commit must be one full lowercase SHA-1."))

    if type(base_tree) is not str or not _GIT_SHA1_RE.fullmatch(base_tree):
        issues.append(_issue("invalid_base_tree", "base_tree", "base_tree must be one full lowercase SHA-1."))

    normalized_target = _normalize_repo_path(target_path, field="target_path", issues=issues)
    if normalized_target:
        if not normalized_target.startswith("modules/") or not normalized_target.casefold().endswith(".py"):
            issues.append(_issue("unsupported_target", "target_path", "First DTR profile requires one existing Python module under modules/."))
        if _target_protected(normalized_target):
            issues.append(_issue("protected_target", "target_path", "Target is protected by the DTR first-task profile."))

    if isinstance(context_entries, (str, bytes, bytearray)) or not isinstance(context_entries, Sequence):
        issues.append(_issue("invalid_type", "context_entries", "context_entries must be a finite sequence."))
        context_entries = ()

    if not 1 <= len(context_entries) <= DTR_MAX_CONTEXT_FILES:
        issues.append(_issue("context_count", "context_entries", f"Context must contain 1 to {DTR_MAX_CONTEXT_FILES} files."))

    bound: list[DeveloperTaskProposalBoundSource] = []
    seen_casefold: set[str] = set()
    total_bytes = 0

    for index, entry in enumerate(context_entries):
        field = f"context_entries[{index}]"
        if type(entry) is not DeveloperTaskProposalContextInput:
            issues.append(_issue("invalid_type", field, "Context item must be DeveloperTaskProposalContextInput."))
            continue

        path = _normalize_repo_path(entry.path, field=f"{field}.path", issues=issues)
        if path and _read_context_forbidden(path):
            issues.append(_issue("forbidden_context_path", f"{field}.path", "Context path is forbidden by DTR disclosure policy."))

        folded = path.casefold()
        if path and folded in seen_casefold:
            issues.append(_issue("duplicate_context_path", f"{field}.path", "Context paths must be unique case-insensitively."))
        if path:
            seen_casefold.add(folded)

        if type(entry.mode) is not str or entry.mode != "100644":
            issues.append(_issue("unsupported_mode", f"{field}.mode", "DTR first profile accepts regular 100644 files only."))

        if type(entry.git_blob_oid) is not str or not _GIT_SHA1_RE.fullmatch(entry.git_blob_oid):
            issues.append(_issue("invalid_blob_oid", f"{field}.git_blob_oid", "git_blob_oid must be one full lowercase SHA-1."))

        if not isinstance(entry.content, (bytes, bytearray)):
            issues.append(_issue("invalid_type", f"{field}.content", "Context content must be bytes-like."))
            content = b""
        else:
            content = bytes(entry.content)

        if len(content) > DTR_MAX_CONTEXT_FILE_BYTES:
            issues.append(_issue("context_file_too_large", f"{field}.content", f"Context file exceeds {DTR_MAX_CONTEXT_FILE_BYTES} bytes."))

        if (
            type(entry.git_blob_oid) is str
            and _GIT_SHA1_RE.fullmatch(entry.git_blob_oid)
            and entry.git_blob_oid != _git_blob_oid(content)
        ):
            issues.append(_issue("blob_content_mismatch", f"{field}.git_blob_oid", "git_blob_oid does not match the exact context bytes."))

        total_bytes += len(content)
        bound.append(
            DeveloperTaskProposalBoundSource(
                path=path,
                mode=entry.mode if isinstance(entry.mode, str) else "",
                git_blob_oid=entry.git_blob_oid if isinstance(entry.git_blob_oid, str) else "",
                content_sha256=dtr_sha256(content),
                content_bytes=len(content),
                content=content,
            )
        )

    if total_bytes > DTR_MAX_CONTEXT_TOTAL_BYTES:
        issues.append(_issue("context_total_too_large", "context_entries", f"Context exceeds {DTR_MAX_CONTEXT_TOTAL_BYTES} bytes."))

    bound.sort(key=lambda item: item.path.casefold())
    frozen_context = tuple(bound)
    target_entries = tuple(item for item in frozen_context if item.path == normalized_target)

    if normalized_target and len(target_entries) != 1:
        issues.append(_issue("target_not_bound", "target_path", "Target must appear exactly once in the source context."))
    elif target_entries and target_entries[0].content_bytes > DTR_MAX_TARGET_FILE_BYTES:
        issues.append(_issue("target_too_large", "target_path", f"Target exceeds {DTR_MAX_TARGET_FILE_BYTES} bytes."))

    if issues:
        raise DeveloperTaskProposalRequestError(issues)

    checks = _fixed_checks()
    digest = _context_digest(frozen_context)
    provisional = DeveloperTaskProposalRequest(
        schema_version=DTR_PROPOSAL_REQUEST_SCHEMA_VERSION,
        policy_id=DTR_PROPOSAL_POLICY_ID,
        profile_id=DTR_PROPOSAL_PROFILE_ID,
        transport_mode=DTR_PROPOSAL_TRANSPORT_MODE,
        origin=DTR_PROPOSAL_ORIGIN,
        task_id=task_id,
        title=title,
        request_id=request_id,
        instruction=instruction,
        base_commit=base_commit,
        base_tree=base_tree,
        target_path=normalized_target,
        context=frozen_context,
        context_digest=digest,
        checks=checks,
        install_policy=DEVELOPER_TASK_INSTALL_MANUAL_CONFIRMATION,
        request_fingerprint="",
    )
    fingerprint = developer_task_proposal_request_fingerprint(provisional)
    return DeveloperTaskProposalRequest(
        schema_version=provisional.schema_version,
        policy_id=provisional.policy_id,
        profile_id=provisional.profile_id,
        transport_mode=provisional.transport_mode,
        origin=provisional.origin,
        task_id=provisional.task_id,
        title=provisional.title,
        request_id=provisional.request_id,
        instruction=provisional.instruction,
        base_commit=provisional.base_commit,
        base_tree=provisional.base_tree,
        target_path=provisional.target_path,
        context=provisional.context,
        context_digest=provisional.context_digest,
        checks=provisional.checks,
        install_policy=provisional.install_policy,
        request_fingerprint=fingerprint,
    )


def _validate_bound_request(request: DeveloperTaskProposalRequest) -> tuple[DeveloperTaskProposalIssue, ...]:
    issues: list[DeveloperTaskProposalIssue] = []

    if type(request) is not DeveloperTaskProposalRequest:
        return (_issue("invalid_request_type", "request", "Request must be an exact DeveloperTaskProposalRequest."),)

    if type(request.context) is not tuple or any(
        type(item) is not DeveloperTaskProposalBoundSource
        for item in request.context
    ):
        return (_issue("invalid_request_context", "request.context", "Bound request context has an invalid runtime type."),)

    context_inputs = tuple(
        DeveloperTaskProposalContextInput(
            path=item.path,
            mode=item.mode,
            git_blob_oid=item.git_blob_oid,
            content=item.content,
        )
        for item in request.context
    )

    try:
        canonical = prepare_developer_task_proposal_request(
            task_id=request.task_id,
            title=request.title,
            request_id=request.request_id,
            instruction=request.instruction,
            base_commit=request.base_commit,
            base_tree=request.base_tree,
            target_path=request.target_path,
            context_entries=context_inputs,
            origin=request.origin,
        )
    except DeveloperTaskProposalRequestError as exc:
        return tuple(
            _issue(
                f"request_{item.code}",
                f"request.{item.field}",
                item.message,
            )
            for item in exc.issues
        )

    if request.schema_version != canonical.schema_version:
        issues.append(_issue("request_schema_mismatch", "request.schema_version", "Unexpected request schema version."))
    if request.policy_id != canonical.policy_id:
        issues.append(_issue("policy_mismatch", "request.policy_id", "Unexpected DTR policy."))
    if request.profile_id != canonical.profile_id:
        issues.append(_issue("profile_mismatch", "request.profile_id", "Unexpected DTR profile."))
    if request.transport_mode != canonical.transport_mode:
        issues.append(_issue("transport_mismatch", "request.transport_mode", "Unexpected transport mode."))
    if request.checks != canonical.checks:
        issues.append(_issue("check_profile_mismatch", "request.checks", "Required fixed check profile changed."))
    if request.install_policy != canonical.install_policy:
        issues.append(_issue("install_policy_mismatch", "request.install_policy", "Install policy changed."))
    if request.context != canonical.context:
        issues.append(_issue("context_binding_mismatch", "request.context", "Bound context differs from the canonical DTR request."))
    if request.context_digest != canonical.context_digest:
        issues.append(_issue("context_digest_mismatch", "request.context_digest", "Context binding changed."))
    if request.request_fingerprint != canonical.request_fingerprint:
        issues.append(_issue("request_fingerprint_mismatch", "request.request_fingerprint", "Request binding changed."))

    return tuple(issues)


class _DuplicateJsonKey(ValueError):
    pass


class _NonFiniteJsonNumber(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise _NonFiniteJsonNumber(value)


def _json_depth(value: Any, depth: int = 1) -> int:
    if isinstance(value, Mapping):
        children = list(value.values())
    elif isinstance(value, list):
        children = value
    else:
        return depth

    if not children:
        return depth
    return max(_json_depth(child, depth + 1) for child in children)


def _contains_unpaired_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        try:
            value.encode("utf-8", "strict")
        except UnicodeEncodeError:
            return True
        return False
    if isinstance(value, Mapping):
        return any(
            _contains_unpaired_surrogate(key) or _contains_unpaired_surrogate(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_unpaired_surrogate(item) for item in value)
    return False


def _parse_proposal_bytes(
    raw_response: bytes,
) -> tuple[dict[str, Any] | None, tuple[DeveloperTaskProposalIssue, ...]]:
    issues: list[DeveloperTaskProposalIssue] = []

    if not raw_response:
        return None, (_issue("empty_response", "$", "Response must not be empty."),)
    if len(raw_response) > DTR_MAX_RAW_RESPONSE_BYTES:
        return None, (_issue("response_too_large", "$", f"Response exceeds {DTR_MAX_RAW_RESPONSE_BYTES} bytes."),)
    if raw_response.startswith(b"\xef\xbb\xbf"):
        return None, (_issue("utf8_bom", "$", "UTF-8 BOM is forbidden."),)

    try:
        text = raw_response.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return None, (_issue("invalid_utf8", "$", "Response must be strict UTF-8."),)

    if text.startswith("\ufeff"):
        return None, (_issue("utf8_bom", "$", "UTF-8 BOM is forbidden."),)

    try:
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except _DuplicateJsonKey as exc:
        return None, (_issue("duplicate_json_key", "$", f"Duplicate JSON key: {exc}."),)
    except _NonFiniteJsonNumber:
        return None, (_issue("non_finite_number", "$", "NaN and Infinity are forbidden."),)
    except json.JSONDecodeError:
        return None, (_issue("invalid_json", "$", "Response must contain exactly one valid JSON value."),)

    if _json_depth(value) > DTR_MAX_JSON_DEPTH:
        issues.append(_issue("json_too_deep", "$", f"JSON exceeds maximum depth {DTR_MAX_JSON_DEPTH}."))
    if _contains_unpaired_surrogate(value):
        issues.append(_issue("invalid_unicode", "$", "JSON strings must encode as strict UTF-8."))
    if not isinstance(value, dict):
        issues.append(_issue("invalid_type", "$", "Proposal root must be an object."))
        return None, tuple(issues)

    unknown = sorted(set(value) - _PROPOSAL_FIELDS)
    missing = sorted(_PROPOSAL_FIELDS - set(value))
    for field in unknown:
        issues.append(_issue("unknown_field", field, "Proposal field is not allowed."))
    for field in missing:
        issues.append(_issue("missing_field", field, "Proposal field is required."))

    return value, tuple(issues)


def intake_developer_task_proposal(
    request: DeveloperTaskProposalRequest,
    raw_response: bytes | bytearray,
) -> DeveloperTaskProposalIntakeResult:
    """Pure model-response intake. Returns data only and never creates task/runtime authority."""
    request_issues = _validate_bound_request(request)
    if request_issues:
        return DeveloperTaskProposalIntakeResult(plan=None, issues=request_issues)

    if not isinstance(raw_response, (bytes, bytearray)):
        return DeveloperTaskProposalIntakeResult(
            plan=None,
            issues=(_issue("invalid_response_type", "$", "raw_response must be bytes-like."),),
        )

    raw_bytes = bytes(raw_response)
    payload, parse_issues = _parse_proposal_bytes(raw_bytes)
    if parse_issues:
        return DeveloperTaskProposalIntakeResult(plan=None, issues=parse_issues)
    assert payload is not None

    issues: list[DeveloperTaskProposalIssue] = []

    kind = payload.get("kind")
    if type(kind) is not str or kind != DTR_PROPOSAL_KIND:
        issues.append(_issue("invalid_kind", "kind", f"kind must be {DTR_PROPOSAL_KIND}."))

    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != DTR_PROPOSAL_SCHEMA_VERSION:
        issues.append(_issue("invalid_schema_version", "schema_version", f"schema_version must be integer {DTR_PROPOSAL_SCHEMA_VERSION}."))

    response_request_id = payload.get("request_id")
    if type(response_request_id) is not str or response_request_id != request.request_id:
        issues.append(_issue("request_id_mismatch", "request_id", "Proposal request_id does not match the trusted request."))

    response_fingerprint = payload.get("request_fingerprint")
    if type(response_fingerprint) is not str or response_fingerprint != request.request_fingerprint:
        issues.append(_issue("request_fingerprint_mismatch", "request_fingerprint", "Proposal fingerprint does not match the trusted request."))

    patch_text = payload.get("patch_text")
    patch_bytes = _encode_text(
        patch_text,
        field="patch_text",
        max_bytes=DTR_MAX_PATCH_UTF8_BYTES,
        trimmed=False,
        issues=issues,
    )
    if isinstance(patch_text, str) and not patch_text.strip():
        issues.append(_issue("invalid_string", "patch_text", "Patch must contain non-whitespace text."))

    explanation = payload.get("explanation")
    _encode_text(
        explanation,
        field="explanation",
        max_bytes=DTR_MAX_EXPLANATION_UTF8_BYTES,
        trimmed=False,
        issues=issues,
    )
    if isinstance(explanation, str) and not explanation.strip():
        issues.append(_issue("invalid_string", "explanation", "Explanation must contain non-whitespace text."))

    if issues:
        return DeveloperTaskProposalIntakeResult(plan=None, issues=tuple(issues))

    assert isinstance(patch_text, str)
    assert isinstance(explanation, str)

    raw_sha256 = dtr_sha256(raw_bytes)
    patch_sha256 = dtr_sha256(patch_bytes)

    proposal = DeveloperTaskPatchProposal(
        kind=DTR_PROPOSAL_KIND,
        schema_version=DTR_PROPOSAL_SCHEMA_VERSION,
        request_id=request.request_id,
        request_fingerprint=request.request_fingerprint,
        raw_response_sha256=raw_sha256,
        raw_response_bytes=raw_bytes,
        patch_text=patch_text,
        patch_sha256=patch_sha256,
        patch_bytes=patch_bytes,
        explanation=explanation,
    )

    manifest_payload = {
        "schema_version": 1,
        "task_kind": "patch",
        "task_id": request.task_id,
        "title": request.title,
        "project": "SkynetVS",
        "origin": DTR_PROPOSAL_ORIGIN,
        "source_ref": f"dtr-proposal:{request.request_id}",
        "source_sha256": raw_sha256,
        "base_commit": request.base_commit,
        "patch_file": DTR_PROPOSAL_PATCH_FILE,
        "patch_sha256": patch_sha256,
        "allowed_files": [request.target_path],
        "checks": [item.to_dict() for item in request.checks],
        "install_policy": request.install_policy,
    }
    manifest_result = validate_developer_task_manifest(manifest_payload)
    if not manifest_result.ok or manifest_result.manifest is None:
        return DeveloperTaskProposalIntakeResult(
            plan=None,
            issues=tuple(
                _issue(
                    f"manifest_{item.code}",
                    f"manifest.{item.field}",
                    item.message,
                )
                for item in manifest_result.issues
            ),
        )

    manifest = manifest_result.manifest
    plan = DeveloperTaskProposalPlan(
        request=request,
        proposal=proposal,
        manifest=manifest,
        manifest_fingerprint=developer_task_manifest_fingerprint(manifest),
    )
    return DeveloperTaskProposalIntakeResult(plan=plan, issues=())
