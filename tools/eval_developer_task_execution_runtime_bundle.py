from __future__ import annotations

import hashlib
import inspect
import io
import json
import os
import stat
import tempfile
import warnings
import zipfile

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_runtime_bundle as runtime_bundle_module

from modules.developer.developer_task_execution_runtime_bundle import (
    DeveloperTaskPythonRuntimeBundleError,
    DeveloperTaskPythonRuntimeBundleFile,
    _build_runtime_manifest_bytes,
    _canonical_json_bytes,
    _cleanup_staging_root,
    _create_staging_root,
    _inspect_zip_infos,
    _payload,
    _scan_flat_regular_files,
    _stage_and_verify_payloads,
    _validate_artifact_parent,
    _validate_zip_path,
    _verify_staging_tree,
    build_developer_task_execution_runtime_bundle,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    RUNTIME_LOCKED_PTH_BYTES,
    RUNTIME_LOCKED_PTH_FILE_NAME,
    RUNTIME_LOCKED_PTH_SHA256,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PROBE_BYTES,
    RUNTIME_PROBE_FILE_NAME,
    RUNTIME_PROBE_SHA256,
    RUNTIME_RUNNER_BYTES,
    RUNTIME_RUNNER_FILE_NAME,
    RUNTIME_RUNNER_SHA256,
    RUNTIME_SOURCE_FILE_NAME,
    RUNTIME_SOURCE_FILES,
    RUNTIME_SOURCE_FINGERPRINT,
    RUNTIME_SOURCE_OUTER_ENTRY_COUNT,
    RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
    RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
    RUNTIME_TREE_MANIFEST_SHA256,
    TRUSTED_PYTHON_RUNTIME_POLICY_V1,
    runtime_launch_contract,
    runtime_launch_contract_fingerprint,
    validate_trusted_python_runtime_policy,
)


def _error_code(callable_: Any) -> str:
    try:
        callable_()
    except DeveloperTaskPythonRuntimeBundleError as exc:
        return exc.code
    return ""


