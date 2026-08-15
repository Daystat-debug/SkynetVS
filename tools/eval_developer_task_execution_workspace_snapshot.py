from __future__ import annotations

import copy
import hashlib
import inspect
import json
import pickle
import subprocess
import tempfile
import unicodedata

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_workspace_snapshot as snapshot_module

from modules.developer.developer_task_check_static import run_developer_task_static_checks
from modules.developer.developer_task_contract import DeveloperTaskCheck, DeveloperTaskManifest
from modules.developer.developer_task_execution_workspace_snapshot import (
    DeveloperTaskExecutionWorkspaceSnapshotError,
    _TreeIdentityEntry,
    _parse_tree_identity,
    _validate_repository_path,
    _validate_tree_identity_entries,
    capture_developer_task_execution_workspace_snapshot,
)
from modules.developer.developer_task_execution_workspace_snapshot_policy import (
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_FILE_COUNT,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_TOTAL_BYTES,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID,
    developer_task_execution_workspace_snapshot_policy_fingerprint,
    validate_developer_task_execution_workspace_snapshot_policy,
)
from modules.developer.developer_task_patch_apply import apply_developer_task_patch
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_preflight_composition import run_developer_task_preflight
from modules.developer.developer_task_workspace import create_developer_task_workspace


def _git(root: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
        check=True,
    )


def _init_repo(root: Path, files: dict[str, bytes]) -> str:
    root.mkdir(parents=True)
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "eval@example.com")
    _git(root, "config", "user.name", "V1C1A Eval")
    _git(root, "config", "core.autocrlf", "false")
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "initial")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _make_patch(repo: Path, changes: dict[str, bytes | None]) -> bytes:
    for relative, content in changes.items():
        path = repo / relative
        if content is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    _git(repo, "add", "-A")
    payload = _git(
        repo,
        "diff",
        "--cached",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
        "HEAD",
        "--",
        binary=True,
    ).stdout
    _git(repo, "reset", "--hard", "HEAD")
    _git(repo, "clean", "-fd")
    return bytes(payload)


def _manifest(
    base_commit: str,
    patch_bytes: bytes,
    allowed_files: tuple[str, ...],
    *,
    task_id: str,
) -> DeveloperTaskManifest:
    return DeveloperTaskManifest(
        schema_version=1,
        task_kind="patch",
        task_id=task_id,
        title="Evaluate V1C1A exact result-tree snapshot",
        project="SkynetVS",
        origin="manual",
        source_ref="eval:v1c1a-workspace-snapshot",
        source_sha256="a" * 64,
        base_commit=base_commit,
        patch_file="changes.patch",
        patch_sha256=hashlib.sha256(patch_bytes).hexdigest(),
        allowed_files=allowed_files,
        checks=(
            DeveloperTaskCheck(type="git_diff_check"),
            DeveloperTaskCheck(type="py_compile", scope="changed_python_files"),
            DeveloperTaskCheck(type="python_module", module="tools.eval_snapshot_dummy"),
            DeveloperTaskCheck(type="pipeline", flow="check"),
        ),
        install_policy="manual_confirmation",
    )


def _prepare(
    root: Path,
    *,
    baseline: dict[str, bytes],
    changes: dict[str, bytes | None],
    task_id: str,
):
    repo = root / "source"
    task_root = root / "task"
    workspace_parent = root / "workspaces"
    base_commit = _init_repo(repo, baseline)
    patch_bytes = _make_patch(repo, changes)
    task_root.mkdir()
    workspace_parent.mkdir()
    manifest = _manifest(
        base_commit,
        patch_bytes,
        tuple(sorted(changes)),
        task_id=task_id,
    )
    (task_root / manifest.patch_file).write_bytes(patch_bytes)
    preflight = run_developer_task_preflight(
        manifest,
        project_root=repo,
        task_root=task_root,
    )
    assert preflight.ok, preflight.to_dict()
    workspace = create_developer_task_workspace(
        manifest,
        preflight_report=preflight,
        workspace_parent=workspace_parent,
    )
    assert workspace.ok, workspace.to_dict()
    apply_report = apply_developer_task_patch(
        manifest,
        preflight_report=preflight,
        workspace_report=workspace,
        workspace_parent=workspace_parent,
    )
    assert apply_report.ok, apply_report.to_dict()
    static_report = run_developer_task_static_checks(
        manifest,
        preflight_report=preflight,
        workspace_report=workspace,
        patch_apply_report=apply_report,
        workspace_parent=workspace_parent,
    )
    assert static_report.ok, static_report.to_dict()
    return repo, task_root, workspace_parent, manifest, preflight, workspace, apply_report, static_report


