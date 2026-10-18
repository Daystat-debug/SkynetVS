"""Read-only, narrow M074 DTR-B evidence viewer.

The receipt is data from a diagnostic run, NOT an authenticated software release,
not an authorization to run, apply, promote or install any patch.
"""
from __future__ import annotations

from io import BytesIO
import hashlib
import stat
import zipfile
from typing import Any

from .core import strict_json, sha256

SCHEMA = "SKYNETVS_DTRB_M074_VIEW_V1"
M074_EVIDENCE_SHA256 = "1ce566fe3c12a233c6c029b3cf1331d1a798ec6f37bc3452d815d37cf5063d13"
EXPECTED_MEMBERS = frozenset({
    "M074_DTRB_Result.json", "M074_DTRB_ExactReport.json",
    "M074_SourceBefore.json", "M074_SourceAfter.json",
    "M074_CleanCheckout.json", "M074_GitCommands.json", "M074_PathBudget.json",
})
MAX_ZIP_BYTES = 2 * 1024 * 1024
MAX_UNCOMPRESSED = 4 * 1024 * 1024
MAX_MEMBER = 1024 * 1024
EXPECTED_CHECKS = ["git_diff_check", "py_compile"]
EXPECTED_PENDING = [{"flow": "check", "type": "pipeline"}]
EXPECTED_STAGES = [
    "DTRA_PLAN", "SOURCE_BEFORE", "ARTIFACT_LAYOUT", "PATCH_MATERIALIZE",
    "PREFLIGHT", "WORKSPACE", "PATCH_APPLY", "STATIC_CHECKS",
    "WORKSPACE_CLEANUP", "SOURCE_AFTER",
]


def require(condition: Any, code: str) -> None:
    if condition is not True:
        raise ValueError("DTRB_EVIDENCE_" + code)


def _as_json(member: bytes, name: str) -> dict[str, Any]:
    parsed = strict_json(member, MAX_MEMBER)
    require(isinstance(parsed, dict), "NOT_OBJECT:" + name)
    return parsed


def read_m074_evidence(data: bytes, *, expected_sha256: str | None = M074_EVIDENCE_SHA256) -> dict[str, dict[str, Any]]:
    require(isinstance(data, bytes) and 0 < len(data) <= MAX_ZIP_BYTES, "ZIP_SIZE")
    if expected_sha256 is not None:
        require(sha256(data) == expected_sha256, "UNRECOGNIZED_ARCHIVE_HASH")
    try:
        with zipfile.ZipFile(BytesIO(data)) as z:
            infos = z.infolist()
            require(len(infos) == len(EXPECTED_MEMBERS), "MEMBER_COUNT")
            require(set(x.filename for x in infos) == EXPECTED_MEMBERS, "MEMBER_NAMES")
            require(len({x.filename.casefold() for x in infos}) == len(infos), "CASE_COLLISION")
            size_total = 0
            for item in infos:
                require(not item.is_dir(), "DIRECTORY_ENTRY")
                mode = (item.external_attr >> 16) & 0o170000
                require(mode not in (stat.S_IFLNK, stat.S_IFDIR), "SPECIAL_ENTRY")
                require(item.file_size <= MAX_MEMBER, "MEMBER_SIZE")
                require(item.compress_size <= MAX_ZIP_BYTES, "COMPRESSED_SIZE")
                size_total += item.file_size
            require(size_total <= MAX_UNCOMPRESSED, "TOTAL_SIZE")
            return {name: _as_json(z.read(name), name) for name in EXPECTED_MEMBERS}
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError) as exc:
        raise ValueError("DTRB_EVIDENCE_CORRUPT_ARCHIVE") from exc


def _same(a: Any, b: Any, code: str) -> None:
    require(a == b, code)


