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


if __name__ == "__main__":
    if sys.argv[1:] not in (["discovery"], ["paired"], ["verify"]):
        sys.exit("Expected discovery, paired or verify")
    verify = sys.argv[1] == "verify"
    stage = "paired" if verify else sys.argv[1]
    path = pilot.ROOT / DIR / (stage + ".json")
    measured = run(stage)
    if verify:
        saved = json.loads(path.read_text(encoding="utf8"))
        for result in (measured, saved):
            del result["implementation"]
            for group in result["profiles"].values():
                for row in group["rows"]:
                    del row["seconds"]
        assert measured == saved, "Answer, decision, Git evidence or rendered output changed"
        print("Exact replay verified.")
    else:
        pilot.dump(path, measured)
