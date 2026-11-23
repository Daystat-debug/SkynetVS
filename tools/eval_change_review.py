"""Review controlled changes in a disposable private clone; journal only case outcomes/counts."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_change_review as review

app = review.app
pilot = app.lab.cli.pilot
DIR = "docs/maintenance/change_review"
LOCK = "9e2c2831e02002c9342885668df35cb4c6ea58cb"


def verify_refs(report, root):
    n = 0
    for row in report["changes"]:
        locs = [(side,row[side]["ref"]) for side in ("before","after") if row[side]]
        for link in row["related"]:
            locs.extend(("after" if row["after"] else "before",r) for r in link["refs"])
        for side,r in locs:
            path,a,b = r["path"],r["start"],r["end"]
            assert path in app.lab.SCOPE
            if side == "before":
                assert r["commit"] == report["head"]
                raw = pilot.git("cat-file","blob",r["commit"]+":"+path,cwd=root)
                assert r["blob_oid"] == pilot.git("rev-parse",r["commit"]+":"+path,cwd=root).decode().strip()
                url = f"https://github.com/Daystat-debug/SkynetVS/blob/{r['commit']}/{path}#L{a}-L{b}"
            else:
                assert r["snapshot_id"] == report["working_tree"]
                raw = (root/path).read_bytes()
                url = f"{(root/path).as_uri()}#L{a}-L{b}&snapshot={r['snapshot_id']}"
            lines = raw.splitlines(keepends=True)
            assert 1 <= a <= b <= len(lines) and r["url"] == url
            assert pilot.sha(raw) == r["source_sha256"] and pilot.sha(b"".join(lines[a-1:b])) == r["excerpt_sha256"]
            n += 1
    return n


def suite(root, plan):
    head = plan["head"]
    pilot.git("clone","--quiet","--local","--no-checkout",str(pilot.ROOT),str(root))
    pilot.git("update-ref","--no-deref","HEAD",head,cwd=root)
    pilot.git("read-tree","HEAD",cwd=root)
    originals = {p:pilot.git("cat-file","blob","HEAD:"+p,cwd=root) for p in app.lab.SCOPE}
    for p,raw in originals.items():
        (root/p).parent.mkdir(parents=True,exist_ok=True)
        (root/p).write_bytes(raw)
    records = []

    def observed(case):
        r = review.review(root)
        assert r["head"] == head and set(r["allowed_files"]) == app.lab.SCOPE
        assert not r["execution_observed"] and not r["project_exhaustive"]
        rows = r["changes"]
        records.append(dict(case=case,changes=len(rows),related=sum(len(x["related"]) for x in rows),
                            checked_references=verify_refs(r,root)))
        return rows

    def change(path, old, new):
        txt = (root/path).read_bytes()
        assert txt.count(old.encode()) == 1
        (root/path).write_bytes(txt.replace(old.encode(),new.encode()))

    def restore(path):
        (root/path).write_bytes(originals[path])

    def failed(case, reason):
        shown = []
        try:
            shown.append(review.review(root))
        except app.Rejected as exc:
            assert str(exc) == reason
        else:
            raise AssertionError(case)
        assert not shown
        records.append(dict(case=case,reason=reason,published=False))

    rk, cs = pilot.RK, pilot.CS
    assert not observed("empty")
    change(rk,"def rank(title,old_sources):","# harmless fixture comment\ndef rank(title,old_sources):")
    comment, = observed("comment")
    assert comment["kind"] == "text" and not comment["related"]
    restore(rk)
    change(rk,"used+b>6_000_000","used+b>=6_000_000")
    change(rk,"title,old_sources,top_n=10","title,old_sources,top_n=4")
    rows = observed("boundary_and_call")
    assert {r["kind"] for r in rows} == {"call","condition"} and len(rows) == 2
    for r in rows:
        assert r["owner"] == ("rank",)
        assert any(l["kind"]=="direct_call" and l["name"]=="search_repository" for l in r["related"])
        assert r["possible_effect"] and r["suggested_check"]
    cond = next(r for r in rows if r["kind"]=="condition")
    assert ">=" in cond["after"]["expression"] and "равенств" in cond["suggested_check"]
    call = next(r for r in rows if r["kind"]=="call")
    assert "top_n=10" in call["before"]["expression"] and "top_n=4" in call["after"]["expression"]
    assert any(l["kind"]=="direct_target" and l["name"]=="rank_title_only" for l in call["related"])
    restore(rk)
    change(cs,'"candidate_functions": base["function_candidates_total"]',
              '"candidate_functions": base["module_candidates_total"]')
    field, = observed("report_field")
    assert field["field"] == "candidate_functions" and "module_candidates_total" in field["after"]["expression"]
    assert any(l["kind"]=="same_key_read" and l["name"]=="format_context" for l in field["related"])
    restore(cs)
    change(rk,"def candidate_id(c):","def replacement_identity(c):")
    rows = observed("added_and_removed")
    assert len(rows)==2 and all(r["kind"]=="function" for r in rows)
    assert {(r["owner"][0],r["before"] is None,r["after"] is None) for r in rows} == {
        ("candidate_id",False,True),("replacement_identity",True,False)}
    assert {r["definition_delta"] for r in rows} == {"added","removed"}
    restore(rk)
    (root/"outside.py").write_bytes(b"raise RuntimeError('must not run')\n")
    assert not observed("outside")
    (root/rk).write_bytes(b"def incomplete(\n")
    failed("invalid","working_invalid_python")
    restore(rk)
    guard = review.WorkingSources.publication_guard
    @contextmanager
    def move_head(src):
        pilot.git("update-ref","--no-deref","HEAD",head+"^",cwd=root)
        with guard(src):
            yield
    with patch.object(review.WorkingSources,"publication_guard",move_head):
        failed("moved_head","review_head_changed")
    pilot.git("update-ref","--no-deref","HEAD",head,cwd=root)
    @contextmanager
    def update_file(src):
        (root/rk).write_bytes(originals[rk]+b"\n")
        with guard(src):
            yield
    with patch.object(review.WorkingSources,"publication_guard",update_file):
        failed("changed_working","working_changed")
    restore(rk)
    assert {r["case"] for r in records} == plan["cases"].keys()
    # Transfer checks: run after code freeze. Duplicate tokens definitions must not produce false links.
    symbols = pilot.PREFIX + "retrieval/m127_symbol.py"
    change(symbols,"len(t) <= 48","len(t) <= 32")
    nested, = observed("transfer_nested_condition")
    assert nested["kind"] == "condition" and nested["owner"] == ("tokens",) and not nested["related"]
    assert "48" in nested["before"]["expression"] and "32" in nested["after"]["expression"]
    restore(symbols)
    change(rk,"function_candidates_total=sym['symbol_candidates']","function_candidates_total=len(functions)")
    constructor, = observed("transfer_constructor_field")
    assert constructor["field"] == "function_candidates_total" and constructor["after"]["expression"] == "len(functions)"
    assert any(l["name"]=="search_repository" and l["kind"]=="direct_call" for l in constructor["related"])
    restore(rk)
    return records


def main():
    mode, = sys.argv[1:]
    assert mode in ("record","verify")
    plan = json.loads(pilot.git("show",LOCK+":"+DIR+"/protocol.json"))
    with tempfile.TemporaryDirectory(prefix="skynet-review-") as temp:
        records = suite(Path(temp)/"repo",plan)
    log = dict(protocol=LOCK,fixture_head=plan["head"],cases=records,
               file_symlink="UNVERIFIED",model_generations=0)
    dest = pilot.ROOT / DIR / "results.json"
    if mode == "record":
        pilot.dump(dest,log)
    else:
        assert json.loads(dest.read_text(encoding="utf8")) == log
    print(len(records),"controlled cases verified; real file symlink UNVERIFIED")


if __name__ == "__main__":
    main()
