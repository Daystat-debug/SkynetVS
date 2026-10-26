"""Correction-memory regression checks; only owned synthetic histories are used."""
from __future__ import annotations

from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True


class CorrectionMemoryIdempotenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_correction_snapshot_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.memory_module = self.load("correction_memory", "modules/learning/correction_memory.py")
        self.analyzer_module = self.load("feedback_analyzer", "modules/learning/feedback_analyzer.py")
        self.memory_path = self.root / "memory.jsonl"
        self.memory = self.memory_module.CorrectionMemory(str(self.memory_path))
        self.source = "feedback_analyzer_v2"

    def load(self, name, relative):
        spec = importlib.util.spec_from_file_location("snapshot_test_" + name, PROJECT_ROOT / relative)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def pair(count=1, **changes):
        row = {
            "failed_text": "мне нужен текстовый редактор",
            "corrected_text": "открой блокнот",
            "corrected_intent": "OPEN_APP",
            "corrected_confidence": 0.9,
            "corrected_slots": {"app": "notepad"},
            "count": count,
        }
        row.update(changes)
        return row

    def sync(self, pairs=None, *, source=None):
        return self.memory.sync_cumulative_candidates(
            [self.pair()] if pairs is None else pairs,
            source=self.source if source is None else source,
        )

    def rows(self):
        return [json.loads(line) for line in self.memory_path.read_text(encoding="utf-8").splitlines() if line]

    def write_rows(self, rows):
        self.memory_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    def legacy(self, count=99):
        candidate = self.pair()
        return {
            "key": self.memory._make_key(candidate["failed_text"], candidate["corrected_text"], candidate["corrected_intent"]),
            "created_ts": "2020-01-02T03:04:05", "last_seen_ts": "2020-01-03T03:04:05",
            "seen_count": count, "status": "reviewed",
            **{k: v for k, v in candidate.items() if k != "count"},
            "sources": ["old_source", self.source], "custom": {"keep": ["untouched"]},
        }

    def prepare_cli(self):
        project = self.root / "isolated project"
        for relative in ("modules/learning/correction_memory.py",
                         "modules/learning/feedback_analyzer.py", "tools/build_correction_memory.py"):
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT_ROOT / relative, target)
        for relative in ("modules/__init__.py", "modules/learning/__init__.py"):
            (project / relative).write_text("", encoding="utf-8")
        learning = project / "data/learning"
        learning.mkdir(parents=True)
        return project, learning

    @staticmethod
    def history_pair(index=0, failed="мне нужен текстовый редактор", corrected="открой блокнот"):
        moment = datetime(2026, 1, 1) + timedelta(minutes=index * 2)
        return [
            {"ts": moment.isoformat(), "raw_text": failed, "final_text": failed,
             "accepted": False, "missing_slots": [], "meta": {"intent": "UNKNOWN", "confidence": 0.1, "slots": {}}},
            {"ts": (moment + timedelta(seconds=2)).isoformat(), "raw_text": corrected,
             "final_text": corrected, "accepted": True, "missing_slots": [],
             "meta": {"intent": "OPEN_APP", "confidence": 0.9, "slots": {"app": "notepad"}}},
        ]

    @staticmethod
    def write_history(learning, rows):
        (learning / "command_history.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    def run_cli(self, project):
        bootstrap = (
            "import runpy,sys; sys.path.insert(0," + repr(str(project)) + "); "
            "runpy.run_path(" + repr(str(project / "tools/build_correction_memory.py")) + ",run_name='__main__')"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", bootstrap],
            cwd=project, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_cli_replay_preserves_bytes_and_timestamp(self):
        project, learning = self.prepare_cli()
        self.write_history(learning, self.history_pair())
        self.run_cli(project)
        target = learning / "correction_memory.jsonl"
        original, mtime = target.read_bytes(), target.stat().st_mtime_ns
        self.assertEqual(json.loads(original)["seen_count"], 1)
        self.run_cli(project)
        self.run_cli(project)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(target.stat().st_mtime_ns, mtime)

    def test_cli_growth_adds_only_new_evidence(self):
        project, learning = self.prepare_cli()
        history = self.history_pair()
        self.write_history(learning, history)
        self.run_cli(project)
        history += self.history_pair(1)
        self.write_history(learning, history)
        self.run_cli(project)
        target = learning / "correction_memory.jsonl"
        self.assertEqual(json.loads(target.read_bytes())["seen_count"], 2)
        original = target.read_bytes()
        self.run_cli(project)
        self.assertEqual(target.read_bytes(), original)

    def test_cli_consumes_all_pairs_but_default_report_stays_top_ten(self):
        project, learning = self.prepare_cli()
        history = []
        for index in range(12):
            history += self.history_pair(index, failed="исходная команда " + str(index))
        self.write_history(learning, history)
        analyzer = self.analyzer_module.FeedbackAnalyzer(str(learning))
        self.assertEqual(len(analyzer.analyze()["correction_pairs"]), 10)
        self.run_cli(project)
        target = learning / "correction_memory.jsonl"
        rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row["seen_count"] == 1 for row in rows))
        before = target.read_bytes()
        self.run_cli(project)
        self.assertEqual(target.read_bytes(), before)

    def test_normalized_variants_are_summed_before_checkpoint(self):
        pairs = [
            self.pair(2, failed_text="  ОТКРОЙ   НАТПАД ", corrected_text=" ОТКРОЙ БЛОКНОТ "),
            self.pair(3, failed_text="открой натпад", corrected_intent=" open_app "),
        ]
        stats = self.sync(pairs)
        row = self.rows()[0]
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(row["seen_count"], 5)
        self.assertEqual(row["cumulative_evidence"][self.source]["observed_count"], 5)
        self.assertEqual(stats["processed"], 1)
        original = self.memory_path.read_bytes()
        with mock.patch.object(self.memory, "_now", side_effect=AssertionError("No new evidence")):
            self.sync(list(reversed(pairs)))
        self.assertEqual(self.memory_path.read_bytes(), original)
        pairs[1]["count"] = 4
        self.sync(pairs)
        self.assertEqual(self.rows()[0]["seen_count"], 6)

    def test_new_snapshot_tracks_actual_total_and_replay_is_no_op(self):
        self.sync([self.pair(3)])
        row = self.rows()[0]
        self.assertEqual(row["seen_count"], 3)
        self.assertFalse(row["cumulative_evidence"][self.source]["legacy_baseline"])
        original = self.memory_path.read_bytes()
        with mock.patch.object(self.memory, "_now", side_effect=AssertionError("No new evidence")), \
                mock.patch.object(self.memory, "_write_snapshot", side_effect=AssertionError("No write")):
            stats = self.sync([self.pair(3)])
        self.assertFalse(stats["written"])
        self.assertEqual(stats["unchanged"], 1)
        self.assertEqual(self.memory_path.read_bytes(), original)

    def test_legacy_baseline_preserves_all_old_fields_and_timestamps(self):
        legacy = self.legacy()
        self.write_rows([legacy])
        with mock.patch.object(self.memory, "_now", side_effect=AssertionError("Baseline is not an event")):
            stats = self.sync([self.pair(5, corrected_confidence=0.95, corrected_slots={"app": "new"})])
        row = self.rows()[0]
        self.assertEqual({k: v for k, v in row.items() if k != "cumulative_evidence"}, legacy)
        self.assertEqual(row["cumulative_evidence"][self.source],
                         {"version": 1, "observed_count": 5, "legacy_baseline": True})
        self.assertEqual(stats["baselined"], 1)
        before = self.memory_path.read_bytes()
        self.sync([self.pair(5)])
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_legacy_growth_adds_delta_without_repairing_unknown_inflation(self):
        legacy = self.legacy()
        self.write_rows([legacy])
        self.sync([self.pair(5)])
        with mock.patch.object(self.memory, "_now", return_value="2026-01-02T03:04:05"):
            self.sync([self.pair(7)])
        row = self.rows()[0]
        self.assertEqual(row["seen_count"], 101)
        self.assertEqual(row["created_ts"], legacy["created_ts"])
        self.assertEqual(row["last_seen_ts"], "2026-01-02T03:04:05")
        self.assertEqual(row["status"], legacy["status"])
        self.assertEqual(row["custom"], legacy["custom"])

    def test_lower_total_retains_high_water_and_does_not_claim_new_events(self):
        self.sync([self.pair(5)])
        before = self.memory_path.read_bytes()
        with mock.patch.object(self.memory, "_now", side_effect=AssertionError("Lower total is ambiguous")):
            stats = self.sync([self.pair(2)])
            self.sync([self.pair(4)])
            self.sync([self.pair(5)])
        self.assertEqual(stats["lower_totals"], 1)
        self.assertEqual(self.memory_path.read_bytes(), before)
        self.sync([self.pair(6)])
        self.assertEqual(self.rows()[0]["seen_count"], 6)

    def test_empty_snapshot_preserves_absent_rows_and_creates_no_file(self):
        stats = self.sync([])
        self.assertFalse(stats["written"])
        self.assertFalse(self.memory_path.exists())
        self.sync()
        before = self.memory_path.read_bytes()
        self.sync([])
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_unrelated_rows_unknown_fields_and_status_are_preserved(self):
        first, other = self.legacy(4), self.legacy(12)
        other["key"] = "different | corrected | UNKNOWN"
        other["status"] = "rejected"
        other["unknown_metadata"] = {"nested": [1, 2, 3]}
        self.write_rows([first, other])
        self.sync([self.pair(4)])
        self.sync([self.pair(5)])
        rows = self.rows()
        self.assertEqual(rows[1], other)
        self.assertEqual(rows[0]["custom"], first["custom"])
        self.assertEqual(rows[0]["status"], first["status"])

    def test_existing_additive_upsert_contract_remains_available(self):
        self.sync([self.pair(2)])
        row = self.pair()
        self.memory.upsert_candidate(**{k: v for k, v in row.items() if k != "count"},
                                     evidence_count=3, source="explicit_new_events")
        self.assertEqual(self.rows()[0]["seen_count"], 5)
        before = self.memory_path.read_bytes()
        self.sync([self.pair(2)])
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_source_checkpoints_are_independent_and_new_source_is_baselined(self):
        self.sync([self.pair(2)], source="first")
        self.sync([self.pair(20)], source="second")
        self.assertEqual(self.rows()[0]["seen_count"], 2)
        self.sync([self.pair(21)], source="second")
        row = self.rows()[0]
        self.assertEqual(row["seen_count"], 3)
        self.assertEqual(row["cumulative_evidence"]["first"]["observed_count"], 2)
        self.assertEqual(row["cumulative_evidence"]["second"]["observed_count"], 21)

    def test_same_count_metadata_changes_do_not_invent_new_observation(self):
        self.sync([self.pair(2)])
        before = self.memory_path.read_bytes()
        with mock.patch.object(self.memory, "_now", side_effect=AssertionError("No new evidence")):
            self.sync([self.pair(2, corrected_confidence=0.99, corrected_slots={"app": "changed"})])
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_growth_merges_metadata_and_keeps_first_creation_time(self):
        self.sync([self.pair(1, corrected_confidence=0.5, corrected_slots={"app": "notepad", "keep": "yes"})])
        created = self.rows()[0]["created_ts"]
        self.sync([self.pair(2, corrected_confidence=0.9, corrected_slots={"app": "notepad2"})])
        row = self.rows()[0]
        self.assertEqual(row["corrected_confidence"], 0.9)
        self.assertEqual(row["corrected_slots"], {"app": "notepad2", "keep": "yes"})
        self.assertEqual(row["created_ts"], created)

    def test_replays_do_not_cross_real_promotion_gates_but_new_evidence_can(self):
        promotion = self.load("promotion_engine", "modules/learning/promotion_engine.py")
        for failed, threshold, expected in (
                ("мне нужен текстовый редактор", 3, "intent_example"),
                ("открой текстовый редактор", 2, "entity_alias")):
            with self.subTest(promotion_type=expected):
                path = self.root / ("promotion_" + expected + ".jsonl")
                memory = self.memory_module.CorrectionMemory(str(path))
                pair = self.pair(failed_text=failed)
                memory.sync_cumulative_candidates([pair], source=self.source)
                before = path.read_bytes()
                for _ in range(3):
                    memory.sync_cumulative_candidates([pair], source=self.source)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(promotion.classify_row(json.loads(path.read_bytes()))["promotion_type"],
                                     "phrase_correction")
                pair["count"] = threshold
                memory.sync_cumulative_candidates([pair], source=self.source)
                result = promotion.classify_row(json.loads(path.read_bytes()))
                self.assertEqual(result["seen_count"], threshold)
                self.assertEqual(result["promotion_type"], expected)

    def test_invalid_candidate_later_in_batch_cannot_partially_write(self):
        self.sync()
        before = self.memory_path.read_bytes()
        with self.assertRaises((ValueError, TypeError)):
            self.sync([self.pair(2), self.pair("not-a-count", failed_text="another")])
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_malformed_or_nonobject_memory_is_refused_without_rewriting(self):
        for raw in (b"{broken}\n", b"[]\n", b"null\n", b"12\n",
                    b'{"key":"first","key":"duplicate","seen_count":1}\n',
                    b'{"key":"x","seen_count":NaN}\n'):
            with self.subTest(raw=raw):
                self.memory_path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.sync()
                self.assertEqual(self.memory_path.read_bytes(), raw)

    def test_duplicate_existing_keys_are_refused_without_rewriting(self):
        self.write_rows([self.legacy(), self.legacy()])
        before = self.memory_path.read_bytes()
        with self.assertRaises(ValueError):
            self.sync()
        self.assertEqual(self.memory_path.read_bytes(), before)

    def test_invalid_tracking_state_is_refused_before_write(self):
        for state in ([], {"x": -1}, {"x": {"version": 2, "observed_count": 1, "legacy_baseline": False}},
                      {"x": {"version": 1, "observed_count": "3", "legacy_baseline": False}},
                      {"x": {"version": 1, "observed_count": -1, "legacy_baseline": False}}):
            with self.subTest(state=state):
                row = self.legacy()
                row["cumulative_evidence"] = state
                self.write_rows([row])
                before = self.memory_path.read_bytes()
                with self.assertRaises(ValueError):
                    self.sync()
                self.assertEqual(self.memory_path.read_bytes(), before)

    def test_bad_count_or_nonfinite_confidence_is_refused_without_write(self):
        self.sync()
        before = self.memory_path.read_bytes()
        for pair in (self.pair(0), self.pair(-1), self.pair(True), self.pair(1.5),
                     self.pair(corrected_slots=[]),
                     self.pair(corrected_confidence=float("nan")),
                     self.pair(corrected_confidence=float("inf"))):
            with self.subTest(pair=pair):
                with self.assertRaises(ValueError):
                    self.sync([pair])
                self.assertEqual(self.memory_path.read_bytes(), before)

    def test_serialization_failure_preserves_original_memory(self):
        self.sync()
        before = self.memory_path.read_bytes()
        with self.assertRaises((ValueError, TypeError)):
            self.sync([self.pair(2, corrected_slots={"not_serializable": object()})])
        self.assertEqual(self.memory_path.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.memory_path])

    def test_atomic_replace_failure_preserves_original_and_removes_temporary(self):
        self.sync()
        before = self.memory_path.read_bytes()
        with mock.patch.object(self.memory_module.os, "replace", side_effect=OSError("synthetic replace failure")):
            with self.assertRaises(OSError):
                self.sync([self.pair(2)])
        self.assertEqual(self.memory_path.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.memory_path])

    def test_atomic_flush_failure_preserves_original_and_removes_temporary(self):
        self.sync()
        before = self.memory_path.read_bytes()
        with mock.patch.object(self.memory_module.os, "fsync", side_effect=OSError("synthetic fsync failure")):
            with self.assertRaises(OSError):
                self.sync([self.pair(2)])
        self.assertEqual(self.memory_path.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.memory_path])


if __name__ == "__main__":
    unittest.main(verbosity=2)
