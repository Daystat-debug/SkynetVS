import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_semantic_identity as lab
from test_object_binding import catalog

sem=lab.identity


class Identity(unittest.TestCase):
    def propose(self, quote, unsupported=False):
        effects=catalog()
        q=[dict(text="Где описан горячий сосуд?")]
        def choose(prompt,body):
            cards=json.loads(body)["0"]["карточки"]
            ids={row[0]:int(k) for k,row in cards.items()}
            a,b=(ids[e.label] for e in effects)
            pair=[a,b] if prompt==sem.RANK else [b if not unsupported else 999,quote]
            return json.dumps({"0":pair},ensure_ascii=False),{"finish_reason":"stop"}
        return sem.propose(q,effects,"identity_contrast",choose,lambda _:False)[0]

    def test_rival_can_replace_nominee_only_with_source_fragment(self):
        r=self.propose("Кофейник нагрелся")
        self.assertNotEqual(r["first"],r["chosen"])
        self.assertEqual(r["chosen"],1)
        self.assertIsNone(self.propose("кипяток в лаборатории")["chosen"])
        self.assertIsNone(self.propose("Кофейник",True)["chosen"])

    def test_quote_uses_host_only_and_preserves_scope(self):
        def forbidden(*_):
            self.fail("model called")
        def ask(q):
            return lab.ev.loop.investigate(q,lab.ev.pilot.ROOT,discovery="identity_contrast",select=forbidden)
        out=ask("Где «M134_GOAL_EMPTY_OR_TOO_LONG»?")
        self.assertEqual((out["state"],out["parts"][0]["binding"]["via"]),("answered","quote"))
        self.assertEqual(ask("Где в modules/private.py эта строка?")["reason"],"out_of_scope")

    def test_no_model_has_offline_grounding_fallback(self):
        q="Где печатается количество выбранных окон?"
        def down(*_):
            raise OSError("offline")
        opts=dict(select=down)
        old=lab.ev.loop.investigate(q,lab.ev.pilot.ROOT,discovery="joint_plan",**opts)
        new=lab.ev.loop.investigate(q,lab.ev.pilot.ROOT,discovery="identity_contrast",**opts)
        self.assertEqual((new["state"],new["parts"][0]["binding"]),(old["state"],old["parts"][0]["binding"]))


if __name__=="__main__":
    unittest.main()
