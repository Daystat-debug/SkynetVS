from __future__ import annotations

import ast
import base64
import copy
import hashlib
import inspect
import json
import os
import tempfile

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from modules.developer.developer_task_execution_backend_lifecycle_windows import (
    DeveloperTaskExecutionBackendProcessEvidence,
    DeveloperTaskExecutionBackendTerminationResult,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction import (
    COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED,
    issue_developer_task_execution_compile_ast_claim_transaction,
)
from modules.developer.developer_task_execution_compile_ast_composition import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED,
    DeveloperTaskExecutionCompileAstCompositionReport,
    _CompileAstCompositionRuntime,
    _attest_developer_task_execution_compile_ast_composition,
    attest_developer_task_execution_compile_ast_composition,
)
from modules.developer.developer_task_execution_compile_ast_composition_fs import (
    DeveloperTaskExecutionCompileAstCompositionFileSystemError,
    DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence,
    _materialize_flat_exact_files,
    _render_wsb_template,
    _safe_flat_name,
    publish_developer_task_execution_compile_ast_composition_authorization,
    read_developer_task_execution_compile_ast_composition_artifact_bytes,
    validate_developer_task_execution_compile_ast_composition_artifact_parent,
)
from modules.developer.developer_task_execution_compile_ast_composition_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_SLICE_IDENTITY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1,
    canonical_developer_task_execution_compile_ast_composition_policy_json,
    developer_task_execution_compile_ast_composition_policy_bytes,
    developer_task_execution_compile_ast_composition_policy_fingerprint,
    validate_developer_task_execution_compile_ast_composition_policy,
)
from modules.developer.developer_task_execution_compile_ast_contract import (
    build_compile_ast_source_manifest,
    encode_compile_ast_document,
    parse_compile_ast_request,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker import (
    DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport,
    build_developer_task_execution_compile_ast_controller_worker_bundle,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    build_developer_task_execution_compile_ast_runner_bundle,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_TREE_MANIFEST_SHA256,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from tools.eval_developer_task_execution_compile_ast_claim_transaction import (
    _lease_claim_context,
    _reset_registries,
    _synthetic_plan,
    _synthetic_runtime_lease,
)
from tools.eval_developer_task_execution_compile_ast_contract import build_valid_payloads
from tools.eval_developer_task_execution_runtime_lease import _host


PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = PROJECT_ROOT / "modules" / "developer" / "developer_task_execution_compile_ast_composition_policy.py"
FS_PATH = PROJECT_ROOT / "modules" / "developer" / "developer_task_execution_compile_ast_composition_fs.py"
COMPOSITION_PATH = PROJECT_ROOT / "modules" / "developer" / "developer_task_execution_compile_ast_composition.py"
WINDOWS_EVALUATOR_PATH = PROJECT_ROOT / "tools" / "eval_developer_task_execution_compile_ast_composition_windows.py"
_PUBLIC_KEY = (
    b"ECS1"
    + b"\x20\x00\x00\x00"
    + int("6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296", 16).to_bytes(32, "big")
    + int("4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5", 16).to_bytes(32, "big")
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: dict[str, Any], *, final_lf: bool = False) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return data + (b"\n" if final_lf else b"")


def _error_code(callback: Any) -> str:
    try:
        callback()
    except DeveloperTaskExecutionCompileAstCompositionFileSystemError as exc:
        return exc.code
    except TypeError:
        return "TypeError"
    return ""


class _FakePin:
    ok = True
    issues: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"ok": True, "status": "compile_ast_transcript_pinned", "issues": []}


class _FakeSigned:
    ok = True
    issues: tuple[Any, ...] = ()
    terminal_status = "compile_ast_attested_passed"
    boundary_ok = True
    check_passed = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "compile_ast_transcript_verified",
            "terminal_status": self.terminal_status,
            "boundary_ok": True,
            "check_passed": True,
            "issues": [],
        }


class _FakeLauncher:
    pid = 4242


