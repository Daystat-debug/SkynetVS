from __future__ import annotations

import inspect
import json
import os
import tempfile

from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import modules.developer.developer_task_execution_runtime_composition as composition_module
import tools.eval_developer_task_execution_runtime_attestation_verifier as verifier_fixture

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
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
    build_developer_task_execution_runtime_attestation_payload,
)
from modules.developer.developer_task_execution_runtime_attestation_contract import (
    parse_runtime_attestation_authorize,
    parse_runtime_attestation_ready,
    parse_runtime_attestation_request,
    parse_runtime_attestation_result,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME,
    RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME,
    RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME,
    RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME,
    RUNTIME_ATTESTATION_CONTROLLER_FAILURE_FILE_NAME,
    RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME,
    RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME,
    RUNTIME_ATTESTATION_POLICY_FILE_NAME,
    RUNTIME_ATTESTATION_READY_FILE_NAME,
    RUNTIME_ATTESTATION_REQUEST_FILE_NAME,
    RUNTIME_ATTESTATION_RESULT_FILE_NAME,
    RUNTIME_ATTESTATION_SIGNATURE_FILE_NAME,
    RUNTIME_ATTESTATION_TERMINAL_FILE_NAME,
    RUNTIME_ATTESTATION_WSB_FILE_NAME,
    build_runtime_attestation_request,
    build_runtime_attestation_wsb_config,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_verifier import (
    verify_developer_task_execution_runtime_attestation_transcript,
)
from modules.developer.developer_task_execution_runtime_composition import (
    ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED,
    ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED,
    ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE,
    _RuntimeCompositionRuntime,
    _attest_developer_task_execution_runtime_composition,
    attest_developer_task_execution_runtime_composition,
)
from modules.developer.developer_task_execution_runtime_composition_fs import (
    RUNTIME_COMPOSITION_ARTIFACT_PREFIX,
    DeveloperTaskExecutionRuntimeCompositionFileEvidence,
    DeveloperTaskExecutionRuntimeCompositionFileSystemError,
    DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence,
    DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts,
    publish_developer_task_execution_runtime_composition_authorization,
    read_developer_task_execution_runtime_composition_artifact_bytes,
    remove_developer_task_execution_runtime_composition_artifacts,
    validate_developer_task_execution_runtime_composition_artifact_parent,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_TREE_MANIFEST_SHA256,
)


_PROCESS = DeveloperTaskExecutionBackendProcessEvidence(
    name="WindowsSandboxRemoteSession.exe",
    pid=4242,
    created_epoch_ns=1786559400000000000,
    executable_path=r"C:\Windows\System32\WindowsSandboxRemoteSession.exe",
)


@dataclass(frozen=True)
class _FakeBundleReport:
    source_sha256: str = RUNTIME_SOURCE_SHA256
    bundle_fingerprint: str = RUNTIME_BUNDLE_FINGERPRINT


@dataclass(frozen=True)
class _FakeBundle:
    ok: bool = True
    report: _FakeBundleReport = _FakeBundleReport()


class _Launcher:
    pid = 5151


class _FakeRuntime(_RuntimeCompositionRuntime):
    def __init__(
        self,
        host: DeveloperTaskExecutionBackendHostReport,
        *,
        mode: str = "success",
    ) -> None:
        self.host = host
        self.mode = mode
        self.clock = 0.0
        self.base_epoch = (
            1786559400.75
            if mode == "subsecond_authorization_timing"
            else 1786559400.0
        )
        self.launched = False
        self.authorized = False
        self.terminal_written = False
        self.root: Path | None = None
        self.prepared: DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts | None = None
        self.launch_calls = 0
        self.publish_calls = 0
        self.pin_calls = 0
        self.verify_calls = 0
        self.materialization_calls = 0
        self.terminate_calls = 0
        self.cleanup_calls = 0
        self.read_counts: dict[str, int] = {}
        self.inspect_calls = 0
        self.post_terminal_snapshot_calls = 0
        self.launcher_exit_ready_at = 0.0
        self.authorization_observed_epochs: list[float] = []

    def inspect_host(self) -> DeveloperTaskExecutionBackendHostReport:
        self.inspect_calls += 1
        if self.mode == "boot_epoch_quantization_jitter":
            return replace(
                self.host,
                host_boot_epoch_seconds=(
                    self.host.host_boot_epoch_seconds
                    + (self.inspect_calls % 2)
                ),
            )
        if (
            self.mode == "boot_epoch_drift_before_launch"
            and self.inspect_calls >= 2
        ):
            return replace(
                self.host,
                host_boot_epoch_seconds=(
                    self.host.host_boot_epoch_seconds + 2
                ),
            )
        if self.mode == "host_changes_after" and self.verify_calls:
            executable = (
                replace(self.host.executable, sha256="b" * 64)
                if self.host.executable is not None
                else None
            )
            return replace(self.host, executable=executable)
        return self.host

    def build_runtime_bundle(self, runtime_zip: Path, *, artifact_parent: Path) -> Any:
        if self.mode == "runtime_bundle_failure":
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_runtime_bundle_failed",
                "fake runtime bundle failure",
            )
        if self.mode == "runtime_bundle_invalid":
            return _FakeBundle(ok=False)
        return _FakeBundle()

    def build_payload_bundle(self) -> Any:
        bundle = build_developer_task_execution_runtime_attestation_payload()
        if self.mode == "payload_bundle_invalid":
            return replace(bundle, payload_fingerprint="0" * 64)
        return bundle

    def prepare_artifacts(self, **kwargs: Any) -> Any:
        if self.mode == "prepare_failure":
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_artifact_write_failed",
                "fake preparation failure",
            )
        parent = Path(kwargs["artifact_parent"])
        request_id = kwargs["request_id"]
        host_nonce = kwargs["host_nonce"]
        payload = kwargs["payload_bundle"]
        runtime_bundle = kwargs["runtime_bundle"]
        root = parent / f"{RUNTIME_COMPOSITION_ARTIFACT_PREFIX}{request_id[:8]}-fake"
        root.mkdir()
        input_root = root / "input"
        runtime_root = root / "runtime"
        control_root = root / "control"
        output_root = root / "output"
        for directory in (input_root, runtime_root, control_root, output_root):
            directory.mkdir()

        wsb_bytes = build_runtime_attestation_wsb_config(
            input_host_path=r"C:\SkynetVSTest\Input",
            runtime_host_path=r"C:\SkynetVSTest\Runtime",
            control_host_path=r"C:\SkynetVSTest\Control",
            output_host_path=r"C:\SkynetVSTest\Output",
        )
        input_data = {
            RUNTIME_ATTESTATION_POLICY_FILE_NAME: payload.exact_bytes(
                RUNTIME_ATTESTATION_POLICY_FILE_NAME
            ),
            RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME: payload.exact_bytes(
                RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME
            ),
            RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME: payload.exact_bytes(
                RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME
            ),
            RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME: payload.exact_bytes(
                RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME
            ),
            RUNTIME_ATTESTATION_WSB_FILE_NAME: wsb_bytes,
        }
        for name, data in input_data.items():
            (input_root / name).write_bytes(data)
        request = build_runtime_attestation_request(
            request_id=request_id,
            host_nonce=host_nonce,
            created_at_epoch_seconds=kwargs["created_at_epoch_seconds"],
            policy_sha256=composition_module._sha256(
                input_data[RUNTIME_ATTESTATION_POLICY_FILE_NAME]
            ),
            bootstrap_sha256=composition_module._sha256(
                input_data[RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME]
            ),
            controller_sha256=composition_module._sha256(
                input_data[RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME]
            ),
            native_helper_sha256=composition_module._sha256(
                input_data[RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME]
            ),
            wsb_sha256=composition_module._sha256(wsb_bytes),
        )
        request_path = input_root / RUNTIME_ATTESTATION_REQUEST_FILE_NAME
        request_path.write_bytes(request.canonical_bytes)
        (runtime_root / "runtime.placeholder").write_bytes(b"fixed-runtime")
        prepared = DeveloperTaskExecutionRuntimeCompositionPreparedArtifacts(
            root=root,
            root_metadata=os.lstat(root),
            input_root=input_root,
            runtime_root=runtime_root,
            control_root=control_root,
            output_root=output_root,
            request_path=request_path,
            ready_path=output_root / RUNTIME_ATTESTATION_READY_FILE_NAME,
            authorize_path=control_root / RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME,
            authorize_commit_path=control_root
            / RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME,
            runtime_result_path=output_root / RUNTIME_ATTESTATION_RESULT_FILE_NAME,
            terminal_payload_path=output_root / RUNTIME_ATTESTATION_TERMINAL_FILE_NAME,
            terminal_signature_path=output_root / RUNTIME_ATTESTATION_SIGNATURE_FILE_NAME,
            bootstrap_failure_path=output_root
            / RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME,
            controller_failure_path=output_root
            / RUNTIME_ATTESTATION_CONTROLLER_FAILURE_FILE_NAME,
            policy_path=input_root / RUNTIME_ATTESTATION_POLICY_FILE_NAME,
            bootstrap_path=input_root / RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME,
            controller_path=input_root / RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME,
            native_helper_path=input_root / RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME,
            wsb_path=input_root / RUNTIME_ATTESTATION_WSB_FILE_NAME,
            request=request,
            runtime_files=(
                DeveloperTaskExecutionRuntimeCompositionFileEvidence(
                    path="runtime.placeholder",
                    size_bytes=13,
                    sha256=composition_module._sha256(b"fixed-runtime"),
                ),
            ),
            input_files=(),
            runtime_bundle=runtime_bundle,
            payload_bundle=payload,
            wsb_bytes=wsb_bytes,
        )
        self.root = root
        self.prepared = prepared
        return prepared

    def verify_materialization(self, prepared: Any) -> Any:
        self.materialization_calls += 1
        if self.mode == "materialization_failure":
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_materialization_identity_mismatch",
                "fake materialization failure",
            )
        if (
            self.mode == "post_pin_materialization_mutation"
            and self.materialization_calls >= 3
        ):
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_runtime_file_changed",
                "fake post-pin runtime mutation",
            )
        if self.mode == "post_exit_materialization_mutation" and self.terminal_written:
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_runtime_file_changed",
                "fake post-exit runtime mutation",
            )
        return DeveloperTaskExecutionRuntimeCompositionMaterializationEvidence(
            runtime_file_count=RUNTIME_BUNDLE_FILE_COUNT,
            runtime_total_bytes=RUNTIME_BUNDLE_TOTAL_BYTES,
            runtime_tree_manifest_sha256=RUNTIME_TREE_MANIFEST_SHA256,
            runtime_manifest_sha256=RUNTIME_MANIFEST_SHA256,
            input_file_count=6,
            input_manifest_sha256="c" * 64,
            regular_files_verified=True,
            reparse_points_absent=True,
        )

    def launch(self, executable: Path, config_path: Path) -> Any:
        self.launch_calls += 1
        self.launched = True
        if self.mode == "launch_failure":
            raise RuntimeError("fake launch failure")
        return _Launcher()

    def launcher_exited(self, launcher: Any) -> bool:
        if self.mode == "launcher_never_exits":
            return False
        if self.mode == "launcher_exit_lag":
            return self.terminal_written and self.clock >= self.launcher_exit_ready_at
        return self.terminal_written or self.mode == "guest_failure_before_ready"

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
            self.post_terminal_snapshot_calls += 1
            if (
                self.mode == "process_reappearance_gap"
                and self.post_terminal_snapshot_calls == 3
            ):
                return (_PROCESS,)
            return ()
        if self.mode == "guest_failure_before_ready":
            return ()
        return (_PROCESS,)

    def artifact_exists(self, path: Path) -> bool:
        if self.prepared is None:
            return os.path.lexists(path)
        if (
            path.name == RUNTIME_ATTESTATION_TERMINAL_FILE_NAME
            and self.mode == "early_terminal"
        ):
            path.write_bytes(b"early")
            return True
        if path.name == RUNTIME_ATTESTATION_READY_FILE_NAME and self.launched and not path.exists():
            if self.mode == "guest_failure_before_ready":
                failure_payload = {
                    "schema_version": 1,
                    "request_id": str(self.prepared.request.field("request_id")),
                    "stage": "controller_identity",
                    "error_type": "RuntimeException",
                    "error_code": "runtime_attestation_controller_stage_failed",
                    "worker_account_created": False,
                    "worker_account_deleted": False,
                    "job_closed": False,
                    "completed_at_utc": "2026-08-13T00:00:00.0000000Z",
                    "execution_authorized": False,
                }
                self.prepared.controller_failure_path.write_bytes(
                    json.dumps(
                        failure_payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
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
        if (
            self.mode == "ready_mutation"
            and artifact_name == RUNTIME_ATTESTATION_READY_FILE_NAME
            and self.read_counts[artifact_name] == 2
        ):
            payload = json.loads(path.read_bytes())
            payload["controller_name"] = "NT AUTHORITY\\MUTATE"
            path.write_bytes(verifier_fixture._canonical(payload))
        if (
            self.mode == "post_exit_ready_mutation"
            and artifact_name == RUNTIME_ATTESTATION_READY_FILE_NAME
            and self.terminal_written
            and self.read_counts[artifact_name] >= 3
        ):
            payload = json.loads(path.read_bytes())
            payload["controller_name"] = "NT AUTHORITY\\POSTEX"
            path.write_bytes(verifier_fixture._canonical(payload))
        return super().read_artifact(
            path,
            max_bytes=max_bytes,
            artifact_name=artifact_name,
            expected_size=expected_size,
        )

    def publish_authorize(self, path: Path, data: bytes) -> tuple[str, str]:
        self.publish_calls += 1
        if self.mode == "authorization_failure":
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_authorization_publish_failed",
                "fake authorization failure",
            )
        hashes = publish_developer_task_execution_runtime_composition_authorization(
            path,
            data,
        )
        self.authorized = True
        if self.mode not in {"terminal_timeout"}:
            self._write_terminal(data)
        return hashes

    def pin_transcript(self, **kwargs: Any) -> Any:
        self.pin_calls += 1
        self.authorization_observed_epochs.append(
            float(kwargs["authorization_observed_epoch"])
        )
        if self.mode == "pin_failure":
            kwargs["expected_host_nonce"] = "f" * 64
        return super().pin_transcript(**kwargs)

    def verify_transcript(self, *args: Any, **kwargs: Any) -> Any:
        self.verify_calls += 1
        kwargs["signature_verifier"] = (
            (lambda *_args: False)
            if self.mode == "signature_failure"
            else (lambda *_args: True)
        )
        return verify_developer_task_execution_runtime_attestation_transcript(
            *args,
            **kwargs,
        )

    def cleanup(self, prepared: Any, *, artifact_parent: Path) -> int:
        self.cleanup_calls += 1
        if self.mode == "cleanup_failure":
            raise DeveloperTaskExecutionRuntimeCompositionFileSystemError(
                "runtime_composition_artifact_cleanup_failed",
                "fake cleanup failure",
            )
        return remove_developer_task_execution_runtime_composition_artifacts(
            prepared.root,
            artifact_parent=artifact_parent,
            initial_metadata=prepared.root_metadata,
        )

    def monotonic(self) -> float:
        return self.clock

    def epoch(self) -> float:
        return self.base_epoch + self.clock

    def sleep(self, seconds: float) -> None:
        self.clock += max(seconds, 1.0)

    def _write_ready(self, path: Path) -> None:
        assert self.prepared is not None
        self.clock += 1.0
        request = parse_runtime_attestation_request(
            self.prepared.request_path.read_bytes()
        )
        ready_epoch = (
            self.epoch() - 0.25
            if self.mode == "subsecond_authorization_timing"
            else int(self.epoch())
        )
        ready = verifier_fixture._sample_ready(
            request,
            ready_epoch=ready_epoch,
        )
        path.write_bytes(ready.canonical_bytes)

    def _write_terminal(self, authorize_bytes: bytes) -> None:
        assert self.prepared is not None
        request = parse_runtime_attestation_request(
            self.prepared.request_path.read_bytes()
        )
        ready = parse_runtime_attestation_ready(
            self.prepared.ready_path.read_bytes()
        )
        authorize = parse_runtime_attestation_authorize(authorize_bytes)
        runtime_result_bytes = verifier_fixture._sample_runtime_result()
        runtime_result = parse_runtime_attestation_result(runtime_result_bytes)
        terminal_bytes = verifier_fixture._sample_terminal(
            request,
            ready,
            authorize,
            runtime_result,
            completed_epoch=int(self.epoch()) + 2,
        )
        self.prepared.runtime_result_path.write_bytes(runtime_result_bytes)
        self.prepared.terminal_payload_path.write_bytes(terminal_bytes)
        self.prepared.terminal_signature_path.write_bytes(verifier_fixture._SIGNATURE)
        self.terminal_written = True
        if self.mode == "launcher_exit_lag":
            self.launcher_exit_ready_at = self.clock + 2.0


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
        host_boot_epoch_seconds=1786550000,
        feature_state="enabled",
        feature_probe_error="",
        executable=executable,
        wsb_cli_found=False,
        wsb_cli_path="",
        wsb_cli_probe_error="",
        running_sandbox_processes=(),
        issues=issues,
    )


