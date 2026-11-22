"""Run the frozen questions through the CLI on a detached source tree, or verify a saved run."""
from contextlib import nullcontext, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_explain as cli

pilot = cli.pilot
LOCK = "d475f4e4c64db4d41bbd8d45d1ddf77205faf3cf"
QUESTIONS = "docs/maintenance/data_flow/questions.json"


def verify(run, plan):
    commit = plan["source"]
    assert run["lock"] == LOCK and run["source"] == commit
    blobs = {p:pilot.git("show",commit+":"+p) for p in (pilot.CS,pilot.RK,pilot.GS)}
    for case,r in zip(plan["cases"],run["results"],strict=True):
        assert (r["id"],r["q"]) == (case["id"],case["q"])
        assert "Вызовов локальной модели: 0" in r["console"]
        for claim in r["answer"]["claims"]:
            assert claim["text"] in r["console"] and claim["evidence_blocks"]
            for ref in claim["evidence_blocks"]:
                p,lo,hi = ref["path"],ref["start"],ref["end"]
                raw = blobs[p]
                lines = raw.splitlines(keepends=True)
                assert 1 <= lo <= hi <= len(lines)
                identity = [commit,p,lo,hi,pilot.sha(raw),pilot.sha(b"".join(lines[lo-1:hi]))]
                assert identity == [ref[k] for k in ("commit","path","start","end","source_sha256","excerpt_sha256")]
                assert ref["id"] == "E"+pilot.sha(json.dumps(identity).encode())[:16]
                assert ref["blob_oid"] == pilot.git("rev-parse",commit+":"+p).decode().strip()
                assert ref["url"] == f"https://github.com/Daystat-debug/SkynetVS/blob/{commit}/{p}#L{lo}-L{hi}"
                assert ref["url"] in r["console"] and ref["source_code_executed"] is False
    print("Verified frozen questions, CLI output, zero model calls and Git evidence.")


def measure(plan):
    commit = plan["source"]
    run = {"lock":LOCK,"source":commit,"implementation":pilot.git("rev-parse","HEAD").decode().strip(),"results":[]}
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)/"repo"
        pilot.git("clone","--local","--quiet","--no-checkout",str(pilot.ROOT),str(repo))
        pilot.git("checkout","--quiet","--detach",commit,cwd=repo)
        with cli.local_reader(repo) as session, patch.object(cli,"local_reader",lambda **kw:nullcontext(session)):
            for case in plan["cases"]:
                output = io.StringIO()
                started = time.perf_counter()
                with redirect_stdout(output), patch.object(sys,"argv",["skynet_explain.py","--flow",case["q"]]):
                    result = cli.main()
                elapsed = round(time.perf_counter()-started,3)
                run["results"].append(dict(id=case["id"],q=case["q"],answer=result,seconds=elapsed,console=output.getvalue()))
                print(case["id"], result["status"], elapsed, flush=True)
    return run


if __name__ == "__main__":
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    mode, name = sys.argv[1:]
    plan = json.loads(pilot.git("show", LOCK+":"+QUESTIONS))
    if mode == "run":
        with Path(name).open("x",encoding="utf8",newline="\n") as stream:
            run = measure(plan)
            json.dump(run,stream,ensure_ascii=False,indent=2)
            stream.write("\n")
    else:
        assert mode == "verify"
        run = json.loads(Path(name).read_text(encoding="utf8"))
    verify(run,plan)
