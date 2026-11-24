"""Matched evaluation of goal selection, cited facts and verified static relations."""
import argparse
import ast
from contextlib import nullcontext
import json
from pathlib import Path
from statistics import median
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_observation_goals as ev
import skynet_source_language as language

PLAN = "606b0d126de3df47085985da3330607092d0f0ab:docs/maintenance/core_08/transfer.json"
SECOND = "8856d8fec59b3fa15d0a5d134840e3bde95a01f3:docs/maintenance/core_08/transfer_2.json"
DIR = ev.pilot.ROOT / "docs/maintenance/core_08"
ARMS = ("checked", "lexical", "syntax", "captions", "caption_join", "explore")
SECOND_ARMS = ("checked", "site", "syntax", "explore", "pooled", "facets")


def fixture_case(case, offset):
    c = dict(case)
    def shifted(term):
        if isinstance(term,list):
            return [term[0],*(shifted(t) for t in term[1:])]
        if type(term) is bool:
            return term
        return term+offset if term>0 else term-offset
    if "line" in c:
        c.update(line=c["line"]+offset, refs=[v+offset for v in c["refs"]])
        c["controls"] = [[name,line+offset, shifted(term)]
                         for name,line,term in c.get("controls",[])]
    if "marks" in c:
        c["marks"] = [[p,line+offset] for p,line in c["marks"]]
        c["must"] = {p:[n+offset for n in ns] for p,ns in c["must"].items()}
    return c


def measure(case, out, src, root):
    claims = out["claims"]
    refs = [r for cl in claims for r in cl["refs"]]
    ev.old.verify_refs(root,src.commit,refs)
    meta = out.get("discovery",{})
    for option in meta.get("options",[]):
        ev.old.verify_refs(root,src.commit,[option["ref"]])
    def covers(path, line, subset=refs):
        return any(r["path"]==ev.previous.PATHS[path] and r["start"]<=line<=r["end"] for r in subset)
    def expression(path, line, owner):
        tree = ast.parse(src.snapshot.sources[ev.previous.PATHS[path]])
        fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==owner)
        values = {ast.unparse(n) for n in ast.walk(fn) if isinstance(n,(ast.Constant,ast.JoinedStr))
                  and n.lineno == line}
        return any(owner in cl["text"] and f"строке {line} записано выражение" in cl["text"]
                   and any(v in cl["text"] for v in values) and covers(path,line,cl["refs"]) for cl in claims)
    if "reasons" in case:
        full = not claims and out.get("reason") in case["reasons"]
        return dict(goal=None, conclusion=None, obligations=[], complete_evidence=None,
                    full=full, false_publication=bool(claims), false_claim=bool(claims))
    if "edge" in case:
        goal = meta.get("action")=="connect" and all(covers(p,n) for p,n in case["marks"])
        edge = any(cl.get("edge")==case["edge"] for cl in claims)
        statements = [expression(p,n,owner) for (p,n),owner in zip(case["marks"],case["edge"],strict=True)]
        conclusion = edge and all(statements) and out.get("execution_observed") is False
        parts = {f"{p}:{n}":covers(p,n) for p,ns in case["must"].items() for n in ns}
        parts["direct_edge"] = edge
    else:
        located = (meta.get("owner")==case["owner"] and meta.get("line")==case["line"] and
                   covers(case["path"],case["line"]) and any(case["owner"] in cl["text"] for cl in claims))
        goal = meta.get("action")==case["action"] and located
        parts = {f"{case['path']}:{n}":covers(case["path"],n) for n in case["refs"]}
        parts.update({f"{p}:{n}":covers(p,n) for p,ns in case.get("other_refs",{}).items() for n in ns})
        conclusion = expression(case["path"],case["line"],case["owner"])
        extra = []
        if "binding" in case:
            extra.append(any(case["binding"] in cl["text"] for cl in claims))
        functions = {fn.name:fn for body in src.snapshot.sources.values() for fn in ast.parse(body).body
                     if isinstance(fn,ast.FunctionDef)}
        controls = ev.previous.controls
        def signature(term):
            return controls.truth_signature(controls.normalize(term))
        for name,line,expected in case.get("controls",[]):
            # An earlier exit may mention this line inside a proof for another instruction.
            # Parse the displayed predicate only for the exact instruction header.
            fn = functions[name]
            headers = tuple(f"В {name} исследована инструкция "+chr(96)+ast.unparse(n)+chr(96)+f" (стр. {line}). "
                            for n in ast.walk(fn) if isinstance(n,ast.stmt) and n.lineno==line)
            extra.append(any(signature(controls.displayed(cl["text"],fn,line))==signature(expected)
                             for cl in claims if cl["text"].startswith(headers)))
        if "caller" in case:
            extra.append(any(cl.get("edge")==[case["caller"],case["owner"]] for cl in claims))
        parts.update({f"semantic_{i}":v for i,v in enumerate(extra)})
        conclusion = conclusion and all(extra)
        if "binding" in case:
            bindings = next((cl["text"] for cl in claims if cl.get("edge")==[case["caller"],case["owner"]]),"")
            call = next(n for n in ast.walk(ast.parse(src.snapshot.sources[ev.previous.PATHS["R"]]))
                        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==case["owner"])
            fn = next(n for n in ast.parse(src.snapshot.sources[ev.previous.PATHS[case["path"]]]).body
                      if isinstance(n,ast.FunctionDef) and n.name==case["owner"])
            expected = [(arg.arg,ast.unparse(val)) for arg,val in zip(fn.args.args,call.args)]
            expected.extend((kw.arg,ast.unparse(kw.value)) for kw in call.keywords)
            parts["all_arguments"] = all(f"{k} ← "+chr(96)+v+chr(96) in bindings for k,v in expected)
            conclusion = conclusion and parts["all_arguments"]
    complete = all(parts.values())
    full = bool(goal and conclusion and complete and out["state"]=="answered")
    return dict(goal=bool(goal), conclusion=bool(conclusion), obligations=parts, complete_evidence=complete,
                full=full,false_publication=out["state"]=="answered" and not full,
                false_claim=bool(claims and not (goal or conclusion)))


