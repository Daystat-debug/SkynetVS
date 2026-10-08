from __future__ import annotations

"""V2 source-preflight facts. These data objects never confer execution authority."""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

GUEST_PREFLIGHT_KIND = "DTR_GUEST_SOURCE_PREFLIGHT_V2"
GUEST_PREFLIGHT_POLICY_ID = "skynetvs-v1c6-one-python-modify-preflight-v2"
GUEST_PREFLIGHT_PASS = "SOURCE_PREFLIGHT_VERIFIED_NOT_AUTHORIZED"
GUEST_PREFLIGHT_REJECTED = "GUEST_SOURCE_PREFLIGHT_REJECTED"
# Exact Git blob, independently reconstructed from the accepted 73fef5c6 base.
# Full-byte identity preserves the reviewed legacy topology without executing it.
PROTECTED_PIPELINE_PATH = "tools/pipeline.py"
PROTECTED_PIPELINE_OID = "058c7e9da07c253355154006a189378500490df8"
PROTECTED_PIPELINE_BYTES = 90064
PROTECTED_PIPELINE_SHA256 = "e5ddf0ce77dea99c9cce14d8820f81109e281144e322a79eacbdc2d604a98221"
STAGES = (
    "manifest_response_request", "patch_format", "repository", "source_membership",
    "profile_entrypoints", "patch_applicability", "patch_scope", "candidate_tree",
    "repository_unchanged", "temporary_cleanup",
)


class DeveloperTaskGuestPreflightError(ValueError):
    """Stable code only: no source, patch, response or Git stderr is disclosed."""
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise DeveloperTaskGuestPreflightError(code)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def object_oid(kind: str, raw: bytes) -> str:
    return hashlib.sha1(kind.encode("ascii") + b" " + str(len(raw)).encode("ascii")
                        + b"\0" + raw).hexdigest()


@dataclass(frozen=True, slots=True)
class GuestPreflightFactsV2:
    observation_id: str
    repository_root: str
    task_base_commit: str
    task_base_tree: str
    request_fingerprint: str
    manifest_fingerprint: str
    source_sha256: str
    patch_sha256: str
    profile_sha256: str
    target_path: str
    target_preimage_oid: str
    candidate_blob_oid: str
    candidate_content_sha256: str
    candidate_content_bytes: int
    candidate_tree: str
    git_executable_sha256: str
    git_version: str
    repository_snapshot_sha256: str
    tracked_paths: int
    protected_entrypoints: int
    pipeline_blob_oid: str
    context_files: int

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def fingerprint(self) -> str:
        return sha(canonical({"kind": GUEST_PREFLIGHT_KIND,
                              "policy_id": GUEST_PREFLIGHT_POLICY_ID, **self.to_dict()}))


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestPreflightResult:
    facts: GuestPreflightFactsV2 | None
    completed_stages: tuple[str, ...]
    issue_codes: tuple[str, ...]
    repository_observed: bool = False
    repository_unchanged_verified: bool = False
    temporary_cleanup_verified: bool = False
    git_command_count: int = 0

    @property
    def ok(self) -> bool:
        return (type(self.facts) is GuestPreflightFactsV2
                and not self.issue_codes and self.completed_stages == STAGES
                and self.repository_observed and self.repository_unchanged_verified
                and self.temporary_cleanup_verified)

    @property
    def status(self) -> str:
        return GUEST_PREFLIGHT_PASS if self.ok else GUEST_PREFLIGHT_REJECTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": GUEST_PREFLIGHT_KIND, "schema_version": 2,
            "policy_id": GUEST_PREFLIGHT_POLICY_ID, "ok": self.ok, "status": self.status,
            "issue_codes": list(self.issue_codes), "completed_stages": list(self.completed_stages),
            "facts": self.facts.to_dict() if self.ok else None,
            "accepted_preflight_binding": self.facts.fingerprint if self.ok else "",
            "validation_scope": "READ_ONLY_BASE_CONTEXT_PROFILE_ENTRYPOINTS_AND_ONE_TEXT_MODIFY",
            "preflight_validated": self.ok, "patch_validated": self.ok,
            "patch_scope_validated": self.ok, "patch_applicability_verified": self.ok,
            "source_membership_verified": self.ok, "candidate_tree_computed": self.ok,
            "protected_entrypoints_verified": self.ok, "protected_pipeline_identity_verified": self.ok,
            "repository_observed": self.repository_observed,
            "repository_unchanged_verified": self.repository_unchanged_verified,
            "temporary_cleanup_verified": self.temporary_cleanup_verified,
            "git_command_count": self.git_command_count,
            "completed_task_checks": ["git_diff_check"] if self.ok else [],
            "pending_task_checks": ["py_compile", "pipeline:check_guest_source_v1"],
            "protected_helper_closure_verified": False,
            "execution_plan_validated": False, "task_execution_authorized": False,
            "provider_authenticated": False, "replay_prevention_verified": False,
            "git_runtime_bundle_accepted": False, "capability_issued": False,
            "guest_profile_executed": False, "changed_task_code_executed": False,
            "required_profile_checks_passed": False, "all_required_checks_passed": False,
            "ready_to_promote": False, "runtime_authorized": False,
            "promotion_authorized": False, "legacy_full_check_equivalent": False,
            "behavioral_correctness": "NOT_EVALUATED",
            "live_repository_write_attempted": False, "network_requested": False,
            "sandbox_launched": False, "once_marker_created": False,
            "threat_model": "quiescent trusted local repository and trusted caller; not a same-user attacker sandbox",
        }


