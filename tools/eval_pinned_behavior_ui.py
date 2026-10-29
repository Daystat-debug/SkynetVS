"""M157 headless UI checks, AST-extract only; never creates Tk window or imports runtime."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'modules/developer_task_ui/app/ui.py'
selected={'import_pinned_behavior_evidence'}

class Slot:
    def __init__(self):self.text=''
    def set(self,v):self.text=v

class Store:
    def __init__(self,root,fail=''):
        self.root=root;self.fail=fail
    def _folder(self,prefix):
        p=self.root/(prefix+'test');p.mkdir(exist_ok=False);return p
    def write(self,folder,name,raw):
        if self.fail==name:raise OSError('deliberate_test_failure')
        with (folder/name).open('xb') as f:f.write(raw)

def json_bytes(r):return (json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def read_plain(path,limit):
    b=path.read_bytes()
    if len(b)>limit:raise ValueError('too large')
    return b


def class_factory():
    tree=ast.parse(UI.read_text('utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DeveloperWindow')
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in selected]
    if len(methods)!=len(selected):raise RuntimeError('M157_UI_METHOD_MISSING')
    new=ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Window',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[]))
    ns={'Path':Path,'filedialog':types.SimpleNamespace(askopenfilename=lambda **k:None),
        'reconcile_pinned_bundle':lambda raw:{'base_commit':'c'*40,'m155_plan_sha256':'d'*64,
                                              'schema':'TEST','status':'PINNED_PILOT_EVIDENCE_CORRELATED'},
        'format_pinned_evidence':lambda r:'Only accepted evidence, not permission.',
        'read_plain':read_plain, 'json_bytes':json_bytes}
    exec(compile(new,str(UI),'exec'),ns)
    return ns['Window'],ns

class UiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.file=self.root/'pilot.zip';self.file.write_bytes(b'fake pilot bytes')
        self.cls,self.env=class_factory();self.w=self.cls()
        self.env['filedialog'].askopenfilename=lambda **kw:str(self.file)
        self.w.root=object();self.w.ai_busy=False
        self.w.ai_info=Slot();self.w.ai_text=Slot()
        self.w.ai_tab=object();self.w.tabs=types.SimpleNamespace(select=lambda tab:None)
        self.w.events=[]
        self.w.event=lambda name,**kw:self.w.events.append(dict(event=name,**kw))
        self.w.set_text=lambda widget,value: widget.set(value)
        self.w.store=Store(self.root)
        self.w.ai_pilot_evidence=None
        self.w.fail=lambda exc:self.w.events.append({'event':'ERROR','message':str(exc)})
    def test_01_success(self):
        result=self.w.import_pinned_behavior_evidence()
        self.assertEqual(result['status'],'PINNED_PILOT_EVIDENCE_CORRELATED')
        self.assertEqual(len(self.w.events),1)
        self.assertIn('SAVED',self.w.events[0]['event'])
        self.assertTrue((self.root/'behavior_evidence_test/Core_BehaviorEvidence.json').is_file())
        self.assertIn('Only accepted',self.w.ai_text.text)
    def test_02_cancel_nothing_written(self):
        self.env['filedialog'].askopenfilename=lambda **kw:''
        self.assertIsNone(self.w.import_pinned_behavior_evidence())
        self.assertEqual(self.w.events,[])
    def test_03_busy_refuses(self):
        self.w.ai_busy=True
        self.assertIsNone(self.w.import_pinned_behavior_evidence())
        self.assertEqual(self.w.events,[])
        self.assertIn('дождись',self.w.ai_info.text.lower())
    def test_04_invalid_evidence_refused(self):
        def fail(raw):raise ValueError('PIN_REFUSAL')
        self.env['reconcile_pinned_bundle']=fail
        self.assertIsNone(self.w.import_pinned_behavior_evidence())
        self.assertEqual(self.w.ai_pilot_evidence,None)
        self.assertTrue(any('NOT_ACCEPTED' in e['event'] for e in self.w.events))
    def test_05_json_save_fail_does_not_claim(self):
        self.w.store.fail='Core_BehaviorEvidence.json'
        self.assertIsNone(self.w.import_pinned_behavior_evidence())
        self.assertEqual(self.w.ai_pilot_evidence,None)
        self.assertNotIn('SAVED',[e['event'] for e in self.w.events])
    def test_06_txt_save_fail_does_not_claim(self):
        self.w.store.fail='Core_BehaviorEvidence.txt'
        self.assertIsNone(self.w.import_pinned_behavior_evidence())
        self.assertEqual(self.w.ai_pilot_evidence,None)
        self.assertFalse((self.root/'behavior_evidence_test/Core_BehaviorEvidence.txt').exists())
    def test_07_oversize_refused(self):
        self.file.write_bytes(b'x'*(128*1024+1))
        self.assertIsNone(self.w.import_pinned_behavior_evidence())
        self.assertEqual(self.w.ai_pilot_evidence,None)
    def test_08_no_dtr_apply_methods_called(self):
        tree=ast.parse(UI.read_text('utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DeveloperWindow')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='import_pinned_behavior_evidence')
        calls=[n.func.id for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        for dangerous in ['apply_approved','git','subprocess','exec','eval','open']:
            self.assertNotIn(dangerous,calls)
    def test_09_no_existing_plan_state_upgraded(self):
        self.w.core_behavior_plan={'status':'HYPOTHESES_AND_TEST_OBLIGATIONS_ONLY'}
        self.w.core_behavior_state='SAVED'
        self.w.import_pinned_behavior_evidence()
        self.assertEqual(self.w.core_behavior_state,'SAVED')
        self.assertEqual(self.w.core_behavior_plan['status'],'HYPOTHESES_AND_TEST_OBLIGATIONS_ONLY')
    def test_10_no_source_files_changed(self):
        digest=hashlib.sha256(UI.read_bytes()).hexdigest()
        self.w.import_pinned_behavior_evidence()
        self.assertEqual(hashlib.sha256(UI.read_bytes()).hexdigest(),digest)
    def test_11_acceptance_not_current_request(self):
        self.w.core_request_context_sha256='f'*64
        self.w.import_pinned_behavior_evidence()
        self.assertNotIn('DTR',self.w.events[0]['event'])
    def test_12_report_json_text_matches(self):
        self.w.import_pinned_behavior_evidence()
        data=json.loads((self.root/'behavior_evidence_test/Core_BehaviorEvidence.json').read_bytes())
        self.assertFalse(data.get('apply_authorized',False))
        self.assertIn('not permission',self.w.ai_text.text.lower())

if __name__=='__main__':unittest.main(verbosity=2)
