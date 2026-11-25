"""A requested answer slot belongs to a source expression. Dependencies only support that slot."""
from collections import Counter, defaultdict
from functools import lru_cache
import json
import math
from pathlib import Path

import skynet_obligation_check as memory

req = memory.req
POLICIES = ("relation_nearest", "relation_frame")
MODEL = Path(__file__).with_name("skynet_relation_fit.json")


def wording(text, label=""):
    # Remove only overlap with the grounded expression; leave relation words in discourse order.
    subject = set(req.goals.terms(label))
    words = memory.words(text)
    return " ".join(w for w in words if not (len(w) >= 4 and subject.intersection(req.goals.terms(w))))


def vector(text):
    words = text.split()
    features = memory.features(text)
    features.update("pair:" + a + "_" + b for a, b in zip(words, words[1:]))
    return features


class Classifier:
    """Cosine nearest neighbour and a regularized linear least-squares readout on the same vectors."""
    def __init__(self, examples):
        docs = [vector(text) for text, _ in examples]
        df = Counter(f for doc in docs for f in doc)
        self.idf = {f: 1 + math.log((1 + len(docs)) / (1 + n)) for f, n in df.items()}
        self.rows = [(self.encode(doc), label) for doc, (_, label) in zip(docs, examples)]
        self.labels = sorted({label for _, label in examples})
        # Deterministic dual coordinate descent, squared loss, unit-normalized rows and ridge=1.
        self.weights = {k: defaultdict(float) for k in self.labels}
        for label, weights in self.weights.items():
            dual = [0.] * len(self.rows)
            for _ in range(12):
                for i, (row, k) in enumerate(self.rows):
                    pred = sum(weights[f] * x for f, x in row.items())
                    delta = ((k == label) - pred - dual[i]) / 2
                    dual[i] += delta
                    for f, x in row.items():
                        weights[f] += delta * x

    def encode(self, features):
        raw = {f: self.idf.get(f, 2.) for f in sorted(features)}
        norm = math.sqrt(sum(x*x for x in raw.values()))
        return {f: x/norm for f, x in raw.items()}

    def predict(self, text, nearest):
        query = self.encode(vector(text))
        scores = {k: 0. for k in self.labels}
        for row, label in self.rows:
            scores[label] = max(scores[label], sum(x * row.get(f, 0.) for f, x in query.items()))
        if not nearest:
            for label, weights in self.weights.items():
                scores[label] = (scores[label] + sum(x * weights.get(f, 0.) for f, x in query.items())) / 2
        first, second = sorted(scores, key=scores.get, reverse=True)[:2]
        return first, scores[first], scores[first] - scores[second]


@lru_cache(maxsize=1)
def fitted():
    data = json.loads(MODEL.read_text(encoding="utf8"))
    return Classifier(data["examples"]), data["cutoffs"]


def interpret(parts, edges, effects, policy):
    model, cutoffs = fitted()
    simple = policy == "relation_nearest"
    decisions = []
    for i, (part, edge) in enumerate(zip(parts, edges, strict=True)):
        expr = effects.get(edge["target"])
        raw = part["text"]
        query = wording(raw, expr.label if expr else "")
        source = None
        # A coordinated literal can inherit a predicate, independently of its object identity.
        if (not simple and i and req.goals.quoted(raw) and query.split() in (["и"], ["а", "также"])
                and decisions[-1]["kind"] in req.KINDS):
            kind = decisions[-1]["kind"]
            source = i - 1
        else:
            kind, score, margin = model.predict(query, simple)
            floor, separation = cutoffs[policy]
            if score < floor or margin < separation:
                kind = "unverified_meaning"
        if req.goals.route.arguments.cli.auto_reader.EVENT.search(raw):
            kind, source = "runtime", None
        decisions.append(dict(kind=kind, inherited_from=source))
    return decisions


def plan(decisions):
    return [(list(req.closure([r["kind"]])), [], i) if r["kind"] in req.KINDS
            else ([], [r["kind"]], i) for i, r in enumerate(decisions)]


def projection(part, decision, claims):
    kind = decision["kind"]
    direct = [n for n in part["claims"] if claims[n]["kind"] == kind]
    return dict(**decision, direct=direct, support=[n for n in part["claims"] if n not in direct])


def verify(parts, meta, claims, catalog, commit, policy):
    import skynet_object_binding as objects
    edges, effects = objects.resolve(parts, catalog, commit, policy)
    decisions = interpret(parts, edges, effects, policy)
    for p, decision, (needs, gaps, _) in zip(meta["parts"], decisions, plan(decisions), strict=True):
        expected = projection(p, decision, claims)
        if (p.get("relation") != expected or p["need"] != needs or not set(gaps) <= set(p["issues"])
                or (p["status"] == "established" and not expected["direct"])):
            raise req.observed.route.arguments.host.Rejected("claim_binding")
