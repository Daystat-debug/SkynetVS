from __future__ import annotations

import json
import tempfile

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_backend_lifecycle as lifecycle_module
import modules.developer.developer_task_execution_backend_lifecycle_windows as lifecycle_windows_module
import modules.developer.developer_task_execution_backend_lifecycle_windows as lifecycle_windows_module

from modules.developer.developer_task_execution_backend_host import (
    DeveloperTaskExecutionBackendExecutableEvidence,
    DeveloperTaskExecutionBackendHostReport,
)
from modules.developer.developer_task_execution_backend_lifecycle import (
    LIFECYCLE_STATUS_ATTESTED,
    LIFECYCLE_STATUS_FAILED,
    LIFECYCLE_STATUS_FAILED_ACTIVE,
    attest_developer_task_execution_backend_lifecycle,
)
from modules.developer.developer_task_execution_backend_lifecycle_payload import (
    DeveloperTaskExecutionBackendLifecyclePayloadError,
    build_lifecycle_guest_script,
    build_lifecycle_request,
    build_lifecycle_wsb_config,
    canonical_json_bytes,
    validate_lifecycle_guest_result,
)
from modules.developer.developer_task_execution_backend_lifecycle_windows import (
    DeveloperTaskExecutionBackendLifecycleWindowsError,
    DeveloperTaskExecutionBackendProcessEvidence,
)
from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue


_POLICY_FINGERPRINT = "5c731d5f246929aa1b59f614d2a01371b086244cc09f2c5846d93531b194af21"


def _host_report(*, sha256: str = "a" * 64, issues: tuple[DeveloperTaskPreflightIssue, ...] = ()) -> DeveloperTaskExecutionBackendHostReport:
    policy = WINDOWS_SANDBOX_EXECUTION_POLICY_V1
    return DeveloperTaskExecutionBackendHostReport(
        backend_id=policy.backend_id,
        policy=policy,
        policy_fingerprint=policy.fingerprint,
        host_platform="win32",
        host_architecture="AMD64",
        process_bitness=64,
        windows_build=26200,
        host_boot_epoch_seconds=1785870000,
        feature_state="enabled",
        feature_probe_error="",
        executable=DeveloperTaskExecutionBackendExecutableEvidence(
            path=r"C:\Windows\System32\WindowsSandbox.exe",
            version="10.0.26100.8875",
            size_bytes=123456,
            mtime_ns=123456789,
            sha256=sha256,
        ),
        wsb_cli_found=False,
        wsb_cli_path="",
        wsb_cli_probe_error="",
        running_sandbox_processes=(),
        issues=issues,
    )


def _guest_result_bytes(result_path: Path, *, mode: str = "valid") -> bytes:
    input_root = result_path.parent.parent / "input"
    request_path = input_root / "request.json"
    guest_path = input_root / "guest_lifecycle_probe.ps1"
    wsb_path = input_root / "SkynetVS_Lifecycle.wsb"
    request = json.loads(request_path.read_text(encoding="utf-8"))

    value: dict[str, Any] = {
        "schema_version": 1,
        "backend_id": request["backend_id"],
        "policy_fingerprint": request["policy_fingerprint"],
        "request_id": request["request_id"],
        "nonce": request["nonce"],
        "request_sha256": __import__("hashlib").sha256(request_path.read_bytes()).hexdigest(),
        "guest_script_sha256": __import__("hashlib").sha256(guest_path.read_bytes()).hexdigest(),
        "wsb_sha256": __import__("hashlib").sha256(wsb_path.read_bytes()).hexdigest(),
        "completed_at": "2026-08-05T17:13:32.9657864Z",
        "overall_ok": True,
        "shutdown": {
            "scheduled": True,
            "exit_code": 0,
            "error": "",
            "delay_seconds": 5,
        },
        "guest": {
            "computer_name": "TEST-VM",
            "user_name": r"TEST-VM\WDAGUtilityAccount",
            "process_architecture": "X64",
            "os_description": "Microsoft Windows 10.0.26100",
            "powershell_version": "5.1.26100.8875",
        },
        "controls": {
            "input_mapping_present": True,
            "input_mapping_read_only_enforced": True,
            "output_mapping_present": True,
            "output_mapping_writable": True,
            "ipv4_default_route_present": False,
            "ipv4_external_tcp_reachable": False,
            "ipv6_default_route_present": False,
            "ipv6_external_tcp_reachable": False,
        },
        "diagnostics": {
            "input_write_error": "access denied",
            "output_write_error": "",
            "ipv4_route_error": "",
            "ipv6_route_error": "",
            "ipv4_tcp_error": "blocked",
            "ipv6_tcp_error": "blocked",
        },
    }

    if mode == "network_open":
        value["controls"]["ipv4_default_route_present"] = True
    elif mode == "unknown_field":
        value["unexpected"] = True
    elif mode == "bad_nonce":
        value["nonce"] = "0" * 64
    elif mode == "bad_user":
        value["guest"]["user_name"] = r"TEST-VM\Administrator"
    elif mode == "bad_shutdown":
        value["shutdown"]["scheduled"] = False
        value["overall_ok"] = False

    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class _MetadataFailureKernel:
    def __init__(self, wait_result: int) -> None:
        self.wait_result = wait_result
        self.open_calls = 0
        self.wait_calls = 0
        self.close_calls = 0

    def QueryFullProcessImageNameW(self, *_args: Any) -> bool:
        return False

    def OpenProcess(self, _access: int, _inherit: bool, _pid: int) -> object:
        self.open_calls += 1
        return object()

    def WaitForSingleObject(self, _handle: Any, _milliseconds: int) -> int:
        self.wait_calls += 1
        return self.wait_result

    def CloseHandle(self, _handle: Any) -> bool:
        self.close_calls += 1
        return True


