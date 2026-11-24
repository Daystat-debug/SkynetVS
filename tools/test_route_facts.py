"""Small tests on AST inputs. None of the sample Python is executed."""
import ast
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_investigate as loop

facts = loop.research.facts


def site(code):
    tree = ast.parse(code)
    target, source = tree.body[-2:]
    functions = [loop.host.lab.cli.flow.Function("fixture.py",tree,node) for node in (source,target)]
    call, = [n for n in ast.walk(source) if isinstance(n,ast.Call)]
    return loop.arguments.Site(*functions,call,[])


class RouteFacts(unittest.TestCase):
    def test_bind_defaults_and_positional_only(self):
        s = site("def dest(a, /, *, b=-2): pass\ndef origin(): return dest(0)")
        rows, values = facts.bind(s,{})
        self.assertEqual(values,{"a":0,"b":-2})
        self.assertEqual(rows,[("a","0",False),("b","-2",True)])
        self.assertIs(facts.call_statement(s).value,s.call)

    def test_rebinding_and_default_expressions(self):
        s = site("def dest(a,b=external):\n a = 1\n return a\ndef origin(): return dest(value)")
        self.assertEqual(facts.bind(s,{"value":False})[1],{})

    def test_argument_errors(self):
        for call in ("dest(b=1)","dest(*items)","dest(**items)","dest(1,2)"):
            with self.subTest(call=call), self.assertRaises(facts.Gap):
                facts.bind(site("def dest(a): pass\ndef origin(): return "+call),{})

    def test_indirect_evaluation_and_shadow(self):
        for code in ("def origin(): return active and dest(1)",
                     "def origin(dest): return dest(1)",
                     "def origin(): return (dest(2) if on else 0)"):
            with self.subTest(code=code), self.assertRaises(facts.Gap):
                facts.call_statement(site("def dest(a): pass\n"+code))

    def test_unknown_predicate_and_shadowed_builtin(self):
        for prefix, expected in (("",True),("isinstance = override\n",facts.UNKNOWN)):
            s = site(prefix+"def dest(a): pass\ndef origin(): return dest(5)")
            expr = ast.parse("isinstance(a, int) and a >= 4",mode="eval").body
            self.assertIs(facts.boolean(expr,s.callee,{"a":5}),expected)
            self.assertIs(facts.boolean(expr,s.callee,{}),facts.UNKNOWN)
            self.assertIs(facts.boolean(ast.parse("a.attr",mode="eval").body,s.callee,{"a":5}),facts.UNKNOWN)

    def test_direction_and_remainder(self):
        self.assertEqual(loop.research.goal("a → b@12",loop.endpoints),("a","b@12"))
        self.assertIsNone(loop.research.goal("a -> b и запусти его",loop.endpoints))


if __name__ == "__main__":
    unittest.main()
