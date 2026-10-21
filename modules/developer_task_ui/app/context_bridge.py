"""M136 proof-of-integration: deterministic, read-only relation between M134 windows and own AST findings.

This module does not access disk, Git, network, the UI, models, or patch APIs.
It is NOT installed in SkynetVS and does not grant patch-authority.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PATH = re.compile(r"(?:main\.py|modules/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)\Z")
_MAX_FINDINGS = 1000
_MAX_WINDOWS = 24


class ContextBridgeRefusal(ValueError):
    """Invalid, stale or unverified source relationship."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ContextBridgeRefusal(message)


def _path(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= 300 and _PATH.fullmatch(value) is not None


def correlate(goal: str, context: dict, analysis: dict, *, expected_analyzer_schema: str) -> dict:
    """Return provenance-only overlap. Never modify either argument or infer patch quality.

    Inputs are reports from M134.search_repository and existing own_analyzer.
    Callers must not allow this output into an apply/approval gate.
    """
    _require(isinstance(goal, str) and bool(goal.strip()) and len(goal) <= 1200
             and len(goal.encode("utf-8")) <= 2500, "M136_GOAL_INVALID")
    _require(isinstance(context, dict) and context.get("schema") ==
             "SKYNETVS_M134_READONLY_PROJECT_CONTEXT_V1", "M136_CONTEXT_SCHEMA_INVALID")
    _require(context.get("no_patch_or_apply") is True and
             context.get("repo_worktree_not_read") is True, "M136_CONTEXT_NOT_READ_ONLY")
    _require(isinstance(expected_analyzer_schema, str) and bool(expected_analyzer_schema)
             and isinstance(analysis, dict) and analysis.get("schema") == expected_analyzer_schema,
             "M136_ANALYZER_SCHEMA_INVALID")
    commit = context.get("git_commit")
    _require(isinstance(commit, str) and _HEX40.fullmatch(commit) is not None,
             "M136_CONTEXT_COMMIT_INVALID")
    _require(analysis.get("git_commit") == commit, "M136_COMMIT_MISMATCH")
    sha = hashlib.sha256(goal.encode("utf-8")).hexdigest()
    _require(context.get("goal_sha256") == sha, "M136_STALE_GOAL")
    amatch = analysis.get("goal_sha256")
    if amatch is not None:
        _require(amatch == sha, "M136_ANALYSIS_GOAL_MISMATCH")
    metadata = context.get("contexts_metadata")
    _require(isinstance(metadata, dict), "M136_CONTEXT_METADATA_INVALID")
    budget = metadata.get("8192")
    _require(isinstance(budget, dict), "M136_CONTEXT_8192_INVALID")
    windows = budget.get("ranges")
    _require(isinstance(windows, list) and len(windows) <= _MAX_WINDOWS,
             "M136_WINDOWS_INVALID")
    parsed_windows = []
    identifiers = set()
    for index, win in enumerate(windows):
        _require(isinstance(win, dict), "M136_WINDOW_INVALID")
        path, lo, hi = win.get("path"), win.get("start"), win.get("end")
        sh = win.get("source_sha256")
        wh = win.get("window_sha256")
        _require(_path(path) and type(lo) is int and type(hi) is int and 1 <= lo <= hi <= 1_000_000,
                 "M136_WINDOW_SPAN_INVALID")
        _require(isinstance(sh, str) and _HEX64.fullmatch(sh) is not None and
                 isinstance(wh, str) and _HEX64.fullmatch(wh) is not None,
                 "M136_WINDOW_HASH_INVALID")
        ident = (path, lo, hi)
        _require(ident not in identifiers, "M136_DUPLICATE_WINDOW")
        identifiers.add(ident)
        parsed_windows.append((index, path, lo, hi))
    findings = analysis.get("findings")
    _require(isinstance(findings, list) and len(findings) <= _MAX_FINDINGS,
             "M136_FINDINGS_INVALID")
    selected = []
    seen_ids = set()
    for index, finding in enumerate(findings):
        _require(isinstance(finding, dict), "M136_FINDING_INVALID")
        path, line, fid, rule = (finding.get(k) for k in ("file", "line", "id", "rule_id"))
        _require(_path(path) and type(line) is int and 1 <= line <= 1_000_000 and
                 isinstance(fid, str) and bool(fid) and len(fid) <= 200 and
                 isinstance(rule, str) and bool(rule) and len(rule) <= 200,
                 "M136_FINDING_FIELDS_INVALID")
        _require(fid not in seen_ids, "M136_DUPLICATE_FINDING_ID")
        seen_ids.add(fid)
        hits = [i for i, p, lo, hi in parsed_windows if p == path and lo <= line <= hi]
        in_file = any(p == path for _, p, _, _ in parsed_windows)
        relationship = "LINE_INSIDE_SELECTED_WINDOW" if hits else (
            "SAME_FILE_ONLY_NOT_LOCALIZED" if in_file else "NO_RELATION_TO_CONTEXT")
        selected.append({"finding_index": index, "finding_id": fid, "rule_id": rule,
                         "path": path, "line": line, "relationship": relationship,
                         "window_indices": hits})
    order = {"LINE_INSIDE_SELECTED_WINDOW": 0,
             "SAME_FILE_ONLY_NOT_LOCALIZED": 1, "NO_RELATION_TO_CONTEXT": 2}
    selected.sort(key=lambda x: (order[x["relationship"]], x["finding_index"]))
    counts = {k: sum(r["relationship"] == k for r in selected) for k in order}
    return {"schema": "SKYNETVS_M136_CONTEXT_FINDING_CORRELATION_V1",
            "git_commit": commit, "goal_sha256": sha, "analyzer_schema": expected_analyzer_schema,
            "contexts_considered": len(parsed_windows), "findings_considered": len(selected),
            "counts": counts, "findings": selected,
            "confidence": "STRUCTURAL_LINE_OVERLAP_ONLY_NOT_BUG_PROOF",
            "analysis_goal_binding": ("MATCHED_SHA256" if amatch is not None
                                      else "UNVERIFIED_ANALYZER_GOAL_UNATTESTED"),
            "current_head_rechecked": False,
            "no_patch_or_apply": True, "source_text_included": False,
            "approval_status": "NOT_AUTHORIZED"}


def format_summary(result: dict) -> str:
    _require(isinstance(result, dict) and result.get("schema") ==
             "SKYNETVS_M136_CONTEXT_FINDING_CORRELATION_V1", "M136_SUMMARY_SCHEMA")
    counts = result["counts"]
    lines = ["SkynetVS — связь контекста и AST-находок (только чтение)",
             "Git HEAD: " + result["git_commit"],
             "Попали в выбранные окна: " + str(counts["LINE_INSIDE_SELECTED_WINDOW"]),
             "Только в том же файле: " + str(counts["SAME_FILE_ONLY_NOT_LOCALIZED"]),
             "Не связаны с окнами: " + str(counts["NO_RELATION_TO_CONTEXT"]),
             "Совпадение диапазона НЕ означает доказанное исправление.",
             "Предложение diff не создано. Применение НЕ разрешено."]
    for item in result["findings"][:50]:
        lines.append(f"{item['path']}:{item['line']} — {item['rule_id']} — {item['relationship']}")
    return "\n".join(lines)
