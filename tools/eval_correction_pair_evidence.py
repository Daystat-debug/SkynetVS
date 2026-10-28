"""Fixed synthetic tests for the pure identified correction-pair planner.

Run: python -I -S -B -X utf8 tools/eval_correction_pair_evidence.py
No application entry point, settings, models, live history or builder is run.
"""
from __future__ import annotations

import ast
import builtins
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-private-pair-marker-93"


class CorrectionPairEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_pair_evidence_")
        self.addCleanup(temporary.cleanup)
        self.temporary = Path(temporary.name)
        self.module = self.load("planner", "modules/learning/correction_pair_evidence.py")

    @staticmethod
    def load(name, relative):
        spec = importlib.util.spec_from_file_location("synthetic_pair_" + name, ROOT / relative)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def row(event_id="failed", *, accepted=False, text=None, ts=None, **changes):
        text = text if text is not None else "открой блокнот" if accepted else "запусти редактор"
        row = {"event_id": event_id, "ts": ts or ("2026-01-01T12:00:01" if accepted else "2026-01-01T12:00:00"),
               "raw_text": text, "final_text": text, "accepted": accepted,
               "mode": "text", "immediate_label": "accepted" if accepted else "rejected",
               "missing_slots": [], "meta": {"intent": "OPEN_APP" if accepted else None,
               "confidence": 0.9 if accepted else 0.1, "slots": {"app": "notepad"},
               "say": "", "_text": text}}
        row.update(changes)
        return row

    def pair(self):
        return [self.row(), self.row("corrected", accepted=True)]

    def plan(self, rows):
        result = self.module.plan_correction_pair_evidence(rows, snapshot_complete=True)
        self.assertEqual(result["kind"], "SKYNETVS_CORRECTION_PAIR_EVIDENCE_PLAN_V1")
        self.assertFalse(result["scope"]["counting_applied"])
        self.assertFalse(result["scope"]["persistent_replay_protection"])
        self.assertFalse(result["scope"]["independent_observations_verified"])
        self.assertEqual(result["scope"]["training_readiness"], "NOT_ASSESSED")
        if result["status"] == "REFUSED":
            self.assertEqual(result["pairs"], [])
            self.assertIsNone(result["observations"])
            self.assertNotIn(SECRET, json.dumps(result))
        else:
            self.assertEqual(result["status"], "READY")
            self.assertIsNone(result["reason"])
            self.assertEqual(result["observations"]["candidate_pairs"], len(result["pairs"]))
        return result

    def test_completeness_is_required_exact_bool_and_not_attested(self):
        with self.assertRaises(TypeError):
            self.module.plan_correction_pair_evidence(self.pair())
        for flag, reason in ((False, "INCOMPLETE_SNAPSHOT"), (1, "INVALID_COMPLETENESS_FLAG"),
                             (None, "INVALID_COMPLETENESS_FLAG"), (SECRET, "INVALID_COMPLETENESS_FLAG")):
            result = self.module.plan_correction_pair_evidence(self.pair(), snapshot_complete=flag)
            self.assertEqual(result["status"], "REFUSED")
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["pairs"], [])
            self.assertIsNone(result["observations"])
            self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(self.plan(self.pair())["scope"]["snapshot_completeness"],
                         "CALLER_ASSERTED_NOT_VERIFIED")

    def test_only_exact_list_or_tuple_are_accepted_without_iteration_hooks(self):
        class ExplosiveList(list):
            def __iter__(self):
                raise AssertionError("must not iterate subclass")
            def __len__(self):
                raise AssertionError("must not size subclass")
        for value in ({}, SECRET, iter(self.pair()), ExplosiveList(self.pair())):
            self.assertEqual(self.plan(value)["reason"], "INVALID_INPUT_CONTAINER")
        self.assertEqual(len(self.plan(tuple(self.pair()))["pairs"]), 1)

    def test_pair_has_versioned_endpoint_identity_without_count_increment(self):
        rows = self.pair()
        result = self.plan(rows)
        pair = result["pairs"][0]
        self.assertEqual(pair["pair_identity"], {"rule_version": "adjacent_unique_observation_v1",
                                               "failed_event_id": "failed", "corrected_event_id": "corrected"})
        self.assertEqual((pair["failed_index"], pair["corrected_index"]), (0, 1))
        self.assertEqual(pair["corrected_intent"], "OPEN_APP")
        self.assertEqual(pair["corrected_confidence"], 0.9)
        self.assertEqual(pair["delta_sec"], 1.0)
        self.assertNotIn("count", pair)
        self.assertEqual(result["observations"]["barrier_rows"], 0)

    def test_clean_monotonic_pairs_match_legacy_candidate_projection(self):
        analyzer = self.load("legacy", "modules/learning/feedback_analyzer.py").FeedbackAnalyzer(str(self.temporary))
        rows = self.pair() + [self.row("failed2", text="открывай текстовик", ts="2026-01-01T12:00:05"),
                             self.row("corrected2", accepted=True, text="запусти блокнот", ts="2026-01-01T12:00:06")]
        fields = ("failed_text", "corrected_text", "corrected_intent", "corrected_confidence",
                  "corrected_slots", "delta_sec")
        for padded_intent in (False, True):
            with self.subTest(padded_intent=padded_intent):
                selected = copy.deepcopy(rows)
                if padded_intent:
                    for row in selected:
                        if row["accepted"]:
                            row["meta"]["intent"] = " open_app "
                old = analyzer._find_correction_pairs(selected, limit=None)
                new = self.plan(selected)["pairs"]
                self.assertEqual([{key: row[key] for key in fields} for row in new],
                                 [{key: row[key] for key in fields} for row in old])
                self.assertTrue(all(row["count"] == 1 for row in old))

    def test_original_order_and_timestamp_ties_are_never_sorted(self):
        rows = self.pair()
        rows[1]["ts"] = rows[0]["ts"]
        self.assertEqual(len(self.plan(rows)["pairs"]), 1)
        self.assertEqual(self.plan(list(reversed(rows)))["pairs"], [])
        rows = self.pair()
        self.assertEqual(self.plan(list(reversed(rows)))["pairs"], [])
        analyzer = self.load("sort_reference", "modules/learning/feedback_analyzer.py").FeedbackAnalyzer(str(self.temporary))
        self.assertEqual(len(analyzer._find_correction_pairs(list(reversed(rows)), limit=None)), 1)
        rows[0]["ts"] = "2026-01-01T12:00:02"
        self.assertEqual(self.plan(rows)["pairs"], [])

    def test_time_and_confidence_thresholds_are_inclusive(self):
        for timestamp, confidence, count in (("2026-01-01T12:00:00", 0.4, 1),
                                            ("2026-01-01T12:01:00", 0.4, 1),
                                            ("2026-01-01T12:01:00.000001", 0.4, 0),
                                            ("2026-01-01T12:00:01", 0.399999, 0)):
            with self.subTest(timestamp=timestamp, confidence=confidence):
                rows = self.pair()
                rows[1]["ts"] = timestamp
                rows[1]["meta"]["confidence"] = confidence
                self.assertEqual(len(self.plan(rows)["pairs"]), count)

    def test_existing_text_and_missing_slot_filters_remain(self):
        for text in ("повтори", " ЕЩЁ ", "еще"):
            for index in (0, 1):
                rows = self.pair()
                rows[index]["raw_text"] = text
                self.assertEqual(self.plan(rows)["pairs"], [])
        rows = self.pair()
        rows[1]["missing_slots"] = ["app"]
        self.assertEqual(self.plan(rows)["pairs"], [])
        rows = self.pair()
        rows[1]["raw_text"] = "  " + rows[0]["raw_text"] + "  "
        self.assertEqual(self.plan(rows)["pairs"], [])
        rows = self.pair()
        rows[0]["raw_text"] = ""
        self.assertEqual(len(self.plan(rows)["pairs"]), 1)
        rows[0]["raw_text"] = "   "
        self.assertEqual(self.plan(rows)["pairs"], [])

    def test_identical_replays_block_every_occurrence_without_removal(self):
        rows = self.pair()
        result = self.plan(rows + copy.deepcopy(rows))
        self.assertEqual(result["pairs"], [])
        self.assertEqual(result["observations"]["repeated_event_id_groups"], 2)
        self.assertEqual(result["observations"]["repeated_event_id_rows"], 4)
        self.assertEqual(result["observations"]["conflicting_event_id_groups"], 0)
        self.assertEqual(result["observations"]["barrier_rows"], 4)

    def test_later_conflict_quarantines_earlier_candidate(self):
        rows = self.pair()
        changed = copy.deepcopy(rows[1])
        changed["future"] = {"nested": [SECRET]}
        result = self.plan(rows + [changed])
        self.assertEqual(result["pairs"], [])
        self.assertEqual(result["observations"]["repeated_event_id_groups"], 1)
        self.assertEqual(result["observations"]["conflicting_event_id_groups"], 1)
        self.assertNotIn(SECRET, json.dumps(result))

    def test_invalid_later_same_id_is_counted_before_eligibility(self):
        for invalid in ("schema", "nan", "object", "cycle"):
            with self.subTest(invalid=invalid):
                rows = self.pair()
                bad = copy.deepcopy(rows[1])
                if invalid == "schema":
                    bad["meta"] = SECRET
                elif invalid == "nan":
                    bad["future"] = float("nan")
                elif invalid == "object":
                    bad["future"] = object()
                else:
                    bad["future"] = bad
                result = self.plan(rows + [bad])
                self.assertEqual(result["status"], "READY")
                self.assertEqual(result["pairs"], [])
                self.assertEqual(result["observations"]["repeated_event_id_rows"], 2)
                self.assertEqual(result["observations"]["invalid_rows"], 1)

    def test_legacy_nonobject_and_invalid_rows_remain_positional_barriers(self):
        legacy = self.row("legacy")
        del legacy["event_id"]
        for barrier in (legacy, None, [], {"event_id": "bad", "ts": "broken"},
                        self.row("empty", text=""), self.row("low", accepted=True)):
            if type(barrier) is dict and barrier.get("event_id") == "low":
                barrier["meta"]["confidence"] = 0.1
            rows = self.pair()
            result = self.plan([rows[0], barrier, rows[1]])
            self.assertEqual(result["pairs"], [])
        repeated = self.row("repeated", accepted=True)
        rows = self.pair()
        self.assertEqual(self.plan([rows[0], repeated, repeated, rows[1]])["pairs"], [])

    def test_corrected_id_cannot_supply_two_failed_observations(self):
        rows = self.pair()
        rows += [self.row("another-failure", text="другое непонимание"), copy.deepcopy(rows[1])]
        result = self.plan(rows)
        self.assertEqual(result["pairs"], [])
        unique = self.pair() + [self.row("failed2"), self.row("corrected2", accepted=True)]
        pairs = self.plan(unique)["pairs"]
        corrected_ids = [row["pair_identity"]["corrected_event_id"] for row in pairs]
        self.assertEqual(len(corrected_ids), len(set(corrected_ids)))
        self.assertEqual(len(pairs), 2)

    def test_canonical_conflicts_agree_with_existing_v2_auditor(self):
        auditor = self.load("auditor", "tools/audit_learning_data.py")
        variants = (({"a": 1, "b": "ёж"}, {"b": "ёж", "a": 1}, 0),
                    (1, 1.0, 1), (True, 1, 1), ([1, 2], [2, 1], 1),
                    ("a", " a", 1), (0.0, -0.0, 1))
        for left, right, conflicts in variants:
            rows = [self.row("same", future=left), self.row("same", future=right)]
            result = self.plan(rows)
            item = auditor._new_input("command_history")
            tracker = auditor._EventPayloads()
            for row in rows:
                tracker.record(row, item)
            self.assertEqual(result["observations"]["conflicting_event_id_groups"], conflicts)
            self.assertEqual(item["findings"]["conflicting_event_id_groups"], conflicts)

    def test_ids_are_exact_and_identity_does_not_depend_on_index(self):
        rows = [self.row(" ID "), self.row("id", accepted=True)]
        first = self.plan(rows)["pairs"][0]
        second = self.plan([None] + rows)["pairs"][0]
        self.assertEqual(first["pair_identity"], second["pair_identity"])
        self.assertEqual(first["pair_identity"]["failed_event_id"], " ID ")
        self.assertEqual((second["failed_index"], second["corrected_index"]), (1, 2))

    def test_strict_schema_avoids_truthiness_and_number_coercion(self):
        mutations = [lambda row: row.update(accepted="yes"),
                     lambda row: row.update(missing_slots=""),
                     lambda row: row["meta"].update(intent=" "),
                     lambda row: row["meta"].update(confidence=True),
                     lambda row: row["meta"].update(confidence="0.9"),
                     lambda row: row["meta"].update(confidence=1.1),
                     lambda row: row["meta"].update(slots=[])]
        for mutate in mutations:
            rows = self.pair()
            mutate(rows[1])
            self.assertEqual(self.plan(rows)["pairs"], [])

    def test_aware_offsets_work_without_sorting_and_mixed_modes_refuse(self):
        rows = self.pair()
        rows[0]["ts"] = "2026-01-01T12:00:00+02:00"
        rows[1]["ts"] = "2026-01-01T11:00:30+01:00"
        self.assertEqual(self.plan(rows)["pairs"][0]["delta_sec"], 30.0)
        mixed = self.pair() + [self.row("aware-barrier", ts="2026-01-01T12:00:02+00:00")]
        del mixed[-1]["event_id"]
        self.assertEqual(self.plan(mixed)["reason"], "MIXED_TIMESTAMP_MODES")

    def test_invalid_timestamps_and_unicode_are_barriers(self):
        for timestamp in (None, "broken", 0):
            rows = self.pair()
            rows[1]["ts"] = timestamp
            self.assertEqual(self.plan(rows)["pairs"], [])
        rows = self.pair()
        rows[1]["future"] = "\ud800"
        result = self.plan(rows)
        self.assertEqual(result["pairs"], [])
        self.assertEqual(result["observations"]["invalid_rows"], 1)

    def test_row_and_total_canonical_limits_refuse_without_partial_pairs(self):
        rows = self.pair() + [self.row("third")]
        with mock.patch.object(self.module, "MAX_ROWS", 2):
            self.assertEqual(self.plan(rows)["reason"], "RESOURCE_LIMIT")
        with mock.patch.object(self.module, "MAX_CANONICAL_TOTAL_BYTES", 1):
            self.assertEqual(self.plan(rows)["reason"], "RESOURCE_LIMIT")
        rows[-1]["future"] = "x" * 2000
        with mock.patch.object(self.module, "MAX_CANONICAL_ROW_BYTES", 1000):
            self.assertEqual(self.plan(rows)["reason"], "RESOURCE_LIMIT")

    def test_depth_node_and_integer_limits_are_not_swallowed_as_barriers(self):
        for field, limit, extra in (("MAX_JSON_DEPTH", 4, [[[[[[0]]]]]]),
                                    ("MAX_JSON_NODES_PER_ROW", 50, list(range(60))),
                                    ("MAX_INTEGER_BITS", 32, 1 << 33)):
            rows = self.pair() + [self.row("limited", future=extra)]
            with mock.patch.object(self.module, field, limit):
                self.assertEqual(self.plan(rows)["reason"], "RESOURCE_LIMIT")

    def test_shared_reference_expansion_is_bounded_before_serialization(self):
        shared = [0] * 20
        rows = self.pair() + [self.row("expanded", future=[shared] * 20)]
        with mock.patch.object(self.module, "MAX_JSON_NODES_PER_ROW", 100):
            self.assertEqual(self.plan(rows)["reason"], "RESOURCE_LIMIT")

    def test_global_work_budgets_include_uncanonicalizable_rows(self):
        invalid = {"event_id": "bad", "visited": list(range(20)), "bad": object()}
        with mock.patch.object(self.module, "MAX_TOTAL_VISITED_NODES", 100):
            self.assertEqual(self.plan([invalid])["status"], "READY")
            self.assertEqual(self.plan([invalid] * 10)["reason"], "RESOURCE_LIMIT")
        invalid = {"event_id": "bad", "bad": object(), "ts": " " * 800 + "2026-01-01T12:00:00"}
        with mock.patch.object(self.module, "MAX_TOTAL_SCALAR_UNITS", 1500):
            self.assertEqual(self.plan([invalid])["status"], "READY")
            self.assertEqual(self.plan([invalid] * 2)["reason"], "RESOURCE_LIMIT")

    def test_oversized_id_or_timestamp_refuses_before_unbounded_parse(self):
        for field in ("event_id", "ts"):
            invalid = {"bad": object(), "event_id": "bad", "ts": "broken"}
            invalid[field] = " " * 1100
            with mock.patch.object(self.module, "MAX_CANONICAL_ROW_BYTES", 1000):
                self.assertEqual(self.plan(self.pair() + [invalid])["reason"], "RESOURCE_LIMIT")

    def test_subclass_and_unsupported_values_do_not_execute_callbacks(self):
        class Explosive:
            def __repr__(self):
                raise AssertionError("must not stringify private value")
        class ExplosiveString(str):
            def strip(self, *args):
                raise AssertionError("must not invoke subclass")
        for value in (Explosive(), ExplosiveString(SECRET)):
            rows = self.pair()
            rows[1]["future"] = value
            result = self.plan(rows)
            self.assertEqual(result["pairs"], [])
            self.assertEqual(result["observations"]["uncomparable_rows"], 1)
            self.assertNotIn(SECRET, json.dumps(result))

    def test_output_is_deterministic_detached_and_requires_no_io(self):
        rows = self.pair()
        rows[1]["meta"]["slots"]["nested"] = {"items": [1, 2]}
        before = copy.deepcopy(rows)
        with mock.patch.object(builtins, "open", side_effect=AssertionError("unexpected I/O")):
            first = self.plan(rows)
            second = self.plan(rows)
        self.assertEqual(first, second)
        self.assertEqual(rows, before)
        first["pairs"][0]["corrected_slots"]["nested"]["items"].append(3)
        self.assertEqual(rows, before)
        rows[1]["meta"]["slots"]["nested"]["items"].append(4)
        self.assertEqual(second["pairs"][0]["corrected_slots"]["nested"]["items"], [1, 2])
        tree = ast.parse((ROOT / "modules/learning/correction_pair_evidence.py").read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertEqual(imports, {"__future__", "datetime", "json", "math"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
