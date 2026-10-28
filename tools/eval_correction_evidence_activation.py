"""Named, isolated checks of retained-backup correction-evidence activation.

All private paths are synthetic temporary fixtures. Application initializers,
environment settings, models, test discovery and user data are never loaded.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-private-activation-marker-97"
CHILDREN = ("correction_pair_evidence", "learning_history_snapshot", "correction_evidence_ledger",
            "correction_memory", "feedback_analyzer", "correction_evidence_projection",
            "correction_evidence_runtime", "learning_memory", "correction_evidence_activation")


class CorrectionEvidenceActivationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_evidence_activation_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo with spaces # unicode-я"
        self.learning = self.repo / "data" / "learning"
        self.learning.mkdir(parents=True)
        self.backups = self.root / "private backups"
        self.backups.mkdir()
        self.history = self.learning / "command_history.jsonl"
        self.history.write_bytes(b"")
        self.memory_path = self.learning / "correction_memory.jsonl"
        self.database = self.learning / "correction_evidence.sqlite3"
        self.control_path = self.learning / "correction_evidence_runtime.json"
        self.lock_path = self.learning / "correction_evidence_runtime.lock"
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
        self.activation = package.correction_evidence_activation
        self.runtime = package.correction_evidence_runtime
        self.ledger = package.correction_evidence_ledger
        self.projection = package.correction_evidence_projection
        self.writer_module = package.learning_memory
        self.memory_module = package.correction_memory
        self.attempt = 0

    @staticmethod
    def history_row(index=0, *, accepted=False, identified=True):
        text = "open notepad" if accepted else "launch editor"
        row = {"ts": (datetime(2026, 1, 1, 12) + timedelta(seconds=index)).isoformat(),
               "raw_text": text, "final_text": text, "mode": "text", "accepted": accepted,
               "immediate_label": "synthetic", "missing_slots": [],
               "meta": {"intent": "OPEN_APP" if accepted else None,
                        "confidence": 0.9 if accepted else 0.1,
                        "slots": {"app": "notepad"} if accepted else {}, "say": "", "_text": ""}}
        if identified:
            row["event_id"] = "synthetic-event-" + str(index)
        return row

    @staticmethod
    def memory_row():
        return {"key": "launch editor | open notepad | OPEN_APP", "seen_count": 37,
                "failed_text": "launch editor", "corrected_text": "open notepad",
                "corrected_intent": "OPEN_APP", "corrected_confidence": 0.5,
                "corrected_slots": {"legacy": "retained"}, "status": "rejected",
                "created_ts": "2020-01-01T00:00:00", "last_seen_ts": "2020-01-02T00:00:00",
                "sources": ["feedback_analyzer_v2", "manual"], "custom": {"value": SECRET},
                "cumulative_evidence": {"feedback_analyzer_v2":
                    {"version": 1, "observed_count": 12, "legacy_baseline": True}}}

    @staticmethod
    def encoded(rows):
        return "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows).encode("ascii")

    def write_history(self, rows):
        self.history.write_bytes(self.encoded(rows))

    def write_memory(self, rows):
        self.memory_path.write_bytes(self.encoded(rows))

    def run_activation(self):
        self.attempt += 1
        self.backup = self.backups / ("attempt-" + str(self.attempt))
        result = self.activation.activate_correction_evidence_safely(self.repo, self.backup)
        self.assertTrue(self.activation.validate_public_result(result), result)
        public = json.dumps(result)
        self.assertNotIn(SECRET, public)
        self.assertNotIn(str(self.root), public)
        return result

    def activate(self):
        result = self.run_activation()
        self.assertEqual(result["status"], "ACTIVATED", result)
        return self.runtime.read_learning_evidence_control(self.learning)["epoch"]

    def assert_not_activated(self):
        self.assertFalse(self.control_path.exists())
        self.assertFalse(self.database.exists())

    def test_first_activation_preserves_old_bytes_counts_status_and_zero_credit_baseline(self):
        self.write_history([self.history_row(0, identified=False), self.history_row(1), self.history_row(2, accepted=True)])
        self.write_memory([self.memory_row()])
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (self.history, self.memory_path)}
        result = self.run_activation()
        self.assertEqual((result["status"], result["initial_state"], result["final_state"]),
                         ("ACTIVATED", "LEGACY", "ACTIVE"))
        self.assertEqual((result["history_rows"], result["memory_rows"], result["pairs_after"]), (3, 1, 0))
        self.assertEqual({path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before}, before)
        for path, (raw, _) in before.items():
            self.assertEqual((self.backup / "before/data/learning" / path.name).read_bytes(), raw)
        manifest = json.loads((self.backup / "backup_ready.json").read_bytes())
        self.assertEqual(set(manifest["files"]), set(self.activation.FILES))
        self.assertIsNone(manifest["files"][self.database.name])
        self.assertEqual(json.loads((self.backup / "outcome.json").read_bytes()), result)

    def test_empty_history_and_absent_memory_are_preserved_without_creating_memory(self):
        result = self.run_activation()
        self.assertEqual(result["status"], "ACTIVATED")
        self.assertEqual((result["history_rows"], result["memory_rows"], result["pairs_after"]), (0, 0, 0))
        self.assertFalse(self.memory_path.exists())
        self.assertEqual(self.history.read_bytes(), b"")

    def test_new_writer_after_controlled_cutover_and_builder_count_once(self):
        self.write_memory([self.memory_row()])
        epoch = self.activate()
        writer = self.writer_module.LearningMemory(str(self.learning))
        for accepted in (False, True):
            row = self.history_row(int(accepted), accepted=accepted)
            arguments = {name: row[name] for name in ("raw_text", "final_text", "meta", "mode", "accepted", "immediate_label", "missing_slots")}
            writer.log_command(**arguments)
        history = [json.loads(line) for line in self.history.read_bytes().splitlines()]
        self.assertEqual([row["evidence_epoch"] for row in history], [epoch, epoch])
        first = self.runtime.build_learning_corrections(self.repo)
        self.assertEqual(first["stats"]["new_evidence"], 1)
        before = self.memory_path.read_bytes()
        self.assertEqual(json.loads(before)["seen_count"], 38)
        self.assertEqual(self.runtime.build_learning_corrections(self.repo)["stats"]["new_evidence"], 0)
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_active_retry_accepts_existing_valid_event_checkpoints_and_preserves_prior_backups(self):
        self.write_memory([self.memory_row()])
        epoch = self.activate()
        original_backup = self.backup
        rows = [self.history_row(0), self.history_row(1, accepted=True)]
        for row in rows:
            row["evidence_epoch"] = epoch
        self.write_history(rows)
        self.assertEqual(self.runtime.build_learning_corrections(self.repo)["stats"]["new_evidence"], 1)
        before = (self.history.read_bytes(), self.memory_path.read_bytes(), self.database.read_bytes())
        result = self.run_activation()
        self.assertEqual((result["status"], result["pairs_before"], result["pairs_after"]), ("ALREADY_ACTIVE", 1, 1))
        self.assertEqual((self.history.read_bytes(), self.memory_path.read_bytes(), self.database.read_bytes()), before)
        self.assertTrue((original_backup / "outcome.json").is_file())
        self.assertNotEqual(original_backup, self.backup)

    def test_preparing_without_database_resumes_existing_state(self):
        self.control_path.write_bytes(self.runtime._encoded_control("PREPARING", None))
        result = self.run_activation()
        self.assertEqual((result["status"], result["initial_state"], result["pairs_after"]), ("ACTIVATED", "PREPARING", 0))
        self.assertEqual(json.loads((self.backup / "before/data/learning" / self.control_path.name).read_bytes())["state"], "PREPARING")

    def test_preparing_with_valid_zero_pair_ledger_resumes_same_epoch(self):
        with mock.patch.object(self.runtime, "_activate_control", side_effect=OSError(SECRET)):
            self.assertEqual(self.runtime.activate_learning_evidence(self.repo)["status"], "REFUSED")
        epoch = self.ledger.read_correction_evidence_totals(self.repo)["epoch"]
        database = self.database.read_bytes()
        result = self.run_activation()
        self.assertEqual((result["status"], result["initial_state"]), ("ACTIVATED", "PREPARING"))
        self.assertEqual(self.runtime.read_learning_evidence_control(self.learning)["epoch"], epoch)
        self.assertEqual((self.backup / "before/data/learning" / self.database.name).read_bytes(), database)

    def test_malformed_control_and_orphan_ledger_are_retained_and_refused(self):
        self.control_path.write_bytes(SECRET.encode())
        result = self.run_activation()
        self.assertEqual((result["reason"], result["activation_status"]), ("CONTROL_INVALID", "NOT_RUN"))
        self.assertEqual(self.control_path.read_bytes(), SECRET.encode())
        self.control_path.unlink()
        self.database.write_bytes(SECRET.encode())
        result = self.run_activation()
        self.assertEqual((result["reason"], result["activation_status"]), ("ORPHAN_LEDGER", "NOT_RUN"))
        self.assertEqual(self.database.read_bytes(), SECRET.encode())

    def test_corrupt_preparing_database_is_backed_up_and_never_automatically_rebuilt(self):
        self.control_path.write_bytes(self.runtime._encoded_control("PREPARING", None))
        self.database.write_bytes(SECRET.encode())
        result = self.run_activation()
        self.assertEqual((result["reason"], result["activation_status"]), ("LEDGER_INVALID", "NOT_RUN"))
        self.assertEqual((self.backup / "before/data/learning" / self.database.name).read_bytes(), SECRET.encode())
        self.assertEqual(self.database.read_bytes(), SECRET.encode())
        self.assertEqual(self.runtime.read_learning_evidence_control(self.learning)["state"], "PREPARING")

    def test_history_requires_complete_decodable_schema_without_rewriting_bad_rows(self):
        invalid = self.history_row()
        invalid["accepted"] = "yes"
        cases = (b"not json\n", b"{}", b"\n", b"{\"raw_text\":\"\\ud800\"}\n", self.encoded([invalid]))
        for raw in cases:
            with self.subTest(raw_kind=len(raw)):
                self.history.write_bytes(raw)
                result = self.run_activation()
                self.assertEqual(result["status"], "REFUSED")
                self.assertIn(result["reason"], ("HISTORY_REFUSED", "HISTORY_INVALID"))
                self.assertEqual(result["activation_status"], "NOT_RUN")
                self.assertEqual(self.history.read_bytes(), raw)
                self.assert_not_activated()

    def test_identical_and_conflicting_duplicate_event_ids_refuse_fresh_cutover(self):
        row = self.history_row()
        for other in (deepcopy(row), dict(row, raw_text=SECRET)):
            self.write_history([row, other])
            result = self.run_activation()
            self.assertEqual(result["reason"], "HISTORY_DUPLICATE_IDS")
            self.assert_not_activated()

    def test_memory_strict_schema_portability_and_legacy_checkpoints_are_checked(self):
        cases = [dict(self.memory_row(), key="wrong key"),
                 dict(self.memory_row(), seen_count=True),
                 dict(self.memory_row(), corrected_confidence=2.0),
                 dict(self.memory_row(), custom="\ud800"),
                 dict(self.memory_row(), cumulative_evidence={"x": {"version": 0}})]
        for row in cases:
            self.write_memory([row])
            before = self.memory_path.read_bytes()
            result = self.run_activation()
            self.assertEqual((result["reason"], result["activation_status"]), ("MEMORY_INVALID", "NOT_RUN"))
            self.assertEqual(self.memory_path.read_bytes(), before)
            self.assert_not_activated()

    def test_missing_control_never_adopts_event_checkpoint_as_legacy(self):
        row = self.memory_row()
        row["event_evidence"] = {"version": 1, "epoch": "a" * 32, "observed_count": 0}
        self.write_memory([row])
        result = self.run_activation()
        self.assertEqual(result["reason"], "MISSING_CONTROL_STATE")
        self.assert_not_activated()

    def test_active_memory_checkpoint_shape_epoch_and_regression_are_validated(self):
        epoch = self.activate()
        cases = (({"version": 1, "epoch": "f" * 32, "observed_count": 0}, "EPOCH_MISMATCH"),
                 ({"version": True, "epoch": epoch, "observed_count": 0}, "MEMORY_INVALID"),
                 ({"version": 1, "epoch": epoch, "observed_count": 1}, "MEMORY_LEDGER_MISMATCH"))
        for checkpoint, expected in cases:
            self.write_memory([dict(self.memory_row(), event_evidence=checkpoint)])
            before = self.memory_path.read_bytes()
            result = self.run_activation()
            self.assertEqual((result["reason"], result["activation_status"]), (expected, "NOT_RUN"))
            self.assertEqual(self.memory_path.read_bytes(), before)

    def test_database_and_sidecar_before_images_precede_every_sqlite_access(self):
        self.activate()
        journal = self.learning / (self.database.name + "-journal")
        journal.write_bytes(SECRET.encode())
        before_db = self.database.read_bytes()
        real = self.ledger.read_correction_evidence_totals
        calls = []
        def checked(repo):
            self.assertTrue((self.backup / "backup_ready.json").is_file())
            self.assertTrue((self.backup / "sqlite_intent.json").is_file())
            self.assertEqual((self.backup / "before/data/learning" / journal.name).read_bytes(), SECRET.encode())
            self.assertEqual((self.backup / "before/data/learning" / self.database.name).read_bytes(), before_db)
            if journal.exists():
                journal.unlink()  # Simulate recovery only in the owned fixture.
            calls.append(True)
            return real(repo)
        with mock.patch.object(self.ledger, "read_correction_evidence_totals", side_effect=checked):
            result = self.run_activation()
        self.assertEqual(result["status"], "ALREADY_ACTIVE")
        self.assertGreaterEqual(len(calls), 3)

    def test_copy_failure_retains_partial_backup_and_prevents_runtime_call(self):
        real = self.activation._fingerprint
        def failed(path, maximum, expected=None, *, target=None):
            if target is not None:
                raise OSError(SECRET)
            return real(path, maximum, expected, target=target)
        with mock.patch.object(self.activation, "_fingerprint", side_effect=failed), \
                mock.patch.object(self.runtime, "_activate_learning_evidence_locked") as called:
            result = self.run_activation()
        self.assertEqual((result["backup_status"], result["activation_status"]), ("INCOMPLETE", "NOT_RUN"))
        self.assertTrue(self.backup.is_dir())
        called.assert_not_called()
        self.assert_not_activated()

    def test_backup_ready_marker_failure_prevents_sqlite_access_and_cutover(self):
        with mock.patch.object(self.activation, "_write_record", side_effect=OSError(SECRET)), \
                mock.patch.object(self.ledger, "read_correction_evidence_totals") as read:
            result = self.run_activation()
        self.assertEqual((result["backup_status"], result["activation_status"]), ("INCOMPLETE", "NOT_RUN"))
        read.assert_not_called()
        self.assert_not_activated()

    def test_source_change_during_copy_is_detected_before_cutover(self):
        real = self.activation._fingerprint
        def changed(path, maximum, expected=None, *, target=None):
            result = real(path, maximum, expected, target=target)
            if target is not None and path == self.history:
                self.history.write_bytes(self.encoded([self.history_row()]))
            return result
        with mock.patch.object(self.activation, "_fingerprint", side_effect=changed):
            result = self.run_activation()
        self.assertEqual((result["reason"], result["activation_status"]), ("INPUT_CHANGED", "NOT_RUN"))
        self.assert_not_activated()

    def test_source_change_after_backup_is_detected_before_runtime_call(self):
        real = self.activation._admissible_history
        def changed(backup_repo):
            result = real(backup_repo)
            self.history.write_bytes(self.encoded([self.history_row()]))
            return result
        with mock.patch.object(self.activation, "_admissible_history", side_effect=changed):
            result = self.run_activation()
        self.assertEqual((result["reason"], result["activation_status"]), ("INPUT_CHANGED", "NOT_RUN"))
        self.assert_not_activated()

    def test_failure_after_control_replace_is_unknown_and_retry_reconciles_active_state(self):
        real = self.runtime._activate_control
        def after_replace(base, epoch):
            real(base, epoch)
            raise OSError(SECRET)
        with mock.patch.object(self.runtime, "_activate_control", side_effect=after_replace):
            first = self.run_activation()
        self.assertEqual((first["reason"], first["activation_status"]), ("ACTIVATION_OUTCOME_UNKNOWN", "UNKNOWN"))
        failed_backup = self.backup
        self.assertTrue((failed_backup / "activation_intent.json").is_file())
        self.assertEqual(self.runtime.read_learning_evidence_control(self.learning)["state"], "ACTIVE")
        self.assertEqual(self.run_activation()["status"], "ALREADY_ACTIVE")
        self.assertTrue(failed_backup.is_dir())

    def test_failure_after_preparing_creation_retains_state_for_retry(self):
        with mock.patch.object(self.ledger, "initialize_correction_evidence_ledger", side_effect=OSError(SECRET)):
            result = self.run_activation()
        self.assertEqual(result["activation_status"], "UNKNOWN")
        self.assertEqual(self.runtime.read_learning_evidence_control(self.learning)["state"], "PREPARING")
        self.assertFalse(self.database.exists())
        self.assertEqual(self.run_activation()["status"], "ACTIVATED")

    def test_outcome_receipt_failure_does_not_claim_activation_was_not_run(self):
        real = self.activation._write_record
        def fail_outcome(path, record):
            if path.name == "outcome.json":
                raise OSError(SECRET)
            return real(path, record)
        with mock.patch.object(self.activation, "_write_record", side_effect=fail_outcome):
            result = self.run_activation()
        self.assertEqual((result["reason"], result["activation_status"], result["final_state"]),
                         ("RECEIPT_WRITE_FAILED", "ACTIVATED", "ACTIVE"))
        self.assertEqual(self.run_activation()["status"], "ALREADY_ACTIVE")

    def test_last_resort_public_fallback_preserves_unknown_after_actual_activation(self):
        destination = self.backups / "forced-public-fallback"
        with mock.patch.object(self.activation, "validate_public_result", return_value=False):
            result = self.activation.activate_correction_evidence_safely(self.repo, destination)
        self.assertTrue(self.activation.validate_public_result(result))
        self.assertEqual((result["status"], result["reason"], result["activation_status"], result["stage"]),
                         ("REFUSED", "ACTIVATION_OUTCOME_UNKNOWN", "UNKNOWN", "POSTCHECK"))
        self.assertEqual(self.runtime.read_learning_evidence_control(self.learning)["state"], "ACTIVE")
        self.assertTrue((destination / "activation_intent.json").is_file())
        self.assertNotIn(SECRET, json.dumps(result))

    def test_busy_lock_refuses_without_backup_and_lock_is_never_copied(self):
        with self.runtime.learning_evidence_lock(self.learning):
            result = self.run_activation()
        self.assertEqual((result["reason"], result["stage"]), ("BUSY", "LOCK"))
        self.assertFalse(self.backup.exists())
        real = self.activation._fingerprint
        def no_lock(path, maximum, expected=None, *, target=None):
            self.assertNotEqual(path.name, self.lock_path.name)
            return real(path, maximum, expected, target=target)
        with mock.patch.object(self.activation, "_fingerprint", side_effect=no_lock):
            self.assertEqual(self.run_activation()["status"], "ACTIVATED")
        self.assertEqual(self.lock_path.read_bytes(), b"\x00")

    def test_one_lock_excludes_cooperating_writer_and_builder_through_backup_and_cutover(self):
        real = self.activation._backup
        writer = self.writer_module.LearningMemory(str(self.learning))
        def checked(base, destination):
            row = self.history_row()
            args = {name: row[name] for name in ("raw_text", "final_text", "meta", "mode", "accepted", "immediate_label", "missing_slots")}
            with self.assertRaises(self.runtime.RuntimeRefused) as caught:
                writer.log_command(**args)
            self.assertEqual(caught.exception.reason, "BUSY")
            self.assertEqual(self.runtime.build_learning_corrections(self.repo)["reason"], "BUSY")
            return real(base, destination)
        with mock.patch.object(self.activation, "_backup", side_effect=checked):
            result = self.run_activation()
        self.assertEqual(result["status"], "ACTIVATED")
        self.assertEqual(self.history.read_bytes(), b"")

    def test_postcheck_real_change_is_reported_without_automatic_restore(self):
        real = self.runtime._activate_learning_evidence_locked
        changed = self.encoded([self.history_row()])
        def after(root, base):
            result = real(root, base)
            self.history.write_bytes(changed)
            return result
        with mock.patch.object(self.runtime, "_activate_learning_evidence_locked", side_effect=after):
            result = self.run_activation()
        self.assertEqual((result["reason"], result["history_preserved"]), ("HISTORY_CHANGED", False))
        self.assertEqual(self.history.read_bytes(), changed)
        self.assertEqual((self.backup / "before/data/learning/command_history.jsonl").read_bytes(), b"")

    def test_postcheck_unreadable_input_is_unknown_not_confirmed_changed(self):
        real = self.activation._verify_inputs
        def unreadable(base, before, fingerprints, names):
            if names == ("command_history.jsonl",):
                raise OSError(SECRET)
            return real(base, before, fingerprints, names)
        with mock.patch.object(self.activation, "_verify_inputs", side_effect=unreadable):
            result = self.run_activation()
        self.assertEqual((result["reason"], result["history_preserved"]), ("POSTCHECK_FAILED", None))
        self.assertEqual(result["activation_status"], "ACTIVATED")

    def test_existing_backup_and_project_local_destinations_are_refused_without_overwrite(self):
        existing = self.backups / "existing"
        existing.mkdir()
        marker = existing / "marker"
        marker.write_bytes(SECRET.encode())
        for path, reason in ((existing, "BACKUP_EXISTS"), (self.repo / "backup", "BACKUP_IN_PROJECT"),
                             (self.root, "BACKUP_IN_PROJECT")):
            result = self.activation.activate_correction_evidence_safely(self.repo, path)
            self.assertTrue(self.activation.validate_public_result(result))
            self.assertEqual(result["reason"], reason)
        self.assertEqual(marker.read_bytes(), SECRET.encode())
        self.assert_not_activated()

    def test_hardlink_or_symlink_inputs_are_refused_without_following_them(self):
        external = self.root / "private external history"
        external.write_bytes(self.encoded([self.history_row()]))
        self.history.unlink()
        os.link(external, self.history)
        result = self.run_activation()
        self.assertEqual(result["reason"], "UNSAFE_PATH")
        self.assert_not_activated()
        self.history.unlink()
        try:
            self.history.symlink_to(external)
        except OSError:
            # The hardlink case above remains mandatory on Windows without
            # developer-mode symlink privileges; no test is reported skipped.
            self.history.write_bytes(b"")
        else:
            result = self.run_activation()
            self.assertEqual(result["reason"], "UNSAFE_PATH")
            self.assert_not_activated()
        self.assertEqual(external.read_bytes(), self.encoded([self.history_row()]))

    def test_bounded_inventory_refuses_large_inputs_before_copy_or_activation(self):
        self.history.write_bytes(b"abc\n")
        limits = dict(self.activation.FILES)
        limits["command_history.jsonl"] = 1
        with mock.patch.object(self.activation, "FILES", limits), \
                mock.patch.object(self.activation, "_fingerprint") as copied:
            result = self.run_activation()
        self.assertEqual(result["reason"], "RESOURCE_LIMIT")
        copied.assert_not_called()
        self.assert_not_activated()

    def test_missing_history_refuses_without_fabricating_or_creating_it(self):
        self.history.unlink()
        result = self.run_activation()
        self.assertEqual((result["reason"], result["activation_status"]), ("HISTORY_REFUSED", "NOT_RUN"))
        self.assertFalse(self.history.exists())
        self.assert_not_activated()

    def test_public_schema_rejects_private_additions_false_success_and_boolean_counts(self):
        result = self.run_activation()
        self.assertEqual(result["status"], "ACTIVATED")
        for changed in (dict(result, private=SECRET), dict(result, reason=SECRET),
                        dict(result, history_rows=True), dict(result, activation_status="NOT_RUN"),
                        dict(result, scope=dict(result["scope"], training_run=True)),
                        dict(result, pairs_after=1)):
            self.assertFalse(self.activation.validate_public_result(changed))

    def test_unrelated_environment_model_logs_and_data_are_not_changed(self):
        sentinel_paths = (self.repo / ".env", self.repo / "models/nlu_intent.joblib",
                          self.repo / "logs/old.log", self.learning / "other_history.jsonl")
        for path in sentinel_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(SECRET.encode())
        self.assertEqual(self.run_activation()["status"], "ACTIVATED")
        self.assertEqual({path.read_bytes() for path in sentinel_paths}, {SECRET.encode()})
        backup_names = {path.name for path in (self.backup / "before/data/learning").iterdir()}
        self.assertEqual(backup_names, {"command_history.jsonl"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
