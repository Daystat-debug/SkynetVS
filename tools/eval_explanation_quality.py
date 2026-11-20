"""Run one preregistered arm against a detached copy of the same Git snapshot."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_skynet_explain import Trace, cli, pilot, verify

FREEZE = "7da41f76ea20db22b9e7d576b19b6dc97b1861ce"
CONTROL = "docs/maintenance/explanation_quality/control.json"


class Recording(Trace):
    def complete(self, system, user):
        self.write("input", case=self.case, system_text=system, user_text=user)
        return super().complete(system, user)


def oracle_prompt(case, aliases, src):
    lines, shown = [case["q"]], {}
    for alias, ranges in case["context"].items():
        path = aliases[alias]
        lines.append("Файл " + path)
        original = src.snapshot.sources[path].splitlines()
        for start, end in ranges:
            for n in range(start, end + 1):
                if n in src.pages[path]:
                    key = f"{alias}:{n}"
                    shown[key] = path, n
                    lines.append(f"{key} {original[n-1]}")
    return "\n".join(lines), shown


def run(group, arm, output):
    assert group in {"oracle", "cli"} and arm in {"baseline", "reviewed"}
    control = json.loads(pilot.git("show", FREEZE + ":" + CONTROL))
    source = control["source"]
    with tempfile.TemporaryDirectory() as temp, output.open("x", encoding="utf8", newline="\n") as stream:
        repo = Path(temp) / "repo"
        pilot.git("clone", "--quiet", "--local", "--no-checkout", str(pilot.ROOT), str(repo))
        pilot.git("checkout", "--quiet", "--detach", source, cwd=repo)
        trace = Recording(stream, len(control[group]) * (1 if arm == "baseline" else 2))
        with cli.local_reader(repo) as (src, ground, provider):
            trace.provider = provider
            trace.write("setup", freeze=FREEZE, source=src.commit, blobs=src.oids, group=group, arm=arm)
            assert src.commit == source
            for case in control[group]:
                trace.case = case["id"]
                q = case["q"]
                before = time.perf_counter()
                if group == "oracle":
                    user, shown = oracle_prompt(case, control["aliases"], src)
                    if arm == "baseline":
                        raw, timing = trace.complete(cli.windows.ANSWER, user)
                        try:
                            result = cli.publish(raw, src, shown, ground) if timing["finish_reason"] == "stop" else cli.refusal("invalid")
                        except (ValueError, KeyError, TypeError, RecursionError):
                            result = cli.refusal("invalid")
                    else:
                        result = cli.reviewed_context(q, shown, src, ground, trace)
                else:
                    result = cli.answer(q, src, ground, trace, reviewed=arm == "reviewed")
                elapsed = round(time.perf_counter() - before, 3)
                verify(result, src.commit, src.raw)
                trace.write("result", case=trace.case, seconds=elapsed, result=result)
                print(trace.case, result["status"], elapsed, flush=True)
            info = provider.p.info if provider.p else {}
        assert trace.count == info.get("requests", 0) and info.get("stopped", True)
        trace.write("done", calls=trace.count, session=info)


def verify_recording(path):
    """Check literal evidence and call accounting without starting a provider."""
    records = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
    setup, done = records[0], records[-1]
    assert setup["kind"] == "setup" and setup["freeze"] == FREEZE and done["kind"] == "done"
    control = json.loads(pilot.git("show", FREEZE + ":" + CONTROL))
    commit = control["source"]
    assert setup["source"] == commit and set(setup["blobs"]) == set(control["aliases"].values())
    blobs = {p: pilot.git("show", commit + ":" + p) for p in setup["blobs"]}
    for p, oid in setup["blobs"].items():
        assert pilot.git("rev-parse", commit + ":" + p).decode().strip() == oid
    pos, calls = 1, 0
    for case in control[setup["group"]]:
        start = calls
        while records[pos]["kind"] == "input":
            inp, reserve, completion = records[pos:pos+3]
            pos += 3
            calls += 1
            assert reserve["kind"] == "reserve" and completion["kind"] == "completion"
            assert reserve["seq"] == completion["seq"] == calls
            assert inp["case"] == reserve["case"] == case["id"] and case["q"] in inp["user_text"]
            for key in ("system", "user"):
                assert pilot.sha(inp[key + "_text"].encode()) == reserve[key]
            assert len((inp["system_text"] + inp["user_text"]).encode()) == reserve["input_bytes"]
        assert calls - start <= (1 if setup["arm"] == "baseline" else 2)
        row = records[pos]
        pos += 1
        assert row["kind"] == "result" and row["case"] == case["id"]
        result = row["result"]
        verify(result, commit, blobs)
        for c in result["claims"]:
            for ref, anchor in zip(c.get("evidence_blocks", []), c["anchors"]):
                p, lo, hi = ref["path"], ref["start"], ref["end"]
                assert p == anchor["path"] and 1 <= lo <= anchor["line"] <= hi <= len(blobs[p].splitlines())
                assert ref["url"] == anchor["url"].split("#")[0] + f"#L{lo}-L{hi}"
    assert pos == len(records)-1 and done["calls"] == calls == done["session"]["requests"] and done["session"]["stopped"]
    print(path.name, calls, "generations verified")


if __name__ == "__main__":
    if sys.argv[1] == "verify" and not sys.flags.optimize:
        for name in sys.argv[2:]:
            verify_recording(Path(name))
    else:
        run(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
