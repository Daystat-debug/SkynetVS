from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_boundary_composition as composition_module

from modules.developer.developer_task_execution_backend_host import (
    DeveloperTaskExecutionBackendExecutableEvidence,
    DeveloperTaskExecutionBackendHostReport,
)
from modules.developer.developer_task_execution_backend_lifecycle_windows import (
    DeveloperTaskExecutionBackendProcessEvidence,
    DeveloperTaskExecutionBackendTerminationResult,
)
from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_boundary_composition import (
    ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED,
    ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED,
    ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED_ACTIVE,
    _CompositionRuntime,
    _attest_developer_task_execution_boundary_composition,
    attest_developer_task_execution_boundary_composition,
)
from modules.developer.developer_task_execution_boundary_composition_payload import (
    COMPOSITION_AUTHORIZE_COMMIT_NAME,
    COMPOSITION_AUTHORIZE_NAME,
    COMPOSITION_BOOTSTRAP_NAME,
    COMPOSITION_CONTROLLER_NAME,
    COMPOSITION_READY_NAME,
    COMPOSITION_REQUEST_NAME,
    COMPOSITION_TERMINAL_PAYLOAD_NAME,
    COMPOSITION_TERMINAL_SIGNATURE_NAME,
    COMPOSITION_WORKER_RESULT_NAME,
    COMPOSITION_WSB_NAME,
    DeveloperTaskExecutionBoundaryCompositionPayloadError,
    build_composition_authorize,
    build_composition_bootstrap_script,
    build_composition_controller_script,
    build_composition_request,
    build_composition_wsb_config,
    read_composition_artifact_bytes,
)
from modules.developer.developer_task_execution_boundary_contract import (
    parse_boundary_ready,
    parse_boundary_request,
)
from modules.developer.developer_task_execution_boundary_policy import (
    WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
)
from modules.developer.developer_task_execution_boundary_verifier import (
    verify_developer_task_execution_signed_transcript,
)
from modules.developer.developer_task_execution_boundary_worker import (
    build_developer_task_execution_boundary_worker_bundle,
)


_PUBLIC_BLOB = base64.b64decode(
    "RUNTMSAAAABrF9Hy4SxCR/i85uVjpEDydwN9gS3rM6D0oTlF2JjClk/jQuL+Gn+bjufrSnwPnhYrzjNXazFezsu2QGg3v1H1"
)
_PROCESS = DeveloperTaskExecutionBackendProcessEvidence(
    name="WindowsSandboxRemoteSession.exe",
    pid=4242,
    created_epoch_ns=1786053600000000000,
    executable_path=r"C:\Windows\System32\WindowsSandboxRemoteSession.exe",
)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _host_report(*, issues: tuple[Any, ...] = ()) -> DeveloperTaskExecutionBackendHostReport:
    policy = WINDOWS_SANDBOX_EXECUTION_POLICY_V1
    executable = DeveloperTaskExecutionBackendExecutableEvidence(
        path=r"C:\Windows\System32\WindowsSandbox.exe",
        version="10.0.26100.8875",
        size_bytes=123456,
        mtime_ns=123456789,
        sha256="a" * 64,
    )
    return DeveloperTaskExecutionBackendHostReport(
        backend_id=policy.backend_id,
        policy=policy,
        policy_fingerprint=policy.fingerprint,
        host_platform="win32",
        host_architecture="AMD64",
        process_bitness=64,
        windows_build=26200,
        host_boot_epoch_seconds=1786050000,
        feature_state="enabled",
        feature_probe_error="",
        executable=executable,
        wsb_cli_found=False,
        wsb_cli_path="",
        wsb_cli_probe_error="",
        running_sandbox_processes=(),
        issues=issues,
    )


class _Launcher:
    pid = 5151


