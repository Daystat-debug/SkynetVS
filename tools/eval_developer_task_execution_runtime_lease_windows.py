from __future__ import annotations

import json
import os
import tempfile

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_backend_host import (
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    build_developer_task_execution_runtime_bundle,
)
from modules.developer.developer_task_execution_runtime_lease import (
    DeveloperTaskExecutionRuntimeLeaseError,
    LEASE_STATE_CLAIMED,
    LEASE_STATE_ISSUED,
    issue_developer_task_execution_runtime_lease,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
    RUNTIME_LEASE_TTL_SECONDS,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_SOURCE_FILE_NAME,
    RUNTIME_SOURCE_SHA256,
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
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    if os.name != "nt":
        print("[SKIP] V1B4D runtime capability lease Windows smoke requires Windows.")
        return 0

    runtime_zip = _runtime_zip_path()
    host_before = inspect_developer_task_execution_backend_host()
    runtime_exists = runtime_zip.is_file()
    check(
        "V1B4D REAL HOST AND PINNED RUNTIME SOURCE ARE READY",
        {
            "host_ok": host_before.ok,
            "issue_codes": list(host_before.issue_codes),
            "running_processes": list(host_before.running_sandbox_processes),
            "runtime_name": runtime_zip.name,
            "runtime_exists": runtime_exists,
            "execution_authorized": host_before.to_dict()["execution_authorized"],
        },
        {
            "host_ok": True,
            "issue_codes": [],
            "running_processes": [],
            "runtime_name": RUNTIME_SOURCE_FILE_NAME,
            "runtime_exists": True,
            "execution_authorized": False,
        },
    )
    if not host_before.ok or not runtime_exists or runtime_zip.name != RUNTIME_SOURCE_FILE_NAME:
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
        return 1

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1b4d-windows-") as temporary:
        artifact_parent = Path(temporary)
        bundle = build_developer_task_execution_runtime_bundle(
            runtime_zip,
            artifact_parent=artifact_parent,
        )
        lease = issue_developer_task_execution_runtime_lease(host_before, bundle)
        check(
            "V1B4D REAL LEASE ISSUES AS PROCESS LOCAL NON AUTHORIZING CAPABILITY",
            {
                "state": lease.status().state,
                "policy_fingerprint": lease.status().policy_fingerprint,
                "ttl_seconds": lease.status().ttl_seconds,
                "bundle_ok": bundle.ok,
                "bundle_fingerprint": bundle.report.bundle_fingerprint,
                "source_sha256": bundle.report.source_sha256,
                "staging_cleaned": bundle.report.staging_cleaned,
                "interpreter_executed": bundle.report.interpreter_executed,
                "execution_authorized": lease.execution_authorized,
            },
            {
                "state": LEASE_STATE_ISSUED,
                "policy_fingerprint": RUNTIME_LEASE_POLICY_FINGERPRINT,
                "ttl_seconds": RUNTIME_LEASE_TTL_SECONDS,
                "bundle_ok": True,
                "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
                "source_sha256": RUNTIME_SOURCE_SHA256,
                "staging_cleaned": True,
                "interpreter_executed": False,
                "execution_authorized": False,
            },
        )

        claimed = lease.claim()
        try:
            lease.claim()
        except DeveloperTaskExecutionRuntimeLeaseError as exc:
            replay_code = exc.code
        else:
            replay_code = ""
        check(
            "V1B4D REAL LEASE CLAIM RETURNS EXACT BUNDLE ONCE AND REJECTS REPLAY",
            {
                "same_bundle": claimed is bundle,
                "state": lease.status().state,
                "replay_code": replay_code,
                "execution_authorized": lease.execution_authorized,
            },
            {
                "same_bundle": True,
                "state": LEASE_STATE_CLAIMED,
                "replay_code": "runtime_lease_already_claimed",
                "execution_authorized": False,
            },
        )

        host_after = inspect_developer_task_execution_backend_host()
        check(
            "V1B4D REAL HOST REMAINS SANDBOX FREE AFTER ISSUE AND CLAIM",
            {
                "host_ok": host_after.ok,
                "issue_codes": list(host_after.issue_codes),
                "running_processes": list(host_after.running_sandbox_processes),
                "artifact_parent_empty": list(artifact_parent.iterdir()) == [],
            },
            {
                "host_ok": True,
                "issue_codes": [],
                "running_processes": [],
                "artifact_parent_empty": True,
            },
        )

        check(
            "V1B4D WINDOWS SMOKE EXECUTES NO CANDIDATE INTERPRETER AND GRANTS NO EXECUTION",
            {
                "bundle_interpreter_executed": claimed.report.interpreter_executed,
                "bundle_execution_authorized": claimed.report.execution_authorized,
                "lease_execution_authorized": lease.execution_authorized,
            },
            {
                "bundle_interpreter_executed": False,
                "bundle_execution_authorized": False,
                "lease_execution_authorized": False,
            },
        )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
