from __future__ import annotations

import json

from typing import Any

from modules.developer_task_contract import (
    DeveloperTaskValidationError,
    developer_task_manifest_fingerprint,
)
from modules.developer_task_validator import (
    require_valid_developer_task_manifest,
    validate_developer_task_manifest,
)


def _valid_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_kind": "patch",
        "task_id": "developer-contract-smoke",
        "title": "Проверить контракт задачи разработки",
        "project": "SkynetVS",
        "origin": "manual",
        "source_ref": "chatgpt:manual:developer-contract-smoke",
        "source_sha256": "a" * 64,
        "base_commit": "0123456789abcdef0123456789abcdef01234567",
        "patch_file": "changes.patch",
        "patch_sha256": "b" * 64,
        "allowed_files": [
            "modules/example.py",
            "tools/eval_example.py",
        ],
        "checks": [
            {
                "type": "git_diff_check",
            },
            {
                "type": "py_compile",
                "scope": "changed_python_files",
            },
            {
                "type": "python_module",
                "module": "tools.eval_example",
            },
            {
                "type": "pipeline",
                "flow": "check",
            },
        ],
        "install_policy": "manual_confirmation",
    }


def _issue_presence(
    payload: Any,
    expected_codes: tuple[str, ...],
) -> dict[str, Any]:
    result = validate_developer_task_manifest(payload)
    codes = set(result.issue_codes)

    return {
        "ok": result.ok,
        "contains": {
            code: code in codes
            for code in expected_codes
        },
    }


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

    payload = _valid_manifest()
    result = validate_developer_task_manifest(payload)
    manifest = result.manifest

    check(
        "VALID MANUAL TASK",
        {
            "ok": result.ok,
            "task_id": manifest.task_id if manifest else None,
            "origin": manifest.origin if manifest else None,
            "allowed_files": list(manifest.allowed_files) if manifest else None,
            "check_types": [item.type for item in manifest.checks] if manifest else None,
            "fingerprint_length": len(developer_task_manifest_fingerprint(manifest)) if manifest else 0,
        },
        {
            "ok": True,
            "task_id": "developer-contract-smoke",
            "origin": "manual",
            "allowed_files": [
                "modules/example.py",
                "tools/eval_example.py",
            ],
            "check_types": [
                "git_diff_check",
                "py_compile",
                "python_module",
                "pipeline",
            ],
            "fingerprint_length": 64,
        },
    )

    reordered_payload = {
        key: payload[key]
        for key in reversed(tuple(payload))
    }
    reordered_manifest = require_valid_developer_task_manifest(reordered_payload)

    check(
        "CANONICAL FINGERPRINT IS STABLE",
        developer_task_manifest_fingerprint(manifest),
        developer_task_manifest_fingerprint(reordered_manifest),
    )

    payload = _valid_manifest()
    payload["origin"] = "browser_bridge"
    payload["source_ref"] = "opera:chatgpt:selected-answer"
    payload["allowed_files"] = [
        ".env.example",
    ]
    payload["checks"] = [
        {
            "type": "git_diff_check",
        },
        {
            "type": "pipeline",
            "flow": "check",
        },
    ]
    result = validate_developer_task_manifest(payload)

    check(
        "BROWSER BRIDGE TASK IS ALLOWED",
        {
            "ok": result.ok,
            "origin": result.manifest.origin if result.manifest else None,
            "allowed_files": list(result.manifest.allowed_files) if result.manifest else None,
        },
        {
            "ok": True,
            "origin": "browser_bridge",
            "allowed_files": [
                ".env.example",
            ],
        },
    )

    payload = _valid_manifest()
    payload["origin"] = "teacher_api"

    check(
        "TEACHER API ORIGIN IS REJECTED",
        _issue_presence(payload, ("unsupported_origin",)),
        {
            "ok": False,
            "contains": {
                "unsupported_origin": True,
            },
        },
    )

    payload = _valid_manifest()
    del payload["title"]
    payload["command"] = "Remove-Item C:\\Project\\SkynetVS"

    check(
        "UNKNOWN AND MISSING FIELDS ARE REJECTED",
        _issue_presence(
            payload,
            (
                "missing_field",
                "unknown_field",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "missing_field": True,
                "unknown_field": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["allowed_files"] = [
        "../main.py",
        "C:/temp/file.py",
        "modules\\bad.py",
    ]

    check(
        "UNSAFE PATH FORMS ARE REJECTED",
        _issue_presence(
            payload,
            (
                "path_traversal",
                "absolute_path",
                "backslash_path",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "path_traversal": True,
                "absolute_path": True,
                "backslash_path": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["allowed_files"] = [
        ".env",
        "models/model.bin",
        "data/logs/runtime.jsonl",
        "tools/pipeline.py",
        "modules/developer_executor.py",
        "scripts/install.ps1",
    ]

    check(
        "FORBIDDEN AND PROTECTED PATHS ARE REJECTED",
        _issue_presence(
            payload,
            (
                "forbidden_path",
                "protected_path",
                "forbidden_file_type",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "forbidden_path": True,
                "protected_path": True,
                "forbidden_file_type": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["allowed_files"] = [
        "modules/CON.py",
        "modules/bad?.py",
        "modules/name.",
    ]

    check(
        "WINDOWS UNSAFE PATHS ARE REJECTED",
        _issue_presence(
            payload,
            (
                "windows_reserved_path",
                "windows_unsafe_path",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "windows_reserved_path": True,
                "windows_unsafe_path": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["allowed_files"] = [
        "modules/Example.py",
        "modules/example.py",
    ]

    check(
        "CASE INSENSITIVE DUPLICATE PATH IS REJECTED",
        _issue_presence(payload, ("duplicate_allowed_file",)),
        {
            "ok": False,
            "contains": {
                "duplicate_allowed_file": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["checks"] = [
        {
            "type": "shell",
            "command": "Remove-Item C:\\Project\\SkynetVS -Recurse",
        },
        {
            "type": "pipeline",
            "flow": "check",
        },
    ]

    check(
        "ARBITRARY SHELL CHECK IS REJECTED",
        _issue_presence(
            payload,
            (
                "unsupported_check_type",
                "missing_git_diff_check",
                "missing_py_compile_check",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "unsupported_check_type": True,
                "missing_git_diff_check": True,
                "missing_py_compile_check": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["checks"] = [
        {
            "type": "git_diff_check",
        },
        {
            "type": "py_compile",
            "scope": "all_files",
        },
        {
            "type": "python_module",
            "module": "os.system",
        },
        {
            "type": "pipeline",
            "flow": "check; Remove-Item",
        },
        {
            "type": "pipeline",
            "flow": "check",
        },
    ]

    check(
        "INVALID TYPED CHECK PARAMETERS ARE REJECTED",
        _issue_presence(
            payload,
            (
                "invalid_check_scope",
                "invalid_python_module",
                "invalid_pipeline_flow",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "invalid_check_scope": True,
                "invalid_python_module": True,
                "invalid_pipeline_flow": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["checks"] = [
        {
            "type": "pipeline",
            "flow": "check",
        },
    ]

    check(
        "REQUIRED QUALITY CHECKS ARE ENFORCED",
        _issue_presence(
            payload,
            (
                "missing_git_diff_check",
                "missing_py_compile_check",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "missing_git_diff_check": True,
                "missing_py_compile_check": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["checks"] = [
        {
            "type": "git_diff_check",
        },
        {
            "type": "py_compile",
            "scope": "changed_python_files",
        },
        {
            "type": "pipeline",
            "flow": "check",
        },
        {
            "type": "python_module",
            "module": "tools.eval_example",
        },
    ]

    check(
        "FULL PIPELINE CHECK MUST BE LAST",
        _issue_presence(payload, ("full_pipeline_check_not_last",)),
        {
            "ok": False,
            "contains": {
                "full_pipeline_check_not_last": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["source_sha256"] = "A" * 64
    payload["patch_sha256"] = "z" * 64
    payload["base_commit"] = "HEAD"
    payload["patch_file"] = "../changes.patch"

    check(
        "HASH COMMIT AND PATCH FILE FORMATS ARE STRICT",
        _issue_presence(
            payload,
            (
                "invalid_sha256",
                "invalid_base_commit",
                "invalid_patch_file",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "invalid_sha256": True,
                "invalid_base_commit": True,
                "invalid_patch_file": True,
            },
        },
    )

    payload = _valid_manifest()
    payload["schema_version"] = 2
    payload["task_kind"] = "instruction"
    payload["project"] = "OtherProject"
    payload["install_policy"] = "automatic"

    check(
        "CORE CONTRACT VALUES ARE STRICT",
        _issue_presence(
            payload,
            (
                "unsupported_schema_version",
                "unsupported_task_kind",
                "invalid_project",
                "invalid_install_policy",
            ),
        ),
        {
            "ok": False,
            "contains": {
                "unsupported_schema_version": True,
                "unsupported_task_kind": True,
                "invalid_project": True,
                "invalid_install_policy": True,
            },
        },
    )

    result = validate_developer_task_manifest([])

    check(
        "NON OBJECT MANIFEST IS REJECTED",
        {
            "ok": result.ok,
            "issue_codes": list(result.issue_codes),
        },
        {
            "ok": False,
            "issue_codes": [
                "invalid_type",
            ],
        },
    )

    payload = _valid_manifest()
    payload["origin"] = "teacher_api"
    raised = False
    error_codes: list[str] = []

    try:
        require_valid_developer_task_manifest(payload)
    except DeveloperTaskValidationError as error:
        raised = True
        error_codes = [
            item.code
            for item in error.issues
        ]

    check(
        "REQUIRE VALID RAISES STRUCTURED ERROR",
        {
            "raised": raised,
            "contains_unsupported_origin": "unsupported_origin" in error_codes,
        },
        {
            "raised": True,
            "contains_unsupported_origin": True,
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