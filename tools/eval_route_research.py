"""Replay public answers on frozen Git objects, scoring calls, local formulas and bindings."""
import argparse
import ast
import json
from pathlib import Path
from statistics import median
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_control_conditions as controls
from eval_route_fixtures import suite

archive, loop, old, pilot = controls.archive, controls.loop, controls.old, controls.pilot
BASE = "7b0dab53f726e649e4b3bbd899391c97a2269b7d"
FROZEN_CASES = "a8db74b80aa8a389e3d3611f2350d63c76a91804:docs/maintenance/core_06/transfer.json"
DIR = pilot.ROOT / "docs/maintenance/core_06"
ARMS = ("core05", "first", "lazy", "eager", "adaptive")
PATHS = {"R":old.RANK, "S":old.SYMBOL, "T":old.TITLE, "C":pilot.CS, "G":pilot.PREFIX+"git_source.py"}


def inspect_answer(case, out, root, src):
    claims = out["claims"]
    refs = [ref for c in claims for ref in c["refs"]]
    old.verify_refs(root, src.commit, refs)
    def covered(path, line, items):
        return any(r["path"] == path and r["start"] <= line <= r["end"] for r in items)

    expected = case["expect"]
    verdict = out.get("research", {}).get("verdict", "legacy" if claims else "unproven")
    checks = {}
    for path, lines in case.get("refs", {}).items():
        for line in lines:
            checks[f"{path}:{line}"] = covered(PATHS[path], line, refs)
    definitions = [(path,n) for path in src.pages for n in ast.parse(src.snapshot.sources[path]).body
                   if isinstance(n, ast.FunctionDef)]
    functions = {fn.name:fn for _,fn in definitions}
    for caller, callee, line in case.get("edges", []):
        path, = [p for p,fn in definitions if fn.name==caller and fn.lineno<=line<=fn.end_lineno]
        checks[f"{caller}@{line}->{callee}"] = any(c.get("edge")==[caller,callee] and covered(path,line,c["refs"])
                                                   for c in claims)
    for owner, line, formula in case.get("controls", []):
        good = False
        for claim in claims:
            if claim["text"].startswith(f"В {owner} исследована инструкция ") and f"(стр. {line}). " in claim["text"]:
                actual = controls.displayed(claim["text"], functions[owner], line)
                good |= controls.truth_signature(controls.normalize(actual)) == controls.truth_signature(controls.normalize(formula))
        checks[f"условие {owner}@{line}"] = good
    text = "\n".join(c["text"] for c in claims)
    for word in case.get("text", []):
        checks[word] = word in text

    if expected == "unproven":
        decision = not claims and out.get("reason") in case["reasons"]
        checks = {}
    else:
        decision = verdict == expected and bool(claims)
        if expected == "excluded_route":
            decision &= "Этот вариант перехода исключён." in text and out["state"]=="partial"
        if expected == "conditional_route":
            decision &= out["state"]=="answered"
        # Historical partial evidence can support a conclusion too. A route to
        # an outcome is not a claim of observed execution or joint feasibility.
        if verdict == "legacy" and expected == "conditional_route":
            decision = (all(checks[f"{a}@{n}->{b}"] for a,b,n in case.get("edges",[]))
                        and bool(case.get("text")) and case["text"][-1] in text)
    portable = dict(state=out["state"],reason=out.get("reason"),plan=out["plan"],trace=out["steps"],
                    research=out.get("research"),observations=[])
    for c in claims:
        portable["observations"].append(dict(text=c["text"],refs=[
            [next(k for k,p in PATHS.items() if p==r["path"]),r["start"],r["end"]] for r in c["refs"]]))
    return dict(decision=bool(decision),full=bool(decision and all(checks.values())),
                facts=sum(checks.values()),needed=len(checks),missing=[k for k,v in checks.items() if not v],
                cited=len(refs),answer=portable)


