"""Run the post-freeze questions and seeded topology challenge without executing their code."""
import argparse
from collections import deque
import importlib.util
import json
import os
from pathlib import Path
import random
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_investigation as old
from eval_producer_investigation import anchored, set_head
import skynet_argument_flow as arguments

loop,host,pilot = old.loop, old.host, old.pilot
DIR = "docs/maintenance/core_03"
DEFS = {**old.DEFS, "scan_head":(pilot.CS,68)}


class PathFirst(arguments.Search):
    """Oracle endpoints, cached BFS over call sites; bind actuals only on a complete call path."""
    first_only = False

    def witness(self, origin, target, formal):
        pending = deque([(target,[],{target})])
        while pending:
            name,path,visited = pending.popleft()
            for site in self.incoming(name):
                caller = site.caller.node.name
                route = [*path,site]
                if caller == origin:
                    parameter, claims = formal, []
                    for step in route:
                        transfer = self.bind(step,parameter,origin)
                        if transfer is None:
                            break
                        parameter,claim = transfer
                        claims.append(claim)
                    else:
                        return claims[::-1]
                    if self.first_only:
                        return []
                elif caller not in visited:
                    pending.append((caller,route,visited|{caller}))
        return []


class FirstPath(PathFirst):
    first_only = True


class Greedy(arguments.Search):
    """Filter on the required formal early, prefer a complete proof, otherwise try one branch."""
    def witness(self, origin, target, formal):
        seen = set()
        suffix = []
        while (target,formal) not in seen:
            seen.add((target,formal))
            choices = []
            for site in self.incoming(target):
                transfer = self.bind(site,formal,origin)
                if transfer:
                    previous,claim = transfer
                    if previous is None:
                        return [claim,*suffix]
                    choices.append((site.caller.node.name,previous,claim))
            if not choices:
                break
            target,formal,claim = choices[0]
            suffix.insert(0,claim)
        return []


def baseline(reader,src,q,goal):
    task = host.Task(q,loop.SOURCE,timeout=loop.TIME_LIMIT)
    trace = []
    def retrieve(req):
        search = reader(req,src,host.lab.cli.calls.lookup,trace,loop.MAX_STEPS,task.deadline,
                        loop.head_current,loop.site_anchors)
        return loop.packet(req,src,*search.solve(*goal))
    def verify(req,ev,draft,delivered):
        loop.head_current(src)
        return host.verify_snapshot(src,req,ev,draft,delivered)
    result = task.run(retrieve,host.propose,verify)
    if result["state"] == "failed":
        return dict(state="failed",claims=[],steps=trace,reason=result["reason"])
    proposed = result["answer_proposal"]
    items = {i["ref_id"]:i["locator"] for i in result["evidence_set"]["items"]}
    return dict(state=result["state"],steps=trace,reason=proposed.get("reason"),
                claims=[dict(text=c["text"],refs=[items[a["ref_id"]] for a in c["anchors"]])
                        for c in proposed["claims"]])


def checkout_fixture(root,base,raw):
    # Only synthetic bytes plus the pinned public blob. Do not stage anything from the user's tree.
    set_head(root,base)
    blob = subprocess.check_output(["git","hash-object","-w","--stdin"],cwd=root,input=raw).decode().strip()
    pilot.git("update-index","--cacheinfo",f"100644,{blob},{old.RANK}",cwd=root)
    tree = pilot.git("write-tree",cwd=root).decode().strip()
    env = dict(os.environ, GIT_AUTHOR_DATE="2000-01-01T00:00:00Z",GIT_COMMITTER_DATE="2000-01-01T00:00:00Z")
    commit = subprocess.check_output(["git","-c","user.name=Fixture","-c","user.email=fixture@invalid",
               "-c","commit.gpgSign=false","commit-tree",tree,"-p",base,"-m","generated transfer"],
               cwd=root,env=env).decode().strip()
    set_head(root,commit)
    return commit


