"""Compare the locked CLI to the previous end-to-end baseline on identical Git blobs."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_explain as cli
import m289_quality_route as previous
import m289_diagnostic as pilot

FREEZE = "5329815cd814dfb6818f6c9f293d887da28fc86a"
CONTROL = "docs/maintenance/code_reader/holdout.json"


class Trace:
    def __init__(self, stream, limit):
        self.stream, self.limit = stream, limit
        self.count = 0

    def write(self, kind, **values):
        self.stream.write(json.dumps(dict(kind=kind, **values), ensure_ascii=False) + "\n")
        self.stream.flush()

    def complete(self, system, user):
        if self.count >= self.limit or len((system + user).encode()) > 13000:
            raise ValueError("EVALUATION_BUDGET")
        self.count += 1
        self.write("reserve", case=self.case, seq=self.count, system=pilot.sha(system.encode()),
                   user=pilot.sha(user.encode()), input_bytes=len((system + user).encode()))
        raw, timing = self.provider.complete(system, user)
        self.write("completion", seq=self.count, raw=raw, timing=timing)
        return raw, timing


def verify(result, commit, blobs):
    for claim in result["claims"]:
        for a in claim["anchors"]:
            path, line = a["path"], a["line"]
            raw = blobs[path]
            actual = raw.splitlines(keepends=True)[line - 1]
            assert a["commit"] == commit and pilot.sha(raw) == a["source_sha256"]
            assert a["source_line_with_eol_sha256"] == pilot.sha(actual)
            assert a["source_line"] == actual.decode().splitlines()[0] and a["quote"] in a["source_line"]
            assert a["url"].endswith(f"/{commit}/{path}#L{line}")
            assert a["blob_oid"] == pilot.git("rev-parse", commit + ":" + path).decode().strip()


def measure(trace, questions, call, provider, blobs):
    trace.provider = provider
    for key, q in questions:
        trace.case = key
        before = trace.count
        start = time.perf_counter()
        result = call(q)
        ms = round(1000 * (time.perf_counter() - start), 1)
        verify(result, pilot.PIN, blobs)
        trace.write("result", case=key, result=result, ms=ms, calls=trace.count - before)
        print(key, result["status"], trace.count, flush=True)


def run(arm, output):
    assert arm in {"baseline","cli","final"} and not sys.flags.optimize
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    control = json.loads(pilot.git("show", FREEZE + ":" + CONTROL))
    questions = [(x["id"], x["q"]) for x in control["cases"]]
    if arm == "final":
        holdout = json.loads(pilot.git("show","a718d2c:docs/maintenance/code_reader/final_holdout.json"))
        questions = [r for r in questions if r[0] in {"U1","U3"}]
        questions.extend((x["id"],x["q"]) for x in holdout["cases"])
    with output.open("x", encoding="utf8", newline="\n") as stream, tempfile.TemporaryDirectory() as temp:
        trace = Trace(stream, {"cli":16,"baseline":8,"final":4}[arm])
        work = Path(temp)
        repo = work / "repo"
        pilot.git("clone","--quiet","--no-local","--no-checkout",str(pilot.ROOT),str(repo))
        pilot.git("checkout","--quiet","--detach",pilot.PIN,cwd=repo)
        blobs = {p: pilot.git("show",pilot.PIN+":"+p) for p in (pilot.GS,pilot.CS,pilot.RK)}
        assert all(pilot.git("show","HEAD:"+p) == blob for p,blob in blobs.items())
        trace.write("inputs", arm=arm, freeze=FREEZE, source=pilot.PIN,
                    blobs={p:pilot.sha(b) for p,b in blobs.items()})
        if arm in {"cli","final"}:
            with cli.local_reader(repo) as (src, g, lazy):
                assert src.raw == blobs
                fn = cli.answer if arm == "final" else cli.mapped_answer
                measure(trace, questions, lambda q: fn(q,src,g,trace), lazy, blobs)
                info = lazy.p.info if lazy.p else {}
        else:
            pilot.verify_package()
            import retrieval284 as ret
            import run289 as runner
            import runtime289 as rt
            import ground289 as g
            runner.own_job()
            bridge = ret.Bridge(repo,work/"bundle")
            original = bridge.provider
            catalog = previous.make_catalog(original.capture(),ret.SCOPE)
            with runner.LazyProvider(work,{"provider_sessions":[]},"baseline",rt.LocalProvider) as lazy:
                def call(q):
                    parts, why = previous.plan_for(q,"static",catalog,ret.SCOPE,trace,3584)
                    bridge._bind(bridge.core,previous.PlannedSearch(original,ret.SCOPE,catalog,parts))
                    r = g.answer(previous.PlannedContext(bridge,ret,g,"static"),previous.Handles(trace),q)
                    return dict(status="answer" if r["generated_answer_published"] else "withheld",
                                text=r["display_ru"],claims=r["claims"], reason=r["status"],plan_reason=why)
                measure(trace, questions, call, lazy, blobs)
                info = lazy.p.info if lazy.p else {}
        assert trace.count == info.get("requests",0) and info.get("stopped", True)
        trace.write("done", calls=trace.count, session=info)


if __name__ == "__main__":
    run(sys.argv[1], Path(sys.argv[2]))
