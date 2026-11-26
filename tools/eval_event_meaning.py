"""Score frozen host outputs and independently substitute semantic descriptions, never answer IDs."""
import argparse
import ast
from collections import Counter
from contextlib import ExitStack
import gzip
import json
from math import sqrt
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_semantic_identity as previous
import skynet_event_meaning as meaning

DIR = previous.DIR.parent / "core_18"
ARMS = previous.ARMS[:-1] + ("event_meaning", "known_objects")


def load(path):
    return json.loads(path.read_text(encoding="utf8"))


def semantics(row, gold, aliases):
    if not row:
        return [False] * len(gold)
    return [got in [want] + aliases.get(want, []) for got, want in zip(row, gold, strict=True)]


def lexical(text, labels):
    query = previous.identity.chunks(text)
    scores = []
    for k, label in labels.items():
        features = previous.identity.chunks(label)
        scores.append((len(query & features) / sqrt(max(1, len(query) * len(features))), k))
    scores.sort(reverse=True)
    if scores and scores[0][0] >= .32 and scores[0][0] - (scores[1][0] if len(scores)>1 else 0) >= .09:
        return scores[0][1]
    return None


def diagnostics(tmp, panel, rows, live, cache):
    provider = previous.ev.Generations(tmp, cache, live)
    result = []
    sources = {}
    cases = {r["id"]: r for r in rows}
    aliases = panel["aliases"]
    try:
        for domain, cards in panel["cards"].items():
            # Only original source labels are exposed. Local keys carry no target identity.
            keys = list(cards)
            labels = {str(i): panel["targets"][k][3] for i, k in enumerate(keys)}
            for i, target in enumerate(keys):
                line = panel["targets"][target][2]
                stmt = ast.parse(panel["fixtures"][domain][line-1].strip()).body[0]
                assert isinstance(stmt, ast.Return) and ast.literal_eval(stmt.value)==labels[str(i)]
            provider.prepare()
            provider.used = 0
            provider.key = "closed/" + domain
            extracted, status = meaning.extract(labels, meaning.SOURCE, provider.select,
                                                previous.identity.goals.route.arguments.cli.strict)
            assert not provider.replay_errors
            original = {k: extracted.get(str(i)) for i, k in enumerate(keys)}
            expected = {k: meaning.decode(v) for k, v in cards.items()}
            assert all(expected.values())
            sources[domain] = dict(status=status, frames=original, fields={
                k: semantics(original[k], expected[k], aliases) for k in keys})
            for spec in panel["diagnostics"]:
                key, cue, gold_spec, conflicts = spec
                if key[0] != domain:
                    continue
                rec = cases[key]["event_meaning"]
                mention = next(x for x in rec["identity"] if x["cue"] == cue)
                query = mention["hypothesis"]["query_frame"]
                reference = meaning.decode(gold_spec)
                assert reference
                # Recover precisely the same part that was independently sent to the question extractor.
                spans = previous.prior.parts.split(cases[key]["question"])
                text = spans[previous.prior.old.place(cases[key]["question"], cue, spans)]["text"]
                trials = {}
                for arm, q, events in (("extracted",query,original), ("bag",query,original),
                                       ("known_question",reference,original), ("known_sources",query,expected),
                                       ("known_both",reference,expected)):
                    selected, why, comparison = meaning.decide(q, events, unordered=arm=="bag")
                    observed = {k:v for k,v in comparison.items() if v in ("opposite_polarity","reversed_roles")}
                    trials[arm] = dict(chosen=selected, why=why, comparison=comparison,
                                       true_conflicts=sum(conflicts.get(k)==v for k,v in observed.items()),
                                       false_conflicts=sum(conflicts.get(k)!=v for k,v in observed.items()))
                trials["lexical"] = dict(chosen=lexical(text, {k:panel["targets"][k][3] for k in keys}))
                gold = mention["target"]
                for trial in trials.values():
                    selected = trial["chosen"]
                    trial.update(correct=selected==(None if gold=="-" else gold),
                                 wrong=selected is not None and selected!=gold)
                result.append(dict(id=key,cue=cue,gold=gold,source_domain=domain,
                                   query=query,reference=reference,fields=semantics(query, reference, aliases),
                                   conflicts=conflicts,trials=trials))
    finally:
        provider.stack.close()
    return dict(sources=sources, questions=result), provider.sessions


