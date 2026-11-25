import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_evidence_plan as lab

cli=lab.ev.loop.arguments.cli
facts=lab.REQ.observed.route.facts
Products=lab.prior.graph.allocation.Products


class Planning(unittest.TestCase):
    def test_static_products_match_original_binding(self):
        for source,expr in [
            ("def f(x, /, y='s', *, z=2): pass","f(v + 1, z=a.b)"),
            ("def f(): pass","f()"),
            ("def f(*a): pass","f(x)"),
            ("def f(x): pass","f(*v)"),
            ("def f(x): pass","f(y=2)"),
            ("def f(**k): pass","f(**kw)"),
            ("def f(*, x): pass","f(x=1, x=2)"),
        ]:
            with self.subTest(expr=expr):
                fn=ast.parse(source).body[0]
                call=ast.parse(expr).body[0].value
                cache=Products(None,cli.calls)
                cache.requested.add(fn)
                cli.calls.argument_text(fn,call,cache.remember)
                s=SimpleNamespace(callee=SimpleNamespace(node=fn),call=call)
                try:
                    expected,_=facts.bind(s,{})
                except facts.Gap:
                    self.assertNotIn((fn,call),cache.arguments)
                else:
                    self.assertEqual(cache.arguments[fn,call],tuple(expected))
                    other=ast.parse(expr).body[0].value
                    self.assertNotIn((fn,other),cache.arguments)

    def test_publication_rejects_swapped_real_arguments(self):
        q="Для «M134_GOAL_EMPTY_OR_TOO_LONG» и «M127_OLD_SOURCES_INVALID» какие значения переданы при вызове?"
        host=lab.ev.loop
        def ask(**options):
            return host.investigate(q,lab.ev.pilot.ROOT,discovery="joint_plan",**options)
        self.assertEqual(ask()["state"],"answered")
        self.assertEqual(ask(lookup=cli.calls.lookup)["state"],"partial")
        original=lab.prior.parts.research
        def swapped(*args):
            output,meta=original(*args)
            a,b=[r for r in output[0] if r["kind"]=="arguments"]
            a["text"],b["text"]=b["text"],a["text"]
            return output,meta
        with patch.object(lab.prior.parts,"research",swapped):
            out=ask()
        self.assertEqual((out["reason"],out["claims"]),("claim_binding",[]))

    def test_products_cannot_be_used_after_snapshot_changes(self):
        def moved(_):
            raise lab.ev.loop.host.Rejected("stale_snapshot")
        s=SimpleNamespace(check_budget=lambda:None,src=object(),current=moved)
        with self.assertRaisesRegex(lab.ev.loop.host.Rejected,"stale_snapshot"):
            Products(s,cli.calls).bound(None)


if __name__=="__main__":
    unittest.main()
