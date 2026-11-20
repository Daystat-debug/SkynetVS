"""One locked end-to-end run. No retries, one persistent reservation per generation."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m289_diagnostic as pilot
import m289_quality_route as route
from m289_russian import RussianSearch
from m289_russian_context import RussianContext

FREEZE = "3bad899e5ddbce09f0e473039e1d62206fc809b3"
CONTROL = "docs/maintenance/m289_answer_quality/control.json"


def milliseconds(start):
    return round((time.perf_counter() - start) * 1000, 2)


class Recorder:
    def __init__(self, stream):
        self.stream = stream
        self.count = 0

    def write(self, event, **values):
        self.stream.write(json.dumps({"event": event, **values}, ensure_ascii=False) + "\n")
        self.stream.flush()

    def complete(self, system, user):
        if self.count >= 40 or len((system + user).encode()) > 3584:
            raise ValueError("COUNT_OR_PROMPT_LIMIT")
        self.count += 1
        self.write("reserve", seq=self.count, arm=self.arm, case=self.case,
                   system_sha=pilot.sha(system.encode()), user_sha=pilot.sha(user.encode()))
        raw, timing = self.runtime.complete(system, user)
        self.write("completion", seq=self.count, raw=raw, timing=timing)
        return raw, timing


def check_turn(turn, blobs, oids, g):
    evidence = turn["evidence"]
    assert len(evidence) <= 3
    for item in evidence:
        r = item["ref"]
        data = blobs[r["path"]]
        excerpt = b"".join(data.splitlines(True)[r["start"] - 1:r["end"]])
        assert r["commit"] == pilot.PIN and r["blob_oid"] == oids[r["path"]]
        assert item["text"].encode() == excerpt and pilot.sha(excerpt) == r["excerpt_sha256"]
        assert pilot.sha(data) == r["source_sha256"]
    assert sum(len(e["text"].encode()) for e in evidence) <= 3000
    if turn["model_called"]:
        assert pilot.sha(g._input(turn["question"], evidence).encode()) == turn["user_payload_sha256"]
    if turn["generated_answer_published"]:
        assert all(c["anchors"] for c in turn["claims"])


def checks(g):
    assert len(g.selftest_details()) == 15
    assert not route.read_parts('{"parts":[]}', 4)
    try:
        route.read_parts('{"parts":[{"id":0,"terms":["m"]}]}', 1)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown catalog ID")
    user = '{"sources":[{"id":"E1","lines":[[17,"    return 42"]]}]}'
    original = '{"status":"answer","reason":"","claims":[{"text":"Ответ равен 42.","lines":["E1:17"]}]}'
    obj = json.loads(route.convert_handles(original, user))
    assert obj["claims"][0]["anchors"] == [{"ref":"E1","line":17,"quote":"return 42"}]
    try:
        route.convert_handles(original.replace("E1:17", "E1:16"), user)
    except KeyError:
        pass
    else:
        raise AssertionError("foreign line accepted")
    assert route.locate(["alpha = 0", "print(alpha)", "return 827"], ["827"]) == 2
    assert len(route.ANSWER.encode()) <= len(g.SYSTEM.encode())


def run(out):
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    members = pilot.verify_package()
    import ground289 as g
    import retrieval284 as ret
    import runtime289 as rt
    import run289 as runner
    checks(g)
    protocol = json.loads(pilot.git("show", FREEZE + ":" + CONTROL))
    assert protocol["source"] == pilot.PIN
    cases = [(x["id"], x["q"], x["basis"]) for x in protocol["cases"]]
    assert len(cases) == 8
    blobs = {p: pilot.git("show", pilot.PIN + ":" + p) for p in ret.SCOPE}
    oids = {p: pilot.git("rev-parse", pilot.PIN + ":" + p).decode().strip() for p in ret.SCOPE}
    runner.own_job()
    with out.open("x", encoding="utf8", newline="\n") as stream, tempfile.TemporaryDirectory() as temp:
        log = Recorder(stream)
        work = Path(temp)
        repo = work / "repo"
        pilot.git("clone", "--quiet", "--no-local", "--no-checkout", str(pilot.ROOT), str(repo))
        pilot.git("checkout", "--quiet", "--detach", pilot.PIN, cwd=repo)
        bridge = ret.Bridge(repo, work / "bundle")
        original = bridge.provider
        start = time.perf_counter()
        snap = original.capture()
        catalog = route.make_catalog(snap, ret.SCOPE)
        assert all(snap.sources[p].encode() == data for p, data in blobs.items())
        log.write("inputs", freeze=FREEZE, snapshot=pilot.PIN, members=members, blobs=oids,
                  capture_and_catalog_ms=milliseconds(start), catalog=catalog, model=rt.MODEL_SHA256,
                  runtime=rt.RUNTIME_SHA256, test_count=15)
        russian = RussianSearch(original, ret.SCOPE)
        plans, costs, payloads = {}, {}, {}
        for arm in ("O", "A", "plan", "B", "C"):
            profile = work / ("profile_" + arm)
            profile.mkdir()
            start = time.perf_counter()
            with rt.LocalProvider(profile) as provider:
                log.runtime, log.arm = provider, arm
                log.write("start", arm=arm, startup_ms=milliseconds(start))
                for key, q, basis in cases:
                    log.case = key
                    start = time.perf_counter()
                    if arm == "plan":
                        plans[key], reason = route.plan_for(q, basis, catalog, ret.SCOPE, log, 3584)
                        costs[key] = milliseconds(start)
                        log.write("plan", case=key, parts=plans[key], reason=reason, ms=costs[key])
                        continue
                    if arm == "O":
                        provider_search, cls = original, None
                    elif arm == "A":
                        provider_search, cls = russian, RussianContext
                    else:
                        provider_search = route.PlannedSearch(original, ret.SCOPE, catalog, plans[key])
                        cls = route.PlannedContext
                    bridge._bind(bridge.core, provider_search)
                    api = cls(bridge, ret, g, basis) if cls else bridge
                    turn = g.answer(api, route.Handles(log) if arm == "C" else log, q, basis=basis)
                    elapsed = milliseconds(start)
                    check_turn(turn, blobs, oids, g)
                    if arm == "B":
                        payloads[key] = turn.get("user_payload_sha256")
                    if arm == "C":
                        assert turn.get("user_payload_sha256") == payloads[key]
                    # The original Git lines are reconstructible from refs; retain the original anchors.
                    refs = [item["ref"] for item in turn.pop("evidence")]
                    log.write("turn", arm=arm, case=key, turn=turn, refs=refs, ms=elapsed,
                              end_to_end_ms=round(elapsed + (costs[key] if arm in ("B","C") else 0), 2))
                    print(arm, key, turn["status"], "calls", log.count, flush=True)
            log.write("session", arm=arm, info=provider.info)
        log.write("done", calls=log.count)


if __name__ == "__main__":
    run(Path(sys.argv[1]))