@dataclass(frozen=True, slots=True)
class GuestPatchFormat:
    old_oid_prefix: str
    new_oid_prefix: str
    hunks: int


def validate_guest_patch_format(raw: bytes, target_path: str, preimage_oid: str) -> GuestPatchFormat:
    """Conservative single-file Git unified diff; applicability is checked by Git later.

    No preamble/trailer, rename/copy, binary, mode changes, quoted/timestamp paths,
    combined diff or second file. Hunk content stays byte-exact; no EOL rewriting.
    """
    require(type(raw) is bytes and 0 < len(raw) <= 128 * 1024, "patch_bytes_invalid")
    require(b"\0" not in raw and raw.endswith(b"\n"), "patch_termination_invalid")
    try:
        text = raw.decode("utf-8", "strict")
        target = target_path.encode("utf-8", "strict")
    except (UnicodeError, AttributeError) as exc:
        raise DeveloperTaskGuestPreflightError("patch_utf8_invalid") from exc
    del text
    # Split solely on LF. Unicode line separators and CR in content are literal.
    lines = [line + b"\n" for line in raw.split(b"\n")[:-1]]
    require(lines[0] == b"diff --git a/" + target + b" b/" + target + b"\n", "patch_target_header")
    i = 1
    old = new = ""
    if i < len(lines) and lines[i].startswith(b"index "):
        m = re.fullmatch(rb"index ([0-9a-f]{7,40})\.\.([0-9a-f]{7,40})(?: (100644))?\n", lines[i])
        require(m is not None, "patch_index_header")
        old, new = m.group(1).decode(), m.group(2).decode()
        require(preimage_oid.startswith(old), "patch_old_oid_mismatch")
        i += 1
    require(lines[i:i+2] == [b"--- a/" + target + b"\n", b"+++ b/" + target + b"\n"], "patch_file_headers")
    i += 2
    hunks = 0
    edits = 0
    while i < len(lines):
        h = re.fullmatch(rb"@@ -([0-9]{1,9})(?:,([0-9]{1,9}))? \+([0-9]{1,9})(?:,([0-9]{1,9}))? @@[^\r\n]*\n", lines[i])
        require(h is not None, "patch_hunk_header")
        old_count = int(h.group(2)) if h.group(2) is not None else 1
        new_count = int(h.group(4)) if h.group(4) is not None else 1
        require(0 < old_count + new_count <= 262144, "patch_hunk_count")
        i += 1
        a = b = 0
        marker_allowed = False
        while i < len(lines) and not lines[i].startswith(b"@@ "):
            line = lines[i]
            if line == b"\\ No newline at end of file\n":
                require(marker_allowed, "patch_newline_marker")
                marker_allowed = False
            elif line[:1] in (b" ", b"+", b"-"):
                require(a < old_count or b < new_count, "patch_trailer")
                a += line[:1] in (b" ", b"-")
                b += line[:1] in (b" ", b"+")
                edits += line[:1] in (b"+", b"-")
                marker_allowed = True
            else:
                raise DeveloperTaskGuestPreflightError("patch_extra_or_unsupported_section")
            require(a <= old_count and b <= new_count, "patch_hunk_overflow")
            i += 1
        require((a, b) == (old_count, new_count), "patch_hunk_truncated")
        hunks += 1
        require(hunks <= 1024, "patch_hunk_limit")
    require(hunks > 0 and edits > 0, "patch_no_hunks_or_edits")
    return GuestPatchFormat(old, new, hunks)
