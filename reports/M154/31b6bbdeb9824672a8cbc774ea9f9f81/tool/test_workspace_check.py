"""Integration tests for diagnostic publication and preservation of source Git."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workspace_check as check


class WorkspaceCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='m154_workspace_')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.git(self.source, 'init', '--quiet', '-b', 'sandbox/m154')
        self.git(self.source, 'remote', 'add', 'origin', check.REMOTE)
        (self.source / '.gitignore').write_bytes(b'.env\n.venv/\n')
        (self.source / 'modules').mkdir()
        (self.source / 'tools').mkdir()
        (self.source / 'modules/file.py').write_bytes(b'x = 1\n')
        (self.source / 'tools/file.py').write_bytes(b'x = 1\n')
        self.git(self.source, 'add', '--', '.gitignore', 'modules/file.py', 'tools/file.py')
        self.git(self.source, 'commit', '--quiet', '-m', 'fixture')
        (self.source / '.env').write_bytes(b'PRIVATE_VALUE=must-remain-local\n')
        (self.source / 'modules/file.py').write_bytes(b'x = 2\n')
        self.git(self.source, 'add', '--', 'modules/file.py')
        (self.source / 'private-untracked-file.txt').write_bytes(b'user work\n')
        self.remote = self.root / 'remote.git'
        self.git(self.root, 'init', '--quiet', '--bare', str(self.remote))
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        here = Path(__file__).resolve().parent
        names = ('workspace_check.py', 'probe.py', 'test_probe.py', 'test_workspace_check.py',
                 'git_transport.py', 'workflow_run.py', 'development_lessons.py')
        for name in names:
            shutil.copyfile(here / name, self.bundle / name)
        for name, data in [('launch_template.ps1', b'# fixture; not executed\n'),
                           ('preparation_qa.json', b'{"fixture":true}\n'),
                           ('preparation_qa.log.txt', b'fixture\n')]:
            (self.bundle / name).write_bytes(data)
        entries = {p.name: {'sha256': check.sha(p.read_bytes()), 'size_bytes': p.stat().st_size}
                   for p in self.bundle.iterdir()}
        (self.bundle / 'manifest.json').write_bytes(check.json_bytes({'schema': 'SKYNETVS_M154_WORKSPACE_CHECK_PACKAGE_V1', 'files': entries}))

    @staticmethod
    def git(repo, *args):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
        return subprocess.check_output(['git', '--no-optional-locks', '-c', 'core.autocrlf=false',
            '-c', 'core.hooksPath='+os.devnull, '-c', 'commit.gpgsign=false',
            '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', '-C', str(repo), *args],
            env=env, stderr=subprocess.PIPE)

    def snapshot(self):
        return {str(p.relative_to(self.source)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.source.rglob('*') if p.is_file()}

    def execute(self, run_name='run', remote=None):
        return check.run_check(self.source, self.bundle, self.root / run_name,
                               project_repo=self.source, remote_url=str(remote or self.remote))

    def test_exact_report_sources_and_retry_preserve_source_and_ignore_extra_file(self):
        before = self.snapshot()
        result = self.execute()
        self.assertEqual(result['summary']['status'], 'COLLECTED')
        self.assertEqual(result['publication']['candidate']['status'], 'NOT_CREATED')
        self.assertEqual(result['publication']['report']['status'], 'PUBLISHED')
        self.assertEqual(self.snapshot(), before)
        public = self.root / 'run/public'
        receipt = json.loads((public / 'receipt.json').read_bytes())
        run_id = result['summary']['run_id']
        for name in receipt['files']:
            saved = self.git(self.remote, 'show', 'refs/heads/reports/m154:reports/M154/' + run_id + '/' + name)
            self.assertEqual(saved, (public / name).read_bytes())
        self.assertNotIn('must-remain-local', (public / 'summary.json').read_text())
        self.assertNotIn('private-untracked-file.txt', (public / 'summary.json').read_text())
        head = self.git(self.remote, 'rev-parse', 'refs/heads/reports/m154')
        (public / 'extra.txt').write_bytes(b'never publish this\n')
        with patch.object(check, 'collect', side_effect=AssertionError('must not recollect')):
            repeated = self.execute()
        self.assertTrue(repeated['reused_saved_diagnostics'])
        self.assertEqual(self.git(self.remote, 'rev-parse', 'refs/heads/reports/m154'), head)
        self.assertEqual(self.snapshot(), before)

    def test_offline_local_commit_and_later_retry_without_recollection(self):
        absent = self.root / 'temporarily-missing.git'
        result = self.execute(remote=absent)
        self.assertEqual(result['publication']['report']['status'], 'PENDING')
        self.assertTrue(result['publication']['local_report_commit'])
        self.git(self.root, 'init', '--quiet', '--bare', str(absent))
        with patch.object(check, 'collect', side_effect=AssertionError('must not recollect')):
            repeated = self.execute(remote=absent)
        self.assertEqual(repeated['publication']['report']['status'], 'PUBLISHED')
        self.assertEqual(repeated['summary'], result['summary'])

    def test_actual_git_root_overlap_rejected_before_write(self):
        run = self.source / 'should-not-exist'
        with self.assertRaisesRegex(check.CheckError, 'REPORT_SOURCE_OVERLAP'):
            check.run_check(self.source / 'modules', self.bundle, run,
                            project_repo=self.source / 'tools', remote_url=str(self.remote))
        self.assertFalse(run.exists())

    def test_retry_rejects_changed_binding_and_changed_public_bytes(self):
        self.execute()
        with self.assertRaisesRegex(check.CheckError, 'SAVED_RUN_BINDING_MISMATCH'):
            check.run_check(self.source / 'modules', self.bundle, self.root / 'run',
                            project_repo=self.source, remote_url=str(self.remote))
        summary = self.root / 'run/public/summary.json'
        summary.write_bytes(summary.read_bytes() + b' ')
        with self.assertRaisesRegex(check.CheckError, 'REPORT_BYTES_CHANGED'):
            self.execute()


if __name__ == '__main__':
    unittest.main(verbosity=2)
