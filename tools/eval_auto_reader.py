"""Run the locked auto cases through one-shot and interactive CLI entry points."""
from contextlib import nullcontext, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from eval_data_flow import cli, pilot, verify, verify_output

LOCK = "151203313826c2b8e627fc9e266048e6909d8a12"
QUESTIONS = "docs/maintenance/auto_reader/questions.json"


def capture(q=None, replies=()):
    results = []
    original = cli.answer
    def observe(*args, **kw):
        with patch.object(cli.calls,"lookup",wraps=cli.calls.lookup) as calls, \
                patch.object(cli.flow.Slice,"answer",autospec=True,side_effect=cli.flow.Slice.answer) as flow:
            answer = original(*args,**kw)
        results.append({"q":args[0],"answer":answer,"calls":calls.call_count,"flow":flow.call_count})
        return answer
    output = io.StringIO()
    argv = ["skynet_explain.py","--auto"] + ([q] if q else [])
    started = time.perf_counter()
    with patch.object(cli,"answer",observe), patch.object(sys,"argv",argv), redirect_stdout(output), \
            patch("builtins.input",side_effect=[*replies,"/exit"]):
        cli.main()
    return results,output.getvalue(),round(time.perf_counter()-started,3)


def measure(plan):
    run = dict(lock=LOCK,source=plan["source"],implementation=pilot.git("rev-parse","HEAD").decode().strip(),
               results=[],dialogues=[])
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)/"repo"
        pilot.git("clone","--local","--quiet","--no-checkout",str(pilot.ROOT),str(repo))
        pilot.git("checkout","--quiet","--detach",run["source"],cwd=repo)
        with cli.local_reader(repo) as session, patch.object(cli,"local_reader",lambda **kw:nullcontext(session)):
            for case in plan["cases"]:
                (row,),console,seconds = capture(case["q"])
                run["results"].append(dict(row,id=case["id"],console=console,seconds=seconds))
            qs = {c["id"]:c["q"] for c in plan["cases"]}
            for d in plan["dialogues"]:
                rows,console,seconds = capture(replies=[qs[d["first"]],d["reply"]])
                run["dialogues"].append(dict(first=d["first"],turns=rows,console=console,seconds=seconds))
            assert session[2].p is None
            for case,row in zip(plan["cases"],run["results"],strict=True):
                if case["route"] in {"calls","flow"}:
                    direct = cli.answer(case["target"],*session,callers=case["route"]=="calls",data_flow=case["route"]=="flow")
                    row["matches_manual"] = all(row["answer"].get(k) == v for k,v in direct.items())
            assert session[2].p is None
    return run


def score(case,row):
    route = case["route"]
    answer = row["answer"]
    return (route == answer.get("auto_route") and case.get("target") == answer.get("auto_target")
            and row["calls"] == int(route == "calls") and row["flow"] == int(route == "flow"))


def check(run,plan):
    verify(run,plan,lock=LOCK)
    blobs = {p:pilot.git("show",plan["source"]+":"+p) for p in (pilot.CS,pilot.RK,pilot.GS)}
    qs = {c["id"]:c for c in plan["cases"]}
    for case,row in zip(plan["cases"],run["results"],strict=True):
        print(case["id"],row["answer"]["auto_route"],row["answer"].get("auto_target",""),
              "correct" if score(case,row) else "MISMATCH", "manual",row.get("matches_manual","-"))
    for d,dialog in zip(plan["dialogues"],run["dialogues"],strict=True):
        first,last = dialog["turns"]
        assert dialog["first"] == d["first"] and first["q"] == qs[d["first"]]["q"] and last["q"] == d["reply"]
        for turn in dialog["turns"]:
            verify_output(turn["answer"],dialog["console"],plan["source"],blobs)
        print(d["first"],"follow-up","correct" if score(qs[d["first"]],first) and score(d,last) else "MISMATCH")


if __name__ == "__main__":
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    mode,name = sys.argv[1:]
    plan = json.loads(pilot.git("show",LOCK+":"+QUESTIONS))
    if mode == "run":
        with Path(name).open("x",encoding="utf8",newline="\n") as out:
            run = measure(plan)
            json.dump(run,out,ensure_ascii=False,indent=2)
            out.write("\n")
    else:
        assert mode == "verify"
        run = json.loads(Path(name).read_text(encoding="utf8"))
    check(run,plan)
