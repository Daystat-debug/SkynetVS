"""Replay training/calibration snapshots, fit a bounded policy, and reproduce its provenance."""
import argparse
import json
import random
import re
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_obligation_check as scoring
import skynet_experience as policy
from skynet_task_parts import split

prev=scoring.previous
DIR=scoring.DIR.parent/"core_12"
TRAIN=scoring.PLAN
CALIBRATION="17d444011f52c19b1f3d4ad5b062383655bc9827:docs/maintenance/core_12/grouped_calibration.json"


def signatures(panel):
    return {tuple(sorted(kind for _,_,kind in demands)) for _,_,demands in panel["cases"]}


def reward(case, row, targets):
    # Static evidence has already passed the independent per-demand oracle in previous.grade.
    out=row["answer"]
    wanted=[targets[t] for _,t,_ in case[2] if t!="-"]
    wrong=any(not any(owner in c["text"] and label in c["text"] for _,owner,_,label,*_ in wanted)
              for c in out["claims"] if c["kind"]=="site")
    if wrong or row["false_complete"]:
        return -6
    if row["useful_full"]:
        return 5
    gaps=[s for s in row["scores"] if s["proved"] is None]
    typed=all(s["understood"] for s in gaps)
    if row["useful_partial"]:
        return 4 if typed else 2
    if row["expected"]=="insufficient" and row["status_correct"] and typed:
        return 1
    return 0


def experience(ref,arms=policy.ACTIONS):
    panel=json.loads(prev.ev.pilot.git("show",ref))
    with tempfile.TemporaryDirectory() as tmp:
        rows,_,_=prev.run(Path(tmp),panel,False,{},arms)
    samples=[]
    for case,row in zip(panel["cases"],rows,strict=True):
        outcomes={k:reward(case,row[k],panel["targets"]) for k in arms}
        samples.append(dict(id=row["id"],features=policy.features(row["question"]),reward=outcomes))
    return samples,rows


def train_receipts(cases,rows):
    # One record per original span. Keep all labels for a multi-demand span together.
    examples=[]
    for case,row in zip(cases,rows,strict=True):
        assert case[0]==row["id"] and case[1]==row["question"]
        parts=split(case[1])
        assigned=0
        for part,(signals,prior,_) in zip(parts,policy.clause_inputs(parts),strict=True):
            labels=[k for cue,_,k in case[2] if re.search(r"(?<!\w)"+re.escape(cue),part["text"])]
            assigned+=len(labels)
            # Unannotated connective fragments are not gold negative examples.
            if labels:
                examples.append((signals,prior,set(labels),row["shared_evidence"]["false_complete"]))
        assert assigned==len(case[2])
    # Mask rare lexical features so a single question cannot teach an object name.
    from collections import Counter
    counts=Counter(k for signals,_,_,_ in examples for k in signals)
    weights={label:{} for label in policy.LABELS}
    rng=random.Random(1203)
    for _ in range(6):
        rng.shuffle(examples)
        for signals,prior,labels,was_false_complete in examples:
            active={k:v for k,v in signals.items() if not k.startswith("word/") or counts[k]>=2}
            norm=sum(v*v for _,v in sorted(active.items()))
            for label,w in weights.items():
                sign=1 if label in labels else -1
                loss=1-sign*policy.margin(w,active,label in prior)
                if loss>0:
                    delta=sign*min(1.0 if was_false_complete else .5,loss/norm)
                    for key,value in active.items():
                        w[key]=w.get(key,0.0)+delta*value
    return {label:{k:round(w[k],8) for k in sorted(w) if abs(w[k])>=1e-8} for label,w in weights.items()}


def build():
    assert not signatures(json.loads(prev.ev.pilot.git("show",TRAIN))) & signatures(
        json.loads(prev.ev.pilot.git("show",CALIBRATION)))
    training,train_rows=experience(TRAIN)
    calibration,cal_rows=experience(CALIBRATION)
    seed=[r for r in training if r["id"].startswith("R")]
    trials=[]
    for depth in range(3):
        tree,_=policy.fit(training,depth)
        utility=sum(r["reward"][policy.apply(tree,r["features"])] for r in calibration)
        trials.append((utility,depth))
    depth=max(trials,key=lambda row:(row[0],-row[1]))[1]
    model=dict(experience=policy.fit(training,depth)[0],experience_seed=policy.fit(seed,depth)[0],
               experience_global=policy.constant(training)[0])
    cases=json.loads(prev.ev.pilot.git("show",TRAIN))["cases"]
    for name,subset in (("receipt_zero",[]),("receipt_seed",[i for i,r in enumerate(training) if r in seed]),
                        ("receipt_trained",list(range(len(cases))))):
        model[name]=dict(weights=train_receipts([cases[i] for i in subset],[train_rows[i] for i in subset]),threshold=0)
    calibrations=[]
    with patch.object(policy,"model",lambda:model):
        for threshold in (0,.35,.70):
            model["receipt_trained"]["threshold"]=threshold
            feedback,_=experience(CALIBRATION,("receipt_trained",))
            calibrations.append((sum(r["reward"]["receipt_trained"] for r in feedback),threshold))
    best,threshold=max(calibrations,key=lambda entry:entry[0])
    for name in policy.LEARNERS:
        model[name]["threshold"]=threshold
    model["selected"]="receipt_trained" if best>max(x for x,_ in trials) else "experience"
    log=dict(training=TRAIN,calibration=CALIBRATION,seed=[r["id"] for r in seed],
             calibration_trials=trials,depth=depth,train_feedback=training,calibration_feedback=calibration,
             train_answers=train_rows,calibration_answers=cal_rows,receipt_calibration=calibrations)
    return model,log


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    model,log=build()
    for path,data in ((policy.MODEL,model),(DIR/"experience.json",log)):
        text=json.dumps(data,ensure_ascii=False,indent=1)+"\n"
        if args.verify:
            assert path.read_text(encoding="utf8")==text,path
        else:
            path.write_text(text,encoding="utf8",newline="\n")
    print(model["experience"],model["selected"],log["receipt_calibration"])
    print("calibration rewards / depth",log["calibration_trials"])


if __name__=="__main__":
    main()
