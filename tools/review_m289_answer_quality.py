"""Render de-duplicated outputs without arm names, or join frozen judgments to run receipts."""
import hashlib
import json
from pathlib import Path
import statistics
import sys


def receipt_view(row):
    turn = row["turn"]
    return {"case": row["case"], "display": turn["display_ru"],
            "published": turn["generated_answer_published"],
            "claims": [[c["text"], [[a["path"], a["line"], a["source_line"], a["quote"]]
                                    for a in c["anchors"]]] for c in turn["claims"]]}


def token(view):
    return hashlib.sha256(json.dumps(view, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def review(folder, show_scores):
    events = [json.loads(s) for s in (folder / "run.jsonl").read_text(encoding="utf8").splitlines()]
    turns = [r for r in events if r["event"] == "turn"]
    assert len(turns) == 32 and events[-1]["event"] == "done"
    calls = [e for e in events if e["event"] == "reserve"]
    assert len(calls) == len([e for e in events if e["event"] == "completion"]) == events[-1]["calls"] <= 40
    assert len(calls) == sum(e["info"]["requests"] for e in events if e["event"] == "session")
    views = {token(receipt_view(r)): receipt_view(r) for r in turns}
    if not show_scores:
        for key, v in sorted(views.items()):
            print(key, json.dumps(v, ensure_ascii=False))
        return
    judgments = json.loads((folder / "review.json").read_text(encoding="utf8"))
    assert set(judgments) == set(views)
    control = json.loads((folder / "control.json").read_text(encoding="utf8"))
    rubric = {x["id"]: x for x in control["cases"]}
    for arm in ("O", "A", "B", "C"):
        rows = [r for r in turns if r["arm"] == arm]
        facts = complete = multi = controls = specific = unsupported = claims = 0
        for r in rows:
            case = rubric[r["case"]]
            v = receipt_view(r)
            j = judgments[token(v)]
            hit = j["supported_facts"]
            bad = j["unsupported_claims"]
            assert len(hit) == len(set(hit)) and all(1 <= n <= len(case.get("facts", [])) for n in hit)
            assert len(bad) == len(set(bad)) and all(1 <= n <= len(v["claims"]) for n in bad)
            assert v["published"] or not (hit or bad)
            claims += len(v["claims"])
            unsupported += len(bad)
            facts += len(hit)
            if "facts" in case:
                full = len(hit) == len(case["facts"]) and not bad
                complete += full
                multi += full and len({f[1] for f in case["facts"]}) > 1
            else:
                controls += not v["published"]
                specific += j.get("specific_refusal", False)
        print(arm, dict(facts=facts, full=complete, multi=multi, unsupported=unsupported, claims=claims,
                        controls_withheld=controls, specific=specific,
                        median_ms=round(statistics.median(r["end_to_end_ms"] for r in rows)),
                        calls=sum(e["arm"] == arm for e in calls)))
    print("Planner calls", sum(e["arm"] == "plan" for e in calls), "total", len(calls))


if __name__ == "__main__":
    review(Path(sys.argv[1]), "--scores" in sys.argv[2:])
