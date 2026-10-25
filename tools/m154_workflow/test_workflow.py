"""Behavioral integration checks: real Git, disposable repositories, no network."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import SCHEMA, WorkflowError, git, git_text, json_bytes, publish_saved, run_experiment, run_lock, sha256, source_snapshot


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m154qa_")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.remote = self.root / "remote.git"
        self.bundle = self.root / "bundle"
        (self.bundle / "payload").mkdir(parents=True)
        self.run_dir = self.root / "run"
        git(self.source, "init", "--quiet", "-b", "main")
        git(self.source, "config", "user.name", "M154 temporary test")
        git(self.source, "config", "user.email", "m154-test@example.invalid")
        self.old = b"VALUE = 0\n"
        (self.source / "demo.py").write_bytes(self.old)
        git(self.source, "add", "--", "demo.py")
        git(self.source, "commit", "--quiet", "-m", "fixture")
        self.base = git_text(self.source, "rev-parse", "HEAD")
        git(self.root, "init", "--bare", "--quiet", str(self.remote))
        git(self.source, "push", str(self.remote), "HEAD:refs/heads/main", "HEAD:refs/heads/sandbox/m154")
        self.remote_initial = git(self.remote, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/main", "refs/heads/sandbox/m154").stdout
        self.plan("from pathlib import Path; assert Path('demo.py').read_text() == 'VALUE = 1\\n'")

    def tearDown(self):
        # Own disposable repositories only; Git on Windows may make loose objects read-only.
        def make_writable(function, path, error):
            os.chmod(path, 0o700)
            function(path)
        import shutil
        shutil.rmtree(self.root, onerror=make_writable)
        self.temp.cleanup()

    def plan(self, command: str, timeout: int = 10):
        data = b"VALUE = 1\n"
        (self.bundle / "payload" / "demo.py").write_bytes(data)
        self.manifest = {"schema": SCHEMA, "stage": "M154", "purpose": "AUTOMATION_SELFTEST",
                         "goal": "Test experiment publication", "base_commit": self.base,
                         "payloads": [{"path": "demo.py", "before_sha256": sha256(self.old), "sha256": sha256(data)}],
                         "checks": [{"id": "behavior", "argv": ["{python}", "-B", "-c", command], "timeout_seconds": timeout}],
                         "remaining_checks": ["pipeline(flow=check)"]}
        self.write_plan()

    def write_plan(self):
        (self.bundle / "plan.json").write_bytes(json_bytes(self.manifest))

    def run_it(self, remote: Path | None = None):
        return run_experiment(self.source, self.bundle, self.run_dir, remote_url=str(remote or self.remote))

    def public_from_remote(self, result, name="summary.json"):
        path = "reports/M154/" + result["summary"]["run_id"] + "/" + name
        raw = git(self.remote, "show", "refs/heads/reports/m154:" + path).stdout
        return json.loads(raw)

    def assert_source_refs_preserved(self):
        self.assertEqual(self.remote_initial, git(self.remote, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/main", "refs/heads/sandbox/m154").stdout)
        self.assertEqual(self.base, git_text(self.source, "rev-parse", "HEAD"))
        self.assertEqual(self.old, (self.source / "demo.py").read_bytes())

    def test_pass_code_and_report_are_published(self):
        before = source_snapshot(self.source)
        result = self.run_it()
        self.assertEqual("PASS", result["summary"]["status"])
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])
        summary = self.public_from_remote(result)
        self.assertEqual(result["summary"], summary)
        commit = summary["candidate_commit"]
        self.assertEqual(b"VALUE = 1\n", git(self.remote, "show", commit + ":demo.py").stdout)
        self.assertEqual(before, source_snapshot(self.source))
        self.assertFalse(summary["pipeline_gate_closed"])
        self.assert_source_refs_preserved()

    def test_failure_exit_is_preserved_and_published(self):
        self.plan("print('expected intentional failure'); raise SystemExit(7)")
        result = self.run_it()
        self.assertEqual(("FAIL", 7), (result["summary"]["status"], result["summary"]["exit_code"]))
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])
        self.assertEqual(7, self.public_from_remote(result)["checks"][0]["exit_code"])
        observation = self.public_from_remote(result, "observation.json")
        self.assertEqual("observed_only", observation["status"])
        self.assertIsNone(observation["root_cause"])
        self.assertIsNone(observation["training_label"])
        self.assert_source_refs_preserved()

    def test_preparation_failure_is_reported_without_false_candidate(self):
        self.manifest["base_commit"] = "0" * 40
        self.write_plan()
        result = self.run_it()
        self.assertEqual("SETUP_FAILED", result["summary"]["status"])
        self.assertIsNone(result["summary"]["candidate_commit"])
        self.assertEqual("NOT_RUN", result["summary"]["checks"][0]["status"])
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])
        self.assertEqual("BASE_COMMIT_MISMATCH", self.public_from_remote(result, "diagnostics.json")["errors"][0]["code"])
        self.assert_source_refs_preserved()

    def test_invalid_root_plan_still_has_report(self):
        (self.bundle / "plan.json").write_bytes(b"[]\n")
        result = self.run_it()
        self.assertEqual("SETUP_FAILED", result["summary"]["status"])
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])
        self.assertEqual("INVALID_PLAN_SCHEMA", self.public_from_remote(result, "diagnostics.json")["errors"][0]["code"])

    def test_offline_retry_does_not_execute_tests_again(self):
        self.plan("from pathlib import Path; p=Path('test_invocations.txt'); p.write_text(p.read_text()+'x' if p.exists() else 'x')")
        offline_remote = self.root / "not_yet_available.git"
        first = self.run_it(offline_remote)
        self.assertEqual("PASS", first["summary"]["status"])
        self.assertEqual("PENDING", first["publication"]["queue_state"])
        self.assertTrue((self.run_dir / "report_git" / "state.json").is_file())
        git(self.root, "init", "--bare", "--quiet", str(offline_remote))
        second = self.run_it(offline_remote)
        self.assertTrue(second["retried_without_tests"])
        self.assertEqual("PUBLISHED", second["publication"]["queue_state"])
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual("x", (self.run_dir / "c" / "test_invocations.txt").read_text())
        self.assert_source_refs_preserved()

    def test_dirty_staged_untracked_work_is_preserved(self):
        (self.source / "demo.py").write_bytes(b"LOCAL UNSTAGED CONTENT\n")
        (self.source / "staged.txt").write_bytes(b"STAGED\n")
        git(self.source, "add", "--", "staged.txt")
        (self.source / "private_note.txt").write_bytes(b"PRIVATE UNTRACKED\n")
        before = source_snapshot(self.source)
        result = self.run_it()
        self.assertEqual("PASS", result["summary"]["status"])
        self.assertEqual(before, source_snapshot(self.source))
        self.assertEqual(b"LOCAL UNSTAGED CONTENT\n", (self.source / "demo.py").read_bytes())
        self.assertEqual(b"PRIVATE UNTRACKED\n", (self.source / "private_note.txt").read_bytes())
        tree = git(self.remote, "ls-tree", "-r", "--name-only", result["summary"]["candidate_commit"]).stdout.decode()
        self.assertNotIn("private_note", tree)
        self.assertNotIn("staged.txt", tree)

    def test_test_outputs_are_not_added_to_candidate_commit(self):
        self.plan("from pathlib import Path; Path('generated.txt').write_text('test-only output')")
        result = self.run_it()
        self.assertTrue(result["summary"]["post_check_worktree_dirty"])
        tree = git(self.remote, "ls-tree", "-r", "--name-only", result["summary"]["candidate_commit"]).stdout.decode()
        self.assertNotIn("generated.txt", tree)
        self.assertEqual("PASS", result["summary"]["status"])

    def test_changed_candidate_is_recorded_as_snapshot_failure(self):
        self.plan("from pathlib import Path; Path('demo.py').write_text('changed by test')")
        result = self.run_it()
        self.assertEqual("SNAPSHOT_CHANGED", result["summary"]["status"])
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])
        self.assertEqual(b"VALUE = 1\n", git(self.remote, "show", result["summary"]["candidate_commit"] + ":demo.py").stdout)

    def test_timeout_is_published(self):
        self.plan("import time; time.sleep(30)", timeout=1)
        result = self.run_it()
        self.assertEqual("TIMEOUT", result["summary"]["status"])
        self.assertEqual(124, result["summary"]["exit_code"])
        self.assertTrue(result["summary"]["checks"][0]["process_tree_terminated"])
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])

    def test_missing_check_interpreter_is_not_left_running(self):
        result = run_experiment(self.source, self.bundle, self.run_dir,
                                python=str(self.root / "missing-python"), remote_url=str(self.remote))
        self.assertEqual("START_FAILED", result["summary"]["status"])
        self.assertEqual("START_FAILED", result["summary"]["checks"][0]["status"])
        self.assertEqual(2, result["summary"]["exit_code"])
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])

    def test_run_inside_source_is_rejected_before_any_write(self):
        bad = self.source / "run"
        with self.assertRaisesRegex(WorkflowError, "outside"):
            run_experiment(self.source, self.bundle, bad, remote_url=str(self.remote))
        self.assertFalse(bad.exists())

    def test_extra_file_in_public_directory_is_not_published(self):
        self.plan("from pathlib import Path; p=Path(r'{run}')/'public'; p.mkdir(); (p/'private.txt').write_text('not an allowed report file')")
        result = self.run_it()
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])
        paths = git(self.remote, "ls-tree", "-r", "--name-only", "refs/heads/reports/m154").stdout.decode()
        self.assertNotIn("private.txt", paths)
        self.assertEqual("not an allowed report file", (self.run_dir / "public" / "private.txt").read_text())

    def test_edited_receipt_file_is_rejected_before_retry(self):
        result = self.run_it()
        before = git_text(self.remote, "rev-parse", "refs/heads/reports/m154")
        (self.run_dir / "public" / "summary.json").write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(WorkflowError, "receipt"):
            publish_saved(self.run_dir)
        self.assertEqual(before, git_text(self.remote, "rev-parse", "refs/heads/reports/m154"))

    def test_same_run_cannot_silently_switch_to_another_plan(self):
        first = self.run_it()
        self.manifest["goal"] = "A different experiment"
        self.write_plan()
        with self.assertRaisesRegex(WorkflowError, "different prepared plan"):
            self.run_it()
        self.assertEqual(first["summary"], self.public_from_remote(first))

    def test_active_run_is_not_recovered_or_reexecuted(self):
        self.run_dir.mkdir()
        with run_lock(self.run_dir):
            with self.assertRaisesRegex(WorkflowError, "already active"):
                self.run_it()
        self.assertFalse((self.run_dir / "state.json").exists())

    def test_interrupted_run_is_published_without_a_second_test(self):
        self.plan("from pathlib import Path; Path('should_not_run.txt').write_text('unexpected')")
        self.run_dir.mkdir()
        identifier = "8" * 32
        state = {"schema": "SKYNETVS_M154_LOCAL_RUN_V1", "run_id": identifier, "phase": "CHECKING",
                 "source": str(self.source.resolve()), "bundle": str(self.bundle.resolve()), "remote_url": str(self.remote),
                 "started_at": "2026-10-25T00:00:00+00:00", "candidate_commit": None,
                 "candidate_branch": "experiments/m154/" + identifier,
                 "plan_input_sha256": sha256((self.bundle / "plan.json").read_bytes()), "plan": self.manifest,
                 "checks": [{"name": "behavior", "status": "RUNNING", "exit_code": None}]}
        (self.run_dir / "state.json").write_bytes(json_bytes(state))
        result = self.run_it()
        self.assertTrue(result["retried_without_tests"])
        self.assertEqual("INTERRUPTED", result["summary"]["status"])
        self.assertEqual("INTERRUPTED_UNKNOWN_EXIT", result["summary"]["checks"][0]["status"])
        self.assertEqual("PUBLISHED", result["publication"]["queue_state"])
        self.assertFalse((self.run_dir / "c").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