class _Launcher:
    def __init__(self, runtime: "_FakeRuntime") -> None:
        self.runtime = runtime
        self.pid = 21544


class _FakeRuntime:
    def __init__(
        self,
        *,
        host_reports: list[DeveloperTaskExecutionBackendHostReport] | None = None,
        baseline_processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...] = (),
        observe_process: bool = True,
        active_forever: bool = False,
        result_at: float = 0.5,
        shutdown_at: float = 1.0,
        result_mode: str = "valid",
        launch_error: Exception | None = None,
        sleep_step: float | None = None,
        termination_succeeds: bool = True,
        change_result_after_exit: bool = False,
        process_handoff_gap_until: float = 0.0,
    ) -> None:
        self.host_reports = list(host_reports or [_host_report(), _host_report()])
        self.baseline_processes = baseline_processes
        self.observe_process = observe_process
        self.active_forever = active_forever
        self.result_at = result_at
        self.shutdown_at = shutdown_at
        self.result_mode = result_mode
        self.launch_error = launch_error
        self.sleep_step = sleep_step
        self.termination_succeeds = termination_succeeds
        self.change_result_after_exit = change_result_after_exit
        self.process_handoff_gap_until = process_handoff_gap_until
        self.read_calls = 0
        self.now = 0.0
        self.launched = False

    def inspect_host(self):
        if len(self.host_reports) > 1:
            return self.host_reports.pop(0)
        return self.host_reports[0]

    def snapshot_processes(self):
        if not self.launched:
            return self.baseline_processes
        if not self.observe_process:
            return ()
        if self.now < self.process_handoff_gap_until:
            return ()
        if self.active_forever or self.now < self.shutdown_at:
            return (
                DeveloperTaskExecutionBackendProcessEvidence(
                    name="WindowsSandboxRemoteSession.exe",
                    pid=15548,
                    created_epoch_ns=123456789,
                    executable_path=r"C:\Program Files\WindowsApps\WindowsSandboxRemoteSession.exe",
                ),
            )
        return ()

    def launch(self, _executable: Path, _config_path: Path):
        if self.launch_error is not None:
            raise self.launch_error
        self.launched = True
        return _Launcher(self)

    def launcher_exited(self, _launcher: _Launcher) -> bool:
        return self.now >= 0.4


    def terminate(self, observed, *, executable: Path):
        current = self.snapshot_processes()
        if self.termination_succeeds:
            self.active_forever = False
            self.shutdown_at = self.now
            remaining = ()
        else:
            remaining = current
        from modules.developer.developer_task_execution_backend_lifecycle_windows import DeveloperTaskExecutionBackendTerminationResult
        return DeveloperTaskExecutionBackendTerminationResult(
            attempted=True,
            succeeded=self.termination_succeeds,
            targeted_processes=tuple(observed),
            remaining_processes=tuple(remaining),
            errors=() if self.termination_succeeds else ("fake termination failure",),
        )

    def result_exists(self, _path: Path) -> bool:
        return self.now >= self.result_at

    def read_result(self, path: Path, max_bytes: int):
        self.read_calls += 1
        data = _guest_result_bytes(path, mode=self.result_mode)
        if self.change_result_after_exit and self.read_calls > 1:
            data += b" "
        if len(data) > max_bytes:
            raise AssertionError("fixture result exceeded max_bytes")
        return data, __import__("hashlib").sha256(data).hexdigest()

    def monotonic(self) -> float:
        return self.now

    def epoch(self) -> float:
        return 1000.0 + self.now

    def sleep(self, seconds: float) -> None:
        self.now += self.sleep_step if self.sleep_step is not None else seconds


