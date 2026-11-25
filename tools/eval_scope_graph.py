"""Replay a whole-task intervention without handing any oracle a source fact or expected outcome."""
from collections import Counter
from contextlib import ExitStack
import argparse
import json
from pathlib import Path
from statistics import median
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_object_binding as old
import skynet_scope_graph as graph

parts = old.parts
binding = parts.objects
runner = old.prev
ev = runner.ev
DIR = old.DIR.parent / "core_15"
ARMS = ("object_offline", "relation_frame", "scope_local", "scope_nearest", "scope_graph",
        "known_objects", "known_kinds", "known_links")


def hints(case, panel, offset):
    key, question, demands = case
    spans = parts.split(question)
    identities = {}
    linked = [None] * len(spans)
    predicates = [None] * len(spans)
    for cue, k in panel["predicates"][key]:
        i = old.place(question, cue, spans)
        assert predicates[i] is None
        predicates[i] = k
    for cue, target, kind in demands:
        i = old.place(question, cue, spans)
        assert linked[i] is None
        if target != "-":
            path, owner, line = panel["targets"][target][:3]
            identities[i] = (ev.previous.PATHS[path], owner, line + offset)
        linked[i] = predicates[i] if kind == "ambiguous" else kind
    assert all(linked), "Every scored mention needs an explicit gold obligation"
    return identities, predicates, linked


def with_objects(resolve, ids):
    def oracle(spans, catalog, commit, policy, suggestions=None):
        edges, _ = resolve(spans, catalog, commit, policy, suggestions)
        effects = {}
        first = {}
        for i, edge in enumerate(edges):
            if i in ids:
                hits = [e for e in catalog if (e.fn.path,e.fn.node.name,e.expr.lineno) == ids[i]]
                assert len(hits) == 1
                obj = binding.identity(hits[0],commit)
                edge.update(object=obj, via="oracle_object", antecedent=None, tentative=False, gap=None)
            if edge["object"]:
                obj = edge["object"]
                target = first.setdefault(tuple(obj.values()), i)
                edge["target"] = target
                effects[target] = next(e for e in catalog if binding.identity(e,commit) == obj)
        return edges, effects
    return oracle


def observe(planner, cases, panel, synthetic_offset):
    def wrapped(question, root, *, discovery, **kw):
        case = cases[question]
        traces = []
        collect = parts.req.collect
        def measured(ctl, effect, needs, locate, schedule):
            row = dict(path=effect.fn.path, owner=effect.fn.node.name, line=effect.expr.lineno,
                       schedule=list(schedule), collected=[])
            traces.append(row)
            result, receipt = collect(ctl, effect, needs, locate, schedule)
            row.update(collected=receipt["supported"], gaps=receipt["gaps"])
            return result, receipt
        with ExitStack() as stack:
            stack.enter_context(patch.object(parts.req, "collect", measured))
            if discovery.startswith("known_"):
                ids, seeds, attached = hints(case, panel, synthetic_offset if case[0][0] != "R" else 0)
                if discovery in ("known_objects", "known_links"):
                    stack.enter_context(patch.object(binding, "resolve", with_objects(binding.resolve, ids)))
                if discovery == "known_kinds":
                    stack.enter_context(patch.object(graph, "predicates", lambda *_:list(seeds)))
                if discovery == "known_links":
                    # Pass only the required relation for each mention. No decision about availability.
                    stack.enter_context(patch.object(graph, "interpret", lambda *_:[
                        dict(kind=k, initial=k, origins=[i], alternatives=[k], revised=False)
                        for i,k in enumerate(attached)]))
                discovery = "scope_graph"
            out = planner(question, root, discovery=discovery, **kw)
        out["collector_log"] = traces
        return out
    return wrapped


