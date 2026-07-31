from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_patch_integrity as patch_integrity

from modules.developer.developer_task_contract import (
    DeveloperTaskCheck,
    DeveloperTaskManifest,
)
from modules.developer.developer_task_patch_integrity import (
    run_developer_task_patch_integrity_preflight,
)
from modules.developer.developer_task_preflight import (
    DeveloperTaskPreflightIssue,
    run_developer_task_repository_preflight,
)


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)

    for key in (
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_WORK_TREE",
    ):
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


def _init_repo(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "--initial-branch=main")
    hooks_path = root / ".git" / "eval-empty-hooks"
    hooks_path.mkdir(parents=True, exist_ok=True)
    _git(root, "config", "commit.gpgSign", "false")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "config", "core.fsmonitor", "false")
    _git(root, "config", "core.hooksPath", str(hooks_path))
    _git(root, "config", "user.name", "SkynetVS Eval")
    _git(root, "config", "user.email", "eval@example.invalid")
    (root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-m", "baseline")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _manifest(
    base_commit: str,
    patch_bytes: bytes,
    *,
    patch_file: str = "changes.patch",
    patch_sha256: str | None = None,
    title: str = "Evaluate patch integrity preflight",
) -> DeveloperTaskManifest:
    return DeveloperTaskManifest(
        schema_version=1,
        task_kind="patch",
        task_id="developer-patch-integrity-eval",
        title=title,
        project="SkynetVS",
        origin="manual",
        source_ref="eval:developer-task-patch-integrity",
        source_sha256="a" * 64,
        base_commit=base_commit,
        patch_file=patch_file,
        patch_sha256=patch_sha256 or hashlib.sha256(patch_bytes).hexdigest(),
        allowed_files=("modules/example.py",),
        checks=(
            DeveloperTaskCheck(type="git_diff_check"),
            DeveloperTaskCheck(type="py_compile", scope="changed_python_files"),
            DeveloperTaskCheck(type="pipeline", flow="check"),
        ),
        install_policy="manual_confirmation",
    )


