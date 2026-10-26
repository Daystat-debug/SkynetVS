"""Synthetic-only regression checks for the read-only learning-data diagnostic."""
from __future__ import annotations

import builtins
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
SECRET = "PRIVATE_CANARY_729410_DO_NOT_EMIT"


class LearningDataAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_learning_audit_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.learning = self.root / "data/learning"
        self.learning.mkdir(parents=True)
        self.history_path = self.learning / "command_history.jsonl"
        self.memory_path = self.learning / "correction_memory.jsonl"
        specification = importlib.util.spec_from_file_location(
            "standalone_learning_audit_test", PROJECT_ROOT / "tools/audit_learning_data.py")
        assert specification is not None and specification.loader is not None
        self.audit = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(self.audit)

    @staticmethod
    def history(**changes):
        row = {"ts": "2026-01-01T12:00:00", "raw_text": "открой блокнот",
               "final_text": "открой блокнот", "mode": "text", "accepted": True,
               "immediate_label": "accepted", "missing_slots": [],
               "meta": {"intent": "OPEN_APP", "confidence": 0.9, "slots": {"app": "notepad"},
                        "say": "готово", "_text": "открой блокнот"}}
        row.update(changes)
        return row

    @staticmethod
    def memory(**changes):
        row = {"key": "запусти редактор | открой блокнот | OPEN_APP", "seen_count": 3,
               "failed_text": "запусти редактор", "corrected_text": "открой блокнот",
               "corrected_intent": "OPEN_APP", "corrected_confidence": 0.9,
               "corrected_slots": {"app": "notepad"}, "sources": ["feedback_analyzer_v2"],
               "created_ts": "2026-01-01T12:00:00", "last_seen_ts": "2026-01-01T12:00:01",
               "status": "candidate", "cumulative_evidence": {
                   "feedback_analyzer_v2": {"version": 1, "observed_count": 3, "legacy_baseline": False}}}
        row.update(changes)
        return row

    @staticmethod
    def write_rows(path, rows):
        path.write_text("".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows), encoding="utf-8")

    def valid_inputs(self):
        self.write_rows(self.history_path, [self.history()])
        self.write_rows(self.memory_path, [self.memory()])

    def run_audit(self):
        report = self.audit.audit_learning_data(self.root)
        self.assertTrue(self.audit.validate_public_report(report), report)
        encoded = json.dumps(report, sort_keys=True)
        self.assertNotIn(SECRET, encoded)
        self.assertNotIn(str(self.root), encoded)
        return report

    def findings(self, name="command_history"):
        return self.run_audit()["inputs"][name]["findings"]

    def cli(self, *arguments, script=None, cwd=None):
        return subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-X", "utf8",
             str(script or PROJECT_ROOT / "tools/audit_learning_data.py"), *map(str, arguments)],
            cwd=cwd or self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)

    def test_valid_current_writer_and_no_event_id_are_not_provenance_proof(self):
        self.valid_inputs()
        report = self.run_audit()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["inputs"]["command_history"]["observations"]["rows_without_event_id"], 1)
        self.assertFalse(report["scope"]["historical_counts_verified"])
        self.assertFalse(report["scope"]["stable_event_identity_verified"])

    def test_missing_both_is_distinct_from_missing_one(self):
        report = self.run_audit()
        self.assertEqual(report["status"], "INPUTS_MISSING")
        self.assertEqual(report["exit_code"], 2)
        self.write_rows(self.history_path, [self.history()])
        report = self.run_audit()
        self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
        self.assertEqual(report["inputs"]["command_history"]["object_rows"], 1)

    def test_empty_and_blank_inputs_do_not_claim_data_quality(self):
        self.history_path.write_bytes(b"")
        self.memory_path.write_bytes(b" \r\n\t\n")
        report = self.run_audit()
        self.assertEqual(report["status"], "NO_DATA_TO_CHECK")
        self.assertEqual(report["exit_code"], 2)
        self.assertTrue(all(item["state"] == "EMPTY" for item in report["inputs"].values()))

    def test_one_empty_input_is_explicit_and_other_input_can_be_checked(self):
        self.valid_inputs()
        self.memory_path.write_bytes(b"")
        report = self.run_audit()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertEqual(report["inputs"]["correction_memory"]["state"], "EMPTY")

    def test_malformed_utf8_json_partial_line_and_later_rows_are_counted(self):
        self.valid_inputs()
        row = json.dumps(self.history()).encode("utf-8")
        self.history_path.write_bytes(row + b"\n\n\xff\n{bad " + SECRET.encode() + b"\n" + row + b"\n{\"partial\":")
        item = self.run_audit()["inputs"]["command_history"]
        self.assertEqual(item["state"], "READ")
        self.assertEqual(item["lines_read"], 6)
        self.assertEqual(item["blank_lines"], 1)
        self.assertEqual(item["object_rows"], 2)
        self.assertEqual(item["findings"]["invalid_utf8_lines"], 1)
        self.assertEqual(item["findings"]["invalid_json_lines"], 2)

    def test_nonobject_json_rows_are_findings(self):
        self.valid_inputs()
        self.write_rows(self.history_path, [None, [], SECRET, 0, True])
        report = self.run_audit()
        self.assertEqual(report["status"], "FINDINGS_IN_CHECKED_STRUCTURE")
        self.assertEqual(report["inputs"]["command_history"]["findings"]["non_object_rows"], 5)

    def test_nested_and_top_level_duplicate_fields_are_rejected(self):
        self.valid_inputs()
        self.history_path.write_text('{"ts":1,"ts":2}\n{"meta":{"' + SECRET + '":1,"' + SECRET + '":2}}\n', encoding="utf-8")
        self.assertEqual(self.findings()["duplicate_field_lines"], 2)

    def test_nonfinite_literals_and_overflow_are_reported_without_traceback(self):
        self.valid_inputs()
        self.history_path.write_text("\n".join('{"value":' + value + "}" for value in ("NaN", "Infinity", "-Infinity", "1e400")), encoding="utf-8")
        self.assertEqual(self.findings()["non_finite_number_lines"], 4)

    def test_lone_surrogate_is_not_later_treated_as_portable_unicode(self):
        self.valid_inputs()
        row = self.history()
        row["raw_text"] = SECRET + "\ud800"
        self.write_rows(self.history_path, [row])
        self.assertEqual(self.findings()["invalid_unicode_lines"], 1)

    def test_rejected_null_intent_is_valid_accepted_without_intent_is_not(self):
        self.valid_inputs()
        row = self.history(accepted=False)
        row["meta"]["intent"] = None
        self.write_rows(self.history_path, [row])
        self.assertEqual(self.run_audit()["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        row["accepted"] = True
        self.write_rows(self.history_path, [row])
        self.assertEqual(self.findings()["accepted_without_intent_rows"], 1)

    def test_history_schema_types_do_not_crash(self):
        self.valid_inputs()
        rows = [self.history(raw_text=[], final_text=None, accepted=1, missing_slots="bad", mode=[], meta=[]),
                self.history(meta={"intent": [], "confidence": True, "slots": [], "say": {}})]
        self.write_rows(self.history_path, rows)
        findings = self.findings()
        for key in ("invalid_text_rows", "invalid_accepted_rows", "invalid_missing_slots_rows",
                    "invalid_meta_rows", "invalid_intent_rows", "invalid_confidence_rows", "invalid_slots_rows"):
            self.assertEqual(findings[key], 1, key)
        self.assertEqual(findings["invalid_auxiliary_text_rows"], 2)

    def test_confidence_bounds_and_huge_int_have_safe_diagnostic_codes(self):
        self.valid_inputs()
        self.write_rows(self.memory_path, [self.memory(corrected_confidence=10 ** 400),
                                          self.memory(corrected_confidence=-0.1),
                                          self.memory(corrected_confidence=1.1)])
        findings = self.findings("correction_memory")
        self.assertEqual(findings["invalid_confidence_rows"], 1)
        self.assertEqual(findings["confidence_out_of_range_rows"], 2)

    def test_history_timestamps_naive_aware_mixed_invalid_and_order(self):
        self.valid_inputs()
        self.write_rows(self.history_path, [
            self.history(ts="2026-01-01T12:00:02"), self.history(ts="2026-01-01T12:00:01"),
            self.history(ts="2026-01-01T12:00:04+01:00"), self.history(ts="2026-01-01T11:00:03Z"),
            self.history(ts=SECRET)])
        item = self.run_audit()["inputs"]["command_history"]
        self.assertEqual(item["findings"]["out_of_order_timestamp_rows"], 2)
        self.assertEqual(item["findings"]["mixed_timezone_files"], 1)
        self.assertEqual(item["findings"]["invalid_timestamp_rows"], 1)
        self.assertEqual(item["observations"]["naive_timestamp_values"], 2)
        self.assertEqual(item["observations"]["aware_timestamp_values"], 2)

    def test_aware_timestamps_and_invalid_fallback_are_findings(self):
        self.valid_inputs()
        self.write_rows(self.history_path, [self.history(ts="2026-01-01T12:00:00Z"), self.history(ts=None)])
        self.assertEqual(self.findings()["invalid_timestamp_rows"], 1)
        self.assertEqual(self.run_audit()["status"], "FINDINGS_IN_CHECKED_STRUCTURE")

    def test_event_ids_are_counted_without_claiming_stability(self):
        self.valid_inputs()
        self.write_rows(self.history_path, [self.history(event_id=SECRET), self.history(event_id=SECRET),
                                           self.history(event_id=0)])
        item = self.run_audit()["inputs"]["command_history"]
        self.assertEqual(item["findings"]["duplicate_event_id_rows"], 1)
        self.assertEqual(item["findings"]["invalid_event_id_rows"], 1)

    def test_key_mismatch_duplicates_and_normalized_duplicates(self):
        self.valid_inputs()
        rows = [self.memory(), self.memory(), self.memory(key=SECRET, failed_text="  ЗАПУСТИ   РЕДАКТОР ")]
        self.write_rows(self.memory_path, rows)
        findings = self.findings("correction_memory")
        self.assertEqual(findings["duplicate_key_rows"], 1)
        self.assertEqual(findings["duplicate_normalized_key_rows"], 2)
        self.assertEqual(findings["key_mismatch_rows"], 1)

    def test_invalid_memory_types_are_findings(self):
        self.valid_inputs()
        self.write_rows(self.memory_path, [self.memory(key=3, failed_text=[], corrected_intent=None,
                                                       seen_count=True, corrected_confidence="0.9",
                                                       corrected_slots=[], sources={}, status=[])])
        findings = self.findings("correction_memory")
        for key in ("invalid_key_rows", "invalid_text_rows", "invalid_intent_rows", "invalid_seen_count_rows",
                    "invalid_confidence_rows", "invalid_slots_rows", "invalid_sources_rows", "invalid_status_rows"):
            self.assertEqual(findings[key], 1, key)

    def test_legacy_nullable_fields_unknown_status_and_counts_are_informational(self):
        self.valid_inputs()
        row = self.memory(seen_count=99, corrected_slots=None, sources=None, status=SECRET)
        del row["cumulative_evidence"]
        self.write_rows(self.memory_path, [row])
        report = self.run_audit()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertEqual(report["inputs"]["correction_memory"]["observations"]["rows_without_checkpoint"], 1)

    def test_missing_optional_memory_fields_follow_strict_reader_defaults(self):
        self.valid_inputs()
        row = self.memory()
        for key in ("seen_count", "corrected_confidence", "corrected_slots", "sources"):
            del row[key]
        self.write_rows(self.memory_path, [row])
        self.assertEqual(self.run_audit()["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")

    def test_legacy_and_multiple_checkpoint_counts_are_not_equality_invariants(self):
        self.valid_inputs()
        row = self.memory(seen_count=2, cumulative_evidence={
            SECRET: {"version": 1, "observed_count": 1000, "legacy_baseline": True},
            "another": {"version": 1, "observed_count": 10, "legacy_baseline": False}})
        self.write_rows(self.memory_path, [row])
        report = self.run_audit()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertEqual(report["inputs"]["correction_memory"]["observations"]["rows_with_legacy_baseline"], 1)

    def test_checkpoint_shape_versions_counts_flags_and_source_keys(self):
        self.valid_inputs()
        good = {"version": 1, "observed_count": 2, "legacy_baseline": False}
        variants = [None, [], {" ": good}, {"s": []}]
        for field, value in (("version", True), ("version", 2), ("observed_count", True),
                             ("observed_count", -1), ("legacy_baseline", 1)):
            state = dict(good)
            state[field] = value
            variants.append({"s": state})
        for states in variants:
            with self.subTest(checkpoint=states):
                self.write_rows(self.memory_path, [self.memory(cumulative_evidence=states)])
                self.assertEqual(self.findings("correction_memory")["invalid_checkpoint_rows"], 1)

    def test_memory_timestamps_and_duplicate_sources(self):
        self.valid_inputs()
        self.write_rows(self.memory_path, [self.memory(last_seen_ts="2025-01-01T00:00:00", sources=[SECRET, SECRET]),
                                          self.memory(created_ts=None, last_seen_ts="2026-01-01T00:00:00Z")])
        findings = self.findings("correction_memory")
        self.assertEqual(findings["last_seen_before_created_rows"], 1)
        self.assertEqual(findings["duplicate_sources_rows"], 1)
        self.assertEqual(findings["invalid_timestamp_rows"], 1)
        self.assertEqual(findings["mixed_timezone_files"], 1)

    def test_file_byte_limit_prevents_content_read(self):
        self.valid_inputs()
        with mock.patch.dict(self.audit.LIMITS, {"bytes_per_file": 20}), mock.patch.object(
                self.audit.os, "open", side_effect=AssertionError("too large inputs must not be opened")):
            report = self.run_audit()
        self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
        self.assertTrue(all(item["state"] == "LIMIT_REACHED" for item in report["inputs"].values()))

    def test_line_length_and_line_count_bounds_keep_partial_results(self):
        self.valid_inputs()
        row = json.dumps(self.history()).encode()
        self.history_path.write_bytes(row + b"\n" + b"x" * 2048)
        with mock.patch.dict(self.audit.LIMITS, {"bytes_per_line": 1024}):
            item = self.run_audit()["inputs"]["command_history"]
        self.assertEqual(item["state"], "LIMIT_REACHED")
        self.assertEqual(item["object_rows"], 1)
        self.write_rows(self.history_path, [self.history(), self.history()])
        with mock.patch.dict(self.audit.LIMITS, {"lines_per_file": 1}):
            item = self.run_audit()["inputs"]["command_history"]
        self.assertEqual(item["state"], "LIMIT_REACHED")
        self.assertEqual(item["lines_read"], 1)

    def test_excessive_json_nesting_is_incomplete_not_clean(self):
        self.valid_inputs()
        for depth in (70, 1500):
            with self.subTest(depth=depth):
                self.history_path.write_text("[" * depth + "0" + "]" * depth, encoding="utf-8")
                report = self.run_audit()
                self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
                self.assertEqual(report["inputs"]["command_history"]["state"], "LIMIT_REACHED")

    @staticmethod
    def metadata_with(info, **changes):
        values = {name: getattr(info, name) for name in
                  ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")}
        values.update(changes)
        return SimpleNamespace(**values)

    def test_cross_api_creation_change_time_difference_is_not_a_write(self):
        self.valid_inputs()
        paths = (self.history_path, self.memory_path)
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        actual_fstat = os.fstat

        def different_clock(fd):
            info = actual_fstat(fd)
            return self.metadata_with(info, st_ctime_ns=info.st_ctime_ns + 1_000_000_000)

        # Windows CPython path stats can expose birth time here while fstat
        # exposes change time. Each API remains stable across both observations.
        with mock.patch.object(self.audit.os, "fstat", side_effect=different_clock):
            report = self.run_audit()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertTrue(all(item["complete"] and item["object_rows"] == 1
                            for item in report["inputs"].values()))
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})

    def test_cross_api_permission_bits_do_not_reject_regular_file(self):
        self.valid_inputs()
        actual_fstat = os.fstat

        def different_permissions(fd):
            info = actual_fstat(fd)
            return self.metadata_with(info, st_mode=info.st_mode ^ stat.S_IWUSR)

        with mock.patch.object(self.audit.os, "fstat", side_effect=different_permissions):
            report = self.run_audit()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertTrue(all(item["object_rows"] == 1 for item in report["inputs"].values()))

    def test_descriptor_change_time_change_is_detected_within_api(self):
        self.valid_inputs()
        actual_fstat = os.fstat
        observations = 0

        def changed_descriptor(fd):
            nonlocal observations
            observations += 1
            info = actual_fstat(fd)
            if observations == 2:
                return self.metadata_with(info, st_ctime_ns=info.st_ctime_ns + 1_000_000_000)
            return info

        with mock.patch.object(self.audit.os, "fstat", side_effect=changed_descriptor):
            report = self.run_audit()
        self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
        item = report["inputs"]["command_history"]
        self.assertEqual(item["state"], "CHANGED_DURING_READ")
        self.assertGreater(item["bytes_read"], 0)
        self.assertFalse(item["complete"])
        self.assertEqual(report["inputs"]["correction_memory"]["state"], "READ")

    def test_path_change_time_change_is_detected_within_api(self):
        self.valid_inputs()
        actual_lstat = Path.lstat
        observations = 0

        def changed_path(path, *args, **kwargs):
            nonlocal observations
            info = actual_lstat(path, *args, **kwargs)
            if path == self.history_path:
                observations += 1
                if observations >= 3:
                    return self.metadata_with(info, st_ctime_ns=info.st_ctime_ns + 1_000_000_000)
            return info

        with mock.patch.object(Path, "lstat", changed_path):
            report = self.run_audit()
        self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
        item = report["inputs"]["command_history"]
        self.assertEqual(item["state"], "CHANGED_DURING_READ")
        self.assertGreater(item["bytes_read"], 0)
        self.assertFalse(item["complete"])
        self.assertEqual(report["inputs"]["correction_memory"]["state"], "READ")

    def test_cross_api_identity_and_version_mismatches_prevent_reading(self):
        self.valid_inputs()
        actual_fstat = os.fstat
        for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_mode"):
            with self.subTest(field=field):
                def mismatch(fd):
                    info = actual_fstat(fd)
                    value = stat.S_IFDIR if field == "st_mode" else getattr(info, field) + 1
                    return self.metadata_with(info, **{field: value})

                with mock.patch.object(self.audit.os, "fstat", side_effect=mismatch), mock.patch.object(
                        self.audit.os, "fdopen", side_effect=AssertionError("mismatched descriptor must not be read")):
                    report = self.run_audit()
                self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
                self.assertTrue(all(item["state"] == "CHANGED_DURING_READ" and item["bytes_read"] == 0
                                    for item in report["inputs"].values()))

    def test_detected_append_replace_and_truncate_never_claim_complete(self):
        for operation in ("append", "replace", "truncate"):
            with self.subTest(operation=operation):
                self.valid_inputs()
                # Windows disallows replacing an open file. Replace the first
                # input while the second is read, then exercise the final restat.
                hook = "_memory_row" if operation == "replace" else "_history_row"
                original = getattr(self.audit, hook)
                changed = False

                def mutate(*args):
                    nonlocal changed
                    original(*args)
                    if changed:
                        return
                    changed = True
                    if operation == "append":
                        with self.history_path.open("ab") as stream:
                            stream.write(b"\n")
                    elif operation == "replace":
                        replacement = self.root / "replacement"
                        replacement.write_bytes(self.history_path.read_bytes())
                        os.replace(replacement, self.history_path)
                    else:
                        self.history_path.write_bytes(b"")

                with mock.patch.object(self.audit, hook, side_effect=mutate):
                    report = self.run_audit()
                self.assertEqual(report["status"], "NOT_FULLY_CHECKED")
                self.assertEqual(report["inputs"]["command_history"]["state"], "CHANGED_DURING_READ")

    def test_first_input_changed_while_second_is_read_is_detected(self):
        self.valid_inputs()
        original = self.audit._memory_row

        def mutate(*args):
            original(*args)
            self.history_path.write_bytes(b"")

        with mock.patch.object(self.audit, "_memory_row", side_effect=mutate):
            report = self.run_audit()
        self.assertEqual(report["inputs"]["command_history"]["state"], "CHANGED_DURING_READ")

    def test_symlink_and_reparse_paths_are_refused_before_open(self):
        self.valid_inputs()
        real_open, real_lstat = os.open, Path.lstat
        # No Windows developer-mode/symlink privilege is needed to exercise the
        # complete refusal path, including Windows reparse-point attributes.
        cases = ((self.history_path, stat.S_IFLNK, 0),
                 (self.history_path, stat.S_IFREG, 0x400),
                 (self.learning, stat.S_IFDIR, 0x400))
        for refused_path, mode, attributes in cases:
            with self.subTest(mode=mode, attributes=attributes):
                opened = []

                def inspect(path, *args, **kwargs):
                    if path == refused_path:
                        return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                    return real_lstat(path, *args, **kwargs)

                def spy(path, flags, *args, **kwargs):
                    opened.append(Path(path))
                    return real_open(path, flags, *args, **kwargs)

                with mock.patch.object(Path, "lstat", inspect), mock.patch.object(self.audit.os, "open", side_effect=spy):
                    report = self.run_audit()
                self.assertEqual(report["inputs"]["command_history"]["state"], "SYMLINK_REFUSED")
                self.assertEqual(opened, [] if refused_path == self.learning else [self.memory_path])

    def test_nonregular_input_is_refused_without_opening_it(self):
        self.valid_inputs()
        self.history_path.unlink()
        self.history_path.mkdir()
        report = self.run_audit()
        self.assertEqual(report["inputs"]["command_history"]["state"], "NON_REGULAR")
        if hasattr(os, "mkfifo"):
            self.history_path.rmdir()
            os.mkfifo(self.history_path)
            report = self.run_audit()
            self.assertEqual(report["inputs"]["command_history"]["state"], "NON_REGULAR")

    def test_permission_and_unexpected_errors_are_sanitized(self):
        self.valid_inputs()
        with mock.patch.object(self.audit.os, "open", side_effect=PermissionError(SECRET)):
            report = self.run_audit()
        self.assertEqual(report["inputs"]["command_history"]["state"], "UNREADABLE")
        with mock.patch.object(self.audit, "_history_row", side_effect=RuntimeError(SECRET)):
            report = self.run_audit()
        self.assertEqual(report["invocation"], "INTERNAL_ERROR")

    def test_only_fixed_inputs_are_opened_no_env_model_or_other_history_reads(self):
        self.valid_inputs()
        for relative in (".env", "models/nlu_intent.joblib", "data/learning/nlu_hard_cases.jsonl"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(SECRET, encoding="utf-8")
        actual_open = os.open
        opened = []

        def allow_only_inputs(path, flags, *args, **kwargs):
            self.assertIn(Path(path), (self.history_path, self.memory_path))
            self.assertEqual(flags & (os.O_WRONLY | os.O_RDWR), 0)
            self.assertEqual(flags & (os.O_CREAT | os.O_TRUNC | os.O_APPEND), 0)
            opened.append(Path(path))
            return actual_open(path, flags, *args, **kwargs)

        with mock.patch.object(self.audit.os, "open", side_effect=allow_only_inputs), mock.patch.object(
                builtins, "open", side_effect=AssertionError("unexpected generic content read")):
            report = self.run_audit()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertEqual(opened, [self.history_path, self.memory_path])

    def test_bytes_mtimes_directory_inventory_and_mutation_calls_are_unchanged(self):
        self.valid_inputs()
        paths = [self.history_path, self.memory_path]
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        inventory = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        mutators = ("replace", "rename", "remove", "unlink", "mkdir", "rmdir", "chmod", "utime", "truncate")
        patches = [mock.patch.object(self.audit.os, name, side_effect=AssertionError("unexpected mutation"))
                   for name in mutators]
        for patch in patches:
            patch.start()
        try:
            report = self.run_audit()
        finally:
            for patch in reversed(patches):
                patch.stop()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})
        self.assertEqual(inventory, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))

    def test_no_runtime_imports_and_no_analyzer_or_builder_execution(self):
        self.valid_inputs()
        original_import = builtins.__import__
        attempted = []

        def guarded_import(name, *args, **kwargs):
            attempted.append(name)
            self.assertNotIn(name.split(".")[0], ("modules", "tools", "joblib", "sklearn", "numpy"))
            return original_import(name, *args, **kwargs)

        with mock.patch.object(builtins, "__import__", side_effect=guarded_import), mock.patch.object(
                subprocess, "run", side_effect=AssertionError("diagnostic must not launch processes")):
            report = self.run_audit()
        self.assertEqual(report["status"], "NO_ISSUES_IN_CHECKED_STRUCTURE")

    def test_private_strings_in_all_payload_fields_never_escape(self):
        self.valid_inputs()
        history = self.history(raw_text=SECRET, final_text=SECRET, mode=SECRET, immediate_label=SECRET,
                               missing_slots=[SECRET], event_id=SECRET, ts=SECRET,
                               meta={"intent": SECRET, "confidence": 0.8, "slots": {SECRET: SECRET},
                                     "say": SECRET, "_text": SECRET}, **{SECRET: SECRET})
        memory = self.memory(key=SECRET, failed_text=SECRET, corrected_text=SECRET, corrected_intent=SECRET,
                             corrected_slots={SECRET: SECRET}, sources=[SECRET], status=SECRET,
                             created_ts=SECRET, last_seen_ts=SECRET,
                             cumulative_evidence={SECRET: {"version": 1, "observed_count": 10, "legacy_baseline": True}})
        self.write_rows(self.history_path, [history])
        self.write_rows(self.memory_path, [memory])
        result = self.cli("--repo", self.root)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertNotIn(SECRET, result.stdout)
        self.assertNotIn(str(self.root), result.stdout)
        self.assertTrue(self.audit.validate_public_report(json.loads(result.stdout)))

    def test_closed_schema_rejects_private_fields_types_codes_and_false_clean(self):
        self.valid_inputs()
        report = self.run_audit()
        mutations = [
            lambda value: value.update(private=SECRET),
            lambda value: value.update(status=SECRET),
            lambda value: value.update(schema_version=True),
            lambda value: value["scope"].update(files_written=0),
            lambda value: value["inputs"]["command_history"].update(bytes_read="1"),
            lambda value: value["inputs"]["command_history"]["findings"].update(private=1),
            lambda value: value["inputs"]["command_history"]["findings"].update(invalid_json_lines=True),
            lambda value: value["inputs"]["command_history"].update(state=SECRET),
            lambda value: value["inputs"]["command_history"].update(lines_read=3),
            lambda value: value["inputs"]["command_history"].update(state="MISSING", complete=False),
            lambda value: value["inputs"]["command_history"]["findings"].update(invalid_timestamp_rows=2),
            lambda value: value["inputs"]["command_history"]["findings"].update(invalid_timestamp_rows=1),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                candidate = copy.deepcopy(report)
                mutate(candidate)
                self.assertFalse(self.audit.validate_public_report(candidate))

    def test_cli_json_exits_are_separate_from_test_success(self):
        self.valid_inputs()
        for expected, malformed in ((0, False), (1, True)):
            if malformed:
                self.history_path.write_bytes(b"{broken")
            result = self.cli("--repo", self.root)
            self.assertEqual(result.returncode, expected)
            self.assertEqual(result.stderr, "")
            report = json.loads(result.stdout)
            self.assertTrue(self.audit.validate_public_report(report))
            self.assertEqual(report["exit_code"], expected)
        self.memory_path.unlink()
        result = self.cli("--repo", self.root)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "NOT_FULLY_CHECKED")

    def test_cli_default_root_uses_script_not_cwd_and_is_deterministic(self):
        self.valid_inputs()
        tool = self.root / "tools/audit_learning_data.py"
        tool.parent.mkdir()
        shutil.copyfile(PROJECT_ROOT / "tools/audit_learning_data.py", tool)
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        first = self.cli(script=tool, cwd=elsewhere)
        second = self.cli("--repo", self.root, script=tool, cwd=elsewhere)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.stderr + second.stderr, "")

    def test_cli_invalid_arguments_and_repo_never_print_user_input(self):
        for arguments, expected in ((("--" + SECRET,), "INVALID_ARGUMENTS"),
                                    (("--repo", self.root / SECRET), "INVALID_REPO")):
            with self.subTest(invocation=expected):
                result = self.cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "")
                self.assertNotIn(SECRET, result.stdout)
                self.assertEqual(json.loads(result.stdout)["invocation"], expected)
        output = io.StringIO()
        with mock.patch.object(self.audit.sys, "stdout", output), mock.patch.object(
                self.audit.os, "open", side_effect=OSError(SECRET)):
            self.valid_inputs()
            exit_code = self.audit.main(["--repo", str(self.root)])
        self.assertEqual(exit_code, 2)
        self.assertNotIn(SECRET, output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
