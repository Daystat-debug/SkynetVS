"""Frozen laboratory inference over raw pairs. Predictions cannot supply coordinates or proof."""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "docs/maintenance/core_19"
LABELS = ("equal", "different", "unknown")
TAGS = ("o", "a", "r", "x", "b", "n")


def words(text):
    return re.findall(r"[^\W_]+", text.casefold().replace("ё","е"))[:96]


def context(seq, i, previous):
    window = [seq[j] if 0 <= j < len(seq) else "#" for j in range(i-2,i+3)]
    keys = ["bias", "prevtag/"+previous]
    for j,word in enumerate(window):
        keys.extend((f"{j}w/{word}",f"{j}s/{word[-2:]}",f"{j}p/{word[:3]}"))
    keys.extend(("left/"+window[1]+"/"+window[2][-2:], "right/"+window[3]+"/"+window[2][-2:]))
    return keys


def tag(weights, keys):
    scores = [0.] * len(TAGS)
    for key in keys:
        if key in weights:
            for j, value in enumerate(weights[key]):
                scores[j] += value
    return max(range(len(TAGS)), key=scores.__getitem__)


def analyze(text, model):
    seq = words(text)
    frame = {t:[] for t in TAGS[1:]}
    prev = "o"
    for i, word in enumerate(seq):
        prev = TAGS[tag(model["tagger"],context(seq,i,prev))]
        if prev != "o":
            frame[prev].append(model["predicates"].get(word,word) if prev=="r" else word)
    return seq, frame


@lru_cache(maxsize=8192)
def similarity(a,b):
    if a==b:
        return 1.
    length = 0
    for x,y in zip(a,b):
        if x!=y:
            break
        length += 1
    return length / max(len(a),len(b))


def coverage(left,right):
    return sum(max((similarity(a,b) for b in right),default=0.) for a in left)/max(1,len(left))


def features(left,right,structured):
    q,f = left
    s,g = right
    result = [1.,coverage(q,s),coverage(s,q),len(set(q)&set(s))/max(1,len(set(q)|set(s)))]
    if structured:
        for role in ("a","r","x","b"):
            a,b = f[role],g[role]
            result.extend((float(bool(a)!=bool(b)),float(bool(a and b)),
                           min(coverage(a,b),coverage(b,a))))
        result.extend((float(bool(f["n"])!=bool(g["n"])),coverage(f["a"],g["b"]),
                       coverage(f["b"],g["a"])))
    return result


def probabilities(weights, values):
    scores = [sum(w*v for w,v in zip(row,values,strict=True)) for row in weights]
    peak = max(scores)
    mass = [math.exp(s-peak) for s in scores]
    return [v/sum(mass) for v in mass]


def infer(question, labels, model, arm):
    structured = arm=="learn_roles"
    def encode(text):
        return analyze(text,model) if structured else (words(text),{})
    q = encode(question)
    predictions = []
    for label in labels:
        s = encode(label)
        probs = probabilities(model[arm],features(q,s,structured))
        verdict = LABELS[max(range(len(probs)),key=probs.__getitem__)]
        predictions.append(dict(probs=[round(v,8) for v in probs], verdict=verdict, frame=s[1]))
    return q[1], predictions


def decide(predictions, cutoff, margin):
    order = sorted(range(len(predictions)),key=lambda j:-predictions[j]["probs"][0])
    if not order:
        return None
    top = predictions[order[0]]
    next_score = predictions[order[1]]["probs"][0] if len(order)>1 else 0.
    if top["verdict"]=="equal" and top["probs"][0]>=cutoff and top["probs"][0]-next_score>=margin:
        return order[0]
    return None


@lru_cache(maxsize=1)
def frozen():
    return json.loads((DIR/"weights.json").read_text(encoding="utf8"))


def propose(parts,catalog,policy,skip,shortlist,payload):
    model = frozen()
    menus = {i:shortlist(part["text"],catalog)[0] for i,part in enumerate(parts) if not skip(part["text"])}
    if menus and payload(parts,catalog,menus) is None:
        return {i:dict(pool=[],first=None,chosen=None,why="input_budget") for i in menus}
    records = {}
    for i,pool in menus.items():
        frame, predictions = infer(parts[i]["text"],[catalog[k].label[:120] for k in pool],model,policy)
        position = decide(predictions,*model["thresholds"][policy])
        chosen = pool[position] if position is not None else None
        records[i] = dict(pool=pool,first=chosen,chosen=chosen,why=policy if chosen is not None else "ambiguous",
                          query_frame=frame,pairs=predictions)
    return records
