from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_learned_match as lab
import fit_semantic_pairs as fit


class LearnedPairs(unittest.TestCase):
    def test_compiler_distinguishes_unknown_from_changed(self):
        a=(1,2,3,4,False)
        self.assertEqual(fit.event_label(a,a),"equal")
        self.assertEqual(fit.event_label((1,2,None,4,False),a),"unknown")
        self.assertEqual(fit.event_label((4,2,None,1,False),a),"different")

    def test_candidate_order_and_abstention(self):
        model=lab.match.frozen()
        q="мастер передал валик маляру"
        choices=[q,"маляр передал валик мастеру"]
        _,p=lab.match.infer(q,choices,model,"learn_roles")
        _,r=lab.match.infer(q,choices[::-1],model,"learn_roles")
        self.assertEqual(r,p[::-1])
        self.assertIsNone(lab.match.decide([p[0],p[0]],*model["thresholds"]["learn_roles"]))

    def test_host_enforces_scope_without_provider(self):
        def forbidden(*_):
            self.fail("unexpected provider call")
        args=dict(discovery="learn_roles",select=forbidden)
        root=lab.old.ev.pilot.ROOT
        run=lab.old.ev.loop.investigate
        self.assertEqual(run("Где в modules/private.py нужное условие?",root,**args)["reason"],"out_of_scope")
        exact=run("Где «M127_TITLE_INVALID»?",root,**args)
        self.assertTrue(exact["claims"] and exact["state"]=="answered")


if __name__=="__main__":
    unittest.main()
