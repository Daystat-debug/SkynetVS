from __future__ import annotations

import json
import os
import tempfile

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_backend_host import (
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_runtime_composition import (
    ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED,
    attest_developer_task_execution_runtime_composition,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_SOURCE_FILE_NAME,
    RUNTIME_SOURCE_SHA256,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)


def _runtime_zip_path() -> Path:
    explicit = os.environ.get("SKYNETVS_TRUSTED_RUNTIME_ZIP", "").strip()
    if explicit:
        return Path(explicit)
    return (
        Path.home()
        / "Downloads"
        / "SkynetVS_V1B4A_Runtime_Source_3_13_15"
        / RUNTIME_SOURCE_FILE_NAME
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
        print(
            json.dumps(
                {"actual": actual, "expected": expected, "ok": ok},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    if os.name != "nt":
        check("V1B4C2B ACTIVE TRUSTED RUNTIME REQUIRES WINDOWS", os.name, "nt")
        print()
        print("=== SUMMARY ===")
        print(
            json.dumps(
                {"case_count": case_count, "fail_count": fail_count},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    runtime_zip = _runtime_zip_path()
    host = inspect_developer_task_execution_backend_host()
    runtime_exists = runtime_zip.is_file()
    check(
        "HOST AND PINNED RUNTIME SOURCE ARE READY BEFORE V1B4C2B",
        {
            "host_ok": host.ok,
            "issue_codes": list(host.issue_codes),
            "running_processes": list(host.running_sandbox_processes),
            "runtime_path": str(runtime_zip),
            "runtime_name": runtime_zip.name,
            "runtime_exists": runtime_exists,
            "execution_authorized": host.to_dict()["execution_authorized"],
        },
        {
            "host_ok": True,
            "issue_codes": [],
            "running_processes": [],
            "runtime_path": str(runtime_zip),
            "runtime_name": RUNTIME_SOURCE_FILE_NAME,
            "runtime_exists": True,
            "execution_authorized": False,
        },
    )
    if not host.ok or not runtime_exists or runtime_zip.name != RUNTIME_SOURCE_FILE_NAME:
        print()
        print("=== SUMMARY ===")
        print(
            json.dumps(
                {"case_count": case_count, "fail_count": fail_count},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    with tempfile.TemporaryDirectory(
        prefix="skynetvs-v1b4c2b-active-parent-",
        ignore_cleanup_errors=True,
    ) as temporary:
        report = attest_developer_task_execution_runtime_composition(
            host,
            runtime_zip,
            artifact_parent=Path(temporary),
        )
        check(
            "ACTIVE V1B4C2B TRUSTED RUNTIME COMPOSITION PASSES",
            {
                "ok": report.ok,
                "status": report.status,
                "issue_codes": list(report.issue_codes),
                "runtime_source_sha256": (
                    report.artifacts.runtime_source_sha256
                    if report.artifacts is not None
                    else ""
                ),
                "runtime_bundle_fingerprint": report.runtime_bundle_fingerprint,
                "runtime_attestation_policy_fingerprint": (
                    report.runtime_attestation_policy.fingerprint
                ),
                "payload_bundle_fingerprint": report.payload_bundle_fingerprint,
                "pin_ok": bool(report.pin_report and report.pin_report.ok),
                "signed_report_ok": bool(
                    report.signed_report and report.signed_report.ok
                ),
                "signature_valid": bool(
                    report.signed_report and report.signed_report.signature_valid
                ),
                "runtime_result_verified": bool(
                    report.signed_report
                    and report.signed_report.runtime_result_verified
                ),
                "terminal_verified": bool(
                    report.signed_report and report.signed_report.terminal_verified
                ),
                "process_observed": report.process_observed,
                "all_processes_exited": report.all_processes_exited,
                "forced_cleanup_attempted": report.termination.attempted,
                "artifacts_removed": bool(
                    report.artifacts and report.artifacts.removed
                ),
                "interpreter_executed": report.interpreter_executed,
                "reusable_lease_issued": report.reusable_lease_issued,
                "execution_authorized": report.execution_authorized,
            },
            {
                "ok": True,
                "status": ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED,
                "issue_codes": [],
                "runtime_source_sha256": RUNTIME_SOURCE_SHA256,
                "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
                "runtime_attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
                "payload_bundle_fingerprint": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
                "pin_ok": True,
                "signed_report_ok": True,
                "signature_valid": True,
                "runtime_result_verified": True,
                "terminal_verified": True,
                "process_observed": True,
                "all_processes_exited": True,
                "forced_cleanup_attempted": False,
                "artifacts_removed": True,
                "interpreter_executed": True,
                "reusable_lease_issued": False,
                "execution_authorized": False,
            },
        )

    post_host = inspect_developer_task_execution_backend_host()
    check(
        "NO WINDOWS SANDBOX PROCESS REMAINS AFTER V1B4C2B",
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
    print("=== V1B4C2B ACTIVE REPORT ===")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {"case_count": case_count, "fail_count": fail_count},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
