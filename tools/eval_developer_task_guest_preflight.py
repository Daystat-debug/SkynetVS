from __future__ import annotations

"""Portable V2 source-preflight fixtures. Git only; no guest pipeline or target execution."""

import difflib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import stat
from types import SimpleNamespace
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from modules.developer import developer_task_guest_preflight as api
from modules.developer import developer_task_guest_preflight_git as ng
from modules.developer import developer_task_guest_preflight_contract as c
from modules.developer import developer_task_guest_request as req
from modules.developer import developer_task_guest_proposal_intake as intake
from modules.developer.developer_task_guest_profile_document import GUEST_PROFILE_DOCUMENT
from modules.developer.developer_task_validator import validate_developer_task_manifest

ROOT = Path(__file__).resolve().parents[1]
GIT = Path(shutil.which("git") or "git").resolve()
TARGET = "modules/v2_preflight_fixture.py"
CONTENT = b'"""Not executed by preflight."""\nVALUE = 1\n'
RESULT = CONTENT.replace(b"VALUE = 1", b"VALUE = 2")
PIPELINE = "tools/pipeline.py"


def cleanup_tree(path):
    def onerror(function, filename, _exc):
        os.chmod(filename, 0o700)
        function(filename)
    shutil.rmtree(ng.extended(path), onerror=onerror)


def oid(raw):
    return c.object_oid("blob", raw)


