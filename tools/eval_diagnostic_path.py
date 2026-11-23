"""Replay the four policies on public Git objects; never execute subject Python."""
import argparse
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
from statistics import median
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_argument_flow as prior_eval
from eval_producer_investigation import anchored, set_head

old, loop, pilot = prior_eval.old, prior_eval.loop, prior_eval.pilot
diag = loop.diagnostic
BASE = "dc7000c6ce693964e551c9af16f5d710c286c9ec"
DIR = pilot.ROOT / "docs/maintenance/core_04"
ARMS = ("core03", "direct", "sequential", "core04")


def sequential(search, origin, candidates):
    for item in candidates:
        result = diag.witness(search, origin, [item])
        if result:
            return result
    return None


def direct(search, origin, candidates):
    return diag.witness(search, origin, candidates, direct=True)


def fixture(rng, number, raw):
    """Emit source and its oracle together. The planner never receives the oracle."""
    lines, defs = [], {}
    offset = len(raw.splitlines())

    def fresh():
        return "fn_" + format(rng.getrandbits(44), "x")

    def emit(line):
        lines.append(line)
        return offset + len(lines)

    def define(name):
        emit("")
        defs[name] = (old.RANK, emit(f"def {name}(value):"))

    count = rng.choice((2, 3, 4))
    targets = [fresh() for _ in range(count)]
    chosen = rng.randrange(count)
    origin = fresh()
    msg = "CASE_" + format(rng.getrandbits(36), "X")
    case = dict(id=f"G{number:02}", q=f"Из {origin} при каком условии возникает ошибка {msg}?")
    shape = ("near", "deep", "ambiguous", "shadow", "unsupported", "no_match")[number % 6]
    for i, name in enumerate(targets):
        define(name)
        if shape == "unsupported":
            emit("    try:")
            emit(f"        raise ValueError('{msg}')")
            emit("    finally:")
            emit("        pass")
        else:
            guard = emit("    if value:")
            if i % 2:
                emit("        return 0")
                emit("    else:")
            if shape == "no_match":
                emit(f"        return '{msg}'")
            else:
                site = emit(f"        raise ValueError('{msg}')")
                if i == chosen:
                    case.update(owner=name, refs=[guard, site], facts=[
                        f"raise ValueError('{msg}')", "`value` " + ("ложно" if i % 2 else "истинно")])
    chain = []
    for i, target in enumerate(targets):
        # Unrelated callers may have a deep hierarchy too. With an early correct
        # deep branch the per-target policy may win; with a late shallow one it may lose.
        depth = (1 if shape == "near" else 3) if i == chosen else rng.randint(1, 4)
        for j in range(depth):
            name = origin if i == chosen and j == depth - 1 else fresh()
            define(name)
            if name == origin and shape == "shadow":
                emit(f"    {target} = value")
            call = emit(f"    return {target}(value)")
            if i == chosen:
                chain.insert(0, [name, target, call])
            target = name
    if shape in ("near", "deep"):
        case["edges"] = chain
    else:
        case = dict(id=case["id"], q=case["q"], reason={
            "ambiguous": "diagnostic_ambiguous", "shadow": "path_unproven",
            "unsupported": "diagnostic_context", "no_match": "diagnostic_missing"}[shape])
        if shape == "ambiguous":
            case["q"] = f"При каком условии возникает ошибка {msg}?"
        if shape == "shadow":
            # Unexplored branches at the cap are a valid reason to withhold here.
            case["allowed_reason"] = "step_budget"
    return raw + ("\n".join(lines) + "\n").encode(), case, defs


def score(case, result, root, commit, defs):
    if "alternatives" in case:
        return any(score(option, result, root, commit, defs) for option in case["alternatives"])
    claims = result["claims"]
    for claim in claims:
        old.verify_refs(root, commit, claim["refs"])
    if "reason" in case:
        return (not claims and result["state"] == "insufficient" and
                result.get("reason") in {case["reason"], case.get("allowed_reason", case["reason"])})
    if result["state"] != "answered" or len(claims) != len(case["edges"]) + 1:
        return False
    for edge, claim in zip(case["edges"], claims):
        caller, target, site, *imports = edge
        path, _ = defs[caller]
        required = [defs[caller], defs[target], (path, site), *((path, n) for n in imports)]
        if (claim.get("edge") != [caller, target] or
                not all(anchored(claim["refs"], p, n) for p, n in required)):
            return False
    last = claims[-1]
    name = case["owner"]
    path, line = defs[name]
    return (name in last["text"] and all(s in last["text"] for s in case["facts"])
            and all(anchored(last["refs"], path, n) for n in [line, *case["refs"]]))


