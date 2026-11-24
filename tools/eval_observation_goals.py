"""Matched, read-only evaluation on real and generated Git blobs. Only the selector generates."""
import argparse
import ast
from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import median
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_route_research as previous

loop, archive, old, pilot = previous.loop, previous.archive, previous.old, previous.pilot
BASE = "fb30428c94b3d477dde9b5e081435a1669822aad"
DIR = pilot.ROOT/"docs/maintenance/core_07"
ARMS = ("core06","lexical","model","hybrid")


def fixture(raw, seed):
    rng = random.Random(int(seed[:16],16))
    sink, caller, other = ["node_" + format(rng.getrandbits(50),"x") for _ in range(3)]
    threshold = rng.randint(11,40)
    lines = ["",f"def {sink}(units):",f"    if units < {threshold}:",
             "        raise ValueError('Запас комплектующих ниже порога')",
             "    return 'Заказ передан на упаковку'", "",f"def {caller}():",
             f"    return {sink}({threshold+1})", "",f"def {other}(closed):",
             "    if closed:", "        return 'Заказ передан на хранение'",
             "    return 'Запас комплектующих ниже порога'"]
    return raw+("\n".join(lines)+"\n").encode(), dict(sink=sink,caller=caller,other=other,
               base=len(raw.splitlines()),threshold=threshold)


class Generations:
    def __init__(self,temp,cache,live):
        self.temp,self.cache,self.live = temp,cache,live
        self.provider = None
        self.stack = ExitStack()
        self.sessions = []
        self.key = ""
        self.used = 0

    def prepare(self):
        if not self.live or (self.provider and self.provider.calls<16):
            return
        self.stack.close()
        import runtime289
        profile = self.temp/("model-"+str(len(self.sessions)))
        profile.mkdir()
        self.provider = self.stack.enter_context(runtime289.LocalProvider(profile))
        self.sessions.append(dict(startup_s=self.provider.info["startup_seconds"],
                        model_sha256=runtime289.MODEL_SHA256,runtime_sha256=runtime289.RUNTIME_SHA256))

    def select(self,system,user):
        self.used+=1
        assert self.used==1
        digest = sha256(json.dumps([system,user],ensure_ascii=False).encode()).hexdigest()
        if self.live:
            raw,timing = self.provider.complete(system,user)
            self.cache[self.key]=dict(digest=digest,raw=raw,**timing)
        entry=self.cache[self.key]
        assert entry["digest"]==digest
        return entry["raw"],entry


def expected(case,info):
    if not case["id"].startswith("G") or "owner" not in case:
        return case
    c = dict(case, owner=info[case["owner"]],line=case["line"]+info["base"])
    c["refs"]=[n+info["base"] for n in case["refs"]]
    if "caller" in c:
        c["caller"]=info[c["caller"]]
    c["controls"] = [[info[fn],line+info["base"],(term if type(term) is bool else
                     (abs(term)+info["base"])*(1 if term>0 else -1))] for fn,line,term in case.get("controls",[])]
    return c


def grade(c,answer,root,src):
    refs = [r for claim in answer["claims"] for r in claim["refs"]]
    old.verify_refs(root,src.commit,refs)
    meta = answer.get("discovery",{})
    text = "\n".join(cl["text"] for cl in answer["claims"])
    if "reasons" in c:
        good = not refs and answer.get("reason") in c["reasons"]
        return dict(full=good,target=None,spurious=bool(refs),checks=[],cited=len(refs))
    path = previous.PATHS[c["path"]]
    functions = {fn.name:fn for source in src.snapshot.sources.values()
                 for fn in ast.parse(source).body if isinstance(fn,ast.FunctionDef)}
    cited = lambda n:any(r["path"]==path and r["start"]<=n<=r["end"] for r in refs)
    target = (cited(c["line"]) and c["owner"] in text and (meta.get("owner",c["owner"])==c["owner"])
              and meta.get("line",c["line"])==c["line"])
    checks = [target,all(cited(n) for n in c["refs"])]
    for code,lines in c.get("other_refs",{}).items():
        checks.append(all(any(r["path"]==previous.PATHS[code] and r["start"]<=line<=r["end"] for r in refs)
                          for line in lines))
    if "binding" in c:
        checks.append(c["binding"] in text)
    for name,line,term in c.get("controls",[]):
        terms=[]
        for cl in answer["claims"]:
            if cl["text"].startswith(f"В {name} исследована инструкция ") and f"(стр. {line}). " in cl["text"]:
                terms.append(previous.controls.displayed(cl["text"],functions[name],line))
        checks.append(any(previous.controls.truth_signature(previous.controls.normalize(t))
                          ==previous.controls.truth_signature(previous.controls.normalize(term)) for t in terms))
    if c.get("caller"):
        source = c["caller"]
        checks.append(any(cl.get("edge")==[source,c["owner"]] for cl in answer["claims"]))
    if "verdict" in c:
        checks.append(meta.get("verdict")==c["verdict"])
    supported = answer["state"]=="answered" or (answer["state"]=="partial" and c.get("verdict")=="excluded_route")
    return dict(full=bool(supported and all(checks)),target=bool(target),
                spurious=bool(refs and not target),checks=checks,cited=len(refs))


