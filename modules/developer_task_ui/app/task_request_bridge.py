"""M145: bounded, read-only task -> existing DTR-A request candidate selection.

Pure metadata filtering. No source read, patch generation, authorization or network.
The existing DTR-A target policy and GitSourceReader are the only source gates.
"""
from __future__ import annotations

import hashlib
import math
import re

SCHEMA = "SKYNETVS_M134_READONLY_PROJECT_CONTEXT_V1"
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
PATH = re.compile(r"modules/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py\Z")


class BridgeRefusal(ValueError):
    pass


def _check(condition: bool, code: str) -> None:
    if not condition:
        raise BridgeRefusal(code)


def bounded_title(goal: str) -> str:
    _check(isinstance(goal, str) and bool(goal.strip()), "M145_EMPTY_GOAL")
    title = " ".join(goal.strip().split())
    return title[:120].rstrip()


def eligible_targets(goal: str, report: dict, validate_target) -> list[str]:
    """Find eligible paths from the actual M134 Top5 and selected source windows.

    They remain *candidates*, not bug locations. Fail closed on stale/malformed
    provenance; never silently use a different task or Git revision.
    """
    _check(isinstance(goal, str) and goal.strip() and len(goal) <= 1200 and
           len(goal.encode("utf-8")) <= 2500, "M145_GOAL_INVALID")
    _check(isinstance(report, dict) and report.get("schema") == SCHEMA,
           "M145_SEARCH_SCHEMA")
    _check(report.get("goal_sha256") == hashlib.sha256(goal.encode("utf-8")).hexdigest() and
           isinstance(report.get("goal_sha256"), str) and SHA64.fullmatch(report["goal_sha256"]) is not None,
           "M145_STALE_GOAL")
    _check(isinstance(report.get("git_commit"), str) and
           SHA40.fullmatch(report["git_commit"]) is not None, "M145_COMMIT_FORMAT")
    _check(report.get("no_patch_or_apply") is True and
           report.get("repo_worktree_not_read") is True, "M145_UNSAFE_CONTEXT")
    ranked = report.get("file_rank_top5")
    meta = report.get("contexts_metadata")
    _check(isinstance(ranked, list) and len(ranked) <= 5 and
           isinstance(meta, dict) and isinstance(meta.get("8192"), dict),
           "M145_RANK_SCHEMA")
    windows = meta["8192"].get("ranges")
    _check(isinstance(windows, list) and len(windows) <= 24, "M145_WINDOWS_INVALID")
    ordered = []
    for row in ranked:
        _check(isinstance(row, dict) and isinstance(row.get("path"), str) and
               type(row.get("score")) in (float, int) and
               math.isfinite(row["score"]), "M145_FILE_SCORE_INVALID")
        ordered.append(row["path"])
    for window in windows:
        _check(isinstance(window, dict) and isinstance(window.get("path"), str) and
               isinstance(window.get("source_sha256"), str) and
               SHA64.fullmatch(window["source_sha256"]) is not None,
               "M145_SOURCE_WINDOW_INVALID")
        ordered.append(window["path"])
    choices = []
    for path in ordered:
        _check(len(path) <= 300 and ".." not in path.split("/") and
               not path.startswith("/"), "M145_UNSAFE_RANKED_PATH")
        if not PATH.fullmatch(path) or path in choices:
            continue
        try:
            validate_target(path)  # original DTR-A one-file allowlist
        except ValueError:
            continue
        choices.append(path)
        if len(choices) >= 12:
            break
    return choices


def verify_capture(selected_path: str, report: dict, captured) -> None:
    """Capture was made by GitSourceReader; bind it to the same search commit."""
    _check(getattr(captured, "path", None) == selected_path and
           getattr(captured, "base_commit", None) == report.get("git_commit") and
           isinstance(getattr(captured, "provenance", None), dict) and
           captured.provenance.get("kind") == "OBSERVED_COMMITTED_FILE" and
           captured.provenance.get("current_git_head_observed") is True and
           getattr(captured, "content", None) is not None and
           type(captured.content) is bytes and len(captured.content) <= 65536,
           "M145_SOURCE_OR_HEAD_DRIFT")
