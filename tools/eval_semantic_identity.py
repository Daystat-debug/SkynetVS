"""Paired object resolution on the unchanged task planner and source evidence path."""
import argparse
from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path
from statistics import median
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_evidence_plan as base
import skynet_semantic_identity as identity

prior, runner, ev = base.prior, base.runner, base.ev
binding=prior.binding
DIR=base.DIR.parent/"core_17"
ARMS=("joint_plan","identity_lexical","identity_rank","identity_contrast","known_objects")


def harness(panel):
    cases={c[1]:c for c in panel["cases"]}
    shift=len(ev.old.blob(ev.pilot.ROOT,panel["base"],ev.old.RANK)[0].splitlines())
    host=ev.loop.investigate
    nominate=binding.nominations
    captured={}
    def run(q,root,*,discovery,**kw):
        def collect(spans,catalog,commit,policy,select):
            records=nominate(spans,catalog,commit,policy,select)
            captured.update(catalog=catalog,records=records,arm=discovery)
            return records
        def selected(question,root,**options):
            options["discovery"]="joint_plan" if discovery=="known_objects" else discovery
            return host(question,root,**options)
        with patch.object(binding,"nominations",collect):
            return prior.observe(selected,cases,panel,shift)(q,root,discovery=discovery,**kw)
    def grade(case,out,plan,src,root,offset):
        rec=prior.grade(case,out,plan,src,root,offset)
        key,q,demands=case
        catalog=captured["catalog"]
        cards=[binding.identity(e,src.commit) for e in catalog]
        rows=[]
        for (cue,target,kind),s in zip(demands,rec["scores"],strict=True):
            spans=out.get("parts") or prior.parts.split(q)
            i=prior.old.place(q,cue,spans)
            p=spans[i]
            obj=p.get("binding",{}).get("object")
            text=p["text"]
            record=captured["records"].get(i,{})
            quotes=identity.goals.quoted(text)
            ref=not quotes and bool(binding.ORDINAL.search(text) or binding.ANAPHOR.search(text))
            if record:
                pool=record["pool"]
            elif quotes:
                pool=[j for j,e in enumerate(catalog) if len(quotes)==1 and quotes[0].casefold() in e.label.casefold()]
            elif ref:
                pool=[]
            else:
                pool=[j for score,j,_ in identity.language.lexical_rows("Где "+text,catalog,"explore") if score>0][:identity.LIMIT]
            # Source oracle coordinates and the rubric are used exclusively in scoring here.
            expected=target if target!="-" else plan.get("negative_referents",{}).get(key+"/"+cue)
            gold=None
            if expected:
                t=plan["targets"][expected]
                hits=[j for j,e in enumerate(catalog) if e.fn.path==ev.previous.PATHS[t[0]]
                      and e.fn.node.name==t[1] and e.expr.lineno==t[2]+offset]
                assert len(hits)==1
                gold=hits[0]
            actual=cards.index(obj) if obj else None
            issue=p.get("issues",[out.get("reason")])
            if target=="-":
                wanted=plan.get("negative_reasons",{}).get(key+"/"+cue,kind)
                s["correct_reason"]=wanted in issue
            rows.append(dict(cue=cue,target=target,kind=kind,gold=gold,chosen=actual,wrong=actual is not None and actual!=gold,
                             direct_search=not ref,rank=pool.index(gold)+1 if gold in pool else None,
                             first=record.get("first"),reviewed="review" in record,decision=record.get("why"),
                             hypothesis=record,via=p.get("binding",{}).get("via"),issues=issue,
                             understood=s.get("requirement",s.get("correct_reason")),fact=s.get("delivered"),
                             coordinates=obj))
        wrong=any(r["wrong"] for r in rows)
        rec["full"] &= not wrong
        rec["partial"] &= not wrong
        rec["false_complete"]=out["state"]=="answered" and not rec["full"]
        rec["correct"]=(rec["full"] or rec["partial"] or rec["limited"]) and not wrong and all(
            s["correct_reason"] for s in rec["scores"] if "negative" in s)
        rec["identity"]=rows
        rec["useful_partial"]=bool(out["state"]=="partial" and not wrong and any(r["fact"] for r in rows)
                                   and all(r["fact"] or r["issues"] for r in rows))
        return rec
    return run,grade


