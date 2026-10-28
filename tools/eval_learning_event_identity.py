"""New command-history identity checks; only owned synthetic files are used."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest import mock
from uuid import UUID, RFC_4122


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
FIXED_TIME = datetime(2026, 1, 1, 12, 0, 0)


class LearningEventIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_learning_identity_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.learning = self.root / "data/learning"
        self.history = self.learning / "command_history.jsonl"
        # Canonical isolated packages provide the writer's runtime dependency
        # without importing either real package initializer or the application.
        names = ("modules", "modules.learning", "modules.learning.correction_evidence_runtime")
        absent = object()
        previous = {name: sys.modules.get(name, absent) for name in names}
        def restore():
            for name, value in previous.items():
                if value is absent:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
        self.addCleanup(restore)
        parent = ModuleType("modules")
        parent.__path__ = []
        package = ModuleType("modules.learning")
        package.__path__ = []
        parent.learning = package
        sys.modules["modules"] = parent
        sys.modules["modules.learning"] = package
        runtime = self.load("runtime", "modules/learning/correction_evidence_runtime.py")
        sys.modules[names[-1]] = runtime
        package.correction_evidence_runtime = runtime
        self.writer = self.load("writer", "modules/learning/learning_memory.py")
        self.memory = self.writer.LearningMemory(str(self.learning))

    @staticmethod
    def load(name, relative):
        specification = importlib.util.spec_from_file_location(
            "standalone_identity_" + name, PROJECT_ROOT / relative)
        assert specification is not None and specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module

    @staticmethod
    def arguments(**changes):
        values = {
            "raw_text": "открой блокнот", "final_text": "открой блокнот",
            "meta": {"intent": "OPEN_APP", "confidence": 0.9,
                     "slots": {"app": "notepad"}, "say": "готово", "_text": "открой блокнот"},
            "mode": "text", "accepted": True, "immediate_label": "immediate", "missing_slots": [],
        }
        values.update(changes)
        return values

    @staticmethod
    def legacy_row():
        values = LearningEventIdentityTests.arguments()
        return {"ts": "2025-12-31T12:00:00", **values}

    def rows(self, path=None):
        return [json.loads(line) for line in (path or self.history).read_text(encoding="utf-8").splitlines() if line]

    def record(self, *, memory=None, **changes):
        with mock.patch.object(self.writer, "datetime") as clock:
            clock.now.return_value = FIXED_TIME
            return (memory or self.memory).log_command(**self.arguments(**changes))

    def assert_uuid4(self, value):
        self.assertIsInstance(value, str)
        parsed = UUID(value)
        self.assertEqual(parsed.version, 4)
        self.assertEqual(parsed.variant, RFC_4122)
        self.assertEqual(value, parsed.hex)

    def prepare_auditable_memory(self):
        self.learning.mkdir(parents=True, exist_ok=True)
        row = {
            "key": "запусти редактор | открой блокнот | OPEN_APP", "seen_count": 1,
            "failed_text": "запусти редактор", "corrected_text": "открой блокнот",
            "corrected_intent": "OPEN_APP", "corrected_confidence": 0.9,
            "corrected_slots": {"app": "notepad"}, "sources": ["legacy_source"],
            "created_ts": "2025-12-31T12:00:00", "last_seen_ts": "2025-12-31T12:00:01", "status": "candidate",
        }
        (self.learning / "correction_memory.jsonl").write_text(
            json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    def audit_report(self):
        auditor = self.load("audit", "tools/audit_learning_data.py")
        report = auditor.audit_learning_data(self.root)
        self.assertTrue(auditor.validate_public_report(report))
        self.assertFalse(report["scope"]["stable_event_identity_verified"])
        self.assertFalse(report["scope"]["historical_counts_verified"])
        self.assertNotIn(str(self.root), json.dumps(report))
        return report

    def test_accepted_and_rejected_observations_get_uuid4_ids(self):
        self.record()
        self.record(accepted=False, meta={"intent": None, "confidence": 0.1, "slots": {}})
        rows = self.rows()
        self.assertEqual([row["accepted"] for row in rows], [True, False])
        for row in rows:
            self.assert_uuid4(row["event_id"])

    def test_identical_calls_at_same_time_are_distinct_across_instances(self):
        self.record()
        self.record()
        self.record(memory=self.writer.LearningMemory(str(self.learning)))
        rows = self.rows()
        self.assertEqual(len({row["event_id"] for row in rows}), 3)
        self.assertEqual(len({row["ts"] for row in rows}), 1)
        self.assertEqual(len({row["raw_text"] for row in rows}), 1)
        for row in rows:
            self.assert_uuid4(row["event_id"])

    def test_payload_timestamp_return_and_caller_objects_are_preserved(self):
        arguments = self.arguments()
        arguments["meta"]["event_id"] = "caller-value-must-not-become-row-identity"
        arguments["meta"]["confidence"] = "0.75"
        arguments["missing_slots"] = ["app"]
        before = copy.deepcopy(arguments)
        with mock.patch.object(self.writer, "datetime") as clock:
            clock.now.return_value = FIXED_TIME.replace(microsecond=123456)
            result = self.memory.log_command(**arguments)
        self.assertIsNone(result)
        self.assertEqual(arguments, before)
        row = self.rows()[0]
        identity = row.pop("event_id")
        self.assert_uuid4(identity)
        self.assertNotEqual(identity, arguments["meta"]["event_id"])
        expected = copy.deepcopy(arguments)
        expected["meta"].pop("event_id")
        expected["meta"]["confidence"] = 0.75
        self.assertEqual(row, {"ts": "2026-01-01T12:00:00", **expected})
        self.assertIsNone(datetime.fromisoformat(row["ts"]).tzinfo)

    def test_legacy_utf8_crlf_bytes_are_preserved_without_backfill_or_read(self):
        self.learning.mkdir(parents=True)
        legacy = (json.dumps(self.legacy_row(), ensure_ascii=False) + "\r\n").encode("utf-8")
        self.history.write_bytes(legacy)
        original_open = Path.open

        def append_only(path, mode="r", *args, **kwargs):
            if path == self.history and mode != "a":
                raise AssertionError("The writer must not read or rewrite existing history")
            return original_open(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", append_only):
            self.record()
        current = self.history.read_bytes()
        self.assertEqual(current[:len(legacy)], legacy)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertNotIn("event_id", rows[0])
        self.assertEqual(rows[0], self.legacy_row())
        self.assert_uuid4(rows[1]["event_id"])

    def test_command_learning_bridge_records_one_history_identity(self):
        bridge = self.load("bridge", "modules/command_learning.py")
        arguments = self.arguments(missing_slots=["app"])
        with mock.patch.object(self.writer, "datetime") as clock:
            clock.now.return_value = FIXED_TIME
            bridge.log_command_observation(learning_memory=self.memory, **arguments)
        rows = self.rows()
        candidates = self.rows(self.learning / "resolver_candidates.jsonl")
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(candidates), 1)
        self.assert_uuid4(rows[0]["event_id"])
        self.assertNotIn("event_id", candidates[0])
        self.assertEqual(candidates[0]["reason"], "missing_required_slots")

    def test_other_learning_logs_do_not_allocate_or_add_identity(self):
        arguments = self.arguments()
        shared = {name: arguments[name] for name in ("raw_text", "final_text", "meta", "mode")}
        with mock.patch.object(self.writer, "uuid4", side_effect=AssertionError("Only command history allocates identity")):
            self.memory.log_nlu_hard_case(**shared, reason="not_accepted")
            self.memory.log_action_failure(**shared, error=RuntimeError("synthetic action failure"))
            self.memory.log_resolver_candidate(**shared, missing_slots=["app"], reason="missing_required_slots")
        common = {"ts", "raw_text", "final_text", "meta", "mode"}
        for name, extra in (
            ("nlu_hard_cases.jsonl", {"reason"}),
            ("action_failures.jsonl", {"error_type", "error"}),
            ("resolver_candidates.jsonl", {"missing_slots", "reason"}),
        ):
            rows = self.rows(self.learning / name)
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]), common | extra)
        self.assertFalse(self.history.exists())

    def test_uuid_failure_propagates_before_history_append(self):
        self.learning.mkdir(parents=True)
        original = (json.dumps(self.legacy_row(), ensure_ascii=False) + "\n").encode("utf-8")
        self.history.write_bytes(original)
        with mock.patch.object(self.writer, "uuid4", side_effect=RuntimeError("synthetic entropy failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic entropy failure"):
                self.record()
        self.assertEqual(self.history.read_bytes(), original)
        self.assertEqual(sorted(path.name for path in self.learning.iterdir()), ["command_history.jsonl"])

    def test_auditor_accepts_mixed_legacy_and_new_rows_without_provenance_claim(self):
        self.prepare_auditable_memory()
        self.history.write_text(json.dumps(self.legacy_row(), ensure_ascii=False) + "\n", encoding="utf-8")
        self.record()
        report = self.audit_report()
        item = report["inputs"]["command_history"]
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertTrue(item["complete"])
        self.assertEqual(item["observations"]["rows_without_event_id"], 1)
        self.assertEqual(item["observations"]["rows_with_event_id"], 1)
        self.assertFalse(any(item["findings"].values()))

    def test_auditor_flags_copied_identity_without_publishing_values(self):
        self.prepare_auditable_memory()
        self.record()
        original = self.history.read_bytes()
        event_id = self.rows()[0]["event_id"]
        with self.history.open("ab") as stream:
            stream.write(original)
        report = self.audit_report()
        item = report["inputs"]["command_history"]
        self.assertEqual(report["status"], "FINDINGS_IN_CHECKED_STRUCTURE")
        self.assertEqual(item["observations"]["rows_with_event_id"], 2)
        self.assertEqual(item["findings"]["duplicate_event_id_rows"], 1)
        self.assertNotIn(event_id, json.dumps(report))
        self.assertNotIn("открой блокнот", json.dumps(report, ensure_ascii=False))

    def test_analyzer_group_counts_remain_compatible_with_identity(self):
        analyzer_module = self.load("analyzer", "modules/learning/feedback_analyzer.py")
        moments = [FIXED_TIME + timedelta(seconds=seconds) for seconds in (0, 2, 120, 122)]
        with mock.patch.object(self.writer, "datetime") as clock:
            clock.now.side_effect = moments
            for _ in range(2):
                self.memory.log_command(**self.arguments(
                    raw_text="нужен редактор", final_text="нужен редактор", accepted=False,
                    meta={"intent": None, "confidence": 0.1, "slots": {}}))
                self.memory.log_command(**self.arguments())
        rows = self.rows()
        self.assertEqual(len({row["event_id"] for row in rows}), 4)
        legacy = [{key: value for key, value in row.items() if key != "event_id"} for row in rows]
        analyzer = analyzer_module.FeedbackAnalyzer(str(self.learning))
        identified_pairs = analyzer.analyze(correction_limit=None)["correction_pairs"]
        legacy_pairs = analyzer._find_correction_pairs(legacy, limit=None)
        projection = lambda pairs: [(row["failed_text"], row["corrected_text"], row["corrected_intent"], row["count"]) for row in pairs]
        self.assertEqual(projection(identified_pairs), projection(legacy_pairs))
        self.assertEqual(projection(identified_pairs), [("нужен редактор", "открой блокнот", "OPEN_APP", 2)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