def _zip_bytes(entries: list[tuple[zipfile.ZipInfo | str, bytes]], *, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return stream.getvalue()


def _manifest_payload_files() -> tuple[DeveloperTaskPythonRuntimeBundleFile, ...]:
    payloads: list[DeveloperTaskPythonRuntimeBundleFile] = []
    for item in RUNTIME_SOURCE_FILES:
        if item.path == RUNTIME_LOCKED_PTH_FILE_NAME:
            continue
        payloads.append(
            DeveloperTaskPythonRuntimeBundleFile(
                path=item.path,
                kind="source",
                size_bytes=item.size_bytes,
                sha256=item.sha256,
                _bytes=b"",
            )
        )
    payloads.extend(
        (
            _payload("locked_runtime_path", RUNTIME_LOCKED_PTH_FILE_NAME, RUNTIME_LOCKED_PTH_BYTES),
            _payload("trusted_probe", RUNTIME_PROBE_FILE_NAME, RUNTIME_PROBE_BYTES),
            _payload("trusted_runner", RUNTIME_RUNNER_FILE_NAME, RUNTIME_RUNNER_BYTES),
        )
    )
    return tuple(sorted(payloads, key=lambda item: item.path))


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

    policy = TRUSTED_PYTHON_RUNTIME_POLICY_V1
    validate_trusted_python_runtime_policy(policy)

    check(
        "V1B4B PINNED RUNTIME POLICY SELF CHECKS",
        {
            "ok": policy.ok,
            "fingerprint": policy.fingerprint,
            "source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
            "source_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
            "source_entries": len(policy.source_files),
            "execution_authorized": policy.to_dict()["behavior"]["execution_authorized"],
        },
        {
            "ok": True,
            "fingerprint": RUNTIME_BUNDLE_POLICY_FINGERPRINT,
            "source_fingerprint": "6027ca87d35d94fa131d64c8210e5c6f5002f801274752421e480a9a180dba45",
            "source_policy_fingerprint": "232d65ce4fdb9d990e588f15133db3593cb69f31c5d4e3dfece28b79b827c503",
            "source_entries": RUNTIME_SOURCE_OUTER_ENTRY_COUNT,
            "execution_authorized": False,
        },
    )

    check(
        "V1B4B PUBLIC BUILDER ACCEPTS ONLY SOURCE PATH AND ARTIFACT PARENT",
        {
            name: {
                "kind": parameter.kind.name,
                "default": None if parameter.default is inspect.Parameter.empty else str(parameter.default),
            }
            for name, parameter in inspect.signature(build_developer_task_execution_runtime_bundle).parameters.items()
        },
        {
            "runtime_zip": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "artifact_parent": {"kind": "KEYWORD_ONLY", "default": None},
        },
    )

    check(
        "V1B4B SOURCE IDENTITY IS LOCKED TO CPYTHON 3.13.15",
        {
            "file_name": policy.to_dict()["source"]["file_name"],
            "sha256": policy.to_dict()["source"]["sha256"],
            "outer_manifest": policy.to_dict()["source"]["outer_manifest_sha256"],
            "stdlib_manifest": policy.to_dict()["source"]["stdlib_manifest_sha256"],
        },
        {
            "file_name": RUNTIME_SOURCE_FILE_NAME,
            "sha256": RUNTIME_SOURCE_SHA256,
            "outer_manifest": RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
            "stdlib_manifest": RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
        },
    )

    check(
        "V1B4B PROJECT OWNED RUNTIME PAYLOAD HASHES ARE LOCKED",
        {
            "pth": hashlib.sha256(RUNTIME_LOCKED_PTH_BYTES).hexdigest(),
            "probe": hashlib.sha256(RUNTIME_PROBE_BYTES).hexdigest(),
            "runner": hashlib.sha256(RUNTIME_RUNNER_BYTES).hexdigest(),
        },
        {
            "pth": RUNTIME_LOCKED_PTH_SHA256,
            "probe": RUNTIME_PROBE_SHA256,
            "runner": RUNTIME_RUNNER_SHA256,
        },
    )

    check(
        "V1B4B LOCKED PTH IS MINIMAL AND SITE FREE",
        {
            "bytes": RUNTIME_LOCKED_PTH_BYTES.decode("ascii").splitlines(),
            "import_site": b"import site" in RUNTIME_LOCKED_PTH_BYTES.lower(),
            "crlf_only": (
                RUNTIME_LOCKED_PTH_BYTES.count(b"\n") == RUNTIME_LOCKED_PTH_BYTES.count(b"\r\n")
                and RUNTIME_LOCKED_PTH_BYTES.count(b"\r") == RUNTIME_LOCKED_PTH_BYTES.count(b"\r\n")
            ),
        },
        {
            "bytes": ["python313.zip", "."],
            "import_site": False,
            "crlf_only": True,
        },
    )

    launch = runtime_launch_contract()
    check(
        "V1B4B LAUNCH CONTRACT IS FIXED AND CALLER FREE",
        {
            "fingerprint": runtime_launch_contract_fingerprint(),
            "mode": launch["mode"],
            "application": launch["application_file_name"],
            "flags": launch["flags"],
            "runner": launch["runner_file_name"],
            "shell": launch["shell"],
            "caller_arguments": launch["caller_arguments"],
            "caller_environment": launch["caller_environment"],
        },
        {
            "fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
            "mode": "runtime_probe",
            "application": "python.exe",
            "flags": ["-I", "-S", "-B", "-E", "-s", "-P", "-X", "utf8"],
            "runner": RUNTIME_RUNNER_FILE_NAME,
            "shell": False,
            "caller_arguments": False,
            "caller_environment": False,
        },
    )

    payloads = _manifest_payload_files()
    runtime_manifest = _build_runtime_manifest_bytes(payloads, policy)
    check(
        "V1B4B RUNTIME MANIFEST IS CANONICAL AND LOCKED",
        {
            "sha256": hashlib.sha256(runtime_manifest).hexdigest(),
            "final_lf": runtime_manifest.endswith(b"\n"),
            "contains_absolute_host_path": b"C:\\\\" in runtime_manifest or b"/mnt/" in runtime_manifest,
            "execution_authorized": json.loads(runtime_manifest)["execution_authorized"],
        },
        {
            "sha256": RUNTIME_MANIFEST_SHA256,
            "final_lf": True,
            "contains_absolute_host_path": False,
            "execution_authorized": False,
        },
    )

    tree_rows = [
        {"path": item.path, "size_bytes": item.size_bytes, "sha256": item.sha256}
        for item in payloads
    ] + [
        {
            "path": "runtime_manifest.json",
            "size_bytes": len(runtime_manifest),
            "sha256": hashlib.sha256(runtime_manifest).hexdigest(),
        }
    ]
    tree_rows.sort(key=lambda item: item["path"])
    check(
        "V1B4B DERIVED TREE IDENTITY IS LOCKED",
        {
            "file_count": len(tree_rows),
            "total_bytes": sum(item["size_bytes"] for item in tree_rows),
            "tree_manifest": hashlib.sha256(_canonical_json_bytes(tree_rows)).hexdigest(),
            "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        },
        {
            "file_count": RUNTIME_BUNDLE_FILE_COUNT,
            "total_bytes": RUNTIME_BUNDLE_TOTAL_BYTES,
            "tree_manifest": RUNTIME_TREE_MANIFEST_SHA256,
            "bundle_fingerprint": "1c98ad24ec3e4bb1b8b4bcd530ffedcf6ff62a6fee5b94cb795f6c84fb1c8c4b",
        },
    )

    immutable = False
    try:
        payloads[-1].path = "mutated"  # type: ignore[misc]
    except FrozenInstanceError:
        immutable = True
    check("V1B4B BUNDLE FILE EVIDENCE IS IMMUTABLE", immutable, True)

    serialized = payloads[-1].to_dict()
    check(
        "V1B4B SERIALIZATION HIDES EXACT RUNTIME BYTES",
        {
            "bytes_field": "_bytes" in serialized,
            "source_in_repr": "Fixed V1B4" in repr(payloads[-1]),
        },
        {"bytes_field": False, "source_in_repr": False},
    )

    check(
        "V1B4B ZIP PATH POLICY REJECTS UNSAFE FORMS",
        {
            "traversal": _error_code(lambda: _validate_zip_path("../evil", label="test_zip", allow_nested=True)),
            "absolute": _error_code(lambda: _validate_zip_path("/evil", label="test_zip", allow_nested=True)),
            "drive": _error_code(lambda: _validate_zip_path("C:/evil", label="test_zip", allow_nested=True)),
            "backslash": _error_code(lambda: _validate_zip_path(r"a\\b", label="test_zip", allow_nested=True)),
            "ads": _error_code(lambda: _validate_zip_path("file:evil", label="test_zip", allow_nested=True)),
            "reserved": _error_code(lambda: _validate_zip_path("CON.txt", label="test_zip", allow_nested=True)),
            "nested_outer": _error_code(lambda: _validate_zip_path("a/b", label="test_zip", allow_nested=False)),
        },
        {
            "traversal": "test_zip_path_traversal",
            "absolute": "test_zip_absolute_path",
            "drive": "test_zip_absolute_path",
            "backslash": "test_zip_backslash_path",
            "ads": "test_zip_alternate_stream_path",
            "reserved": "test_zip_windows_reserved_path",
            "nested_outer": "test_zip_nested_path",
        },
    )

    duplicate_stream = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(duplicate_stream, "w") as archive:
            archive.writestr("same.txt", b"a")
            archive.writestr("same.txt", b"b")
    with zipfile.ZipFile(io.BytesIO(duplicate_stream.getvalue())) as archive:
        duplicate_code = _error_code(
            lambda: _inspect_zip_infos(
                archive,
                label="test_zip",
                max_entries=10,
                max_total_bytes=1024,
                max_entry_bytes=1024,
                allow_nested=False,
            )
        )
    check("V1B4B DUPLICATE ZIP PATH IS REJECTED", duplicate_code, "test_zip_duplicate_path")

    case_bytes = _zip_bytes([("Foo.txt", b"a"), ("foo.TXT", b"b")])
    with zipfile.ZipFile(io.BytesIO(case_bytes)) as archive:
        case_code = _error_code(
            lambda: _inspect_zip_infos(
                archive,
                label="test_zip",
                max_entries=10,
                max_total_bytes=1024,
                max_entry_bytes=1024,
                allow_nested=False,
            )
        )
    check("V1B4B WINDOWS CASE COLLISION IS REJECTED", case_code, "test_zip_case_collision")

    symlink_info = zipfile.ZipInfo("link")
    symlink_info.create_system = 3
    symlink_info.external_attr = (stat.S_IFLNK | 0o777) << 16
    symlink_bytes = _zip_bytes([(symlink_info, b"target")], compression=zipfile.ZIP_STORED)
    with zipfile.ZipFile(io.BytesIO(symlink_bytes)) as archive:
        symlink_code = _error_code(
            lambda: _inspect_zip_infos(
                archive,
                label="test_zip",
                max_entries=10,
                max_total_bytes=1024,
                max_entry_bytes=1024,
                allow_nested=False,
            )
        )
    check("V1B4B SYMLINK ZIP ENTRY IS REJECTED", symlink_code, "test_zip_symlink_entry")

    bzip_bytes = _zip_bytes([("file.txt", b"payload")], compression=zipfile.ZIP_BZIP2)
    with zipfile.ZipFile(io.BytesIO(bzip_bytes)) as archive:
        compression_code = _error_code(
            lambda: _inspect_zip_infos(
                archive,
                label="test_zip",
                max_entries=10,
                max_total_bytes=1024,
                max_entry_bytes=1024,
                allow_nested=False,
            )
        )
    check("V1B4B UNAPPROVED ZIP COMPRESSION IS REJECTED", compression_code, "test_zip_compression_invalid")

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1b4b-eval-") as temp:
        root = Path(temp)
        parent = root / "artifacts"
        parent.mkdir()
        validated_parent = _validate_artifact_parent(parent)
        check("V1B4B REGULAR ARTIFACT PARENT IS ACCEPTED", validated_parent, parent)

        missing_parent = root / "missing"
        check(
            "V1B4B MISSING ARTIFACT PARENT IS STRUCTURED",
            _error_code(lambda: _validate_artifact_parent(missing_parent)),
            "runtime_artifact_parent_missing",
        )

        file_parent = root / "not-a-directory"
        file_parent.write_bytes(b"x")
        check(
            "V1B4B FILE ARTIFACT PARENT IS REJECTED",
            _error_code(lambda: _validate_artifact_parent(file_parent)),
            "runtime_artifact_parent_not_directory",
        )

        small_payloads = (
            _payload("test", "a.bin", b"alpha"),
            _payload("test", "b.bin", b"beta"),
        )
        readback = _stage_and_verify_payloads(parent, small_payloads)
        check(
            "V1B4B FRESH STAGING WRITES REREADS AND CLEANS",
            {
                "names": [item.path for item in readback],
                "bytes": [item.exact_bytes().decode("ascii") for item in readback],
                "leftovers": sorted(path.name for path in parent.iterdir()),
            },
            {
                "names": ["a.bin", "b.bin"],
                "bytes": ["alpha", "beta"],
                "leftovers": [],
            },
        )

        fixed_token = "ab" * 12
        collision_root = parent / f"skynetvs-runtime-bundle-{fixed_token}"
        collision_root.mkdir()
        with patch.object(runtime_bundle_module.secrets, "token_hex", return_value=fixed_token):
            collision_code = _error_code(lambda: _create_staging_root(parent))
        collision_root.rmdir()
        check("V1B4B PREEXISTING STAGING ROOT FAILS CLOSED", collision_code, "runtime_bundle_root_exists")

        original_write = runtime_bundle_module._write_exclusive_file
        write_calls = 0

        def fail_second_write(path: Path, data: bytes) -> None:
            nonlocal write_calls
            write_calls += 1
            if write_calls == 2:
                raise DeveloperTaskPythonRuntimeBundleError(
                    "synthetic_write_failed",
                    "synthetic",
                )
            original_write(path, data)

        with patch.object(runtime_bundle_module, "_write_exclusive_file", side_effect=fail_second_write):
            write_failure_code = _error_code(lambda: _stage_and_verify_payloads(parent, small_payloads))
        check(
            "V1B4B PARTIAL WRITE FAILURE CLEANS STAGING",
            {
                "code": write_failure_code,
                "leftovers": sorted(path.name for path in parent.iterdir()),
            },
            {"code": "synthetic_write_failed", "leftovers": []},
        )

        with patch.object(
            runtime_bundle_module,
            "_verify_staging_tree",
            side_effect=DeveloperTaskPythonRuntimeBundleError("synthetic_verify_failed", "synthetic"),
        ):
            verify_failure_code = _error_code(lambda: _stage_and_verify_payloads(parent, small_payloads))
        check(
            "V1B4B POST WRITE VERIFICATION FAILURE CLEANS STAGING",
            {
                "code": verify_failure_code,
                "leftovers": sorted(path.name for path in parent.iterdir()),
            },
            {"code": "synthetic_verify_failed", "leftovers": []},
        )

        staging = _create_staging_root(parent)
        try:
            for item in small_payloads:
                runtime_bundle_module._write_exclusive_file(staging / item.path, item.exact_bytes())
            (staging / "a.bin").write_bytes(b"omega")
            mutation_code = _error_code(lambda: _verify_staging_tree(staging, small_payloads))
        finally:
            _cleanup_staging_root(staging)
        check("V1B4B POST WRITE MUTATION IS REJECTED", mutation_code, "runtime_bundle_post_write_mismatch")

        staging = _create_staging_root(parent)
        try:
            for item in small_payloads:
                runtime_bundle_module._write_exclusive_file(staging / item.path, item.exact_bytes())
            (staging / "extra.bin").write_bytes(b"x")
            extra_code = _error_code(lambda: _verify_staging_tree(staging, small_payloads))
        finally:
            _cleanup_staging_root(staging)
        check("V1B4B EXTRA STAGING FILE IS REJECTED", extra_code, "runtime_bundle_file_set_mismatch")

        staging = _create_staging_root(parent)
        try:
            (staging / "nested").mkdir()
            non_regular_code = _error_code(lambda: _scan_flat_regular_files(staging))
            (staging / "nested").rmdir()
        finally:
            _cleanup_staging_root(staging)
        check("V1B4B STAGING DIRECTORIES ARE REJECTED", non_regular_code, "runtime_bundle_non_regular_entry")

        fake_source = root / RUNTIME_SOURCE_FILE_NAME
        fake_source.write_bytes(_zip_bytes([("fake.txt", b"x")]))
        public_code = _error_code(
            lambda: build_developer_task_execution_runtime_bundle(
                fake_source,
                artifact_parent=parent,
            )
        )
        check("V1B4B PUBLIC BUILDER REJECTS NONPINNED SOURCE BYTES", public_code, "runtime_source_identity_mismatch")

    type_runtime = False
    try:
        build_developer_task_execution_runtime_bundle("runtime.zip", artifact_parent=Path("."))  # type: ignore[arg-type]
    except TypeError:
        type_runtime = True
    check("V1B4B PUBLIC BUILDER REJECTS STRING SOURCE PATH", type_runtime, True)

    type_parent = False
    try:
        build_developer_task_execution_runtime_bundle(Path(RUNTIME_SOURCE_FILE_NAME), artifact_parent=".")  # type: ignore[arg-type]
    except TypeError:
        type_parent = True
    check("V1B4B PUBLIC BUILDER REJECTS STRING ARTIFACT PARENT", type_parent, True)

    wrong_name_code = _error_code(
        lambda: build_developer_task_execution_runtime_bundle(
            Path("wrong-name.zip"),
            artifact_parent=Path("."),
        )
    )
    check("V1B4B WRONG SOURCE FILE NAME FAILS BEFORE FILE READ", wrong_name_code, "runtime_source_name_mismatch")

    module_source = inspect.getsource(runtime_bundle_module)
    check(
        "V1B4B PRODUCTION BUILDER HAS NO EXECUTION OR INSTALL SURFACE",
        {
            "subprocess_import": "import subprocess" in module_source,
            "popen": "Popen(" in module_source,
            "os_system": "os.system(" in module_source,
            "shell_true": "shell=True" in module_source,
            "zip_extract": ".extract(" in module_source or ".extractall(" in module_source,
            "pip_install": "pip install" in module_source,
            "python_launch": "python.exe" in module_source and "subprocess" in module_source,
            "cleanup_path_exists_follow": "staging_root.exists()" in module_source or "root.exists()" in inspect.getsource(_cleanup_staging_root),
        },
        {
            "subprocess_import": False,
            "popen": False,
            "os_system": False,
            "shell_true": False,
            "zip_extract": False,
            "pip_install": False,
            "python_launch": False,
            "cleanup_path_exists_follow": False,
        },
    )

    check(
        "V1B4B TRUSTED PROBE AND RUNNER ARE FIXED BENIGN PAYLOADS",
        {
            "probe_subprocess": b"subprocess" in RUNTIME_PROBE_BYTES,
            "probe_socket": b"socket" in RUNTIME_PROBE_BYTES,
            "runner_subprocess": b"subprocess" in RUNTIME_RUNNER_BYTES,
            "runner_shell": b"shell" in RUNTIME_RUNNER_BYTES,
            "probe_exec": b"exec(" in RUNTIME_PROBE_BYTES or b"eval(" in RUNTIME_PROBE_BYTES,
            "runner_exec": b"exec(" in RUNTIME_RUNNER_BYTES or b"eval(" in RUNTIME_RUNNER_BYTES,
            "probe_environment_values": b"python_environment\": python_environment" in RUNTIME_PROBE_BYTES,
            "probe_environment_keys": b"python_environment_keys" in RUNTIME_PROBE_BYTES,
        },
        {
            "probe_subprocess": False,
            "probe_socket": False,
            "runner_subprocess": False,
            "runner_shell": False,
            "probe_exec": False,
            "runner_exec": False,
            "probe_environment_values": False,
            "probe_environment_keys": True,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
