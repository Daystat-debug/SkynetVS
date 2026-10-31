"""M159 real bounded repair evaluation: synthetic fixtures + exact-source negatives."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'modules' / 'developer_task_ui'))
from app.feedback_meta_repair import (
    BASE_COMMIT, SOURCE_SHA256, TARGET, NEW_SNIPPET, OLD_SNIPPET,
    RepairRefused, make_repair_proposal, format_repair_proposal)

PINNED = ROOT / TARGET


def proposal():
    data = PINNED.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA256
    return make_repair_proposal(path=TARGET, content=data, base_commit=BASE_COMMIT,
                                provenance={'kind':'OBSERVED_COMMITTED_FILE',
                                            'current_git_head_observed': True})


def load_analyzer(src):
    namespace = {'__name__': 'm159_synthetic_feedback', '__file__': '<pinned_code>',
                 '__package__': None}
    exec(compile(src.decode('utf-8'), '<pinned_code>', 'exec'), namespace)
    return namespace['FeedbackAnalyzer']


class RepairProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = PINNED.read_bytes()
        cls.expected = proposal()
        cls.old = load_analyzer(cls.data)
        cls.new_bytes = cls.data.replace(OLD_SNIPPET.encode(), NEW_SNIPPET.encode(), 1)
        cls.new = load_analyzer(cls.new_bytes)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='m159_repair_case_')
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def run_case(self, analyzer, files):
        for name,rows in files.items():
            (self.dir/name).write_text(''.join(json.dumps(row,ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return analyzer(str(self.dir)).analyze(correction_limit=None)

    def good_pair(self):
        return [
            {'ts':'2026-01-01T00:00:00', 'accepted':False,'raw_text':'открой натпад',
             'meta':{'intent':'UNKNOWN','confidence':0.1, 'slots':{}}},
            {'ts':'2026-01-01T00:00:02','accepted':True,'raw_text':'открой блокнот',
             'meta':{'intent':'OPEN_APP','confidence':0.9,'slots':{'app':'notepad'}}},
        ]

    def test_proposal_is_deterministic(self):
        self.assertEqual(proposal(), self.expected)
    def test_status_is_proposal_only(self):
        p=self.expected
        self.assertEqual(p['generator'],'OWN_DETERMINISTIC_AST_RECIPE')
        self.assertFalse(p['tests_executed'])
        self.assertFalse(p['behavior_verified'])
        self.assertFalse(p['model_generated'])
        self.assertFalse(p['apply_authorized'])
        self.assertFalse(p['promotion_authorized'])
    def test_diff_roundtrip(self):
        # git apply --check in a synthetic repo, NOT in the user project.
        p=self.expected
        repo=self.dir
        target=repo/TARGET
        target.parent.mkdir(parents=True)
        target.write_bytes(self.data)
        subprocess.run(['git','init','-q',str(repo)],check=True,stdout=subprocess.PIPE)
        check=subprocess.run(['git','-C',str(repo),'apply','--check','--'],input=p['patch_text'].encode(),capture_output=True)
        self.assertEqual(check.returncode,0,check.stderr)
        ok=subprocess.run(['git','-C',str(repo),'apply','--'],input=p['patch_text'].encode(),capture_output=True)
        self.assertEqual(ok.returncode,0,ok.stderr)
        # Git on Windows with core.autocrlf=true may materialize the exact
        # applied candidate using CRLF; this is not a source-level deviation.
        # Accept ONLY the pinned LF candidate or its full CRLF representation.
        # Mixed line endings or altered bytes must still fail.
        got = target.read_bytes()
        allowed = (self.new_bytes, self.new_bytes.replace(b'\n', b'\r\n'))
        self.assertIn(got, allowed, 'GIT_APPLY_CHANGED_BEYOND_EXACT_EOL')
    def test_candidate_sha_is_exact(self):
        self.assertEqual(self.expected['candidate_sha256'],hashlib.sha256(self.new_bytes).hexdigest())
    def test_method_others_unchanged(self):
        def rest(src):
            tree=ast.parse(src)
            cl=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='FeedbackAnalyzer')
            cl.body=[x for x in cl.body if getattr(x,'name',None)!='_read_jsonl']
            return ast.dump(tree, include_attributes=False)
        self.assertEqual(rest(self.data),rest(self.new_bytes))
    def test_output_utf8_and_bounded(self):
        self.assertIn('Конкретный',format_repair_proposal(self.expected))
        self.assertLess(len(json.dumps(self.expected).encode()),16000)
    def test_broken_path_refuses(self):
        with self.assertRaises(RepairRefused):
            make_repair_proposal(path='../other.py',content=self.data,base_commit=BASE_COMMIT,provenance={'kind':'OBSERVED_COMMITTED_FILE','current_git_head_observed':True})
    def test_wrong_commit_refuses(self):
        with self.assertRaisesRegex(RepairRefused,'BASE_COMMIT_INVALID'):
            make_repair_proposal(path=TARGET,content=self.data,base_commit='invalid sha',provenance={'kind':'OBSERVED_COMMITTED_FILE','current_git_head_observed':True})
    def test_observed_head_after_installer_commit_is_allowed(self):
        newer = make_repair_proposal(
            path=TARGET, content=self.data, base_commit='a'*40,
            provenance={'kind':'OBSERVED_COMMITTED_FILE','current_git_head_observed':True})
        self.assertEqual(newer['base_commit'], 'a'*40)
        self.assertEqual(newer['candidate_sha256'], self.expected['candidate_sha256'])

    def test_restore_not_current_refuses(self):
        with self.assertRaisesRegex(RepairRefused,'OBSERVED_GIT'):
            make_repair_proposal(path=TARGET,content=self.data,base_commit=BASE_COMMIT,provenance={'kind':'RESTORED_FILE','current_git_head_observed':False})
    def test_bytes_drift_refuses(self):
        bad=self.data.replace(b'json.loads(line)',b'json.loads(line)  # drift')
        with self.assertRaisesRegex(RepairRefused,'SOURCE_SHA_CHANGED'):
            make_repair_proposal(path=TARGET,content=bad,base_commit=BASE_COMMIT,provenance={'kind':'OBSERVED_COMMITTED_FILE','current_git_head_observed':True})
    def test_crlf_source_refuses(self):
        with self.assertRaisesRegex(RepairRefused,'SOURCE_PROFILE'):
            make_repair_proposal(path=TARGET,content=self.data.replace(b'\n',b'\r\n'),base_commit=BASE_COMMIT,provenance={'kind':'OBSERVED_COMMITTED_FILE','current_git_head_observed':True})
    def test_already_fixed_refuses(self):
        with self.assertRaises(RepairRefused):
            make_repair_proposal(path=TARGET,content=self.new_bytes,base_commit=BASE_COMMIT,provenance={'kind':'OBSERVED_COMMITTED_FILE','current_git_head_observed':True})
    def test_no_meta_valid_pair_preserved(self):
        files={'command_history.jsonl':self.good_pair()}
        old=self.run_case(self.old,files)
        new=self.run_case(self.new,files)
        self.assertEqual(old,new)
        self.assertEqual(len(new['correction_pairs']),1)
    def test_only_valid_records_match(self):
        files={'command_history.jsonl':self.good_pair(),
               'nlu_hard_cases.jsonl':[{'raw_text':'спроси','meta':{'intent':'UNKNOWN'}}],
               'action_failures.jsonl':[{'raw_text':'открой','meta':{'intent':'OPEN_APP'},'error_type':'Test'}],
               'resolver_candidates.jsonl':[{'raw_text':'открой','meta':{'intent':'OPEN_APP'}, 'missing_slots':['app']}]}
        self.assertEqual(self.run_case(self.old,files),self.run_case(self.new,files))
    def test_all_missing_or_null_meta_kept(self):
        files={'nlu_hard_cases.jsonl':[{'raw_text':'один'}, {'raw_text':'два','meta':None}]}
        a=self.run_case(self.old,files);b=self.run_case(self.new,files)
        self.assertEqual(a,b);self.assertEqual(b['totals']['hard_cases'],2)
    def test_command_history_list_meta_crashes_baseline(self):
        files={'command_history.jsonl':[self.good_pair()[0],{'ts':'2026-01-01T00:00:01','accepted':True,'raw_text':'брак','meta':['bad']}, self.good_pair()[1]]}
        with self.assertRaises(AttributeError):self.run_case(self.old,files)
        got=self.run_case(self.new,files)
        self.assertEqual(got['totals']['command_history'],2)
        self.assertEqual(len(got['correction_pairs']),1)
    def test_command_history_number_meta_crashes_baseline(self):
        files={'command_history.jsonl':[self.good_pair()[0],{'ts':'2026-01-01T00:00:01','accepted':True,'raw_text':'брак','meta':33}, self.good_pair()[1]]}
        with self.assertRaises(AttributeError):self.run_case(self.old,files)
        got=self.run_case(self.new,files);self.assertEqual(got['totals']['command_history'],2)
    def test_command_history_string_meta_crashes_baseline(self):
        files={'command_history.jsonl':[self.good_pair()[0],{'ts':'2026-01-01T00:00:01','accepted':True,'raw_text':'брак','meta':'unsafe'}, self.good_pair()[1]]}
        with self.assertRaises(AttributeError):self.run_case(self.old,files)
        got=self.run_case(self.new,files);self.assertEqual(got['totals']['command_history'],2)
    def test_action_failure_meta_array_crashes_baseline(self):
        files={'action_failures.jsonl':[{'raw_text':'открой','error_type':'ERR','meta':['bad']}]}
        with self.assertRaises(AttributeError):self.run_case(self.old,files)
        self.assertEqual(self.run_case(self.new,files)['totals']['action_failures'],0)
    def test_resolver_meta_array_crashes_baseline(self):
        files={'resolver_candidates.jsonl':[{'raw_text':'открой','missing_slots':['url'],'meta':[1]}]}
        with self.assertRaises(AttributeError):self.run_case(self.old,files)
        self.assertEqual(self.run_case(self.new,files)['totals']['resolver_candidates'],0)
    def test_boolean_true_meta_crashes_baseline(self):
        files={'action_failures.jsonl':[{'raw_text':'открой','error_type':'ERR','meta':True}]}
        with self.assertRaises(AttributeError):self.run_case(self.old,files)
        self.assertEqual(self.run_case(self.new,files)['totals']['action_failures'],0)
    def test_empty_list_is_rejected_as_invalid(self):
        files={'nlu_hard_cases.jsonl':[{'raw_text':'абв','meta':[]}]}
        self.assertEqual(self.run_case(self.old,files)['totals']['hard_cases'],1)
        self.assertEqual(self.run_case(self.new,files)['totals']['hard_cases'],0)
    def test_nested_other_type_not_claimed_fixed(self):
        files={'command_history.jsonl':[self.good_pair()[0],
               {'ts':'2026-01-01T00:00:01','accepted':True,'raw_text':'брак',
               'meta':{'intent':'OPEN_APP','confidence':'invalid','slots':{}}}]}
        # Valid dict meta may still carry a wrong confidence type.
        with self.assertRaises(ValueError):self.run_case(self.new,files)
    def test_malformed_json_behavior_retained(self):
        (self.dir/'nlu_hard_cases.jsonl').write_text('{bad\n{"raw_text":"ok","meta":{}}\n',encoding='utf-8')
        a=self.old(str(self.dir)).analyze(); b=self.new(str(self.dir)).analyze()
        self.assertEqual(a,b)
        self.assertEqual(b['totals']['hard_cases'],1)
    def test_clean_valid_alias_unchanged(self):
        files={'command_history.jsonl':self.good_pair()+self.good_pair()}
        self.assertEqual(self.run_case(self.old,files),self.run_case(self.new,files))


if __name__ == '__main__':
    unittest.main(verbosity=2)
