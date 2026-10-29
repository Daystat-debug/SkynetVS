"""Bounded behavioral verification obligations from an already accepted Core review.

No source execution, model inference, filesystem, repository or network I/O.
The input is the in-memory report returned by the trusted Core review path.
This module only proposes checks; expected results are deliberately unspecified.
"""
from __future__ import annotations

import hashlib
import json
import re

SCHEMA = "SKYNETVS_CORE_BEHAVIOR_PLAN_V1"
REVIEW_SCHEMA = "SKYNETVS_CORE_CANDIDATE_REVIEW_V1"
MAX_INPUT_BYTES = 131072
MAX_OUTPUT_BYTES = 65536
MAX_CASES = 32
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
QUALNAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,200}\Z")


class BehaviorPlanError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(ok: bool, code: str):
    if not ok:
        raise BehaviorPlanError(code)


def _canon(value) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError, MemoryError) as exc:
        raise BehaviorPlanError("PLAN_INPUT_NOT_CANONICAL") from exc


def _name(value) -> str:
    _require(type(value) is str and QUALNAME.fullmatch(value) is not None,
             "PLAN_QUALNAME_INVALID")
    return value


def _sha(value) -> str:
    _require(type(value) is str and SHA256.fullmatch(value) is not None,
             "PLAN_SHA_INVALID")
    return value


def _path(value) -> str:
    _require(type(value) is str and len(value) <= 300 and not value.startswith("/")
             and "\\" not in value and ".." not in value.split("/")
             and (value == "main.py" or (value.startswith("modules/") and value.endswith(".py"))),
             "PLAN_PATH_INVALID")
    return value


