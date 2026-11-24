"""Second reading of the published experiment. No analyzer code or fixture is executed."""
import ast
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_route_fixtures import suite

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT/"docs/maintenance/core_06"
ARMS = ("core05","first","lazy","eager","adaptive")
BOUND = re.compile(r"В (\w+) на строке (\d+) записан прямой вызов (\w+)\. Аргументы: (.*)\.")


def constant(expr, values):
    if isinstance(expr,ast.Name):
        return values[expr.id]
    val = ast.literal_eval(expr)
    assert type(val) is int
    return val


def synthetic_verdict(fixture, case, answer):
    """Reconstruct the actually selected site and numeric predicate from raw syntax."""
    fns = {fn.name:fn for fn in ast.parse(fixture).body if isinstance(fn,ast.FunctionDef)}
    origin, message = re.fullmatch(r"Как из (\w+) дойти до ошибки (\w+)\?",case["q"]).groups()
    owner = origin
    env = {}
    texts = [o["text"] for o in answer["observations"]]
    for o in answer["observations"]:
        m = BOUND.fullmatch(o["text"])
        if not m:
            continue
        caller, line, target, rendered = m.groups()
        assert caller==owner
        stmt, = [s for s in fns[caller].body if s.lineno==int(line)]
        call = stmt.value
        assert isinstance(call,ast.Call) and call.func.id==target
        assert any(p=="R" and lo<=int(line)<=hi for p,lo,hi in o["refs"])
        owner = target
        formal = fns[target].args.args
        if not formal:
            assert not (call.args or call.keywords) and rendered=="явных параметров нет"
            env = {}
            continue
        p, = formal
        supplied = [*call.args, *(k.value for k in call.keywords if k.arg==p.arg)]
        expr, = supplied or fns[target].args.defaults
        assert rendered == f"{p.arg} ← `{ast.unparse(expr)}`" + ("" if supplied else " (по умолчанию)")
        env = {p.arg:constant(expr,env)}
    guard = fns[owner].body[0]
    assert isinstance(guard,ast.If)
    test = guard.test
    negated = isinstance(test,ast.UnaryOp)
    cmp = test.operand if negated else test
    assert isinstance(cmp,ast.Compare) and (not negated or isinstance(test.op,ast.Not))
    left = env[cmp.left.id]
    right = constant(cmp.comparators[0],{})
    op, = cmp.ops
    true = {ast.Eq:left==right,ast.Lt:left<right,ast.GtE:left>=right}[type(op)] != negated
    terminal, = guard.body
    assert isinstance(terminal,ast.Raise) and terminal.exc.args[0].value==message
    assert any(ast.unparse(terminal) in t for t in texts)
    exclusions = [t for t in texts if "Этот вариант перехода исключён." in t]
    expected = "conditional_route" if true else "excluded_route"
    assert answer["research"]["verdict"] == expected and len(exclusions) == int(not true)
    if exclusions:
        assert f"{cmp.left.id}={left}" in exclusions[0] and f"{owner}@{terminal.lineno}" in exclusions[0]
    return expected


def main():
    data = json.loads((DIR/"results.json").read_text(encoding="utf8"))
    plan = json.loads((DIR/"transfer.json").read_text(encoding="utf8"))
    raw = subprocess.check_output(["git","show",plan["source"]+":modules/developer_task_ui/app/retrieval/m130_rank.py"],cwd=ROOT)
    generated = {c["id"]:(fixture,c) for fixture,c in suite(int(plan["implementation"][:16],16),raw)}
    counts = Counter()
    for row in data["rows"]:
        for arm in ARMS:
            result = row[arm]
            a = result["answer"]
            assert all(s["tool"] not in ("classify_intent","model","qwen") for s in a["trace"])
            if row["id"].startswith("T") and arm not in ("core05","adaptive"):
                assert a["observations"]==row["adaptive"]["answer"]["observations"]
            if row["id"] in generated and arm!="core05" and a["observations"]:
                synthetic_verdict(*generated[row["id"]],a)
                counts[arm] += 1
    # The original 0.5 formulation of the single local check is semantically
    # sufficient. Keep the preregistered mechanical score and credit this separately.
    local, = [r for r in data["rows"] if r["id"]=="T09"]
    old = local["core05"]
    assert old["missing"]==["условие receipt_without_source@233"]
    observation, = old["answer"]["observations"]
    assert "`report.get('schema')` отличается от `'SKYNETVS_M134_READONLY_PROJECT_CONTEXT_V1'`" in observation["text"]
    assert ["C",232,232] in observation["refs"]
    print("Independent numeric check on every published generated route:",dict(counts))
    print("Core 0.5 T09: complete in meaning; strict score kept in original log.")


if __name__=="__main__":
    main()
