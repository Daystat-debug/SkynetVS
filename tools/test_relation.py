from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_object_binding as historical
import skynet_relation as relation
import skynet_task_parts as parts


class RelationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = historical.prev.ev.loop
        cls.root = historical.prev.ev.pilot.ROOT
        cls.snapshot = cls.host.read_head(cls.root)

    def ask(self, question):
        return self.host.investigate(question, self.root, discovery="relation_frame",
            select=lambda *_: self.fail("offline provider"), opener=lambda _: self.snapshot)

    def test_authentic_support_does_not_replace_requested_fact(self):
        question = "Кто вызывает обработчик «M134_GOAL_EMPTY_OR_TOO_LONG»?"
        out = self.ask(question)
        self.assertEqual(out["state"], "answered")
        slot = out["parts"][0]["relation"]
        self.assertEqual([out["claims"][n]["kind"] for n in slot["direct"]], ["caller"])
        self.assertEqual([out["claims"][n]["kind"] for n in slot["support"]], ["site"])
        original = parts.research
        def substitute(*args):
            result, meta = original(*args)
            slot = meta["parts"][0]["relation"]
            slot["direct"], slot["support"] = slot["support"], slot["direct"]
            return result, meta
        with patch.object(parts, "research", substitute):
            rejected = self.ask(question)
        self.assertEqual((rejected["reason"], rejected["claims"]), ("claim_binding", []))

    def test_missing_direct_fact(self):
        projection = relation.projection({"claims":[0]}, {"kind":"arguments","inherited_from":None}, [{"kind":"site"}])
        self.assertEqual((projection["direct"],projection["support"]), ([],[0]))

    def test_scope_and_part_budget(self):
        self.assertEqual(self.ask("Где в modules/private.py эта строка?")["reason"], "out_of_scope")
        self.assertEqual(self.ask(" ".join(["Где «пример»?"] * 9))["reason"], "part_budget")


if __name__ == "__main__":
    unittest.main()
