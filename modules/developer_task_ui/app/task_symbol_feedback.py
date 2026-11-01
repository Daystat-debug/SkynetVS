"""M163: manually asserted task -> committed Python symbol relevance.

This is a prospective *candidate* label, NOT a verified bugfix, test result,
training permission, model inference, patch proposal or code-apply authority.
Sources are read as Git blobs only and are never executed or stored in labels.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from pathlib import Path

from .symbol_investigation import SCHEMA as SYMBOL_SCHEMA
from .symbol_task_bridge import report_fingerprint

SCHEMA = "SKYNETVS_M163_USER_ASSERTED_TASK_SYMBOL_V1"
ASSESSMENTS = frozenset({"RELEVANT", "NOT_RELEVANT"})
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_QUALNAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*\Z")
_FILE_BYTES_MAX = 256 * 1024


class FeedbackRefused(ValueError):
    pass


def _require(value, code):
    if not value:
        raise FeedbackRefused(code)


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _path_in_scope(path):
    from .context_search import _include  # Existing read-only Git search allowlist.
    return type(path) is str and len(path) <= 300 and _include(path)


def _matches_ast_definition(source: str, item: dict) -> bool:
    """Match a single definition by full lexical name, line span, and AST kind."""
    tree = ast.parse(source, filename="<m163_pinned_git_source>")
    found = []

    def walk(node, chain=()):
        for child in ast.iter_child_nodes(node):
            next_chain = chain
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                next_chain = (*chain, child.name)
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if (".".join(next_chain) == item["qualname"] and
                        child.lineno == item["start"] and
                        child.end_lineno == item["end"] and
                        type(child).__name__ == item["kind"]):
                    found.append(child)
            walk(child, next_chain)
    walk(tree)
    return len(found) == 1


def prepare_feedback(*, repository: Path, goal: str, report: dict,
                     report_sha256: str, assessment: str, reader=None) -> dict:
    """Revalidate CURRENT Git HEAD + selected definition before returning local data.

    Does not create any files, modify the Git repository, train or execute source.
    The caller must ask the user and persist the result in a private folder.
    """
    _require(type(assessment) is str and assessment in ASSESSMENTS,
             "M163_FEEDBACK_ASSESSMENT_REQUIRED")
    _require(type(goal) is str and goal == goal.strip() and 0 < len(goal) <= 1200,
             "M163_FEEDBACK_GOAL_INVALID")
    try:
        task_bytes = goal.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise FeedbackRefused("M163_FEEDBACK_GOAL_INVALID_UTF8") from exc
    _require(len(task_bytes) <= 2500 and b"\x00" not in task_bytes,
             "M163_FEEDBACK_GOAL_BYTES_INVALID")
    _require(type(report) is dict and report.get("schema") == SYMBOL_SCHEMA and
             report.get("status") == "COMPLETE", "M163_FEEDBACK_SYMBOL_NOT_SELECTED")
    _require(type(report_sha256) is str and _SHA64.fullmatch(report_sha256) and
             report_fingerprint(report) == report_sha256,
             "M163_FEEDBACK_REPORT_CHANGED")
    _require(report.get("goal_sha256") == _hash(task_bytes),
             "M163_FEEDBACK_GOAL_CHANGED")
    commit = report.get("git_commit")
    _require(type(commit) is str and _SHA40.fullmatch(commit),
             "M163_FEEDBACK_COMMIT_INVALID")
    _require(report.get("git_head_observed") is True and
             report.get("source_binding") == "OBSERVED_GIT_HEAD_BLOBS" and
             report.get("structural_only") is True and
             report.get("no_patch_or_apply") is True and
             report.get("repo_worktree_not_read") is True and
             report.get("source_code_executed") is False and
             report.get("source_text_included") is False and
             report.get("runtime_calls_proven") is False,
             "M163_FEEDBACK_EVIDENCE_NOT_READONLY")
    selected = report.get("selected")
    _require(type(selected) is dict, "M163_FEEDBACK_SYMBOL_INVALID")
    _require(_path_in_scope(selected.get("path")) and
             type(selected.get("qualname")) is str and
             len(selected["qualname"]) <= 400 and
             _QUALNAME.fullmatch(selected["qualname"]) is not None and
             selected.get("kind") in ("FunctionDef", "AsyncFunctionDef") and
             type(selected.get("start")) is int and 0 < selected["start"] <= 9999999 and
             type(selected.get("end")) is int and
             selected["start"] <= selected["end"] <= 9999999 and
             type(selected.get("source_sha256")) is str and
             _SHA64.fullmatch(selected["source_sha256"]) is not None and
             type(selected.get("blob_oid")) is str and
             _SHA40.fullmatch(selected["blob_oid"]) is not None and
             type(selected.get("id")) is str and
             _SHA64.fullmatch(selected["id"]) is not None,
             "M163_FEEDBACK_SELECTED_FIELDS_INVALID")
    expected_id = _hash(json.dumps([commit, selected["path"],
                                    selected["qualname"], selected["start"]],
                                   separators=(",", ":")).encode("utf-8"))
    _require(expected_id == selected["id"], "M163_FEEDBACK_SYMBOL_ID_INVALID")

    repository = Path(os.path.abspath(repository))
    if reader is None:
        from .git_source import GitSourceReader, find_git
        reader = GitSourceReader(repository, find_git())
    _require(reader._sha("rev-parse", "--verify", "HEAD^{commit}") == commit,
             "M163_FEEDBACK_STALE_GIT_HEAD")
    top = reader._run("rev-parse", "--show-toplevel").decode("utf-8", "strict").strip()
    _require(os.path.normcase(os.path.abspath(top)).casefold() == str(repository).casefold(),
             "M163_FEEDBACK_PROJECT_ROOT_MISMATCH")
    path = selected["path"]
    row = reader._run("ls-tree", "-z", "--full-tree", commit, "--", path)
    expected_row = re.fullmatch(
        rb"(100644|100755) blob ([0-9a-f]{40})\t" + re.escape(path.encode("ascii")) + rb"\x00", row)
    _require(expected_row is not None and expected_row.group(2).decode("ascii") == selected["blob_oid"],
             "M163_FEEDBACK_GIT_BLOB_CHANGED")
    size_raw = reader._run("cat-file", "-s", selected["blob_oid"]).strip()
    _require(re.fullmatch(rb"[0-9]{1,8}", size_raw) is not None and
             int(size_raw) <= _FILE_BYTES_MAX, "M163_FEEDBACK_SOURCE_SIZE_INVALID")
    body = reader._run("cat-file", "blob", selected["blob_oid"], limit=_FILE_BYTES_MAX + 1)
    _require(len(body) == int(size_raw) and _hash(body) == selected["source_sha256"],
             "M163_FEEDBACK_SOURCE_SHA_INVALID")
    _require(hashlib.sha1((f"blob {len(body)}\0").encode("ascii") + body).hexdigest()
             == selected["blob_oid"], "M163_FEEDBACK_SOURCE_OID_INVALID")
    try:
        _require(_matches_ast_definition(body.decode("utf-8", "strict"), selected),
                 "M163_FEEDBACK_SYMBOL_AST_CHANGED")
    except (UnicodeError, SyntaxError, RecursionError, MemoryError) as exc:
        raise FeedbackRefused("M163_FEEDBACK_SYMBOL_AST_INVALID") from exc
    _require(reader._sha("rev-parse", "--verify", "HEAD^{commit}") == commit,
             "M163_FEEDBACK_HEAD_CHANGED_DURING_READ")
    coverage = report.get("coverage")
    _require(isinstance(coverage, dict) and type(coverage.get("partial")) is bool,
             "M163_FEEDBACK_COVERAGE_INVALID")
    return {
        "schema": SCHEMA,
        "assessment": assessment,
        "origin": "EXPLICIT_USER_SELECTION_IN_EXISTING_GUI",
        "task_text": goal,   # PRIVATE. Never include in public receipts.
        "task_sha256": _hash(task_bytes),
        "symbol_investigation_report_sha256": report_sha256,
        "git_commit": commit,
        "symbol": {key: selected[key] for key in
                   ("id", "path", "qualname", "kind", "start", "end", "source_sha256", "blob_oid")},
        "investigation_partial": coverage["partial"],
        "label_semantics": "USER_ASSERTED_RELEVANCE_NOT_VERIFIED_BUGFIX",
        "independently_verified_correctness": False,
        "training_approved": False,
        "model_deployed": False,
        "code_executed": False,
        "patch_created": False,
        "action_authorized": False,
        "working_tree_read": False,
    }
