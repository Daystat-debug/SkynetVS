"""Score raw text, independently intervene on lexical meaning / role attachment, then run the host."""
import argparse
import ast
from collections import Counter, defaultdict
from contextlib import ExitStack
import gzip
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_learned_match as prev
import fit_description_match as fit

m=fit.method
old=prev.old
ARMS=("joint_plan","identity_lexical","learn_bag","learn_roles","desc_bag",*m.POLICIES,"known_objects")


def role_counts(actual,gold):
    predicted={(i,t) for i,tag in enumerate(actual) for t in tag.split("+") if t!="o"}
    required={(i,t) for i,tag in enumerate(gold) for t in tag.split("+") if t!="o"}
    return Counter(correct=len(predicted&required),predicted=len(predicted),gold=len(required),
                   whole=int(actual==gold),utterances=1)


def closed(panel):
    models=m.models()
    main=models["selected"]
    corpus=prev.lab.load(m.DIR/"experience.json")
    seen={s["text"].casefold() for k in m.POLICIES for s in fit.material(corpus["records"],k)}
    assert {row["domain"] for row in corpus["records"]}.isdisjoint(panel["domains"].values())
    assert not {tuple(r["event"]) for r in corpus["records"]}&{tuple(v[1]) for v in panel["labels"].values()}
    role_scores=defaultdict(Counter)
    counted=set()
    cases={k:(q,demands) for k,q,demands in panel["cases"]}
    individual=[]
    for key,cue,markup,event in panel["queries"]:
        question,demands=cases[key]
        spans=old.prior.parts.split(question)
        body=spans[old.prior.old.place(question,cue,spans)]["text"]
        q=fit.annotated(markup,event)
        assert q["seq"]==m.old.words(body),(key,body,q["text"])
        keys=panel["menus"][key[0]]
        sources=[fit.annotated(*panel["labels"][k]) for k in keys]
        for k,s in zip(keys,sources,strict=True):
            t=panel["targets"][k]
            stmt=ast.parse(panel["fixtures"][key[0]][t[2]-1].strip()).body[0]
            assert isinstance(stmt,ast.Return) and ast.literal_eval(stmt.value)==t[3]==s["text"]
        entries=[q,*sources]
        assert all(s["text"].casefold() not in seen for s in entries)
        gold=[fit.outcome(event,s["event"]) for s in sources]
        hits=[k for k,y in zip(keys,gold) if y=="equal"]
        target=next(t for prefix,t,_ in demands if prefix==cue)
        assert hits==([] if target=="-" else [target]),(key,hits,target)
        arms={}
        tags_by_arm={}
        # The forced-negative arm rejects every pair, including partial information.
        arms["always_different"]=(None,["different"]*len(keys))
        labels={k:s["text"] for k,s in zip(keys,sources)}
        arms["trigrams"]=(prev.lab.lexical(q["text"],labels),[])
        for arm in ("learn_bag","learn_roles","desc_bag"):
            model=models["bag"] if arm=="desc_bag" else m.old.frozen()
            head="learn_bag" if arm=="desc_bag" else arm
            _,pred=m.old.infer(q["text"],list(labels.values()),model,head)
            thresholds=model["thresholds"] if arm=="desc_bag" else model["thresholds"][arm]
            pos=m.old.decide(pred,*thresholds)
            arms[arm]=(None if pos is None else keys[pos],[p["verdict"] for p in pred])
        for arm in (*m.POLICIES,"gold_roles","gold_concepts","gold_both"):
            model=models["variants"].get(arm,models["variants"][main])
            frames=[]
            predicted=[]
            for j,s in enumerate(entries):
                tags,frame=m.interpret(s["seq"],model,tags=s["tags"] if arm in ("gold_roles","gold_both") else None,
                                       concepts=s["concepts"] if arm in ("gold_concepts","gold_both") else None)
                frames.append(frame)
                predicted.append(tags)
                utterance=("source",keys[j-1]) if j else ("question",key,cue)
                if arm in m.POLICIES and (arm,utterance) not in counted:
                    role_scores[arm+"/"+utterance[0]].update(role_counts(tags,s["tags"]))
                    counted.add((arm,utterance))
            verdicts=[m.compare(frames[0],f) for f in frames[1:]]
            pos=m.select(verdicts)
            arms[arm]=(None if pos is None else keys[pos],[v for v,_ in verdicts])
            if arm==main or arm=="gold_both":
                tags_by_arm[arm]=dict(frames=frames,tags=predicted,reasons=[w for _,w in verdicts])
        individual.append(dict(id=key,cue=cue,target=target,menu=keys,gold=gold,arms=arms,interpretations=tags_by_arm))
    metrics={}
    for arm in individual[0]["arms"]:
        conf=[[0]*3 for _ in range(3)]
        right=wrong=held=0
        for rec in individual:
            choice,ys=rec["arms"][arm]
            right+=choice==rec["target"]
            wrong+=choice is not None and choice!=rec["target"]
            held+=choice is None and rec["target"]=="-"
            if ys:
                for g,v in zip(rec["gold"],ys,strict=True):
                    conf[m.old.LABELS.index(g)][m.old.LABELS.index(v)]+=1
        metrics[arm]=dict(right=right,wrong=wrong,held=held,matrix=conf if arm!="trigrams" else None)
    return dict(order=m.old.LABELS,metrics=metrics,roles=role_scores,individual=individual)


