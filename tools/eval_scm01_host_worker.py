from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_ROOT = PROJECT_ROOT / "native" / "scm01_host_worker_v1" / "tests"
EXPECTED_TESTS = 114
TEST_MODULES = (
    "native.scm01_host_worker_v1.tests.test_contract_and_lifecycle",
    "native.scm01_host_worker_v1.tests.test_native_api_source",
    "native.scm01_host_worker_v1.tests.test_owner_and_admission",
    "native.scm01_host_worker_v1.tests.test_source_boundary",
)

_CHILD = r'''
import json
from pathlib import Path
import sys
import unittest
root = Path(sys.argv[1]).resolve()
module = sys.argv[2]
sys.path.insert(0, str(root))
suite = unittest.defaultTestLoader.loadTestsFromName(module)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print("HWA01_TEST_RESULT=" + json.dumps({
    "module": module,
    "tests_run": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "skipped": len(result.skipped),
    "ok": result.wasSuccessful(),
}, ensure_ascii=False, sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() else 1)
'''


def _run_module(module: str) -> dict[str, object]:
    cmd = [
        sys.executable,
        "-I",
        "-S",
        "-B",
        "-X",
        "utf8",
        "-c",
        _CHILD,
        str(PROJECT_ROOT),
        module,
    ]
    completed = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=False,
    )
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    marker = None
    for line in completed.stdout.splitlines():
        if line.startswith("HWA01_TEST_RESULT="):
            marker = json.loads(line.removeprefix("HWA01_TEST_RESULT="))
    if not isinstance(marker, dict):
        return {
            "module": module,
            "tests_run": 0,
            "failures": 0,
            "errors": 1,
            "skipped": 0,
            "ok": False,
            "returncode": completed.returncode,
            "issue": "missing_child_result",
        }
    marker["returncode"] = completed.returncode
    marker["ok"] = bool(marker.get("ok")) and completed.returncode == 0
    return marker


def main() -> int:
    if not TEST_ROOT.is_dir():
        print(json.dumps({"result": "HWA01_TEST_ROOT_MISSING", "path": str(TEST_ROOT)}, ensure_ascii=False, sort_keys=True))
        return 1

    results = [_run_module(module) for module in TEST_MODULES]
    tests_run = sum(int(item.get("tests_run", 0)) for item in results)
    failures = sum(int(item.get("failures", 0)) for item in results)
    errors = sum(int(item.get("errors", 0)) for item in results)
    skipped = sum(int(item.get("skipped", 0)) for item in results)
    ok = (
        all(item.get("ok") is True for item in results)
        and tests_run == EXPECTED_TESTS
        and failures == 0
        and errors == 0
        and skipped == 0
    )
    summary = {
        "kind": "SCM01_HOST_WORKER_SOURCE_EVAL_V1",
        "test_processes": len(TEST_MODULES),
        "tests_run": tests_run,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "expected_tests": EXPECTED_TESTS,
        "native_execution_authorized": False,
        "modules": results,
        "result": "PASS" if ok else "FAIL",
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
