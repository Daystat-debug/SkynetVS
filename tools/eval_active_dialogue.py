"""Frozen dialogue simulator and direct evidence scorer. A test-only disposable Git clone."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
import tempfile
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_task_parts as historical
import skynet_dialogue as dialog

ev = historical.ev
DIR = ev.pilot.ROOT/"docs/maintenance/core_21"
BASELINES = ("joint_plan","learn_roles","desc_mixed","identity_lexical")


def simulate(prompt, user, channel):
    # No repository, object ID, hidden menu, expected evidence or scores enter this function.
    if (not user or prompt["part"] != user["part"] or prompt["axis"] != user["axis"]):
        return "не знаю"
    if channel == "free":
        return user["reply"]
    mark = user.get("visible")
    hits = [i for i,v in enumerate(prompt["options"]) if mark and mark.casefold() in v.casefold()]
    return "#"+str(hits[0]+1) if len(hits)==1 else "ни один"


def baseline(raw):
    parts = []
    for p in raw.get("parts",[]):
        obj = p["binding"]["object"]
        direct = p.get("relation",{}).get("direct",[])
        parts.append(dict(object=obj, kind=p.get("relation",{}).get("kind"),
                          claims=[raw["claims"][j] for j in p["claims"]],
                          direct=[raw["claims"][j] for j in direct], issues=p["issues"]))
    return dict(state=raw["state"],parts=parts,steps=len(raw["steps"]),snapshot=raw.get("snapshot"))


def grade(answer, case, targets, src, root, offset):
    facts, wrong, wrong_kind = [], [], []
    refs = [r for p in answer["parts"] for c in p["claims"] for r in c["refs"]]
    ev.old.verify_refs(root,src.commit,refs)
    for i, (name,kind) in enumerate(case["needs"]):
        p = answer["parts"][i] if i < len(answer["parts"]) else {}
        obj = p.get("object") or {}
        if name is None:
            if p.get("direct"):
                wrong.append(i)
            continue
        t = targets[name]
        same = (obj.get("commit"),obj.get("path"),obj.get("owner"),obj.get("line")) == (
            src.commit,ev.previous.PATHS[t[0]],t[1],t[2]+offset)
        if obj and not same:
            wrong.append(i)
        if p.get("direct") and p.get("kind") != kind:
            wrong_kind.append(i)
        if (same and kind != "unavailable" and p.get("kind")==kind and
                historical.fact(p.get("claims",[]),t,"site",src,offset) and
                historical.fact(p.get("direct",[]),t,kind,src,offset)):
            facts.append(i)
    full = len(facts)==len(case["needs"]) and answer["state"]=="answered" and not wrong
    return dict(facts=facts,full=full,partial=bool(facts and answer["state"]=="partial" and not wrong and not wrong_kind),
                false_full=answer["state"]=="answered" and not full,wrong=wrong,wrong_kind=wrong_kind,
                state=answer["state"],steps=answer["steps"],refs=len(refs))


def run(panel):
    timings, rows, logs = {}, [], []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)/"repo"
        ev.pilot.git("clone","--quiet","--local","--no-checkout",str(ev.pilot.ROOT),str(root))
        base = panel["base"]
        raw,_ = ev.old.blob(root,base,ev.old.RANK)
        for group in panel["groups"]:
            offset = 0
            if group["source"]:
                offset = len(raw.splitlines())
                ev.archive.prior_eval.checkout_fixture(root,base,raw+("\n".join(group["source"])+"\n").encode())
            else:
                ev.archive.set_head(root,base)
            src,ground = ev.loop.read_head(root)
            for case in group["cases"]:
                key, q = case["id"],case["question"]
                row = dict(id=key)
                log = dict(id=key,question=q,snapshot=src.commit)
                times = timings[key] = {}
                def timed(arm, f):
                    t = perf_counter()
                    result = f()
                    times[arm] = round(1000*(perf_counter()-t),2)
                    return result
                def score(out):
                    return grade(out,case,group["targets"],src,root,offset)
                for arm in BASELINES:
                    # All arms open and verify the scoped Git HEAD themselves.
                    out = timed(arm,lambda:baseline(ev.loop.investigate(q,root,discovery=arm)))
                    row[arm],log[arm] = score(out),out
                for style in ("contrast","list"):
                    for channel in ("free","choice"):
                        arm = style+"_"+channel
                        session = dialog.Dialogue(root,style)
                        (first,prompt) = timed(arm+"_start", lambda:session.start(q))
                        initial = score(first)
                        if style=="contrast" and channel=="free":
                            row["autonomous"],log["autonomous"] = initial,first
                        assert initial == row["autonomous"]
                        answer, reason, extra, reply = first,None,0,None
                        shown_ok = pool_ok = None
                        if prompt:
                            reply = simulate(prompt,case.get("user"),channel)
                            name = case["needs"][prompt["part"]][0]
                            if name and prompt["axis"]=="object":
                                target = group["targets"][name]
                                coord = target[1], ev.previous.PATHS[target[0]], target[2]+offset
                                def covered(ids):
                                    return any(session.cards[j][1:]==coord for j in ids)
                                pool_ok = covered(session.pending["pool"])
                                shown_ok = covered(session.pending["shown"])
                            answer,reason,extra = timed(arm+"_reply",lambda:session.resume(reply))
                        post = score(answer)
                        assert initial["steps"]<=6 and extra<=6
                        gaps = [p["gap"] for p in first["parts"]]
                        row[arm] = dict(**post, initial_gaps=gaps, gap_exact=gaps==case["gaps"],
                            asked=bool(prompt), targeted=bool(prompt and case.get("user") and
                            (prompt["part"],prompt["axis"])==(case["user"]["part"],case["user"]["axis"])),
                            unnecessary=bool(prompt and not case.get("user")), options=len(prompt["options"]) if prompt else 0,
                            shown_chars=len(prompt["prompt"])+sum(map(len,prompt["options"])) if prompt else 0,
                            retained=set(initial["facts"]).issubset(post["facts"]), pool=pool_ok, shown=shown_ok,
                            changed=post["facts"]!=initial["facts"],total_steps=initial["steps"]+extra,reason=reason)
                        hypotheses = [session.cards[j] for j in session.pending.get("pool",[])] if prompt else []
                        log[arm] = dict(prompt=prompt,hypotheses=hypotheses,reply=reply,result=answer,reason=reason)
                rows.append(row)
                logs.append(log)
    return rows,logs,timings


def dump(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode",choices=("record","verify"))
    args = parser.parse_args()
    panel = json.loads((DIR/"final.json").read_text(encoding="utf8"))
    rows,logs,times = run(panel)
    bundles = {"scores.jsonl":b"".join(dump(r)+b"\n" for r in rows),
               "dialogues.json.gz":gzip.compress(dump(logs),mtime=0)}
    for path, data in bundles.items():
        if args.mode=="record":
            (DIR/path).write_bytes(data)
        else:
            saved = (DIR/path).read_bytes()
            assert (gzip.decompress(saved)==gzip.decompress(data) if path.endswith(".gz") else saved==data),path
    if args.mode=="record":
        (DIR/"latency.json").write_bytes(dump(times)+b"\n")
    for arm in (*BASELINES,"autonomous","list_choice","contrast_choice","list_free","contrast_free"):
        stats = Counter()
        for row in rows:
            s = row[arm]
            stats.update({k:int(s.get(k,0)) for k in ("full","partial","false_full","asked","targeted","unnecessary","options")})
            stats.update(facts=len(s["facts"]),wrong=len(s["wrong"]),steps=s.get("total_steps",s["steps"]))
        print(arm, dict(stats))


if __name__ == "__main__":
    main()
