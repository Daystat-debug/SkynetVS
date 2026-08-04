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

import modules.developer.developer_task_check_static as static_module
import modules.developer.developer_task_check_static_git as static_git_module
import modules.developer.developer_task_check_static_python as static_python_module

from modules.developer.developer_task_check_static import (
    DeveloperTaskStaticCheckReport,
    run_developer_task_static_checks,
)
from modules.developer.developer_task_check_static_git import DeveloperTaskStaticGitError
from modules.developer.developer_task_check_static_python import (
    DeveloperTaskStaticPythonError,
    compile_changed_python_files,
)
from modules.developer.developer_task_contract import (
    DeveloperTaskCheck,
    DeveloperTaskManifest,
)
from modules.developer.developer_task_patch_apply import (
    DeveloperTaskPatchApplyReport,
    apply_developer_task_patch,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_preflight_composition import (
    DeveloperTaskPreflightReport,
    run_developer_task_preflight,
)
from modules.developer.developer_task_workspace import (
    DeveloperTaskWorkspaceReport,
    create_developer_task_workspace,
)
from modules.developer.developer_task_workspace_cleanup import (
    cleanup_developer_task_workspace,
)
from tools.eval_developer_task_workspace import (
    _git,
    _git_bytes,
    _index_path,
    _object_snapshot,
    _sha256,
)
from tools.eval_developer_task_workspace_cleanup import _remove_fixture_tree


def _issue(code: str = "forced_failure") -> DeveloperTaskPreflightIssue:
    return DeveloperTaskPreflightIssue(
        code=code,
        check="eval",
        message="Forced eval failure.",
    )


def _init_repo(root: Path, files: dict[str, bytes]) -> str:
    root.mkdir(parents=True)
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "eval@example.com")
    _git(root, "config", "user.name", "Static Check Eval")

    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "initial")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _make_patch(
    repo: Path,
    changes: dict[str, bytes | None],
) -> bytes:
    for relative, content in changes.items():
        path = repo / relative

        if content is None:
            path.unlink()
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    _git(repo, "add", "-A")
    payload = _git_bytes(
        repo,
        "diff",
        "--cached",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
        "HEAD",
        "--",
    ).stdout
    _git(repo, "reset", "--hard", "HEAD")
    _git(repo, "clean", "-fd")
    return payload


def _manifest(
    base_commit: str,
    patch_bytes: bytes,
    allowed_files: tuple[str, ...],
    *,
    task_id: str,
    with_py_compile: bool,
) -> DeveloperTaskManifest:
    checks = [DeveloperTaskCheck(type="git_diff_check")]

    if with_py_compile:
        checks.append(
            DeveloperTaskCheck(
                type="py_compile",
                scope="changed_python_files",
            )
        )

    checks.extend((
        DeveloperTaskCheck(
            type="python_module",
            module="tools.eval_static_dummy",
        ),
        DeveloperTaskCheck(
            type="pipeline",
            flow="check",
        ),
    ))

    return DeveloperTaskManifest(
        schema_version=1,
        task_kind="patch",
        task_id=task_id,
        title="Evaluate developer task static evidence gate",
        project="SkynetVS",
        origin="manual",
        source_ref="eval:developer-task-static-check",
        source_sha256="a" * 64,
        base_commit=base_commit,
        patch_file="changes.patch",
        patch_sha256=hashlib.sha256(patch_bytes).hexdigest(),
        allowed_files=allowed_files,
        checks=tuple(checks),
        install_policy="manual_confirmation",
    )