def summary(rows,times,cache,arm,panel):
    data=[r[arm] for r in rows]
    identities=[x for r in data for x in r["identity"]]
    positives=[x for x in identities if x["target"]!="-"]
    direct=[x for x in positives if x["direct_search"]]
    calls=[c for r in data for c in r["calls"]]
    passed={row["id"] for row in rows if row[arm]["correct"]}
    return dict(static=len(positives), searched=len(direct), candidates=sum(x["rank"] is not None for x in direct),
            right=sum(x["chosen"]==x["gold"] for x in positives),wrong=sum(x["wrong"] for x in identities),
            types=sum(x["understood"] for x in positives),facts=sum(x["fact"] for x in positives),
            full=sum(r["full"] for r in data),partial=sum(r["partial"] for r in data),
            useful_partial=sum(r["useful_partial"] for r in data),
            false_complete=sum(r["false_complete"] for r in data),refused=sum(r["answer"]["state"]=="insufficient" for r in data),
            failed=sum(r["answer"]["state"]=="failed" for r in data),
            contrasts=[pair for pair in panel["contrasts"] if set(pair)<=passed],
            gaps=dict(Counter(g for x in identities for g in x["issues"])),steps=sum(len(r["answer"]["steps"]) for r in data),
            calls=len(calls),input_tokens=sum(cache[k]["prompt_tokens"] for k in calls),
            output_tokens=sum(cache[k]["completion_tokens"] for k in calls),median_ms=round(median(t[arm] for t in times.values()),1))


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("record","verify"))
    cli.add_argument("panel",choices=("history","transfer"))
    args=cli.parse_args()
    path=(base.DIR if args.panel=="history" else DIR)/"transfer.json"
    panel=json.loads(path.read_text(encoding="utf8"))
    if args.panel=="history":
        panel["cases"]=[c for c in panel["cases"] if c[0]=="F10"]
        panel["contrasts"]=[]
    dest=DIR/(args.panel+"_results.json")
    compact=DIR/(args.panel+"_scores.json")
    live=args.mode=="record"
    if live and (dest.exists() or compact.exists()):
        cli.error("record requires new files")
    saved={} if live else json.loads(dest.read_text(encoding="utf8"))
    cache=saved.get("generations",{})
    wrapped,grade=harness(panel)
    with ExitStack() as stack:
        tmp=stack.enter_context(tempfile.TemporaryDirectory())
        stack.enter_context(patch.object(ev.loop,"investigate",wrapped))
        stack.enter_context(patch.object(runner,"grade",grade))
        rows,times,sessions=runner.run(Path(tmp),panel,live,cache,ARMS)
    if not live:
        times=saved["ms"]
        sessions=saved["sessions"]
    scores={arm:summary(rows,times,cache,arm,panel) for arm in ARMS}
    data=dict(panel_blob=ev.pilot.git("hash-object",str(path)).decode().strip(),rows=rows,ms=times,
              metrics=scores,generations=cache,sessions=sessions)
    short=dict(metrics=scores,questions=[dict(id=r["id"],question=r["question"],arms={arm:dict(
        state=r[arm]["answer"]["state"],full=r[arm]["full"],partial=r[arm]["partial"],
        useful_partial=r[arm]["useful_partial"],false_complete=r[arm]["false_complete"],
        mentions=[{k:x[k] for k in ("target","kind","gold","chosen","rank","wrong","understood","fact","decision","issues")}
                  for x in r[arm]["identity"]]) for arm in ARMS}) for r in rows])
    for file,content in ((dest,data),(compact,short)):
        if live:
            with file.open("x",encoding="utf8",newline="\n") as f:
                json.dump(content,f,ensure_ascii=False,indent=1)
                f.write("\n")
        else:
            assert json.loads(file.read_text(encoding="utf8"))==content,file
    for arm,m in scores.items():
        print(arm,m)


if __name__=="__main__":
    main()
