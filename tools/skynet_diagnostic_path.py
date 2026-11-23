"""Find a static witness for a diagnostic whose emitting function is initially unknown."""
import ast
from collections import deque
from dataclasses import dataclass
import re

import skynet_argument_flow as arguments

host = arguments.host
cli = host.lab.cli
IDENT = re.compile(r"\b[A-Za-z_][A-Za-z_0-9]*\b")
CODE = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")
QUOTES = re.compile(r'«([^»\n]+)»|"([^"\n]+)"|`([^`\n]+)`')
DIAG = re.compile(r"\b(?:ошибк|ошибо|исключени|сообщени|диагностик|отказ|проверка срабатыв)\w*", re.I)
# Restrict the operation to explaining a static condition or a route. In particular
# do not silently drop a second request, negation, repair, or runtime observation.
WORDS = re.compile(
    r"(?:а|бы|быть|бывает|в|во|внутри|возник\w*|возмо\w*|вход\w*|выбрас\w*|выда\w*|"
    r"вызов\w*|вызыва\w*|где|да[её]т|диагностик\w*|до|дойти|доход\w*|"
    r"если|есть|за|из|и|или|исключени\w*|источник\w*|как\w*|код\w*|котор\w*|"
    r"к|ли|мест\w*|мож\w*|на|найди|начина\w*|объясни|один|от|отказ\w*|откуда|"
    r"ошиб\w*|покажи|получ\w*|появ\w*|почему|при|прив\w*|пример|проверк\w*|"
    r"происход\w*|проследи|путь|пути|разбери|с|сигнал\w*|сообщени\w*|"
    r"срабатыв\w*|статическ\w*|так\w*|текст\w*|услови\w*|функци\w*|цепочк\w*|через|что|эт\w*)", re.I)
ENTRY = re.compile(r"(?:\b(?:из|от|в|внутри|при вызове|начиная с)\s+(?:функци[ию]\s+)?)$", re.I)


@dataclass(frozen=True)
class Question:
    message: str
    origin: str | None
    exception: str | None = None


def interpret(question):
    """None delegates to the old host. False asks for clarification."""
    pasted = re.fullmatch(r"([A-Za-z_]\w*(?:Error|Exception)|Exception): ([^\r\n]{1,240})", question.strip())
    if pasted:
        return Question(pasted[2], None, pasted[1])
    plain = QUOTES.sub(lambda m: " " * len(m[0]), question)
    if not DIAG.search(plain) or not re.search(r"почему|услови|откуда|где|источник|путь|доход|дойти|привод|возник|срабатыв|цепочк", plain, re.I):
        return None
    names = list(IDENT.finditer(plain))
    quoted = [next(s for s in m.groups() if s) for m in QUOTES.finditer(question)]
    codes = [m[0] for m in names if CODE.fullmatch(m[0])]
    messages = quoted + codes
    if not messages and not names:
        return None
    entries = [m for m in names if not CODE.fullmatch(m[0])]
    if len(messages) != 1 or len(entries) > 1 or len(messages[0]) > 240:
        return False
    if entries and not ENTRY.search(plain[:entries[0].start()]):
        return False
    words = IDENT.sub(" ", plain)
    if (re.search(r"[^А-Яа-яЁё\s?!.,:—–-]", words) or
            not all(WORDS.fullmatch(w) for w in re.findall(r"[А-Яа-яЁё]+", words))):
        return False
    return Question(messages[0], entries[0][0] if entries else None)


@dataclass
class Origin:
    function: object
    node: ast.Raise
    message: str
    guards: tuple
    supported: bool


def origins(search, question):
    """Walk lexical function bodies. A matching comment, log or nested def is never a raise."""
    found = []
    for fn in search.index.functions:
        pending = [(stmt, (), True) for stmt in reversed(fn.node.body)]
        while pending:
            node, guards, supported = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(node, ast.Raise):
                exc = node.exc
                if (isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and len(exc.args) == 1
                        and not exc.keywords and isinstance(exc.args[0], ast.Constant)
                        and isinstance(exc.args[0].value, str)):
                    literal = exc.args[0].value
                    matches = literal == question.message or (
                        CODE.fullmatch(question.message) and literal.partition(":")[0] == question.message)
                    if matches and (not question.exception or question.exception == exc.func.id):
                        found.append(Origin(fn, node, literal, guards, supported))
                continue
            if isinstance(node, ast.If):
                for body, truth in ((node.body, True), (node.orelse, False)):
                    pending.extend((stmt, guards + (("if", node.test, truth),), supported) for stmt in reversed(body))
            elif isinstance(node, (ast.For, ast.While)):
                guard = ("for", node, True) if isinstance(node, ast.For) else ("while", node.test, True)
                pending.extend((stmt, guards + (guard,), supported) for stmt in reversed(node.body))
                pending.extend((stmt, guards, False) for stmt in reversed(node.orelse))
            else:
                # Keep track of unsupported occurrences so that a try/except or match
                # can never be silently presented as a known unconditional failure.
                pending.extend((child, guards, False) for child in ast.iter_child_nodes(node))
    return sorted(found, key=lambda hit: (hit.function.path, hit.node.lineno))


