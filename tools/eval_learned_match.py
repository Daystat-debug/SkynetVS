"""Compare raw-text pair decisions separately from end-to-end verified claim delivery."""
import argparse
import ast
from collections import Counter
from contextlib import ExitStack
import gzip
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_event_meaning as lab
import skynet_learned_match as match

old = lab.previous
ARMS = ("joint_plan","identity_lexical","identity_rank","identity_contrast","event_vocab",
        "learn_bag","learn_roles","known_objects")


def closed(panel):
    material = json.loads(gzip.decompress((match.DIR/"compiled.json.gz").read_bytes()))
    seen = {tuple(match.words(e["text"])) for groups in material.values() for row in groups
            for e in [row["query"],*row["candidates"]]}
    domains = {r["domain"] for groups in material.values() for r in groups}
    assert domains.isdisjoint(panel["domains"].values())
    result = []
    cases = {key:q for key,q,_ in panel["cases"]}
    model = match.frozen()
    for key,cue,annotations in panel["pairs"]:
        q = cases[key]
        spans = old.prior.parts.split(q)
        text = spans[old.prior.old.place(q,cue,spans)]["text"]
        keys = panel["menus"][key[0]]
        assert set(keys)==set(annotations) and len(keys)==len(set(keys))
        labels = {}
        for k in keys:
            _,_,line,label,*_ = panel["targets"][k]
            stmt = ast.parse(panel["fixtures"][key[0]][line-1].strip()).body[0]
            assert isinstance(stmt,ast.Return) and ast.literal_eval(stmt.value)==label
            labels[k] = label
        assert all(tuple(match.words(s)) not in seen for s in [text,*labels.values()])
        positives = [k for k,(y,_) in annotations.items() if y=="equal"]
        assert len(positives)<=1
        gold = next(iter(positives),None)
        arms = {"trigrams":dict(chosen=lab.lexical(text,labels))}
        for arm in ("learn_bag","learn_roles"):
            frame,rows = match.infer(text,list(labels.values()),model,arm)
            pos = match.decide(rows,*model["thresholds"][arm])
            arms[arm] = dict(chosen=keys[pos] if pos is not None else None,query_frame=frame,
                             candidates=dict(zip(keys,rows,strict=True)))
        result.append(dict(id=key,cue=cue,gold=gold,annotations=annotations,arms=arms))
    metrics = {}
    for arm in result[0]["arms"]:
        conf = Counter()
        by_change = Counter()
        hits = wrong = held = 0
        for row in result:
            selected = row["arms"][arm]
            chosen = selected["chosen"]
            hits += chosen is not None and chosen==row["gold"]
            wrong += chosen is not None and chosen!=row["gold"]
            held += chosen is None and row["gold"] is None
            for k,entry in selected.get("candidates",{}).items():
                expected,change = row["annotations"][k]
                conf[expected+"/"+entry["verdict"]] += 1
                by_change[change+"/"+str(expected==entry["verdict"])] += 1
        metrics[arm] = dict(positive=hits,wrong=wrong,correct_hold=held,
                            confusion=dict(conf),changes=dict(by_change))
    return dict(metrics=metrics,rows=result)


def execute(live):
    path = match.DIR/"final.json"
    panel = lab.load(path)
    pair_scores = closed(panel)
    dest = match.DIR/"trace.json.gz"
    compact = match.DIR/"scores.json"
    if live and (dest.exists() or compact.exists()):
        raise FileExistsError("record requires new files")
    saved = {} if live else json.loads(gzip.decompress(dest.read_bytes()))
    cache = saved.get("generations",{})
    run,grade = old.harness(panel)
    with ExitStack() as stack:
        tmp = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(old.ev.loop,"investigate",run))
        stack.enter_context(patch.object(old.runner,"grade",grade))
        rows,ms,sessions = old.runner.run(tmp,panel,live,cache,ARMS)
    if not live:
        ms,sessions = saved["ms"],saved["sessions"]
    metrics = {arm:old.summary(rows,ms,cache,arm,panel) for arm in ARMS}
    scores = []
    for row in rows:
        for a,b,c in zip(*(row[k]["identity"] for k in ("learn_roles","learn_bag","identity_rank")),strict=True):
            assert a["hypothesis"].get("pool")==b["hypothesis"].get("pool")==c["hypothesis"].get("pool")
        arms = {}
        for arm in ARMS:
            r = row[arm]
            arms[arm] = dict(state=r["answer"]["state"],full=r["full"],useful_partial=r["useful_partial"],
                             false_complete=r["false_complete"],mentions=[{k:x[k] for k in (
                                 "gold","chosen","rank","wrong","understood","fact","issues")} for x in r["identity"]])
        scores.append(dict(id=row["id"],question=row["question"],arms=arms))
    data = dict(panel_blob=old.ev.pilot.git("hash-object",str(path)).decode().strip(),generations=cache,
                rows=rows,ms=ms,sessions=sessions,metrics=metrics,closed=pair_scores)
    lab.artifact(dest,data,live)
    lab.artifact(compact,dict(metrics=metrics,questions=scores,closed=pair_scores),live)
    print("closed",pair_scores["metrics"])
    for arm,m in metrics.items():
        print(arm,{k:m[k] for k in ("right","wrong","facts","full","useful_partial","false_complete","refused","calls","median_ms")})


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("record","verify","check-panel"))
    mode=cli.parse_args().mode
    if mode=="check-panel":
        panel=lab.load(match.DIR/"final.json")
        for c in panel["cases"]:
            old.prior.hints(c,panel,0)
        print("rubric spans",len(panel["cases"]))
    else:
        execute(mode=="record")
