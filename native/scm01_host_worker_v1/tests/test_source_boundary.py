import ast
import contextlib
import dataclasses
import io
import json
from pathlib import Path
import sys
import unittest
from native.scm01_host_worker_v1 import host_worker_entry
from native.scm01_host_worker_v1.contract import Plan, ContractError, TOTAL_NS, CLEANUP_NS
from native.scm01_host_worker_v1.lifecycle import Lifecycle, ORDER
from .test_contract_and_lifecycle import fixture, run_until, data_for


class SourceBoundaryTests(unittest.TestCase):
    def test_entrypoint_always_closed(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = host_worker_entry.main()
        self.assertEqual(code, 92)
        value = json.loads(output.getvalue())
        self.assertEqual(value['result'], 'HOST_WORKER_EXECUTION_CLOSED')
        self.assertIs(value['native_admission'], False)
        self.assertIs(value['runtime_authorized'], False)

    def test_candidate_no_native_or_process_imports(self):
        root = Path(host_worker_entry.__file__).parent
        banned = {'ctypes', 'subprocess', 'socket', 'multiprocessing', 'threading',
                  'pickle', 'marshal', 'importlib', 'os'}
        # The pure Contract V1 slice stays pure; new native modules have separate boundary tests.
        for name in ('__init__.py', 'contract.py', 'protocol.py', 'lifecycle.py'):
            source = root / name
            tree = ast.parse(source.read_bytes(), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name.split('.')[0], banned)
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or '').split('.')[0], banned)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, ('exec', 'eval', 'compile', '__import__', 'open'))

    def test_new_code_has_no_old_ben01_import(self):
        root = Path(host_worker_entry.__file__).parent
        for source in root.glob('*.py'):
            text = source.read_text(encoding='utf-8')
            self.assertNotIn('from native.scm01_wsb01_benign_v1', text)
            self.assertNotIn('import native.scm01_wsb01_benign_v1', text)
        self.assertFalse(any(n.startswith('native.scm01_wsb01_benign_v1') for n in sys.modules))

    def test_frozen_data_not_issuer(self):
        plan,_,_=fixture()
        with self.assertRaises(dataclasses.FrozenInstanceError): plan.run_id='f'*32
        self.assertFalse(hasattr(plan, 'permit'))
        self.assertFalse(hasattr(plan, 'claim'))

    def test_every_failure_point_cannot_resume(self):
        for event in ORDER:
            life,_ = run_until(event)
            life.fail('injected_port_failure', 100)
            with self.subTest(event=event):
                with self.assertRaises(ContractError):life.observe(event,101,{})
                self.assertEqual(life.first_error,'injected_port_failure')
                self.assertFalse(life.report()['runtime_authorized'])

    def test_total_deadline_not_extended(self):
        plan,supervisor,child=fixture()
        life=Lifecycle(plan,supervisor,0)
        data=data_for(plan,child)
        for index,event in enumerate(ORDER):
            if event == 'RESUME_INTENT': break
            life.observe(event,TOTAL_NS-100+index,data[event])
        life.observe('RESUME_INTENT',TOTAL_NS-10,{})
        self.assertEqual(life.step_deadline_ns,TOTAL_NS)
        with self.assertRaisesRegex(ContractError,'deadline_expired'):life.tick(TOTAL_NS)

    def test_source_syntax_python312(self):
        root=Path(host_worker_entry.__file__).parent
        for source in root.glob('*.py'):
            ast.parse(source.read_bytes(),filename=str(source),feature_version=(3,12))

    def test_no_ctypes_loaded(self):
        self.assertNotIn('ctypes',sys.modules)
        self.assertNotIn('_ctypes',sys.modules)