def artifact(path, data, live):
    if live:
        raw = (json.dumps(data, ensure_ascii=False, indent=1)+"\n").encode()
        with path.open("xb") as stream:
            stream.write(gzip.compress(raw, mtime=0) if path.suffix==".gz" else raw)
    else:
        raw = path.read_bytes()
        assert json.loads(gzip.decompress(raw) if path.suffix==".gz" else raw)==data, path


def execute(mode, name):
    live = mode == "record"
    path = (previous.DIR if name=="history" else DIR) / "transfer.json"
    panel = load(path)
    if name=="history":
        panel["cases"] = [c for c in panel["cases"] if c[0] in ("D2","D3","P2","P6")]
        panel["contrasts"] = []
    dest = DIR/(name+"_trace.json.gz")
    scores = DIR/(name+"_scores.json")
    if live and (dest.exists() or scores.exists()):
        raise FileExistsError("record requires new files")
    saved = {} if live else json.loads(gzip.decompress(dest.read_bytes()))
    cache = saved.get("generations", {})
    arms_to_run = ARMS if name=="history" else ARMS + ("event_vocab",)
    run, grade = previous.harness(panel)
    with ExitStack() as stack:
        tmp = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(previous.ev.loop, "investigate", run))
        stack.enter_context(patch.object(previous.runner, "grade", grade))
        rows, ms, sessions = previous.runner.run(tmp, panel, live, cache, arms_to_run)
        diagnostic, extra = {}, []
        if name != "history":
            directory = tmp/"controlled"
            directory.mkdir()
            diagnostic, extra = diagnostics(directory, panel, rows, live, cache)
    if not live:
        ms, sessions, extra = saved["ms"], saved["sessions"], saved["controlled_sessions"]
    metrics = {arm:previous.summary(rows, ms, cache, arm, panel) for arm in arms_to_run}
    questions = []
    for r in rows:
        for x, y in zip(r["event_meaning"]["identity"],r["identity_rank"]["identity"],strict=True):
            if x["hypothesis"] or y["hypothesis"]:
                assert x["hypothesis"]["pool"]==y["hypothesis"]["pool"]
        if name!="history":
            for x,y in zip(r["event_meaning"]["identity"],r["event_vocab"]["identity"],strict=True):
                assert x["hypothesis"].get("pool")==y["hypothesis"].get("pool")
                if "extraction" in x["hypothesis"]:
                    assert cache[r["event_meaning"]["calls"][1]]["digest"]==cache[r["event_vocab"]["calls"][0]]["digest"]
        arms = {}
        for arm in arms_to_run:
            rec = r[arm]
            mentions = []
            for x in rec["identity"]:
                info = {k:x[k] for k in ("gold","chosen","kind","rank","wrong","issues","understood","fact","decision")}
                if "extraction" in x["hypothesis"]:
                    info["extraction"] = x["hypothesis"]["extraction"]
                    info["comparisons"] = dict(Counter(x["hypothesis"]["comparison"].values()))
                    if name!="history":
                        frames = x["hypothesis"]["source_frames"]
                        selected, reason, _ = meaning.decide(x["hypothesis"]["query_frame"],frames,unordered=True)
                        info["same_frames_bag"] = dict(chosen=int(selected) if selected is not None else None,why=reason)
                mentions.append(info)
            arms[arm] = dict(state=rec["answer"]["state"], full=rec["full"], useful_partial=rec["useful_partial"],
                             false_complete=rec["false_complete"], mentions=mentions)
        questions.append(dict(id=r["id"], question=r["question"], arms=arms))
    data = dict(panel_blob=previous.ev.pilot.git("hash-object",str(path)).decode().strip(), rows=rows,
                ms=ms, sessions=sessions, controlled_sessions=extra, generations=cache,
                diagnostics=diagnostic, metrics=metrics)
    artifact(dest, data, live)
    artifact(scores, dict(metrics=metrics, questions=questions, diagnostics=diagnostic), live)
    for arm, m in metrics.items():
        print(arm, {k:m[k] for k in ("right","wrong","facts","full","useful_partial","false_complete","refused","calls","median_ms")})


if __name__=="__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("mode", choices=("record","verify"))
    cli.add_argument("panel", choices=("history","transfer"))
    args = cli.parse_args()
    execute(args.mode, args.panel)
