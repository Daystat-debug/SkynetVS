"""M163: bounded, read-only, lexical candidates for an explicit GUI selection.

The existing M126/M127/M130 scorer ranks the committed Git snapshot. This
module does NOT run or load a neural checkpoint. A user must still select a
specific definition and run the existing independent AST investigation before
any relevance label can be recorded. No source text is returned or persisted.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

SCHEMA = "SKYNETVS_M163_TASK_SYMBOL_SHORTLIST_V1"
MAX_CANDIDATES = 8
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_ALLOWED_KINDS = frozenset(("FunctionDef", "AsyncFunctionDef"))


class ShortlistRefused(ValueError):
    pass


def _check(ok: bool, code: str) -> None:
    if not ok:
        raise ShortlistRefused(code)


def from_ranking(goal: str, commit: str, ranking: dict, scan: dict) -> dict:
    """Pure, bounded shaping of M130 BEFORE-only results; no inference claims."""
    _check(type(goal) is str and goal == goal.strip() and 0 < len(goal) <= 1200 and
           len(goal.encode("utf-8", "strict")) <= 2500, "M163_SHORTLIST_GOAL_INVALID")
    _check(type(commit) is str and _SHA40.fullmatch(commit) is not None,
           "M163_SHORTLIST_COMMIT_INVALID")
    _check(type(ranking) is dict and
           ranking.get("schema") == "SKYNETVS_M130_BEFORE_ONLY_CANDIDATE_POOL_V1" and
           ranking.get("no_after_gold_test_patch_or_fix_path_consumed") is True and
           ranking.get("trained_model") is False,
           "M163_SHORTLIST_RANK_CONTRACT_INVALID")
    file_info = ranking.get("file_ranks")
    _check(type(file_info) is dict and
           file_info.get("retrieval_confidence") in ("NO_LEXICAL_MATCH", "LEXICAL_MATCH_EXISTS"),
           "M163_SHORTLIST_FILE_RANK_INVALID")
    candidates = ranking.get("function_rank_top100")
    _check(type(candidates) is list and len(candidates) <= 100,
           "M163_SHORTLIST_FUNCTION_POOL_INVALID")
    _check(type(scan) is dict and type(scan.get("partial")) is bool and
           type(scan.get("sources_read")) is int, "M163_SHORTLIST_SCAN_INVALID")
    rows, seen = [], set()
    if file_info["retrieval_confidence"] == "LEXICAL_MATCH_EXISTS":
        for item in candidates:
            _check(type(item) is dict, "M163_SHORTLIST_ROW_INVALID")
            path, name, kind = item.get("path"), item.get("qualname"), item.get("kind")
            start, end, score = item.get("start"), item.get("end"), item.get("bm25_name_body_score")
            _check(type(path) is str and type(name) is str and kind in _ALLOWED_KINDS and
                   type(start) is int and type(end) is int and 1 <= start <= end and
                   type(score) in (float, int) and not isinstance(score, bool) and
                   0 <= score < 1e8,
                   "M163_SHORTLIST_ROW_INVALID")
            # These are Git metadata strings, not sources or user-generated commands.
            _check(len(path) < 300 and re.fullmatch(
                   r"(?:main\.py|modules/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)", path) is not None and
                   re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*", name) is not None,
                   "M163_SHORTLIST_SELECTOR_INVALID")
            if score <= 0:
                continue
            key = (path, name, start)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"path": path, "qualname": name, "kind": kind,
                         "start": start, "end": end, "rank_score": score,
                         "selector": f"{path}::{name}@{start}"})
            if len(rows) == MAX_CANDIDATES:
                break
    return {"schema": SCHEMA, "status": "CANDIDATES" if rows else "NO_MATCH",
            "goal_sha256": hashlib.sha256(goal.encode("utf-8")).hexdigest(),
            "git_commit": commit, "candidates": rows,
            "candidate_pool_size": len(candidates), "source_files_read": scan["sources_read"],
            "partial": scan["partial"], "ranker": "EXISTING_M130_M127_LEXICAL",
            "trained_model_used": False, "model_deployed": False,
            "selection_required": True, "source_code_executed": False,
            "no_patch_or_apply": True, "repo_worktree_not_read": True}


def shortlist_repository(repository: Path, goal: str, notify=None, *, reader=None):
    """Read only the current committed Git snapshot and recheck HEAD."""
    from .context_search import scan_head, expand_query
    from .retrieval.m130_rank import rank
    if reader is None:
        from .git_source import GitSourceReader, find_git
        reader = GitSourceReader(repository, find_git())
    effective, _ = expand_query(goal)
    commit, sources, scan = scan_head(reader, notify)
    if notify:
        notify("Ранжирую определения функций по существующему лексическому поиску…")
    ranking = rank(effective, sources)
    result = from_ranking(goal, commit, ranking, scan)
    _check(reader._sha("rev-parse", "--verify", "HEAD^{commit}") == commit,
           "M163_SHORTLIST_HEAD_CHANGED")
    # M226 never changes M130 candidates or their ordering. Optional CPU model
    # runs in a separate bounded process and is presentation-only evidence.
    try:
        from .task_symbol_shadow import maybe_shadow
        result["shadow"] = maybe_shadow(repository, goal, commit, sources, ranking)
    except Exception:
        result["shadow"] = {"schema": "SKYNETVS_M226_SHADOW_RANKING_V1",
                            "status": "UNAVAILABLE", "selection_authorized": False,
                            "model_deployed": False, "no_patch_or_apply": True}
    _check(reader._sha("rev-parse", "--verify", "HEAD^{commit}") == commit,
           "M163_SHORTLIST_HEAD_CHANGED")
    return result


def validate_choice(report: dict, goal: str, index: int) -> tuple[str, str]:
    """User-initiated selection only; the caller rechecks commit during AST scan."""
    _check(type(report) is dict and report.get("schema") == SCHEMA and
           report.get("status") == "CANDIDATES" and
           report.get("selection_required") is True and
           report.get("no_patch_or_apply") is True and
           report.get("trained_model_used") is False,
           "M163_SHORTLIST_CHOICE_REPORT_INVALID")
    _check(type(goal) is str and hashlib.sha256(goal.encode("utf-8")).hexdigest() ==
           report.get("goal_sha256"), "M163_SHORTLIST_GOAL_CHANGED")
    rows = report.get("candidates")
    _check(type(index) is int and type(rows) is list and 0 <= index < len(rows),
           "M163_SHORTLIST_CHOICE_OUT_OF_RANGE")
    selector = rows[index].get("selector")
    commit = report.get("git_commit")
    _check(type(selector) is str and 0 < len(selector) <= 640 and
           type(commit) is str and _SHA40.fullmatch(commit) is not None,
           "M163_SHORTLIST_SELECTOR_INVALID")
    return selector, commit
