import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_obligation_check as subject
import build_obligation_memory as build
import eval_task_parts as prior


class IndependentCheck(unittest.TestCase):
    def test_exact_original_spans(self):
        q = 'Где «А, Б и В», сколько осталось? Назови автора.'
        parts = subject.segment(q)
        self.assertEqual(len(parts),3)
        self.assertEqual([q[p["start"]:p["end"]] for p in parts],[p["text"] for p in parts])
        self.assertEqual(q,"".join(p["text"] for p in parts))

    def test_holdout_not_required_to_build(self):
        import json
        self.assertEqual(json.loads(build.OUTPUT.read_text(encoding="utf8")),json.loads(json.dumps(build.build())))

    def test_verifier_ignores_plan_and_requires_actual_condition(self):
        parts = [dict(text="Какие проверки должны пропустить управление к «метка»?",
                      status="established", claims=[0], target=0, need=["site"])]
        rows = [dict(kind="site",text="метка")]
        self.assertIn("condition",subject.expected(parts[0]["text"])[0])
        with self.assertRaises(subject.req.observed.route.arguments.host.Rejected):
            subject.verify(parts,rows)
        parts[0]["claims"].append(1)
        rows.append(dict(kind="condition",text="predicate"))
        subject.verify(parts,rows)
        rows[0]["text"]="другой результат"
        with self.assertRaises(subject.req.observed.route.arguments.host.Rejected):
            subject.verify(parts,rows)

    def test_unknown_cannot_be_certified_by_an_interpreter(self):
        parts=[dict(text="цццщщъъъ",claims=[0],status="established",target=0)]
        with self.assertRaises(subject.req.observed.route.arguments.host.Rejected):
            subject.verify(parts,[dict(kind="site",text="something")])

    def test_independent_kind_can_schedule_more_work(self):
        q="Какие проверки должны пропустить управление к «X»?"
        plan=subject.augment(subject.segment(q),[ (["site"],[],0) ])
        self.assertIn("condition",plan[0][0])

    def test_host_recollects_condition_and_keeps_reference_and_scope_checks(self):
        root=prior.ev.pilot.ROOT
        src,ground=prior.ev.loop.read_head(root)
        calls=[]
        def wrong_kind(*_):
            calls.append(True)
            return '{"1":"1 site"}',dict(finish_reason="stop")
        args=dict(discovery="independent",opener=lambda _:(src,ground),select=wrong_kind)
        q="Какие проверки должны пропустить управление к «M126_QUERY_INVALID»?"
        out=prior.ev.loop.investigate(q,root,**args)
        self.assertEqual(out["state"],"answered")
        self.assertIn("condition",[claim["kind"] for claim in out["claims"]])
        denied=prior.ev.loop.investigate("Где в modules/other.py это условие?",root,**args)
        self.assertEqual(denied["reason"],"out_of_scope")
        self.assertEqual(len(calls),1)
        cited=prior.ev.loop.host.lab.cli.calls.cited
        with patch.object(prior.ev.loop.host.lab.cli.calls,"cited",lambda *a:dict(cited(*a),url="forged")):
            rejected=prior.ev.loop.investigate(q,root,**args)
            self.assertEqual(rejected["reason"],"invalid_reference")
            self.assertEqual(rejected["claims"],[])

if __name__=="__main__":
    unittest.main()
