"""Paired warm measurements at the unmodified M289 serialization boundary."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_m289_multifragment as prior
from m289_russian import RussianSearch, stems

pilot = prior.pilot
BASE = "d5b5f26dc06ec1e617f2c3a5dcae07c8bc26b5eb"
FREEZE = "09d8dc930effe79c1304629f155156224db45537"
DIR = "docs/maintenance/m289_russian/"


def cases():
    original = json.loads(pilot.git("show", BASE + ":docs/maintenance/m289_multifragment/measurements.json"))
    for key, case in original["cases"].items():
        yield key, case["question"], case["basis"], case["rubric"], case["background_ranges"], case["multi"]
    control = json.loads(pilot.git("show", FREEZE + ":" + DIR + "control.json"))
    assert control["source"] == pilot.PIN and control["baseline"] == BASE
    for key, basis, question, gold in control["cases"]:
        rubric = [(pilot.PREFIX + control["paths"][p], name, units) for p, name, units in gold]
        yield key, question, basis, rubric, [], None


def profile_n4(bridge, scoped, ret, ground, row):
    """Non-overlapping spans for search, provider inspections and multi-window packing."""
    traces = []
    q, basis, gold = row["question"], row["basis"], row["rubric"]
    for repeat in range(3):
        for arm in (("single", "multi") if repeat % 2 == 0 else ("multi", "single")):
            bridge._bind(bridge.core, scoped)
            api = bridge if arm == "single" else prior.MultiFragment(bridge, ret, ground, basis)
            spans = []

            def measure(fn, label):
                def timed(*args, **kwargs):
                    start = time.perf_counter_ns()
                    result = fn(*args, **kwargs)
                    spans.append({"stage": label, "ms": round((time.perf_counter_ns()-start)/1e6, 3),
                                  "selector": args[-1] if label == "inspect" else None})
                    return result
                return timed

            with ExitStack() as stack:
                for obj, name in [(scoped, "search"), (scoped, "inspect")]:
                    stack.enter_context(patch.object(obj, name, measure(getattr(obj, name), name)))
                if arm == "multi":
                    stack.enter_context(patch.object(api, "pack", measure(api.pack, "pack")))
                result, ms = prior.previous.run_one(api, ground, q, basis, gold)
            assert result["payload_sha256"] == row[arm]["payload_sha256"]
            traces.append({"arm": arm, "total_ms": ms, "spans": spans,
                           "other_ms": round(ms - sum(s["ms"] for s in spans), 3)})
    return traces


def controlled(bridge, provider, ret, phase):
    a = sorted(ret.SCOPE)[0]
    snap = bridge.core.Snapshot(pilot.PIN, {
        a: 'def alpha():\n    return "зелёная корзина"\n',
        "main.py": 'def beta():\n    return "зелёная корзина"\n'}, {})
    q = "Откуда взялись зелёные корзины?"
    rows = provider.search(snap, q)
    assert [(r["path"], r["qualname"]) for r in rows] == [(a, "alpha")]
    assert not provider.search(snap, "Прилетели синицы?")
    if phase == "context":
        from m289_russian_context import russian_windows
        selector = a + "::alpha@1"
        chosen, _ = russian_windows(bridge.core, snap, [selector], q)
        assert len(chosen) == 1 and chosen[0].center == 2
        assert not russian_windows(bridge.core, snap, [selector], "Какого цвета корзина?")[0]
        assert not russian_windows(bridge.core, snap, [selector], q + " missing_var?")[0]


def run(phase, out, rank_path):
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    members = pilot.verify_package()
    import ground289 as ground
    import retrieval284 as ret
    if phase == "context":
        from m289_russian_context import RussianContext
        ranks = json.loads(rank_path.read_bytes())
        assert ranks["source"] == pilot.PIN and ranks["freeze"] == FREEZE and ranks["phase"] == "rank"
    raw = {p: pilot.git("show", pilot.PIN + ":" + p) for p in ret.SCOPE}
    oids = {p: pilot.git("rev-parse", pilot.PIN + ":" + p).decode().strip() for p in ret.SCOPE}
    data = dict(phase=phase, source=pilot.PIN, baseline=BASE, freeze=FREEZE, members=members,
                blobs=oids, repeats=2, cases={})
    with tempfile.TemporaryDirectory(prefix="m289-ru-") as temp:
        work = Path(temp)
        repo = work / "repo"
        pilot.git("clone", "--quiet", "--no-local", "--no-checkout", str(pilot.ROOT), str(repo))
        pilot.git("checkout", "--quiet", "--detach", pilot.PIN, cwd=repo)
        bridge = ret.Bridge(repo, work / "bundle")
        scoped = prior.ScopedCandidates(bridge.provider, ret.SCOPE)
        russian = RussianSearch(bridge.provider, ret.SCOPE)
        scoped.capture()
        data["ground_tests"] = prior.test_packing(bridge, ret, ground)
        controlled(bridge, russian, ret, phase)
        from app.context_search import expand_query
        from app.retrieval.m126_rank import tokens
        if phase == "rank":
            old = json.loads(pilot.git("show", BASE + ":docs/maintenance/m289_multifragment/measurements.json"))
            data["n4_profile"] = profile_n4(bridge, scoped, ret, ground, old["cases"]["N4"])
        for key, q, basis, gold, supports, baseline in cases():
            record = dict(question=q, basis=basis, rubric=gold, support_ranges=supports,
                          m126_tokens=sorted(set(tokens(expand_query(q)[0]))), russian_prefixes=sorted(stems(q)))
            arms = ("A", "B") if phase == "rank" else ("B", "C")
            elapsed = {arm: [] for arm in arms}
            for rep in range(2):
                for arm in (arms if (rep + int(key[1:])) % 2 else reversed(arms)):
                    bridge._bind(bridge.core, scoped if arm == "A" else russian)
                    cls = RussianContext if arm == "C" else prior.MultiFragment
                    api = cls(bridge, ret, ground, basis)
                    res, ms = prior.previous.run_one(api, ground, q, basis, gold)
                    res["reason"] = api.reason
                    prior.verify_delivery(res, q, basis, gold, supports, raw, oids, ground)
                    assert all(v.split("::", 1)[0] in ret.SCOPE for v in res["candidates"])
                    if arm == "A" and baseline:
                        assert all(res[f] == baseline[f] for f in res)
                    if phase == "context" and arm == "B":
                        assert all(res[f] == ranks["cases"][key]["B"][f] for f in res)
                    if rep:
                        assert record[arm] == res
                    else:
                        record[arm] = res
                    elapsed[arm].append(ms)
            if phase == "context":
                assert record["B"]["candidates"] == record["C"]["candidates"]
            for arm in arms:
                record[arm]["ms"] = elapsed[arm]
            data["cases"][key] = record
            print(key, [(a, record[a]["reason"], sum(record[a]["facts"])) for a in arms], flush=True)
    pilot.dump(out, data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("rank", "context"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--rank", type=Path)
    args = parser.parse_args()
    if args.phase == "context" and not args.rank:
        parser.error("context requires --rank from the completed rank phase")
    run(args.phase, args.output, args.rank)