def make_behavior_plan(review: dict) -> dict:
    """Create explicit review/test obligations; never claim behavioral PASS.

    Review is accepted from the in-session Core comparison, not a user-supplied
    sidecar. Structural validation below does *not* authenticate arbitrary reports.
    """
    _require(type(review) is dict, "PLAN_REVIEW_TYPE")
    raw = _canon(review)
    _require(len(raw) <= MAX_INPUT_BYTES, "PLAN_REVIEW_TOO_LARGE")
    _require(review.get("schema") == REVIEW_SCHEMA and
             review.get("status") == "STRUCTURAL_REVIEW_COMPLETE" and
             review.get("structural_only") is True and
             review.get("no_patch_or_apply") is True and
             review.get("source_code_executed") is False and
             review.get("changed_code_executed") is False and
             review.get("installation_authorized") is False and
             review.get("behavior") == "NOT_TESTED", "PLAN_REVIEW_NOT_TRUSTED_STATE")
    _require(type(review.get("selected")) is dict and
             type(review.get("file_comparison")) is dict and
             type(review.get("historical_references")) is dict and
             type(review.get("coverage")) is dict, "PLAN_MISSING_EVIDENCE")
    source = review["selected"]
    selected = _name(source["before"]["qualname"])
    path = _path(review["target_path"])
    old_commit = review.get("base_commit")
    _require(type(old_commit) is str and COMMIT.fullmatch(old_commit) is not None,
             "PLAN_COMMIT_INVALID")
    response_sha = _sha(review.get("response_sha256"))
    context_sha = _sha(review.get("context_sha256"))
    review_sha = hashlib.sha256(raw).hexdigest()
    _require(type(review.get("request_id")) is str and
             1 <= len(review["request_id"]) <= 150 and
             type(review.get("request_fingerprint")) is str and
             len(review["request_fingerprint"]) == 64 and
             SHA256.fullmatch(review["request_fingerprint"]) is not None,
             "PLAN_REQUEST_BINDING_INVALID")
    comparison = review["file_comparison"]
    coverage = review["coverage"]
    _require(type(coverage.get("partial")) is bool, "PLAN_COVERAGE_INVALID")
    mapping = source.get("mapping")
    selected_ast = source.get("ast_changed")
    _require(type(mapping) is str and type(selected_ast) in (bool, type(None)),
             "PLAN_SELECTED_INVALID")
    outside_ast = comparison.get("outside_selected_ast_changed")
    outside_text = comparison.get("outside_selected_text_changed")
    module_ast = comparison.get("module_level_ast_changed")
    _require(type(outside_ast) in (bool, type(None)) and
             type(outside_text) in (bool, type(None)) and
             type(module_ast) is bool, "PLAN_FILE_COMPARISON_INVALID")
    definition_changes = review.get("definition_changes")
    _require(type(definition_changes) is list and len(definition_changes) <= 64,
             "PLAN_DEFINITION_CHANGES_INVALID")
    history = review["historical_references"]
    incoming = history.get("incoming")
    _require(type(incoming) is list and len(incoming) <= 64 and
             history.get("runtime_calls_proven") is False and
             history.get("callers_reanalyzed_against_candidate") is False,
             "PLAN_HISTORICAL_REFERENCES_INVALID")
    cases = []
    hypotheses = []
    attempted = 0

    def add_case(kind: str, target: str, why: str, ref: dict | None = None):
        nonlocal attempted
        attempted += 1
        if len(cases) >= MAX_CASES:
            return
        item = {"case_id": f"T{len(cases)+1:03d}", "kind": kind,
                "target": _name(target), "basis": why,
                "expected_result": None, "oracle": "MUST_BE_SPECIFIED_BEFORE_TEST",
                "execution": "NOT_RUN", "result": "UNKNOWN"}
        if ref is not None:
            item["historical_reference"] = ref
        cases.append(item)

    mapped = mapping == "UNIQUE_QUALNAME" and selected_ast is not None
    if not mapped or coverage["partial"]:
        hypotheses.append({"code": "H_SCOPE_INCOMPLETE", "finding": "INVESTIGATION_INCOMPLETE",
                           "basis": "AMBIGUOUS_OR_PARTIAL_STATIC_MAPPING", "verified_bug": False})
    if selected_ast is False:
        hypotheses.append({"code": "H_SELECTED_UNCHANGED", "finding": "NO_SELECTED_AST_CHANGE",
                           "basis": "SELECTED_QUALNAME_MAPPING", "verified_bug": False})
        add_case("VERIFY_REQUESTED_EFFECT", selected, "SELECTED_AST_UNCHANGED")
    elif selected_ast is True:
        hypotheses.append({"code": "H_SELECTED_CHANGE", "finding": "SELECTED_AST_CHANGED",
                           "basis": "AST_COMPARISON_ONLY", "verified_bug": False})
        add_case("SELECTED_FUNCTION_BEHAVIOR", selected, "SELECTED_AST_CHANGED")
    else:
        add_case("IDENTIFY_SELECTED_TARGET", selected, "SELECTED_MAPPING_UNKNOWN")

    other_changes = []
    for row in definition_changes:
        _require(type(row) is dict and type(row.get("relation_to_selected")) is str and
                 row.get("relation_to_selected") in {"SELECTED", "OTHER", "ANCESTOR", "DESCENDANT"} and
                 row.get("status") in {"ADDED", "REMOVED", "CHANGED"},
                 "PLAN_DEFINITION_ROW_INVALID")
        name = _name(row.get("qualname"))
        if row["relation_to_selected"] != "SELECTED":
            other_changes.append(name)
            add_case("OTHER_DEFINITION_REGRESSION", name, "CHANGED_OUTSIDE_SELECTED_AST")
    drift = outside_ast is True or outside_text is True or bool(other_changes)
    if drift:
        hypotheses.append({"code": "H_SCOPE_DRIFT", "finding": "CHANGES_OUTSIDE_SELECTED",
                           "basis": "OUTSIDE_SCOPE_AST_OR_TEXT", "verified_bug": False})
        if not other_changes:
            add_case("OUTSIDE_SCOPE_REVIEW", selected, "OUTSIDE_SELECTED_TEXT_OR_AST_CHANGED")

    # Historical links identify review targets, not execution paths or reliable callers.
    seen = set()
    for row in incoming:
        _require(type(row) is dict and type(row.get("caller")) is dict and
                 type(row.get("call_site")) is dict, "PLAN_CALLER_ROW_INVALID")
        caller = row["caller"]
        caller_name = _name(caller.get("qualname"))
        caller_path = _path(caller.get("path"))
        line = row["call_site"].get("line")
        _require(type(line) is int and 1 <= line <= 2000000, "PLAN_CALLER_LINE_INVALID")
        key = (caller_path, caller_name, line)
        if key in seen:
            continue
        seen.add(key)
        add_case("HISTORICAL_CALLSITE_REGRESSION", caller_name, "HISTORICAL_STATIC_CALLSITE",
                 {"path": caller_path, "line": line, "commit": old_commit,
                  "runtime_call_proven": False})
    if module_ast:
        add_case("MODULE_IMPORT_REGRESSION", selected, "MODULE_LEVEL_AST_CHANGED")
    changed_components = source.get("components_changed")
    if type(changed_components) is dict:
        if changed_components.get("signature") is True or changed_components.get("kind") is True:
            add_case("CALL_INTERFACE_COMPATIBILITY", selected, "SIGNATURE_OR_ASYNC_CHANGE")
    partial_cases = attempted > MAX_CASES or coverage["partial"]
    if not mapped or coverage["partial"]:
        disposition = "INSUFFICIENT_STATIC_EVIDENCE"
    elif drift or selected_ast is False:
        disposition = "HUMAN_SCOPE_AND_INTENT_REVIEW_REQUIRED"
    else:
        disposition = "TEST_ORACLE_REQUIRED"
    result = {"schema": SCHEMA, "status": "HYPOTHESES_AND_TEST_OBLIGATIONS_ONLY",
              "disposition": disposition, "base_commit": old_commit,
              "target_path": path, "selected_qualname": selected,
              "request_id": review["request_id"],
              "request_fingerprint": review["request_fingerprint"],
              "context_sha256": context_sha, "response_sha256": response_sha,
              "core_candidate_review_sha256": review_sha,
              "selected_mapping": mapping,
              "candidate_selected_ast_changed": selected_ast,
              "changes_outside_selected": drift,
              "historical_callers_proven_at_runtime": False,
              "hypotheses": hypotheses, "test_obligations": cases,
              "coverage": {"partial": partial_cases, "truncated": attempted > MAX_CASES,
                           "historical_incoming_observed": len(seen),
                           "changed_other_definitions_observed": len(other_changes),
                           "source_coverage_partial": coverage["partial"]},
              "expected_behavior_supplied": False, "model_generated": False,
              "tests_generated": False, "tests_executed": False,
              "behavior_proven": False, "fix_verified": False,
              "git_diff_check": "NOT_RUN", "py_compile": "NOT_RUN",
              "pipeline_check": "NOT_RUN", "dtrb_rehearsal": "NOT_RUN",
              "execution_authorized": False, "apply_authorized": False,
              "promotion_authorized": False,
              "limitations": ["STATIC_AST_ONLY_NOT_A_BEHAVIOR_ORACLE",
                              "EXPECTED_RESULTS_MUST_BE_DEFINED_INDEPENDENTLY",
                              "HISTORICAL_CALLS_NOT_RUNTIME_CONFIRMED",
                              "NO_PROPOSED_SOURCE_EXECUTION_OR_AUTO_APPLY"]}
    _require(len(_canon(result)) <= MAX_OUTPUT_BYTES, "PLAN_RESULT_TOO_LARGE")
    return result


