"""Compare local explanations on pinned public Git bytes; no subject code is executed."""
import argparse
import ast
from contextlib import ExitStack
from itertools import product
import json
from pathlib import Path
import random
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_diagnostic_path as archive
from test_control_conditions import control

loop, pilot, old = archive.loop, archive.pilot, archive.old
BASE = "d7dafa045d8e32cce7a50318a0fe947cea0bb605"
DIR = pilot.ROOT / "docs/maintenance/core_05"
ARMS = ("core04", "guards", "static", "core05")


class Guards(control.Proof):
    """Domination by a sequence of guards, including a sequential scan for an early exit."""
    def fold(self, block, after, on_continue):
        for stmt in reversed(block):
            if isinstance(stmt, ast.If):
                exits = (ast.Return, ast.Raise, ast.Continue, ast.Break)
                nested = [n for arm in (stmt.body, stmt.orelse) for child in arm
                          if not isinstance(child, exits) for n in loop.host.lab.cli.flow.local_nodes(child)
                          if isinstance(n, exits)]
                if nested:
                    raise control.Gap("control_unsupported")
            if isinstance(stmt, ast.For):
                # Independent guarded exits are conjunctive on every iteration. A
                # continue before a later exit would make the latter conditional.
                skipped = False
                for child in stmt.body:
                    nodes = list(loop.host.lab.cli.flow.local_nodes(child))
                    if skipped and any(isinstance(n, (ast.Return, ast.Raise)) for n in nodes):
                        raise control.Gap("control_unsupported")
                    skipped |= any(isinstance(n, ast.Continue) for n in nodes)
            after = super().fold([stmt], after, on_continue)
        return after


def compact(term):
    if type(term) is bool:
        return term
    op, *a = term
    if op == "test":
        return a[0]
    if op == "iteration":
        return [op, a[0]]
    if op in ("past", "all"):
        return [op, a[0], compact(a[2])]
    return [op, *(compact(t) for t in a)]


def atoms(term, scope=()):
    if type(term) is bool:
        return set()
    if type(term) is int:
        return {(*scope, abs(term))}
    op, *args = term
    if op == "iteration":
        return {(*scope, op, args[0])}
    if op in ("past", "all"):
        return atoms(args[1], (*scope, op, args[0]))
    return set().union(*(atoms(a, scope) for a in args))


def normalize(term):
    """Treat each quantifier as an atom identified by its loop and its truth table."""
    if not isinstance(term, list):
        return term
    op, *args = term
    if op in ("all", "past"):
        return (op, args[0], truth_signature(normalize(args[1])))
    if op == "iteration":
        return tuple(term)
    return [op, *(normalize(a) for a in args)]


def variables(term):
    if type(term) is bool:
        return set()
    if isinstance(term, list):
        return set().union(*(variables(a) for a in term[1:]))
    return {abs(term) if type(term) is int else term}


def truth(term, env):
    if type(term) is bool:
        return term
    if type(term) is int:
        return env[abs(term)] if term > 0 else not env[-term]
    if isinstance(term, tuple):
        return env[term]
    op, *args = term
    if op == "if":
        return truth(args[1] if truth(args[0], env) else args[2], env)
    if op == "not":
        return not truth(args[0], env)
    assert op == "and"
    return all(truth(t, env) for t in args)


def truth_signature(term):
    keys = sorted(variables(term), key=repr)
    assert len(keys) <= 14
    rows = {bits:truth(term, dict(zip(keys, bits))) for bits in product((False, True), repeat=len(keys))}
    needed = [i for i in range(len(keys)) if any(value != rows[bits[:i]+(not bits[i],)+bits[i+1:]]
                                                    for bits,value in rows.items())]
    table = {tuple(bits[i] for i in needed):value for bits,value in rows.items()}
    return tuple(keys[i] for i in needed), tuple(v for _,v in sorted(table.items()))


