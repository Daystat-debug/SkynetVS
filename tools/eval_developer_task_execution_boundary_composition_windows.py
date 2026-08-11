from __future__ import annotations

import json
import os
import tempfile

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_backend_host import (
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_boundary_composition import (
    ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED,
    attest_developer_task_execution_boundary_composition,
)
from modules.developer.developer_task_execution_boundary_worker import (
    build_developer_task_execution_boundary_worker_bundle,
)


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        if not ok:
            fail_count += 1
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    if os.name != "nt":
        check("V1B3D ACTIVE WINDOWS COMPOSITION REQUIRES WINDOWS", os.name, "nt")
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
        return 1

    host = inspect_developer_task_execution_backend_host()
    check(
        "HOST CAPABILITY IS READY BEFORE V1B3D",
        {
            "ok": host.ok,
            "issue_codes": list(host.issue_codes),
            "running_processes": list(host.running_sandbox_processes),
            "execution_authorized": host.to_dict()["execution_authorized"],
        },
        {
            "ok": True,
            "issue_codes": [],
            "running_processes": [],
            "execution_authorized": False,
        },
    )
    if not host.ok:
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
        return 1

    with tempfile.TemporaryDirectory(
        prefix="skynetvs-v1b3d-active-parent-",
        ignore_cleanup_errors=True,
    ) as temporary:
        report = attest_developer_task_execution_boundary_composition(
            host,
            artifact_parent=Path(temporary),
        )
        bundle = build_developer_task_execution_boundary_worker_bundle()
        check(
            "ACTIVE V1B3D SIGNED BOUNDARY COMPOSITION PASSES",
            {
                "ok": report.ok,
                "status": report.status,
                "issue_codes": list(report.issue_codes),
                "worker_bundle_fingerprint": report.worker_bundle_fingerprint,
                "pin_ok": bool(report.pin_report and report.pin_report.ok),
                "signed_report_ok": bool(report.signed_report and report.signed_report.ok),
                "signature_valid": bool(report.signed_report and report.signed_report.signature_valid),
                "process_observed": report.process_observed,
                "all_processes_exited": report.all_processes_exited,
                "forced_cleanup_attempted": report.termination.attempted,
                "artifacts_removed": bool(report.artifacts and report.artifacts.removed),
                "execution_authorized": report.execution_authorized,
            },
            {
                "ok": True,
                "status": ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED,
                "issue_codes": [],
                "worker_bundle_fingerprint": bundle.bundle_fingerprint,
                "pin_ok": True,
                "signed_report_ok": True,
                "signature_valid": True,
                "process_observed": True,
                "all_processes_exited": True,
                "forced_cleanup_attempted": False,
                "artifacts_removed": True,
                "execution_authorized": False,
            },
        )

    post_host = inspect_developer_task_execution_backend_host()
    check(
        "NO WINDOWS SANDBOX PROCESS REMAINS AFTER V1B3D",
        {
            "ok": post_host.ok,
            "issue_codes": list(post_host.issue_codes),
            "running_processes": list(post_host.running_sandbox_processes),
            "execution_authorized": post_host.to_dict()["execution_authorized"],
        },
        {
            "ok": True,
            "issue_codes": [],
            "running_processes": [],
            "execution_authorized": False,
        },
    )

    print()
    print("=== V1B3D ACTIVE REPORT ===")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
