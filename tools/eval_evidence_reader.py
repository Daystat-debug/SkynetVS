"""Replay preregistered questions or independently verify stored inputs, links and call counts."""
from contextlib import nullcontext, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_explanation_quality import Recording, cli, oracle_prompt, pilot, verify

LOCK = "0cd30c7e2f59a89a7d17893378aedcea490f3e06"
PROTOCOL = "docs/maintenance/evidence_reader/protocol.json"
CALL_LOCK = "cdaef8461f7391d7533dfb19f9f6696cf2730abd"


class Capture(Recording):
    @property
    def p(self):
        return self.provider.p


def inputs(group, arm):
    plan = json.loads(pilot.git("show", LOCK + ":" + PROTOCOL))
    earlier = json.loads(pilot.git("show", plan["earlier_control"]))
    if group in {"call_oracle","calls"}:
        calls = json.loads(pilot.git("show",CALL_LOCK + ":docs/maintenance/evidence_reader/calls_protocol.json"))
        cases = [calls["oracle"]] if group == "call_oracle" else calls["cli"]
        return calls["source"], earlier["aliases"], cases[:1] if arm == "baseline" else cases
    cases = earlier[group]
    if group == "cli" and arm == "prose":
        cases = cases + plan["additional_cli"]
    return plan["source"], earlier["aliases"], cases


def run(group, arm, out):
    assert (group, arm) in {("oracle","prose"), ("cli","baseline"), ("cli","prose"),
                            ("call_oracle","static"), ("calls","baseline"), ("calls","static")}
    commit, aliases, cases = inputs(group, arm)
    with tempfile.TemporaryDirectory() as tmp, out.open("x", encoding="utf8", newline="\n") as stream:
        repo = Path(tmp) / "repo"
        pilot.git("clone", "--quiet", "--local", "--no-checkout", str(pilot.ROOT), str(repo))
        pilot.git("checkout", "--quiet", "--detach", commit, cwd=repo)
        limit = 2 if group == "oracle" else (4 if arm == "baseline" else 10)
        if group in {"call_oracle","calls"}:
            limit = int(arm == "baseline")
        trace = Capture(stream, limit)
        with cli.local_reader(repo, prose=arm == "prose") as (src, ground, provider):
            assert src.commit == commit and set(src.raw) == set(aliases.values())
            trace.provider = provider
            trace.write("setup", lock=CALL_LOCK if group in {"call_oracle","calls"} else LOCK,
                        group=group, arm=arm, source=commit, blobs=src.oids)
            for case in cases:
                trace.case, q = case["id"], case["q"]
                start = time.perf_counter()
                output = io.StringIO()
                with redirect_stdout(output):
                    if group == "oracle":
                        _, rows = oracle_prompt(case, aliases, src)
                        result = cli.evidence.explain(q, rows.values(), src, trace, cli.refusal)
                        cli.display(result)
                    elif group == "call_oracle":
                        files = [p for p in src.pages if p.endswith("/" + case["file"])]
                        assert len(files) == 1
                        result = cli.calls.lookup(q,src,cli.refusal,files)
                        cli.display(result)
                    else:
                        argv = ["skynet_explain.py"] + {"prose":["--prose"], "baseline":[], "static":["--calls"]}[arm] + [q]
                        def reader(*, prose):
                            assert prose == (arm == "prose")
                            return nullcontext((src, ground, trace))
                        with patch.object(sys, "argv", argv), patch.object(cli, "local_reader", reader):
                            result = cli.main()
                trace.write("result", case=trace.case, result=result, console=output.getvalue(),
                            seconds=round(time.perf_counter()-start, 3))
                print(trace.case, result["status"], trace.count, flush=True)
            info = provider.p.info if provider.p else {}
        assert info.get("requests",0) == trace.count and info.get("stopped",True)
        trace.write("done", calls=trace.count, session=info)


def check(path):
    with path.open(encoding="utf8") as stream:
        records = iter([json.loads(s) for s in stream])
    head = next(records)
    commit, aliases, cases = inputs(head["group"], head["arm"])
    assert head["kind"] == "setup" and head["source"] == commit
    assert head["lock"] == (CALL_LOCK if head["group"] in {"call_oracle","calls"} else LOCK)
    blobs = {p:pilot.git("show",commit + ":" + p) for p in aliases.values()}
    assert head["blobs"] == {p:pilot.git("rev-parse", commit+":"+p).decode().strip() for p in blobs}
    calls = links = 0
    for case in cases:
        user = ""
        row = next(records)
        while row["kind"] == "input":
            req, reply = next(records), next(records)
            calls += 1
            user = row["user_text"]
            assert req["kind"] == "reserve" and reply["kind"] == "completion" and req["seq"] == reply["seq"] == calls
            assert row["case"] == req["case"] == case["id"] and case["q"] in user
            assert req["user"] == pilot.sha(user.encode()) and req["system"] == pilot.sha(row["system_text"].encode())
            row = next(records)
        assert row["kind"] == "result" and row["case"] == case["id"]
        res = row["result"]
        verify(res, commit, blobs)
        links += sum(len(c["anchors"]) for c in res["claims"])
        refs = res.get("sources", []) + [r for claim in res["claims"] for r in claim.get("evidence_blocks", [])]
        for ref in refs:
            p, a, b = ref["path"], ref["start"], ref["end"]
            buf = blobs[p].splitlines(keepends=True)
            assert 1 <= a <= b <= len(buf)
            excerpt = b"".join(buf[a-1:b])
            identity = [commit,p,a,b,pilot.sha(blobs[p]),pilot.sha(excerpt)]
            assert [ref[k] for k in ("commit","path","start","end","source_sha256","excerpt_sha256")] == identity
            assert ref["id"] == "E"+pilot.sha(json.dumps(identity).encode())[:16] and ref["blob_oid"] == head["blobs"][p]
            assert ref["url"] == f"https://github.com/Daystat-debug/SkynetVS/blob/{commit}/{p}#L{a}-L{b}"
            assert ref["url"] in row["console"]
            if head["arm"] == "prose":
                assert f"{p} ({a}–{b})\n" + "\n".join(excerpt.decode().splitlines()) in user
            links += 1
    done = next(records)
    assert done["kind"] == "done" and calls == done["calls"] == done["session"].get("requests",0) and done["session"].get("stopped",True)
    assert next(records,None) is None
    print(path.name, calls, "generations,", links, "Git links verified")


if __name__ == "__main__":
    assert not sys.flags.optimize and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    if sys.argv[1] == "check":
        for arg in sys.argv[2:]:
            check(Path(arg))
    else:
        run(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
