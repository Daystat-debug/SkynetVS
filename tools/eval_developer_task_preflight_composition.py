from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import modules.developer.developer_task_preflight_composition as composition

from modules.developer.developer_task_contract import (
    DeveloperTaskCheck,
    DeveloperTaskManifest,
)
from modules.developer.developer_task_preflight_composition import (
    run_developer_task_preflight,
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
    (root / "other.txt").write_text("other baseline\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _patch_for_change(repo: Path, path: str, content: str) -> bytes:
    (repo / path).write_text(content, encoding="utf-8")
    payload = _git_bytes(
        repo,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
        "HEAD",
        "--",
        path,
    ).stdout
    _git(repo, "reset", "--hard", "HEAD")
    _git(repo, "clean", "-fd")
    return payload


def _manifest(
    base_commit: str,
    patch_bytes: bytes,
    *,
    allowed_files: tuple[str, ...] = ("tracked.txt",),
    patch_sha256: str | None = None,
) -> DeveloperTaskManifest:
    return DeveloperTaskManifest(
        schema_version=1,
        task_kind="patch",
        task_id="developer-preflight-composition-eval",
        title="Evaluate complete developer task preflight composition",
        project="SkynetVS",
        origin="manual",
        source_ref="eval:developer-task-preflight-composition",
        source_sha256="a" * 64,
        base_commit=base_commit,
        patch_file="changes.patch",
        patch_sha256=patch_sha256 or hashlib.sha256(patch_bytes).hexdigest(),
        allowed_files=allowed_files,
        checks=(
            DeveloperTaskCheck(type="git_diff_check"),
            DeveloperTaskCheck(type="pipeline", flow="check"),
        ),
        install_policy="manual_confirmation",
    )


def _prepare(
    root: Path,
    *,
    changed_path: str = "tracked.txt",
    allowed_files: tuple[str, ...] = ("tracked.txt",),
    patch_bytes: bytes | None = None,
    patch_sha256: str | None = None,
) -> tuple[Path, Path, DeveloperTaskManifest, bytes]:
    repo = root / "repo"
    task_root = root / "task"
    base_commit = _init_repo(repo)
    task_root.mkdir()

    if patch_bytes is None:
        patch_bytes = _patch_for_change(repo, changed_path, "changed by preflight\n")

    manifest = _manifest(
        base_commit,
        patch_bytes,
        allowed_files=allowed_files,
        patch_sha256=patch_sha256,
    )
    (task_root / manifest.patch_file).write_bytes(patch_bytes)
    return repo, task_root, manifest, patch_bytes


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


def _serialized_contains_bytes(value: Any) -> bool:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return True

    if isinstance(value, dict):
        return any(_serialized_contains_bytes(item) for item in value.values())

    if isinstance(value, (list, tuple)):
        return any(_serialized_contains_bytes(item) for item in value)

    return False


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

    with tempfile.TemporaryDirectory() as temp_dir:
        repo, task_root, manifest, patch_bytes = _prepare(Path(temp_dir))
        index_path = _index_path(repo)
        index_before = _sha256(index_path)
        tracked_before = (repo / "tracked.txt").read_bytes()
        objects_before = _object_snapshot(repo)
        status_before = _git(repo, "status", "--porcelain=v2", "-z").stdout
        report = run_developer_task_preflight(
            manifest,
            project_root=repo,
            task_root=task_root,
        )
        check(
            "COMPLETE PREFLIGHT PASSES WITH IMMUTABLE EVIDENCE",
            {
                "ok": report.ok,
                "failed_stage": report.failed_stage,
                "completed_stages": list(report.completed_stages),
                "issue_codes": list(report.issue_codes),
                "repository_root": report.repository_root == str(repo.resolve()),
                "base_commit": report.base_commit == manifest.base_commit,
                "changed_files": list(report.changed_files),
                "patch_matches": report.patch is not None and report.patch.content == patch_bytes,
                "nested_reports": [
                    report.repository_report is not None and report.repository_report.ok,
                    report.patch_integrity_report is not None and report.patch_integrity_report.ok,
                    report.patch_index_report is not None and report.patch_index_report.ok,
                    report.patch_scope_report is not None and report.patch_scope_report.ok,
                ],
                "index_unchanged": _sha256(index_path) == index_before,
                "tracked_unchanged": (repo / "tracked.txt").read_bytes() == tracked_before,
                "objects_unchanged": _object_snapshot(repo) == objects_before,
                "status_unchanged": _git(repo, "status", "--porcelain=v2", "-z").stdout == status_before,
                "index_lock_absent": not Path(str(index_path) + ".lock").exists(),
            },
            {
                "ok": True,
                "failed_stage": "",
                "completed_stages": [
                    "manifest",
                    "repository",
                    "patch_integrity",
                    "patch_index",
                    "patch_scope",
                    "composition",
                ],
                "issue_codes": [],
                "repository_root": True,
                "base_commit": True,
                "changed_files": ["tracked.txt"],
                "patch_matches": True,
                "nested_reports": [True, True, True, True],
                "index_unchanged": True,
                "tracked_unchanged": True,
                "objects_unchanged": True,
                "status_unchanged": True,
                "index_lock_absent": True,
            },
        )

        immutable = False

        try:
            report.failed_stage = "forged"  # type: ignore[misc]
        except FrozenInstanceError:
            immutable = True

        check("COMPOSITE REPORT IS IMMUTABLE", immutable, True)

        serialized = report.to_dict()
        report_patch = report.patch
        check(
            "SERIALIZATION EXCLUDES PATCH BYTES",
            {
                "contains_bytes": _serialized_contains_bytes(serialized),
                "json_serializable": bool(json.dumps(serialized, ensure_ascii=False)),
                "repr_contains_content": repr(patch_bytes) in repr(report),
                "patch_metadata_present": (
                    report_patch is not None
                    and serialized["patch"] == report_patch.to_dict()
                ),
            },
            {
                "contains_bytes": False,
                "json_serializable": True,
                "repr_contains_content": False,
                "patch_metadata_present": True,
            },
        )

        repeated = run_developer_task_preflight(
            manifest,
            project_root=repo,
            task_root=task_root,
        )
        check(
            "REPEATED COMPLETE PREFLIGHT IS DETERMINISTIC",
            repeated.to_dict(),
            report.to_dict(),
        )

        raw_manifest_rejected = False

        try:
            run_developer_task_preflight(  # type: ignore[arg-type]
                manifest.to_dict(),
                project_root=repo,
                task_root=task_root,
            )
        except TypeError:
            raw_manifest_rejected = True

        check("RAW MANIFEST IS REJECTED", raw_manifest_rejected, True)

        string_project_root_rejected = False

        try:
            run_developer_task_preflight(  # type: ignore[arg-type]
                manifest,
                project_root=str(repo),
                task_root=task_root,
            )
        except TypeError:
            string_project_root_rejected = True

        check("STRING PROJECT ROOT IS REJECTED", string_project_root_rejected, True)

        string_task_root_rejected = False

        try:
            run_developer_task_preflight(  # type: ignore[arg-type]
                manifest,
                project_root=repo,
                task_root=str(task_root),
            )
        except TypeError:
            string_task_root_rejected = True

        check("STRING TASK ROOT IS REJECTED", string_task_root_rejected, True)

        invalid_manifest = replace(
            manifest,
            allowed_files=("tracked.txt", "TRACKED.TXT"),
        )

        with patch.object(
            composition,
            "run_developer_task_repository_preflight",
        ) as repository_mock:
            invalid_report = run_developer_task_preflight(
                invalid_manifest,
                project_root=repo,
                task_root=task_root,
            )

        check(
            "INVALID MANIFEST BLOCKS ALL RUNTIME GATES",
            {
                "failed_stage": invalid_report.failed_stage,
                "completed_stages": list(invalid_report.completed_stages),
                "issue_codes": list(invalid_report.issue_codes),
                "repository_calls": repository_mock.call_count,
            },
            {
                "failed_stage": "manifest",
                "completed_stages": [],
                "issue_codes": ["manifest_invalid"],
                "repository_calls": 0,
            },
        )

        with patch.object(
            composition,
            "validate_developer_task_manifest",
            side_effect=RuntimeError("fake validator failure"),
        ), patch.object(
            composition,
            "run_developer_task_repository_preflight",
        ) as repository_mock:
            validation_failure = run_developer_task_preflight(
                manifest,
                project_root=repo,
                task_root=task_root,
            )

        check(
            "MANIFEST VALIDATOR FAILURE IS STRUCTURED AND SHORT-CIRCUITED",
            {
                "failed_stage": validation_failure.failed_stage,
                "issue_codes": list(validation_failure.issue_codes),
                "repository_calls": repository_mock.call_count,
            },
            {
                "failed_stage": "manifest",
                "issue_codes": ["manifest_validation_failed"],
                "repository_calls": 0,
            },
        )

        originals: dict[str, Callable[..., Any]] = {
            "repository": composition.run_developer_task_repository_preflight,
            "patch_integrity": composition.run_developer_task_patch_integrity_preflight,
            "patch_index": composition.run_developer_task_patch_index_preflight,
            "patch_scope": composition.run_developer_task_patch_scope_preflight,
        }
        order: list[str] = []

        def _record(name: str) -> Callable[..., Any]:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                order.append(name)
                return originals[name](*args, **kwargs)

            return wrapper

        with patch.object(composition, "run_developer_task_repository_preflight", _record("repository")), patch.object(
            composition,
            "run_developer_task_patch_integrity_preflight",
            _record("patch_integrity"),
        ), patch.object(
            composition,
            "run_developer_task_patch_index_preflight",
            _record("patch_index"),
        ), patch.object(
            composition,
            "run_developer_task_patch_scope_preflight",
            _record("patch_scope"),
        ):
            ordered_report = run_developer_task_preflight(
                manifest,
                project_root=repo,
                task_root=task_root,
            )

        check(
            "GATES RUN IN FIXED FAIL-CLOSED ORDER",
            {"order": order, "ok": ordered_report.ok},
            {
                "order": ["repository", "patch_integrity", "patch_index", "patch_scope"],
                "ok": True,
            },
        )

        exception_results: list[dict[str, Any]] = []

        for stage, target in (
            ("repository", "run_developer_task_repository_preflight"),
            ("patch_integrity", "run_developer_task_patch_integrity_preflight"),
            ("patch_index", "run_developer_task_patch_index_preflight"),
            ("patch_scope", "run_developer_task_patch_scope_preflight"),
        ):
            with patch.object(
                composition,
                target,
                side_effect=RuntimeError(f"fake {stage} failure"),
            ):
                failed = run_developer_task_preflight(
                    manifest,
                    project_root=repo,
                    task_root=task_root,
                )

            exception_results.append({
                "stage": stage,
                "failed_stage": failed.failed_stage,
                "issue_codes": list(failed.issue_codes),
                "ok": failed.ok,
            })

        check(
            "UNEXPECTED STAGE FAILURES ARE STRUCTURED",
            exception_results,
            [
                {
                    "stage": stage,
                    "failed_stage": stage,
                    "issue_codes": [f"{stage}_execution_failed"],
                    "ok": False,
                }
                for stage in ("repository", "patch_integrity", "patch_index", "patch_scope")
            ],
        )

        invalid_type_results: list[dict[str, Any]] = []

        for stage, target in (
            ("repository", "run_developer_task_repository_preflight"),
            ("patch_integrity", "run_developer_task_patch_integrity_preflight"),
            ("patch_index", "run_developer_task_patch_index_preflight"),
            ("patch_scope", "run_developer_task_patch_scope_preflight"),
        ):
            with patch.object(composition, target, return_value=object()):
                failed = run_developer_task_preflight(
                    manifest,
                    project_root=repo,
                    task_root=task_root,
                )

            invalid_type_results.append({
                "stage": stage,
                "failed_stage": failed.failed_stage,
                "issue_codes": list(failed.issue_codes),
                "ok": failed.ok,
            })

        check(
            "INVALID STAGE REPORT TYPES FAIL CLOSED",
            invalid_type_results,
            [
                {
                    "stage": stage,
                    "failed_stage": stage,
                    "issue_codes": [f"{stage}_report_invalid"],
                    "ok": False,
                }
                for stage in ("repository", "patch_integrity", "patch_index", "patch_scope")
            ],
        )

        original_scope = composition.run_developer_task_patch_scope_preflight

        def inconsistent_scope(*args: Any, **kwargs: Any) -> Any:
            value = original_scope(*args, **kwargs)
            return replace(value, changed_files=("forged.txt",))

        with patch.object(
            composition,
            "run_developer_task_patch_scope_preflight",
            inconsistent_scope,
        ):
            inconsistent = run_developer_task_preflight(
                manifest,
                project_root=repo,
                task_root=task_root,
            )

        check(
            "FINAL EVIDENCE CHAIN MISMATCH IS REJECTED",
            {
                "failed_stage": inconsistent.failed_stage,
                "completed_stages": list(inconsistent.completed_stages),
                "issue_codes": list(inconsistent.issue_codes),
                "ok": inconsistent.ok,
            },
            {
                "failed_stage": "composition",
                "completed_stages": [
                    "manifest",
                    "repository",
                    "patch_integrity",
                    "patch_index",
                    "patch_scope",
                ],
                "issue_codes": ["preflight_chain_invalid"],
                "ok": False,
            },
        )

        assert report.patch_scope_report is not None
        forged_report = replace(
            report,
            patch_scope_report=replace(
                report.patch_scope_report,
                changed_files=("forged.txt",),
            ),
        )
        check("FORGED COMPOSITE REPORT DOES NOT CLAIM SUCCESS", forged_report.ok, False)

    with tempfile.TemporaryDirectory() as temp_dir:
        repo, task_root, manifest, _ = _prepare(Path(temp_dir))
        (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")

        with patch.object(
            composition,
            "run_developer_task_patch_integrity_preflight",
        ) as integrity_mock:
            failed = run_developer_task_preflight(
                manifest,
                project_root=repo,
                task_root=task_root,
            )

        check(
            "REPOSITORY FAILURE SHORT-CIRCUITS LATER GATES",
            {
                "failed_stage": failed.failed_stage,
                "completed_stages": list(failed.completed_stages),
                "issue_codes": list(failed.issue_codes),
                "integrity_calls": integrity_mock.call_count,
                "integrity_report": failed.patch_integrity_report,
            },
            {
                "failed_stage": "repository",
                "completed_stages": ["manifest"],
                "issue_codes": ["dirty_worktree"],
                "integrity_calls": 0,
                "integrity_report": None,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        repo, task_root, manifest, _ = _prepare(
            Path(temp_dir),
            patch_sha256="f" * 64,
        )

        with patch.object(
            composition,
            "run_developer_task_patch_index_preflight",
        ) as index_mock:
            failed = run_developer_task_preflight(
                manifest,
                project_root=repo,
                task_root=task_root,
            )

        check(
            "PATCH INTEGRITY FAILURE SHORT-CIRCUITS INDEX AND SCOPE",
            {
                "failed_stage": failed.failed_stage,
                "completed_stages": list(failed.completed_stages),
                "issue_codes": list(failed.issue_codes),
                "index_calls": index_mock.call_count,
                "patch": failed.patch,
            },
            {
                "failed_stage": "patch_integrity",
                "completed_stages": ["manifest", "repository"],
                "issue_codes": ["patch_hash_mismatch"],
                "index_calls": 0,
                "patch": None,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        malformed = b"this is not a git patch\n"
        repo, task_root, manifest, _ = _prepare(
            Path(temp_dir),
            patch_bytes=malformed,
        )

        with patch.object(
            composition,
            "run_developer_task_patch_scope_preflight",
        ) as scope_mock:
            failed = run_developer_task_preflight(
                manifest,
                project_root=repo,
                task_root=task_root,
            )

        check(
            "PATCH INDEX FAILURE SHORT-CIRCUITS SCOPE",
            {
                "failed_stage": failed.failed_stage,
                "completed_stages": list(failed.completed_stages),
                "issue_codes": list(failed.issue_codes),
                "scope_calls": scope_mock.call_count,
            },
            {
                "failed_stage": "patch_index",
                "completed_stages": ["manifest", "repository", "patch_integrity"],
                "issue_codes": ["patch_no_changes"],
                "scope_calls": 0,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        repo, task_root, manifest, _ = _prepare(
            Path(temp_dir),
            changed_path="other.txt",
            allowed_files=("tracked.txt",),
        )
        failed = run_developer_task_preflight(
            manifest,
            project_root=repo,
            task_root=task_root,
        )
        check(
            "PATCH SCOPE FAILURE IS TERMINAL",
            {
                "failed_stage": failed.failed_stage,
                "completed_stages": list(failed.completed_stages),
                "issue_codes": list(failed.issue_codes),
                "changed_files": list(failed.changed_files),
                "patch_exposed": failed.patch is not None,
            },
            {
                "failed_stage": "patch_scope",
                "completed_stages": [
                    "manifest",
                    "repository",
                    "patch_integrity",
                    "patch_index",
                ],
                "issue_codes": ["patch_scope_violation"],
                "changed_files": [],
                "patch_exposed": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        repo, _, manifest, _ = _prepare(root)
        failed = run_developer_task_preflight(
            manifest,
            project_root=repo,
            task_root=repo,
        )
        check(
            "OVERLAPPING TASK ROOT IS PROPAGATED FAIL CLOSED",
            {
                "failed_stage": failed.failed_stage,
                "issue_codes": list(failed.issue_codes),
                "completed_stages": list(failed.completed_stages),
            },
            {
                "failed_stage": "patch_integrity",
                "issue_codes": ["task_root_overlaps_project"],
                "completed_stages": ["manifest", "repository"],
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