def integrity(root, src, ground):
    opts = dict(opener=lambda _: (src,ground), research_mode=True)
    q = "rank -> M127_TOP_LIMIT_INVALID"
    def denied(reason, **kwargs):
        ans = loop.investigate(q,root,**opts,**kwargs)
        assert (ans.get("reason"), ans["claims"]) == (reason, []), ans
        return reason
    cited = loop.host.lab.cli.calls.cited
    checks = []
    for key, val, reason in (("url","wrong","invalid_reference"),("start",0,"endpoint_binding")):
        with patch.object(loop.host.lab.cli.calls,"cited",lambda *args:dict(cited(*args),**{key:val})):
            checks.append(denied(reason))
    checks.append(denied("step_budget",steps=1))
    def switch(*args):
        raw = loop.host.lab.cli.calls.lookup(*args)
        archive.set_head(root, BASE+"^")
        return raw
    try:
        checks.append(denied("stale_snapshot",lookup=switch))
    finally:
        archive.set_head(root, BASE)
    return checks


def run(plan, temp):
    root = temp/"fixture"
    pilot.git("clone","--quiet","--local","--no-checkout",str(pilot.ROOT),str(root))
    archive.set_head(root, BASE)
    prev = archive.pinned_host(temp,"accepted_05",BASE)
    raw, _ = old.blob(root,BASE,old.RANK)
    trials = [(None,c) for c in plan["cases"]]
    trials.extend(suite(int(plan["implementation"][:16],16),raw))
    rows, times = [], {}
    for i,(fixture,case) in enumerate(trials):
        if fixture is not None:
            archive.prior_eval.checkout_fixture(root,BASE,fixture)
        src, ground = loop.read_head(root)
        opts = dict(opener=lambda _: (src,ground))
        row = dict(id=case["id"],q=case["q"],expected=case["expect"],commit=src.commit)
        times[case["id"]] = {}
        arms = ARMS[i%len(ARMS):]+ARMS[:i%len(ARMS)]
        for arm in arms:
            start = perf_counter()
            if arm == "core05":
                out = prev.investigate(case["q"],root,**opts)
            else:
                out = loop.investigate(case["q"],root,research_mode=True,research_policy=arm,**opts)
            times[case["id"]][arm] = round(1000*(perf_counter()-start),1)
            row[arm] = inspect_answer(case,out,root,src)
            assert len(out["steps"]) <= loop.MAX_STEPS
            assert not any(s["tool"] == "classify_intent" or "model" in s["tool"] or "qwen" in s["tool"]
                           for s in out["steps"]), out["steps"]
        rows.append(row)
    archive.set_head(root,BASE)
    return rows,times,integrity(root,*loop.read_head(root))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record","verify"))
    args = parser.parse_args()
    plan = json.loads(pilot.git("show",FROZEN_CASES))
    with tempfile.TemporaryDirectory(prefix="skynet-route-") as tmp:
        rows,times,checks = run(plan,Path(tmp))
    dest = DIR/"results.json"
    if args.mode == "record":
        with dest.open("x",encoding="utf8",newline="\n") as f:
            json.dump(dict(rows=rows,ms=times,integrity=checks),f,ensure_ascii=False,separators=(",",":"))
            f.write("\n")
    else:
        saved = json.loads(dest.read_text(encoding="utf8"))
        assert (rows,checks)==(saved["rows"],saved["integrity"])
    for prefix in ("T","G"):
        group = [r for r in rows if r["id"].startswith(prefix)]
        for arm in ARMS:
            stats = [r[arm] for r in group]
            print(prefix,arm,"full",sum(s["full"] for s in stats),"/",len(stats),
                  "decision",sum(s["decision"] for s in stats),"facts",sum(s["facts"] for s in stats),
                  "/",sum(s["needed"] for s in stats),"median ms",median(times[r["id"]][arm] for r in group))
    print("Integrity:",checks)


if __name__ == "__main__":
    main()
