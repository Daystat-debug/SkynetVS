"""Replay frozen navigation cases from the repository root; JSON to stdout only."""
import argparse
import json
import platform
import re
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter_ns

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nav


def grep(rev, flags, pattern, paths):
    result = subprocess.run(["git", "--no-replace-objects", "grep", "--no-color",
                             *flags, "-e", pattern, rev, "--", *paths],
                            stdout=subprocess.PIPE, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git grep exited {result.returncode}")
    # Drop the repeated revision prefix. The common header identifies the snapshot.
    return [line.removeprefix(rev + ":") for line in result.stdout.decode().splitlines()]


def baseline(rev, symbol):
    definitions = grep(rev, ["-n", "-E"], r"^(async def|def|class) " + re.escape(symbol)
                       + r"([(: ]|$)", ["*.py"])
    owners = sorted({row.split(":", 1)[0] for row in definitions})
    imports = grep(rev, ["-n", "-E"], r"^[[:space:]]*(from|import) ", owners) if owners else []
    checks = grep(rev, ["-l", "-w", "-F"], symbol, ["tools/eval_*.py", "tools/test_*.py",
                                                     "tools/**/eval_*.py", "tools/**/test_*.py"])
    return "\n".join(definitions + imports + checks)


def batch_baseline(rev, symbols):
    alternatives = "|".join(map(re.escape, symbols))
    definitions = grep(rev, ["-n", "-E"], r"^(async def|def|class) (" + alternatives
                       + r")([(: ]|$)", ["*.py"])
    owners = sorted({r.split(":", 1)[0] for r in definitions})
    imports = grep(rev, ["-n", "-E"], r"^[[:space:]]*(from|import) ", owners) if owners else []
    hits = grep(rev, ["-o", "-w", "-E"], "(" + alternatives + ")",
                ["tools/eval_*.py", "tools/test_*.py", "tools/**/eval_*.py", "tools/**/test_*.py"])
    responses = []
    for symbol in symbols:
        pattern = re.compile(r":(?:async def|def|class) " + re.escape(symbol) + r"[(: ]")
        defs = [row for row in definitions if pattern.search(row)]
        paths = {r.split(":", 1)[0] for r in defs}
        checks = sorted({p for p, _, word in (r.rpartition(":") for r in hits) if word == symbol})
        responses.append("\n".join(defs + [r for r in imports if r.split(":", 1)[0] in paths] + checks))
    return responses


def coverage(text, case, arm):
    symbol, owner, dep, check = case
    if arm == "grep":
        defined = any(row.startswith(owner + ":") and re.search(
            r":(?:async def|def|class) " + re.escape(symbol) + r"[( :]", row)
                      for row in text.splitlines())
        # Gold null means there is no required dependency target; scored separately.
        dependency = dep[:-3].replace("/", ".") in text if dep else None
        checked = check in text.splitlines()
    else:
        defined = f"{symbol} {owner}:" in text
        dependency = ">" + dep in text if dep else None
        checked = bool(re.search(r"(?:^|\s)" + re.escape(check) + r":\d+", text))
    return {"definition": defined, "dependency": dependency, "check": checked}


def elapsed(start):
    return round((perf_counter_ns() - start) / 1e6, 3)


def render(rows):
    return ("\n".join(rows) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error("use at least two rounds for alternating order")
    suite = json.loads(Path("docs/maintenance/navigation_01/questions.json").read_text("utf8"))
    rev, cases = suite["snapshot"], suite["cases"]
    report = {"snapshot": rev, "python": platform.python_version(),
              "git": nav.git("--version").decode().strip(), "os": platform.system(),
              "rounds": [], "cases": {}, "limits": {"rows_per_group": 8, "tokens": None}}
    header = "snapshot " + rev
    symbols = [case[0] for case in cases]
    for run in range(args.repeats):
        timings = {}
        arms = ["grep", "index", "batch_grep", "quick"]
        offset = run % len(arms)
        order = arms[offset:] + arms[:offset]
        for arm in order:
            start = perf_counter_ns()
            if arm in ("index", "quick"):
                snap = nav.Snapshot(rev)
                index = nav.Index(snap) if arm == "index" else nav.quick_index(snap, symbols)
                if index.errors:
                    raise ValueError(index.errors)
                timings[arm + "_build_ms"] = elapsed(start)
            if arm == "batch_grep":
                responses = batch_baseline(rev, symbols)
            batch = [header]
            for i, case in enumerate(cases):
                symbol = case[0]
                t = perf_counter_ns()
                if arm == "grep":
                    response = baseline(rev, symbol)
                elif arm == "batch_grep":
                    response = responses[i]
                else:
                    response = index.brief(symbol, 8)
                duration = elapsed(t)
                batch.append(response)
                row = report["cases"].setdefault(symbol, {}).setdefault(arm, {
                    "utf8_bytes_without_header": len(render([response])),
                    "coverage": coverage(response, case, "grep" if arm.endswith("grep") else arm),
                    "query_ms": []})
                row["query_ms"].append(duration)
            timings[arm + "_batch_ms"] = elapsed(start)
            timings[arm + "_batch_bytes"] = len(render(batch))
        report["rounds"].append(timings)
    report["median"] = {key: statistics.median(r[key] for r in report["rounds"])
                        for key in report["rounds"][0]}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
