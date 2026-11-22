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
PREVIOUS = "c6acb522c7eeb2feea938f4ed40c04f9af119782"


def regression_plan():
    suites = [
        ("docs/maintenance/data_flow/questions.json", "cases", [
            ("flow","candidate_functions"),("flow","candidate_files_full_tree"),("flow","candidate_modules"),
            ("flow","no_patch_or_apply"),("clarify",None),("observation",None),("external",None),("calls","format_context")]),
        ("docs/maintenance/evidence_reader/calls_protocol.json","cli", [
            ("calls","rank"),("calls","interleave_3_to_1"),("calls","format_context"),("clarify",None)])]
    cases = []
    for path,key,targets in suites:
        old = json.loads(pilot.git("show",PREVIOUS+":"+path))
        cases.extend(dict(case,route=r,target=t) for case,(r,t) in zip(old[key],targets,strict=True))
    return {"cases":cases,"source":PREVIOUS,"dialogues":[]}


def capture(q=None, replies=(), *, mode="--auto", record_order=False):
    results = []
    original = cli.answer
    def observe(*args, **kw):
        events = []
        lookup,trace = cli.calls.lookup,cli.flow.Slice.answer
        def lookup_spy(name,*a,**k):
            events.append("calls:"+name)
            return lookup(name,*a,**k)
        def flow_spy(index,name,*a,**k):
            events.append("flow:"+name)
            return trace(index,name,*a,**k)
        with patch.object(cli.calls,"lookup",side_effect=lookup_spy) as calls, \
                patch.object(cli.flow.Slice,"answer",autospec=True,side_effect=flow_spy) as flow:
            answer = original(*args,**kw)
        results.append({"q":args[0],"answer":answer,"calls":calls.call_count,"flow":flow.call_count})
        if record_order:
            results[-1]["executed"] = events
        return answer
    output = io.StringIO()
    argv = ["skynet_explain.py",mode] + ([q] if q else [])
    started = time.perf_counter()
    with patch.object(cli,"answer",observe), patch.object(sys,"argv",argv), redirect_stdout(output), \
            patch("builtins.input",side_effect=[*replies,"/exit"]):
        cli.main()
    return results,output.getvalue(),round(time.perf_counter()-started,3)


def measure(plan, lock):
    run = dict(lock=lock,source=plan["source"],implementation=pilot.git("rev-parse","HEAD").decode().strip(),
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


def check(run,plan,lock):
    verify(run,plan,lock=lock)
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
    mode,name,*flags = sys.argv[1:]
    assert flags in ([],["regression"])
    plan = regression_plan() if flags else json.loads(pilot.git("show",LOCK+":"+QUESTIONS))
    lock = PREVIOUS if flags else LOCK
    if mode == "run":
        with Path(name).open("x",encoding="utf8",newline="\n") as out:
            run = measure(plan,lock)
            json.dump(run,out,ensure_ascii=False,indent=2)
            out.write("\n")
    else:
        assert mode == "verify"
        run = json.loads(Path(name).read_text(encoding="utf8"))
    check(run,plan,lock)