def controls(root, src, ground):
    loop = ev.loop
    opts = dict(opener=lambda _:(src,ground), discovery="explore")
    q = "Есть ли вызов между «M127_TOP_LIMIT_INVALID» и «M130_OLD_TREE_EMPTY»?"
    def check(reason, **kw):
        out = loop.investigate(q,root,**opts,**kw)
        assert out.get("reason")==reason and not out["claims"], out
        return out["reason"]
    small = check("step_budget",steps=2)
    cited = loop.host.lab.cli.calls.cited
    with patch.object(loop.host.lab.cli.calls,"cited",lambda *a:dict(cited(*a),url="unissued")):
        forged = check("invalid_reference")
    lookup = loop.host.lab.cli.calls.lookup
    def switch(*args):
        ev.archive.set_head(root, src.commit+"^")
        return lookup(*args)
    try:
        stale = check("stale_snapshot",lookup=switch)
    finally:
        ev.archive.set_head(root,src.commit)
    return dict(short_budget=small, bad_reference=forged, changed_head=stale)


def interpretation_controls(root, src, ground):
    """Exercise the provider boundary even when a local model is unavailable."""
    opts=dict(opener=lambda _:(src,ground),discovery="facets")
    question="Где неизвестное особое явление?"
    def run(q, select, reason):
        result=ev.loop.investigate(q,root,select=select,**opts)
        assert result.get("reason")==reason and not result["claims"], result
        return reason
    replies=[]
    def invalid(prompt,user):
        assert user==question and "scan_head" not in prompt
        replies.append(user)
        return '{"op":"read","file":"outside.py"}',dict(finish_reason="stop")
    bad=run(question,invalid,"observation_ambiguous")
    def switched(prompt,user):
        ev.archive.set_head(root,src.commit+"^")
        return ('{"op":"where","a":{"object":"hypothesis","detail":"example"},"b":null}',
                dict(finish_reason="stop"))
    try:
        stale=run(question,switched,"stale_snapshot")
    finally:
        ev.archive.set_head(root,src.commit)
    denied=run("Где в modules/nonexistent.py неизвестное явление?",invalid,"out_of_scope")
    assert replies==[question]
    return dict(bad_model_schema=bad,stale_after_interpreter=stale,scope_before_interpreter=denied)


