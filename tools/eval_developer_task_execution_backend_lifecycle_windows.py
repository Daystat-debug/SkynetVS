from __future__ import annotations

import json
import os
import sys
import tempfile

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_backend_host import (
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_backend_lifecycle import (
    LIFECYCLE_STATUS_ATTESTED,
    attest_developer_task_execution_backend_lifecycle,
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
        print(json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    if sys.platform != "win32" or os.name != "nt":
        check(
            "WINDOWS SANDBOX LIFECYCLE SMOKE REQUIRES WINDOWS",
            {"platform": sys.platform, "os_name": os.name},
            {"platform": "win32", "os_name": "nt"},
        )
    else:
        host = inspect_developer_task_execution_backend_host()
        check(
            "HOST CAPABILITY IS READY BEFORE ACTIVE LIFECYCLE",
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

        if host.ok:
            with tempfile.TemporaryDirectory(
                prefix="skynetvs-lifecycle-parent-",
            ) as temp_dir:
                report = attest_developer_task_execution_backend_lifecycle(
                    host,
                    artifact_parent=Path(temp_dir),
                )

            process_names = sorted({
                process.name
                for snapshot in report.process_timeline
                for process in snapshot.processes
            })
            shutdown_duration_ms = (
                report.all_processes_exited_ms - report.result_received_ms
                if report.all_processes_exited_ms is not None
                and report.result_received_ms is not None
                else None
            )
            check(
                "TRADITIONAL WSB TRUSTED LIFECYCLE IS ACTIVELY ATTESTED",
                {
                    "ok": report.ok,
                    "status": report.status,
                    "issue_codes": list(report.issue_codes),
                    "backend_id": report.backend_id,
                    "policy_fingerprint": report.policy_fingerprint,
                    "launcher_pid_positive": report.launcher_pid > 0,
                    "process_observed": report.process_observed,
                    "all_processes_exited": report.all_processes_exited,
                    "launcher_process_seen": "WindowsSandbox.exe" in process_names,
                    "remote_session_seen": "WindowsSandboxRemoteSession.exe" in process_names,
                    "only_known_processes": set(process_names).issubset({
                        "WindowsSandbox.exe",
                        "WindowsSandboxClient.exe",
                        "WindowsSandboxRemoteSession.exe",
                    }),
                    "guest_ok": (
                        report.guest_evidence.ok
                        if report.guest_evidence is not None
                        else False
                    ),
                    "ipv4_isolated": (
                        not report.guest_evidence.ipv4_default_route_present
                        and not report.guest_evidence.ipv4_external_tcp_reachable
                        if report.guest_evidence is not None
                        else False
                    ),
                    "ipv6_isolated": (
                        not report.guest_evidence.ipv6_default_route_present
                        and not report.guest_evidence.ipv6_external_tcp_reachable
                        if report.guest_evidence is not None
                        else False
                    ),
                    "forced_cleanup_attempted": report.forced_cleanup_attempted,
                    "artifacts_removed": (
                        report.artifacts.removed
                        if report.artifacts is not None
                        else False
                    ),
                    "result_received_ms": report.result_received_ms,
                    "shutdown_duration_ms": shutdown_duration_ms,
                    "execution_authorized": report.to_dict()["execution_authorized"],
                },
                {
                    "ok": True,
                    "status": LIFECYCLE_STATUS_ATTESTED,
                    "issue_codes": [],
                    "backend_id": "traditional_wsb_logoncommand_v1",
                    "policy_fingerprint": "5c731d5f246929aa1b59f614d2a01371b086244cc09f2c5846d93531b194af21",
                    "launcher_pid_positive": True,
                    "process_observed": True,
                    "all_processes_exited": True,
                    "launcher_process_seen": True,
                    "remote_session_seen": True,
                    "only_known_processes": True,
                    "guest_ok": True,
                    "ipv4_isolated": True,
                    "ipv6_isolated": True,
                    "forced_cleanup_attempted": False,
                    "artifacts_removed": True,
                    "result_received_ms": report.result_received_ms,
                    "shutdown_duration_ms": shutdown_duration_ms,
                    "execution_authorized": False,
                },
            )

            check(
                "ACTIVE LIFECYCLE TIMINGS STAY WITHIN POLICY LIMITS",
                {
                    "result_within_launch_timeout": (
                        report.result_received_ms is not None
                        and report.result_received_ms <= 180_000
                    ),
                    "shutdown_within_grace": (
                        shutdown_duration_ms is not None
                        and 0 <= shutdown_duration_ms <= 30_000
                    ),
                    "total_covers_exit": (
                        report.all_processes_exited_ms is not None
                        and report.total_ms >= report.all_processes_exited_ms
                    ),
                },
                {
                    "result_within_launch_timeout": True,
                    "shutdown_within_grace": True,
                    "total_covers_exit": True,
                },
            )

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {
            "case_count": case_count,
            "fail_count": fail_count,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
