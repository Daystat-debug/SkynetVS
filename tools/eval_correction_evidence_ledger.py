"""Named isolated synthetic checks for the private correction evidence ledger.

Run: python -I -S -B -X utf8 tools/eval_correction_evidence_ledger.py
Loads only the three standalone source modules into a synthetic package.
Every database/history fixture is created under one temporary directory.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-private-ledger-marker-95"


class CorrectionEvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_evidence_ledger_")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.fixture("repo with spaces # unicode-я")
        self.package_name = "modules.learning"
        children = ("correction_pair_evidence", "learning_history_snapshot", "correction_evidence_ledger")
        module_names = ("modules", self.package_name, *(self.package_name + "." + name for name in children))
        absent = object()
        previous = {name: sys.modules.get(name, absent) for name in module_names}
        def restore_modules():
            for name, value in previous.items():
                if value is absent:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
        self.addCleanup(restore_modules)
        parent = ModuleType("modules")
        parent.__path__ = []
        package = ModuleType(self.package_name)
        package.__path__ = []
        parent.learning = package
        sys.modules["modules"] = parent
        sys.modules[self.package_name] = package
        for name in children:
            full_name = self.package_name + "." + name
            spec = importlib.util.spec_from_file_location(full_name, ROOT / "modules" / "learning" / (name + ".py"))
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[full_name] = module
            setattr(package, name, module)
            spec.loader.exec_module(module)
        self.module = package.correction_evidence_ledger
        self.planner = package.correction_pair_evidence
        self.reader = package.learning_history_snapshot
        self.epoch = None

    def fixture(self, name):
        self.repo = self.base / name
        self.learning = self.repo / "data" / "learning"
        self.learning.mkdir(parents=True)
        self.history = self.learning / "command_history.jsonl"
        self.history.write_bytes(b"")
        self.database = self.learning / "correction_evidence.sqlite3"

    @staticmethod
    def row(event_id="failed", *, accepted=False, epoch=None):
        text = "открой блокнот" if accepted else "запусти редактор"
        row = {"event_id": event_id, "ts": "2026-01-01T12:00:01" if accepted else "2026-01-01T12:00:00",
               "raw_text": text, "final_text": text, "accepted": accepted, "missing_slots": [],
               "meta": {"intent": "OPEN_APP" if accepted else None, "confidence": 0.9 if accepted else 0.1,
                        "slots": {"app": "notepad", "nested": [SECRET, {"value": True}]}}}
        if epoch is not None:
            row["evidence_epoch"] = epoch
        return row

    def pair(self, prefix="", *, epoch=True):
        marker = self.epoch if epoch is True else epoch if type(epoch) is str else None
        return [self.row(prefix + "failed", epoch=marker),
                self.row(prefix + "corrected", accepted=True, epoch=marker)]

    @staticmethod
    def line(row):
        return json.dumps(row, ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"

    def put(self, rows):
        self.history.write_bytes(b"".join(self.line(row) for row in rows))

    def call(self, initialize=False):
        result = (self.module.initialize_correction_evidence_ledger if initialize else
                  self.module.sync_correction_evidence_ledger)(self.repo)
        self.assertEqual(set(result), {"kind", "operation", "status", "reason", "input_reason", "epoch",
                                       "transaction_committed", "ledger_file_created", "stats", "scope", "limits"})
        self.assertEqual(result["kind"], "SKYNETVS_CORRECTION_EVIDENCE_LEDGER_RESULT_V1")
        self.assertEqual(result["operation"], "INITIALIZE" if initialize else "SYNC")
        self.assertFalse(result["scope"]["runtime_integration"])
        self.assertFalse(result["scope"]["correction_memory_written"])
        self.assertFalse(result["scope"]["legacy_aggregate_disabled"])
        self.assertFalse(result["scope"]["event_identity_authenticated"])
        self.assertEqual(result["scope"]["training_readiness"], "NOT_ASSESSED")
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(str(self.repo), json.dumps(result))
        return result

    def initialize(self, rows=None):
        if rows is not None:
            self.put(rows)
        result = self.call(True)
        self.assertEqual(result["status"], "INITIALIZED", result)
        self.assertTrue(result["transaction_committed"])
        self.assertTrue(result["ledger_file_created"])
        self.assertRegex(result["epoch"], r"^[0-9a-f]{32}$")
        self.epoch = result["epoch"]
        return result

    def sync(self, rows=None):
        if rows is not None:
            self.put(rows)
        return self.call()

    def refuse(self, result, reason, *, unknown=False):
        self.assertEqual(result["status"], "REFUSED", result)
        self.assertEqual(result["reason"], reason, result)
        self.assertIsNone(result["stats"])
        self.assertIsNone(result["epoch"])
        self.assertIs(result["transaction_committed"], None if unknown else False)
        self.assertFalse(result["scope"]["refusal_guarantees_unchanged_file_bytes"])

    def connect(self):
        return sqlite3.connect(self.database.as_uri() + "?mode=rw", uri=True)

    def state(self):
        with self.connect() as connection:
            result = {table: connection.execute("SELECT * FROM " + table + " ORDER BY 1").fetchall()
                      for table in ("meta", "events", "pairs", "endpoints")}
        connection.close()
        return result

    def mutate(self, sql, parameters=()):
        with self.connect() as connection:
            connection.execute(sql, parameters)
        connection.close()

    def connection_patch(self, connection_type):
        real_connect = sqlite3.connect
        def connect(target):
            return real_connect(target.as_uri() + "?mode=rw", uri=True, timeout=0,
                                isolation_level=None, factory=connection_type)
        return mock.patch.object(self.module, "_connect", side_effect=connect)

    def test_empty_baseline_creates_fresh_epoch_and_no_evidence(self):
        result = self.initialize()
        self.assertEqual(result["stats"]["bound_events_total"], 0)
        self.assertEqual(result["stats"]["accepted_pairs_total"], 0)
        self.assertEqual(self.state()["meta"][0][4], self.epoch)
        first_epoch = self.epoch
        self.fixture("another repo")
        self.initialize()
        self.assertNotEqual(self.epoch, first_epoch)

    def test_baseline_pairs_are_bound_without_counting_on_every_replay(self):
        rows = self.pair(epoch=False)
        result = self.initialize(rows)
        self.assertEqual(result["stats"]["new_bindings"], 2)
        self.assertEqual(result["stats"]["baseline_pairs_skipped"], 1)
        before = self.state()
        repeated = self.sync(rows)
        self.assertEqual(repeated["status"], "UNCHANGED")
        self.assertEqual(repeated["stats"]["accepted_pairs_total"], 0)
        self.assertEqual(self.state(), before)

    def test_epoch_pair_is_durable_and_counted_once_after_reopening(self):
        self.initialize()
        rows = self.pair()
        first = self.sync(rows)
        self.assertEqual(first["status"], "APPLIED")
        self.assertEqual(first["stats"]["new_pairs"], 1)
        before = self.state()
        self.assertEqual(len(before["endpoints"]), 2)
        for _ in range(3):
            replay = self.sync(rows)
            self.assertEqual(replay["status"], "UNCHANGED")
            self.assertEqual(replay["stats"]["replayed_pairs"], 1)
            self.assertEqual(replay["stats"]["new_pairs"], 0)
            self.assertEqual(replay["stats"]["accepted_pairs_total"], 1)
        self.assertEqual(self.state(), before)

    def test_restored_previously_unseen_old_ids_without_epoch_never_count(self):
        self.initialize()
        rows = self.pair("restored-", epoch=False)
        result = self.sync(rows)
        self.assertEqual(result["stats"]["new_bindings"], 2)
        self.assertEqual(result["stats"]["epoch_pairs_skipped"], 1)
        self.assertEqual(result["stats"]["accepted_pairs_total"], 0)

    def test_foreign_missing_nonstring_and_mixed_epochs_are_ineligible(self):
        self.initialize()
        for index, marker in enumerate(("foreign", "", True, 95, None)):
            with self.subTest(index=index):
                rows = self.pair(str(index))
                if marker is None:
                    rows[1].pop("evidence_epoch")
                else:
                    rows[1]["evidence_epoch"] = marker
                result = self.sync(rows)
                self.assertEqual(result["stats"]["epoch_pairs_skipped"], 1)
                self.assertEqual(result["stats"]["accepted_pairs_total"], 0)

    def test_epoch_cannot_be_retrofitted_onto_already_bound_event(self):
        old = self.pair(epoch=False)
        self.initialize(old)
        changed = copy.deepcopy(old)
        for row in changed:
            row["evidence_epoch"] = self.epoch
        before = self.state()
        self.refuse(self.sync(changed), "EVENT_PAYLOAD_CONFLICT")
        self.assertEqual(self.state(), before)

    def test_in_snapshot_payload_conflict_refuses_before_database_creation(self):
        failed, corrected = self.pair(epoch=False)
        conflict = copy.deepcopy(failed)
        conflict["unknown"] = SECRET
        self.put([failed, corrected, conflict])
        self.refuse(self.call(True), "EVENT_PAYLOAD_CONFLICT")
        self.assertFalse(self.database.exists())

    def test_cross_snapshot_conflict_rolls_back_all_other_new_evidence(self):
        self.initialize()
        original = self.pair()
        self.sync(original)
        before = self.state()
        altered = copy.deepcopy(original[0])
        altered["raw_text"] = "другая команда"
        self.refuse(self.sync([*self.pair("fresh-"), altered]), "EVENT_PAYLOAD_CONFLICT")
        self.assertEqual(self.state(), before)

    def test_schema_invalid_visible_id_still_blocks_changed_payload(self):
        self.initialize()
        malformed = self.row("invalid", epoch=self.epoch)
        malformed["accepted"] = "false"
        result = self.sync([malformed])
        self.assertEqual(result["stats"]["new_bindings"], 1)
        before = self.state()
        valid = self.row("invalid", epoch=self.epoch)
        self.refuse(self.sync([valid, self.row("c", accepted=True, epoch=self.epoch)]), "EVENT_PAYLOAD_CONFLICT")
        self.assertEqual(self.state(), before)

    def test_unknown_nested_fields_participate_in_full_payload_binding(self):
        self.initialize()
        rows = self.pair()
        rows[0]["extra"] = {"private": [SECRET, 1]}
        self.sync(rows)
        before = self.state()
        changed = copy.deepcopy(rows)
        changed[0]["extra"]["private"][1] = 2
        self.refuse(self.sync(changed), "EVENT_PAYLOAD_CONFLICT")
        self.assertEqual(self.state(), before)

    def test_key_order_and_json_formatting_preserve_binding_but_numeric_types_do_not(self):
        self.initialize()
        rows = self.pair()
        rows[0]["extra"] = 1
        self.sync(rows)
        before = self.state()
        reordered = [{key: row[key] for key in reversed(row)} for row in rows]
        self.history.write_bytes(b"".join(json.dumps(row, ensure_ascii=True, separators=(", ", ": ")).encode() + b"\r\n"
                                          for row in reordered))
        self.assertEqual(self.sync()["status"], "UNCHANGED")
        for value in (1.0, True):
            changed = copy.deepcopy(rows)
            changed[0]["extra"] = value
            self.refuse(self.sync(changed), "EVENT_PAYLOAD_CONFLICT")
        self.assertEqual(self.state(), before)

    def test_opaque_ids_keep_spaces_case_unicode_and_surrogates(self):
        self.initialize()
        ids = (" id ", "id", "ID", "Ид", "bad\ud800")
        result = self.sync([self.row(value, epoch=self.epoch) for value in ids])
        self.assertEqual(result["stats"]["new_bindings"], len(ids))
        stored = {json.loads(row[0].decode("ascii")) for row in self.state()["events"]}
        self.assertEqual(stored, set(ids))
        self.assertEqual(result["stats"]["accepted_pairs_total"], 0)

    def test_duplicate_id_quarantine_survives_later_deduplication(self):
        self.initialize()
        rows = self.pair()
        first = self.sync([*rows, copy.deepcopy(rows[0])])
        self.assertEqual(first["stats"]["new_pairs"], 0)
        self.assertEqual(first["stats"]["new_quarantines"], 1)
        second = self.sync(rows)
        self.assertEqual(second["stats"]["quarantined_pairs_skipped"], 1)
        self.assertEqual(second["stats"]["new_pairs"], 0)
        self.assertEqual(second["stats"]["quarantined_events_total"], 1)

    def test_late_quarantine_preserves_prior_count_and_blocks_future_use(self):
        self.initialize()
        rows = self.pair()
        self.sync(rows)
        repeated = self.sync([*rows, copy.deepcopy(rows[1])])
        self.assertEqual(repeated["stats"]["new_quarantines"], 1)
        self.assertEqual(repeated["stats"]["accepted_pairs_total"], 1)
        next_result = self.sync([self.row("different", epoch=self.epoch), rows[1]])
        self.assertEqual(next_result["stats"]["quarantined_pairs_skipped"], 1)
        self.assertEqual(next_result["stats"]["accepted_pairs_total"], 1)

    def test_corrected_endpoint_cannot_be_reused_with_new_failed_event(self):
        self.initialize()
        original = self.pair()
        self.sync(original)
        result = self.sync([self.row("other-failed", epoch=self.epoch), original[1]])
        self.assertEqual(result["stats"]["consumed_endpoint_pairs_skipped"], 1)
        self.assertEqual(result["stats"]["new_pairs"], 0)
        self.assertEqual(result["stats"]["accepted_pairs_total"], 1)

    def test_failed_endpoint_cannot_be_reused_with_new_corrected_event(self):
        self.initialize()
        original = self.pair()
        self.sync(original)
        result = self.sync([original[0], self.row("other-corrected", accepted=True, epoch=self.epoch)])
        self.assertEqual(result["stats"]["consumed_endpoint_pairs_skipped"], 1)
        self.assertEqual(result["stats"]["accepted_pairs_total"], 1)

    def test_rotation_overlap_and_empty_history_do_not_reset_consumed_ids(self):
        self.initialize()
        first, second = self.pair("one-"), self.pair("two-")
        self.assertEqual(self.sync(first)["stats"]["new_pairs"], 1)
        self.assertEqual(self.sync([*first, *second])["stats"]["new_pairs"], 1)
        self.assertEqual(self.sync([])["stats"]["accepted_pairs_total"], 2)
        rotated = self.sync([*second, *first])
        self.assertEqual(rotated["stats"]["replayed_pairs"], 2)
        self.assertEqual(rotated["stats"]["new_pairs"], 0)
        self.assertEqual(rotated["stats"]["accepted_pairs_total"], 2)

    def test_baseline_endpoint_mixed_with_new_epoch_endpoint_cannot_count(self):
        old = self.row("baseline")
        self.initialize([old])
        result = self.sync([old, self.row("new", accepted=True, epoch=self.epoch)])
        self.assertEqual(result["stats"]["baseline_pairs_skipped"], 1)
        self.assertEqual(result["stats"]["accepted_pairs_total"], 0)

    def test_reader_barriers_and_legacy_positions_never_create_false_pairs(self):
        self.initialize()
        failed, corrected = self.pair()
        legacy = self.row("unused")
        legacy.pop("event_id")
        for barrier in (b"{bad\n", b"\xff\n", b"{\"event_id\":\"x\",\"event_id\":\"y\"}\n", b" \n", self.line(legacy)):
            with self.subTest(barrier=barrier[:4]):
                self.history.write_bytes(self.line(failed) + barrier + self.line(corrected))
                result = self.sync()
                self.assertEqual(result["stats"]["accepted_pairs_total"], 0)

    def test_incomplete_history_refuses_before_any_database_open(self):
        self.put(self.pair(epoch=False))
        with self.history.open("ab") as stream:
            stream.write(b"{}")
        with mock.patch.object(self.module, "_connect", side_effect=AssertionError("must not connect")):
            result = self.call(True)
        self.refuse(result, "HISTORY_REFUSED")
        self.assertEqual(result["input_reason"], "UNTERMINATED_FINAL_LINE")
        self.assertFalse(self.database.exists())

    def test_planner_refusal_and_resource_failure_happen_before_ledger_creation(self):
        rows = self.pair(epoch=False)
        rows[1]["ts"] += "+00:00"
        self.put(rows)
        with mock.patch.object(self.module, "_connect", side_effect=AssertionError("must not connect")):
            result = self.call(True)
        self.refuse(result, "PLAN_REFUSED")
        self.assertEqual(result["input_reason"], "MIXED_TIMESTAMP_MODES")
        self.put(self.pair(epoch=False))
        with mock.patch.object(self.planner, "MAX_ROWS", 1):
            result = self.call(True)
        self.refuse(result, "PLAN_REFUSED")
        self.assertEqual(result["input_reason"], "RESOURCE_LIMIT")
        self.assertFalse(self.database.exists())

    def test_uncomparable_visible_id_never_becomes_a_persisted_placeholder(self):
        self.put([self.row()])
        with mock.patch.object(self.planner, "_canonical_payload", return_value=(None, False)):
            result = self.call(True)
        self.refuse(result, "UNCOMPARABLE_EVENT_PAYLOAD")
        self.assertFalse(self.database.exists())
        real_prepare = self.module._prepare_rows
        with mock.patch.object(self.module, "_prepare_rows", side_effect=self.planner._LimitReached):
            self.refuse(self.call(True), "RESOURCE_LIMIT")
        self.assertIs(self.module._prepare_rows, real_prepare)

    def test_existing_ledger_cannot_be_reinitialized_or_rebaselined(self):
        self.initialize()
        self.sync(self.pair())
        before = self.state()
        self.refuse(self.call(True), "LEDGER_ALREADY_EXISTS")
        self.assertEqual(self.state(), before)

    def test_sync_never_creates_missing_state(self):
        self.put(self.pair(epoch=False))
        self.refuse(self.call(), "LEDGER_MISSING")
        self.assertFalse(self.database.exists())

    def test_empty_and_corrupt_existing_state_are_preserved_not_rebuilt(self):
        for index, raw in enumerate((b"", b"not a SQLite database " + SECRET.encode())):
            with self.subTest(index=index):
                if index:
                    self.fixture("corrupt repo")
                self.database.write_bytes(raw)
                self.refuse(self.call(), "STATE_INVALID")
                self.assertEqual(self.database.read_bytes(), raw)
                self.refuse(self.call(True), "LEDGER_ALREADY_EXISTS")
                self.assertEqual(self.database.read_bytes(), raw)

    def test_extra_schema_objects_including_sqlitex_prefix_are_refused(self):
        statements = ("CREATE TABLE extra (value TEXT)", "CREATE TABLE sqliteXhidden (value TEXT)",
                      "CREATE VIEW extra_view AS SELECT * FROM events",
                      "CREATE TRIGGER sqliteXtrigger AFTER INSERT ON events BEGIN DELETE FROM events; END")
        for index, statement in enumerate(statements):
            with self.subTest(index=index):
                if index:
                    self.fixture("schema " + str(index))
                self.initialize()
                self.mutate(statement)
                before = self.database.read_bytes()
                self.put(self.pair())
                self.refuse(self.call(), "STATE_INVALID")
                self.assertEqual(self.database.read_bytes(), before)

    def test_state_version_rule_epoch_and_legacy_source_are_closed(self):
        statements = ("PRAGMA user_version = 2", "PRAGMA application_id = 0",
                      "UPDATE meta SET kind = 'other'", "UPDATE meta SET rule_version = 'future'",
                      "UPDATE meta SET epoch = 'invalid'", "UPDATE meta SET legacy_source = 'other'")
        for index, statement in enumerate(statements):
            with self.subTest(index=index):
                if index:
                    self.fixture("version " + str(index))
                self.initialize()
                self.mutate(statement)
                self.refuse(self.sync(self.pair()), "STATE_INVALID")

    def test_dangling_foreign_keys_and_incomplete_endpoint_pairs_refuse(self):
        for index, statement in enumerate(("DELETE FROM endpoints WHERE role = 'corrected'", "DELETE FROM events")):
            with self.subTest(index=index):
                if index:
                    self.fixture("references " + str(index))
                self.initialize()
                self.sync(self.pair())
                self.mutate(statement)
                before = self.state()
                self.refuse(self.sync(self.pair("new-")), "STATE_INVALID")
                self.assertEqual(self.state(), before)

    def test_endpoint_role_and_pair_links_cannot_satisfy_only_total_count(self):
        self.initialize()
        self.sync(self.pair())
        with self.connect() as connection:
            connection.execute("PRAGMA ignore_check_constraints = ON")
            connection.execute("UPDATE endpoints SET role = 'temp' WHERE role = 'failed'")
            connection.execute("UPDATE endpoints SET role = 'failed' WHERE role = 'corrected'")
            connection.execute("UPDATE endpoints SET role = 'corrected' WHERE role = 'temp'")
        connection.close()
        before = self.state()
        self.assertEqual(len(before["endpoints"]), 2)
        self.refuse(self.sync(self.pair("new-")), "STATE_INVALID")
        self.assertEqual(self.state(), before)

    def test_busy_writer_is_refused_without_partial_binding(self):
        self.initialize()
        before = self.state()
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            result = self.sync(self.pair())
            self.refuse(result, "BUSY")
        finally:
            connection.rollback()
            connection.close()
        self.assertEqual(self.state(), before)

    def test_failure_mid_transaction_rolls_back_events_pairs_and_endpoints(self):
        class FailEndpoints(sqlite3.Connection):
            def executemany(self, sql, parameters):
                if sql.startswith("INSERT INTO endpoints"):
                    raise sqlite3.OperationalError(SECRET)
                return super().executemany(sql, parameters)
        self.initialize()
        before = self.state()
        with self.connection_patch(FailEndpoints):
            self.refuse(self.sync(self.pair()), "STORAGE_ERROR")
        self.assertEqual(self.state(), before)

    def test_commit_error_after_commit_is_unknown_and_retry_does_not_duplicate(self):
        class CommitThenFail(sqlite3.Connection):
            def commit(self):
                super().commit()
                raise sqlite3.OperationalError(SECRET)
        self.initialize()
        rows = self.pair()
        with self.connection_patch(CommitThenFail):
            self.refuse(self.sync(rows), "COMMIT_OUTCOME_UNKNOWN", unknown=True)
        self.assertEqual(len(self.state()["pairs"]), 1)
        repeated = self.sync(rows)
        self.assertEqual(repeated["stats"]["replayed_pairs"], 1)
        self.assertEqual(repeated["stats"]["new_pairs"], 0)

    def test_commit_error_before_commit_is_unknown_and_retry_counts_once(self):
        class FailCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError(SECRET)
        self.initialize()
        before = self.state()
        rows = self.pair()
        with self.connection_patch(FailCommit):
            self.refuse(self.sync(rows), "COMMIT_OUTCOME_UNKNOWN", unknown=True)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.sync(rows)["stats"]["new_pairs"], 1)
        self.assertEqual(self.sync(rows)["stats"]["new_pairs"], 0)

    def test_rollback_exception_does_not_claim_confirmed_no_change(self):
        class FailRollback(sqlite3.Connection):
            def executemany(self, sql, parameters):
                if sql.startswith("INSERT INTO endpoints"):
                    raise sqlite3.OperationalError(SECRET)
                return super().executemany(sql, parameters)
            def rollback(self):
                raise sqlite3.OperationalError(SECRET)
        self.initialize()
        before = self.state()
        with self.connection_patch(FailRollback):
            self.refuse(self.sync(self.pair()), "ROLLBACK_OUTCOME_UNKNOWN", unknown=True)
        self.assertEqual(self.state(), before)

    def test_noop_rollback_exception_reports_unknown_even_if_lock_was_released(self):
        class RollbackThenFail(sqlite3.Connection):
            def rollback(self):
                super().rollback()
                raise sqlite3.OperationalError(SECRET)
        self.initialize()
        rows = self.pair()
        self.sync(rows)
        before = self.state()
        with self.connection_patch(RollbackThenFail):
            self.refuse(self.sync(rows), "ROLLBACK_OUTCOME_UNKNOWN", unknown=True)
        self.assertEqual(self.state(), before)

    def test_observed_path_replacement_before_commit_rolls_back_changes(self):
        self.initialize()
        before = self.state()
        inspect = self.module._inspect_storage
        calls = []
        def observed(target, **kwargs):
            result = inspect(target, **kwargs)
            calls.append(result)
            if len(calls) == 3:
                chain, (device, inode, mode) = result
                return chain, (device, inode + 1, mode)
            return result
        with mock.patch.object(self.module, "_inspect_storage", side_effect=observed):
            self.refuse(self.sync(self.pair()), "PATH_CHANGED")
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.state(), before)

    def test_failed_initialization_retains_file_and_never_auto_repairs_it(self):
        with mock.patch.object(self.module, "_connect", side_effect=sqlite3.OperationalError(SECRET)):
            result = self.call(True)
        self.refuse(result, "STORAGE_ERROR")
        self.assertTrue(result["ledger_file_created"])
        self.assertTrue(self.database.is_file())
        self.assertEqual(self.database.read_bytes(), b"")
        self.refuse(self.call(True), "LEDGER_ALREADY_EXISTS")
        self.refuse(self.call(), "STATE_INVALID")

    def test_state_capacity_limits_refuse_before_partial_changes(self):
        for index, limit in enumerate(("bound_events", "bound_payload_bytes", "accepted_pairs", "pair_payload_bytes")):
            with self.subTest(limit=limit):
                if index:
                    self.fixture("limit " + str(index))
                self.initialize()
                before = self.state()
                with mock.patch.dict(self.module.LIMITS, {limit: 0}):
                    self.refuse(self.sync(self.pair()), "RESOURCE_LIMIT")
                self.assertEqual(self.state(), before)
        self.fixture("exact events limit")
        self.initialize()
        with mock.patch.dict(self.module.LIMITS, {"bound_events": 2, "accepted_pairs": 1}):
            self.assertEqual(self.sync(self.pair())["stats"]["new_pairs"], 1)
            self.refuse(self.sync(self.pair("new-")), "RESOURCE_LIMIT")
        self.assertEqual(len(self.state()["pairs"]), 1)

    def test_database_size_and_unexpected_sidecars_refuse_before_open(self):
        self.initialize()
        before = self.database.read_bytes()
        with mock.patch.dict(self.module.LIMITS, {"database_bytes": len(before) - 1}), \
                mock.patch.object(self.module, "_connect", side_effect=AssertionError("must not connect")):
            self.refuse(self.call(), "RESOURCE_LIMIT")
        for suffix in ("-wal", "-shm"):
            sidecar = self.database.with_name(self.database.name + suffix)
            sidecar.write_bytes(b"synthetic sidecar")
            with mock.patch.object(self.module, "_connect", side_effect=AssertionError("must not connect")):
                self.refuse(self.call(), "UNEXPECTED_SIDECAR")
            self.assertEqual(sidecar.read_bytes(), b"synthetic sidecar")
            sidecar.unlink()
        self.assertEqual(self.database.read_bytes(), before)

    def test_link_reparse_nonregular_and_hardlink_metadata_are_refused(self):
        self.initialize()
        real_lstat = Path.lstat
        original = self.database.lstat()
        for changes in ({"st_mode": stat.S_IFLNK | 0o600}, {"st_mode": stat.S_IFIFO | 0o600},
                        {"st_file_attributes": 0x400}, {"st_nlink": 2}):
            with self.subTest(changes=changes):
                values = {name: getattr(original, name) for name in ("st_dev", "st_ino", "st_mode", "st_size", "st_nlink")}
                values["st_file_attributes"] = getattr(original, "st_file_attributes", 0)
                values.update(changes)
                def inspect(path, *args, **kwargs):
                    return SimpleNamespace(**values) if path == self.database else real_lstat(path, *args, **kwargs)
                with mock.patch.object(Path, "lstat", inspect), \
                        mock.patch.object(self.module, "_connect", side_effect=AssertionError("must not connect")):
                    self.refuse(self.call(), "UNSAFE_PATH")

    def test_sidecar_symlink_or_nonregular_metadata_never_reaches_sqlite(self):
        self.initialize()
        sidecar = self.database.with_name(self.database.name + "-journal")
        sidecar.write_bytes(b"owned fixture")
        original = sidecar.lstat()
        real_lstat = Path.lstat
        for mode in (stat.S_IFLNK, stat.S_IFDIR, stat.S_IFIFO):
            values = {name: getattr(original, name) for name in ("st_dev", "st_ino", "st_mode", "st_size", "st_nlink")}
            values["st_mode"] = mode | 0o600
            values["st_file_attributes"] = 0
            def inspect(path, *args, **kwargs):
                return SimpleNamespace(**values) if path == sidecar else real_lstat(path, *args, **kwargs)
            with mock.patch.object(Path, "lstat", inspect), \
                    mock.patch.object(self.module, "_connect", side_effect=AssertionError("must not connect")):
                self.refuse(self.call(), "UNSAFE_PATH")
        self.assertEqual(sidecar.read_bytes(), b"owned fixture")

    def test_invalid_roots_are_rejected_without_path_hooks_or_database_open(self):
        class Hook:
            def __fspath__(self):
                raise AssertionError("path hook invoked")
        for value in ("relative", "../repo", "bad\x00path", Hook(), None):
            with self.subTest(value=type(value).__name__), \
                    mock.patch.object(self.module, "_connect", side_effect=AssertionError("must not connect")):
                result = self.module.initialize_correction_evidence_ledger(value)
                self.refuse(result, "HISTORY_REFUSED")
                self.assertEqual(result["input_reason"], "INVALID_REPO")

    def test_fixed_path_scope_preserves_environment_history_and_unrelated_files(self):
        sentinels = (self.repo / ".env", self.repo / "models" / "nlu_intent.joblib",
                     self.repo / ".venv" / "sentinel.txt", self.learning / "correction_memory.jsonl")
        for index, path in enumerate(sentinels):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((SECRET + str(index)).encode())
        before = {path: path.read_bytes() for path in sentinels}
        environment = dict(os.environ)
        self.initialize()
        self.put(self.pair())
        history = self.history.read_bytes()
        self.sync()
        self.assertEqual(self.history.read_bytes(), history)
        self.assertEqual({path: path.read_bytes() for path in sentinels}, before)
        self.assertEqual(dict(os.environ), environment)
        source = (ROOT / "modules/learning/correction_evidence_ledger.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {"__future__", "pathlib", "uuid", "modules.learning", "modules.learning.learning_history_snapshot"})
        self.assertNotIn("main", [node.name for node in tree.body if isinstance(node, ast.FunctionDef)])

    def test_connections_are_closed_on_success_and_precommit_refusal(self):
        connections = []
        real_connect = self.module._connect
        def capture(target):
            connection = real_connect(target)
            connections.append(connection)
            return connection
        with mock.patch.object(self.module, "_connect", side_effect=capture):
            self.initialize()
            self.sync(self.pair())
            changed = self.pair()
            changed[0]["raw_text"] = "changed"
            self.refuse(self.sync(changed), "EVENT_PAYLOAD_CONFLICT")
        self.assertEqual(len(connections), 3)
        for connection in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
