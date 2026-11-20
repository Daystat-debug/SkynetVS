"""Experimental context assembly over the unchanged scoped M289 bridge."""
import re
from dataclasses import dataclass


IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:[.-][A-Za-z0-9_]+)*")
PY_PATH = re.compile(r"[\w./\\-]+\.py\b", re.I)


@dataclass
class Window:
    selector: str
    path: str
    name: str
    first: int
    last: int
    center: int
    hits: set
    calls: set


def windows(core, snapshot, candidates, question):
    """Use literal code mentions as a conservative admission gate, in rank order."""
    names = {s.split("::")[1].split("@")[0].split(".")[-1].casefold() for s in candidates}
    mentions = {m.casefold() for m in IDENT.findall(question)
                if any(c in m for c in "_.-") or m.isupper() or m.casefold() in names}
    if not mentions:
        return [], "NO_CODE_MENTION"
    explicit_names = mentions & names
    matches = []
    for selector in candidates:
        path, node = core.definition(snapshot, selector)
        lines = snapshot.sources[path].splitlines()
        view = core.structural_view(snapshot, selector)["evidence"]
        name = node.name.casefold()
        line_hits = []
        calls = set()
        for n in range(view["start"], view["end"] + 1):
            line = lines[n - 1]
            words = {w.casefold() for w in IDENT.findall(line)}
            # Also recognize terminal method names in qualified calls.
            words.update(w.rsplit(".", 1)[-1] for w in tuple(words))
            hits = words & mentions
            if hits:
                line_hits.append((n, hits))
                calls.update(re.findall(r"([a-z_]\w*)\s*\(", line.casefold()))
        if not line_hits:
            continue
        hits = set.union(*(h for _, h in line_hits))
        # Prefer the line with the most requested identifiers, then source order.
        center = max(line_hits, key=lambda pair: len(pair[1]))[0]
        matches.append(Window(selector, path, name, view["start"], view["end"], center, hits, calls))
    if not matches or set.union(*(w.hits for w in matches)) != mentions:
        return [], "MISSING_MENTION"
    if len(matches) > 1 and not explicit_names and all(m.isalnum() for m in mentions):
        return [], "AMBIGUOUS_MENTION"
    # Reserve places for named definitions before considering mentions in callers.
    chosen = [w for w in matches if w.name in explicit_names]
    covered = set().union(*(w.hits for w in chosen))
    for w in matches:
        if w in chosen:
            continue
        if w.hits - covered or (not explicit_names and any(c.name in w.calls for c in chosen)):
            chosen.append(w)
            covered.update(w.hits)
    if len(chosen) > 3 and not mentions.issubset(set.union(*(w.hits for w in chosen[:3]))):
        return [], "TOO_MANY_REQUIRED_WINDOWS"
    return chosen[:3], "SUPPORTED_MENTIONS"


class MultiFragment:
    select_windows = staticmethod(windows)

    def __init__(self, bridge, retrieval, grounding, basis):
        self.bridge = bridge
        self.retrieval = retrieval
        self.grounding = grounding
        self.basis = basis
        self.reason = None

    def check(self, ref):
        return self.bridge.check(ref)

    def retrieve(self, question):
        report = self.bridge.retrieve(question)
        if report["status"] != "READY":
            self.reason = report["status"]
            return report
        session = self.bridge.active
        snapshot = session.snapshot
        candidates = report["candidates"][:4]
        scope = self.retrieval.SCOPE
        if any(s.split("::", 1)[0] not in scope for s in candidates):
            raise ValueError("M289_CANDIDATE_OUTSIDE_SCOPE")
        self.bridge.issued.clear()
        report.update(status="NO_MATCH", evidence=[], excerpts_clipped=False)
        if self.basis == "live":
            self.reason = "NO_LIVE_OBSERVATION"
            return report
        for path in PY_PATH.findall(question):
            if not any(p == path or p.endswith("/" + path) for p in scope):
                self.reason = "REQUESTED_PATH_OUTSIDE_SCOPE"
                report["status"] = "OUT_OF_SCOPE"
                return report
        selected, self.reason = self.select_windows(self.bridge.core, snapshot, candidates, question)
        if not selected:
            return report
        for w in selected:
            if w.selector != candidates[0]:
                view = session.inspect(w.selector)["selected_view"]
                if view["selector"] != w.selector or not self.bridge.core.check_reference(snapshot, view["evidence"]):
                    raise ValueError("M289_INSPECTION_MISMATCH")
        rows = self.pack(question, snapshot, selected)
        if not rows:
            self.reason = "WINDOWS_DO_NOT_FIT"
            report["status"] = "SOURCE_BUDGET"
            return report
        for row in rows:
            ref = row["ref"]
            self.bridge.issued[ref["id"]] = dict(ref)
        if not all(self.check(row["ref"]) for row in rows):
            raise ValueError("M289_EVIDENCE_CHANGED")
        report.update(status="READY", evidence=rows, excerpts_clipped=any(
            r["ref"]["start"] != w.first or r["ref"]["end"] != w.last
            or self.bridge.core.definition(snapshot, w.selector)[1].end_lineno != w.last
            for r, w in zip(rows, selected)))
        return report

    def pack(self, question, snapshot, selected):
        """Reserve an anchored line per function, then expand whole lines fairly."""
        system = self.grounding.SYSTEM + (self.grounding.LINKED_RULE if self.basis == "linked" else "")
        bounds = [[w.center, w.center] for w in selected]

        def materialize():
            rows = []
            seen = set()
            byte_count = 0
            for w, (lo, hi) in zip(selected, bounds):
                span = {(w.path, n) for n in range(lo, hi + 1)}
                if seen & span:
                    return []
                seen.update(span)
                ref = self.bridge.core.reference(snapshot, w.path, lo, hi)
                body = self.retrieval.excerpt(snapshot, ref)
                byte_count += len(body.encode("utf-8"))
                rows.append({"ref": ref, "text": body})
            if byte_count > self.retrieval.MAX_CONTEXT_BYTES:
                return []
            prompt = system + self.grounding._input(question, rows)
            return rows if len(prompt.encode("utf-8")) <= 3584 else []

        rows = materialize()
        if not rows:
            return []
        while True:
            grew = False
            for i, w in enumerate(selected):
                for edge, limit, step in ((0, w.first, -1), (1, w.last, 1)):
                    if bounds[i][edge] == limit:
                        continue
                    bounds[i][edge] += step
                    proposed = materialize()
                    if proposed:
                        rows = proposed
                        grew = True
                    else:
                        bounds[i][edge] -= step
            if not grew:
                break
        visible = {token.casefold() for row in rows for token in IDENT.findall(row["text"])}
        visible.update(t.rsplit(".", 1)[-1] for t in tuple(visible))
        required = set.union(*(w.hits for w in selected))
        return rows if required.issubset(visible) else []
