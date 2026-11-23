"""Evaluation baseline: enumerate local paths forward, sharing only target and loop semantics."""
import ast

import skynet_control_conditions as control


def either(left, right):
    if left is True or right is True:
        return True
    if left is False:
        return right
    if right is False or left == right:
        return left
    return control.choice(left, True, right)


class Forward(control.Proof):
    """Carry surviving paths through each prefix; merge them at the end of each branch."""
    def walk(self, block, live, continued):
        for stmt in block:
            if live is False:
                break
            self.visit()
            if isinstance(stmt, (ast.Return, ast.Raise)):
                self.exit_at(stmt)
                live = False
            elif isinstance(stmt, ast.Continue):
                self.exit_at(stmt)
                continued = either(continued, live)
                live = False
            elif isinstance(stmt, ast.If):
                test = self.test(stmt.test)
                if type(test) is bool:
                    live, continued = self.walk(stmt.body if test else stmt.orelse, live, continued)
                    continue
                # Enumerate branch-local paths first. Common prefixes and joins
                # are factored out so irrelevant diamonds do not multiply paths.
                a, ac = self.walk(stmt.body, True, False)
                b, bc = self.walk(stmt.orelse, True, False)
                cont = control.choice(test, ac, bc)
                continued = either(continued, control.both(live, cont))
                live = control.both(live, control.choice(test, a, b))
            elif isinstance(stmt, ast.For):
                pass_loop = self.loop(stmt)
                live, continued = self.walk(stmt.orelse, control.both(live, pass_loop), continued)
            elif not isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Pass,
                                       ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Delete,
                                       ast.Global, ast.Nonlocal)):
                raise control.Gap("control_unsupported")
        return live, continued

    def fold(self, block, after, on_continue):
        normal, cont = self.walk(block, True, False)
        return either(control.both(normal, after), control.both(cont, on_continue is True))