def execute(mode):
    path=m.DIR/"final.json"
    panel=prev.lab.load(path)
    if mode=="check-panel":
        for case in panel["cases"]:
            old.prior.hints(case,panel,0)
        return
    dest=m.DIR/"trace.json.gz"
    summary=m.DIR/"scores.json"
    live=mode=="record"
    if live and (dest.exists() or summary.exists()):
        raise FileExistsError("record requires new files")
    pairs=closed(panel)
    run,grade=old.harness(panel)
    with ExitStack() as stack:
        tmp=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(old.ev.loop,"investigate",run))
        stack.enter_context(patch.object(old.runner,"grade",grade))
        rows,ms,sessions=old.runner.run(tmp,panel,False,{},ARMS)
    assert not sessions and all(not r[a]["calls"] for r in rows for a in ARMS)
    if not live:
        ms=json.loads(gzip.decompress(dest.read_bytes()))["ms"]
    metrics={arm:old.summary(rows,ms,{},arm,panel) for arm in ARMS}
    scores=[]
    for row in rows:
        for xs in zip(*(row[a]["identity"] for a in ("learn_roles","desc_bag",*m.POLICIES)),strict=True):
            assert all(x["hypothesis"].get("pool")==xs[0]["hypothesis"].get("pool") for x in xs)
        scores.append(dict(id=row["id"],arms={a:dict(
            state=row[a]["answer"]["state"],full=row[a]["full"],partial=row[a]["useful_partial"],
            false_complete=row[a]["false_complete"],facts=sum(bool(x["fact"]) for x in row[a]["identity"]),
            wrong=sum(x["wrong"] for x in row[a]["identity"])) for a in ARMS}))
    # Use JSON types in both live storage and archive verification.
    pairs=json.loads(json.dumps(pairs,ensure_ascii=False))
    prev.lab.artifact(dest,dict(panel_blob=old.ev.pilot.git("hash-object",str(path)).decode().strip(),
                                rows=rows,ms=ms,metrics=metrics,closed=pairs),live)
    compact=[{k:v for k,v in r.items() if k!="interpretations"} for r in pairs["individual"]]
    prev.lab.artifact(summary,dict(metrics=metrics,questions=scores,closed={**pairs,"individual":compact}),live)
    print("pairs",pairs["metrics"])
    for a,z in metrics.items():
        print(a,*(z[k] for k in ("facts","full","useful_partial","wrong","false_complete","refused","median_ms")))


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("check-panel","record","verify"))
    execute(cli.parse_args().mode)
