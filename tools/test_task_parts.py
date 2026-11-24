import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_task_parts as ev
import skynet_task_parts as mod


class Parts(unittest.TestCase):
    def test_residual_must_be_unique_and_word_aligned(self):
        p=dict(start=7,text="слово, слово, подпись автора")
        for fragment in ("слово","пись","подписи",".","авто"):
            self.assertIsNone(mod.residual_span(p,fragment))
        self.assertEqual(mod.residual_span(p,"подпись автора")["start"],21)

    def test_offsets_and_literal_conjunction(self):
        q="  Где «да и нет»?\n   И кто вызывает?"
        parts=mod.split(q)
        self.assertEqual("".join(p["text"] for p in parts),q)
        self.assertEqual(len(parts),2)
        for p in parts:
            self.assertEqual(q[p["start"]:p["end"]],p["text"])

    def test_missing_key_and_budget(self):
        reply=lambda *_:('{"1":"1 site","99":"1 site"}',dict(finish_reason="stop"))
        parts=mod.split("Где метка и какова цена?")
        self.assertEqual(mod.plan(parts,reply,"parts")[1],([],["uninterpreted"],1))
        many=mod.split(" и ".join(["пункт"]*9))
        self.assertTrue(all(issues==["part_budget"] for _,issues,_ in mod.plan(many,None,"parts")))

    def test_lost_word_and_unexplained_gap(self):
        q="Найди журнал"
        p=dict(mod.split(q)[0],claims=[],status="unknown",issues=["external"])
        for change in (dict(text="журнал"),dict(issues=[])):
            with self.subTest(change=change),self.assertRaises(mod.req.observed.route.arguments.host.Rejected):
                mod.verify(q,dict(parts=[dict(p,**change)],proofs=[]),[])

    def test_revise_after_receipts_and_reject_tampering(self):
        root=ev.ev.pilot.ROOT
        src,ground=ev.ev.loop.read_head(root)
        q="Где «M126_QUERY_INVALID» и каковы условия?"
        def select(prompt,payload):
            data={"1":"1 site","2":"1 site"} if prompt==mod.PROMPT else {"1":"ok","2":"condition"}
            return json.dumps(data),dict(finish_reason="stop")
        def run():
            return ev.ev.loop.investigate(q,root,discovery="parts",opener=lambda _:(src,ground),select=select)
        out=run()
        self.assertEqual(out["state"],"answered")
        self.assertEqual(out["parts"][1]["need"],["site","condition"])
        self.assertIn("revise_plan",[s["tool"] for s in out["steps"]])
        original=ev.ev.loop.host.lab.cli.calls.cited
        with patch.object(ev.ev.loop.host.lab.cli.calls,"cited",lambda *a:dict(original(*a),url="wrong")):
            self.assertEqual(run().get("reason"),"invalid_reference")

    def test_mixed_unsplit_question_and_scope_before_model(self):
        root=ev.ev.pilot.ROOT
        src,ground=ev.ev.loop.read_head(root)
        q="Укажи условия для «M126_QUERY_INVALID», сообщив цену доставки."
        calls=[]
        def select(prompt,payload):
            calls.append(prompt)
            obj={"1":"1 condition"} if prompt==mod.PROMPT else {"1":{"missing":"цену доставки","why":"external"}}
            return json.dumps(obj,ensure_ascii=False),dict(finish_reason="stop")
        opts=dict(discovery="residual",opener=lambda _:(src,ground),select=select)
        out=ev.ev.loop.investigate(q,root,**opts)
        self.assertEqual(out["state"],"partial")
        gap=out["parts"][0]["residual"]
        self.assertEqual(q[gap["start"]:gap["end"]],"цену доставки")
        self.assertIn("condition",[c["kind"] for c in out["claims"]])
        denied=ev.ev.loop.investigate("Где в modules/private.py такая строка?",root,**opts)
        self.assertEqual(denied["reason"],"out_of_scope")
        self.assertEqual(calls,[mod.PROMPT,mod.RESIDUAL])


if __name__=="__main__":
    unittest.main()
