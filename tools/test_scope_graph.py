from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_scope_graph as lab


class Scopes(unittest.TestCase):
    def links(self, seeds, strategy="scope_graph"):
        spans=[dict(text="a") for _ in seeds]
        edges=[dict(target=i,via="quote") for i in range(len(spans))]
        return lab.graph.link(spans,edges,seeds,strategy)

    def test_both_directions_and_competing_scope(self):
        for seeds in ([None,"condition"],["condition",None]):
            self.assertEqual([r["kind"] for r in self.links(seeds)],["condition"]*2)
        result=self.links(["condition",None,"caller"])
        self.assertEqual(result[1]["alternatives"],["caller","condition"])
        self.assertEqual(result[1]["kind"],"ambiguous")
        self.assertNotEqual(self.links(["condition",None,"caller"],"scope_nearest")[1]["kind"],"ambiguous")

    def test_dangling_and_external_predicate(self):
        self.assertEqual(self.links([None,None])[1]["kind"],"unverified_meaning")
        self.assertEqual(self.links([None,"external"])[0]["kind"],"unverified_meaning")

    def test_host_checks_origins_and_access(self):
        loop=lab.ev.loop
        root=lab.ev.pilot.ROOT
        def ask(q):
            return loop.investigate(q,root,discovery="scope_graph",select=lambda *_:self.fail("provider"))
        question="Где «M134_GOAL_EMPTY_OR_TOO_LONG» и «M134_EXPANDED_QUERY_TOO_LONG»?"
        out=ask(question)
        self.assertEqual(out["state"],"answered")
        self.assertEqual(out["parts"][1]["relation"]["origins"],[0])
        original=lab.parts.research
        def falsify(*args):
            result,meta=original(*args)
            meta["parts"][1]["relation"]["origins"]=[1]
            return result,meta
        with patch.object(lab.parts,"research",falsify):
            denied=ask(question)
        self.assertEqual((denied["reason"],denied["claims"]),("claim_binding",[]))
        self.assertEqual(ask("Где в modules/private.py это записано?")["reason"],"out_of_scope")


if __name__=="__main__":
    unittest.main()