def portable(out):
    public=dict(out)
    public["claims"]=[{**c,"refs":[[next(k for k,p in previous.PATHS.items() if p==r["path"]),
                         r["start"],r["end"]] for r in c["refs"]]} for c in out["claims"]]
    return json.loads(json.dumps(public))


def run(temp,plan,calls,live):
    root = temp/"repo"
    pilot.git("clone","--quiet","--local","--no-checkout",str(pilot.ROOT),str(root))
    archive.set_head(root,BASE)
    prior=archive.pinned_host(temp,"accepted_core06",BASE)
    raw,_=old.blob(root,BASE,old.RANK)
    generated,info=fixture(raw,plan["implementation"])
    src,ground=loop.read_head(root)
    provider=Generations(temp,calls,live)
    rows,ms=[],{}
    try:
        for i,case in enumerate(plan["cases"]):
            if case["id"].startswith("G") and src.commit==BASE:
                archive.prior_eval.checkout_fixture(root,BASE,generated)
                src,ground=loop.read_head(root)
            c=expected(case,info)
            row=dict(id=c["id"],q=c["q"],commit=src.commit)
            ms[c["id"]]={}
            for arm in ARMS[i%4:]+ARMS[:i%4]:
                provider.key=c["id"]+"/"+arm
                provider.used=0
                if arm in ("model","hybrid"):
                    provider.prepare()
                opts=dict(opener=lambda _:(src,ground))
                start=perf_counter()
                if arm=="core06":
                    out=prior.investigate(c["q"],root,**opts)
                else:
                    out=loop.investigate(c["q"],root,discovery=arm,select=provider.select,**opts)
                ms[c["id"]][arm]=round((perf_counter()-start)*1000,1)
                assert len(out["steps"])<=6 and not any(s["tool"]=="classify_intent" for s in out["steps"])
                row[arm]=dict(**grade(c,out,root,src),calls=provider.used,answer=portable(out))
            rows.append(row)
    finally:
        provider.stack.close()
    archive.set_head(root,BASE)
    src,ground=loop.read_head(root)
    opts=dict(opener=lambda _:(src,ground),discovery="hybrid")
    q='Когда появляется «Контекст не собран»?'
    cited=loop.host.lab.cli.calls.cited
    with patch.object(loop.host.lab.cli.calls,"cited",lambda *args:dict(cited(*args),url="unissued")):
        bad=loop.investigate(q,root,**opts)
        assert bad.get("reason")=="invalid_reference" and not bad["claims"]
    def switch(*args):
        archive.set_head(root,BASE+"^")
        return '{"id":1,"action":"where"}',dict(finish_reason="stop")
    stale=loop.investigate("Где сообщение?",root,select=switch,**opts)
    assert stale.get("reason")=="stale_snapshot" and not stale["claims"]
    archive.set_head(root,BASE)
    limited=loop.investigate(q,root,steps=1,**opts)
    assert limited.get("reason")=="step_budget" and not limited["claims"]
    return rows,ms,provider.sessions


def historical(root):
    src,_=loop.read_head(root)
    plan=json.loads(pilot.git("show",previous.FROZEN_CASES))
    results=[]
    for c in plan["cases"]:
        if c["id"] in ("T05","T06","T08"):
            r=loop.investigate(c["q"],root,discovery="hybrid")
            g=previous.inspect_answer(c,r,root,src)
            results.append(dict(id=c["id"],full=g["full"],facts=g["facts"],needed=g["needed"],answer=portable(r)))
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("record","verify"))
    args=parser.parse_args()
    live=args.mode=="record"
    plan=json.loads((DIR/"transfer.json").read_text(encoding="utf8"))
    dest=DIR/"results.json"
    saved={} if live else json.loads(dest.read_text(encoding="utf8"))
    calls=saved.get("generations",{})
    with tempfile.TemporaryDirectory(prefix="skynet-goals-") as tmp:
        rows,ms,sessions=run(Path(tmp),plan,calls,live)
        historical_rows=historical(Path(tmp)/"repo")
    if live:
        with dest.open("x",encoding="utf8",newline="\n") as f:
            json.dump(dict(rows=rows,ms=ms,generations=calls,sessions=sessions,historical=historical_rows),
                      f,ensure_ascii=False,indent=1)
            f.write("\n")
    else:
        assert (rows,historical_rows)==(saved["rows"],saved["historical"])
    for arm in ARMS:
        print(arm,"full",sum(r[arm]["full"] for r in rows),"/",len(rows),
              "wrong target",sum(r[arm]["spurious"] for r in rows),"model selections",sum(r[arm]["calls"] for r in rows),
              "median ms",median(ms[r["id"]][arm] for r in rows))
    print("Historical",[(r["id"],r["full"],r["facts"],r["needed"]) for r in historical_rows],
          "live model calls",len(calls) if live else 0)


if __name__=="__main__":
    main()
