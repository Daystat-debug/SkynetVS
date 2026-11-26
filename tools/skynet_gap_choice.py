"""Source-grounded hypotheses and contrastive prompts for the isolated dialogue."""
from collections import Counter
import re


def words(text):
    return tuple(re.findall(r"[^\W_]+", text.casefold().replace("ё", "е")))


def contains(sequence, phrase):
    return bool(phrase) and any(sequence[i:i + len(phrase)] == phrase for i in range(len(sequence)))


def literal_match(text, catalog):
    """Require an attested label or an explicit owner with only one catalogued event."""
    query = words(text)
    owners = {e.fn.node.name for e in catalog if re.search(
        r"(?<!\w)" + re.escape(e.fn.node.name) + r"(?!\w)", text)}
    eligible = [i for i,e in enumerate(catalog) if not owners or e.fn.node.name in owners]
    matches = [i for i in eligible if contains(query, words(catalog[i].label))]
    if len(matches) == 1:
        return matches[0]
    if len(owners) == len(eligible) == 1:
        return eligible[0]
    return None


def difference(labels):
    """Remove shared boundaries only. Internal order and negative particles remain visible."""
    rows = [label.split() for label in labels]
    if len(rows) < 2:
        return labels
    while min(map(len, rows)) > 1 and len({r[0] for r in rows}) == 1:
        rows = [r[1:] for r in rows]
    while min(map(len, rows)) > 1 and len({r[-1] for r in rows}) == 1:
        rows = [r[:-1] for r in rows]
    return [" ".join(r) for r in rows]


def candidates(text, cards, shortlist, terms):
    # Seed with the same bounded discovery menu as Core 0.17; rank within it for display.
    query = set(terms(text))
    docs = [set(terms(label)) for label, *_ in cards]
    counts = Counter(w for doc in docs for w in doc)
    weight = lambda i: sum(1 / counts[w] for w in sorted(query & docs[i]))
    return sorted(shortlist, key=lambda i: -weight(i))


def resolve_reply(reply, labels):
    """Accept only an unambiguous distinguishing ordered span in the offered evidence.

    Use the entire source menu for competition, including candidates hidden by a short prompt.
    Missing lexical knowledge is unresolved. A preceding 'не' cannot confirm a positive span.
    """
    query = words(reply)
    spans = []
    for label in labels:
        doc = words(label)
        best = 0
        for i in range(len(query)):
            for j in range(len(doc)):
                if ("не" in query[:i]) != ("не" in doc[:j]):
                    continue
                k = 0
                while i+k < len(query) and j+k < len(doc) and query[i+k] == doc[j+k]:
                    k += 1
                if k and (k > 1 or len(query[i]) >= 4):
                    best = max(best, k)
        spans.append(best)
    top = max(spans, default=0)
    if top and spans.count(top) == 1:
        return spans.index(top)
    return None
