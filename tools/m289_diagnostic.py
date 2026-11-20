"""Replay the fixed M289 protocol. Run with project Python 3.12 -I -S -B."""
from __future__ import annotations
import base64
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

PIN = "e67c9ad013f4fa451046b9c461e8f055db8beaaf"
PLAN = "docs/maintenance/M289_Explain_Code_Diagnostic_Plan.md"
PLAN_BLOB = "4ff52ae1ccd1f544eb0cc9cc8778c2756b0040f0"
PACK = "db2e8be37e2083906d27e06561d60120af97a8ac83cfeb3ec4fb210fd88ba81b"
ARCHIVE = "04d6d0a5d784b33fc8728e61fa63a91bfa3aab994d6d0253f296b4ae5fac1229"
PREFIX = "modules/developer_task_ui/app/"
CS, GS, RK = (PREFIX + n for n in ("context_search.py", "git_source.py", "retrieval/m130_rank.py"))
ROOT = Path(__file__).resolve().parents[1]
PILOT = Path(os.environ["LOCALAPPDATA"]) / "SkynetVS/ModelLab/Runs/m289_preview_ba27865bbfcd41479fb4246bbfe10174"
GOLD = [
    [(CS,47,54)], [(GS,92,108)], [(CS,47,54),(CS,144,154),(RK,110,117)],
    [(RK,117,125)], [(GS,102,108)], [], [(GS,110,114),(CS,81,82),(CS,135,141)],
    [(RK,125,130),(RK,135,138),(CS,153,157)], [(RK,117,125)],
    [(CS,159,169),(RK,131,141)], [(CS,47,54)],
    [(CS,95,99),(CS,117,122),(CS,43,45),(CS,159,162)],
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    with path.open("x", encoding="utf8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd)


def verify_package():
    launcher = Path.home() / "Downloads/SkynetVS_M289_CodeQuestion_Preview.ps1"
    source = launcher.read_text(encoding="utf-8-sig")
    packed = base64.b64decode(re.search(r"\$packed = @'\s*(.*?)\s*'@", source, re.S)[1])
    assert sha(packed) == PACK
    package = PILOT / "package"
    with zipfile.ZipFile(io.BytesIO(packed)) as z:
        assert set(z.namelist()) == {p.name for p in package.iterdir()}
        for n in z.namelist():
            assert (package/n).read_bytes() == z.read(n)
    sys.path.insert(0, str(package))
    return {p.name:sha(p.read_bytes()) for p in sorted(package.iterdir())}


def historical(out):
    raw = (PILOT/"M289_Evidence.zip").read_bytes()
    assert sha(raw) == ARCHIVE
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for n, row in json.loads(z.read("M289_Manifest.json"))["files"].items():
            b = z.read(n)
            assert b == (PILOT/n).read_bytes() and sha(b) == row["sha256"]
        receipt = json.loads(z.read("M289_Run.json"))
        assert receipt["git_commit_expected"] == PIN
        turns = []
        for meta in receipt["turns"]:
            turn = json.loads(z.read(meta["id"]+".json"))
            assert turn["status"] == meta["status"]
            for item in turn["evidence"]:
                r = item["ref"]
                data = git("show", PIN+":"+r["path"])
                assert sha(data) == r["source_sha256"]
                assert item["text"] == b"".join(data.splitlines(True)[r["start"]-1:r["end"]]).decode()
            turns.append(turn)
        dump(out/"D.json",turns)


class Oracle:
    """Issue only frozen genuine source references, without proposing code to M289."""
    def __init__(self, bridge, spans):
        self.bridge = bridge
        self.snapshot = bridge.provider.capture()
        self.items = []
        for path,a,b in spans:
            ref = bridge.core.reference(self.snapshot,path,a,b)
            data = git("show",PIN+":"+path)
            body = b"".join(data.splitlines(True)[a-1:b])
            assert ref["source_sha256"] == sha(data) and ref["excerpt_sha256"] == sha(body)
            assert ref["blob_oid"] == git("rev-parse",PIN+":"+path).decode().strip()
            self.items.append({"ref":ref,"text":body.decode()})

    def retrieve(self, question):
        return {"status":"READY" if self.items else "NO_MATCH","commit":PIN,"evidence":self.items}

    def check(self, ref):
        return (self.bridge.provider.head()==PIN and any(i["ref"]==ref for i in self.items)
                and self.bridge.core.check_reference(self.snapshot,ref))


class Observe:
    def __init__(self, bridge):
        self.bridge = bridge

    def retrieve(self, question):
        self.result = self.bridge.retrieve(question)
        return self.result

    def check(self, ref):
        return self.bridge.check(ref)


def fixtures():
    def proposal(text, anchors):
        obj = {"status":"answer","reason":"","claims":[{"text":text,"anchors":[
            {"ref":ref,"line":line,"quote":quote} for ref,line,quote in anchors]}]}
        return json.dumps(obj,ensure_ascii=False,separators=(",",":"))
    ok = "Строка длиной 1201 символ превышает предел 1200: до расширения вызывающий код получает ValueError M134_GOAL_EMPTY_OR_TOO_LONG."
    a = ("E1",48,"len(goal) > 1200")
    b = ("E1",49,'raise ValueError("M134_GOAL_EMPTY_OR_TOO_LONG")')
    return [(1,proposal(ok,[a,b]),True),(1,proposal(ok,[("E9",48,a[2]),b]),False),
            (1,proposal(ok,[("E1",48,"len(goal) > 1111"),b]),False),
            (4,proposal("Файл будет пропущен.",[("E1",122,"continue")]),False),
            (5,proposal("Последний процесс завершился с кодом ноль.",[("E1",103,'"exit_code": code')]),False)]


def main():
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
    out=Path(sys.argv[1]).resolve()
    out.mkdir(exist_ok=False)
    package = verify_package()
    historical(out)
    import ground289 as g
    import runtime289 as rt
    import retrieval284 as ret
    import run289 as runner
    import cases289
    plan = git("cat-file","blob",PLAN_BLOB)
    assert git("rev-parse","27f0240:"+PLAN).decode().strip()==PLAN_BLOB
    cases=re.findall(r"^\| H(\d+) \| (.*?) \|",plan.decode(),re.M)
    assert [int(n) for n,q in cases]==list(range(1,13))
    fixed=fixtures()
    dump(out/"C_inputs.json",fixed)
    # Fixture tests complete before any H question or inference.
    qa=g.selftest_details()
    assert qa and cases289.fingerprint()=="704a8e5dab1cf056dcbfd6daae9a7ab05cbb2f1441addaae4548ea119ecaae91"
    runner.own_job()
    private=Path(tempfile.mkdtemp(prefix="skynet-m289-diag-"))
    repo=private/"git"
    git("clone","--quiet","--no-local","--no-checkout",str(ROOT),str(repo))
    git("checkout","--quiet","--detach",PIN,cwd=repo)
    bridge=ret.Bridge(repo,private/"tooling")
    all_gold=[Oracle(bridge,spans) for spans in GOLD]
    exe,_=rt.checked_files()
    settings={"pilot_archive":PACK,"evidence_archive":ARCHIVE,"members":package,
              "snapshot":PIN,"plan_blob":PLAN_BLOB,"protocol_sha256":sha(plan),
              "model_sha256":rt.MODEL_SHA256,"runtime_zip":rt.RUNTIME_SHA256,"server_sha256":sha(exe.read_bytes()),
              "provider":"b11960 Vulkan; ctx=4096, seed=289, temperature=0, max_tokens=448, reasoning off",
              "system":g.SYSTEM,"prompt_budget_bytes":3584,"retrieval_budget_bytes":ret.MAX_CONTEXT_BYTES,
              "scan":bridge.provider.capture().scan,"selftest":qa,
              "driver_sha256":sha(Path(__file__).read_bytes()),"H_ids":[n for n,q in cases],
              "gold_refs":[[i["ref"] for i in o.items] for o in all_gold]}
    dump(out/"inputs.json",settings)
    class Fixed:
        def complete(self, system,user):
            return self.value,{"finish_reason":"stop"}
    mock=Fixed()
    control=g.answer(all_gold[0],FixedAnswer(fixed[0][1]),cases[0][1])
    assert control["generated_answer_published"] and all_gold[0].check(all_gold[0].items[0]["ref"])
    assert g.answer(all_gold[5],None,cases[5][1])["model_called"] is False
    sessions={"provider_sessions":[]}
    for arm in ("A","B"):
        with runner.LazyProvider(private,sessions,arm,rt.LocalProvider) as provider:
            for ns,q in cases:
                n=int(ns); basis="live" if n in (5,6) else "static"
                oracle=all_gold[n-1]
                if arm=="B" and (len(oracle.items)>3 or oracle.items and len((g.SYSTEM+g._input(q,oracle.items)).encode())>3584):
                    turn={"question":q,"status":"BLOCKED_BUDGET","model_called":False,"evidence":[],
                          "bytes_required":len((g.SYSTEM+g._input(q,oracle.items)).encode()),"basis":basis}
                else:
                    observer=Observe(bridge if arm=="A" else oracle)
                    turn=g.answer(observer,provider,q,basis=basis)
                    turn["selected_before_prompt"]=observer.result["evidence"]
                    turn["all_candidates"]=observer.result.get("candidates",[])
                    if arm=="A" and bridge.active:
                        view=bridge.active.turns[-1]["selected_view"]
                        turn["top_ref_before_clip"]=view["evidence"] if view else None
                dump(out/(arm+ns+".json"),turn)
                print(arm+ns,turn["status"],flush=True)
    dump(out/"sessions.json",sessions)
    cres=[]
    for j,(n,value,wanted) in enumerate(fixed,1):
        mock.value=value
        t=g.answer(all_gold[n-1],mock,cases[n-1][1],basis="live" if n==5 else "static")
        cres.append({"fixture":j,"expected_publish":wanted,"actual_publish":t["generated_answer_published"],
                     "status":t["status"],"reason":t.get("diagnostic")})
    dump(out/"C_results.json",cres)


class FixedAnswer:
    def __init__(self,value):
        self.value=value

    def complete(self,system,user):
        return self.value,{"finish_reason":"stop"}


if __name__=="__main__":
    main()
