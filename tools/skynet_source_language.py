"""Russian search features keyed by source syntax, never used as proof."""
import ast
from collections import Counter, defaultdict
from functools import lru_cache
from hashlib import sha256
import json
from math import log
from pathlib import Path
import re

import skynet_observation_goal as goals


STOP = set(goals.terms("где когда почему какой какая каком какие может который которых если если бы "
                       "сообщение строка функция участок условие место случае появляется выводится "
                       "формируется записано коде программы найти покажи меня интересует или для при "
                       "чтобы что это как есть будет этим когда ли без по из до во на от со об же"))


def descriptor(effect):
    return json.dumps([effect.fn.node.name, type(effect.stmt).__name__, ast.unparse(effect.expr),
                       effect.guard], ensure_ascii=False, separators=(",", ":"))


def vocabulary(entries, captions):
    """Conservative cross-document alignment. One example cannot teach an alias."""
    sources, targets, pairs = Counter(), Counter(), defaultdict(Counter)
    for raw in entries:
        caption = captions.get(sha256(raw.encode()).hexdigest(), "")
        if not caption:
            continue
        terms = set(re.findall(r"[a-z]{3,}", raw.lower()))
        translated = {w for w in goals.terms(caption) if re.fullmatch("[а-я]+", w)} - STOP
        sources.update(terms)
        targets.update(translated)
        for term in terms:
            pairs[term].update(translated)
    aliases = {}
    for term, hits in pairs.items():
        # Require majority support in both directions across distinct source cards.
        words = sorted(w for w, n in hits.items() if n >= 2 and 2*n >= sources[term] and 2*n >= targets[w])
        if words:
            aliases[term] = words
    return aliases


@lru_cache(maxsize=1)
def features():
    path = Path(__file__).with_name("skynet_source_features.json")
    return json.loads(path.read_text(encoding="utf8"))


@lru_cache(maxsize=1)
def operations():
    return json.loads(Path(__file__).with_name("skynet_operation_features.json").read_text(encoding="utf8"))


def operation(question):
    explicit = goals.action(question)
    if explicit or goals.unsupported(question):
        return explicit
    query = set(goals.terms(goals.QUOTES.sub(" ", question)))
    scores = {}
    for label, examples in operations().items():
        values = []
        for example in examples:
            words = set(goals.terms(example)) - {"призн"}
            overlap = words & query
            values.append(len(overlap)/(max(1, len(words)*len(query))**.5) if len(overlap)>=2 else 0.)
        scores[label] = max(values, default=0.)
    best, second = sorted(scores, key=scores.get, reverse=True)[:2]
    if best != "unsupported" and scores[best] >= .4 and scores[best] > 1.3*scores[second]:
        return best
    return None


def choose(question, catalog, policy):
    quotes = goals.quoted(question)
    op = operation(question)
    if not op:
        raise goals.route.control.Gap("observation_ambiguous")
    if quotes:
        hits = [e for e in catalog if all(q.casefold() in e.label.casefold() for q in quotes)]
        if not hits:
            raise goals.route.control.Gap("observation_missing")
        if len(hits) != 1:
            raise goals.NeedChoice(hits[:3])
        return hits[0], op, "unique_quote"
    enriched = policy != "syntax"
    index = features() if enriched else {}
    query = set(goals.terms(question)) - STOP
    docs = []
    for effect in catalog:
        raw = descriptor(effect)
        words = goals.terms(raw)
        if enriched:
            caption = index["captions"].get(sha256(raw.encode()).hexdigest(), "")
            words += goals.terms(caption)
            if not caption and policy != "captions":
                for term in sorted(set(re.findall("[a-z]{3,}", raw.lower()))):
                    words.extend(index["aliases"].get(term, []))
        docs.append(Counter(w for w in words if w not in STOP))
    df = Counter(w for doc in docs for w in doc)
    avg = sum(doc.total() for doc in docs) / max(1, len(docs))
    rows = []
    for i, doc in enumerate(docs):
        shared = sorted(query & doc.keys())
        score = sum(log(1+(len(docs)-df[w]+.5)/(df[w]+.5)) * doc[w]*2.2 /
                    (doc[w]+1.2*(.25+.75*doc.total()/max(1,avg))) for w in shared)
        rows.append((score, i, len(shared)))
    rows.sort(key=lambda row: (-row[0], row[1]))
    if not rows:
        raise goals.route.control.Gap("observation_missing")
    score, i, overlap = rows[0]
    second = rows[1][0] if len(rows)>1 else 0
    if overlap < 2 or score <= 1.4*max(1,second):
        raise goals.route.control.Gap("observation_ambiguous")
    numbers = set(re.findall(r"(?<!\w)\d+(?!\w)", question))
    if not numbers.issubset(re.findall(r"(?<!\w)\d+(?!\w)", descriptor(catalog[i]))):
        raise goals.route.control.Gap("observation_missing")
    return catalog[i], op, policy


