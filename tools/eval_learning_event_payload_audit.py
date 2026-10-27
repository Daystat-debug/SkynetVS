"""Synthetic, standard-library checks for read-only event payload auditing.

Run: python -I -S -B -X utf8 tools/eval_learning_event_payload_audit.py
Only this evaluator's temporary data is inspected. No application entry point,
settings, model, real user history, builder or promotion module is imported.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-private-marker-92"


class LearningEventPayloadAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_event_payload_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        learning = self.root / "data/learning"
        learning.mkdir(parents=True)
        self.history_path = learning / "command_history.jsonl"
        self.memory_path = learning / "correction_memory.jsonl"
        self.memory_path.write_bytes(b"")
        specification = importlib.util.spec_from_file_location(
            "standalone_event_payload_audit_test", PROJECT_ROOT / "tools/audit_learning_data.py")
        assert specification is not None and specification.loader is not None
        self.audit = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(self.audit)

    @staticmethod
    def row(**changes):
        row = {"event_id": "fixture-event", "ts": "2026-01-01T12:00:00",
               "raw_text": "открой блокнот", "final_text": "открой блокнот",
               "mode": "text", "accepted": True, "immediate_label": "accepted",
               "missing_slots": [],
               "meta": {"intent": "OPEN_APP", "confidence": 0.9,
                        "slots": {"app": "notepad"}, "say": "готово", "_text": "открой блокнот"}}
        row.update(changes)
        return row

    def write(self, rows):
        self.history_path.write_bytes(b"".join(
            (json.dumps(row, ensure_ascii=True) + "\n").encode("ascii") for row in rows))

    def run_audit(self):
        before = {path: path.read_bytes() for path in (self.history_path, self.memory_path)
                  if path.exists()}
        report = self.audit.audit_learning_data(self.root)
        self.assertTrue(self.audit.validate_public_report(report), report)
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents)
        encoded = json.dumps(report, sort_keys=True)
        self.assertNotIn(SECRET, encoded)
        self.assertNotIn(str(self.root), encoded)
        self.assertFalse(report["scope"]["stable_event_identity_verified"])
        self.assertFalse(report["scope"]["historical_counts_verified"])
        self.assertFalse(report["scope"]["counts_recomputed"])
        return report

    def counts(self, report):
        item = report["inputs"]["command_history"]
        findings, observations = item["findings"], item["observations"]
        result = (findings["duplicate_event_id_rows"],
                  observations["replayed_event_id_rows"],
                  findings["conflicting_event_id_groups"], findings["conflicting_event_id_rows"])
        duplicate, replayed, groups, conflicting = result
        self.assertEqual(duplicate, replayed + conflicting - groups)
        self.assertLessEqual(2 * groups, conflicting)
        self.assertLessEqual(conflicting, observations["rows_with_event_id"])
        self.assertLessEqual(groups, observations["rows_with_event_id"] - duplicate)
        return result

    def test_v2_schema_is_explicit_and_v1_is_distinct(self):
        self.write([self.row()])
        report = self.run_audit()
        self.assertEqual(report["kind"], "SKYNETVS_LEARNING_DATA_AUDIT_V2")
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["limits"]["event_payload_bytes"], 64 * 1024 * 1024)
        old = copy.deepcopy(report)
        old.update(kind="SKYNETVS_LEARNING_DATA_AUDIT_V1", schema_version=1)
        self.assertFalse(self.audit.validate_public_report(old))
        self.assertEqual(report["exit_code"], 0)

    def test_legacy_and_invalid_ids_keep_existing_classification(self):
        legacy = self.row()
        del legacy["event_id"]
        self.write([legacy, self.row(event_id=None), self.row(event_id=0),
                    self.row(event_id="  "), self.row(event_id="new-valid-id")])
        report = self.run_audit()
        item = report["inputs"]["command_history"]
        self.assertEqual(item["observations"]["rows_without_event_id"], 4)
        self.assertEqual(item["observations"]["rows_with_event_id"], 1)
        self.assertEqual(item["findings"]["invalid_event_id_rows"], 3)
        self.assertEqual(self.counts(report), (0, 0, 0, 0))

    def test_identical_copies_are_replays_and_remain_findings(self):
        row = self.row(event_id=SECRET)
        self.write([row, row, row])
        report = self.run_audit()
        self.assertEqual(self.counts(report), (2, 2, 0, 0))
        self.assertEqual(report["status"], "FINDINGS_IN_CHECKED_STRUCTURE")
        self.assertEqual(report["exit_code"], 1)

    def test_conflict_reclassifies_whole_group_in_every_order(self):
        original, changed = self.row(), self.row(raw_text="изменённая строка")
        for changed_at in range(4):
            with self.subTest(changed_at=changed_at):
                rows = [copy.deepcopy(original) for _ in range(4)]
                rows[changed_at] = changed
                self.write(rows)
                report = self.run_audit()
                self.assertEqual(self.counts(report), (3, 0, 1, 4))
                self.assertEqual(report["exit_code"], 1)

    def test_multiple_groups_keep_disjoint_replay_conflict_and_legacy_counts(self):
        original, changed = self.row(event_id="conflict"), self.row(event_id="conflict", accepted=False)
        replay = self.row(event_id="replay")
        legacy = self.row()
        del legacy["event_id"]
        self.write([original, replay, original, self.row(event_id="unique"), replay,
                    changed, replay, original, legacy])
        report = self.run_audit()
        self.assertEqual(self.counts(report), (5, 2, 1, 4))
        item = report["inputs"]["command_history"]
        self.assertEqual(item["object_rows"], 9)
        self.assertEqual(item["observations"]["rows_with_event_id"], 8)

    def test_all_known_and_unknown_payload_fields_participate(self):
        original = self.row()
        mutations = [
            lambda row: row.update(raw_text="other"),
            lambda row: row.update(final_text="other"),
            lambda row: row.update(ts="2026-01-01T12:00:01"),
            lambda row: row.update(mode="voice"),
            lambda row: row.update(accepted=False),
            lambda row: row.update(immediate_label="other"),
            lambda row: row.update(missing_slots=["app"]),
            lambda row: row["meta"].update(intent="CLOSE_APP"),
            lambda row: row["meta"].update(confidence=0.8),
            lambda row: row["meta"]["slots"].update(app="editor"),
            lambda row: row["meta"].update(say="other"),
            lambda row: row["meta"].update(_text="other"),
            lambda row: row["meta"].update(future={"nested": [SECRET]}),
            lambda row: row.update(future={"nested": [SECRET]}),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(field_case=index):
                changed = copy.deepcopy(original)
                mutate(changed)
                self.write([original, changed])
                self.assertEqual(self.counts(self.run_audit()), (1, 0, 1, 2))

    def test_key_order_formatting_and_decoded_escapes_are_equivalent(self):
        first = self.row(event_id=SECRET, future={"a": 1, "b": {"x": "ёж", "y": 2}})
        second = dict(reversed(list(first.items())))
        second["meta"] = dict(reversed(list(first["meta"].items())))
        second["future"] = {"b": {"y": 2, "x": "ёж"}, "a": 1}
        self.history_path.write_bytes(
            (json.dumps(first, ensure_ascii=False) + "\r\n").encode("utf-8")
            + (json.dumps(second, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii"))
        self.assertEqual(self.counts(self.run_audit()), (1, 1, 0, 0))

    def test_distinct_ids_are_not_trimmed_casefolded_or_inferred(self):
        self.write([self.row(event_id=value) for value in ("ABC", "abc", " abc", "abc ", "legacy-id")])
        report = self.run_audit()
        self.assertEqual(self.counts(report), (0, 0, 0, 0))
        self.assertEqual(report["inputs"]["command_history"]["observations"]["rows_with_event_id"], 5)
        self.assertEqual(report["exit_code"], 0)

    def test_number_types_and_signed_float_zero_are_conservative(self):
        for left, right in ((True, 1), (1, 1.0), (0.0, -0.0)):
            with self.subTest(types=(type(left).__name__, type(right).__name__)):
                self.write([self.row(future=left), self.row(future=right)])
                self.assertEqual(self.counts(self.run_audit()), (1, 0, 1, 2))
        raw = json.dumps(self.row(future=1.0))
        self.history_path.write_text(raw + "\n" + raw.replace('"future": 1.0', '"future": 1e0') + "\n",
                                     encoding="utf-8")
        self.assertEqual(self.counts(self.run_audit()), (1, 1, 0, 0))

    def test_array_order_and_string_content_remain_significant(self):
        for left, right in (([1, 2], [2, 1]), ("word", " word"), ("A", "a"),
                            ("ё", "е\u0308")):
            with self.subTest(value_types=(type(left).__name__, type(right).__name__)):
                self.write([self.row(future=left), self.row(future=right)])
                self.assertEqual(self.counts(self.run_audit()), (1, 0, 1, 2))

    def test_structurally_invalid_objects_are_not_legitimized_by_replay(self):
        invalid = self.row(accepted="yes", meta=[], missing_slots=SECRET)
        self.write([invalid, invalid])
        report = self.run_audit()
        self.assertEqual(self.counts(report), (1, 1, 0, 0))
        findings = report["inputs"]["command_history"]["findings"]
        self.assertEqual(findings["invalid_accepted_rows"], 2)
        self.assertEqual(findings["invalid_meta_rows"], 2)
        self.assertEqual(findings["invalid_missing_slots_rows"], 2)
        self.assertEqual(report["exit_code"], 1)

    def test_strict_parse_failures_are_not_identified_objects(self):
        row = self.row(event_id=SECRET)
        encoded = json.dumps(row).encode("ascii")
        duplicate_key = encoded[:-1] + b', "event_id": "other"}'
        self.history_path.write_bytes(encoded + b"\n" + duplicate_key + b"\n"
                                      + b'{"event_id":"x","n":NaN}\n{broken\n[]\n\xff\n')
        report = self.run_audit()
        item = report["inputs"]["command_history"]
        self.assertEqual(item["object_rows"], 1)
        self.assertEqual(item["observations"]["rows_with_event_id"], 1)
        self.assertEqual(self.counts(report), (0, 0, 0, 0))
        for key in ("duplicate_field_lines", "non_finite_number_lines", "invalid_json_lines",
                    "non_object_rows", "invalid_utf8_lines"):
            self.assertEqual(item["findings"][key], 1)

    def test_invalid_unicode_is_reported_without_encoding_failure_or_disclosure(self):
        row = self.row(event_id=SECRET + "\ud800", future={"value": "\udfff"})
        self.write([row, row, self.row(event_id=row["event_id"], future={"value": "\udffe"})])
        report = self.run_audit()
        self.assertEqual(self.counts(report), (2, 0, 1, 3))
        self.assertEqual(report["inputs"]["command_history"]["findings"]["invalid_unicode_lines"], 3)
        self.assertEqual(report["exit_code"], 1)

    def test_retained_payload_cap_stops_before_half_counting_object(self):
        row = self.row(event_id=SECRET)
        size = len(json.dumps(row, sort_keys=True, ensure_ascii=True, allow_nan=False,
                              separators=(",", ":")).encode("ascii"))
        self.write([row, row, self.row(event_id="next-identity"), row])
        with mock.patch.dict(self.audit.LIMITS, event_payload_bytes=size):
            report = self.run_audit()
        item = report["inputs"]["command_history"]
        self.assertEqual(item["state"], "LIMIT_REACHED")
        self.assertFalse(item["complete"])
        self.assertEqual(item["lines_read"], 3)
        self.assertEqual(item["object_rows"], 2)
        self.assertEqual(item["observations"]["rows_with_event_id"], 2)
        self.assertEqual(self.counts(report), (1, 1, 0, 0))
        self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
        self.assertEqual(report["exit_code"], 2)
        self.assertGreater(item["bytes_read"], len(self.history_path.read_bytes().splitlines(keepends=True)[0]) * 2)

    def test_partial_line_limit_does_not_claim_complete_group_consistency(self):
        row = self.row()
        self.write([row, row, self.row(raw_text="later-conflict")])
        with mock.patch.dict(self.audit.LIMITS, lines_per_file=2):
            report = self.run_audit()
        self.assertEqual(report["inputs"]["command_history"]["state"], "LIMIT_REACHED")
        self.assertEqual(self.counts(report), (1, 1, 0, 0))
        self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
        self.assertEqual(report["exit_code"], 2)

    def test_concurrent_metadata_change_keeps_result_incomplete(self):
        self.write([self.row(), self.row(raw_text="other")])
        original = self.audit._history_row
        changed = False

        def touch_after_row(*args, **kwargs):
            nonlocal changed
            original(*args, **kwargs)
            if not changed:
                info = self.history_path.stat()
                os.utime(self.history_path, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
                changed = True

        with mock.patch.object(self.audit, "_history_row", side_effect=touch_after_row):
            report = self.run_audit()
        self.assertEqual(self.counts(report), (1, 0, 1, 2))
        self.assertEqual(report["inputs"]["command_history"]["state"], "CHANGED_DURING_READ")
        self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
        self.assertEqual(report["exit_code"], 2)

    def test_closed_validator_rejects_impossible_identity_counters(self):
        self.write([self.row(), self.row()])
        report = self.run_audit()
        mutations = [
            lambda value: value["inputs"]["command_history"]["findings"].update(conflicting_event_id_groups=True),
            lambda value: value["inputs"]["command_history"]["findings"].update(conflicting_event_id_rows=-1),
            lambda value: value["inputs"]["command_history"]["observations"].update(replayed_event_id_rows=False),
            lambda value: value["inputs"]["command_history"]["observations"].update(replayed_event_id_rows=2),
            lambda value: value["inputs"]["command_history"]["findings"].update(conflicting_event_id_groups=1),
            lambda value: value["inputs"]["command_history"]["findings"].update(conflicting_event_id_rows=2),
            lambda value: value["inputs"]["command_history"]["observations"].update(private=SECRET),
            lambda value: value.update(status="NO_ISSUES_IN_CHECKED_STRUCTURE", exit_code=0),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                candidate = copy.deepcopy(report)
                mutate(candidate)
                self.assertFalse(self.audit.validate_public_report(candidate))
        self.write([self.row(), self.row(raw_text="other"), self.row(raw_text="other"),
                    self.row(event_id="another")])
        impossible = self.run_audit()
        item = impossible["inputs"]["command_history"]
        item["findings"].update(duplicate_event_id_rows=3)
        item["observations"].update(replayed_event_id_rows=1)
        self.assertFalse(self.audit.validate_public_report(impossible))

    def test_cli_reports_only_aggregate_schema_and_separate_exit_status(self):
        script = PROJECT_ROOT / "tools/audit_learning_data.py"
        for rows, expected in (([self.row(event_id=SECRET)], 0),
                               ([self.row(event_id=SECRET)] * 2, 1),
                               ([self.row(event_id=SECRET), self.row(event_id=SECRET, future=SECRET)], 1)):
            with self.subTest(expected=expected, count=len(rows)):
                self.write(rows)
                result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8",
                                         str(script), "--repo", str(self.root)],
                                        cwd=self.root, capture_output=True, text=True,
                                        encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, expected)
                self.assertEqual(result.stderr, "")
                self.assertNotIn(SECRET, result.stdout)
                self.assertNotIn(str(self.root), result.stdout)
                report = json.loads(result.stdout)
                self.assertTrue(self.audit.validate_public_report(report))
                self.assertEqual(report["exit_code"], expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