class _FakeRuntime(_CompositionRuntime):
    def __init__(self, host: DeveloperTaskExecutionBackendHostReport, *, mode: str = "success") -> None:
        self.host = host
        self.mode = mode
        self.clock = 0.0
        self.base_epoch = 1786053600.0
        self.launched = False
        self.authorized = False
        self.terminal_written = False
        self.root: Path | None = None
        self.launch_calls = 0
        self.publish_calls = 0
        self.pin_calls = 0
        self.verify_calls = 0
        self.terminate_calls = 0
        self.read_counts: dict[str, int] = {}

    def inspect_host(self) -> DeveloperTaskExecutionBackendHostReport:
        if self.mode == "host_changes_after" and self.verify_calls:
            executable = replace(self.host.executable, sha256="b" * 64) if self.host.executable else None
            return replace(self.host, executable=executable)
        return self.host

    def launch(self, _executable: Path, config_path: Path):
        self.launch_calls += 1
        self.launched = True
        self.root = config_path.parent.parent
        if self.mode == "launch_failure":
            raise RuntimeError("fake launch failure")
        return _Launcher()

    def launcher_exited(self, _launcher: Any) -> bool:
        return self.terminal_written

    def terminate(
        self,
        observed: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...],
        *,
        executable: Path,
    ) -> DeveloperTaskExecutionBackendTerminationResult:
        self.terminate_calls += 1
        self.mode = "terminated"
        return DeveloperTaskExecutionBackendTerminationResult(
            attempted=True,
            succeeded=True,
            targeted_processes=observed,
            remaining_processes=(),
            errors=(),
        )

    def snapshot_processes(self) -> tuple[DeveloperTaskExecutionBackendProcessEvidence, ...]:
        if self.mode == "snapshot_failure" and self.launched:
            raise RuntimeError("fake snapshot failure")
        if not self.launched:
            return (_PROCESS,) if self.mode == "baseline_active" else ()
        if self.mode == "shutdown_timeout":
            return (_PROCESS,)
        if self.mode == "terminated":
            return ()
        if self.terminal_written:
            return ()
        return (_PROCESS,)

    def artifact_exists(self, path: Path) -> bool:
        if self.root is None:
            return os.path.lexists(path)
        if path.name == COMPOSITION_TERMINAL_PAYLOAD_NAME and self.mode == "early_terminal":
            path.write_bytes(b"early")
            return True
        if path.name == COMPOSITION_READY_NAME and self.launched and not path.exists():
            if self.mode == "guest_failure_before_ready":
                (self.root / "output" / "controller_failure.json").write_bytes(b'{"failed":true}')
            elif self.mode != "ready_timeout":
                self._write_ready(path)
        return os.path.lexists(path)

    def read_artifact(
        self,
        path: Path,
        *,
        max_bytes: int,
        artifact_name: str,
        expected_size: int | None = None,
    ) -> tuple[bytes, str]:
        self.read_counts[artifact_name] = self.read_counts.get(artifact_name, 0) + 1
        if self.mode == "ready_mutation" and artifact_name == COMPOSITION_READY_NAME and self.read_counts[artifact_name] == 2:
            payload = json.loads(path.read_bytes())
            payload["controller_name"] = r"NT AUTHORITY\MUTATE"
            path.write_bytes(_canonical(payload))
        if self.mode == "post_exit_ready_mutation" and artifact_name == COMPOSITION_READY_NAME and self.read_counts[artifact_name] >= 3:
            payload = json.loads(path.read_bytes())
            payload["controller_name"] = r"NT AUTHORITY\POSTEX"
            path.write_bytes(_canonical(payload))
        return super().read_artifact(
            path,
            max_bytes=max_bytes,
            artifact_name=artifact_name,
            expected_size=expected_size,
        )

    def publish_authorize(self, path: Path, data: bytes) -> None:
        self.publish_calls += 1
        super().publish_authorize(path, data)
        self.authorized = True
        if self.mode not in {"terminal_timeout", "shutdown_timeout"}:
            self._write_terminal(data)
        elif self.mode == "shutdown_timeout":
            self._write_terminal(data)

    def pin_transcript(self, **kwargs: Any):
        self.pin_calls += 1
        if self.mode == "pin_failure":
            kwargs["expected_host_nonce"] = "f" * 64
        return super().pin_transcript(**kwargs)

    def verify_transcript(self, *args: Any, **kwargs: Any):
        self.verify_calls += 1
        if self.mode == "signature_failure":
            kwargs["signature_verifier"] = lambda *_args: False
        else:
            kwargs["signature_verifier"] = lambda *_args: True
        return verify_developer_task_execution_signed_transcript(*args, **kwargs)

    def monotonic(self) -> float:
        return self.clock

    def epoch(self) -> float:
        return self.base_epoch + self.clock

    def sleep(self, seconds: float) -> None:
        self.clock += max(seconds, 1.0)

    def _write_ready(self, path: Path) -> None:
        request_bytes = (self.root / "input" / COMPOSITION_REQUEST_NAME).read_bytes()  # type: ignore[operator]
        request = json.loads(request_bytes)
        public_hash = _sha256(_PUBLIC_BLOB)
        ready = {
            "schema_version": 1,
            "backend_id": request["backend_id"],
            "base_policy_fingerprint": request["base_policy_fingerprint"],
            "boundary_id": request["boundary_id"],
            "boundary_fingerprint": request["boundary_fingerprint"],
            "request_id": request["request_id"],
            "host_nonce": request["host_nonce"],
            "request_sha256": _sha256(request_bytes),
            "policy_sha256": request["policy_sha256"],
            "bootstrap_sha256": request["bootstrap_sha256"],
            "controller_sha256": request["controller_sha256"],
            "worker_source_sha256": request["worker_source_sha256"],
            "wsb_sha256": request["wsb_sha256"],
            "controller_sid": "S-1-5-18",
            "controller_name": r"NT AUTHORITY\SYSTEM",
            "controller_is_system": True,
            "controller_is_administrator": True,
            "controller_integrity_rid": 0x4000,
            "key_is_ephemeral": True,
            "key_name_empty": True,
            "key_unique_name_empty": True,
            "public_key_format": "EccPublicBlob",
            "public_key_blob_base64": base64.b64encode(_PUBLIC_BLOB).decode("ascii"),
            "public_key_sha256": public_hash,
            "input_write_blocked": True,
            "control_write_blocked": True,
            "output_writable": True,
            "bootstrap_task_deleted": True,
            "ready_checks": {
                "controller_is_system": True,
                "controller_is_administrator": True,
                "controller_integrity_is_system": True,
                "key_is_ephemeral": True,
                "key_name_empty": True,
                "key_unique_name_empty": True,
                "input_write_blocked": True,
                "control_write_blocked": True,
                "output_writable": True,
            },
            "failed_ready_checks": [],
            "created_at_utc": _utc(self.epoch() + 1),
            "overall_ok": True,
            "execution_authorized": False,
        }
        path.write_bytes(_canonical(ready))

    def _write_terminal(self, authorize_bytes: bytes) -> None:
        assert self.root is not None
        input_root = self.root / "input"
        output_root = self.root / "output"
        request_bytes = (input_root / COMPOSITION_REQUEST_NAME).read_bytes()
        ready_bytes = (output_root / COMPOSITION_READY_NAME).read_bytes()
        request = json.loads(request_bytes)
        ready = json.loads(ready_bytes)
        authorize = json.loads(authorize_bytes)
        worker_result = {
            "schema_version": 1,
            "request_id": request["request_id"],
            "worker_sid": "S-1-5-21-1-2-3-1000",
            "worker_name": r"TEST\svb3worker",
            "worker_is_administrator": False,
            "worker_integrity_rid": 0x2000,
            "controller_secret_absent": True,
            "sentinel_handle_inherited": False,
            "controller_vm_read_blocked": True,
            "input_write_blocked": True,
            "control_write_blocked": True,
            "output_writable": True,
            "worker_in_job": True,
            "child_pid": 1234,
            "child_in_job": True,
            "overall_ok": True,
        }
        worker_result_bytes = _canonical(worker_result)
        terminal = {
            "schema_version": 1,
            "backend_id": request["backend_id"],
            "base_policy_fingerprint": request["base_policy_fingerprint"],
            "boundary_id": request["boundary_id"],
            "boundary_fingerprint": request["boundary_fingerprint"],
            "request_id": request["request_id"],
            "host_nonce": request["host_nonce"],
            "authorization_nonce": authorize["authorization_nonce"],
            "request_sha256": _sha256(request_bytes),
            "ready_sha256": _sha256(ready_bytes),
            "authorize_sha256": _sha256(authorize_bytes),
            "policy_sha256": request["policy_sha256"],
            "bootstrap_sha256": request["bootstrap_sha256"],
            "controller_sha256": request["controller_sha256"],
            "worker_source_sha256": request["worker_source_sha256"],
            "wsb_sha256": request["wsb_sha256"],
            "worker_result_sha256": _sha256(worker_result_bytes),
            "public_key_sha256": ready["public_key_sha256"],
            "controller": {
                "sid": "S-1-5-18",
                "name": r"NT AUTHORITY\SYSTEM",
                "is_system": True,
                "is_administrator": True,
                "integrity_rid": 0x4000,
                "key_is_ephemeral": True,
                "key_name_empty": True,
                "key_unique_name_empty": True,
            },
            "worker": {
                "account_created": True,
                "sid": worker_result["worker_sid"],
                "created_suspended": True,
                "resume_previous_count": 1,
                "assigned_before_resume": True,
                "result_ok": True,
                "exit_code": 0,
                "is_administrator": False,
                "integrity_rid": 0x2000,
                "controller_secret_absent": True,
                "sentinel_handle_inherited": False,
                "controller_vm_read_blocked": True,
                "worker_in_job": True,
                "child_pid": 1234,
                "child_in_job": True,
                "child_in_specific_job": True,
                "job_closed": True,
                "child_killed_by_job_close": True,
                "sid_process_set_empty": True,
                "account_deleted": True,
            },
            "controls": {
                "input_write_blocked": True,
                "control_write_blocked": True,
                "output_writable": True,
                "ipv4_default_route_present": False,
                "ipv4_external_tcp_reachable": False,
                "ipv6_default_route_present": False,
                "ipv6_external_tcp_reachable": False,
            },
            "shutdown": {"scheduled": True, "delay_seconds": 8},
            "completed_at_utc": _utc(self.epoch() + 2),
            "overall_ok": True,
            "execution_authorized": False,
        }
        (output_root / COMPOSITION_WORKER_RESULT_NAME).write_bytes(worker_result_bytes)
        (output_root / COMPOSITION_TERMINAL_PAYLOAD_NAME).write_bytes(_canonical(terminal))
        (output_root / COMPOSITION_TERMINAL_SIGNATURE_NAME).write_bytes(b"\x01" * 64)
        self.terminal_written = True


