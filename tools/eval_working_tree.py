"""Run the frozen paired test in a private Git clone. Only this fixture writer edits source."""
import _winapi
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_core_explain as app
import skynet_working_tree as wt

pilot = app.lab.cli.pilot
LOCK = "5d0256a7bdec3b24ce0bc6778b5719d4172f4e70"
DIR = "docs/maintenance/working_tree_reader"


def prepare(root, plan):
    # No checkout, hooks, smudge filters or execution of modules from the fixture.
    pilot.git("clone", "--quiet", "--local", "--no-checkout", str(pilot.ROOT), str(root))
    pilot.git("update-ref", "--no-deref", "HEAD", plan["head"], cwd=root)
    pilot.git("read-tree", "HEAD", cwd=root)
    for p in app.lab.SCOPE:
        target = root / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pilot.git("cat-file","blob","HEAD:"+p,cwd=root))
    edit = plan["edit"]
    target = root / edit["path"]
    raw = target.read_bytes()
    assert raw.count(edit["before"].encode()) == 1
    target.write_bytes(raw.replace(edit["before"].encode(), edit["after"].encode()))
    assert pilot.git("diff","--no-ext-diff","--no-textconv","--name-only","HEAD","--",edit["path"],cwd=root).decode().strip() == edit["path"]
    return target


def measure(host, case):
    result = host.run(host.task(case["q"]))
    assert result["state"] == ("insufficient" if case["id"] == "W3" else "answered"), result.get("reason")
    e = result["evidence_set"]
    local = host.mode == "working-tree"
    snapshot = e["snapshot_id"]
    raw = {p:(host.root / p).read_bytes() if local else pilot.git("cat-file","blob",snapshot+":"+p,cwd=host.root)
           for p in app.lab.SCOPE}
    if local:
        hashes = {p:wt.digest(data) for p,data in raw.items()}
        assert hashes == e["analysis"]["file_hashes"]
        assert snapshot == "wt-sha256-" + wt.digest(json.dumps(hashes,sort_keys=True,separators=(",",":")).encode())
        assert "github.com" not in json.dumps(result) and '"commit":' not in json.dumps(result)
    locators = []
    for item in e["items"]:
        ref = item["locator"]
        p, a, b = ref["path"], ref["start"], ref["end"]
        excerpt = b"".join(raw[p].splitlines(keepends=True)[a-1:b])
        assert raw[p] and excerpt.decode("utf8") == item["text"] and wt.digest(excerpt) == ref["excerpt_sha256"]
        assert wt.digest(raw[p]) == ref["source_sha256"]
        if local:
            assert "blob_oid" not in ref and ref["snapshot_id"] == snapshot
            assert ref["url"] == f"{(host.root/p).as_uri()}#L{a}-L{b}&snapshot={snapshot}"
        else:
            assert ref["url"] == f"https://github.com/Daystat-debug/SkynetVS/blob/{snapshot}/{p}#L{a}-L{b}"
        # A temporary clone ceases to exist. Keep portable coordinates and the measured excerpt.
        locators.append(dict(ref_id=item["ref_id"],path=p,start=a,end=b,excerpt=item["text"],
                             source_sha256=ref["source_sha256"],excerpt_sha256=ref["excerpt_sha256"]))
    draft = result["answer_proposal"]
    analysis = e["analysis"]
    if case["id"] == "W1":
        text = " ".join(c["text"] for c in draft["claims"])
        assert "len(rows)" in text and len(analysis["relations"]) == 1
        assert f"`limit` получает `{37 if local else 100}`" in text
    elif case["id"] == "W2":
        assert any("True" in c["text"] for c in draft["claims"])
    else:
        assert draft["reason"] == "out_of_scope" and not locators
    return dict(id=case["id"],mode=host.mode,snapshot=snapshot,decision=result["state"],proposal=draft,
                relations=analysis["relations"],items=locators)


