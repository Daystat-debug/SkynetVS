from __future__ import annotations

"""Native Git + in-memory compilation fixtures; no guest profile or task execution.

Only fixture builders from the landed preflight evaluator are reused; its test
suite is not inherited/run and production never imports an evaluator.
"""
import ast
import json
import sys
import unittest
import warnings
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch
from modules.developer import developer_task_guest_static_check as api
from modules.developer import developer_task_guest_preflight_contract as c
from modules.developer.developer_task_guest_profile_document import GUEST_PROFILE_DOCUMENT
from tools import eval_developer_task_guest_preflight as fx


class StaticCheckTests(unittest.TestCase):
    setUpClass = classmethod(fx.GuestPreflightTests.setUpClass.__func__)
    tearDownClass = classmethod(fx.GuestPreflightTests.tearDownClass.__func__)
    setUp = fx.GuestPreflightTests.setUp
    tearDown = fx.GuestPreflightTests.tearDown
    rebind = fx.GuestPreflightTests.rebind
    wire = fx.GuestPreflightTests.wire
    commit_file = fx.GuestPreflightTests.commit_file

    def run_static(self, **changes):
        kw = dict(raw_response=self.response, expected_request=self.request,
                  profile_document=GUEST_PROFILE_DOCUMENT, repository_root=self.repo,
                  git_executable=fx.GIT, expected_git_sha256=self.git_sha, scratch_parent=self.scratch)
        manifest = changes.pop("raw_manifest", self.manifest)
        kw.update(changes)
        return api.run_developer_task_guest_static_checks_v2(manifest, **kw)

    def success(self, **changes):
        result = self.run_static(**changes)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.status, api.STATIC_CHECK_PASS)
        self.assertEqual(result.completed_stages, api.STATIC_STAGES)
        d = result.to_dict()
        self.assertEqual(d["completed_task_checks"], ["git_diff_check", "py_compile"])
        self.assertEqual(d["pending_task_checks"], ["pipeline:check_guest_source_v1"])
        self.assertTrue(d["py_compile_check_passed"])
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertGreater(result.reconstruction_git_command_count, 0)
        self.no_authority(d)
        return result

    def no_authority(self, d):
        for key in ("candidate_module_imported", "code_object_executed", "code_object_retained", "pyc_written",
                    "candidate_written_to_worktree", "changed_task_code_executed", "guest_profile_executed",
                    "full_check_executed", "protected_helper_closure_verified", "execution_plan_validated",
                    "compiler_runtime_bundle_accepted", "git_runtime_bundle_accepted", "guest_target_interpreter_used",
                    "capability_issued", "replay_prevention_verified", "provider_authenticated",
                    "required_profile_checks_passed", "all_required_checks_passed", "ready_to_promote",
                    "runtime_authorized", "promotion_authorized", "legacy_full_check_equivalent",
                    "live_repository_write_attempted", "network_requested", "sandbox_launched", "once_marker_created"):
            self.assertIs(d[key], False, key)

    def reject(self, **changes):
        result = self.run_static(**changes)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.status, api.STATIC_CHECK_REJECTED)
        self.assertTrue(result.issue_codes)
        self.assertIsNone(result.facts)
        d = result.to_dict()
        self.assertIsNone(d["facts"])
        self.assertEqual(d["static_check_fingerprint"], "")
        self.assertEqual(d["accepted_preflight_binding"], "")
        self.assertEqual(d["completed_task_checks"], [])
        self.assertEqual(d["pending_task_checks"], list(api.ALL_CHECKS))
        self.no_authority(d)
        return result

    def set_result_content(self, data):
        self.response, self.manifest = self.wire(fx.make_patch(new=data))

    def mutate_after_preflight(self, fn):
        original = api.source_preflight.run_developer_task_guest_preflight_v2
        def wrapper(*a, **kw):
            result = original(*a, **kw)
            self.assertTrue(result.ok, result.to_dict())
            return fn(result)
        return patch.object(api.source_preflight, "run_developer_task_guest_preflight_v2", wrapper)

    def test_success_exact_blob_compiled(self):
        with patch.object(api, "_compile_candidate", wraps=api._compile_candidate) as call:
            result = self.success()
        call.assert_called_once_with(fx.RESULT, fx.TARGET)
        self.assertEqual(result.facts.preflight.candidate_blob_oid, fx.oid(fx.RESULT))
        self.assertEqual(result.facts.preflight.candidate_content_sha256, c.sha(fx.RESULT))
        self.assertEqual(result.facts.preflight.candidate_content_bytes, len(fx.RESULT))
        self.assertEqual(result.facts.compiler.version, sys.version)
        self.assertEqual(result.facts.compiler.cache_tag, sys.implementation.cache_tag)

    def test_source_index_objects_and_files_unchanged(self):
        md = api.native.metadata_snapshot(self.repo / ".git")
        index = (self.repo / ".git/index").read_bytes()
        files = sorted(str(x.relative_to(self.repo)) for x in self.repo.rglob("*"))
        self.success()
        self.assertEqual(md, api.native.metadata_snapshot(self.repo / ".git"))
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertEqual((self.repo / fx.TARGET).read_bytes(), fx.CONTENT)
        self.assertEqual(files, sorted(str(x.relative_to(self.repo)) for x in self.repo.rglob("*")))
        self.assertEqual(list(self.repo.rglob("*.pyc")), [])

    def test_independent_git_tree(self):
        result = self.success()
        (self.repo / fx.TARGET).write_bytes(fx.RESULT)
        fx.git(self.repo, "add", "--", fx.TARGET)
        self.assertEqual(fx.git(self.repo, "write-tree").decode().strip(), result.facts.preflight.candidate_tree)

    def test_crlf_worktree(self):
        fx.git(self.repo, "config", "core.autocrlf", "true")
        for p in self.repo.rglob("*.py"):
            p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.success()

    def test_empty_candidate_is_valid_python(self):
        self.set_result_content(b"")
        self.assertEqual(self.success().facts.preflight.candidate_content_bytes, 0)

    def test_comments_only_candidate(self):
        self.set_result_content(b"# no executable statements\n")
        self.success()

    def test_utf8_declared_source(self):
        self.set_result_content('# coding: utf-8\nVALUE = "Проверка"\n'.encode())
        self.success()

    def test_nonexistent_import_is_not_imported(self):
        self.set_result_content(b"import skynetvs_definitely_missing_static_fixture_7ff11\n")
        self.success()

    def test_top_level_target_not_executed(self):
        marker = self.case / "TARGET_MUST_NOT_EXECUTE.txt"
        source = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nraise RuntimeError('target executed')\n".encode()
        self.set_result_content(source)
        self.success()
        self.assertFalse(marker.exists())

    def test_syntax_error_rejected_after_successful_preflight(self):
        self.set_result_content(b"def secret_unclosed(\n")
        result = self.reject()
        self.assertTrue(result.source_preflight_result.ok)
        self.assertIn("candidate_python_syntax_error", result.issue_codes)
        self.assertTrue(result.compilation_attempted)
        self.assertFalse(result.compilation_observed_success)
        self.assertTrue(result.repository_unchanged_verified)
        self.assertTrue(result.temporary_cleanup_verified)
        self.assertEqual(result.syntax_error_line, 1)
        self.assertNotIn("secret_unclosed", json.dumps(result.to_dict()))

    def test_indentation_error(self):
        self.set_result_content(b"if True:\nno_indent = 1\n")
        self.assertIn("candidate_python_syntax_error", self.reject().issue_codes)

    def test_unknown_source_encoding(self):
        self.set_result_content(b"# coding: unknown-skynetvs-fixture-encoding\nVALUE = 2\n")
        self.assertIn("candidate_python_syntax_error", self.reject().issue_codes)

    def test_future_directive_wrong_location(self):
        self.set_result_content(b"VALUE = 1\nfrom __future__ import annotations\n")
        self.assertIn("candidate_python_syntax_error", self.reject().issue_codes)

    def test_compile_warnings_do_not_disclose_source(self):
        self.set_result_content(b"VALUE = (1 is 2)\n")
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            self.success()
        self.assertFalse(any(x.category is SyntaxWarning for x in seen))

    def test_no_inherited_future_flags(self):
        seen = []
        original = compile
        def observe(*args, **kwargs):
            code = original(*args, **kwargs)
            seen.append((args, kwargs, code.co_flags))
            return code
        with patch.object(api, "compile", observe, create=True):
            self.success()
        import __future__
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][1], {"flags": 0, "dont_inherit": True, "optimize": 0})
        self.assertFalse(seen[0][2] & __future__.annotations.compiler_flag)

    def test_typed_data_immutable_and_json_detached(self):
        result = self.success()
        with self.assertRaises(FrozenInstanceError):
            result.facts.observation_id = "different"
        with self.assertRaises(FrozenInstanceError):
            result.facts.compiler.version = "different"
        data = result.to_dict()
        data["facts"]["source_preflight_facts"]["candidate_tree"] = "f" * 40
        self.assertNotEqual(data["facts"], result.to_dict()["facts"])
        self.assertEqual(result.facts.fingerprint, result.to_dict()["static_check_fingerprint"])

    def test_repeated_read_only_calls_are_not_authority_replay(self):
        a = self.success(); b = self.success()
        self.assertEqual(a.facts.preflight.candidate_tree, b.facts.preflight.candidate_tree)
        self.assertNotEqual(a.facts.fingerprint, b.facts.fingerprint)
        self.assertFalse(a.to_dict()["replay_prevention_verified"])

    def test_second_context_real_membership(self):
        content = (self.repo / "modules/context_fixture.py").read_bytes()
        self.rebind(context=(fx.req.DeveloperTaskGuestContextInputV2(fx.TARGET, "100644", fx.oid(fx.CONTENT), fx.CONTENT),
                             fx.req.DeveloperTaskGuestContextInputV2("modules/context_fixture.py", "100644", fx.oid(content), content)))
        self.assertEqual(self.success().facts.preflight.context_files, 2)

    def test_preflight_failure_never_compiles(self):
        with patch.object(api, "_compile_candidate") as call:
            self.reject(raw_manifest=b"{}")
        call.assert_not_called()
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_v1_manifest_not_reinterpreted(self):
        self.assertFalse(self.reject(raw_manifest=b'{"schema_version":1}').compilation_attempted)

    def test_wrong_trusted_request(self):
        self.assertFalse(self.reject(expected_request=replace(self.request, instruction="different instruction")).compilation_attempted)

    def test_profile_tamper(self):
        self.assertFalse(self.reject(profile_document=GUEST_PROFILE_DOCUMENT+b" ").compilation_attempted)

    def test_stale_head(self):
        (self.repo / "README.md").write_bytes(b"advance\n")
        fx.git(self.repo, "add", "README.md"); fx.git(self.repo, "commit", "-m", "advance")
        self.assertFalse(self.reject().compilation_attempted)

    def test_explicit_descendant_task(self):
        self.commit_file("README.md", b"explicit new bound base\n")
        self.success()

    def test_source_drift_between_gates(self):
        def change(result):
            (self.repo / "README.md").write_bytes(b"drift\n")
            return result
        with self.mutate_after_preflight(change):
            self.assertFalse(self.reject().compilation_attempted)

    def test_clean_but_different_metadata_between_gates(self):
        def change(result):
            fx.git(self.repo, "config", "user.name", "another fixture user")
            return result
        with self.mutate_after_preflight(change): result = self.reject()
        self.assertIn("source_changed_since_fresh_preflight", result.issue_codes)
        self.assertFalse(result.compilation_attempted)

    def test_false_preflight_dict_is_not_accepted(self):
        with patch.object(api.source_preflight, "run_developer_task_guest_preflight_v2", return_value={"ok": True}):
            result = self.reject()
        self.assertIn("invalid_source_preflight_result", result.issue_codes)
        self.assertFalse(result.compilation_attempted)

    def test_foreign_scratch_not_deleted(self):
        sentinel = self.scratch / "FOREIGN_DO_NOT_DELETE.txt"; sentinel.write_bytes(b"foreign")
        result = self.run_static()
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(sentinel.read_bytes(), b"foreign")
        self.assertEqual(list(self.scratch.iterdir()), [sentinel])

    def test_source_change_after_compile_denies_pass(self):
        original = api._compile_candidate
        def change(*a):
            original(*a)
            (self.repo / "README.md").write_bytes(b"post-compile drift\n")
        with patch.object(api, "_compile_candidate", change): result = self.reject()
        self.assertTrue(result.compilation_observed_success)
        self.assertFalse(result.repository_unchanged_verified)
        self.assertTrue(result.temporary_cleanup_verified)

    def test_candidate_bytes_corruption_never_compiles(self):
        original = api.native.GuestPreflightGit.blobs
        def changed(obj, oids, **kw):
            data = original(obj, oids, **kw)
            if obj.root.name.startswith("gsc2_") and kw.get("temporary"):
                return {k:v+b"# changed\n" for k,v in data.items()}
            return data
        with patch.object(api.native.GuestPreflightGit, "blobs", changed), patch.object(api, "_compile_candidate") as call:
            self.reject()
        call.assert_not_called()

    def test_new_reconstruction_version_mismatch(self):
        original = api.native.GuestPreflightGit.run
        def changed(obj, args, **kw):
            if obj.root.name.startswith("gsc2_") and args == ["version"]: return b"git version false-fixture\n"
            return original(obj, args, **kw)
        with patch.object(api.native.GuestPreflightGit, "run", changed): result = self.reject()
        self.assertIn("reconstruction_git_version_mismatch", result.issue_codes)
        self.assertFalse(result.compilation_attempted)

    def test_git_observation_drift_after_compile(self):
        original = api.native.git_identity
        calls = 0
        def changed(*a):
            nonlocal calls
            calls += 1
            data = original(*a)
            return {**data, "bytes": data["bytes"]+1} if calls == 2 else data
        with patch.object(api.native, "git_identity", changed): result = self.reject()
        self.assertIn("git_executable_changed_during_static_check", result.issue_codes)
        self.assertTrue(result.compilation_observed_success)

    def test_compiler_observation_drift(self):
        observed = api._compiler_observation()
        with patch.object(api, "_compiler_observation", side_effect=[observed, replace(observed, version="other")]):
            result = self.reject()
        self.assertIn("static_compiler_changed_during_check", result.issue_codes)
        self.assertFalse(result.compiler_unchanged_verified)

    def test_cleanup_failure_no_pass_no_facts(self):
        with patch.object(api.native, "remove_private_tree", side_effect=OSError("do not expose this private path")):
            result = self.reject()
        self.assertTrue(result.compilation_observed_success)
        self.assertFalse(result.temporary_cleanup_verified)
        self.assertNotIn("do not expose", json.dumps(result.to_dict()))
        self.assertTrue(any(p.name.startswith("gsc2_") for p in self.scratch.iterdir()))

    def test_cleanup_noop_no_pass(self):
        with patch.object(api.native, "remove_private_tree", return_value=None):
            self.assertIn("static_temporary_cleanup_incomplete", self.reject().issue_codes)

    def test_snapshot_error_still_cleans_own_temp(self):
        original = api.native.GuestPreflightGit.snapshot
        def fail(obj, *a):
            if obj.root.name.startswith("gsc2_"): raise OSError("private snapshot details")
            return original(obj, *a)
        with patch.object(api.native.GuestPreflightGit, "snapshot", fail): result = self.reject()
        self.assertFalse(result.compilation_attempted)
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertNotIn("private snapshot details", json.dumps(result.to_dict()))

    def test_unsupported_compiler_never_observes_source(self):
        with patch.object(api, "_compiler_observation", side_effect=c.DeveloperTaskGuestPreflightError("unsupported_static_host_compiler")), \
             patch.object(api.source_preflight, "run_developer_task_guest_preflight_v2") as call:
            self.reject()
        call.assert_not_called()

    def test_noop_patch_rejected_before_compile(self):
        self.set_result_content(fx.CONTENT)
        self.assertFalse(self.reject().compilation_attempted)

    def test_wrong_file_patch_rejected_before_compile(self):
        self.response, self.manifest = self.wire(fx.make_patch(target="modules/wrong_target.py"))
        self.assertFalse(self.reject().compilation_attempted)

    def test_dirty_source_rejected_before_compile(self):
        (self.repo / "README.md").write_bytes(b"dirty\n")
        self.assertFalse(self.reject().compilation_attempted)

    def test_changed_profile_entrypoint_rejected_before_compile(self):
        self.commit_file(self.protected[0], b"# tampered protected entrypoint\n")
        self.assertFalse(self.reject().compilation_attempted)


