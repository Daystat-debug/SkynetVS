"""Executable safety probes. Source below is parsed, never imported or executed."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_explain as cli


def fixture(files):
    return SimpleNamespace(pages=dict.fromkeys(files), snapshot=SimpleNamespace(sources=files),
                           current=lambda: None, commit="test",
                           span=lambda p,a,b: {"ref":{"path":p,"start":a,"end":b}})


BASE = "def produce(value):\n    return value\n"
IMPORT = "from .a import produce as get\n"
CALL = "def run():\n    return get(1)\n"


def call_cases():
    return [
        ("explicit_alias", BASE, IMPORT + CALL, True),
        ("same_name_other_module", BASE, "from .other import produce as get\n" + CALL, False),
        ("two_definitions", BASE, BASE + CALL, False),
        ("parameter_shadow", BASE, IMPORT + "def run(get):\n    return get(1)\n", False),
        ("conditional_rebind", BASE, IMPORT + "if flag: get = other\n" + CALL, False),
        ("star_import", BASE, IMPORT + "from .other import *\n" + CALL, False),
        ("qualified_outside_subset", BASE, "from . import a\ndef run(): return a.produce(1)\n", False),
        ("export_reassigned", BASE + "produce = other\n", IMPORT + CALL, False),
        ("decorated_export", "@replace\n" + BASE, IMPORT + CALL, False),
        ("pattern_capture", BASE, IMPORT + "def run(obj):\n    match obj:\n        case [get]: return get(1)\n", False),
        ("other_function_global_write", BASE, IMPORT + "def swap():\n    global get\n    get = other\n" + CALL, False),
    ]


def probe():
    failures = []
    for name, a, b, expected in call_cases():
        src = fixture({"modules/p/a.py":a, "modules/p/b.py":b})
        r = cli.calls.lookup("produce",src,cli.refusal)
        actual = bool(r["claims"])
        print(name, "linked" if actual else "withheld", "OK" if actual == expected else "FALSE_LINK")
        if actual != expected:
            failures.append(name)
    return failures


def flow_tests():
    a = "def sizes():\n    return dict(total=17)\n"
    prefix = "from .a import sizes as collect\ndef build():\n    data = collect()\n"
    after = "    return {'sample_count': data['total']}\n"
    consumer = "def screen(report):\n    return f\"Образцов: {report['sample_count']}\"\n"

    def ask(a_body=a, b_body=prefix + after + consumer):
        src = fixture({"modules/p/a.py":a_body, "modules/p/b.py":b_body})
        r = cli.flow.Slice(src).answer("sample_count", cli.refusal)
        return r, "\n".join(c["text"] for c in r["claims"])

    r,text = ask()
    assert r["status"] == "flow" and "литералом `17`" in text and "Факт передачи не установлен" in text
    assert {ref["path"] for c in r["claims"] for ref in c["evidence_blocks"]} == {"modules/p/a.py","modules/p/b.py"}
    for mid in ("    data['total'] = 44\n", "    other = data\n    other.clear()\n", "    consume(data)\n",
                "    if uncertain: data = replacement\n", "    data.update(other)\n"):
        r,text = ask(b_body=prefix + mid + after)
        assert r["status"] == "flow_limited" and "литералом `17`" not in text
    for source in ("@decorator\n"+a, a+"sizes = replacement\n",
                   "def sizes():\n    return {'total':17, **unknown}\n",
                   "def sizes():\n    return {'total':17,'total':23}\n",
                   "def sizes():\n    return\n"):
        r,text = ask(a_body=source)
        assert r["status"] == "flow_limited" and "литералом `17`" not in text
    # A literal guard is only evidence for its own branch.
    r,text = ask(a_body="def sizes():\n    if flag: return {'total': 5}\n    return {'total': 9}\n")
    assert r["status"] == "flow" and "при `flag`" in text and "литералом `5`" in text and "литералом `9`" in text
    for source in (a+"globals()['sizes'] = other\n",a+"some_module.sizes = other\n"):
        assert not cli.calls.lookup("sizes",fixture({"modules/p/a.py": source,"modules/p/b.py":prefix+after}),cli.refusal)["claims"]
    print("Field projection, branch, binding, mutation and evidence-scope checks passed.")


if __name__ == "__main__":
    failures = probe()
    flow_tests()
    raise SystemExit(bool(failures))
