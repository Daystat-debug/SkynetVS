"""Replay two separately scored experiments on a pinned five-file snapshot."""
import argparse
import ast
import json
from pathlib import Path
from statistics import median
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_source_language as prior
import skynet_requirements as req

ev = prior.ev
PLAN = "53eab6faf23eecef27351102ff040ed92b2cba6c:docs/maintenance/core_09/transfer.json"
DIR = ev.pilot.ROOT/"docs/maintenance/core_09"
ARMS = ("grounded","one_action","all_evidence","requirements")


def assess(out, target, wanted, root, src, limited):
    p,owner,line,label,predicate,caller,cp,call,caller_pred,bindings,loc,edge = target
    cs=out["claims"]
    refs=[r for c in cs for r in c["refs"]]
    ev.old.verify_refs(root,src.commit,refs)
    for option in out.get("discovery",{}).get("options",[]):
        ev.old.verify_refs(root,src.commit,[option["ref"]])
    def covers(c,code,lines):
        return all(any(r["path"]==ev.previous.PATHS[code] and r["start"]<=n<=r["end"]
                       for r in c["refs"]) for n in lines)
    def condition(code,name,n,term):
        if not name:
            return False
        fn=next(f for f in ast.parse(src.snapshot.sources[ev.previous.PATHS[code]]).body
                if isinstance(f,ast.FunctionDef) and f.name==name)
        controls=ev.previous.controls
        def sig(t):
            return controls.truth_signature(controls.normalize(t))
        for c in cs:
            ctrl=c.get("control",{})
            if ctrl.get("function")==name and ctrl.get("line")==n and covers(c,code,[n]):
                if sig(controls.displayed(c["text"],fn,n))==sig(term):
                    return True
        return False
    site=any(owner in c["text"] and label in c["text"] and covers(c,p,loc) for c in cs)
    facts=dict(site=site,condition=condition(p,owner,line,predicate),
          caller=bool(caller and any(c.get("edge")==[caller,owner] and covers(c,cp,edge) for c in cs)),
          arguments=bool(bindings and any(all(b in c["text"] for b in bindings) and covers(c,cp,edge)
                                         for c in cs)),caller_condition=condition(cp,caller,call,caller_pred))
    missing=[k for k in wanted if not facts[k]]
    sufficient=bool(wanted and not missing)
    solved=sufficient and out["state"]=="answered"
    if limited:
        handled=out["state"]=="partial" and facts["site"] and missing==["caller"] and (
            out.get("requirements",{}).get("gaps",{}).get("caller")=="path_unproven" or
            out.get("discovery",{}).get("gap")=="path_unproven")
    elif not wanted:
        handled=not cs and out.get("reason") in ("clarification","observation_ambiguous","observation_required")
    else:
        handled=solved
    return dict(facts=facts,sufficient=sufficient,solved=solved,handled=handled,
                false_publication=out["state"]=="answered" and not solved)