def format_behavior_plan(plan: dict) -> str:
    _require(type(plan) is dict and plan.get("schema") == SCHEMA and
             plan.get("status") == "HYPOTHESES_AND_TEST_OBLIGATIONS_ONLY",
             "PLAN_REPORT_SHAPE")
    disposition = {"TEST_ORACLE_REQUIRED": "требуются ожидаемые результаты",
                   "HUMAN_SCOPE_AND_INTENT_REVIEW_REQUIRED": "нужна проверка соответствия задаче и области изменений",
                   "INSUFFICIENT_STATIC_EVIDENCE": "недостаточно статических данных"}
    lines = ["Core: гипотезы и план поведенческих проверок (только предложения)",
             "Функция: " + plan["selected_qualname"] + "; Git commit: " + plan["base_commit"],
             "Решение: " + disposition.get(plan["disposition"], "не определено") + "."]
    for h in plan["hypotheses"]:
        if h["code"] == "H_SELECTED_UNCHANGED":
            lines.append("• Выбранная функция не изменилась в AST: ожидаемый эффект задачи не подтверждён.")
        elif h["code"] == "H_SCOPE_DRIFT":
            lines.append("• Есть изменения вне выбранной функции: необходима отдельная проверка их допустимости.")
        elif h["code"] == "H_SELECTED_CHANGE":
            lines.append("• Выбранная функция изменилась в AST, но исправление не доказано.")
        else:
            lines.append("• Неполное / неоднозначное сопоставление: автоматические выводы ограничены.")
    lines.append("Предложенные проверки (ожидаемые результаты ещё не заданы):")
    for test in plan["test_obligations"]:
        lines.append(f"• {test['case_id']} {test['kind']} → {test['target']} ({test['basis']}).")
    if plan["coverage"]["partial"]:
        lines.append("Внимание: план неполный; нельзя считать все риски охваченными.")
    lines.append("Ни один тест не был создан или запущен. Требуются независимые ожидаемые результаты и отдельное разрешение на исполнение.")
    lines.append("План не является DTR-B, git_diff_check, py_compile, pipeline(check), одобрением или применением.")
    return "\n".join(lines) + "\n"
