"""Evaluate held-out, prior-version and retention tasks without allowing the learner to see labels."""
import argparse
from difflib import SequenceMatcher
import json
from math import comb
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_experience_policy as build

prev=build.prev
policy=build.policy
TRANSFER="0684a301923f8362512d46dc6a50b5c45e4d324b:docs/maintenance/core_12/transfer.json"
GROUPED="c2dec15999c2f12b838106487a8f2d25aa59f371:docs/maintenance/core_12/grouped_transfer.json"
ARMS=("requirements","residual",*policy.ACTIONS,"experience_rule","experience_seed",
      "experience_release",*policy.LEARNERS)
RETENTION=("memory_only","lexical_parts","experience_seed","experience_release","receipt_seed","receipt_trained")


def shape(question):
    q=policy.req.goals.QUOTES.sub(" объект ",question.lower().replace("ё","е"))
    return " ".join(re.findall(r"[а-яa-z]+",q))


def audit(panel,strict=True):
    """Check disjoint target incidents and delexicalized question overlap across partitions."""
    training=json.loads(prev.ev.pilot.git("show",build.TRAIN))
    calibration=json.loads(prev.ev.pilot.git("show",build.CALIBRATION))
    partitions={"experience":training,"calibration":calibration,"transfer":panel}
    pairs=[]
    for name,other in (("experience","calibration"),("experience","transfer"),("calibration","transfer")):
        a,b=partitions[name],partitions[other]
        if strict:
            assert not build.signatures(a)&build.signatures(b)
        incidents=lambda p:{(v[1],v[3]) for v in p["targets"].values()}
        assert not incidents(a)&incidents(b)
        candidates=[(SequenceMatcher(None,shape(q),shape(r),autojunk=False).ratio(),i,j)
                    for i,q,_ in a["cases"] for j,r,_ in b["cases"]]
        closest=max(candidates)
        assert closest[0]<.78,(name,other,closest)
        pairs.append(dict(pair=[name,other],maximum_ratio=round(closest[0],4),ids=closest[1:]))
    return pairs


def compare(panel,rows,metrics):
    by_id={r["id"]:r for r in rows}
    rubric={c[0]:c for c in panel["cases"]}
    groups=panel.get("paraphrase_families",[])
    paired={k for group in groups for k in group}
    families=[*groups,*[[k] for k in by_id if k not in paired]]
    def useful(row,arm):
        return build.reward(rubric[row["id"]],row[arm],panel["targets"])>=2
    scores={}
    for arm in metrics:
        gains=losses=0
        for group in families:
            before=all(useful(by_id[k],"experience_seed") for k in group)
            after=all(useful(by_id[k],arm) for k in group)
            gains+=after and not before
            losses+=before and not after
        n=gains+losses
        unquoted=[r for r in rows if not policy.req.goals.quoted(r["question"])]
        scores[arm]=dict(family_gains=gains,family_losses=losses,
                         unquoted_useful=sum(useful(r,arm) for r in unquoted),unquoted=len(unquoted),
                         reward=sum(build.reward(rubric[r["id"]],r[arm],panel["targets"]) for r in rows),
                         paired_sign_p=round(min(1,2*sum(comb(n,i) for i in range(min(gains,losses)+1))/2**n),4))
    return dict(families=len(families),scores=scores)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("record","verify","audit","summary"))
    series=parser.add_mutually_exclusive_group()
    series.add_argument("--retention",action="store_true")
    series.add_argument("--domains",action="store_true")
    parser.add_argument("--file",type=Path)
    a=parser.parse_args()
    ref=prev.CONFIRMATION if a.retention else TRANSFER if a.domains else GROUPED
    panel=json.loads(prev.ev.pilot.git("show",ref))
    checks=[] if a.retention else audit(panel,not a.domains)
    if a.mode=="audit":
        print(checks)
        return
    arms=RETENTION if a.retention else ARMS
    path=a.file or build.DIR/("retention.json" if a.retention else "domains.json" if a.domains else "results.json")
    live=a.mode=="record"
    if live and path.exists():
        parser.error("record requires a new output path")
    saved={} if live else json.loads(path.read_text(encoding="utf8"))
    if a.mode=="summary":
        assert saved["plan"]==ref
        print(json.dumps(compare(panel,saved["rows"],saved["metrics"]),indent=1))
        return
    cache=saved.get("generations",{})
    with tempfile.TemporaryDirectory() as tmp:
        rows,ms,sessions=prev.run(Path(tmp),panel,live and not a.retention,cache,arms)
    if not live:
        assert saved["rows"]==rows and saved["plan"]==ref
        assert set(cache)=={key for row in rows for arm in arms for key in row[arm]["calls"]}
        ms=saved["ms"]
    metrics=build.scoring.score(panel,rows,ms,cache,arms)
    for arm in arms:
        shared=0
        for row in rows:
            parts=row[arm]["answer"].get("parts",[])
            refs=[i for part in parts for i in part["claims"]]
            shared+=len(refs)!=len(set(refs))
        metrics[arm]["questions_reusing_claims"]=shared
    if live:
        with path.open("x",encoding="utf8",newline="\n") as f:
            json.dump(dict(plan=ref,split_audit=checks,metrics=metrics,rows=rows,ms=ms,
                           sessions=sessions,generations=cache),f,ensure_ascii=False,indent=1)
            f.write("\n")
    else:
        assert saved["metrics"]==metrics and saved["split_audit"]==json.loads(json.dumps(checks))
    for name,stats in metrics.items():
        print(name,*(stats[k] for k in ("full","partial","strict_partial","false_complete","facts",
              "understood","status","insufficient","questions_reusing_claims","median_ms","calls")))


if __name__=="__main__":
    main()