def predicate(node):
    """Render the common boolean structure; retain Python for unfamiliar expressions."""
    if isinstance(node, ast.BoolOp):
        parts = [predicate(value) for value in node.values]
        if isinstance(node.op, ast.Or):
            return "хотя бы одно из условий (" + " или ".join(parts) + ")"
        return "все условия (" + " и ".join(parts) + ")"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return f"выражение `{ast.unparse(node.operand)}` ложно"
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        words = {ast.Gt: "больше", ast.Lt: "меньше", ast.GtE: "больше или равно",
                 ast.LtE: "меньше или равно", ast.Eq: "равно", ast.NotEq: "отличается от"}
        comparison = words.get(type(node.ops[0]))
        if comparison:
            return f"`{ast.unparse(node.left)}` {comparison} `{ast.unparse(node.comparators[0])}`"
    return f"выражение `{ast.unparse(node)}` истинно"


def explain(search, hit):
    fn, node = hit.function, hit.node
    spans = [(fn.node.lineno, fn.node.lineno), (node.lineno, node.end_lineno)]
    clauses = []
    for kind, expr, truth in hit.guards:
        if kind == "for":
            clauses.append(f"при очередной итерации `for {ast.unparse(expr.target)} in {ast.unparse(expr.iter)}`")
            spans.append((expr.lineno, expr.iter.end_lineno))
        else:
            clauses.append(predicate(expr) if truth else f"выражение `{ast.unparse(expr)}` ложно")
            spans.append((expr.lineno, expr.end_lineno))
    conditions = ". ".join(clauses) if clauses else "внешних условий if или цикла у строки нет"
    text = (f"В {fn.node.name} записано `{ast.unparse(node)}`. "
            f"Условия окружающих ветвей при достижении этого места: {conditions}.")
    if len(text) > 2200:
        raise arguments.Limit("evidence_budget")
    anchors = []
    for lo, hi in dict.fromkeys(spans):
        ref = cli.calls.cited(search.src, fn.path, lo, hi)
        if (ref["commit"], ref["path"], ref["start"], ref["end"]) != (search.src.commit, fn.path, lo, hi):
            raise host.Rejected("endpoint_binding")
        item = host.checked_item(search.src, ref)
        search.items[item["ref_id"]] = item
        anchors.append(dict(ref_id=item["ref_id"], lines=[lo, hi]))
        search.check_budget()
    return dict(text=text, anchors=anchors)


def witness(search, origin, candidates, *, direct=False):
    """A queue entry carries the terminal occurrence and the checked suffix to it."""
    frontier = deque()
    seen = set()
    for hit in candidates:
        target = hit.function.node.name
        if target == origin:
            return hit, []
        if target not in seen:
            frontier.append((target, hit, []))
            seen.add(target)
    while frontier:
        target, hit, suffix = frontier.popleft()
        for site in search.incoming(target):
            name = site.caller.node.name
            claim = dict(text=f"В теле {name} есть прямой вызов {target}.",
                         edge=[name, target], anchors=site.anchors)
            chain = [claim, *suffix]
            if name == origin:
                return hit, chain
            if not direct and name not in seen:
                frontier.append((name, hit, chain))
                seen.add(name)
    return None


def solve(search, question, planner=witness):
    if search.budget < 1:
        return [], [], "step_budget"
    search.current(search.src)
    hits = origins(search, question)
    search.trace.append(dict(tool="locate_raise", target=question.message, status="searched", matches=len(hits)))
    if not hits:
        return [], [], "diagnostic_missing"
    if question.origin and not search.unique(question.origin):
        return [], [], "clarification"
    if not question.origin and len(hits) != 1:
        return [], [], "diagnostic_ambiguous"
    usable = [h for h in hits if h.supported and search.unique(h.function.node.name) == h.function
              and not h.function.node.decorator_list]
    if not usable:
        return [], [], "diagnostic_context"
    try:
        result = planner(search, question.origin, usable) if question.origin else (usable[0], [])
        if not result:
            return [], [], "diagnostic_context" if len(usable) < len(hits) else "path_unproven"
        hit, chain = result
        claims = [*chain, explain(search, hit)]
        used = dict.fromkeys(a["ref_id"] for claim in claims for a in claim["anchors"])
        return claims, [search.items[k] for k in used], None
    except arguments.Limit as limit:
        return [], [], str(limit)
