"""Expression-evaluation boundaries and constrained goal selection without a model."""
import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_observed_route as observed

goal = observed.goals
Gap = observed.route.control.Gap


def site(body):
    tree = ast.parse("def start(flag):\n "+body)
    fn = tree.body[0]
    call, = [n for n in ast.walk(fn) if isinstance(n,ast.Call)
             and isinstance(n.func,ast.Name) and n.func.id=="dest"]
    return SimpleNamespace(call=call,caller=SimpleNamespace(node=fn))


class Boundaries(unittest.TestCase):
    def test_always_evaluated(self):
        for body in ("if dest(): return", "return wrap(value=dest())","out = wrap(dest())"):
            with self.subTest(body=body):
                self.assertEqual(observed.statement(site(body)).lineno,2)

    def test_conditional_or_deferred(self):
        for body in ("return flag and dest()", "return dest() if flag else 0",
                     "out = lambda: dest()", "return [dest() for _ in flag]",
                     "if flag or wrap(dest()): return", "def x(v=dest()): pass"):
            with self.subTest(body=body),self.assertRaises(Gap):
                observed.statement(site(body))

    def test_shadowed(self):
        with self.assertRaisesRegex(Gap,"argument_unproven"):
            observed.statement(site("dest = flag\n return wrap(dest())"))

    def test_literal_gaps(self):
        self.assertEqual(goal.literal(ast.parse("'ABC' + item + 'XYZ'",mode="eval").body),"ABC{…}XYZ")

    def test_selector_cannot_issue_an_id(self):
        fn=SimpleNamespace(node=SimpleNamespace(name="example"))
        cards=[goal.Effect(fn,None,None,"A public notice","")]
        for output in ('{"id": 2,"action":"when"}','{"id":true,"action":"where"}',
                       '{"id":1,"action":"exec"}','{"id":1,"action":"where","path":"elsewhere"}'):
            with self.subTest(output=output),self.assertRaises(Gap):
                goal.choose("Где сообщение?",cards,"model",lambda *_:(output,dict(finish_reason="stop")))

    def test_duplicate_quotes_and_weakened_request(self):
        fn=SimpleNamespace(node=SimpleNamespace(name="example"))
        card=goal.Effect(fn,None,None,"Один общий текст","")
        with self.assertRaisesRegex(Gap,"ambiguous"):
            goal.choose("Когда появляется «общий текст»?",[card,card],"hybrid",None)
        with self.assertRaisesRegex(Gap,"ambiguous"):
            goal.choose("Когда появляется ответ?",[card],"model",
                        lambda *_:('{"id":1,"action":"where"}',dict(finish_reason="stop")))


if __name__=="__main__":
    unittest.main()
