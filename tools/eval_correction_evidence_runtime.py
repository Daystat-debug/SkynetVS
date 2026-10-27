"""Named synthetic checks of explicit correction-evidence runtime activation.

Only disposable local repositories and their private sentinels are accessed.
Real package initializers, the application, models and training are not loaded.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-private-runtime-marker-96"
CHILDREN = ("correction_pair_evidence", "learning_history_snapshot", "correction_evidence_ledger",
            "correction_memory", "feedback_analyzer", "correction_evidence_projection",
            "correction_evidence_runtime", "learning_memory")


class CorrectionEvidenceRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_evidence_runtime_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo with spaces # unicode-я"
        self.learning = self.repo / "data" / "learning"
        self.learning.mkdir(parents=True)
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
        self.runtime = package.correction_evidence_runtime
        self.ledger = package.correction_evidence_ledger
        self.projection = package.correction_evidence_projection
        self.memory_module = package.correction_memory
        self.analyzer = package.feedback_analyzer
        self.writer_module = package.learning_memory
        self.writer = self.writer_module.LearningMemory(str(self.learning))

    @staticmethod
    def arguments(*, accepted=True):
        text = "открой блокнот" if accepted else "запусти редактор"
        return {"raw_text": text, "final_text": text,
                "meta": {"intent": "OPEN_APP" if accepted else None,
                         "confidence": 0.9 if accepted else 0.1,
                         "slots": {"app": "notepad"} if accepted else {}, "say": "", "_text": ""},
                "mode": "text", "accepted": accepted, "immediate_label": "synthetic", "missing_slots": []}

    def log_pair(self, *, index=0, writer=None):
        moment = datetime(2026, 1, 1, 12) + timedelta(minutes=index * 2)
        with mock.patch.object(self.writer_module, "datetime") as clock:
            clock.now.side_effect = [moment, moment + timedelta(seconds=2)]
            (writer or self.writer).log_command(**self.arguments(accepted=False))
            (writer or self.writer).log_command(**self.arguments())

    @staticmethod
    def legacy_row():
        return {"key": "запусти редактор | открой блокнот | OPEN_APP", "seen_count": 37,
                "failed_text": "запусти редактор", "corrected_text": "открой блокнот",
                "corrected_intent": "OPEN_APP", "corrected_confidence": 0.5,
                "corrected_slots": {"legacy": "retained"}, "status": "rejected",
                "created_ts": "2020-01-01T00:00:00", "last_seen_ts": "2020-01-02T00:00:00",
                "sources": ["feedback_analyzer_v2", "manual"], "custom": {"value": SECRET},
                "cumulative_evidence": {"feedback_analyzer_v2":
                    {"version": 1, "observed_count": 12, "legacy_baseline": True}}}

    def write_memory(self, rows):
        self.memory_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    def memory_rows(self):
        return [json.loads(line) for line in self.memory_path.read_text(encoding="utf-8").splitlines() if line]

    def history_rows(self):
        return [json.loads(line) for line in self.history.read_text(encoding="utf-8").splitlines() if line]

    def control(self):
        return self.runtime.read_learning_evidence_control(self.learning)

    def activate(self):
        result = self.runtime.activate_learning_evidence(self.repo)
        self.assertEqual(result["status"], "ACTIVATED", result)
        self.assertEqual(self.control()["state"], "ACTIVE")
        return self.control()["epoch"]

    def build(self):
        return self.runtime.build_learning_corrections(self.repo)

    def preparing_with_ledger(self):
        with mock.patch.object(self.runtime, "_activate_control", side_effect=OSError(SECRET)):
            result = self.runtime.activate_learning_evidence(self.repo)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(self.control(), {"state": "PREPARING", "epoch": None})
        self.assertTrue(self.database.exists())

    def test_legacy_builder_counts_all_pairs_and_replay_preserves_memory(self):
        self.log_pair()
        self.log_pair(index=1)
        result = self.build()
        self.assertEqual((result["status"], result["mode"]), ("LEGACY", "LEGACY"))
        self.assertEqual(self.memory_rows()[0]["seen_count"], 2)
        before = self.memory_path.read_bytes()
        self.assertEqual(self.build()["stats"]["new_evidence"], 0)
        self.assertEqual(self.memory_path.read_bytes(), before)
        self.assertFalse(self.control_path.exists())
        self.assertFalse(self.database.exists())
        self.assertEqual(self.lock_path.read_bytes(), b"\x00")
        self.assertTrue(all("evidence_epoch" not in row for row in self.history_rows()))

    def test_activation_preserves_history_memory_and_unrelated_private_sentinels(self):
        self.log_pair()
        self.write_memory([self.legacy_row()])
        sentinels = {self.repo / ".env": (SECRET + "-env").encode(),
                     self.repo / "models/nlu_intent.joblib": (SECRET + "-model").encode()}
        for path, raw in sentinels.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        before = {path: path.read_bytes() for path in (self.history, self.memory_path, *sentinels)}
        with mock.patch.object(self.analyzer.FeedbackAnalyzer, "analyze", side_effect=AssertionError("No legacy count")):
            self.activate()
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(self.ledger.read_correction_evidence_totals(self.repo)["pair_count"], 0)

    def test_preexisting_writer_instance_stamps_only_new_commands_after_activation(self):
        self.log_pair()
        before = self.history.read_bytes()
        epoch = self.activate()
        self.log_pair(index=1)
        self.assertEqual(self.history.read_bytes()[:len(before)], before)
        rows = self.history_rows()
        self.assertTrue(all("evidence_epoch" not in row for row in rows[:2]))
        self.assertEqual([row["evidence_epoch"] for row in rows[2:]], [epoch, epoch])

    def test_active_projection_adds_first_new_pair_to_legacy_count_and_replay_is_zero(self):
        legacy = self.legacy_row()
        self.write_memory([legacy])
        self.activate()
        self.log_pair()
        result = self.build()
        self.assertEqual((result["status"], result["mode"]), ("APPLIED", "EVENT"))
        self.assertEqual(result["stats"]["new_evidence"], 1)
        row = self.memory_rows()[0]
        self.assertEqual(row["seen_count"], 38)
        for field in ("status", "custom", "created_ts", "cumulative_evidence"):
            self.assertEqual(row[field], legacy[field])
        self.assertEqual(row["event_evidence"]["observed_count"], 1)
        before = self.memory_path.read_bytes()
        self.assertEqual(self.build()["status"], "UNCHANGED")
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_active_builder_never_calls_legacy_analyzer_or_cumulative_api(self):
        self.activate()
        self.log_pair()
        with mock.patch.object(self.analyzer.FeedbackAnalyzer, "analyze", side_effect=AssertionError("Legacy analyzer")), \
                mock.patch.object(self.memory_module.CorrectionMemory, "sync_cumulative_candidates",
                                  side_effect=AssertionError("Legacy cumulative API")):
            self.assertEqual(self.build()["status"], "APPLIED")

    def test_pending_activation_blocks_builder_but_logs_unstamped_observations(self):
        self.preparing_with_ledger()
        self.log_pair()
        self.assertTrue(all("evidence_epoch" not in row for row in self.history_rows()))
        with mock.patch.object(self.analyzer.FeedbackAnalyzer, "analyze", side_effect=AssertionError("No fallback")):
            result = self.build()
        self.assertEqual(result["reason"], "ACTIVATION_PENDING")
        self.assertFalse(self.memory_path.exists())

    def test_initializer_failure_leaves_preparing_and_explicit_retry_resumes(self):
        with mock.patch.object(self.ledger, "initialize_correction_evidence_ledger",
                               return_value={"status": "REFUSED", "reason": "STORAGE_ERROR"}):
            result = self.runtime.activate_learning_evidence(self.repo)
        self.assertEqual(result["reason"], "LEDGER_INITIALIZATION_REFUSED")
        self.assertEqual(self.control()["state"], "PREPARING")
        self.assertFalse(self.database.exists())
        self.assertEqual(self.build()["reason"], "ACTIVATION_PENDING")
        self.activate()

    def test_active_control_replace_failure_resumes_existing_zero_pair_ledger(self):
        self.preparing_with_ledger()
        original = self.database.read_bytes()
        with mock.patch.object(self.ledger, "initialize_correction_evidence_ledger",
                               side_effect=AssertionError("Do not replace existing database")):
            self.activate()
        self.assertEqual(self.database.read_bytes(), original)

    def test_active_replace_success_then_exception_reconciles_without_reset(self):
        replace = self.runtime.os.replace
        def uncertain(source, target):
            replace(source, target)
            raise OSError(SECRET)
        with mock.patch.object(self.runtime.os, "replace", side_effect=uncertain):
            result = self.runtime.activate_learning_evidence(self.repo)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(self.control()["state"], "ACTIVE")
        before = (self.control_path.read_bytes(), self.database.read_bytes())
        self.assertEqual(self.runtime.activate_learning_evidence(self.repo)["status"], "UNCHANGED")
        self.assertEqual((self.control_path.read_bytes(), self.database.read_bytes()), before)

    def test_partial_preparing_file_is_preserved_and_never_replaced_automatically(self):
        with mock.patch.object(self.runtime, "_encoded_control", side_effect=RuntimeError(SECRET)):
            result = self.runtime.activate_learning_evidence(self.repo)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(self.control_path.read_bytes(), b"")
        self.assertEqual(self.runtime.activate_learning_evidence(self.repo)["reason"], "CONTROL_INVALID")
        self.assertEqual(self.build()["reason"], "CONTROL_INVALID")
        self.assertEqual(self.control_path.read_bytes(), b"")
        self.assertFalse(self.database.exists())

    def test_preparing_resume_revalidates_memory_without_replacing_ledger(self):
        self.preparing_with_ledger()
        before = self.database.read_bytes()
        self.memory_path.write_bytes((SECRET + " not JSON\n").encode())
        result = self.runtime.activate_learning_evidence(self.repo)
        self.assertEqual(result["reason"], "INPUT_INVALID")
        self.assertEqual(self.control()["state"], "PREPARING")
        self.assertEqual(self.database.read_bytes(), before)

    def test_preparing_with_already_accepted_pairs_refuses_ambiguous_activation(self):
        self.preparing_with_ledger()
        self.log_pair()
        rows = self.history_rows()
        epoch = self.ledger.read_correction_evidence_totals(self.repo)["epoch"]
        for row in rows:
            row["evidence_epoch"] = epoch
        self.history.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        self.assertEqual(self.ledger.sync_correction_evidence_ledger(self.repo)["stats"]["new_pairs"], 1)
        before = self.control_path.read_bytes()
        result = self.runtime.activate_learning_evidence(self.repo)
        self.assertEqual(result["reason"], "AMBIGUOUS_PREPARING_LEDGER")
        self.assertEqual(self.control_path.read_bytes(), before)

    def test_missing_active_ledger_refuses_without_recreation_or_legacy_fallback(self):
        self.activate()
        self.database.unlink()
        self.log_pair()
        before = self.history.read_bytes()
        with mock.patch.object(self.analyzer.FeedbackAnalyzer, "analyze", side_effect=AssertionError("No fallback")):
            result = self.build()
        self.assertEqual((result["reason"], result["detail_reason"]), ("LEDGER_READ_REFUSED", "LEDGER_MISSING"))
        self.assertFalse(self.database.exists())
        self.assertFalse(self.memory_path.exists())
        self.assertEqual(self.history.read_bytes(), before)

    def test_wrong_epoch_refuses_before_ledger_binding_or_memory_mutation(self):
        self.activate()
        self.control_path.write_bytes(self.runtime._encoded_control("ACTIVE", "b" * 32))
        self.log_pair()
        before = self.database.read_bytes()
        result = self.build()
        self.assertEqual(result["reason"], "EPOCH_MISMATCH")
        self.assertEqual(self.database.read_bytes(), before)
        self.assertFalse(self.memory_path.exists())

    def test_orphan_database_or_sidecar_never_enables_legacy_fallback(self):
        for suffix in ("", "-journal", "-wal", "-shm"):
            with self.subTest(suffix=suffix):
                path = self.learning / (self.runtime.LEDGER_NAME + suffix)
                path.write_bytes(SECRET.encode())
                before = path.read_bytes()
                self.assertEqual(self.build()["reason"], "ORPHAN_LEDGER")
                self.assertEqual(self.runtime.activate_learning_evidence(self.repo)["reason"], "ORPHAN_LEDGER")
                self.assertEqual(path.read_bytes(), before)
                self.assertFalse(self.control_path.exists())
                path.unlink()

    def test_bad_control_schema_and_duplicate_fields_refuse_before_history_append(self):
        valid = {"kind": self.runtime.CONTROL_KIND, "version": 1, "state": "ACTIVE", "epoch": "a" * 32}
        fixtures = [b"", b"{", json.dumps(dict(valid, version=True)).encode(),
                    json.dumps(dict(valid, extra=SECRET)).encode(), json.dumps(dict(valid, epoch="bad")).encode(),
                    json.dumps(dict(valid, state="PREPARING")).encode(),
                    (json.dumps(valid)[:-1] + ',"epoch":"' + "b" * 32 + '"}').encode(),
                    b" " * (self.runtime.CONTROL_MAX_BYTES + 1)]
        for raw in fixtures:
            with self.subTest(length=len(raw)):
                self.control_path.write_bytes(raw)
                before = self.history.read_bytes()
                with self.assertRaisesRegex(self.runtime.RuntimeRefused, "CONTROL_INVALID"):
                    self.writer.log_command(**self.arguments())
                self.assertEqual(self.history.read_bytes(), before)
                self.assertEqual(self.build()["reason"], "CONTROL_INVALID")
                self.assertEqual(self.control_path.read_bytes(), raw)

    def test_malformed_memory_refuses_before_first_preparing_or_database_creation(self):
        raw = (SECRET + " invalid JSON\n").encode()
        self.memory_path.write_bytes(raw)
        self.assertEqual(self.runtime.activate_learning_evidence(self.repo)["reason"], "INPUT_INVALID")
        self.assertFalse(self.control_path.exists())
        self.assertFalse(self.database.exists())
        self.assertEqual(self.memory_path.read_bytes(), raw)

    def test_residual_event_checkpoint_blocks_legacy_and_activation_even_if_malformed(self):
        for checkpoint in (None, {}, {"version": 1, "epoch": "a" * 32, "observed_count": 1}):
            with self.subTest(checkpoint=checkpoint):
                self.write_memory([dict(self.legacy_row(), event_evidence=checkpoint)])
                before = self.memory_path.read_bytes()
                self.assertEqual(self.build()["reason"], "MISSING_CONTROL_STATE")
                self.assertEqual(self.runtime.activate_learning_evidence(self.repo)["reason"], "MISSING_CONTROL_STATE")
                self.assertFalse(self.control_path.exists())
                self.assertFalse(self.database.exists())
                self.assertEqual(self.memory_path.read_bytes(), before)

    def test_deleted_control_and_database_after_projection_do_not_reenable_legacy(self):
        self.activate()
        self.log_pair()
        self.assertEqual(self.build()["status"], "APPLIED")
        before = self.memory_path.read_bytes()
        self.control_path.unlink()
        self.database.unlink()
        self.assertEqual(self.build()["reason"], "MISSING_CONTROL_STATE")
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_reopened_writer_uses_active_epoch_without_reading_ledger(self):
        epoch = self.activate()
        writer = self.writer_module.LearningMemory(str(self.learning))
        with mock.patch.object(self.ledger, "read_correction_evidence_totals", side_effect=AssertionError("No database read")), \
                mock.patch.object(self.ledger, "sync_correction_evidence_ledger", side_effect=AssertionError("No database sync")):
            self.log_pair(writer=writer)
        self.assertEqual([row["evidence_epoch"] for row in self.history_rows()], [epoch, epoch])

    def test_caller_metadata_cannot_choose_top_level_epoch(self):
        epoch = self.activate()
        arguments = self.arguments()
        arguments["meta"]["evidence_epoch"] = "caller-marker"
        self.writer.log_command(**arguments)
        row = self.history_rows()[0]
        self.assertEqual(row["evidence_epoch"], epoch)
        self.assertNotIn("evidence_epoch", row["meta"])
        self.assertEqual(arguments["meta"]["evidence_epoch"], "caller-marker")

    def test_serialized_legacy_build_prevents_activation_and_command_interleaving(self):
        self.log_pair()
        analyze = self.analyzer.FeedbackAnalyzer.analyze
        def interleave(instance, **options):
            self.assertEqual(self.runtime.activate_learning_evidence(self.repo)["reason"], "BUSY")
            with self.assertRaisesRegex(self.runtime.RuntimeRefused, "BUSY"):
                self.writer.log_command(**self.arguments())
            self.assertFalse(self.control_path.exists())
            return analyze(instance, **options)
        with mock.patch.object(self.analyzer.FeedbackAnalyzer, "analyze", new=interleave):
            self.assertEqual(self.build()["status"], "LEGACY")
        self.assertEqual(self.memory_rows()[0]["seen_count"], 1)
        before = self.memory_path.read_bytes()
        self.activate()
        self.assertEqual(self.memory_path.read_bytes(), before)
        self.assertEqual(self.ledger.read_correction_evidence_totals(self.repo)["pair_count"], 0)

    def child_lock(self, *, crash=False):
        code = (
            "import importlib.util,os,sys; "
            "s=importlib.util.spec_from_file_location('isolated_lock_runtime',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
            "try:\n"
            " with m.learning_evidence_lock(sys.argv[2]):\n"
            "  print('ACQUIRED',flush=True)\n"
            + ("  os._exit(7)\n" if crash else "  pass\n") +
            "except m.RuntimeRefused as error:\n"
            " print(error.reason)\n"
        )
        return subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", code,
                               str(ROOT / "modules/learning/correction_evidence_runtime.py"), str(self.learning)],
                              capture_output=True, text=True, encoding="utf-8", timeout=15)

    def test_os_lock_blocks_other_process_and_releases_without_deleting_file(self):
        with self.runtime.learning_evidence_lock(self.learning):
            busy = self.child_lock()
            self.assertEqual((busy.returncode, busy.stdout.strip(), busy.stderr), (0, "BUSY", ""))
        original = self.lock_path.read_bytes()
        acquired = self.child_lock()
        self.assertEqual((acquired.returncode, acquired.stdout.strip(), acquired.stderr), (0, "ACQUIRED", ""))
        self.assertEqual(self.lock_path.read_bytes(), original)

    def test_process_exit_releases_lock_without_stale_file_cleanup(self):
        result = self.child_lock(crash=True)
        self.assertEqual((result.returncode, result.stdout.strip(), result.stderr), (7, "ACQUIRED", ""))
        before = self.lock_path.stat().st_ino
        with self.runtime.learning_evidence_lock(self.learning):
            self.assertEqual(self.lock_path.stat().st_ino, before)
        self.assertTrue(self.lock_path.exists())

    def test_invalid_lock_file_is_preserved_and_refused(self):
        self.lock_path.write_bytes(SECRET.encode())
        self.assertEqual(self.build()["reason"], "LOCK_INVALID")
        self.assertEqual(self.lock_path.read_bytes(), SECRET.encode())
        self.assertFalse(self.control_path.exists())

    def test_non_regular_control_is_refused_without_removal(self):
        self.control_path.mkdir()
        self.assertEqual(self.build()["reason"], "UNSAFE_PATH")
        self.assertTrue(self.control_path.is_dir())

    def test_failed_ledger_sync_does_not_call_projection_or_legacy(self):
        self.activate()
        with mock.patch.object(self.ledger, "sync_correction_evidence_ledger",
                               return_value={"status": "REFUSED", "reason": "COMMIT_OUTCOME_UNKNOWN"}), \
                mock.patch.object(self.projection, "project_correction_evidence", side_effect=AssertionError("No projection")), \
                mock.patch.object(self.analyzer.FeedbackAnalyzer, "analyze", side_effect=AssertionError("No fallback")):
            result = self.build()
        self.assertEqual((result["reason"], result["detail_reason"]),
                         ("LEDGER_SYNC_REFUSED", "COMMIT_OUTCOME_UNKNOWN"))
        self.assertFalse(self.memory_path.exists())

    def test_interruption_after_ledger_commit_replays_all_totals_next_build(self):
        self.write_memory([self.legacy_row()])
        self.activate()
        self.log_pair()
        before = self.memory_path.read_bytes()
        with mock.patch.object(self.projection, "project_correction_evidence", return_value={
                "status": "REFUSED", "reason": "MEMORY_WRITE_OUTCOME_UNKNOWN"}):
            failed = self.build()
        self.assertEqual(failed["reason"], "PROJECTION_REFUSED")
        self.assertEqual(self.memory_path.read_bytes(), before)
        self.assertEqual(self.ledger.read_correction_evidence_totals(self.repo)["pair_count"], 1)
        result = self.build()
        self.assertEqual(result["stats"]["new_evidence"], 1)
        self.assertEqual(self.memory_rows()[0]["seen_count"], 38)
        self.assertEqual(self.build()["stats"]["new_evidence"], 0)

    def test_restored_old_unstamped_history_never_becomes_new_evidence(self):
        self.log_pair()
        old = self.history.read_bytes()
        self.activate()
        self.log_pair(index=1)
        self.assertEqual(self.build()["stats"]["new_evidence"], 1)
        before = self.memory_path.read_bytes()
        self.history.write_bytes(old)
        self.assertEqual(self.build()["stats"]["new_evidence"], 0)
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_invalid_repo_is_a_fixed_refusal_without_sensitive_exception_text(self):
        for value in (None, {}, "relative", SECRET + "\x00", Path("relative")):
            with self.subTest(value_type=type(value).__name__):
                result = self.runtime.activate_learning_evidence(value)
                self.assertEqual(result["status"], "REFUSED")
                self.assertNotIn(SECRET, json.dumps(result))
        self.assertFalse(self.control_path.exists())

    def prepare_cli(self):
        for name in CHILDREN:
            target = self.repo / "modules/learning" / (name + ".py")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "modules/learning" / (name + ".py"), target)
        for relative in ("modules/__init__.py", "modules/learning/__init__.py"):
            (self.repo / relative).write_text("", encoding="utf-8")
        target = self.repo / "tools/build_correction_memory.py"
        target.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "tools/build_correction_memory.py", target)

    def run_cli(self, *options):
        bootstrap = "import runpy,sys; sys.path.insert(0,sys.argv[1]); del sys.argv[1]; runpy.run_path(sys.argv[0],run_name='__main__')"
        return subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                               "import sys; sys.argv[0]=sys.argv.pop(1); " + bootstrap,
                               str(self.repo / "tools/build_correction_memory.py"), str(self.repo), *options],
                              cwd=self.repo, capture_output=True, text=True, encoding="utf-8", timeout=20)

    def test_cli_activation_is_explicit_and_normal_build_does_not_train(self):
        self.prepare_cli()
        self.write_memory([self.legacy_row()])
        before = self.memory_path.read_bytes()
        legacy = self.run_cli()
        self.assertEqual(legacy.returncode, 0, legacy.stdout + legacy.stderr)
        self.assertIn("CORRECTION_RUNTIME_MODE=LEGACY", legacy.stdout)
        self.assertFalse(self.control_path.exists())
        activated = self.run_cli("--activate-evidence")
        self.assertEqual(activated.returncode, 0, activated.stdout + activated.stderr)
        self.assertIn("CORRECTION_RUNTIME_STATUS=ACTIVATED", activated.stdout)
        self.assertEqual(self.memory_path.read_bytes(), before)
        self.log_pair()
        built = self.run_cli()
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("CORRECTION_RUNTIME_MODE=EVENT", built.stdout)
        self.assertEqual(self.memory_rows()[0]["seen_count"], 38)
        self.assertNotIn(SECRET, legacy.stdout + activated.stdout + built.stdout)
        self.assertFalse((self.repo / "models").exists())

    def test_cli_refusal_uses_exit_two_and_does_not_print_private_content(self):
        self.prepare_cli()
        self.control_path.write_bytes(SECRET.encode())
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("CORRECTION_RUNTIME_REASON=CONTROL_INVALID", result.stdout)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertFalse(self.memory_path.exists())

    def isolated_processor(self, *, memory=None, logger_failure=False):
        children = ("command_learning", "command_outcome", "command_runtime",
                    "command_understanding", "hotword_utils", "command_processor")
        absent = object()
        previous = {"modules." + name: sys.modules.get("modules." + name, absent) for name in children}
        def restore():
            for name, value in previous.items():
                if value is absent:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
        self.addCleanup(restore)
        self.processor_actions = []
        self.processor_notices = []
        decision = SimpleNamespace(accepted=True, missing_slots=[])
        meta = {"intent": "OPEN_APP", "confidence": 0.9, "slots": {"app": "notepad"}}
        def understand(text, **options):
            return SimpleNamespace(raw_text=text, final_text=text, meta=dict(meta), decision=decision)
        def runtime(**options):
            options["router"].execute(options["meta"])
            return SimpleNamespace(meta=options["meta"], reason="executed", last_tts_end=None)
        for name, attrs in {
            "command_outcome": {"classify_command_outcome": lambda meta, decision: SimpleNamespace(kind="execute")},
            "command_runtime": {"handle_command_runtime": runtime},
            "command_understanding": {"understand_command_text": understand},
            "hotword_utils": {"norm_text": lambda value: " ".join(value.split())},
        }.items():
            module = ModuleType("modules." + name)
            for attr, value in attrs.items():
                setattr(module, attr, value)
            sys.modules[module.__name__] = module
        for name in ("command_learning", "command_processor"):
            full = "modules." + name
            spec = importlib.util.spec_from_file_location(full, ROOT / "modules" / (name + ".py"))
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[full] = module
            spec.loader.exec_module(module)
        def notice(kind, payload):
            if logger_failure:
                raise OSError(SECRET)
            self.processor_notices.append((kind, payload))
        return sys.modules["modules.command_processor"].CommandProcessor(
            router=SimpleNamespace(execute=lambda value: self.processor_actions.append(value)),
            logger=SimpleNamespace(event=notice), whisper=None, stt=object(), tts=object(),
            settings=SimpleNamespace(nlu_accept_conf=0.5, whisper_trigger_conf=0.4, hotwords=[]),
            learning_memory=memory or self.writer, mode_manager=object(),
            say_func=lambda *args, **kwargs: 0.0, say_interruptible_func=lambda *args, **kwargs: 0.0,
            reply_text_func=lambda value: "", current_mode_name_func=lambda: "text",
            cancel_cmd_timer_func=lambda: None, print_func=None)

    def test_real_command_processor_dispatches_action_when_observation_lock_is_busy(self):
        processor = self.isolated_processor()
        before = self.history.read_bytes()
        with self.runtime.learning_evidence_lock(self.learning):
            result = processor.process(SECRET, immediate_label="immediate")
        self.assertEqual(result.reason, "executed")
        self.assertEqual(len(self.processor_actions), 1)
        self.assertEqual(self.history.read_bytes(), before)
        self.assertEqual(self.processor_notices, [("learning_observation_unconfirmed", {
            "reason": "BUSY", "observation_status": "NOT_CONFIRMED", "retry_queued": False})])
        self.assertNotIn(SECRET, json.dumps(self.processor_notices))

    def test_real_command_processor_continues_after_invalid_learning_control(self):
        self.control_path.write_bytes(SECRET.encode())
        processor = self.isolated_processor()
        result = processor.process(SECRET, immediate_label="immediate")
        self.assertEqual(result.reason, "executed")
        self.assertEqual(len(self.processor_actions), 1)
        self.assertEqual(self.history.read_bytes(), b"")
        self.assertEqual(self.processor_notices[0][1]["reason"], "CONTROL_INVALID")
        self.assertNotIn(SECRET, json.dumps(self.processor_notices))

    def test_real_command_processor_does_not_swallow_unrelated_programmer_error(self):
        memory = SimpleNamespace(log_command=mock.Mock(side_effect=RuntimeError("synthetic programmer error")))
        processor = self.isolated_processor(memory=memory)
        with self.assertRaisesRegex(RuntimeError, "synthetic programmer error"):
            processor.process(SECRET, immediate_label="immediate")
        self.assertEqual(self.processor_actions, [])
        self.assertEqual(self.processor_notices, [])

    def test_real_command_processor_diagnostic_failure_does_not_stop_action(self):
        processor = self.isolated_processor(logger_failure=True)
        with self.runtime.learning_evidence_lock(self.learning):
            result = processor.process(SECRET, immediate_label="immediate")
        self.assertEqual(result.reason, "executed")
        self.assertEqual(len(self.processor_actions), 1)
        self.assertEqual(self.history.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main(verbosity=2)
