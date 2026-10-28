"""Named synthetic checks of the private-copy rehearsal boundary only.

Fixtures are disposable local files. No application initializer, model, real
history, training, automatic discovery or network operation is used.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-private-rehearsal-marker-99"
CHILDREN = ("correction_pair_evidence", "learning_history_snapshot", "correction_evidence_ledger",
            "correction_memory", "correction_evidence_projection", "correction_evidence_runtime",
            "correction_evidence_activation", "correction_evidence_rehearsal")


class CorrectionEvidenceRehearsalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_evidence_rehearsal_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo with spaces # unicode-я"
        self.learning = self.repo / "data" / "learning"
        self.learning.mkdir(parents=True)
        self.private = self.root / "retained private copies"
        self.private.mkdir()
        self.history = self.learning / "command_history.jsonl"
        self.history.write_bytes(b"")
        self.memory = self.learning / "correction_memory.jsonl"
        self.database = self.learning / "correction_evidence.sqlite3"
        self.control = self.learning / "correction_evidence_runtime.json"
        names = ("modules", "modules.learning", *("modules.learning." + name for name in CHILDREN))
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
        for name in CHILDREN:
            full = "modules.learning." + name
            spec = importlib.util.spec_from_file_location(full, ROOT / "modules/learning" / (name + ".py"))
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[full] = module
            setattr(package, name, module)
            spec.loader.exec_module(module)
        self.rehearsal = package.correction_evidence_rehearsal
        self.runtime = package.correction_evidence_runtime
        self.capture = package.correction_evidence_activation
        self.ledger = package.correction_evidence_ledger
        self.memory_module = package.correction_memory
        self.attempt = 0
        self.epoch = None
        self.pair_index = 0

    @staticmethod
    def encoded(rows):
        return "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows).encode("ascii")

    @staticmethod
    def legacy_row():
        return {"key": "launch editor | open notepad | OPEN_APP", "seen_count": 37,
                "failed_text": "launch editor", "corrected_text": "open notepad",
                "corrected_intent": "OPEN_APP", "corrected_confidence": 0.5,
                "corrected_slots": {"legacy": "retained"}, "status": "rejected",
                "created_ts": "2020-01-01T00:00:00", "last_seen_ts": "2020-01-02T00:00:00",
                "sources": ["feedback_analyzer_v2", "manual"], "custom": {"value": SECRET},
                "cumulative_evidence": {"feedback_analyzer_v2":
                    {"version": 1, "observed_count": 12, "legacy_baseline": True}}}

    def pair(self, *, epoch=None):
        self.pair_index += 1
        rows = []
        for index, accepted in enumerate((False, True)):
            text = "open notepad" if accepted else "launch editor"
            row = {"ts": (datetime(2026, 1, 1, 12) + timedelta(minutes=self.pair_index * 2, seconds=index)).isoformat(),
                   "event_id": "synthetic-event-" + str(self.pair_index) + "-" + str(index),
                   "raw_text": text, "final_text": text, "mode": "text", "accepted": accepted,
                   "immediate_label": "synthetic", "missing_slots": [],
                   "meta": {"intent": "OPEN_APP" if accepted else None,
                            "confidence": 0.9 if accepted else 0.1,
                            "slots": {"app": "notepad", "private": SECRET} if accepted else {},
                            "say": "", "_text": ""}}
            if epoch is not None:
                row["evidence_epoch"] = epoch
            rows.append(row)
        return rows

    def activate(self, *, memory=False):
        if memory:
            self.memory.write_bytes(self.encoded([self.legacy_row()]))
        result = self.runtime.activate_learning_evidence(self.repo)
        self.assertEqual(result["status"], "ACTIVATED", result)
        self.epoch = self.runtime.read_learning_evidence_control(self.learning)["epoch"]

    def append_pair(self):
        self.history.write_bytes(self.history.read_bytes() + self.encoded(self.pair(epoch=self.epoch)))

    def prepared(self, *, memory=True):
        self.activate(memory=memory)
        self.append_pair()

    def source_state(self):
        values = {}
        for name in self.capture.FILES:
            path = self.learning / name
            values[name] = ((path.read_bytes(), self.capture._signature(path.stat())) if path.exists() else None)
        return values

    def run_rehearsal(self, destination=None):
        self.attempt += 1
        self.run = destination if destination is not None else self.private / ("attempt-" + str(self.attempt))
        result = self.rehearsal.rehearse_correction_evidence(self.repo, self.run)
        self.assertTrue(self.rehearsal.validate_public_result(result), result)
        public = json.dumps(result)
        for private in (SECRET, str(self.root), self.epoch):
            if private:
                self.assertNotIn(private, public)
        return result

    def work_rows(self):
        path = self.run / "working/data/learning/correction_memory.jsonl"
        return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []

    def test_positive_credit_preserves_live_and_legacy_fields_and_raw_backup(self):
        self.prepared()
        unrelated = self.repo / "private sentinel.txt"
        unrelated.write_text(SECRET)
        original = self.source_state()
        result = self.run_rehearsal()
        self.assertEqual((result["status"], result["coverage"]), ("VERIFIED", "NEW_PAIRS"), result)
        self.assertEqual((result["pairs_before"], result["pairs_after_first"], result["pairs_after_second"]), (0, 1, 1))
        self.assertEqual((result["new_evidence_first"], result["new_evidence_second"], result["current_epoch_rows"]), (1, 0, 2))
        self.assertEqual(self.source_state(), original)
        self.assertEqual(unrelated.read_text(), SECRET)
        after = self.work_rows()[0]
        self.assertEqual(after["seen_count"], 38)
        for field in ("status", "created_ts", "custom", "cumulative_evidence"):
            self.assertEqual(after[field], self.legacy_row()[field])
        for name, state in original.items():
            path = self.run / "before/data/learning" / name
            self.assertEqual(path.read_bytes() if path.exists() else None, state[0] if state else None)
        self.assertEqual(json.loads((self.run / "outcome.json").read_bytes()), result)

    def test_new_candidate_is_only_created_in_working_copy(self):
        self.prepared(memory=False)
        result = self.run_rehearsal()
        self.assertEqual(result["status"], "VERIFIED", result)
        self.assertFalse(self.memory.exists())
        self.assertFalse((self.run / "before/data/learning/correction_memory.jsonl").exists())
        row = self.work_rows()[0]
        self.assertEqual((row["seen_count"], row["status"], row["event_evidence"]["observed_count"]), (1, "candidate", 1))

    def test_empty_history_preserves_absent_memory_and_reports_limited_coverage(self):
        self.activate()
        result = self.run_rehearsal()
        self.assertEqual((result["status"], result["coverage"], result["current_epoch_rows"]),
                         ("VERIFIED", "NO_NEW_PAIRS", 0), result)
        self.assertEqual(result["new_evidence_first"], 0)
        self.assertFalse((self.run / "working/data/learning/correction_memory.jsonl").exists())

    def test_new_accepted_observation_is_visible_without_invented_pair_credit(self):
        self.activate()
        self.history.write_bytes(self.encoded([self.pair(epoch=self.epoch)[1]]))
        result = self.run_rehearsal()
        self.assertEqual((result["status"], result["coverage"], result["current_epoch_rows"], result["new_pairs_first"]),
                         ("VERIFIED", "NO_NEW_PAIRS", 1, 0), result)

    def test_pending_projection_is_distinguished_from_new_pair_admission(self):
        self.prepared()
        self.assertEqual(self.ledger.sync_correction_evidence_ledger(self.repo)["status"], "APPLIED")
        original = self.source_state()
        result = self.run_rehearsal()
        self.assertEqual((result["status"], result["coverage"], result["new_pairs_first"], result["new_evidence_first"]),
                         ("VERIFIED", "PENDING_PROJECTION_ONLY", 0, 1), result)
        self.assertEqual(self.source_state(), original)

    def test_already_projected_input_is_unchanged_on_both_working_passes(self):
        self.prepared()
        self.assertEqual(self.runtime.build_learning_corrections(self.repo)["status"], "APPLIED")
        result = self.run_rehearsal()
        self.assertEqual((result["status"], result["coverage"], result["first_build_status"], result["second_build_status"]),
                         ("VERIFIED", "NO_NEW_PAIRS", "UNCHANGED", "UNCHANGED"), result)
        self.assertEqual(self.work_rows()[0]["seen_count"], 38)

    def test_baseline_and_foreign_epoch_observations_are_not_credited(self):
        self.history.write_bytes(self.encoded(self.pair()))
        self.activate(memory=True)
        self.history.write_bytes(self.history.read_bytes() + self.encoded(self.pair(epoch="f" * 32)))
        result = self.run_rehearsal()
        self.assertEqual((result["status"], result["current_epoch_rows"], result["new_pairs_first"]), ("VERIFIED", 0, 0), result)
        self.assertEqual(self.work_rows()[0]["seen_count"], 37)

    def test_sqlite_and_both_build_calls_target_only_separate_working_copy(self):
        self.prepared()
        opened = []
        built = []
        connect, build = self.ledger._connect, self.runtime.build_learning_corrections
        def guarded_connect(path):
            opened.append(path)
            self.assertIn("working", path.parts)
            self.assertNotIn("before", path.parts)
            self.assertNotEqual(path, self.database)
            return connect(path)
        def guarded_build(repo):
            built.append(repo)
            return build(repo)
        with mock.patch.object(self.ledger, "_connect", side_effect=guarded_connect), \
                mock.patch.object(self.runtime, "build_learning_corrections", side_effect=guarded_build):
            result = self.run_rehearsal()
        self.assertEqual(result["status"], "VERIFIED", result)
        self.assertTrue(opened)
        self.assertEqual(built, [self.run / "working", self.run / "working"])

    def test_source_change_during_capture_refuses_before_sqlite(self):
        self.prepared()
        backup = self.capture._backup
        def changed(*args):
            result = backup(*args)
            self.history.write_bytes(self.history.read_bytes() + b"\n")
            return result
        with mock.patch.object(self.capture, "_backup", side_effect=changed), \
                mock.patch.object(self.ledger, "_connect", side_effect=AssertionError("SQLite must not open")):
            result = self.run_rehearsal()
        self.assertEqual((result["status"], result["reason"], result["first_build_status"]),
                         ("REFUSED", "INPUT_CHANGED", "NOT_RUN"), result)
        self.assertIsNone(result["source_preserved_at_capture"])

    def test_work_copy_byte_mismatch_refuses_and_retains_raw_before(self):
        self.prepared()
        fingerprint = self.capture._fingerprint
        def mismatched(path, maximum, expected=None, *, target=None):
            result = fingerprint(path, maximum, expected, target=target)
            if target is not None and "working" in target.parts and path.name == self.history.name:
                target.write_bytes(b"different copied bytes")
            return result
        with mock.patch.object(self.capture, "_fingerprint", side_effect=mismatched):
            result = self.run_rehearsal()
        self.assertEqual((result["status"], result["reason"], result["first_build_status"]),
                         ("REFUSED", "WORK_COPY_FAILED", "NOT_RUN"), result)
        self.assertEqual((self.run / "before/data/learning" / self.history.name).read_bytes(), self.history.read_bytes())

    def test_raw_backup_tamper_after_build_is_reported_without_restoring(self):
        self.prepared()
        build = self.runtime.build_learning_corrections
        def tampered(repo):
            result = build(repo)
            (repo.parent / "before/data/learning" / self.history.name).write_bytes(b"tampered")
            return result
        with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=tampered):
            result = self.run_rehearsal()
        self.assertEqual((result["status"], result["reason"], result["backup_preserved"]),
                         ("REFUSED", "BACKUP_CHANGED", False), result)
        self.assertEqual((self.run / "before/data/learning" / self.history.name).read_bytes(), b"tampered")

    def test_later_external_source_change_does_not_expand_capture_scope(self):
        self.prepared()
        original = self.history.read_bytes()
        copy = self.rehearsal._working_copy
        later = self.encoded([self.pair(epoch=self.epoch)[1]])
        def copied(*args):
            result = copy(*args)
            self.history.write_bytes(original + later)
            return result
        with mock.patch.object(self.rehearsal, "_working_copy", side_effect=copied):
            result = self.run_rehearsal()
        self.assertEqual(result["status"], "VERIFIED", result)
        self.assertTrue(result["source_preserved_at_capture"])
        self.assertEqual(result["scope"]["source_preservation"], "VERIFIED_AT_CAPTURE_BEFORE_UNLOCK_ONLY")
        self.assertEqual(self.history.read_bytes(), original + later)
        self.assertEqual((self.run / "before/data/learning" / self.history.name).read_bytes(), original)

    def test_inactive_or_invalid_control_never_calls_builder_or_activation(self):
        for mode in ("LEGACY", "PREPARING", "INVALID"):
            with self.subTest(mode=mode):
                if self.control.exists():
                    self.control.unlink()
                if mode == "PREPARING":
                    self.control.write_bytes(self.runtime._encoded_control("PREPARING", None))
                elif mode == "INVALID":
                    self.control.write_bytes(b"not-json")
                with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=AssertionError(SECRET)), \
                        mock.patch.object(self.runtime, "activate_learning_evidence", side_effect=AssertionError(SECRET)):
                    result = self.run_rehearsal()
                self.assertEqual(result["status"], "REFUSED", result)
                self.assertEqual(result["reason"], "CONTROL_INVALID" if mode == "INVALID" else "ACTIVE_REQUIRED")
                self.assertEqual(result["first_build_status"], "NOT_RUN")
                self.assertFalse(self.database.exists())

    def test_missing_or_corrupt_active_ledger_refuses_without_first_build(self):
        self.activate()
        for raw in (None, b"corrupt SQLite " + SECRET.encode()):
            with self.subTest(missing=raw is None):
                if self.database.exists():
                    self.database.unlink()
                if raw is not None:
                    self.database.write_bytes(raw)
                original = self.source_state()
                result = self.run_rehearsal()
                self.assertEqual((result["status"], result["reason"], result["first_build_status"]),
                                 ("REFUSED", "LEDGER_INVALID", "NOT_RUN"), result)
                self.assertEqual(self.source_state(), original)

    def test_bad_history_or_duplicate_ids_is_not_rewritten_or_partially_used(self):
        self.activate()
        pair = self.pair(epoch=self.epoch)
        for raw in (b"not-json\n", b"\xff\n", self.encoded([pair[0], pair[0], pair[1]]), b"\n"):
            with self.subTest(raw_kind=len(raw)):
                self.history.write_bytes(raw)
                result = self.run_rehearsal()
                self.assertEqual(result["status"], "REFUSED", result)
                self.assertIn(result["reason"], ("HISTORY_REFUSED", "HISTORY_INVALID", "HISTORY_DUPLICATE_IDS"))
                self.assertEqual(result["first_build_status"], "NOT_RUN")
                self.assertEqual(self.history.read_bytes(), raw)

    def test_invalid_memory_or_checkpoint_refuses_before_build(self):
        self.activate()
        row = self.legacy_row()
        future = deepcopy(row)
        future["event_evidence"] = {"version": 1, "epoch": self.epoch, "observed_count": 1}
        for raw in (b"not-json\n", self.encoded([row, row]), self.encoded([future])):
            with self.subTest(raw_kind=len(raw)):
                self.memory.write_bytes(raw)
                result = self.run_rehearsal()
                self.assertEqual(result["status"], "REFUSED", result)
                self.assertIn(result["reason"], ("MEMORY_INVALID", "MEMORY_LEDGER_MISMATCH"))
                self.assertEqual(result["first_build_status"], "NOT_RUN")
                self.assertEqual(self.memory.read_bytes(), raw)

    def test_unsafe_destination_scope_and_reuse_never_overwrite_existing_files(self):
        self.activate()
        existing = self.private / "already exists"
        existing.mkdir()
        sentinel = existing / "sentinel.txt"
        sentinel.write_text(SECRET)
        for destination in (self.repo, self.repo / "nested", self.root, Path("relative"), existing):
            with self.subTest(destination=str(destination)):
                result = self.run_rehearsal(destination)
                self.assertEqual(result["status"], "REFUSED", result)
                self.assertIn(result["reason"], ("BACKUP_IN_PROJECT", "INVALID_PATH", "BACKUP_EXISTS"))
        self.assertEqual(sentinel.read_text(), SECRET)

    def test_hardlinked_private_input_is_refused_before_copy(self):
        self.activate()
        alias = self.root / "history-alias"
        os.link(self.history, alias)
        result = self.run_rehearsal()
        self.assertEqual((result["status"], result["reason"], result["first_build_status"]),
                         ("REFUSED", "UNSAFE_PATH", "NOT_RUN"), result)
        self.assertTrue(alias.exists())

    def test_capture_resource_limit_is_enforced_before_sqlite(self):
        self.activate()
        with mock.patch.object(self.capture, "MAX_BACKUP_BYTES", 1), \
                mock.patch.object(self.ledger, "_connect", side_effect=AssertionError(SECRET)):
            result = self.run_rehearsal()
        self.assertEqual((result["status"], result["reason"], result["first_build_status"]),
                         ("REFUSED", "RESOURCE_LIMIT", "NOT_RUN"), result)

    def test_busy_live_lock_refuses_without_removing_it_or_starting_capture(self):
        self.activate()
        with self.runtime.learning_evidence_lock(self.learning):
            result = self.run_rehearsal()
        self.assertEqual((result["status"], result["reason"], result["backup_status"]),
                         ("REFUSED", "BUSY", "NOT_CREATED"), result)
        self.assertTrue((self.learning / self.runtime.LOCK_NAME).exists())
        self.assertFalse(self.run.exists())

    def test_first_refusal_after_ledger_sync_retains_partial_working_state(self):
        self.prepared()
        original = self.source_state()
        def partial(repo):
            self.assertEqual(self.ledger.sync_correction_evidence_ledger(repo)["status"], "APPLIED")
            return self.runtime._result("BUILD", reason="PROJECTION_REFUSED", detail_reason="MEMORY_WRITE_OUTCOME_UNKNOWN")
        with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=partial):
            result = self.run_rehearsal()
        self.assertEqual((result["reason"], result["first_build_status"], result["second_build_status"]),
                         ("FIRST_BUILD_REFUSED", "REFUSED", "NOT_RUN"), result)
        self.assertEqual(self.ledger.read_correction_evidence_totals(self.run / "working")["pair_count"], 1)
        self.assertEqual(self.work_rows()[0]["seen_count"], 37)
        self.assertEqual(self.source_state(), original)

    def test_first_exception_after_success_has_unknown_outcome_and_keeps_copy(self):
        self.prepared()
        build = self.runtime.build_learning_corrections
        def unknown(repo):
            build(repo)
            raise OSError(SECRET)
        with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=unknown):
            result = self.run_rehearsal()
        self.assertEqual((result["reason"], result["first_build_status"], result["second_build_status"]),
                         ("FIRST_BUILD_OUTCOME_UNKNOWN", "UNKNOWN", "NOT_RUN"), result)
        self.assertEqual(self.work_rows()[0]["seen_count"], 38)

    def test_second_refusal_keeps_first_result_and_does_not_claim_replay(self):
        self.prepared()
        build = self.runtime.build_learning_corrections
        calls = 0
        def second_refused(repo):
            nonlocal calls
            calls += 1
            return build(repo) if calls == 1 else self.runtime._result("BUILD", reason="LEDGER_SYNC_REFUSED")
        with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=second_refused):
            result = self.run_rehearsal()
        self.assertEqual((result["reason"], result["first_build_status"], result["second_build_status"]),
                         ("SECOND_BUILD_REFUSED", "APPLIED", "REFUSED"), result)
        self.assertIsNone(result["replay_memory_preserved"])
        self.assertEqual(self.work_rows()[0]["seen_count"], 38)

    def test_second_positive_claim_is_not_accepted_as_replay(self):
        self.prepared()
        build = self.runtime.build_learning_corrections
        calls = 0
        def false_replay(repo):
            nonlocal calls
            calls += 1
            result = build(repo)
            if calls == 2:
                result["status"] = "APPLIED"
                result["stats"].update(new_evidence=1, written=True)
            return result
        with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=false_replay):
            result = self.run_rehearsal()
        self.assertEqual(result["reason"], "SECOND_BUILD_NOT_REPLAY", result)

    def test_second_memory_change_is_detected_despite_zero_reported_delta(self):
        self.prepared()
        build = self.runtime.build_learning_corrections
        calls = 0
        def changed(repo):
            nonlocal calls
            calls += 1
            result = build(repo)
            if calls == 2:
                path = repo / "data/learning/correction_memory.jsonl"
                row = json.loads(path.read_bytes())
                row["custom"] = {"tampered": True}
                path.write_bytes(self.encoded([row]))
            return result
        with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=changed):
            result = self.run_rehearsal()
        self.assertEqual((result["reason"], result["replay_memory_preserved"]), ("REPLAY_MEMORY_CHANGED", False), result)

    def test_second_binding_change_is_detected_even_when_full_totals_match(self):
        self.prepared()
        build = self.runtime.build_learning_corrections
        calls = 0
        def changed(repo):
            nonlocal calls
            calls += 1
            result = build(repo)
            if calls == 2:
                connection = sqlite3.connect(repo / "data/learning/correction_evidence.sqlite3")
                try:
                    connection.execute("UPDATE events SET quarantined = 1 WHERE baseline = 0")
                    connection.commit()
                finally:
                    connection.close()
            return result
        with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=changed):
            result = self.run_rehearsal()
        self.assertEqual((result["reason"], result["replay_ledger_preserved"]), ("REPLAY_LEDGER_CHANGED", False), result)

    def test_first_projection_must_preserve_business_status_and_unknown_fields(self):
        self.prepared()
        original = self.legacy_row()
        original["custom"].update(flag=True, integer=1, negative_zero=-0.0)
        self.memory.write_bytes(self.encoded([original]))
        build = self.runtime.build_learning_corrections
        mutations = [(lambda row: row.update(status="approved"), "LEGACY_METADATA_CHANGED"),
                     (lambda row: row.pop("custom"), "LEGACY_METADATA_CHANGED"),
                     (lambda row: row["custom"].update(flag=1), "LEGACY_METADATA_CHANGED"),
                     (lambda row: row["custom"].update(integer=1.0), "LEGACY_METADATA_CHANGED"),
                     (lambda row: row["custom"].update(negative_zero=0.0), "LEGACY_METADATA_CHANGED"),
                     (lambda row: row.update(corrected_slots={"wrong": True}), "PROJECTION_MISMATCH"),
                     (lambda row: row.update(corrected_confidence=0.1), "PROJECTION_MISMATCH"),
                     (lambda row: row.update(sources=["wrong"]), "PROJECTION_MISMATCH")]
        for mutation, expected_reason in mutations:
            with self.subTest(reason=expected_reason):
                def lost_legacy(repo):
                    result = build(repo)
                    path = repo / "data/learning/correction_memory.jsonl"
                    row = json.loads(path.read_bytes())
                    mutation(row)
                    path.write_bytes(self.encoded([row]))
                    return result
                with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=lost_legacy):
                    result = self.run_rehearsal()
                self.assertEqual((result["reason"], result["second_build_status"]), (expected_reason, "NOT_RUN"), result)

    def test_first_claimed_credit_is_checked_against_persisted_count_and_checkpoint(self):
        self.prepared()
        build = self.runtime.build_learning_corrections
        def false_count(repo):
            result = build(repo)
            result["stats"]["new_evidence"] += 1
            return result
        with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=false_count):
            result = self.run_rehearsal()
        self.assertEqual((result["reason"], result["second_build_status"]), ("PROJECTION_MISMATCH", "NOT_RUN"), result)

    def test_public_schema_rejects_private_fields_wrong_types_and_inconsistent_success(self):
        self.prepared()
        result = self.run_rehearsal()
        self.assertEqual(result["status"], "VERIFIED", result)
        mutations = [lambda item: item.update(private=SECRET),
                     lambda item: item.update(reason=SECRET),
                     lambda item: item.update(history_rows=True),
                     lambda item: item.update(current_epoch_rows=1_000_001),
                     lambda item: item.update(source_preserved_at_capture=1),
                     lambda item: item.update(coverage="NO_NEW_PAIRS"),
                     lambda item: item.update(new_evidence_second=1),
                     lambda item: item.update(pairs_after_second=2),
                     lambda item: item.update(new_evidence_first=2),
                     lambda item: item.update(current_epoch_rows=1),
                     lambda item: item.update(memory_rows_after=0),
                     lambda item: item.update(first_build_status="NOT_RUN"),
                     lambda item: item["scope"].update(live_sqlite_opened=True)]
        for mutation in mutations:
            changed = deepcopy(result)
            mutation(changed)
            self.assertFalse(self.rehearsal.validate_public_result(changed), changed)
        self.assertFalse(self.rehearsal.validate_public_result([]))

    def test_unexpected_private_exception_is_replaced_by_fixed_reason(self):
        self.prepared()
        with mock.patch.object(self.rehearsal, "_working_copy", side_effect=ValueError(SECRET + str(self.root))):
            result = self.run_rehearsal()
        self.assertEqual((result["reason"], result["first_build_status"]), ("INTERNAL_ERROR", "NOT_RUN"), result)

    def test_working_history_and_control_must_remain_captured_bytes(self):
        self.prepared()
        build = self.runtime.build_learning_corrections
        for name, reason in ((self.history.name, "WORK_HISTORY_CHANGED"), (self.control.name, "WORK_CONTROL_CHANGED")):
            with self.subTest(name=name):
                def changed(repo):
                    result = build(repo)
                    path = repo / "data/learning" / name
                    path.write_bytes(path.read_bytes() + b"\n")
                    return result
                with mock.patch.object(self.runtime, "build_learning_corrections", side_effect=changed):
                    result = self.run_rehearsal()
                self.assertEqual((result["reason"], result["second_build_status"]), (reason, "NOT_RUN"), result)

    def test_final_receipt_failure_does_not_erase_completed_build_outcomes(self):
        self.prepared()
        write = self.capture._write_record
        def refused(path, record):
            if path.name == "outcome.json":
                raise OSError(SECRET)
            return write(path, record)
        with mock.patch.object(self.capture, "_write_record", side_effect=refused):
            result = self.run_rehearsal()
        self.assertEqual((result["status"], result["reason"], result["first_build_status"], result["second_build_status"]),
                         ("REFUSED", "RECEIPT_WRITE_FAILED", "APPLIED", "UNCHANGED"), result)
        self.assertTrue(result["replay_memory_preserved"])
        self.assertTrue(result["backup_preserved"])
        self.assertEqual(self.work_rows()[0]["seen_count"], 38)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CorrectionEvidenceRehearsalTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("CORRECTION_EVIDENCE_REHEARSAL_TESTS=" + ("PASS" if result.wasSuccessful() else "FAIL"))
    print("CASES=" + str(result.testsRun))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
