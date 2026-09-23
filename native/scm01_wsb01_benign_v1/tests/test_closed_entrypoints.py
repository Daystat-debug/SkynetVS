"""CLOSED_ENTRYPOINTS01-08. No guest payload import/execution, no native constructors."""
import ast
import contextlib
import importlib
import io
import json
from pathlib import Path
import unittest
from . import test_contract as f
from .. import benign_main as main
from .. import benign_runtime_gate as gate
from .. import benign_windows_fs as fs
from .. import benign_windows_crypto as crypto
from .. import benign_windows_session as session
from .. import benign_orchestrator as orchestrator
from .. import benign_worker as worker
from .. import benign_capsule as capsule

ROOT = Path(__file__).resolve().parents[1]


class ClosedEntrypointTests(unittest.TestCase):
    def test_CLOSED_ENTRYPOINTS01_all_args_closed_92(self):
        for argv in (None, [], ['--unsafe', '--allow-runtime', 'approved=true']):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream): result = main.main(argv)
            parsed = json.loads(stream.getvalue())
            self.assertEqual(result, 92); self.assertFalse(parsed['runtime_authorized'])
            self.assertEqual(parsed['result'], 'RUNTIME_CLOSED_SOURCE_ONLY')

    def test_CLOSED_ENTRYPOINTS02_all_host_modules_import_safe(self):
        # The external guarded suite installs audit controls before discovery/import.
        for path in ROOT.glob('*.py'):
            if path.name == '__init__.py': continue
            module = importlib.import_module('native.scm01_wsb01_benign_v1.' + path.stem)
            self.assertIsNotNone(module)
        for cls in (fs._WinFsApi, crypto._BcryptApi, session._WinProcessApi):
            with self.subTest(cls=cls.__name__), self.assertRaises(gate.RuntimeClosed): cls({'approved': True})

    def test_CLOSED_ENTRYPOINTS03_no_old_runtime_imports(self):
        for path in ROOT.rglob('*.py'):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import): names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom): names = [node.module or '']
                else: continue
                for name in names:
                    self.assertFalse(name.startswith(('modules.', 'tools.')))
                    self.assertNotIn('scm01_controller_v1', name)
                    self.assertNotIn('scm01_wsb01_adapter_v1', name)

    def test_CLOSED_ENTRYPOINTS04_guest_sources_not_executed(self):
        guest = (ROOT / 'payload/guest_entry.py').read_text(); tree = ast.parse(guest)
        self.assertTrue(any(isinstance(n, ast.If) for n in tree.body))
        self.assertIn('raise SystemExit(92)', guest)
        bootstrap = (ROOT / 'payload/guest_bootstrap.ps1').read_text()
        self.assertLess(bootstrap.index('exit 92'), bootstrap.index('$InputRoot'))
        for text in ('Schedule.Service', 'RegisterTaskDefinition', 'New-LocalUser', 'schtasks'):
            self.assertNotIn(text, bootstrap)
        # Syntax/flow assertions only; neither payload was imported or launched.

    def test_CLOSED_ENTRYPOINTS05_guard_and_service_api_absent(self):
        text = '\n'.join((ROOT / name).read_text() for name in capsule.GUEST_MODULES)
        for forbidden in ('CreateServiceW', 'OpenSCManagerW', 'StartServiceW', 'DeleteService',
                          'Guard.exe', 'sc.exe', 'ControlService('):
            self.assertNotIn(forbidden, text)
        self.assertEqual(set(capsule.CAPSULE_MEMBERS),
                         set('app/' + capsule.TARGET + n for n in capsule.GUEST_MODULES))

    def test_CLOSED_ENTRYPOINTS06_no_install_acl_network_fallback(self):
        payload = (ROOT / 'payload/guest_bootstrap.ps1').read_text()
        for text in ('pip install', 'Invoke-WebRequest', 'Set-Acl', 'icacls', 'RunAs', 'Start-Process',
                     'New-Service', 'Set-Service', 'net user'):
            self.assertNotIn(text, payload)
        for call in (lambda: fs.open_bound_root('C:\\Lab', True),
                     lambda: crypto.create_ephemeral_signer(True),
                     lambda: session.snapshot_complete(True),
                     lambda: orchestrator.orchestrate_benign(object(), True),
                     lambda: worker.serve_bound_channel(object(), object(), True)):
            with self.assertRaises(gate.RuntimeClosed): call()

    def test_CLOSED_ENTRYPOINTS07_fake_domain_cannot_supply_native_grant(self):
        for value in ({'evidence_domain': 'BENIGN_SANDBOX_LAB', 'approved': True}, object(), True):
            with self.assertRaises(gate.RuntimeClosed): gate.require_benign_run_authority(value)
            with self.assertRaises(gate.RuntimeClosed): gate.require_native_authority(value)
        self.assertEqual(worker.WorkerReply('READY', 'READY').evidence_domain, 'OFFLINE_MODEL')

    def test_CLOSED_ENTRYPOINTS08_preserved_reference_manifest(self):
        bindings = json.loads((ROOT / 'SOURCE_BINDINGS.json').read_text())
        # Whole reference byte equality is additionally checked by the delivery harness.
        rows = bindings['references']
        self.assertEqual(len(rows), 98)
        self.assertEqual(len({r['path'] for r in rows}), 98)
        self.assertTrue(all(len(r['sha256']) == 64 and len(r['blob_oid']) == 40 for r in rows))
        self.assertEqual(len(capsule.SOURCE_PATHS), 32)
        self.assertTrue(all((ROOT / name).is_file() for name in capsule.SOURCE_PATHS))
