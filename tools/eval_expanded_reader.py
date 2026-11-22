"""Reproduce the paired five-file experiment without importing Git sources."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_scope_lab as lab
from eval_data_flow import verify_output

LOCK = "2d4b8a3b0109bb1471c88802f42a8b251014a566"
DIR = "docs/maintenance/expanded_reader"
pilot = lab.cli.pilot


def run(stage):
    plan = json.loads(pilot.git("show", LOCK + ":" + DIR + "/questions.json"))
    assert plan["source"] == lab.SOURCE and set(plan["extra"]) == lab.SCOPE - lab.BASE
    core, launch, ground = lab.trusted_tools()
    results = {}
    for name in ("three", "five"):
        src = lab.snapshot(core, launch, baseline=name == "three")
        raw = {p: pilot.git("show", lab.SOURCE + ":" + p) for p in src.pages}
        assert raw == src.raw
        rows = []
        for case in plan["cases"]:
            if stage == "discovery" and not case["id"].startswith("S"):
                continue
            start = perf_counter()
            answer = lab.ask(case["mode"], case["q"], src, ground)
            elapsed = round(perf_counter() - start, 4)
            with redirect_stdout(io.StringIO()) as out:
                lab.display(answer)
            console = out.getvalue()
            verify_output(answer, console, lab.SOURCE, raw)
            rows.append(dict(id=case["id"], mode=case["mode"], question=case["q"], answer=answer,
                             console=console, seconds=elapsed))
            print(name, case["id"], answer["status"], elapsed)
        results[name] = dict(blobs=src.oids, rows=rows)
    return dict(questions_commit=LOCK, source=lab.SOURCE, implementation=pilot.git("rev-parse","HEAD").decode().strip(),
                stage=stage, generations=0, profiles=results)


def regression():
    """Replay old standalone questions in the three-file profile. Compare decisions, claims and spans."""
    core, launch, ground = lab.trusted_tools()
    src = lab.snapshot(core, launch, baseline=True)

    def archive(path):
        return pilot.git("show", lab.SOURCE + ":docs/maintenance/" + path)

    cases = []
    for folder, mode in (("data_flow", "flow"), ("auto_reader", "auto"), ("composed_reader", "compose")):
        for row in json.loads(archive(folder + "/answers.json"))["results"]:
            cases.append((mode, row["id"], row["q"], row["answer"]))
    questions = {r["id"]: r["q"] for r in json.loads(archive("evidence_reader/calls_protocol.json"))["cli"]}
    for line in archive("evidence_reader/calls.jsonl").splitlines():
        row = json.loads(line)
        if "result" in row:
            cases.append(("calls", row["case"], questions[row["case"]], row["result"]))

    def facts(answer):
        decisions = [answer.get(k) for k in ("status", "reason", "auto_route", "auto_target", "field", "actions")]
        claims = [(c["text"], [(r["path"], r["start"], r["end"], r["blob_oid"], r["excerpt_sha256"])
                               for r in c["evidence_blocks"]]) for c in answer["claims"]]
        edges = [(e["function"], e["field"], {k:v for k,v in e["site"].items() if k != "commit"})
                 for e in answer.get("relations", [])]
        return decisions, claims, edges

    failures = []
    for mode, name, question, expected in cases:
        actual = lab.cli.answer(question, src, ground, None, **{lab.MODES[mode]: True})
        if facts(actual) != facts(expected):
            failures.append((mode, name))
    print(f"{len(cases) - len(failures)}/{len(cases)} archived decisions, claims, spans and joins match.", failures)
    return bool(failures)


def compare_previous(run, baseline):
    """All old claims, range hashes, routes and joins must survive; only T1/T2 acquire a new site."""
    for name, group in run["profiles"].items():
        archived = baseline["profiles"][name]
        assert group["blobs"] == archived["blobs"]
        for now, old in zip(group["rows"], archived["rows"], strict=True):
            assert [now[k] for k in ("id","mode","question")] == [old[k] for k in ("id","mode","question")]
            answer, before = now["answer"], old["answer"]
            for k in before.keys() - {"text","claims"}:
                assert answer[k] == before[k], (name, now["id"], k)
            old_sites, added = [], []
            for c in answer["claims"]:
                if c.get("call_site", {}).get("kind") == "module_entry":
                    added.append((Path(c["call_site"]["path"]).name,c["call_site"]["line"]))
                else:
                    old_sites.append({k:v for k,v in c.items() if k != "call_site"})
            assert old_sites == before["claims"]
            expect_new = name == "five" and now["id"] in {"T1","T2"}
            assert added == ([("m126_rank.py",103)] if expect_new else [])
            if "call_coverage" not in answer:
                assert answer == before and now["console"] == old["console"]


if __name__ == "__main__":
    if sys.argv[1:] == ["regression"]:
        sys.exit(regression())
    if sys.argv[1:] not in (["discovery"], ["paired"], ["verify"]):
        sys.exit("Expected discovery, paired, verify or regression")
    verify = sys.argv[1] == "verify"
    stage = "paired" if verify else sys.argv[1]
    path = pilot.ROOT / DIR / (stage + ".json")
    measured = run(stage)
    if verify:
        saved = json.loads(pilot.git("show", "bfdefabf3ed12dc8d92e006a0cafa58b074dd98a:" + DIR + "/paired.json"))
        compare_previous(measured, saved)
        print("14/14 archived question/profile pairs retain their decisions, claims, spans and joins; T1/T2 gain the guarded call.")
    else:
        pilot.dump(path, measured)
