from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import time

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_workspace_cleanup as cleanup
import modules.developer.developer_task_workspace_cleanup_fs as cleanup_fs

from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_workspace import (
    DeveloperTaskWorkspaceReport,
    create_developer_task_workspace,
)
from modules.developer.developer_task_workspace_cleanup import (
    DeveloperTaskWorkspaceCleanupReport,
    cleanup_developer_task_workspace,
)
from modules.developer.developer_task_workspace_git import DeveloperTaskWorkspaceGitError
from tools.eval_developer_task_workspace import (
    _git,
    _git_bytes,
    _index_path,
    _object_snapshot,
    _prepare,
    _sha256,
)


def _issue(code: str = "forced_failure") -> DeveloperTaskPreflightIssue:
    return DeveloperTaskPreflightIssue(
        code=code,
        check="eval",
        message="Forced eval failure.",
    )


def _prepare_workspace(
    root: Path,
) -> tuple[Path, Path, Path, Any, Any, DeveloperTaskWorkspaceReport]:
    repo, task_root, parent, manifest, preflight = _prepare(root)
    workspace_report = create_developer_task_workspace(
        manifest,
        preflight_report=preflight,
        workspace_parent=parent,
    )
    assert workspace_report.ok, workspace_report.to_dict()
    return repo, task_root, parent, manifest, preflight, workspace_report


def _cleanup(
    manifest: Any,
    preflight: Any,
    workspace_report: DeveloperTaskWorkspaceReport,
    parent: Path,
) -> DeveloperTaskWorkspaceCleanupReport:
    return cleanup_developer_task_workspace(
        manifest,
        preflight_report=preflight,
        workspace_report=workspace_report,
        workspace_parent=parent,
    )


_FIXTURE_CLEANUP_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2, 0.4)


def _fixture_rmtree_readonly_handler(
    function: Any,
    path: str,
    exc_info: tuple[type[BaseException], BaseException, Any],
) -> None:
    error = exc_info[1]

    if not isinstance(error, PermissionError):
        raise error

    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        function(path)
    except FileNotFoundError:
        return


def _remove_fixture_tree(path: Path) -> None:
    delays = (0.0, *_FIXTURE_CLEANUP_RETRY_DELAYS_SECONDS)
    last_error: OSError | None = None

    for index, delay in enumerate(delays):
        if delay:
            time.sleep(delay)

        try:
            shutil.rmtree(
                path,
                onerror=_fixture_rmtree_readonly_handler,
            )
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc

            if index != len(delays) - 1:
                continue

    if last_error is not None:
        raise last_error


def _rewrite_marker(
    workspace_report: DeveloperTaskWorkspaceReport,
    payload: Any,
) -> DeveloperTaskWorkspaceReport:
    marker = Path(workspace_report.marker_path)
    data = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    marker.write_bytes(data)
    return replace(
        workspace_report,
        marker_sha256=hashlib.sha256(data).hexdigest(),
    )