for _name, _value in {
    "request_fingerprint": "0" * 64, "manifest_fingerprint": "0" * 64,
    "patch_sha256": "0" * 64, "source_sha256": "0" * 64, "profile_sha256": "0" * 64,
    "task_base_tree": "0" * 40, "target_preimage_oid": "0" * 40,
    "repository_snapshot_sha256": "0" * 64, "candidate_tree": "0" * 40,
    "candidate_blob_oid": "0" * 40, "candidate_content_sha256": "0" * 64,
    "candidate_content_bytes": 1,
}.items():
    def test(self, name=_name, value=_value):
        def change(result): return replace(result, facts=replace(result.facts, **{name:value}))
        with self.mutate_after_preflight(change), patch.object(api, "_compile_candidate") as compile_call:
            result = self.reject()
        compile_call.assert_not_called()
        self.assertFalse(result.compilation_attempted)
    setattr(StaticCheckTests, "test_reject_tampered_preflight_" + _name, test)

for _type in (MemoryError, RecursionError, ValueError, RuntimeError):
    def test(self, err=_type):
        with patch.object(api, "_compile_candidate", side_effect=err("not disclosed")): result = self.reject()
        self.assertTrue(result.compilation_attempted)
        self.assertFalse(result.compilation_observed_success)
        self.assertTrue(result.temporary_cleanup_verified)
        self.assertNotIn("not disclosed", json.dumps(result.to_dict()))
    setattr(StaticCheckTests, "test_compiler_failure_" + _type.__name__, test)