def public(result):
    # Save every published sentence and its precise locations. The enclosing row
    # carries the full commit. The grader has independently checked all Git digests.
    return dict(state=result["state"], reason=result.get("reason"), steps=result["steps"],
                claims=[dict(text=c["text"], refs=[[r["path"], r["start"], r["end"]] for r in c["refs"]])
                        for c in result["claims"]])


def measure(root, src, ground, case, defs, prior, order):
    inputs = dict(opener=lambda _: (src, ground))
    row = dict(id=case["id"], question=case["q"], commit=src.commit, positive="reason" not in case)
    timings = {}
    for arm in ARMS[order:] + ARMS[:order]:
        start = perf_counter()
        if arm == "core03":
            result = prior.investigate(case["q"], root, **inputs)
        else:
            planner = {"direct": direct, "sequential": sequential, "core04": diag.witness}[arm]
            result = loop.investigate(case["q"], root, diagnostic_planner=planner, **inputs)
        timings[arm] = round((perf_counter() - start) * 1000, 1)
        assert len(result["steps"]) <= loop.MAX_STEPS
        correct = score(case, result, root, src.commit, defs)
        row[arm] = dict(correct=correct, **public(result))
    return row, timings


def controls(root, case):
    src, ground = loop.read_head(root)
    lookup = loop.host.lab.cli.calls.lookup

    def corrupted(name, src, refuse):
        result = lookup(name, src, refuse)
        result["claims"][0]["evidence_blocks"][0]["url"] += "#wrong"
        return result

    def switched(name, src, refuse):
        result = lookup(name, src, refuse)
        set_head(root, BASE + "^")
        return result

    checks = [("budget", "step_budget", dict(steps=1)), ("reference", "invalid_reference", dict(lookup=corrupted)),
              ("target", "endpoint_binding", dict(lookup=lambda n, s, r: lookup("expand_query", s, r))),
              ("head", "stale_snapshot", dict(lookup=switched))]
    outcomes = {}
    for label, reason, opts in checks:
        result = loop.investigate(case, root, opener=lambda _: (src, ground), **opts)
        assert not result["claims"] and result.get("reason") == reason, (label, result)
        outcomes[label] = result["reason"]
    set_head(root, BASE)
    return outcomes


def run(temp, plan):
    previous = temp / "core03.py"
    previous.write_bytes(pilot.git("show", BASE + ":tools/skynet_investigate.py"))
    spec = importlib.util.spec_from_file_location("accepted_core03", previous)
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)  # trusted pinned host, separate from the five unexecuted subjects
    root = temp / "fixture"
    pilot.git("clone", "--quiet", "--local", "--no-checkout", str(pilot.ROOT), str(root))
    set_head(root, BASE)
    raw, _ = old.blob(root, BASE, old.RANK)
    defs = {**prior_eval.DEFS, **plan["definitions"]}
    trials = [(None, case, defs) for case in plan["cases"]]
    rng = random.Random(int(plan["implementation"][:8], 16))
    trials.extend(fixture(rng, i, raw) for i in range(18))
    rows, times = [], {}
    for i, (modified, case, defs) in enumerate(trials):
        commit = prior_eval.checkout_fixture(root, BASE, modified) if modified else BASE
        src, ground = loop.read_head(root)
        assert src.commit == commit
        row, timing = measure(root, src, ground, case, defs, prior, i % len(ARMS))
        rows.append(row)
        times[case["id"]] = timing
    set_head(root, BASE)
    return rows, times, controls(root, plan["integrity_question"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record", "verify"))
    args = parser.parse_args()
    plan = json.loads((DIR / "transfer.json").read_text(encoding="utf8"))
    with tempfile.TemporaryDirectory(prefix="skynet-diagnostic-") as tmp:
        rows, ms, checks = run(Path(tmp), plan)
    dest = DIR / "results.json"
    if args.mode == "record":
        with dest.open("x", encoding="utf8", newline="\n") as f:
            json.dump(dict(rows=rows, ms=ms, controls=checks), f, ensure_ascii=False, indent=1)
            f.write("\n")
    else:
        saved = json.loads(dest.read_text(encoding="utf8"))
        assert (saved["rows"], saved["controls"]) == (rows, checks)
    for section in ("R", "G"):
        group = [r for r in rows if r["id"].startswith(section)]
        for arm in ARMS:
            print(section, arm, sum(r[arm]["correct"] for r in group), "/", len(group),
                  median(ms[r["id"]][arm] for r in group), "ms")
    print("integrity", checks)


if __name__ == "__main__":
    main()