def _run(mode: str = "success") -> tuple[Any, _FakeRuntime]:
    host = _host_report()
    runtime = _FakeRuntime(host, mode=mode)
    with tempfile.TemporaryDirectory(
        prefix="skynetvs-v1b4c2b-eval-parent-"
    ) as temporary:
        report = _attest_developer_task_execution_runtime_composition(
            host,
            Path("python-3.13.15-embed-amd64.zip"),
            artifact_parent=Path(temporary),
            runtime=runtime,
        )
    return report, runtime


def _is_frozen(value: Any) -> bool:
    try:
        setattr(value, "status", "mutated")
    except (FrozenInstanceError, AttributeError, TypeError):
        return True
    return False


def _raises(callable_: Any, error_type: type[BaseException]) -> bool:
    try:
        callable_()
    except error_type:
        return True
    except Exception:
        return False
    return False


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

    signature = inspect.signature(
        attest_developer_task_execution_runtime_composition
    )
    check(
        "V1B4C2B PUBLIC API IS EXACT AND CALLER-FREE",
        {
            name: {
                "kind": parameter.kind.name,
                "default": (
                    None
                    if parameter.default is inspect.Parameter.empty
                    else parameter.default
                ),
            }
            for name, parameter in signature.parameters.items()
        },
        {
            "host_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "runtime_zip": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "artifact_parent": {"kind": "KEYWORD_ONLY", "default": None},
        },
    )

    source = inspect.getsource(composition_module)
    check(
        "V1B4C2B PRODUCTION API HAS NO DEVELOPER TASK OR ARBITRARY EXECUTION INPUT",
        {
            "manifest_input": "manifest:" in source,
            "patch_input": "patch:" in source,
            "workspace_input": "workspace:" in source,
            "module_input": "python_module:" in source,
            "pipeline_input": "pipeline_flow:" in source,
            "caller_argv": "caller_argv" in source,
            "caller_environment": "caller_environment" in source,
            "shell_true": "shell=True" in source,
            "execution_true": "execution_authorized = True" in source
            or '"execution_authorized": True' in source,
        },
        {
            "manifest_input": False,
            "patch_input": False,
            "workspace_input": False,
            "module_input": False,
            "pipeline_input": False,
            "caller_argv": False,
            "caller_environment": False,
            "shell_true": False,
            "execution_true": False,
        },
    )

    check(
        "V1B4C2B RAW PUBLIC INPUT TYPES ARE REJECTED",
        {
            "host": _raises(
                lambda: attest_developer_task_execution_runtime_composition(
                    {},  # type: ignore[arg-type]
                    Path("python.zip"),
                    artifact_parent=Path("."),
                ),
                TypeError,
            ),
            "runtime": _raises(
                lambda: attest_developer_task_execution_runtime_composition(
                    _host_report(),
                    "python.zip",  # type: ignore[arg-type]
                    artifact_parent=Path("."),
                ),
                TypeError,
            ),
            "parent": _raises(
                lambda: attest_developer_task_execution_runtime_composition(
                    _host_report(),
                    Path("python.zip"),
                    artifact_parent=".",  # type: ignore[arg-type]
                ),
                TypeError,
            ),
        },
        {"host": True, "runtime": True, "parent": True},
    )

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1b4c2b-fs-") as temporary:
        root = Path(temporary)
        artifact = root / "exact.bin"
        artifact.write_bytes(b"exact-bytes")
        raw, sha256 = read_developer_task_execution_runtime_composition_artifact_bytes(
            artifact,
            max_bytes=64,
            artifact_name="exact.bin",
            expected_size=11,
        )
        check(
            "V1B4C2B ARTIFACT READER RETURNS EXACT BYTES",
            {"raw": raw, "sha256_length": len(sha256)},
            {"raw": b"exact-bytes", "sha256_length": 64},
        )

        control = root / "control"
        control.mkdir()
        authorize = control / RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME
        auth_hash, commit_hash = (
            publish_developer_task_execution_runtime_composition_authorization(
                authorize,
                b"authorization",
            )
        )
        check(
            "V1B4C2B AUTHORIZATION USES DATA THEN EXACT SHA256 COMMIT",
            {
                "authorization": authorize.read_bytes(),
                "commit": (
                    control / RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME
                ).read_bytes(),
                "auth_hash": auth_hash,
                "commit_hash_length": len(commit_hash),
            },
            {
                "authorization": b"authorization",
                "commit": composition_module._sha256(b"authorization").encode(
                    "ascii"
                ),
                "auth_hash": composition_module._sha256(b"authorization"),
                "commit_hash_length": 64,
            },
        )
        check(
            "V1B4C2B PREEXISTING AUTHORIZATION IS REJECTED",
            _raises(
                lambda: publish_developer_task_execution_runtime_composition_authorization(
                    authorize,
                    b"new",
                ),
                DeveloperTaskExecutionRuntimeCompositionFileSystemError,
            ),
            True,
        )

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1b4c2b-git-parent-") as temporary:
        root = Path(temporary)
        (root / ".git").mkdir()
        child = root / "artifacts"
        child.mkdir()
        check(
            "V1B4C2B ARTIFACT PARENT INSIDE GIT REPOSITORY IS REJECTED",
            _raises(
                lambda: validate_developer_task_execution_runtime_composition_artifact_parent(
                    child
                ),
                DeveloperTaskExecutionRuntimeCompositionFileSystemError,
            ),
            True,
        )

    success, success_runtime = _run()
    check(
        "V1B4C2B SIMULATED ACTIVE TRUSTED RUNTIME COMPOSITION PASSES",
        {
            "ok": success.ok,
            "status": success.status,
            "pin": success.pin_report.ok if success.pin_report else False,
            "signed": success.signed_report.ok if success.signed_report else False,
            "runtime_result": (
                success.signed_report.runtime_result_verified
                if success.signed_report
                else False
            ),
            "signature": (
                success.signed_report.signature_valid
                if success.signed_report
                else False
            ),
            "observed": success.process_observed,
            "exited": success.all_processes_exited,
            "removed": success.artifacts.removed if success.artifacts else False,
            "interpreter": success.interpreter_executed,
            "lease": success.reusable_lease_issued,
            "authorized": success.execution_authorized,
        },
        {
            "ok": True,
            "status": ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED,
            "pin": True,
            "signed": True,
            "runtime_result": True,
            "signature": True,
            "observed": True,
            "exited": True,
            "removed": True,
            "interpreter": True,
            "lease": False,
            "authorized": False,
        },
    )
    check(
        "V1B4C2B SUCCESS ORDERS PIN PUBLICATION VERIFICATION AND ONE LAUNCH",
        {
            "launch": success_runtime.launch_calls,
            "pin": success_runtime.pin_calls,
            "publish": success_runtime.publish_calls,
            "verify": success_runtime.verify_calls,
            "materialization_min": success_runtime.materialization_calls >= 4,
            "forced_cleanup": success_runtime.terminate_calls,
        },
        {
            "launch": 1,
            "pin": 1,
            "publish": 1,
            "verify": 1,
            "materialization_min": True,
            "forced_cleanup": 0,
        },
    )

    subsecond, subsecond_runtime = _run("subsecond_authorization_timing")
    subsecond_observed = (
        subsecond_runtime.authorization_observed_epochs[0]
        if subsecond_runtime.authorization_observed_epochs
        else 0.0
    )
    check(
        "V1B4C2B SUBSECOND AUTHORIZATION OBSERVATION IS NOT TRUNCATED",
        {
            "ok": subsecond.ok,
            "status": subsecond.status,
            "fractional_observation": (
                subsecond_observed != int(subsecond_observed)
            ),
            "temporal_inversion": (
                "runtime_attestation_authorization_temporal_inversion"
                in subsecond.issue_codes
            ),
        },
        {
            "ok": True,
            "status": ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED,
            "fractional_observation": True,
            "temporal_inversion": False,
        },
    )

    quantized_boot, quantized_boot_runtime = _run(
        "boot_epoch_quantization_jitter"
    )
    check(
        "V1B4C2B ONE SECOND BOOT EPOCH QUANTIZATION JITTER IS ACCEPTED",
        {
            "ok": quantized_boot.ok,
            "status": quantized_boot.status,
            "inspect_calls": quantized_boot_runtime.inspect_calls,
            "launch_calls": quantized_boot_runtime.launch_calls,
            "host_change_issue": (
                "execution_backend_host_evidence_changed"
                in quantized_boot.issue_codes
            ),
        },
        {
            "ok": True,
            "status": ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED,
            "inspect_calls": quantized_boot_runtime.inspect_calls,
            "launch_calls": 1,
            "host_change_issue": False,
        },
    )

    drifted_boot, drifted_boot_runtime = _run(
        "boot_epoch_drift_before_launch"
    )
    drift_issue = next(
        (
            issue
            for issue in drifted_boot.issues
            if issue.code == "execution_backend_host_evidence_changed"
        ),
        None,
    )
    check(
        "V1B4C2B BOOT EPOCH DRIFT BEYOND QUANTIZATION FAILS BEFORE LAUNCH",
        {
            "ok": drifted_boot.ok,
            "launch_calls": drifted_boot_runtime.launch_calls,
            "code": drift_issue is not None,
            "diagnostic": bool(
                drift_issue
                and "host_boot_epoch_seconds" in drift_issue.actual
            ),
            "authorized": drifted_boot.execution_authorized,
        },
        {
            "ok": False,
            "launch_calls": 0,
            "code": True,
            "diagnostic": True,
            "authorized": False,
        },
    )

    lagged_exit, lagged_runtime = _run("launcher_exit_lag")
    check(
        "V1B4C2B LAUNCHER EXIT LAG DOES NOT ALLOW PREMATURE POST-EXIT TRUST",
        {
            "ok": lagged_exit.ok,
            "exited": lagged_exit.all_processes_exited,
            "exit_after_terminal": bool(
                lagged_exit.all_processes_exited_ms is not None
                and lagged_exit.terminal_detected_ms is not None
                and lagged_exit.all_processes_exited_ms
                > lagged_exit.terminal_detected_ms
            ),
            "cleanup": bool(lagged_exit.artifacts and lagged_exit.artifacts.removed),
            "forced_cleanup": lagged_runtime.terminate_calls,
        },
        {
            "ok": True,
            "exited": True,
            "exit_after_terminal": True,
            "cleanup": True,
            "forced_cleanup": 0,
        },
    )

    reappearing, reappearing_runtime = _run("process_reappearance_gap")
    check(
        "V1B4C2B PROCESS REAPPEARANCE RESETS CONSECUTIVE EXIT PROOF",
        {
            "ok": reappearing.ok,
            "post_terminal_snapshots": reappearing_runtime.post_terminal_snapshot_calls,
            "minimum_confirmations": (
                reappearing_runtime.post_terminal_snapshot_calls >= 6
            ),
            "removed": bool(reappearing.artifacts and reappearing.artifacts.removed),
        },
        {
            "ok": True,
            "post_terminal_snapshots": reappearing_runtime.post_terminal_snapshot_calls,
            "minimum_confirmations": True,
            "removed": True,
        },
    )

    check(
        "V1B4C2B REPORT IS IMMUTABLE AND JSON SERIALIZABLE",
        {
            "immutable": _is_frozen(success),
            "json": isinstance(json.dumps(success.to_dict()), str),
            "issues": list(success.issue_codes),
        },
        {"immutable": True, "json": True, "issues": []},
    )

    failure_expectations = {
        "runtime_bundle_failure": "runtime_composition_runtime_bundle_failed",
        "runtime_bundle_invalid": "runtime_composition_runtime_bundle_invalid",
        "payload_bundle_invalid": "runtime_composition_payload_bundle_invalid",
        "prepare_failure": "runtime_composition_artifact_write_failed",
        "materialization_failure": "runtime_composition_materialization_identity_mismatch",
        "baseline_active": "runtime_composition_sandbox_instance_running",
        "launch_failure": "runtime_composition_unexpected_error",
        "ready_timeout": "runtime_composition_ready_timeout",
        "guest_failure_before_ready": "runtime_composition_guest_failure_reported",
        "early_terminal": "runtime_composition_terminal_before_authorization",
        "pin_failure": "runtime_attestation_transcript_mismatch",
        "ready_mutation": "runtime_composition_ready_changed_before_authorization",
        "post_pin_materialization_mutation": "runtime_composition_runtime_file_changed",
        "authorization_failure": "runtime_composition_authorization_publish_failed",
        "terminal_timeout": "runtime_composition_terminal_timeout",
        "signature_failure": "runtime_attestation_signature_invalid",
        "post_exit_ready_mutation": "runtime_composition_pinned_artifact_changed",
        "post_exit_materialization_mutation": "runtime_composition_runtime_file_changed",
        "host_changes_after": "execution_backend_host_evidence_changed",
        "cleanup_failure": "runtime_composition_artifact_cleanup_failed",
    }
    for mode, expected_code in failure_expectations.items():
        report, runtime = _run(mode)
        check(
            f"V1B4C2B {mode.upper()} FAILS CLOSED",
            {
                "ok": report.ok,
                "status_is_success": report.status
                == ACTIVE_TRUSTED_RUNTIME_STATUS_ATTESTED,
                "code": expected_code in report.issue_codes,
                "authorized": report.execution_authorized,
            },
            {
                "ok": False,
                "status_is_success": False,
                "code": True,
                "authorized": False,
            },
        )

    guest_failure, _ = _run("guest_failure_before_ready")
    guest_issue = next(
        (
            issue
            for issue in guest_failure.issues
            if issue.code == "runtime_composition_guest_failure_reported"
        ),
        None,
    )
    check(
        "V1B4C2B EARLY GUEST FAILURE DIAGNOSTIC IS CAPTURED BEFORE CLEANUP",
        {
            "code": guest_issue is not None,
            "stage": bool(guest_issue and "stage=controller_identity" in guest_issue.actual),
            "error_type": bool(guest_issue and "error_type=RuntimeException" in guest_issue.actual),
            "error_code": bool(
                guest_issue
                and "error_code=runtime_attestation_controller_stage_failed"
                in guest_issue.actual
            ),
            "artifact_hash": bool(
                guest_failure.artifacts
                and len(guest_failure.artifacts.failure_artifact_sha256) == 64
            ),
            "removed": bool(
                guest_failure.artifacts and guest_failure.artifacts.removed
            ),
            "authorized": guest_failure.execution_authorized,
        },
        {
            "code": True,
            "stage": True,
            "error_type": True,
            "error_code": True,
            "artifact_hash": True,
            "removed": True,
            "authorized": False,
        },
    )

    shutdown, shutdown_runtime = _run("shutdown_timeout")
    check(
        "V1B4C2B SHUTDOWN TIMEOUT USES FAILURE-ONLY FORCED CLEANUP",
        {
            "ok": shutdown.ok,
            "status": shutdown.status,
            "termination": shutdown.termination.attempted,
            "terminate_calls": shutdown_runtime.terminate_calls,
            "code": "runtime_composition_shutdown_timeout" in shutdown.issue_codes,
        },
        {
            "ok": False,
            "status": ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED,
            "termination": True,
            "terminate_calls": 1,
            "code": True,
        },
    )

    launcher_active, _ = _run("launcher_never_exits")
    check(
        "V1B4C2B EMPTY PROCESS SNAPSHOT CANNOT OVERRIDE ACTIVE LAUNCHER",
        {
            "ok": launcher_active.ok,
            "status": launcher_active.status,
            "launcher_code": "runtime_composition_launcher_still_active"
            in launcher_active.issue_codes,
            "removed": bool(
                launcher_active.artifacts and launcher_active.artifacts.removed
            ),
        },
        {
            "ok": False,
            "status": ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE,
            "launcher_code": True,
            "removed": False,
        },
    )

    snapshot_failure, _ = _run("snapshot_failure")
    check(
        "V1B4C2B UNPROVEN PROCESS STATE RETURNS FAILED ACTIVE",
        {
            "ok": snapshot_failure.ok,
            "status": snapshot_failure.status,
            "code": "runtime_composition_process_state_unproven"
            in snapshot_failure.issue_codes,
        },
        {
            "ok": False,
            "status": ACTIVE_TRUSTED_RUNTIME_STATUS_FAILED_ACTIVE,
            "code": True,
        },
    )

    failed_host = replace(
        _host_report(),
        issues=(
            SimpleNamespace(
                code="fake_host_failure",
                to_dict=lambda: {"code": "fake_host_failure"},
            ),
        ),
    )
    failed_runtime = _FakeRuntime(_host_report())
    with tempfile.TemporaryDirectory(
        prefix="skynetvs-v1b4c2b-failed-host-"
    ) as temporary:
        failed_host_report = _attest_developer_task_execution_runtime_composition(
            failed_host,
            Path("python-3.13.15-embed-amd64.zip"),
            artifact_parent=Path(temporary),
            runtime=failed_runtime,
        )
    check(
        "V1B4C2B FAILED HOST REPORT BLOCKS MATERIALIZATION AND LAUNCH",
        {
            "ok": failed_host_report.ok,
            "launch_calls": failed_runtime.launch_calls,
            "code": "execution_backend_host_report_failed"
            in failed_host_report.issue_codes,
        },
        {"ok": False, "launch_calls": 0, "code": True},
    )

    fs_source = inspect.getsource(
        __import__(
            "modules.developer.developer_task_execution_runtime_composition_fs",
            fromlist=["dummy"],
        )
    )
    check(
        "V1B4C2B FILESYSTEM BOUNDARY USES EXCLUSIVE NO-OVERWRITE MATERIALIZATION",
        {
            "exclusive": 'open("xb")' in fs_source,
            "fsync": "os.fsync" in fs_source,
            "no_extract": ".extract(" not in fs_source
            and ".extractall(" not in fs_source,
            "commit_marker": "RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME"
            in fs_source,
            "safe_cleanup": "remove_verified_workspace" in fs_source,
        },
        {
            "exclusive": True,
            "fsync": True,
            "no_extract": True,
            "commit_marker": True,
            "safe_cleanup": True,
        },
    )

    check(
        "V1B4C2B SOURCE BINDS REAL V1B4B C1 C2A AND WINDOWS LIFECYCLE PRIMITIVES",
        {
            "runtime_builder": "build_developer_task_execution_runtime_bundle" in source,
            "payload_builder": "build_developer_task_execution_runtime_attestation_payload"
            in source,
            "pin": "pin_developer_task_execution_runtime_attestation_transcript"
            in source,
            "verify": "verify_developer_task_execution_runtime_attestation_transcript"
            in source,
            "launch": "launch_windows_sandbox" in source,
            "snapshot": "snapshot_windows_sandbox_processes" in source,
            "terminate": "terminate_observed_windows_sandbox_processes" in source,
        },
        {
            "runtime_builder": True,
            "payload_builder": True,
            "pin": True,
            "verify": True,
            "launch": True,
            "snapshot": True,
            "terminate": True,
        },
    )

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
