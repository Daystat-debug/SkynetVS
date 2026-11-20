"""Replay H/N and the frozen P set at the real ground289 provider boundary."""
import hashlib
import json
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_m289_scoped_retrieval as previous
import m289_diagnostic as pilot
from m289_multifragment import MultiFragment, Window, windows
from m289_scoped_retrieval import ScopedCandidates

BASE = "e88c0c9403e0d3bc8ec4aec54f7cd16d94655692"
FREEZE = "57672baf55667619d6e2fc069893e25dab90e644"
CONTROL = "docs/maintenance/m289_multifragment/control.json"
OLD = "docs/maintenance/m289_scoped_retrieval/measurements.json"


def test_packing(bridge, ret, ground):
    core = bridge.core
    a, b = sorted(ret.SCOPE)[:2]
    code = "def input_color():\n    return 'blue'\n"
    caller = "def report_color():\n    return input_color()\n"
    snap = core.Snapshot(pilot.PIN, {a: code, b: caller}, {})
    ids = [a + "::input_color@1", b + "::report_color@1"]
    q = "Как связаны input_color и report_color?"
    selected, reason = windows(core, snap, ids, q)
    assert reason == "SUPPORTED_MENTIONS" and len(selected) == 2
    adapter = MultiFragment(bridge, ret, ground, "linked")
    rows = adapter.pack(q, snap, selected)
    assert [r["text"] for r in rows] == [code, caller]
    assert all(core.check_reference(snap, r["ref"]) for r in rows)
    assert not core.check_reference(snap, dict(rows[1]["ref"], blob_oid="0" * 40))
    assert not windows(core, snap, ids, "Где input_color и missing_label?")[0]
    assert not windows(core, snap, ids, "Как связаны варианты?")[0]
    assert not adapter.pack(q, snap, selected * 2)
    long = "def wide_case():\n    return '" + "ж" * 1800 + "'\n"
    wide = core.Snapshot(pilot.PIN, {a: long}, {})
    point = Window("", a, "", 1, 2, 2, set(), set())
    assert not adapter.pack(q, wide, [point])
    point.center = 1
    assert adapter.pack(q, wide, [point])[0]["text"] == long.splitlines(True)[0]
    # Even a compromised candidate list cannot cause inspection outside SCOPE.
    class Bad:
        active = type("Active", (), {"snapshot": snap})()

        def retrieve(self, question):
            return {"status": "READY", "candidates": ["main.py::other@1"]}
    try:
        MultiFragment(Bad(), ret, ground, "static").retrieve(q)
    except ValueError as exc:
        assert str(exc) == "M289_CANDIDATE_OUTSIDE_SCOPE"
    else:
        raise AssertionError("outside candidate accepted")
    return ground.selftest_details()


def cases():
    old = json.loads(pilot.git("show", BASE + ":" + OLD))["cases"]
    historic = json.loads(pilot.git("show", previous.BASE + ":docs/maintenance/m289_diagnostic/A.json"))
    for key, row in old.items():
        basis = historic[int(key[1:]) - 1]["basis"] if key.startswith("H") else (
            "live" if key == "N8" else "static")
        supports = []
        if key.startswith("H") and not row["rubric"]:
            supports = pilot.GOLD[int(key[1:]) - 1]
        yield key, row["question"], basis, row["rubric"], supports, row["scoped"]
    control = json.loads(pilot.git("show", FREEZE + ":" + CONTROL))
    assert control["source"] == pilot.PIN and control["baseline"] == BASE
    for key, basis, q, rubric in control["cases"]:
        gold = [(pilot.PREFIX + control["notes"]["paths"][p], name, units)
                for p, name, units in rubric]
        yield key, q, basis, gold, [], None


def verify_delivery(row, q, basis, rubric, supports, source, oids, ground):
    targets = {(p, n) for p, _, units in rubric for unit in units for n in unit}
    targets.update((p, n) for p, lo, hi in supports for n in range(lo, hi + 1))
    sent = []
    relevant = []
    used = set()
    for ref in row["selected"]:
        path = ref["path"]
        assert ref["commit"] == pilot.PIN and ref["blob_oid"] == oids[path]
        raw = source[path]
        assert ref["source_sha256"] == hashlib.sha256(raw).hexdigest()
        excerpt = b"".join(raw.splitlines(True)[ref["start"] - 1:ref["end"]])
        assert ref["excerpt_sha256"] == hashlib.sha256(excerpt).hexdigest()
    for p, lo, hi in row["sent"]:
        ref = next(r for r in row["selected"] if (r["path"], r["start"], r["end"]) == (p, lo, hi))
        line_ids = {(p, n) for n in range(lo, hi + 1)}
        assert not used & line_ids
        used.update(line_ids)
        relevant.append(bool(targets & line_ids))
        body = b"".join(source[p].splitlines(True)[lo - 1:hi]).decode()
        sent.append({"ref": ref, "text": body})
    assert row["facts"] == [all((p, n) in used for n in unit)
                            for p, _, units in rubric for unit in units]
    payload = ground._input(q, sent)
    assert (pilot.sha(payload.encode()) if sent else None) == row["payload_sha256"]
    system = ground.SYSTEM + (ground.LINKED_RULE if basis == "linked" else "")
    prompt_bytes = len((system + payload).encode()) if sent else 0
    raw_bytes = sum(len(r["text"].encode()) for r in sent)
    row.update(fragment_on_target=relevant, source_bytes=raw_bytes, prompt_bytes=prompt_bytes,
               over_budget=raw_bytes > 3000 or prompt_bytes > 3584 or len(sent) > 3)
    assert not row["over_budget"]


