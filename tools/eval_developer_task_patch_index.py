from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import modules.developer.developer_task_patch_index as patch_index

from modules.developer.developer_task_contract import (
    DeveloperTaskCheck,
    DeveloperTaskManifest,
)
from modules.developer.developer_task_patch_index import (
    run_developer_task_patch_index_preflight,
)
from modules.developer.developer_task_patch_integrity import (
    run_developer_task_patch_integrity_preflight,
)
from modules.developer.developer_task_preflight import (
    DeveloperTaskPreflightIssue,
    run_developer_task_repository_preflight,
)


def _git(
    root: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)

    for key in tuple(env):
        if key.startswith("GIT_"):
            env.pop(key, None)

    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
        env=env,
    )


def _git_bytes(
    root: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)

    for key in tuple(env):
        if key.startswith("GIT_"):
            env.pop(key, None)

    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=check,
        env=env,
    )


def _init_repo(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "--initial-branch=main")
    hooks_path = root / ".git" / "eval-empty-hooks"
    hooks_path.mkdir(parents=True, exist_ok=True)
    _git(root, "config", "commit.gpgSign", "false")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "config", "core.filemode", "true")
    _git(root, "config", "core.fsmonitor", "false")
    _git(root, "config", "core.hooksPath", str(hooks_path))
    _git(root, "config", "user.name", "SkynetVS Eval")
    _git(root, "config", "user.email", "eval@example.invalid")
    (root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    (root / "old_name.txt").write_text("rename me\n", encoding="utf-8")
    (root / "CaseBase.txt").write_text("case baseline\n", encoding="utf-8")
    (root / "mode.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _manifest(
    base_commit: str,
    patch_bytes: bytes,
    *,
    allowed_files: tuple[str, ...],
    title: str = "Evaluate isolated patch index preflight",
) -> DeveloperTaskManifest:
    return DeveloperTaskManifest(
        schema_version=1,
        task_kind="patch",
        task_id="developer-patch-index-eval",
        title=title,
        project="SkynetVS",
        origin="manual",
        source_ref="eval:developer-task-patch-index",
        source_sha256="a" * 64,
        base_commit=base_commit,
        patch_file="changes.patch",
        patch_sha256=hashlib.sha256(patch_bytes).hexdigest(),
        allowed_files=allowed_files,
        checks=(
            DeveloperTaskCheck(type="git_diff_check"),
            DeveloperTaskCheck(type="pipeline", flow="check"),
        ),
        install_policy="manual_confirmation",
    )


def _reports(
    repo: Path,
    task_root: Path,
    patch_bytes: bytes,
    *,
    allowed_files: tuple[str, ...],
) -> tuple[DeveloperTaskManifest, Any, Any]:
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    manifest = _manifest(head, patch_bytes, allowed_files=allowed_files)
    (task_root / manifest.patch_file).write_bytes(patch_bytes)
    repository_report = run_developer_task_repository_preflight(
        manifest,
        project_root=repo,
    )
    patch_report = run_developer_task_patch_integrity_preflight(
        manifest,
        repository_report=repository_report,
        task_root=task_root,
    )
    return manifest, repository_report, patch_report


def _staged_patch(
    repo: Path,
    mutate: Callable[[], None],
    *,
    detect_renames: bool = False,
    detect_copies: bool = False,
) -> bytes:
    mutate()
    _git(repo, "add", "-A")
    args = [
        "diff",
        "--cached",
        "--binary",
        "--full-index",
        "--no-ext-diff",
    ]

    if detect_copies:
        args.extend(("-C", "--find-copies-harder"))
    elif detect_renames:
        args.append("-M")
    else:
        args.append("--no-renames")

    payload = _git_bytes(repo, *args).stdout
    _git(repo, "reset", "--hard", "HEAD")
    _git(repo, "clean", "-fd")
    return payload


def _index_path(root: Path) -> Path:
    value = _git(root, "rev-parse", "--git-path", "index").stdout.strip()
    path = Path(value)
    return path if path.is_absolute() else root / path


def _object_snapshot(root: Path) -> dict[str, str]:
    value = _git(root, "rev-parse", "--git-path", "objects").stdout.strip()
    object_root = Path(value)

    if not object_root.is_absolute():
        object_root = root / object_root

    result: dict[str, str] = {}

    for path in sorted(object_root.rglob("*")):
        if path.is_file():
            result[path.relative_to(object_root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()

    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mode_change_patch() -> bytes:
    return (
        "diff --git a/mode.sh b/mode.sh\n"
        "old mode 100644\n"
        "new mode 100755\n"
    ).encode("utf-8")


def _symlink_patch() -> bytes:
    return (
        "diff --git a/link b/link\n"
        "new file mode 120000\n"
        "index 0000000..1de5659\n"
        "--- /dev/null\n"
        "+++ b/link\n"
        "@@ -0,0 +1 @@\n"
        "+target\n"
        "\\ No newline at end of file\n"
    ).encode("utf-8")


def _gitlink_patch(commit: str) -> bytes:
    return (
        "diff --git a/vendor/sub b/vendor/sub\n"
        "new file mode 160000\n"
        f"index 0000000..{commit[:7]}\n"
        "--- /dev/null\n"
        "+++ b/vendor/sub\n"
        "@@ -0,0 +1 @@\n"
        f"+Subproject commit {commit}\n"
    ).encode("utf-8")


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

    with tempfile.TemporaryDirectory(prefix="skynet_patch_index_eval_") as temp_dir:
        temp_root = Path(temp_dir)
        repo = temp_root / "repo"
        head = _init_repo(repo)
        task_root = temp_root / "task inbox"
        task_root.mkdir()
        scratch_parent = temp_root / "scratch"
        scratch_parent.mkdir()

        valid_patch = _staged_patch(
            repo,
            lambda: (repo / "tracked.txt").write_text("changed\n", encoding="utf-8"),
        )
        manifest, repository_report, patch_report = _reports(
            repo,
            task_root,
            valid_patch,
            allowed_files=("tracked.txt",),
        )
        index_path = _index_path(repo)
        index_before = _sha256(index_path)
        tracked_before = _sha256(repo / "tracked.txt")
        objects_before = _object_snapshot(repo)

        def create_scratch() -> Path:
            return Path(tempfile.mkdtemp(
                prefix=patch_index._TEMP_WORKSPACE_PREFIX,
                dir=scratch_parent,
            ))

        poison_trace = temp_root / "git-trace.log"
        poison_index = temp_root / "poison-index"
        poison_objects = temp_root / "poison-objects"
        poison_objects.mkdir()

        with patch.dict(
            os.environ,
            {
                "GIT_EXTERNAL_DIFF": "definitely-not-a-command",
                "GIT_INDEX_FILE": str(poison_index),
                "GIT_OBJECT_DIRECTORY": str(poison_objects),
                "GIT_TRACE": str(poison_trace),
            },
        ), patch(
            "modules.developer.developer_task_patch_index._create_temporary_workspace",
            side_effect=create_scratch,
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )

        check(
            "VALID PATCH PASSES IN FULLY ISOLATED GIT STATE",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "changed_files": list(report.changed_files),
                "changes": [item.to_dict() for item in report.changes],
                "result_index_paths": list(report.result_index_paths),
                "index_unchanged": index_before == _sha256(index_path),
                "tracked_unchanged": tracked_before == _sha256(repo / "tracked.txt"),
                "objects_unchanged": objects_before == _object_snapshot(repo),
                "scratch_cleaned": list(scratch_parent.iterdir()) == [],
                "poison_index_absent": not poison_index.exists(),
                "poison_trace_absent": not poison_trace.exists(),
            },
            {
                "ok": True,
                "issue_codes": [],
                "changed_files": ["tracked.txt"],
                "changes": [{
                    "path": "tracked.txt",
                    "status": "M",
                    "old_mode": "100644",
                    "new_mode": "100644",
                }],
                "result_index_paths": [
                    "CaseBase.txt",
                    "mode.sh",
                    "old_name.txt",
                    "tracked.txt",
                ],
                "index_unchanged": True,
                "tracked_unchanged": True,
                "objects_unchanged": True,
                "scratch_cleaned": True,
                "poison_index_absent": True,
                "poison_trace_absent": True,
            },
        )

        report_frozen = False
        change_frozen = False

        try:
            report.base_commit = "changed"
        except FrozenInstanceError:
            report_frozen = True

        try:
            report.changes[0].status = "A"
        except FrozenInstanceError:
            change_frozen = True

        check(
            "PATCH INDEX REPORT AND CHANGES ARE IMMUTABLE",
            {"report": report_frozen, "change": change_frozen},
            {"report": True, "change": True},
        )

        raw_manifest_rejected = False

        try:
            run_developer_task_patch_index_preflight(  # type: ignore[arg-type]
                {},
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        except TypeError:
            raw_manifest_rejected = True

        check("RAW MANIFEST IS REJECTED", raw_manifest_rejected, True)

        raw_repository_report_rejected = False

        try:
            run_developer_task_patch_index_preflight(  # type: ignore[arg-type]
                manifest,
                repository_report={},
                patch_integrity_report=patch_report,
            )
        except TypeError:
            raw_repository_report_rejected = True

        check("RAW REPOSITORY REPORT IS REJECTED", raw_repository_report_rejected, True)

        raw_patch_report_rejected = False

        try:
            run_developer_task_patch_index_preflight(  # type: ignore[arg-type]
                manifest,
                repository_report=repository_report,
                patch_integrity_report={},
            )
        except TypeError:
            raw_patch_report_rejected = True

        check("RAW PATCH REPORT IS REJECTED", raw_patch_report_rejected, True)

        failed_repository_report = replace(
            repository_report,
            issues=(DeveloperTaskPreflightIssue(
                code="dirty_worktree",
                check="worktree_cleanliness",
                message="fake failure",
            ),),
        )
        report = run_developer_task_patch_index_preflight(
            manifest,
            repository_report=failed_repository_report,
            patch_integrity_report=patch_report,
        )
        check(
            "FAILED REPOSITORY PREFLIGHT BLOCKS INDEX ANALYSIS",
            list(report.issue_codes),
            ["repository_preflight_failed"],
        )

        failed_patch_report = replace(
            patch_report,
            issues=(DeveloperTaskPreflightIssue(
                code="patch_hash_mismatch",
                check="patch_sha256",
                message="fake failure",
            ),),
            patch=None,
        )
        report = run_developer_task_patch_index_preflight(
            manifest,
            repository_report=repository_report,
            patch_integrity_report=failed_patch_report,
        )
        check(
            "FAILED PATCH INTEGRITY PREFLIGHT BLOCKS INDEX ANALYSIS",
            list(report.issue_codes),
            ["patch_integrity_preflight_failed"],
        )

        mismatched_repository_report = replace(
            repository_report,
            manifest_fingerprint="0" * 64,
        )
        report = run_developer_task_patch_index_preflight(
            manifest,
            repository_report=mismatched_repository_report,
            patch_integrity_report=patch_report,
        )
        check(
            "MANIFEST FINGERPRINT MISMATCH IS REJECTED",
            list(report.issue_codes),
            ["manifest_fingerprint_mismatch"],
        )

        wrong_root_patch_report = replace(
            patch_report,
            repository_root=str(temp_root / "other-repo"),
        )
        report = run_developer_task_patch_index_preflight(
            manifest,
            repository_report=repository_report,
            patch_integrity_report=wrong_root_patch_report,
        )
        check(
            "PATCH REPORT ROOT MISMATCH IS REJECTED",
            list(report.issue_codes),
            ["patch_integrity_preflight_invalid"],
        )

        assert patch_report.patch is not None
        invalid_content = patch_report.patch.content + b"x"
        invalid_snapshot = replace(
            patch_report.patch,
            content=invalid_content,
            size_bytes=len(invalid_content),
        )
        invalid_snapshot_report = replace(
            patch_report,
            patch=invalid_snapshot,
            patch_size_bytes=invalid_snapshot.size_bytes,
        )
        report = run_developer_task_patch_index_preflight(
            manifest,
            repository_report=repository_report,
            patch_integrity_report=invalid_snapshot_report,
        )
        check(
            "INCONSISTENT PATCH SNAPSHOT IS REJECTED",
            list(report.issue_codes),
            ["patch_snapshot_invalid"],
        )

        report = run_developer_task_patch_index_preflight(
            replace(manifest, title="mutated after proof"),
            repository_report=repository_report,
            patch_integrity_report=patch_report,
        )
        check(
            "MUTATED MANIFEST WITHOUT NEW PROOFS IS REJECTED",
            list(report.issue_codes),
            ["manifest_fingerprint_mismatch"],
        )

        rename_patch = _staged_patch(
            repo,
            lambda: _git(repo, "mv", "old_name.txt", "new_name.txt"),
            detect_renames=True,
        )
        rename_manifest, rename_repository, rename_integrity = _reports(
            repo,
            task_root,
            rename_patch,
            allowed_files=("old_name.txt", "new_name.txt"),
        )
        report = run_developer_task_patch_index_preflight(
            rename_manifest,
            repository_report=rename_repository,
            patch_integrity_report=rename_integrity,
        )
        check(
            "RENAME IS NORMALIZED TO DELETE AND ADD",
            {
                "ok": report.ok,
                "changed_files": list(report.changed_files),
                "statuses": [item.status for item in report.changes],
            },
            {
                "ok": True,
                "changed_files": ["new_name.txt", "old_name.txt"],
                "statuses": ["A", "D"],
            },
        )

        copy_patch = _staged_patch(
            repo,
            lambda: (repo / "copied.txt").write_text(
                (repo / "old_name.txt").read_text(encoding="utf-8"),
                encoding="utf-8",
            ),
            detect_copies=True,
        )
        copy_manifest, copy_repository, copy_integrity = _reports(
            repo,
            task_root,
            copy_patch,
            allowed_files=("copied.txt",),
        )
        report = run_developer_task_patch_index_preflight(
            copy_manifest,
            repository_report=copy_repository,
            patch_integrity_report=copy_integrity,
        )
        check(
            "EXPLICIT COPY OPERATION IS REJECTED",
            list(report.issue_codes),
            ["patch_copy_unsupported"],
        )

        multi_patch = _staged_patch(
            repo,
            lambda: (
                (repo / "old_name.txt").unlink(),
                (repo / "added.txt").write_text("new\n", encoding="utf-8"),
            ),
        )
        multi_manifest, multi_repository, multi_integrity = _reports(
            repo,
            task_root,
            multi_patch,
            allowed_files=("old_name.txt", "added.txt"),
        )
        report = run_developer_task_patch_index_preflight(
            multi_manifest,
            repository_report=multi_repository,
            patch_integrity_report=multi_integrity,
        )
        check(
            "ADD AND DELETE MODES ARE REPORTED",
            [item.to_dict() for item in report.changes],
            [
                {"path": "added.txt", "status": "A", "old_mode": "000000", "new_mode": "100644"},
                {"path": "old_name.txt", "status": "D", "old_mode": "100644", "new_mode": "000000"},
            ],
        )

        mode_bytes = _mode_change_patch()
        mode_manifest, mode_repository, mode_integrity = _reports(
            repo,
            task_root,
            mode_bytes,
            allowed_files=("mode.sh",),
        )
        report = run_developer_task_patch_index_preflight(
            mode_manifest,
            repository_report=mode_repository,
            patch_integrity_report=mode_integrity,
        )
        check(
            "EXECUTABLE MODE CHANGE IS REPORTED",
            [item.to_dict() for item in report.changes],
            [{"path": "mode.sh", "status": "M", "old_mode": "100644", "new_mode": "100755"}],
        )

        symlink_manifest, symlink_repository, symlink_integrity = _reports(
            repo,
            task_root,
            _symlink_patch(),
            allowed_files=("link",),
        )
        report = run_developer_task_patch_index_preflight(
            symlink_manifest,
            repository_report=symlink_repository,
            patch_integrity_report=symlink_integrity,
        )
        check(
            "SYMLINK MODE IS EXPOSED FOR THE POLICY GATE",
            [item.to_dict() for item in report.changes],
            [{"path": "link", "status": "A", "old_mode": "000000", "new_mode": "120000"}],
        )

        gitlink_manifest, gitlink_repository, gitlink_integrity = _reports(
            repo,
            task_root,
            _gitlink_patch(head),
            allowed_files=("vendor/sub",),
        )
        report = run_developer_task_patch_index_preflight(
            gitlink_manifest,
            repository_report=gitlink_repository,
            patch_integrity_report=gitlink_integrity,
        )
        check(
            "GITLINK MODE IS EXPOSED FOR THE POLICY GATE",
            [item.to_dict() for item in report.changes],
            [{"path": "vendor/sub", "status": "A", "old_mode": "000000", "new_mode": "160000"}],
        )

        malformed = b"not a patch\n"
        malformed_manifest, malformed_repository, malformed_integrity = _reports(
            repo,
            task_root,
            malformed,
            allowed_files=("tracked.txt",),
        )
        report = run_developer_task_patch_index_preflight(
            malformed_manifest,
            repository_report=malformed_repository,
            patch_integrity_report=malformed_integrity,
        )
        check(
            "NON-PATCH PAYLOAD PRODUCES NO CHANGES",
            list(report.issue_codes),
            ["patch_no_changes"],
        )

        no_diff_patch = b"Subject: developer task without a diff\n\n"
        no_diff_manifest, no_diff_repository, no_diff_integrity = _reports(
            repo,
            task_root,
            no_diff_patch,
            allowed_files=("tracked.txt",),
        )
        report = run_developer_task_patch_index_preflight(
            no_diff_manifest,
            repository_report=no_diff_repository,
            patch_integrity_report=no_diff_integrity,
        )
        check("PATCH WITHOUT A DIFF IS REJECTED", list(report.issue_codes), ["patch_no_changes"])

        with patch(
            "modules.developer.developer_task_patch_index._parse_raw_diff",
            return_value=(),
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check("PATCH WITH NO RESULTING CHANGES IS REJECTED", list(report.issue_codes), ["patch_no_changes"])

        with patch(
            "modules.developer.developer_task_patch_index._parse_raw_diff",
            side_effect=ValueError("fake raw output failure"),
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check(
            "INVALID GIT MACHINE OUTPUT IS STRUCTURED",
            list(report.issue_codes),
            ["patch_index_output_invalid"],
        )

        with patch(
            "modules.developer.developer_task_patch_index._create_temporary_workspace",
            side_effect=PermissionError("fake temp creation failure"),
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check("TEMPORARY WORKSPACE CREATION FAILURE IS STRUCTURED", list(report.issue_codes), ["temporary_workspace_failed"])

        with patch(
            "modules.developer.developer_task_patch_index._create_temporary_workspace",
            return_value=repo,
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check(
            "TEMPORARY WORKSPACE MUST NOT OVERLAP OR DELETE REPOSITORY",
            {
                "issue_codes": list(report.issue_codes),
                "repository_exists": repo.is_dir(),
                "head_unchanged": _git(repo, "rev-parse", "HEAD").stdout.strip() == head,
            },
            {
                "issue_codes": ["temporary_workspace_overlap"],
                "repository_exists": True,
                "head_unchanged": True,
            },
        )

        unsafe_scratch = temp_root / f"{patch_index._TEMP_WORKSPACE_PREFIX}unsafe"
        unsafe_scratch.mkdir()
        with patch(
            "modules.developer.developer_task_patch_index._create_temporary_workspace",
            return_value=unsafe_scratch,
        ), patch(
            "modules.developer.developer_task_patch_index._prepare_temporary_git_environment",
            side_effect=OSError("fake temp preparation failure"),
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check("TEMPORARY WORKSPACE PREPARATION FAILURE IS STRUCTURED", list(report.issue_codes), ["temporary_workspace_failed"])

        cleanup_retry_scratch = temp_root / f"{patch_index._TEMP_WORKSPACE_PREFIX}retry"
        cleanup_retry_scratch.mkdir()
        with patch(
            "modules.developer.developer_task_patch_index._create_temporary_workspace",
            return_value=cleanup_retry_scratch,
        ), patch(
            "modules.developer.developer_task_patch_index.shutil.rmtree",
            side_effect=[PermissionError("fake transient cleanup lock"), None],
        ) as cleanup_retry, patch(
            "modules.developer.developer_task_patch_index.time.sleep",
        ) as cleanup_sleep:
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check(
            "TRANSIENT TEMPORARY WORKSPACE CLEANUP FAILURE IS RETRIED",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "cleanup_calls": cleanup_retry.call_count,
                "sleep_calls": cleanup_sleep.call_count,
            },
            {
                "ok": True,
                "issue_codes": [],
                "cleanup_calls": 2,
                "sleep_calls": 1,
            },
        )
        shutil.rmtree(cleanup_retry_scratch)

        cleanup_scratch = temp_root / f"{patch_index._TEMP_WORKSPACE_PREFIX}cleanup"
        cleanup_scratch.mkdir()
        with patch(
            "modules.developer.developer_task_patch_index._create_temporary_workspace",
            return_value=cleanup_scratch,
        ), patch(
            "modules.developer.developer_task_patch_index.shutil.rmtree",
            side_effect=PermissionError("fake cleanup failure"),
        ) as cleanup_failure, patch(
            "modules.developer.developer_task_patch_index.time.sleep",
        ) as cleanup_sleep:
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check(
            "TEMPORARY WORKSPACE CLEANUP FAILURE IS STRUCTURED",
            {
                "issue_codes": list(report.issue_codes),
                "cleanup_calls": cleanup_failure.call_count,
                "sleep_calls": cleanup_sleep.call_count,
            },
            {
                "issue_codes": ["temporary_workspace_cleanup_failed"],
                "cleanup_calls": 5,
                "sleep_calls": 4,
            },
        )
        shutil.rmtree(cleanup_scratch)

        with patch(
            "modules.developer.developer_task_patch_index.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=10),
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check("GIT TIMEOUT IS STRUCTURED", list(report.issue_codes), ["git_command_timeout"])

        with patch(
            "modules.developer.developer_task_patch_index.subprocess.run",
            side_effect=FileNotFoundError("fake missing git"),
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check("MISSING GIT IS STRUCTURED", list(report.issue_codes), ["git_unavailable"])

        with patch(
            "modules.developer.developer_task_patch_index.subprocess.run",
            side_effect=OSError("fake launch failure"),
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check("GIT LAUNCH FAILURE IS STRUCTURED", list(report.issue_codes), ["git_command_failed"])

        original_run_git = patch_index._run_git_bytes

        def invalid_object_dir(root: Path, *args: str, **kwargs: Any) -> Any:
            if args == ("rev-parse", "--git-path", "objects"):
                return patch_index._GitBytesResult(0, b"bad\npath\n", b"")
            return original_run_git(root, *args, **kwargs)

        with patch(
            "modules.developer.developer_task_patch_index._run_git_bytes",
            side_effect=invalid_object_dir,
        ):
            report = run_developer_task_patch_index_preflight(
                manifest,
                repository_report=repository_report,
                patch_integrity_report=patch_report,
            )
        check("INVALID OBJECT DIRECTORY OUTPUT IS STRUCTURED", list(report.issue_codes), ["git_object_directory_unresolved"])

        raw_payload = (
            b":000000 100644 " + b"0" * 40 + b" " + b"1" * 40 + b" A\x00new.txt\x00"
            b":100644 000000 " + b"2" * 40 + b" " + b"0" * 40 + b" D\x00old.txt\x00"
        )
        parsed = patch_index._parse_raw_diff(raw_payload)
        check(
            "RAW DIFF PARSER CLASSIFIES ADD AND DELETE",
            [item.to_dict() for item in parsed],
            [
                {"path": "new.txt", "status": "A", "old_mode": "000000", "new_mode": "100644"},
                {"path": "old.txt", "status": "D", "old_mode": "100644", "new_mode": "000000"},
            ],
        )

        check(
            "WINDOWS PATH KEY PRESERVES DISTINCT UNICODE NAMES",
            {
                "ascii_case_matches": patch_index._path_key("Foo.py") == patch_index._path_key("foo.py"),
                "sharp_s_is_distinct": patch_index._path_key("straße.py") != patch_index._path_key("strasse.py"),
            },
            {"ascii_case_matches": True, "sharp_s_is_distinct": True},
        )

        unsafe_windows_path_rejected = False
        unsafe_payload = (
            b":000000 100644 " + b"0" * 40 + b" " + b"1" * 40 + b" A\x00CON.txt\x00"
        )

        try:
            patch_index._parse_raw_diff(unsafe_payload)
        except ValueError:
            unsafe_windows_path_rejected = True

        check("RAW DIFF PARSER REJECTS WINDOWS-UNSAFE PATHS", unsafe_windows_path_rejected, True)

        invalid_raw_rejected = False

        try:
            patch_index._parse_raw_diff(b"not-raw\x00path\x00")
        except ValueError:
            invalid_raw_rejected = True

        check("RAW DIFF PARSER REJECTS INVALID RECORDS", invalid_raw_rejected, True)

        index_payload = (
            b"100644 " + b"1" * 40 + b" 0\tFoo.txt\x00"
            b"100644 " + b"2" * 40 + b" 0\tfoo.TXT\x00"
        )
        check(
            "INDEX PARSER PRESERVES DISTINCT CASED PATHS FOR POLICY",
            list(patch_index._parse_index_paths(index_payload)),
            ["Foo.txt", "foo.TXT"],
        )

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
