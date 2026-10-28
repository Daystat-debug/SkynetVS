"""Named synthetic checks for replaying ledger totals into correction memory.

Run: python -I -S -B -X utf8 tools/eval_correction_evidence_projection.py
Only standalone learning leaves are loaded into an isolated canonical package.
All histories, databases, correction memories and fault fixtures are temporary.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-private-projection-marker-96"
FAILED = "запусти редактор"
CORRECTED = "открой блокнот"
KEY = FAILED + " | " + CORRECTED + " | OPEN_APP"
DEFAULT_EPOCH = object()


class CorrectionEvidenceProjectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_evidence_projection_")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.repo = self.base / "repo with spaces # unicode-я"
        self.learning = self.repo / "data" / "learning"
        self.learning.mkdir(parents=True)
        self.history = self.learning / "command_history.jsonl"
        self.history.write_bytes(b"")
        self.database = self.learning / "correction_evidence.sqlite3"
        self.memory_path = self.learning / "correction_memory.jsonl"
        children = ("correction_pair_evidence", "learning_history_snapshot", "correction_evidence_ledger",
                    "correction_memory", "correction_evidence_projection")
        names = ("modules", "modules.learning", *("modules.learning." + name for name in children))
        absent = object()
        previous = {name: sys.modules.get(name, absent) for name in names}

        def restore_modules():
            for name, value in previous.items():
                if value is absent:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value

        self.addCleanup(restore_modules)
        parent, package = ModuleType("modules"), ModuleType("modules.learning")
        parent.__path__, package.__path__ = [], []
        parent.learning = package
        sys.modules["modules"], sys.modules["modules.learning"] = parent, package
        for name in children:
            full_name = "modules.learning." + name
            spec = importlib.util.spec_from_file_location(full_name, ROOT / "modules" / "learning" / (name + ".py"))
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[full_name] = module
            setattr(package, name, module)
            spec.loader.exec_module(module)
        self.ledger = package.correction_evidence_ledger
        self.memory_module = package.correction_memory
        self.projection = package.correction_evidence_projection
        self.epoch = None

    @staticmethod
    def encoded(rows):
        return b"".join(json.dumps(row, ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
                        for row in rows)

    @staticmethod
    def canonical(row):
        return json.dumps(row, ensure_ascii=True, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("ascii")

    def put_history(self, rows):
        self.history.write_bytes(self.encoded(rows))

    def put_memory(self, rows):
        self.memory_path.write_bytes(self.encoded(rows))

    def rows(self):
        return [json.loads(line) for line in self.memory_path.read_bytes().splitlines() if line.strip()]

    def memory_state(self):
        if not self.memory_path.exists():
            return None
        return self.memory_path.read_bytes(), self.memory_path.stat().st_mtime_ns

    def pair(self, prefix="", *, failed=FAILED, corrected=CORRECTED, confidence=0.9, slots=None):
        slots = {"app": "notepad", "private": SECRET} if slots is None else slots
        return [
            {"event_id": prefix + "failed", "evidence_epoch": self.epoch,
             "ts": "2026-01-01T12:00:00", "raw_text": failed, "final_text": failed,
             "accepted": False, "missing_slots": [],
             "meta": {"intent": None, "confidence": 0.1, "slots": {}}},
            {"event_id": prefix + "corrected", "evidence_epoch": self.epoch,
             "ts": "2026-01-01T12:00:01", "raw_text": corrected, "final_text": corrected,
             "accepted": True, "missing_slots": [],
             "meta": {"intent": "OPEN_APP", "confidence": confidence, "slots": slots}},
        ]

    def initialize(self, rows=None):
        if rows is not None:
            self.put_history(rows)
        result = self.ledger.initialize_correction_evidence_ledger(self.repo)
        self.assertEqual(result["status"], "INITIALIZED", result)
        self.epoch = result["epoch"]
        return result

    def accept(self, *pairs):
        self.put_history([row for pair in pairs for row in pair])
        result = self.ledger.sync_correction_evidence_ledger(self.repo)
        self.assertIn(result["status"], ("APPLIED", "UNCHANGED"), result)
        return result

    def totals(self):
        result = self.ledger.read_correction_evidence_totals(self.repo)
        self.assertEqual(result["kind"], "SKYNETVS_CORRECTION_EVIDENCE_TOTALS_V1")
        self.assertIn(result["status"], ("READY", "REFUSED"))
        return result

    def project(self, *, epoch=DEFAULT_EPOCH):
        result = self.projection.project_correction_evidence(
            self.repo, expected_epoch=self.epoch if epoch is DEFAULT_EPOCH else epoch)
        self.assertEqual(result["kind"], "SKYNETVS_CORRECTION_EVIDENCE_PROJECTION_V1")
        self.assertEqual(set(result), {"kind", "status", "reason", "input_reason", "epoch", "stats",
                                       "pair_count", "memory_written", "scope"})
        self.assertIn(result["status"], ("APPLIED", "UNCHANGED", "REFUSED"))
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(str(self.repo), json.dumps(result))
        if result["status"] != "REFUSED":
            self.assertEqual(result["epoch"], self.epoch)
            self.assertEqual(set(result["stats"]),
                             {"processed", "created", "increased", "unchanged", "new_evidence", "written"})
            for key, value in result["stats"].items():
                self.assertIs(type(value), bool if key == "written" else int)
        return result

    def refused_without_memory_change(self, before, *, epoch=DEFAULT_EPOCH, reason=None):
        result = self.project(epoch=epoch)
        self.assertEqual(result["status"], "REFUSED", result)
        self.assertIsNone(result["stats"])
        if reason is not None:
            self.assertEqual(result["reason"], reason)
        self.assertEqual(self.memory_state(), before)
        return result

    def legacy(self, *, key=KEY, count=99, status="approved"):
        return {"key": key, "failed_text": FAILED, "corrected_text": CORRECTED,
                "corrected_intent": "OPEN_APP", "corrected_confidence": 0.8,
                "corrected_slots": {"old": "kept"}, "seen_count": count,
                "created_ts": "2020-01-02T03:04:05", "last_seen_ts": "2020-01-03T03:04:05",
                "sources": ["old_source", "feedback_analyzer_v2"], "status": status,
                "cumulative_evidence": {"feedback_analyzer_v2":
                    {"version": 1, "observed_count": 7, "legacy_baseline": True}},
                "unknown": {"nested": [SECRET, True, None]}}

    def connect(self):
        return sqlite3.connect(self.database.as_uri() + "?mode=rw", uri=True, timeout=0)

    def mutate(self, statement, parameters=()):
        connection = self.connect()
        try:
            with connection:
                connection.execute(statement, parameters)
        finally:
            connection.close()

    def test_empty_ledger_totals_and_projection_create_no_memory(self):
        self.initialize()
        result = self.totals()
        self.assertEqual(result["status"], "READY", result)
        self.assertEqual(result["epoch"], self.epoch)
        self.assertEqual(result["pair_count"], 0)
        self.assertEqual(result["candidates"], [])
        projected = self.project()
        self.assertEqual(projected["status"], "UNCHANGED", projected)
        self.assertEqual(projected["stats"]["new_evidence"], 0)
        self.assertFalse(self.memory_path.exists())

    def test_missing_ledger_is_refused_without_creating_storage(self):
        self.epoch = "a" * 32
        totals = self.totals()
        self.assertEqual(totals["status"], "REFUSED", totals)
        self.refused_without_memory_change(None)
        self.assertFalse(self.database.exists())
        self.assertEqual(sorted(path.name for path in self.learning.iterdir()), ["command_history.jsonl"])

    def test_reader_uses_persisted_pairs_after_history_is_removed(self):
        self.initialize()
        self.accept(self.pair())
        self.history.unlink()
        totals = self.totals()
        self.assertEqual(totals["status"], "READY", totals)
        self.assertEqual(totals["pair_count"], 1)
        self.assertEqual(len(totals["candidates"]), 1)
        self.assertEqual(totals["candidates"][0]["count"], 1)
        result = self.project()
        self.assertEqual(result["status"], "APPLIED", result)
        self.assertEqual(self.rows()[0]["seen_count"], 1)

    def test_reader_does_not_sync_new_unaccepted_history(self):
        self.initialize()
        self.accept(self.pair())
        self.put_history(self.pair("not-synced-"))
        totals = self.totals()
        self.assertEqual(totals["pair_count"], 1)
        self.project()
        self.assertEqual(self.rows()[0]["seen_count"], 1)
        self.accept(self.pair("not-synced-"))
        self.project()
        self.assertEqual(self.rows()[0]["seen_count"], 2)

    def test_normalized_variants_are_summed_without_replacing_other_groups(self):
        self.initialize()
        self.accept(self.pair("a-"), self.pair("b-", failed="  ЗАПУСТИ   РЕДАКТОР  ",
                                               corrected=" ОТКРОЙ  БЛОКНОТ "),
                    self.pair("other-", failed="другой редактор"))
        totals = self.totals()
        self.assertEqual(totals["status"], "READY", totals)
        self.assertEqual(totals["pair_count"], 3)
        self.assertEqual(sorted(candidate["count"] for candidate in totals["candidates"]), [1, 2])
        self.project()
        rows = {row["key"]: row for row in self.rows()}
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[KEY]["seen_count"], 2)
        self.assertEqual(rows["другой редактор | " + CORRECTED + " | OPEN_APP"]["seen_count"], 1)

    def test_totals_are_stable_across_reopening_and_do_not_write_ledger(self):
        self.initialize()
        self.accept(self.pair())
        before = self.database.read_bytes(), self.database.stat().st_mtime_ns
        first, second = self.totals(), self.totals()
        self.assertEqual(first, second)
        self.assertEqual((self.database.read_bytes(), self.database.stat().st_mtime_ns), before)

    def test_real_sqlite_exclusive_lock_refuses_then_retry_reads_totals(self):
        self.initialize()
        self.accept(self.pair())
        connection = self.connect()
        try:
            connection.execute("BEGIN EXCLUSIVE")
            result = self.totals()
            self.assertEqual(result["status"], "REFUSED", result)
            self.refused_without_memory_change(None)
        finally:
            connection.rollback()
            connection.close()
        self.assertEqual(self.totals()["status"], "READY")
        self.assertEqual(self.project()["status"], "APPLIED")

    def test_corrupt_database_refuses_without_changing_memory(self):
        self.database.write_bytes(b"synthetic not a sqlite database " + SECRET.encode("ascii"))
        self.epoch = "a" * 32
        self.put_memory([self.legacy()])
        before = self.memory_state()
        self.assertEqual(self.totals()["status"], "REFUSED")
        self.refused_without_memory_change(before)

    def test_invalid_stored_pair_json_refuses_before_memory_projection(self):
        self.initialize()
        self.accept(self.pair())
        self.put_memory([self.legacy()])
        before = self.memory_state()
        self.mutate("UPDATE pairs SET evidence = ?", (b'{"broken":',))
        self.assertEqual(self.totals()["status"], "REFUSED")
        self.refused_without_memory_change(before)

    def test_pair_identity_mismatch_is_not_credited(self):
        self.initialize()
        self.accept(self.pair())
        connection = self.connect()
        try:
            payload = json.loads(connection.execute("SELECT evidence FROM pairs").fetchone()[0])
        finally:
            connection.close()
        payload["pair_identity"]["corrected_event_id"] = "different-id"
        self.mutate("UPDATE pairs SET evidence = ?", (self.canonical(payload),))
        self.assertEqual(self.totals()["status"], "REFUSED")
        self.refused_without_memory_change(None)

    def test_first_projection_credits_existing_row_and_keeps_legacy_checkpoint(self):
        self.initialize()
        self.accept(self.pair())
        original = self.legacy()
        self.put_memory([original])
        result = self.project()
        self.assertEqual(result["status"], "APPLIED", result)
        self.assertEqual(result["stats"]["new_evidence"], 1)
        self.assertEqual(result["stats"]["increased"], 1)
        row = self.rows()[0]
        self.assertEqual(row["seen_count"], 100)
        self.assertEqual(row["cumulative_evidence"], original["cumulative_evidence"])
        self.assertEqual(row["event_evidence"], {"version": 1, "epoch": self.epoch, "observed_count": 1})
        self.assertEqual(row["sources"], [*original["sources"], "correction_evidence_v1"])
        self.assertEqual(row["corrected_slots"]["old"], "kept")

    def test_new_candidate_receives_total_checkpoint_and_candidate_status(self):
        self.initialize()
        self.accept(self.pair("first-"), self.pair("second-"))
        result = self.project()
        self.assertEqual(result["stats"]["created"], 1)
        self.assertEqual(result["stats"]["new_evidence"], 2)
        row = self.rows()[0]
        self.assertEqual(row["key"], KEY)
        self.assertEqual(row["seen_count"], 2)
        self.assertEqual(row["status"], "candidate")
        self.assertEqual(row["event_evidence"], {"version": 1, "epoch": self.epoch, "observed_count": 2})
        self.assertEqual(row["corrected_intent"], "OPEN_APP")
        self.assertEqual(row["corrected_slots"]["app"], "notepad")

    def test_replay_preserves_memory_bytes_timestamp_and_business_metadata(self):
        self.initialize()
        self.accept(self.pair())
        self.put_memory([self.legacy()])
        self.project()
        before = self.memory_state()
        with mock.patch.object(self.memory_module.CorrectionMemory, "_write_snapshot",
                               side_effect=AssertionError("No write on replay")):
            for _ in range(3):
                result = self.project()
                self.assertEqual(result["status"], "UNCHANGED", result)
                self.assertEqual(result["stats"]["new_evidence"], 0)
                self.assertFalse(result["stats"]["written"])
        self.assertEqual(self.memory_state(), before)

    def test_later_growth_adds_only_difference_from_persisted_total(self):
        self.initialize()
        self.accept(self.pair("one-"), self.pair("two-"))
        self.put_memory([self.legacy(count=20)])
        self.project()
        self.assertEqual(self.rows()[0]["seen_count"], 22)
        self.accept(self.pair("three-"))
        result = self.project()
        self.assertEqual(result["stats"]["new_evidence"], 1)
        self.assertEqual(self.rows()[0]["seen_count"], 23)
        self.assertEqual(self.rows()[0]["event_evidence"]["observed_count"], 3)

    def test_status_unknown_fields_and_unrelated_row_order_are_preserved(self):
        self.initialize()
        self.accept(self.pair())
        first = self.legacy(status="rejected")
        unrelated = self.legacy(key="unrelated | corrected | OTHER", count=7, status="reviewed")
        self.put_memory([unrelated, first])
        self.project()
        rows = self.rows()
        self.assertEqual(rows[0], unrelated)
        for name in ("status", "unknown", "created_ts", "cumulative_evidence"):
            self.assertEqual(rows[1][name], first[name])

    def test_no_pair_evidence_leaves_existing_memory_exactly_unchanged(self):
        self.initialize()
        self.put_memory([self.legacy()])
        before = self.memory_state()
        result = self.project()
        self.assertEqual(result["status"], "UNCHANGED", result)
        self.assertEqual(self.memory_state(), before)
        self.assertNotIn("event_evidence", self.rows()[0])

    def test_baseline_history_never_becomes_projection_credit(self):
        old = self.pair("old-")
        for row in old:
            row.pop("evidence_epoch")
        self.initialize(old)
        self.put_memory([self.legacy()])
        before = self.memory_state()
        self.assertEqual(self.totals()["pair_count"], 0)
        self.assertEqual(self.project()["status"], "UNCHANGED")
        self.assertEqual(self.memory_state(), before)
        self.accept(self.pair("new-"))
        self.project()
        self.assertEqual(self.rows()[0]["seen_count"], 100)

    def test_expected_epoch_mismatch_refuses_before_memory_changes(self):
        self.initialize()
        self.accept(self.pair())
        self.put_memory([self.legacy()])
        self.refused_without_memory_change(self.memory_state(), epoch="f" * 32 if self.epoch != "f" * 32 else "a" * 32,
                                           reason="EPOCH_MISMATCH")

    def test_invalid_expected_epoch_values_are_refused(self):
        self.initialize()
        self.accept(self.pair())
        for value in (None, "", "a" * 31, "A" * 32, "a" * 33, True, 96, [], {}):
            with self.subTest(value_type=type(value).__name__):
                self.refused_without_memory_change(None, epoch=value, reason="INVALID_EPOCH")

    def test_existing_checkpoint_for_other_epoch_is_not_silently_rebased(self):
        self.initialize()
        self.accept(self.pair())
        row = self.legacy()
        row["event_evidence"] = {"version": 1, "epoch": "f" * 32 if self.epoch != "f" * 32 else "a" * 32,
                                 "observed_count": 1}
        self.put_memory([row])
        self.refused_without_memory_change(self.memory_state())

    def test_checkpoint_above_ledger_total_refuses_without_lowering_counts(self):
        self.initialize()
        self.accept(self.pair())
        row = self.legacy()
        row["event_evidence"] = {"version": 1, "epoch": self.epoch, "observed_count": 2}
        self.put_memory([row])
        self.refused_without_memory_change(self.memory_state())

    def test_checkpoint_for_absent_candidate_refuses_partial_projection(self):
        self.initialize()
        self.accept(self.pair())
        row = self.legacy(key="missing | correction | OTHER")
        row["event_evidence"] = {"version": 1, "epoch": self.epoch, "observed_count": 1}
        self.put_memory([self.legacy(), row])
        self.refused_without_memory_change(self.memory_state())

    def test_malformed_event_checkpoints_refuse_instead_of_becoming_zero(self):
        self.initialize()
        self.accept(self.pair())
        values = (None, [], {}, {"version": True, "epoch": self.epoch, "observed_count": 1},
                  {"version": 1, "epoch": self.epoch, "observed_count": True},
                  {"version": 1, "epoch": self.epoch, "observed_count": -1},
                  {"version": 2, "epoch": self.epoch, "observed_count": 1},
                  {"version": 1, "epoch": self.epoch, "observed_count": 1, "extra": SECRET})
        for value in values:
            with self.subTest(value=value):
                row = self.legacy()
                row["event_evidence"] = value
                self.put_memory([row])
                self.refused_without_memory_change(self.memory_state(), reason="MEMORY_INVALID")

    def test_explicit_zero_checkpoint_still_credits_first_event(self):
        self.initialize()
        self.accept(self.pair())
        row = self.legacy(count=7)
        row["event_evidence"] = {"version": 1, "epoch": self.epoch, "observed_count": 0}
        self.put_memory([row])
        self.assertEqual(self.project()["stats"]["new_evidence"], 1)
        self.assertEqual(self.rows()[0]["seen_count"], 8)

    def test_malformed_json_memory_refuses_without_dropping_valid_rows(self):
        self.initialize()
        self.accept(self.pair())
        for suffix in (b'{"unfinished":', b'{"key":"bad","seen_count":NaN}\n',
                       b'{"key":"duplicate","key":"again"}\n'):
            with self.subTest(suffix=suffix):
                self.memory_path.write_bytes(self.encoded([self.legacy()]) + suffix)
                self.refused_without_memory_change(self.memory_state())

    def test_duplicate_memory_candidate_keys_refuse_whole_write(self):
        self.initialize()
        self.accept(self.pair())
        self.put_memory([self.legacy(), self.legacy(count=1)])
        self.refused_without_memory_change(self.memory_state())

    def test_invalid_legacy_checkpoint_or_count_refuses_whole_write(self):
        self.initialize()
        self.accept(self.pair())
        rows = []
        row = self.legacy()
        row["seen_count"] = True
        rows.append(row)
        row = self.legacy()
        row["cumulative_evidence"]["feedback_analyzer_v2"]["observed_count"] = -1
        rows.append(row)
        row = self.legacy(count=0)
        row["event_evidence"] = {"version": 1, "epoch": self.epoch, "observed_count": 1}
        rows.append(row)
        for row in rows:
            with self.subTest(row=row):
                self.put_memory([row])
                self.refused_without_memory_change(self.memory_state())

    def test_failure_before_replace_preserves_memory_and_retry_credits_once(self):
        self.initialize()
        self.accept(self.pair())
        self.put_memory([self.legacy(count=7)])
        before = self.memory_state()
        with mock.patch.object(self.memory_module.os, "replace", side_effect=OSError(SECRET)):
            result = self.project()
        self.assertEqual(result["status"], "REFUSED", result)
        self.assertEqual(result["reason"], "MEMORY_WRITE_OUTCOME_UNKNOWN")
        self.assertIsNone(result["memory_written"])
        self.assertEqual(self.memory_state(), before)
        self.assertEqual(sorted(path.name for path in self.learning.iterdir()),
                         ["command_history.jsonl", "correction_evidence.sqlite3", "correction_memory.jsonl"])
        self.assertEqual(self.totals()["pair_count"], 1)
        self.assertEqual(self.project()["stats"]["new_evidence"], 1)
        self.assertEqual(self.rows()[0]["seen_count"], 8)
        self.assertEqual(self.project()["status"], "UNCHANGED")

    def test_failure_after_replace_reconciles_checkpoint_without_double_credit(self):
        self.initialize()
        self.accept(self.pair())
        self.put_memory([self.legacy(count=7)])
        real_replace = self.memory_module.os.replace

        def replaced_then_failed(source, destination):
            real_replace(source, destination)
            raise OSError(SECRET)

        with mock.patch.object(self.memory_module.os, "replace", side_effect=replaced_then_failed):
            result = self.project()
        self.assertEqual(result["status"], "REFUSED", result)
        self.assertEqual(result["reason"], "MEMORY_WRITE_OUTCOME_UNKNOWN")
        self.assertIsNone(result["memory_written"])
        self.assertIsNone(result["stats"])
        self.assertEqual(self.rows()[0]["seen_count"], 8)
        self.assertEqual(self.rows()[0]["event_evidence"]["observed_count"], 1)
        after = self.memory_state()
        self.assertEqual(self.project()["status"], "UNCHANGED")
        self.assertEqual(self.memory_state(), after)

    def test_ledger_commit_with_deferred_projection_is_recoverable_from_totals(self):
        self.initialize()
        self.put_memory([self.legacy(count=10)])
        self.accept(self.pair("one-"))
        self.accept(self.pair("two-"))
        self.assertEqual(self.rows()[0]["seen_count"], 10)
        self.history.write_bytes(b"not valid history anymore\n")
        result = self.project()
        self.assertEqual(result["stats"]["new_evidence"], 2)
        self.assertEqual(self.rows()[0]["seen_count"], 12)
        self.assertEqual(self.project()["status"], "UNCHANGED")

    def test_serialization_failure_before_disk_preserves_original_memory(self):
        self.initialize()
        self.accept(self.pair())
        row = self.legacy()
        row["unknown"]["nonportable"] = "\ud800"
        self.put_memory([row])
        before = self.memory_state()
        self.refused_without_memory_change(before)

    def test_caller_mutating_returned_totals_cannot_change_persisted_evidence(self):
        self.initialize()
        self.accept(self.pair())
        first = self.totals()
        original = copy.deepcopy(first)
        first["candidates"][0]["count"] = 900
        first["candidates"][0]["corrected_slots"]["app"] = "changed"
        self.assertEqual(self.totals(), original)
        self.project()
        self.assertEqual(self.rows()[0]["seen_count"], 1)

    def test_metadata_uses_admission_order_max_confidence_and_later_slots(self):
        self.initialize()
        self.accept(self.pair("z-first-", failed="ЗАПУСТИ РЕДАКТОР", confidence=0.95,
                              slots={"first_only": True, "app": "old", "nested": {"old": 1}}))
        self.accept(self.pair("a-later-", confidence=0.7,
                              slots={"later_only": 96, "app": "notepad", "nested": {"new": 2}}))
        totals = self.totals()
        self.assertEqual(totals["status"], "READY", totals)
        candidate = totals["candidates"][0]
        self.assertEqual(candidate["failed_text"], "ЗАПУСТИ РЕДАКТОР")
        self.assertEqual(candidate["corrected_confidence"], 0.95)
        self.assertEqual(candidate["corrected_slots"],
                         {"first_only": True, "app": "notepad", "nested": {"new": 2}, "later_only": 96})
        self.project()
        row = self.rows()[0]
        self.assertEqual(row["corrected_confidence"], 0.95)
        self.assertEqual(row["corrected_slots"], candidate["corrected_slots"])

    def test_timestamps_change_only_when_new_evidence_is_projected(self):
        self.initialize()
        self.accept(self.pair("first-"))
        with mock.patch.object(self.memory_module.CorrectionMemory, "_now", return_value="2026-02-01T01:02:03"):
            self.project()
        row = self.rows()[0]
        self.assertEqual(row["created_ts"], "2026-02-01T01:02:03")
        self.assertEqual(row["last_seen_ts"], "2026-02-01T01:02:03")
        with mock.patch.object(self.memory_module.CorrectionMemory, "_now", side_effect=AssertionError("Replay is not an event")):
            self.assertEqual(self.project()["status"], "UNCHANGED")
        self.accept(self.pair("second-"))
        with mock.patch.object(self.memory_module.CorrectionMemory, "_now", return_value="2026-02-02T04:05:06"):
            self.project()
        row = self.rows()[0]
        self.assertEqual(row["created_ts"], "2026-02-01T01:02:03")
        self.assertEqual(row["last_seen_ts"], "2026-02-02T04:05:06")

    def test_stored_evidence_must_match_its_bound_event_payloads(self):
        self.initialize()
        self.accept(self.pair())
        connection = self.connect()
        try:
            payload = json.loads(connection.execute("SELECT evidence FROM pairs").fetchone()[0])
        finally:
            connection.close()
        payload["corrected_confidence"] = 0.99
        self.mutate("UPDATE pairs SET evidence = ?", (self.canonical(payload),))
        self.assertEqual(self.totals()["status"], "REFUSED")
        self.refused_without_memory_change(None, reason="LEDGER_REFUSED")

    def test_bound_event_epoch_change_invalidates_stored_pair_totals(self):
        self.initialize()
        self.accept(self.pair())
        connection = self.connect()
        try:
            event_id, raw = connection.execute("SELECT event_id, payload FROM events LIMIT 1").fetchone()
        finally:
            connection.close()
        payload = json.loads(raw)
        payload["evidence_epoch"] = "f" * 32 if self.epoch != "f" * 32 else "a" * 32
        self.mutate("UPDATE events SET payload = ? WHERE event_id = ?", (self.canonical(payload), event_id))
        self.assertEqual(self.totals()["status"], "REFUSED")
        self.refused_without_memory_change(None, reason="LEDGER_REFUSED")

    def test_totals_capacity_refusal_cannot_partially_update_memory(self):
        self.initialize()
        self.accept(self.pair())
        self.put_memory([self.legacy()])
        before = self.memory_state()
        with mock.patch.dict(self.ledger.LIMITS, {"accepted_pairs": 0}):
            totals = self.totals()
            self.assertEqual(totals["status"], "REFUSED", totals)
            self.assertEqual(totals["reason"], "RESOURCE_LIMIT")
            self.refused_without_memory_change(before, reason="LEDGER_REFUSED")

    def test_observed_intervening_memory_change_is_preserved_and_refused(self):
        self.initialize()
        self.accept(self.pair())
        self.put_memory([self.legacy(count=7)])
        concurrent = self.legacy(count=700)
        concurrent["external_change"] = True

        def other_writer_then_clock():
            self.put_memory([concurrent])
            return "2026-02-03T01:02:03"

        with mock.patch.object(self.memory_module.CorrectionMemory, "_now", side_effect=other_writer_then_clock):
            result = self.project()
        self.assertEqual(result["status"], "REFUSED", result)
        self.assertEqual(result["reason"], "MEMORY_CHANGED")
        self.assertEqual(self.rows(), [concurrent])
        self.assertNotIn("event_evidence", self.rows()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
