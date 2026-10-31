"""M159 UI integration checks without Tk display or project modifications."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT/'modules/developer_task_ui/app/ui.py'
SOURCE = ROOT/'modules/learning/feedback_analyzer.py'
sys.path.insert(0, str(ROOT/'modules/developer_task_ui'))
from app.feedback_meta_repair import TARGET,BASE_COMMIT,make_repair_proposal,format_repair_proposal


class Var:
    def __init__(self,value=None):self.value=value
    def set(self,v):self.value=v


class Store:
    def __init__(self,root):self.root=root;self.fail=None;self.created=[]
    def _folder(self,prefix):
        p=self.root/(prefix+str(len(self.created)+1));p.mkdir()
        self.created.append(p)
        return p
    def write(self,folder,name,data):
        if self.fail==name:raise OSError('test simulated write fail')
        (folder/name).write_bytes(data)


class FakeWindow:
    def __init__(self,root):
        self.ai_busy=False
        self.ai_info=Var()
        self.ai_text=object()
        self.ai_tab=object()
        self.tabs=types.SimpleNamespace(selected=None,select=lambda tab:None)
        self.repository=root
        self.store=Store(root)
        self.root=object()
        self.ai_bounded_repair=None
        self.events=[];self.displays=[];self.failures=[]
        self.request=object();self.core_request_context=b'previous_task';self.ai_apply_checked=None
    def set_text(self,w,t):self.displays.append(t)
    def event(self,n,**kw):self.events.append((n,kw))
    def fail(self,e):self.failures.append(str(e))


def read_method():
    tree=ast.parse(UI.read_text(encoding='utf-8'))
    w=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DeveloperWindow')
    m=next(n for n in w.body if isinstance(n,ast.FunctionDef) and n.name=='propose_feedback_meta_guard')
    return compile(ast.fix_missing_locations(ast.Module(body=[m],type_ignores=[])),str(UI),'exec')


class RepairUITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='m159_ui_')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.window=FakeWindow(self.root)
        content=SOURCE.read_bytes()
        assert hashlib.sha256(content).hexdigest()=='29105239ae6b61631cc9ef7b3cfb9f22e53c81657c26acfbbc72872eab200b87'
        self.source=types.SimpleNamespace(path=TARGET, content=content, base_commit=BASE_COMMIT,
                                          provenance={'kind':'OBSERVED_COMMITTED_FILE','current_git_head_observed':True})
        self.reader=mock.Mock()
        self.reader.return_value.capture.return_value=self.source
        self.ask=mock.Mock(return_value=True)
        self.namespace={'messagebox':types.SimpleNamespace(askyesno=self.ask),
                        'GitSourceReader':self.reader,
                        'find_git':lambda: 'git',
                        'REPAIR_TARGET':TARGET,
                        'make_repair_proposal':make_repair_proposal,
                        'format_repair_proposal':format_repair_proposal,
                        'json_bytes':lambda x:(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode(),
                        'Path':Path}
        exec(read_method(),self.namespace)
        self.action=self.namespace['propose_feedback_meta_guard']

    def invoke(self):return self.action(self.window)
    def test_button_command_exists_once(self):
        ui=UI.read_text(encoding='utf-8')
        self.assertEqual(ui.count('command=self.propose_feedback_meta_guard'),1)
        self.assertEqual(ui.count('from .feedback_meta_repair import'),1)
    def test_success_creates_three_distinct_artifacts(self):
        p=self.invoke();self.assertIsNotNone(p)
        files=sorted(x.name for x in self.window.store.created[0].iterdir())
        self.assertEqual(files,['Core_BoundedRepair.patch','Core_BoundedRepairProposal.json','Core_BoundedRepairProposal.txt'])
    def test_artifacts_linked_to_same_proposal(self):
        p=self.invoke();folder=self.window.store.created[0]
        self.assertEqual(json.loads((folder/'Core_BoundedRepairProposal.json').read_bytes()),p)
        self.assertEqual((folder/'Core_BoundedRepair.patch').read_bytes(),p['patch_text'].encode())
        self.assertEqual((folder/'Core_BoundedRepairProposal.txt').read_text(encoding='utf-8'),format_repair_proposal(p))
    def test_current_task_context_unchanged(self):
        old=self.window.request;self.invoke()
        self.assertIs(self.window.request,old)
        self.assertEqual(self.window.core_request_context,b'previous_task')
        self.assertIsNone(self.window.ai_apply_checked)
    def test_declined_input_never_reads_repo(self):
        self.ask.return_value=False
        self.assertIsNone(self.invoke());self.reader.assert_not_called()
        self.assertEqual(self.window.store.created,[])
    def test_busy_input_never_reads_repo(self):
        self.window.ai_busy=True
        self.assertIsNone(self.invoke());self.reader.assert_not_called()
        self.ask.assert_not_called()
    def test_git_capture_is_one_target(self):
        self.invoke()
        self.assertEqual(self.reader.return_value.capture.call_count,1)
        self.assertEqual(self.reader.return_value.capture.call_args.args[0],self.root/TARGET)
    def test_modified_source_fails_closed(self):
        self.source.content+=b'\n# edited\n'
        self.assertIsNone(self.invoke());self.assertTrue(self.window.failures)
        self.assertFalse(any(n=='M159_BOUNDED_REPAIR_SAVED' for n,_ in self.window.events))
    def test_wrong_head_fails_closed(self):
        self.source.base_commit='invalid sha'
        self.assertIsNone(self.invoke());self.assertEqual(len(self.window.store.created),0)
    def test_new_current_head_after_install_is_accepted(self):
        self.source.base_commit='b'*40
        result=self.invoke()
        self.assertEqual(result['base_commit'], 'b'*40)
        self.assertEqual(self.window.events[-1][0], 'M159_BOUNDED_REPAIR_SAVED')

    def test_single_write_failure_no_success_event(self):
        self.window.store.fail='Core_BoundedRepairProposal.txt'
        self.assertIsNone(self.invoke())
        self.assertIsNone(self.window.ai_bounded_repair)
        self.assertFalse(any(n=='M159_BOUNDED_REPAIR_SAVED' for n,_ in self.window.events))
    def test_missing_git_capture_no_success(self):
        self.reader.return_value.capture.side_effect=ValueError('M159 missing source')
        self.assertIsNone(self.invoke())
        self.assertEqual(self.window.store.created,[])
    def test_saved_event_never_grants_approval(self):
        p=self.invoke()
        self.assertEqual(self.window.events[-1][0],'M159_BOUNDED_REPAIR_SAVED')
        self.assertFalse(p['apply_authorized'])
        self.assertFalse(p['promotion_authorized'])
        self.assertIn('тесты ещё НЕ запущены',self.window.displays[-1])
    def test_static_guards_no_auto_apply(self):
        method=ast.parse(UI.read_text(encoding='utf-8')).body[2]
        # source-wise guard is no-op for actions, no model calls or self.apply...
        s=ast.get_source_segment(UI.read_text(encoding='utf-8'),next(n for n in ast.walk(ast.parse(UI.read_text(encoding='utf-8')))
                           if isinstance(n,ast.FunctionDef) and n.name=='propose_feedback_meta_guard'))
        for forbidden in ('apply_approved(', 'self.apply_own_proposal(', 'self.ai_apply_button.state(',
                          'subprocess.', 'os.system(', 'exec(', 'eval('):
            self.assertNotIn(forbidden,s)

if __name__=='__main__': unittest.main(verbosity=2)
