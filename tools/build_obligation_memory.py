"""Build the language memory exclusively from three pinned, previously published human rubrics."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_obligation_check as check

BASE = "a801f03501b53d86782e61967c7eddaa4f362b48"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).with_name("skynet_obligation_memory.json")


def read(relative):
    raw = subprocess.check_output(["git","show",f"{BASE}:docs/maintenance/{relative}.json"],cwd=ROOT)
    return json.loads(raw)


def annotated(panel):
    for _,question,demands in panel["cases"]:
        starts = [re.search(r"(?<!\w)"+re.escape(cue),question).start() for cue,_,_ in demands]
        assert starts == sorted(set(starts))
        for i,(_,_,label) in enumerate(demands):
            start = starts[i] if i else 0
            end = starts[i+1] if i+1 < len(starts) else len(question)
            yield " ".join(check.words(question[start:end])),label


def build():
    examples = set(annotated(read("core_10/transfer")))
    for _,_,question,labels,*_ in read("core_09/transfer")["cases"]:
        leaves = [k for k in labels.split() if k!="site"]
        if len(leaves)<=1 and labels:
            examples.add((" ".join(check.words(question.replace("{x}", ""))), (leaves or ["site"])[0]))
    examples = sorted(examples)
    memory = check.Memory(examples)
    calibration = list(annotated(read("core_10/confirmation")))
    errors, peaks = [], []
    for text,label in calibration:
        scores = memory.scores(text)
        best = max(scores.values())
        errors.append(best-scores.get(label,0))
        peaks.append(best)
    # Empirical 80th percentile of the correct label's gap; low novelty cutoff.
    # Fragments share questions: this is a development operating point, not a confidence guarantee.
    quantile = lambda values,p: sorted(values)[math.ceil(p*len(values))-1]
    return dict(training_base=BASE, examples=examples, calibration_count=len(calibration),
                margin=round(quantile(errors,.80),6),floor=round(quantile(peaks,.10),6))


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    content=json.dumps(build(),ensure_ascii=False,indent=1)+"\n"
    if args.verify:
        assert OUTPUT.read_text(encoding="utf8")==content
    else:
        OUTPUT.write_text(content,encoding="utf8",newline="\n")