def _is_frozen(value: Any) -> bool:
    try:
        setattr(value, "status", "mutated")
    except (FrozenInstanceError, AttributeError, TypeError):
        return True
    return False


def _raises_type(callable_: Any, error_type: type[BaseException]) -> bool:
    try:
        callable_()
    except error_type:
        return True
    except Exception:
        return False
    return False


def _run(mode: str = "success"):
    host = _host_report()
    runtime = _FakeRuntime(host, mode=mode)
    with tempfile.TemporaryDirectory(prefix="skynetvs-v1b3d-eval-parent-") as temporary:
        report = _attest_developer_task_execution_boundary_composition(
            host,
            artifact_parent=Path(temporary),
            runtime=runtime,
        )
    return report, runtime


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

    backend = WINDOWS_SANDBOX_EXECUTION_POLICY_V1
    boundary = WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1
    bundle = build_developer_task_execution_boundary_worker_bundle()
    bootstrap = build_composition_bootstrap_script()
    controller = build_composition_controller_script(
        backend_policy=backend,
        boundary_policy=boundary,
        worker_bundle=bundle,
    )

    request = build_composition_request(
        backend_policy=backend,
        boundary_policy=boundary,
        request_id="1" * 32,
        host_nonce="2" * 64,
        created_at_epoch_seconds=1786053600.0,
        policy_sha256=_sha256(boundary.canonical_bytes()),
        bootstrap_sha256=_sha256(bootstrap),
        controller_sha256=_sha256(controller),
        worker_source_sha256=bundle.worker_probe.sha256,
        wsb_sha256="3" * 64,
    )
    check("V1B3D REQUEST IS CANONICAL AND FAIL CLOSED", {"kind": request.kind, "canonical": request.canonical_bytes == _canonical(request.to_dict()), "execution_authorized": request.field("execution_authorized")}, {"kind": "request", "canonical": True, "execution_authorized": False})
    check("V1B3D REQUEST IDENTIFIERS ARE STRICT", _raises_type(lambda: build_composition_request(backend_policy=backend, boundary_policy=boundary, request_id="bad", host_nonce="2" * 64, created_at_epoch_seconds=1786053600.0, policy_sha256="a" * 64, bootstrap_sha256="b" * 64, controller_sha256="c" * 64, worker_source_sha256="d" * 64, wsb_sha256="e" * 64), DeveloperTaskExecutionBoundaryCompositionPayloadError), True)

    fake_ready_runtime = _FakeRuntime(_host_report())
    with tempfile.TemporaryDirectory() as temporary:
        fake_ready_runtime.root = Path(temporary)
        (fake_ready_runtime.root / "input").mkdir()
        (fake_ready_runtime.root / "output").mkdir()
        (fake_ready_runtime.root / "input" / COMPOSITION_REQUEST_NAME).write_bytes(request.canonical_bytes)
        fake_ready_runtime._write_ready(fake_ready_runtime.root / "output" / COMPOSITION_READY_NAME)
        ready = parse_boundary_ready((fake_ready_runtime.root / "output" / COMPOSITION_READY_NAME).read_bytes())
    authorize = build_composition_authorize(request=request, ready=ready, authorization_nonce="4" * 64, authorization_deadline_epoch=1786053690)
    check("V1B3D AUTHORIZATION BINDS PINNED READY WITHOUT EXECUTION", {"ready": authorize.field("ready_sha256") == ready.sha256, "worker": authorize.field("allow_benign_worker"), "execution_authorized": authorize.field("execution_authorized")}, {"ready": True, "worker": True, "execution_authorized": False})

    check("V1B3D BOOTSTRAP IS DETERMINISTIC UTF8 LF", {"stable": bootstrap == build_composition_bootstrap_script(), "bom": bootstrap.startswith(b"\xef\xbb\xbf"), "cr": b"\r" in bootstrap, "lf": bootstrap.endswith(b"\n")}, {"stable": True, "bom": False, "cr": False, "lf": True})
    check("V1B3D CONTROLLER BINDS EXACT V1B3C PAYLOAD", {"native_hash": bundle.native_helper.sha256.encode() in controller, "worker_hash": bundle.worker_probe.sha256.encode() in controller, "bundle_hash": bundle.bundle_fingerprint.encode() in controller, "fixed_worker": bundle.worker_executable_file_name.encode() in controller}, {"native_hash": True, "worker_hash": True, "bundle_hash": True, "fixed_worker": True})
    check("V1B3D CONTROLLER USES TRUE EPHEMERAL CNG KEY", {"typed_null": b"(string)null" in controller, "nonexportable": b"CngExportPolicies.None" in controller, "is_ephemeral": b"IsEphemeral" in controller}, {"typed_null": True, "nonexportable": True, "is_ephemeral": True})
    check("V1B3D CONTROLLER PROBES SYSTEM INTEGRITY FROM TOKEN", {"token_info": b"GetTokenInformation" in controller, "integrity_class": b"TokenIntegrityLevel" in controller, "helper_call": b"GetCurrentIntegrityRid" in controller, "groups_scan_absent": b"identity.Groups" not in controller}, {"token_info": True, "integrity_class": True, "helper_call": True, "groups_scan_absent": True})
    check("V1B3D CONTROLLER HAS FIXED BENIGN SCOPE ONLY", {"patch": b"changes.patch" in controller, "workspace": b"workspace" in controller.lower(), "python_module": b"python_module" in controller, "pipeline": b"pipeline" in controller, "worker": b"allow_benign_worker" in controller}, {"patch": False, "workspace": False, "python_module": False, "pipeline": False, "worker": True})
    check("V1B3D CONTROLLER CLOSES JOB AND DELETES EXACT ACCOUNT BEFORE SIGNING", {"job_before_sign": controller.index(b"$jobClosed = $true") < controller.index(b"$signatureBytes = $ecdsa.SignHash"), "delete_before_sign": controller.index(b"DeleteLocalUserExact") < controller.index(b"$signatureBytes = $ecdsa.SignHash"), "sid_sweep": b"WaitForWorkerSidQuiescence" in controller}, {"job_before_sign": True, "delete_before_sign": True, "sid_sweep": True})
    check(
        "V1B3D CONTROLLER REQUIRES VERIFIED AUTHORIZATION HASH COMMIT",
        {
            "commit_path": b'Join-Path $controlRoot "authorize.sha256"' in controller,
            "waits_for_commit": b"Test-Path -LiteralPath $authorizeCommitPath -PathType Leaf" in controller,
            "strict_commit_size": b"$commitBytes.Length -ne 64" in controller,
            "strict_lower_hex": b'^[0-9a-f]{64}$' in controller,
            "hash_match": b"$candidateSha256 -cne $commitText" in controller,
            "verified_before_parse": controller.index(b"$candidateSha256 -cne $commitText") < controller.index(b"$authorize = $authorizeText | ConvertFrom-Json"),
        },
        {
            "commit_path": True,
            "waits_for_commit": True,
            "strict_commit_size": True,
            "strict_lower_hex": True,
            "hash_match": True,
            "verified_before_parse": True,
        },
    )

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        input_root = (root / "input").resolve(); input_root.mkdir()
        control_root = (root / "control").resolve(); control_root.mkdir()
        output_root = (root / "output").resolve(); output_root.mkdir()
        wsb = build_composition_wsb_config(backend, input_root=input_root, control_root=control_root, output_root=output_root)
    check("V1B3D WSB USES EXACT SECURITY AND THREE MAPPINGS", {"network": b"<Networking>Disable</Networking>" in wsb, "protected": b"<ProtectedClient>Enable</ProtectedClient>" in wsb, "input_ro": wsb.count(b"<ReadOnly>true</ReadOnly>") == 2, "output_rw": b"<ReadOnly>false</ReadOnly>" in wsb, "logon": b"bootstrap.ps1" in wsb}, {"network": True, "protected": True, "input_ro": True, "output_rw": True, "logon": True})

    with tempfile.TemporaryDirectory() as temporary:
        artifact = Path(temporary) / "artifact.bin"
        artifact.write_bytes(b"exact-bytes")
        raw, digest = read_composition_artifact_bytes(artifact, max_bytes=64, artifact_name="artifact")
    check("V1B3D ARTIFACT READER RETURNS EXACT BYTES", {"raw": raw, "hash": digest}, {"raw": b"exact-bytes", "hash": _sha256(b"exact-bytes")})
    with tempfile.TemporaryDirectory() as temporary:
        empty = Path(temporary) / "empty.bin"; empty.write_bytes(b"")
        empty_rejected = _raises_type(lambda: read_composition_artifact_bytes(empty, max_bytes=64, artifact_name="empty"), DeveloperTaskExecutionBoundaryCompositionPayloadError)
    check("V1B3D ARTIFACT READER REJECTS EMPTY INPUT", empty_rejected, True)

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        control = root / "control"
        control.mkdir()
        target = control / COMPOSITION_AUTHORIZE_NAME
        commit = control / COMPOSITION_AUTHORIZE_COMMIT_NAME
        write_order: list[str] = []
        real_write = composition_module._write_new_file

        def capture_write(path: Path, data: bytes) -> None:
            write_order.append(Path(path).name)
            real_write(path, data)

        with (
            patch.object(composition_module, "_write_new_file", side_effect=capture_write),
            patch.object(composition_module.os, "replace") as replace_mock,
        ):
            composition_module._write_committed_authorization(target, b"authorization")

        direct_commit_result = {
            "write_order": write_order,
            "authorization": target.read_bytes(),
            "commit": commit.read_bytes(),
            "commit_length": commit.stat().st_size,
            "replace_calls": replace_mock.call_count,
        }
    check(
        "V1B3D AUTHORIZATION USES DIRECT DATA THEN SHA256 COMMIT",
        direct_commit_result,
        {
            "write_order": [COMPOSITION_AUTHORIZE_NAME, COMPOSITION_AUTHORIZE_COMMIT_NAME],
            "authorization": b"authorization",
            "commit": _sha256(b"authorization").encode("ascii"),
            "commit_length": 64,
            "replace_calls": 0,
        },
    )

    preexisting_results: dict[str, dict[str, Any]] = {}
    for existing_name in (COMPOSITION_AUTHORIZE_NAME, COMPOSITION_AUTHORIZE_COMMIT_NAME):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            control = root / "control"
            control.mkdir()
            target = control / COMPOSITION_AUTHORIZE_NAME
            commit = control / COMPOSITION_AUTHORIZE_COMMIT_NAME
            existing = control / existing_name
            existing.write_bytes(b"existing")
            failure_code = ""
            try:
                composition_module._write_committed_authorization(target, b"authorization")
            except DeveloperTaskExecutionBoundaryCompositionPayloadError as exc:
                failure_code = exc.code
            preexisting_results[existing_name] = {
                "failure_code": failure_code,
                "existing_preserved": existing.read_bytes() == b"existing",
                "other_absent": not (commit if existing == target else target).exists(),
            }
    check(
        "V1B3D PREEXISTING AUTHORIZATION DATA OR COMMIT FAILS CLOSED",
        preexisting_results,
        {
            COMPOSITION_AUTHORIZE_NAME: {
                "failure_code": "boundary_composition_authorization_already_exists",
                "existing_preserved": True,
                "other_absent": True,
            },
            COMPOSITION_AUTHORIZE_COMMIT_NAME: {
                "failure_code": "boundary_composition_authorization_already_exists",
                "existing_preserved": True,
                "other_absent": True,
            },
        },
    )

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        control = root / "control"
        control.mkdir()
        target = control / COMPOSITION_AUTHORIZE_NAME
        commit = control / COMPOSITION_AUTHORIZE_COMMIT_NAME
        failure_code = ""
        try:
            with patch.object(
                composition_module,
                "read_composition_artifact_bytes",
                side_effect=DeveloperTaskExecutionBoundaryCompositionPayloadError(
                    "boundary_composition_artifact_read_failed",
                    "simulated authorization verification failure",
                ),
            ):
                composition_module._write_committed_authorization(target, b"authorization")
        except DeveloperTaskExecutionBoundaryCompositionPayloadError as exc:
            failure_code = exc.code
        verification_failure_result = {
            "failure_code": failure_code,
            "authorization_present": target.read_bytes() == b"authorization",
            "commit_absent": not commit.exists(),
        }
    check(
        "V1B3D AUTHORIZATION VERIFICATION FAILURE NEVER PUBLISHES COMMIT",
        verification_failure_result,
        {
            "failure_code": "boundary_composition_authorization_publish_failed",
            "authorization_present": True,
            "commit_absent": True,
        },
    )

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        control = root / "control"
        control.mkdir()
        target = control / COMPOSITION_AUTHORIZE_NAME
        commit = control / COMPOSITION_AUTHORIZE_COMMIT_NAME
        real_write = composition_module._write_new_file
        write_calls = 0
        failure_code = ""

        def fail_commit_write(path: Path, data: bytes) -> None:
            nonlocal write_calls
            write_calls += 1
            if write_calls == 2:
                raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                    "boundary_composition_artifact_write_failed",
                    "simulated commit write failure",
                )
            real_write(path, data)

        try:
            with patch.object(composition_module, "_write_new_file", side_effect=fail_commit_write):
                composition_module._write_committed_authorization(target, b"authorization")
        except DeveloperTaskExecutionBoundaryCompositionPayloadError as exc:
            failure_code = exc.code
        commit_failure_result = {
            "write_calls": write_calls,
            "failure_code": failure_code,
            "authorization_present": target.read_bytes() == b"authorization",
            "commit_absent": not commit.exists(),
        }
    check(
        "V1B3D COMMIT WRITE FAILURE LEAVES AUTHORIZATION UNCOMMITTED",
        commit_failure_result,
        {
            "write_calls": 2,
            "failure_code": "boundary_composition_authorization_publish_failed",
            "authorization_present": True,
            "commit_absent": True,
        },
    )

    source = Path(composition_module.__file__).read_text(encoding="utf-8")
    check("V1B3D HOST PINS BEFORE AUTHORIZATION PUBLICATION", source.index("runtime.pin_transcript(") < source.index("runtime.publish_authorize("), True)
    check("V1B3D HOST VERIFIES ONLY AFTER PROVEN SANDBOX EXIT", source.index("if not context.all_processes_exited:") < source.index("runtime.verify_transcript("), True)
    check("V1B3D HOST NEVER AUTHORIZES PATCHED EXECUTION", {"execution_true": "execution_authorized = True" in source or '"execution_authorized": True' in source, "manifest": "manifest" in source, "workspace_input": "workspace_report" in source, "host_fallback": "host fallback" in source.lower()}, {"execution_true": False, "manifest": False, "workspace_input": False, "host_fallback": False})

    check("V1B3D USES ONE SANDBOX RUN INSTEAD OF REUSING V1B2 ATTESTATION", {"v1b2_attest": "attest_developer_task_execution_backend_lifecycle" in source, "launch_call": "runtime.launch(" in source, "post_exit_verify": "runtime.verify_transcript(" in source}, {"v1b2_attest": False, "launch_call": True, "post_exit_verify": True})

    report, runtime = _run("success")
    check("SIMULATED ACTIVE SIGNED COMPOSITION PASSES", {"ok": report.ok, "status": report.status, "pin": bool(report.pin_report and report.pin_report.ok), "signed": bool(report.signed_report and report.signed_report.ok), "exited": report.all_processes_exited, "removed": bool(report.artifacts and report.artifacts.removed), "authorized": report.execution_authorized}, {"ok": True, "status": ACTIVE_SIGNED_BOUNDARY_STATUS_ATTESTED, "pin": True, "signed": True, "exited": True, "removed": True, "authorized": False})
    check("COMPOSITION REPORT IS IMMUTABLE AND SERIALIZABLE", {"immutable": _is_frozen(report), "json": bool(json.dumps(report.to_dict())), "timeline": len(report.process_timeline) >= 2}, {"immutable": True, "json": True, "timeline": True})
    check("SUCCESS PUBLISHES AUTHORIZATION ONLY AFTER PIN", {"pin_calls": runtime.pin_calls, "publish_calls": runtime.publish_calls, "verify_calls": runtime.verify_calls}, {"pin_calls": 1, "publish_calls": 1, "verify_calls": 1})

    failed_pin, failed_pin_runtime = _run("pin_failure")
    check("PIN FAILURE BLOCKS AUTHORIZATION", {"ok": failed_pin.ok, "status": failed_pin.status, "publish": failed_pin_runtime.publish_calls, "codes": "boundary_transcript_mismatch" in failed_pin.issue_codes}, {"ok": False, "status": ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED, "publish": 0, "codes": True})
    mutated_ready, mutated_runtime = _run("ready_mutation")
    check("READY MUTATION BEFORE PUBLICATION FAILS CLOSED", {"ok": mutated_ready.ok, "publish": mutated_runtime.publish_calls, "code": "boundary_composition_ready_changed_before_authorization" in mutated_ready.issue_codes}, {"ok": False, "publish": 0, "code": True})
    early, early_runtime = _run("early_terminal")
    check("TERMINAL BEFORE AUTHORIZATION FAILS CLOSED", {"ok": early.ok, "publish": early_runtime.publish_calls, "code": "boundary_composition_terminal_before_authorization" in early.issue_codes}, {"ok": False, "publish": 0, "code": True})
    guest_failure, _ = _run("guest_failure_before_ready")
    check("GUEST FAILURE BEFORE READY IS STRUCTURED", {"ok": guest_failure.ok, "code": "boundary_composition_guest_failure_reported" in guest_failure.issue_codes, "exited": guest_failure.all_processes_exited}, {"ok": False, "code": True, "exited": True})
    signature_failure, _ = _run("signature_failure")
    check("INVALID TERMINAL SIGNATURE FAILS CLOSED", {"ok": signature_failure.ok, "code": "boundary_signature_invalid" in signature_failure.issue_codes}, {"ok": False, "code": True})
    post_mutation, _ = _run("post_exit_ready_mutation")
    check("POST-EXIT PINNED ARTIFACT MUTATION IS REJECTED", {"ok": post_mutation.ok, "code": "boundary_composition_pinned_artifact_changed" in post_mutation.issue_codes}, {"ok": False, "code": True})
    timeout, timeout_runtime = _run("shutdown_timeout")
    check("SHUTDOWN TIMEOUT USES FAILURE-ONLY FORCED CLEANUP", {"ok": timeout.ok, "status": timeout.status, "termination": timeout.termination.attempted, "terminate_calls": timeout_runtime.terminate_calls, "code": "boundary_composition_shutdown_timeout" in timeout.issue_codes}, {"ok": False, "status": ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED, "termination": True, "terminate_calls": 1, "code": True})
    snapshot_failure, _ = _run("snapshot_failure")
    check("UNPROVEN PROCESS STATE RETURNS FAILED ACTIVE", {"ok": snapshot_failure.ok, "status": snapshot_failure.status, "code": "boundary_composition_process_state_unproven" in snapshot_failure.issue_codes}, {"ok": False, "status": ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED_ACTIVE, "code": True})
    host_drift, _ = _run("host_changes_after")
    check("HOST EVIDENCE DRIFT AFTER RUN FAILS CLOSED", {"ok": host_drift.ok, "code": "execution_backend_host_evidence_changed" in host_drift.issue_codes}, {"ok": False, "code": True})
    launch_failure, launch_runtime = _run("launch_failure")
    check("SANDBOX LAUNCH FAILURE IS CONTAINED", {"ok": launch_failure.ok, "launch_calls": launch_runtime.launch_calls, "authorized": launch_failure.execution_authorized}, {"ok": False, "launch_calls": 1, "authorized": False})
    baseline_active, baseline_runtime = _run("baseline_active")
    check("EXISTING SANDBOX INSTANCE BLOCKS V1B3D", {"ok": baseline_active.ok, "launch_calls": baseline_runtime.launch_calls, "code": "boundary_composition_sandbox_instance_running" in baseline_active.issue_codes}, {"ok": False, "launch_calls": 0, "code": True})
    terminal_timeout, terminal_runtime = _run("terminal_timeout")
    check("TERMINAL TIMEOUT NEVER BECOMES SUCCESS", {"ok": terminal_timeout.ok, "publish": terminal_runtime.publish_calls, "code": "boundary_composition_terminal_timeout" in terminal_timeout.issue_codes, "forced": terminal_timeout.termination.attempted}, {"ok": False, "publish": 1, "code": True, "forced": True})
    with patch.object(
        composition_module,
        "_cleanup_artifacts",
        side_effect=DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_cleanup_failed",
            "fake cleanup failure",
        ),
    ):
        cleanup_failure, _ = _run("success")
    check("ARTIFACT CLEANUP FAILURE INVALIDATES SUCCESS", {"ok": cleanup_failure.ok, "status": cleanup_failure.status, "removed": bool(cleanup_failure.artifacts and cleanup_failure.artifacts.removed), "code": "boundary_composition_artifact_cleanup_failed" in cleanup_failure.issue_codes}, {"ok": False, "status": ACTIVE_SIGNED_BOUNDARY_STATUS_FAILED, "removed": False, "code": True})

    bad_host = replace(_host_report(), feature_state="disabled")
    bad_runtime = _FakeRuntime(bad_host)
    with tempfile.TemporaryDirectory() as temporary:
        bad_report = _attest_developer_task_execution_boundary_composition(bad_host, artifact_parent=Path(temporary), runtime=bad_runtime)
    check("FAILED HOST REPORT BLOCKS LAUNCH", {"ok": bad_report.ok, "launch_calls": bad_runtime.launch_calls, "code": "execution_backend_host_report_failed" in bad_report.issue_codes}, {"ok": False, "launch_calls": 0, "code": True})

    check("PUBLIC API REJECTS RAW HOST REPORT", _raises_type(lambda: attest_developer_task_execution_boundary_composition({}, artifact_parent=Path(".")), TypeError), True)
    check("PUBLIC API REJECTS STRING ARTIFACT PARENT", _raises_type(lambda: attest_developer_task_execution_boundary_composition(_host_report(), artifact_parent="."), TypeError), True)

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
