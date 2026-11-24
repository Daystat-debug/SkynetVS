"""Replay evidence and task accounting on real and synthetic pinned Git objects."""
import argparse
import ast
import json
import re
from pathlib import Path
from statistics import median
import sys
import tempfile
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_requirements as old

ev=old.ev
PLAN="7a2b3c3824805265ed8d8264b3633cc3fb2003e5:docs/maintenance/core_10/transfer.json"
DIR=ev.pilot.ROOT/"docs/maintenance/core_10"
ARMS=("requirements","lexical_parts","parts_once","parts")
CONFIRMATION="8ec46cb8d5366381324cb4e6f67befbef77adee7:docs/maintenance/core_10/confirmation.json"
FINAL_ARMS=("requirements","lexical_parts","parts","flat_residual","residual")


def fact(claims,target,kind,src,offset):
    path,name,line,label,*details=target
    line+=offset
    def covers(c,p,n):
        return any(r["path"]==ev.previous.PATHS[p] and r["start"]<=n<=r["end"] for r in c["refs"])
    if kind=="site":
        return any(c["kind"]=="site" and label in c["text"] and name in c["text"] and covers(c,path,line) for c in claims)
    if kind=="condition":
        pred=details[0]
        if offset:
            pred=pred+offset if pred>0 else pred-offset
        controls=ev.previous.controls
        fn=next(n for n in ast.parse(src.snapshot.sources[ev.previous.PATHS[path]]).body if isinstance(n,ast.FunctionDef) and n.name==name)
        for c in claims:
            ctrl=c.get("control",{})
            if ctrl.get("function")==name and ctrl.get("line")==line and covers(c,path,line):
                term=controls.displayed(c["text"],fn,line)
                if controls.truth_signature(controls.normalize(term))==controls.truth_signature(controls.normalize(pred)):
                    return True
        return False
    _,caller,cp,call,bindings,*imp=details
    return any(covers(c,cp,call+offset) and all(covers(c,cp,n) for n in imp)
               and ((kind=="caller" and c.get("edge")==[caller,name]) or
                    (kind=="arguments" and all(arg in c["text"] for arg in bindings))) for c in claims)


def grade(case,out,plan,src,root,offset):
    key,q,demands=case
    cs=out["claims"]
    ev.old.verify_refs(root,src.commit,[r for c in cs for r in c["refs"]])
    parts=out.get("parts",[])
    scores=[]
    for cue,target,kind in demands:
        assert cue in q
        # Respect the annotated word boundary ("и строку" also ends "Укажи строку").
        p=next((p for p in parts if re.search(r"(?<!\w)"+re.escape(cue),p["text"])),{})
        kinds=p.get("need",[]) if parts else out.get("requirements",{}).get("required",[])
        issues=p.get("issues",[]) if parts else [out.get("reason")]
        if target=="-":
            understood=kind in issues or (kind=="runtime" and "observation_required" in issues)
            acknowledged=bool(p and issues and p.get("status")!="established") or (not p and understood)
            proved=None
        else:
            understood=kind in kinds
            acknowledged=bool(p) or understood
            selected=[cs[n] for n in p.get("claims",[])] if parts else cs
            proved=fact(selected,plan["targets"][target],kind,src,offset)
        scores.append(dict(cue=cue,kind=kind,understood=understood,acknowledged=acknowledged,proved=proved))
    supported=[s for s in scores if s["proved"] is not None]
    gaps=[s for s in scores if s["proved"] is None]
    expected="partial" if supported and gaps else "answered" if supported else "insufficient"
    state=out["state"]
    allfacts=all(s["proved"] for s in supported)
    allgaps=all(s["acknowledged"] for s in gaps)
    return dict(scores=scores,expected=expected,status_correct=expected==state,
                useful_full=expected==state=="answered" and allfacts,
                useful_partial=expected==state=="partial" and allfacts and allgaps,
                false_complete=state=="answered" and (bool(gaps) or not allfacts))


def summary(saved,plan,arms):
    """Distinguish showing an unresolved clause from correctly explaining its gap."""
    print("strategy | exact kind sets/questions | demands accounted | correct kinds | evidence | useful partial with correct reasons | steps | calls | input/output tokens")
    for arm in arms:
        exact=retained=recognized=evidence=useful=steps=0
        for case,row in zip(plan["cases"],saved["rows"],strict=True):
            result=row[arm]
            out=result["answer"]
            scores=result["scores"]
            retained+=sum(s["acknowledged"] for s in scores)
            recognized+=sum(s["understood"] for s in scores)
            evidence+=sum(s["proved"] is True for s in scores)
            steps+=len(out["steps"])
            parts=out.get("parts") or [dict(text=row["question"],need=out.get("requirements",{}).get("required",[]),
                                            issues=[out.get("reason")])]
            gaps_correct=True
            kinds_exact=True
            for part in parts:
                ds=[(cue,target,k) for cue,target,k in case[2] if re.search(r"(?<!\w)"+re.escape(cue),part["text"])]
                need=set(old.req.closure([k for _,t,k in ds if t!="-"]))
                missing={k for _,t,k in ds if t=="-"}
                reasons=set(part.get("issues",[]))
                if "observation_required" in reasons:
                    reasons.add("runtime")
                if "observation_ambiguous" in reasons:
                    reasons.add("ambiguous")
                typed=reasons.intersection(("runtime","external","unsupported","ambiguous"))
                kinds_exact &= need==set(part.get("need",[])) and missing==typed
                gaps_correct &= missing.issubset(typed)
                gap=part.get("residual")
                if gap and gap["why"] in missing:
                    gaps_correct &= any((cue.casefold() in gap["text"].casefold() or
                                        gap["text"].casefold() in cue.casefold()) for cue,t,k in ds
                                        if t=="-" and k==gap["why"])
            exact+=kinds_exact
            useful+=bool(result["useful_partial"] and gaps_correct)
        gens=[v for k,v in saved["generations"].items() if k.split("/")[1]==arm]
        print(arm,exact,retained,recognized,evidence,useful,steps,len(gens),
              sum(g["prompt_tokens"] for g in gens),sum(g["completion_tokens"] for g in gens))


