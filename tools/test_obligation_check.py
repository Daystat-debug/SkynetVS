import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_obligation_check as subject
import build_obligation_memory as build


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

if __name__=="__main__":
    unittest.main()
