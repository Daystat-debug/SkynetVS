"""Isolated tests: never import or execute SkynetVS application/source or suggested diffs."""
from __future__ import annotations
import unittest, json, hashlib, sys, importlib.util, copy
from pathlib import Path
from zipfile import ZipFile

_HERE = Path(__file__).resolve().parents[1]
ROOT = _HERE/'source' if (_HERE/'source').exists() else _HERE
MODULE = ROOT/'modules/developer_task_ui/app/symbol_behavior_plan.py'
spec=importlib.util.spec_from_file_location('m155_plan', MODULE)
plan=importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)


def fixture():
    """Owned synthetic report with only the schema fields read by the planner."""
    return {"schema": "SKYNETVS_CORE_CANDIDATE_REVIEW_V1", "status": "STRUCTURAL_REVIEW_COMPLETE",
            "structural_only": True, "no_patch_or_apply": True, "source_code_executed": False,
            "changed_code_executed": False, "installation_authorized": False,
            "behavior": "NOT_TESTED", "selected": {"mapping":"UNIQUE_QUALNAME", "ast_changed": True,
                "before":{"qualname":"normalize"}, "components_changed":{"body":True,"signature":False,"kind":False}},
            "file_comparison":{"outside_selected_ast_changed":False,"outside_selected_text_changed":False,
                               "module_level_ast_changed":False},
            "historical_references":{"incoming": [{"caller":{"qualname":"caller","path":"modules/sample.py"},
                "call_site":{"line":8}}], "runtime_calls_proven":False,"callers_reanalyzed_against_candidate":False},
            "coverage":{"partial":False}, "definition_changes": [],
            "base_commit":"a"*40,"context_sha256":"c"*64,"response_sha256":"d"*64,
            "request_id":"req:synthetic:test", "request_fingerprint":"f"*64,
            "target_path":"modules/sample.py"}

class PlanTests(unittest.TestCase):
    def test_01_selected_changed_requires_oracle(self):
        r=plan.make_behavior_plan(fixture())
        self.assertEqual(r['disposition'],'TEST_ORACLE_REQUIRED')
        self.assertEqual([x['kind'] for x in r['test_obligations']],
                         ['SELECTED_FUNCTION_BEHAVIOR','HISTORICAL_CALLSITE_REGRESSION'])
        self.assertFalse(r['tests_executed'])
        self.assertTrue(all(x['expected_result'] is None for x in r['test_obligations']))
    def test_02_selected_unchanged_outside_change(self):
        s=fixture();s['selected']['ast_changed']=False
        s['file_comparison']['outside_selected_ast_changed']=True
        s['definition_changes']=[{"qualname":"_directory","relation_to_selected":"OTHER","status":"CHANGED"}]
        r=plan.make_behavior_plan(s)
        self.assertEqual(r['disposition'],'HUMAN_SCOPE_AND_INTENT_REVIEW_REQUIRED')
        self.assertEqual([x['code'] for x in r['hypotheses']],['H_SELECTED_UNCHANGED','H_SCOPE_DRIFT'])
        self.assertIn('_directory',plan.format_behavior_plan(r))
    def test_03_ambiguity_does_not_claim_mapping(self):
        s=fixture();s['selected'].update(mapping='AMBIGUOUS_DEFINITIONS',ast_changed=None)
        self.assertEqual(plan.make_behavior_plan(s)['disposition'],'INSUFFICIENT_STATIC_EVIDENCE')
    def test_04_partial_coverage(self):
        s=fixture();s['coverage']['partial']=True
        r=plan.make_behavior_plan(s)
        self.assertTrue(r['coverage']['partial'])
        self.assertEqual(r['disposition'],'INSUFFICIENT_STATIC_EVIDENCE')
    def test_05_change_signature_adds_compatibility_check(self):
        s=fixture();s['selected']['components_changed']['signature']=True
        kinds=[x['kind'] for x in plan.make_behavior_plan(s)['test_obligations']]
        self.assertIn('CALL_INTERFACE_COMPATIBILITY',kinds)
    def test_06_module_level_change(self):
        s=fixture();s['file_comparison']['module_level_ast_changed']=True
        self.assertIn('MODULE_IMPORT_REGRESSION',[x['kind'] for x in plan.make_behavior_plan(s)['test_obligations']])
    def test_07_dedupe_exact_callsite_not_distinct_lines(self):
        s=fixture();s['historical_references']['incoming']*=2
        r=plan.make_behavior_plan(s)
        self.assertEqual(r['coverage']['historical_incoming_observed'],1)
    def test_08_bounded_result_honestly_truncated(self):
        s=fixture();s['definition_changes']=[{"qualname":f"f_{i}","relation_to_selected":"OTHER","status":"CHANGED"} for i in range(50)]
        r=plan.make_behavior_plan(s)
        self.assertEqual(len(r['test_obligations']),plan.MAX_CASES)
        self.assertTrue(r['coverage']['partial'] and r['coverage']['truncated'])
    def test_09_reject_unauthorized_or_executed(self):
        for k,v in [('installation_authorized',True),('changed_code_executed',True),('behavior','PASS')]:
            s=fixture();s[k]=v
            with self.subTest(k=k),self.assertRaises(plan.BehaviorPlanError):plan.make_behavior_plan(s)
    def test_10_refuse_malformed_or_traversal(self):
        for key,value in [('target_path','../data/secret.py'),('response_sha256','x'*64),('request_id',None)]:
            s=fixture();s[key]=value
            with self.subTest(key=key),self.assertRaises(plan.BehaviorPlanError):plan.make_behavior_plan(s)
    def test_11_no_source_or_user_text_propagation(self):
        s=fixture();s['secret_text']='PRIVATE_SKYNETVS_MESSAGE_NOT_FOR_EXPORT'
        raw=json.dumps(plan.make_behavior_plan(s),ensure_ascii=False)
        self.assertNotIn('PRIVATE_SKYNETVS_MESSAGE_NOT_FOR_EXPORT',raw)
        self.assertNotIn('secret_text',raw)
    def test_12_result_byte_deterministic(self):
        s=fixture()
        self.assertEqual(plan._canon(plan.make_behavior_plan(s)),plan._canon(plan.make_behavior_plan(copy.deepcopy(s))))
    def test_13_main_py_is_allowed(self):
        s=fixture();s['target_path']='main.py';s['historical_references']['incoming'][0]['caller']['path']='main.py'
        self.assertEqual(plan.make_behavior_plan(s)['target_path'],'main.py')
    def test_14_missing_caller_rows_not_proof_of_no_callers(self):
        s=fixture();s['historical_references']['incoming']=[]
        r=plan.make_behavior_plan(s)
        self.assertFalse(r['historical_callers_proven_at_runtime'])
    def test_15_reject_malformed_caller_line(self):
        s=fixture();s['historical_references']['incoming'][0]['call_site']['line']='9'
        with self.assertRaises(plan.BehaviorPlanError):plan.make_behavior_plan(s)
    def test_16_source_does_not_use_unsafe_runtime(self):
        import ast
        tree=ast.parse(MODULE.read_text('utf-8'))
        imports=[n.module for n in tree.body if isinstance(n,ast.ImportFrom)] + [a.name for n in tree.body if isinstance(n,ast.Import) for a in n.names]
        self.assertFalse(set(imports)&{'os','subprocess','requests','socket','pickle','torch','exec'})
    def test_17_readonly_original_vs_mutated_preview(self):
        s=fixture();old=copy.deepcopy(s)
        plan.make_behavior_plan(s)
        self.assertEqual(s,old)

if __name__=='__main__':unittest.main(verbosity=2)