def _prepare_applied(
    root: Path,
    *,
    baseline: dict[str, bytes],
    changes: dict[str, bytes | None],
    task_id: str,
) -> tuple[
    Path,
    Path,
    Path,
    DeveloperTaskManifest,
    DeveloperTaskPreflightReport,
    DeveloperTaskWorkspaceReport,
    DeveloperTaskPatchApplyReport,
]:
    repo = root / "source"
    task_root = root / "task"
    workspace_parent = root / "workspaces"
    base_commit = _init_repo(repo, baseline)
    patch_bytes = _make_patch(repo, changes)
    task_root.mkdir()
    workspace_parent.mkdir()
    allowed_files = tuple(sorted(changes))
    with_py_compile = any(path.casefold().endswith(".py") for path in allowed_files)
    manifest = _manifest(
        base_commit,
        patch_bytes,
        allowed_files,
        task_id=task_id,
        with_py_compile=with_py_compile,
    )
    (task_root / manifest.patch_file).write_bytes(patch_bytes)
    preflight = run_developer_task_preflight(
        manifest,
        project_root=repo,
        task_root=task_root,
    )
    assert preflight.ok
    workspace = create_developer_task_workspace(
        manifest,
        preflight_report=preflight,
        workspace_parent=workspace_parent,
    )
    assert workspace.ok
    apply_report = apply_developer_task_patch(
        manifest,
        preflight_report=preflight,
        workspace_report=workspace,
        workspace_parent=workspace_parent,
    )
    assert apply_report.ok
    return (
        repo,
        task_root,
        workspace_parent,
        manifest,
        preflight,
        workspace,
        apply_report,
    )


def _run(
    manifest: Any,
    preflight: Any,
    workspace: Any,
    apply_report: Any,
    parent: Any,
) -> DeveloperTaskStaticCheckReport:
    return run_developer_task_static_checks(
        manifest,
        preflight_report=preflight,
        workspace_report=workspace,
        patch_apply_report=apply_report,
        workspace_parent=parent,
    )


