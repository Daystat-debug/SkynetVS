"""Focused real-Git fixtures for the read-only workspace collector."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe import collect, resolve_root

IGNORE = b'.env\n.idea/\n__pycache__/\n.venv/\nmodels/\ndata/learning/*.jsonl\ndata/inbox_labeled.jsonl\ndata/inbox_unlabeled.jsonl\n'


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m154_probe_')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '--quiet', '-b', 'sandbox/m154')
        self.git('remote', 'add', 'origin', 'https://github.com/Daystat-debug/SkynetVS.git')
        for folder in ('modules', 'tools'):
            (self.repo / folder).mkdir()
            (self.repo / folder / 'marker.txt').write_bytes(b'fixture\n')
        (self.repo / '.gitignore').write_bytes(IGNORE)
        self.git('add', '--', '.gitignore', 'modules', 'tools')
        self.git('commit', '--quiet', '-m', 'fixture')
        self.base = self.git('rev-parse', 'HEAD').decode().strip()

    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
        return subprocess.check_output(['git', '-c', 'core.autocrlf=false', '-c', 'core.hooksPath='+os.devnull,
                                       '-c', 'commit.gpgsign=false', '-c', 'user.name=Fixture',
                                       '-c', 'user.email=fixture@example.invalid', '-C', str(self.repo), *args], env=env, stderr=subprocess.PIPE)

    def probe(self):
        result = collect(self.repo, expected_base=self.base)
        self.assertTrue(result['source_git_state_unchanged'])
        return result

    @staticmethod
    def item(result, path):
        return next(item for item in result['ignore_probes'] if item['path'] == path)

    def test_normal_ignored_files_and_no_runtime_or_arbitrary_names_published(self):
        (self.repo / '.env').write_bytes(b'TEST_SECRET=never-publish-this-value\n')
        (self.repo / 'private-customer-name.txt').write_bytes(b'private')
        result = self.probe()
        self.assertEqual(result['branch'], 'sandbox/m154')
        self.assertEqual(result['head_layout']['classification'], 'SOURCE_TREE')
        self.assertTrue(self.item(result, '.env')['ignored_by_rules'])
        self.assertFalse(self.item(result, '.env')['tracked_in_index'])
        self.assertEqual(result['changed_path_count'], 1)
        self.assertEqual(result['changed_path_categories'], {'other': 1})
        public = json.dumps(result)
        self.assertNotIn('never-publish-this-value', public)
        self.assertNotIn('private-customer-name', public)
        self.assertTrue(result['root_gitignore']['worktree_matches_head'])
        self.assertEqual(resolve_root(self.repo / 'modules'), self.repo.resolve())

    def test_force_staged_ignored_file_is_visible_but_not_published(self):
        (self.repo / '.env').write_bytes(b'fixture-secret\n')
        self.git('add', '-f', '--', '.env')
        before = (self.repo / '.git/index').read_bytes()
        result = self.probe()
        self.assertEqual(result['tracked_ignored_count'], 1)
        self.assertEqual(result['status_counts'], {'A ': 1})
        self.assertTrue(self.item(result, '.env')['ignored_by_rules'])
        self.assertTrue(self.item(result, '.env')['tracked_in_index'])
        self.assertEqual((self.repo / '.git/index').read_bytes(), before)
        self.assertNotIn('fixture-secret', json.dumps(result))

    def test_reports_only_tree_does_not_infer_code_from_branch_name(self):
        self.git('rm', '-r', '--quiet', '--', '.gitignore', 'modules', 'tools')
        (self.repo / 'reports').mkdir()
        (self.repo / 'reports/report.json').write_bytes(b'{}\n')
        self.git('add', '--', 'reports')
        self.git('commit', '--quiet', '-m', 'reports-only fixture')
        (self.repo / '.env').write_bytes(b'secret remains local')
        result = self.probe()
        self.assertEqual(result['branch'], 'sandbox/m154')
        self.assertEqual(result['head_layout']['classification'], 'REPORTS_ONLY_TREE')
        self.assertFalse(result['root_gitignore']['head']['present'])
        self.assertEqual(result['root_gitignore']['worktree']['kind'], 'missing')
        self.assertFalse(self.item(result, '.env')['ignored_by_rules'])
        self.assertEqual(result['changed_path_categories'], {'environment_files': 1})

    def test_missing_and_utf16_ignore_are_distinguished(self):
        (self.repo / '.gitignore').unlink()
        (self.repo / '.env').write_bytes(b'not captured')
        missing = self.probe()
        self.assertEqual(missing['root_gitignore']['worktree']['kind'], 'missing')
        self.assertTrue(missing['root_gitignore']['head']['present'])
        self.assertFalse(self.item(missing, '.env')['ignored_by_rules'])
        (self.repo / '.gitignore').write_bytes(IGNORE.decode().encode('utf-16'))
        encoded = self.probe()
        self.assertEqual(encoded['root_gitignore']['worktree']['bom'], 'UTF16_LE_BOM' if sys.byteorder == 'little' else 'UTF16_BE_BOM')
        self.assertGreater(encoded['root_gitignore']['worktree']['nul_byte_count'], 0)
        self.assertFalse(encoded['root_gitignore']['worktree_matches_head'])

    def test_dirty_staged_renamed_untracked_work_and_negation_preserved(self):
        (self.repo / '.gitignore').write_bytes(IGNORE + b'!.env\n')
        self.git('mv', '--', 'modules/marker.txt', 'modules/renamed.txt')
        (self.repo / 'tools/marker.txt').write_bytes(b'edited unstaged\n')
        (self.repo / '.env').write_bytes(b'retain me\n')
        before = {p.relative_to(self.repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.repo.rglob('*') if p.is_file() and '.git' not in p.relative_to(self.repo).parts}
        index_before = (self.repo / '.git/index').read_bytes()
        result = self.probe()
        self.assertEqual(result['changed_path_count'], 4)
        self.assertEqual(result['status_counts']['R '], 1)
        env = self.item(result, '.env')
        self.assertTrue(env['matched'])
        self.assertEqual(env['pattern'], '!.env')
        self.assertFalse(env['ignored_by_rules'])
        after = {p.relative_to(self.repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.repo.rglob('*') if p.is_file() and '.git' not in p.relative_to(self.repo).parts}
        self.assertEqual(before, after)
        self.assertEqual(index_before, (self.repo / '.git/index').read_bytes())

    def test_unrelated_project_is_not_inspected(self):
        self.git('remote', 'set-url', 'origin', 'https://private-token@example.invalid/secret-project.git')
        (self.repo / '.env').write_bytes(b'not even inspected')
        result = collect(self.repo, expected_base=self.base)
        self.assertEqual(result['status'], 'UNVERIFIED_PROJECT')
        self.assertFalse(result['details_collected'])
        self.assertNotIn('branch', result)
        self.assertNotIn('status_counts', result)
        self.assertNotIn('private-token', json.dumps(result))
        self.assertNotIn('secret-project', json.dumps(result))

    def test_symlink_gitignore_contents_are_not_read_or_hashed(self):
        with tempfile.TemporaryDirectory(prefix='m154_ignore_external_') as external:
            target = Path(external) / 'private-ignore.txt'
            secret = b'EXTERNAL_SECRET_MUST_NOT_BE_READ\n.env\n'
            target.write_bytes(secret)
            (self.repo / '.gitignore').unlink()
            try:
                (self.repo / '.gitignore').symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('This environment cannot create symlinks.')
            result = self.probe()
            self.assertEqual(result['root_gitignore']['worktree'], {'kind': 'symlink', 'content_read': False})
            self.assertNotIn('EXTERNAL_SECRET', json.dumps(result))
            self.assertNotIn(hashlib.sha256(secret).hexdigest(), json.dumps(result))
            self.assertEqual(target.read_bytes(), secret)


if __name__ == '__main__':
    unittest.main(verbosity=2)