class _FakeRuntime(_CompileAstCompositionRuntime):
    def __init__(self, host: Any, lease_services: Any, *, fail_before_ready: bool = False) -> None:
        self.host = host
        self.lease_services = lease_services
        self.fail_before_ready = fail_before_ready
        self.clock = 0.0
        self.epoch_base = 1786809600.0
        self.process_calls = 0
        self.authorized = False
        self.prepared: Any | None = None
        self.artifacts: dict[str, bytes] = {}
        self.tokens = ["a" * 32, "b" * 64, "c" * 64]

    def inspect_host(self):
        return self.host

    def claim_transaction(self, transaction):
        with _lease_claim_context(self.lease_services):
            return transaction.claim()

    def token_hex(self, bytes_count: int) -> str:
        return self.tokens.pop(0)

    def prepare_artifacts(self, **kwargs: Any):
        material = kwargs["transaction_material"]
        request_id = kwargs["request_id"]
        host_nonce = kwargs["host_nonce"]
        parent = kwargs["artifact_parent"]
        root = parent / "fake-v1c2c2"
        input_root = root / "input"
        source_root = input_root / "sources"
        runtime_root = root / "runtime"
        control_root = root / "control"
        output_root = root / "output"
        for path in (source_root, runtime_root, control_root, output_root):
            path.mkdir(parents=True, exist_ok=True)
        manifest = build_compile_ast_source_manifest(
            material.plan_material.report,
            request_id=request_id,
            host_nonce=host_nonce,
        )
        runner = kwargs["runner_bundle"]
        controller = kwargs["controller_worker_bundle"]
        request_payload = build_valid_payloads()[1]
        request_payload = copy.deepcopy(request_payload)
        request_payload.update(
            {
                "request_id": request_id,
                "host_nonce": host_nonce,
                "created_at_utc": "2026-08-16T00:00:00.000Z",
                "policy_sha256": runner.contract_policy.sha256,
                "bootstrap_sha256": controller.bootstrap.sha256,
                "controller_sha256": controller.controller.sha256,
                "native_helper_sha256": controller.native_helper.sha256,
                "runner_sha256": runner.runner.sha256,
                "payload_sha256": runner.payload_manifest.sha256,
                "wsb_sha256": "d" * 64,
                "runtime_lease_fingerprint": material.runtime_lease_fingerprint,
                "plan_fingerprint": material.plan_material.report.plan_fingerprint,
                "source_manifest_sha256": manifest.sha256,
                "selected_file_count": material.plan_material.report.selected_file_count,
                "selected_total_bytes": material.plan_material.report.selected_total_bytes,
            }
        )
        request = parse_compile_ast_request(encode_compile_ast_document("request", request_payload))
        paths = {
            "request_path": input_root / "request.json",
            "source_manifest_path": input_root / "source_manifest.json",
            "ready_path": output_root / "ready.json",
            "authorize_path": control_root / "authorize.json",
            "authorize_commit_path": control_root / "authorize.sha256",
            "result_path": output_root / "result.json",
            "terminal_payload_path": output_root / "terminal_payload.json",
            "terminal_signature_path": output_root / "terminal_signature.bin",
            "controller_evidence_payload_path": (
                output_root / "controller_evidence_payload.json"
            ),
            "controller_evidence_signature_path": (
                output_root / "controller_evidence_signature.bin"
            ),
            "bootstrap_failure_path": output_root / "bootstrap_failure.json",
            "controller_failure_path": output_root / "controller_failure.json",
            "wsb_path": input_root / "SkynetVS_V1C2C1.wsb",
        }
        prepared = SimpleNamespace(
            root=root,
            root_metadata=os.lstat(root),
            input_root=input_root,
            source_root=source_root,
            runtime_root=runtime_root,
            control_root=control_root,
            output_root=output_root,
            request=request,
            source_manifest=manifest,
            wsb_bytes=b"<Configuration/>\n",
            transaction_material=material,
            **paths,
        )
        self.prepared = prepared
        self.artifacts[str(prepared.request_path)] = request.canonical_bytes
        self.artifacts[str(prepared.source_manifest_path)] = manifest.canonical_bytes

        template_ready = copy.deepcopy(build_valid_payloads()[2])
        rq = request.to_dict()
        template_ready.update(
            {
                "request_id": request_id,
                "host_nonce": host_nonce,
                "request_sha256": request.sha256,
                "source_manifest_sha256": manifest.sha256,
                "public_key_blob_base64": base64.b64encode(_PUBLIC_KEY).decode("ascii"),
                "public_key_sha256": _sha256(_PUBLIC_KEY),
                "created_at_utc": "2026-08-16T00:00:05.000Z",
            }
        )
        for field in (
            "policy_sha256",
            "bootstrap_sha256",
            "controller_sha256",
            "native_helper_sha256",
            "runner_sha256",
            "payload_sha256",
            "wsb_sha256",
            "runtime_attestation_policy_fingerprint",
            "runtime_bundle_fingerprint",
            "runtime_lease_policy_fingerprint",
            "runtime_lease_fingerprint",
            "plan_policy_fingerprint",
            "plan_fingerprint",
        ):
            template_ready[field] = rq[field]
        self.artifacts[str(prepared.ready_path)] = encode_compile_ast_document("ready", template_ready)
        if self.fail_before_ready:
            self.artifacts.pop(str(prepared.ready_path), None)
            self.artifacts[str(prepared.controller_failure_path)] = _canonical(
                {"stage": "request_validation", "error_type": "Synthetic", "error_code": "synthetic"}
            )
        return prepared

    def verify_materialization(self, prepared):
        return DeveloperTaskExecutionCompileAstCompositionMaterializationEvidence(
            runtime_file_count=RUNTIME_BUNDLE_FILE_COUNT,
            runtime_total_bytes=RUNTIME_BUNDLE_TOTAL_BYTES,
            runtime_tree_manifest_sha256=RUNTIME_TREE_MANIFEST_SHA256,
            runtime_manifest_sha256=RUNTIME_MANIFEST_SHA256,
            input_file_count=10,
            input_manifest_sha256="1" * 64,
            source_file_count=1,
            source_total_bytes=10,
            source_manifest_sha256=prepared.source_manifest.sha256,
            regular_files_verified=True,
            reparse_points_absent=True,
        )

    def snapshot_processes(self):
        self.process_calls += 1
        if self.process_calls <= 2:
            return ()
        if self.process_calls <= 4:
            return (
                DeveloperTaskExecutionBackendProcessEvidence(
                    name="WindowsSandboxRemoteSession.exe",
                    pid=5000,
                    created_epoch_ns=1,
                    executable_path=r"C:\Windows\System32\WindowsSandboxRemoteSession.exe",
                ),
            )
        return ()

    def launch(self, executable: Path, config_path: Path):
        return _FakeLauncher()

    def launcher_exited(self, launcher: Any) -> bool:
        return self.process_calls >= 5

    def artifact_exists(self, path: Path) -> bool:
        return str(path) in self.artifacts

    def read_artifact(self, path: Path, *, max_bytes: int, artifact_name: str, expected_size: int | None = None):
        raw = self.artifacts[str(path)]
        if expected_size is not None and len(raw) != expected_size:
            raise AssertionError("fake expected size mismatch")
        return raw, _sha256(raw)

    def publish_authorize(self, path: Path, data: bytes):
        self.authorized = True
        self.artifacts[str(path)] = data
        commit = _sha256(data).encode("ascii")
        self.artifacts[str(path.with_name("authorize.sha256"))] = commit
        assert self.prepared is not None
        self.artifacts[str(self.prepared.result_path)] = b"{}\n"
        self.artifacts[str(self.prepared.terminal_payload_path)] = b"{}"
        self.artifacts[str(self.prepared.terminal_signature_path)] = b"S" * 64
        self.artifacts[str(self.prepared.controller_evidence_payload_path)] = b"{}"
        self.artifacts[str(self.prepared.controller_evidence_signature_path)] = b"E" * 64
        return _sha256(data), _sha256(commit)

    def pin_transcript(self, **kwargs: Any):
        return _FakePin()

    def verify_transcript(self, *args: Any, **kwargs: Any):
        return _FakeSigned()

    def verify_controller_evidence(self, expectation: Any, **kwargs: Any):
        return DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport(
            ok=True,
            status="controller_signed_success",
            terminal_status="compile_ast_attested_passed",
            issue_codes=(),
            signature_valid=True,
            legacy_terminal_signature_valid=True,
            ready_stable=True,
            evidence_stable=True,
            result_stable=True,
            private_relay_hash_bound=True,
        )

    def cleanup(self, prepared, *, artifact_parent: Path):
        import shutil
        shutil.rmtree(prepared.root)
        return 1

    def monotonic(self) -> float:
        self.clock += 0.05
        return self.clock

    def epoch(self) -> float:
        return self.epoch_base + self.clock

    def sleep(self, seconds: float) -> None:
        self.clock += seconds

    def terminate(self, observed, *, executable: Path):
        return DeveloperTaskExecutionBackendTerminationResult(
            attempted=True,
            succeeded=True,
            targeted_processes=tuple(observed),
            remaining_processes=(),
            errors=(),
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

    policy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1
    policy_bytes = developer_task_execution_compile_ast_composition_policy_bytes(policy)
    check("V1C2C2 POLICY SELF CHECK", list(validate_developer_task_execution_compile_ast_composition_policy(policy)), [])
    check("V1C2C2 POLICY ID", policy.policy_id, DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_ID)
    check("V1C2C2 POLICY FINGERPRINT", developer_task_execution_compile_ast_composition_policy_fingerprint(policy), DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT)
    check("V1C2C2 POLICY BYTES SHA", _sha256(policy_bytes), DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256)
    check("V1C2C2 ARCHITECTURE DECISION", policy.architecture_decision_fingerprint, DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_DECISION_FINGERPRINT)
    check("V1C2C2 ARCHITECTURE SLICE", policy.architecture_slice_identity, DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_SLICE_IDENTITY)
    check("V1C2C2 CANONICAL JSON", canonical_developer_task_execution_compile_ast_composition_policy_json(policy).encode("utf-8") + b"\n", policy_bytes)
    check("V1C2C2 PUBLIC API", {k: v.kind.name for k, v in inspect.signature(attest_developer_task_execution_compile_ast_composition).parameters.items()}, {"host_report": "POSITIONAL_OR_KEYWORD", "transaction": "POSITIONAL_OR_KEYWORD", "artifact_parent": "KEYWORD_ONLY"})
    check("V1C2C2 CALLER SURFACE", list(inspect.signature(attest_developer_task_execution_compile_ast_composition).parameters), ["host_report", "transaction", "artifact_parent"])
    check("V1C2C2 RESULT FLAGS", policy.to_dict()["result_flags"], {"changed_code_executed": False, "reusable_lease_issued": False, "execution_authorized": False})
    check("V1C2C2 PROHIBITIONS", all(value is False for value in policy.to_dict()["prohibitions"].values()), True)
    check("V1C2C2 CLAIM ORDER", policy.to_dict()["claim_order"], ["compile_ast_plan", "runtime_lease"])
    check("V1C2C2 SUCCESS CLASS", policy.to_dict()["accepted_result"]["terminal_status"], "compile_ast_attested_passed")
    controller = build_developer_task_execution_compile_ast_controller_worker_bundle()
    controller_dependency = policy.to_dict()["dependencies"]["controller_worker"]
    check(
        "V1C2C2 CONTROLLER-WORKER R4 BINDING",
        {
            "implementation_revision": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1.to_dict()["implementation_revision"],
            "policy_id": controller_dependency["policy_id"],
            "policy_fingerprint": controller_dependency["policy_fingerprint"],
            "policy_sha256": controller_dependency["policy_sha256"],
            "bundle_fingerprint": controller.bundle_fingerprint,
            "bootstrap_sha256": controller.bootstrap.sha256,
            "controller_sha256": controller.controller.sha256,
            "native_helper_sha256": controller.native_helper.sha256,
            "wsb_template_sha256": controller.wsb_template.sha256,
        },
        {
            "implementation_revision": "V1C2C1R4",
            "policy_id": "skynetvs-v1c2c1r4-fixed-system-controller-standard-user-worker-bundle-v5",
            "policy_fingerprint": "2dc6aaba3384a072524053a90adbdbf394332a8d83c10b6863dd62f1a6365f2f",
            "policy_sha256": "04102be389be5624c34fcc12c88d998c57840633e9f349d1e59fc0ba03e1eb17",
            "bundle_fingerprint": "6e09456eb4d0c76eef136dd7f1d0c40510932dba6887f738529d19481fb5ead0",
            "bootstrap_sha256": "7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d",
            "controller_sha256": "75ebefd7c3d6fa06f9176ba4f1c75424940b7e92e3f2cfb4901c656da4326653",
            "native_helper_sha256": "f05437852c9204bcdb0cce70e30989544251070a836f55d748d559f289ddd8e8",
            "wsb_template_sha256": "3de7527400c576ce9ce75ef58f616622ab52a57426811b193270e292d641c281",
        },
    )
    check(
        "V1C2C2 PRODUCTION TERMINOLOGY REBOUND TO R4",
        any(
            marker
            in (
                COMPOSITION_PATH.read_text(encoding="utf-8")
                + FS_PATH.read_text(encoding="utf-8")
            )
            for marker in ("V1C2C1R1", "V1C2C1R2", "V1C2C1R3")
        ),
        False,
    )
    check(
        "V1C2C2 R4 SIGNED TRANSPORT POLICY",
        policy.to_dict()["controller_evidence_transport"],
        {
            "architecture_decision_id": "skynetvs-v1c2c1r4-untrusted-wsb-transport-signed-controller-evidence-lock-v1",
            "architecture_decision_fingerprint": "8ccd984bb6b92d9ad5a6091168efaf902d3ec6524593c89437acd16ad2cdb955",
            "key": "ephemeral_controller_ecc_key",
            "ready_pinned_before_worker_creation": True,
            "ready_post_exit_stability_required": True,
            "host_transport": "untrusted_writable_wsb_mapping",
            "payload_file": "controller_evidence_payload.json",
            "signature_file": "controller_evidence_signature.bin",
            "payload_max_bytes": 16 * 1024,
            "terminal_success_signed": True,
            "terminal_failure_signed": True,
            "failure_artifact_authority": "signed_controller_terminal_only",
            "unsigned_guest_artifacts_authoritative": False,
            "worker_may_only_cause_dos": True,
            "legacy_success_terminal_signature_required": True,
            "legacy_v1c2b_transcript_verification_required": True,
            "stable_post_exit_reads": 2,
            "terminal_bindings": [
                "request_id",
                "host_nonce",
                "request_sha256",
                "ready_sha256",
                "authorize_sha256",
                "public_key_sha256",
                "runtime_bundle_fingerprint",
                "runtime_lease_fingerprint",
                "plan_fingerprint",
                "source_manifest_sha256",
                "private_result_sha256",
                "relayed_result_sha256",
                "terminal_status",
            ],
        },
    )
    check(
        "V1C2C2 TEMPORARY FAILURE DIAGNOSTIC REMOVED",
        "=== V1C2C2 FULL FAILURE REPORT ===" in WINDOWS_EVALUATOR_PATH.read_text(encoding="utf-8"),
        False,
    )

    check("V1C2C2 SAFE FLAT NAME", _safe_flat_name("source-0001.py"), "source-0001.py")
    for index, invalid in enumerate(("", ".", "..", "a/b", "a\\b", "a:b", "trail.", "trail "), start=1):
        check(f"V1C2C2 UNSAFE NAME {index}", _error_code(lambda value=invalid: _safe_flat_name(value)), "compile_ast_composition_file_name_invalid")

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1c2c2-eval-") as temporary:
        parent = Path(temporary)
        check("V1C2C2 ARTIFACT PARENT", validate_developer_task_execution_compile_ast_composition_artifact_parent(parent), parent.resolve())
        artifact = parent / "artifact.bin"
        artifact.write_bytes(b"abc")
        check("V1C2C2 BOUNDED READ", read_developer_task_execution_compile_ast_composition_artifact_bytes(artifact, max_bytes=3, artifact_name="artifact.bin"), (b"abc", _sha256(b"abc")))
        check("V1C2C2 READ LIMIT", _error_code(lambda: read_developer_task_execution_compile_ast_composition_artifact_bytes(artifact, max_bytes=2, artifact_name="artifact.bin")), "compile_ast_composition_artifact_size_invalid")
        authorize = parent / "authorize.json"
        auth_sha, commit_sha = publish_developer_task_execution_compile_ast_composition_authorization(authorize, b"{}")
        check("V1C2C2 AUTH PUBLISH", {"authorize": auth_sha, "commit": commit_sha, "marker": (parent / "authorize.sha256").read_bytes()}, {"authorize": _sha256(b"{}"), "commit": _sha256(_sha256(b"{}").encode("ascii")), "marker": _sha256(b"{}").encode("ascii")})
        check("V1C2C2 AUTH REPLAY", _error_code(lambda: publish_developer_task_execution_compile_ast_composition_authorization(authorize, b"{}")), "compile_ast_composition_authorization_already_exists")

        layout_input = parent / "layout-input"
        layout_input.mkdir()
        layout_input_files = _materialize_flat_exact_files(
            layout_input,
            (("request.json", b"{}"),),
            code_prefix="compile_ast_composition_layout_input",
        )
        layout_source = layout_input / "sources"
        layout_source.mkdir()
        layout_source_files = _materialize_flat_exact_files(
            layout_source,
            (("source-0001.py", b"value = 2\n"),),
            code_prefix="compile_ast_composition_layout_source",
        )
        fs_source = FS_PATH.read_text(encoding="utf-8")
        fs_tree = ast.parse(fs_source)
        prepare_node = next(
            node
            for node in fs_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name
            == "prepare_developer_task_execution_compile_ast_composition_artifacts"
        )
        prepare_source = ast.get_source_segment(fs_source, prepare_node) or ""
        input_materialization_offset = prepare_source.find(
            "input_files_without_request = _materialize_flat_exact_files"
        )
        source_root_create_offset = prepare_source.find("source_root.mkdir")
        initial_roots = next(
            [
                item.id
                for item in node.iter.elts
                if isinstance(item, ast.Name)
            ]
            for node in ast.walk(prepare_node)
            if isinstance(node, ast.For)
            and isinstance(node.target, ast.Name)
            and node.target.id == "directory"
            and isinstance(node.iter, ast.Tuple)
            and any(
                isinstance(item, ast.Name) and item.id == "input_root"
                for item in node.iter.elts
            )
        )
        check(
            "V1C2C2 FLAT INPUT PRECEDES NESTED SOURCE ROOT",
            {
                "input_files": [item.path for item in layout_input_files],
                "source_files": [item.path for item in layout_source_files],
                "initial_roots": initial_roots,
                "input_then_source": (
                    input_materialization_offset >= 0
                    and source_root_create_offset > input_materialization_offset
                ),
                "input_names": sorted(path.name for path in layout_input.iterdir()),
            },
            {
                "input_files": ["request.json"],
                "source_files": ["source-0001.py"],
                "initial_roots": [
                    "input_root",
                    "runtime_root",
                    "control_root",
                    "output_root",
                ],
                "input_then_source": True,
                "input_names": ["request.json", "sources"],
            },
        )

    rendered = _render_wsb_template(
        controller.wsb_template.exact_bytes(),
        input_root=Path("C:/a&b/input"),
        runtime_root=Path("C:/runtime"),
        control_root=Path("C:/control"),
        output_root=Path("C:/output"),
        host_path_mapper=lambda path: str(path),
    )
    check("V1C2C2 WSB TOKENS RESOLVED", b"@@SKYNETVS_" in rendered, False)
    check("V1C2C2 WSB XML ESCAPE", b"a&amp;b" in rendered, True)

    source_text = "\n".join(path.read_text(encoding="utf-8") for path in (POLICY_PATH, FS_PATH, COMPOSITION_PATH))
    tree = ast.parse(COMPOSITION_PATH.read_text(encoding="utf-8"))
    check("V1C2C2 NO EXEC EVAL", {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval"}}, set())
    check("V1C2C2 NO SUBPROCESS SHELL", "shell=True" in source_text, False)
    check("V1C2C2 NO WORKSPACE INPUT", "workspace_path" in inspect.signature(attest_developer_task_execution_compile_ast_composition).parameters, False)

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, lease_services = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with tempfile.TemporaryDirectory(prefix="skynetvs-v1c2c2-fake-") as temporary:
        fake = _FakeRuntime(_host(), lease_services)
        report = _attest_developer_task_execution_compile_ast_composition(
            _host(), transaction, artifact_parent=Path(temporary), runtime=fake
        )
    check("V1C2C2 SYNTHETIC ACTIVE PASS", {"ok": report.ok, "status": report.status, "terminal": report.signed_report.terminal_status if report.signed_report else "", "transaction": transaction.status().state}, {"ok": True, "status": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED, "terminal": "compile_ast_attested_passed", "transaction": COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED})
    check(
        "V1C2C2 SYNTHETIC R4 CONTROLLER EVIDENCE",
        report.controller_evidence_report.to_dict()
        if report.controller_evidence_report
        else None,
        {
            "ok": True,
            "status": "controller_signed_success",
            "terminal_status": "compile_ast_attested_passed",
            "issue_codes": [],
            "signature_valid": True,
            "legacy_terminal_signature_valid": True,
            "ready_stable": True,
            "evidence_stable": True,
            "result_stable": True,
            "private_relay_hash_bound": True,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        },
    )
    check(
        "V1C2C2 SYNTHETIC R4 ARTIFACT HASHES",
        {
            "controller_evidence_payload_sha256": (
                report.artifacts.controller_evidence_payload_sha256
                if report.artifacts
                else ""
            ),
            "controller_evidence_signature_sha256": (
                report.artifacts.controller_evidence_signature_sha256
                if report.artifacts
                else ""
            ),
        },
        {
            "controller_evidence_payload_sha256": _sha256(b"{}"),
            "controller_evidence_signature_sha256": _sha256(b"E" * 64),
        },
    )
    check("V1C2C2 ACTIVE FLAGS", {"claim": report.claim_transaction_consumed, "lease": report.runtime_lease_claimed, "sandbox": report.sandbox_launched, "interpreter": report.candidate_interpreter_executed, "processed": report.changed_source_processed, "parsed": report.changed_source_ast_parsed, "compiled": report.changed_source_compiled, "executed": report.changed_code_executed, "reusable": report.reusable_lease_issued, "authorized": report.execution_authorized}, {"claim": True, "lease": True, "sandbox": True, "interpreter": True, "processed": True, "parsed": True, "compiled": True, "executed": False, "reusable": False, "authorized": False})
    check("V1C2C2 CLEANUP", report.artifacts.removed if report.artifacts else False, True)
    check("V1C2C2 NO FORCED CLEANUP ON PASS", report.termination.attempted, False)

    _reset_registries()
    plan = _synthetic_plan(plan_fingerprint="9" * 64)
    lease, _, lease_services = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with tempfile.TemporaryDirectory(prefix="skynetvs-v1c2c2-failure-") as temporary:
        fake_failure = _FakeRuntime(_host(), lease_services, fail_before_ready=True)
        failed = _attest_developer_task_execution_compile_ast_composition(
            _host(), transaction, artifact_parent=Path(temporary), runtime=fake_failure
        )
    check("V1C2C2 FAILURE FAILS CLOSED", {"ok": failed.ok, "status": failed.status, "authorized": failed.execution_authorized, "executed": failed.changed_code_executed}, {"ok": False, "status": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED, "authorized": False, "executed": False})
    check("V1C2C2 FAILURE CONSUMES TRANSACTION", transaction.status().state, COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED)

    failed_host = replace(_host(), issues=(DeveloperTaskPreflightIssue(code="synthetic", check="host", message="synthetic"),))
    _reset_registries()
    plan = _synthetic_plan(plan_fingerprint="8" * 64)
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with tempfile.TemporaryDirectory(prefix="skynetvs-v1c2c2-host-failure-") as temporary:
        early = _attest_developer_task_execution_compile_ast_composition(
            failed_host, transaction, artifact_parent=Path(temporary), runtime=_FakeRuntime(_host(), None)
        )
    check("V1C2C2 FAILED HOST DOES NOT CLAIM", {"ok": early.ok, "transaction": transaction.status().state}, {"ok": False, "transaction": "issued"})

    check("V1C2C2 REPORT TYPE", isinstance(report, DeveloperTaskExecutionCompileAstCompositionReport), True)
    check("V1C2C2 REPORT REDACTION", "execution_authorized" in report.to_dict() and report.to_dict()["execution_authorized"] is False, True)

    summary = {
        "case_count": case_count,
        "fail_count": fail_count,
        "ok": fail_count == 0,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT,
        "policy_bytes_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256,
        "active_fake_status": report.status,
        "changed_code_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    print()
    print("=== V1C2C2 SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