def generator(seed, raw):
    """Generate a new control tree, remembering its decisions while emitting lines."""
    rng = random.Random(seed)
    lines, cases = [], []
    def emit(line):
        lines.append(line)
        return len(raw.splitlines()) + len(lines)
    for i in range(12):
        name = "case_" + format(rng.getrandbits(40), "x")
        def cond():
            return "v_" + format(rng.getrandbits(32),"x")
        emit("")
        emit(f"def {name}(env):")
        refs = []
        def subtree(indent, depth):
            test = emit(indent + f"if env.{cond()}:")
            refs.append(test)
            if depth and rng.random() < .8:
                yes = subtree(indent+"    ",depth-1)
            else:
                refs.append(emit(indent+"    "+rng.choice(("return 1","raise ValueError('early')"))))
                yes = False
            normal_else = True
            if depth and rng.random() < .55:
                emit(indent+"else:")
                normal_else = subtree(indent+"    ",depth-1)
            return ["if",test,yes,normal_else]

        guards = subtree("    ",rng.choice((1,2,2)))
        if i % 2:
            cycle = emit("    for item in env.items:")
            skip = emit(f"        if item.{cond()}:")
            k = emit("            continue")
            stop = emit(f"        if item.{cond()}:")
            z = emit("            return 2")
            guards = ["and", guards, ["all",cycle,["if",skip,True,-stop]]]
            refs.extend([cycle, skip,k,stop,z])
        final = emit(f"    if env.{cond()}:")
        code = "OUT_" + format(rng.getrandbits(36),"X")
        line = emit(f"        raise ValueError('{code}')")
        cases.append(dict(id=f"G{i:02}",q="Почему возникает ошибка "+code+"?", selector=code,
                          target=[name,line], formula=["and",guards,final], refs=refs+[final,line]))
    return raw + ("\n".join(lines)+"\n").encode(), cases


def lexical(result, src, case):
    """Decode what 0.4 actually published. Require an exact legacy rendering and site."""
    if result["state"] != "answered" or len(result["claims"]) != 1 or "target" not in case:
        return None
    name, line = case["target"]
    fn = next((f for f in loop.host.lab.cli.flow.Slice(src).functions if f.node.name == name), None)
    if not fn:
        return None
    text = result["claims"][0]["text"]
    parents = {child:n for n in ast.walk(fn.node) for child in ast.iter_child_nodes(n)}
    hits = [n for n in parents if isinstance(n, ast.Raise) and n.lineno == line and ast.unparse(n) in text]
    if len(hits) != 1:
        return None
    terms = []
    n = hits[0]
    while n is not fn.node:
        parent = parents[n]
        if isinstance(parent, ast.If):
            terms.append(parent.test.lineno if n in parent.body else -parent.test.lineno)
        elif isinstance(parent, ast.For):
            terms.append(["iteration",parent.lineno])
        n = parent
    return ["and",*terms]


def grade(case, out, src, root):
    claims = out["claims"]
    refs = [r for claim in claims for r in claim["refs"]]
    old.verify_refs(root, src.commit, refs)
    row = dict(state=out["state"], reason=out.get("reason"), steps=out["steps"],
               claims=[dict(text=c["text"], refs=[[r["path"],r["start"],r["end"]] for r in c["refs"]])
                       for c in claims], missing=[], excess=[], wrong_logic=False)
    if "reason" in case:
        row["correct"] = not claims and out.get("reason") == case["reason"] and out["state"] == "insufficient"
        row["unwarranted"] = bool(claims)
        return row
    meta = out.get("control")
    actual = compact(meta["condition"]) if meta else lexical(out, src, case)
    row["formula"] = actual
    row["correct"] = False
    row["unwarranted"] = bool(claims) and actual is None
    if actual is None:
        return row
    gold = case["formula"]
    row["missing"] = sorted(map(str, atoms(gold)-atoms(actual)))
    row["excess"] = sorted(map(str, atoms(actual)-atoms(gold)))
    got, want = normalize(actual), normalize(gold)
    row["wrong_logic"] = truth_signature(got) != truth_signature(want)
    keys = sorted(variables(got) | variables(want), key=repr)
    assert len(keys) <= 16
    row["unwarranted"] = any(truth(want,env) and not truth(got,env)
                             for bits in product((False,True),repeat=len(keys)) for env in [dict(zip(keys,bits))])
    name, line = case["target"]
    owners = [f for f in loop.host.lab.cli.flow.Slice(src).functions if f.node.name == name]
    fn, = owners
    identity = not meta or (meta["path"],meta["function"],meta["line"]) == (fn.path,name,line)
    coverage = all(archive.prior_eval.anchored(refs,fn.path,n) for n in [line,fn.node.lineno,*case["refs"]])
    row["correct"] = bool(identity and coverage and not row["wrong_logic"] and out["state"] == "answered")
    return row


