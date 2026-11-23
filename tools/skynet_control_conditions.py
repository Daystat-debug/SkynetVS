"""Local explicit control flow in the host's AST. Predicates denote observations at their lines."""
import ast

import skynet_diagnostic_path as diagnostic


class Gap(ValueError):
    """The selected control-flow model cannot justify publication."""


def negate(term):
    if type(term) is bool:
        return not term
    return term[1] if term[0] == "not" else ("not", term)


def both(left, right):
    if left is False or right is False:
        return False
    if left is True:
        return right
    if right is True:
        return left
    return ("and", left, right)


def choice(atom, yes, no):
    if yes == no:
        return yes
    if no is False:
        return both(atom, yes)
    if yes is False:
        return both(negate(atom), no)
    return ("if", atom, yes, no)


def render(term):
    if type(term) is bool:
        return "да" if term else "нет"
    op, *args = term
    if op == "test":
        return f"`{args[1]}` истинно (стр. {args[0]})"
    if op == "not" and args[0][0] == "test":
        return f"`{args[0][2]}` ложно (стр. {args[0][1]})"
    if op == "not":
        return "не выполнено условие (" + render(args[0]) + ")"
    if op == "and":
        return render(args[0]) + " и " + render(args[1])
    if op == "if":
        return f"(если {render(args[0])}, требуется {render(args[1])}, иначе — {render(args[2])})"
    line, header = args[:2]
    if op == "iteration":
        return f"началась рассматриваемая итерация `{header}` (стр. {line})"
    extent = "предыдущих" if op == "past" else "всех"
    if args[2] is False:
        return (f"до этой итерации не было других итераций `{header}` (стр. {line})" if op == "past" else
                f"перебор `{header}` (стр. {line}) пуст")
    return f"для {extent} итераций `{header}` (стр. {line}, включая пустой перебор) выполнено ({render(args[2])})"


class Proof:
    """Backwards conditions for reaching one statement before leaving its function."""
    def __init__(self, function, target):
        self.function = function
        self.target = target
        self.spans = {(function.lineno, function.lineno), (target.lineno, target.end_lineno)}
        self.exits = {}
        self.work = 0
        self.ancestors = {target}
        parent = {child: node for node in ast.walk(function) for child in ast.iter_child_nodes(node)}
        node = target
        while node is not function:
            node = parent[node]
            self.ancestors.add(node)

    def visit(self):
        self.work += 1
        if self.work > 512 or len(self.spans) > 90:
            raise Gap("evidence_budget")

    def test(self, expr):
        self.spans.add((expr.lineno, expr.end_lineno))
        if isinstance(expr, ast.Constant) and type(expr.value) is bool:
            return expr.value
        return ("test", expr.lineno, ast.unparse(expr))

    def exit_at(self, stmt):
        self.spans.add((stmt.lineno, stmt.end_lineno))
        self.exits[(stmt.lineno, stmt.col_offset)] = ast.unparse(stmt)

    def branch(self, stmt, arm):
        test = self.test(stmt.test)
        if type(test) is bool:
            return arm(stmt.body if test else stmt.orelse)
        yes, no = arm(stmt.body), arm(stmt.orelse)
        return choice(test, yes, no)

    def loop(self, stmt, *, past=False):
        line = stmt.lineno
        self.spans.add((line, stmt.iter.end_lineno))
        header = f"for {ast.unparse(stmt.target)} in {ast.unparse(stmt.iter)}"
        normal = self.fold(stmt.body, True, True)
        if normal is True:
            return True
        return ("past" if past else "all", line, header, normal)

    def fold(self, block, after, on_continue):
        for stmt in reversed(block):
            self.visit()
            if isinstance(stmt, (ast.Return, ast.Raise)):
                self.exit_at(stmt)
                after = False
            elif isinstance(stmt, ast.Continue) and on_continue is not None:
                self.exit_at(stmt)
                after = on_continue
            elif isinstance(stmt, ast.If):
                after = self.branch(stmt, lambda arm: self.fold(arm, after, on_continue))
            elif isinstance(stmt, ast.For):
                exhausted = self.loop(stmt)
                after = both(exhausted, self.fold(stmt.orelse, after, on_continue))
            elif not isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Pass,
                                       ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Delete,
                                       ast.Global, ast.Nonlocal)):
                raise Gap("control_unsupported")
        return after

    def reach(self, block):
        for i, stmt in enumerate(block):
            self.visit()
            if stmt not in self.ancestors:
                continue
            if stmt is self.target:
                reached = True
            elif isinstance(stmt, ast.If):
                reached = self.branch(stmt, self.reach)
            elif isinstance(stmt, ast.For):
                in_body = any(s in self.ancestors for s in stmt.body)
                completed = self.loop(stmt, past=in_body)
                reached = self.reach(stmt.body if in_body else stmt.orelse)
                if in_body:
                    header = f"for {ast.unparse(stmt.target)} in {ast.unparse(stmt.iter)}"
                    reached = both(("iteration", stmt.lineno, header), reached)
                reached = both(completed, reached)
            else:
                raise Gap("control_unsupported")
            # A continue in this prefix skips the selected site on this iteration.
            return self.fold(block[:i], reached, False)
        return False

    def build(self):
        if self.function.decorator_list:
            raise Gap("control_unsupported")
        for stmt in self.function.body:
            if any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await)) for n in diagnostic.cli.flow.local_nodes(stmt)):
                raise Gap("control_unsupported")
        term = self.reach(self.function.body)
        if term is False:
            raise Gap("control_unreachable")
        # Bound expansion before rendering an expression with shared continuations.
        remaining, pending = 128, [term]
        while pending:
            current = pending.pop()
            remaining -= 1
            if remaining < 0:
                raise Gap("evidence_budget")
            if isinstance(current, tuple):
                pending.extend(arg for arg in current[1:] if isinstance(arg, tuple))
        return term


def claim(search, fn, target, proof_type=Proof):
    proof = proof_type(fn.node, target)
    term = proof.build()
    detail = ("Предшествующих явных условий перехода нет." if term is True else
              "Для достижения строки требуется: " + render(term) + ".")
    if proof.exits:
        detail += " При расчёте учтены переходы " + ", ".join(
            f"`{value}` (стр. {line})" for (line, _), value in sorted(proof.exits.items())) + "."
    statement = ast.unparse(target)
    text = (f"В {fn.node.name} исследована инструкция `{statement}` (стр. {target.lineno}). {detail} "
            "Предикаты относятся к своим строкам при нормальном завершении вычислений и конечном переборе.")
    if len(text) > 3800:
        raise Gap("evidence_budget")
    anchors = []
    for lo, hi in sorted(proof.spans):
        ref = diagnostic.cli.calls.cited(search.src, fn.path, lo, hi)
        if (ref["commit"], ref["path"], ref["start"], ref["end"]) != (search.src.commit, fn.path, lo, hi):
            raise diagnostic.host.Rejected("endpoint_binding")
        item = diagnostic.host.checked_item(search.src, ref)
        search.items[item["ref_id"]] = item
        anchors.append(dict(ref_id=item["ref_id"], lines=[lo, hi]))
        search.check_budget()
    return dict(text=text, anchors=anchors, control=dict(path=fn.path, function=fn.node.name,
                line=target.lineno, condition=term, work=proof.work))
