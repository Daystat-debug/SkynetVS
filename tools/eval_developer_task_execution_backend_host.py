from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_backend_host as host_module
import modules.developer.developer_task_execution_backend_policy as policy_module

from modules.developer.developer_task_execution_backend_host import (
    DeveloperTaskExecutionBackendExecutableEvidence,
    DeveloperTaskExecutionBackendHostError,
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
    validate_execution_backend_policy,
)


_VALID_POLICY_FINGERPRINT = (
    "5c731d5f246929aa1b59f614d2a01371b086244cc09f2c5846d93531b194af21"
)


def _executable(
    *,
    version: str = "10.0.26100.8875",
) -> DeveloperTaskExecutionBackendExecutableEvidence:
    return DeveloperTaskExecutionBackendExecutableEvidence(
        path=r"C:\Windows\System32\WindowsSandbox.exe",
        version=version,
        size_bytes=123456,
        mtime_ns=123456789,
        sha256="a" * 64,
    )


def _run_host(
    *,
    platform_name: str = "win32",
    architecture: str = "AMD64",
    windows_build: int = 26200,
    process_bitness: int = 64,
    boot_epoch: int = 1785870000,
    executable: DeveloperTaskExecutionBackendExecutableEvidence | Exception | None = None,
    feature: tuple[str, str] = ("enabled", ""),
    processes: tuple[str, ...] | Exception = (),
    wsb: tuple[bool, str] | Exception = (False, ""),
):
    executable_value = executable if executable is not None else _executable()

    def executable_probe(_policy):
        if isinstance(executable_value, Exception):
            raise executable_value
        return executable_value

    def process_probe():
        if isinstance(processes, Exception):
            raise processes
        return processes

    def wsb_probe():
        if isinstance(wsb, Exception):
            raise wsb
        return wsb

    with (
        patch.object(host_module, "_current_platform", return_value=platform_name),
        patch.object(host_module, "_current_architecture", return_value=architecture),
        patch.object(host_module, "_current_process_bitness", return_value=process_bitness),
        patch.object(host_module, "_current_windows_build", return_value=windows_build),
        patch.object(host_module, "_current_boot_epoch_seconds", return_value=boot_epoch),
        patch.object(host_module, "_inspect_sandbox_executable", side_effect=executable_probe),
        patch.object(host_module, "_probe_optional_feature_state", return_value=feature),
        patch.object(host_module, "_probe_running_sandbox_processes", side_effect=process_probe),
        patch.object(host_module, "_probe_wsb_cli", side_effect=wsb_probe),
    ):
        return inspect_developer_task_execution_backend_host()


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

    policy = WINDOWS_SANDBOX_EXECUTION_POLICY_V1

    check(
        "CANONICAL BACKEND POLICY FINGERPRINT IS STABLE",
        policy.fingerprint,
        _VALID_POLICY_FINGERPRINT,
    )

    check(
        "CANONICAL BACKEND POLICY IS FAIL CLOSED",
        {
            "backend": policy.backend_id,
            "networking": policy.networking,
            "protected_client": policy.protected_client,
            "input_read_only": policy.input_read_only,
            "output_read_only": policy.output_read_only,
            "ipv4": policy.ipv4_probe_required,
            "ipv6": policy.ipv6_probe_required,
            "host_fallback": policy.host_fallback_allowed,
            "patched_code": policy.patched_code_allowed_during_capability_gate,
            "result_authentication": policy.result_authentication,
            "worker_isolation": policy.worker_isolation,
            "runtime": policy.python_runtime_strategy,
            "validation": list(validate_execution_backend_policy(policy)),
        },
        {
            "backend": "traditional_wsb_logoncommand_v1",
            "networking": "Disable",
            "protected_client": "Enable",
            "input_read_only": True,
            "output_read_only": False,
            "ipv4": True,
            "ipv6": True,
            "host_fallback": False,
            "patched_code": False,
            "result_authentication": "ecdsa_p256_two_phase_v1",
            "worker_isolation": "system_controller_standard_user_job_v1",
            "runtime": "pinned_read_only_runtime_bundle_v1",
            "validation": [],
        },
    )

    invalid_policy = replace(policy, memory_mb=2048, host_fallback_allowed=True)
    check(
        "POLICY MUTATION IS REJECTED",
        list(validate_execution_backend_policy(invalid_policy)),
        ["policy_memory_invalid", "policy_prohibitions_invalid"],
    )

    try:
        policy.memory_mb = 2048  # type: ignore[misc]
        policy_immutable = False
    except FrozenInstanceError:
        policy_immutable = True

    check(
        "BACKEND POLICY IS IMMUTABLE AND JSON SERIALIZABLE",
        {
            "immutable": policy_immutable,
            "json": bool(json.dumps(policy.to_dict(), sort_keys=True)),
        },
        {
            "immutable": True,
            "json": True,
        },
    )

    report = _run_host()
    check(
        "SUPPORTED HOST PASSES WITHOUT LAUNCHING SANDBOX",
        {
            "ok": report.ok,
            "issue_codes": list(report.issue_codes),
            "backend": report.backend_id,
            "policy": report.policy_fingerprint,
            "platform": report.host_platform,
            "architecture": report.host_architecture,
            "process_bitness": report.process_bitness,
            "build": report.windows_build,
            "feature": report.feature_state,
            "version": report.executable.version if report.executable else "",
            "wsb_cli": report.wsb_cli_found,
            "processes": list(report.running_sandbox_processes),
            "execution_authorized": report.to_dict()["execution_authorized"],
        },
        {
            "ok": True,
            "issue_codes": [],
            "backend": "traditional_wsb_logoncommand_v1",
            "policy": _VALID_POLICY_FINGERPRINT,
            "platform": "win32",
            "architecture": "AMD64",
            "process_bitness": 64,
            "build": 26200,
            "feature": "enabled",
            "version": "10.0.26100.8875",
            "wsb_cli": False,
            "processes": [],
            "execution_authorized": False,
        },
    )

    try:
        report.windows_build = 1  # type: ignore[misc]
        report_immutable = False
    except FrozenInstanceError:
        report_immutable = True

    check(
        "HOST REPORT IS IMMUTABLE AND JSON SERIALIZABLE",
        {
            "immutable": report_immutable,
            "json": bool(json.dumps(report.to_dict(), sort_keys=True)),
        },
        {
            "immutable": True,
            "json": True,
        },
    )

    unknown_feature = _run_host(feature=("unknown", "administrator_required"))
    check(
        "UNKNOWN OPTIONAL FEATURE STATE IS ADVISORY",
        {
            "ok": unknown_feature.ok,
            "feature": unknown_feature.feature_state,
            "error": unknown_feature.feature_probe_error,
            "issue_codes": list(unknown_feature.issue_codes),
        },
        {
            "ok": True,
            "feature": "unknown",
            "error": "administrator_required",
            "issue_codes": [],
        },
    )

    no_cli = _run_host(wsb=(False, ""))
    check(
        "WSB CLI IS NOT REQUIRED FOR TRADITIONAL BACKEND",
        {
            "ok": no_cli.ok,
            "found": no_cli.wsb_cli_found,
            "path": no_cli.wsb_cli_path,
        },
        {
            "ok": True,
            "found": False,
            "path": "",
        },
    )

    with_cli = _run_host(wsb=(True, r"C:\Windows\System32\wsb.exe"))
    check(
        "WSB CLI PRESENCE IS RECORDED WITHOUT CHANGING BACKEND",
        {
            "ok": with_cli.ok,
            "backend": with_cli.backend_id,
            "found": with_cli.wsb_cli_found,
        },
        {
            "ok": True,
            "backend": "traditional_wsb_logoncommand_v1",
            "found": True,
        },
    )

    cli_probe_failure = _run_host(wsb=RuntimeError("fake CLI probe failure"))
    check(
        "OPTIONAL WSB CLI PROBE FAILURE IS ADVISORY",
        {
            "ok": cli_probe_failure.ok,
            "found": cli_probe_failure.wsb_cli_found,
            "error": cli_probe_failure.wsb_cli_probe_error,
            "issue_codes": list(cli_probe_failure.issue_codes),
        },
        {
            "ok": True,
            "found": False,
            "error": "RuntimeError: fake CLI probe failure",
            "issue_codes": [],
        },
    )

    unsupported_platform = _run_host(platform_name="linux")
    check(
        "NON WINDOWS HOST IS REJECTED BEFORE PROBES",
        list(unsupported_platform.issue_codes),
        ["execution_backend_platform_unsupported"],
    )

    unsupported_architecture = _run_host(architecture="ARM64")
    check(
        "UNSUPPORTED HOST ARCHITECTURE IS REJECTED",
        list(unsupported_architecture.issue_codes),
        ["execution_backend_architecture_unsupported"],
    )

    unsupported_bitness = _run_host(process_bitness=32)
    check(
        "THIRTY TWO BIT HOST PROCESS IS REJECTED",
        list(unsupported_bitness.issue_codes),
        ["execution_backend_process_bitness_unsupported"],
    )

    old_windows = _run_host(windows_build=22631)
    check(
        "WINDOWS BUILD BELOW POLICY MINIMUM IS REJECTED",
        list(old_windows.issue_codes),
        ["execution_backend_windows_build_unsupported"],
    )

    with patch.object(
        host_module,
        "_current_boot_epoch_seconds",
        side_effect=OSError("fake boot probe failure"),
    ):
        with (
            patch.object(host_module, "_current_platform", return_value="win32"),
            patch.object(host_module, "_current_architecture", return_value="AMD64"),
            patch.object(host_module, "_current_process_bitness", return_value=64),
            patch.object(host_module, "_current_windows_build", return_value=26200),
            patch.object(host_module, "_inspect_sandbox_executable", return_value=_executable()),
            patch.object(host_module, "_probe_optional_feature_state", return_value=("enabled", "")),
            patch.object(host_module, "_probe_running_sandbox_processes", return_value=()),
            patch.object(host_module, "_probe_wsb_cli", return_value=(False, "")),
        ):
            boot_failure = inspect_developer_task_execution_backend_host()

    check(
        "HOST BOOT IDENTITY FAILURE IS STRUCTURED",
        list(boot_failure.issue_codes),
        ["execution_backend_boot_identity_failed"],
    )

    missing_executable = _run_host(
        executable=DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_missing",
            "missing",
            actual="fixed-path",
        )
    )
    check(
        "MISSING SANDBOX EXECUTABLE IS STRUCTURED",
        list(missing_executable.issue_codes),
        ["sandbox_executable_missing"],
    )

    old_executable = _run_host(executable=_executable(version="10.0.22631.1"))
    check(
        "SANDBOX EXECUTABLE BELOW POLICY MINIMUM IS REJECTED",
        list(old_executable.issue_codes),
        ["sandbox_executable_version_unsupported"],
    )

    disabled_feature = _run_host(feature=("disabled", ""))
    check(
        "DISABLED SANDBOX FEATURE IS REJECTED",
        list(disabled_feature.issue_codes),
        ["sandbox_feature_disabled"],
    )

    pending_feature = _run_host(feature=("enable_pending", ""))
    check(
        "PENDING SANDBOX FEATURE REQUIRES RESTART",
        list(pending_feature.issue_codes),
        ["sandbox_feature_restart_required"],
    )

    running_instance = _run_host(
        processes=("windowssandbox.exe:1234",)
    )
    check(
        "RUNNING SANDBOX INSTANCE BLOCKS CAPABILITY",
        {
            "issue_codes": list(running_instance.issue_codes),
            "processes": list(running_instance.running_sandbox_processes),
        },
        {
            "issue_codes": ["sandbox_instance_running"],
            "processes": ["windowssandbox.exe:1234"],
        },
    )

    process_failure = _run_host(
        processes=DeveloperTaskExecutionBackendHostError(
            "sandbox_process_probe_timeout",
            "timeout",
        )
    )
    check(
        "SANDBOX PROCESS PROBE FAILURE FAILS CLOSED",
        list(process_failure.issue_codes),
        ["sandbox_process_probe_timeout"],
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        executable_path = Path(temp_dir) / "WindowsSandbox.exe"
        content = b"sandbox-binary\x00\xff"
        executable_path.write_bytes(content)
        size, _mtime, sha256 = host_module._read_regular_file_sha256(executable_path)

        check(
            "SANDBOX EXECUTABLE IS HASHED AS EXACT BYTES",
            {
                "size": size,
                "sha256": sha256,
            },
            {
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir) / "WindowsSandbox.exe"
        directory.mkdir()
        try:
            host_module._read_regular_file_sha256(directory)
            directory_code = ""
        except DeveloperTaskExecutionBackendHostError as exc:
            directory_code = exc.code

        check(
            "SANDBOX EXECUTABLE DIRECTORY IS REJECTED",
            directory_code,
            "sandbox_executable_not_regular",
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        empty = Path(temp_dir) / "WindowsSandbox.exe"
        empty.write_bytes(b"")
        try:
            host_module._read_regular_file_sha256(empty)
            empty_code = ""
        except DeveloperTaskExecutionBackendHostError as exc:
            empty_code = exc.code

        check(
            "EMPTY SANDBOX EXECUTABLE IS REJECTED",
            empty_code,
            "sandbox_executable_size_invalid",
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        target = root / "target.exe"
        link = root / "WindowsSandbox.exe"
        target.write_bytes(b"target")
        try:
            link.symlink_to(target)
            try:
                host_module._read_regular_file_sha256(link)
                link_code = ""
            except DeveloperTaskExecutionBackendHostError as exc:
                link_code = exc.code
        except OSError:
            link_code = "unsupported"

        check(
            "SANDBOX EXECUTABLE REPARSE OR SYMLINK IS REJECTED",
            link_code,
            "unsupported" if link_code == "unsupported" else "sandbox_executable_reparse_point",
        )

    check(
        "VERSION BUILD PARSER IS STRICT",
        {
            "valid": host_module._version_build("10.0.26100.8875"),
            "short": host_module._version_build("10.0"),
            "invalid": host_module._version_build("10.x.26100.1"),
        },
        {
            "valid": 26100,
            "short": 0,
            "invalid": 0,
        },
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        windows = Path(temp_dir) / "Windows"
        powershell = (
            windows
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        powershell.parent.mkdir(parents=True)
        powershell.write_bytes(b"powershell")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"10.0.26100.8875",
            stderr=b"",
        )

        with (
            patch.object(host_module.sys, "platform", "win32"),
            patch.object(host_module, "_windows_directory", return_value=windows),
            patch.object(host_module, "_fixed_host_environment", return_value={}),
            patch.object(host_module.subprocess, "run", return_value=completed) as run_mock,
        ):
            probed_version = host_module._read_windows_file_version(
                Path(r"C:\Windows\System32\WindowsSandbox.exe")
            )

        command = run_mock.call_args.args[0]
        keyword_arguments = run_mock.call_args.kwargs

    check(
        "EXECUTABLE VERSION PROBE USES FIXED POWERSHELL WITHOUT SHELL",
        {
            "version": probed_version,
            "powershell": command[0] == str(powershell),
            "literal_path": "Get-Item -LiteralPath" in command[-1],
            "shell_absent": "shell" not in keyword_arguments,
            "timeout": keyword_arguments.get("timeout"),
        },
        {
            "version": "10.0.26100.8875",
            "powershell": True,
            "literal_path": True,
            "shell_absent": True,
            "timeout": 10.0,
        },
    )

    with (
        patch.object(
            host_module,
            "_system_directory",
            return_value=Path("/trusted/windows/System32"),
        ),
        patch.dict(os.environ, {"PATH": "/poison"}, clear=True),
    ):
        fixed_path = host_module._sandbox_executable_path(policy)

    check(
        "SANDBOX EXECUTABLE USES FIXED WINDOWS SYSTEM PATH",
        str(fixed_path),
        str(Path("/trusted/windows/System32") / "WindowsSandbox.exe"),
    )

    source_text = Path(host_module.__file__).read_text(encoding="utf-8")
    check(
        "HOST GATE HAS NO SANDBOX LAUNCH OR HOST FALLBACK",
        {
            "no_start_process": "Start-Process" not in source_text,
            "no_popen": "subprocess.Popen" not in source_text,
            "no_shell_true": "shell=True" not in source_text,
            "no_manifest": "DeveloperTaskManifest" not in source_text,
            "no_python_module": "python_module" not in source_text,
            "no_pipeline_execute": "tools/pipeline.py" not in source_text,
            "execution_authorized_false": '"execution_authorized": False' in source_text,
        },
        {
            "no_start_process": True,
            "no_popen": True,
            "no_shell_true": True,
            "no_manifest": True,
            "no_python_module": True,
            "no_pipeline_execute": True,
            "execution_authorized_false": True,
        },
    )

    policy_text = Path(policy_module.__file__).read_text(encoding="utf-8")
    check(
        "POLICY SOURCE LOCKS FUTURE AUTHENTICITY AND PRIVILEGE BOUNDARIES",
        {
            "ecdsa": "ecdsa_p256_two_phase_v1" in policy_text,
            "system_controller": "system_controller_standard_user_job_v1" in policy_text,
            "runtime_bundle": "pinned_read_only_runtime_bundle_v1" in policy_text,
            "ipv6": "ipv6_probe_required=True" in policy_text,
            "no_host_fallback": "host_fallback_allowed=False" in policy_text,
        },
        {
            "ecdsa": True,
            "system_controller": True,
            "runtime_bundle": True,
            "ipv6": True,
            "no_host_fallback": True,
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
