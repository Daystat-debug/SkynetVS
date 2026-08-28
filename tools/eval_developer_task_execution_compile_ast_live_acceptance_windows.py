from __future__ import annotations

"""Future real Windows V1C2C3 three-row live acceptance harness.

RC034 authorizes this source to exist but does not authorize its execution.
The harness therefore requires an explicit host-side environment guard before
it performs any host inspection, capability issue/claim, or Sandbox launch.
"""

import argparse
import hashlib
import hmac
import json
import os
import platform
import secrets
import tempfile

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_backend_host import (
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_backend_lifecycle_windows import (
    snapshot_windows_sandbox_processes,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction import (
    issue_developer_task_execution_compile_ast_claim_transaction,
)
from modules.developer.developer_task_execution_compile_ast_composition import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED,
    _CompileAstCompositionRuntime,
    _attest_developer_task_execution_compile_ast_composition,
    attest_developer_task_execution_compile_ast_composition,
)
from modules.developer.developer_task_execution_compile_ast_contract import (
    parse_compile_ast_result,
)
from modules.developer.developer_task_execution_compile_ast_plan import (
    issue_developer_task_execution_compile_ast_plan,
)
from modules.developer.developer_task_execution_compile_ast_verifier import (
    DeveloperTaskExecutionCompileAstTranscriptReport,
    verify_developer_task_execution_compile_ast_transcript,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    build_developer_task_execution_runtime_bundle,
)
from modules.developer.developer_task_execution_runtime_lease import (
    issue_developer_task_execution_runtime_lease,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_SOURCE_FILE_NAME,
)
from tools.eval_developer_task_execution_workspace_snapshot import (
    _capture,
    _git,
    _prepare,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_AUTHORITY_ENV = "SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED"
ACTIVE_AUTHORITY_VALUE = "1"
HISTORICAL_V1C2C3_EVIDENCE_IDENTITY = (
    "b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8"
)
BOUNDARY_FAULT_KIND = "post_ready_pre_authorization_source_substitution"
INVALID_SYNTAX_SOURCE = b"def broken(:\n"

ROW_PASS = "live_pass"
ROW_SYNTAX = "authentic_syntax_failure"
ROW_BOUNDARY = "signed_post_ready_boundary_failure"
ROWS = (ROW_PASS, ROW_SYNTAX, ROW_BOUNDARY)
ROW_PATH_LABELS = {
    ROW_PASS: "p",
    ROW_SYNTAX: "s",
    ROW_BOUNDARY: "b",
}

_ROW_AUTHORITY_DIGEST: bytes | None = None


class _RowAuthority:
    __slots__ = ("row", "_token")

    def __init__(self, row: str, token: bytes) -> None:
        self.row = row
        self._token = token


def _mint_row_authority(row: str) -> _RowAuthority:
    global _ROW_AUTHORITY_DIGEST
    if row not in ROWS:
        raise ValueError(f"unsupported V1C2C3 row: {row}")
    if os.environ.get(ACTIVE_AUTHORITY_ENV, "") != ACTIVE_AUTHORITY_VALUE:
        raise RuntimeError("V1C2C3 row authority cannot be minted before host guard")
    if _ROW_AUTHORITY_DIGEST is not None:
        raise RuntimeError("V1C2C3 row authority is already active")
    token = secrets.token_bytes(32)
    _ROW_AUTHORITY_DIGEST = hashlib.sha256(token).digest()
    return _RowAuthority(row, token)


def _consume_row_authority(authority: _RowAuthority, row: str) -> None:
    global _ROW_AUTHORITY_DIGEST
    if (
        type(authority) is not _RowAuthority
        or authority.row != row
        or _ROW_AUTHORITY_DIGEST is None
        or not hmac.compare_digest(
            hashlib.sha256(authority._token).digest(),
            _ROW_AUTHORITY_DIGEST,
        )
    ):
        raise RuntimeError("V1C2C3 row authority is missing, forged, or mismatched")
    _ROW_AUTHORITY_DIGEST = None


def _parse_row(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(
        description="Run exactly one authorized V1C2C3 live acceptance row."
    )
    parser.add_argument(
        "--row",
        required=True,
        choices=ROWS,
        help="One locked V1C2C3 row to execute.",
    )
    return str(parser.parse_args(argv).row)


@dataclass(frozen=True)
class _CapturedTranscript:
    result_bytes: bytes | None
    terminal_payload_bytes: bytes
    terminal_signature_bytes: bytes


class _CaptureRuntime(_CompileAstCompositionRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.captured: _CapturedTranscript | None = None

    @staticmethod
    def _first(value: tuple[bytes, bytes] | None) -> bytes | None:
        if value is None:
            return None
        return value[0]

    def verify_controller_evidence(self, expectation: Any, **kwargs: Any):
        terminal_payload = self._first(kwargs.get("terminal_payload_reads"))
        terminal_signature = self._first(kwargs.get("terminal_signature_reads"))
        if terminal_payload is not None and terminal_signature is not None:
            self.captured = _CapturedTranscript(
                result_bytes=self._first(kwargs.get("relayed_result_reads")),
                terminal_payload_bytes=terminal_payload,
                terminal_signature_bytes=terminal_signature,
            )
        return super().verify_controller_evidence(expectation, **kwargs)


class _BoundaryFaultRuntime(_CaptureRuntime):
    """Eval-only post-ready/pre-authorization source substitution."""

    def __init__(self) -> None:
        super().__init__()
        self.fault_kind = BOUNDARY_FAULT_KIND
        self.fault_path: Path | None = None
        self.original_bytes: bytes | None = None
        self.fault_applied = False
        self.fault_restored = False
        self.materialization_calls = 0

    def publish_authorize(self, path: Path, data: bytes) -> tuple[str, str]:
        prepared = getattr(self, "_v1c2c3_prepared", None)
        if prepared is None:
            raise RuntimeError(
                "V1C2C3 prepared artifacts are unavailable for boundary fault"
            )
        source_paths = sorted(prepared.source_root.glob("source-*.py"))
        if not source_paths:
            raise RuntimeError(
                "V1C2C3 boundary fault requires one materialized Python source"
            )
        self.fault_path = source_paths[0]
        self.original_bytes = self.fault_path.read_bytes()
        substituted = b"value = 999999\n"
        if substituted == self.original_bytes:
            substituted = b"value = 999998\n"
        self.fault_path.write_bytes(substituted)
        self.fault_applied = True
        return super().publish_authorize(path, data)

    def prepare_artifacts(self, **kwargs: Any):
        prepared = super().prepare_artifacts(**kwargs)
        self._v1c2c3_prepared = prepared
        return prepared

    def verify_materialization(self, prepared: Any):
        self.materialization_calls += 1
        if (
            self.fault_applied
            and not self.fault_restored
            and self.materialization_calls >= 4
        ):
            if self.fault_path is None or self.original_bytes is None:
                raise RuntimeError(
                    "V1C2C3 boundary fault restore state is incomplete"
                )
            self.fault_path.write_bytes(self.original_bytes)
            self.fault_restored = True
        return super().verify_materialization(prepared)


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


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_bytes(root: Path, *args: str) -> bytes:
    return bytes(_git(root, *args, binary=True).stdout)


def _index_path(root: Path) -> Path:
    raw = _git(root, "rev-parse", "--git-path", "index").stdout.strip()
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _object_snapshot(root: Path) -> dict[str, tuple[int, str]]:
    git_dir = Path(_git(root, "rev-parse", "--absolute-git-dir").stdout.strip())
    objects = git_dir / "objects"
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(objects.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(objects).as_posix()
        result[relative] = (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    return result


def _repository_snapshot(root: Path) -> dict[str, Any]:
    index = _index_path(root)
    return {
        "index": _sha256_file(index),
        "status": _git_bytes(root, "status", "--porcelain=v2", "-z"),
        "objects": _object_snapshot(root),
        "head": _git(root, "rev-parse", "HEAD").stdout.strip(),
    }


def _snapshot_tree(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(
            str(path.relative_to(root)).replace(os.sep, "/")
            for path in root.rglob("*")
        )
    )


def _verify_captured_transcript(
    report: Any,
    runtime: _CaptureRuntime,
) -> DeveloperTaskExecutionCompileAstTranscriptReport:
    pin = report.pin_report
    captured = runtime.captured
    if pin is None or not pin.ok:
        raise RuntimeError(
            "V1C2C3 requires a genuine successful pre-authorization pin"
        )
    if (
        pin.source_manifest is None
        or pin.request is None
        or pin.ready is None
        or pin.authorize is None
    ):
        raise RuntimeError("V1C2C3 pinned transcript is incomplete")
    if captured is None:
        raise RuntimeError(
            "V1C2C3 controller transport did not expose terminal bytes"
        )
    return verify_developer_task_execution_compile_ast_transcript(
        pin,
        source_manifest_bytes=pin.source_manifest.canonical_bytes,
        request_bytes=pin.request.canonical_bytes,
        ready_bytes=pin.ready.canonical_bytes,
        authorize_bytes=pin.authorize.canonical_bytes,
        result_bytes=captured.result_bytes,
        terminal_payload_bytes=captured.terminal_payload_bytes,
        terminal_signature_bytes=captured.terminal_signature_bytes,
    )


def _row_changes(row: str) -> dict[str, bytes | None]:
    if row == ROW_SYNTAX:
        return {
            "module.py": INVALID_SYNTAX_SOURCE,
            "delete.py": None,
            "notes.txt": b"new\n",
        }
    if row == ROW_BOUNDARY:
        return {
            "module.py": b"value = 3\n",
            "delete.py": None,
            "notes.txt": b"new\n",
        }
    return {
        "module.py": b"value = 2\n",
        "delete.py": None,
        "notes.txt": b"new\n",
    }


def _run_case(
    row: str,
    *,
    authority: _RowAuthority,
    runtime_zip: Path,
    parent: Path,
) -> dict[str, Any]:
    _consume_row_authority(authority, row)
    if row not in ROWS:
        raise ValueError(f"unsupported V1C2C3 row: {row}")

    baseline_processes = snapshot_windows_sandbox_processes()
    if baseline_processes:
        raise RuntimeError(
            "V1C2C3 requires an empty Sandbox process set before every row"
        )

    host_report = inspect_developer_task_execution_backend_host()
    if not host_report.ok or host_report.running_sandbox_processes:
        raise RuntimeError(
            "V1C2C3 fresh host report failed: "
            + ",".join(host_report.issue_codes)
        )

    row_label = ROW_PATH_LABELS[row]
    row_root = parent / row_label
    row_root.mkdir()
    fixture = _prepare(
        row_root / "plan-fixture",
        baseline={
            "module.py": b"value = 1\n",
            "delete.py": b"delete = True\n",
            "notes.txt": b"old\n",
            "keep.py": b"keep = True\n",
        },
        changes=_row_changes(row),
        task_id=f"v3-{row_label}",
    )
    source_repo, _, _, _, _, workspace, _, _ = fixture
    workspace_repo = Path(workspace.repository_root)

    snapshot = _capture(fixture)
    plan = issue_developer_task_execution_compile_ast_plan(snapshot)

    runtime_artifact_parent = row_root / "runtime-artifacts"
    runtime_artifact_parent.mkdir()
    runtime_bundle = build_developer_task_execution_runtime_bundle(
        runtime_zip,
        artifact_parent=runtime_artifact_parent,
    )
    lease = issue_developer_task_execution_runtime_lease(
        host_report,
        runtime_bundle,
    )
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(
        plan,
        lease,
    )

    source_before = _repository_snapshot(source_repo)
    workspace_before = _repository_snapshot(workspace_repo)

    active_parent = row_root / "active"
    active_parent.mkdir()
    runtime: _CaptureRuntime | None = None
    if row == ROW_PASS:
        report = attest_developer_task_execution_compile_ast_composition(
            host_report,
            transaction,
            artifact_parent=active_parent,
        )
        signed = report.signed_report
    elif row == ROW_SYNTAX:
        runtime = _CaptureRuntime()
        report = _attest_developer_task_execution_compile_ast_composition(
            host_report,
            transaction,
            artifact_parent=active_parent,
            runtime=runtime,
        )
        signed = _verify_captured_transcript(report, runtime)
    else:
        runtime = _BoundaryFaultRuntime()
        report = _attest_developer_task_execution_compile_ast_composition(
            host_report,
            transaction,
            artifact_parent=active_parent,
            runtime=runtime,
        )
        signed = _verify_captured_transcript(report, runtime)

    if signed is None:
        raise RuntimeError(
            f"V1C2C3 {row} did not yield signed transcript evidence"
        )

    source_after = _repository_snapshot(source_repo)
    workspace_after = _repository_snapshot(workspace_repo)
    active_tree_after = _snapshot_tree(active_parent)
    runtime_tree_after = _snapshot_tree(runtime_artifact_parent)
    processes_after = snapshot_windows_sandbox_processes()

    pin = report.pin_report
    if pin is None or pin.expectation is None:
        raise RuntimeError(f"V1C2C3 {row} missing fresh pin expectation")
    expectation = pin.expectation

    captured_result_payload: dict[str, Any] | None = None
    if runtime is not None and runtime.captured is not None:
        if runtime.captured.result_bytes is not None:
            captured_result_payload = parse_compile_ast_result(
                runtime.captured.result_bytes
            ).to_dict()

    controller = report.controller_evidence_report
    return {
        "row": row,
        "report": report,
        "signed": signed,
        "controller": controller,
        "captured_result": captured_result_payload,
        "request_id": expectation.request_id,
        "runtime_lease_fingerprint": expectation.runtime_lease_fingerprint,
        "plan_fingerprint": expectation.plan_fingerprint,
        "public_key_sha256": signed.public_key_sha256,
        "source_unchanged": source_before == source_after,
        "workspace_unchanged": workspace_before == workspace_after,
        "active_tree_after": active_tree_after,
        "runtime_tree_after": runtime_tree_after,
        "processes_after": processes_after,
        "boundary_fault_applied": bool(
            isinstance(runtime, _BoundaryFaultRuntime)
            and runtime.fault_applied
        ),
        "boundary_fault_restored": bool(
            isinstance(runtime, _BoundaryFaultRuntime)
            and runtime.fault_restored
        ),
        "boundary_fault_kind": (
            runtime.fault_kind
            if isinstance(runtime, _BoundaryFaultRuntime)
            else ""
        ),
    }


def main(argv: list[str] | None = None) -> int:
    selected_row = _parse_row(argv)

    if os.environ.get(ACTIVE_AUTHORITY_ENV, "") != ACTIVE_AUTHORITY_VALUE:
        print(
            "BLOCKED: V1C2C3 active matrix is blocked without later roadmap authority."
        )
        print(f"Required host guard: {ACTIVE_AUTHORITY_ENV}=1")
        return 2

    if os.name != "nt" or platform.system().lower() != "windows":
        print("SKIP: V1C2C3 live acceptance requires Windows.")
        return 0

    runtime_zip = _runtime_zip_path()
    if not runtime_zip.is_file() or runtime_zip.name != RUNTIME_SOURCE_FILE_NAME:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "v1c2c3_runtime_source_unavailable",
                    "row": selected_row,
                    "runtime_path": str(runtime_zip),
                    "runtime_exists": runtime_zip.is_file(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    initial_processes = snapshot_windows_sandbox_processes()
    if initial_processes:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "sandbox_process_set_not_empty_before_v1c2c3",
                    "row": selected_row,
                    "processes": [
                        item.to_dict() for item in initial_processes
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    authority = _mint_row_authority(selected_row)

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

    with tempfile.TemporaryDirectory(
        prefix="sv3-",
        ignore_cleanup_errors=True,
    ) as temporary:
        parent = Path(temporary).resolve()
        item = _run_case(
            selected_row,
            authority=authority,
            runtime_zip=runtime_zip,
            parent=parent,
        )

    report = item["report"]
    signed = item["signed"]
    controller = item["controller"]

    if selected_row == ROW_PASS:
        check(
            "V1C2C3 LIVE PASS",
            {
                "composition_ok": report.ok,
                "composition_status": report.status,
                "signed_ok": signed.ok,
                "terminal_status": signed.terminal_status,
                "boundary_ok": signed.boundary_ok,
                "check_passed": signed.check_passed,
                "controller_status": controller.status if controller else "",
                "controller_terminal": (
                    controller.terminal_status if controller else ""
                ),
            },
            {
                "composition_ok": True,
                "composition_status": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED,
                "signed_ok": True,
                "terminal_status": "compile_ast_attested_passed",
                "boundary_ok": True,
                "check_passed": True,
                "controller_status": "controller_signed_success",
                "controller_terminal": "compile_ast_attested_passed",
            },
        )
    elif selected_row == ROW_SYNTAX:
        syntax_result = item["captured_result"] or {}
        syntax_files = syntax_result.get("files", [])
        syntax_errors = [
            source_item.get("error")
            for source_item in syntax_files
            if isinstance(source_item, dict)
            and source_item.get("error") is not None
        ]
        check(
            "V1C2C3 AUTHENTIC SYNTAX FAILURE",
            {
                "composition_ok": report.ok,
                "composition_status": report.status,
                "signed_ok": signed.ok,
                "terminal_status": signed.terminal_status,
                "boundary_ok": signed.boundary_ok,
                "check_passed": signed.check_passed,
                "controller_status": controller.status if controller else "",
                "controller_terminal": (
                    controller.terminal_status if controller else ""
                ),
                "trusted_interpreter_executed": syntax_result.get(
                    "trusted_interpreter_executed"
                ),
                "changed_source_processed": syntax_result.get(
                    "changed_source_processed"
                ),
                "changed_source_ast_parsed": syntax_result.get(
                    "changed_source_ast_parsed"
                ),
                "changed_source_compiled": syntax_result.get(
                    "changed_source_compiled"
                ),
                "changed_code_executed": syntax_result.get(
                    "changed_code_executed"
                ),
                "syntax_error_type": (
                    syntax_errors[0].get("type") if syntax_errors else ""
                ),
                "raw_source_absent": all(
                    isinstance(error, dict) and "text" not in error
                    for error in syntax_errors
                ),
            },
            {
                "composition_ok": False,
                "composition_status": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED,
                "signed_ok": True,
                "terminal_status": "compile_ast_attested_failed",
                "boundary_ok": True,
                "check_passed": False,
                "controller_status": "controller_signed_success",
                "controller_terminal": "compile_ast_attested_failed",
                "trusted_interpreter_executed": True,
                "changed_source_processed": True,
                "changed_source_ast_parsed": False,
                "changed_source_compiled": False,
                "changed_code_executed": False,
                "syntax_error_type": "SyntaxError",
                "raw_source_absent": True,
            },
        )
    else:
        check(
            "V1C2C3 SIGNED POST-READY BOUNDARY FAILURE",
            {
                "composition_ok": report.ok,
                "composition_status": report.status,
                "signed_ok": signed.ok,
                "terminal_status": signed.terminal_status,
                "boundary_ok": signed.boundary_ok,
                "check_passed": signed.check_passed,
                "result_sha256": signed.result_sha256,
                "controller_status": controller.status if controller else "",
                "controller_terminal": (
                    controller.terminal_status if controller else ""
                ),
                "fault_applied": item["boundary_fault_applied"],
                "fault_restored": item["boundary_fault_restored"],
                "fault_kind": item["boundary_fault_kind"],
            },
            {
                "composition_ok": False,
                "composition_status": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED,
                "signed_ok": True,
                "terminal_status": "compile_ast_boundary_failed",
                "boundary_ok": False,
                "check_passed": False,
                "result_sha256": None,
                "controller_status": "controller_signed_success",
                "controller_terminal": "compile_ast_boundary_failed",
                "fault_applied": True,
                "fault_restored": True,
                "fault_kind": BOUNDARY_FAULT_KIND,
            },
        )

    check(
        "V1C2C3 SINGLE ROW FRESH CAPABILITY EVIDENCE",
        {
            "row": item["row"],
            "request_id_length": len(item["request_id"]),
            "runtime_lease_fingerprint_length": len(
                item["runtime_lease_fingerprint"]
            ),
            "plan_fingerprint_length": len(item["plan_fingerprint"]),
            "controller_public_key_sha256_length": len(
                item["public_key_sha256"]
            ),
        },
        {
            "row": selected_row,
            "request_id_length": 32,
            "runtime_lease_fingerprint_length": 64,
            "plan_fingerprint_length": 64,
            "controller_public_key_sha256_length": 64,
        },
    )

    check(
        "V1C2C3 ACTIVE SECURITY FLAGS",
        {
            "claim_transaction_consumed": report.claim_transaction_consumed,
            "runtime_lease_claimed": report.runtime_lease_claimed,
            "sandbox_launched": report.sandbox_launched,
            "changed_code_executed": report.changed_code_executed,
            "reusable_lease_issued": report.reusable_lease_issued,
            "execution_authorized": report.execution_authorized,
        },
        {
            "claim_transaction_consumed": True,
            "runtime_lease_claimed": True,
            "sandbox_launched": True,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        },
    )

    check(
        "V1C2C3 ROW CLEANUP",
        {
            "all_processes_exited": report.all_processes_exited,
            "forced_cleanup_attempted": report.termination.attempted,
            "artifacts_removed": (
                report.artifacts.removed
                if report.artifacts is not None
                else False
            ),
            "source_unchanged": item["source_unchanged"],
            "workspace_unchanged": item["workspace_unchanged"],
            "active_tree_after": list(item["active_tree_after"]),
            "runtime_tree_after": list(item["runtime_tree_after"]),
            "processes_after": [
                process.to_dict() for process in item["processes_after"]
            ],
        },
        {
            "all_processes_exited": True,
            "forced_cleanup_attempted": False,
            "artifacts_removed": True,
            "source_unchanged": True,
            "workspace_unchanged": True,
            "active_tree_after": [],
            "runtime_tree_after": [],
            "processes_after": [],
        },
    )

    final_processes = snapshot_windows_sandbox_processes()
    check(
        "V1C2C3 FINAL SANDBOX PROCESS SET",
        [process.to_dict() for process in final_processes],
        [],
    )

    summary = {
        "case_count": case_count,
        "fail_count": fail_count,
        "ok": fail_count == 0,
        "historical_evidence_identity": HISTORICAL_V1C2C3_EVIDENCE_IDENTITY,
        "row": selected_row,
        "request_id": item["request_id"],
        "runtime_lease_fingerprint": item["runtime_lease_fingerprint"],
        "plan_fingerprint": item["plan_fingerprint"],
        "controller_public_key_sha256": item["public_key_sha256"],
        "terminal_status": signed.terminal_status,
        "boundary_ok": signed.boundary_ok,
        "check_passed": signed.check_passed,
        "result_sha256": signed.result_sha256,
        "changed_code_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    print()
    print("=== V1C2C3 WINDOWS ROW SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
