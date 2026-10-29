"""AST-extracted headless UI tests; no Tk window or application imports."""
from __future__ import annotations
import ast, contextlib, hashlib, importlib.util, json, tempfile, types, unittest
from pathlib import Path
from unittest.mock import Mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from eval_core_behavior_plan import fixture, plan
_HERE=Path(__file__).resolve().parents[1]
ROOT=_HERE/'source' if (_HERE/'source').exists() else _HERE
UI=ROOT/'modules/developer_task_ui/app/ui.py'

class Widget:
    def __init__(self):self.value='';self.tags=[]
    def set(self,v):self.value=v
    def get(self):return self.value
    def configure(self,**kw): pass
    def delete(self,*a):self.value=''
    def insert(self,*a):self.value=a[-1]
    def tag_add(self,*a):self.tags.append(a)

class Store:
    def __init__(self,root, fail=None):self.root=root;self.fail=fail
    def write(self,folder,name,data):
        if self.fail==name:raise OSError('synthetic_failure')
        p=folder/name
        with p.open('xb') as f:f.write(data)

def json_bytes(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')
def read_plain(p,limit):
    data=p.read_bytes()
    if len(data)>limit:raise ValueError('too_large')
    return data

selected={'_clear_core_candidate_review','_review_core_candidate','_save_core_behavior_plan','_show_static_preview','_check_cached_receipts'}
def load_class():
    tree=ast.parse(UI.read_text('utf8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DeveloperWindow')
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in selected]
    if len(methods)!=len(selected):raise RuntimeError('missing expected methods')
    newcls=ast.ClassDef(name='Window',bases=[],keywords=[],body=methods,decorator_list=[])
    mod=ast.fix_missing_locations(ast.Module(body=[newcls],type_ignores=[]))
    ns={'CandidateReviewError':type('CandidateReviewError',(ValueError,),{}),
        'review_candidate':lambda **kwargs: fixture(),
        'format_candidate_review':lambda report:'Core: структурная проверка кандидата\n',
        'make_behavior_plan':plan.make_behavior_plan,
        'format_behavior_plan':plan.format_behavior_plan,
        'json_bytes':json_bytes,'read_plain':read_plain,'hashlib':hashlib}
    exec(compile(mod,str(UI),'exec'),ns)
    return ns['Window']

Window=load_class()

def window(temp, *, fail=None, report=None):
    w=Window()
    root=Path(temp)
    w.store=Store(root,fail)
    w.static_folder=root/'static';w.static_folder.mkdir()
    w.core_request_context=b'only_test_bound_context'
    w.core_request_context_sha256=hashlib.sha256(w.core_request_context).hexdigest()
    w.imported_session=False
    w.request=types.SimpleNamespace(request_id='req:synthetic:test')
    w.source=object();w.accepted_response_bytes=b'{"test":"payload"}'
    w.review={'patch_text':'diff --git a/x b/x\n-old\n+new\n'}
    w.static_preview={'preview_status':'TEXT_APPLICABLE_AST_PASS_NOT_EXECUTABLE_CHECKS',
                      'text_applicability':'EXACT_BYTE_IN_MEMORY_PASS','python_ast_parse':'PASS',
                      'message':'synthetic preview text'}
    w.static_input_sha256='0'*64
    w.events=[];w.status=Widget();w.static_summary=Widget();w.patch=Widget()
    w.set_text=lambda widget,text:widget.set(text)
    w.event=lambda name,**fields:w.events.append({'event':name,**fields})
    w._clear_core_candidate_review()
    return w

class UITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.w=window(self.temp.name)
    def save(self):
        self.w._review_core_candidate(self.w.static_preview,self.w.static_folder)
    def test_ui01_save_produces_both_reports(self):
        self.save()
        self.assertEqual(self.w.core_candidate_state,'SAVED')
        self.assertEqual(self.w.core_behavior_state,'SAVED')
        self.assertEqual(len(list(self.w.static_folder.iterdir())),4)
        self.assertEqual(json_bytes(self.w.core_behavior_plan),(self.w.static_folder/'Core_BehaviorPlan.json').read_bytes())
    def test_ui02_output_precedes_diff(self):
        self.save();self.w._show_static_preview()
        text=self.w.patch.get()
        self.assertIn('Core: гипотезы',text)
        self.assertIn('структурная проверка',text)
        self.assertTrue(text.endswith('diff --git a/x b/x\n-old\n+new\n'))
    def test_ui03_rejected_preview_writes_nothing(self):
        self.w.static_preview['python_ast_parse']='FAILED'
        self.save()
        self.assertNotEqual(self.w.core_behavior_state,'SAVED')
        self.assertEqual(list(self.w.static_folder.iterdir()),[])
    def test_ui04_plan_save_failure_retains_core_receipt(self):
        self.w.store.fail='Core_BehaviorPlan.json'
        self.save()
        self.assertEqual(self.w.core_candidate_state,'SAVED')
        self.assertEqual(self.w.core_behavior_state,'FAILED')
        self.assertTrue((self.w.static_folder/'Core_CandidateReview.json').is_file())
        self.assertNotIn('CORE_BEHAVIOR_PLAN_SAVED',[e['event'] for e in self.w.events])
    def test_ui05_tampered_plan_does_not_upgrade_to_pass(self):
        self.save()
        (self.w.static_folder/'Core_BehaviorPlan.json').write_bytes(b'{}')
        (self.w.static_folder/'DTR_PatchStaticPreview.json').write_bytes(json_bytes(self.w.static_preview))
        self.w._check_cached_receipts()
        self.assertEqual(self.w.core_behavior_state,'FAILED')
        self.assertEqual(self.w.core_candidate_state,'SAVED')
    def test_ui06_clean_cached_receipts(self):
        self.save()
        (self.w.static_folder/'DTR_PatchStaticPreview.json').write_bytes(json_bytes(self.w.static_preview))
        self.w._check_cached_receipts()
        self.assertEqual(self.w.core_behavior_state,'SAVED')
    def test_ui07_reset_clears_previous_reports(self):
        self.save();self.w._clear_core_candidate_review()
        self.assertIsNone(self.w.core_behavior_plan)
        self.assertEqual(self.w.core_behavior_text,'')
        self.assertEqual(self.w.core_behavior_state,'NOT_CHECKED')
    def test_ui08_unbound_core_never_proposes_tests(self):
        self.w.core_request_context=self.w.core_request_context_sha256=None
        self.save()
        self.assertEqual(self.w.core_candidate_state,'UNBOUND')
        self.assertEqual(list(self.w.static_folder.iterdir()),[])
    def test_ui09_core_receipt_write_failure_never_claims_plan(self):
        self.w.store.fail='Core_CandidateReview.json'
        self.save()
        self.assertEqual(self.w.core_candidate_state,'SAVE_FAILED')
        self.assertNotEqual(self.w.core_behavior_state,'SAVED')
    def test_ui10_plan_txt_write_failure_partial_not_complete(self):
        self.w.store.fail='Core_BehaviorPlan.txt'
        self.save()
        self.assertEqual(self.w.core_behavior_state,'FAILED')
        self.assertFalse((self.w.static_folder/'Core_BehaviorPlan.txt').exists())

if __name__=='__main__':unittest.main(verbosity=2)
