"""Offline policy learning over audited outcomes. The runtime can select only fixed readers."""
from functools import lru_cache
import json
import math
from pathlib import Path

import skynet_obligation_check as memory

req = memory.req
ACTIONS = ("memory_only", "lexical_parts", "shared_evidence")
POLICIES = ("experience_seed", "experience", "experience_global", "experience_rule","experience_release")
LEARNERS = ("receipt_zero", "receipt_seed", "receipt_trained")
LABELS = req.KINDS + ("runtime","external","ambiguous","unsupported")
MODEL = Path(__file__).with_name("skynet_experience_policy.json")


def shared_plan(parts):
    """Pool requests about the same literal; collect the union of the requested receipt types."""
    if len(parts)>8:
        return [([],["part_budget"],i) for i in range(len(parts))]
    target = 0
    seen = {}
    previous = ()
    planned = []
    for i,part in enumerate(parts):
        text = part["text"]
        quotes = req.goals.quoted(text)
        if quotes:
            target = seen.setdefault(tuple(q.casefold() for q in quotes),i)
        needs, gaps = memory.expected(text)
        operation = req.language.operation(text)
        signal = {"where":("site",),"when":("condition",),"via":("caller",)}.get(operation,())
        if signal and not set(gaps).difference({"unverified_meaning"}):
            needs = req.closure([*needs,*signal])
            # A lexical reading cannot resolve a competing non-static interpretation.
            if gaps and not memory.alternatives(text):
                gaps = ()
        if quotes and previous and i and len(memory.words(text))<=3 and not signal and not gaps:
            needs = req.closure([*previous,*needs])
        planned.append((list(needs),list(gaps),target))
        previous = needs if not gaps else ()
    return planned


def features(question):
    from skynet_task_parts import split
    parts = split(question)
    quotes = req.goals.quoted(question)
    readings = [memory.expected(p["text"]) for p in parts]
    return {
        "quote":bool(quotes),
        "several_quotes":len(quotes)>1,
        "compound":len(parts)>1,
        "comma_split":len(memory.segment(question))!=len(parts),
        "lexical":bool(req.language.operation(question)),
        "uncertain":any("unverified_meaning" in gaps for _,gaps in readings),
        "nonstatic":any(set(gaps)-{"unverified_meaning"} for _,gaps in readings),
        "has_static":any(needs for needs,_ in readings),
        "shared_subject":len(parts)>1 and len(set(quotes))==1,
    }


def constant(samples):
    totals = {k:sum(row["reward"][k] for row in samples) for k in ACTIONS}
    choice = max(ACTIONS,key=totals.get)
    return {"action":choice},totals[choice]


def fit(samples,depth):
    leaf, best = constant(samples)
    if not depth or len(samples)<6:
        return leaf,best
    tree = leaf
    for key in sorted(samples[0]["features"]):
        left = [row for row in samples if not row["features"][key]]
        right = [row for row in samples if row["features"][key]]
        if min(len(left),len(right))<3:
            continue
        lo,a = fit(left,depth-1)
        hi,b = fit(right,depth-1)
        # Charge for each split in units of the prespecified task reward.
        gain = a+b-2
        if gain>best:
            tree,best = dict(feature=key,no=lo,yes=hi),gain
    return tree,best


def apply(tree, signals):
    while "feature" in tree:
        tree = tree["yes" if signals[tree["feature"]] else "no"]
    action = tree["action"]
    if action not in ACTIONS:
        raise ValueError("invalid experience action")
    return action


@lru_cache(maxsize=1)
def model():
    return json.loads(MODEL.read_text(encoding="utf8"))


def select(policy,question):
    if policy=="experience_rule":
        return "memory_only" if req.goals.quoted(question) else "lexical_parts"
    if policy=="experience_release":
        policy=model()["selected"]
        if policy=="receipt_trained":
            return policy
        if policy!="experience":
            raise ValueError("invalid release policy")
    return apply(model()[policy],features(question))


def clause_inputs(parts):
    """Local and neighboring evidence requests. Never include a quotation or a source identifier."""
    proposals = shared_plan(parts)
    context = set()
    for i,(p,(needs,gaps,target)) in enumerate(zip(parts,proposals,strict=True)):
        leaves = set(needs) | (set(gaps) & set(LABELS))
        if len(needs)>1:
            leaves.discard("site")
        if "arguments" in leaves or "caller_condition" in leaves:
            leaves.discard("caller")
        words = [w for w in memory.words(p["text"]) if w.isalpha() and not w.isascii()]
        signals = {"bias":1.0}
        for prefix,names in (("prior/",leaves),("previous/",context)):
            signals.update((prefix+n,1.0) for n in names)
        for key,flag in (("quoted",req.goals.quoted(p["text"])),("linked",target!=i),
                         ("compound",len(parts)>1),("short",len(words)<4)):
            if flag:
                signals[key]=1.0
        vocab = {"word/"+w[:5] for w in words}
        signals.update((key,1/math.sqrt(max(1,len(vocab)))) for key in vocab)
        yield signals,leaves,target
        context = leaves


def margin(weights,signals,initial):
    return (1.0 if initial else -1.0)+sum(weights.get(k,0.0)*v for k,v in sorted(signals.items()))


def learned_plan(parts,version):
    if len(parts)>8:
        return [([],["part_budget"],i) for i in range(len(parts))]
    params=model()[version]
    plan=[]
    for signals,prior,target in clause_inputs(parts):
        labels=[k for k in LABELS if margin(params["weights"][k],signals,k in prior)>params["threshold"]]
        needs=req.closure([k for k in labels if k in req.KINDS])
        issues=[k for k in labels if k not in req.KINDS]
        if not labels:
            issues=["unverified_meaning"]
        plan.append((list(needs),issues,target))
    return plan
