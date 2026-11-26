"""Materialize aligned experience and fit equally sized local sequence models."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_description_match as method
import fit_semantic_pairs as previous


def annotated(markup,event):
    tokens=re.findall(r"([^\W_]+)(?:\{([^}]+)\})?",markup.casefold().replace("ё","е"))
    seq=[w for w,_ in tokens]
    tags=[tag or "o" for _,tag in tokens]
    assert all(tag in method.TAGS for tag in tags)
    text=re.sub(r"\{[^}]+\}","",markup)
    assert method.old.words(text)==seq and len(seq)==len(tokens)
    concepts=[None]*len(seq)
    for j,r in enumerate(method.ROLES):
        ix=[i for i,t in enumerate(tags) if r in t.split("+")]
        assert bool(ix)==(event[j] not in (None,"?")),(markup,event,r)
        for i in ix:
            concepts[i]=event[j]
    sign="?" if "u" in tags else "-" if any("n" in t.split("+") for t in tags) else "+"
    assert sign==event[-1],(markup,event,sign)
    return dict(text=text,seq=seq,tags=tags,concepts=concepts,event=event)


def material(records,style):
    output=[]
    for i,row in enumerate(records):
        regular=row["regular"]
        simple=[regular,"Где указано, что "+regular[0].lower()+regular[1:]+"?"]
        free=row["free"]
        variants=simple if style=="desc_regular" else free if style=="desc_free" else [
            simple[i%2],free[1-i%2]]
        output.extend(annotated(s,row["event"]) for s in variants)
    return output


def outcome(left,right):
    for a,b in zip(left[:-1],right[:-1],strict=True):
        if a!=b and "?" not in (a,b):
            return "different"
    if "?" in left or "?" in right:
        return "unknown"
    return "equal" if left[-1]==right[-1] else "different"


def fit(samples):
    size=len(method.TAGS)
    weights=defaultdict(lambda:[0]*size)
    totals=defaultdict(lambda:[0]*size)
    stamps={}
    names=defaultdict(set)
    required=defaultdict(set)
    for s in samples:
        for w,v in zip(s["seq"],s["concepts"]):
            if v is not None:
                names[w].add(v)
        for r,value in zip(method.ROLES,s["event"][:-1],strict=True):
            if value is not None:
                required[s["event"][1]].add(r)
    rng=random.Random(2001)
    order=list(samples)
    step=0
    for epoch in range(12):
        rng.shuffle(order)
        for s in order:
            step+=1
            seq,gold=s["seq"],s["tags"]
            mask=epoch%3==1
            pred=method.decode(seq,weights,mask)
            if pred==gold:
                continue
            for tags,delta in ((gold,1),(pred,-1)):
                prev="^"
                for i,tag in enumerate(tags):
                    idx=method.TAGS.index(tag)
                    for key in [*method.features(seq,i,mask),"from/"+prev]:
                        totals[key][idx]+=(step-stamps.get((key,idx),0))*weights[key][idx]
                        stamps[key,idx]=step
                        weights[key][idx]+=delta
                    prev=tag
    averaged={k:[round((totals[k][j]+(step-stamps.get((k,j),0))*v)/step,5)
                 for j,v in enumerate(row)] for k,row in weights.items()}
    return dict(weights=averaged,concepts={w:next(iter(v)) for w,v in names.items() if len(v)==1},
                required={k:sorted(v) for k,v in required.items()})


def build():
    corpus=json.loads((method.DIR/"experience.json").read_text(encoding="utf8"))
    train=[r for r in corpus["records"] if r["domain"] not in corpus["calibration_domains"]]
    cal=[r for r in corpus["records"] if r["domain"] in corpus["calibration_domains"]]
    assert not {tuple(r["event"]) for r in train}&{tuple(r["event"]) for r in cal}
    held=material(cal,"desc_free")
    out,metrics={},{}
    for style in method.POLICIES:
        samples=material(train,style)
        assert not {s["text"].casefold() for s in samples}&{s["text"].casefold() for s in held}
        model=out[style]=fit(samples)
        frames=[method.interpret(s["seq"],model)[1] for s in held]
        matrix=Counter()
        for i,q in enumerate(held):
            for j,s in enumerate(held):
                if i!=j:
                    matrix[outcome(q["event"],s["event"]),method.compare(frames[i],frames[j])[0]]+=1
        recall=sum(matrix[k,k]/sum(v for (t,_),v in matrix.items() if t==k) for k in method.old.LABELS)/3
        metrics[style]=dict(macro_recall=recall,train_phrases=len(samples),tokens=sum(len(s["seq"]) for s in samples),
                            matrix={a+"/"+b:n for (a,b),n in matrix.items()})
    winner=max(out,key=lambda k:(metrics[k]["macro_recall"],k=="desc_mixed"))
    # Same recorded phrases, including the mixed assignment made before grouping by domain.
    def paired(records,samples):
        domains=[r["domain"] for r in records for _ in range(2)]
        return [(d,q,[s for j,s in enumerate(samples) if domains[j]==d and j!=i])
                for i,(d,q) in enumerate(zip(domains,samples,strict=True))]
    pairs=paired(train,material(train,winner))
    bag={"learn_bag":previous.fit_head(pairs,{},"learn_bag",label=outcome)}
    calibration=paired(cal,held)
    # Previous calibration expects None for an unknown coordinate. The unused role has a
    # distinct explicit marker so unary properties can still form complete events.
    def legacy(s):
        return dict(s,event=tuple(None if v=="?" else "*" if v is None else v for v in s["event"]))
    adapted=[(d,legacy(q),[legacy(s) for s in ss]) for d,q,ss in calibration]
    bag["thresholds"],bag["selection"]=previous.calibrate(adapted,bag,"learn_bag")
    return dict(selected=winner,variants=out,calibration=metrics,bag=bag)


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("fit","verify"))
    cli.add_argument("--output",type=Path,default=method.DIR/"models.json")
    args=cli.parse_args()
    result=build()
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n"
    if args.mode=="verify":
        assert args.output.read_text(encoding="utf8")==raw
    else:
        with args.output.open("x",encoding="utf8",newline="\n") as stream:
            stream.write(raw)
    print(result["selected"],result["calibration"])
