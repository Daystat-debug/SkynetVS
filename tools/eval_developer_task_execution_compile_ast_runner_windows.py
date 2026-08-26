from __future__ import annotations

import json
import ntpath

from modules.developer.developer_task_execution_compile_ast_runner import (
    build_developer_task_execution_compile_ast_runner_bundle,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
)


def main() -> int:
    bundle = build_developer_task_execution_compile_ast_runner_bundle()
    launch = bundle.to_dict()["launch"]
    actual = {
        "ok": bundle.ok,
        "policy_fingerprint": bundle.policy_fingerprint,
        "bundle_fingerprint": bundle.bundle_fingerprint,
        "contract_policy_sha256": bundle.contract_policy.sha256,
        "runner_sha256": bundle.runner.sha256,
        "payload_sha256": bundle.payload_manifest.sha256,
        "runtime_executable": launch["runtime_executable"],
        "runtime_flags": launch["runtime_flags"],
        "runner_path": launch["runner_path"],
        "working_directory": launch["working_directory"],
        "runner_basename": ntpath.basename(launch["runner_path"]),
        "runtime_basename": ntpath.basename(launch["runtime_executable"]),
        "contract_policy_size_bytes": bundle.contract_policy.size_bytes,
        "runner_size_bytes": bundle.runner.size_bytes,
        "payload_size_bytes": bundle.payload_manifest.size_bytes,
        "sandbox_launched": bundle.sandbox_launched,
        "runtime_lease_issued": bundle.runtime_lease_issued,
        "runtime_lease_claimed": bundle.runtime_lease_claimed,
        "candidate_interpreter_executed": bundle.candidate_interpreter_executed,
        "changed_source_processed": bundle.changed_source_processed,
        "changed_source_ast_parsed": bundle.changed_source_ast_parsed,
        "changed_source_compiled": bundle.changed_source_compiled,
        "changed_code_executed": bundle.changed_code_executed,
        "reusable_lease_issued": bundle.reusable_lease_issued,
        "execution_authorized": bundle.execution_authorized,
    }
    expected = {
        "ok": True,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        "bundle_fingerprint": "9179cf51614dc3c43dc4189d5dc2835cb4ed3ba781811dbe0050cea4470ee9bf",
        "contract_policy_sha256": "f280f9c564dd1cfd780cd5465a3ecd98244e0f00f10827a295b3709b2d8b0ed2",
        "runner_sha256": "6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9",
        "payload_sha256": "501ed90023f8f8afc75c7676a8acba3d1497334e398f929d0a8d1d96b9ee9249",
        "runtime_executable": r"C:\SkynetVSRuntime\python.exe",
        "runtime_flags": ["-I", "-S", "-B", "-E", "-s", "-P", "-X", "utf8"],
        "runner_path": r"C:\SkynetVSInput\SkynetVS_V1C2A2_runner.py",
        "working_directory": r"C:\SkynetVSOutput",
        "runner_basename": "SkynetVS_V1C2A2_runner.py",
        "runtime_basename": "python.exe",
        "contract_policy_size_bytes": 3033,
        "runner_size_bytes": 19456,
        "payload_size_bytes": 1045,
        "sandbox_launched": False,
        "runtime_lease_issued": False,
        "runtime_lease_claimed": False,
        "candidate_interpreter_executed": False,
        "changed_source_processed": False,
        "changed_source_ast_parsed": False,
        "changed_source_compiled": False,
        "changed_code_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    ok = actual == expected
    print("=== V1C2A2 REAL WINDOWS FIXED COMPILE AST RUNNER BUNDLE ===")
    print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
    print(f"[{'OK' if ok else 'FAIL'}] V1C2A2 REAL WINDOWS FIXED COMPILE AST RUNNER BUNDLE")
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": 1, "fail_count": 0 if ok else 1}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
