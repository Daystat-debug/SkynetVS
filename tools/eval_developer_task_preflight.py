from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.developer.developer_task_contract import (
    DeveloperTaskCheck,
    DeveloperTaskManifest,
)
from modules.developer.developer_task_preflight import (
    _dirty_categories,
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


def _init_repo(root: Path, *, commit: bool = True) -> str:
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

    if not commit:
        return ""

    (root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-m", "baseline")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _manifest(base_commit: str) -> DeveloperTaskManifest:
    return DeveloperTaskManifest(
        schema_version=1,
        task_kind="patch",
        task_id="developer-preflight-eval",
        title="Evaluate developer task preflight",
        project="SkynetVS",
        origin="manual",
        source_ref="eval:developer-task-preflight",
        source_sha256="a" * 64,
        base_commit=base_commit,
        patch_file="changes.patch",
        patch_sha256="b" * 64,
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

    with tempfile.TemporaryDirectory(prefix="skynet_preflight_eval_") as temp_dir:
        temp_root = Path(temp_dir)
        repo = temp_root / "repo with spaces"
        head = _init_repo(repo)
        index_path = _index_path(repo)
        index_hash_before = _sha256(index_path)
        tracked_hash_before = _sha256(repo / "tracked.txt")
        report = run_developer_task_repository_preflight(_manifest(head), project_root=repo)
        index_hash_after = _sha256(index_path)
        tracked_hash_after = _sha256(repo / "tracked.txt")

        check(
            "CLEAN REPOSITORY PASSES WITHOUT MUTATION",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "head_matches": report.head_commit == head,
                "base_matches": report.resolved_base_commit == head,
                "repository_root_matches": Path(report.repository_root) == repo.resolve(),
                "fingerprint_length": len(report.manifest_fingerprint),
                "dirty_categories": list(report.dirty_categories),
                "index_unchanged": index_hash_before == index_hash_after,
                "tracked_file_unchanged": tracked_hash_before == tracked_hash_after,
                "index_lock_absent": not Path(str(index_path) + ".lock").exists(),
                "dict_issue_count": len(report.to_dict()["issues"]),
            },
            {
                "ok": True,
                "issue_codes": [],
                "head_matches": True,
                "base_matches": True,
                "repository_root_matches": True,
                "fingerprint_length": 64,
                "dirty_categories": [],
                "index_unchanged": True,
                "tracked_file_unchanged": True,
                "index_lock_absent": True,
                "dict_issue_count": 0,
            },
        )

        frozen = False

        try:
            report.head_commit = "changed"
        except FrozenInstanceError:
            frozen = True

        check("REPORT IS IMMUTABLE", frozen, True)

        raw_manifest_rejected = False

        try:
            run_developer_task_repository_preflight({}, project_root=repo)  # type: ignore[arg-type]
        except TypeError:
            raw_manifest_rejected = True

        check("RAW MANIFEST IS REJECTED", raw_manifest_rejected, True)

        string_root_rejected = False

        try:
            run_developer_task_repository_preflight(_manifest(head), project_root=str(repo))  # type: ignore[arg-type]
        except TypeError:
            string_root_rejected = True

        check("STRING PROJECT ROOT IS REJECTED", string_root_rejected, True)

        subdir = repo / "nested"
        subdir.mkdir()
        report = run_developer_task_repository_preflight(_manifest(head), project_root=subdir)
        check("SUBDIRECTORY ROOT IS REJECTED", list(report.issue_codes), ["repository_root_mismatch"])

        missing = temp_root / "missing"
        report = run_developer_task_repository_preflight(_manifest(head), project_root=missing)
        check("MISSING ROOT IS REJECTED", list(report.issue_codes), ["project_root_missing"])

        file_root = temp_root / "not-dir.txt"
        file_root.write_text("x", encoding="utf-8")
        report = run_developer_task_repository_preflight(_manifest(head), project_root=file_root)
        check("FILE ROOT IS REJECTED", list(report.issue_codes), ["project_root_not_directory"])

        not_repo = temp_root / "not-repo"
        not_repo.mkdir()
        report = run_developer_task_repository_preflight(_manifest(head), project_root=not_repo)
        check("NON REPOSITORY IS REJECTED", list(report.issue_codes), ["not_git_repository"])

        bare = temp_root / "bare.git"
        bare.mkdir()
        _git(bare, "init", "--bare")
        report = run_developer_task_repository_preflight(_manifest(head), project_root=bare)
        check("BARE REPOSITORY IS REJECTED", list(report.issue_codes), ["bare_repository"])

        old_head = head
        (repo / "tracked.txt").write_text("second\n", encoding="utf-8")
        _git(repo, "add", "tracked.txt")
        _git(repo, "commit", "-m", "second")
        current_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        report = run_developer_task_repository_preflight(_manifest(old_head), project_root=repo)

        check(
            "BASE COMMIT MISMATCH IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "head": report.head_commit,
                "base": report.resolved_base_commit,
            },
            {
                "issue_codes": ["base_commit_mismatch"],
                "head": current_head,
                "base": old_head,
            },
        )

        report = run_developer_task_repository_preflight(_manifest("deadbee"), project_root=repo)
        check("UNKNOWN BASE COMMIT IS REJECTED", list(report.issue_codes), ["base_commit_unresolved"])

        (repo / "staged.txt").write_text("staged\n", encoding="utf-8")
        _git(repo, "add", "staged.txt")
        report = run_developer_task_repository_preflight(_manifest(current_head), project_root=repo)

        check(
            "STAGED CHANGE IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "dirty_categories": list(report.dirty_categories),
            },
            {
                "issue_codes": ["dirty_worktree"],
                "dirty_categories": ["staged"],
            },
        )
        _git(repo, "reset", "--hard", "HEAD")

        (repo / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
        report = run_developer_task_repository_preflight(_manifest(current_head), project_root=repo)

        check(
            "UNSTAGED CHANGE IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "dirty_categories": list(report.dirty_categories),
            },
            {
                "issue_codes": ["dirty_worktree"],
                "dirty_categories": ["unstaged"],
            },
        )
        _git(repo, "reset", "--hard", "HEAD")

        (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        report = run_developer_task_repository_preflight(_manifest(current_head), project_root=repo)

        check(
            "UNTRACKED FILE IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "dirty_categories": list(report.dirty_categories),
            },
            {
                "issue_codes": ["dirty_worktree"],
                "dirty_categories": ["untracked"],
            },
        )
        (repo / "untracked.txt").unlink()

        _git(repo, "checkout", "-b", "conflict-side")
        (repo / "tracked.txt").write_text("side\n", encoding="utf-8")
        _git(repo, "add", "tracked.txt")
        _git(repo, "commit", "-m", "side change")
        _git(repo, "checkout", "main")
        (repo / "tracked.txt").write_text("main\n", encoding="utf-8")
        _git(repo, "add", "tracked.txt")
        _git(repo, "commit", "-m", "main change")
        current_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        merge = _git(repo, "merge", "conflict-side", check=False)

        if merge.returncode == 0:
            raise RuntimeError("Expected merge conflict was not created")

        report = run_developer_task_repository_preflight(_manifest(current_head), project_root=repo)

        check(
            "MERGE CONFLICT IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "dirty_categories": list(report.dirty_categories),
            },
            {
                "issue_codes": ["dirty_worktree"],
                "dirty_categories": ["conflict"],
            },
        )
        _git(repo, "merge", "--abort")

        unborn = temp_root / "unborn"
        _init_repo(unborn, commit=False)
        report = run_developer_task_repository_preflight(_manifest("deadbee"), project_root=unborn)

        check(
            "UNBORN HEAD IS REJECTED",
            list(report.issue_codes),
            ["head_commit_unresolved", "base_commit_unresolved"],
        )

        poison_repo = temp_root / "poison-repo"
        poison_head = _init_repo(poison_repo)
        trace_path = temp_root / "git-trace.json"

        with patch.dict(
            os.environ,
            {
                "GIT_DIR": str(poison_repo / ".git"),
                "GIT_WORK_TREE": str(poison_repo),
                "GIT_INDEX_FILE": str(_index_path(poison_repo)),
                "GIT_TRACE2_EVENT": str(trace_path),
            },
            clear=False,
        ):
            report = run_developer_task_repository_preflight(_manifest(current_head), project_root=repo)

        check(
            "INHERITED GIT REDIRECTION IS IGNORED",
            {
                "ok": report.ok,
                "head": report.head_commit,
                "target_head": current_head,
                "poison_head_used": report.head_commit == poison_head,
                "trace_file_created": trace_path.exists(),
            },
            {
                "ok": True,
                "head": current_head,
                "target_head": current_head,
                "poison_head_used": False,
                "trace_file_created": False,
            },
        )

        with patch(
            "modules.developer.developer_task_preflight.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=10),
        ):
            report = run_developer_task_repository_preflight(_manifest(current_head), project_root=repo)

        check("GIT TIMEOUT IS STRUCTURED", list(report.issue_codes), ["git_command_timeout"])

        with patch(
            "modules.developer.developer_task_preflight.subprocess.run",
            side_effect=FileNotFoundError("git missing"),
        ):
            report = run_developer_task_repository_preflight(_manifest(current_head), project_root=repo)

        check("MISSING GIT IS STRUCTURED", list(report.issue_codes), ["git_unavailable"])

        with patch(
            "modules.developer.developer_task_preflight.subprocess.run",
            side_effect=OSError("fake launch failure"),
        ):
            report = run_developer_task_repository_preflight(_manifest(current_head), project_root=repo)

        check("GIT LAUNCH FAILURE IS STRUCTURED", list(report.issue_codes), ["git_command_failed"])

    check(
        "PORCELAIN PARSER CLASSIFIES ALL DIRTY STATES",
        list(_dirty_categories(
            "1 M. N... 100644 100644 100644 aaaaaaa bbbbbbb staged.txt\x00"
            "1 .M N... 100644 100644 100644 aaaaaaa bbbbbbb unstaged.txt\x00"
            "1 .. S.MU 160000 160000 160000 aaaaaaa bbbbbbb submodule\x00"
            "u UU N... 100644 100644 100644 100644 aaaaaaa bbbbbbb ccccccc conflict.txt\x00"
            "? untracked.txt\x00"
        )),
        ["conflict", "staged", "unstaged", "untracked", "submodule"],
    )

    check(
        "PORCELAIN RENAME SOURCE FIELD IS SKIPPED",
        list(_dirty_categories(
            "2 R. N... 100644 100644 100644 aaaaaaa bbbbbbb R100 new.txt\x00"
            "old.txt\x00"
            "? untracked.txt\x00"
        )),
        ["staged", "untracked"],
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