def run(plan, temp, decisions, live):
    root = temp/"fixture"
    pilot.git("clone","--quiet","--local","--no-checkout",str(pilot.ROOT),str(root))
    archive.set_head(root,BASE)
    prev = archive.pinned_host(temp, "core04", BASE)
    src, ground = loop.read_head(root)
    raw,_ = old.blob(root,BASE,old.RANK)
    generated, extra = generator(int(plan["implementation"][:8],16),raw)
    rows, times, info = [], {}, {}
    with ExitStack() as stack:
        import runtime289  # verified by read_head before loading the local provider
        provider = None
        def language(question):
            nonlocal provider
            if not live:
                return decisions[question]
            if provider is None:
                profile = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="skynet-control-intent-")))
                provider = stack.enter_context(runtime289.LocalProvider(profile))
            decision = loop.causal.classify(question, provider.complete)
            decisions[question] = decision
            return decision
        for i,case in enumerate([*plan["cases"],*extra]):
            if i == len(plan["cases"]):
                archive.prior_eval.checkout_fixture(root,BASE,generated)
                src,ground = loop.read_head(root)
            opts = dict(opener=lambda _: (src,ground))
            row = dict(id=case["id"],q=case["q"],commit=src.commit,positive="reason" not in case)
            times[case["id"]] = {}
            offset = i % len(ARMS)
            for arm in ARMS[offset:]+ARMS[:offset]:
                start = perf_counter()
                if arm == "core04":
                    answer = prev.investigate(case["q"],root,**opts)
                elif arm == "guards":
                    answer = loop.investigate(case.get("selector",case["q"]),root,why=True,proof_type=Guards,
                                              classifier=lambda _:False,**opts)
                else:
                    answer = loop.investigate(case["q"],root,why=True,
                                              classifier=language if arm=="core05" else lambda _:False,**opts)
                times[case["id"]][arm] = round((perf_counter()-start)*1000,1)
                row[arm] = grade(case,answer,src,root)
            rows.append(row)
        if provider:
            info = dict(calls=provider.calls, startup_seconds=provider.info["startup_seconds"],
                        model_sha256=runtime289.MODEL_SHA256, runtime_sha256=runtime289.RUNTIME_SHA256)
    if provider:
        info["stopped"] = provider.info["stopped"]
    archive.set_head(root,BASE)
    src,ground = loop.read_head(root)
    opts = dict(opener=lambda _: (src,ground),why=True)
    sample = "_include@65"
    cited = loop.host.lab.cli.calls.cited
    with patch.object(loop.host.lab.cli.calls,"cited",lambda *args:dict(cited(*args),url="unissued")):
        bad = loop.investigate(sample,root,**opts)
        assert (bad["state"],bad["reason"],bad["claims"]) == ("failed","invalid_reference",[])
    with patch.object(loop.host.lab.cli.calls,"cited",lambda *args:dict(cited(*args),start=0)):
        bad = loop.investigate(sample,root,**opts)
        assert bad["reason"] == "endpoint_binding" and not bad["claims"]
    def switched(question):
        archive.set_head(root,BASE+"^")
        return True
    stale = loop.investigate("Разбери "+sample,root,classifier=switched,**opts)
    assert stale.get("reason") == "stale_snapshot" and not stale["claims"]
    archive.set_head(root,BASE)
    budget = loop.investigate(sample,root,steps=1,**opts)
    assert budget["reason"] == "step_budget" and not budget["claims"]
    return rows, times, info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode",choices=("record","verify"))
    parser.add_argument("--live-model",action="store_true")
    args = parser.parse_args()
    plan = json.loads((DIR/"transfer.json").read_text(encoding="utf8"))
    path = DIR/"results.json"
    saved = json.loads(path.read_text(encoding="utf8")) if args.mode=="verify" else {}
    decisions = dict(saved.get("intent",{}))
    live = args.mode=="record" or args.live_model
    with tempfile.TemporaryDirectory(prefix="skynet-control-") as temp:
        rows,ms,model = run(plan,Path(temp),decisions,live)
    if args.mode=="record":
        pilot.dump(path,dict(rows=rows,ms=ms,intent=decisions,model=model))
    else:
        assert rows==saved["rows"] and decisions==saved["intent"]
    for prefix in ("T","G","R"):
        group = [r for r in rows if r["id"].startswith(prefix)]
        print(prefix,len(group), {arm:sum(r[arm]["correct"] for r in group) for arm in ARMS})
    print("Model calls in this run:",model.get("calls",0),"; integrity controls: 4/4")


if __name__ == "__main__":
    main()
