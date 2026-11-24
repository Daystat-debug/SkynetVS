"""Replay object/receipt assignments at known requirements and through the full host."""
import argparse
import json
from pathlib import Path
import re
from statistics import median
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_experience as prior
import skynet_task_parts as parts

prev=prior.prev
PLAN="59847e4a6b0c38b4173a4761593f31e977fd594e:docs/maintenance/core_13/transfer.json"
FINAL="ddd2b60e4032def685af34b01942ac87b5506a0e:docs/maintenance/core_13/confirmation.json"
DIR=prior.build.DIR.parent/"core_13"
FULL=("residual","memory_only","experience_release","object_local","object_recent","object_offline","object_graph")
ORACLE=("parts_once","object_local","object_recent","object_offline","object_graph")


def place(q,cue,spans):
    matches=list(re.finditer(r"(?<!\w)"+re.escape(cue),q))
    assert len(matches)==1,(cue,q)
    pos=matches[0].end()-1
    return next(i for i,p in enumerate(spans) if p["start"]<=pos<p["end"])


def inputs(panel):
    # Return only requirement kinds per host segment. Never pass the gold referent to the interpreter.
    result={}
    for key,q,demands in panel["cases"]:
        spans=parts.split(q)
        labels=[[] for _ in spans]
        for cue,_,kind in demands:
            labels[place(q,cue,spans)].append(panel.get("oracle_overrides",{}).get(key+"/"+cue,kind))
        result[q]=labels
    return result


def oracle_planner(lookup):
    def propose(spans,*_):
        rows=[]
        last=0
        for i,(p,labels) in enumerate(zip(spans,lookup["".join(p["text"] for p in spans)],strict=True)):
            if parts.req.goals.quoted(p["text"]):
                last=i
            needs=list(parts.req.closure([k for k in labels if k in parts.req.KINDS]))
            gaps=[k for k in labels if k not in parts.req.KINDS]
            rows.append((needs,gaps or ([] if needs else ["uninterpreted"]),last))
        return rows
    return propose


def grade(case,out,panel,src,root,offset):
    key,q,demands=case
    claims=out["claims"]
    prev.ev.old.verify_refs(root,src.commit,[r for c in claims for r in c["refs"]])
    spans=out.get("parts") or [dict(start=0,end=len(q),need=[],issues=[out.get("reason")],claims=[])]
    scores=[]
    for cue,t,kind in demands:
        span=spans[place(q,cue,spans)]
        rows=[claims[i] for i in span["claims"]]
        sites=[c for c in rows if c["kind"]=="site"]
        issues=set(span["issues"])
        if t=="-":
            reason=kind in issues or (kind=="ambiguous" and "observation_ambiguous" in issues) or (
                kind=="unsupported" and "observation_missing" in issues)
            scores.append(dict(cue=cue,kind=kind,gap=bool(issues),reason=reason,
                               incorrect_site=bool(sites and key+"/"+cue in panel.get("oracle_overrides",{}))))
            continue
        target=panel["targets"][t]
        def matches(c):
            return prev.fact([c],target,"site",src,offset)
        site="missing" if not sites else "right" if all(matches(c) for c in sites) else "wrong"
        binding=span.get("binding",{}).get("object")
        chosen=None if not binding else (binding["commit"]==src.commit and
            binding["path"]==prev.ev.previous.PATHS[target[0]] and binding["owner"]==target[1]
            and binding["line"]==target[2]+offset)
        scores.append(dict(cue=cue,kind=kind,type_found=kind in span["need"],site=site,chosen=chosen,
                           proved=site=="right" and prev.fact(rows,target,kind,src,offset)))
    facts=[s for s in scores if "site" in s]
    missing=[s for s in scores if "gap" in s]
    expected="partial" if facts and missing else "answered" if facts else "insufficient"
    wrong=any(s["site"]=="wrong" for s in facts) or any(s["incorrect_site"] for s in missing)
    complete=all(s["proved"] for s in facts) and not wrong
    full=out["state"]==expected=="answered" and complete
    partial=out["state"]==expected=="partial" and complete and all(s["gap"] for s in missing)
    return dict(scores=scores,expected=expected,full=full,partial=partial,
                strict_partial=partial and all(s["reason"] for s in missing),
                false_complete=out["state"]=="answered" and not full,
                wrong_binding=wrong,status_correct=out["state"]==expected)


def summary(rows,arms,ms,cache):
    metrics={}
    for arm in arms:
        data=[r[arm] for r in rows]
        scores=[s for rec in data for s in rec["scores"] if "site" in s]
        vals={k:sum(r[k] for r in data) for k in
              ("full","partial","strict_partial","false_complete","wrong_binding","status_correct")}
        for name in ("right","wrong","missing"):
            vals[name]=sum(s["site"]==name for s in scores)
        calls=[k for r in data for k in r["calls"]]
        metrics[arm]=dict(vals,recognized=sum(s["type_found"] for s in scores),
                          correct_objects=sum(s["chosen"] is True for s in scores),
                          facts=sum(s["proved"] for s in scores),steps=sum(len(r["answer"]["steps"]) for r in data),
                          median_ms=round(median(t[arm] for t in ms.values()),1),calls=len(calls),
                          input_tokens=sum(cache[k]["prompt_tokens"] for k in calls),
                          output_tokens=sum(cache[k]["completion_tokens"] for k in calls))
    return metrics