def challenge(rng,width,number,raw,negative=None,plausible=False):
    # Record the oracle while EMITTING statements. No AST reader or planner is used to label tasks.
    def fresh():
        return "f_"+format(rng.getrandbits(52),"x")
    origin,leaf = fresh(),fresh()
    arms = [fresh() for _ in range(width)]
    chosen = rng.randrange(width)
    suffix = []
    defs = {}
    first_line = len(raw.splitlines())
    def emit(line):
        suffix.append(line)
        return first_line + len(suffix)
    def define(name,args):
        emit("")
        defs[name] = (old.RANK,emit(f"def {name}({args}):"))
    define(leaf,"*, payload=0")
    emit("    return payload")
    for i,arm in enumerate(arms):
        define(arm,"incoming")
        if i == chosen or plausible:
            copy_line = emit("    copy = incoming")
            if negative == "reassigned":
                emit("    copy = 9")
            call = "()" if negative == "default" else "(payload=copy)"
            call_line = emit(f"    return {leaf}{call}")
            if i == chosen:
                alias,leaf_line = copy_line,call_line
        else:
            expr = "incoming + 1" if i % 2 else str(i+1)
            emit(f"    return {leaf}(payload={expr})")
    define(origin,"ticket")
    for i,arm in enumerate(arms):
        if plausible and i != chosen:
            continue
        line = emit(f"    {arm}(ticket)")
        if i == chosen:
            origin_line = line
    q = f"Что из {origin} передаётся в {leaf}.payload?"
    case = dict(id=("B" if plausible else "G")+f"{number:02}",q=q,goal=[origin,leaf,"payload"],width=width)
    if negative:
        case["reason"] = "argument_unproven"
    else:
        case["hops"] = [[origin,arms[chosen],"incoming","ticket",origin_line],
                        [arms[chosen],leaf,"payload","copy",leaf_line]]
        case["alias"] = alias
    return raw+("\n".join(suffix)+"\n").encode(), case,defs


def grade(case,result,root,commit,defs):
    claims = result["claims"]
    for c in claims:
        old.verify_refs(root,commit,c["refs"])
    if "reason" in case:
        return result["state"] == "insufficient" and not claims and case["reason"] == result.get("reason")
    hops = case["hops"]
    if len(claims) != len(hops) or result["state"] != "answered":
        return False
    for hop,claim in zip(hops,claims):
        caller,callee,param,expr,line,*imports = hop
        path,header = defs[caller]
        required = [(path,header),defs[callee],(path,line),*((path,i) for i in imports)]
        if "alias" in case and hop == hops[-1]:
            required.append((path,case["alias"]))
        if not all(anchored(claim["refs"],p,n) for p,n in required):
            return False
        expected = f"В {caller} выражение «{expr}» передаётся в {callee}.{param}."
        if "alias" in case and hop == hops[-1]:
            expected += " Привязка copy получена из incoming."
        if claim["text"] != expected:
            # Permit semantically equivalent output from the older direct calls tool.
            if (case.get("alias") or caller not in claim["text"] or callee not in claim["text"]
                    or f"\x60{param}\x60 получает \x60{expr}\x60" not in claim["text"]):
                return False
    return True


def evaluate(case,root,commit,defs,prior,ordinal):
    src,ground = loop.read_head(root)
    assert src.commit == commit
    q = case["q"]
    inputs = lambda _: (src,ground)
    runners = [("core02",lambda:prior.investigate(q,root,opener=inputs)),
               ("first",lambda:baseline(FirstPath,src,q,case["goal"])),
               ("all_paths",lambda:baseline(PathFirst,src,q,case["goal"])),
               ("greedy",lambda:baseline(Greedy,src,q,case["goal"])),
               ("core03",lambda:loop.investigate(q,root,opener=inputs))]
    row = dict(id=case["id"],positive="hops" in case,commit=commit)
    times = {}
    offset = ordinal % len(runners)
    for arm,run in runners[offset:] + runners[:offset]:
        start = perf_counter()
        result = run()
        times[arm] = round((perf_counter()-start)*1000,1)
        assert len(result["steps"]) <= loop.MAX_STEPS
        row[arm] = dict(correct=grade(case,result,root,commit,defs),state=result["state"],
                        reason=result.get("reason"),steps=len(result["steps"]),claims=len(result["claims"]))
        if arm == "core03":
            row["actions"] = [s["target"] for s in result["steps"]]
            # Only known public/synthetic fixtures; line coordinates allow independent replay.
            row["answer"] = [dict(text=c["text"],locations=[[r["path"],r["start"],r["end"]]
                                 for r in c["refs"]]) for c in result["claims"]]
    return row,times