def encode(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def git(repo, *args):
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_"):
            env.pop(key, None)
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    cp = subprocess.run([str(GIT), "-C", str(repo), *args], env=env, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, timeout=30, check=False)
    if cp.returncode != 0:
        raise AssertionError((args, cp.returncode, cp.stderr.decode("utf-8", "replace")[:300]))
    return cp.stdout


def make_patch(new=RESULT, old=CONTENT, target=TARGET):
    diff = "".join(difflib.unified_diff(old.decode().splitlines(keepends=True), new.decode().splitlines(keepends=True),
                                     fromfile="a/"+target, tofile="b/"+target))
    return ("diff --git a/" + target + " b/" + target + "\n" + diff).encode()


class GuestPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix="vgp2_"))
        cls.seed = cls.work / "seed"
        cls.seed.mkdir()
        document = json.loads(GUEST_PROFILE_DOCUMENT)
        cls.protected = [x["path"] for x in document["steps"]]
        selected = cls.protected + [x["path"] for x in document["excluded_steps"]] + [PIPELINE]
        for rel in selected:
            dest = cls.seed / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT / rel).read_bytes())
        for rel, data in {TARGET: CONTENT, "modules/context_fixture.py": b"CONTEXT = 1\n",
                          ".gitattributes": b"* text=auto\n", "README.md": b"fixture\n"}.items():
            dest = cls.seed / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        git(cls.seed, "init", "-b", "main")
        for key, value in (("user.name", "SkynetVS Fixture"), ("user.email", "fixture@example.invalid"),
                           ("core.autocrlf", "false")):
            git(cls.seed, "config", key, value)
        git(cls.seed, "add", "--all")
        git(cls.seed, "commit", "-m", "source preflight fixture")
        cls.git_sha = hashlib.sha256(GIT.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cleanup_tree(cls.work)

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(prefix="case_", dir=self.work))
        self.repo = self.case / "repo"
        shutil.copytree(self.seed, self.repo)
        self.scratch = self.case / "scratch"
        self.scratch.mkdir()
        self.rebind()

    def tearDown(self):
        cleanup_tree(self.case)

    def rebind(self, *, content=CONTENT, context=None, base_commit=None, base_tree=None):
        self.head = git(self.repo, "rev-parse", "HEAD").decode().strip()
        self.tree = git(self.repo, "rev-parse", "HEAD^{tree}").decode().strip()
        self.request = req.prepare_developer_task_guest_request_v2(
            task_id="v2-source-preflight", request_id="v2-preflight-fixture", title="Bound text patch",
            instruction="Change VALUE in the fixed target.", task_base_commit=base_commit or self.head,
            task_base_tree=base_tree or self.tree, target_path=TARGET,
            context_entries=context or (req.DeveloperTaskGuestContextInputV2(TARGET, "100644", oid(content), content),),
            profile_document=GUEST_PROFILE_DOCUMENT,
        )
        self.response, self.manifest = self.wire(make_patch(old=content))

    def wire(self, raw_patch):
        response = intake.encode_developer_task_guest_proposal_v2(
            expected_request=self.request, patch_text=raw_patch.decode(), explanation="Fixture; never execute target.",
            profile_document=GUEST_PROFILE_DOCUMENT,
        )
        plan = intake.parse_developer_task_guest_proposal_v2(response, expected_request=self.request,
                                                            profile_document=GUEST_PROFILE_DOCUMENT)
        manifest = intake.canonical_developer_task_guest_manifest_v2(
            plan.manifest, expected_request=self.request, raw_response=response, profile_document=GUEST_PROFILE_DOCUMENT,
        )
        return response, manifest

    def run_preflight(self, **changes):
        kwargs = dict(raw_response=self.response, expected_request=self.request, profile_document=GUEST_PROFILE_DOCUMENT,
                      repository_root=self.repo, git_executable=GIT, expected_git_sha256=self.git_sha,
                      scratch_parent=self.scratch)
        manifest = changes.pop("raw_manifest", self.manifest)
        kwargs.update(changes)
        return api.run_developer_task_guest_preflight_v2(manifest, **kwargs)

    def reject(self, **changes):
        result = self.run_preflight(**changes)
        self.assertFalse(result.ok)
        self.assertIsNone(result.facts)
        self.assertTrue(result.issue_codes)
        self.assertEqual(result.to_dict()["accepted_preflight_binding"], "")
        for name in ("runtime_authorized", "promotion_authorized", "guest_profile_executed", "changed_task_code_executed",
                     "capability_issued", "all_required_checks_passed", "ready_to_promote"):
            self.assertFalse(result.to_dict()[name])
        return result

    def success(self, **changes):
        result = self.run_preflight(**changes)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.completed_stages, c.STAGES)
        self.assertTrue(result.repository_unchanged_verified)
        self.assertTrue(result.temporary_cleanup_verified)
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertEqual(result.facts.protected_entrypoints, 101)
        for name in ("runtime_authorized", "promotion_authorized", "guest_profile_executed", "changed_task_code_executed",
                     "capability_issued", "all_required_checks_passed", "ready_to_promote", "protected_helper_closure_verified",
                     "git_runtime_bundle_accepted", "replay_prevention_verified"):
            self.assertFalse(result.to_dict()[name])
        self.assertEqual(result.to_dict()["pending_task_checks"], ["py_compile", "pipeline:check_guest_source_v1"])
        return result

    def commit_file(self, path, data):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        git(self.repo, "add", "--", path)
        git(self.repo, "commit", "-m", "fixture change")
        self.rebind()

    def test_valid_lf_and_independent_candidate_tree(self):
        before_index = (self.repo / ".git/index").read_bytes()
        result = self.success()
        self.assertEqual((self.repo / ".git/index").read_bytes(), before_index)
        self.assertEqual((self.repo / TARGET).read_bytes(), CONTENT)
        self.assertEqual(result.facts.candidate_blob_oid, oid(RESULT))
        self.assertEqual(result.facts.candidate_content_sha256, c.sha(RESULT))
        (self.repo / TARGET).write_bytes(RESULT)
        git(self.repo, "add", "--", TARGET)
        self.assertEqual(git(self.repo, "write-tree").strip().decode(), result.facts.candidate_tree)

    def test_crlf_worktree(self):
        git(self.repo, "config", "core.autocrlf", "true")
        for p in self.repo.rglob("*.py"):
            p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.success()

    def test_second_context_real_membership(self):
        data = (self.repo / "modules/context_fixture.py").read_bytes()
        self.rebind(context=(req.DeveloperTaskGuestContextInputV2(TARGET, "100644", oid(CONTENT), CONTENT),
                             req.DeveloperTaskGuestContextInputV2("modules/context_fixture.py", "100644", oid(data), data)))
        self.assertEqual(self.success().facts.context_files, 2)

    def test_newly_pinned_descendant(self):
        self.commit_file("README.md", b"explicitly pinned new task base\n")
        self.success()

    def test_stale_head_refused(self):
        (self.repo / "README.md").write_bytes(b"new head\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "advance")
        self.assertIn("repository_head_mismatch", self.reject().issue_codes)

    def test_wrong_base_tree(self):
        self.rebind(base_tree="a" * 40)
        self.assertIn("repository_base_tree_mismatch", self.reject().issue_codes)

    def test_false_preimage(self):
        self.rebind(content=CONTENT.replace(b"VALUE = 1", b"VALUE = 7"))
        self.assertIn("context_not_in_base_tree", self.reject().issue_codes)

    def test_untracked_worktree_file(self):
        (self.repo / "extra.txt").write_bytes(b"extra")
        self.reject()

    def test_dirty_tracked_file(self):
        (self.repo / "README.md").write_bytes(b"dirty\n")
        self.assertIn("repository_not_clean", self.reject().issue_codes)

    def test_foreign_staging(self):
        (self.repo / "README.md").write_bytes(b"staged\n")
        git(self.repo, "add", "README.md")
        self.assertIn("repository_index_mismatch", self.reject().issue_codes)

    def test_skip_worktree(self):
        git(self.repo, "update-index", "--skip-worktree", "README.md")
        self.assertIn("repository_index_flags", self.reject().issue_codes)

    def test_assume_unchanged(self):
        git(self.repo, "update-index", "--assume-unchanged", "README.md")
        self.assertIn("repository_index_flags", self.reject().issue_codes)

    def test_hardlinked_source(self):
        os.link(self.repo / TARGET, self.case / "source_link")
        self.assertIn("hardlinked_source_file", self.reject().issue_codes)

    def test_hardlinked_git_read_is_allowed(self):
        exe = self.case / "git.exe"
        shutil.copyfile(GIT, exe)
        exe.chmod(0o755)
        os.link(exe, self.case / "git_link.exe")
        # Git-for-Windows cmd/git.exe is a launcher with installation-relative
        # dependencies: copying it is valid for observing hardlinks, not execution.
        pin = ng.git_identity(exe, self.git_sha)
        self.assertEqual(pin["sha256"], self.git_sha)
        self.assertEqual(os.stat(exe).st_nlink, 2)
        self.success()

    def test_wrong_git_pin(self):
        result = self.reject(expected_git_sha256="0" * 64)
        self.assertEqual(result.git_command_count, 0)

    def test_scratch_inside_repo(self):
        result = self.reject(scratch_parent=self.repo)
        self.assertEqual(result.git_command_count, 0)

    def test_relative_repository_refused(self):
        self.reject(repository_root=Path("relative"))

    def test_symlink_repository_refused(self):
        link = self.case / "repo_alias"
        try:
            link.symlink_to(self.repo, target_is_directory=True)
        except OSError:
            # Windows privilege-independent substitute: emulate the OS reparse bit
            # at the single filesystem observation, without replacing admission logic.
            original = os.lstat
            class Attrs:
                def __init__(self, st):
                    for name in dir(st):
                        if name.startswith("st_"):
                            setattr(self, name, getattr(st, name))
                    self.st_file_attributes = getattr(st, "st_file_attributes", 0) | 0x400
            def observe(path, *a, **kw):
                st = original(path, *a, **kw)
                return Attrs(st) if os.path.normcase(str(path)).endswith(os.path.normcase(str(self.repo))) else st
            with patch.object(ng.os, "lstat", observe):
                self.reject()
        else:
            self.reject(repository_root=link)
            link.unlink()

    def test_gitdir_pointer_refused(self):
        shutil.move(self.repo / ".git", self.case / "git_backup")
        (self.repo / ".git").write_text("gitdir: ../git_backup\n")
        self.reject()

    def test_profile_step_drift_refused(self):
        name = self.protected[0]
        self.commit_file(name, (self.repo / name).read_bytes() + b"\n# changed protected harness\n")
        self.assertIn("protected_profile_entrypoint_changed", self.reject().issue_codes)

    def test_pipeline_drift_refused(self):
        self.commit_file(PIPELINE, (self.repo / PIPELINE).read_bytes() + b"\n# topology change\n")
        self.assertIn("protected_profile_entrypoint_changed", self.reject().issue_codes)

    def test_malformed_profile_before_io(self):
        result = self.reject(profile_document=GUEST_PROFILE_DOCUMENT + b"\n")
        self.assertEqual(result.git_command_count, 0)

    def test_manifest_tamper_before_io(self):
        data = json.loads(self.manifest)
        data["patch_sha256"] = "0" * 64
        result = self.reject(raw_manifest=encode(data))
        self.assertEqual(result.git_command_count, 0)

    def test_v1_manifest_refused_without_io(self):
        result = self.reject(raw_manifest=b'{"schema_version":1}')
        self.assertEqual(result.git_command_count, 0)

    def test_rehashed_manifest_tamper_before_io(self):
        data = json.loads(self.manifest)
        data["allowed_files"] = ["modules/other.py"]
        data.pop("manifest_fingerprint")
        data["manifest_fingerprint"] = c.sha(c.canonical(data))
        self.assertEqual(self.reject(raw_manifest=encode(data)).git_command_count, 0)

    def test_tampered_frozen_request_refused(self):
        self.assertEqual(self.reject(expected_request=replace(self.request, instruction="different task")).git_command_count, 0)

    def test_duplicate_manifest_key_before_io(self):
        bad = self.manifest.rstrip()[:-1] + b',"schema_version":2}\n'
        self.assertEqual(self.reject(raw_manifest=bad).git_command_count, 0)

    def test_raw_response_format_is_bound(self):
        pretty = json.dumps(json.loads(self.response), indent=2).encode()
        self.assertEqual(self.reject(raw_response=pretty).git_command_count, 0)

    def test_preflight_report_not_v1_manifest(self):
        data = self.success().to_dict()
        self.assertFalse(validate_developer_task_manifest(data).ok)

    def test_preflight_fingerprint_covers_candidate_and_manifest(self):
        result = self.success()
        self.assertNotEqual(replace(result.facts, candidate_tree="a" * 40).fingerprint, result.facts.fingerprint)
        self.assertNotEqual(replace(result.facts, manifest_fingerprint="0" * 64).fingerprint, result.facts.fingerprint)

    def test_new_observation_is_not_reused_capability(self):
        a = self.success()
        b = self.success()
        self.assertEqual(a.facts.candidate_tree, b.facts.candidate_tree)
        self.assertNotEqual(a.facts.fingerprint, b.facts.fingerprint)
        self.assertNotEqual(a.facts.observation_id, b.facts.observation_id)

    def test_request_target_and_patch_not_executed(self):
        marker = self.case / "never-created"
        new = CONTENT + ("open(" + repr(str(marker)) + ", 'w').write('unsafe')\n").encode()
        self.response, self.manifest = self.wire(make_patch(new=new))
        self.success()
        self.assertFalse(marker.exists())

    def test_python_syntax_check_is_explicitly_pending(self):
        self.response, self.manifest = self.wire(make_patch(new=b"not valid python!!!\n"))
        self.success()

    def test_unapplicable_hunk(self):
        raw = make_patch().replace(b"-VALUE = 1", b"-VALUE = 999")
        self.response, self.manifest = self.wire(raw)
        result = self.reject()
        self.assertIn("git_apply_failed", result.issue_codes)
        self.assertTrue(result.repository_unchanged_verified)
        self.assertTrue(result.temporary_cleanup_verified)

    def test_whitespace_error_rejected(self):
        self.response, self.manifest = self.wire(make_patch(new=CONTENT.replace(b"VALUE = 1", b"VALUE = 2  ")))
        self.assertIn("git_apply_failed", self.reject().issue_codes)

    def test_exact_index_header_valid(self):
        raw = make_patch().replace(b"--- a/", ("index " + oid(CONTENT) + ".." + oid(RESULT) + " 100644\n--- a/").encode(), 1)
        self.response, self.manifest = self.wire(raw)
        self.success()

    def test_false_new_index_oid(self):
        raw = make_patch().replace(b"--- a/", ("index " + oid(CONTENT) + ".." + "a"*40 + " 100644\n--- a/").encode(), 1)
        self.response, self.manifest = self.wire(raw)
        self.assertIn("patch_new_oid_mismatch", self.reject().issue_codes)

    def test_added_no_newline_marker(self):
        raw = make_patch(new=RESULT).replace(b"+VALUE = 2\n", b"+VALUE = 2\n\\ No newline at end of file\n")
        self.response, self.manifest = self.wire(raw)
        result = self.success()
        self.assertEqual(result.facts.candidate_blob_oid, oid(RESULT.rstrip(b"\n")))

    def test_live_repository_changed_during_temp_apply(self):
        original = ng.GuestPreflightGit.apply_patch
        def changed(obj, *args, **kwargs):
            original(obj, *args, **kwargs)
            (self.repo / "README.md").write_bytes(b"race\n")
        with patch.object(ng.GuestPreflightGit, "apply_patch", changed):
            result = self.reject()
        self.assertFalse(result.repository_unchanged_verified)
        self.assertTrue(result.temporary_cleanup_verified)

    def test_scope_failure_after_private_apply(self):
        original = ng.GuestPreflightGit.candidate
        def wrong(obj, base, rows, target, old):
            return original(obj, base, rows, target + "-wrong", old)
        with patch.object(ng.GuestPreflightGit, "candidate", wrong):
            result = self.reject()
        self.assertIn("patch_scope_mismatch", result.issue_codes)
        self.assertTrue(result.repository_unchanged_verified)

    def test_cleanup_failure_cannot_pass(self):
        with patch.object(api, "remove_private_tree", side_effect=OSError("fixture")):
            result = self.reject()
        self.assertFalse(result.temporary_cleanup_verified)
        self.assertTrue(result.repository_unchanged_verified)

    def test_source_hardlink_gitmeta_unchanged(self):
        os.link(self.repo / "README.md", self.case / "other")
        before = (self.repo / ".git/index").read_bytes()
        self.reject()
        self.assertEqual(before, (self.repo / ".git/index").read_bytes())

    def test_host_git_overrides_not_inherited(self):
        with patch.dict(os.environ, {"GIT_DIR": str(self.case / "wrong"), "GIT_INDEX_FILE": str(self.case / "badindex"),
                                    "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "alias.status", "GIT_CONFIG_VALUE_0": "!bad"}):
            self.success()
        self.assertFalse((self.case / "badindex").exists())

    def test_only_git_executable_and_no_network_commands(self):
        original = ng.subprocess.Popen
        calls = []
        def record(args, **kwargs):
            if any(a.startswith("--git-dir=") for a in args):
                calls.append(args)
                self.assertEqual(args[0], str(GIT))
                self.assertFalse(kwargs["shell"])
                self.assertEqual(kwargs["env"]["GIT_ALLOW_PROTOCOL"], "")
                self.assertNotIn("PYTHONPATH", kwargs["env"])
            return original(args, **kwargs)
        with patch.object(ng.subprocess, "Popen", record):
            self.success()
        self.assertTrue(calls)
        for call in calls:
            verb = call[next(i for i, a in enumerate(call) if a.startswith("--work-tree=")) + 1]
            self.assertNotIn(verb, ("push", "fetch", "clone", "commit", "reset", "checkout", "add"))

    def test_git_timeout_returns_failure(self):
        class Fake:
            returncode = None
            def poll(self): return self.returncode
            def kill(self): self.returncode = -1
            def wait(self, timeout=None): return self.returncode
        with patch.object(ng.subprocess, "Popen", return_value=Fake()), patch.object(ng, "GIT_TIMEOUT_SECONDS", -1):
            self.assertIn("git_command_timeout", self.reject().issue_codes)

    def test_git_output_limit_returns_failure(self):
        class Fake:
            returncode = 0
            def poll(self): return 0
        def spawn(_cmd, **kw):
            kw["stdout"].write(b"x" * 2048)
            kw["stdout"].flush()
            return Fake()
        with patch.object(ng.subprocess, "Popen", spawn), patch.object(ng, "MAX_GIT_OUTPUT", 1024):
            self.assertIn("git_output_limit", self.reject().issue_codes)

    def test_full_source_path_fixture(self):
        # All current source paths, not a claim of reproducing missing non-source bytes.
        files = []
        for sub in ("modules", "tools", "docs", "tests", "train", "native"):
            directory = ROOT / sub
            if directory.is_dir():
                files.extend(p for p in directory.rglob("*") if p.is_file()
                             and "__pycache__" not in p.parts)
        for p in files:
            rel = p.relative_to(ROOT)
            q = self.repo / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_bytes(p.read_bytes())
        git(self.repo, "add", "--all")
        git(self.repo, "commit", "-m", "full source fixture")
        self.rebind()
        self.assertGreaterEqual(self.success().facts.tracked_paths, 400)


    def test_readonly_private_cleanup(self):
        root = self.scratch / "owned"
        root.mkdir()
        p = root / "readonly"
        p.write_bytes(b"owned scratch data")
        p.chmod(0o400)
        ng.remove_private_tree(root)
        self.assertFalse(root.exists())

    def test_hardlinked_private_cleanup_refuses_attribute_changes(self):
        root = self.scratch / "owned"
        root.mkdir()
        outside = self.case / "outside"
        outside.write_bytes(b"untouched")
        os.link(outside, root / "link")
        with self.assertRaises(c.DeveloperTaskGuestPreflightError):
            ng.remove_private_tree(root)
        self.assertEqual(outside.read_bytes(), b"untouched")

    def test_wrong_context_membership_even_with_consistent_hash(self):
        fake = b"NOT_IN_TREE = 3\n"
        self.rebind(context=(req.DeveloperTaskGuestContextInputV2(TARGET, "100644", oid(CONTENT), CONTENT),
                             req.DeveloperTaskGuestContextInputV2("modules/context_fixture.py", "100644", oid(fake), fake)))
        self.assertIn("context_not_in_base_tree", self.reject().issue_codes)

    def test_excluded_entrypoint_drift_does_not_change_coverage(self):
        name = json.loads(GUEST_PROFILE_DOCUMENT)["excluded_steps"][0]["path"]
        self.commit_file(name, (self.repo / name).read_bytes() + b"\n# changed exclusion\n")
        self.assertIn("protected_profile_entrypoint_changed", self.reject().issue_codes)

    def test_untracked_attribute_file_rejected(self):
        (self.repo / "modules/.gitattributes").write_bytes(b"*.py filter=evil\n")
        self.assertIn("untracked_attribute_file", self.reject().issue_codes)

    def test_filter_attribute_rejected_without_filter_execution(self):
        self.commit_file(".gitattributes", b"* text=auto\n*.py filter=not-installed\n")
        self.assertIn("external_or_transforming_attribute", self.reject().issue_codes)

    def test_no_net_change_patch_rejected(self):
        raw = make_patch().replace(b"+VALUE = 2\n", b"+VALUE = 1\n")
        self.response, self.manifest = self.wire(raw)
        self.assertIn("patch_scope_mismatch", self.reject().issue_codes)

    def test_case_colliding_index_paths_rejected(self):
        entries = [{"mode": "100644", "oid": "a"*40, "path": "modules/A.py"},
                   {"mode": "100644", "oid": "b"*40, "path": "modules/a.py"}]
        with self.assertRaises(c.DeveloperTaskGuestPreflightError):
            ng.check_entries(entries)

    def test_special_index_modes_rejected(self):
        for mode in ("120000", "160000"):
            with self.assertRaises(c.DeveloperTaskGuestPreflightError):
                ng.check_entries([{"mode": mode, "oid": "a"*40, "path": "modules/a.py"}])

    def test_protocol_and_live_write_commands_refused(self):
        root = self.scratch / "adapter"
        root.mkdir()
        g = ng.GuestPreflightGit(self.repo, GIT, root)
        g.checked_config = True
        for args in (["fetch"], ["push"], ["add", "--", TARGET], ["read-tree", self.head],
                     ["apply", "--cached", "-"], ["config", "user.name", "changed"]):
            with self.assertRaises(c.DeveloperTaskGuestPreflightError):
                g.run(args)
        self.assertEqual(g.command_count, 0)

    def test_git_symlink_metadata_refused(self):
        original = ng.indirect
        # Privilege-independent reparse observation for this test only.
        with patch.object(ng, "indirect", lambda st: True):
            result = self.reject()
        self.assertEqual(result.git_command_count, 0)


# Each case is a distinct test, with a newly isolated Git fixture.
BAD_PATCHES = {
    "plain_text": b"opaque non-diff\n",
    "wrong_file": make_patch(target="modules/other.py"),
    "traversal_header": make_patch(target="../outside.py"),
    "absolute_header": make_patch(target="/outside.py"),
    "preamble": b"mail header\n" + make_patch(),
    "trailer": make_patch() + b"trailer\n",
    "second_file": make_patch() + make_patch(target="modules/other.py"),
    "rename": ("diff --git a/"+TARGET+" b/"+TARGET+"\nsimilarity index 100%\nrename from x\nrename to y\n").encode(),
    "copy": make_patch().replace(b"--- a/", b"copy from x\ncopy to y\n--- a/", 1),
    "mode_change": make_patch().replace(b"--- a/", b"old mode 100644\nnew mode 100755\n--- a/", 1),
    "binary": ("diff --git a/"+TARGET+" b/"+TARGET+"\nGIT binary patch\nliteral 0\nHcmV?d00001\n").encode(),
    "quoted_path": make_patch().replace(b"diff --git a/", b'diff --git "a/', 1),
    "new_file": make_patch().replace(("--- a/"+TARGET).encode(), b"--- /dev/null"),
    "delete_file": make_patch().replace(("+++ b/"+TARGET).encode(), b"+++ /dev/null"),
    "hunk_overflow": make_patch().replace(b"@@ -1,2 +1,2 @@", b"@@ -1,1 +1,1 @@"),
    "hunk_truncated": make_patch().replace(b"@@ -1,2 +1,2 @@", b"@@ -1,9 +1,9 @@"),
    "index_wrong_old": make_patch().replace(b"--- a/", b"index aaaaaaa..bbbbbbb 100644\n--- a/", 1),
    "index_wrong_mode": make_patch().replace(b"--- a/", ("index "+oid(CONTENT)+".."+oid(RESULT)+" 100755\n--- a/").encode(), 1),
    "header_timestamp": make_patch().replace(("+++ b/"+TARGET+"\n").encode(), ("+++ b/"+TARGET+"\t2026-01-01\n").encode()),
    "unterminated_diff": make_patch().rstrip(b"\n"),
    "no_hunks": ("diff --git a/"+TARGET+" b/"+TARGET+"\n--- a/"+TARGET+"\n+++ b/"+TARGET+"\n").encode(),
    "orphan_newline_marker": make_patch().replace(b"@@ -1,2 +1,2 @@\n", b"@@ -1,2 +1,2 @@\n\\ No newline at end of file\n"),
}
for _name, _data in BAD_PATCHES.items():
    def _test(self, raw=_data):
        self.response, self.manifest = self.wire(raw)
        result = self.reject()
        self.assertEqual(result.git_command_count, 0)
    setattr(GuestPreflightTests, "test_patch_format_" + _name, _test)

for _key, _value in {
    "filter.bad.clean": "fake-external-command",
    "core.fsmonitor": "fake-external-command",
    "include.path": "other-config",
    "core.attributesfile": "other-attributes",
    "core.sparsecheckout": "true",
    "diff.bad.textconv": "fake-external-command",
}.items():
    def _test(self, key=_key, value=_value):
        git(self.repo, "config", key, value)
        result = self.reject()
        self.assertTrue(set(result.issue_codes) & {"unsafe_git_config", "unsupported_git_config"})
    setattr(GuestPreflightTests, "test_config_" + _key.replace(".", "_"), _test)

for _path in ("shallow", "info/grafts", "objects/info/alternates", "index.lock", "MERGE_HEAD", "refs/replace/" + "a"*40):
    def _test(self, rel=_path):
        p = self.repo / ".git" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fixture")
        result = self.reject()
        self.assertEqual(result.git_command_count, 0)
    setattr(GuestPreflightTests, "test_git_metadata_" + _path.replace("/", "_"), _test)


class ReaderCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="mode_"))
        self.exe = self.work / "fixture.exe"
        self.data = b"MZ read-only fixture; never executed"
        self.exe.write_bytes(self.data)

    def tearDown(self):
        cleanup_tree(self.work)

    @staticmethod
    def row(mode=0o100666, **changes):
        fields = dict(st_dev=7, st_ino=123, st_mode=mode, st_size=32,
                      st_mtime_ns=1700000000123456700, st_nlink=1, st_file_attributes=32)
        fields.update(changes)
        return SimpleNamespace(**fields)

    def test_original_full_mode_equality_reproduces_false_alarm(self):
        self.assertNotEqual(ng._version(self.row(0o100777)), ng._version(self.row()))
        self.assertTrue(ng._path_handle_match(self.exe, self.row(0o100777), self.row(), windows=True))

    def test_native_regular_executable_suffix_read(self):
        self.assertEqual(ng.read_regular(self.exe), self.data)

    def test_all_four_windows_suffixes_and_case(self):
        for suffix in (".exe", ".bat", ".cmd", ".com", ".EXE", ".CmD"):
            p = self.work / ("fixture" + suffix)
            self.assertTrue(ng._path_handle_match(p, self.row(0o100777), self.row(), windows=True))

    def test_native_bat_cmd_com_suffix_reads(self):
        for suffix in (".bat", ".cmd", ".com"):
            p = self.work / ("fixture" + suffix); p.write_bytes(self.data)
            self.assertEqual(ng.read_regular(p), self.data)

    def test_non_windows_execute_bit_difference_rejected(self):
        self.assertFalse(ng._path_handle_match(self.exe, self.row(0o100777), self.row(), windows=False))

    def test_non_executable_suffix_difference_rejected(self):
        self.assertFalse(ng._path_handle_match(self.work / "fixture.py", self.row(0o100777), self.row(), windows=True))

    def test_reversed_difference_rejected(self):
        self.assertFalse(ng._path_handle_match(self.exe, self.row(), self.row(0o100777), windows=True))

    def test_partial_execute_difference_rejected(self):
        self.assertFalse(ng._path_handle_match(self.exe, self.row(0o100766), self.row(), windows=True))

    def test_read_write_permission_difference_rejected(self):
        self.assertFalse(ng._path_handle_match(self.exe, self.row(0o100577), self.row(), windows=True))

    def test_read_only_mode_synthesis_allowed(self):
        self.assertTrue(ng._path_handle_match(self.exe, self.row(0o100555), self.row(0o100444), windows=True))

    def test_same_api_mode_changes_are_not_normalized(self):
        self.assertNotEqual(ng._version(self.row(0o100777)), ng._version(self.row(0o100666)))

    def test_executable_source_hardlinks_still_rejected(self):
        os.link(self.exe, self.work / "alias.exe")
        with self.assertRaises(c.DeveloperTaskGuestPreflightError):
            ng.read_regular(self.exe)
        self.assertEqual(ng.read_regular(self.exe, hardlinks=True), self.data)

    def test_changed_handle_during_read_rejected(self):
        real_read = ng.os.read
        changed = False
        def mutate(fd, size):
            nonlocal changed
            raw = real_read(fd, size)
            if not changed:
                changed = True
                st = os.stat(self.exe)
                os.utime(self.exe, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
            return raw
        with patch.object(ng.os, "read", mutate):
            with self.assertRaises(c.DeveloperTaskGuestPreflightError):
                ng.read_regular(self.exe)


for _field, _different in {
    "st_dev": 8, "st_ino": 124, "st_size": 33, "st_mtime_ns": 1700000000123456800,
    "st_nlink": 2, "st_file_attributes": 33,
}.items():
    def _test(self, field=_field, different=_different):
        self.assertFalse(ng._path_handle_match(self.exe, self.row(0o100777),
                                             self.row(**{field: different}), windows=True))
    setattr(ReaderCompatibilityTests, "test_cross_api_reject_" + _field, _test)


if __name__ == "__main__":
    suite = unittest.TestSuite((
        unittest.defaultTestLoader.loadTestsFromTestCase(GuestPreflightTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(ReaderCompatibilityTests),
    ))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({
        "status": "PASS_READ_ONLY_GUEST_PREFLIGHT" if result.wasSuccessful() else "FAIL_READ_ONLY_GUEST_PREFLIGHT",
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "candidate_preflight_code_executed_for_tests": True,
        "synthetic_git_repositories_only": True, "guest_profile_executed": False,
        "changed_task_code_executed": False, "network_requested": False,
        "runtime_authorized": False, "promotion_authorized": False,
    }, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
