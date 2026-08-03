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

import modules.developer.developer_task_patch_apply as patch_apply_module
import modules.developer.developer_task_patch_apply_git as patch_apply_git_module

from modules.developer.developer_task_patch_apply import (
    PATCH_APPLY_MARKER_NAME,
    DeveloperTaskPatchApplyReport,
    apply_developer_task_patch,
)
from modules.developer.developer_task_patch_apply_git import (
    DeveloperTaskPatchApplyRollbackResult,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_preflight_composition import run_developer_task_preflight
from modules.developer.developer_task_workspace import create_developer_task_workspace
from modules.developer.developer_task_workspace_cleanup import (
    cleanup_developer_task_workspace,
)
from tools.eval_developer_task_workspace import (
    _git,
    _git_bytes,
    _init_repo,
    _manifest,
    _sha256,
)
from tools.eval_developer_task_workspace_cleanup import (
    _prepare_workspace,
    _remove_fixture_tree,
)


def _issue(code: str = "forced_failure") -> DeveloperTaskPreflightIssue:
    return DeveloperTaskPreflightIssue(
        code=code,
        check="eval",
        message="Forced eval failure.",
    )


def _apply(
    manifest: Any,
    preflight: Any,
    workspace: Any,
    parent: Path,
) -> DeveloperTaskPatchApplyReport:
    return apply_developer_task_patch(
        manifest,
        preflight_report=preflight,
        workspace_report=workspace,
        workspace_parent=parent,
    )


def _cleanup_workspace(
    manifest: Any,
    preflight: Any,
    workspace: Any,
    parent: Path,
) -> None:
    root = Path(workspace.workspace_root) if workspace.workspace_root else None

    try:
        report = cleanup_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_report=workspace,
            workspace_parent=parent,
        )

        if report.ok:
            return
    except Exception:
        pass

    if root is not None:
        _remove_fixture_tree(root)


def _staged_status(repository_root: Path) -> bytes:
    return _git_bytes(
        repository_root,
        "status",
        "--porcelain=v2",
        "-z",
        "--no-branch",
        "--untracked-files=all",
        "--ignore-submodules=none",
    ).stdout


