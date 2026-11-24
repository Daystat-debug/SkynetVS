"""Independent, example-based request check. Inputs are wording and static receipts only."""
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
import re

import skynet_requirements as req


def words(text):
    return re.findall(r"[а-яa-z0-9]+", req.goals.QUOTES.sub(" ", text.casefold().replace("ё", "е")))


def features(text):
    result = set()
    for word in words(text):
        padded = "^" + word + "$"
        result.add(word)
        result.update(padded[i:i+3] for i in range(len(padded)-2))
    return result


def segment(question):
    """Keep punctuation in the original span, never split a quoted source anchor."""
    masked = req.goals.QUOTES.sub(lambda m: "_" * len(m[0]), question)
    starts = [0]
    for m in re.finditer(r"(?<=[,;!?.:\n])\s+(?=\S)|\s+(?=(?:и|но|а)\s+)", masked, re.I):
        if question[starts[-1]:m.end()].strip():
            starts.append(m.end())
    return [dict(start=a, end=b, text=question[a:b])
            for a,b in zip(starts, starts[1:]+[len(question)])]


class Memory:
    def __init__(self, examples):
        self.examples = [(features(text), label) for text,label in examples]
        counts = Counter(f for fs,_ in self.examples for f in fs)
        self.weight = {f: 1 + math.log((1+len(examples))/(1+n)) for f,n in counts.items()}

    def scores(self, text):
        query = features(text)
        def mass(fs):
            return sum(self.weight.get(f, 2) for f in sorted(fs))
        size = mass(query)
        best = {}
        for fs,label in self.examples:
            shared = mass(query & fs)
            similarity = shared / max(1, math.sqrt(size * mass(fs)))
            best[label] = max(best.get(label, 0), similarity)
        return best


@lru_cache(maxsize=1)
def load():
    data = json.loads(Path(__file__).with_name("skynet_obligation_memory.json").read_text(encoding="utf8"))
    return Memory(data["examples"]), data["margin"], data["floor"]


@lru_cache(maxsize=128)
def alternatives(text):
    memory, margin, floor = load()
    scores = memory.scores(text)
    best = max(scores.values())
    if best < floor:
        return ()
    return tuple(sorted(k for k,v in scores.items() if best-v <= margin and v > 0))


def expected(text):
    plausible = alternatives(text)
    if not plausible or len(plausible)>2:
        return (), ("unverified_meaning",)
    static = req.closure([k for k in plausible if k in req.KINDS])
    gaps = tuple(k for k in plausible if k not in req.KINDS)
    if len(plausible)>1 and gaps:
        gaps = ("unverified_meaning",)
    return static, gaps


def augment(parts, proposals):
    planned = []
    for part,(needs,issues,target) in zip(parts,proposals,strict=True):
        required,missing = expected(part["text"])
        if required and issues == ["uninterpreted"]:
            issues = []
        # Collect the union now, so a stronger independent interpretation can obtain evidence.
        planned.append((list(req.closure([*needs,*required])),list(dict.fromkeys([*issues,*missing])),target))
    return planned


def verify(parts, claims):
    """Recompute from verbatim spans and actual facts, without trusting planner.need or a review vote."""
    for part in parts:
        required, gaps = expected(part["text"])
        bound = [claims[i] for i in part["claims"]]
        kinds = {row["kind"] for row in bound}
        if part["status"] == "established":
            quotes = req.goals.quoted(part["text"]) or req.goals.quoted(parts[part["target"]]["text"])
            sites = [row["text"] for row in bound if row["kind"]=="site"]
            if (gaps or not set(required) <= kinds or
                    any(not any(q.casefold() in site.casefold() for site in sites) for q in quotes)):
                raise req.observed.route.arguments.host.Rejected("claim_binding")