def run(temp, plan, cache, live, arms):
    root = temp/"repo"
    ev.pilot.git("clone","--quiet","--local","--no-checkout",str(ev.pilot.ROOT),str(root))
    base = plan["source"]
    ev.archive.set_head(root,base)
    prior = ev.archive.pinned_host(temp,"core07",base)
    raw,_ = ev.old.blob(root,base,ev.old.RANK)
    captures = []
    def read():
        t = perf_counter()
        obj = ev.loop.read_head(root)
        captures.append(round(1000*(perf_counter()-t),1))
        return obj
    src,ground = read()
    guards = controls(root,src,ground)
    model = ev.Generations(temp,cache,live)
    preexisting = set(cache)
    rows,elapsed = [],{}
    try:
        for i,case in enumerate(plan["cases"]):
            if case["id"].startswith("F"):
                if src.commit==base:
                    added = ("\n".join(plan["fixture"])+"\n").encode()
                    ev.archive.prior_eval.checkout_fixture(root,base,raw+added)
                    src,ground = read()
                case = fixture_case(case,len(raw.splitlines()))
            row = dict(id=case["id"],question=case["q"],commit=src.commit)
            elapsed[case["id"]] = {}
            for arm in arms[i%len(arms):]+arms[:i%len(arms)]:
                model.key,model.used = case["id"]+"/"+arm,0
                model.live = live and model.key not in preexisting
                if arm in ("checked","site","pooled","facets"):
                    model.prepare()
                opts=dict(opener=lambda _:(src,ground),select=model.select)
                arm_host = prior if arm in ("lexical","checked") else ev.loop
                context = nullcontext()
                policy = arm
                if arm=="caption_join":
                    context = patch.object(language,"features",return_value=dict(language.features(),aliases={}))
                    policy = "explore"
                start = perf_counter()
                with context:
                    out = arm_host.investigate(case["q"],root,discovery=policy,**opts)
                elapsed[case["id"]][arm] = round(1000*(perf_counter()-start),1)
                assert len(out["steps"])<=6 and not model.replay_errors
                assert all(s["tool"]!="classify_intent" for s in out["steps"])
                # Preserve the original decision and range IDs. URLs are reconstructed from
                # path + snapshot, including for the unpushed synthetic commit.
                row[arm] = dict(**measure(case,out,src,root),calls=model.used,answer=ev.portable(out))
            rows.append(row)
    finally:
        model.stack.close()
    return rows,elapsed,dict(snapshot_ms=captures,sessions=model.sessions),guards


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("record","verify","guards"))
    p.add_argument("--file",type=Path)
    p.add_argument("--second",action="store_true")
    p.add_argument("--reuse",type=Path,help="Resume using issued model responses after a recorder failure")
    p.add_argument("--timings-file",type=Path,help="Save measured host times on replay with generation excluded")
    args=p.parse_args()
    live=args.mode=="record"
    plan_id = SECOND if args.second else PLAN
    arms = SECOND_ARMS if args.second else ARMS
    args.file = args.file or DIR/("results_2.json" if args.second else "results.json")
    if live and args.file.exists():
        p.error("Choose a new file for a live recording")
    plan=json.loads(ev.pilot.git("show",plan_id))
    if args.mode=="guards":
        with tempfile.TemporaryDirectory(prefix="skynet-boundary-") as tmp:
            repo=Path(tmp)/"repo"
            ev.pilot.git("clone","--quiet","--local","--no-checkout",str(ev.pilot.ROOT),str(repo))
            ev.archive.set_head(repo,plan["source"])
            src,ground=ev.loop.read_head(repo)
            print({**controls(repo,src,ground),**interpretation_controls(repo,src,ground)})
        return
    saved={} if live else json.loads(args.file.read_text(encoding="utf8"))
    cache=saved.get("generations",{})
    reused=[]
    if args.reuse:
        if not live or not args.second:
            p.error("--reuse requires record --second")
        cache=json.loads(args.reuse.read_text(encoding="utf8"))
        reused=sorted(cache)
    if args.timings_file and live:
        p.error("--timings-file requires verify")
    try:
        with tempfile.TemporaryDirectory(prefix="skynet-semantic-") as tmp:
            rows,elapsed,cost,guards=run(Path(tmp),plan,cache,live,arms)
    except Exception:
        if live and cache:
            with tempfile.NamedTemporaryFile(prefix="interrupted-",suffix=".json",dir=args.file.parent,
                                             delete=False,mode="w",encoding="utf8") as f:
                json.dump(cache,f,ensure_ascii=False,indent=1)
        raise
    if live:
        if reused:
            cost["reused_model_responses"]=reused
        with args.file.open("x",encoding="utf8",newline="\n") as f:
            json.dump(dict(plan=plan_id,rows=rows,ms=elapsed,cost=cost,guards=guards,generations=cache),
                      f,ensure_ascii=False,indent=1)
            f.write("\n")
    else:
        assert rows==saved["rows"] and guards==saved["guards"] and saved["plan"]==plan_id
        if args.timings_file:
            with args.timings_file.open("x",encoding="utf8",newline="\n") as f:
                json.dump(dict(ms=elapsed,source_read_ms=cost["snapshot_ms"]),f,indent=1)
                f.write("\n")
        elapsed=saved["ms"]
    print("arm | goal | conclusion | evidence | correct | wrong publication | median online ms")
    for arm in arms:
        print(arm,*[sum(bool(row[arm][k]) for row in rows) for k in
              ("goal","conclusion","complete_evidence","full","false_publication")],
              round(median(row[arm] for row in elapsed.values()),1),sep=" | ")


if __name__=="__main__":
    main()
