"""Compare a menu with operator selection and one-step routing; exercise the legacy report in scratch."""
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter_ns


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "docs/maintenance/navigation_01/integration_cases.json"
NAV = Path("tools/navigation_lab/nav.py")
INVENTORY = Path("tools/project_inventory.py")


def run(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, env=env, check=True, stdout=subprocess.PIPE).stdout


def archived(sha, path):
    return run(["git", "--no-replace-objects", "show", f"{sha}:{path.as_posix()}"], ROOT)


def verify_inventory(scratch, sha):
    repo = scratch / "checkout"
    run(["git", "clone", "-q", "--local", "--no-hardlinks", "--no-checkout", str(ROOT), str(repo)], ROOT)
    run(["git", "checkout", "-q", "--detach", sha], repo)
    original = (repo / "project_inventory.md").read_bytes()
    py = [sys.executable, "-I", "-S", "-B"]
    run([*py, INVENTORY], repo)
    legacy = (repo / "project_inventory.md").read_bytes()
    assert legacy != original, "legacy default did not write report"
    (repo / "project_inventory.md").write_bytes(original)
    env = {**os.environ, "TMP": str(scratch), "TEMP": str(scratch), "TMPDIR": str(scratch)}
    run([*py, ROOT / INVENTORY], repo, env)
    default, = scratch.glob("skynetvs-inventory-*.md")
    explicit = scratch / "explicit.md"
    run([*py, ROOT / INVENTORY, "--out", explicit], repo, env)
    assert legacy == default.read_bytes() == explicit.read_bytes()
    assert (repo / "project_inventory.md").read_bytes() == original
    assert not run(["git", "status", "--porcelain"], repo)
    return {"legacy_default_rewrites_tracked_report": True, "temp_default_outside_checkout": True,
            "explicit_and_default_equal_legacy_report": True, "checkout_clean": True}


def navigation(scratch, suite):
    rev = suite["baseline"]
    old = scratch / "nav.py"
    old.write_bytes(archived(rev, NAV))
    (scratch / "topics.json").write_bytes(archived(rev, NAV.with_name("topics.json")))
    rows = []
    for case in suite["cases"]:
        row = {"id": case["id"], "menu": {}, "task": {}}
        for repeat in range(4):
            for arm in (("menu", "task") if repeat % 2 == 0 else ("task", "menu")):
                script = old if arm == "menu" else ROOT / NAV
                cmd = [sys.executable, "-I", "-S", "-B", script, "--snapshot", rev]
                start = perf_counter_ns()
                if arm == "menu":
                    # Best-case operator selects the specified area after seeing the menu.
                    outputs = [run([*cmd, "topic"], ROOT)]
                    if len(case["keys"]) == 1:
                        outputs.append(run([*cmd, "topic", *case["keys"]], ROOT))
                else:
                    outputs = [run([*cmd, "task", case["question"]], ROOT)]
                ms = (perf_counter_ns() - start) / 1e6
                stats = row[arm]
                stats.setdefault("elapsed_ms", []).append(round(ms, 2))
                stats["commands"] = len(outputs)
                stats["stdout_bytes"] = sum(map(len, outputs))
                answer = outputs[-1].decode("utf-8").splitlines()
                if arm == "task":
                    stats["returned"] = answer[1:]
                    keys = sorted(line.split()[1] for line in answer if line.startswith("topic "))
                    if not case["keys"]:
                        correct = not keys and answer[1].startswith("Нет совпадений")
                    elif len(case["keys"]) > 1:
                        correct = keys == sorted(case["keys"]) and answer[1].startswith("Уточните")
                    else:
                        correct = (keys == case["keys"] and
                                   all(any(line.endswith(": " + path) for line in answer)
                                       for path in case["paths"]))
                    stats["matches_rubric"] = correct
                    if len(case["keys"]) == 1:
                        # Time any follow-up actually required to reach the same pair of paths.
                        follow_start = perf_counter_ns()
                        follow = []
                        if not correct:
                            if case["keys"][0] not in keys:
                                follow.append(run([*cmd, "topic"], ROOT))
                            follow.append(run([*cmd, "topic", *case["keys"]], ROOT))
                            assert all((": " + path + "\n").encode() in follow[-1]
                                       for path in case["paths"])
                        stats["assisted_commands"] = len(outputs) + len(follow)
                        stats["assisted_bytes"] = stats["stdout_bytes"] + sum(map(len, follow))
                        total = ms + (perf_counter_ns() - follow_start) / 1e6
                        stats.setdefault("assisted_elapsed_ms", []).append(round(total, 2))
                elif len(case["keys"]) == 1:
                    stats["contains_requested_paths"] = all(any(line.endswith(": " + path) for line in answer)
                                                            for path in case["paths"])
        for arm in ("menu", "task"):
            row[arm]["median_ms"] = round(median(row[arm]["elapsed_ms"]), 2)
        rows.append(row)
    return rows


def main():
    suite = json.loads(CASES.read_text("utf-8"))
    transfer = json.loads(CASES.with_name("integration_transfer.json").read_text("utf-8"))
    suite["cases"].extend(transfer["cases"])
    with tempfile.TemporaryDirectory(prefix="sk-nav-") as tmp:
        scratch = Path(tmp)
        print(json.dumps({"baseline": suite["baseline"], "cases": navigation(scratch, suite),
                          "inventory": verify_inventory(scratch, suite["baseline"])},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    main()
