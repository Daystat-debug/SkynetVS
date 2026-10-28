"""Fixed synthetic tests for bounded, positional history snapshots.

Run: python -I -S -B -X utf8 tools/eval_learning_history_snapshot.py
Only temporary fixtures and explicitly loaded standalone source modules are used.
No application entry point, private history, model, training or builder is run.
"""
from __future__ import annotations

import ast
import builtins
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-private-history-marker-94"


class LearningHistorySnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_history_snapshot_")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name) / "repo with spaces"
        self.learning = self.repo / "data" / "learning"
        self.learning.mkdir(parents=True)
        self.history = self.learning / "command_history.jsonl"
        self.module = self.load("reader", "modules/learning/learning_history_snapshot.py")
        self.planner = self.load("planner", "modules/learning/correction_pair_evidence.py")

    @staticmethod
    def load(name, relative):
        spec = importlib.util.spec_from_file_location("synthetic_history_" + name, ROOT / relative)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def row(event_id="failed", *, accepted=False):
        text = "открой блокнот" if accepted else "запусти редактор"
        return {"event_id": event_id, "ts": "2026-01-01T12:00:01" if accepted else "2026-01-01T12:00:00",
                "raw_text": text, "final_text": text, "accepted": accepted,
                "missing_slots": [], "meta": {"intent": "OPEN_APP" if accepted else None,
                "confidence": 0.9 if accepted else 0.1, "slots": {"app": "notepad"}}}

    def pair(self):
        return [self.row(), self.row("corrected", accepted=True)]

    @staticmethod
    def line(row, ending=b"\n"):
        return json.dumps(row, ensure_ascii=True, allow_nan=False).encode("ascii") + ending

    def put(self, raw):
        self.history.write_bytes(raw)

    def snapshot(self, root=None):
        result = self.module.read_learning_history_snapshot(self.repo if root is None else root)
        self.assertEqual(result["kind"], "SKYNETVS_LEARNING_HISTORY_SNAPSHOT_V1")
        self.assertFalse(result["scope"]["file_writes"])
        self.assertFalse(result["scope"]["atomic_snapshot"])
        self.assertFalse(result["scope"]["event_identity_authenticated"])
        self.assertFalse(result["scope"]["undecodable_event_ids_recovered"])
        self.assertFalse(result["scope"]["runtime_integration"])
        self.assertEqual(result["scope"]["training_readiness"], "NOT_ASSESSED")
        if result["status"] == "REFUSED":
            self.assertIn(result["reason"], self.module.REASONS)
            self.assertFalse(result["snapshot_complete"])
            self.assertFalse(result["metadata_unchanged"])
            self.assertEqual(result["rows"], [])
            self.assertIsNone(result["observations"])
            self.assertNotIn(SECRET, json.dumps(result))
            self.assertNotIn(str(self.repo), json.dumps(result))
        else:
            self.assertEqual(result["status"], "COMPLETE")
            self.assertIsNone(result["reason"])
            self.assertTrue(result["snapshot_complete"])
            self.assertTrue(result["metadata_unchanged"])
            self.assertTrue(all(type(row) is dict or row is None for row in result["rows"]))
            observed = result["observations"]
            self.assertEqual(observed["physical_lines"], len(result["rows"]))
            self.assertEqual(observed["decoded_objects"], sum(type(row) is dict for row in result["rows"]))
            self.assertEqual(observed["barrier_lines"], sum(row is None for row in result["rows"]))
            self.assertEqual(observed["physical_lines"], observed["decoded_objects"] + observed["barrier_lines"])
            self.assertEqual(observed["barrier_lines"], sum(observed[key] for key in (
                "blank_lines", "invalid_utf8_lines", "invalid_json_lines", "duplicate_field_lines",
                "non_finite_number_lines", "non_object_lines")))
        return result

    def plan(self, snapshot):
        return self.planner.plan_correction_pair_evidence(
            snapshot["rows"], snapshot_complete=snapshot["snapshot_complete"])

    @staticmethod
    def changed_stat(info, **changes):
        fields = {name: getattr(info, name) for name in (
            "st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")}
        fields["st_file_attributes"] = getattr(info, "st_file_attributes", 0)
        fields.update(changes)
        return SimpleNamespace(**fields)

    def test_complete_lf_and_crlf_history_composes_with_frozen_planner(self):
        expected = self.pair()
        expected[0]["unknown"] = {"ordered": [1, True, 1.5, None], "text": SECRET}
        for ending in (b"\n", b"\r\n"):
            with self.subTest(ending=ending):
                raw = b"".join(self.line(row, ending) for row in expected)
                self.put(raw)
                result = self.snapshot(str(self.repo))
                self.assertEqual(result["rows"], expected)
                self.assertEqual(result["observations"]["bytes_read"], len(raw))
                plan = self.plan(result)
                self.assertEqual(plan["status"], "READY")
                self.assertEqual(len(plan["pairs"]), 1)
                self.assertEqual((plan["pairs"][0]["failed_index"], plan["pairs"][0]["corrected_index"]), (0, 1))

    def test_blank_bom_utf8_and_malformed_lines_keep_physical_positions(self):
        failed, corrected = self.pair()
        bad = [b" \t\r\n", b"\xef\xbb\xbf{}\n", b"\xff\n", b"{bad\n", b"\xc2\xa0\n"]
        self.put(self.line(failed) + b"".join(bad) + self.line(corrected))
        result = self.snapshot()
        self.assertEqual(result["rows"], [failed, *([None] * 5), corrected])
        self.assertEqual(result["observations"]["blank_lines"], 1)
        self.assertEqual(result["observations"]["invalid_utf8_lines"], 1)
        self.assertEqual(result["observations"]["invalid_json_lines"], 3)
        self.assertEqual(self.plan(result)["pairs"], [])

    def test_all_nonobject_json_values_are_positional_barriers(self):
        values = [None, True, False, 0, 1.5, SECRET, [], [self.row()]]
        self.put(b"".join(self.line(value) for value in values))
        result = self.snapshot()
        self.assertEqual(result["rows"], [None] * len(values))
        self.assertEqual(result["observations"]["non_object_lines"], len(values))

    def test_duplicate_decoded_keys_never_select_a_last_value(self):
        raw = (b'{"event_id":"a","event_id":"b"}\n'
               b'{"event_id":"a","event\\u005fid":"b"}\n'
               b'{"event_id":"a","meta":{"slots":{"app":"one","app":"two"}}}\n')
        self.put(raw)
        result = self.snapshot()
        self.assertEqual(result["rows"], [None, None, None])
        self.assertEqual(result["observations"]["duplicate_field_lines"], 3)
        self.assertEqual(self.plan(result)["observations"]["rows_with_event_id"], 0)

    def test_nonfinite_literals_and_float_overflow_are_barriers(self):
        bad = [b"NaN", b"Infinity", b"-Infinity", b"1e309"]
        self.put(b"".join(b'{"unknown":' + value + b'}\n' for value in bad)
                 + b'{"unknown":1e-4000}\n')
        result = self.snapshot()
        self.assertEqual(result["rows"], [None] * 4 + [{"unknown": 0.0}])
        self.assertEqual(result["observations"]["non_finite_number_lines"], 4)

    def test_schema_invalid_legacy_and_unknown_objects_are_retained(self):
        rows = [{}, {"event_id": "a", "accepted": "wrong", "unknown": SECRET},
                {"event_id": "b", "meta": {"slots": []}}, {"raw_text": "legacy"}]
        self.put(b"".join(self.line(row) for row in rows))
        result = self.snapshot()
        self.assertEqual(result["rows"], rows)
        self.assertEqual(result["observations"]["barrier_lines"], 0)
        self.assertEqual(self.plan(result)["observations"]["barrier_rows"], len(rows))

    def test_surrogate_dict_retains_visible_id_and_blocks_earlier_pair(self):
        rows = self.pair() + [{"event_id": "failed", "bad": "\ud800"}]
        self.put(b"".join(self.line(row) for row in rows))
        result = self.snapshot()
        self.assertEqual(result["rows"], rows)
        plan = self.plan(result)
        self.assertEqual(plan["pairs"], [])
        self.assertEqual(plan["observations"]["repeated_event_id_groups"], 1)
        self.assertEqual(plan["observations"]["repeated_event_id_rows"], 2)

    def test_unterminated_final_fragment_refuses_even_valid_json_or_whitespace(self):
        prefix = b"".join(self.line(row) for row in self.pair())
        for tail in (b"{}", b" ", b"\r", b"{", b"\xff"):
            with self.subTest(tail=tail):
                self.put(prefix + tail)
                self.assertEqual(self.snapshot()["reason"], "UNTERMINATED_FINAL_LINE")

    def test_empty_file_is_complete_and_missing_is_distinct(self):
        self.assertEqual(self.snapshot()["reason"], "MISSING")
        self.put(b"")
        result = self.snapshot()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["rows"], [])
        self.assertTrue(all(value == 0 for value in result["observations"].values()))
        self.assertEqual(self.plan(result)["status"], "READY")

    def test_exact_file_byte_limit_and_oversize_preflight(self):
        with mock.patch.dict(self.module.LIMITS, {"bytes_per_file": 3}):
            self.put(b"{}\n")
            self.assertEqual(self.snapshot()["status"], "COMPLETE")
            self.put(b"{}\n\n")
            with mock.patch.object(self.module.os, "open") as opener:
                self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")
                opener.assert_not_called()

    def test_line_limit_counts_terminator_and_precedes_decoding(self):
        self.put(b"{}\n")
        with mock.patch.dict(self.module.LIMITS, {"bytes_per_line": 3}):
            self.assertEqual(self.snapshot()["status"], "COMPLETE")
        with mock.patch.dict(self.module.LIMITS, {"bytes_per_line": 2}), \
                mock.patch.object(self.module, "_decode_line") as decoder:
            self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")
            decoder.assert_not_called()

    def test_physical_line_limit_accepts_exact_eof_and_rejects_extra_byte(self):
        with mock.patch.dict(self.module.LIMITS, {"physical_lines": 2}):
            self.put(b"{}\n\n")
            self.assertEqual(self.snapshot()["status"], "COMPLETE")
            for tail in (b"\n", b" ", b"{}\n"):
                self.put(b"{}\n\n" + tail)
                self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")

    def test_container_depth_bound_precedes_parse_even_for_malformed_json(self):
        with mock.patch.dict(self.module.LIMITS, {"json_container_depth": 3}):
            self.put(b'{"a":[[]]}\n')
            self.assertEqual(self.snapshot()["status"], "COMPLETE")
            for raw in (b'{"a":[[[]]]}\n', b"[[[[\n"):
                self.put(raw)
                with mock.patch.object(self.module.json, "loads") as parser:
                    self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")
                    parser.assert_not_called()

    def test_quoted_brackets_and_escaped_quotes_do_not_consume_depth(self):
        expected = {"key[{}]": '[[[[ {{{{ \\" [ ] \\ \\\" \\u005b ' + SECRET}
        self.put(self.line(expected))
        with mock.patch.dict(self.module.LIMITS, {"json_container_depth": 1}):
            result = self.snapshot()
        self.assertEqual(result["rows"], [expected])
        self.assertEqual(result["observations"]["lexical_units"], 3)

    def test_per_line_lexical_bound_precedes_json_allocation(self):
        self.put(b'{"a":0}\n')
        with mock.patch.dict(self.module.LIMITS, {"lexical_units_per_line": 3}):
            self.assertEqual(self.snapshot()["status"], "COMPLETE")
        with mock.patch.dict(self.module.LIMITS, {"lexical_units_per_line": 2}), \
                mock.patch.object(self.module.json, "loads") as parser:
            self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")
            parser.assert_not_called()

    def test_global_lexical_budget_includes_invalid_parse_attempts(self):
        self.put(b"bad bad\nbad bad\n")
        with mock.patch.dict(self.module.LIMITS, {"lexical_units_total": 3}):
            self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")
        self.put(b'{"a":0}\nbad bad\n')
        with mock.patch.dict(self.module.LIMITS, {"lexical_units_total": 5}):
            self.assertEqual(self.snapshot()["rows"], [{"a": 0}, None])
        with mock.patch.dict(self.module.LIMITS, {"lexical_units_total": 4}):
            self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")

    def test_integer_digit_bound_refuses_whole_snapshot(self):
        for value in (b"999", b"-999"):
            self.put(b'{"n":' + value + b'}\n')
            with mock.patch.dict(self.module.LIMITS, {"integer_decimal_digits": 3}):
                self.assertEqual(self.snapshot()["rows"], [{"n": int(value)}])
        prefix = b"".join(self.line(row) for row in self.pair())
        self.put(prefix + b'{"n":' + b"9" * 4097 + b'}\n')
        self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")
        self.put(b'{"n":' + b"9" * 4096 + b'}\n')
        result = self.snapshot()
        self.assertEqual(result["rows"][0]["n"], 10 ** 4096 - 1)

    def test_parser_recursion_failure_cannot_become_a_usable_barrier(self):
        self.put(self.line(self.row()))
        with mock.patch.object(self.module.json, "loads", side_effect=RecursionError(SECRET)):
            self.assertEqual(self.snapshot()["reason"], "RESOURCE_LIMIT")

    def test_invalid_roots_and_path_hooks_are_refused_before_io(self):
        class ExplosivePathLike:
            def __fspath__(self):
                raise AssertionError(SECRET)
        class ExplosiveString(str):
            def __str__(self):
                raise AssertionError(SECRET)
        class ExplosivePath(type(Path())):
            def __fspath__(self):
                raise AssertionError(SECRET)
        values = [None, b"bytes", "relative", "", Path("relative"), self.repo / ".." / "other",
                  str(self.repo) + "\x00", "//server/share", "\\\\server\\share",
                  ExplosivePathLike(), ExplosiveString(str(self.repo)), ExplosivePath(self.repo)]
        with mock.patch.object(self.module.os, "open") as opener, mock.patch.object(Path, "lstat") as inspector:
            for value in values:
                result = self.module.read_learning_history_snapshot(value)
                self.assertEqual(result["reason"], "INVALID_REPO")
                self.assertEqual(result["rows"], [])
            opener.assert_not_called()
            inspector.assert_not_called()

    def test_symlink_and_reparse_components_are_refused_before_open(self):
        self.put(b"{}\n")
        original = Path.lstat
        for selected in (self.history, self.learning):
            for kind in ("symlink", "reparse"):
                def inspect(path, *args, **kwargs):
                    info = original(path, *args, **kwargs)
                    if path == selected:
                        return self.changed_stat(info, **(
                            {"st_mode": stat.S_IFLNK | 0o777} if kind == "symlink" else {"st_file_attributes": 0x400}))
                    return info
                with mock.patch.object(Path, "lstat", inspect), mock.patch.object(self.module.os, "open") as opener:
                    self.assertEqual(self.snapshot()["reason"], "SYMLINK_REFUSED")
                    opener.assert_not_called()

    def test_nonregular_targets_and_ancestors_are_refused_before_open(self):
        self.put(b"{}\n")
        original = Path.lstat
        for selected, mode in ((self.history, stat.S_IFDIR), (self.history, stat.S_IFIFO),
                               (self.learning, stat.S_IFREG)):
            def inspect(path, *args, **kwargs):
                info = original(path, *args, **kwargs)
                return self.changed_stat(info, st_mode=mode | 0o600) if path == selected else info
            with mock.patch.object(Path, "lstat", inspect), mock.patch.object(self.module.os, "open") as opener:
                self.assertEqual(self.snapshot()["reason"], "NON_REGULAR")
                opener.assert_not_called()

    def test_descriptor_identity_type_and_version_mismatches_prevent_read(self):
        self.put(self.line(self.row()))
        original = os.fstat
        original_open = os.open
        changes = (lambda s: {"st_ino": s.st_ino + 1}, lambda s: {"st_size": s.st_size + 1},
                   lambda s: {"st_mtime_ns": s.st_mtime_ns + 1}, lambda s: {"st_mode": stat.S_IFIFO | 0o600})
        for change in changes:
            descriptors = []
            def track_open(path, flags):
                descriptor = original_open(path, flags)
                descriptors.append(descriptor)
                return descriptor
            def inspect(fd):
                info = original(fd)
                return self.changed_stat(info, **change(info))
            with mock.patch.object(self.module.os, "fstat", inspect), \
                    mock.patch.object(self.module.os, "open", track_open), \
                    mock.patch.object(self.module, "_read_rows") as reader:
                self.assertEqual(self.snapshot()["reason"], "CHANGED_DURING_READ")
                reader.assert_not_called()
            self.assertEqual(len(descriptors), 1)
            with self.assertRaises(OSError):
                original(descriptors[0])

    def test_cross_api_ctime_and_permission_differences_remain_compatible(self):
        self.put(b"".join(self.line(row) for row in self.pair()))
        original = os.fstat
        def inspect(fd):
            info = original(fd)
            return self.changed_stat(info, st_ctime_ns=info.st_ctime_ns + 12345, st_mode=info.st_mode ^ 0o111)
        with mock.patch.object(self.module.os, "fstat", inspect):
            result = self.snapshot()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(len(self.plan(result)["pairs"]), 1)

    def test_same_api_change_time_changes_invalidate_snapshot(self):
        self.put(self.line(self.row()))
        original_fstat = os.fstat
        calls = 0
        def inspect_fd(fd):
            nonlocal calls
            calls += 1
            info = original_fstat(fd)
            return self.changed_stat(info, st_ctime_ns=info.st_ctime_ns + int(calls > 1))
        with mock.patch.object(self.module.os, "fstat", inspect_fd):
            self.assertEqual(self.snapshot()["reason"], "CHANGED_DURING_READ")
        original_lstat = Path.lstat
        calls = 0
        def inspect_path(path, *args, **kwargs):
            nonlocal calls
            info = original_lstat(path, *args, **kwargs)
            if path == self.history:
                calls += 1
                return self.changed_stat(info, st_ctime_ns=info.st_ctime_ns + int(calls > 2))
            return info
        with mock.patch.object(Path, "lstat", inspect_path):
            self.assertEqual(self.snapshot()["reason"], "CHANGED_DURING_READ")

    def test_append_truncate_replace_and_directory_swap_during_read_refuse(self):
        raw = b"".join(self.line(row) for row in self.pair())
        original = self.module._decode_line
        original_lstat = Path.lstat
        for mutation in ("append", "truncate", "replace", "directory"):
            self.put(raw)
            changed = False
            def decode(line, observations):
                nonlocal changed
                value = original(line, observations)
                if not changed:
                    changed = True
                    if mutation == "append":
                        with self.history.open("ab") as stream:
                            stream.write(b"\n")
                    elif mutation == "truncate":
                        self.history.write_bytes(b"{}\n")
                return value
            def inspect(path, *args, **kwargs):
                info = original_lstat(path, *args, **kwargs)
                # Windows disallows delete/replace with the ordinary CRT read
                # handle open. Simulate the observed replacement identity;
                # actual pre-open replacement has its own filesystem test.
                selected = self.history if mutation == "replace" else self.learning
                if changed and mutation in ("replace", "directory") and path == selected:
                    return self.changed_stat(info, st_ino=info.st_ino + 1)
                return info
            with self.subTest(mutation=mutation), mock.patch.object(self.module, "_decode_line", decode), \
                    mock.patch.object(Path, "lstat", inspect):
                self.assertEqual(self.snapshot()["reason"], "CHANGED_DURING_READ")

    def test_path_replacement_before_open_is_detected_before_content_read(self):
        raw = self.line(self.row())
        self.put(raw)
        original = os.open
        def open_after_replacement(path, flags):
            replacement = self.learning / "replacement.jsonl"
            replacement.write_bytes(raw)
            replacement.replace(self.history)
            return original(path, flags)
        with mock.patch.object(self.module.os, "open", open_after_replacement), \
                mock.patch.object(self.module, "_read_rows") as reader:
            self.assertEqual(self.snapshot()["reason"], "CHANGED_DURING_READ")
            reader.assert_not_called()

    def test_permission_io_and_unexpected_errors_clear_private_results(self):
        self.put(self.line(self.row()))
        with mock.patch.object(self.module.os, "open", side_effect=PermissionError(SECRET)):
            self.assertEqual(self.snapshot()["reason"], "UNREADABLE")
        original_open = os.open
        for exception, reason in ((OSError(SECRET), "UNREADABLE"), (RuntimeError(SECRET), "INTERNAL_ERROR")):
            descriptors = []
            def track_open(path, flags):
                descriptor = original_open(path, flags)
                descriptors.append(descriptor)
                return descriptor
            with mock.patch.object(self.module, "_decode_line", side_effect=exception), \
                    mock.patch.object(self.module.os, "open", track_open):
                self.assertEqual(self.snapshot()["reason"], reason)
            self.assertEqual(len(descriptors), 1)
            with self.assertRaises(OSError):
                os.fstat(descriptors[0])

    def test_short_eof_or_disappearance_cannot_produce_complete_snapshot(self):
        raw = b"".join(self.line(row) for row in self.pair())
        self.put(raw)
        original_fdopen = os.fdopen
        class ShortStream:
            def __init__(self, stream):
                self.stream = stream
                self.calls = 0
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
            def fileno(self):
                return self.stream.fileno()
            def readline(self, maximum):
                self.calls += 1
                return self.stream.readline(maximum) if self.calls == 1 else b""
        with mock.patch.object(self.module.os, "fdopen", lambda fd, mode: ShortStream(original_fdopen(fd, mode))):
            self.assertEqual(self.snapshot()["reason"], "CHANGED_DURING_READ")
        original_lstat = Path.lstat
        observations = 0
        def inspect_disappearance(path, *args, **kwargs):
            nonlocal observations
            if path == self.history:
                observations += 1
                if observations >= 3:
                    raise FileNotFoundError(SECRET)
            return original_lstat(path, *args, **kwargs)
        with mock.patch.object(Path, "lstat", inspect_disappearance):
            self.assertEqual(self.snapshot()["reason"], "CHANGED_DURING_READ")

    def test_readonly_scope_preserves_inputs_other_files_and_environment(self):
        self.put(b"".join(self.line(row) for row in self.pair()))
        for relative in (".env", "models/nlu_intent.joblib", ".venv/Scripts/python.exe",
                         "data/learning/correction_memory.jsonl", "data/learning/other.jsonl"):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(SECRET.encode())
        def inventory():
            return {str(path.relative_to(self.repo)): (path.read_bytes(), path.stat().st_mtime_ns)
                    for path in self.repo.rglob("*") if path.is_file()}
        before = inventory()
        directories = sorted(str(path.relative_to(self.repo)) for path in self.repo.rglob("*") if path.is_dir())
        environment = dict(os.environ)
        original_open = os.open
        opened = []
        def open_readonly(path, flags):
            opened.append((path, flags))
            return original_open(path, flags)
        with mock.patch.object(self.module.os, "open", open_readonly), \
                mock.patch.object(builtins, "open", side_effect=AssertionError("unexpected builtin open")), \
                mock.patch.object(self.module.os, "replace", side_effect=AssertionError("unexpected replace")), \
                mock.patch.object(self.module.os, "rename", side_effect=AssertionError("unexpected rename")), \
                mock.patch.object(self.module.os, "unlink", side_effect=AssertionError("unexpected unlink")), \
                mock.patch.object(self.module.os, "mkdir", side_effect=AssertionError("unexpected mkdir")):
            result = self.snapshot()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0][0], self.history)
        self.assertEqual(opened[0][1] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND), 0)
        self.assertEqual(inventory(), before)
        self.assertEqual(sorted(str(path.relative_to(self.repo)) for path in self.repo.rglob("*") if path.is_dir()), directories)
        self.assertEqual(dict(os.environ), environment)
        tree = ast.parse((ROOT / "modules/learning/learning_history_snapshot.py").read_text(encoding="utf-8"))
        imports = [node.module if isinstance(node, ast.ImportFrom) else alias.name
                   for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                   for alias in (node.names if isinstance(node, ast.Import) else [None])]
        self.assertEqual(set(imports), {"__future__", "json", "math", "os", "pathlib", "stat"})
        self.assertNotIn("main", [node.name for node in tree.body if isinstance(node, ast.FunctionDef)])

    def test_failed_snapshot_never_supplies_partial_evidence_and_reads_are_detached(self):
        raw = b"".join(self.line(row) for row in self.pair())
        self.put(raw + b"{bad\n")
        first, second = self.snapshot(), self.snapshot()
        self.assertEqual(first, second)
        self.assertEqual(len(self.plan(first)["pairs"]), 1)
        first["rows"][0]["meta"]["slots"]["app"] = SECRET
        self.assertEqual(second["rows"][0]["meta"]["slots"]["app"], "notepad")
        self.put(raw + b"{}")
        refused = self.snapshot()
        plan = self.plan(refused)
        self.assertEqual(plan["status"], "REFUSED")
        self.assertEqual(plan["reason"], "INCOMPLETE_SNAPSHOT")
        self.assertEqual(plan["pairs"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