def summary(captured):
    totals = {}
    for group in ("H", "N", "P"):
        cases_in_group = [v for k, v in captured.items() if k.startswith(group)]
        totals[group] = {}
        for arm in ("single", "multi"):
            positions, facts, frags, times = [], [], [], []
            full_multi = multi_count = calls = exceed = budget_refusals = 0
            for case in cases_in_group:
                r = case[arm]
                positions.extend(r["positions"])
                facts.extend(r["facts"])
                frags.extend(r["fragment_on_target"])
                times.append(statistics.median(r["ms"]))
                exceed += r["over_budget"]
                budget_refusals += r["gate"] == "NO_GENERATION_SOURCE_BUDGET"
                calls += bool(r["sent"])
                if len({p for p, _, _ in case["rubric"]}) > 1:
                    multi_count += 1
                    full_multi += all(r["facts"])
            totals[group][arm] = dict(
                functions=len(positions), top1=positions.count(1),
                top4=sum(v is not None and v <= 4 for v in positions),
                top8=sum(v is not None for v in positions),
                facts=[sum(facts), len(facts)], full_multifile=[full_multi, multi_count],
                off_target=[frags.count(False), len(frags)], reached_provider=calls,
                over_budget=exceed, budget_refusals=budget_refusals,
                median_ms=round(statistics.median(times), 1))
    return totals


def run(out):
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    members = pilot.verify_package()
    import retrieval284 as ret
    import ground289 as ground

    source = {p: pilot.git("show", pilot.PIN + ":" + p) for p in ret.SCOPE}
    oids = {p: pilot.git("rev-parse", pilot.PIN + ":" + p).decode().strip() for p in ret.SCOPE}
    result = {"freeze": FREEZE, "baseline": BASE, "source": pilot.PIN, "members": members,
              "scope_blobs": oids, "paired_repeats": 3, "cases": {}}
    with tempfile.TemporaryDirectory(prefix="m289-windows-") as temp:
        work = Path(temp)
        repo = work / "repo"
        pilot.git("clone", "--quiet", "--no-local", "--no-checkout", str(pilot.ROOT), str(repo))
        pilot.git("checkout", "--quiet", "--detach", pilot.PIN, cwd=repo)
        bridge = ret.Bridge(repo, work / "bundle")
        scoped = ScopedCandidates(bridge.provider, ret.SCOPE)
        scoped.capture()
        result["ground_selftests"] = test_packing(bridge, ret, ground)
        print("CONTROLLED CHECKS PASSED", flush=True)
        for key, q, basis, rubric, supports, old in cases():
            case = {"question": q, "basis": basis, "rubric": rubric, "background_ranges": supports}
            times = {"single": [], "multi": []}
            for repeat in range(3):
                order = ("single", "multi") if (int(key[1:]) + repeat) % 2 else ("multi", "single")
                for arm in order:
                    bridge._bind(bridge.core, scoped)
                    api = bridge if arm == "single" else MultiFragment(bridge, ret, ground, basis)
                    row, elapsed = previous.run_one(api, ground, q, basis, rubric)
                    row["reason"] = row["status"] if arm == "single" else api.reason
                    verify_delivery(row, q, basis, rubric, supports, source, oids, ground)
                    if arm == "multi":
                        assert len(row["selected"]) == len(row["sent"])
                    if repeat:
                        assert row == case[arm]
                    else:
                        case[arm] = row
                    times[arm].append(elapsed)
            assert case["single"]["candidates"] == case["multi"]["candidates"]
            if old:
                for field in ("status", "gate", "positions", "facts", "candidates", "payload_sha256"):
                    assert case["single"][field] == old[field]
            for arm in times:
                case[arm]["ms"] = times[arm]
            result["cases"][key] = case
            print(key, case["multi"]["reason"], sum(case["single"]["facts"]),
                  sum(case["multi"]["facts"]), flush=True)
    result["summary"] = summary(result["cases"])
    pilot.dump(out, result)


if __name__ == "__main__":
    run(Path(sys.argv[1]))