class CompilerUnitTests(unittest.TestCase):
    def test_helper_uses_exact_bytes_and_discards_code(self):
        self.assertIsNone(api._compile_candidate(b"VALUE = 1\n", "modules/unit.py"))
    def test_empty_compiles(self):
        self.assertIsNone(api._compile_candidate(b"", "modules/unit.py"))
    def test_casefold_python_suffix(self):
        self.assertIsNone(api._compile_candidate(b"VALUE = 1\n", "modules/unit.PY"))
    def test_size_limit(self):
        with self.assertRaises(c.DeveloperTaskGuestPreflightError):
            api._compile_candidate(b"#"*(api.MAX_CANDIDATE_BYTES+1), "modules/unit.py")
    def test_bytearray_not_accepted(self):
        with self.assertRaises(c.DeveloperTaskGuestPreflightError):
            api._compile_candidate(bytearray(b"x=1"), "modules/unit.py")
    def test_null_byte_rejected(self):
        with self.assertRaises(c.DeveloperTaskGuestPreflightError):
            api._compile_candidate(b"x=1\0", "modules/unit.py")
    def test_non_python_rejected(self):
        with self.assertRaises(c.DeveloperTaskGuestPreflightError):
            api._compile_candidate(b"x=1", "modules/unit.txt")
    def test_unsafe_filename_rejected(self):
        with self.assertRaises(c.DeveloperTaskGuestPreflightError):
            api._compile_candidate(b"x=1", "../unit.py")
    def test_compiler_observation_not_bundle_receipt(self):
        x = api._compiler_observation().to_dict()
        self.assertIs(x["runtime_bundle_accepted"], False)
        self.assertIs(x["executable_identity_attested"], False)
        self.assertIs(x["guest_target_interpreter_used"], False)
        self.assertEqual(x["version"], sys.version)
    def test_no_execution_calls_in_new_production_source(self):
        tree = ast.parse(Path(api.__file__).read_text(encoding="utf-8"))
        names = {x.func.id for x in ast.walk(tree) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)}
        self.assertFalse(names & {"eval", "exec", "__import__"})
        self.assertIn("compile", names)
        self.assertEqual(len([x for x in ast.walk(tree) if isinstance(x, ast.ImportFrom) and x.module and "developer_task_validator" in x.module]), 0)
    def test_incomplete_result_is_not_pass(self):
        result = api.DeveloperTaskGuestStaticCheckResult(None, None, (), ())
        self.assertFalse(result.ok)
        self.assertEqual(result.to_dict()["static_check_fingerprint"], "")


if __name__ == "__main__":
    suite = unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(StaticCheckTests),
                                unittest.defaultTestLoader.loadTestsFromTestCase(CompilerUnitTests)))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    ok = result.wasSuccessful() and not result.skipped
    print(json.dumps({
        "status": "PASS_NON_EXECUTING_GUEST_STATIC_CHECKS" if ok else "FAIL_GUEST_STATIC_CHECKS",
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "candidate_static_check_code_executed_for_tests": True,
        "candidate_target_compiled_not_executed": True, "synthetic_git_repositories_only": True,
        "guest_profile_executed": False, "changed_task_code_executed": False, "pyc_written_by_gate": False,
        "network_requested": False, "runtime_authorized": False, "promotion_authorized": False,
    }, sort_keys=True))
    raise SystemExit(0 if ok else 1)