def inspect_m074_evidence(data: bytes, *, request: Any, review: dict[str, Any],
                          preview: dict[str, Any], expected_sha256: str | None = M074_EVIDENCE_SHA256) -> dict[str, Any]:
    """Check one known diagnostic receipt against an existing, accepted DTR-A session.

    `expected_sha256=None` is reserved for negative *unit tests*, not UI actions.
    """
    require(request is not None and review is not None and preview is not None, "SESSION_MISSING")
    require(review.get("intake", {}).get("ok") is True, "DTRA_NOT_ACCEPTED")
    require(preview.get("preview_status") == "TEXT_APPLICABLE_AST_PASS_NOT_EXECUTABLE_CHECKS", "PREVIEW_NOT_ACCEPTED")
    _same(preview.get("request_fingerprint"), request.request_fingerprint, "PREVIEW_BINDING")
    _same(preview.get("response_sha256"), review.get("response_sha256"), "PREVIEW_RESPONSE")
    _same(preview.get("target_path"), request.target_path, "PREVIEW_TARGET")
    docs = read_m074_evidence(data, expected_sha256=expected_sha256)
    outer = docs["M074_DTRB_Result.json"]
    report = docs["M074_DTRB_ExactReport.json"]
    before = docs["M074_SourceBefore.json"]
    after = docs["M074_SourceAfter.json"]
    checkout = docs["M074_CleanCheckout.json"]
    budget = docs["M074_PathBudget.json"]
    cmds = docs["M074_GitCommands.json"]

    _same(outer.get("schema"), "SKYNETVS_M074_DTRB_RESULT_V1", "OUTER_SCHEMA")
    _same(outer.get("status"), "M074_CLEAN_COMMIT_STATIC_REHEARSAL_PASS_NONACTIVE", "OUTER_STATUS")
    _same(outer.get("stage"), "COMPLETE", "OUTER_STAGE")
    _same(outer.get("dtrb_status"), "STATIC_REHEARSAL_RECORDED_NOT_PROMOTABLE", "OUTER_DTRB_STATUS")
    _same(outer.get("dtrb_completed_checks"), EXPECTED_CHECKS, "OUTER_CHECKS")
    _same(outer.get("dtrb_pending_checks"), EXPECTED_PENDING, "OUTER_PENDING")
    _same(outer.get("request_fingerprint"), request.request_fingerprint, "OUTER_BINDING")
    _same(outer.get("requested_base_commit"), request.base_commit, "OUTER_COMMIT")
    require(outer.get("path_budget_pass") is True and outer.get("source_inputs_stable") is True, "OUTER_INPUTS")
    require(outer.get("patch_applied_in_isolated_workspace") is True and outer.get("source_snapshot_separately_clean") is True, "OUTER_SNAPSHOT")
    require(outer.get("dirty_source_preserved") is True, "DIRTY_PRESERVATION")
    require(outer.get("clean_snapshot_head") == request.base_commit, "CLEAN_HEAD")
    for field in ("changed_code_executed", "pipeline_executed", "source_repository_written_by_runner",
                  "runtime_authorized", "promotion_authorized", "installation_authorized", "production_origin_verified", "os_sandbox_claimed"):
        require(outer.get(field) is False, "OUTER_AUTHORITY:" + field)

    _same(report.get("status"), outer["dtrb_status"], "REPORT_STATUS")
    _same(report.get("request_fingerprint"), request.request_fingerprint, "REPORT_BINDING")
    _same(report.get("base_commit"), request.base_commit, "REPORT_COMMIT")
    _same(report.get("target_path"), request.target_path, "REPORT_TARGET")
    _same(report.get("raw_response_sha256"), review.get("response_sha256"), "REPORT_RESPONSE")
    _same(report.get("completed_checks"), EXPECTED_CHECKS, "REPORT_CHECKS")
    _same(report.get("pending_executable_checks"), EXPECTED_PENDING, "REPORT_PENDING")
    _same(report.get("source_snapshot_before"), report.get("source_snapshot_after"), "REPORT_SOURCE_CHANGED")
    for field in ("ok", "patch_applied_in_isolated_workspace", "workspace_removed", "source_repository_unchanged", "patch_materialized", "result_recorded"):
        require(report.get(field) is True, "REPORT_MISSING_PASS:" + field)
    for field in ("changed_code_executed", "ready_to_promote", "all_required_checks_passed", "runtime_authorized",
                  "promotion_authorized", "authority_granted", "model_provider_called", "network", "native_worker_launched", "sandbox"):
        require(report.get(field) is False, "REPORT_AUTHORITY:" + field)
    _same(report.get("behavioral_correctness"), "NOT_EVALUATED", "REPORT_BEHAVIOR")
    _same(report.get("issue_codes"), [], "REPORT_ISSUES")
    _same(report.get("issues"), [], "REPORT_ISSUE_DETAILS")
    _same(report.get("terminal_stage"), "RESULT_RECORD", "REPORT_TERMINAL")

    stages = report.get("stage_evidence")
    require(isinstance(stages, list), "STAGES_TYPE")
    _same([s.get("stage") for s in stages if isinstance(s, dict)], EXPECTED_STAGES, "STAGE_ORDER")
    require(all(isinstance(s, dict) and s.get("ok") is True for s in stages), "STAGE_FAILED")
    for stage in stages:
        if stage["stage"] == "STATIC_CHECKS":
            _same(stage["payload"].get("completed_checks"), EXPECTED_CHECKS, "STAGE_STATIC_CHECKS")
            _same(stage["payload"].get("changed_files"), [request.target_path], "STAGE_TARGET")
        if stage["stage"] == "WORKSPACE_CLEANUP":
            require(stage["payload"].get("removed") is True, "STAGE_WORKSPACE_CLEANUP")
        if stage["stage"] == "DTRA_PLAN":
            req = stage["payload"].get("request", {})
            _same(req.get("request_id"), request.request_id, "STAGE_REQUEST_ID")
            _same(req.get("request_fingerprint"), request.request_fingerprint, "STAGE_REQUEST_FINGERPRINT")
            _same(req.get("base_commit"), request.base_commit, "STAGE_REQUEST_COMMIT")
            _same(req.get("target_write_allowlist"), [request.target_path], "STAGE_REQUEST_TARGET")

    _same(before, after, "LIVE_SOURCE_CHANGED")
    _same(before.get("head"), request.base_commit, "LIVE_HEAD")
    _same(before.get("tree"), request.base_tree, "LIVE_TREE")
    preimage = next(item for item in request.context if item.path == request.target_path)
    _same(before.get("target_index_sha256"), preimage.content_sha256, "LIVE_PREIMAGE")
    require(checkout.get("checkout_accepted") is True, "CHECKOUT_NOT_ACCEPTED")
    _same(checkout.get("head"), request.base_commit, "CHECKOUT_HEAD")
    _same(checkout.get("tree"), request.base_tree, "CHECKOUT_TREE")
    require(budget.get("passed") is True and budget.get("tracked_files") == 552, "PATH_BUDGET")
    require(isinstance(cmds.get("commands"), list) and len(cmds["commands"]) >= 1, "NO_GIT_COMMANDS")

    return {
        "schema": SCHEMA, "result_kind": "EXTERNAL_DIAGNOSTIC_RECEIPT_VIEW_ONLY",
        "source_kind": "USER_SUPPLIED_M074_EVIDENCE_HASH_PINNED",
        "evidence_sha256": sha256(data), "request_id": request.request_id,
        "request_fingerprint": request.request_fingerprint, "target_path": request.target_path,
        "base_commit": request.base_commit, "response_sha256": review["response_sha256"],
        "static_preview": "EXACT_BYTE_IN_MEMORY_PASS_AND_AST_PASS",
        "dtrb_status": "STATIC_REHEARSAL_RECORDED_NOT_PROMOTABLE",
        "git_diff_check": "PASS_REPORTED_BY_M074", "py_compile": "PASS_REPORTED_BY_M074",
        "pipeline_check": "NOT_RUN", "changed_code_executed": False,
        "patch_applied_only_in_isolated_workspace": True,
        "source_repository_unchanged_per_receipt": True,
        "workspace_removed_per_receipt": True,
        "behavior_tested": False, "os_sandbox_attested": False, "report_origin_authenticated": False,
        "runtime_authorized": False, "installation_authorized": False,
        "promotion_authorized": False,
        "message": "По согласованному M074 evidence статические проверки прошли. Внешний отчёт не является доверенной подписью; "
                   "код не выполнялся, pipeline и проверка поведения не выполнены, применение в рабочий Git запрещено.",
    }
