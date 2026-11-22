"""Paired read-only CLI runs, including the interactive continuation."""
import ast
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from eval_auto_reader import capture, cli, pilot, verify, verify_output

LOCK = "0b55f75765ad666ae4dadc067b076d7a3b37f2e5"
QUESTIONS = "docs/maintenance/composed_reader/questions.json"


def measure(plan):
    result = dict(lock=LOCK,source=plan["source"],implementation=pilot.git("rev-parse","HEAD").decode().strip())
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)/"repo"
        pilot.git("clone","--quiet","--local","--no-checkout",str(pilot.ROOT),str(repo))
        pilot.git("checkout","--quiet","--detach",plan["source"],cwd=repo)
        with cli.local_reader(repo) as session, patch.object(cli,"local_reader",lambda **kw:nullcontext(session)):
            for mode,key in [("--auto","baseline"),("--compose","results")]:
                result[key] = []
                for case in plan["cases"]:
                    (row,),console,seconds = capture(case["q"],mode=mode,record_order=True)
                    result[key].append(dict(row,id=case["id"],console=console,seconds=seconds))
            d = plan["dialogue"]
            first = next(c["q"] for c in plan["cases"] if c["id"] == d["first"])
            turns,console,seconds = capture(replies=[first,d["reply"]],mode="--compose",record_order=True)
            result["dialogue"] = dict(turns=turns,console=console,seconds=seconds)
            assert session[2].p is None
    return result


def check(run,plan):
    verify(run,plan,lock=LOCK)
    verify(dict(run,results=run["baseline"]),plan,lock=LOCK)
    blobs = {p:pilot.git("show",run["source"]+":"+p) for p in (pilot.CS,pilot.GS,pilot.RK)}
    trees = {p:ast.parse(raw) for p,raw in blobs.items()}
    d = run["dialogue"]
    first,reply = d["turns"]
    control = plan["dialogue"]
    before = next(r for r in run["results"] if r["id"] == control["first"])
    assert first["answer"] == before["answer"] and reply["q"] == control["reply"]
    for turn in d["turns"]:
        verify_output(turn["answer"],d["console"],run["source"],blobs)
    for case,row in [*zip(plan["cases"],run["results"],strict=True),(control,reply)]:
        answer = row["answer"]
        relations = answer.get("relations",[])
        for edge in relations:
            site = edge["site"]
            assert site["commit"] == run["source"]
            assert any(isinstance(n,ast.Call) and
                       (n.lineno,n.col_offset,n.end_lineno,n.end_col_offset) ==
                       (site["line"],site["column"],site["end_line"],site["end_column"])
                       for n in ast.walk(trees[site["path"]]))
            assert any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name == edge["function"]
                       and n.lineno == site["definition_line"] for n in trees[site["definition_path"]].body)
        match = (row["executed"] == case.get("tasks",[]) and
                 sorted(r["function"]+":"+r["field"] for r in relations) == sorted(case.get("links",[])) and
                 ("decision" not in case or case["decision"] == answer["auto_route"]))
        print(case.get("id","dialogue"),answer["status"],row["executed"],"OK" if match else "MISMATCH")


if __name__ == "__main__":
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    mode,name = sys.argv[1:]
    plan = json.loads(pilot.git("show",LOCK+":"+QUESTIONS))
    if mode == "run":
        with Path(name).open("x",encoding="utf8",newline="\n") as out:
            run = measure(plan)
            json.dump(run,out,indent=2,ensure_ascii=False)
            out.write("\n")
    else:
        assert mode == "verify"
        run = json.loads(Path(name).read_text(encoding="utf8"))
    check(run,plan)
