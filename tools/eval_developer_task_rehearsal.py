from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.developer.developer_task_proposal_contract import (
    DeveloperTaskProposalContextInput,
)
from modules.developer.developer_task_proposal_intake import (
    intake_developer_task_proposal,
    prepare_developer_task_proposal_request,
)
from modules.developer.developer_task_rehearsal import (
    run_developer_task_static_rehearsal,
)
from modules.developer.developer_task_rehearsal_contract import (
    DTRB_FAILED_CLEAN_STATUS,
    DTRB_REJECTED_CLEAN_STATUS,
    DTRB_STOP_REVIEW_STATUS,
    DTRB_SUCCESS_STATUS,
    canonical_rehearsal_json_bytes,
)
from modules.developer.developer_task_rehearsal_fs import (
    DeveloperTaskRehearsalFileSystemError,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class EvalFailure(RuntimeError):
    pass


def _eval_temp_parent() -> Path | None:
    # Keep Windows fixture paths short enough for the identity-rich independent
    # workspace path used by Developer Workspace V1.
    if os.name == "nt":
        return Path.home()
    return None


def _hermetic_git_environment(control_root: Path) -> dict[str, str]:
    env = os.environ.copy()

    for key in tuple(env):
        upper = key.upper()
        if (
            upper in {
                "GIT_DIR",
                "GIT_WORK_TREE",
                "GIT_INDEX_FILE",
                "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                "GIT_COMMON_DIR",
                "GIT_CEILING_DIRECTORIES",
                "GIT_PREFIX",
                "GIT_NAMESPACE",
                "GIT_SHALLOW_FILE",
                "GIT_REPLACE_REF_BASE",
                "GIT_QUARANTINE_PATH",
                "GIT_GRAFT_FILE",
                "GIT_CONFIG",
                "GIT_CONFIG_GLOBAL",
                "GIT_CONFIG_SYSTEM",
                "GIT_CONFIG_COUNT",
            }
            or upper.startswith("GIT_CONFIG_KEY_")
            or upper.startswith("GIT_CONFIG_VALUE_")
        ):
            env.pop(key, None)

    empty_global = control_root / ".empty-gitconfig"
    empty_global.write_bytes(b"")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = str(empty_global)
    env["GIT_ATTR_NOSYSTEM"] = "1"

    if os.name == "nt":
        home = str(Path.home())
        env["TEMP"] = home
        env["TMP"] = home
        env["TMPDIR"] = home

    command_config = (
        ("core.autocrlf", "false"),
        ("core.eol", "lf"),
        ("core.safecrlf", "false"),
        ("core.fsmonitor", "false"),
        ("core.longpaths", "true"),
        ("commit.gpgsign", "false"),
        ("tag.gpgsign", "false"),
        ("push.gpgsign", "false"),
    )
    env["GIT_CONFIG_COUNT"] = str(len(command_config))
    for index, (key, value) in enumerate(command_config):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value

    return env


def _git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    cp = subprocess.run(
        ["git", "-C", str(root), *args],
        input=input_bytes,
        stdin=None if input_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if cp.returncode:
        raise EvalFailure((cp.stderr or cp.stdout).decode("utf-8", "replace"))
    return cp.stdout


def _blob_oid(payload: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(f"blob {len(payload)}\0".encode("ascii"))
    digest.update(payload)
    return digest.hexdigest()


def _init_repo(root: Path) -> tuple[str, str]:
    root.mkdir()
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "dtrb-eval@example.com")
    _git(root, "config", "user.name", "DTR-B Eval")

    demo = root / "modules" / "demo.py"
    other = root / "modules" / "other.py"
    demo.parent.mkdir()
    demo.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    other.write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "--", "modules/demo.py", "modules/other.py")
    _git(root, "commit", "--quiet", "-m", "base")
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    return head, tree


def _patch_for_change(repo: Path, relative: str, content: str) -> bytes:
    path = repo / relative
    path.write_text(content, encoding="utf-8")
    payload = _git(
        repo,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
        "HEAD",
        "--",
        relative,
    )
    _git(repo, "checkout", "--", relative)
    return payload


def _plan(
    repo: Path,
    *,
    base_commit: str,
    base_tree: str,
    patch_bytes: bytes,
    request_id: str,
):
    original = (repo / "modules" / "demo.py").read_bytes()
    request = prepare_developer_task_proposal_request(
        task_id="dtrb-eval",
        title="DTR-B static rehearsal eval",
        request_id=request_id,
        instruction="Change only modules/demo.py as requested.",
        base_commit=base_commit,
        base_tree=base_tree,
        target_path="modules/demo.py",
        context_entries=(
            DeveloperTaskProposalContextInput(
                path="modules/demo.py",
                mode="100644",
                git_blob_oid=_blob_oid(original),
                content=original,
            ),
        ),
    )
    raw = json.dumps(
        {
            "kind": "DTR_PATCH_PROPOSAL_V1",
            "schema_version": 1,
            "request_id": request.request_id,
            "request_fingerprint": request.request_fingerprint,
            "patch_text": patch_bytes.decode("utf-8"),
            "explanation": "DTR-B evaluator proposal.",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    intake = intake_developer_task_proposal(request, raw)
    if not intake.ok or intake.plan is None:
        raise EvalFailure(f"DTR-A intake failed: {intake.to_dict()}")
    return intake.plan


def _read_result(report) -> dict[str, Any]:
    if report.artifact is None:
        raise EvalFailure("report has no artifact layout")
    raw = Path(report.artifact.result_path).read_bytes()
    return json.loads(raw.decode("utf-8"))


def _source_status(repo: Path) -> str:
    return _git(repo, "status", "--porcelain=v1").decode("utf-8")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports




def _return_in_finally(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for item in node.finalbody:
            if any(isinstance(child, ast.Return) for child in ast.walk(item)):
                return True
    return False

def _run_cases(
    root: Path,
    repo: Path,
    artifacts: Path,
    check,
) -> None:
    base_commit, base_tree = _init_repo(repo)

    valid_patch = _patch_for_change(
        repo,
        "modules/demo.py",
        'def add(a, b):\n    """Add two values."""\n    return a + b\n',
    )
    valid_plan = _plan(
        repo,
        base_commit=base_commit,
        base_tree=base_tree,
        patch_bytes=valid_patch,
        request_id="eval-valid-001",
    )

    success = run_developer_task_static_rehearsal(
        valid_plan,
        project_root=repo,
        artifact_parent=artifacts,
    )
    success_json = _read_result(success)

    check("SUCCESS STATUS", success.status, DTRB_SUCCESS_STATUS)
    check("SUCCESS OK", success.ok, True)
    check("SUCCESS SOURCE UNCHANGED", success.source_repository_unchanged, True)
    check("SUCCESS WORKSPACE REMOVED", success.workspace_removed, True)
    check("SUCCESS PATCH MATERIALIZED", success.patch_materialized, True)
    check("SUCCESS PATCH APPLIED IN ISOLATED WORKSPACE", success.patch_applied_in_isolated_workspace, True)
    check("SUCCESS RESULT RECORDED", success.result_recorded, True)
    check("SUCCESS COMPLETED CHECKS", success.completed_checks, ("git_diff_check", "py_compile"))
    check(
        "SUCCESS PENDING EXECUTABLE CHECKS",
        tuple(item.to_dict() for item in success.pending_executable_checks),
        ({"type": "pipeline", "flow": "check"},),
    )
    check("SUCCESS ALL REQUIRED CHECKS FALSE", success.all_required_checks_passed, False)
    check("SUCCESS BEHAVIOR NOT EVALUATED", success.behavioral_correctness, "NOT_EVALUATED")
    check("SUCCESS READY TO PROMOTE FALSE", success.ready_to_promote, False)
    check("SUCCESS AUTHORITIES FALSE", (success.authority_granted, success.runtime_authorized, success.promotion_authorized), (False, False, False))
    check("SUCCESS EXECUTION SURFACES FALSE", (success.model_provider_called, success.network, success.sandbox, success.native_worker_launched, success.changed_code_executed), (False, False, False, False, False))
    check("SUCCESS SOURCE REPO CLEAN", _source_status(repo), "")
    check("SUCCESS WORKSPACES EMPTY", list(Path(success.artifact.workspace_parent).iterdir()), [])
    check("SUCCESS PATCH BYTES EXACT", Path(success.artifact.patch_path).read_bytes(), valid_plan.proposal.patch_bytes)
    check("SUCCESS RESULT JSON STATUS", success_json["status"], DTRB_SUCCESS_STATUS)
    check("SUCCESS RESULT JSON NO CLEANUP TOKEN", "cleanup_token" in json.dumps(success_json), False)
    check("SUCCESS RESULT JSON NO CHECK TOKEN", "check_token" in json.dumps(success_json), False)
    persisted = Path(success.artifact.result_path).read_bytes()
    check("SUCCESS RESULT JSON CANONICAL", persisted, canonical_rehearsal_json_bytes(success.to_dict()))

    second = run_developer_task_static_rehearsal(
        valid_plan,
        project_root=repo,
        artifact_parent=artifacts,
    )
    check("DISTINCT RUN IDS", second.run_id != success.run_id, True)
    check("DISTINCT ARTIFACT ROOTS", second.artifact.artifact_root != success.artifact.artifact_root, True)
    check("SECOND SUCCESS", second.status, DTRB_SUCCESS_STATUS)

    syntax_patch = _patch_for_change(
        repo,
        "modules/demo.py",
        "def add(a, b):\n    return (a + b\n",
    )
    syntax_plan = _plan(
        repo,
        base_commit=base_commit,
        base_tree=base_tree,
        patch_bytes=syntax_patch,
        request_id="eval-syntax-001",
    )
    syntax = run_developer_task_static_rehearsal(
        syntax_plan,
        project_root=repo,
        artifact_parent=artifacts,
    )
    check("SYNTAX FAILURE STATUS", syntax.status, DTRB_FAILED_CLEAN_STATUS)
    check("SYNTAX FAILURE NOT OK", syntax.ok, False)
    check("SYNTAX FAILURE SOURCE UNCHANGED", syntax.source_repository_unchanged, True)
    check("SYNTAX FAILURE WORKSPACE REMOVED", syntax.workspace_removed, True)
    check("SYNTAX FAILURE COMPLETED CHECKS", syntax.completed_checks, ("git_diff_check",))
    check(
        "SYNTAX FAILURE PIPELINE STILL PENDING",
        tuple(item.to_dict() for item in syntax.pending_executable_checks),
        ({"type": "pipeline", "flow": "check"},),
    )
    static_payloads = [item.payload_dict() for item in syntax.stage_evidence if item.stage == "STATIC_CHECKS"]
    check("SYNTAX FAILURE CODE", static_payloads[0]["issue_codes"], ["static_python_syntax_error"])
    check("SYNTAX FAILURE SOURCE REPO CLEAN", _source_status(repo), "")
    check("SYNTAX FAILURE RESULT RECORDED", syntax.result_recorded, True)

    scope_patch = _patch_for_change(repo, "modules/other.py", "VALUE = 2\n")
    scope_plan = _plan(
        repo,
        base_commit=base_commit,
        base_tree=base_tree,
        patch_bytes=scope_patch,
        request_id="eval-scope-001",
    )
    scope = run_developer_task_static_rehearsal(
        scope_plan,
        project_root=repo,
        artifact_parent=artifacts,
    )
    check("SCOPE REJECTION STATUS", scope.status, DTRB_REJECTED_CLEAN_STATUS)
    check("SCOPE REJECTION WORKSPACE REMOVED FALSE", scope.workspace_removed, False)
    check("SCOPE REJECTION SOURCE UNCHANGED", scope.source_repository_unchanged, True)
    check("SCOPE REJECTION SOURCE CLEAN", _source_status(repo), "")
    check("SCOPE REJECTION WORKSPACES EMPTY", list(Path(scope.artifact.workspace_parent).iterdir()), [])

    forged_authority = replace(valid_plan, authority_granted=True)
    forged = run_developer_task_static_rehearsal(
        forged_authority,
        project_root=repo,
        artifact_parent=artifacts,
    )
    check("FORGED AUTHORITY REJECTED", forged.status, DTRB_REJECTED_CLEAN_STATUS)
    check("FORGED AUTHORITY HAS NO ARTIFACT", forged.artifact, None)
    check("FORGED AUTHORITY ISSUE", forged.issue_codes, ("plan_authority_invalid",))

    forged_manifest = replace(
        valid_plan,
        manifest=replace(valid_plan.manifest, allowed_files=("modules/other.py",)),
    )
    forged2 = run_developer_task_static_rehearsal(
        forged_manifest,
        project_root=repo,
        artifact_parent=artifacts,
    )
    check("FORGED MANIFEST REJECTED", forged2.status, DTRB_REJECTED_CLEAN_STATUS)
    check("FORGED MANIFEST ISSUE", forged2.issue_codes, ("plan_canonical_mismatch",))

    overlap = run_developer_task_static_rehearsal(
        valid_plan,
        project_root=repo,
        artifact_parent=repo,
    )
    check("ARTIFACT OVERLAP REJECTED", overlap.status, DTRB_REJECTED_CLEAN_STATUS)
    check("ARTIFACT OVERLAP SOURCE UNCHANGED", overlap.source_repository_unchanged, True)
    check("ARTIFACT OVERLAP SOURCE CLEAN", _source_status(repo), "")

    nested_git = root / "nested-git"
    nested_git.mkdir()
    _git(nested_git, "init", "--quiet")
    nested_artifacts = nested_git / "artifacts"
    nested_artifacts.mkdir()
    inside_git = run_developer_task_static_rehearsal(
        valid_plan,
        project_root=repo,
        artifact_parent=nested_artifacts,
    )
    check("ARTIFACT INSIDE GIT REJECTED", inside_git.status, DTRB_REJECTED_CLEAN_STATUS)
    check("ARTIFACT INSIDE GIT ISSUE", inside_git.issue_codes, ("artifact_parent_inside_git_repository",))

    marker = root / "executed.marker"
    execution_patch = _patch_for_change(
        repo,
        "modules/demo.py",
        f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n\ndef add(a, b):\n    return a + b\n',
    )
    execution_plan = _plan(
        repo,
        base_commit=base_commit,
        base_tree=base_tree,
        patch_bytes=execution_patch,
        request_id="eval-noexec-001",
    )
    noexec = run_developer_task_static_rehearsal(
        execution_plan,
        project_root=repo,
        artifact_parent=artifacts,
    )
    check("CHANGED CODE NOT EXECUTED", marker.exists(), False)
    check("NOEXEC REHEARSAL STATIC SUCCESS", noexec.status, DTRB_SUCCESS_STATUS)

    cleanup_calls = {"count": 0}
    def _cleanup_boom(*args, **kwargs):
        cleanup_calls["count"] += 1
        raise RuntimeError("forced cleanup failure")

    with patch(
        "modules.developer.developer_task_rehearsal.cleanup_developer_task_workspace",
        side_effect=_cleanup_boom,
    ):
        cleanup_fail = run_developer_task_static_rehearsal(
            valid_plan,
            project_root=repo,
            artifact_parent=artifacts,
        )
    check("CLEANUP FAILURE STOP REVIEW", cleanup_fail.status, DTRB_STOP_REVIEW_STATUS)
    check("CLEANUP FAILURE ONCE", cleanup_calls["count"], 1)
    check("CLEANUP FAILURE SOURCE UNCHANGED", cleanup_fail.source_repository_unchanged, True)
    check("CLEANUP FAILURE WORKSPACE REMOVED FALSE", cleanup_fail.workspace_removed, False)
    check("CLEANUP FAILURE RESULT RECORDED", cleanup_fail.result_recorded, True)
    if cleanup_fail.artifact is not None:
        # Eval-only cleanup of forced-failure residue; production DTR-B intentionally preserves it for review.
        shutil.rmtree(cleanup_fail.artifact.artifact_root, ignore_errors=True)

    def _result_boom(*args, **kwargs):
        raise DeveloperTaskRehearsalFileSystemError(
            "forced_result_failure",
            "forced result failure",
        )

    with patch(
        "modules.developer.developer_task_rehearsal.write_rehearsal_result",
        side_effect=_result_boom,
    ):
        result_fail = run_developer_task_static_rehearsal(
            valid_plan,
            project_root=repo,
            artifact_parent=artifacts,
        )
    check("RESULT WRITE FAILURE STOP REVIEW", result_fail.status, DTRB_STOP_REVIEW_STATUS)
    check("RESULT WRITE FAILURE NOT RECORDED", result_fail.result_recorded, False)
    check("RESULT WRITE FAILURE WORKSPACE REMOVED", result_fail.workspace_removed, True)
    check("RESULT WRITE FAILURE SOURCE UNCHANGED", result_fail.source_repository_unchanged, True)

    imports = _imports(PROJECT_ROOT / "modules" / "developer" / "developer_task_rehearsal.py")
    fs_imports = _imports(PROJECT_ROOT / "modules" / "developer" / "developer_task_rehearsal_fs.py")
    check("ORCHESTRATOR NO SUBPROCESS IMPORT", "subprocess" in imports, False)
    check("ORCHESTRATOR NO SOCKET IMPORT", "socket" in imports, False)
    check("FS NO SUBPROCESS IMPORT", "subprocess" in fs_imports, False)
    check("FS NO SOCKET IMPORT", "socket" in fs_imports, False)
    fs_text = (PROJECT_ROOT / "modules" / "developer" / "developer_task_rehearsal_fs.py").read_text(encoding="utf-8")
    check("FS REUSES REPARSE PATH VALIDATION", "validate_workspace_parent" in fs_text, True)
    check("FS RECHECKS REPARSE DIRECTORY METADATA", "is_reparse_or_symlink" in fs_text, True)
    check(
        "ORCHESTRATOR HAS NO RETURN IN FINALLY",
        _return_in_finally(PROJECT_ROOT / "modules" / "developer" / "developer_task_rehearsal.py"),
        False,
    )
    check(
        "ORCHESTRATOR NO EXECUTION BACKEND IMPORT",
        any(name.startswith("modules.developer.developer_task_execution_") for name in imports),
        False,
    )
    check("FINAL SOURCE REPO CLEAN", _source_status(repo), "")
    check("FINAL SOURCE HEAD", _git(repo, "rev-parse", "HEAD").decode().strip(), base_commit)



def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    with tempfile.TemporaryDirectory(prefix=".dtrb-", dir=_eval_temp_parent()) as td:
        root = Path(td)
        repo = root / "source"
        artifacts = root / "artifacts"
        artifacts.mkdir()

        hermetic_env = _hermetic_git_environment(root)
        with patch.dict(os.environ, hermetic_env, clear=True):
            _run_cases(root, repo, artifacts, check)

    summary = {
        "kind": "DTRB_STATIC_REHEARSAL_EVAL_V1",
        "result": "PASS" if fail_count == 0 else "FAIL",
        "case_count": case_count,
        "fail_count": fail_count,
        "dtrb_acceptance_requirements_covered": [f"T{index:02d}" for index in range(1, 33)],
        "model_provider_called": False,
        "network": False,
        "sandbox": False,
        "native_worker_launched": False,
        "changed_code_executed": False,
        "promotion_authorized": False,
        "runtime_authorized": False,
    }
    print()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