def _cleanup(
    manifest: DeveloperTaskManifest,
    preflight: DeveloperTaskPreflightReport,
    workspace: DeveloperTaskWorkspaceReport,
    parent: Path,
) -> None:
    root = Path(workspace.workspace_root)

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

    _remove_fixture_tree(root)


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
        (
            repo,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={
                "module.py": b"value = 1\n",
                "unchanged.py": b"def untouched(:\n",
            },
            changes={
                "module.py": b"value = 2\n",
            },
            task_id="static-check-success",
        )
        repository_root = Path(workspace.repository_root)
        source_index = _index_path(repo)
        source_index_before = _sha256(source_index)
        source_file_before = (repo / "module.py").read_bytes()
        source_objects_before = _object_snapshot(repo)
        workspace_objects_before = _object_snapshot(repository_root)
        source_status_before = _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
        workspace_status_before = _git_bytes(
            repository_root,
            "status",
            "--porcelain=v2",
            "-z",
        ).stdout
        report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "STATIC GATE PASSES WITH IMMUTABLE GIT AND PYTHON EVIDENCE",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "completed": list(report.completed_checks),
                "pending": [item.type for item in report.pending_executable_checks],
                "changed_python": list(report.changed_python_files),
                "compiled": [
                    item.path
                    for item in report.python_evidence.compiled_files
                ] if report.python_evidence else [],
                "workspace_unchanged": report.workspace_unchanged,
                "source_unchanged": report.source_repository_unchanged,
                "source_index_unchanged": _sha256(source_index) == source_index_before,
                "source_file_unchanged": (repo / "module.py").read_bytes() == source_file_before,
                "source_objects_unchanged": _object_snapshot(repo) == source_objects_before,
                "workspace_objects_unchanged": (
                    _object_snapshot(repository_root) == workspace_objects_before
                ),
                "source_status_unchanged": (
                    _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
                    == source_status_before
                ),
                "workspace_status_unchanged": (
                    _git_bytes(
                        repository_root,
                        "status",
                        "--porcelain=v2",
                        "-z",
                    ).stdout
                    == workspace_status_before
                ),
                "no_pycache": not any(repository_root.rglob("__pycache__")),
            },
            {
                "ok": True,
                "issue_codes": [],
                "completed": ["git_diff_check", "py_compile"],
                "pending": ["python_module", "pipeline"],
                "changed_python": ["module.py"],
                "compiled": ["module.py"],
                "workspace_unchanged": True,
                "source_unchanged": True,
                "source_index_unchanged": True,
                "source_file_unchanged": True,
                "source_objects_unchanged": True,
                "workspace_objects_unchanged": True,
                "source_status_unchanged": True,
                "workspace_status_unchanged": True,
                "no_pycache": True,
            },
        )

        try:
            report.issues = ()
            immutable = False
        except FrozenInstanceError:
            immutable = True

        check("STATIC REPORT IS IMMUTABLE", immutable, True)
        check(
            "STATIC REPORT IS JSON SERIALIZABLE",
            isinstance(json.dumps(report.to_dict(), ensure_ascii=False), str),
            True,
        )
        check(
            "UNCHANGED INVALID PYTHON FILE IS NOT COMPILED",
            {
                "ok": report.ok,
                "compiled": [
                    item.path
                    for item in report.python_evidence.compiled_files
                ] if report.python_evidence else [],
            },
            {
                "ok": True,
                "compiled": ["module.py"],
            },
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        sentinel = Path(temp_dir) / "executed.txt"
        payload = (
            "from pathlib import Path\n"
            f"Path({str(sentinel)!r}).write_text('executed', encoding='utf-8')\n"
        ).encode("utf-8")
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir) / "case",
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": payload},
            task_id="static-check-no-exec",
        )
        report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "PYTHON TOP LEVEL IS COMPILED BUT NEVER EXECUTED",
            {
                "ok": report.ok,
                "sentinel_exists": sentinel.exists(),
            },
            {
                "ok": True,
                "sentinel_exists": False,
            },
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-types",
        )
        raw_checks: dict[str, bool] = {}

        for name, args in {
            "manifest": ({}, preflight, workspace, apply_report, parent),
            "preflight": (manifest, {}, workspace, apply_report, parent),
            "workspace": (manifest, preflight, {}, apply_report, parent),
            "apply": (manifest, preflight, workspace, {}, parent),
            "parent": (manifest, preflight, workspace, apply_report, str(parent)),
        }.items():
            try:
                _run(*args)
                raw_checks[name] = False
            except TypeError:
                raw_checks[name] = True

        check(
            "RAW STATIC INPUTS ARE REJECTED",
            raw_checks,
            {
                "manifest": True,
                "preflight": True,
                "workspace": True,
                "apply": True,
                "parent": True,
            },
        )

        failed_preflight = replace(preflight, issues=(_issue(),))
        check(
            "FAILED PREFLIGHT BLOCKS STATIC CHECKS",
            list(_run(
                manifest,
                failed_preflight,
                workspace,
                apply_report,
                parent,
            ).issue_codes),
            ["preflight_report_failed"],
        )

        failed_apply = replace(
            apply_report,
            applied=False,
            issues=(_issue(),),
        )
        check(
            "FAILED APPLY REPORT BLOCKS STATIC CHECKS",
            list(_run(
                manifest,
                preflight,
                workspace,
                failed_apply,
                parent,
            ).issue_codes),
            ["patch_apply_report_failed"],
        )

        check(
            "EXPLICIT WORKSPACE PARENT MISMATCH IS REJECTED",
            list(_run(
                manifest,
                preflight,
                workspace,
                apply_report,
                parent.parent,
            ).issue_codes),
            ["workspace_parent_mismatch"],
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-marker",
        )
        marker = Path(apply_report.apply_marker_path)
        marker.unlink()
        check(
            "MISSING APPLY MARKER BLOCKS STATIC CHECKS",
            list(_run(
                manifest,
                preflight,
                workspace,
                apply_report,
                parent,
            ).issue_codes),
            ["workspace_marker_missing"],
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-token",
        )
        forged = replace(apply_report, check_token=b"x" * 32)
        check(
            "FORGED CHECK CAPABILITY FAILS CANONICAL MARKER VALIDATION",
            list(_run(
                manifest,
                preflight,
                workspace,
                forged,
                parent,
            ).issue_codes),
            ["workspace_marker_evidence_mismatch"],
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-dirty",
        )
        repository_root = Path(workspace.repository_root)
        (repository_root / "module.py").write_text("value = 3\n", encoding="utf-8")
        report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "POST APPLY WORKTREE MUTATION IS REJECTED",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
            },
            {
                "ok": False,
                "issue_codes": ["workspace_patch_state_invalid"],
            },
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-index",
        )
        repository_root = Path(workspace.repository_root)
        (repository_root / "extra.txt").write_text("extra\n", encoding="utf-8")
        _git(repository_root, "add", "extra.txt")
        report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "POST APPLY INDEX MUTATION IS REJECTED",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
            },
            {
                "ok": False,
                "issue_codes": ["workspace_patch_facts_mismatch"],
            },
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            repo,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-source",
        )
        (repo / "module.py").write_text("source mutation\n", encoding="utf-8")
        report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "SOURCE MUTATION BEFORE STATIC CHECKS IS REJECTED",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
            },
            {
                "ok": False,
                "issue_codes": ["source_repository_changed"],
            },
        )
        _git(repo, "reset", "--hard", "HEAD")
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"def broken(:\n"},
            task_id="static-check-syntax",
        )
        repository_root = Path(workspace.repository_root)
        status_before = _git_bytes(
            repository_root,
            "status",
            "--porcelain=v2",
            "-z",
        ).stdout
        report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "PYTHON SYNTAX ERROR IS STRUCTURED WITHOUT WORKSPACE MUTATION",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "workspace_unchanged": report.workspace_unchanged,
                "status_unchanged": (
                    _git_bytes(
                        repository_root,
                        "status",
                        "--porcelain=v2",
                        "-z",
                    ).stdout
                    == status_before
                ),
            },
            {
                "ok": False,
                "issue_codes": ["static_python_syntax_error"],
                "workspace_unchanged": True,
                "status_unchanged": True,
            },
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": None},
            task_id="static-check-delete",
        )
        report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "DELETED PYTHON FILE IS RECORDED WITHOUT READ OR COMPILE",
            {
                "ok": report.ok,
                "compiled": [
                    item.path
                    for item in report.python_evidence.compiled_files
                ] if report.python_evidence else [],
                "deleted": list(
                    report.python_evidence.deleted_files
                ) if report.python_evidence else [],
            },
            {
                "ok": True,
                "compiled": [],
                "deleted": ["module.py"],
            },
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"tracked.txt": b"before\n"},
            changes={"tracked.txt": b"after\n"},
            task_id="static-check-non-python",
        )
        report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "NON PYTHON PATCH RUNS ONLY GIT DIFF STATIC CHECK",
            {
                "ok": report.ok,
                "completed": list(report.completed_checks),
                "python_evidence": report.python_evidence,
            },
            {
                "ok": True,
                "completed": ["git_diff_check"],
                "python_evidence": None,
            },
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        (root / "big.py").write_bytes(b"x" * 32)
        try:
            compile_changed_python_files(
                root,
                changed_files=("big.py",),
                result_index_paths=("big.py",),
                max_file_bytes=8,
            )
            code = ""
        except DeveloperTaskStaticPythonError as exc:
            code = exc.code
        check("PYTHON FILE SIZE LIMIT FAILS CLOSED", code, "static_python_file_too_large")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        (root / "a.py").write_bytes(b"a = 1\n")
        (root / "b.py").write_bytes(b"b = 2\n")
        try:
            compile_changed_python_files(
                root,
                changed_files=("a.py", "b.py"),
                result_index_paths=("a.py", "b.py"),
                max_file_bytes=100,
                max_total_bytes=10,
            )
            code = ""
        except DeveloperTaskStaticPythonError as exc:
            code = exc.code
        check("PYTHON TOTAL SIZE LIMIT FAILS CLOSED", code, "static_python_total_too_large")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        target = root / "target.py"
        link = root / "link.py"
        target.write_text("value = 1\n", encoding="utf-8")

        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            actual = "unsupported"
            expected = "unsupported"
        else:
            try:
                compile_changed_python_files(
                    root,
                    changed_files=("link.py",),
                    result_index_paths=("link.py",),
                )
                actual = ""
            except DeveloperTaskStaticPythonError as exc:
                actual = exc.code
            expected = "static_python_reparse_point"

        check("PYTHON SYMLINK OR REPARSE INPUT IS REJECTED", actual, expected)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        path = root / "module.py"
        path.write_text("value = 1\n", encoding="utf-8")
        with patch.object(static_python_module.os, "read", side_effect=OSError("forced")):
            try:
                compile_changed_python_files(
                    root,
                    changed_files=("module.py",),
                    result_index_paths=("module.py",),
                )
                code = ""
            except DeveloperTaskStaticPythonError as exc:
                code = exc.code
        check("PYTHON READ FAILURE IS STRUCTURED", code, "static_python_file_read_failed")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-git-failure",
        )
        with patch.object(
            static_git_module,
            "inspect_applied_independent_workspace",
            side_effect=DeveloperTaskStaticGitError(
                "git_command_timeout",
                "forced timeout",
            ),
        ):
            report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "STATIC GIT FAILURE IS STRUCTURED",
            list(report.issue_codes),
            ["git_command_timeout"],
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            _,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-compile-failure",
        )
        with patch.object(
            static_module,
            "compile_changed_python_files",
            side_effect=DeveloperTaskStaticPythonError(
                "static_python_compile_failed",
                "forced compiler failure",
                path="module.py",
            ),
        ):
            report = _run(manifest, preflight, workspace, apply_report, parent)
        check(
            "STATIC COMPILER FAILURE IS STRUCTURED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_unchanged": report.workspace_unchanged,
            },
            {
                "issue_codes": ["static_python_compile_failed"],
                "workspace_unchanged": True,
            },
        )
        _cleanup(manifest, preflight, workspace, parent)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        (
            repo,
            _,
            parent,
            manifest,
            preflight,
            workspace,
            apply_report,
        ) = _prepare_applied(
            Path(temp_dir),
            baseline={"module.py": b"value = 1\n"},
            changes={"module.py": b"value = 2\n"},
            task_id="static-check-source-during",
        )
        original_compile = static_module.compile_changed_python_files

        def mutate_source(*args: Any, **kwargs: Any) -> Any:
            result = original_compile(*args, **kwargs)
            (repo / "module.py").write_text("changed during static\n", encoding="utf-8")
            return result

        with patch.object(
            static_module,
            "compile_changed_python_files",
            side_effect=mutate_source,
        ):
            report = _run(manifest, preflight, workspace, apply_report, parent)

        check(
            "SOURCE MUTATION DURING STATIC CHECKS FAILS CLOSED",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "source_unchanged": report.source_repository_unchanged,
            },
            {
                "ok": False,
                "issue_codes": ["source_repository_changed"],
                "source_unchanged": False,
            },
        )
        _git(repo, "reset", "--hard", "HEAD")
        _cleanup(manifest, preflight, workspace, parent)

    import ast

    static_sources = (
        Path(static_module.__file__).read_text(encoding="utf-8"),
        Path(static_python_module.__file__).read_text(encoding="utf-8"),
    )
    imported_modules: set[str] = set()
    called_names: set[str] = set()

    for source in static_sources:
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called_names.add(node.func.id)

    check(
        "STATIC RUNNER DOES NOT IMPORT OR EXECUTE WORKSPACE MODULES",
        {
            "no_importlib": "importlib" not in imported_modules,
            "no_runpy": "runpy" not in imported_modules,
            "no_exec_call": "exec" not in called_names,
            "no_eval_call": "eval" not in called_names,
            "no_pyc_api": "py_compile" not in imported_modules,
        },
        {
            "no_importlib": True,
            "no_runpy": True,
            "no_exec_call": True,
            "no_eval_call": True,
            "no_pyc_api": True,
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
