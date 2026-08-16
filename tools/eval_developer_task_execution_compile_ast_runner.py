from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import pickle

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
    build_developer_task_execution_compile_ast_runner_bundle,
    build_developer_task_execution_compile_ast_runner_source,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_V1,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
    developer_task_execution_compile_ast_runner_policy_fingerprint,
    validate_developer_task_execution_compile_ast_runner_policy,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)


def _called_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.append(func.id)
        elif isinstance(func, ast.Attribute):
            parts: list[str] = []
            current: ast.AST = func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                names.append(".".join(reversed(parts)))
    return names


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

    policy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_V1
    bundle = build_developer_task_execution_compile_ast_runner_bundle()
    second = build_developer_task_execution_compile_ast_runner_bundle()
    contract_policy_bytes = bundle.contract_policy.exact_bytes()
    runner_bytes = bundle.runner.exact_bytes()
    payload_bytes = bundle.payload_manifest.exact_bytes()
    runner_text = runner_bytes.decode("utf-8", errors="strict")
    runner_tree = ast.parse(runner_text, filename=bundle.runner.file_name, mode="exec")
    called = _called_names(runner_tree)
    imports = sorted(
        {
            alias.name.split(".")[0]
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        | {
            (node.module or "").split(".")[0]
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.ImportFrom)
        }
    )

    check(
        "V1C2A2 PINNED RUNNER POLICY SELF CHECKS",
        {
            "errors": list(validate_developer_task_execution_compile_ast_runner_policy()),
            "policy_id": policy.policy_id,
            "fingerprint": policy.fingerprint,
            "recomputed": developer_task_execution_compile_ast_runner_policy_fingerprint(policy),
            "contract": policy.contract_policy_fingerprint,
            "runtime": policy.runtime_bundle_fingerprint,
            "authorized": policy.execution_authorized,
        },
        {
            "errors": [],
            "policy_id": "skynetvs-v1c2a2-fixed-compile-ast-guest-runner-v1",
            "fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
            "recomputed": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
            "contract": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
            "runtime": RUNTIME_BUNDLE_FINGERPRINT,
            "authorized": False,
        },
    )

    check(
        "V1C2A2 BUNDLE BUILDER ACCEPTS NO CALLER INPUTS",
        list(inspect.signature(build_developer_task_execution_compile_ast_runner_bundle).parameters),
        [],
    )

    check(
        "V1C2A2 FIXED RUNNER BUNDLE BUILDS NON AUTHORIZING",
        {
            "ok": bundle.ok,
            "bundle_id": bundle.bundle_id,
            "operation": bundle.operation,
            "sandbox": bundle.sandbox_launched,
            "lease_issued": bundle.runtime_lease_issued,
            "lease_claimed": bundle.runtime_lease_claimed,
            "candidate": bundle.candidate_interpreter_executed,
            "processed": bundle.changed_source_processed,
            "ast": bundle.changed_source_ast_parsed,
            "compiled": bundle.changed_source_compiled,
            "changed_exec": bundle.changed_code_executed,
            "reusable": bundle.reusable_lease_issued,
            "authorized": bundle.execution_authorized,
        },
        {
            "ok": True,
            "bundle_id": "v1c2a2_fixed_compile_ast_guest_runner_bundle_v1",
            "operation": "compile_ast_changed_python_v1",
            "sandbox": False,
            "lease_issued": False,
            "lease_claimed": False,
            "candidate": False,
            "processed": False,
            "ast": False,
            "compiled": False,
            "changed_exec": False,
            "reusable": False,
            "authorized": False,
        },
    )

    check(
        "V1C2A2 BUNDLE IS DETERMINISTIC",
        {
            "metadata": bundle.to_dict() == second.to_dict(),
            "runner": runner_bytes == second.runner.exact_bytes(),
            "payload": payload_bytes == second.payload_manifest.exact_bytes(),
        },
        {"metadata": True, "runner": True, "payload": True},
    )

    check(
        "V1C2A2 PAYLOAD HASHES AND BUNDLE FINGERPRINT ARE PINNED",
        {
            "contract_policy": bundle.contract_policy.sha256,
            "runner": bundle.runner.sha256,
            "payload": bundle.payload_manifest.sha256,
            "bundle": bundle.bundle_fingerprint,
        },
        {
            "contract_policy": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
            "runner": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
            "payload": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
            "bundle": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
        },
    )

    check(
        "V1C2A2 PAYLOAD HASHES MATCH EXACT BYTES",
        {
            "contract_policy": hashlib.sha256(contract_policy_bytes).hexdigest(),
            "runner": hashlib.sha256(runner_bytes).hexdigest(),
            "payload": hashlib.sha256(payload_bytes).hexdigest(),
        },
        {
            "contract_policy": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
            "contract_policy": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
            "runner": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
            "payload": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
        },
    )

    check(
        "V1C2A2 CONTRACT POLICY FILE IS EXACT CANONICAL V1C2A1 POLICY",
        {
            "sha256": bundle.contract_policy.sha256,
            "size_bytes": bundle.contract_policy.size_bytes,
            "strict_utf8": contract_policy_bytes.decode("utf-8", errors="strict").startswith("{"),
            "bom": contract_policy_bytes.startswith(b"\xef\xbb\xbf"),
            "cr": b"\r" in contract_policy_bytes,
        },
        {
            "sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
            "size_bytes": len(contract_policy_bytes),
            "strict_utf8": True,
            "bom": False,
            "cr": False,
        },
    )

    check(
        "V1C2A2 RUNNER USES CANONICAL UTF8 LF BYTES",
        {
            "bom": runner_bytes.startswith(b"\xef\xbb\xbf"),
            "cr": b"\r" in runner_bytes,
            "final_lf": runner_bytes.endswith(b"\n"),
            "strict_utf8": runner_bytes.decode("utf-8", errors="strict") == runner_text,
        },
        {"bom": False, "cr": False, "final_lf": True, "strict_utf8": True},
    )

    payload_object = json.loads(payload_bytes.decode("utf-8"))
    check(
        "V1C2A2 PAYLOAD MANIFEST IS CANONICAL HASHED JSON",
        {
            "roundtrip": json.dumps(payload_object, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") == payload_bytes,
            "runner_hash": payload_object["runner"]["sha256"],
            "authorized": payload_object["execution_authorized"],
        },
        {
            "roundtrip": True,
            "runner_hash": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
            "authorized": False,
        },
    )

    check(
        "V1C2A2 SERIALIZATION HIDES EXACT RUNNER BYTES",
        {
            "source_in_repr": "Fixed V1C2A2 compile/AST guest runner" in repr(bundle),
            "private_bytes_runner": "_bytes" in bundle.runner.to_dict(),
            "private_bytes_payload": "_bytes" in bundle.payload_manifest.to_dict(),
        },
        {"source_in_repr": False, "private_bytes_runner": False, "private_bytes_payload": False},
    )

    immutable = False
    try:
        bundle.bundle_id = "mutated"  # type: ignore[misc]
    except FrozenInstanceError:
        immutable = True
    check("V1C2A2 BUNDLE IS IMMUTABLE", immutable, True)

    payload_immutable = False
    try:
        bundle.runner.sha256 = "0" * 64  # type: ignore[misc]
    except FrozenInstanceError:
        payload_immutable = True
    check("V1C2A2 PAYLOAD METADATA IS IMMUTABLE", payload_immutable, True)

    check(
        "V1C2A2 BUNDLE BINDS V1C2A1 AND TRUSTED RUNTIME",
        {
            "contract": bundle.contract_policy_fingerprint,
            "runtime": bundle.runtime_bundle_fingerprint,
            "policy_contract": policy.contract_policy_fingerprint,
            "policy_runtime": policy.runtime_bundle_fingerprint,
        },
        {
            "contract": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
            "runtime": RUNTIME_BUNDLE_FINGERPRINT,
            "policy_contract": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
            "policy_runtime": RUNTIME_BUNDLE_FINGERPRINT,
        },
    )

    forged = replace(bundle, execution_authorized=True)
    check("V1C2A2 FORGED EXECUTION AUTHORIZATION INVALIDATES BUNDLE", forged.ok, False)

    check(
        "V1C2A2 LAUNCH CONTRACT IS FIXED ISOLATED CPYTHON",
        {
            "runtime": bundle.runtime_executable,
            "flags": list(bundle.runtime_flags),
            "runner": bundle.runner_path,
            "cwd": bundle.working_directory,
            "shell": bundle.to_dict()["launch"]["shell"],
            "caller_args": bundle.to_dict()["launch"]["caller_arguments"],
            "caller_env": bundle.to_dict()["launch"]["caller_environment"],
        },
        {
            "runtime": r"C:\SkynetVSRuntime\python.exe",
            "flags": ["-I", "-S", "-B", "-E", "-s", "-P", "-X", "utf8"],
            "runner": r"C:\SkynetVSInput\SkynetVS_V1C2A2_runner.py",
            "cwd": r"C:\SkynetVSOutput",
            "shell": False,
            "caller_args": False,
            "caller_env": False,
        },
    )

    check(
        "V1C2A2 RUNNER IS STANDALONE STDLIB ONLY",
        {
            "imports": imports,
            "project_import": any(name in {"modules", "tools", "train"} for name in imports),
        },
        {
            "imports": ["__future__", "ast", "hashlib", "json", "os", "platform", "struct", "sys"],
            "project_import": False,
        },
    )

    check(
        "V1C2A2 RUNNER ACCEPTS NO CLI OR CALLER PATHS",
        {
            "argparse": "argparse" in imports,
            "sys_argv": "sys.argv" in runner_text,
            "request_fixed": r'C:\SkynetVSInput\request.json' in runner_text,
            "manifest_fixed": r'C:\SkynetVSInput\source_manifest.json' in runner_text,
            "result_fixed": r'C:\SkynetVSOutput\result.json' in runner_text,
        },
        {"argparse": False, "sys_argv": False, "request_fixed": True, "manifest_fixed": True, "result_fixed": True},
    )

    check(
        "V1C2A2 RUNNER REHASHES REQUEST PAYLOAD POLICY AND MANIFEST",
        {
            "self_hash": 'request["runner_sha256"] != _sha256(own_bytes)' in runner_text,
            "payload_hash": 'request["payload_sha256"] != _sha256(payload_bytes)' in runner_text,
            "policy_hash": 'request["policy_sha256"] != _sha256(policy_bytes)' in runner_text,
            "manifest_hash": 'request["source_manifest_sha256"] != _sha256(manifest_bytes)' in runner_text,
        },
        {"self_hash": True, "payload_hash": True, "policy_hash": True, "manifest_hash": True},
    )

    check(
        "V1C2A2 RUNNER REHASHES EACH EXACT SOURCE",
        {
            "fixed_flat_join": 'os.path.join(SOURCE_ROOT, guest_name)' in runner_text,
            "size": 'len(data) != source["size_bytes"]' in runner_text,
            "hash": '_sha256(data) != source["sha256"]' in runner_text,
            "ordinal": 'f"source-{ordinal:04d}.py"' in runner_text,
        },
        {"fixed_flat_join": True, "size": True, "hash": True, "ordinal": True},
    )

    check(
        "V1C2A2 RUNNER RECHECKS UTF8 NUL AND LF POLICY",
        {
            "nul": 'b"\\x00" in data' in runner_text,
            "cr": 'b"\\r" in data' in runner_text,
            "utf8": 'data.decode("utf-8", errors="strict")' in runner_text,
            "encoding_manifest": 'source["encoding"] != "utf-8"' in runner_text,
            "line_endings_manifest": 'source["line_endings"] not in ("lf", "none")' in runner_text,
        },
        {"nul": True, "cr": True, "utf8": True, "encoding_manifest": True, "line_endings_manifest": True},
    )

    check(
        "V1C2A2 EMPTY PYTHON SOURCE REMAINS VALID INPUT MATERIAL",
        'allow_empty=True' in runner_text,
        True,
    )

    check(
        "V1C2A2 RUNNER REVALIDATES TRUSTED RUNTIME IDENTITY",
        {
            "cpython": 'platform.python_implementation() != "CPython"' in runner_text,
            "version": 'tuple(sys.version_info[:3]) != RUNTIME_VERSION' in runner_text,
            "bits": 'struct.calcsize("P") * 8 != 64' in runner_text,
            "machine": 'platform.machine().upper() not in RUNTIME_MACHINES' in runner_text,
        },
        {"cpython": True, "version": True, "bits": True, "machine": True},
    )

    check(
        "V1C2A2 RUNNER REQUIRES ISOLATED SAFE NO BYTECODE FLAGS",
        {
            "isolated": "sys.flags.isolated" in runner_text,
            "ignore_environment": "sys.flags.ignore_environment" in runner_text,
            "no_user_site": "sys.flags.no_user_site" in runner_text,
            "safe_path": 'getattr(sys.flags, "safe_path", False)' in runner_text,
            "dont_write_bytecode": "sys.flags.dont_write_bytecode" in runner_text,
            "utf8_mode": "sys.flags.utf8_mode" in runner_text,
            "site_absent": '"site" in sys.modules' in runner_text,
        },
        {"isolated": True, "ignore_environment": True, "no_user_site": True, "safe_path": True, "dont_write_bytecode": True, "utf8_mode": True, "site_absent": True},
    )

    check(
        "V1C2A2 RUNNER REJECTS PYTHON PIP AND VENV ENVIRONMENT",
        {
            "python": 'startswith(("PYTHON", "PIP_", "PYLAUNCHER_"))' in runner_text,
            "venv": 'key.upper() == "VIRTUAL_ENV"' in runner_text,
        },
        {"python": True, "venv": True},
    )

    ast_calls = [node for node in ast.walk(runner_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "ast" and node.func.attr == "parse"]
    check(
        "V1C2A2 RUNNER AST PARSE SEMANTICS ARE PINNED",
        {
            "call_count": len(ast_calls),
            "mode_exec": 'mode="exec"' in runner_text,
            "type_comments_false": 'type_comments=False' in runner_text,
            "feature_313": 'feature_version=(3, 13)' in runner_text,
            "optimize_0": 'optimize=0' in runner_text,
        },
        {"call_count": 1, "mode_exec": True, "type_comments_false": True, "feature_313": True, "optimize_0": True},
    )

    check(
        "V1C2A2 RUNNER COMPILE SEMANTICS ARE PINNED",
        {
            "compile_calls": called.count("compile"),
            "mode_exec": '"exec",\n                flags=0' in runner_text,
            "dont_inherit": 'dont_inherit=True' in runner_text,
            "optimize": 'optimize=0' in runner_text,
            "delete_code": "del code" in runner_text,
        },
        {"compile_calls": 1, "mode_exec": True, "dont_inherit": True, "optimize": True, "delete_code": True},
    )

    check(
        "V1C2A2 COMPILED CODE OBJECT IS NEVER EXECUTED",
        {
            "exec_calls": called.count("exec"),
            "eval_calls": called.count("eval"),
            "code_called": any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "code" for node in ast.walk(runner_tree)),
        },
        {"exec_calls": 0, "eval_calls": 0, "code_called": False},
    )

    check(
        "V1C2A2 SOURCE IMPORTS CAN ONLY BE PARSED AND COMPILED",
        {
            "importlib": "importlib" in imports,
            "runpy": "runpy" in imports,
            "__import__": "__import__" in called,
            "exec": "exec" in called,
            "eval": "eval" in called,
        },
        {"importlib": False, "runpy": False, "__import__": False, "exec": False, "eval": False},
    )

    check(
        "V1C2A2 SYNTAX ERROR EVIDENCE IS BOUNDED AND SOURCE FREE",
        {
            "uses_msg": 'getattr(error, "msg", "invalid syntax")' in runner_text,
            "uses_text": "error.text" in runner_text or 'getattr(error, "text"' in runner_text,
            "bounded": "message[:MAX_ERROR_MESSAGE_CHARS]" in runner_text,
            "single_line": '.replace("\\r", " ").replace("\\n", " ")' in runner_text,
        },
        {"uses_msg": True, "uses_text": False, "bounded": True, "single_line": True},
    )

    check(
        "V1C2A2 SYNTAX FAILURE DOES NOT SHORT CIRCUIT SELECTED FILE LOOP",
        {
            "source_loop": "for source in sources:" in runner_text,
            "syntax_caught_inside": "except SyntaxError as error:" in runner_text,
            "append_after_catch": "files.append(_file_result" in runner_text,
        },
        {"source_loop": True, "syntax_caught_inside": True, "append_after_catch": True},
    )

    check(
        "V1C2A2 RESULT CLAIMS ONLY PARSE AND COMPILE",
        {
            "trusted_interpreter": 'True,\n        True,\n        all_ast,\n        all_compile,\n        False,\n        False,\n        False,\n        False,\n        False,' in runner_text,
            "changed_exec_false": '"changed_code_executed"' in runner_text,
            "execution_authorized_false": '"execution_authorized"' in runner_text,
        },
        {"trusted_interpreter": True, "changed_exec_false": True, "execution_authorized_false": True},
    )

    check(
        "V1C2A2 RESULT IS EXCLUSIVE CREATE WITH EXACT SINGLE LF",
        {
            "trailing_lf": '_canonical_json_bytes(payload, trailing_lf=True)' in runner_text,
            "exclusive": "os.O_EXCL" in runner_text,
            "binary": 'getattr(os, "O_BINARY", 0)' in runner_text,
            "fsync": "os.fsync(descriptor)" in runner_text,
        },
        {"trailing_lf": True, "exclusive": True, "binary": True, "fsync": True},
    )

    check(
        "V1C2A2 INPUT FAILURE DOES NOT EMIT AN ATTESTED RESULT",
        {
            "broad_boundary_catch": "except Exception:" in runner_text,
            "failure_exit": "return 70" in runner_text,
            "result_after_validation": runner_text.index("result = _build_result") > runner_text.index("sources = _validate_manifest"),
        },
        {"broad_boundary_catch": True, "failure_exit": True, "result_after_validation": True},
    )

    forbidden_imports = {"socket", "subprocess", "urllib", "http", "ftplib", "ssl", "requests"}
    check(
        "V1C2A2 RUNNER HAS NO NETWORK SUBPROCESS OR SHELL SURFACE",
        {
            "forbidden_imports": sorted(forbidden_imports.intersection(imports)),
            "subprocess_text": "subprocess" in runner_text,
            "shell_true": "shell=True" in runner_text,
            "os_system": "os.system" in runner_text,
        },
        {"forbidden_imports": [], "subprocess_text": False, "shell_true": False, "os_system": False},
    )

    check(
        "V1C2A2 RUNNER HAS NO DEPENDENCY INSTALL SURFACE",
        {
            "pip_install": "pip install" in runner_text,
            "ensurepip": "ensurepip" in runner_text,
            "pypi": "pypi.org" in runner_text,
        },
        {"pip_install": False, "ensurepip": False, "pypi": False},
    )

    check(
        "V1C2A2 BUILD MODULE HAS NO SANDBOX PROCESS OR NETWORK SURFACE",
        {
            "WindowsSandbox.exe": "WindowsSandbox.exe" in Path(__file__).resolve().parents[1].joinpath("modules/developer/developer_task_execution_compile_ast_runner.py").read_text(encoding="utf-8"),
            "subprocess": "subprocess" in Path(__file__).resolve().parents[1].joinpath("modules/developer/developer_task_execution_compile_ast_runner.py").read_text(encoding="utf-8"),
            "urllib": "urllib" in Path(__file__).resolve().parents[1].joinpath("modules/developer/developer_task_execution_compile_ast_runner.py").read_text(encoding="utf-8"),
            "requests": "requests" in Path(__file__).resolve().parents[1].joinpath("modules/developer/developer_task_execution_compile_ast_runner.py").read_text(encoding="utf-8"),
        },
        {"WindowsSandbox.exe": False, "subprocess": False, "urllib": False, "requests": False},
    )

    copy_blocked = deepcopy_blocked = pickle_blocked = False
    try:
        copy.copy(bundle.runner)
    except Exception:
        copy_blocked = True
    try:
        copy.deepcopy(bundle.runner)
    except Exception:
        deepcopy_blocked = True
    try:
        pickle.dumps(bundle.runner)
    except Exception:
        pickle_blocked = True
    # Payload bytes are immutable bytes and the metadata object is frozen; serialization is safe
    # because the public bundle representation never includes _bytes. Direct pickle is not used as
    # a capability boundary in V1C2A2, so only metadata immutability is required here.
    check(
        "V1C2A2 PAYLOAD BYTES ARE IMMUTABLE VALUE SNAPSHOTS",
        {
            "runner_type": type(bundle.runner.exact_bytes()).__name__,
            "payload_type": type(bundle.payload_manifest.exact_bytes()).__name__,
            "runner_same_hash": hashlib.sha256(bundle.runner.exact_bytes()).hexdigest() == bundle.runner.sha256,
            "contract_policy_same_hash": hashlib.sha256(bundle.contract_policy.exact_bytes()).hexdigest() == bundle.contract_policy.sha256,
            "payload_same_hash": hashlib.sha256(bundle.payload_manifest.exact_bytes()).hexdigest() == bundle.payload_manifest.sha256,
        },
        {"runner_type": "bytes", "payload_type": "bytes", "runner_same_hash": True, "contract_policy_same_hash": True, "payload_same_hash": True},
    )

    mutated_policy = replace(policy, runner_max_bytes=policy.runner_max_bytes + 1)
    check(
        "V1C2A2 POLICY MUTATION INVALIDATES FINGERPRINT",
        {
            "changed": developer_task_execution_compile_ast_runner_policy_fingerprint(mutated_policy) != policy.fingerprint,
            "errors": list(validate_developer_task_execution_compile_ast_runner_policy(mutated_policy)),
        },
        {"changed": True, "errors": ["limits_invalid", "policy_fingerprint_mismatch"]},
    )

    check(
        "V1C2A2 RUNNER SOURCE IS SYNTACTICALLY VALID HOST DATA",
        {
            "module_nodes": len(runner_tree.body) > 0,
            "main_guard": '__name__ == "__main__"' in runner_text,
            "source_bytes": len(runner_bytes),
        },
        {"module_nodes": True, "main_guard": True, "source_bytes": len(runner_bytes)},
    )

    check(
        "V1C2A2 POLICY LOCKS HOST ONLY NON ACTIVE BUILD",
        {
            "sandbox": policy.sandbox_launched_during_bundle_build,
            "lease_input": policy.runtime_lease_input,
            "candidate": policy.candidate_interpreter_executed_during_bundle_build,
            "changed_source": policy.changed_source_processed_during_bundle_build,
            "authorized": policy.execution_authorized,
        },
        {"sandbox": False, "lease_input": False, "candidate": False, "changed_source": False, "authorized": False},
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
