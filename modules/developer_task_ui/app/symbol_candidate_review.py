"""Relate an accepted one-file DTR proposal to its captured Core symbol.

Only captured bytes are parsed. This module performs no filesystem, Git, network,
source execution, compilation, patch application or runtime caller analysis.
The context digest detects mutation of current-session UI state; it does not
authenticate an externally supplied sidecar or re-observe the current Git HEAD.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import warnings

from .core import (DeveloperTaskProposalRequest, SourceSnapshot, blob_oid,
                   make_request, request_document, review_response, strict_json)
from .patch_preview import PatchPreviewError, _reconstruct
from .symbol_task_bridge import (MAX_REPORT_BYTES, task_instruction,
                                 verify_symbol_capture)
from .task_request_bridge import bounded_title

CONTEXT_SCHEMA = "SKYNETVS_CORE_SYMBOL_TASK_CONTEXT_V1"
SCHEMA = "SKYNETVS_CORE_CANDIDATE_REVIEW_V1"
MAX_CONTEXT_BYTES = MAX_REPORT_BYTES + 65536
MAX_SOURCE_BYTES = 65536
MAX_AST_NODES = 60000
MAX_AST_DEPTH = 80
MAX_DEFINITIONS = 2048
MAX_RESULT_ROWS = 64
MAX_REVIEW_BYTES = MAX_REPORT_BYTES + 65536
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_PATH = re.compile(r"(?:main\.py|modules/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)\Z")
_CODE = re.compile(r"[A-Z][A-Za-z0-9_]{0,119}\Z")
_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_LOCATIONS = frozenset(("lineno", "col_offset", "end_lineno", "end_col_offset"))


class CandidateReviewError(ValueError):
    """Bounded, source-free refusal code suitable for a separate UI message."""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _check(condition, code):
    if not condition:
        raise CandidateReviewError(code)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError, MemoryError) as exc:
        raise CandidateReviewError("CORE_CANDIDATE_JSON_INVALID") from exc


def _keys(value, required, optional=()):
    _check(type(value) is dict and set(required) <= set(value) <= set(required) | set(optional),
           "CORE_CANDIDATE_EVIDENCE_SHAPE")


def _integer(value):
    _check(type(value) is int and 0 <= value <= 2**53, "CORE_CANDIDATE_EVIDENCE_NUMBER")


def _code(value):
    _check(type(value) is str and _CODE.fullmatch(value), "CORE_CANDIDATE_EVIDENCE_CODE")


def _path(value):
    _check(type(value) is str and len(value) <= 300 and _PATH.fullmatch(value),
           "CORE_CANDIDATE_EVIDENCE_PATH")


def _reference(row):
    _keys(row, ("id", "path", "qualname", "kind", "start", "end", "source_sha256", "blob_oid"))
    _path(row["path"])
    name = row["qualname"]
    _check(type(name) is str and 0 < len(name) <= 400 and
           (name == "<module>" or all(part.isidentifier() for part in name.split("."))),
           "CORE_CANDIDATE_EVIDENCE_NAME")
    _check(row["kind"] in ("Module", "ClassDef", "FunctionDef", "AsyncFunctionDef"),
           "CORE_CANDIDATE_EVIDENCE_KIND")
    for key in ("id", "source_sha256", "blob_oid"):
        pattern = _SHA40 if key == "blob_oid" else _SHA64
        _check(type(row[key]) is str and pattern.fullmatch(row[key]), "CORE_CANDIDATE_EVIDENCE_HASH")
    _integer(row["start"]); _integer(row["end"])
    _check(0 < row["start"] <= row["end"], "CORE_CANDIDATE_EVIDENCE_RANGE")


def _evidence_report(report):
    """Accept only metadata emitted by the existing symbol report producer.

    A full retained report is useful, but arbitrary extra fields must not smuggle
    source text into a document described as source-free. This is shape checking,
    not proof of the historical scan or resolution of its unknown references.
    """
    _keys(report, ("schema", "status", "git_commit", "goal_sha256", "selector", "selected",
                   "candidates", "outgoing", "incoming", "unknown_outgoing", "coverage",
                   "source_binding", "git_head_observed", "structural_only", "no_patch_or_apply",
                   "repo_worktree_not_read", "source_code_executed", "source_text_included",
                   "runtime_calls_proven"))
    _check(type(report["selector"]) is str and len(report["selector"]) <= 640 and
           re.fullmatch(r"(?:(?:main\.py|modules/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)::)?"
                        r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:@[1-9][0-9]{0,6})?",
                        report["selector"]), "CORE_CANDIDATE_EVIDENCE_SELECTOR")
    _reference(report["selected"])
    _check(type(report["candidates"]) is list and report["candidates"] == [report["selected"]],
           "CORE_CANDIDATE_EVIDENCE_SELECTION")
    for field in ("incoming", "outgoing", "unknown_outgoing"):
        rows = report[field]
        _check(type(rows) is list and len(rows) <= 256, "CORE_CANDIDATE_EVIDENCE_ROWS")
        for row in rows:
            extra = ("reason",) if field == "unknown_outgoing" else ("callee", "resolution", "runtime_execution")
            _keys(row, ("caller", "call_site", "callee_name", *extra))
            _reference(row["caller"])
            site = row["call_site"]
            _keys(site, ("path", "line", "column", "end_line", "source_sha256", "blob_oid"))
            _path(site["path"])
            for key in ("line", "column", "end_line"):
                _integer(site[key])
            _check(site["line"] > 0 and site["end_line"] >= site["line"], "CORE_CANDIDATE_EVIDENCE_RANGE")
            for key, pattern in (("source_sha256", _SHA64), ("blob_oid", _SHA40)):
                _check(type(site[key]) is str and pattern.fullmatch(site[key]), "CORE_CANDIDATE_EVIDENCE_HASH")
            name = row["callee_name"]
            _check(type(name) is str and 0 < len(name) <= 300 and
                   (re.fullmatch(r"<[A-Za-z]+>", name) or
                    all(part.isidentifier() for part in name.rstrip(".").split("."))),
                   "CORE_CANDIDATE_EVIDENCE_NAME")
            if field == "unknown_outgoing":
                _code(row["reason"])
            else:
                _reference(row["callee"])
                _check(row["resolution"] in ("SAME_MODULE_NAME", "EXPLICIT_IMPORT") and
                       row["runtime_execution"] == "NOT_PROVEN", "CORE_CANDIDATE_EVIDENCE_RESOLUTION")
            selected_key = "callee" if field == "incoming" else "caller"
            _check(row[selected_key] == report["selected"], "CORE_CANDIDATE_EVIDENCE_RELATION")
    coverage = report["coverage"]
    _keys(coverage, ("scan", "source_files_supplied", "source_bytes_supplied", "parsed_files",
                     "functions_indexed", "ast_nodes", "parse_diagnostics", "partial", "counts",
                     "unknown_reason_counts", "candidate_matches", "truncated", "limits",
                     "resolution_model", "limitations"))
    for key in ("source_files_supplied", "source_bytes_supplied", "parsed_files", "functions_indexed",
                "ast_nodes", "candidate_matches"):
        _integer(coverage[key])
    _check(type(coverage["partial"]) is bool and coverage["candidate_matches"] == 1,
           "CORE_CANDIDATE_EVIDENCE_COVERAGE")
    scan = coverage["scan"]
    _keys(scan, (), ("tracked_python_paths", "sources_read", "source_bytes", "scope", "partial", "skipped"))
    for key in ("tracked_python_paths", "sources_read", "source_bytes"):
        if key in scan:
            _integer(scan[key])
    if "scope" in scan:
        _check(scan["scope"] == "GIT_HEAD_MAIN_PY_AND_MODULES_PY_ONLY", "CORE_CANDIDATE_EVIDENCE_SCOPE")
    if "partial" in scan:
        _check(type(scan["partial"]) is bool, "CORE_CANDIDATE_EVIDENCE_COVERAGE")
    if "skipped" in scan:
        _keys(scan["skipped"], (), ("too_large", "total_budget", "not_utf8", "binary"))
        for number in scan["skipped"].values():
            _integer(number)
    count_keys = ("call_sites", "resolved_references", "unresolved_calls", "outgoing", "incoming",
                  "selected_unknowns", "call_sites_omitted")
    truncate_keys = ("candidates", "outgoing", "incoming", "unknowns", "call_sites")
    limit_keys = ("files", "source_bytes", "file_bytes", "ast_nodes", "ast_nodes_per_file", "functions",
                  "call_sites", "result_rows", "candidates")
    for key, names in (("counts", count_keys), ("truncated", truncate_keys), ("limits", limit_keys)):
        _keys(coverage[key], names)
        for number in coverage[key].values():
            _integer(number)
    _check(type(coverage["unknown_reason_counts"]) is dict and len(coverage["unknown_reason_counts"]) <= 128,
           "CORE_CANDIDATE_EVIDENCE_REASONS")
    for reason, number in coverage["unknown_reason_counts"].items():
        _code(reason); _integer(number)
    for field, count_key, clipped_key in (("incoming", "incoming", "incoming"),
                                          ("outgoing", "outgoing", "outgoing"),
                                          ("unknown_outgoing", "selected_unknowns", "unknowns")):
        _check(coverage["counts"][count_key] == len(report[field]) + coverage["truncated"][clipped_key],
               "CORE_CANDIDATE_EVIDENCE_COUNTS")
    diagnostics = coverage["parse_diagnostics"]
    _check(type(diagnostics) is list and len(diagnostics) <= MAX_AST_NODES, "CORE_CANDIDATE_EVIDENCE_ROWS")
    for row in diagnostics:
        _keys(row, ("path", "reason", "partial"), ("line",))
        _path(row["path"]); _code(row["reason"])
        _check(type(row["partial"]) is bool, "CORE_CANDIDATE_EVIDENCE_COVERAGE")
        if row.get("line") is not None:
            _integer(row["line"])
    _check(coverage["resolution_model"] == "STABLE_MODULE_FUNCTIONS_AND_EXPLICIT_IMPORTS_ONLY" and
           type(coverage["limitations"]) is list and len(coverage["limitations"]) <= 32,
           "CORE_CANDIDATE_EVIDENCE_SCOPE")
    for item in coverage["limitations"]:
        _code(item)


def _parse(content):
    _check(type(content) is bytes and 0 < len(content) <= MAX_SOURCE_BYTES,
           "CORE_CANDIDATE_SOURCE_BUDGET")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", SyntaxWarning)
            tree = ast.parse(content.decode("utf-8", "strict"), filename="<Core_candidate_bytes>",
                             mode="exec", type_comments=True)
        count = depth = 0
        pending = [(tree, 0)]
        while pending:
            node, level = pending.pop()
            count += 1
            depth = max(depth, level)
            _check(count <= MAX_AST_NODES and depth <= MAX_AST_DEPTH, "CORE_CANDIDATE_AST_BUDGET")
            pending.extend((child, level + 1) for child in ast.iter_child_nodes(node))
        definitions = []

        def walk(node, parents):
            if isinstance(node, _DEFS):
                name = ".".join((*parents, node.name))
                _check(len(name) <= 400, "CORE_CANDIDATE_DEFINITION_NAME_BUDGET")
                definitions.append({"node": node, "qualname": name, "kind": type(node).__name__,
                                    "start": node.lineno, "end": node.end_lineno,
                                    "text_start": min([node.lineno] + [d.lineno for d in node.decorator_list])})
                _check(len(definitions) <= MAX_DEFINITIONS, "CORE_CANDIDATE_DEFINITION_BUDGET")
                for child in node.body:
                    walk(child, (*parents, node.name))
            else:
                for child in ast.iter_child_nodes(node):
                    walk(child, parents)
        walk(tree, ())
        return tree, definitions, {"nodes": count, "depth": depth, "definitions": len(definitions),
                                   "syntax_warnings": len(caught)}
    except CandidateReviewError:
        raise
    except (SyntaxError, UnicodeError, ValueError, RecursionError, MemoryError) as exc:
        raise CandidateReviewError("CORE_CANDIDATE_AST_REFUSED") from exc


def _normal(value, *, replace=None, module_skeleton=False):
    """Position-free structure used only for hashing; never included in reports."""
    if isinstance(value, ast.AST):
        if value is replace:
            return ["SELECTED_DEFINITION_PLACEHOLDER"]
        if module_skeleton and isinstance(value, _DEFS):
            return ["DEFINITION_BINDING", type(value).__name__, value.name]
        return [type(value).__name__, [[name, _normal(item, replace=replace, module_skeleton=module_skeleton)]
                                      for name, item in ast.iter_fields(value) if name not in _LOCATIONS]]
    if isinstance(value, list):
        return [_normal(item, replace=replace, module_skeleton=module_skeleton) for item in value]
    # AST Constant values may be bytes, complex, Ellipsis or non-finite floats;
    # tagged repr is hashed in memory, never emitted. Preserve their exact type.
    return [type(value).__name__, repr(value)]


def _ast_hash(value, **kwargs):
    return _sha(_canonical(_normal(value, **kwargs)))


def _definition_metadata(item):
    return {key: item[key] for key in ("qualname", "kind", "start", "end", "text_start")}


def _selected_original(report, source, definitions):
    selected = report["selected"]
    matches = [item for item in definitions if all(item[key] == selected[key]
               for key in ("qualname", "kind", "start", "end")) and isinstance(item["node"], _FUNCTIONS)]
    identity = _sha(json.dumps([source.base_commit, source.path, selected["qualname"], selected["start"]],
                               separators=(",", ":")).encode("utf-8"))
    _check(len(matches) == 1 and selected["id"] == identity and
           selected["source_sha256"] == _sha(source.content) and selected["blob_oid"] == blob_oid(source.content),
           "CORE_CANDIDATE_SELECTED_DEFINITION_MISMATCH")
    return matches[0]


def bind_request_context(*, goal, report, expected_report_sha256, request, source) -> bytes:
    """Freeze source-free Core evidence alongside the exact existing DTR request.

    Call only with the current session's observed investigation/capture. Loading
    this JSON later does not establish that session provenance or current HEAD.
    """
    try:
        _check(type(goal) is str and 0 < len(goal) <= 1200 and len(goal.encode("utf-8")) <= 2500,
               "CORE_CANDIDATE_GOAL_INVALID")
        _check(isinstance(request, DeveloperTaskProposalRequest) and isinstance(source, SourceSnapshot),
               "CORE_CANDIDATE_REQUEST_TYPE")
        verify_symbol_capture(goal, report, expected_report_sha256, source)
        _evidence_report(report)
        _, definitions, _ = _parse(source.content)
        _selected_original(report, source, definitions)
        binding = request_document(request, source)["binding"]
        rebuilt = make_request(source, bounded_title(goal), task_instruction(goal, report, expected_report_sha256),
                               request_id=request.request_id, task_id=request.task_id)
        _check(binding == rebuilt.binding_dict(), "CORE_CANDIDATE_REQUEST_BINDING_MISMATCH")
        context = {"schema": CONTEXT_SCHEMA, "goal": goal, "report_sha256": expected_report_sha256,
                   "report": report, "request_binding": binding,
                   "source": {"path": source.path, "base_commit": source.base_commit,
                              "base_tree": source.base_tree, "source_sha256": _sha(source.content),
                              "blob_oid": blob_oid(source.content), "content_bytes": len(source.content)},
                   "source_text_included": False, "current_session_only": True,
                   "external_sidecar_authenticated": False}
        encoded = _canonical(context)
        _check(len(encoded) <= MAX_CONTEXT_BYTES, "CORE_CANDIDATE_CONTEXT_BUDGET")
        return encoded
    except CandidateReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError, MemoryError) as exc:
        raise CandidateReviewError("CORE_CANDIDATE_CONTEXT_BINDING_REFUSED") from exc


def _restore_context(context_bytes, expected_context_sha256, request, source):
    _check(type(context_bytes) is bytes and 0 < len(context_bytes) <= MAX_CONTEXT_BYTES,
           "CORE_CANDIDATE_CONTEXT_BUDGET")
    _check(type(expected_context_sha256) is str and _SHA64.fullmatch(expected_context_sha256) and
           _sha(context_bytes) == expected_context_sha256, "CORE_CANDIDATE_CONTEXT_CHANGED")
    try:
        context = strict_json(context_bytes, maximum=MAX_CONTEXT_BYTES)
        _keys(context, ("schema", "goal", "report_sha256", "report", "request_binding", "source",
                        "source_text_included", "current_session_only", "external_sidecar_authenticated"))
        _check(context["schema"] == CONTEXT_SCHEMA and _canonical(context) == context_bytes,
               "CORE_CANDIDATE_CONTEXT_ENCODING")
        rebuilt = bind_request_context(goal=context["goal"], report=context["report"],
                                       expected_report_sha256=context["report_sha256"], request=request, source=source)
        _check(rebuilt == context_bytes, "CORE_CANDIDATE_CONTEXT_BINDING_MISMATCH")
        return context
    except CandidateReviewError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, MemoryError) as exc:
        raise CandidateReviewError("CORE_CANDIDATE_CONTEXT_INVALID") from exc


def _components(item):
    node = item["node"]
    if isinstance(node, _FUNCTIONS):
        signature = [node.args, node.returns, node.type_comment, getattr(node, "type_params", [])]
    else:
        signature = [node.bases, node.keywords, getattr(node, "type_params", [])]
    return {"body": _ast_hash(node.body), "signature": _ast_hash(signature),
            "decorators": _ast_hash(node.decorator_list), "name": _ast_hash(node.name),
            "kind": _ast_hash(type(node).__name__)}


def _pair(before, after):
    old = _components(before); new = _components(after)
    return {"before": _definition_metadata(before), "after": _definition_metadata(after),
            "ast_changed": _ast_hash(before["node"]) != _ast_hash(after["node"]),
            "components_changed": {key: old[key] != new[key] for key in old},
            "component_sha256_before": old, "component_sha256_after": new}


def _groups(definitions):
    groups = {}
    for item in definitions:
        groups.setdefault(item["qualname"], []).append(item)
    return groups


def _relation(name, selected):
    if name == selected:
        return "SELECTED"
    if selected.startswith(name + "."):
        return "ANCESTOR"
    if name.startswith(selected + "."):
        return "DESCENDANT"
    return "OTHER"


def _compatible(before, after):
    return (before["kind"] == after["kind"] or
            (isinstance(before["node"], _FUNCTIONS) and isinstance(after["node"], _FUNCTIONS)))


def _definition_changes(before, after, selected_name):
    old = _groups(before); new = _groups(after)
    changes = []
    for name in sorted(set(old) | set(new)):
        previous = old.get(name, []); current = new.get(name, [])
        row = {"qualname": name, "relation_to_selected": _relation(name, selected_name)}
        if len(previous) > 1 or len(current) > 1:
            row.update(status="AMBIGUOUS_DEFINITIONS", before_count=len(previous), after_count=len(current))
        elif not previous:
            row.update(status="ADDED", before=None, after=_definition_metadata(current[0]))
        elif not current:
            row.update(status="REMOVED_OR_RENAMED", before=_definition_metadata(previous[0]), after=None)
        elif not _compatible(previous[0], current[0]):
            row.update(status="UNSUPPORTED_KIND_CHANGE", before=_definition_metadata(previous[0]),
                       after=_definition_metadata(current[0]))
        else:
            pair = _pair(previous[0], current[0])
            if not pair["ast_changed"]:
                continue
            row.update(status="CHANGED", **pair)
        row["ancestor_body_includes_selected"] = row["relation_to_selected"] == "ANCESTOR"
        changes.append(row)
    return changes


def _outside_text(content, selected):
    lines = content.splitlines(keepends=True)
    return b"".join(lines[:selected["text_start"] - 1]) + b"<SELECTED_DEFINITION>\n" + b"".join(lines[selected["end"]:])


def _preview_candidate(request, source, response_bytes, preview):
    _check(type(response_bytes) is bytes, "CORE_CANDIDATE_RESPONSE_TYPE")
    try:
        intake = review_response(request, response_bytes)
        _check(intake["intake"].get("ok") is True and
               intake["checks"]["dtra_format_and_binding"] == "PASS", "CORE_CANDIDATE_DTRA_REJECTED")
        updated, hunks, added, removed = _reconstruct(source.content, intake["patch_text"], source.path)
        expected = {"schema": "SKYNETVS_DTR_PATCH_PREVIEW_V1", "target_path": source.path,
                    "request_fingerprint": request.request_fingerprint, "response_sha256": _sha(response_bytes),
                    "original_sha256": _sha(source.content), "proposed_sha256": _sha(updated),
                    "preview_status": "TEXT_APPLICABLE_AST_PASS_NOT_EXECUTABLE_CHECKS",
                    "text_applicability": "EXACT_BYTE_IN_MEMORY_PASS", "python_ast_parse": "PASS",
                    "issue_code": None, "hunks": hunks, "added_lines": added, "removed_lines": removed,
                    "project_file_written": False, "changed_code_executed": False,
                    "git_diff_check": "NOT_RUN", "py_compile": "NOT_RUN", "pipeline_check": "NOT_RUN",
                    "behavior": "NOT_TESTED", "runtime_authorized": False, "promotion_authorized": False,
                    "installation_authorized": False, "dtrb_rehearsal_completed": False, "os_sandbox_claimed": False}
        _check(type(preview) is dict and all(key in preview and type(preview[key]) is type(value) and
               preview[key] == value for key, value in expected.items()), "CORE_CANDIDATE_PREVIEW_BINDING_MISMATCH")
        return updated
    except CandidateReviewError:
        raise
    except PatchPreviewError as exc:
        raise CandidateReviewError("CORE_CANDIDATE_PATCH_REFUSED") from exc
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError, MemoryError) as exc:
        raise CandidateReviewError("CORE_CANDIDATE_DTRA_REFUSED") from exc


def review_candidate(*, context_bytes, expected_context_sha256, request, source,
                     response_bytes, preview) -> dict:
    """Compare an accepted proposal to a selected definition, without executing it.

    COMPLETE means the bounded structural review was constructed. Unknown mapping
    and truncated historical evidence remain explicit; behavior is never proved.
    """
    context = _restore_context(context_bytes, expected_context_sha256, request, source)
    updated = _preview_candidate(request, source, response_bytes, preview)
    original_tree, original_defs, original_stats = _parse(source.content)
    proposed_tree, proposed_defs, proposed_stats = _parse(updated)
    evidence = context["report"]
    original = _selected_original(evidence, source, original_defs)
    name = original["qualname"]
    old_matches = _groups(original_defs).get(name, [])
    matches = _groups(proposed_defs).get(name, [])
    mapping = "UNIQUE_QUALNAME"
    candidate = None
    if len(old_matches) != 1 or len(matches) > 1:
        mapping = "AMBIGUOUS_DEFINITIONS"
    elif not matches:
        mapping = "REMOVED_OR_RENAMED"
    elif not _compatible(original, matches[0]):
        mapping = "UNSUPPORTED_KIND_CHANGE"
    else:
        candidate = matches[0]
    selected = {"original_reference": evidence["selected"], "mapping": mapping,
                "before": _definition_metadata(original), "after": None,
                "ast_changed": None, "components_changed": None,
                "name_change_inferred": False, "mapping_proves_runtime_identity": False}
    outside_ast = outside_text = None
    if candidate is not None:
        selected.update(_pair(original, candidate))
        outside_ast = (_ast_hash(original_tree, replace=original["node"]) !=
                       _ast_hash(proposed_tree, replace=candidate["node"]))
        outside_text = _outside_text(source.content, original) != _outside_text(updated, candidate)
    changes = _definition_changes(original_defs, proposed_defs, name)
    original_ast_sha = _ast_hash(original_tree)
    proposed_ast_sha = _ast_hash(proposed_tree)
    historical_coverage = {**evidence["coverage"],
                           "parse_diagnostics": evidence["coverage"]["parse_diagnostics"][:MAX_RESULT_ROWS]}
    historical = {"git_commit": evidence["git_commit"], "report_sha256": context["report_sha256"],
                  "status": "HISTORICAL_STATIC_REFERENCES_TO_ORIGINAL_COMMIT",
                  "runtime_calls_proven": False, "callers_reanalyzed_against_candidate": False,
                  "all_callers_known": False, "coverage": historical_coverage,
                  "full_original_report_retained_in_context": True,
                  "rows_omitted_by_review": {"parse_diagnostics": max(0, len(evidence["coverage"]["parse_diagnostics"]) - MAX_RESULT_ROWS)}}
    for field in ("incoming", "outgoing", "unknown_outgoing"):
        historical[field] = evidence[field][:MAX_RESULT_ROWS]
        historical["rows_omitted_by_review"][field] = max(0, len(evidence[field]) - MAX_RESULT_ROWS)
    omissions = max(0, len(changes) - MAX_RESULT_ROWS)
    partial = bool(evidence["coverage"]["partial"] or omissions or
                   any(historical["rows_omitted_by_review"].values()) or candidate is None)
    report = {"schema": SCHEMA, "status": "STRUCTURAL_REVIEW_COMPLETE", "context_sha256": expected_context_sha256,
              "source_binding": "CAPTURED_DTRA_REQUEST_BYTES", "current_git_head_rechecked": False,
              "request_id": request.request_id, "request_fingerprint": request.request_fingerprint,
              "response_sha256": _sha(response_bytes), "base_commit": source.base_commit,
              "base_tree": source.base_tree, "target_path": source.path,
              "original_sha256": _sha(source.content), "proposed_sha256": _sha(updated),
              "original_ast_sha256": original_ast_sha, "proposed_ast_sha256": proposed_ast_sha,
              "selected": selected, "definition_changes": changes[:MAX_RESULT_ROWS],
              "file_comparison": {"text_changed": source.content != updated,
                                  "ast_changed": original_ast_sha != proposed_ast_sha,
                                  "text_only_ast_unchanged": original_ast_sha == proposed_ast_sha,
                                  "outside_selected_ast_changed": outside_ast,
                                  "outside_selected_text_changed": outside_text,
                                  "outside_selected_scope": "WHOLE_FILE_WITH_SELECTED_REPLACED" if candidate else "UNKNOWN",
                                  "outside_text_scope": "COMPLETE_DEFINITION_LINES_INCLUDING_DECORATORS" if candidate else "UNKNOWN",
                                  "module_level_ast_changed": _ast_hash(original_tree, module_skeleton=True) !=
                                                              _ast_hash(proposed_tree, module_skeleton=True),
                                  "module_level_scope": "OUTSIDE_DEFINITION_SUBTREES_WITH_ORDERED_NAME_KIND_MARKERS",
                                  "semantic_equivalence_proven": False},
              "historical_references": historical,
              "coverage": {"partial": partial, "original_ast": original_stats, "proposed_ast": proposed_stats,
                           "definition_changes_total": len(changes), "definition_changes_omitted": omissions,
                           "limits": {"source_bytes": MAX_SOURCE_BYTES, "ast_nodes_per_file": MAX_AST_NODES,
                                      "ast_depth": MAX_AST_DEPTH, "definitions_per_file": MAX_DEFINITIONS,
                                      "rows_per_section": MAX_RESULT_ROWS, "context_bytes": MAX_CONTEXT_BYTES},
                           "limitations": ["AST_CHANGES_DO_NOT_PROVE_BEHAVIOR_OR_BUG_FIX",
                                           "AST_UNCHANGED_DOES_NOT_PROVE_SEMANTIC_EQUIVALENCE",
                                           "UNIQUE_QUALNAME_MAPPING_DOES_NOT_PROVE_RUNTIME_IDENTITY",
                                           "REMOVAL_IS_NOT_PROOF_OF_RENAME",
                                           "ANCESTOR_BODY_HASH_INCLUDES_DESCENDANT_CHANGES",
                                           "HISTORICAL_REFERENCES_ARE_NOT_REANALYZED_CALLER_IMPACTS",
                                           "NO_FOUND_CALLERS_IS_NOT_PROOF_OF_NO_CALLERS"]},
              "structural_only": True, "runtime_calls_proven": False, "no_patch_or_apply": True,
              "source_text_included": False, "project_file_written": False, "source_code_executed": False,
              "changed_code_executed": False, "behavior": "NOT_TESTED", "git_diff_check": "NOT_RUN",
              "py_compile": "NOT_RUN", "pipeline_check": "NOT_RUN", "dtrb_rehearsal_completed": False,
              "runtime_authorized": False, "promotion_authorized": False, "installation_authorized": False}
    _check(len(_canonical(report)) <= MAX_REVIEW_BYTES, "CORE_CANDIDATE_REVIEW_BUDGET")
    return report


def format_candidate_review(report) -> str:
    """Human-readable structural result, separate from the static DTR receipt."""
    _check(type(report) is dict and report.get("schema") == SCHEMA and
           report.get("status") == "STRUCTURAL_REVIEW_COMPLETE", "CORE_CANDIDATE_REVIEW_SCHEMA")
    selected = report["selected"]
    comparison = report["file_comparison"]
    state = lambda value: "неизвестно" if value is None else ("да" if value else "нет")
    lines = ["Core: структурная проверка кандидата", f"Файл: {report['target_path']}",
             f"Основа: захваченные байты DTR-A; commit {report['base_commit']}.",
             "Текущий Git HEAD повторно не проверялся.",
             f"Функция: {selected['before']['qualname']}; сопоставление: {selected['mapping']}."]
    if selected["components_changed"] is not None:
        labels = {"body": "тело", "signature": "сигнатура", "decorators": "декораторы", "name": "имя", "kind": "вид / async"}
        changed = [labels[key] for key, value in selected["components_changed"].items() if value]
        lines.append("Изменения выбранного определения в AST: " + (", ".join(changed) or "не обнаружены") + ".")
    else:
        lines.append("Продолжение выбранного определения не установлено; переименование не выводится автоматически.")
    lines += [f"AST изменён вне выбранной функции: {state(comparison['outside_selected_ast_changed'])}.",
              f"Текст изменён вне её полных строк с декораторами: {state(comparison['outside_selected_text_changed'])}.",
              f"AST на уровне модуля вне определений изменён: {state(comparison['module_level_ast_changed'])}."]
    if comparison["text_only_ast_unchanged"]:
        lines.append("Байты изменились, AST совпал: это текстовое изменение, не доказательство эквивалентного поведения.")
    relations = {"SELECTED": "выбранное", "ANCESTOR": "внешнее определение", "DESCENDANT": "вложенное определение", "OTHER": "другое определение"}
    for row in report["definition_changes"]:
        lines.append(f"• {row['qualname']}: {row['status']}; {relations[row['relation_to_selected']]}." +
                     (" Его AST включает изменения потомков." if row["ancestor_body_includes_selected"] else ""))
    history = report["historical_references"]
    lines += [f"Исторические входящие ссылки: {history['coverage']['counts']['incoming']}; "
              f"показано {len(history['incoming'])}. Они относятся к исходному commit.",
              "Ссылки не доказывают реальный вызов, полный список вызывающих функций или их поломку после изменения."]
    for row in history["incoming"]:
        caller = row["caller"]; site = row["call_site"]
        lines.append(f"• {caller['path']}::{caller['qualname']}, строка вызова {site['line']}: {row['resolution']}.")
    lines += [f"Неразрешённых исходящих вызовов исходной функции: {history['coverage']['counts']['selected_unknowns']}.",
              f"Неполнота / ограничение вывода: {state(report['coverage']['partial'])}; "
              f"пропущено определений в выводе: {report['coverage']['definition_changes_omitted']}.",
              "Код не выполнялся и не применялся. Поведение, исправление и совместимость вызывающего кода не проверены.",
              "Это не git_diff_check, py_compile, pipeline(check), DTR-B или разрешение на исполнение / установку."]
    return "\n".join(lines) + "\n"
