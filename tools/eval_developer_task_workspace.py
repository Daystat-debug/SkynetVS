from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_workspace as workspace
import modules.developer.developer_task_workspace_git as workspace_git

from modules.developer.developer_task_contract import (
    DeveloperTaskCheck,
    DeveloperTaskManifest,
)
from modules.developer.developer_task_preflight_composition import (
    DeveloperTaskPreflightReport,
    run_developer_task_preflight,
)
from modules.developer.developer_task_workspace import (
    create_developer_task_workspace,
)


def _git(
    root: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def _git_bytes(
    root: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _init_repo(root: Path) -> str:
    root.mkdir(parents=True)
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "eval@example.com")
    _git(root, "config", "user.name", "Workspace Eval")
    (root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "--quiet", "-m", "initial")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _patch_for_change(repo: Path, path: str = "tracked.txt") -> bytes:
    (repo / path).write_text("changed in task\n", encoding="utf-8")
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


def _manifest(base_commit: str, patch_bytes: bytes, *, task_id: str = "developer-workspace-eval") -> DeveloperTaskManifest:
    return DeveloperTaskManifest(
        schema_version=1,
        task_kind="patch",
        task_id=task_id,
        title="Evaluate independent developer task workspace",
        project="SkynetVS",
        origin="manual",
        source_ref="eval:developer-task-workspace",
        source_sha256="a" * 64,
        base_commit=base_commit,
        patch_file="changes.patch",
        patch_sha256=hashlib.sha256(patch_bytes).hexdigest(),
        allowed_files=("tracked.txt",),
        checks=(
            DeveloperTaskCheck(type="git_diff_check"),
            DeveloperTaskCheck(type="pipeline", flow="check"),
        ),
        install_policy="manual_confirmation",
    )


def _prepare(root: Path) -> tuple[Path, Path, Path, DeveloperTaskManifest, DeveloperTaskPreflightReport]:
    root.mkdir(parents=True, exist_ok=True)
    repo = root / "source"
    task_root = root / "task"
    workspace_parent = root / "workspaces"
    base_commit = _init_repo(repo)
    patch_bytes = _patch_for_change(repo)
    task_root.mkdir()
    workspace_parent.mkdir()
    manifest = _manifest(base_commit, patch_bytes)
    (task_root / manifest.patch_file).write_bytes(patch_bytes)
    preflight = run_developer_task_preflight(
        manifest,
        project_root=repo,
        task_root=task_root,
    )
    assert preflight.ok
    return repo, task_root, workspace_parent, manifest, preflight


def _index_path(root: Path) -> Path:
    value = _git(root, "rev-parse", "--git-path", "index").stdout.strip()
    path = Path(value)
    return path if path.is_absolute() else root / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object_snapshot(root: Path) -> dict[str, tuple[int, str]]:
    git_dir_value = _git(root, "rev-parse", "--absolute-git-dir").stdout.strip()
    objects = Path(git_dir_value) / "objects"
    result: dict[str, tuple[int, str]] = {}

    for path in sorted(objects.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(objects).as_posix()
        result[relative] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())

    return result


def _marker_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
        repo, task_root, parent, manifest, preflight = _prepare(Path(temp_dir))
        source_index = _index_path(repo)
        index_before = _sha256(source_index)
        tracked_before = (repo / "tracked.txt").read_bytes()
        objects_before = _object_snapshot(repo)
        refs_before = _git(repo, "for-each-ref", "--format=%(objectname) %(refname)").stdout
        status_before = _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
        commands: list[tuple[str, ...]] = []
        command_environments: list[dict[str, str]] = []
        original_run = subprocess.run

        def recording_run(command: Any, *args: Any, **kwargs: Any) -> Any:
            commands.append(tuple(str(item) for item in command))
            command_environments.append(dict(kwargs.get("env") or {}))
            return original_run(command, *args, **kwargs)

        with patch.object(workspace_git.subprocess, "run", side_effect=recording_run):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        repository_root = Path(report.repository_root)
        marker_path = Path(report.marker_path)
        clone_indexes = [index for index, item in enumerate(commands) if "clone" in item]
        clone_commands = [commands[index] for index in clone_indexes]
        clone_environment = (
            command_environments[clone_indexes[0]]
            if clone_indexes
            else {}
        )
        control_root = Path(report.control_root)
        marker = _marker_payload(marker_path) if marker_path.exists() else {}
        repository_file_path = repository_root / "tracked.txt"
        repository_file = (
            repository_file_path.read_text(encoding="utf-8")
            if report.ok and repository_file_path.is_file()
            else None
        )
        check(
            "INDEPENDENT WORKSPACE PASSES WITHOUT SOURCE MUTATION",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "head_matches": report.head_commit == manifest.base_commit,
                "detached": report.detached_head,
                "shallow": report.shallow_repository,
                "clean": report.clean_worktree,
                "remotes": list(report.remote_names),
                "refs": list(report.ref_names),
                "alternates": list(report.alternate_object_directories),
                "separate_git_dir": report.git_dir == str(repository_root / ".git"),
                "repository_file": repository_file,
                "marker_matches": (
                    marker.get("workspace_id") == report.workspace_id
                    and marker.get("base_commit") == report.base_commit
                    and hashlib.sha256(marker_path.read_bytes()).hexdigest() == report.marker_sha256
                ),
                "clone_flags": bool(clone_commands) and all(
                    value in clone_commands[0]
                    for value in (
                        "--no-local",
                        "--no-hardlinks",
                        "--no-checkout",
                        "--no-tags",
                        "--single-branch",
                        "--depth=1",
                    )
                ),
                "no_worktree_command": not any("worktree" in item for item in commands),
                "git_policy_hardened": bool(clone_commands) and all(
                    value in clone_commands[0]
                    for value in (
                        "core.autocrlf=false",
                        "core.eol=lf",
                        "core.safecrlf=true",
                        "core.protectNTFS=true",
                        "core.protectHFS=true",
                    )
                ),
                "environment_isolated": (
                    clone_environment.get("GIT_CONFIG_NOSYSTEM") == "1"
                    and clone_environment.get("GIT_ATTR_NOSYSTEM") == "1"
                    and clone_environment.get("GIT_TERMINAL_PROMPT") == "0"
                    and clone_environment.get("GIT_ALLOW_PROTOCOL") == "file"
                    and Path(clone_environment.get("HOME", "")).is_relative_to(control_root)
                    and Path(clone_environment.get("USERPROFILE", "")).is_relative_to(control_root)
                    and Path(clone_environment.get("XDG_CONFIG_HOME", "")).is_relative_to(control_root)
                    and Path(clone_environment.get("GIT_CONFIG_GLOBAL", "")).is_relative_to(control_root)
                    and Path(clone_environment.get("GIT_TEMPLATE_DIR", "")).is_relative_to(control_root)
                    and "GIT_DIR" not in clone_environment
                    and "GIT_WORK_TREE" not in clone_environment
                    and "GIT_INDEX_FILE" not in clone_environment
                    and "GIT_OBJECT_DIRECTORY" not in clone_environment
                    and "GIT_ALTERNATE_OBJECT_DIRECTORIES" not in clone_environment
                    and "GIT_CONFIG_COUNT" not in clone_environment
                ),
                "source_index_unchanged": _sha256(source_index) == index_before,
                "source_tracked_unchanged": (repo / "tracked.txt").read_bytes() == tracked_before,
                "source_objects_unchanged": _object_snapshot(repo) == objects_before,
                "source_refs_unchanged": _git(repo, "for-each-ref", "--format=%(objectname) %(refname)").stdout == refs_before,
                "source_status_unchanged": _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout == status_before,
            },
            {
                "ok": True,
                "issue_codes": [],
                "head_matches": True,
                "detached": True,
                "shallow": True,
                "clean": True,
                "remotes": [],
                "refs": [],
                "alternates": [],
                "separate_git_dir": True,
                "repository_file": "baseline\n",
                "marker_matches": True,
                "clone_flags": True,
                "no_worktree_command": True,
                "git_policy_hardened": True,
                "environment_isolated": True,
                "source_index_unchanged": True,
                "source_tracked_unchanged": True,
                "source_objects_unchanged": True,
                "source_refs_unchanged": True,
                "source_status_unchanged": True,
            },
        )

        immutable = False

        try:
            report.workspace_id = "forged"  # type: ignore[misc]
        except FrozenInstanceError:
            immutable = True

        check("WORKSPACE REPORT IS IMMUTABLE", immutable, True)
        check(
            "WORKSPACE REPORT IS JSON SERIALIZABLE",
            bool(json.dumps(report.to_dict(), ensure_ascii=False)),
            True,
        )

        raw_manifest_rejected = False

        try:
            create_developer_task_workspace(  # type: ignore[arg-type]
                manifest.to_dict(),
                preflight_report=preflight,
                workspace_parent=parent,
            )
        except TypeError:
            raw_manifest_rejected = True

        check("RAW MANIFEST IS REJECTED", raw_manifest_rejected, True)

        raw_preflight_rejected = False

        try:
            create_developer_task_workspace(  # type: ignore[arg-type]
                manifest,
                preflight_report=preflight.to_dict(),
                workspace_parent=parent,
            )
        except TypeError:
            raw_preflight_rejected = True

        check("RAW PREFLIGHT REPORT IS REJECTED", raw_preflight_rejected, True)

        string_parent_rejected = False

        try:
            create_developer_task_workspace(  # type: ignore[arg-type]
                manifest,
                preflight_report=preflight,
                workspace_parent=str(parent),
            )
        except TypeError:
            string_parent_rejected = True

        check("STRING WORKSPACE PARENT IS REJECTED", string_parent_rejected, True)

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        home = root / "home"
        xdg = root / "xdg"
        home.mkdir()
        xdg.mkdir()
        (home / ".gitconfig").write_text(
            "[core]\n\tautocrlf = true\n",
            encoding="utf-8",
        )

        with patch.dict(
            os.environ,
            {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "XDG_CONFIG_HOME": str(xdg),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_ATTR_NOSYSTEM": "1",
            },
            clear=False,
        ):
            repo, _, parent, manifest, preflight = _prepare(root / "case")
            source_bytes = (repo / "tracked.txt").read_bytes()
            source_status = _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check(
            "SOURCE LINE ENDING POLICY DOES NOT CREATE FALSE STALE REPORT",
            {
                "preflight_ok": preflight.ok,
                "source_uses_crlf": b"\r\n" in source_bytes,
                "source_status_clean": source_status == b"",
                "workspace_ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "source_unchanged": report.source_repository_unchanged,
            },
            {
                "preflight_ok": True,
                "source_uses_crlf": True,
                "source_status_clean": True,
                "workspace_ok": True,
                "issue_codes": [],
                "source_unchanged": True,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        repo, task_root, parent, manifest, _ = _prepare(Path(temp_dir))
        bad_manifest = replace(manifest, patch_sha256="f" * 64)
        failed_preflight = run_developer_task_preflight(
            bad_manifest,
            project_root=repo,
            task_root=task_root,
        )
        report = create_developer_task_workspace(
            bad_manifest,
            preflight_report=failed_preflight,
            workspace_parent=parent,
        )
        check(
            "FAILED PREFLIGHT BLOCKS WORKSPACE CREATION",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_created": bool(tuple(parent.iterdir())),
            },
            {
                "issue_codes": ["preflight_report_failed"],
                "workspace_created": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        other_manifest = replace(manifest, title="Different valid title")
        report = create_developer_task_workspace(
            other_manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        check(
            "MANIFEST FINGERPRINT MISMATCH IS REJECTED",
            list(report.issue_codes),
            ["preflight_report_invalid"],
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        missing = parent / "missing"
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=missing,
        )
        check("MISSING WORKSPACE PARENT IS REJECTED", list(report.issue_codes), ["workspace_parent_missing"])

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        file_parent = parent / "file"
        file_parent.write_text("not a directory", encoding="utf-8")
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=file_parent,
        )
        check("FILE WORKSPACE PARENT IS REJECTED", list(report.issue_codes), ["workspace_parent_not_directory"])

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        real_metadata = workspace._directory_metadata

        def reparse_metadata(path: Path) -> Any:
            value = real_metadata(path)

            if path == parent:
                return SimpleNamespace(
                    st_mode=value.st_mode,
                    st_file_attributes=int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)),
                )

            return value

        with patch.object(workspace, "_directory_metadata", side_effect=reparse_metadata):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check("REPARSE WORKSPACE PARENT IS REJECTED", list(report.issue_codes), ["workspace_parent_reparse_point"])

    with tempfile.TemporaryDirectory() as temp_dir:
        repo, _, _, manifest, preflight = _prepare(Path(temp_dir))
        parent = repo / "workspace-parent"
        parent.mkdir()
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        check("WORKSPACE PARENT INSIDE SOURCE IS REJECTED", list(report.issue_codes), ["workspace_parent_overlaps_repository"])

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        repo, _, _, manifest, preflight = _prepare(root / "nested")
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=root,
        )
        check("WORKSPACE PARENT CONTAINING SOURCE IS REJECTED", list(report.issue_codes), ["workspace_parent_overlaps_repository"])

    with tempfile.TemporaryDirectory() as temp_dir:
        _, task_root, _, manifest, preflight = _prepare(Path(temp_dir))
        parent = task_root / "workspaces"
        parent.mkdir()
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        check("WORKSPACE PARENT INSIDE TASK ROOT IS REJECTED", list(report.issue_codes), ["workspace_parent_overlaps_task_root"])

    with tempfile.TemporaryDirectory() as temp_dir:
        repo, task_root, _, manifest, preflight = _prepare(Path(temp_dir))
        unrelated = Path(temp_dir) / "unrelated"
        unrelated.mkdir()
        _git(unrelated, "init", "--quiet")
        parent = unrelated / "workspaces"
        parent.mkdir()
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        check("WORKSPACE PARENT INSIDE ANOTHER GIT REPOSITORY IS REJECTED", list(report.issue_codes), ["workspace_parent_inside_git_repository"])
        assert repo.exists() and task_root.exists()

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, _, manifest, preflight = _prepare(Path(temp_dir) / "task-context")
        unrelated = Path(temp_dir) / "unrelated-admin"
        unrelated.mkdir()
        _git(unrelated, "init", "--quiet")
        parent = unrelated / ".git" / "workspace-parent"
        parent.mkdir()
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        check(
            "WORKSPACE PARENT INSIDE GIT ADMIN DIRECTORY IS REJECTED",
            list(report.issue_codes),
            ["workspace_parent_inside_git_repository"],
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, _, manifest, preflight = _prepare(Path(temp_dir) / "task-context")
        bare = Path(temp_dir) / "bare.git"
        _git(bare.parent, "init", "--bare", "--quiet", str(bare))
        parent = bare / "workspace-parent"
        parent.mkdir()
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        check(
            "WORKSPACE PARENT INSIDE BARE REPOSITORY IS REJECTED",
            list(report.issue_codes),
            ["workspace_parent_inside_git_repository"],
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        repo, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        (repo / "tracked.txt").write_text("dirty after preflight\n", encoding="utf-8")
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        check(
            "STALE SOURCE REPOSITORY IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_created": bool(tuple(parent.iterdir())),
            },
            {
                "issue_codes": ["source_repository_stale"],
                "workspace_created": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        main_repo = root / "main"
        linked_repo = root / "linked"
        task_root = root / "task"
        parent = root / "workspaces"
        base_commit = _init_repo(main_repo)
        _git(main_repo, "worktree", "add", "--quiet", "--detach", str(linked_repo), base_commit)
        patch_bytes = _patch_for_change(linked_repo)
        task_root.mkdir()
        parent.mkdir()
        manifest = _manifest(base_commit, patch_bytes, task_id="linked-worktree-eval")
        (task_root / manifest.patch_file).write_bytes(patch_bytes)
        preflight = run_developer_task_preflight(
            manifest,
            project_root=linked_repo,
            task_root=task_root,
        )
        assert preflight.ok
        report = create_developer_task_workspace(
            manifest,
            preflight_report=preflight,
            workspace_parent=parent,
        )
        check(
            "LINKED SOURCE WORKTREE IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": bool(report.workspace_root and Path(report.workspace_root).exists()),
            },
            {
                "issue_codes": ["source_repository_not_independent"],
                "workspace_present": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        fixed_token = "a" * 12
        expected_name = f"skynetvs-task-{manifest.task_id[:24]}-{preflight.manifest_fingerprint[:12]}-{fixed_token}"
        (parent / expected_name).mkdir()

        with patch.object(workspace.secrets, "token_hex", return_value=fixed_token):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check("GENERATED WORKSPACE PATH COLLISION IS REJECTED", list(report.issue_codes), ["workspace_path_exists"])

    regular_tree = b"100644 blob " + b"a" * 40 + b"\ttracked.txt\x00"
    check("REGULAR BASELINE TREE IS ACCEPTED", list(workspace_git.parse_baseline_tree(regular_tree)), ["tracked.txt"])

    parser_cases = (
        (
            "SYMLINK BASELINE ENTRY IS REJECTED",
            b"120000 blob " + b"a" * 40 + b"\tlink\x00",
            "workspace_baseline_symlink",
        ),
        (
            "GITLINK BASELINE ENTRY IS REJECTED",
            b"160000 commit " + b"a" * 40 + b"\tsubmodule\x00",
            "workspace_baseline_gitlink",
        ),
        (
            "UNSUPPORTED BASELINE MODE IS REJECTED",
            b"100600 blob " + b"a" * 40 + b"\tfile.txt\x00",
            "workspace_baseline_mode_unsupported",
        ),
        (
            "BASELINE CASE COLLISION IS REJECTED",
            b"100644 blob " + b"a" * 40 + b"\tCase.txt\x00"
            + b"100644 blob " + b"b" * 40 + b"\tcase.txt\x00",
            "workspace_baseline_case_collision",
        ),
        (
            "BASELINE DIRECTORY CASE COLLISION IS REJECTED",
            b"100644 blob " + b"a" * 40 + b"\tDir/one.txt\x00"
            + b"100644 blob " + b"b" * 40 + b"\tdir/two.txt\x00",
            "workspace_baseline_case_collision",
        ),
        (
            "BASELINE FILE DIRECTORY COLLISION IS REJECTED",
            b"100644 blob " + b"a" * 40 + b"\tFoo\x00"
            + b"100644 blob " + b"b" * 40 + b"\tfoo/bar.txt\x00",
            "workspace_baseline_case_collision",
        ),
    )

    for name, payload, expected_code in parser_cases:
        actual_code = ""

        try:
            workspace_git.parse_baseline_tree(payload)
        except workspace_git.DeveloperTaskWorkspaceGitError as exc:
            actual_code = exc.code

        check(name, actual_code, expected_code)

    unsafe_rejected = False

    try:
        workspace_git.parse_baseline_tree(
            b"100644 blob " + b"a" * 40 + b"\tCON.txt\x00"
        )
    except ValueError:
        unsafe_rejected = True

    check("WINDOWS UNSAFE BASELINE PATH IS REJECTED", unsafe_rejected, True)

    git_control_path_rejected = False

    try:
        workspace_git.parse_baseline_tree(
            b"100644 blob " + b"a" * 40 + b"\t.git/config\x00"
        )
    except ValueError:
        git_control_path_rejected = True

    check("GIT CONTROL BASELINE PATH IS REJECTED", git_control_path_rejected, True)

    malformed_rejected = False

    try:
        workspace_git.parse_baseline_tree(b"malformed\x00")
    except ValueError:
        malformed_rejected = True

    check("MALFORMED BASELINE TREE IS REJECTED", malformed_rejected, True)

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))

        def clone_failure(request: Any) -> Any:
            raise workspace_git.DeveloperTaskWorkspaceGitError(
                "workspace_clone_failed",
                "fake clone failure",
            )

        with patch.object(workspace, "create_independent_git_workspace", side_effect=clone_failure):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check(
            "CLONE FAILURE IS STRUCTURED AND CLEANED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_clone_failed"],
                "workspace_present": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))

        with patch.object(workspace_git, "_remove_all_remotes", return_value=None):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check(
            "RETAINED REMOTE FAILS CLOSED AND CLEANS WORKSPACE",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_remote_present"],
                "workspace_present": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))

        with patch.object(workspace_git, "_read_alternates", return_value=("C:/shared/objects",)):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check(
            "ALTERNATE OBJECT DIRECTORY FAILS CLOSED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_alternates_present"],
                "workspace_present": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        original_snapshot = workspace_git._snapshot_source
        calls = 0

        def changing_snapshot(context: Any) -> Any:
            nonlocal calls
            calls += 1
            value = original_snapshot(context)

            if calls == 2:
                return replace(value, refs=value.refs + b"changed")

            return value

        with patch.object(workspace_git, "_snapshot_source", side_effect=changing_snapshot):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check(
            "SOURCE CHANGE DURING CREATION FAILS CLOSED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(report.workspace_root).exists(),
            },
            {
                "issue_codes": ["source_repository_changed"],
                "workspace_present": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        original_open = workspace.os.open

        def marker_open(
            path: Any,
            flags: int,
            mode: int = 0o777,
            *args: Any,
            **kwargs: Any,
        ) -> int:
            if not args and not kwargs and Path(path).name == "workspace.json":
                raise PermissionError("fake marker failure")
            return original_open(path, flags, mode, *args, **kwargs)

        with patch.object(workspace.os, "open", side_effect=marker_open):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check(
            "MARKER FAILURE IS STRUCTURED AND CLEANED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_marker_write_failed"],
                "workspace_present": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))
        original_rmtree = workspace.shutil.rmtree
        cleanup_calls = 0

        def transient_rmtree(*args: Any, **kwargs: Any) -> Any:
            nonlocal cleanup_calls
            cleanup_calls += 1

            if cleanup_calls == 1:
                raise PermissionError("temporary lock")

            return original_rmtree(*args, **kwargs)

        def clone_failure(request: Any) -> Any:
            raise workspace_git.DeveloperTaskWorkspaceGitError(
                "workspace_clone_failed",
                "fake clone failure",
            )

        with patch.object(workspace, "create_independent_git_workspace", side_effect=clone_failure), patch.object(
            workspace.shutil,
            "rmtree",
            side_effect=transient_rmtree,
        ), patch.object(workspace.time, "sleep", return_value=None):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        check(
            "TRANSIENT FAILED-WORKSPACE CLEANUP IS RETRIED",
            {
                "issue_codes": list(report.issue_codes),
                "cleanup_calls": cleanup_calls,
                "workspace_present": Path(report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_clone_failed"],
                "cleanup_calls": 2,
                "workspace_present": False,
            },
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        _, _, parent, manifest, preflight = _prepare(Path(temp_dir))

        def clone_failure(request: Any) -> Any:
            raise workspace_git.DeveloperTaskWorkspaceGitError(
                "workspace_clone_failed",
                "fake clone failure",
            )

        with patch.object(workspace, "create_independent_git_workspace", side_effect=clone_failure), patch.object(
            workspace.shutil,
            "rmtree",
            side_effect=PermissionError("permanent lock"),
        ), patch.object(workspace.time, "sleep", return_value=None):
            report = create_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_parent=parent,
            )

        workspace_path = Path(report.workspace_root)
        check(
            "PERMANENT FAILED-WORKSPACE CLEANUP IS STRUCTURED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": workspace_path.exists(),
            },
            {
                "issue_codes": ["workspace_clone_failed", "workspace_cleanup_failed"],
                "workspace_present": True,
            },
        )
        shutil.rmtree(workspace_path)

    source_text = (
        Path(workspace.__file__).read_text(encoding="utf-8")
        + "\n"
        + Path(workspace_git.__file__).read_text(encoding="utf-8")
    )
    check(
        "PRODUCTION WORKSPACE USES INDEPENDENT CLONE CONTRACT",
        {
            "no_worktree_add": "worktree add" not in source_text,
            "no_shared_clone": '"--shared"' not in source_text,
            "no_local_disabled": '"--no-local"' in source_text,
            "hardlinks_disabled": '"--no-hardlinks"' in source_text,
            "checkout_deferred": '"--no-checkout"' in source_text,
            "tags_disabled": '"--no-tags"' in source_text,
            "history_depth_limited": '"--depth=1"' in source_text,
        },
        {
            "no_worktree_add": True,
            "no_shared_clone": True,
            "no_local_disabled": True,
            "hardlinks_disabled": True,
            "checkout_deferred": True,
            "tags_disabled": True,
            "history_depth_limited": True,
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
