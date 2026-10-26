"""Pipeline JSON regression checks using temporary or mocked child processes."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_SOURCE = PROJECT_ROOT / "tools/pipeline.py"
sys.dont_write_bytecode = True


class PipelineSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_pipeline_summary_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        name = "pipeline_summary_under_test"
        previous = sys.modules.get(name)
        self.addCleanup(self.restore_module, name, previous)
        spec = importlib.util.spec_from_file_location(name, PIPELINE_SOURCE)
        assert spec is not None and spec.loader is not None
        self.pipeline = importlib.util.module_from_spec(spec)
        sys.modules[name] = self.pipeline
        spec.loader.exec_module(self.pipeline)
        self.pipeline.PROJECT_ROOT = self.root
        self.pipeline.PIPELINE_LOG_DIR = self.root / "pipeline-logs"

    @staticmethod
    def restore_module(name: str, previous: object) -> None:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous

    def step(self, name: str, source: str = "pass"):
        return self.pipeline.Step(name, [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", source])

    def windows_step(self):
        return next(step for step in self.pipeline.available_flows()["audio_control"]
                    if "tools/eval_audio_control_windows.py" in step.cmd)

    def run_steps(self, steps, flow="fixture"):
        output, log = io.StringIO(), io.StringIO()
        with mock.patch.object(self.pipeline, "available_flows", return_value={"fixture": steps}), \
                redirect_stdout(output):
            result = self.pipeline.run_flow_result(flow, log_file=log)
        self.assertEqual(output.getvalue(), log.getvalue())
        return result, output.getvalue()

    def run_main(self, steps, *options, flow="fixture"):
        with mock.patch.object(self.pipeline, "available_flows", return_value={"fixture": steps}), \
                mock.patch.object(sys, "argv", ["pipeline.py", flow, *options]), \
                redirect_stdout(io.StringIO()) as output:
            code = self.pipeline.main()
        return code, output.getvalue()

    def test_pass_result_has_versioned_unicode_metadata_without_raw_output(self) -> None:
        result, output = self.run_steps([
            self.step("Проверка текста", 'print("PRIVATE_CHILD_OUTPUT [SKIP] inner case")'),
        ])
        data = result.to_dict()
        self.assertEqual(data["kind"], "SKYNETVS_PIPELINE_RESULT_V1")
        self.assertEqual(data["schema_version"], 1)
        self.assertRegex(data["run_id"], r"^[0-9a-f]{32}$")
        self.assertEqual((data["flow"], data["status"], data["all_steps_passed"], data["returncode"]),
                         ("fixture", "PASS", True, 0))
        self.assertEqual(data["counts"], {"PASS": 1, "FAIL": 0, "SKIP": 0, "NOT_RUN": 0, "TOTAL": 1})
        self.assertEqual(data["steps"], [{"index": 1, "name": "Проверка текста", "status": "PASS",
                                         "returncode": 0, "reason_code": ""}])
        encoded = json.dumps(data, ensure_ascii=False)
        self.assertEqual(json.loads(encoded), data)
        self.assertNotIn("PRIVATE_CHILD_OUTPUT", encoded)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn(sys.executable, encoded)
        self.assertIn("PRIVATE_CHILD_OUTPUT", output)
        self.assertIn("[PASS] Проверка текста", output)
        self.assertIn("completed successfully", output)

    def test_skip_has_zero_returncode_but_is_incomplete_and_launches_nothing(self) -> None:
        step = self.windows_step()
        with mock.patch.object(self.pipeline, "_is_windows", return_value=False), \
                mock.patch.object(self.pipeline.subprocess, "Popen") as launch:
            result, output = self.run_steps([step])
        launch.assert_not_called()
        data = result.to_dict()
        self.assertEqual((data["status"], data["all_steps_passed"], data["returncode"]),
                         ("INCOMPLETE", False, 0))
        self.assertEqual(data["counts"], {"PASS": 0, "FAIL": 0, "SKIP": 1, "NOT_RUN": 0, "TOTAL": 1})
        self.assertEqual(data["steps"][0]["reason_code"], "requires_windows")
        self.assertIsNone(data["steps"][0]["returncode"])
        self.assertIn("[INCOMPLETE]", output)
        self.assertNotIn("completed successfully", output)

    def test_mixed_outcomes_preserve_order_counts_failure_and_unstarted_steps(self) -> None:
        steps = [self.step("first"), self.windows_step(), self.step("fails", "raise SystemExit(7)"),
                 self.step("pending", 'from pathlib import Path; Path("bad.flag").touch()')]
        with mock.patch.object(self.pipeline, "_is_windows", return_value=False):
            result, output = self.run_steps(steps)
        data = result.to_dict()
        self.assertEqual((data["status"], data["all_steps_passed"], data["returncode"]), ("FAIL", False, 7))
        self.assertEqual(data["counts"], {"PASS": 1, "FAIL": 1, "SKIP": 1, "NOT_RUN": 1, "TOTAL": 4})
        self.assertEqual([item["index"] for item in data["steps"]], [1, 2, 3, 4])
        self.assertEqual([item["status"] for item in data["steps"]], ["PASS", "SKIP", "FAIL", "NOT_RUN"])
        self.assertEqual([item["returncode"] for item in data["steps"]], [0, None, 7, None])
        self.assertEqual([item["reason_code"] for item in data["steps"]],
                         ["", "requires_windows", "nonzero_exit", "flow_stopped"])
        self.assertFalse((self.root / "bad.flag").exists())
        self.assertIn("PASS=1; FAIL=1; SKIP=1; NOT_RUN=1", output)

    def test_unknown_or_empty_flow_is_never_a_vacuous_pass(self) -> None:
        for flow in ("no-such-flow", "fixture"):
            with self.subTest(flow=flow), mock.patch.object(self.pipeline.subprocess, "Popen") as launch:
                result, output = self.run_steps([], flow=flow)
                launch.assert_not_called()
                data = result.to_dict()
                self.assertEqual((data["status"], data["all_steps_passed"], data["returncode"]), ("FAIL", False, 2))
                self.assertEqual(data["reason_code"], "unknown_flow")
                self.assertEqual(data["steps"], [])
                self.assertEqual(data["counts"]["TOTAL"], 0)
                self.assertIn("[FAIL] Unknown flow", output)

    def test_launch_error_keeps_machine_paths_in_text_log_only(self) -> None:
        secret_path = str(self.root / "private-executable-location")
        step = self.pipeline.Step("cannot start", [secret_path])
        result, output = self.run_steps([step, self.step("pending")])
        data = result.to_dict()
        self.assertEqual((data["status"], data["returncode"]), ("FAIL", 1))
        self.assertEqual(data["steps"][0]["reason_code"], "execution_error")
        self.assertNotIn(secret_path, json.dumps(data))
        self.assertNotIn("FileNotFoundError", json.dumps(data))
        self.assertIn("FileNotFoundError", output)

    def test_interruption_is_a_failure_with_pending_steps_not_run(self) -> None:
        process = SimpleNamespace(stdout=mock.MagicMock(), wait=mock.Mock(), kill=mock.Mock())
        process.stdout.__iter__.side_effect = KeyboardInterrupt
        with mock.patch.object(self.pipeline.subprocess, "Popen", return_value=process):
            result, _ = self.run_steps([self.step("interrupted"), self.step("pending")])
        data = result.to_dict()
        self.assertEqual((data["status"], data["returncode"]), ("FAIL", 130))
        self.assertEqual([item["reason_code"] for item in data["steps"]], ["interrupted", "flow_stopped"])
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)

    def test_cli_no_log_writes_json_with_the_console_counts(self) -> None:
        target = self.root / "итог.json"
        code, output = self.run_main([self.step("Проверка")], "--no-log", "--summary-json", str(target))
        self.assertEqual(code, 0)
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual((data["status"], data["steps"][0]["name"]), ("PASS", "Проверка"))
        self.assertIn("PASS=1; FAIL=0; SKIP=0; NOT_RUN=0", output)
        self.assertFalse((self.root / "pipeline-logs").exists())
        self.assertEqual(set(self.root.iterdir()), {target})

    def test_relative_summary_uses_project_root_and_each_run_has_a_new_id(self) -> None:
        ids = []
        for filename in ("first.json", "second.json"):
            code, _ = self.run_main([self.step("portable")], "--no-log", "--summary-json", filename)
            self.assertEqual(code, 0)
            data = json.loads((self.root / filename).read_text(encoding="utf-8"))
            ids.append(data["run_id"])
        self.assertNotEqual(ids[0], ids[1])

    def test_legacy_no_summary_option_creates_no_report(self) -> None:
        steps = [self.step("portable")]
        code, _ = self.run_main(steps, "--no-log")
        self.assertIs(type(code), int)
        self.assertEqual(code, 0)
        self.assertEqual(list(self.root.iterdir()), [])
        with mock.patch.object(self.pipeline, "available_flows", return_value={"fixture": steps}), \
                redirect_stdout(io.StringIO()):
            legacy_code = self.pipeline.run_flow("fixture")
        self.assertIs(type(legacy_code), int)
        self.assertEqual(legacy_code, 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_summary_and_log_are_preserved_before_any_child_runs(self) -> None:
        target, log_path = self.root / "previous.json", self.root / "previous.log"
        target.write_bytes(b'{"status":"PASS","old_run":true}\n')
        log_path.write_bytes(b"KEEP_PREVIOUS_LOG\n")
        with mock.patch.object(self.pipeline, "run_flow_result") as run:
            code, output = self.run_main([self.step("forbidden")], "--summary-json", str(target),
                                         "--log-file", str(log_path))
        run.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(target.read_bytes(), b'{"status":"PASS","old_run":true}\n')
        self.assertEqual(log_path.read_bytes(), b"KEEP_PREVIOUS_LOG\n")
        self.assertIn("[FAIL]", output)

    def test_missing_summary_parent_is_not_created_and_no_child_runs(self) -> None:
        target = self.root / "missing" / "result.json"
        log_path = self.root / "also-missing" / "result.log"
        with mock.patch.object(self.pipeline, "run_flow_result") as run:
            code, _ = self.run_main([self.step("forbidden")], "--summary-json", str(target),
                                    "--log-file", str(log_path))
        run.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_same_summary_and_log_path_is_refused_without_creating_it(self) -> None:
        target = self.root / "same.json"
        with mock.patch.object(self.pipeline, "run_flow_result") as run:
            code, _ = self.run_main([self.step("forbidden")], "--summary-json", str(target),
                                    "--log-file", str(target))
        run.assert_not_called()
        self.assertEqual(code, 2)
        self.assertFalse(target.exists())

    def test_normalized_summary_and_log_alias_is_also_refused(self) -> None:
        target = self.root / "same.json"
        folder = self.root / "existing"
        folder.mkdir()
        alias = folder / ".." / "same.json"
        with mock.patch.object(self.pipeline, "run_flow_result") as run:
            code, _ = self.run_main([self.step("forbidden")], "--summary-json", str(target),
                                    "--log-file", str(alias))
        run.assert_not_called()
        self.assertEqual(code, 2)
        self.assertFalse(target.exists())

    def test_no_log_ignores_log_path_and_still_writes_requested_json(self) -> None:
        target = self.root / "summary.json"
        code, _ = self.run_main([self.step("portable")], "--no-log", "--summary-json", str(target),
                                "--log-file", str(target))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["status"], "PASS")

    def test_json_write_failure_is_nonzero_and_partial_file_is_not_a_report(self) -> None:
        target = self.root / "partial.json"

        def fail_write(value, stream, **kwargs):
            stream.write("{")
            raise OSError("synthetic full disk")

        with mock.patch.object(self.pipeline.json, "dump", side_effect=fail_write):
            code, output = self.run_main([self.step("portable")], "--no-log", "--summary-json", str(target))
        self.assertEqual(code, 2)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(target.read_text(encoding="utf-8"))
        self.assertIn("[FAIL] Pipeline output", output)
        self.assertNotIn("Pipeline JSON summary saved", output)

    def test_log_open_failure_leaves_empty_summary_and_launches_no_children(self) -> None:
        target = self.root / "not-finished.json"
        log_directory = self.root / "directory-not-log-file"
        log_directory.mkdir()
        with mock.patch.object(self.pipeline, "run_flow_result") as run:
            code, _ = self.run_main([self.step("forbidden")], "--summary-json", str(target),
                                    "--log-file", str(log_directory))
        run.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(target.read_bytes(), b"")

    def test_help_creates_no_summary_or_log_and_launches_no_children(self) -> None:
        target = self.root / "missing" / "help.json"
        with mock.patch.object(self.pipeline, "run_flow_result") as run:
            code, output = self.run_main([self.step("forbidden")], "--help", "--summary-json", str(target))
        run.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("--summary-json", output)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_actual_cli_unknown_flow_writes_a_failure_summary(self) -> None:
        target = self.root / "unknown.json"
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(PIPELINE_SOURCE),
             "m154_missing_flow", "--no-log", "--summary-json", str(target)],
            cwd=str(self.root), capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual((data["status"], data["all_steps_passed"], data["returncode"]), ("FAIL", False, 2))
        self.assertEqual(data["reason_code"], "unknown_flow")
        self.assertEqual(data["counts"]["TOTAL"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