def safety(root, changed, case):
    host = app.WorkspaceHost("working-tree",root)
    rows = []
    def expect(name, reason, *, provider=app.propose):
        r = host.run(host.task(case["q"]),provider)
        assert (r["state"],r.get("reason")) == ("failed",reason), (name,r["state"],r.get("reason"))
        assert "evidence_set" not in r and "answer_proposal" not in r
        rows.append(dict(case=name,reason=reason,stage=r["stage"]))

    def intervening(fn):
        def provider(req, e):
            fn()
            return app.propose(req,e)
        return provider

    raw = changed.read_bytes()
    old = changed.stat()
    def same_size():
        changed.write_bytes(raw.replace(b"limit=37)",b"limit=38)"))
        os.utime(changed,ns=(old.st_atime_ns,old.st_mtime_ns))
    expect("same_size_time_new_content","working_changed",provider=intervening(same_size))
    changed.write_bytes(raw)
    def replace():
        alternate = root / "replacement.tmp"
        alternate.write_bytes(raw)
        os.replace(alternate,changed)
    expect("same_bytes_new_file","working_changed",provider=intervening(replace))
    other = root / app.lab.cli.pilot.GS
    original = other.read_bytes()
    expect("unquoted_member_changed","working_changed",provider=intervening(lambda:other.write_bytes(original+b"\n")))
    other.write_bytes(original)
    with changed.open("r+b"):
        expect("writer_open_before_capture","working_busy")
    # Attempt a concurrent write during actual reading, while all files are pinned.
    read = wt.read_files
    blocked = []
    def competing(*args):
        try:
            with changed.open("r+b"):
                raise AssertionError("Writer acquired a handle")
        except PermissionError:
            blocked.append(True)
        return read(*args)
    with patch.object(wt,"read_files",competing):
        assert host.run(host.task(case["q"]))["state"] == "answered"
    assert len(blocked) == 2
    rows.append(dict(case="writer_during_capture_and_final_check",reason="write_open_denied_twice"))
    for name in ("../outside.py", "../"+app.lab.cli.pilot.RK, str(other), "*.py", "x.py:stream"):
        try:
            wt.checked_path(root,name)
        except app.Rejected as exc:
            assert str(exc) == "working_path_outside_profile"
        else:
            raise AssertionError(name)
    rows.append(dict(case="five_path_escapes",reason="working_path_outside_profile"))

    link = root.parent / "linked.tmp"
    os.link(changed,link)
    try:
        expect("hardlink","working_file_type")
    finally:
        link.unlink()
    parent = changed.parent
    outside = root.parent / "outside"
    assert parent.is_relative_to(root) and outside.parent == root.parent and not outside.exists()
    parent.rename(outside)
    try:
        _winapi.CreateJunction(str(outside),str(parent))
        try:
            expect("ancestor_junction","working_reparse_point")
        finally:
            parent.rmdir()
    finally:
        outside.rename(parent)
    ask = app.lab.ask
    def forged(*args):
        result = ask(*args)
        result["claims"][0]["evidence_blocks"][0]["url"] = "https://github.com/forged"
        return result
    with patch.object(app.lab,"ask",forged):
        expect("forged_remote_locator","invalid_reference")
    snap = wt.WorkingSources(root)
    before = snap.commit
    same_size()
    newer = host.run(host.task(case["q"]))
    assert snap.raw[app.lab.cli.pilot.RK] == raw and newer["state"] == "answered"
    assert newer["evidence_set"]["snapshot_id"] != before
    assert any("`limit` получает `38`" in c["text"] for c in newer["answer_proposal"]["claims"])
    rows.append(dict(case="new_task_new_snapshot",reason="38_in_new_snapshot_37_in_original"))
    return rows


def main():
    mode, = sys.argv[1:]
    assert mode in ("record","verify")
    plan = json.loads(pilot.git("show",LOCK+":"+DIR+"/questions.json"))
    with tempfile.TemporaryDirectory(prefix="skynet-working-") as temp:
        root = Path(temp) / "repo"
        target = prepare(root,plan)
        rows = [measure(app.WorkspaceHost(m,root),c) for c in plan["cases"] for m in ("git-head","working-tree")]
        assert all(r["snapshot"] == plan["head"] for r in rows if r["mode"] == "git-head")
        controls = safety(root,target,plan["cases"][0])
    result = dict(protocol=LOCK,head=plan["head"],questions=rows,controls=controls,model_generations=0)
    path = pilot.ROOT / DIR / "results.json"
    if mode == "record":
        pilot.dump(path,result)
    else:
        assert result == json.loads(path.read_text(encoding="utf8"))
    print("6 paired answers and",len(controls),"filesystem/publication checks verified")


if __name__ == "__main__":
    main()
