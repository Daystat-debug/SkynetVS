"""Small independent semantic checks; subject snippets are parsed, never executed."""
import ast
from pathlib import Path
import sys
import unittest
from itertools import product

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_control_conditions as control
from eval_control_answer_text import displayed


def evaluate(term, values, loops=None):
    if type(term) is bool:
        return term
    op, *args = term
    if op == "test":
        return values[args[0]]
    if op == "not":
        return not evaluate(args[0], values, loops)
    if op == "and":
        return all(evaluate(v, values, loops) for v in args)
    if op == "if":
        return evaluate(args[1] if evaluate(args[0], values, loops) else args[2], values, loops)
    if op == "iteration":
        return loops[(op, args[0])]
    return all(evaluate(args[2], v, loops) for v in loops[(op, args[0])])


def proof(body, target="return 42"):
    fn = ast.parse("def sample():\n" + "\n".join("    " + s for s in body.splitlines())).body[0]
    selected, = (s for s in ast.walk(fn) if isinstance(s, ast.stmt) and ast.unparse(s) == target)
    return control.Proof(fn, selected).build()


class Conditions(unittest.TestCase):
    def test_visible_polarity_and_location(self):
        fn = ast.parse("def f(x):\n    if x: return 7").body[0]
        claim = ("В f исследована инструкция `return 7` (стр. 2). Для достижения строки требуется: "
                 "`x` истинно (стр. 2). Предикаты относятся к своим строкам при нормальном завершении вычислений и конечном переборе.")
        self.assertEqual(displayed(claim, fn, 2), 2)
        self.assertEqual(displayed(claim.replace("истинно","ложно"), fn, 2), -2)
        with self.assertRaises(AssertionError):
            displayed(claim.replace("`x` истинно (стр. 2)", "`x` истинно (стр. 1)"), fn, 2)

    def test_choices_and_prior_exits(self):
        term = proof("if a:\n    if b: return 0\nelse:\n    if c: raise Bad()\nif d:\n    return 42")
        for a,b,c,d in product((False,True), repeat=4):
            self.assertEqual(evaluate(term, {2:a,3:b,5:c,6:d}), d and not (b if a else c))

    def test_empty_or_no_match(self):
        term = proof("for x in xs:\n    if ready(x): return x\nreturn 42")
        for sequence in ([], [True], [False, True], [False, False]):
            self.assertEqual(evaluate(term, {}, {("all",2): [{3:v} for v in sequence]}), not any(sequence))

    def test_continue_separates_current_and_past(self):
        term = proof("for x in xs:\n    if skip: continue\n    if stop: return 0\n    if take: return 42")
        for s,t,k in product((False,True), repeat=3):
            for ps,pt,pk in product((False,True),repeat=3):
                env = {3:s,4:t,5:k}
                loop = {("past",2):[{3:ps,4:pt,5:pk}], ("iteration",2):True}
                self.assertEqual(evaluate(term, env, loop), (ps or not (pt or pk)) and not s and not t and k)

    def test_lexical_exclusions_and_unsupported(self):
        self.assertIs(proof("def inner():\n    return 8\nreturn 42"), True)
        for text in ("return 1\nreturn 42", "if False:\n    return 42"):
            with self.assertRaisesRegex(control.Gap, "control_unreachable"):
                proof(text)
        for prefix in ("try:\n    return 1\nfinally:\n    pass", "while x:\n    pass",
                       "for x in xs:\n    if x: break", "yield 1", "assert x"):
            with self.assertRaisesRegex(control.Gap, "control_unsupported"):
                proof(prefix + "\nreturn 42")


if __name__ == "__main__":
    unittest.main()
