"""Check pre-run descriptions using metadata, mocked boundaries and owned fixtures."""
from __future__ import annotations

import builtins
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_SOURCE = PROJECT_ROOT / "tools/pipeline.py"
sys.dont_write_bytecode = True


class PipelineEffectsTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_pipeline_effects_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        name = "pipeline_effects_under_test"
        previous = sys.modules.get(name)
        self.addCleanup(self.restore_module, name, previous)
        spec = importlib.util.spec_from_file_location(name, PIPELINE_SOURCE)
        assert spec is not None and spec.loader is not None
        self.pipeline = importlib.util.module_from_spec(spec)
        sys.modules[name] = self.pipeline
        spec.loader.exec_module(self.pipeline)
        self.pipeline.PROJECT_ROOT = self.root
        self.pipeline.PIPELINE_LOG_DIR = self.root / "pipeline-logs"
        self.sentinels = {
            ".env": b"DESCRIPTION_MUST_NOT_READ_CONFIG=synthetic-fixture\n",
            "models/nlu_intent.joblib": b"NOT_A_MODEL_DESCRIPTION_MUST_NOT_LOAD\n",
            "data/intents.json": b"NOT_JSON_DESCRIPTION_MUST_NOT_READ\n",
        }
        for relative, raw in self.sentinels.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    @staticmethod
    def restore_module(name: str, previous: object) -> None:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    @staticmethod
    def outputs(description):
        return {path for step in description["steps"] for path in step["default_outputs"]}

    def main(self, flow, *options):
        with mock.patch.object(sys, "argv", ["pipeline.py", flow, *options]), \
                redirect_stdout(io.StringIO()) as output:
            code = self.pipeline.main()
        return code, output.getvalue()

    def test_analyze_discloses_correction_memory_write_and_is_not_execution_result(self):
        data = self.pipeline.describe_flow("analyze")
        self.assertEqual(data["kind"], "SKYNETVS_PIPELINE_DESCRIPTION_V1")
        self.assertEqual(data["schema_version"], 1)
        self.assertTrue(data["known_flow"])
        self.assertEqual(data["execution"], "NOT_RUN")
        self.assertEqual(data["counts"], {"REVIEWED": 5, "UNREVIEWED": 0, "TOTAL": 5})
        self.assertIn("WRITE_DATA", data["effects"])
        self.assertIn("READ_CONFIG", data["effects"])
        self.assertEqual(self.outputs(data), {
            "data/learning/correction_memory.jsonl", "data/learning/correction_evidence_runtime.lock",
            "data/learning/correction_evidence.sqlite3", "data/learning/correction_evidence.sqlite3-journal"})
        self.assertNotIn("TRAIN_MODEL", data["effects"])
        self.assertNotIn("WRITE_MODEL", data["effects"])
        self.assertNotIn("status", data)
        self.assertNotIn("all_steps_passed", data)
        self.assertEqual(json.loads(json.dumps(data)), data)

    def test_full_describes_export_and_is_not_analyze_or_a_training_run(self):
        full = self.pipeline.describe_flow("full")
        analyze = self.pipeline.describe_flow("analyze")
        self.assertEqual(self.outputs(full), {
            "data/learning/correction_memory.jsonl", "data/inbox_unlabeled.jsonl",
            "data/learning/alias_suggestions.jsonl", "data/learning/phrase_correction_suggestions.jsonl",
            "data/learning/correction_evidence_runtime.lock", "data/learning/correction_evidence.sqlite3",
            "data/learning/correction_evidence.sqlite3-journal",
        })
        self.assertNotEqual([x["name"] for x in full["steps"]], [x["name"] for x in analyze["steps"]])
        self.assertNotIn("READ_CONFIG", full["effects"])
        self.assertNotIn("TRAIN_MODEL", full["effects"])
        self.assertNotIn("WRITE_MODEL", full["effects"])
        self.assertEqual(full["counts"], {"REVIEWED": 5, "UNREVIEWED": 0, "TOTAL": 5})

    def test_export_modes_describe_outputs_and_rewrites_without_additions(self):
        promotion = self.pipeline.describe_flow("promote")
        raw = self.pipeline.describe_flow("raw_inbox")
        self.assertEqual(self.outputs(promotion), {
            "data/inbox_unlabeled.jsonl", "data/learning/alias_suggestions.jsonl",
            "data/learning/phrase_correction_suggestions.jsonl",
        })
        self.assertEqual(self.outputs(raw), {"data/inbox_unlabeled.jsonl"})
        self.assertIn("data/learning/resolver_candidates.jsonl", raw["steps"][0]["default_inputs"])
        self.assertNotIn("data/learning/command_history.jsonl", raw["steps"][0]["default_inputs"])
        for data in (promotion, raw):
            self.assertIn("WRITE_DATA", data["effects"])
            self.assertTrue(any("even when no new" in note for note in data["steps"][0]["notes"]))
            self.assertNotIn("WRITE_MODEL", data["effects"])

    def test_label_discloses_interaction_and_actual_changed_files(self):
        data = self.pipeline.describe_flow("label")
        self.assertEqual(self.outputs(data), {"data/intents.json", "data/inbox_labeled.jsonl"})
        self.assertIn("INTERACTIVE", data["effects"])
        self.assertIn("WRITE_DATA", data["effects"])
        self.assertTrue(data["steps"][0]["interactive"])
        self.assertTrue(any("quit or skip" in note for note in data["steps"][0]["notes"]))
        self.assertNotIn("TRAIN_MODEL", data["effects"])

    def test_train_describes_active_model_replacement_before_quick_test(self):
        data = self.pipeline.describe_flow("train")
        self.assertEqual(self.outputs(data), {"models/nlu_intent.joblib"})
        self.assertIn("data/nlu_training_recipe.json", data["steps"][0]["default_inputs"])
        self.assertIn("TRAIN_MODEL", data["effects"])
        self.assertIn("WRITE_MODEL", data["effects"])
        self.assertIn("before the printed quick test", data["steps"][0]["description"])
        self.assertFalse(data["steps"][0]["interactive"])

    def test_prediction_descriptions_include_conditional_model_and_config_reads(self):
        for flow in ("eval", "nlu_diag", "nlu_risk", "nlu_risk_guard"):
            with self.subTest(flow=flow):
                data = self.pipeline.describe_flow(flow)
                self.assertTrue({"READ_CONFIG", "READ_DATA", "LOAD_MODEL"}.issubset(data["effects"]))
                self.assertIn("models/nlu_intent.joblib", data["steps"][0]["default_inputs"])
                self.assertNotIn("TRAIN_MODEL", data["effects"])
                self.assertNotIn("WRITE_MODEL", data["effects"])
                self.assertEqual(data["execution"], "NOT_RUN")

    def test_command_audit_reads_actions_as_source_text(self):
        data = self.pipeline.describe_flow("audit")
        self.assertIn("READ_SOURCE", data["effects"])
        self.assertIn("modules/actions.py", data["steps"][0]["default_inputs"])
        self.assertTrue(any("read as text" in note for note in data["steps"][0]["notes"]))

    def test_check_honestly_reports_partial_effect_coverage(self):
        data = self.pipeline.describe_flow("check")
        total = len(self.pipeline.available_flows()["check"])
        self.assertEqual(data["counts"], {"REVIEWED": 4, "UNREVIEWED": total - 4, "TOTAL": total})
        self.assertGreater(data["counts"]["UNREVIEWED"], 0)
        self.assertIn("UNREVIEWED", data["effects"])
        self.assertIn("LOAD_MODEL", data["effects"])
        self.assertNotIn("READ_ONLY", json.dumps(data))
        self.assertEqual([item["index"] for item in data["steps"]], list(range(1, total + 1)))
        self.assertTrue(any("not an exhaustive" in note for note in data["notes"]))

    def test_changed_argument_shapes_never_inherit_reviewed_effects(self):
        commands = [
            [sys.executable, "train/train_nlu.py", "--different"],
            [sys.executable, "-I", "train/train_nlu.py"],
            [sys.executable, "./train/train_nlu.py"],
            ["another-python", "train/train_nlu.py"],
            [sys.executable, "tools/eval_unreviewed_windows.py"],
            [sys.executable], [],
        ]
        steps = [self.pipeline.Step("case " + str(index), cmd) for index, cmd in enumerate(commands)]
        with mock.patch.object(self.pipeline, "available_flows", return_value={"fixture": steps}):
            data = self.pipeline.describe_flow("fixture")
        self.assertEqual(data["counts"], {"REVIEWED": 0, "UNREVIEWED": len(steps), "TOTAL": len(steps)})
        self.assertEqual(data["effects"], ["UNREVIEWED"])
        for item in data["steps"]:
            self.assertEqual(item["review"], "UNREVIEWED")
            self.assertEqual(item["default_outputs"], [])

    def test_unknown_or_empty_flow_has_no_execution_success_shape(self):
        with mock.patch.object(self.pipeline, "available_flows", return_value={"empty": []}):
            for flow in ("missing", "empty"):
                data = self.pipeline.describe_flow(flow)
                self.assertFalse(data["known_flow"])
                self.assertEqual(data["reason_code"], "unknown_flow")
                self.assertEqual(data["execution"], "NOT_RUN")
                self.assertEqual(data["counts"], {"REVIEWED": 0, "UNREVIEWED": 0, "TOTAL": 0})
                self.assertEqual(data["steps"], [])
                self.assertNotIn("status", data)

    def test_all_descriptions_import_no_runtime_read_no_inputs_and_launch_nothing(self):
        before = self.snapshot()
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.split(".", 1)[0] in {"modules", "tools", "train", "joblib", "numpy", "sklearn", "dotenv"}:
                raise AssertionError("Description tried to import runtime: " + name)
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=guarded_import), \
                mock.patch("builtins.open", side_effect=AssertionError("Description opened a file")), \
                mock.patch.object(Path, "open", side_effect=AssertionError("Description opened a path")), \
                mock.patch.object(Path, "mkdir", side_effect=AssertionError("Description created a directory")), \
                mock.patch.object(self.pipeline.subprocess, "Popen", side_effect=AssertionError("Child launched")), \
                mock.patch.object(self.pipeline, "run_flow_result", side_effect=AssertionError("Flow executed")):
            for name, steps in self.pipeline.available_flows().items():
                data = self.pipeline.describe_flow(name)
                self.assertTrue(data["known_flow"])
                self.assertEqual(data["counts"]["TOTAL"], len(steps))
                self.assertEqual([x["name"] for x in data["steps"]], [x.name for x in steps])
        self.assertEqual(self.snapshot(), before)

    def test_mutating_returned_description_does_not_change_registry(self):
        first = self.pipeline.describe_flow("train")
        first["steps"][0]["effects"].append("FAKE_EFFECT")
        first["steps"][0]["default_outputs"].clear()
        second = self.pipeline.describe_flow("train")
        self.assertNotIn("FAKE_EFFECT", second["steps"][0]["effects"])
        self.assertEqual(self.outputs(second), {"models/nlu_intent.joblib"})

    def test_describe_main_returns_before_output_paths_or_execution(self):
        before = self.snapshot()
        with mock.patch.object(self.pipeline, "run_flow_result", side_effect=AssertionError("Flow executed")), \
                mock.patch.object(self.pipeline, "_select_log_path", side_effect=AssertionError("Log selected")), \
                mock.patch.object(Path, "open", side_effect=AssertionError("File opened")):
            for options in (("--describe",), ("--describe", "--no-log")):
                code, output = self.main("train", *options)
                self.assertEqual(code, 0)
                self.assertIn("execution=NOT_RUN", output)
                self.assertIn("models/nlu_intent.joblib", output)
                self.assertIn("WRITE_MODEL", output)
                self.assertNotIn("[DONE]", output)
        self.assertEqual(self.snapshot(), before)

    def test_output_options_are_rejected_before_files_or_children(self):
        target = self.root / "missing" / "do-not-create.json"
        before = self.snapshot()
        combinations = [
            ("--summary-json", str(target)), ("--log-file", str(target)),
            ("--no-log", "--log-file", str(target)),
            ("--summary-json", str(target), "--log-file", str(target)),
        ]
        with mock.patch.object(self.pipeline, "run_flow_result", side_effect=AssertionError("Flow executed")), \
                mock.patch.object(self.pipeline, "print_flow_description") as describe:
            for options in combinations:
                code, output = self.main("train", "--describe", *options)
                self.assertEqual(code, 2)
                self.assertIn("cannot be combined", output)
            describe.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(target.parent.exists())

    def test_unknown_describe_cli_is_nonzero_without_files(self):
        before = self.snapshot()
        with mock.patch.object(self.pipeline, "run_flow_result", side_effect=AssertionError("Flow executed")):
            code, output = self.main("missing", "--describe")
        self.assertEqual(code, 2)
        self.assertIn("Unknown flow", output)
        self.assertEqual(self.snapshot(), before)

    def test_help_priority_and_effect_descriptions_are_preserved(self):
        before = self.snapshot()
        with mock.patch.object(self.pipeline, "run_flow_result", side_effect=AssertionError("Flow executed")):
            code, output = self.main("train", "--describe", "--help", "--summary-json", "unused.json")
        self.assertEqual(code, 0)
        self.assertIn("--describe", output)
        self.assertIn("update correction memory", output)
        self.assertIn("replace models/nlu_intent.joblib", output)
        self.assertIn("does not disable data/model writes", output)
        self.assertNotIn("Run analysis reports only", output)
        self.assertNotIn("Analyze + promote", output)
        self.assertEqual(self.snapshot(), before)

    def test_no_describe_flag_preserves_execution_and_json_route(self):
        outcome = self.pipeline.FlowResult("fixture", (self.pipeline.StepResult("safe", "PASS", 0),), 0)
        target = self.root / "actual-result.json"
        with mock.patch.object(self.pipeline, "run_flow_result", return_value=outcome) as run, \
                mock.patch.object(self.pipeline, "print_flow_description", side_effect=AssertionError("Unexpected description")):
            code, _ = self.main("fixture", "--no-log", "--summary-json", str(target))
        run.assert_called_once_with("fixture", log_file=None)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["kind"], "SKYNETVS_PIPELINE_RESULT_V1")

    def test_actual_cli_describes_isolated_copy_without_executing_child_stubs(self):
        copied = self.root / "tools/pipeline.py"
        copied.parent.mkdir(parents=True)
        copied.write_bytes(PIPELINE_SOURCE.read_bytes())
        flows = self.pipeline.available_flows()
        scripts = {step.cmd[1] for flow in ("train", "full") for step in flows[flow]}
        sentinel_source = 'from pathlib import Path\nPath("CHILD_EXECUTED").write_text("forbidden")\nraise SystemExit(37)\n'
        for script in scripts:
            path = self.root / script
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(sentinel_source, encoding="ascii")
        before = self.snapshot()
        for flow in ("train", "full"):
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(copied), flow, "--describe"],
                cwd=str(self.root), capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[DESCRIBE]", result.stdout)
            self.assertIn("execution=NOT_RUN", result.stdout)
            self.assertNotIn("[RUN]", result.stdout)
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
