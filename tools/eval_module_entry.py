"""Paired checks for the frozen module-entry rubric. Analyzed Python is only parsed."""
import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_expanded_reader as previous
from test_flow_reader import fixture

lab, pilot = previous.lab, previous.pilot
DIR = "docs/maintenance/module_entry_reader"
LOCK = "1eb40d95690644ec4b0ba978c3b4e970e70c990e"


def old_analyzer(commit, path):
    # Only the accepted analyzer tool is loaded. No module from either source profile is imported.
    path.write_bytes(pilot.git("show", commit + ":tools/skynet_call_sites.py"))
    spec = importlib.util.spec_from_file_location("archived_call_analyzer", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sites_in(source):
    return {(n.lineno,n.col_offset,n.end_lineno,n.end_col_offset):ast.get_source_segment(source,n)
            for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)}


def synthetic(plan):
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        old = old_analyzer(plan["baseline"], Path(tmp) / "analyzer.py")
        for name, layout, body, expected in plan["cases"]:
            b = "modules/p/b.py"
            files = {b:body}
            if layout == "alias":
                files[b] = plan["alias"] + body
                files["modules/p/a.py"] = plan["definition"]
            calls = sites_in(files[b])
            row = dict(id=name, expected=expected)
            for label, analyzer in (("before", old), ("after", lab.cli.calls)):
                evidence = {}
                answer = analyzer.lookup(plan["target"], fixture(files), lab.cli.refusal, evidence=evidence)
                result = []
                for site, i in sorted(evidence.items()):
                    assert site.path == b
                    loc = (site.line, site.column, site.end_line, site.end_column)
                    c = answer["claims"][i]
                    kind = c["call_site"]["kind"] if label == "after" else "function"
                    result.append(dict(site=kind + ":" + calls[loc], coordinates=loc, text=c["text"]))
                row[label] = result
                assert len(result) == len(answer["claims"])
                if label == "after":
                    assert sorted(expected) == sorted(r["site"] for r in result), name
                    assert answer["call_coverage"]["project_exhaustive"] is False
            cases.append(row)
    return cases


def real(plan):
    core, launch, ground = lab.trusted_tools()
    reports = []
    for profile in ("three", "five"):
        src = lab.snapshot(core, launch, baseline=profile == "three")
        for case in plan["real"]:
            a = lab.ask(case["mode"], case["q"], src, ground)
            with redirect_stdout(io.StringIO()) as out:
                lab.display(a)
            previous.verify_output(a, out.getvalue(), src.commit, src.raw)
            got = []
            for c in a["claims"]:
                s = c.get("call_site")
                if s is None:
                    continue
                path, line = s["path"], s["line"]
                pos = (line,s["column"],s["end_line"],s["end_column"])
                assert pos in sites_in(src.snapshot.sources[path])
                assert s["commit"] == src.commit
                refs = c["evidence_blocks"]
                for file,n in ((path,line),(path,s["context_line"]),(s["definition_path"],s["definition_line"])):
                    assert any(r["path"] == file and r["start"] <= n <= r["end"] for r in refs)
                got.append(f"{Path(path).name}:{line}:{s['kind']}")
            if profile == "five" or case["id"] == "R1":
                assert sorted(got) == sorted(case["sites"])
                assert a["call_coverage"] == lab.cli.calls.coverage(src.pages)
                assert all(f in out.getvalue() for f in case["facts"])
                assert len(a.get("relations", [])) == case.get("joins", 0)
            else:
                assert a["status"] == "withheld" and not got
            reports.append(dict(profile=profile,id=case["id"],question=case["q"],sites=got,
                                answer=a,console=out.getvalue()))
    return reports


def main():
    if sys.argv[1:] not in (["record"], ["verify"]):
        sys.exit("Expected record or verify")
    plan = json.loads(pilot.git("show", LOCK + ":" + DIR + "/questions.json"))
    assert lab.SOURCE == plan["source"]
    results = dict(lock=LOCK, source=lab.SOURCE, generations=0, synthetic=synthetic(plan), real=real(plan))
    path = pilot.ROOT / DIR / "results.json"
    if sys.argv[1] == "record":
        pilot.dump(path, results)
    else:
        assert json.loads(path.read_text(encoding="utf8")) == json.loads(json.dumps(results))
    print("10 frozen AST cases and 6 real question/profile pairs verified.")


if __name__ == "__main__":
    main()
