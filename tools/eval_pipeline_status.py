"""Pipeline result regression checks; only temporary or mocked children run."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
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


class PipelineStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_pipeline_status_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        name = "pipeline_status_under_test"
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

    def command(self, source: str) -> list[str]:
        return [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", source]

    def step(self, name: str, source: str):
        return self.pipeline.Step(name, self.command(source))

    def windows_step(self):
        return next(step for step in self.pipeline.available_flows()["audio_control"]
                    if "tools/eval_audio_control_windows.py" in step.cmd)

    def run_steps(self, steps):
        output, log = io.StringIO(), io.StringIO()
        with mock.patch.object(self.pipeline, "available_flows", return_value={"fixture": steps}), \
                redirect_stdout(output):
            code = self.pipeline.run_flow("fixture", log_file=log)
        self.assertEqual(output.getvalue(), log.getvalue())
        return code, output.getvalue()

    @staticmethod
    def child_result(code=0, output=""):
        return SimpleNamespace(stdout=io.StringIO(output), wait=mock.Mock(return_value=code),
                               kill=mock.Mock())

    def test_known_windows_skip_never_becomes_pass_or_launches_child(self) -> None:
        step = self.windows_step()
        with mock.patch.object(self.pipeline, "_is_windows", return_value=False), \
                mock.patch.object(self.pipeline.subprocess, "Popen") as launch:
            code, output = self.run_steps([step])
        launch.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("[SKIP] " + step.name, output)
        self.assertIn("PASS=0; FAIL=0; SKIP=1; NOT_RUN=0", output)
        self.assertIn("[INCOMPLETE]", output)
        self.assertNotIn("[PASS]", output)
        self.assertNotIn("[OK]", output)
        self.assertNotIn("completed successfully", output)

    def test_real_child_pass_preserves_console_log_and_output(self) -> None:
        step = self.step("portable", 'import sys; print("проверка"); print("stderr", file=sys.stderr)')
        code, output = self.run_steps([step])
        self.assertEqual(code, 0)
        self.assertIn("проверка", output)
        self.assertIn("stderr", output)
        self.assertIn("[PASS] portable", output)
        self.assertIn("PASS=1; FAIL=0; SKIP=0; NOT_RUN=0", output)
        self.assertIn("completed successfully", output)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_registered_step_runs_on_supported_windows_host(self) -> None:
        step = self.windows_step()
        process = self.child_result(0, "synthetic Windows result\n")
        with mock.patch.object(self.pipeline, "_is_windows", return_value=True), \
                mock.patch.object(self.pipeline.subprocess, "Popen", return_value=process) as launch, \
                redirect_stdout(io.StringIO()):
            result = self.pipeline.run_step_result(step, cwd=self.root)
        self.assertEqual((result.status, result.returncode), ("PASS", 0))
        self.assertEqual(launch.call_args.args[0], step.cmd)
        self.assertTrue(process.stdout.closed)

    def test_platform_fail_gates_and_portable_windows_named_check_are_not_skipped(self) -> None:
        protected = [
            "tools/eval_developer_task_execution_backend_host_windows.py",
            "tools/eval_developer_task_execution_backend_lifecycle_windows.py",
            "tools/eval_developer_task_execution_boundary_composition_windows.py",
            "tools/eval_developer_task_execution_runtime_composition_windows.py",
            "tools/eval_developer_task_execution_dependency_profile_windows.py",
            "tools/eval_developer_task_execution_dependency_acquisition_windows.py",
            "tools/eval_developer_task_execution_compile_ast_contract_windows.py",
            "tools/eval_developer_task_execution_compile_ast_runner_windows.py",
        ]
        for script in protected:
            with self.subTest(script=script), \
                    mock.patch.object(self.pipeline, "_is_windows", return_value=False), \
                    mock.patch.object(self.pipeline.subprocess, "Popen", return_value=self.child_result(7)) as launch, \
                    redirect_stdout(io.StringIO()):
                result = self.pipeline.run_step_result(
                    self.pipeline.Step("retained gate", [sys.executable, script]), cwd=self.root)
                self.assertEqual((result.status, result.returncode), ("FAIL", 7))
                launch.assert_called_once()

    def test_registry_does_not_match_a_script_among_other_command_arguments(self) -> None:
        command = self.command("raise SystemExit(7)") + ["tools/eval_audio_control_windows.py"]
        with mock.patch.object(self.pipeline, "_is_windows", return_value=False), redirect_stdout(io.StringIO()):
            result = self.pipeline.run_step_result(self.pipeline.Step("ordinary", command), cwd=self.root)
        self.assertEqual((result.status, result.returncode), ("FAIL", 7))

    def test_nonzero_failure_retains_exit_code_and_marks_unstarted_steps(self) -> None:
        first = self.step("fails", "raise SystemExit(7)")
        later = self.step("must not run", 'from pathlib import Path; Path("later.flag").write_text("bad")')
        code, output = self.run_steps([first, later])
        self.assertEqual(code, 7)
        self.assertIn("[FAIL] fails: exit code 7", output)
        self.assertIn("[NOT_RUN] must not run", output)
        self.assertIn("PASS=0; FAIL=1; SKIP=0; NOT_RUN=1", output)
        self.assertNotIn("[RUN] must not run", output)
        self.assertFalse((self.root / "later.flag").exists())

    def test_mixed_pass_and_skip_flow_continues_but_is_incomplete(self) -> None:
        first = self.step("first", 'from pathlib import Path; Path("first.flag").write_text("ran")')
        last = self.step("last", 'from pathlib import Path; Path("last.flag").write_text("ran")')
        with mock.patch.object(self.pipeline, "_is_windows", return_value=False):
            code, output = self.run_steps([first, self.windows_step(), last])
        self.assertEqual(code, 0)
        self.assertEqual((self.root / "first.flag").read_text(), "ran")
        self.assertEqual((self.root / "last.flag").read_text(), "ran")
        self.assertIn("PASS=2; FAIL=0; SKIP=1; NOT_RUN=0", output)
        self.assertIn("[INCOMPLETE]", output)
        self.assertNotIn("completed successfully", output)

    def test_launch_error_fails_and_does_not_run_remaining_steps(self) -> None:
        missing = self.pipeline.Step("missing", [str(self.root / "no-such-executable")])
        later = self.step("later", 'from pathlib import Path; Path("later.flag").touch()')
        code, output = self.run_steps([missing, later])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL] missing: FileNotFoundError", output)
        self.assertIn("[NOT_RUN] later", output)
        self.assertFalse((self.root / "later.flag").exists())

    def test_interactive_results_keep_inherited_streams_and_integer_codes(self) -> None:
        step = self.pipeline.Step("interactive", ["synthetic-command"], interactive=True)
        for code, status in [(0, "PASS"), (6, "FAIL")]:
            with self.subTest(code=code), \
                    mock.patch.object(self.pipeline.subprocess, "run", return_value=subprocess.CompletedProcess(step.cmd, code)) as launch, \
                    redirect_stdout(io.StringIO()):
                result = self.pipeline.run_step_result(step, cwd=self.root)
                self.assertEqual((result.status, result.returncode), (status, code))
                self.assertNotIn("stdout", launch.call_args.kwargs)
                self.assertNotIn("stdin", launch.call_args.kwargs)
        with mock.patch.object(self.pipeline.subprocess, "run", side_effect=KeyboardInterrupt), \
                redirect_stdout(io.StringIO()):
            result = self.pipeline.run_step_result(step, cwd=self.root)
        self.assertEqual((result.status, result.returncode), ("FAIL", 130))

    def test_interrupt_stops_child_and_marks_remaining_steps_not_run(self) -> None:
        process = self.child_result(-9)
        process.stdout = mock.MagicMock()
        process.stdout.__iter__.side_effect = KeyboardInterrupt
        with mock.patch.object(self.pipeline.subprocess, "Popen", return_value=process) as launch:
            code, output = self.run_steps([self.step("interrupted", "pass"), self.step("later", "pass")])
        self.assertEqual(code, 130)
        launch.assert_called_once()
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)
        process.stdout.close.assert_called_once()
        self.assertIn("[FAIL] interrupted: interrupted by user", output)
        self.assertIn("[NOT_RUN] later", output)
        self.assertIn("PASS=0; FAIL=1; SKIP=0; NOT_RUN=1", output)

    def test_legacy_run_step_still_returns_integer_exit_codes(self) -> None:
        for code in (0, 7):
            with self.subTest(code=code), redirect_stdout(io.StringIO()):
                result = self.pipeline.run_step(self.step("legacy", f"raise SystemExit({code})"), cwd=self.root)
                self.assertIs(type(result), int)
                self.assertEqual(result, code)
        with mock.patch.object(self.pipeline, "_is_windows", return_value=False), redirect_stdout(io.StringIO()):
            self.assertEqual(self.pipeline.run_step(self.windows_step(), cwd=self.root), 0)

    def test_unknown_flow_is_an_error_and_launches_nothing(self) -> None:
        with mock.patch.object(self.pipeline.subprocess, "Popen") as launch, redirect_stdout(io.StringIO()) as output:
            code = self.pipeline.run_flow("no-such-flow")
        self.assertEqual(code, 2)
        launch.assert_not_called()
        self.assertIn("[FAIL] Unknown flow", output.getvalue())
        self.assertNotIn("completed successfully", output.getvalue())

    def test_child_text_is_not_used_as_a_step_status_protocol(self) -> None:
        step = self.step("ordinary", 'print("[SKIP] optional inner case; other checks ran")')
        code, output = self.run_steps([step])
        self.assertEqual(code, 0)
        self.assertIn("[PASS] ordinary", output)
        self.assertIn("PASS=1; FAIL=0; SKIP=0; NOT_RUN=0", output)

    def test_main_records_summary_and_no_log_only_disables_runner_log(self) -> None:
        log_path = self.root / "explicit" / "flow.log"
        first = self.step("logged", 'from pathlib import Path; Path("logged.flag").touch()')
        with mock.patch.object(self.pipeline, "available_flows", return_value={"fixture": [first]}), \
                mock.patch.object(sys, "argv", ["pipeline.py", "fixture", "--log-file", str(log_path)]), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.pipeline.main(), 0)
        original_log = log_path.read_bytes()
        self.assertIn(b"PASS=1; FAIL=0; SKIP=0; NOT_RUN=0", original_log)
        self.assertTrue((self.root / "logged.flag").is_file())
        second = self.step("without runner log", 'from pathlib import Path; Path("no-log.flag").touch()')
        with mock.patch.object(self.pipeline, "available_flows", return_value={"fixture": [second]}), \
                mock.patch.object(sys, "argv", ["pipeline.py", "fixture", "--no-log"]), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.pipeline.main(), 0)
        self.assertEqual(log_path.read_bytes(), original_log)
        self.assertTrue((self.root / "no-log.flag").is_file())
        self.assertFalse((self.root / "pipeline-logs").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