def _index_path(root: Path) -> Path:
    value = _git(root, "rev-parse", "--git-path", "index").stdout.strip()
    path = Path(value)
    return path if path.is_absolute() else root / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            {
                "actual": actual,
                "expected": expected,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ))

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    with tempfile.TemporaryDirectory(prefix="skynet_patch_integrity_eval_") as temp_dir:
        temp_root = Path(temp_dir)
        repo = temp_root / "repo"
        head = _init_repo(repo)
        task_root = temp_root / "task inbox"
        task_root.mkdir()
        patch_bytes = b"diff --git a/modules/example.py b/modules/example.py\n"
        manifest = _manifest(head, patch_bytes)
        patch_path = task_root / manifest.patch_file
        patch_path.write_bytes(patch_bytes)
        repository_report = run_developer_task_repository_preflight(manifest, project_root=repo)
        index_path = _index_path(repo)
        index_hash_before = _sha256(index_path)
        tracked_hash_before = _sha256(repo / "tracked.txt")
        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=repository_report,
            task_root=task_root,
        )
        index_hash_after = _sha256(index_path)
        tracked_hash_after = _sha256(repo / "tracked.txt")
        serialized = json.dumps(report.to_dict(), ensure_ascii=False)

        check(
            "VALID PATCH PASSES WITH IMMUTABLE BYTE SNAPSHOT",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "task_root_matches": Path(report.task_root) == task_root.resolve(),
                "patch_path_matches": Path(report.patch_path) == patch_path.resolve(),
                "size": report.patch_size_bytes,
                "hash": report.actual_patch_sha256,
                "snapshot_exists": report.patch is not None,
                "snapshot_bytes_match": report.patch is not None and report.patch.content == patch_bytes,
                "snapshot_path_matches": report.patch is not None and Path(report.patch.path) == patch_path.resolve(),
                "serialized_excludes_content": "content" not in serialized and "diff --git" not in serialized,
                "index_unchanged": index_hash_before == index_hash_after,
                "tracked_file_unchanged": tracked_hash_before == tracked_hash_after,
            },
            {
                "ok": True,
                "issue_codes": [],
                "task_root_matches": True,
                "patch_path_matches": True,
                "size": len(patch_bytes),
                "hash": hashlib.sha256(patch_bytes).hexdigest(),
                "snapshot_exists": True,
                "snapshot_bytes_match": True,
                "snapshot_path_matches": True,
                "serialized_excludes_content": True,
                "index_unchanged": True,
                "tracked_file_unchanged": True,
            },
        )

        report_frozen = False
        snapshot_frozen = False

        try:
            report.patch_size_bytes = 0
        except FrozenInstanceError:
            report_frozen = True

        try:
            if report.patch is not None:
                report.patch.content = b"changed"
        except FrozenInstanceError:
            snapshot_frozen = True

        check(
            "PATCH REPORT AND SNAPSHOT ARE IMMUTABLE",
            {
                "report": report_frozen,
                "snapshot": snapshot_frozen,
            },
            {
                "report": True,
                "snapshot": True,
            },
        )

        version_base = SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600,
            st_dev=10,
            st_ino=20,
            st_size=len(patch_bytes),
            st_mtime_ns=1_000,
            st_ctime_ns=2_000,
        )
        version_ctime_changed = SimpleNamespace(
            st_mode=version_base.st_mode,
            st_dev=version_base.st_dev,
            st_ino=version_base.st_ino,
            st_size=version_base.st_size,
            st_mtime_ns=version_base.st_mtime_ns,
            st_ctime_ns=9_000,
        )
        check(
            "PLATFORM CTIME DIFFERENCE DOES NOT INVALIDATE FILE VERSION",
            patch_integrity._same_file_version(version_base, version_ctime_changed),
            True,
        )

        raw_manifest_rejected = False

        try:
            run_developer_task_patch_integrity_preflight(  # type: ignore[arg-type]
                {},
                repository_report=repository_report,
                task_root=task_root,
            )
        except TypeError:
            raw_manifest_rejected = True

        check("RAW MANIFEST IS REJECTED", raw_manifest_rejected, True)

        raw_report_rejected = False

        try:
            run_developer_task_patch_integrity_preflight(  # type: ignore[arg-type]
                manifest,
                repository_report={},
                task_root=task_root,
            )
        except TypeError:
            raw_report_rejected = True

        check("RAW REPOSITORY REPORT IS REJECTED", raw_report_rejected, True)

        string_root_rejected = False

        try:
            run_developer_task_patch_integrity_preflight(  # type: ignore[arg-type]
                manifest,
                repository_report=repository_report,
                task_root=str(task_root),
            )
        except TypeError:
            string_root_rejected = True

        check("STRING TASK ROOT IS REJECTED", string_root_rejected, True)

        failed_repository_report = replace(
            repository_report,
            issues=(
                DeveloperTaskPreflightIssue(
                    code="dirty_worktree",
                    check="worktree_cleanliness",
                    message="fake failure",
                ),
            ),
        )
        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=failed_repository_report,
            task_root=task_root,
        )
        check(
            "FAILED REPOSITORY PREFLIGHT BLOCKS PATCH READ",
            {
                "issue_codes": list(report.issue_codes),
                "patch": report.patch,
            },
            {
                "issue_codes": ["repository_preflight_failed"],
                "patch": None,
            },
        )

        invalid_repository_report = replace(repository_report, repository_root="")
        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=invalid_repository_report,
            task_root=task_root,
        )
        check(
            "INCONSISTENT REPOSITORY REPORT IS REJECTED",
            list(report.issue_codes),
            ["repository_preflight_invalid"],
        )

        different_manifest = _manifest(head, patch_bytes, title="Different manifest")
        report = run_developer_task_patch_integrity_preflight(
            different_manifest,
            repository_report=repository_report,
            task_root=task_root,
        )
        check(
            "MANIFEST FINGERPRINT MISMATCH IS REJECTED",
            list(report.issue_codes),
            ["manifest_fingerprint_mismatch"],
        )

        missing_root = temp_root / "missing task root"
        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=repository_report,
            task_root=missing_root,
        )
        check("MISSING TASK ROOT IS REJECTED", list(report.issue_codes), ["task_root_missing"])

        file_root = temp_root / "task-root-file"
        file_root.write_text("not a directory", encoding="utf-8")
        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=repository_report,
            task_root=file_root,
        )
        check("FILE TASK ROOT IS REJECTED", list(report.issue_codes), ["task_root_not_directory"])

        with patch(
            "modules.developer.developer_task_patch_integrity._read_path_metadata",
            side_effect=PermissionError("fake task root metadata failure"),
        ):
            report = run_developer_task_patch_integrity_preflight(
                manifest,
                repository_report=repository_report,
                task_root=task_root,
            )

        check(
            "TASK ROOT METADATA FAILURE IS STRUCTURED",
            list(report.issue_codes),
            ["task_root_metadata_failed"],
        )

        with patch(
            "modules.developer.developer_task_patch_integrity._is_reparse_or_symlink",
            return_value=True,
        ):
            report = run_developer_task_patch_integrity_preflight(
                manifest,
                repository_report=repository_report,
                task_root=task_root,
            )

        check("TASK ROOT REPARSE POINT IS REJECTED", list(report.issue_codes), ["task_root_reparse_point"])

        inside_root = repo / "task inbox"
        inside_root.mkdir()
        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=repository_report,
            task_root=inside_root,
        )
        check("TASK ROOT INSIDE PROJECT IS REJECTED", list(report.issue_codes), ["task_root_overlaps_project"])
        inside_root.rmdir()

        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=repository_report,
            task_root=temp_root,
        )
        check("TASK ROOT CONTAINING PROJECT IS REJECTED", list(report.issue_codes), ["task_root_overlaps_project"])

        invalid_name_manifest = _manifest(head, patch_bytes, patch_file="../escape.patch")
        invalid_name_repository_report = run_developer_task_repository_preflight(
            invalid_name_manifest,
            project_root=repo,
        )
        report = run_developer_task_patch_integrity_preflight(
            invalid_name_manifest,
            repository_report=invalid_name_repository_report,
            task_root=task_root,
        )
        check("INVALID PATCH FILE NAME IS REJECTED", list(report.issue_codes), ["patch_file_invalid"])

        invalid_hash_manifest = _manifest(head, patch_bytes, patch_sha256="NOT-A-SHA256")
        invalid_hash_repository_report = run_developer_task_repository_preflight(
            invalid_hash_manifest,
            project_root=repo,
        )
        report = run_developer_task_patch_integrity_preflight(
            invalid_hash_manifest,
            repository_report=invalid_hash_repository_report,
            task_root=task_root,
        )
        check("INVALID PATCH HASH FORMAT IS REJECTED", list(report.issue_codes), ["patch_hash_invalid"])

        patch_path.unlink()
        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=repository_report,
            task_root=task_root,
        )
        check("MISSING PATCH FILE IS REJECTED", list(report.issue_codes), ["patch_file_missing"])

        patch_path.mkdir()
        report = run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=repository_report,
            task_root=task_root,
        )
        check("PATCH DIRECTORY IS REJECTED", list(report.issue_codes), ["patch_file_not_regular"])
        patch_path.rmdir()

        patch_path.write_bytes(patch_bytes)
        with patch(
            "modules.developer.developer_task_patch_integrity._is_reparse_or_symlink",
            side_effect=[False, True],
        ):
            report = run_developer_task_patch_integrity_preflight(
                manifest,
                repository_report=repository_report,
                task_root=task_root,
            )

        check("PATCH REPARSE POINT IS REJECTED", list(report.issue_codes), ["patch_file_reparse_point"])

        task_metadata = os.lstat(task_root)
        with patch(
            "modules.developer.developer_task_patch_integrity._read_path_metadata",
            side_effect=[task_metadata, PermissionError("fake patch metadata failure")],
        ):
            report = run_developer_task_patch_integrity_preflight(
                manifest,
                repository_report=repository_report,
                task_root=task_root,
            )

        check(
            "PATCH METADATA FAILURE IS STRUCTURED",
            list(report.issue_codes),
            ["patch_file_metadata_failed"],
        )

        empty_manifest = _manifest(head, b"")
        empty_repository_report = run_developer_task_repository_preflight(empty_manifest, project_root=repo)
        patch_path.write_bytes(b"")
        report = run_developer_task_patch_integrity_preflight(
            empty_manifest,
            repository_report=empty_repository_report,
            task_root=task_root,
        )
        check("EMPTY PATCH IS REJECTED", list(report.issue_codes), ["patch_file_empty"])

        large_bytes = b"12345"
        large_manifest = _manifest(head, large_bytes)
        large_repository_report = run_developer_task_repository_preflight(large_manifest, project_root=repo)
        patch_path.write_bytes(large_bytes)
        with patch("modules.developer.developer_task_patch_integrity._MAX_PATCH_BYTES", 4):
            report = run_developer_task_patch_integrity_preflight(
                large_manifest,
                repository_report=large_repository_report,
                task_root=task_root,
            )

        check(
            "OVERSIZED PATCH IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "size": report.patch_size_bytes,
            },
            {
                "issue_codes": ["patch_file_too_large"],
                "size": len(large_bytes),
            },
        )

        patch_path.write_bytes(patch_bytes)
        wrong_hash_manifest = _manifest(head, patch_bytes, patch_sha256="0" * 64)
        wrong_hash_repository_report = run_developer_task_repository_preflight(
            wrong_hash_manifest,
            project_root=repo,
        )
        report = run_developer_task_patch_integrity_preflight(
            wrong_hash_manifest,
            repository_report=wrong_hash_repository_report,
            task_root=task_root,
        )
        check(
            "PATCH HASH MISMATCH IS REJECTED WITHOUT SNAPSHOT",
            {
                "issue_codes": list(report.issue_codes),
                "actual_hash": report.actual_patch_sha256,
                "patch": report.patch,
            },
            {
                "issue_codes": ["patch_hash_mismatch"],
                "actual_hash": hashlib.sha256(patch_bytes).hexdigest(),
                "patch": None,
            },
        )

        exact_bytes = b"\xff\r\nraw-bytes\x80\n"
        exact_manifest = _manifest(head, exact_bytes)
        exact_repository_report = run_developer_task_repository_preflight(exact_manifest, project_root=repo)
        patch_path.write_bytes(exact_bytes)
        report = run_developer_task_patch_integrity_preflight(
            exact_manifest,
            repository_report=exact_repository_report,
            task_root=task_root,
        )
        check(
            "PATCH IS READ AS EXACT BINARY BYTES",
            {
                "ok": report.ok,
                "content": report.patch.content if report.patch is not None else None,
                "size": report.patch_size_bytes,
            },
            {
                "ok": True,
                "content": exact_bytes,
                "size": len(exact_bytes),
            },
        )

        patch_path.write_bytes(patch_bytes)
        with patch(
            "modules.developer.developer_task_patch_integrity.os.open",
            side_effect=PermissionError("fake open failure"),
        ):
            report = run_developer_task_patch_integrity_preflight(
                manifest,
                repository_report=repository_report,
                task_root=task_root,
            )

        check("PATCH OPEN FAILURE IS STRUCTURED", list(report.issue_codes), ["patch_file_open_failed"])

        with patch(
            "modules.developer.developer_task_patch_integrity.os.read",
            side_effect=OSError("fake read failure"),
        ):
            report = run_developer_task_patch_integrity_preflight(
                manifest,
                repository_report=repository_report,
                task_root=task_root,
            )

        check("PATCH READ FAILURE IS STRUCTURED", list(report.issue_codes), ["patch_file_read_failed"])

        with patch(
            "modules.developer.developer_task_patch_integrity._same_file_version",
            return_value=False,
        ):
            report = run_developer_task_patch_integrity_preflight(
                manifest,
                repository_report=repository_report,
                task_root=task_root,
            )

        check(
            "PATCH SWAP BEFORE OPEN IS REJECTED",
            list(report.issue_codes),
            ["patch_file_changed_during_read"],
        )

        with patch(
            "modules.developer.developer_task_patch_integrity._same_file_version",
            side_effect=[True, False],
        ):
            report = run_developer_task_patch_integrity_preflight(
                manifest,
                repository_report=repository_report,
                task_root=task_root,
            )

        check(
            "PATCH CHANGE DURING READ IS REJECTED",
            list(report.issue_codes),
            ["patch_file_changed_during_read"],
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
