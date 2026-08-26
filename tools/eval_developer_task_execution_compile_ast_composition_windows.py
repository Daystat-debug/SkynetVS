from __future__ import annotations

"""Real Windows V1C2C2 active compile/AST composition smoke."""

import hashlib
import json
import os
import platform
import tempfile

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
    attest_developer_task_execution_compile_ast_composition,
)
from modules.developer.developer_task_execution_compile_ast_composition_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_compile_ast_plan import (
    issue_developer_task_execution_compile_ast_plan,
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


def main() -> int:
    if os.name != "nt" or platform.system().lower() != "windows":
        print("SKIP: V1C2C2 active composition Windows evaluator requires Windows.")
        return 0

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

    baseline_processes = snapshot_windows_sandbox_processes()
    if baseline_processes:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "sandbox_process_set_not_empty_before_v1c2c2",
                    "processes": [item.to_dict() for item in baseline_processes],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    runtime_zip = _runtime_zip_path()
    host_report = inspect_developer_task_execution_backend_host()
    prerequisites_ok = (
        host_report.ok
        and not host_report.running_sandbox_processes
        and runtime_zip.is_file()
        and runtime_zip.name == RUNTIME_SOURCE_FILE_NAME
    )
    if not prerequisites_ok:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "v1c2c2_windows_prerequisites_failed",
                    "host_ok": host_report.ok,
                    "host_issue_codes": list(host_report.issue_codes),
                    "running_processes": list(host_report.running_sandbox_processes),
                    "runtime_path": str(runtime_zip),
                    "runtime_name": runtime_zip.name,
                    "runtime_exists": runtime_zip.is_file(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    report = None
    source_before: dict[str, Any] | None = None
    source_after: dict[str, Any] | None = None
    workspace_before: dict[str, Any] | None = None
    workspace_after: dict[str, Any] | None = None
    active_tree_after: tuple[str, ...] = ()
    runtime_artifact_tree_after: tuple[str, ...] = ()

    with tempfile.TemporaryDirectory(
        prefix="skynetvs-v1c2c2-windows-",
        ignore_cleanup_errors=True,
    ) as temporary:
        parent = Path(temporary).resolve()
        fixture = _prepare(
            parent / "plan-fixture",
            baseline={
                "module.py": b"value = 1\n",
                "delete.py": b"delete = True\n",
                "notes.txt": b"old\n",
                "keep.py": b"keep = True\n",
            },
            changes={
                "module.py": b"value = 2\n",
                "delete.py": None,
                "notes.txt": b"new\n",
            },
            task_id="v1c2c2-windows-active-pass",
        )
        source_repo, _, _, _, _, workspace, _, _ = fixture
        workspace_repo = Path(workspace.repository_root)

        snapshot = _capture(fixture)
        plan = issue_developer_task_execution_compile_ast_plan(snapshot)

        runtime_artifact_parent = parent / "runtime-artifacts"
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

        active_parent = parent / "active"
        active_parent.mkdir()
        report = attest_developer_task_execution_compile_ast_composition(
            host_report,
            transaction,
            artifact_parent=active_parent,
        )

        source_after = _repository_snapshot(source_repo)
        workspace_after = _repository_snapshot(workspace_repo)
        active_tree_after = _snapshot_tree(active_parent)
        runtime_artifact_tree_after = _snapshot_tree(runtime_artifact_parent)

    assert report is not None
    check(
        "V1C2C2 ACTIVE ATTESTED PASS",
        {
            "ok": report.ok,
            "status": report.status,
            "policy_fingerprint": report.policy.policy_fingerprint,
            "policy_bytes_sha256": (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256
            ),
            "terminal_status": (
                report.signed_report.terminal_status
                if report.signed_report is not None
                else ""
            ),
            "controller_evidence_status": (
                report.controller_evidence_report.status
                if report.controller_evidence_report is not None
                else ""
            ),
            "controller_evidence_terminal_status": (
                report.controller_evidence_report.terminal_status
                if report.controller_evidence_report is not None
                else ""
            ),
            "controller_evidence_signature_valid": (
                report.controller_evidence_report.signature_valid
                if report.controller_evidence_report is not None
                else False
            ),
            "controller_legacy_terminal_signature_valid": (
                report.controller_evidence_report.legacy_terminal_signature_valid
                if report.controller_evidence_report is not None
                else False
            ),
            "controller_ready_stable": (
                report.controller_evidence_report.ready_stable
                if report.controller_evidence_report is not None
                else False
            ),
            "controller_evidence_stable": (
                report.controller_evidence_report.evidence_stable
                if report.controller_evidence_report is not None
                else False
            ),
            "controller_result_stable": (
                report.controller_evidence_report.result_stable
                if report.controller_evidence_report is not None
                else False
            ),
            "controller_private_relay_hash_bound": (
                report.controller_evidence_report.private_relay_hash_bound
                if report.controller_evidence_report is not None
                else False
            ),
            "boundary_ok": (
                report.signed_report.boundary_ok
                if report.signed_report is not None
                else False
            ),
            "check_passed": (
                report.signed_report.check_passed
                if report.signed_report is not None
                else False
            ),
            "signature_valid": (
                report.signed_report.signature_valid
                if report.signed_report is not None
                else False
            ),
            "result_verified": (
                report.signed_report.result_verified
                if report.signed_report is not None
                else False
            ),
            "relayed_result_hash_match": (
                report.artifacts is not None
                and report.signed_report is not None
                and report.artifacts.result_sha256
                == report.signed_report.result_sha256
            ),
            "controller_evidence_hashes_present": (
                report.artifacts is not None
                and len(report.artifacts.controller_evidence_payload_sha256) == 64
                and len(report.artifacts.controller_evidence_signature_sha256) == 64
            ),
            "all_processes_exited": report.all_processes_exited,
            "forced_cleanup_attempted": report.termination.attempted,
        },
        {
            "ok": True,
            "status": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED,
            "policy_fingerprint": (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT
            ),
            "policy_bytes_sha256": (
                DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256
            ),
            "terminal_status": "compile_ast_attested_passed",
            "controller_evidence_status": "controller_signed_success",
            "controller_evidence_terminal_status": "compile_ast_attested_passed",
            "controller_evidence_signature_valid": True,
            "controller_legacy_terminal_signature_valid": True,
            "controller_ready_stable": True,
            "controller_evidence_stable": True,
            "controller_result_stable": True,
            "controller_private_relay_hash_bound": True,
            "boundary_ok": True,
            "check_passed": True,
            "signature_valid": True,
            "result_verified": True,
            "relayed_result_hash_match": True,
            "controller_evidence_hashes_present": True,
            "all_processes_exited": True,
            "forced_cleanup_attempted": False,
        },
    )
    check(
        "V1C2C2 ACTIVE SECURITY FLAGS",
        {
            "claim_transaction_consumed": report.claim_transaction_consumed,
            "runtime_lease_claimed": report.runtime_lease_claimed,
            "sandbox_launched": report.sandbox_launched,
            "candidate_interpreter_executed": report.candidate_interpreter_executed,
            "changed_source_processed": report.changed_source_processed,
            "changed_source_ast_parsed": report.changed_source_ast_parsed,
            "changed_source_compiled": report.changed_source_compiled,
            "changed_code_executed": report.changed_code_executed,
            "reusable_lease_issued": report.reusable_lease_issued,
            "execution_authorized": report.execution_authorized,
            "artifacts_removed": report.artifacts.removed if report.artifacts else False,
            "issue_codes": list(report.issue_codes),
        },
        {
            "claim_transaction_consumed": True,
            "runtime_lease_claimed": True,
            "sandbox_launched": True,
            "candidate_interpreter_executed": True,
            "changed_source_processed": True,
            "changed_source_ast_parsed": True,
            "changed_source_compiled": True,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
            "artifacts_removed": True,
            "issue_codes": [],
        },
    )
    processes_after = snapshot_windows_sandbox_processes()
    check(
        "V1C2C2 HOST REPOSITORY AND ARTIFACT CLEANUP",
        {
            "source_unchanged": source_before == source_after,
            "workspace_unchanged": workspace_before == workspace_after,
            "known_sandbox_processes": [item.to_dict() for item in processes_after],
            "active_artifact_parent": list(active_tree_after),
            "runtime_artifact_parent": list(runtime_artifact_tree_after),
        },
        {
            "source_unchanged": True,
            "workspace_unchanged": True,
            "known_sandbox_processes": [],
            "active_artifact_parent": [],
            "runtime_artifact_parent": [],
        },
    )

    summary = {
        "case_count": case_count,
        "fail_count": fail_count,
        "ok": fail_count == 0,
        "status": report.status,
        "policy_fingerprint": report.policy.policy_fingerprint,
        "policy_bytes_sha256": (
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256
        ),
        "terminal_status": (
            report.signed_report.terminal_status if report.signed_report else ""
        ),
        "controller_evidence_status": (
            report.controller_evidence_report.status
            if report.controller_evidence_report
            else ""
        ),
        "controller_evidence_terminal_status": (
            report.controller_evidence_report.terminal_status
            if report.controller_evidence_report
            else ""
        ),
        "controller_evidence_signature_valid": (
            report.controller_evidence_report.signature_valid
            if report.controller_evidence_report
            else False
        ),
        "controller_ready_stable": (
            report.controller_evidence_report.ready_stable
            if report.controller_evidence_report
            else False
        ),
        "controller_evidence_stable": (
            report.controller_evidence_report.evidence_stable
            if report.controller_evidence_report
            else False
        ),
        "controller_result_stable": (
            report.controller_evidence_report.result_stable
            if report.controller_evidence_report
            else False
        ),
        "controller_private_relay_hash_bound": (
            report.controller_evidence_report.private_relay_hash_bound
            if report.controller_evidence_report
            else False
        ),
        "signature_valid": (
            report.signed_report.signature_valid if report.signed_report else False
        ),
        "result_verified": (
            report.signed_report.result_verified if report.signed_report else False
        ),
        "relayed_result_hash_match": (
            report.artifacts is not None
            and report.signed_report is not None
            and report.artifacts.result_sha256
            == report.signed_report.result_sha256
        ),
        "all_processes_exited": report.all_processes_exited,
        "forced_cleanup_attempted": report.termination.attempted,
        "artifacts_removed": report.artifacts.removed if report.artifacts else False,
        "changed_code_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    print()
    print("=== V1C2C2 WINDOWS SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
