"""Opt-in M289 experiment: narrow the candidate corpus before lexical ranking."""
from dataclasses import replace


class ScopedCandidates:
    def __init__(self, provider, source_scope):
        self.provider = provider
        self.scope = frozenset(source_scope)

    def head(self):
        return self.provider.head()

    def capture(self):
        return self.provider.capture()

    def search(self, snapshot, question):
        sources = {path: text for path, text in snapshot.sources.items() if path in self.scope}
        if not sources:
            return []
        return self.provider.search(replace(snapshot, sources=sources), question)

    def inspect(self, snapshot, question, selector):
        if selector.partition("::")[0] not in self.scope:
            raise ValueError("M289_CANDIDATE_OUTSIDE_SCOPE")
        return self.provider.inspect(snapshot, question, selector)
