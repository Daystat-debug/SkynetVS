"""Probe the fixed object capability and lexical flow analysis with source data only."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_scope_lab as lab
from test_flow_reader import fixture


def refused(f):
    try:
        f()
    except (ValueError, KeyError):
        return
    raise AssertionError("Expected refusal")


def test_objects():
    core, launch, ground = lab.trusted_tools()
    backend = lab.Objects(launch, baseline=True)
    extra = min(lab.SCOPE - lab.BASE)
    path = min(lab.BASE)
    with patch.object(lab.subprocess, "Popen", side_effect=AssertionError("Git started")):
        for name in ("../" + path, "main.py", "*.py", extra, str(lab.cli.pilot.ROOT / path)):
            refused(lambda: backend._run("ls-tree", "-z", "--full-tree", lab.SOURCE, "--", name))
        refused(lambda: backend._run("ls-tree", "-z", "--full-tree", "HEAD", "--", path))
        refused(lambda: backend._run("cat-file", "blob", lab.SOURCE))
        refused(lambda: backend._run("cat-file", "-s", lab.SOURCE))
        refused(lambda: backend._run("show", "HEAD"))
    src = lab.snapshot(core, launch)
    assert set(src.raw) == lab.SCOPE and len(src.raw) == 5
    oid = src.oids[path]
    refused(lambda: src.reader._run("cat-file", "blob", oid, limit=999999))
    refused(lambda: src.span("main.py", 1, 1))
    refused(lambda: src.span(path, 0, 1))
    src.raw[path] += b" "
    refused(lambda: src.span(path, 1, 1))
    assert not any(n == "app" or n.startswith(("app.", "modules.developer_task_ui")) for n in sys.modules)


def test_lexical():
    path = "modules/sample.py"

    def trace(body):
        source = "raise RuntimeError('source was executed')\n" + body
        src = fixture({path: source})
        src.lexical_flows = True
        return lab.cli.flow.Slice(src).answer("items_total", lab.cli.refusal)

    sample = ("def collect(inputs):\n"
              "    def helper(): return {'items_total': 400}\n"
              "    result = []\n"
              "    for x in inputs:\n"
              "        result.append(x)\n"
              "    return {'items_total': len(result)}\n")
    result = trace(sample)
    text = "\n".join(c["text"] for c in result["claims"])
    assert result["status"] == "flow" and "len(result)" in text and "result.append(x)" in text and "400" not in text
    for statement in ("    yield 1", "    def helper(x=(yield 4)): pass", "    for x in inputs: return {}"):
        assert trace(sample.replace("    result = []", statement + "\n    result = []"))["status"] == "withheld"
    assert trace(sample.replace("len(result)", "len(*inputs)"))["status"] == "flow_limited"
    shadow = trace(sample.replace("def collect(inputs):", "def collect(inputs, len):"))
    assert shadow["status"] == "flow_limited"
    other = trace(sample.replace("result.append(x)", "inputs.append(x)"))
    assert not any("пополняется" in c["text"] for c in other["claims"])


if __name__ == "__main__":
    test_objects()
    test_lexical()
    print("Pinned-object scope, checked spans, no source imports and lexical edge cases passed.")