def breakdown(panel,rows,arm):
    exact=unquoted_useful=unquoted_count=refusals=unavailable_closed=0
    semantic=tentative=direct=reference=0
    for (key,q,demands),row in zip(panel["cases"],rows,strict=True):
        record=row[arm]
        out=record["answer"]
        refusals+=out["state"]=="insufficient"
        if not parts.req.goals.quoted(q):
            unquoted_count+=1
            unquoted_useful+=record["full"] or record["partial"]
        spans=out.get("parts",[])
        if not spans:
            continue
        requested=[[] for _ in spans]
        for cue,_,k in demands:
            idx=place(q,cue,spans)
            requested[idx].append(panel.get("oracle_overrides",{}).get(key+"/"+cue,k))
            if k in parts.ISSUES and spans[idx]["status"]=="established":
                unavailable_closed+=1
        matched=True
        for span,labels in zip(spans,requested,strict=True):
            expected=set(parts.req.closure([k for k in labels if k in parts.req.KINDS]))
            expected.update(k for k in labels if k not in parts.req.KINDS)
            inferred=set(span["need"]) | (set(span["issues"]) & set(parts.ISSUES))
            matched &= inferred==expected
            binding=span.get("binding",{})
            semantic+=binding.get("via")=="semantic"
            tentative+=bool(binding.get("tentative"))
            direct+=binding.get("via") in ("description","quote")
            reference+=binding.get("via")=="reference"
        exact+=matched
    return dict(exact_requirements=exact,insufficient=refusals,unquoted_useful=unquoted_useful,
                unquoted_total=unquoted_count,direct=direct,references=reference,
                semantic=semantic,tentative=tentative,unavailable_demands_marked_established=unavailable_closed)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("record","verify","summary"))
    group=p.add_mutually_exclusive_group()
    group.add_argument("--history",action="store_true")
    group.add_argument("--final",action="store_true")
    p.add_argument("--file",type=Path)
    a=p.parse_args()
    ref=prior.GROUPED if a.history else FINAL if a.final else PLAN
    panel=json.loads(prev.ev.pilot.git("show",ref))
    path=a.file or DIR/("history.json" if a.history else "confirmation_results.json" if a.final else "results.json")
    live=a.mode=="record"
    if live and path.exists():
        p.error("record requires a new file")
    saved={} if live else json.loads(path.read_text(encoding="utf8"))
    if a.mode=="summary":
        assert saved["plan"]==ref
        for block in ("full","oracle"):
            for arm in saved.get(block,{}):
                print(block,arm,breakdown(panel,saved[block+"_rows"],arm))
        return
    cache=saved.get("generations",{})
    arms=(("experience_release","object_graph") if a.history else
          ("residual","memory_only","experience_release","shared_evidence","object_offline","object_graph","object_assisted")
          if a.final else FULL)
    with patch.object(prev,"grade",grade),tempfile.TemporaryDirectory() as tmp:
        rows,times,sessions=prev.run(Path(tmp),panel,live,cache,arms)
    if not live:
        assert saved["plan"]==ref and saved["full_rows"]==rows
        assert {k for r in rows for arm in arms for k in r[arm]["calls"]}==set(cache)
        times=saved["ms"]
    data=dict(plan=ref,full_rows=rows,ms=times,full=summary(rows,arms,times,cache),generations=cache)
    if not a.history:
        oracle=("parts_once","object_offline","object_graph","object_assisted") if a.final else ORACLE
        propose=oracle_planner(inputs(panel))
        with patch.object(parts,"plan",propose),patch.object(parts.experience,"shared_plan",propose),\
                patch.object(prev,"grade",grade),tempfile.TemporaryDirectory() as tmp:
            known,t,_=prev.run(Path(tmp),panel,False,cache,oracle)
        if not live:
            assert known==saved["oracle_rows"]
            t=saved["oracle_ms"]
        data.update(oracle_rows=known,oracle_ms=t,oracle=summary(known,oracle,t,cache))
    if live:
        with path.open("x",encoding="utf8",newline="\n") as f:
            json.dump(dict(data,sessions=sessions),f,ensure_ascii=False,indent=1)
            f.write("\n")
    else:
        for key in data:
            assert data[key]==saved[key],key
    for block in ("full","oracle"):
        for arm,m in data.get(block,{}).items():
            print(block,arm,*[m[k] for k in ("right","wrong","missing","facts","full","partial","false_complete","median_ms","calls")])


if __name__=="__main__":
    main()
