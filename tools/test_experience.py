import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_experience as ev
import skynet_task_parts as parts

policy=ev.policy


class ExperienceTests(unittest.TestCase):
    def test_learning_from_payoffs_changes_choice_without_question_ids(self):
        rows=[]
        for signal in [True]*4+[False]*4:
            rewards=dict.fromkeys(policy.ACTIONS,0)
            rewards["lexical_parts" if signal else "memory_only"]=5
            rows.append(dict(features={"quote":signal},reward=rewards))
        tree,_=policy.fit(rows,1)
        self.assertEqual(policy.apply(tree,{"quote":True}),"lexical_parts")
        self.assertEqual(policy.apply(tree,{"quote":False}),"memory_only")
        with self.assertRaises(ValueError):
            policy.apply({"action":"unlisted"},{})

    def test_strict_compositions_and_same_target_paraphrases(self):
        p=json.loads(ev.prev.ev.pilot.git("show",ev.GROUPED))
        self.assertEqual(len(ev.audit(p)),3)
        by_id={k:sorted((target,kind) for _,target,kind in demands) for k,_,demands in p["cases"]}
        for group in p["paraphrase_families"]:
            self.assertEqual(len({tuple(by_id[k]) for k in group}),1)

    def test_forbidden_path_before_learning_and_forged_citation(self):
        loop=ev.prev.ev.loop
        root=ev.prev.ev.pilot.ROOT
        src,ground=loop.read_head(root)
        opts=dict(discovery="experience_release",opener=lambda _:(src,ground))
        with patch.object(policy,"select",side_effect=AssertionError("premature learner")):
            out=loop.investigate("Где в modules/outside.py условие?",root,**opts)
            self.assertEqual(out["reason"],"out_of_scope")
        q="Где появляется «M127_TOP_LIMIT_INVALID»?"
        cited=loop.host.lab.cli.calls.cited
        self.assertTrue(loop.investigate(q,root,**opts)["claims"])
        with patch.object(loop.host.lab.cli.calls,"cited",lambda *a:dict(cited(*a),url="forged")):
            result=loop.investigate(q,root,**opts)
            self.assertEqual((result["reason"],result["claims"]),("invalid_reference",[]))

    def test_shared_quoted_subject_and_budget(self):
        repeated=parts.split("Где «Меточка» и почему появляется «Меточка»?")
        self.assertEqual([target for _,_,target in policy.shared_plan(repeated)],[0,0])
        self.assertEqual([target for _,_,target in policy.shared_plan(parts.split("Где «Один» и почему «Два»?"))],[0,1])
        long=parts.split(" и ".join(["часть"]*9))
        self.assertTrue(all(gaps==["part_budget"] for _,gaps,_ in policy.learned_plan(long,"receipt_trained")))


if __name__=="__main__":
    unittest.main()