def refusal_controls(root,base,case):
    set_head(root,base)
    src,ground = loop.read_head(root)
    rows = {}
    def check(name, reason, state, count, **kwargs):
        result = loop.investigate(kwargs.pop("question",case["q"]),root,opener=lambda _: (src,ground),**kwargs)
        actual = (result["state"],result.get("reason"),len(result["steps"]),result["claims"])
        assert actual == (state,reason,count,[]), (name,actual)
        rows[name] = reason
    check("one_step","step_budget","insufficient",1,steps=1)
    check("outside","out_of_scope","insufficient",0,question=case["q"]+" в main.py")
    check("live","observation_required","insufficient",0,question=case["q"]+" в последнем запуске")
    lookup = host.lab.cli.calls.lookup
    check("other_real_target","endpoint_binding","failed",1,lookup=lambda _,s,r:lookup("rank_symbols",s,r))
    def bad_ref(name,s,r):
        raw = lookup(name,s,r)
        raw["claims"][0]["evidence_blocks"][0]["url"] += "#unissued"
        return raw
    check("unissued_reference","invalid_reference","failed",1,lookup=bad_ref)
    def changed_head(name,s,r):
        raw = lookup(name,s,r)
        set_head(root,"1de73ad")
        return raw
    check("changed_head","stale_snapshot","failed",1,lookup=changed_head)
    set_head(root,base)
    def broken(*args):
        raise RuntimeError("fixture unavailable")
    check("tool_error","tool_error","failed",1,lookup=broken)
    return rows


def run_all(temp):
    plan = json.loads(pilot.git("show","0d1b175:"+DIR+"/transfer.json"))
    base = plan["fixture"]
    prior_file = temp/"accepted_core_02.py"
    prior_file.write_bytes(pilot.git("show",base+":tools/skynet_investigate.py"))
    spec = importlib.util.spec_from_file_location("accepted_core_02",prior_file)
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)  # pinned trusted experimental host; never load the five source files
    root = temp/"fixture"
    pilot.git("clone","--quiet","--local","--no-checkout",str(pilot.ROOT),str(root))
    set_head(root,base)
    trials = [(c,DEFS,None) for c in plan["cases"]]
    rng = random.Random(plan["seed"])
    raw,_ = old.blob(root,base,old.RANK)
    assert raw.endswith(b"\n")
    for number,width in enumerate([2]*4+[4]*4+[8]*4+[4,4],1):
        modified,case,defs = challenge(rng,width,number,raw,{13:"reassigned",14:"default"}.get(number))
        trials.append((case,defs,modified))
    branching = json.loads(pilot.git("show","2cb561a:"+DIR+"/branching.json"))
    second_rng = random.Random(branching["seed"])
    for number,width in enumerate([2]*3+[3]*3+[6]*3,1):
        modified,case,defs = challenge(second_rng,width,number,raw,plausible=True)
        trials.append((case,defs,modified))
    rows,timing = [],{}
    for n,(case,defs,modified) in enumerate(trials):
        commit = checkout_fixture(root,base,modified) if modified else base
        row,ms = evaluate(case,root,commit,defs,prior,n)
        rows.append(row)
        timing[case["id"]] = ms
    return rows,timing,refusal_controls(root,base,plan["cases"][0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record","verify"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="skynet-argflow-") as temp:
        rows,timing,controls = run_all(Path(temp))
    dest = pilot.ROOT/DIR/"results.json"
    first = [{k:v for k,v in r.items() if k != "greedy"} for r in rows[:23]]
    assert json.loads(dest.read_text(encoding="utf8"))["rows"] == first
    extra = dict(greedy_first={r["id"]:r["greedy"] for r in rows[:23]},branching=rows[23:])
    supplement = dest.with_name("supplement.json")
    if args.mode == "record":
        pilot.dump(supplement,dict(extra,ms=timing))
    else:
        saved = json.loads(supplement.read_text(encoding="utf8"))
        assert all(saved[k] == v for k,v in extra.items())
    print("Refusal controls:",controls)
    for label,group in (("project",rows[:9]),("generated",rows[9:23]),("plausible",rows[23:])):
        for arm in ("core02","first","all_paths","greedy","core03"):
            print(label,arm,sum(r[arm]["correct"] for r in group),"/",len(group),
                  median(timing[r["id"]][arm] for r in group),"ms")


if __name__ == "__main__":
    main()
