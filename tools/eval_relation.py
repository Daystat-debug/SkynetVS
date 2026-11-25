"""Grade the delivered source-bound claims separately from the interpretation that requested them."""
import argparse
import json
from pathlib import Path
from statistics import median
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_object_binding as previous

ARMS = ("object_offline", "relation_nearest", "relation_frame")
DIR = previous.DIR.parent / "core_14"
REFS = {"control":"f934ab67d87c106bfd4ea3ba210faa380348424b",
        "challenge":"65ee023a2de52bfac6afb8523ecde0f23e8037ae"}


def grade(case, out, panel, src, root, offset):
    record = previous.grade(case, out, panel, src, root, offset)
    spans = out.get("parts", [])
    for score in record["scores"]:
        if "site" not in score:
            continue
        part = spans[previous.place(case[1], score["cue"], spans)] if spans else {}
        # A planner collecting everything does not demonstrate that it understood the requested slot.
        closure = previous.parts.req.closure([score["kind"]])
        score["exact_type"] = set(part.get("need", [])) == set(closure)
        score["joint"] = bool(score["chosen"] and score["exact_type"])
        if "relation" in part:
            direct = [out["claims"][n] for n in part["relation"]["direct"]]
            target = next(t for cue,t,k in case[2] if cue == score["cue"])
            score["proved"] &= previous.prev.fact(direct, panel["targets"][target], score["kind"], src, offset)
    facts = [s for s in record["scores"] if "site" in s]
    covered = all(s["proved"] for s in facts)
    record["full"] &= covered
    record["partial"] &= covered
    record["strict_partial"] &= covered
    record["false_complete"] = out["state"] == "answered" and not record["full"]
    return record


def metrics(rows, panel, times, arm):
    by_id = {r["id"]:r[arm] for r in rows}
    items = list(by_id.values())
    scores = [s for r in items for s in r["scores"] if "site" in s]
    gaps = [s for r in items for s in r["scores"] if "gap" in s]
    passed = []
    for a,b in panel["contrasts"]:
        if all(by_id[k]["full"] and all(s["joint"] and s["proved"] for s in by_id[k]["scores"])
               for k in (a,b)):
            passed.append([a,b])
    return dict(static=len(scores), objects=sum(s["chosen"] is True for s in scores),
                types=sum(s["exact_type"] for s in scores), joint=sum(s["joint"] for s in scores),
                facts=sum(s["proved"] for s in scores), gaps=len(gaps), correct_gap=sum(s["reason"] for s in gaps),
                full=sum(r["full"] for r in items), partial=sum(r["partial"] for r in items),
                strict_partial=sum(r["strict_partial"] for r in items), false_complete=sum(r["false_complete"] for r in items),
                insufficient=sum(r["answer"]["state"]=="insufficient" for r in items),
                contrasts=passed, steps=sum(len(r["answer"]["steps"]) for r in items),
                calls=sum(len(r["calls"]) for r in items), median_ms=median(t[arm] for t in times.values()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record","verify"))
    parser.add_argument("--history", action="store_true", help="Replay three known calibration cases separately")
    args = parser.parse_args()
    sources = {name:sha + ":docs/maintenance/core_14/" + name + ".json" for name, sha in REFS.items()}
    if args.history:
        sources = {"history":previous.FINAL}
    for name, ref in sources.items():
        panel = json.loads(previous.prev.ev.pilot.git("show", ref))
        if args.history:
            panel["cases"] = [case for case in panel["cases"] if case[0] in ("R2","E4","E5")]
            panel["contrasts"] = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(previous.prev, "grade", grade):
            rows, times, sessions = previous.prev.run(Path(tmp), panel, False, {}, ARMS)
        assert not sessions and not any(r[a]["calls"] for r in rows for a in ARMS)
        path = DIR / (name + "_results.json")
        if args.mode == "verify":
            saved = json.loads(path.read_text(encoding="utf8"))
            times = saved["ms"]
        result = dict(panel=ref, rows=rows, ms=times, metrics={a:metrics(rows,panel,times,a) for a in ARMS})
        if args.mode == "record":
            with path.open("x", encoding="utf8", newline="\n") as f:
                json.dump(result, f, ensure_ascii=False, indent=1)
                f.write("\n")
        else:
            assert saved == result, name
        print(name, json.dumps(result["metrics"], indent=1))


if __name__ == "__main__":
    main()
