"""Paired retrieval-only measurement on an isolated clone of the pinned snapshot."""
import json
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m289_diagnostic as pilot
from m289_scoped_retrieval import ScopedCandidates

FREEZE = "72c214290cbcc9f87e526bf3ee433277b304d9bf"
NEW = "docs/maintenance/m289_scoped_retrieval/holdout.json"
BASE = "d32683c875d490d1c0be84942efde8f293a5219f"
CS, GS, RK = "cs", "gs", "rk"
# Scorable H answer facts, matching the baseline report's 19 units.
H = {
    1:[(CS,"expand_query",[[48],[48,49,50]])],
    2:[(GS,"GitSourceReader._run",[[93],[95,96],[97,106,107]])],
    3:[(CS,"expand_query",[[50,51]]),(CS,"search_repository",[[146,153]]),(RK,"rank",[[116]])],
    4:[(RK,"rank",[[120],[121,122],[124]])],
    7:[(GS,"GitSourceReader._sha",[[112],[112,113]]),(CS,"scan_head",[[81,137],[137,138]])],
    8:[(RK,"rank",[[125,126,127],[128],[138]]),(CS,"search_repository",[[157]])],
}


def synthetic(provider, core, pin):
    allow, other = "modules/foo.py", "modules/bar.py"
    adapter = ScopedCandidates(provider, {allow})
    snap = core.Snapshot(pin, {other:"def emerald():\n    return 'emerald'\n",
                              allow:"def allowed():\n    return 'sapphire'\n"}, {})
    assert provider.search(snap, "emerald")[0]["path"] == other
    assert not adapter.search(snap, "emerald")
    assert adapter.search(snap, "sapphire")[0]["path"] == allow
    assert not ScopedCandidates(provider,set()).search(snap, "sapphire")
    try:
        adapter.inspect(snap, "emerald", other+"::emerald@1")
    except ValueError as exc:
        assert str(exc) == "M289_CANDIDATE_OUTSIDE_SCOPE"
    else:
        raise AssertionError("out-of-scope inspection")
    assert set(snap.sources)=={allow,other}


class AtProvider(Exception):
    """Stop after the original code has validated and serialized the context."""


class Probe:
    def complete(self, system, user):
        self.user = user
        raise AtProvider


class Tap:
    def __init__(self, bridge):
        self.bridge = bridge

    def retrieve(self, question):
        self.found = self.bridge.retrieve(question)
        return self.found

    def check(self, ref):
        return self.bridge.check(ref)


def run_one(bridge, grounding, question, basis, rubric):
    tap, probe = Tap(bridge), Probe()
    sent = []
    start = time.perf_counter_ns()
    try:
        decision = grounding.answer(tap,probe,question,basis=basis)["status"]
    except AtProvider:
        decision = "PROVIDER_BOUNDARY"
    elapsed = (time.perf_counter_ns()-start)/1e6
    if decision=="PROVIDER_BOUNDARY":
        sent=json.loads(probe.user)["sources"]
    rows=tap.found
    ids=rows["candidates"]
    sent_lines = {(row["path"],ln) for row in sent for ln,_ in row["lines"]}
    positions = []
    facts = []
    for path,name,units in rubric:
        target = path+"::"+name+"@"
        positions.append(next((i for i,s in enumerate(ids,1) if s.startswith(target)),None))
        facts.extend(all((path,ln) in sent_lines for ln in unit) for unit in units)
    return {"status":rows["status"],"gate":decision,"candidates":ids,
            "selected":[item["ref"] for item in rows["evidence"]],
            "payload_sha256":pilot.sha(probe.user.encode()) if sent else None,
            "sent":[[r["path"],r["lines"][0][0],r["lines"][-1][0]] for r in sent],
            "positions":positions,"facts":facts},round(elapsed,3)


def main(out):
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    members=pilot.verify_package()
    import retrieval284 as retrieval
    import ground289 as grounding
    frozen=pilot.git("show",FREEZE+":"+NEW)
    assert pilot.git("rev-parse",FREEZE+":"+NEW).decode().strip()=="a5ffbe10b77bfedaca28fc8a3352ef35e3ab6d03"
    holdout=json.loads(frozen)
    old=json.loads(pilot.git("show",BASE+":docs/maintenance/m289_diagnostic/A.json"))
    questions=[(f"H{n}",r["question"],H.get(n,[]),r["basis"]) for n,r in enumerate(old,1)]
    questions += [(key,q,g,"live" if key=="N8" else "static") for key,q,g in holdout["cases"]]
    work=Path(tempfile.mkdtemp(prefix="m289-ranking-"))
    repo=work/"repo"
    pilot.git("clone","--quiet","--no-local","--no-checkout",str(pilot.ROOT),str(repo))
    pilot.git("checkout","--quiet","--detach",pilot.PIN,cwd=repo)
    bridge=retrieval.Bridge(repo,work/"bundle")
    full=bridge.provider
    scoped=ScopedCandidates(full,retrieval.SCOPE)
    snap=full.capture()
    synthetic(full,bridge.core,pilot.PIN)
    from app.context_search import expand_query
    from app.retrieval.m126_rank import rank_title_only,tokens
    result={"source":pilot.PIN,"freeze":FREEZE,"pilot_pack":pilot.PACK,
            "scope":sorted(retrieval.SCOPE),"package_members":members,"scan":snap.scan,
            "arms":["base","scoped"],"pairs_per_question":3,"cases":{}}
    for key,q,g,basis in questions:
        rubric=[(pilot.PREFIX+holdout["paths"][p],name,units) for p,name,units in g]
        case={"question":q,"rubric":rubric}
        arm_order=[("base",full),("scoped",scoped)]
        # File gate diagnostics outside the timed call, with the original tokenizer.
        effective,hints=expand_query(q)
        case["tokens"]=list(dict.fromkeys(tokens(effective)))
        case["hints"]=hints
        for arm,subset in (("base",snap.sources),("scoped",{p:s for p,s in snap.sources.items() if p in scoped.scope})):
            files=rank_title_only(effective,dict(subset))
            case[arm]={"file_gate":files["retrieval_confidence"],"positive_files":files["nonzero_scores"],
                       "ms":[]}
        for rep in range(3):
            for arm,provider in (arm_order if (rep+int(key[1:]))%2==0 else reversed(arm_order)):
                bridge._bind(bridge.core,provider)
                row,ms=run_one(bridge,grounding,q,basis,rubric)
                if rep:
                    assert all(case[arm][k]==v for k,v in row.items())
                else:
                    case[arm].update(row)
                case[arm]["ms"].append(ms)
        if key.startswith("H"):
            previous=old[int(key[1:])-1]
            assert case["base"]["status"]==previous["retrieval_status"]
            assert case["base"]["candidates"]==previous["all_candidates"]
            assert case["base"]["payload_sha256"]==previous.get("user_payload_sha256")
        result["cases"][key]=case
        print(key,case["base"]["status"],case["scoped"]["status"],flush=True)
    pilot.dump(out,result)


if __name__=="__main__":
    main(Path(sys.argv[1]))