def relation(question):
    """Recognize a symmetric existential operator; keep both operands opaque."""
    quotes = []
    def slot(match):
        quotes.append(match[0])
        return f"«{len(quotes)-1}»"
    plain = goals.QUOTES.sub(slot, question.strip().rstrip("?.!")).casefold()
    match = re.fullmatch(r"(?:есть ли|существует ли|проверь,? есть ли) (?:прямой )?вызов между (.+)", plain)
    if not match:
        return None
    parts = re.split(r"\s+и\s+", match[1])
    if len(parts) != 2:
        raise goals.route.control.Gap("observation_ambiguous")
    return [re.sub(r"«(\d+)»", lambda m: quotes[int(m[1])], part) for part in parts]


def candidates(part, catalog, policy):
    quoted = goals.quoted(part)
    if quoted:
        # A literal is a locator, not permission to ignore arbitrary extra requirements.
        if len(quoted) != 1 or goals.QUOTES.sub("", part).strip():
            raise goals.route.control.Gap("observation_ambiguous")
        hits = [e for e in catalog if quoted[0].casefold() in e.label.casefold()]
        if not hits:
            raise goals.route.control.Gap("observation_missing")
        if len(hits) > 3:
            raise goals.NeedChoice(hits[:3])
        return hits
    return [choose("Где " + part, catalog, policy)[0]]


def connect(controller, parts, catalog, policy):
    left, right = [candidates(p, catalog, policy) for p in parts]
    return join(controller, left, right)


def join(controller, left, right, *, directed=False):
    orders = ((left,right),) if directed else ((left,right),(right,left))
    for sources, targets in orders:
        for target in targets:
            if not any(e.fn != target.fn for e in sources):
                continue
            for site in controller.s.incoming(target.fn.node.name):
                for source in sources:
                    if site.caller != source.fn or source.fn == target.fn:
                        continue
                    claims = []
                    for e in (source, target):
                        fact = controller.outcome(e.fn, e.stmt,
                            f"В {e.fn.node.name} на строке {e.expr.lineno} записано выражение {ast.unparse(e.expr)}.",
                            [(e.expr.lineno, e.expr.end_lineno)])
                        claims.append(fact.fact)
                    claims.append(dict(text=f"В {site.caller.node.name} на строке {site.call.lineno} записан "
                        f"прямой вызов {site.callee.node.name}. Это связь тел функций. Порядок появления "
                        "двух признаков при исполнении не установлен.", anchors=site.anchors,
                        edge=[site.caller.node.name, site.callee.node.name]))
                    refs = dict.fromkeys(a["ref_id"] for c in claims for a in c["anchors"])
                    meta = dict(action="connect", verdict="direct_edge", owner=target.fn.node.name,
                                line=target.expr.lineno, interpretation=f"{source.label} ↔ {target.label}")
                    return (claims, [controller.s.items[k] for k in refs], None), meta
    raise goals.route.control.Gap("path_unproven")