def _marker_payload(workspace_report: DeveloperTaskWorkspaceReport) -> dict[str, Any]:
    return json.loads(Path(workspace_report.marker_path).read_text(encoding="utf-8"))


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
        repo, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        source_index = _index_path(repo)
        index_before = _sha256(source_index)
        tracked_before = (repo / "tracked.txt").read_bytes()
        objects_before = _object_snapshot(repo)
        refs_before = _git(repo, "for-each-ref", "--format=%(objectname) %(refname)").stdout
        status_before = _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
        sibling = parent / "do-not-delete"
        sibling.mkdir()
        (sibling / "sentinel.txt").write_text("keep\n", encoding="utf-8")
        report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "VERIFIED WORKSPACE IS REMOVED WITHOUT SOURCE MUTATION",
            {
                "ok": report.ok,
                "state": report.state,
                "issue_codes": list(report.issue_codes),
                "removed": report.removed,
                "already_absent": report.already_absent,
                "attempts": report.attempts,
                "workspace_absent": not Path(report.workspace_root).exists(),
                "marker_absent": not Path(report.marker_path).exists(),
                "sibling_preserved": (sibling / "sentinel.txt").read_text(encoding="utf-8") == "keep\n",
                "source_unchanged": report.source_repository_unchanged,
                "index_unchanged": _sha256(source_index) == index_before,
                "tracked_unchanged": (repo / "tracked.txt").read_bytes() == tracked_before,
                "objects_unchanged": _object_snapshot(repo) == objects_before,
                "refs_unchanged": _git(repo, "for-each-ref", "--format=%(objectname) %(refname)").stdout == refs_before,
                "status_unchanged": _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout == status_before,
                "serialized_state": report.to_dict()["state"],
            },
            {
                "ok": True,
                "state": "removed",
                "issue_codes": [],
                "removed": True,
                "already_absent": False,
                "attempts": 1,
                "workspace_absent": True,
                "marker_absent": True,
                "sibling_preserved": True,
                "source_unchanged": True,
                "index_unchanged": True,
                "tracked_unchanged": True,
                "objects_unchanged": True,
                "refs_unchanged": True,
                "status_unchanged": True,
                "serialized_state": "removed",
            },
        )

        second = _cleanup(manifest, preflight, workspace_report, parent)
        check(
            "CLEANUP IS IDEMPOTENT AFTER SUCCESS",
            {
                "ok": second.ok,
                "state": second.state,
                "removed": second.removed,
                "already_absent": second.already_absent,
                "attempts": second.attempts,
                "issue_codes": list(second.issue_codes),
                "source_unchanged": second.source_repository_unchanged,
            },
            {
                "ok": True,
                "state": "already_absent",
                "removed": False,
                "already_absent": True,
                "attempts": 0,
                "issue_codes": [],
                "source_unchanged": True,
            },
        )

        immutable = False

        try:
            report.removed = False  # type: ignore[misc]
        except FrozenInstanceError:
            immutable = True

        check("CLEANUP REPORT IS IMMUTABLE", immutable, True)
        check(
            "CLEANUP REPORT IS JSON SERIALIZABLE",
            bool(json.dumps(report.to_dict(), ensure_ascii=False)),
            True,
        )
        check(
            "CLEANUP CAPABILITY IS NOT SERIALIZED OR REPR EXPOSED",
            {
                "to_dict": "cleanup_token" not in workspace_report.to_dict(),
                "repr": workspace_report.cleanup_token.hex() not in repr(workspace_report),
                "present": workspace_report.to_dict().get("cleanup_capability_present"),
            },
            {"to_dict": True, "repr": True, "present": True},
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        raw_manifest_rejected = False

        try:
            cleanup_developer_task_workspace(
                manifest.to_dict(),  # type: ignore[arg-type]
                preflight_report=preflight,
                workspace_report=workspace_report,
                workspace_parent=parent,
            )
        except TypeError:
            raw_manifest_rejected = True

        check("RAW MANIFEST IS REJECTED", raw_manifest_rejected, True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        raw_preflight_rejected = False

        try:
            cleanup_developer_task_workspace(
                manifest,
                preflight_report=preflight.to_dict(),  # type: ignore[arg-type]
                workspace_report=workspace_report,
                workspace_parent=parent,
            )
        except TypeError:
            raw_preflight_rejected = True

        check("RAW PREFLIGHT REPORT IS REJECTED", raw_preflight_rejected, True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        raw_workspace_rejected = False

        try:
            cleanup_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_report=workspace_report.to_dict(),  # type: ignore[arg-type]
                workspace_parent=parent,
            )
        except TypeError:
            raw_workspace_rejected = True

        check("RAW WORKSPACE REPORT IS REJECTED", raw_workspace_rejected, True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        string_parent_rejected = False

        try:
            cleanup_developer_task_workspace(
                manifest,
                preflight_report=preflight,
                workspace_report=workspace_report,
                workspace_parent=str(parent),  # type: ignore[arg-type]
            )
        except TypeError:
            string_parent_rejected = True

        check("STRING WORKSPACE PARENT IS REJECTED", string_parent_rejected, True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        failed_preflight = replace(preflight, issues=(_issue("forced_preflight_failure"),))
        report = _cleanup(manifest, failed_preflight, workspace_report, parent)
        check(
            "FAILED PREFLIGHT BLOCKS CLEANUP",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["preflight_report_failed"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        failed_workspace = replace(workspace_report, issues=(_issue("forced_workspace_failure"),))
        report = _cleanup(manifest, preflight, failed_workspace, parent)
        check(
            "FAILED WORKSPACE REPORT BLOCKS CLEANUP",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_report_failed"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        mismatched_manifest = replace(manifest, title="Different manifest title")
        report = _cleanup(mismatched_manifest, preflight, workspace_report, parent)
        check(
            "MANIFEST FINGERPRINT MISMATCH BLOCKS CLEANUP",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["preflight_report_invalid"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(root / "case")
        other_parent = root / "other"
        other_parent.mkdir()
        report = _cleanup(manifest, preflight, workspace_report, other_parent)
        check(
            "EXPLICIT WORKSPACE PARENT MISMATCH IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_parent_mismatch"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        invalid_id = replace(workspace_report, workspace_id="skynetvs-task-forged")
        report = _cleanup(manifest, preflight, invalid_id, parent)
        check(
            "INVALID WORKSPACE ID IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_id_invalid"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        repo, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        forged = replace(workspace_report, workspace_root=str(repo), repository_root=str(repo))
        report = _cleanup(manifest, preflight, forged, parent)
        check(
            "FORGED SOURCE PATH CANNOT BE DELETED",
            {
                "issue_codes": list(report.issue_codes),
                "source_present": (repo / "tracked.txt").is_file(),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_report_paths_invalid"],
                "source_present": True,
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(root / "case")
        _remove_fixture_tree(parent)
        report = _cleanup(manifest, preflight, workspace_report, parent)
        check("MISSING WORKSPACE PARENT IS REJECTED", list(report.issue_codes), ["workspace_parent_missing"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        root = Path(temp_dir)
        repo, task_root, parent, manifest, preflight, workspace_report = _prepare_workspace(root / "case")
        _remove_fixture_tree(Path(workspace_report.workspace_root))
        parent.rmdir()
        parent.write_text("not a directory\n", encoding="utf-8")
        report = _cleanup(manifest, preflight, workspace_report, parent)
        check("FILE WORKSPACE PARENT IS REJECTED", list(report.issue_codes), ["workspace_parent_not_directory"])
        assert (repo / "tracked.txt").is_file() and task_root.is_dir()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        real_lstat = cleanup_fs.os.lstat

        def parent_reparse_lstat(path: Any) -> Any:
            value = real_lstat(path)

            if cleanup_fs.same_path(path, parent):
                return SimpleNamespace(
                    st_mode=value.st_mode,
                    st_file_attributes=0x400,
                )

            return value

        with patch.object(cleanup_fs.os, "lstat", side_effect=parent_reparse_lstat):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "WORKSPACE PARENT REPARSE POINT IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_parent_reparse_point"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        workspace_root = Path(workspace_report.workspace_root)
        real_lstat = cleanup_fs.os.lstat

        def root_reparse_lstat(path: Any) -> Any:
            value = real_lstat(path)

            if cleanup_fs.same_path(path, workspace_root):
                return SimpleNamespace(
                    st_mode=value.st_mode,
                    st_file_attributes=0x400,
                )

            return value

        with patch.object(cleanup_fs.os, "lstat", side_effect=root_reparse_lstat):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "WORKSPACE ROOT REPARSE POINT IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": workspace_root.exists(),
            },
            {
                "issue_codes": ["workspace_root_reparse_point"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        marker = Path(workspace_report.marker_path)
        marker.unlink()
        report = _cleanup(manifest, preflight, workspace_report, parent)
        check(
            "MISSING MARKER BLOCKS CLEANUP",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_marker_missing"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        marker = Path(workspace_report.marker_path)
        marker.unlink()
        marker.mkdir()
        report = _cleanup(manifest, preflight, workspace_report, parent)
        check("MARKER DIRECTORY IS REJECTED", list(report.issue_codes), ["workspace_marker_not_regular"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        marker = Path(workspace_report.marker_path)
        real_lstat = cleanup_fs.os.lstat

        def marker_reparse_lstat(path: Any) -> Any:
            value = real_lstat(path)

            if cleanup_fs.same_path(path, marker):
                return SimpleNamespace(
                    st_mode=value.st_mode,
                    st_file_attributes=0x400,
                    st_size=value.st_size,
                )

            return value

        with patch.object(cleanup_fs.os, "lstat", side_effect=marker_reparse_lstat):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "MARKER REPARSE POINT IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_marker_reparse_point"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        marker = Path(workspace_report.marker_path)
        marker.write_bytes(marker.read_bytes() + b"\n")
        report = _cleanup(manifest, preflight, workspace_report, parent)
        check("MARKER HASH MISMATCH IS REJECTED", list(report.issue_codes), ["workspace_marker_hash_mismatch"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        forged_capability = replace(workspace_report, cleanup_token=b"x" * 32)
        report = _cleanup(manifest, preflight, forged_capability, parent)
        check(
            "CLEANUP CAPABILITY MISMATCH IS REJECTED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_marker_evidence_mismatch"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        marker = Path(workspace_report.marker_path)
        malformed = b"{not-json"
        marker.write_bytes(malformed)
        changed_report = replace(workspace_report, marker_sha256=hashlib.sha256(malformed).hexdigest())
        report = _cleanup(manifest, preflight, changed_report, parent)
        check("MALFORMED MARKER IS REJECTED", list(report.issue_codes), ["workspace_marker_invalid"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        payload = _marker_payload(workspace_report)
        payload["unexpected"] = True
        changed_report = _rewrite_marker(workspace_report, payload)
        report = _cleanup(manifest, preflight, changed_report, parent)
        check("UNKNOWN MARKER FIELD IS REJECTED", list(report.issue_codes), ["workspace_marker_fields_invalid"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        payload = _marker_payload(workspace_report)
        payload["head_commit"] = "f" * 40
        changed_report = _rewrite_marker(workspace_report, payload)
        report = _cleanup(manifest, preflight, changed_report, parent)
        check("MARKER EVIDENCE MISMATCH IS REJECTED", list(report.issue_codes), ["workspace_marker_evidence_mismatch"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        marker = Path(workspace_report.marker_path)
        payload = _marker_payload(workspace_report)
        noncanonical = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        marker.write_bytes(noncanonical)
        changed_report = replace(
            workspace_report,
            marker_sha256=hashlib.sha256(noncanonical).hexdigest(),
        )
        report = _cleanup(manifest, preflight, changed_report, parent)
        check(
            "NONCANONICAL MARKER ENCODING IS REJECTED",
            list(report.issue_codes),
            ["workspace_marker_evidence_mismatch"],
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        marker = Path(workspace_report.marker_path)
        oversized = b"x" * (cleanup_fs.MARKER_MAX_BYTES + 1)
        marker.write_bytes(oversized)
        changed_report = replace(workspace_report, marker_sha256=hashlib.sha256(oversized).hexdigest())
        report = _cleanup(manifest, preflight, changed_report, parent)
        check("OVERSIZED MARKER IS REJECTED", list(report.issue_codes), ["workspace_marker_size_invalid"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))

        with patch.object(cleanup_fs, "_read_file_descriptor", side_effect=OSError("forced marker read failure")):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check("MARKER READ FAILURE IS STRUCTURED", list(report.issue_codes), ["workspace_marker_read_failed"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        original_file_version = cleanup_fs._file_version
        calls = 0

        def changing_version(value: Any) -> Any:
            nonlocal calls
            calls += 1
            result = original_file_version(value)
            return (*result[:-1], result[-1] + 1) if calls == 2 else result

        with patch.object(cleanup_fs, "_file_version", side_effect=changing_version):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check("MARKER CHANGE DURING READ IS REJECTED", list(report.issue_codes), ["workspace_marker_changed_during_read"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        unsafe_path = Path(workspace_report.workspace_root) / "repository" / "unsafe-link"

        with patch.object(
            cleanup_fs,
            "_find_unsafe_tree_entry",
            return_value=("workspace_tree_reparse_point", str(unsafe_path)),
        ):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "DESCENDANT REPARSE POINT BLOCKS CLEANUP",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_tree_reparse_point"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        unsafe_path = Path(workspace_report.workspace_root) / "repository" / "special"

        with patch.object(
            cleanup_fs,
            "_find_unsafe_tree_entry",
            return_value=("workspace_tree_special_file", str(unsafe_path)),
        ):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check("SPECIAL TREE ENTRY BLOCKS CLEANUP", list(report.issue_codes), ["workspace_tree_special_file"])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))

        with patch.object(
            cleanup_fs,
            "_find_unsafe_tree_entry",
            side_effect=OSError("forced tree scan failure"),
        ):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "TREE SCAN FAILURE IS STRUCTURED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_tree_scan_failed"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        original_rmtree = cleanup_fs.shutil.rmtree
        calls = 0

        def transient_rmtree(*args: Any, **kwargs: Any) -> None:
            nonlocal calls
            calls += 1

            if calls == 1:
                raise PermissionError("transient lock")

            original_rmtree(*args, **kwargs)

        with (
            patch.object(cleanup_fs.shutil, "rmtree", side_effect=transient_rmtree),
            patch.object(cleanup_fs.time, "sleep", return_value=None),
        ):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "TRANSIENT WINDOWS CLEANUP FAILURE IS RETRIED",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "attempts": report.attempts,
                "workspace_absent": not Path(workspace_report.workspace_root).exists(),
            },
            {
                "ok": True,
                "issue_codes": [],
                "attempts": 2,
                "workspace_absent": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))

        with (
            patch.object(cleanup_fs.shutil, "rmtree", side_effect=PermissionError("permanent lock")),
            patch.object(cleanup_fs.time, "sleep", return_value=None),
        ):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "PERMANENT CLEANUP FAILURE IS STRUCTURED",
            {
                "issue_codes": list(report.issue_codes),
                "attempts": report.attempts,
                "workspace_present": Path(workspace_report.workspace_root).exists(),
                "source_unchanged": report.source_repository_unchanged,
            },
            {
                "issue_codes": ["workspace_cleanup_failed"],
                "attempts": 5,
                "workspace_present": True,
                "source_unchanged": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        original_rmtree = cleanup_fs.shutil.rmtree
        rmtree_calls = 0
        identity_calls = 0

        def first_rmtree_fails(*args: Any, **kwargs: Any) -> None:
            nonlocal rmtree_calls
            rmtree_calls += 1

            if rmtree_calls == 1:
                raise PermissionError("retry")

            original_rmtree(*args, **kwargs)

        def changed_identity(*args: Any, **kwargs: Any) -> bool:
            nonlocal identity_calls
            identity_calls += 1
            return identity_calls == 1

        with (
            patch.object(cleanup_fs.shutil, "rmtree", side_effect=first_rmtree_fails),
            patch.object(cleanup_fs, "_same_directory_identity", side_effect=changed_identity),
            patch.object(cleanup_fs.time, "sleep", return_value=None),
        ):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "TARGET IDENTITY CHANGE FAILS CLOSED",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["workspace_cleanup_target_changed"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))

        with patch.object(
            cleanup,
            "snapshot_developer_task_source_repository",
            side_effect=DeveloperTaskWorkspaceGitError(
                "source_repository_snapshot_failed",
                "forced source snapshot failure",
            ),
        ):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "SOURCE SNAPSHOT FAILURE BLOCKS CLEANUP",
            {
                "issue_codes": list(report.issue_codes),
                "workspace_present": Path(workspace_report.workspace_root).exists(),
            },
            {
                "issue_codes": ["source_repository_snapshot_failed"],
                "workspace_present": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        original_snapshot = cleanup.snapshot_developer_task_source_repository
        before = original_snapshot(Path(workspace_report.source_repository_root))
        calls = 0

        def changing_source(root: Path) -> Any:
            nonlocal calls
            calls += 1
            return before if calls == 1 else replace(before, refs=before.refs + b"changed")

        with patch.object(cleanup, "snapshot_developer_task_source_repository", side_effect=changing_source):
            report = _cleanup(manifest, preflight, workspace_report, parent)

        check(
            "SOURCE CHANGE DURING CLEANUP IS REPORTED",
            {
                "removed": report.removed,
                "issue_codes": list(report.issue_codes),
                "source_unchanged": report.source_repository_unchanged,
                "workspace_absent": not Path(workspace_report.workspace_root).exists(),
            },
            {
                "removed": True,
                "issue_codes": ["source_repository_changed"],
                "source_unchanged": False,
                "workspace_absent": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        repo, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        (repo / "tracked.txt").write_text("user change before cleanup\n", encoding="utf-8")
        status_before = _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
        report = _cleanup(manifest, preflight, workspace_report, parent)
        status_after = _git_bytes(repo, "status", "--porcelain=v2", "-z").stdout
        check(
            "PREEXISTING SOURCE CHANGES DO NOT PREVENT SAFE CLEANUP",
            {
                "ok": report.ok,
                "issue_codes": list(report.issue_codes),
                "source_status_preserved": status_before == status_after and bool(status_before),
                "workspace_absent": not Path(workspace_report.workspace_root).exists(),
            },
            {
                "ok": True,
                "issue_codes": [],
                "source_status_preserved": True,
                "workspace_absent": True,
            },
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        _, _, parent, manifest, preflight, workspace_report = _prepare_workspace(Path(temp_dir))
        workspace_root = Path(workspace_report.workspace_root)
        _remove_fixture_tree(workspace_root)
        workspace_root.write_text("replaced by file\n", encoding="utf-8")
        report = _cleanup(manifest, preflight, workspace_report, parent)
        check("FILE WORKSPACE ROOT IS REJECTED", list(report.issue_codes), ["workspace_root_not_directory"])

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
