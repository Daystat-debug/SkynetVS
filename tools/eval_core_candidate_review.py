"""Synthetic real-contract roundtrips for the Core structural candidate review.

Run: Python -I -S -B tools/eval_core_candidate_review.py
Only owned source strings are parsed, never imported, compiled or executed.
Synthetic observed flags below are fixture metadata, not actual Git observation.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import replace
import difflib
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).absolute().parent.parent
BUNDLE = ROOT / "modules" / "developer_task_ui"
sys.dont_write_bytecode = True
sys.path[:0] = [str(BUNDLE / "vendor"), str(BUNDLE)]

from app.core import (SourceSnapshot, json_bytes, make_request, request_document,
                      response_template, restore_request, review_response)
from app.patch_preview import preview_patch_in_memory
from app.symbol_candidate_review import (CandidateReviewError, CONTEXT_SCHEMA,
    MAX_AST_DEPTH, MAX_AST_NODES, MAX_CONTEXT_BYTES, MAX_DEFINITIONS, MAX_RESULT_ROWS,
    SCHEMA, bind_request_context, format_candidate_review, review_candidate)
from app.symbol_investigation import investigate_sources
from app.symbol_task_bridge import report_fingerprint, task_instruction
from app.task_request_bridge import bounded_title
from modules.developer import developer_task_proposal_intake as bundled_intake

COMMIT = "a" * 40
TREE = "b" * 40
PATH = "modules/sample.py"
GOAL = "Измени выбранную функцию в modules/sample.py, сохрани поведение остальных функций."
SOURCE = ("def normalize(value):\n    return value.strip()\n\n"
          "def clean(value):\n    return normalize(value)\n")
PROPOSED = SOURCE.replace("return value.strip()", "return value.strip().lower()")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fixture(original=SOURCE, *, selector="normalize", extra_sources=None, report_mutator=None):
    sources = {PATH: original, **(extra_sources or {})}
    report = investigate_sources(COMMIT, sources, {"partial": False}, GOAL, f"{PATH}::{selector}")
    report["git_head_observed"] = True
    report["source_binding"] = "OBSERVED_GIT_HEAD_BLOBS"
    if report_mutator is not None:
        report_mutator(report)
    source = SourceSnapshot(PATH, original.encode("utf-8"), COMMIT, TREE,
                            {"kind": "OBSERVED_COMMITTED_FILE", "current_git_head_observed": True,
                             "synthetic_test_fixture": True})
    digest = report_fingerprint(report)
    request = make_request(source, bounded_title(GOAL), task_instruction(GOAL, report, digest),
                           request_id="req:core:candidate:test", task_id="core-candidate-test")
    context = bind_request_context(goal=GOAL, report=report, expected_report_sha256=digest,
                                   request=request, source=source)
    return {"report": report, "source": source, "request": request, "context_bytes": context,
            "expected_context_sha256": _sha(context)}


def proposal(state, proposed=PROPOSED, *, patch_text=None):
    source = state["source"]
    if patch_text is None:
        patch_text = f"diff --git a/{PATH} b/{PATH}\n" + "".join(difflib.unified_diff(
            source.content.decode("utf-8").splitlines(keepends=True), proposed.splitlines(keepends=True),
            fromfile="a/" + PATH, tofile="b/" + PATH))
    response = response_template(state["request"])
    response.update(patch_text=patch_text, explanation="Owned synthetic structural candidate; never executed.")
    raw = json_bytes(response)
    # Exercise the actual pinned intake and preview, not a fabricated PASS.
    intake = review_response(state["request"], raw)
    preview = preview_patch_in_memory(original=source.content, patch_text=intake["patch_text"], target_path=PATH,
                                      request_fingerprint=state["request"].request_fingerprint,
                                      response_sha256=intake["response_sha256"])
    return raw, preview


def run_review(state, proposed=PROPOSED, **overrides):
    raw, preview = proposal(state, proposed)
    kwargs = {key: state[key] for key in ("context_bytes", "expected_context_sha256", "request", "source")}
    kwargs.update(response_bytes=raw, preview=preview)
    kwargs.update(overrides)
    return review_candidate(**kwargs)


class CoreCandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.state = fixture()

    def assertRefused(self, expected_code, state=None, proposed=PROPOSED, **overrides):
        with self.assertRaisesRegex(CandidateReviewError, expected_code):
            run_review(state or self.state, proposed, **overrides)

    def test_ccr01_real_vendor_intake_and_request_roundtrip(self):
        self.assertTrue(Path(bundled_intake.__file__).resolve().is_relative_to((BUNDLE / "vendor").resolve()))
        request, source = restore_request(json_bytes(request_document(self.state["request"], self.state["source"])))
        result = run_review(self.state, request=request, source=source)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["status"], "STRUCTURAL_REVIEW_COMPLETE")
        self.assertEqual(result["source_binding"], "CAPTURED_DTRA_REQUEST_BYTES")
        self.assertFalse(result["current_git_head_rechecked"])
        # This tests byte binding only; UI restoration does not re-establish a
        # trusted current-session context and is covered by the UI evaluator.

    def test_ccr02_body_change_is_selected_and_keeps_historical_caller(self):
        result = run_review(self.state)
        self.assertEqual(result["selected"]["mapping"], "UNIQUE_QUALNAME")
        self.assertEqual(result["selected"]["components_changed"],
                         {"body": True, "signature": False, "decorators": False, "name": False, "kind": False})
        self.assertFalse(result["file_comparison"]["outside_selected_ast_changed"])
        self.assertFalse(result["file_comparison"]["outside_selected_text_changed"])
        history = result["historical_references"]
        self.assertEqual(history["incoming"][0]["caller"]["qualname"], "clean")
        self.assertEqual(history["git_commit"], COMMIT)
        self.assertFalse(history["callers_reanalyzed_against_candidate"])
        self.assertFalse(history["all_callers_known"])

    def test_ccr03_signature_defaults_annotations_and_kind_separate(self):
        proposed = SOURCE.replace("def normalize(value):", "def normalize(value: str, extra=None) -> str:")
        result = run_review(self.state, proposed)
        self.assertTrue(result["selected"]["components_changed"]["signature"])
        self.assertFalse(result["selected"]["components_changed"]["body"])
        self.assertFalse(result["selected"]["components_changed"]["kind"])
        self.assertFalse(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr04_async_conversion_maps_unique_name_and_flags_kind(self):
        result = run_review(self.state, SOURCE.replace("def normalize", "async def normalize"))
        self.assertEqual(result["selected"]["mapping"], "UNIQUE_QUALNAME")
        self.assertEqual(result["selected"]["after"]["kind"], "AsyncFunctionDef")
        self.assertTrue(result["selected"]["components_changed"]["kind"])
        self.assertFalse(result["selected"]["components_changed"]["body"])
        self.assertFalse(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr05_decorators_are_inside_definition_text_range(self):
        original = "@decorate\n" + SOURCE
        state = fixture(original)
        result = run_review(state, original.replace("@decorate", "@another"))
        self.assertEqual(result["selected"]["before"]["start"], 2)
        self.assertEqual(result["selected"]["before"]["text_start"], 1)
        self.assertTrue(result["selected"]["components_changed"]["decorators"])
        self.assertFalse(result["file_comparison"]["outside_selected_text_changed"])
        self.assertFalse(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr06_other_function_change_is_outside_selected(self):
        result = run_review(self.state, SOURCE.replace("return normalize(value)", "return normalize(value).upper()"))
        self.assertFalse(result["selected"]["ast_changed"])
        self.assertTrue(result["file_comparison"]["outside_selected_ast_changed"])
        rows = result["definition_changes"]
        self.assertEqual([(row["qualname"], row["relation_to_selected"]) for row in rows], [("clean", "OTHER")])

    def test_ccr07_added_and_removed_definitions_are_explicit(self):
        proposed = SOURCE[:SOURCE.index("def clean")] + "def helper(value):\n    return value\n"
        result = run_review(self.state, proposed)
        rows = {row["qualname"]: row["status"] for row in result["definition_changes"]}
        self.assertEqual(rows, {"clean": "REMOVED_OR_RENAMED", "helper": "ADDED"})
        self.assertTrue(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr08_selected_disappearance_never_infers_rename_or_only_selected(self):
        result = run_review(self.state, SOURCE.replace("def normalize", "def renamed"))
        self.assertEqual(result["selected"]["mapping"], "REMOVED_OR_RENAMED")
        self.assertFalse(result["selected"]["name_change_inferred"])
        self.assertIsNone(result["file_comparison"]["outside_selected_ast_changed"])
        self.assertEqual(result["file_comparison"]["outside_selected_scope"], "UNKNOWN")
        self.assertTrue(result["coverage"]["partial"])

    def test_ccr09_candidate_duplicate_name_is_ambiguous_even_different_kind(self):
        result = run_review(self.state, PROPOSED + "\nasync def normalize(value):\n    return value\n")
        self.assertEqual(result["selected"]["mapping"], "AMBIGUOUS_DEFINITIONS")
        self.assertIsNone(result["file_comparison"]["outside_selected_ast_changed"])
        self.assertTrue(any(row["status"] == "AMBIGUOUS_DEFINITIONS" for row in result["definition_changes"]))

    def test_ccr10_original_duplicate_selected_by_line_still_maps_conservatively(self):
        original = "def normalize(value):\n    return value\n\ndef normalize(value):\n    return value.strip()\n"
        state = fixture(original, selector="normalize@1")
        result = run_review(state, original.replace("return value\n", "return str(value)\n", 1))
        self.assertEqual(result["selected"]["mapping"], "AMBIGUOUS_DEFINITIONS")
        self.assertIsNone(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr11_nested_selection_marks_ancestor_reflection(self):
        original = ("def outer(value):\n    def normalize(item):\n        return item.strip()\n"
                    "    return normalize(value)\n")
        state = fixture(original, selector="outer.normalize")
        result = run_review(state, original.replace("item.strip()", "item.strip().lower()"))
        rows = {row["qualname"]: row for row in result["definition_changes"]}
        self.assertEqual(rows["outer"]["relation_to_selected"], "ANCESTOR")
        self.assertTrue(rows["outer"]["ancestor_body_includes_selected"])
        self.assertEqual(rows["outer.normalize"]["relation_to_selected"], "SELECTED")
        self.assertFalse(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr12_nested_descendant_change_is_not_unrelated(self):
        original = ("def normalize(value):\n    def helper(item):\n        return item.strip()\n"
                    "    return helper(value)\n")
        state = fixture(original)
        result = run_review(state, original.replace("item.strip()", "item.strip().lower()"))
        rows = {row["qualname"]: row for row in result["definition_changes"]}
        self.assertEqual(rows["normalize.helper"]["relation_to_selected"], "DESCENDANT")
        self.assertTrue(rows["normalize"]["components_changed"]["body"])
        self.assertFalse(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr13_module_import_global_and_control_flow_do_not_disappear(self):
        original = "import os\nFLAG = 1\n" + SOURCE + "\nif FLAG:\n    clean('x')\n"
        state = fixture(original)
        for old, new in (("import os", "import sys"), ("FLAG = 1", "FLAG = 2"), ("if FLAG:", "if not FLAG:")):
            with self.subTest(change=old):
                result = run_review(state, original.replace(old, new))
                self.assertTrue(result["file_comparison"]["outside_selected_ast_changed"])
                self.assertTrue(result["file_comparison"]["module_level_ast_changed"])
                self.assertEqual(result["definition_changes"], [])

    def test_ccr14_definition_reordering_is_outside_change(self):
        first, second = SOURCE.split("\ndef clean", 1)
        result = run_review(self.state, "def clean" + second + "\n" + first)
        self.assertTrue(result["file_comparison"]["outside_selected_ast_changed"])
        self.assertTrue(result["file_comparison"]["module_level_ast_changed"])
        self.assertFalse(result["selected"]["ast_changed"])

    def test_ccr15_whitespace_comment_only_is_ast_unchanged_not_behavior_proof(self):
        proposed = SOURCE.replace("return value.strip()", "return  value.strip()  # explanatory comment")
        result = run_review(self.state, proposed)
        self.assertTrue(result["file_comparison"]["text_only_ast_unchanged"])
        self.assertFalse(result["file_comparison"]["semantic_equivalence_proven"])
        self.assertFalse(result["selected"]["ast_changed"])
        self.assertEqual(result["definition_changes"], [])
        self.assertEqual(result["behavior"], "NOT_TESTED")

    def test_ccr16_outside_comment_is_visible_without_ast_claim(self):
        result = run_review(self.state, "# added outside function\n" + SOURCE)
        self.assertTrue(result["file_comparison"]["text_only_ast_unchanged"])
        self.assertTrue(result["file_comparison"]["outside_selected_text_changed"])
        self.assertFalse(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr17_unknown_dynamic_references_survive(self):
        original = SOURCE.replace("return value.strip()", "return callback(value)")
        state = fixture(original)
        result = run_review(state, original.replace("callback(value)", "callback(str(value))"))
        historical = result["historical_references"]
        self.assertEqual(historical["coverage"]["counts"]["selected_unknowns"], 1)
        self.assertEqual(historical["unknown_outgoing"][0]["reason"], "EXTERNAL_OR_UNBOUND_NAME")
        self.assertFalse(historical["runtime_calls_proven"])

    def test_ccr18_historical_caller_and_definition_rows_have_honest_limits(self):
        callers = "".join(f"\ndef caller_{i}(value):\n    return normalize(value)\n" for i in range(80))
        original = SOURCE + callers
        state = fixture(original)
        proposed = original.replace("return normalize(value)", "return normalize(value).upper()")
        result = run_review(state, proposed)
        self.assertEqual(len(result["historical_references"]["incoming"]), MAX_RESULT_ROWS)
        self.assertEqual(result["historical_references"]["rows_omitted_by_review"]["incoming"], 17)
        self.assertEqual(len(result["definition_changes"]), MAX_RESULT_ROWS)
        self.assertEqual(result["coverage"]["definition_changes_omitted"], 17)
        self.assertTrue(result["coverage"]["partial"])

    def test_ccr19_existing_scan_limits_and_original_truncation_are_retained(self):
        callers = "".join(f"\ndef caller_{i}(value):\n    return normalize(value)\n" for i in range(280))
        state = fixture(SOURCE + callers)
        result = run_review(state, PROPOSED + callers)
        history = result["historical_references"]
        self.assertEqual(history["coverage"]["counts"]["incoming"], 281)
        self.assertEqual(history["coverage"]["truncated"]["incoming"], 25)
        self.assertEqual(history["rows_omitted_by_review"]["incoming"], 192)
        self.assertTrue(result["coverage"]["partial"])

    def test_ccr20_context_is_canonical_immutable_and_source_free(self):
        data = self.state["context_bytes"]
        context = json.loads(data)
        self.assertEqual(context["schema"], CONTEXT_SCHEMA)
        self.assertEqual(_canonical(context), data)
        self.assertLessEqual(len(data), MAX_CONTEXT_BYTES)
        self.assertEqual(context["report"], self.state["report"])
        self.assertNotIn("context_base64", context)
        self.assertNotIn("return value.strip()", data.decode("utf-8"))
        self.state["report"]["selected"]["end"] += 1
        self.assertEqual(run_review(self.state)["selected"]["before"]["end"], 2)

    def test_ccr21_context_mutation_wrong_digest_noncanonical_and_extra_source_refused(self):
        data = self.state["context_bytes"]
        self.assertRefused("CONTEXT_CHANGED", context_bytes=data + b" ")
        self.assertRefused("CONTEXT_CHANGED", expected_context_sha256="0" * 64)
        altered = data + b"\n"
        self.assertRefused("CONTEXT_ENCODING", context_bytes=altered, expected_context_sha256=_sha(altered))
        obj = json.loads(data)
        obj["report"]["raw_source"] = SOURCE
        changed = _canonical(obj)
        self.assertRefused("CONTEXT_BINDING_REFUSED|EVIDENCE_SHAPE", context_bytes=changed,
                          expected_context_sha256=_sha(changed))

    def test_ccr22_rebound_context_with_another_request_is_refused(self):
        request = self.state["request"]
        alternate = make_request(self.state["source"], request.title, request.instruction,
                                 request_id="req:another:request", task_id=request.task_id)
        self.assertRefused("CONTEXT_BINDING_MISMATCH", request=alternate)
        for change in ({"base_commit": "c" * 40}, {"base_tree": "d" * 40},
                       {"path": "modules/other.py"}, {"content": self.state["source"].content + b"\n"}):
            with self.subTest(fields=list(change)):
                self.assertRefused("CONTEXT_BINDING_REFUSED|REQUEST_BINDING_MISMATCH",
                                  source=replace(self.state["source"], **change))

    def test_ccr23_title_instruction_and_exact_selected_metadata_are_verified(self):
        report = self.state["report"]; source = self.state["source"]; request = self.state["request"]
        for title, instruction in (("Another title", request.instruction), (request.title, "Измени другую функцию.")):
            wrong = make_request(source, title, instruction, request_id=request.request_id, task_id=request.task_id)
            with self.assertRaisesRegex(CandidateReviewError, "REQUEST_BINDING_MISMATCH"):
                bind_request_context(goal=GOAL, report=report, expected_report_sha256=report_fingerprint(report),
                                     request=wrong, source=source)
        for key, value in (("end", 3), ("id", "0" * 64), ("kind", "AsyncFunctionDef")):
            with self.subTest(field=key):
                altered = copy.deepcopy(report)
                altered["selected"][key] = value
                altered["candidates"] = [copy.deepcopy(altered["selected"])]
                # The selection metadata is changed in incoming edges as well,
                # so the test reaches verification against actual source AST.
                for row in altered["incoming"]:
                    row["callee"] = copy.deepcopy(altered["selected"])
                for field in ("outgoing", "unknown_outgoing"):
                    for row in altered[field]:
                        row["caller"] = copy.deepcopy(altered["selected"])
                with self.assertRaisesRegex(CandidateReviewError, "SELECTED_DEFINITION_MISMATCH"):
                    bind_request_context(goal=GOAL, report=altered, expected_report_sha256=report_fingerprint(altered),
                                         request=request, source=source)

    def test_ccr24_invalid_or_foreign_response_uses_actual_dtra_rejection(self):
        raw, preview = proposal(self.state)
        for candidate in (b"not json", b"{}", b'{"kind":1,"kind":2}'):
            with self.subTest(response=candidate):
                self.assertRefused("DTRA_REJECTED", response_bytes=candidate, preview=preview)
        response = json.loads(raw)
        response["request_id"] = "req:foreign:response"
        self.assertRefused("DTRA_REJECTED", response_bytes=json_bytes(response), preview=preview)

    def test_ccr25_preview_hashes_status_and_authority_flags_are_bound(self):
        raw, preview = proposal(self.state)
        changes = {"request_fingerprint": "0" * 64, "response_sha256": "0" * 64,
                   "original_sha256": "0" * 64, "proposed_sha256": "0" * 64,
                   "target_path": "modules/other.py", "preview_status": "OTHER", "python_ast_parse": "REJECTED",
                   "text_applicability": "NOT_PROVEN", "project_file_written": True, "hunks": True,
                   "runtime_authorized": True, "py_compile": "PASS", "behavior": "PASS", "issue_code": "ERROR"}
        for field, value in changes.items():
            with self.subTest(field=field):
                altered = {**preview, field: value}
                self.assertRefused("PREVIEW_BINDING_MISMATCH", response_bytes=raw, preview=altered)

    def test_ccr26_patch_is_reconstructed_even_if_preview_claims_pass(self):
        raw, preview = proposal(self.state)
        response = json.loads(raw)
        response["patch_text"] = response["patch_text"].replace("-    return value.strip()", "-    return absent(value)")
        changed = json_bytes(response)
        preview["response_sha256"] = _sha(changed)
        self.assertRefused("PATCH_REFUSED", response_bytes=changed, preview=preview)

    def test_ccr27_candidate_ast_is_reparsed_even_if_preview_claims_pass(self):
        proposed = SOURCE.replace("return value.strip()", "return (")
        raw, preview = proposal(self.state, proposed)
        self.assertEqual(preview["python_ast_parse"], "REJECTED")
        self.assertRefused("PREVIEW_BINDING_MISMATCH", response_bytes=raw, preview=preview)
        forged = {**preview, "preview_status": "TEXT_APPLICABLE_AST_PASS_NOT_EXECUTABLE_CHECKS",
                  "python_ast_parse": "PASS", "issue_code": None}
        self.assertRefused("AST_REFUSED", response_bytes=raw, preview=forged)

    def test_ccr28_class_conversion_is_unsupported_mapping(self):
        result = run_review(self.state, SOURCE.replace("def normalize(value):", "class normalize:"))
        self.assertEqual(result["selected"]["mapping"], "UNSUPPORTED_KIND_CHANGE")
        self.assertIsNone(result["selected"]["after"])
        self.assertIsNone(result["file_comparison"]["outside_selected_ast_changed"])

    def test_ccr29_original_and_candidate_execution_are_absent_and_literals_do_not_leak(self):
        original = "raise RuntimeError('THIS_SOURCE_MUST_NEVER_EXECUTE')\n" + SOURCE
        state = fixture(original)
        proposed = original.replace("return value.strip()", "return 'SENSITIVE_CANDIDATE_LITERAL_73428'")
        result = run_review(state, proposed)
        rendered = _canonical(result).decode("utf-8") + format_candidate_review(result)
        for secret in ("THIS_SOURCE_MUST_NEVER_EXECUTE", "SENSITIVE_CANDIDATE_LITERAL_73428", "return value.strip()"):
            self.assertNotIn(secret, rendered)
        for flag in ("source_text_included", "source_code_executed", "changed_code_executed", "project_file_written",
                     "runtime_calls_proven", "runtime_authorized", "promotion_authorized", "installation_authorized"):
            self.assertFalse(result[flag])
        self.assertTrue(result["structural_only"])
        self.assertTrue(result["no_patch_or_apply"])

    def test_ccr30_ast_and_definition_budgets_refuse_without_partial_guess(self):
        # Lowering documented budgets exercises real parsed structures cheaply;
        # the production limits remain unchanged and are checked below.
        self.assertEqual((MAX_AST_NODES, MAX_AST_DEPTH, MAX_DEFINITIONS), (60000, 80, 2048))
        for name, value in (("MAX_AST_NODES", 3), ("MAX_AST_DEPTH", 1), ("MAX_DEFINITIONS", 1)):
            with self.subTest(budget=name), patch("app.symbol_candidate_review." + name, value):
                self.assertRefused("AST_BUDGET|DEFINITION_BUDGET")

    def test_ccr31_partial_scan_and_parse_diagnostic_are_preserved(self):
        def partial(report):
            report["coverage"]["scan"] = {"partial": True, "skipped": {"too_large": 1}}
            report["coverage"]["partial"] = True
        state = fixture(extra_sources={"modules/broken.py": "def broken(:\n"}, report_mutator=partial)
        result = run_review(state)
        self.assertTrue(result["coverage"]["partial"])
        history = result["historical_references"]["coverage"]
        self.assertEqual(history["scan"]["skipped"]["too_large"], 1)
        self.assertEqual(history["parse_diagnostics"][0]["reason"], "AST_SyntaxError")

    def test_ccr32_module_type_ignore_line_numbers_do_not_fake_ast_changes(self):
        original = "import os  # type: ignore\n" + SOURCE
        state = fixture(original)
        result = run_review(state, "\n" + original)
        self.assertTrue(result["file_comparison"]["text_only_ast_unchanged"])
        self.assertFalse(result["file_comparison"]["module_level_ast_changed"])

    def test_ccr33_cross_module_callers_stay_at_original_commit(self):
        other = "from modules.sample import normalize\n\ndef caller(value):\n    return normalize(value)\n"
        state = fixture(extra_sources={"modules/consumer.py": other})
        result = run_review(state)
        rows = result["historical_references"]["incoming"]
        self.assertTrue(any(row["caller"]["path"] == "modules/consumer.py" and
                            row["resolution"] == "EXPLICIT_IMPORT" for row in rows))
        self.assertIn("исходному commit", format_candidate_review(result))
        self.assertFalse(result["historical_references"]["callers_reanalyzed_against_candidate"])

    def test_ccr34_closed_evidence_schema_rejects_new_source_fields_even_rehashed(self):
        report = copy.deepcopy(self.state["report"])
        report["coverage"]["source_text"] = SOURCE
        with self.assertRaisesRegex(CandidateReviewError, "EVIDENCE_SHAPE"):
            bind_request_context(goal=GOAL, report=report, expected_report_sha256=report_fingerprint(report),
                                 request=self.state["request"], source=self.state["source"])

    def test_ccr35_no_filesystem_network_process_or_eval_operations_in_review_module(self):
        # Static guard for this pure module; fixtures above exercise its actual
        # bundled-contract behavior without running any proposed source text.
        path = BUNDLE / "app" / "symbol_candidate_review.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_names = {"eval", "exec", "compile", "open", "__import__"}
        forbidden_roots = {"os", "subprocess", "socket", "requests", "urllib", "pathlib", "importlib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, forbidden_names)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                self.assertFalse(any(name.split(".")[0] in forbidden_roots for name in names))

    def test_ccr36_parse_diagnostics_are_capped_and_full_context_is_retained(self):
        bad_sources = {f"modules/broken_{i}.py": "def broken(:\n" for i in range(80)}
        state = fixture(extra_sources=bad_sources)
        result = run_review(state)
        history = result["historical_references"]
        self.assertEqual(len(history["coverage"]["parse_diagnostics"]), MAX_RESULT_ROWS)
        self.assertEqual(history["rows_omitted_by_review"]["parse_diagnostics"], 16)
        self.assertTrue(history["full_original_report_retained_in_context"])
        self.assertEqual(len(json.loads(state["context_bytes"])["report"]["coverage"]["parse_diagnostics"]), 80)


if __name__ == "__main__":
    unittest.main(verbosity=2)
