"""Freeze the interpreter or its bindings while changing only the collection strategy."""
import argparse
import ast
from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_scope_graph as prior

ev, runner = prior.ev, prior.runner
DIR = prior.DIR.parent/"core_16"
FREE = ("scope_graph","scope_nearest","joint_order","joint_cheapest","joint_plan")
ARMS = FREE + tuple("oracle_"+arm for arm in FREE)
SEARCH = ev.loop.arguments.Search
REQ = prior.parts.req


def measured(host, cases, panel, offset):
    def run(q, root, *, discovery, **kw):
        oracle = discovery.startswith("oracle_")
        arm = discovery.removeprefix("oracle_")
        counts = Counter()
        sources = frozenset(kw["opener"](root)[0].snapshot.sources.values())
        def instrument(stack, obj, name, key):
            original = getattr(obj,name)
            def counted(*args, **kwargs):
                counts[key] += 1
                return original(*args, **kwargs)
            stack.enter_context(patch.object(obj,name,counted))

        def selected(question,root,**options):
            options["discovery"]=arm
            return host(question,root,**options)
        observe = prior.observe(selected,cases,panel,offset)
        budget, parse, incoming = SEARCH.check_budget, ast.parse, SEARCH.incoming
        def audit(search):
            counts["peak_items"]=max(counts["peak_items"],len(search.items))
            products=getattr(search,"products",None)
            if products:
                counts["tree_hits"]=products.reused_trees
                counts["argument_hits"]=products.hits
                counts["argument_products"]=len(products.arguments)
            return budget(search)
        def parsing(source,*args,**kwargs):
            if isinstance(source,str) and source in sources:
                counts["file_parses"]+=1
            return parse(source,*args,**kwargs)
        def incoming_sites(search,target):
            if target in search.cache:
                counts["incoming_hits"]+=1
            return incoming(search,target)
        with ExitStack() as stack:
            stack.enter_context(patch.object(SEARCH,"check_budget",audit))
            stack.enter_context(patch.object(ast,"parse",parsing))
            stack.enter_context(patch.object(SEARCH,"incoming",incoming_sites))
            calls=ev.loop.arguments.cli.calls
            instrument(stack,calls,"_lookup_trees","scans")
            instrument(stack,calls,"signature","signatures")
            instrument(stack,REQ.observed.route.facts,"bind","rebinds")
            instrument(stack,REQ.observed.route.control,"claim","conditions")
            out=observe(q,root,discovery="known_links" if oracle else arm,**kw)
        out["work"]=dict(counts)
        assert counts["peak_items"]<=96 and len(out["steps"])<=6
        return out
    return run


def grade(case,out,panel,src,root,offset):
    rec=prior.grade(case,out,panel,src,root,offset)
    static=[s for s in rec["scores"] if "joint" in s]
    delivered=sum(s["delivered"] for s in static)
    wrong=0
    obtained=[]
    for (cue,t,k),s in zip(case[2],rec["scores"],strict=True):
        parts=out.get("parts",[])
        if not parts:
            continue
        part=parts[prior.old.place(case[1],cue,parts)]
        if t=="-":
            wrong+=bool(part["relation"]["direct"])
            continue
        if s["delivered"]:
            obtained.append(t+"/"+k)
        if part["relation"]["kind"]==k and part["relation"]["direct"] and not s["delivered"]:
            wrong+=1
    rec.update(obtained=sorted(obtained),wrong_direct=wrong,kept_partial=bool(out["state"]=="partial" and
               delivered and any(p["issues"] for p in out["parts"])))
    return rec


def metrics(rows,ms,panel,arm):
    m=prior.summarize(rows,ms,panel,arm)
    records={r["id"]:r[arm] for r in rows}
    work=Counter()
    peak=0
    for r in records.values():
        c=dict(r["answer"]["work"])
        peak=max(peak,c.pop("peak_items"))
        work.update(c)
    return dict(m,work=dict(work),peak_items=peak,
                kept_partial=sum(r["kept_partial"] for r in records.values()),
                wrong_direct=sum(r["wrong_direct"] for r in records.values()),
                published_claims=sum(len(r["answer"]["claims"]) for r in records.values()),
                order_differences=[pair for pair in panel.get("permutations",[])
                    if records[pair[0]]["obtained"]!=records[pair[1]]["obtained"]])


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("record","verify"))
    p.add_argument("panel",choices=("transfer","history"))
    args=p.parse_args()
    if args.panel=="history":
        path=prior.DIR/"transfer.json"
    else:
        path=DIR/"transfer.json"
    panel=json.loads(path.read_text(encoding="utf8"))
    if args.panel=="history":
        panel["cases"]=[c for c in panel["cases"] if c[0] in ("R2","D3")]
        panel["contrasts"]=[]
    cases={c[1]:c for c in panel["cases"]}
    offset=len(ev.old.blob(ev.pilot.ROOT,panel["base"],ev.old.RANK)[0].splitlines())
    wrap=measured(ev.loop.investigate,cases,panel,offset)
    with tempfile.TemporaryDirectory() as tmp, patch.object(ev.loop,"investigate",wrap), patch.object(runner,"grade",grade):
        rows,ms,sessions=runner.run(Path(tmp),panel,False,{},ARMS)
    assert not sessions and not any(r[a]["calls"] for r in rows for a in ARMS)
    dest=DIR/(args.panel+"_results.json")
    if args.mode=="verify":
        saved=json.loads(dest.read_text(encoding="utf8"))
        ms=saved["ms"]
    result=dict(panel_blob=ev.pilot.git("hash-object",str(path)).decode().strip(),rows=rows,ms=ms,
                metrics={a:metrics(rows,ms,panel,a) for a in ARMS})
    if args.mode=="verify":
        assert result==saved
    else:
        with dest.open("x",encoding="utf8",newline="\n") as stream:
            json.dump(result,stream,ensure_ascii=False,indent=1)
            stream.write("\n")
    for arm,m in result["metrics"].items():
        print(arm,m["full"],m["facts"],m["steps"],m["work"],m["median_ms"])


if __name__=="__main__":
    main()
