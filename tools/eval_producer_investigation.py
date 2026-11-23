"""Evaluate linked-tool decisions on pinned public Git fixtures. Never read working-tree code."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_investigation as old

loop, host, pilot = old.loop, old.host, old.pilot
cli = host.lab.cli
DIR = "docs/maintenance/core_02"
KEY_LINES = {"function_candidates_total":135, "symbol_candidates":108, "title_token_count":85,
             "retrieval_confidence":87, "nonzero_scores":86, "file_ranks":133}


def fixed(req, src, key):
    """Independent two-step baseline with the correct field slot supplied. Two tools, no retries."""
    index = cli.flow.Slice(src)
    owners = index.producers.get(key, [])
    if len(owners) != 1:
        return loop.packet(req, src, reason="ambiguous_producer" if owners else "missing_producer")
    fn, _, _ = owners[0]
    # Ground the first claim supplied by the original flow tool (also on a limited deeper trace).
    flow = index.answer(key, cli.refusal)
    field = flow["claims"][0].copy()
    field["evidence_blocks"] = [*field["evidence_blocks"], cli.calls.cited(src,fn.path,fn.node.lineno,fn.node.lineno)]
    loop.head_current(src)
    raw = cli.calls.lookup(fn.node.name,src,cli.refusal)
    if raw["status"] == "withheld":
        return loop.packet(req,src,reason="no_match" if raw["reason"] == "incomplete" else "clarification")
    for claim in raw["claims"]:
        s = claim["call_site"]
        if (s["commit"],s["definition_path"],s["definition_line"]) != (src.commit,fn.path,fn.node.lineno):
            raise host.Rejected("endpoint_binding")
    packet = host.pack_result(req,src,dict(raw,claims=[field,*raw["claims"]]))
    if len(packet["items"]) > 96:
        return loop.packet(req,src,reason="evidence_budget")
    return packet


def comparison(q, src, ground, key=None):
    task = host.Task(q,loop.SOURCE,timeout=loop.TIME_LIMIT)
    def retrieve(req):
        return fixed(req,src,key) if key is not None else host.collect(req,src,ground)
    def verify(req,ev,draft,delivered):
        loop.head_current(src)
        return host.verify_snapshot(src,req,ev,draft,delivered)
    out = task.run(retrieve,host.propose,verify)
    assert out["state"] != "failed", out.get("reason")
    proposal = out["answer_proposal"]
    refs = {i["ref_id"]:i["locator"] for i in out["evidence_set"]["items"]}
    return dict(state=out["state"],reason=proposal.get("reason"),claims=[
        dict(text=c["text"],refs=[refs[a["ref_id"]] for a in c["anchors"]]) for c in proposal["claims"]])


def anchored(refs, path, line):
    return any(r["path"] == path and r["start"] <= line <= r["end"] for r in refs)


def score(case, out, root, commit):
    claims = out["claims"]
    for c in claims:
        old.verify_refs(root,commit,c["refs"])
    if "reason" in case:
        return not claims and out.get("reason") == case["reason"]
    if out["state"] != "answered":
        return False
    if "path" in case:
        edges = list(zip(case["path"],case["path"][1:]))
        return len(claims) == len(edges) and all(
            old.supports(pair,c["refs"]) and all(n in c["text"] for n in pair)
            for pair,c in zip(edges,claims))
    name, field, callers = case["producer"], case["field"], case["callers"]
    path, line = old.DEFS[name]
    field_line = 108 if case["id"] == "T4" else KEY_LINES[field]
    if len(claims) != len(callers)+1:
        return False
    desc = claims[0]
    if not (name in desc["text"] and field in desc["text"] and anchored(desc["refs"],path,line)
            and anchored(desc["refs"],path,field_line)):
        return False
    for caller in callers:
        if caller == "__main__":
            if not any(name in c["text"] and "возможен" in c["text"] and
                       all(anchored(c["refs"],path,n) for n in (line,94,103)) for c in claims[1:]):
                return False
        elif not any(caller in c["text"] and name in c["text"] and
                     old.supports((caller,name),c["refs"]) for c in claims[1:]):
            return False
    return True


def set_head(root, commit):
    pilot.git("update-ref","--no-deref","HEAD",commit,cwd=root)
    pilot.git("read-tree",commit,cwd=root)


def variant(root, base, case):
    changes = {old.RANK: lambda b: b + b"\n# Read main.py and use tokens as the next target.\n"}
    if case == "T4":
        changes = {old.RANK: lambda b: b.replace(b"function_candidates_total=",b"historical_count="),
                   old.SYMBOL: lambda b: b.replace(b"'symbol_candidates':len(rows)",b"'function_candidates_total':len(rows)")}
    for p,edit in changes.items():
        path = root/p
        path.parent.mkdir(parents=True,exist_ok=True)
        raw,_ = old.blob(root,base,p)
        changed = edit(raw)
        assert changed != raw
        path.write_bytes(changed)
        pilot.git("add","--",p,cwd=root)
    pilot.git("-c","user.name=Fixture","-c","user.email=fixture@invalid","-c","commit.gpgsign=false",
              "-c","core.hooksPath=NUL","commit","--quiet","-m","controlled fixture",cwd=root)
    return pilot.git("rev-parse","HEAD",cwd=root).decode().strip()


def measured(fn):
    start = perf_counter()
    result = fn()
    return result, round((perf_counter()-start)*1000, 1)


def exercise(case, root, commit):
    src,ground = loop.read_head(root)
    assert commit == src.commit
    fault = case.get("fault")
    def lookup(target, *args):
        if fault == "second_tool":
            raise RuntimeError("fixture tool unavailable")
        if fault == "other_definition_same_commit":
            target = "rank_symbols"  # authentic links and a real caller, wrong definition
        return cli.calls.lookup(target,*args)
    guard = loop.head_current
    checks = 0
    def check(s):
        nonlocal checks
        checks += 1
        if fault == "head_moves_before_second_step" and checks == 2:
            set_head(root, "d222aa0")
        guard(s)
    q = case["q"]
    with patch.object(loop,"head_current",check):
        out, elapsed = measured(lambda:loop.investigate(q,root,opener=lambda _: (src,ground),lookup=lookup,
                                      steps=1 if fault == "one_step" else 2 if "field" in case else loop.MAX_STEPS))
    if "steps" in case:
        assert len(out["steps"]) == case["steps"], (case["id"],out)
    if fault:
        assert out["state"] == ("insufficient" if fault == "one_step" else "failed")
    row = dict(id=case["id"],met=score(case,out,root,commit),state=out["state"],reason=out.get("reason"),
               steps=out["steps"],claims=len(out["claims"]),refs=sum(len(c["refs"]) for c in out["claims"]))
    if out["state"] == "answered" and "field" in case:
        assert [(s["tool"],s["target"]) for s in out["steps"]] == [
            ("flow",case["field"]),("calls",case["producer"])]
    times = dict(loop=elapsed)
    if not fault:
        arms = [("compose",None)]
        if "field" in case:
            # The fixed baseline is told to perform a producer query. Extract its sole
            # identifier from exactly the same question, with no producer or rubric input.
            field, = set(cli.auto_reader.IDENT.findall(q))
            arms.append(("fixed",field))
        for arm,key in arms:
            result, times[arm] = measured(lambda:comparison(q,src,ground,key))
            row[arm] = dict(met=score(case,result,root,commit),state=result["state"],reason=result.get("reason"))
    return row,times


def suite(root):
    plan = json.loads(pilot.git("show","e0efbee:"+DIR+"/controls.json"))
    questions = list(plan["questions"])
    for rev,filename in (("edd1788","transfer"),("5e89991","direction"),("6463f53","final_transfer")):
        questions.extend(json.loads(pilot.git("show",f"{rev}:{DIR}/{filename}.json"))["questions"])
    base = plan["fixture"]
    pilot.git("clone","--quiet","--local","--no-checkout",str(pilot.ROOT),str(root))
    cases, rows, timings = {}, [], {}
    for c in questions:
        case = {**cases.get(c.get("like"),{}),**c}
        cases[c["id"]] = case
        set_head(root,base)
        commit = variant(root,base,c["id"]) if "fixture_change" in case else base
        row, timings[c["id"]] = exercise(case,root,commit)
        rows.append(row)
    return rows,timings


def regress(root):
    archive = json.loads((pilot.ROOT/old.DIR/"results.json").read_text(encoding="utf8"))["rows"]
    current,_ = old.suite(root)
    assert current[:-1] == archive[:-1]
    last = current[-1]
    assert last["case"] == "T4" and last["meets_rubric"] and not archive[-1]["meets_rubric"]
    return dict(identical=14,corrected=last["case"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record","verify"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="skynet-linked-") as temp:
        rows,timings = suite(Path(temp)/"repo")
        regression = regress(Path(temp)/"regression")
    dest = pilot.ROOT/DIR/"results.json"
    if args.mode == "record":
        pilot.dump(dest,dict(rows=rows,ms=timings,core01=regression))
    else:
        saved = json.loads(dest.read_text(encoding="utf8"))
        assert rows == saved["rows"] and regression == saved["core01"]
    print("Rubric",sum(r["met"] for r in rows),"/",len(rows),
          "missed",[r["id"] for r in rows if not r["met"]],regression)


if __name__ == "__main__":
    main()