def _run(parent: Path, runtime: _FakeRuntime, host: DeveloperTaskExecutionBackendHostReport | None = None):
    with patch.object(lifecycle_module, "_LifecycleRuntime", return_value=runtime):
        return attest_developer_task_execution_backend_lifecycle(
            host or _host_report(),
            artifact_parent=parent,
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

    policy = WINDOWS_SANDBOX_EXECUTION_POLICY_V1
    guest = build_lifecycle_guest_script(policy)
    check(
        "TRUSTED GUEST PROBE BINDS POLICY AND BOTH NETWORK FAMILIES",
        {
            "ascii": guest.decode("ascii").startswith("Set-StrictMode"),
            "backend": policy.backend_id.encode("ascii") in guest,
            "policy": policy.fingerprint.encode("ascii") in guest,
            "ipv4": b"1.1.1.1" in guest,
            "ipv6": b"2606:4700:4700::1111" in guest,
            "shutdown": b"shutdown.exe" in guest,
        },
        {"ascii": True, "backend": True, "policy": True, "ipv4": True, "ipv6": True, "shutdown": True},
    )

    wsb = build_lifecycle_wsb_config(policy, input_root=Path(r"C:\Host\Input"), output_root=Path(r"C:\Host\Output"))
    check(
        "WSB CONFIGURATION USES EXACT SECURITY CONTROLS",
        {
            "network": b"<Networking>Disable</Networking>" in wsb,
            "vgpu": b"<vGPU>Disable</vGPU>" in wsb,
            "protected": b"<ProtectedClient>Enable</ProtectedClient>" in wsb,
            "input_ro": b"<ReadOnly>true</ReadOnly>" in wsb,
            "output_rw": b"<ReadOnly>false</ReadOnly>" in wsb,
            "logon": b"guest_lifecycle_probe.ps1" in wsb,
        },
        {"network": True, "vgpu": True, "protected": True, "input_ro": True, "output_rw": True, "logon": True},
    )

    request = build_lifecycle_request(
        policy,
        request_id="1" * 32,
        nonce="2" * 64,
        generated_at_epoch=1785870000,
        guest_script_sha256="3" * 64,
        wsb_sha256="4" * 64,
    )
    check(
        "LIFECYCLE REQUEST IS CANONICAL AND DETERMINISTIC",
        {
            "stable": request.canonical_bytes() == build_lifecycle_request(
                policy,
                request_id="1" * 32,
                nonce="2" * 64,
                generated_at_epoch=1785870000,
                guest_script_sha256="3" * 64,
                wsb_sha256="4" * 64,
            ).canonical_bytes(),
            "canonical": request.canonical_bytes() == canonical_json_bytes(request.to_dict()),
            "hash": len(request.sha256),
        },
        {"stable": True, "canonical": True, "hash": 64},
    )

    try:
        build_lifecycle_request(policy, request_id="bad", nonce="2" * 64, generated_at_epoch=1, guest_script_sha256="3" * 64, wsb_sha256="4" * 64)
        invalid_request_rejected = False
    except DeveloperTaskExecutionBackendLifecyclePayloadError:
        invalid_request_rejected = True
    check("INVALID REQUEST IDENTIFIERS ARE REJECTED", invalid_request_rejected, True)

    valid_result = {
        "schema_version": 1,
        "backend_id": request.backend_id,
        "policy_fingerprint": request.policy_fingerprint,
        "request_id": request.request_id,
        "nonce": request.nonce,
        "request_sha256": request.sha256,
        "guest_script_sha256": request.guest_script_sha256,
        "wsb_sha256": request.wsb_sha256,
        "completed_at": "2026-08-05T17:13:32Z",
        "overall_ok": True,
        "shutdown": {"scheduled": True, "exit_code": 0, "error": "", "delay_seconds": 5},
        "guest": {"computer_name": "VM", "user_name": r"VM\WDAGUtilityAccount", "process_architecture": "X64", "os_description": "Windows", "powershell_version": "5.1"},
        "controls": {"input_mapping_present": True, "input_mapping_read_only_enforced": True, "output_mapping_present": True, "output_mapping_writable": True, "ipv4_default_route_present": False, "ipv4_external_tcp_reachable": False, "ipv6_default_route_present": False, "ipv6_external_tcp_reachable": False},
        "diagnostics": {"input_write_error": "denied", "output_write_error": "", "ipv4_route_error": "", "ipv6_route_error": "", "ipv4_tcp_error": "blocked", "ipv6_tcp_error": "blocked"},
    }
    raw_valid = json.dumps(valid_result, separators=(",", ":")).encode()
    evidence = validate_lifecycle_guest_result(raw_valid, result_sha256=__import__("hashlib").sha256(raw_valid).hexdigest(), request=request, request_sha256=request.sha256)
    check("VALID TRUSTED GUEST RESULT PASSES", evidence.ok, True)

    exited_kernel = _MetadataFailureKernel(
        lifecycle_windows_module._WAIT_OBJECT_0,
    )
    with patch.object(
        lifecycle_windows_module.ctypes,
        "get_last_error",
        return_value=5,
        create=True,
    ):
        exited_result = lifecycle_windows_module._query_process_evidence_from_handle(
            exited_kernel,
            object(),
            15548,
            "WindowsSandboxRemoteSession.exe",
        )
    check(
        "EXITING PROCESS METADATA RACE IS TREATED AS DISAPPEARANCE",
        {
            "result": exited_result,
            "open_calls": exited_kernel.open_calls,
            "wait_calls": exited_kernel.wait_calls,
            "close_calls": exited_kernel.close_calls,
        },
        {
            "result": None,
            "open_calls": 1,
            "wait_calls": 1,
            "close_calls": 1,
        },
    )

    live_kernel = _MetadataFailureKernel(
        lifecycle_windows_module._WAIT_TIMEOUT,
    )
    with patch.object(
        lifecycle_windows_module.ctypes,
        "get_last_error",
        return_value=5,
        create=True,
    ), patch.object(
        lifecycle_windows_module,
        "_winerror_text",
        return_value="pid=15548; winerror=5",
    ):
        try:
            lifecycle_windows_module._query_process_evidence_from_handle(
                live_kernel,
                object(),
                15548,
                "WindowsSandboxRemoteSession.exe",
            )
        except DeveloperTaskExecutionBackendLifecycleWindowsError as exc:
            live_failure_code = exc.code
        else:
            live_failure_code = ""
    check(
        "LIVE PROCESS METADATA FAILURE REMAINS FAIL CLOSED",
        {
            "code": live_failure_code,
            "open_calls": live_kernel.open_calls,
            "wait_calls": live_kernel.wait_calls,
            "close_calls": live_kernel.close_calls,
        },
        {
            "code": "sandbox_process_metadata_failed",
            "open_calls": 1,
            "wait_calls": 1,
            "close_calls": 1,
        },
    )

    metadata_error = DeveloperTaskExecutionBackendLifecycleWindowsError(
        "sandbox_process_metadata_failed",
        "transient metadata race",
    )
    with patch.object(
        lifecycle_windows_module,
        "_query_process_evidence",
        side_effect=[metadata_error, None],
    ) as transient_query, patch.object(
        lifecycle_windows_module.time,
        "sleep",
    ) as transient_sleep:
        transient_result = lifecycle_windows_module._query_process_evidence_with_retry(
            object(),
            15548,
            "WindowsSandboxRemoteSession.exe",
        )

    with patch.object(
        lifecycle_windows_module,
        "_query_process_evidence",
        side_effect=metadata_error,
    ) as persistent_query, patch.object(
        lifecycle_windows_module.time,
        "sleep",
    ) as persistent_sleep:
        try:
            lifecycle_windows_module._query_process_evidence_with_retry(
                object(),
                15548,
                "WindowsSandboxRemoteSession.exe",
            )
        except DeveloperTaskExecutionBackendLifecycleWindowsError as exc:
            persistent_code = exc.code
        else:
            persistent_code = ""

    check(
        "PROCESS METADATA RETRY IS BOUNDED AND FAIL CLOSED",
        {
            "transient_result": transient_result,
            "transient_calls": transient_query.call_count,
            "transient_sleeps": transient_sleep.call_count,
            "persistent_code": persistent_code,
            "persistent_calls": persistent_query.call_count,
            "persistent_sleeps": persistent_sleep.call_count,
        },
        {
            "transient_result": None,
            "transient_calls": 2,
            "transient_sleeps": 1,
            "persistent_code": "sandbox_process_metadata_failed",
            "persistent_calls": 3,
            "persistent_sleeps": 2,
        },
    )

    timing_context = lifecycle_module._LifecycleContext(
        WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
        1000.0,
    )
    lifecycle_module._record_all_processes_exited(
        timing_context,
        elapsed_ms=1234,
    )
    lifecycle_module._record_all_processes_exited(
        timing_context,
        elapsed_ms=9999,
    )
    check(
        "FINALIZATION RECORDS THE FIRST PROVEN PROCESS EXIT TIME",
        {
            "exited": timing_context.all_processes_exited,
            "elapsed_ms": timing_context.all_processes_exited_ms,
        },
        {
            "exited": True,
            "elapsed_ms": 1234,
        },
    )

    duplicate_raw = ('{"schema_version":1,"schema_version":1,' + json.dumps({k: v for k, v in valid_result.items() if k != "schema_version"}, separators=(",", ":"))[1:]).encode()
    try:
        validate_lifecycle_guest_result(duplicate_raw, result_sha256="a" * 64, request=request, request_sha256=request.sha256)
        duplicate_rejected = False
    except DeveloperTaskExecutionBackendLifecyclePayloadError as exc:
        duplicate_rejected = exc.code == "lifecycle_result_duplicate_field"
    check("DUPLICATE RESULT FIELDS ARE REJECTED", duplicate_rejected, True)

    unknown = dict(valid_result)
    unknown["unexpected"] = True
    try:
        validate_lifecycle_guest_result(json.dumps(unknown).encode(), result_sha256="a" * 64, request=request, request_sha256=request.sha256)
        unknown_rejected = False
    except DeveloperTaskExecutionBackendLifecyclePayloadError as exc:
        unknown_rejected = exc.code == "lifecycle_result_fields_invalid"
    check("UNKNOWN RESULT FIELDS ARE REJECTED", unknown_rejected, True)

    try:
        validate_lifecycle_guest_result(b"\xff", result_sha256="a" * 64, request=request, request_sha256=request.sha256)
        encoding_rejected = False
    except DeveloperTaskExecutionBackendLifecyclePayloadError as exc:
        encoding_rejected = exc.code == "lifecycle_result_encoding_invalid"
    check("NON UTF8 RESULT IS REJECTED", encoding_rejected, True)

    network = json.loads(json.dumps(valid_result))
    network["controls"]["ipv4_default_route_present"] = True
    network["overall_ok"] = False
    try:
        raw = json.dumps(network).encode()
        validate_lifecycle_guest_result(raw, result_sha256=__import__("hashlib").sha256(raw).hexdigest(), request=request, request_sha256=request.sha256)
        network_rejected = False
    except DeveloperTaskExecutionBackendLifecyclePayloadError as exc:
        network_rejected = exc.code in {"lifecycle_result_evidence_mismatch", "lifecycle_result_controls_failed"}
    check("OPEN IPV4 ROUTE IS REJECTED", network_rejected, True)

    identity = json.loads(json.dumps(valid_result))
    identity["guest"]["user_name"] = r"VM\Administrator"
    try:
        raw = json.dumps(identity).encode()
        validate_lifecycle_guest_result(raw, result_sha256=__import__("hashlib").sha256(raw).hexdigest(), request=request, request_sha256=request.sha256)
        identity_rejected = False
    except DeveloperTaskExecutionBackendLifecyclePayloadError as exc:
        identity_rejected = exc.code == "lifecycle_result_controls_failed"
    check("NON WDAG GUEST IDENTITY IS REJECTED", identity_rejected, True)

    with tempfile.TemporaryDirectory() as temp_dir:
        report = _run(Path(temp_dir), _FakeRuntime())
        check(
            "TRUSTED LIFECYCLE PASSES AND CLEANS ARTIFACTS",
            {
                "ok": report.ok,
                "status": report.status,
                "issues": list(report.issue_codes),
                "launcher": report.launcher_pid,
                "observed": report.process_observed,
                "exited": report.all_processes_exited,
                "guest": report.guest_evidence.ok if report.guest_evidence else False,
                "removed": report.artifacts.removed if report.artifacts else False,
                "execution_authorized": report.to_dict()["execution_authorized"],
            },
            {"ok": True, "status": LIFECYCLE_STATUS_ATTESTED, "issues": [], "launcher": 21544, "observed": True, "exited": True, "guest": True, "removed": True, "execution_authorized": False},
        )

        try:
            report.status = "x"  # type: ignore[misc]
            immutable = False
        except FrozenInstanceError:
            immutable = True
        check("LIFECYCLE REPORT IS IMMUTABLE AND JSON SERIALIZABLE", {"immutable": immutable, "json": bool(json.dumps(report.to_dict()))}, {"immutable": True, "json": True})

    try:
        attest_developer_task_execution_backend_lifecycle({}, artifact_parent=Path(tempfile.gettempdir()))  # type: ignore[arg-type]
        raw_host_rejected = False
    except TypeError:
        raw_host_rejected = True
    check("RAW HOST REPORT IS REJECTED", raw_host_rejected, True)

    try:
        attest_developer_task_execution_backend_lifecycle(_host_report(), artifact_parent=str(Path(tempfile.gettempdir())))  # type: ignore[arg-type]
        string_parent_rejected = False
    except TypeError:
        string_parent_rejected = True
    check("STRING ARTIFACT PARENT IS REJECTED", string_parent_rejected, True)

    failed_issue = DeveloperTaskPreflightIssue(code="failed", check="host", message="failed", expected="", actual="")
    with tempfile.TemporaryDirectory() as temp_dir:
        failed_report = _run(Path(temp_dir), _FakeRuntime(), _host_report(issues=(failed_issue,)))
        check("FAILED HOST REPORT BLOCKS LIFECYCLE", list(failed_report.issue_codes), ["execution_backend_host_report_failed"])

    forged_host = replace(_host_report(), policy_fingerprint="0" * 64)
    with tempfile.TemporaryDirectory() as temp_dir:
        forged_report = _run(Path(temp_dir), _FakeRuntime(), forged_host)
        check("FORGED HOST POLICY EVIDENCE IS REJECTED", list(forged_report.issue_codes), ["execution_backend_host_report_failed"])

    with tempfile.TemporaryDirectory() as temp_dir:
        changed_report = _run(Path(temp_dir), _FakeRuntime(host_reports=[_host_report(sha256="b" * 64)]))
        check("STALE HOST EVIDENCE IS REJECTED", list(changed_report.issue_codes), ["execution_backend_host_evidence_changed"])

    missing_parent = Path(tempfile.gettempdir()) / "skynetvs-lifecycle-missing-parent"
    if missing_parent.exists():
        __import__("shutil").rmtree(missing_parent)
    missing_report = _run(missing_parent, _FakeRuntime())
    check("MISSING ARTIFACT PARENT IS REJECTED", list(missing_report.issue_codes), ["lifecycle_artifact_parent_missing"])

    with tempfile.TemporaryDirectory() as temp_dir:
        file_parent = Path(temp_dir) / "file"
        file_parent.write_text("x")
        file_report = _run(file_parent, _FakeRuntime())
        check("FILE ARTIFACT PARENT IS REJECTED", list(file_report.issue_codes), ["lifecycle_artifact_parent_not_directory"])

    with tempfile.TemporaryDirectory() as temp_dir:
        git_parent = Path(temp_dir) / "repo" / "artifacts"
        git_parent.mkdir(parents=True)
        (Path(temp_dir) / "repo" / ".git").mkdir()
        git_report = _run(git_parent, _FakeRuntime())
        check("ARTIFACT PARENT INSIDE GIT REPOSITORY IS REJECTED", list(git_report.issue_codes), ["lifecycle_artifact_parent_inside_git_repository"])

    running = DeveloperTaskExecutionBackendProcessEvidence(name="WindowsSandboxRemoteSession.exe", pid=99, created_epoch_ns=1, executable_path="x")
    with tempfile.TemporaryDirectory() as temp_dir:
        running_report = _run(Path(temp_dir), _FakeRuntime(baseline_processes=(running,)))
        check("EXISTING SANDBOX BLOCKS LIFECYCLE", list(running_report.issue_codes), ["lifecycle_sandbox_instance_running"])

    launch_error = DeveloperTaskExecutionBackendLifecycleWindowsError("sandbox_launch_failed", "launch failed")
    with tempfile.TemporaryDirectory() as temp_dir:
        launch_report = _run(Path(temp_dir), _FakeRuntime(launch_error=launch_error))
        check("SANDBOX LAUNCH FAILURE IS STRUCTURED", list(launch_report.issue_codes), ["sandbox_launch_failed"])

    with tempfile.TemporaryDirectory() as temp_dir:
        timeout_report = _run(Path(temp_dir), _FakeRuntime(result_at=9999, sleep_step=30.0, active_forever=True))
        check(
            "RESULT TIMEOUT NEVER BECOMES SUCCESS AFTER FORCED CLEANUP",
            {
                "status": timeout_report.status,
                "code": "lifecycle_result_timeout" in timeout_report.issue_codes,
                "forced_cleanup": timeout_report.forced_cleanup_attempted,
                "ok": timeout_report.ok,
            },
            {"status": LIFECYCLE_STATUS_FAILED, "code": True, "forced_cleanup": True, "ok": False},
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        unobserved_report = _run(Path(temp_dir), _FakeRuntime(observe_process=False))
        check("UNOBSERVED PROCESS FAILS CLOSED", {"ok": unobserved_report.ok, "code": "lifecycle_process_not_observed" in unobserved_report.issue_codes}, {"ok": False, "code": True})

    with tempfile.TemporaryDirectory() as temp_dir:
        handoff_report = _run(
            Path(temp_dir),
            _FakeRuntime(
                result_at=1.0,
                shutdown_at=1.5,
                process_handoff_gap_until=0.75,
            ),
        )
        check(
            "TRANSIENT LAUNCHER TO REMOTE SESSION HANDOFF GAP IS TOLERATED",
            {
                "ok": handoff_report.ok,
                "status": handoff_report.status,
                "observed": handoff_report.process_observed,
                "exited": handoff_report.all_processes_exited,
            },
            {
                "ok": True,
                "status": LIFECYCLE_STATUS_ATTESTED,
                "observed": True,
                "exited": True,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        invalid_result = _run(Path(temp_dir), _FakeRuntime(result_mode="network_open"))
        check("INVALID NETWORK EVIDENCE IS REJECTED AFTER CLEAN SHUTDOWN", {"status": invalid_result.status, "exited": invalid_result.all_processes_exited, "guest": invalid_result.guest_evidence is not None}, {"status": LIFECYCLE_STATUS_FAILED, "exited": True, "guest": False})

    with tempfile.TemporaryDirectory() as temp_dir:
        active_report = _run(Path(temp_dir), _FakeRuntime(active_forever=True, sleep_step=5.0, termination_succeeds=False))
        check("SHUTDOWN AND FORCED CLEANUP FAILURE RETURNS FAILED ACTIVE", {"status": active_report.status, "shutdown": "lifecycle_shutdown_timeout" in active_report.issue_codes, "forced_cleanup": active_report.forced_cleanup_attempted, "removed": active_report.artifacts.removed if active_report.artifacts else True}, {"status": LIFECYCLE_STATUS_FAILED_ACTIVE, "shutdown": True, "forced_cleanup": True, "removed": False})

    with tempfile.TemporaryDirectory() as temp_dir:
        post_report = _run(Path(temp_dir), _FakeRuntime(host_reports=[_host_report(), _host_report(sha256="b" * 64)]))
        check("HOST CHANGE DURING LIFECYCLE IS REJECTED", "execution_backend_host_evidence_changed" in post_report.issue_codes, True)

    with tempfile.TemporaryDirectory() as temp_dir:
        changed_result_report = _run(
            Path(temp_dir),
            _FakeRuntime(change_result_after_exit=True),
        )
        check(
            "RESULT CHANGE BEFORE PROVEN EXIT IS REJECTED",
            "lifecycle_result_changed_before_exit" in changed_result_report.issue_codes,
            True,
        )

    cleanup_error = DeveloperTaskExecutionBackendLifecyclePayloadError("lifecycle_artifact_cleanup_failed", "cleanup failed")
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch.object(lifecycle_module, "_cleanup_artifacts", side_effect=cleanup_error):
            cleanup_report = _run(Path(temp_dir), _FakeRuntime())
        check("ARTIFACT CLEANUP FAILURE IS STRUCTURED", {"status": cleanup_report.status, "code": "lifecycle_artifact_cleanup_failed" in cleanup_report.issue_codes}, {"status": LIFECYCLE_STATUS_FAILED, "code": True})

    trusted_main = DeveloperTaskExecutionBackendProcessEvidence(
        name="WindowsSandbox.exe",
        pid=10,
        created_epoch_ns=100,
        executable_path=r"C:\Windows\System32\WindowsSandbox.exe",
    )
    trusted_remote = DeveloperTaskExecutionBackendProcessEvidence(
        name="WindowsSandboxRemoteSession.exe",
        pid=11,
        created_epoch_ns=101,
        executable_path=(
            "C:\\Program Files\\WindowsApps\\"
            "MicrosoftWindows.WindowsSandbox_0.8.107.0_x64__cw5n1h2txyewy\\"
            "WindowsSandboxRemoteSession.exe"
        ),
    )
    untrusted_remote = DeveloperTaskExecutionBackendProcessEvidence(
        name="WindowsSandboxRemoteSession.exe",
        pid=12,
        created_epoch_ns=102,
        executable_path=r"C:\Temp\WindowsSandboxRemoteSession.exe",
    )
    check(
        "FORCED CLEANUP ACCEPTS ONLY TRUSTED SANDBOX PROCESS PATHS",
        {
            "main": lifecycle_windows_module._is_trusted_sandbox_process_path(
                trusted_main,
                Path(r"C:\Windows\System32\WindowsSandbox.exe"),
            ),
            "remote": lifecycle_windows_module._is_trusted_sandbox_process_path(
                trusted_remote,
                Path(r"C:\Windows\System32\WindowsSandbox.exe"),
            ),
            "untrusted": lifecycle_windows_module._is_trusted_sandbox_process_path(
                untrusted_remote,
                Path(r"C:\Windows\System32\WindowsSandbox.exe"),
            ),
        },
        {"main": True, "remote": True, "untrusted": False},
    )

    sandbox_executable = Path(r"C:\Windows\System32\WindowsSandbox.exe")
    sandbox_environment = lifecycle_windows_module.build_windows_sandbox_environment(
        sandbox_executable
    )
    check(
        "SANDBOX ENVIRONMENT DEFINES FIXED SYSTEM DRIVE",
        {
            "system_drive": sandbox_environment.get("SystemDrive"),
            "system_root": sandbox_environment.get("SystemRoot"),
            "windir": sandbox_environment.get("WINDIR"),
            "path": sandbox_environment.get("PATH"),
        },
        {
            "system_drive": "C:",
            "system_root": r"C:\Windows",
            "windir": r"C:\Windows",
            "path": r"C:\Windows\System32",
        },
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        artifact_root = Path(temp_dir) / "lifecycle-run"
        input_root = artifact_root / "input"
        input_root.mkdir(parents=True)
        config_path = input_root / "SkynetVS_Lifecycle.wsb"
        config_path.write_text("<Configuration />", encoding="utf-8")

        popen_call: dict[str, Any] = {}

        class _FakePopen:
            pid = 12345

            def poll(self):
                return None

        def _fake_popen(*args, **kwargs):
            popen_call["args"] = args
            popen_call["kwargs"] = kwargs
            return _FakePopen()

        with (
            patch.object(lifecycle_windows_module, "_require_windows"),
            patch.object(lifecycle_windows_module.subprocess, "Popen", side_effect=_fake_popen),
        ):
            lifecycle_windows_module.launch_windows_sandbox(
                sandbox_executable,
                config_path,
            )

        check(
            "SANDBOX LAUNCH USES FIXED TRUSTED WORKING DIRECTORY",
            {
                "cwd": popen_call["kwargs"].get("cwd"),
                "system_drive": popen_call["kwargs"]["env"].get("SystemDrive"),
                "shell": popen_call["kwargs"].get("shell"),
            },
            {
                "cwd": str(sandbox_executable.parent),
                "system_drive": "C:",
                "shell": False,
            },
        )

    windows_text = Path(lifecycle_windows_module.__file__).read_text(encoding="utf-8")
    check(
        "FORCED CLEANUP USES EXACT PROCESS HANDLE IDENTITY",
        {
            "uses_open_process": "OpenProcess" in windows_text,
            "uses_creation_identity": "created_epoch_ns" in windows_text,
            "uses_terminate_process": "TerminateProcess" in windows_text,
            "uses_wait_handle": "WaitForSingleObject" in windows_text,
            "rejects_untrusted_path": "untrusted_path=" in windows_text,
            "no_taskkill": "taskkill" not in windows_text.casefold(),
        },
        {
            "uses_open_process": True,
            "uses_creation_identity": True,
            "uses_terminate_process": True,
            "uses_wait_handle": True,
            "rejects_untrusted_path": True,
            "no_taskkill": True,
        },
    )

    production_text = Path(lifecycle_module.__file__).read_text(encoding="utf-8")
    check(
        "PRODUCTION LIFECYCLE NEVER AUTHORIZES OR RUNS PATCHED CODE",
        {
            "execution_false": '"execution_authorized": False' in production_text,
            "no_python_module": "python_module" not in production_text,
            "no_pipeline": "pipeline" not in production_text,
            "no_shell_true": "shell=True" not in production_text,
            "bounded_forced_cleanup": "runtime.terminate(" in production_text,
            "forced_cleanup_not_success": "and not self.termination.attempted" in production_text,
        },
        {"execution_false": True, "no_python_module": True, "no_pipeline": True, "no_shell_true": True, "bounded_forced_cleanup": True, "forced_cleanup_not_success": True},
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
