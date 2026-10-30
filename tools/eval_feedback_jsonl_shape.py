"""M158 regression: FeedbackAnalyzer ignores JSONL values other than objects.

Reads exclusively synthetic TemporaryDirectory inputs. No model, training, network,
real project data, writing to the project, or Git operations. Run with python -I -B.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "modules" / "learning" / "feedback_analyzer.py"
NAMES = (
    ("command_history.jsonl", "command_history"),
    ("nlu_hard_cases.jsonl", "hard_cases"),
    ("action_failures.jsonl", "action_failures"),
    ("resolver_candidates.jsonl", "resolver_candidates"),
)
NONOBJECTS = {
    "array": [], "nested_array": [{}], "null": None, "boolean": False,
    "number": 17, "string": "обманчивый журнал",
}


def load_analyzer():
    spec = importlib.util.spec_from_file_location("m158_feedback_analyzer_tested", TARGET)
    if spec is None or spec.loader is None:
        raise RuntimeError("M158_TARGET_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FeedbackAnalyzer


Analyzer = load_analyzer()


class FeedbackJsonlShapeRegression(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="skynetvs_m158_synthetic_")
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name)
        self.analyzer = Analyzer(str(self.data))

    def write(self, filename, rows):
        (self.data / filename).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
        )

    def summary(self):
        return self.analyzer.analyze(correction_limit=None)

    def test_all_logs_missing(self):
        self.assertEqual(self.summary()["totals"], dict.fromkeys((b for a, b in NAMES), 0))

    def test_empty_lines_ignored(self):
        (self.data / "nlu_hard_cases.jsonl").write_text("  \n\t\n", encoding="utf-8")
        self.assertEqual(self.summary()["totals"]["hard_cases"], 0)

    def test_invalid_json_retains_valid_rows(self):
        (self.data / "nlu_hard_cases.jsonl").write_text(
            '{not-json}\n{"raw_text":"корректная фраза","reason":"test"}\n', encoding="utf-8"
        )
        report = self.summary()
        self.assertEqual(report["totals"]["hard_cases"], 1)
        self.assertEqual(report["top_hard_cases"][0]["text"], "корректная фраза")

    def test_json_object_is_still_accepted(self):
        self.write("nlu_hard_cases.jsonl", [{"raw_text": "тест"}, {}])
        self.assertEqual(self.summary()["totals"]["hard_cases"], 2)

    def test_multiple_valid_records_preserved(self):
        self.write("nlu_hard_cases.jsonl", [{"raw_text": "первый"}, {"raw_text": "второй"}])
        report = self.summary()
        self.assertEqual(report["totals"]["hard_cases"], 2)
        self.assertEqual({r["text"] for r in report["top_hard_cases"]}, {"первый", "второй"})

    def test_unicode_valid_record_preserved(self):
        self.write("nlu_hard_cases.jsonl", [{"raw_text": "ёжик и emoji 😀"}])
        self.assertEqual(self.summary()["top_hard_cases"][0]["text"], "ёжик и emoji 😀")

    def test_json_nonobject_with_malformed_and_object(self):
        (self.data / "nlu_hard_cases.jsonl").write_text(
            '[]\nnot-json\n{"raw_text":"единственная"}\nnull\n', encoding="utf-8"
        )
        self.assertEqual(self.summary()["totals"]["hard_cases"], 1)

    def test_valid_correction_pair_semantics_unchanged(self):
        rows = [
            {"ts": "2026-01-02T03:04:05", "raw_text": "открой блокнат", "final_text": "открой блокнат",
             "accepted": False, "meta": {"intent": "UNKNOWN", "confidence": 0.1}},
            {"ts": "2026-01-02T03:04:07", "raw_text": "открой блокнот", "final_text": "открой блокнот",
             "accepted": True, "meta": {"intent": "OPEN_APP", "confidence": 0.95,
                                      "slots": {"app": "notepad"}}},
        ]
        self.write("command_history.jsonl", rows)
        result = self.summary()
        self.assertEqual(result["totals"]["command_history"], 2)
        self.assertEqual(len(result["correction_pairs"]), 1)
        self.assertEqual(result["correction_pairs"][0]["corrected_text"], "открой блокнот")

    def test_scattered_nonobjects_do_not_create_correction_pair(self):
        self.write("command_history.jsonl", [[], None, 123, True])
        report = self.summary()
        self.assertEqual(report["totals"]["command_history"], 0)
        self.assertEqual(report["correction_pairs"], [])


def make_scalar_case(filename, summary_key, scalar):
    def test(self):
        valid = {"raw_text": "исправная запись", "reason": "synthetic"}
        self.write(filename, [scalar, valid])
        report = self.summary()
        self.assertEqual(report["totals"][summary_key], 1)
    return test


for file_name, summary_key in NAMES:
    for label, scalar in NONOBJECTS.items():
        name = f"test_{summary_key}_skips_{label}"
        setattr(FeedbackJsonlShapeRegression, name, make_scalar_case(file_name, summary_key, scalar))


if __name__ == "__main__":
    unittest.main(verbosity=2)
