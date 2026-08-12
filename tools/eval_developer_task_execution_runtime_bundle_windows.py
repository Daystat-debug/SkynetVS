from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_runtime_bundle import (
    build_developer_task_execution_runtime_bundle,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    RUNTIME_LOCKED_PTH_FILE_NAME,
    RUNTIME_LOCKED_PTH_SHA256,
    RUNTIME_MANIFEST_FILE_NAME,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PROBE_FILE_NAME,
    RUNTIME_PROBE_SHA256,
    RUNTIME_RUNNER_FILE_NAME,
    RUNTIME_RUNNER_SHA256,
    RUNTIME_SOURCE_FILE_NAME,
    RUNTIME_SOURCE_FINGERPRINT,
    RUNTIME_SOURCE_OUTER_ENTRY_COUNT,
    RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
    RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    RUNTIME_SOURCE_PYTHON_DLL_SHA256,
    RUNTIME_SOURCE_PYTHON_EXE_SHA256,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
    RUNTIME_SOURCE_STDLIB_SHA256,
    RUNTIME_TREE_MANIFEST_SHA256,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _runtime_source_path() -> Path:
    override = os.environ.get("SKYNETVS_V1B4_RUNTIME_ZIP", "").strip()
    if override:
        return Path(override)
    return (
        Path.home()
        / "Downloads"
        / "SkynetVS_V1B4A_Runtime_Source_3_13_15"
        / RUNTIME_SOURCE_FILE_NAME
    )


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        if not ok:
            fail_count += 1
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    if sys.platform != "win32":
        print("[SKIP] V1B4B deterministic runtime bundle Windows smoke requires win32.")
        return 0

    runtime_zip = _runtime_source_path()
    if not runtime_zip.is_file():
        print(f"[FAIL] Pinned V1B4A CPython source ZIP is missing: {runtime_zip}")
        return 1

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1b4b-windows-") as temp_dir:
        artifact_parent = Path(temp_dir)
        first = build_developer_task_execution_runtime_bundle(
            runtime_zip,
            artifact_parent=artifact_parent,
        )
        second = build_developer_task_execution_runtime_bundle(
            runtime_zip,
            artifact_parent=artifact_parent,
        )

        report = first.report
        check(
            "V1B4B REAL CPYTHON SOURCE BUILDS DETERMINISTIC CAPABILITY",
            {
                "ok": first.ok,
                "source_entry_count": report.source_entry_count,
                "source_outer_manifest": report.source_outer_manifest_sha256,
                "source_stdlib_manifest": report.source_stdlib_manifest_sha256,
                "bundle_file_count": report.bundle_file_count,
                "bundle_total_bytes": report.bundle_total_bytes,
                "tree_manifest": report.tree_manifest_sha256,
                "bundle_fingerprint": report.bundle_fingerprint,
                "staging_cleaned": report.staging_cleaned,
                "interpreter_executed": report.interpreter_executed,
                "execution_authorized": report.execution_authorized,
            },
            {
                "ok": True,
                "source_entry_count": RUNTIME_SOURCE_OUTER_ENTRY_COUNT,
                "source_outer_manifest": RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
                "source_stdlib_manifest": RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
                "bundle_file_count": RUNTIME_BUNDLE_FILE_COUNT,
                "bundle_total_bytes": RUNTIME_BUNDLE_TOTAL_BYTES,
                "tree_manifest": RUNTIME_TREE_MANIFEST_SHA256,
                "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
                "staging_cleaned": True,
                "interpreter_executed": False,
                "execution_authorized": False,
            },
        )

        check(
            "V1B4B REAL SOURCE AND POLICY IDENTITIES REMAIN PINNED",
            {
                "source_sha256": report.source_sha256,
                "source_fingerprint": report.source_fingerprint,
                "source_policy_fingerprint": report.source_policy_fingerprint,
                "bundle_policy_fingerprint": report.bundle_policy_fingerprint,
                "launch_contract_fingerprint": report.launch_contract_fingerprint,
            },
            {
                "source_sha256": RUNTIME_SOURCE_SHA256,
                "source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
                "source_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
                "bundle_policy_fingerprint": RUNTIME_BUNDLE_POLICY_FINGERPRINT,
                "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
            },
        )

        check(
            "V1B4B REAL BUNDLE EXACT FILE BYTES ARE PINNED",
            {
                "python_exe": _sha256(first.exact_file_bytes("python.exe")),
                "python_dll": _sha256(first.exact_file_bytes("python313.dll")),
                "stdlib": _sha256(first.exact_file_bytes("python313.zip")),
                "pth": _sha256(first.exact_file_bytes(RUNTIME_LOCKED_PTH_FILE_NAME)),
                "probe": _sha256(first.exact_file_bytes(RUNTIME_PROBE_FILE_NAME)),
                "runner": _sha256(first.exact_file_bytes(RUNTIME_RUNNER_FILE_NAME)),
                "manifest": _sha256(first.exact_file_bytes(RUNTIME_MANIFEST_FILE_NAME)),
            },
            {
                "python_exe": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
                "python_dll": RUNTIME_SOURCE_PYTHON_DLL_SHA256,
                "stdlib": RUNTIME_SOURCE_STDLIB_SHA256,
                "pth": RUNTIME_LOCKED_PTH_SHA256,
                "probe": RUNTIME_PROBE_SHA256,
                "runner": RUNTIME_RUNNER_SHA256,
                "manifest": RUNTIME_MANIFEST_SHA256,
            },
        )

        runtime_manifest = json.loads(
            first.exact_file_bytes(RUNTIME_MANIFEST_FILE_NAME).decode("utf-8")
        )
        check(
            "V1B4B RUNTIME MANIFEST CONTAINS NO HOST PATH OR AUTHORIZATION",
            {
                "bundle_id": runtime_manifest["bundle_id"],
                "execution_authorized": runtime_manifest["execution_authorized"],
                "payload_count": len(runtime_manifest["payload_files"]),
                "host_temp_path_present": str(artifact_parent).encode("utf-8") in first.exact_file_bytes(RUNTIME_MANIFEST_FILE_NAME),
            },
            {
                "bundle_id": report.bundle_id,
                "execution_authorized": False,
                "payload_count": RUNTIME_BUNDLE_FILE_COUNT - 1,
                "host_temp_path_present": False,
            },
        )

        check(
            "V1B4B REPEATED REAL BUILDS HAVE IDENTICAL NONSERIALIZED CAPABILITIES",
            {
                "metadata": first.to_dict() == second.to_dict(),
                "file_names": first.file_names == second.file_names,
                "exact_bytes": all(
                    first.exact_file_bytes(name) == second.exact_file_bytes(name)
                    for name in first.file_names
                ),
                "artifact_parent_empty": list(artifact_parent.iterdir()) == [],
            },
            {
                "metadata": True,
                "file_names": True,
                "exact_bytes": True,
                "artifact_parent_empty": True,
            },
        )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
