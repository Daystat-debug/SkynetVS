import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_experience as old
import skynet_object_binding as binding
import skynet_task_parts as parts


def catalog():
    fn=SimpleNamespace(path="lab.py",node=ast.parse("def report(): pass").body[0])
    calls=ast.parse("send('Чашка наполнена водой', 'Кофейник нагрелся утром')").body[0]
    return [binding.req.goals.Effect(fn,calls,x,x.value,"") for x in calls.value.args]


class Binding(unittest.TestCase):
    def test_occurrences_same_line_and_backreferences(self):
        ps=parts.split("Где «Чашка наполнена водой» и где «Кофейник нагрелся утром»? Кто вызывает обработчик первой? А для второго?")
        edges,found=binding.resolve(ps,catalog(),"sha","object_graph")
        self.assertEqual([e["target"] for e in edges],[0,1,0,1])
        self.assertNotEqual(edges[0]["object"]["column"],edges[1]["object"]["column"])
        self.assertEqual(len(found),2)

    def test_missing_slots_ambiguous_and_nominations(self):
        ps=parts.split("Где «Отсутствует» и где «Чашка наполнена водой»? Почему у первого? Почему у него?")
        edges,_=binding.resolve(ps,catalog(),"sha","object_graph")
        self.assertEqual([e["object"] is None for e in edges],[True,False,True,True])
        ps=parts.split("Что происходит при завтраке?")
        cb=lambda *_:('{"0":500}',dict(finish_reason="stop"))
        self.assertEqual(binding.nominations(ps,catalog(),"sha","object_graph",cb),{})
        edges,_=binding.resolve(ps,catalog(),"sha","object_graph",{0:0})
        self.assertTrue(edges[0]["tentative"])

    def test_publication_rejects_substitution_and_scope(self):
        loop=old.prev.ev.loop
        root=old.prev.ev.pilot.ROOT
        src,ground=loop.read_head(root)
        calls=[]
        def select(*_):
            calls.append(True)
            return '{"1":"1 site","2":"1 site"}',dict(finish_reason="stop")
        opts=dict(opener=lambda _:(src,ground),discovery="object_graph",select=select)
        q="Где «M127_TITLE_INVALID» и где «M127_TOP_LIMIT_INVALID»?"
        out=loop.investigate(q,root,**opts)
        self.assertEqual(out["state"],"answered")
        self.assertNotEqual(out["parts"][0]["claims"],out["parts"][1]["claims"])
        original=parts.research
        def substitute(*args):
            result,meta=original(*args)
            meta["parts"][1]["binding"]=meta["parts"][0]["binding"]
            return result,meta
        with patch.object(parts,"research",substitute):
            rejected=loop.investigate(q,root,**opts)
            self.assertEqual((rejected["reason"],rejected["claims"]),("claim_binding",[]))
        def swap_genuine_receipts(*args):
            result,meta=original(*args)
            for proof in meta["proofs"]:
                proof["target"]=1-proof["target"]
            for p in meta["parts"]:
                p["claims"]=[1-p["claims"][0]]
            return result,meta
        with patch.object(parts,"research",swap_genuine_receipts):
            rejected=loop.investigate(q,root,**opts)
            self.assertEqual((rejected["reason"],rejected["claims"]),("claim_binding",[]))
        denied=loop.investigate("Где в modules/elsewhere.py эта строка?",root,**opts)
        self.assertEqual(denied["reason"],"out_of_scope")
        self.assertEqual(len(calls),3)


if __name__=="__main__":
    unittest.main()
