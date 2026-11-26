"""Summarize train-to-transfer behavior without fitting or changing the frozen decisions."""
import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_learned_match as lab


def summarize():
    base=lab.match.DIR
    corpus=json.loads(gzip.decompress((base/"compiled.json.gz").read_bytes()))
    model=lab.match.frozen()
    output={}
    for split,groups in corpus.items():
        metrics={}
        for arm in ("learn_roles","learn_bag"):
            right=wrong=held=positive=0
            for row in groups:
                ss=row["candidates"]
                gold=next((j for j,s in enumerate(ss) if s["label"]=="equal"),None)
                _,pred=lab.match.infer(row["query"]["text"],[s["text"] for s in ss],model,arm)
                choice=lab.match.decide(pred,*model["thresholds"][arm])
                positive+=gold is not None
                right+=choice is not None and choice==gold
                wrong+=choice is not None and choice!=gold
                held+=choice is None and gold is None
            metrics[arm]=dict(positive=positive,right=right,wrong=wrong,correct_hold=held)
        output[split]=metrics
    scores=lab.lab.load(base/"scores.json")
    output["closed"]=scores["closed"]["metrics"]
    output["questions"]={}
    for row in scores["questions"]:
        output["questions"][row["id"]]={arm:dict(
            full=a["full"],useful_partial=a["useful_partial"],false_complete=a["false_complete"],
            facts=sum(bool(x["fact"]) for x in a["mentions"]),wrong=sum(x["wrong"] for x in a["mentions"]))
            for arm,a in row["arms"].items()}
    return output


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("write","verify"))
    lab.lab.artifact(lab.match.DIR/"summary.json",summarize(),cli.parse_args().mode=="write")
