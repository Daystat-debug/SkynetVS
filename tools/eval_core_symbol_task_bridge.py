"""Synthetic integration cases for structural evidence -> unchanged bundled DTR-A.

Run with the project Python: -I -S -B tools/eval_core_symbol_task_bridge.py.
Only owned in-memory source fixtures are parsed. No application source is run.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).absolute().parent.parent
BUNDLE = ROOT / "modules" / "developer_task_ui"
sys.dont_write_bytecode = True
sys.path[:0] = [str(BUNDLE / "vendor"), str(BUNDLE)]

from app.core import (SourceSnapshot, json_bytes, make_request, request_document,
                      restore_request)
from app.symbol_investigation import investigate_sources
from app.symbol_task_bridge import (MAX_CARD_BYTES, report_fingerprint,
                                     selected_target, task_instruction,
                                     verify_symbol_capture)
from app.task_request_bridge import BridgeRefusal, bounded_title
from modules.developer import developer_task_proposal_intake as bundled_intake

COMMIT = "a" * 40
TREE = "b" * 40
PATH = "modules/sample.py"
GOAL = "Измени normalize в modules/sample.py, чтобы пустая строка возвращалась без ошибки."
SOURCE = ("def normalize(value):\n    return value.strip()\n\n"
          "def clean(value):\n    return normalize(value)\n")


def fixture(*, path=PATH, goal=GOAL):
    # Observed flags are explicit synthetic fixture metadata, not a real Git
    # claim. The repository wrapper's actual read path has its own tests.
    report = investigate_sources(COMMIT, {path: SOURCE}, {"partial": False},
                                 goal, f"{path}::normalize")
    report["git_head_observed"] = True
    report["source_binding"] = "OBSERVED_GIT_HEAD_BLOBS"
    source = SourceSnapshot(path, SOURCE.encode("utf-8"), COMMIT, TREE,
                            {"kind": "OBSERVED_COMMITTED_FILE",
                             "current_git_head_observed": True,
                             "synthetic_test_fixture": True})
    return report, source


class CoreSymbolTaskBridgeTests(unittest.TestCase):
    def setUp(self):
        self.report, self.source = fixture()
        self.digest = report_fingerprint(self.report)

    def test_launch_import_layout_uses_pinned_vendor_contract(self):
        actual = Path(bundled_intake.__file__).resolve()
        self.assertTrue(actual.is_relative_to((BUNDLE / "vendor").resolve()))

    def test_complete_observed_report_binds_one_exact_target(self):
        self.assertEqual(selected_target(GOAL, self.report, self.digest), PATH)
        verify_symbol_capture(GOAL, self.report, self.digest, self.source)

    def test_existing_request_roundtrip_binds_evidence_and_source(self):
        instruction = task_instruction(GOAL, self.report, self.digest)
        request = make_request(self.source, bounded_title(GOAL), instruction,
                               request_id="req:core:test", task_id="core-symbol-test")
        restored, source = restore_request(json_bytes(request_document(request, self.source)))
        self.assertEqual(restored.binding_dict(), request.binding_dict())
        self.assertEqual(source.content, self.source.content)
        self.assertIn(self.digest, restored.instruction)
        self.assertIn(self.report["selected"]["id"], restored.instruction)
        self.assertIn('"runtime_calls_proven":false', restored.instruction)
        self.assertIn('"unknown_outgoing":', restored.instruction)
        self.assertLessEqual(len(instruction.encode("utf-8")), MAX_CARD_BYTES)

    def test_read_only_goal_cannot_create_change_request(self):
        goal = "Покажи определение функции normalize без изменений."
        report, _ = fixture(goal=goal)
        with self.assertRaisesRegex(BridgeRefusal, "CHANGE_GOAL_REQUIRED"):
            selected_target(goal, report, report_fingerprint(report))

    def test_another_valid_edit_goal_requires_new_scan(self):
        goal = "Измени normalize в modules/sample.py, чтобы None возвращал пустую строку."
        with self.assertRaisesRegex(BridgeRefusal, "STALE_GOAL"):
            selected_target(goal, self.report, self.digest)

    def test_retained_report_mutation_is_refused(self):
        self.report["coverage"]["new_field"] = "changed"
        with self.assertRaisesRegex(BridgeRefusal, "REPORT_CHANGED"):
            selected_target(GOAL, self.report, self.digest)

    def test_ambiguous_and_missing_selections_are_refused(self):
        for status in ("CHOICE_REQUIRED", "NOT_FOUND"):
            with self.subTest(status=status):
                report = copy.deepcopy(self.report)
                report["status"], report["selected"] = status, None
                with self.assertRaisesRegex(BridgeRefusal, "SELECTION_REQUIRED"):
                    selected_target(GOAL, report, report_fingerprint(report))

    def test_pure_declared_commit_is_not_observed_git_capture(self):
        report = investigate_sources(COMMIT, {PATH: SOURCE}, {"partial": False},
                                     GOAL, "normalize")
        with self.assertRaisesRegex(BridgeRefusal, "UNOBSERVED_OR_UNSAFE_REPORT"):
            selected_target(GOAL, report, report_fingerprint(report))

    def test_changed_observation_and_execution_flags_are_refused(self):
        values = {"git_head_observed": False, "source_binding": "DECLARED",
                  "structural_only": False, "no_patch_or_apply": False,
                  "repo_worktree_not_read": False, "source_code_executed": True,
                  "source_text_included": True, "runtime_calls_proven": True}
        for key, value in values.items():
            with self.subTest(field=key):
                report = copy.deepcopy(self.report)
                report[key] = value
                with self.assertRaisesRegex(BridgeRefusal, "UNOBSERVED_OR_UNSAFE_REPORT"):
                    selected_target(GOAL, report, report_fingerprint(report))

    def test_original_dtra_protected_path_policy_still_applies(self):
        report, _ = fixture(path="modules/core/example.py")
        with self.assertRaises(ValueError):
            selected_target(GOAL, report, report_fingerprint(report))

    def test_head_drift_is_refused_by_existing_capture_gate(self):
        source = SourceSnapshot(PATH, self.source.content, "c" * 40, TREE, self.source.provenance)
        with self.assertRaisesRegex(BridgeRefusal, "SOURCE_OR_HEAD_DRIFT"):
            verify_symbol_capture(GOAL, self.report, self.digest, source)

    def test_content_drift_at_same_declared_head_is_refused(self):
        source = SourceSnapshot(PATH, self.source.content + b"\n", COMMIT, TREE, self.source.provenance)
        with self.assertRaisesRegex(BridgeRefusal, "SOURCE_CHANGED"):
            verify_symbol_capture(GOAL, self.report, self.digest, source)

    def test_capture_of_another_path_is_refused(self):
        source = SourceSnapshot("modules/other.py", self.source.content, COMMIT, TREE,
                                self.source.provenance)
        with self.assertRaisesRegex(BridgeRefusal, "SOURCE_OR_HEAD_DRIFT"):
            verify_symbol_capture(GOAL, self.report, self.digest, source)

    def test_unobserved_capture_is_refused(self):
        source = SourceSnapshot(PATH, self.source.content, COMMIT, TREE,
                                {"kind": "DEMO_SYNTHETIC_NOT_REPOSITORY"})
        with self.assertRaisesRegex(BridgeRefusal, "SOURCE_OR_HEAD_DRIFT"):
            verify_symbol_capture(GOAL, self.report, self.digest, source)

    def test_existing_64k_capture_limit_is_unchanged(self):
        source = SourceSnapshot(PATH, b"x" * 65537, COMMIT, TREE, self.source.provenance)
        with self.assertRaisesRegex(BridgeRefusal, "SOURCE_OR_HEAD_DRIFT"):
            verify_symbol_capture(GOAL, self.report, self.digest, source)

    def test_invalid_reference_metadata_is_refused(self):
        for key, value in (("start", True), ("end", 0), ("blob_oid", "wrong"),
                           ("source_sha256", "wrong"), ("id", "wrong")):
            with self.subTest(field=key):
                report = copy.deepcopy(self.report)
                report["selected"][key] = value
                with self.assertRaisesRegex(BridgeRefusal, "SELECTION_INVALID"):
                    selected_target(GOAL, report, report_fingerprint(report))

    def test_card_budget_keeps_whole_rows_and_counts_omissions(self):
        report = copy.deepcopy(self.report)
        row = report["incoming"][0]
        report["incoming"] = [copy.deepcopy(row) for _ in range(100)]
        report["coverage"]["large_diagnostic"] = "x" * 4000
        instruction = task_instruction(GOAL, report, report_fingerprint(report))
        self.assertLessEqual(len(instruction.encode("utf-8")), MAX_CARD_BYTES)
        start = instruction.index('{"coverage":')
        end = instruction.index("\nЭто основа")
        facts = json.loads(instruction[start:end])
        self.assertEqual(len(facts["incoming"]) + facts["omitted_rows"]["incoming"], 100)
        self.assertGreater(facts["omitted_rows"]["incoming"], 0)
        self.assertTrue(facts["coverage"]["details_in_full_report"])
        self.assertFalse(facts["coverage"]["complete_coverage_claimed"])

    def test_oversized_report_is_refused(self):
        report = {"extra": "x" * (2 * 1024 * 1024)}
        with self.assertRaisesRegex(BridgeRefusal, "REPORT_TOO_LARGE"):
            report_fingerprint(report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
