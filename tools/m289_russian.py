"""Opt-in lexical retrieval over Russian already present in scoped source lines."""
import re

from m289_scoped_retrieval import ScopedCandidates


WORDS = re.compile("[а-яё]{4,}", re.I)
STOP = frozenset("когда какой какая какое какие каких каким которые который которая которое "
                 "которых почему зачем сколько здесь этого этом если после перед между "
                 "будет будут можно нужно также только есть чего себя свою этом делают".split())


def stems(text):
    # Short prefixes tolerate common inflections without translating or guessing identifiers.
    return {w[:4] for w in WORDS.findall(text.casefold().replace("ё", "е")) if w not in STOP}


def best_line(query, lines, start):
    best = frozenset()
    at = start
    for n, line in enumerate(lines, start):
        overlap = query & stems(line)
        if len(overlap) > len(best):
            best, at = overlap, n
    return best, at


def identity(row):
    return row["path"], row["qualname"], row["start"]


class RussianSearch(ScopedCandidates):
    def search(self, snapshot, question):
        baseline = super().search(snapshot, question)
        query = stems(question)
        if len(query) < 2:
            return baseline
        from app.retrieval.m127_symbol import extract_symbols

        allowed = {p: s for p, s in snapshot.sources.items() if p in self.scope}
        if not allowed:
            return baseline
        symbols, _ = extract_symbols(allowed)
        order = {identity(row): i for i, row in enumerate(baseline)}
        supported = []
        for row in symbols:
            hits, _ = best_line(query, row["_source"].splitlines(), row["start"])
            if len(hits) >= 2:
                supported.append((len(hits), row))
        supported.sort(key=lambda pair: (-pair[0], order.get(identity(pair[1]), len(order)),
                                         identity(pair[1])))
        candidates = []
        seen = set()
        for row in [r for _, r in supported] + baseline:
            key = identity(row)
            if key not in seen:
                candidates.append({k: v for k, v in row.items() if k != "_source"})
                seen.add(key)
            if len(candidates) == 8:
                break
        return candidates