def run(tmp,plan,live,cache,arms):
    root=tmp/"repo"
    ev.pilot.git("clone","--quiet","--local","--no-checkout",str(ev.pilot.ROOT),str(root))
    base=plan["base"]
    ev.archive.set_head(root,base)
    raw,_=ev.old.blob(root,base,ev.old.RANK)
    model=ev.Generations(tmp,cache,live)
    rows,ms=[],{}
    group=None
    try:
        for i,case in enumerate(plan["cases"]):
            key,q,_=case
            if group!=key[0]:
                group=key[0]
                offset=0
                if group!="R":
                    offset=len(raw.splitlines())
                    extra=("\n".join(plan["fixtures"][group])+"\n").encode()
                    ev.archive.prior_eval.checkout_fixture(root,base,raw+extra)
                src,ground=ev.loop.read_head(root)
            row=dict(id=key,question=q,snapshot=src.commit)
            ms[key]={}
            shift=i%len(arms)
            for arm in arms[shift:]+arms[:shift]:
                calls=[]
                if live and arm!="lexical_parts":
                    if model.provider and model.provider.calls>=15:
                        model.stack.close()
                        model.provider=None
                    model.prepare()
                def select(system,user):
                    assert len(calls)<2
                    model.key=f"{key}/{arm}/{len(calls)}"
                    model.used=0
                    calls.append(model.key)
                    return model.select(system,user)
                t=perf_counter()
                out=ev.loop.investigate(q,root,opener=lambda _:(src,ground),discovery=arm,select=select)
                ms[key][arm]=round(1000*(perf_counter()-t),1)
                assert not model.replay_errors and len(out["steps"])<=6
                row[arm]=dict(**grade(case,out,plan,src,root,offset),calls=calls,answer=ev.portable(out))
            rows.append(row)
    finally:
        model.stack.close()
    return rows,ms,model.sessions


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("record","verify","rescore","summary"))
    p.add_argument("--final",action="store_true")
    p.add_argument("--file",type=Path)
    a=p.parse_args()
    live=a.mode=="record"
    plan_id,arms=(CONFIRMATION,FINAL_ARMS) if a.final else (PLAN,ARMS)
    a.file=a.file or DIR/("confirmation_results.json" if a.final else "results.json" if live or a.mode=="rescore" else "scored.json")
    if live and a.file.exists():
        p.error("choose a new output file")
    saved={} if live else json.loads(a.file.read_text(encoding="utf8"))
    cache=saved.get("generations",{})
    plan=json.loads(ev.pilot.git("show",plan_id))
    if a.mode=="summary":
        assert saved["plan"]==plan_id
        summary(saved,plan,arms)
        return
    with tempfile.TemporaryDirectory() as tmp:
        rows,ms,sessions=run(Path(tmp),plan,live,cache,arms)
    if live:
        with a.file.open("x",encoding="utf8",newline="\n") as f:
            json.dump(dict(plan=plan_id,rows=rows,ms=ms,generations=cache,sessions=sessions),f,ensure_ascii=False,indent=1)
            f.write("\n")
    else:
        if a.mode=="rescore":
            assert saved["plan"]==PLAN
            for row,original in zip(rows,saved["rows"],strict=True):
                for arm in ARMS:
                    assert row[arm]["answer"]==original[arm]["answer"]
            saved["rows"]=rows
            dest=a.file.with_name("scored.json")
            with dest.open("x",encoding="utf8",newline="\n") as f:
                json.dump(saved,f,ensure_ascii=False,indent=1)
                f.write("\n")
        else:
            assert rows==saved["rows"] and plan_id==saved["plan"]
        ms=saved["ms"]
    for arm in arms:
        obs=[r[arm] for r in rows]
        print(arm,*[sum(r[k] for r in obs) for k in ("status_correct","useful_full","useful_partial","false_complete")],
              round(median(t[arm] for t in ms.values()),1),sum(len(r["calls"]) for r in obs))


if __name__=="__main__":
    main()
