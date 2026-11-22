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


if __name__ == "__main__":
    raise SystemExit(bool(probe()))
