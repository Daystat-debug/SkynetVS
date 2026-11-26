"""Counterfactuals on archived frames only. No new extraction, training or host decisions."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_description_match as lab


def audit():
    raw=json.loads(gzip.decompress((lab.m.DIR/"trace.json.gz").read_bytes()))
    selected=lab.m.models()["selected"]
    rows=[]
    counts=Counter()
    signs={"question":Counter(),"source":Counter()}
    seen=set()
    for row in raw["closed"]["individual"]:
        x=row["interpretations"][selected]["frames"]
        y=row["interpretations"]["gold_both"]["frames"]
        signs["question"][y[0]["sign"]+"/"+x[0]["sign"]]+=1
        for i,k in enumerate(row["menu"],1):
            if k not in seen:
                signs["source"][y[i]["sign"]+"/"+x[i]["sign"]]+=1
                seen.add(k)
        results={}
        for name,q,sources in (("known_question",y[0],x[1:]),("known_sources",x[0],y[1:])):
            decisions=[lab.m.compare(q,s) for s in sources]
            j=lab.m.select(decisions)
            chosen=None if j is None else row["menu"][j]
            results[name]=dict(chosen=chosen,decisions=decisions)
            counts[name+"/correct_positive"]+=chosen==row["target"]
            counts[name+"/wrong"]+=chosen is not None and chosen!=row["target"]
        rows.append(dict(id=row["id"],cue=row["cue"],target=row["target"],results=results))
    return json.loads(json.dumps(dict(metrics=counts,signs=signs,individual=rows),ensure_ascii=False))


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("write","verify"))
    result=audit()
    lab.prev.lab.artifact(lab.m.DIR/"side_audit.json",result,cli.parse_args().mode=="write")
    print(result["metrics"],result["signs"])