def _capture(items: tuple[Any, ...]):
    _, _, parent, manifest, preflight, workspace, apply_report, static_report = items
    return capture_developer_task_execution_workspace_snapshot(
        manifest,
        preflight,
        workspace,
        apply_report,
        static_report,
        workspace_parent=parent,
    )


def _error_code(callback) -> str:
    try:
        callback()
    except DeveloperTaskExecutionWorkspaceSnapshotError as exc:
        return exc.code
    return ""


def _issue(code: str = "forced_failure") -> DeveloperTaskPreflightIssue:
    return DeveloperTaskPreflightIssue(code=code, check="eval", message="forced")


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        print()
        print(f"=== {name} ===")
        print(json.dumps(
            {"actual": actual, "expected": expected, "ok": ok},
            ensure_ascii=False,
            indent=2,
            default=str,
        ))
        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    check(
        "V1C1A PINNED SNAPSHOT POLICY SELF CHECKS",
        {
            "errors": list(validate_developer_task_execution_workspace_snapshot_policy()),
            "policy_id": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY.policy_id,
            "fingerprint": developer_task_execution_workspace_snapshot_policy_fingerprint(),
            "expected_fingerprint": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT,
            "network": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY.network_allowed,
            "runtime_lease_input": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY.runtime_lease_input,
            "authorized": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY.execution_authorized,
        },
        {
            "errors": [],
            "policy_id": DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID,
            "fingerprint": "601c727e9b725f1f868a144fa7b975bbb7a35a878c74c2d25bda0a7677a6cd55",
            "expected_fingerprint": "601c727e9b725f1f868a144fa7b975bbb7a35a878c74c2d25bda0a7677a6cd55",
            "network": False,
            "runtime_lease_input": False,
            "authorized": False,
        },
    )

    signature = inspect.signature(capture_developer_task_execution_workspace_snapshot)
    check(
        "V1C1A PUBLIC API ACCEPTS ONLY TYPED CHAIN AND WORKSPACE PARENT",
        {
            name: {
                "kind": parameter.kind.name,
                "default": None if parameter.default is inspect.Parameter.empty else parameter.default,
            }
            for name, parameter in signature.parameters.items()
        },
        {
            "manifest": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "preflight_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "workspace_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "patch_apply_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "static_check_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "workspace_parent": {"kind": "KEYWORD_ONLY", "default": None},
        },
    )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        fixture = _prepare(
            Path(temp_dir),
            baseline={
                "module.py": b"value = 1\n",
                "unchanged.txt": b"unchanged\n",
                "binary.dat": b"abc\x00def",
                "delete.txt": b"remove me\n",
            },
            changes={
                "module.py": b"value = 2\n",
                "delete.txt": None,
            },
            task_id="v1c1a-success",
        )
        snapshot = _capture(fixture)
        report = snapshot.report
        check(
            "V1C1A EXACT RESULT TREE BUILDS NON AUTHORIZING SNAPSHOT",
            {
                "ok": report.ok,
                "format": report.snapshot_format,
                "files": report.file_count,
                "paths": [item.path for item in report.files],
                "changed": list(report.changed_files),
                "deleted": list(report.deleted_files),
                "tree_manifest_len": len(report.tree_manifest_sha256),
                "snapshot_len": len(report.snapshot_fingerprint),
                "state": snapshot.status().state,
                "repository_mutated": report.repository_mutated,
                "network": report.network_attempted,
                "download": report.artifact_download_attempted,
                "install": report.dependency_install_attempted,
                "sandbox": report.sandbox_launched,
                "lease_issued": report.runtime_lease_issued,
                "lease_claimed": report.runtime_lease_claimed,
                "candidate": report.candidate_interpreter_executed,
                "changed_exec": report.changed_code_executed,
                "reusable": report.reusable_lease_issued,
                "authorized": report.execution_authorized,
            },
            {
                "ok": True,
                "format": "exact_git_result_tree_snapshot_v1",
                "files": 3,
                "paths": ["binary.dat", "module.py", "unchanged.txt"],
                "changed": ["delete.txt", "module.py"],
                "deleted": ["delete.txt"],
                "tree_manifest_len": 64,
                "snapshot_len": 64,
                "state": "issued",
                "repository_mutated": False,
                "network": False,
                "download": False,
                "install": False,
                "sandbox": False,
                "lease_issued": False,
                "lease_claimed": False,
                "candidate": False,
                "changed_exec": False,
                "reusable": False,
                "authorized": False,
            },
        )
        serialized = json.dumps(report.to_dict(), ensure_ascii=False)
        check(
            "V1C1A DURABLE REPORT EXPOSES HASHED IDENTITIES BUT NO SOURCE BYTES OR HOST PATHS",
            {
                "json": isinstance(serialized, str),
                "value2_absent": "value = 2" not in serialized,
                "nul_payload_absent": "abc" not in serialized,
                "workspace_root_absent": fixture[5].workspace_root not in serialized,
                "task_root_absent": fixture[5].task_root not in serialized,
                "sha_present": report.files[0].sha256 in serialized,
            },
            {
                "json": True,
                "value2_absent": True,
                "nul_payload_absent": True,
                "workspace_root_absent": True,
                "task_root_absent": True,
                "sha_present": True,
            },
        )
        try:
            report.file_count = 0
            frozen = False
        except FrozenInstanceError:
            frozen = True
        check("V1C1A REPORT AND FILE IDENTITIES ARE IMMUTABLE", frozen, True)

        noncopyable: dict[str, bool] = {}
        for name, callback in {
            "copy": lambda: copy.copy(snapshot),
            "deepcopy": lambda: copy.deepcopy(snapshot),
            "pickle": lambda: pickle.dumps(snapshot),
        }.items():
            try:
                callback()
                noncopyable[name] = False
            except TypeError:
                noncopyable[name] = True
        check(
            "V1C1A SNAPSHOT CAPABILITY IS NON COPYABLE AND NON SERIALIZABLE",
            noncopyable,
            {"copy": True, "deepcopy": True, "pickle": True},
        )
        material = snapshot.claim_for_plan()
        check(
            "V1C1A SINGLE CLAIM RETURNS EXACT PRIVATE RESULT TREE BYTES",
            {
                "state": snapshot.status().state,
                "paths": list(material.paths),
                "module": material.exact_file_bytes("module.py").decode("utf-8"),
                "binary_sha": hashlib.sha256(material.exact_file_bytes("binary.dat")).hexdigest(),
                "reported_binary_sha": material.entry("binary.dat").sha256,
                "deleted_absent": "delete.txt" not in material.paths,
            },
            {
                "state": "claimed_for_plan",
                "paths": ["binary.dat", "module.py", "unchanged.txt"],
                "module": "value = 2\n",
                "binary_sha": material.entry("binary.dat").sha256,
                "reported_binary_sha": material.entry("binary.dat").sha256,
                "deleted_absent": True,
            },
        )
        check(
            "V1C1A CLAIM REPLAY FAILS CLOSED",
            _error_code(snapshot.claim_for_plan),
            "workspace_snapshot_already_claimed",
        )
        material_guards: dict[str, bool] = {}
        for name, callback in {
            "copy": lambda: copy.copy(material),
            "deepcopy": lambda: copy.deepcopy(material),
            "pickle": lambda: pickle.dumps(material),
        }.items():
            try:
                callback()
                material_guards[name] = False
            except TypeError:
                material_guards[name] = True
        check(
            "V1C1A CLAIMED MATERIAL IS NON COPYABLE AND NON SERIALIZABLE",
            material_guards,
            {"copy": True, "deepcopy": True, "pickle": True},
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        fixture = _prepare(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="v1c1a-deterministic",
        )
        first = _capture(fixture)
        second = _capture(fixture)
        check(
            "V1C1A REPEATED EXACT RESULT TREE SNAPSHOT IS DETERMINISTIC",
            {
                "same_report": first.report == second.report,
                "same_snapshot": first.report.snapshot_fingerprint == second.report.snapshot_fingerprint,
                "same_tree": first.report.tree_manifest_sha256 == second.report.tree_manifest_sha256,
            },
            {"same_report": True, "same_snapshot": True, "same_tree": True},
        )
        expires_at = snapshot_module._REGISTRY[first].expires_at_ns
        with patch.object(snapshot_module._SERVICES, "monotonic_ns", return_value=expires_at):
            check("V1C1A EXPIRED CAPABILITY BECOMES TERMINAL", first.status().state, "expired")
            check(
                "V1C1A EXPIRED CAPABILITY CANNOT BE CLAIMED",
                _error_code(first.claim_for_plan),
                "workspace_snapshot_expired",
            )
        with patch.object(snapshot_module._SERVICES, "monotonic_ns", return_value=-1):
            check("V1C1A INVALID CLOCK INVALIDATES CAPABILITY", second.status().state, "invalidated")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        fixture = _prepare(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="v1c1a-input-validation",
        )
        repo, _, parent, manifest, preflight, workspace, apply_report, static_report = fixture
        raw_results: dict[str, bool] = {}
        calls = {
            "manifest": lambda: capture_developer_task_execution_workspace_snapshot({}, preflight, workspace, apply_report, static_report, workspace_parent=parent),
            "preflight": lambda: capture_developer_task_execution_workspace_snapshot(manifest, {}, workspace, apply_report, static_report, workspace_parent=parent),
            "workspace": lambda: capture_developer_task_execution_workspace_snapshot(manifest, preflight, {}, apply_report, static_report, workspace_parent=parent),
            "apply": lambda: capture_developer_task_execution_workspace_snapshot(manifest, preflight, workspace, {}, static_report, workspace_parent=parent),
            "static": lambda: capture_developer_task_execution_workspace_snapshot(manifest, preflight, workspace, apply_report, {}, workspace_parent=parent),
            "parent": lambda: capture_developer_task_execution_workspace_snapshot(manifest, preflight, workspace, apply_report, static_report, workspace_parent=str(parent)),
        }
        for name, callback in calls.items():
            try:
                callback()
                raw_results[name] = False
            except TypeError:
                raw_results[name] = True
        check(
            "V1C1A RAW PUBLIC INPUT TYPES ARE REJECTED",
            raw_results,
            {"manifest": True, "preflight": True, "workspace": True, "apply": True, "static": True, "parent": True},
        )
        failed_preflight = replace(preflight, issues=(_issue(),))
        check(
            "V1C1A FAILED PREFLIGHT CANNOT BECOME SNAPSHOT AUTHORITY",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, failed_preflight, workspace, apply_report, static_report, workspace_parent=parent
            )),
            "workspace_snapshot_preflight_failed",
        )
        failed_workspace = replace(workspace, clean_worktree=False, issues=(_issue(),))
        check(
            "V1C1A FAILED WORKSPACE REPORT IS REJECTED",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, preflight, failed_workspace, apply_report, static_report, workspace_parent=parent
            )),
            "workspace_snapshot_workspace_failed",
        )
        failed_apply = replace(apply_report, applied=False, issues=(_issue(),))
        check(
            "V1C1A FAILED PATCH APPLY REPORT IS REJECTED",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, preflight, workspace, failed_apply, static_report, workspace_parent=parent
            )),
            "workspace_snapshot_patch_apply_failed",
        )
        failed_static = replace(static_report, issues=(_issue(),))
        check(
            "V1C1A FAILED STATIC REPORT IS REJECTED",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, preflight, workspace, apply_report, failed_static, workspace_parent=parent
            )),
            "workspace_snapshot_static_check_failed",
        )
        forged_static = replace(static_report, base_commit="f" * 40)
        check(
            "V1C1A CROSS REPORT IDENTITY MISMATCH FAILS CLOSED",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, preflight, workspace, apply_report, forged_static, workspace_parent=parent
            )),
            "workspace_snapshot_chain_mismatch",
        )
        check(
            "V1C1A EXPLICIT WORKSPACE PARENT MISMATCH FAILS CLOSED",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, preflight, workspace, apply_report, static_report, workspace_parent=parent.parent
            )),
            "workspace_snapshot_parent_mismatch",
        )
        marker = Path(apply_report.apply_marker_path)
        marker.write_bytes(marker.read_bytes() + b" ")
        check(
            "V1C1A APPLY MARKER TAMPER FAILS CLOSED",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, preflight, workspace, apply_report, static_report, workspace_parent=parent
            )),
            "workspace_snapshot_filesystem_invalid",
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        fixture = _prepare(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="v1c1a-source-drift",
        )
        repo, _, parent, manifest, preflight, workspace, apply_report, static_report = fixture
        (repo / "untracked.txt").write_text("drift\n", encoding="utf-8")
        check(
            "V1C1A SOURCE REPOSITORY DRIFT FAILS CLOSED",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, preflight, workspace, apply_report, static_report, workspace_parent=parent
            )),
            "workspace_snapshot_source_repository_changed",
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        fixture = _prepare(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="v1c1a-workspace-drift",
        )
        _, _, parent, manifest, preflight, workspace, apply_report, static_report = fixture
        Path(workspace.repository_root, "module.py").write_text("value = 3\n", encoding="utf-8")
        check(
            "V1C1A WORKSPACE DRIFT FAILS CLOSED BEFORE CAPTURE",
            _error_code(lambda: capture_developer_task_execution_workspace_snapshot(
                manifest, preflight, workspace, apply_report, static_report, workspace_parent=parent
            )),
            "workspace_snapshot_workspace_probe_failed",
        )

    path_cases = {
        "/absolute.py": "workspace_snapshot_path_invalid",
        "C:/drive.py": "workspace_snapshot_path_invalid",
        "dir\\file.py": "workspace_snapshot_path_invalid",
        "dir/../file.py": "workspace_snapshot_path_invalid",
        "dir/bad?.py": "workspace_snapshot_windows_path_invalid",
        "dir/trailing. ": "workspace_snapshot_windows_path_invalid",
        "CON": "workspace_snapshot_windows_path_invalid",
        "dir/control\x01.py": "workspace_snapshot_path_invalid",
    }
    actual_path_codes: dict[str, str] = {}
    for value, expected_code in path_cases.items():
        actual_path_codes[value] = _error_code(lambda value=value: _validate_repository_path(value))
    check("V1C1A UNSAFE WINDOWS AND RELATIVE PATH FORMS FAIL CLOSED", actual_path_codes, path_cases)

    decomposed = "caf\u0065\u0301.py"
    check(
        "V1C1A NON NFC PATH FAILS CLOSED",
        {
            "normalized_differs": unicodedata.normalize("NFC", decomposed) != decomposed,
            "code": _error_code(lambda: _validate_repository_path(decomposed)),
        },
        {"normalized_differs": True, "code": "workspace_snapshot_path_not_normalized"},
    )

    def identity(path: str, *, mode: str = "100644", object_type: str = "blob", size: int = 1) -> _TreeIdentityEntry:
        return _TreeIdentityEntry(path=path, mode=mode, object_type=object_type, object_id="a" * 40, size_bytes=size)

    check(
        "V1C1A WINDOWS CASE COLLISION FAILS CLOSED",
        _error_code(lambda: _validate_tree_identity_entries((identity("Foo.py"), identity("foo.py")))),
        "workspace_snapshot_windows_case_collision",
    )
    check(
        "V1C1A DIRECTORY FILE COLLISION FAILS CLOSED",
        _error_code(lambda: _validate_tree_identity_entries((identity("folder"), identity("folder/file.py")))),
        "workspace_snapshot_directory_file_collision",
    )
    check(
        "V1C1A UNSUPPORTED FILE MODE FAILS CLOSED",
        _error_code(lambda: _validate_tree_identity_entries((identity("script.py", mode="100755"),))),
        "workspace_snapshot_mode_rejected",
    )
    check(
        "V1C1A GITLINK FAILS CLOSED",
        _error_code(lambda: _validate_tree_identity_entries((identity("vendor", mode="160000", object_type="commit", size=-1),))),
        "workspace_snapshot_gitlink_rejected",
    )
    check(
        "V1C1A NON BLOB TREE ENTRY FAILS CLOSED",
        _error_code(lambda: _validate_tree_identity_entries((identity("nested/file.py", mode="040000", object_type="tree", size=-1),))),
        "workspace_snapshot_non_blob_rejected",
    )
    check(
        "V1C1A SINGLE BLOB SIZE LIMIT FAILS CLOSED BEFORE BLOB READ",
        _error_code(lambda: _validate_tree_identity_entries((identity(
            "large.bin", size=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES + 1
        ),))),
        "workspace_snapshot_blob_too_large",
    )
    check(
        "V1C1A TOTAL TREE SIZE LIMIT FAILS CLOSED BEFORE BLOB READ",
        _error_code(lambda: _validate_tree_identity_entries((
            identity("a.bin", size=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES),
            identity("b.bin", size=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES),
            identity("c.bin", size=1),
        ))),
        "workspace_snapshot_total_bytes_exceeded",
    )
    many = tuple(identity(f"f{index:04d}.txt") for index in range(DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_FILE_COUNT + 1))
    check(
        "V1C1A FILE COUNT LIMIT FAILS CLOSED",
        _error_code(lambda: _validate_tree_identity_entries(many)),
        "workspace_snapshot_file_count_exceeded",
    )
    check(
        "V1C1A MALFORMED LS TREE OUTPUT FAILS CLOSED",
        _error_code(lambda: _parse_tree_identity(b"not-a-tree-record\x00")),
        "workspace_snapshot_tree_output_invalid",
    )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        fixture = _prepare(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="v1c1a-secret",
        )
        with patch.object(snapshot_module._SERVICES, "token_bytes", return_value=b"short"):
            check(
                "V1C1A INVALID SECRET GENERATOR FAILS CLOSED",
                _error_code(lambda: _capture(fixture)),
                "workspace_snapshot_secret_generation_failed",
            )

    source_text = Path(snapshot_module.__file__).read_text(encoding="utf-8")
    check(
        "V1C1A PRODUCTION SNAPSHOT HAS NO SANDBOX PYTHON INSTALL NETWORK OR SHELL SURFACE",
        {
            "WindowsSandbox.exe": "WindowsSandbox.exe" in source_text,
            "python.exe": "python.exe" in source_text,
            "pip install": "pip install" in source_text,
            "files.pythonhosted.org": "files.pythonhosted.org" in source_text,
            "pypi.org": "pypi.org" in source_text,
            "urllib.request": "urllib.request" in source_text,
            "requests.get": "requests.get" in source_text,
            "shell=True": "shell=True" in source_text,
            "CreateProcess": "CreateProcess" in source_text,
            "os.system(": "os.system(" in source_text,
        },
        {
            "WindowsSandbox.exe": False,
            "python.exe": False,
            "pip install": False,
            "files.pythonhosted.org": False,
            "pypi.org": False,
            "urllib.request": False,
            "requests.get": False,
            "shell=True": False,
            "CreateProcess": False,
            "os.system(": False,
        },
    )
    policy_text = Path(snapshot_module.__file__).with_name(
        "developer_task_execution_workspace_snapshot_policy.py"
    ).read_text(encoding="utf-8")
    check(
        "V1C1A POLICY LOCKS PROCESS LOCAL SINGLE USE NON AUTHORIZING CAPABILITY",
        {
            "process_local": "process_local=True" in policy_text,
            "single_use": "single_use=True" in policy_text,
            "runtime_lease_input_false": "runtime_lease_input=False" in policy_text,
            "network_false": "network_allowed=False" in policy_text,
            "execution_false": "execution_authorized=False" in policy_text,
            "ttl_300": "SNAPSHOT_TTL_SECONDS = 300" in policy_text,
            "secret_32": "SNAPSHOT_SECRET_BYTES = 32" in policy_text,
        },
        {
            "process_local": True,
            "single_use": True,
            "runtime_lease_input_false": True,
            "network_false": True,
            "execution_false": True,
            "ttl_300": True,
            "secret_32": True,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