def _workspace_is_clean_base(repository_root: Path, base_commit: str) -> bool:
    status = _staged_status(repository_root)
    head = _git(repository_root, "rev-parse", "HEAD^{commit}").stdout.strip()
    return status == b"" and head == base_commit


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

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        repo, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        source_index = Path(_git(repo, "rev-parse", "--git-path", "index").stdout.strip())
        if not source_index.is_absolute():
            source_index = repo / source_index
        source_index_before = _sha256(source_index)
        source_tracked_before = (repo / "tracked.txt").read_bytes()
        source_status_before = _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
        report = _apply(manifest, preflight, workspace, parent)
        apply_marker = Path(report.apply_marker_path)
        marker_payload = json.loads(apply_marker.read_text(encoding="utf-8")) if apply_marker.is_file() else {}
        staged_status = _staged_status(repository_root)
        check(
            "VERIFIED PATCH IS APPLIED WITH IMMUTABLE EVIDENCE",
            {
                "ok": report.ok,
                "state": report.state,
                "issue_codes": list(report.issue_codes),
                "changed_files": list(report.changed_files),
                "head_matches": report.head_commit == workspace.base_commit,
                "patch_matches": report.patch_sha256 == manifest.patch_sha256,
                "marker_exists": apply_marker.is_file(),
                "marker_hash_matches": (
                    apply_marker.is_file()
                    and hashlib.sha256(apply_marker.read_bytes()).hexdigest()
                    == report.apply_marker_sha256
                ),
                "result_tree_present": bool(report.result_tree),
                "staged_diff_hash_present": len(report.staged_diff_sha256) == 64,
                "workspace_config_hash_present": len(report.workspace_config_sha256) == 64,
                "staged_status_present": bool(staged_status),
                "worktree_matches_index": _git(repository_root, "diff", "--quiet").returncode == 0,
                "source_index_unchanged": _sha256(source_index) == source_index_before,
                "source_file_unchanged": (repo / "tracked.txt").read_bytes() == source_tracked_before,
                "source_status_unchanged": (
                    _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
                    == source_status_before
                ),
            },
            {
                "ok": True,
                "state": "applied",
                "issue_codes": [],
                "changed_files": ["tracked.txt"],
                "head_matches": True,
                "patch_matches": True,
                "marker_exists": True,
                "marker_hash_matches": True,
                "result_tree_present": True,
                "staged_diff_hash_present": True,
                "workspace_config_hash_present": True,
                "staged_status_present": True,
                "worktree_matches_index": True,
                "source_index_unchanged": True,
                "source_file_unchanged": True,
                "source_status_unchanged": True,
            },
        )

        check(
            "APPLY MARKER BINDS CHECK CAPABILITY AND RESULT TREE",
            {
                "schema": marker_payload.get("schema_version"),
                "workspace_id": marker_payload.get("workspace_id") == workspace.workspace_id,
                "patch_sha256": marker_payload.get("patch_sha256") == manifest.patch_sha256,
                "changed_files": marker_payload.get("changed_files"),
                "result_tree": marker_payload.get("result_tree") == report.result_tree,
                "diff_hash": marker_payload.get("staged_diff_sha256") == report.staged_diff_sha256,
                "config_hash": marker_payload.get("workspace_config_sha256")
                == report.workspace_config_sha256,
                "token_hash": marker_payload.get("check_token_sha256")
                == hashlib.sha256(report.check_token).hexdigest(),
            },
            {
                "schema": 1,
                "workspace_id": True,
                "patch_sha256": True,
                "changed_files": ["tracked.txt"],
                "result_tree": True,
                "diff_hash": True,
                "config_hash": True,
                "token_hash": True,
            },
        )

        serialized = report.to_dict()
        check(
            "CHECK CAPABILITY IS NOT SERIALIZED OR REPR EXPOSED",
            {
                "to_dict": report.check_token.hex() not in json.dumps(serialized),
                "repr": report.check_token.hex() not in repr(report),
                "present": serialized["check_capability_present"],
            },
            {"to_dict": True, "repr": True, "present": True},
        )

        immutable = False
        try:
            report.applied = False  # type: ignore[misc]
        except FrozenInstanceError:
            immutable = True
        check("PATCH APPLY REPORT IS IMMUTABLE", immutable, True)

        cleanup = cleanup_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_report=workspace,
            workspace_parent=parent,
        )
        check(
            "APPLIED WORKSPACE REMAINS COMPATIBLE WITH VERIFIED CLEANUP",
            {
                "cleanup_ok": cleanup.ok,
                "state": cleanup.state,
                "workspace_absent": not Path(workspace.workspace_root).exists(),
            },
            {"cleanup_ok": True, "state": "removed", "workspace_absent": True},
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        repo = root / "source"
        task_root = root / "task"
        parent = root / "workspaces"
        base_commit = _init_repo(repo)
        (repo / "tracked.txt").unlink()
        patch_bytes = _git_bytes(
            repo,
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "--no-renames",
            "HEAD",
            "--",
            "tracked.txt",
        ).stdout
        _git(repo, "reset", "--hard", "HEAD")
        task_root.mkdir()
        parent.mkdir()
        manifest = _manifest(
            base_commit,
            patch_bytes,
            task_id="developer-patch-apply-delete-last-file",
        )
        (task_root / manifest.patch_file).write_bytes(patch_bytes)
        preflight = run_developer_task_preflight(
            manifest,
            project_root=repo,
            task_root=task_root,
        )
        workspace = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        report = _apply(manifest, preflight, workspace, parent)
        repository_root = Path(workspace.repository_root)
        check(
            "PATCH MAY DELETE THE FINAL TRACKED FILE WITH AN EMPTY RESULT INDEX",
            {
                "preflight_ok": preflight.ok,
                "workspace_ok": workspace.ok,
                "apply_ok": report.ok,
                "changed_files": list(report.changed_files),
                "result_index_paths": list(report.result_index_paths),
                "tracked_absent": not (repository_root / "tracked.txt").exists(),
            },
            {
                "preflight_ok": True,
                "workspace_ok": True,
                "apply_ok": True,
                "changed_files": ["tracked.txt"],
                "result_index_paths": [],
                "tracked_absent": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        type_checks: dict[str, bool] = {}
        for name, args in {
            "manifest": ({"raw": True}, preflight, workspace, parent),
            "preflight": (manifest, {"raw": True}, workspace, parent),
            "workspace": (manifest, preflight, {"raw": True}, parent),
            "parent": (manifest, preflight, workspace, str(parent)),
        }.items():
            try:
                _apply(*args)  # type: ignore[arg-type]
            except TypeError:
                type_checks[name] = True
            else:
                type_checks[name] = False
        check(
            "RAW APPLY INPUTS ARE REJECTED",
            type_checks,
            {"manifest": True, "preflight": True, "workspace": True, "parent": True},
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        failed_preflight = replace(preflight, failed_stage="repository", issues=(_issue(),))
        report = _apply(manifest, failed_preflight, workspace, parent)
        check(
            "FAILED PREFLIGHT BLOCKS PATCH APPLY",
            {"issue_codes": list(report.issue_codes), "workspace_present": Path(workspace.workspace_root).exists()},
            {"issue_codes": ["preflight_report_failed"], "workspace_present": True},
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        failed_workspace = replace(workspace, issues=(_issue(),))
        report = _apply(manifest, preflight, failed_workspace, parent)
        check(
            "FAILED WORKSPACE REPORT BLOCKS PATCH APPLY",
            list(report.issue_codes),
            ["workspace_report_failed"],
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        other_parent = parent.parent / "other"
        other_parent.mkdir()
        report = _apply(manifest, preflight, workspace, other_parent)
        check(
            "EXPLICIT WORKSPACE PARENT MISMATCH IS REJECTED",
            list(report.issue_codes),
            ["workspace_parent_mismatch"],
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        forged = replace(workspace, repository_root=workspace.source_repository_root)
        report = _apply(manifest, preflight, forged, parent)
        check(
            "FORGED WORKSPACE PATH CANNOT RECEIVE PATCH",
            list(report.issue_codes),
            ["workspace_report_paths_invalid"],
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        Path(workspace.marker_path).unlink()
        report = _apply(manifest, preflight, workspace, parent)
        check("MISSING WORKSPACE MARKER BLOCKS APPLY", list(report.issue_codes), ["workspace_marker_missing"])
        _remove_fixture_tree(Path(workspace.workspace_root))

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        Path(workspace.marker_path).write_text("{}", encoding="utf-8")
        report = _apply(manifest, preflight, workspace, parent)
        check(
            "WORKSPACE MARKER HASH MISMATCH BLOCKS APPLY",
            list(report.issue_codes),
            ["workspace_marker_hash_mismatch"],
        )
        _remove_fixture_tree(Path(workspace.workspace_root))

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        (repository_root / "tracked.txt").write_text("dirty\n", encoding="utf-8")
        report = _apply(manifest, preflight, workspace, parent)
        check(
            "DIRTY WORKSPACE IS REJECTED BEFORE MUTATION",
            {
                "issue_codes": list(report.issue_codes),
                "rollback_attempted": report.rollback_attempted,
                "dirty_preserved": (repository_root / "tracked.txt").read_text(encoding="utf-8") == "dirty\n",
            },
            {
                "issue_codes": ["workspace_not_clean"],
                "rollback_attempted": False,
                "dirty_preserved": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        redirected = Path(temp_dir) / "redirected-worktree"
        redirected.mkdir()
        _git(repository_root, "config", "--local", "core.worktree", str(redirected))
        report = _apply(manifest, preflight, workspace, parent)
        check(
            "WORKSPACE CORE WORKTREE REDIRECTION IS REJECTED BEFORE MUTATION",
            {
                "issue_codes": list(report.issue_codes),
                "rollback_attempted": report.rollback_attempted,
                "redirected_untouched": not any(redirected.iterdir()),
            },
            {
                "issue_codes": ["workspace_configuration_invalid"],
                "rollback_attempted": False,
                "redirected_untouched": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        tracked_before = (repository_root / "tracked.txt").read_bytes()
        _git(repository_root, "config", "--local", "filter.unsafe.smudge", "echo unsafe")
        report = _apply(manifest, preflight, workspace, parent)
        check(
            "WORKSPACE FILTER EXECUTION CONFIG IS REJECTED BEFORE MUTATION",
            {
                "issue_codes": list(report.issue_codes),
                "rollback_attempted": report.rollback_attempted,
                "tracked_unchanged": (repository_root / "tracked.txt").read_bytes()
                == tracked_before,
            },
            {
                "issue_codes": ["workspace_configuration_invalid"],
                "rollback_attempted": False,
                "tracked_unchanged": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        _git(repository_root, "switch", "-c", "unexpected")
        report = _apply(manifest, preflight, workspace, parent)
        check("ATTACHED HEAD IS REJECTED", list(report.issue_codes), ["workspace_head_not_detached"])
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        apply_marker = Path(workspace.control_root) / PATCH_APPLY_MARKER_NAME
        apply_marker.write_text("existing", encoding="utf-8")
        report = _apply(manifest, preflight, workspace, parent)
        check("EXISTING APPLY MARKER BLOCKS REAPPLICATION", list(report.issue_codes), ["patch_already_applied"])
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        original_parse = patch_apply_git_module.parse_developer_task_patch_changes
        with patch.object(
            patch_apply_git_module,
            "parse_developer_task_patch_changes",
            return_value=(),
        ):
            report = _apply(manifest, preflight, workspace, parent)
        check(
            "POST APPLY FACT MISMATCH ROLLS BACK TO CLEAN BASE",
            {
                "issue_codes": list(report.issue_codes),
                "state": report.state,
                "rollback_succeeded": report.rollback_succeeded,
                "clean_base": _workspace_is_clean_base(repository_root, workspace.base_commit),
                "parser_was_callable": callable(original_parse),
            },
            {
                "issue_codes": ["workspace_patch_facts_mismatch"],
                "state": "rejected_clean",
                "rollback_succeeded": True,
                "clean_base": True,
                "parser_was_callable": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        original_open = patch_apply_module.os.open

        def failing_marker_open(path: Any, flags: int, mode: int = 0o777) -> int:
            if Path(path).name == PATCH_APPLY_MARKER_NAME:
                raise PermissionError("forced marker failure")
            return original_open(path, flags, mode)

        with patch.object(patch_apply_module.os, "open", side_effect=failing_marker_open):
            report = _apply(manifest, preflight, workspace, parent)
        check(
            "APPLY MARKER FAILURE ROLLS BACK CLEANLY",
            {
                "issue_codes": list(report.issue_codes),
                "state": report.state,
                "clean_base": _workspace_is_clean_base(repository_root, workspace.base_commit),
                "marker_absent": not (Path(workspace.control_root) / PATCH_APPLY_MARKER_NAME).exists(),
            },
            {
                "issue_codes": ["patch_apply_marker_write_failed"],
                "state": "rejected_clean",
                "clean_base": True,
                "marker_absent": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        original_read_marker = patch_apply_module.read_workspace_marker

        def fail_apply_marker_read(path: Path, expected_sha256: str) -> Any:
            if Path(path).name == PATCH_APPLY_MARKER_NAME:
                raise patch_apply_module.DeveloperTaskWorkspaceCleanupFileSystemError(
                    "workspace_marker_hash_mismatch",
                    "forced apply marker verification failure",
                )
            return original_read_marker(path, expected_sha256)

        with patch.object(
            patch_apply_module,
            "read_workspace_marker",
            side_effect=fail_apply_marker_read,
        ):
            report = _apply(manifest, preflight, workspace, parent)
        check(
            "APPLY MARKER VERIFICATION FAILURE ROLLS BACK CLEANLY",
            {
                "issue_codes": list(report.issue_codes),
                "state": report.state,
                "clean_base": _workspace_is_clean_base(repository_root, workspace.base_commit),
                "marker_absent": not (Path(workspace.control_root) / PATCH_APPLY_MARKER_NAME).exists(),
            },
            {
                "issue_codes": ["patch_apply_marker_invalid"],
                "state": "rejected_clean",
                "clean_base": True,
                "marker_absent": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        source_home = root / "source-home"
        source_xdg = root / "source-xdg"
        source_home.mkdir()
        source_xdg.mkdir()
        (source_home / ".gitconfig").write_text(
            "[core]\n\tautocrlf = true\n",
            encoding="utf-8",
        )
        source_environment = {
            "HOME": str(source_home),
            "USERPROFILE": str(source_home),
            "XDG_CONFIG_HOME": str(source_xdg),
            "GIT_CONFIG_NOSYSTEM": "1",
        }

        with patch.dict(os.environ, source_environment, clear=False):
            repo, _, parent, manifest, preflight, workspace = _prepare_workspace(root / "case")
            repository_root = Path(workspace.repository_root)
            original_apply = patch_apply_module.apply_patch_to_independent_workspace

            def apply_then_mutate_source(request: Any) -> Any:
                evidence = original_apply(request)
                (repo / "tracked.txt").write_text(
                    "external source mutation\n",
                    encoding="utf-8",
                )
                return evidence

            with patch.object(
                patch_apply_module,
                "apply_patch_to_independent_workspace",
                side_effect=apply_then_mutate_source,
            ):
                report = _apply(manifest, preflight, workspace, parent)
            check(
                "SOURCE MUTATION DURING APPLY FAILS CLOSED AND ROLLS BACK WORKSPACE",
                {
                    "issue_codes": list(report.issue_codes),
                    "state": report.state,
                    "source_unchanged": report.source_repository_unchanged,
                    "clean_base": _workspace_is_clean_base(repository_root, workspace.base_commit),
                },
                {
                    "issue_codes": ["source_repository_changed"],
                    "state": "rejected_clean",
                    "source_unchanged": False,
                    "clean_base": True,
                },
            )
            _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        with patch.object(
            patch_apply_module,
            "apply_patch_to_independent_workspace",
            side_effect=RuntimeError("forced unexpected error"),
        ):
            report = _apply(manifest, preflight, workspace, parent)
        check(
            "UNEXPECTED APPLY ERROR IS CONTAINED AND WORKSPACE RESTORED",
            {
                "issue_codes": list(report.issue_codes),
                "state": report.state,
                "clean_base": _workspace_is_clean_base(repository_root, workspace.base_commit),
            },
            {
                "issue_codes": ["patch_apply_unexpected_error"],
                "state": "rejected_clean",
                "clean_base": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        with patch.object(
            patch_apply_git_module,
            "parse_developer_task_patch_changes",
            return_value=(),
        ), patch.object(
            patch_apply_git_module,
            "_rollback_to_base",
            return_value=(True, False, "forced rollback failure"),
        ):
            report = _apply(manifest, preflight, workspace, parent)
        check(
            "ROLLBACK FAILURE IS STRUCTURED AND WORKSPACE IS NOT REUSABLE",
            {
                "issue_codes": list(report.issue_codes),
                "state": report.state,
                "rollback_attempted": report.rollback_attempted,
                "rollback_succeeded": report.rollback_succeeded,
                "workspace_clean": report.workspace_clean,
                "workspace_still_changed": bool(_staged_status(repository_root)),
            },
            {
                "issue_codes": ["workspace_patch_rollback_failed"],
                "state": "failed_dirty",
                "rollback_attempted": True,
                "rollback_succeeded": False,
                "workspace_clean": False,
                "workspace_still_changed": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        original_run_git = patch_apply_git_module._run_git

        def failing_apply(request: Any, *args: str, **kwargs: Any) -> Any:
            if args and args[0] == "apply":
                return patch_apply_git_module._GitResult(1, b"", b"forced apply failure")
            return original_run_git(request, *args, **kwargs)

        with patch.object(patch_apply_git_module, "_run_git", side_effect=failing_apply):
            report = _apply(manifest, preflight, workspace, parent)
        check(
            "GIT APPLY FAILURE ROLLS BACK TO CLEAN BASE",
            {
                "issue_codes": list(report.issue_codes),
                "state": report.state,
                "clean_base": _workspace_is_clean_base(repository_root, workspace.base_commit),
            },
            {
                "issue_codes": ["workspace_patch_apply_failed"],
                "state": "rejected_clean",
                "clean_base": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        original_run = subprocess.run

        def timeout_apply(command: Any, *args: Any, **kwargs: Any) -> Any:
            normalized = tuple(str(item) for item in command)
            if "apply" in normalized:
                raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 0))
            return original_run(command, *args, **kwargs)

        with patch.object(patch_apply_git_module.subprocess, "run", side_effect=timeout_apply):
            report = _apply(manifest, preflight, workspace, parent)
        check(
            "GIT APPLY TIMEOUT IS STRUCTURED AND ROLLED BACK",
            {
                "issue_codes": list(report.issue_codes),
                "state": report.state,
                "clean_base": _workspace_is_clean_base(repository_root, workspace.base_commit),
            },
            {
                "issue_codes": ["git_command_timeout"],
                "state": "rejected_clean",
                "clean_base": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        repository_root = Path(workspace.repository_root)
        with patch.object(
            patch_apply_git_module,
            "parse_developer_task_result_index_paths",
            return_value=(),
        ):
            report = _apply(manifest, preflight, workspace, parent)
        check(
            "RESULT INDEX PATH MISMATCH ROLLS BACK",
            {
                "issue_codes": list(report.issue_codes),
                "state": report.state,
                "clean_base": _workspace_is_clean_base(repository_root, workspace.base_commit),
            },
            {
                "issue_codes": ["workspace_patch_index_paths_mismatch"],
                "state": "rejected_clean",
                "clean_base": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        link = Path(workspace.control_root) / "unsafe-link"
        target = Path(workspace.control_root) / "target.txt"
        target.write_text("x", encoding="utf-8")
        symlink_supported = True
        try:
            link.symlink_to(target)
        except OSError:
            symlink_supported = False

        if symlink_supported:
            report = _apply(manifest, preflight, workspace, parent)
            actual = list(report.issue_codes)
            expected = ["workspace_tree_reparse_point"]
            link.unlink(missing_ok=True)
        else:
            actual = "unsupported"
            expected = "unsupported"
        check("WORKSPACE TREE SYMLINK IS REJECTED", actual, expected)
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        commands: list[tuple[str, ...]] = []
        apply_inputs: list[bytes | None] = []
        original_run = subprocess.run

        def recording_run(command: Any, *args: Any, **kwargs: Any) -> Any:
            normalized = tuple(str(item) for item in command)
            commands.append(normalized)
            if "apply" in normalized:
                apply_inputs.append(kwargs.get("input"))
            return original_run(command, *args, **kwargs)

        with patch.object(patch_apply_git_module.subprocess, "run", side_effect=recording_run):
            report = _apply(manifest, preflight, workspace, parent)

        apply_commands = [item for item in commands if "apply" in item]
        check(
            "PRODUCTION APPLY USES EXACT STDIN BYTES AND SAFE GIT OPTIONS",
            {
                "ok": report.ok,
                "one_apply": len(apply_commands) == 1,
                "uses_index": bool(apply_commands and "--index" in apply_commands[0]),
                "no_3way": all("--3way" not in item for item in apply_commands),
                "no_reject": all("--reject" not in item for item in apply_commands),
                "no_unsafe_paths": all("--unsafe-paths" not in item for item in apply_commands),
                "stdin_exact": apply_inputs == [preflight.patch.content],
                "explicit_git_dir": all(
                    any(part.startswith("--git-dir=") for part in item)
                    for item in apply_commands
                ),
                "explicit_work_tree": all(
                    any(part.startswith("--work-tree=") for part in item)
                    for item in apply_commands
                ),
                "file_protocol_locked": all(
                    "protocol.file.allow=never" in item
                    and item.index("protocol.file.allow=never")
                    > item.index("protocol.file.allow=always")
                    for item in apply_commands
                ),
                "all_commands_git": all(item and item[0] == "git" for item in commands),
            },
            {
                "ok": True,
                "one_apply": True,
                "uses_index": True,
                "no_3way": True,
                "no_reject": True,
                "no_unsafe_paths": True,
                "stdin_exact": True,
                "explicit_git_dir": True,
                "explicit_work_tree": True,
                "file_protocol_locked": True,
                "all_commands_git": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace = _prepare_workspace(Path(temp_dir))
        first = _apply(manifest, preflight, workspace, parent)
        second = _apply(manifest, preflight, workspace, parent)
        check(
            "REPEATED PATCH APPLY IS BLOCKED BY VERIFIED MARKER",
            {
                "first_ok": first.ok,
                "second_codes": list(second.issue_codes),
                "first_marker_preserved": Path(first.apply_marker_path).is_file(),
            },
            {
                "first_ok": True,
                "second_codes": ["patch_already_applied"],
                "first_marker_preserved": True,
            },
        )
        _cleanup_workspace(manifest, preflight, workspace, parent)

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {"case_count": case_count, "fail_count": fail_count},
        ensure_ascii=False,
        indent=2,
    ))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
