"""Compare five policies on the same pinned Git snapshots; replay saved local completions."""
import argparse
import json
from pathlib import Path
import re
from statistics import median
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_task_parts as previous

PLAN = "b0aa0ba5a0fe72f1888ca0de0aba10781e0c6b98:docs/maintenance/core_11/control.json"
ARMS = ("requirements","residual","lexical_parts","memory_only","independent")
DIR = previous.DIR.parent/"core_11"


def score(plan, rows, times, cache, arms=ARMS):
    totals = {}
    rank,_ = previous.ev.old.blob(previous.ev.pilot.ROOT,plan["base"],previous.ev.old.RANK)
    base_lines = len(rank.splitlines())
    for arm in arms:
        metrics = dict(facts=0, understood=0, status=0, full=0, partial=0, strict_partial=0,
                       false_complete=0, insufficient=0, unrelated_sites=0,steps=0)
        for case,row in zip(plan["cases"],rows,strict=True):
            key,q,demands = case
            assert key==row["id"] and q==row["question"]
            rec = row[arm]
            out = rec["answer"]
            parts = out.get("parts",[])
            sites = [c for c in out["claims"] if c.get("kind")=="site"]
            targets = [plan["targets"][t] for _,t,_ in demands if t!="-"]
            unrelated = any(not any(owner in c["text"] and label in c["text"] and
                any(code==path and start<=line+(base_lines if key[0]!="R" else 0)<=end for code,start,end in c["refs"])
                for path,owner,line,label,*_ in targets) for c in sites)
            strict_gap = True
            for cue,t,kind in demands:
                if t!="-":
                    continue
                part = next((p for p in parts if re.search(r"(?<!\w)"+re.escape(cue),p["text"])),{})
                reasons = set(part.get("issues",[]))
                strict_gap &= reasons.intersection(("runtime","external","unsupported","ambiguous"))=={kind}
            metrics["facts"]+=sum(s["proved"] is True for s in rec["scores"])
            metrics["understood"]+=sum(s["understood"] for s in rec["scores"])
            metrics["status"]+=rec["status_correct"]
            metrics["full"]+=rec["useful_full"] and not unrelated
            metrics["partial"]+=rec["useful_partial"] and not unrelated
            metrics["strict_partial"]+=rec["useful_partial"] and strict_gap and not unrelated
            metrics["false_complete"]+=rec["false_complete"] or (out["state"]=="answered" and unrelated)
            metrics["unrelated_sites"]+=unrelated
            metrics["insufficient"]+=out["state"]=="insufficient"
            metrics["steps"]+=len(out["steps"])
        gens = [v for k,v in cache.items() if k.split("/")[1]==arm]
        totals[arm]=dict(metrics,median_ms=round(median(t[arm] for t in times.values()),1),calls=len(gens),
                          input_tokens=sum(g["prompt_tokens"] for g in gens),output_tokens=sum(g["completion_tokens"] for g in gens))
    return totals


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("record","verify","ablate"))
    parser.add_argument("--file",type=Path,default=DIR/"results.json")
    args=parser.parse_args()
    live=args.mode=="record"
    if live and args.file.exists():
        parser.error("record requires a new file")
    saved={} if live else json.loads(args.file.read_text(encoding="utf8"))
    cache=saved.get("generations",{})
    plan=json.loads(previous.ev.pilot.git("show",PLAN))
    if args.mode=="ablate":
        # Keep the segmentation and first Qwen generation identical. Remove the
        # independent obligations only. Same-segment lexical control uses no model.
        import skynet_obligation_check
        import skynet_task_parts
        arms=("parts_once","lexical_parts")
        reused={k.replace("/independent/","/parts_once/"):v for k,v in cache.items() if "/independent/" in k}
        with tempfile.TemporaryDirectory() as tmp, patch.object(skynet_task_parts,"split",skynet_obligation_check.segment):
            rows,times,_=previous.run(Path(tmp),plan,False,reused,arms)
        stats=score(plan,rows,times,reused,arms)
        for values in stats.values():
            del values["median_ms"]  # cached model output cannot measure live latency
        data=dict(plan=PLAN,metrics=stats,rows=rows)
        path=DIR/"ablation.json"
        if path.exists():
            assert json.loads(path.read_text(encoding="utf8"))==data
        else:
            with path.open("x",encoding="utf8",newline="\n") as f:
                json.dump(data,f,ensure_ascii=False,indent=1)
                f.write("\n")
        print(json.dumps(stats,indent=1))
        return
    with tempfile.TemporaryDirectory() as tmp:
        rows,times,sessions=previous.run(Path(tmp),plan,live,cache,ARMS)
    if not live:
        assert saved["plan"]==PLAN and rows==saved["rows"]
        assert set(cache)=={key for row in rows for arm in ARMS for key in row[arm]["calls"]}
        times=saved["ms"]
    metrics=score(plan,rows,times,cache)
    if live:
        with args.file.open("x",encoding="utf8",newline="\n") as f:
            json.dump(dict(plan=PLAN,metrics=metrics,rows=rows,ms=times,generations=cache,sessions=sessions),
                      f,ensure_ascii=False,indent=1)
            f.write("\n")
    else:
        assert metrics==saved["metrics"]
    print(json.dumps(metrics,indent=1))

if __name__=="__main__":
    main()
