"""Read the public Russian condition as a formula, independently of the proof metadata."""
import ast
import re


class Reader:
    def __init__(self, text, fn):
        self.text = text
        self.at = 0
        self.tests = {(n.test.lineno, ast.unparse(n.test)) for n in ast.walk(fn) if isinstance(n, ast.If)}
        self.loops = {(n.lineno, f"for {ast.unparse(n.target)} in {ast.unparse(n.iter)}")
                      for n in ast.walk(fn) if isinstance(n, ast.For)}

    def take(self, literal):
        if self.text.startswith(literal, self.at):
            self.at += len(literal)
            return True
        return False

    def reference(self, grammar, entries):
        match = re.compile(grammar).match(self.text, self.at)
        assert match, self.text[self.at:]
        self.at = match.end()
        expr, line = match["expr"], int(match["line"])
        assert (line, expr) in entries
        return match, line

    def term(self):
        if self.take("(если "):
            test = self.expression()
            assert self.take(", требуется ")
            yes = self.expression()
            assert self.take(", иначе — ")
            no = self.expression()
            assert self.take(")")
            return ["if",test,yes,no]
        if self.take("не выполнено условие ("):
            term = self.expression()
            assert self.take(")")
            return ["not",term]
        if self.take("для "):
            past = self.take("предыдущих")
            assert past or self.take("всех")
            _, line = self.reference(r" итераций `(?P<expr>[^`]+)` \(стр\. (?P<line>\d+), включая пустой перебор\) выполнено \(",self.loops)
            body = self.expression()
            assert self.take(")")
            return ["past" if past else "all",line,body]
        for label, op, end in (("началась рассматриваемая итерация ", "iteration", ""),
                               ("до этой итерации не было других итераций ", "past", ""),
                               ("перебор ", "all", " пуст")):
            if self.take(label):
                _, line = self.reference(r"`(?P<expr>[^`]+)` \(стр\. (?P<line>\d+)\)",self.loops)
                assert self.take(end)
                return [op,line] if op=="iteration" else [op,line,False]
        if self.take("да"):
            return True
        if self.take("нет"):
            return False
        match, line = self.reference(r"`(?P<expr>[^`]+)` (?P<truth>истинно|ложно) \(стр\. (?P<line>\d+)\)", self.tests)
        return line if match["truth"]=="истинно" else -line

    def expression(self):
        terms = [self.term()]
        while self.take(" и "):
            terms.append(self.term())
        return terms[0] if len(terms)==1 else ["and",*terms]


def displayed(text, fn, line):
    prefix = f"В {fn.name} исследована инструкция "
    selected = [ast.unparse(s) for s in ast.walk(fn) if isinstance(s, ast.stmt) and s.lineno == line]
    headers = [f"{prefix}`{stmt}` (стр. {line}). " for stmt in selected]
    header, = [h for h in headers if text.startswith(h)]
    body = text[len(header):]
    body, scope, _ = body.partition(" Предикаты относятся к своим строкам при нормальном завершении вычислений и конечном переборе.")
    assert scope
    main, _, exits = body.partition(" При расчёте учтены переходы ")
    if exits:
        refs = re.findall(r"`([^`]+)` \(стр\. (\d+)\)",exits)
        exits_in_fn = {(ast.unparse(n),n.lineno) for n in ast.walk(fn) if isinstance(n,(ast.Return,ast.Raise,ast.Continue))}
        assert refs and all((code,int(lo)) in exits_in_fn for code,lo in refs)
    if main == "Предшествующих явных условий перехода нет.":
        return True
    preamble = "Для достижения строки требуется: "
    assert main.startswith(preamble) and main.endswith(".")
    reader = Reader(main[len(preamble):-1],fn)
    term = reader.expression()
    assert reader.at == len(reader.text)
    return term
