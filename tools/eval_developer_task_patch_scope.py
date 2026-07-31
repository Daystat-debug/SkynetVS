from __future__ import annotations

import hashlib
import json

from dataclasses import FrozenInstanceError, replace
from typing import Any

import modules.developer.developer_task_patch_scope as patch_scope

from modules.developer.developer_task_contract import (
    DeveloperTaskCheck,
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_patch_index import (
    DeveloperTaskPatchIndexChange,
    DeveloperTaskPatchIndexPreflightReport,
)
from modules.developer.developer_task_patch_scope import (
    DeveloperTaskPatchScopeCollision,
    run_developer_task_patch_scope_preflight,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue


def _manifest(
    *,
    allowed_files: tuple[str, ...],
    title: str = "Evaluate developer task patch scope policy",
) -> DeveloperTaskManifest:
    return DeveloperTaskManifest(
        schema_version=1,
        task_kind="patch",
        task_id="developer-patch-scope-eval",
        title=title,
        project="SkynetVS",
        origin="manual",
        source_ref="eval:developer-task-patch-scope",
        source_sha256="a" * 64,
        base_commit="1" * 40,
        patch_file="changes.patch",
        patch_sha256=hashlib.sha256(b"patch\n").hexdigest(),
        allowed_files=allowed_files,
        checks=(
            DeveloperTaskCheck(type="git_diff_check"),
            DeveloperTaskCheck(type="py_compile", scope="changed_python_files"),
            DeveloperTaskCheck(type="pipeline", flow="check"),
        ),
        install_policy="manual_confirmation",
    )


def _change(
    path: str,
    status: str = "M",
    old_mode: str = "100644",
    new_mode: str = "100644",
) -> DeveloperTaskPatchIndexChange:
    return DeveloperTaskPatchIndexChange(
        path=path,
        status=status,
        old_mode=old_mode,
        new_mode=new_mode,
    )


def _report(
    manifest: DeveloperTaskManifest,
    changes: tuple[DeveloperTaskPatchIndexChange, ...],
    *,
    result_index_paths: tuple[str, ...] | None = None,
    issues: tuple[DeveloperTaskPreflightIssue, ...] = (),
    fingerprint: str | None = None,
) -> DeveloperTaskPatchIndexPreflightReport:
    ordered_changes = tuple(sorted(changes, key=lambda item: (patch_scope._path_key(item.path), item.path)))
    changed_files = tuple(item.path for item in ordered_changes)

    if result_index_paths is None:
        result_index_paths = tuple(
            sorted(
                (item.path for item in ordered_changes if item.status != "D"),
                key=lambda value: (patch_scope._path_key(value), value),
            )
        )
    else:
        result_index_paths = tuple(
            sorted(result_index_paths, key=lambda value: (patch_scope._path_key(value), value))
        )

    return DeveloperTaskPatchIndexPreflightReport(
        manifest_fingerprint=fingerprint or developer_task_manifest_fingerprint(manifest),
        repository_root="C:/Project/SkynetVS",
        base_commit="1" * 40,
        changed_files=changed_files,
        changes=ordered_changes,
        result_index_paths=result_index_paths,
        issues=issues,
    )


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

    manifest = _manifest(allowed_files=("modules/example.py",))
    index_report = _report(manifest, (_change("modules/example.py"),))
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=index_report,
    )
    check(
        "VALID REGULAR PATCH PASSES PURE SCOPE POLICY",
        {
            "ok": scope_report.ok,
            "issue_codes": list(scope_report.issue_codes),
            "allowed_files": list(scope_report.allowed_files),
            "changed_files": list(scope_report.changed_files),
            "repository_root": scope_report.repository_root,
            "serialized_ok": scope_report.to_dict()["ok"],
        },
        {
            "ok": True,
            "issue_codes": [],
            "allowed_files": ["modules/example.py"],
            "changed_files": ["modules/example.py"],
            "repository_root": "C:/Project/SkynetVS",
            "serialized_ok": True,
        },
    )

    report_immutable = False
    collision_immutable = False

    try:
        scope_report.changed_files = ()  # type: ignore[misc]
    except FrozenInstanceError:
        report_immutable = True

    collision = DeveloperTaskPatchScopeCollision(paths=("Foo.py", "foo.py"))

    try:
        collision.paths = ()  # type: ignore[misc]
    except FrozenInstanceError:
        collision_immutable = True

    check(
        "SCOPE REPORT AND COLLISIONS ARE IMMUTABLE",
        {"report": report_immutable, "collision": collision_immutable},
        {"report": True, "collision": True},
    )

    raw_manifest_rejected = False

    try:
        run_developer_task_patch_scope_preflight(  # type: ignore[arg-type]
            manifest.to_dict(),
            patch_index_report=index_report,
        )
    except TypeError:
        raw_manifest_rejected = True

    check("RAW MANIFEST IS REJECTED", raw_manifest_rejected, True)

    raw_report_rejected = False

    try:
        run_developer_task_patch_scope_preflight(  # type: ignore[arg-type]
            manifest,
            patch_index_report=index_report.to_dict(),
        )
    except TypeError:
        raw_report_rejected = True

    check("RAW PATCH INDEX REPORT IS REJECTED", raw_report_rejected, True)

    failed_report = _report(
        manifest,
        (_change("modules/example.py"),),
        issues=(
            DeveloperTaskPreflightIssue(
                code="patch_index_apply_failed",
                check="patch_index_apply",
                message="fake failure",
            ),
        ),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=failed_report,
    )
    check(
        "FAILED PATCH INDEX PREFLIGHT BLOCKS POLICY",
        list(scope_report.issue_codes),
        ["patch_index_preflight_failed"],
    )

    mismatch_report = _report(
        manifest,
        (_change("modules/example.py"),),
        fingerprint="f" * 64,
    )
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=mismatch_report,
    )
    check(
        "MANIFEST FINGERPRINT MISMATCH IS REJECTED",
        list(scope_report.issue_codes),
        ["manifest_fingerprint_mismatch"],
    )

    invalid_manifest = replace(manifest, allowed_files=("modules/example.py", "MODULES/EXAMPLE.PY"))
    invalid_report = _report(invalid_manifest, (_change("modules/example.py"),))
    scope_report = run_developer_task_patch_scope_preflight(
        invalid_manifest,
        patch_index_report=invalid_report,
    )
    check("FORGED INVALID MANIFEST IS REJECTED", list(scope_report.issue_codes), ["manifest_invalid"])

    malformed_manifest = replace(manifest, checks=(object(),))  # type: ignore[arg-type]
    malformed_report = _report(
        malformed_manifest,
        (_change("modules/example.py"),),
        fingerprint="f" * 64,
    )
    scope_report = run_developer_task_patch_scope_preflight(
        malformed_manifest,
        patch_index_report=malformed_report,
    )
    check(
        "MALFORMED MANIFEST OBJECT IS STRUCTURED",
        list(scope_report.issue_codes),
        ["manifest_invalid"],
    )

    inconsistent_report = replace(index_report, changed_files=("other.py",))
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=inconsistent_report,
    )
    check(
        "INCONSISTENT CHANGED FILE EVIDENCE IS REJECTED",
        list(scope_report.issue_codes),
        ["patch_index_preflight_invalid"],
    )

    non_string_path_report = replace(
        index_report,
        changed_files=(1,),  # type: ignore[arg-type]
        result_index_paths=(1,),  # type: ignore[arg-type]
    )
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=non_string_path_report,
    )
    check(
        "NON-STRING PATH EVIDENCE IS STRUCTURED",
        list(scope_report.issue_codes),
        ["patch_index_preflight_invalid"],
    )

    sha256_manifest = replace(manifest, base_commit="1" * 40)
    sha256_report = _report(
        sha256_manifest,
        (_change("modules/example.py"),),
    )
    sha256_report = replace(sha256_report, base_commit="1" * 64)
    scope_report = run_developer_task_patch_scope_preflight(
        sha256_manifest,
        patch_index_report=sha256_report,
    )
    check(
        "SHA256 FULL COMMIT ACCEPTS FORTY-CHAR MANIFEST ABBREVIATION",
        scope_report.ok,
        True,
    )

    missing_result_report = replace(index_report, result_index_paths=())
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=missing_result_report,
    )
    check(
        "NON-DELETED PATH MUST EXIST IN RESULT INDEX",
        list(scope_report.issue_codes),
        ["patch_index_preflight_invalid"],
    )

    delete_manifest = _manifest(allowed_files=("old.txt",))
    delete_report = _report(
        delete_manifest,
        (_change("old.txt", "D", "100644", "000000"),),
        result_index_paths=("old.txt",),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        delete_manifest,
        patch_index_report=delete_report,
    )
    check(
        "DELETED PATH MUST BE ABSENT FROM RESULT INDEX",
        list(scope_report.issue_codes),
        ["patch_index_preflight_invalid"],
    )

    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=_report(manifest, (_change("modules/other.py"),)),
    )
    check(
        "PATH OUTSIDE ALLOWLIST IS REJECTED",
        {
            "issue_codes": list(scope_report.issue_codes),
            "unauthorized": list(scope_report.unauthorized_files),
        },
        {
            "issue_codes": ["patch_scope_violation"],
            "unauthorized": ["modules/other.py"],
        },
    )

    case_manifest = _manifest(allowed_files=("modules/Example.py",))
    scope_report = run_developer_task_patch_scope_preflight(
        case_manifest,
        patch_index_report=_report(case_manifest, (_change("modules/example.py"),)),
    )
    check(
        "ALLOWLIST REQUIRES EXACT PATH CASING",
        {
            "issue_codes": list(scope_report.issue_codes),
            "case_mismatch": list(scope_report.case_mismatch_files),
            "unauthorized": list(scope_report.unauthorized_files),
        },
        {
            "issue_codes": ["patch_scope_case_mismatch"],
            "case_mismatch": ["modules/example.py"],
            "unauthorized": [],
        },
    )

    rename_manifest = _manifest(allowed_files=("new_name.py", "old_name.py"))
    rename_report = _report(
        rename_manifest,
        (
            _change("old_name.py", "D", "100644", "000000"),
            _change("new_name.py", "A", "000000", "100644"),
        ),
        result_index_paths=("new_name.py",),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        rename_manifest,
        patch_index_report=rename_report,
    )
    check("RENAME PASSES WHEN BOTH PATHS ARE ALLOWED", scope_report.ok, True)

    rename_missing_source_manifest = _manifest(allowed_files=("new_name.py",))
    rename_missing_source_report = _report(
        rename_missing_source_manifest,
        (
            _change("old_name.py", "D", "100644", "000000"),
            _change("new_name.py", "A", "000000", "100644"),
        ),
        result_index_paths=("new_name.py",),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        rename_missing_source_manifest,
        patch_index_report=rename_missing_source_report,
    )
    check(
        "RENAME SOURCE MUST ALSO BE ALLOWED",
        list(scope_report.unauthorized_files),
        ["old_name.py"],
    )

    case_rename_manifest = _manifest(allowed_files=("Foo.py",))
    case_rename_report = _report(
        case_rename_manifest,
        (
            _change("Foo.py", "D", "100644", "000000"),
            _change("foo.py", "A", "000000", "100644"),
        ),
        result_index_paths=("foo.py",),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        case_rename_manifest,
        patch_index_report=case_rename_report,
    )
    check(
        "CASE-ONLY RENAME IS BLOCKED",
        {
            "issue_codes": list(scope_report.issue_codes),
            "collisions": [list(item.paths) for item in scope_report.changed_path_collisions],
            "case_mismatch": list(scope_report.case_mismatch_files),
        },
        {
            "issue_codes": ["patch_scope_case_mismatch", "patch_changed_path_collision"],
            "collisions": [["Foo.py", "foo.py"]],
            "case_mismatch": ["foo.py"],
        },
    )

    collision_manifest = _manifest(allowed_files=("new.py",))
    collision_report = _report(
        collision_manifest,
        (_change("new.py", "A", "000000", "100644"),),
        result_index_paths=("CaseBase.txt", "casebase.TXT", "new.py"),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        collision_manifest,
        patch_index_report=collision_report,
    )
    check(
        "RESULT INDEX WINDOWS CASE COLLISION IS BLOCKED",
        {
            "issue_codes": list(scope_report.issue_codes),
            "collisions": [list(item.paths) for item in scope_report.result_index_collisions],
        },
        {
            "issue_codes": ["patch_result_index_collision"],
            "collisions": [["CaseBase.txt", "casebase.TXT"]],
        },
    )

    symlink_manifest = _manifest(allowed_files=("link",))
    scope_report = run_developer_task_patch_scope_preflight(
        symlink_manifest,
        patch_index_report=_report(
            symlink_manifest,
            (_change("link", "A", "000000", "120000"),),
        ),
    )
    check(
        "SYMLINK ADD IS BLOCKED",
        {
            "issue_codes": list(scope_report.issue_codes),
            "paths": list(scope_report.symlink_files),
        },
        {
            "issue_codes": ["patch_symlink_unsupported"],
            "paths": ["link"],
        },
    )

    symlink_delete_manifest = _manifest(allowed_files=("link",))
    scope_report = run_developer_task_patch_scope_preflight(
        symlink_delete_manifest,
        patch_index_report=_report(
            symlink_delete_manifest,
            (_change("link", "D", "120000", "000000"),),
            result_index_paths=(),
        ),
    )
    check("SYMLINK DELETE IS ALSO BLOCKED", list(scope_report.issue_codes), ["patch_symlink_unsupported"])

    gitlink_manifest = _manifest(allowed_files=("vendor/sub",))
    scope_report = run_developer_task_patch_scope_preflight(
        gitlink_manifest,
        patch_index_report=_report(
            gitlink_manifest,
            (_change("vendor/sub", "A", "000000", "160000"),),
        ),
    )
    check(
        "GITLINK ADD IS BLOCKED",
        {
            "issue_codes": list(scope_report.issue_codes),
            "paths": list(scope_report.gitlink_files),
        },
        {
            "issue_codes": ["patch_gitlink_unsupported"],
            "paths": ["vendor/sub"],
        },
    )

    gitlink_delete_manifest = _manifest(allowed_files=("vendor/sub",))
    scope_report = run_developer_task_patch_scope_preflight(
        gitlink_delete_manifest,
        patch_index_report=_report(
            gitlink_delete_manifest,
            (_change("vendor/sub", "D", "160000", "000000"),),
            result_index_paths=(),
        ),
    )
    check("GITLINK DELETE IS ALSO BLOCKED", list(scope_report.issue_codes), ["patch_gitlink_unsupported"])

    type_manifest = _manifest(allowed_files=("entry",))
    scope_report = run_developer_task_patch_scope_preflight(
        type_manifest,
        patch_index_report=_report(
            type_manifest,
            (_change("entry", "T", "100644", "120000"),),
        ),
    )
    check(
        "TYPE CHANGE IS BLOCKED WITH MODE-SPECIFIC EVIDENCE",
        list(scope_report.issue_codes),
        ["patch_symlink_unsupported", "patch_type_change_unsupported"],
    )

    executable_manifest = _manifest(allowed_files=("script.py",))
    scope_report = run_developer_task_patch_scope_preflight(
        executable_manifest,
        patch_index_report=_report(
            executable_manifest,
            (_change("script.py", "A", "000000", "100755"),),
        ),
    )
    check("EXECUTABLE REGULAR FILE ADD IS ALLOWED", scope_report.ok, True)

    mode_manifest = _manifest(allowed_files=("script.py",))
    scope_report = run_developer_task_patch_scope_preflight(
        mode_manifest,
        patch_index_report=_report(
            mode_manifest,
            (_change("script.py", "M", "100644", "100755"),),
        ),
    )
    check("REGULAR EXECUTABLE MODE CHANGE IS ALLOWED", scope_report.ok, True)

    delete_regular_manifest = _manifest(allowed_files=("obsolete.py",))
    scope_report = run_developer_task_patch_scope_preflight(
        delete_regular_manifest,
        patch_index_report=_report(
            delete_regular_manifest,
            (_change("obsolete.py", "D", "100644", "000000"),),
            result_index_paths=(),
        ),
    )
    check("REGULAR FILE DELETE IS ALLOWED", scope_report.ok, True)

    extra_allowlist_manifest = _manifest(allowed_files=("modules/example.py", "modules/unused.py"))
    scope_report = run_developer_task_patch_scope_preflight(
        extra_allowlist_manifest,
        patch_index_report=_report(extra_allowlist_manifest, (_change("modules/example.py"),)),
    )
    check("UNUSED ALLOWLIST ENTRY DOES NOT FAIL POLICY", scope_report.ok, True)

    multiple_manifest = _manifest(allowed_files=("a.py", "b.py"))
    multiple_report = _report(
        multiple_manifest,
        (
            _change("b.py"),
            _change("a.py", "A", "000000", "100644"),
        ),
        result_index_paths=("a.py", "b.py"),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        multiple_manifest,
        patch_index_report=multiple_report,
    )
    check(
        "MULTIPLE AUTHORIZED CHANGES ARE DETERMINISTIC",
        {
            "ok": scope_report.ok,
            "changed_files": list(scope_report.changed_files),
        },
        {
            "ok": True,
            "changed_files": ["a.py", "b.py"],
        },
    )

    unicode_manifest = _manifest(allowed_files=("straße.py", "strasse.py"))
    unicode_report = _report(
        unicode_manifest,
        (
            _change("straße.py"),
            _change("strasse.py"),
        ),
        result_index_paths=("straße.py", "strasse.py"),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        unicode_manifest,
        patch_index_report=unicode_report,
    )
    check(
        "CONTRACT STRICTER UNICODE COLLISION IS REJECTED",
        list(scope_report.issue_codes),
        ["manifest_invalid"],
    )

    invalid_status_report = replace(
        index_report,
        changes=(_change("modules/example.py", "R"),),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=invalid_status_report,
    )
    check("UNKNOWN CHANGE STATUS INVALIDATES EVIDENCE", list(scope_report.issue_codes), ["patch_index_preflight_invalid"])

    invalid_mode_report = replace(
        index_report,
        changes=(_change("modules/example.py", "M", "100644", "100600"),),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=invalid_mode_report,
    )
    check("UNKNOWN FILE MODE INVALIDATES EVIDENCE", list(scope_report.issue_codes), ["patch_index_preflight_invalid"])

    unsafe_path_report = replace(
        index_report,
        changed_files=("../escape.py",),
        changes=(_change("../escape.py"),),
        result_index_paths=("../escape.py",),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=unsafe_path_report,
    )
    check("UNSAFE PATH INVALIDATES EVIDENCE", list(scope_report.issue_codes), ["patch_index_preflight_invalid"])

    duplicate_change_report = replace(
        index_report,
        changed_files=("modules/example.py", "modules/example.py"),
        changes=(
            _change("modules/example.py"),
            _change("modules/example.py"),
        ),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=duplicate_change_report,
    )
    check("EXACT DUPLICATE CHANGE INVALIDATES EVIDENCE", list(scope_report.issue_codes), ["patch_index_preflight_invalid"])

    duplicate_result_report = replace(
        index_report,
        result_index_paths=("modules/example.py", "modules/example.py"),
    )
    scope_report = run_developer_task_patch_scope_preflight(
        manifest,
        patch_index_report=duplicate_result_report,
    )
    check("EXACT DUPLICATE RESULT PATH INVALIDATES EVIDENCE", list(scope_report.issue_codes), ["patch_index_preflight_invalid"])

    check(
        "POLICY MODULE DOES NOT IMPORT GIT OR FILESYSTEM EXECUTION",
        {
            "has_subprocess": "subprocess" in patch_scope.__dict__,
            "has_os": "os" in patch_scope.__dict__,
            "has_pathlib_path": "Path" in patch_scope.__dict__,
        },
        {
            "has_subprocess": False,
            "has_os": False,
            "has_pathlib_path": False,
        },
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