def grade(case, out, panel, src, root, offset):
    key, q, demands = case
    claims = out["claims"]
    ev.old.verify_refs(root, src.commit, [ref for c in claims for ref in c["refs"]])
    spans = out.get("parts") or parts.split(q)
    scores = []
    for cue, target, kind in demands:
        span = spans[old.place(q,cue,spans)]
        issues = span.get("issues", [out.get("reason")])
        marked = bool(issues) and span.get("status") != "established"
        if target == "-":
            expected = {kind}
            if kind == "ambiguous":
                expected.add("observation_ambiguous")
            scores.append(dict(negative=kind, marked=marked, correct_reason=bool(expected.intersection(issues))))
            continue
        t = panel["targets"][target]
        path, owner, line = ev.previous.PATHS[t[0]], t[1], t[2]+offset
        coord = (path,owner,line)
        obj = span.get("binding",{}).get("object") or {}
        chosen = obj.get("commit")==src.commit and (obj.get("path"),obj.get("owner"),obj.get("line"))==coord
        kinds = span.get("need", [])
        exact = set(kinds)==set(parts.req.closure([kind]))
        direct = span.get("relation",{}).get("direct",span.get("claims",[]))
        shown = [claims[n] for n in direct if claims[n]["kind"]==kind]
        site = [claims[n] for n in span.get("claims",[]) if claims[n]["kind"]=="site"]
        traces = [r for r in out["collector_log"] if (r["path"],r["owner"],r["line"])==coord]
        scheduled = any(kind in r["schedule"] for r in traces)
        collected = any(kind in r["collected"] for r in traces)
        blocked = panel.get("unavailable",{}).get(target+"/"+kind)
        delivered = bool(shown and runner.fact(site,t,"site",src,offset) and runner.fact(shown,t,kind,src,offset))
        stage = ("object" if not chosen else "requirement_or_scope" if not exact else "planning" if not scheduled
                 else "evidence" if not collected else "publication" if not delivered else "delivered")
        scores.append(dict(object=chosen, requirement=exact, joint=chosen and exact, delivered=delivered,
                           blocked=blocked, marked=marked, correct_reason=bool(blocked and blocked in issues),
                           stage=stage))
    static = [s for s in scores if "joint" in s]
    gaps = [s for s in scores if s.get("blocked") or "negative" in s]
    possible = [s for s in static if not s["blocked"]]
    semantic = all(s["joint"] for s in possible)
    content = all(s["delivered"] for s in possible)
    full = bool(possible and not gaps and semantic and content and out["state"]=="answered")
    partial = bool(possible and gaps and semantic and content and all(s["marked"] for s in gaps) and out["state"]=="partial")
    limited = not possible and bool(gaps) and out["state"] in ("partial","insufficient") and all(
        s["marked"] and s["correct_reason"] for s in gaps)
    correct = (full or partial or limited) and all(s["joint"] for s in static) and all(s["correct_reason"] for s in gaps)
    return dict(scores=scores,full=full,partial=partial,limited=limited,correct=correct,
                false_complete=out["state"]=="answered" and not full)


def summarize(rows, times, panel, arm):
    entries = {r["id"]:r[arm] for r in rows}
    scores = [s for e in entries.values() for s in e["scores"]]
    static = [s for s in scores if "joint" in s]
    available = [s for s in static if not s["blocked"]]
    result = {k:sum(e[k] for e in entries.values()) for k in ("full","partial","limited","correct","false_complete")}
    result.update({k:sum(s[k] for s in static) for k in ("object","requirement","joint")})
    return dict(result, static=len(static), available=len(available), facts=sum(s["delivered"] for s in available),
                stages=dict(Counter(s["stage"] for s in available)),
                refused=sum(e["answer"]["state"]=="insufficient" for e in entries.values()),
                unresolved_reasons=sum(s["correct_reason"] for s in scores),
                contrasts=[pair for pair in panel["contrasts"] if all(entries[i]["correct"] for i in pair)],
                steps=sum(len(e["answer"]["steps"]) for e in entries.values()),
                calls=sum(len(e["calls"]) for e in entries.values()),
                median_ms=round(median(t[arm] for t in times.values()),1))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("record","verify"))
    parser.add_argument("panel",choices=("control","transfer"))
    args=parser.parse_args()
    path=DIR/(args.panel+".json")
    panel=json.loads(path.read_text(encoding="utf8"))
    cases={c[1]:c for c in panel["cases"]}
    assert len(cases)==len(panel["cases"])
    offset=len(ev.old.blob(ev.pilot.ROOT,panel["base"],ev.old.RANK)[0].splitlines())
    wrapper=observe(ev.loop.investigate,cases,panel,offset)
    with tempfile.TemporaryDirectory() as tmp, patch.object(ev.loop,"investigate",wrapper), patch.object(runner,"grade",grade):
        rows,times,sessions=runner.run(Path(tmp),panel,False,{},ARMS)
    assert not sessions and not any(r[a]["calls"] for r in rows for a in ARMS)
    output=DIR/(args.panel+"_results.json")
    if args.mode=="verify":
        saved=json.loads(output.read_text(encoding="utf8"))
        times=saved["ms"]
    report=dict(panel_blob=ev.pilot.git("hash-object",str(path)).decode("ascii").strip(), rows=rows, ms=times,
                metrics={a:summarize(rows,times,panel,a) for a in ARMS})
    if args.mode=="verify":
        assert report==saved
    else:
        with output.open("x",encoding="utf8",newline="\n") as f:
            json.dump(report,f,ensure_ascii=False,indent=1)
            f.write("\n")
    for arm,metrics in report["metrics"].items():
        print(arm,metrics)


if __name__=="__main__":
    main()