def run(tmp, plan, live, cache, projection=False):
    root=tmp/"repo"
    ev.pilot.git("clone","--quiet","--local","--no-checkout",str(ev.pilot.ROOT),str(root))
    ev.archive.set_head(root,plan["base"])
    src,ground=ev.loop.read_head(root)
    model=ev.Generations(tmp,cache,live)
    rows,times=[],{}
    def prepare(key):
        model.key,model.used=key,0
        model.prepare()
    try:
        for i,(key,t,template,labels,*words) in enumerate(plan["cases"]):
            target=plan["targets"][t]
            q=template.format(x=words[0] if words else "«"+target[3]+"»")
            known=template.format(x="ОБЪЕКТ")
            wanted=labels.split()
            prepare(key+"/oracle")
            try:
                prediction=list(req.interpret(known,model.select))
            except req.Gap as exc:
                prediction=[str(exc)]
            op=prior.language.operation(known)
            simple=list(req.closure({"where":["site"],"when":["condition"],"via":["arguments","condition","caller_condition"]}.get(op,[])))
            row=dict(id=key,question=q,oracle=dict(requirements=prediction,one_action=simple,all_evidence=list(req.KINDS)),wanted=wanted)
            times[key]={}
            arms=(("eager_projection","requirements") if projection else ARMS)
            shift=i%len(arms)
            for arm in arms[shift:]+arms[:shift]:
                prepare(key+"/"+("requirements" if arm=="eager_projection" else arm))
                start=perf_counter()
                out=ev.loop.investigate(q,root,opener=lambda _:(src,ground),discovery=arm,select=model.select)
                times[key][arm]=round((perf_counter()-start)*1000,1)
                assert not model.replay_errors and len(out["steps"])<=6
                row[arm]=dict(**assess(out,target,wanted,root,src,key=="C3"),calls=model.used,
                              answer=ev.portable(out))
            rows.append(row)
    finally:
        model.stack.close()
    opts=dict(discovery="requirements",opener=lambda _:(src,ground),
              select=lambda *_:('{"need":["condition","arguments"]}',dict(finish_reason="stop")))
    q="Когда появляется «M126_QUERY_INVALID»?"
    partial=ev.loop.investigate(q,root,steps=2,**opts)
    assert partial["state"]=="partial" and partial["requirements"]["missing"]==["condition","caller","arguments"]
    cited=ev.loop.host.lab.cli.calls.cited
    with patch.object(ev.loop.host.lab.cli.calls,"cited",lambda *a:dict(cited(*a),url="forged")):
        bad=ev.loop.investigate(q,root,**opts)
        assert bad["reason"]=="invalid_reference" and not bad["claims"]
    def switched(*_):
        ev.archive.set_head(root,plan["base"]+"^")
        return '{"need":["site"]}',dict(finish_reason="stop")
    try:
        stale=ev.loop.investigate(q,root,**dict(opts,select=switched))
        assert stale.get("reason")=="stale_snapshot" and not stale["claims"]
    finally:
        ev.archive.set_head(root,plan["base"])
    called=[]
    denied=ev.loop.investigate("Где в modules/elsewhere.py эта строка?",root,
                               **dict(opts,select=lambda *_:called.append(True)))
    assert denied.get("reason")=="out_of_scope" and not called and not denied["claims"]
    return rows,times,model.sessions


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("record","verify","projection"))
    parser.add_argument("--file",type=Path,default=DIR/"results.json")
    args=parser.parse_args()
    live=args.mode=="record"
    if live and args.file.exists():
        parser.error("Use a new output file")
    plan=json.loads(ev.pilot.git("show",PLAN))
    saved={} if live else json.loads(args.file.read_text(encoding="utf8"))
    cache=saved.get("generations",{})
    with tempfile.TemporaryDirectory() as tmp:
        rows,ms,sessions=run(Path(tmp),plan,live,cache,args.mode=="projection")
    if args.mode=="projection":
        for row,ref in zip(rows,saved["rows"],strict=True):
            assert row["requirements"]==ref["requirements"]
        out=DIR/"projection.json"
        payload=dict(rows=rows,ms=ms)
        if out.exists():
            assert json.loads(out.read_text(encoding="utf8"))["rows"]==rows
        else:
            with out.open("x",encoding="utf8",newline="\n") as f:
                json.dump(payload,f,ensure_ascii=False,indent=1)
                f.write("\n")
        for a in ("eager_projection","requirements"):
            print(a,sum(r[a]["solved"] for r in rows),sum(len(r[a]["answer"]["steps"]) for r in rows),
                  median(t[a] for t in ms.values()))
        return
    if live:
        with args.file.open("x",encoding="utf8",newline="\n") as f:
            json.dump(dict(plan=PLAN,rows=rows,ms=ms,generations=cache,sessions=sessions),f,ensure_ascii=False,indent=1)
            f.write("\n")
    else:
        assert rows==saved["rows"] and saved["plan"]==PLAN
        ms=saved["ms"]
    for a in ARMS:
        exact=sum(r["oracle"].get(a)==r["wanted"] for r in rows) if a!="grounded" else "-"
        print(a,exact,*[sum(r[a][m] for r in rows) for m in ("solved","sufficient","handled","false_publication")],
              median(t[a] for t in ms.values()),sum(r[a]["calls"] for r in rows))


if __name__=="__main__":
    main()
