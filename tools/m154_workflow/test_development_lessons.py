from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import development_lessons as lessons


class FakeModel:
    model = "test-only-no-network"

    def __init__(self):
        self.calls = []
        self.ensure_calls = 0
        self.response = {"findings": []}

    def ensure_installed(self):
        self.ensure_calls += 1

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class DevelopmentLessonsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = lessons.load_lessons(Path(__file__).with_name("lessons.json"))

    def test_task_and_path_select_relevant_lesson(self):
        selected = lessons.select_lessons(self.rows, task="Убрать повтор title после strip",
                                           paths=["modules\\developer_task_ui\\app\\core.py"], tags=[])
        self.assertEqual([x["id"] for x in selected], ["M154.deduplicate-stripped-task-text"])

    def test_unrelated_task_has_no_fallback_memory(self):
        selected = lessons.select_lessons(self.rows, task="Изменить палитру календаря",
                                           paths=["modules/calendar_colors.py"], tags=["palette"])
        self.assertEqual(selected, [])
        self.assertEqual(lessons.render_context(selected), "")

    def test_explicit_tags_select_and_observations_do_not_become_lessons(self):
        observed = copy.deepcopy(self.rows[0])
        observed["status"] = "observed_only"
        observed["id"] = "unreviewed-failure"
        selected = lessons.select_lessons([observed] + self.rows, task="", paths=[], tags=["pipeline"])
        self.assertEqual([x["id"] for x in selected], ["M154.static-is-not-full-check"])

    def test_failed_run_keeps_unknown_cause_and_omits_raw_log(self):
        summary = {"run_id": "a" * 32, "status": "FAIL", "code_commit": "b" * 40,
                   "exit_code": 2, "failed_check": "pipeline", "stderr": "private raw output",
                   "checks": [{"name": "pipeline", "status": "FAIL", "exit_code": 2,
                               "stdout": "private test output"}]}
        incident = lessons.make_observation(summary)
        self.assertEqual(incident["status"], "observed_only")
        self.assertEqual(incident["outcome"], "FAIL")
        self.assertIsNone(incident["root_cause"])
        self.assertIsNone(incident["resolution"])
        self.assertIsNone(incident["training_label"])
        self.assertFalse(incident["is_analyzer_feedback"])
        self.assertNotIn("private", json.dumps(incident))
        self.assertEqual(incident["checks"], [{"name": "pipeline", "status": "FAIL", "exit_code": 2}])

    def test_pass_is_observation_not_an_automatic_verified_lesson(self):
        incident = lessons.make_observation({"status": "PASS", "exit_code": 0})
        self.assertEqual(incident["outcome"], "PASS")
        self.assertEqual(incident["status"], "observed_only")
        self.assertIsNone(incident["training_label"])

    def test_adapter_keeps_system_and_original_prompt_and_records_used_ids(self):
        model = FakeModel()
        selected = lessons.select_lessons(self.rows, task="", paths=[], tags=["pipeline"])
        adapter = lessons.LessonsModelAdapter(model, selected)
        self.assertEqual(model.calls, [])
        self.assertEqual(model.ensure_calls, 0)
        adapter.ensure_installed()
        prompt = 'Original task\n{"request_id":"fixed","request_fingerprint":"unchanged"}'
        response = adapter.generate(system="SYSTEM EXACT", prompt=prompt, max_tokens=350)
        self.assertIs(response, model.response)
        self.assertEqual(model.calls[0]["system"], "SYSTEM EXACT")
        self.assertTrue(model.calls[0]["prompt"].startswith(prompt + "\n\n"))
        self.assertEqual(model.calls[0]["max_tokens"], 350)
        self.assertEqual(adapter.receipts[0]["lesson_ids"], ["M154.static-is-not-full-check"])
        self.assertEqual(adapter.receipts[0]["base_prompt_sha256"], hashlib.sha256(prompt.encode()).hexdigest())
        self.assertEqual(adapter.receipts[0]["status"], "RESPONSE_RECEIVED")

    def test_adapter_with_no_matching_lessons_is_exact_passthrough(self):
        model = FakeModel()
        adapter = lessons.LessonsModelAdapter(model, [])
        adapter.generate(system="S", prompt="P")
        self.assertEqual(model.calls[0], {"system": "S", "prompt": "P", "max_tokens": 1500})
        self.assertEqual(adapter.receipts[0]["lesson_ids"], [])

    def test_context_utf8_bound_and_receipt_ids_match_actual_json(self):
        selected = []
        for i in range(20):
            row = copy.deepcopy(self.rows[0])
            row["id"] = "large-lesson-" + str(i)
            for key in ("symptom", "cause", "prevention", "regression_check"):
                row[key] = "Ж" * 20000
            selected.append(row)
        adapter = lessons.LessonsModelAdapter(FakeModel(), selected)
        prepared = lessons.prepare_context(selected)
        rendered = prepared["text"]
        self.assertEqual(adapter.context, rendered)
        self.assertLessEqual(len(rendered.encode("utf-8")), lessons.MAX_CONTEXT_BYTES)
        payload = json.loads(rendered.split("```json\n", 1)[1].rsplit("\n```", 1)[0])
        self.assertGreater(len(payload["lessons"]), 0)
        self.assertLess(len(payload["lessons"]), len(selected))
        self.assertEqual(adapter.selected_ids, [x["id"] for x in payload["lessons"]])
        self.assertEqual(prepared["lesson_ids"], adapter.selected_ids)

    def test_curated_file_rejects_unreviewed_records(self):
        row = copy.deepcopy(self.rows[0])
        row["status"] = "observed_only"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lessons.json"
            path.write_text(json.dumps({"schema": lessons.LESSONS_SCHEMA, "lessons": [row]}))
            with self.assertRaisesRegex(ValueError, "only verified"):
                lessons.load_lessons(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
