"""M157 synthetic, headless pinned-evidence acceptance tests; no project runtime.

Public repository tests contain no user's historic M155/M156 report bodies.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import unittest
import zipfile

HERE = Path(__file__).resolve().parents[1]
MODULE = HERE / 'modules/developer_task_ui/app/pinned_behavior_evidence.py'
spec = importlib.util.spec_from_file_location('m157_pinned_evidence', MODULE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def make_docs():
    plan = {
        'schema': 'SKYNETVS_CORE_BEHAVIOR_PLAN_V1',
        'status': 'HYPOTHESES_AND_TEST_OBLIGATIONS_ONLY',
        'base_commit': e.BASE_COMMIT, 'target_path': e.TARGET_PATH,
        'selected_qualname': 'normalize', 'response_sha256': e.DTR_RESPONSE_SHA256,
        'request_id': 'req:synthetic:pilot', 'request_fingerprint': 'f'*64,
        'candidate_selected_ast_changed': True,
        'changes_outside_selected': False,
        'tests_executed': False, 'behavior_proven': False,
        'apply_authorized': False, 'promotion_authorized': False,
        'test_obligations': [],
    }
    for ident in e.CASE_COUNTS:
        entry = {'case_id': ident, 'execution': 'NOT_RUN',
                 'expected_result': None, 'result': 'UNKNOWN',
                 'target': 'normalize' if ident == 'T001' else e.CALLSITE_LINES[ident][0]}
        if ident in e.CALLSITE_LINES:
            entry['historical_reference'] = {
                'line': e.CALLSITE_LINES[ident][1], 'commit': e.BASE_COMMIT,
                'path': e.TARGET_PATH, 'runtime_call_proven': False,
            }
        plan['test_obligations'].append(entry)
    fixed = {
        'schema': 'SKYNETVS_M156_BOUNDED_BEHAVIOR_EVIDENCE_V1',
        'status': 'PILOT_FIXED_PAIR_BEHAVIOR_PASS',
        'base_commit': e.BASE_COMMIT, 'target_path': e.TARGET_PATH,
        'scope': 'EXACT_PINNED_NORMALIZE_PAIR_ONLY',
        'sha256': {
            'source_sha256': e.SOURCE_SHA256, 'candidate_sha256': e.CANDIDATE_SHA256,
            'response_sha256': e.DTR_RESPONSE_SHA256, 'plan_sha256': 'TO_BE_SET',
        },
        'git_writes': 0, 'patch_applied': False,
        'promotion_authorized': False,
        'general_behavior_equivalence_proven': False,
        'independent_oracle': {
            'fixture_count': 28, 'passed': 28, 'failed': 0,
            'expected_values_authored_separately': True,
            'cases': [{'case_id':f'case_{i}', 'passed':True, 'original':str(i),
                       'candidate':str(i), 'expected':str(i)} for i in range(28)],
        },
        'm155_obligations': [{'case_id':'T001','fixtures':28,'status':'FIXED_PAIR_CASE_MATRIX_PASS'}] +
             [{'case_id':cid, 'status':'NOT_RUN'} for cid in ('T002','T003','T004')],
    }
    cases = []
    obligations = {}
    for cid in ('T002','T003','T004'):
        target = e.CALLSITE_LINES[cid][0].split('.')[-1] + ':' + str(e.CALLSITE_LINES[cid][1])
        obligations[cid] = {'cases':e.CASE_COUNTS[cid], 'passed':e.CASE_COUNTS[cid],
                            'target_callsite':target}
        for i in range(e.CASE_COUNTS[cid]):
            cases.append({'case_id':f'{cid}_synthetic_{i}', 'obligation':cid,
                          'expected':{'value':i}, 'min_callsite_hits':1,
                          'original':{'result':{'value':i},'target_callsite_hits':1,
                                      'matched_independent_oracle':True},
                          'candidate':{'result':{'value':i},'target_callsite_hits':1,
                                       'matched_independent_oracle':True}, 'passed':True})
    calls = {
        'schema':'SKYNETVS_M156_CALLSITE_BEHAVIOR_EVIDENCE_V1',
        'status':'FIXED_CALLSITE_CASES_PASS','base_commit':e.BASE_COMMIT,
        'target_path':e.TARGET_PATH,'source_sha256':e.SOURCE_SHA256,
        'candidate_sha256':e.CANDIDATE_SHA256,
        'dtr_response_sha256':e.DTR_RESPONSE_SHA256,
        'm155_plan_sha256':'TO_BE_SET',
        'count_total':13,'count_passed':13,'count_failed':0,
        'independent_expected_results_defined_before_execution':True,
        'execution':{
            'production_source_writes':0,'git_write_commands':0,'patch_applied':False,
            'approval_or_promotion_authorized':False,
            'user_training_or_inbox_read':False,'whole_module_imported':False,
        },
        'm155_obligations':obligations,'cases':cases,
    }
    return {'Core_BehaviorPlan.json':plan,'M156_Behavior_Result.json':fixed,
            'M156_Callsite_Result.json':calls}


def encode(doc):
    return (json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False)+'\n').encode('utf-8')


def synthetic_bundle(changes=None):
    docs = make_docs()
    if changes:
        changes(docs)
    raws = {k:encode(v) for k,v in docs.items()}
    plan_sha = hashlib.sha256(raws['Core_BehaviorPlan.json']).hexdigest()
    docs['M156_Behavior_Result.json']['sha256']['plan_sha256'] = plan_sha
    docs['M156_Callsite_Result.json']['m155_plan_sha256'] = plan_sha
    raws = {k:encode(v) for k,v in docs.items()}
    expected = {k:(hashlib.sha256(v).hexdigest(),len(v)) for k,v in raws.items()}
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in raws.items():z.writestr(name,data)
    return result.getvalue(), expected


class EvidenceTests(unittest.TestCase):
    def check(self, mutator=None, *, code=None):
        raw, pins = synthetic_bundle(mutator)
        saved=e.EXPECTED
        e.EXPECTED=pins
        try:
            if code is None:
                result=e.reconcile_pinned_bundle(raw)
                self.assertEqual(result['reported_cases_passed'],41)
                self.assertEqual(result['status'],'PINNED_PILOT_EVIDENCE_CORRELATED')
                self.assertFalse(result['actual_execution_independently_attested'])
                self.assertFalse(result['apply_authorized'])
                return result
            with self.assertRaises(e.EvidenceRefused) as ctx:
                e.reconcile_pinned_bundle(raw)
            self.assertEqual(ctx.exception.code,code)
        finally:e.EXPECTED=saved

    def test_01_synthetic_good(self):self.check()
    def test_02_text_marks_not_attestation(self):
        result=self.check();s=e.format_pinned_evidence(result)
        self.assertIn('41/41',s);self.assertIn('НЕ РАЗРЕШЕНЫ',s)
    def test_03_reject_incorrect_commit(self):
        self.check(lambda d:d['Core_BehaviorPlan.json'].update(base_commit='0'*40),code='M157_PLAN_BINDING_MISMATCH')
    def test_04_reject_other_request(self):
        self.check(lambda d:d['Core_BehaviorPlan.json'].update(response_sha256='0'*64),code='M157_PLAN_BINDING_MISMATCH')
    def test_05_reject_changed_other_function(self):
        self.check(lambda d:d['Core_BehaviorPlan.json'].update(changes_outside_selected=True),code='M157_PLAN_BINDING_MISMATCH')
    def test_06_reject_plan_fake_pass(self):
        self.check(lambda d:d['Core_BehaviorPlan.json']['test_obligations'][0].update(execution='PASS'),code='M157_PLAN_FALSE_EXECUTION')
    def test_07_reject_callsite_wrong_line(self):
        self.check(lambda d:d['Core_BehaviorPlan.json']['test_obligations'][1]['historical_reference'].update(line=99),code='M157_PLAN_CALLSITE_BINDING_MISMATCH')
    def test_08_reject_changed_candidate(self):
        self.check(lambda d:d['M156_Behavior_Result.json']['sha256'].update(candidate_sha256='0'*64),code='M157_FIXED_BINDING_MISMATCH')
    def test_09_reject_false_fixed_expected(self):
        self.check(lambda d:d['M156_Behavior_Result.json']['independent_oracle']['cases'][0].update(expected='wrong'),code='M157_FIXED_CASE_FAILURE')
    def test_10_reject_duplicate_fixed_case(self):
        self.check(lambda d:d['M156_Behavior_Result.json']['independent_oracle']['cases'][1].update(case_id='case_0'),code='M157_FIXED_CASE_FAILURE')
    def test_11_reject_claim_of_general_proof(self):
        self.check(lambda d:d['M156_Behavior_Result.json'].update(general_behavior_equivalence_proven=True),code='M157_FIXED_BINDING_MISMATCH')
    def test_12_reject_callsite_not_hit(self):
        self.check(lambda d:d['M156_Callsite_Result.json']['cases'][0]['candidate'].update(target_callsite_hits=0),code='M157_CALLS_CASE_FAILED_T002')
    def test_13_reject_different_oracle(self):
        self.check(lambda d:d['M156_Callsite_Result.json']['cases'][1]['candidate'].update(result={'value':'wrong'}),code='M157_CALLS_CASE_FAILED_T002')
    def test_14_reject_false_user_data_read(self):
        self.check(lambda d:d['M156_Callsite_Result.json']['execution'].update(user_training_or_inbox_read=True),code='M157_CALLS_EXECUTION_BOUNDARY_MISMATCH')
    def test_15_reject_missing_case(self):
        self.check(lambda d:d['M156_Callsite_Result.json']['cases'].pop(),code='M157_CALLS_CASE_SET_INVALID')
    def test_16_reject_tampered_member_hash(self):
        raw,pins=synthetic_bundle();e0=e.EXPECTED;e.EXPECTED=pins
        try:
            payload=io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(raw)) as src, zipfile.ZipFile(payload,'w',zipfile.ZIP_DEFLATED) as out:
                for name in pins:
                    data=src.read(name)
                    if name=='M156_Callsite_Result.json':
                        data=data.replace(b'T002_synthetic_0',b'T002_synthetic_9',1)
                    out.writestr(name,data)
            with self.assertRaisesRegex(e.EvidenceRefused,'M157_EVIDENCE_HASH_MISMATCH'):
                e.reconcile_pinned_bundle(payload.getvalue())
        finally:e.EXPECTED=e0
    def test_17_reject_duplicate_member(self):
        raw,pins=synthetic_bundle();z=io.BytesIO()
        with zipfile.ZipFile(z,'w') as f:
            for k in pins:f.writestr(k,b'{}')
            f.writestr('Core_BehaviorPlan.json',b'{}')
        with self.assertRaisesRegex(e.EvidenceRefused,'M157_ZIP_ENTRY_COUNT'):
            e.reconcile_pinned_bundle(z.getvalue())
    def test_18_reject_zip_traversal(self):
        z=io.BytesIO()
        with zipfile.ZipFile(z,'w') as f:
            for k in ('../Core_BehaviorPlan.json','M156_Behavior_Result.json','M156_Callsite_Result.json'):
                f.writestr(k,b'{}')
        with self.assertRaisesRegex(e.EvidenceRefused,'M157_ZIP_ENTRY_SET'):
            e.reconcile_pinned_bundle(z.getvalue())
    def test_19_reject_extra_member(self):
        raw,pins=synthetic_bundle();z=io.BytesIO()
        with zipfile.ZipFile(z,'w') as f:
            for k in pins:f.writestr(k,b'{}')
            f.writestr('evil.py',b'pass')
        with self.assertRaisesRegex(e.EvidenceRefused,'M157_ZIP_ENTRY_COUNT'):
            e.reconcile_pinned_bundle(z.getvalue())
    def test_20_reject_non_zip(self):
        with self.assertRaisesRegex(e.EvidenceRefused,'M157_ZIP_READ_REFUSED'):
            e.reconcile_pinned_bundle(b'not a zip')
    def test_21_reject_oversize(self):
        with self.assertRaisesRegex(e.EvidenceRefused,'M157_ZIP_SIZE_OR_TYPE'):
            e.reconcile_pinned_bundle(b'0'*(128*1024+1))
    def test_22_missing_receipt_status(self):
        with self.assertRaises(e.EvidenceRefused):e.format_pinned_evidence({})
    def test_23_no_sensitive_ops_imported(self):
        import ast
        tree=ast.parse(MODULE.read_text('utf-8'))
        imports=[n.module for n in tree.body if isinstance(n,ast.ImportFrom)]+[
            a.name for n in tree.body if isinstance(n,ast.Import) for a in n.names]
        self.assertFalse(set(imports) & {'os','subprocess','requests','socket','pickle','torch'})
        self.assertNotIn('exec(',MODULE.read_text('utf-8'))
    def test_24_refuse_duplicate_json_key(self):
        with self.assertRaisesRegex(e.EvidenceRefused,'M157_JSON_DUPLICATE_KEY'):
            e._json(b'{"x":1,"x":2}')
    def test_25_refuse_nan(self):
        with self.assertRaisesRegex(e.EvidenceRefused,'M157_JSON_NONFINITE'):
            e._json(b'{"x":NaN}')
    def test_26_correctly_reject_missing_historical(self):
        self.check(lambda d:d['Core_BehaviorPlan.json']['test_obligations'][2].pop('historical_reference'),code='M157_PLAN_CALLSITE_BINDING_MISMATCH')
    def test_27_refuse_faked_success(self):
        self.check(lambda d:d['M156_Callsite_Result.json']['cases'][0].update(passed=False),code='M157_CALLS_CASE_FAILED_T002')
    def test_28_result_does_not_expose_case_inputs(self):
        raw,pins=synthetic_bundle();old=e.EXPECTED;e.EXPECTED=pins
        try:
            result=e.reconcile_pinned_bundle(raw)
            s=json.dumps(result,ensure_ascii=False)
            self.assertNotIn('case_0',s)
            self.assertNotIn('synthetic_',s)
        finally:e.EXPECTED=old

if __name__ == '__main__':unittest.main(verbosity=2)
