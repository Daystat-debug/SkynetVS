from __future__ import annotations

import ast
import builtins
import hashlib
import importlib
import json
import socket
import subprocess

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.developer.developer_task_contract import (
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_proposal_contract import (
    DTR_MAX_CONTEXT_FILE_BYTES,
    DTR_MAX_EXPLANATION_UTF8_BYTES,
    DTR_MAX_INSTRUCTION_UTF8_BYTES,
    DTR_MAX_PATCH_UTF8_BYTES,
    DTR_MAX_RAW_RESPONSE_BYTES,
    DTR_PROPOSAL_SUCCESS_STATUS,
    DeveloperTaskProposalContextInput,
    DeveloperTaskProposalRequestError,
    canonical_dtr_json_bytes,
    dtr_sha256,
)
from modules.developer.developer_task_proposal_intake import (
    developer_task_proposal_request_fingerprint,
    intake_developer_task_proposal,
    prepare_developer_task_proposal_request,
)
from modules.developer.developer_task_validator import (
    validate_developer_task_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_PATH = "modules/text_normalizer.py"
BASE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
BASE_TREE = "89abcdef0123456789abcdef0123456789abcdef"


def _git_blob_oid(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _context_input(
    path: str = TARGET_PATH,
    content: bytes | bytearray = b"def normalize(value):\n    return value.strip()\n",
    *,
    mode: str = "100644",
    oid: str | None = None,
) -> DeveloperTaskProposalContextInput:
    frozen = bytes(content)
    return DeveloperTaskProposalContextInput(
        path=path,
        mode=mode,
        git_blob_oid=oid or _git_blob_oid(frozen),
        content=content,
    )


def _request(**overrides: Any):
    values = {
        "task_id": "dtr-proposal-smoke",
        "title": "DTR proposal smoke",
        "request_id": "req:dtr:smoke:001",
        "instruction": "Измени только указанную функцию без изменения публичного контракта.",
        "base_commit": BASE_COMMIT,
        "base_tree": BASE_TREE,
        "target_path": TARGET_PATH,
        "context_entries": [_context_input()],
        "origin": "manual",
    }
    values.update(overrides)
    return prepare_developer_task_proposal_request(**values)


def _proposal_payload(request, **overrides: Any) -> dict[str, Any]:
    payload = {
        "kind": "DTR_PATCH_PROPOSAL_V1",
        "schema_version": 1,
        "request_id": request.request_id,
        "request_fingerprint": request.request_fingerprint,
        "patch_text": (
            "diff --git a/modules/text_normalizer.py b/modules/text_normalizer.py\n"
            "index 1111111..2222222 100644\n"
            "--- a/modules/text_normalizer.py\n"
            "+++ b/modules/text_normalizer.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def normalize(value):\n"
            "-    return value.strip()\n"
            "+    return value.strip().lower()\n"
        ),
        "explanation": "Normalize case after trimming.",
    }
    payload.update(overrides)
    return payload


def _raw(request, **overrides: Any) -> bytes:
    return json.dumps(
        _proposal_payload(request, **overrides),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _codes(result) -> set[str]:
    return set(result.issue_codes)


def _request_error_codes(**kwargs: Any) -> set[str]:
    try:
        _request(**kwargs)
    except DeveloperTaskProposalRequestError as exc:
        return {item.code for item in exc.issues}
    return set()


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

    request = _request()
    result = intake_developer_task_proposal(request, _raw(request))
    plan = result.plan

    check(
        "T01 VALID MANUAL PROPOSAL BINDS WITHOUT AUTHORITY",
        {
            "ok": result.ok,
            "status": result.status,
            "authority": plan.authority_granted if plan else None,
            "runtime": plan.runtime_authorized if plan else None,
            "promotion": plan.promotion_authorized if plan else None,
            "provider_authenticated": plan.provider_authenticated if plan else None,
        },
        {
            "ok": True,
            "status": DTR_PROPOSAL_SUCCESS_STATUS,
            "authority": False,
            "runtime": False,
            "promotion": False,
            "provider_authenticated": False,
        },
    )

    check(
        "T01 EXISTING MANIFEST VALIDATOR ACCEPTS BUILDER OUTPUT",
        validate_developer_task_manifest(plan.manifest.to_dict()).ok if plan else False,
        True,
    )

    authority_payload = _proposal_payload(request)
    authority_payload["allowed_files"] = ["main.py"]
    authority_result = intake_developer_task_proposal(
        request,
        json.dumps(authority_payload, separators=(",", ":")).encode(),
    )
    check("T02 AUTHORITY FIELD IS REJECTED", "unknown_field" in _codes(authority_result), True)

    duplicate = (
        '{"kind":"DTR_PATCH_PROPOSAL_V1","kind":"DTR_PATCH_PROPOSAL_V1",'
        '"schema_version":1,"request_id":"%s","request_fingerprint":"%s",'
        '"patch_text":"x","explanation":"x"}'
        % (request.request_id, request.request_fingerprint)
    ).encode()
    check("T03 DUPLICATE JSON KEY IS REJECTED", "duplicate_json_key" in _codes(intake_developer_task_proposal(request, duplicate)), True)
    check("T03 TRAILING JSON DATA IS REJECTED", "invalid_json" in _codes(intake_developer_task_proposal(request, _raw(request) + b"{}")), True)
    check("T03 MARKDOWN WRAPPER IS REJECTED", "invalid_json" in _codes(intake_developer_task_proposal(request, b"```json\n" + _raw(request) + b"\n```")), True)

    nonfinite = _raw(request).replace(b'"schema_version":1', b'"schema_version":NaN')
    check("T03 NONFINITE NUMBER IS REJECTED", "non_finite_number" in _codes(intake_developer_task_proposal(request, nonfinite)), True)
    deep_payload = _proposal_payload(request)
    nested: Any = "x"
    for _ in range(10):
        nested = [nested]
    deep_payload["extra"] = nested
    deep_result = intake_developer_task_proposal(
        request,
        json.dumps(deep_payload, separators=(",", ":")).encode(),
    )
    check("T03 JSON DEPTH LIMIT IS ENFORCED", "json_too_deep" in _codes(deep_result), True)

    check("T04 BOOL SCHEMA VERSION IS REJECTED", "invalid_schema_version" in _codes(intake_developer_task_proposal(request, _raw(request, schema_version=True))), True)
    check("T04 WRONG PATCH TYPE IS REJECTED", "invalid_type" in _codes(intake_developer_task_proposal(request, _raw(request, patch_text=["not", "text"]))), True)
    check("T04 BAD UTF8 IS REJECTED", "invalid_utf8" in _codes(intake_developer_task_proposal(request, b"\xff")), True)
    check("T04 UTF8 BOM IS REJECTED", "utf8_bom" in _codes(intake_developer_task_proposal(request, b"\xef\xbb\xbf" + _raw(request))), True)

    surrogate_raw = (
        '{"kind":"DTR_PATCH_PROPOSAL_V1","schema_version":1,'
        f'"request_id":"{request.request_id}","request_fingerprint":"{request.request_fingerprint}",'
        '"patch_text":"\\ud800","explanation":"x"}'
    ).encode()
    check("T04 UNPAIRED SURROGATE IS REJECTED", "invalid_unicode" in _codes(intake_developer_task_proposal(request, surrogate_raw)), True)

    check(
        "T05 INSTRUCTION LIMIT IS ENFORCED",
        "too_large" in _request_error_codes(instruction="x" * (DTR_MAX_INSTRUCTION_UTF8_BYTES + 1)),
        True,
    )
    check(
        "T05 CONTEXT FILE LIMIT IS ENFORCED",
        "context_file_too_large" in _request_error_codes(
            context_entries=[_context_input(content=b"x" * (DTR_MAX_CONTEXT_FILE_BYTES + 1))]
        ),
        True,
    )
    context_over_count = [
        _context_input(path=TARGET_PATH),
        _context_input(path="modules/a.py", content=b"a"),
        _context_input(path="modules/b.py", content=b"b"),
        _context_input(path="modules/c.py", content=b"c"),
        _context_input(path="modules/d.py", content=b"d"),
    ]
    check(
        "T05 CONTEXT COUNT LIMIT IS ENFORCED",
        "context_count" in _request_error_codes(context_entries=context_over_count),
        True,
    )
    check(
        "T05 RAW RESPONSE LIMIT IS ENFORCED",
        "response_too_large" in _codes(intake_developer_task_proposal(request, b" " * (DTR_MAX_RAW_RESPONSE_BYTES + 1))),
        True,
    )
    check(
        "T05 PATCH LIMIT IS ENFORCED",
        "too_large" in _codes(intake_developer_task_proposal(request, _raw(request, patch_text="x" * (DTR_MAX_PATCH_UTF8_BYTES + 1)))),
        True,
    )
    check(
        "T05 EXPLANATION LIMIT IS ENFORCED",
        "too_large" in _codes(intake_developer_task_proposal(request, _raw(request, explanation="x" * (DTR_MAX_EXPLANATION_UTF8_BYTES + 1)))),
        True,
    )

    check("T06 WRONG REQUEST ID IS REJECTED", "request_id_mismatch" in _codes(intake_developer_task_proposal(request, _raw(request, request_id="req:other:001"))), True)
    check("T06 WRONG REQUEST FINGERPRINT IS REJECTED", "request_fingerprint_mismatch" in _codes(intake_developer_task_proposal(request, _raw(request, request_fingerprint="0" * 64))), True)

    mutable_content = bytearray(b"original\n")
    mutable_context = [_context_input(content=mutable_content)]
    frozen_request = _request(context_entries=mutable_context)
    mutable_content[:] = b"tampered\n"
    mutable_context.clear()
    check("T07 REQUEST COPIES CALLER CONTEXT", frozen_request.context[0].content, b"original\n")

    mutable_raw = bytearray(_raw(frozen_request))
    frozen_result = intake_developer_task_proposal(frozen_request, mutable_raw)
    frozen_raw = frozen_result.plan.proposal.raw_response_bytes if frozen_result.plan else b""
    mutable_raw[:] = b"{}"
    check("T07 INTAKE COPIES CALLER RESPONSE BUFFER", frozen_result.plan.proposal.raw_response_bytes if frozen_result.plan else b"", frozen_raw)

    exact_patch = "line1\r\nПривет  \nline3\t\r\n"
    exact_result = intake_developer_task_proposal(request, _raw(request, patch_text=exact_patch))
    check("T08 PATCH TEXT IS PRESERVED EXACTLY", exact_result.plan.proposal.patch_bytes if exact_result.plan else b"", exact_patch.encode("utf-8"))
    check("T08 PATCH HASH BINDS EXACT BYTES", exact_result.plan.proposal.patch_sha256 if exact_result.plan else "", hashlib.sha256(exact_patch.encode("utf-8")).hexdigest())

    read_context = [
        _context_input(),
        _context_input(
            path="tools/eval_text_normalizer.py",
            content=b"print('reference only')\n",
        ),
    ]
    scoped_request = _request(context_entries=read_context)
    scoped_result = intake_developer_task_proposal(scoped_request, _raw(scoped_request))
    check("T09 READ CONTEXT DOES NOT EXPAND WRITE SCOPE", list(scoped_result.plan.manifest.allowed_files) if scoped_result.plan else [], [TARGET_PATH])

    check(
        "T10 MANIFEST AUTHORITY FIELDS COME FROM TRUSTED REQUEST",
        {
            "task_id": plan.manifest.task_id if plan else None,
            "base_commit": plan.manifest.base_commit if plan else None,
            "origin": plan.manifest.origin if plan else None,
            "patch_file": plan.manifest.patch_file if plan else None,
            "allowed_files": list(plan.manifest.allowed_files) if plan else None,
            "install_policy": plan.manifest.install_policy if plan else None,
        },
        {
            "task_id": request.task_id,
            "base_commit": BASE_COMMIT,
            "origin": "manual",
            "patch_file": "changes.patch",
            "allowed_files": [TARGET_PATH],
            "install_policy": "manual_confirmation",
        },
    )

    check(
        "T11 REQUIRED CHECK PROFILE IS RETAINED",
        [item.to_dict() for item in plan.manifest.checks] if plan else [],
        [
            {"type": "git_diff_check"},
            {"type": "py_compile", "scope": "changed_python_files"},
            {"type": "pipeline", "flow": "check"},
        ],
    )

    check("T12 MANUAL ORIGIN IS ACCEPTED", request.origin, "manual")
    check("T12 BROWSER BRIDGE IS NOT ADMITTED", "unsupported_origin" in _request_error_codes(origin="browser_bridge"), True)

    protected = _request_error_codes(target_path="modules/action_authority.py", context_entries=[_context_input(path="modules/action_authority.py")])
    check("T13 DTR PROTECTED TARGET IS REJECTED", "protected_target" in protected, True)

    forged_source = replace(request.context[0], path="modules/action_authority.py")
    forged_context = (forged_source,)
    forged_digest = dtr_sha256(canonical_dtr_json_bytes([item.binding_dict() for item in forged_context]))
    forged = replace(
        request,
        target_path="modules/action_authority.py",
        context=forged_context,
        context_digest=forged_digest,
        request_fingerprint="",
    )
    forged = replace(forged, request_fingerprint=developer_task_proposal_request_fingerprint(forged))
    forged_result = intake_developer_task_proposal(forged, _raw(forged))
    check("T13 DIRECTLY CONSTRUCTED SELF-HASHED PROTECTED REQUEST IS REJECTED", "request_protected_target" in _codes(forged_result), True)

    kernel_protected_payload = plan.manifest.to_dict() if plan else {}
    kernel_protected_payload["allowed_files"] = ["modules/developer/developer_task_contract.py"]
    kernel_protected = validate_developer_task_manifest(kernel_protected_payload)
    check("T13 UNCHANGED KERNEL STILL REJECTS ITS PROTECTED PATH", "protected_path" in set(kernel_protected.issue_codes), True)

    side_effect_result = None
    with patch.object(builtins, "open", side_effect=AssertionError("open called")), \
         patch.object(subprocess, "run", side_effect=AssertionError("subprocess called")), \
         patch.object(socket, "socket", side_effect=AssertionError("socket called")), \
         patch.object(importlib, "import_module", side_effect=AssertionError("dynamic import called")):
        side_effect_result = intake_developer_task_proposal(request, _raw(request))
    check("T14 PURE INTAKE HAS NO IO NETWORK SUBPROCESS OR DYNAMIC IMPORT", side_effect_result.ok, True)

    intake_source = (PROJECT_ROOT / "modules" / "developer" / "developer_task_proposal_intake.py").read_text(encoding="utf-8")
    intake_tree = ast.parse(intake_source)
    imported_modules: set[str] = set()
    called_names: set[str] = set()
    for node in ast.walk(intake_tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    forbidden_imports = sorted(name for name in imported_modules if name in {"os", "socket", "subprocess", "importlib", "shutil", "tempfile"})
    forbidden_calls = sorted(called_names & {"open", "create_developer_task_workspace", "apply_developer_task_patch", "issue_developer_task_execution_compile_ast_plan", "attest_developer_task_execution_compile_ast_composition"})
    check("T15 PURE INTAKE IMPORTS NO EFFECT CAPABILITY MODULES", forbidden_imports, [])
    check("T15 PURE INTAKE CALLS NO WORKSPACE APPLY TOKEN OR SANDBOX API", forbidden_calls, [])

    reversed_context = list(reversed(read_context))
    request_a = _request(context_entries=read_context)
    request_b = _request(context_entries=reversed_context)
    check("T16 REQUEST FINGERPRINT IS STABLE ACROSS CONTEXT INPUT ORDER", request_a.request_fingerprint, request_b.request_fingerprint)
    check("T16 REQUEST FINGERPRINT RECOMPUTES CANONICALLY", developer_task_proposal_request_fingerprint(request_a), request_a.request_fingerprint)
    check(
        "T16 CROSS-VERSION CANONICAL FINGERPRINT FIXTURE",
        request.request_fingerprint,
        "b90dcdfa7b77a6fe72a12e3b238b02ba3effd61bebe622789a8dda2e63697e75",
    )
    check("T16 INTAKE SOURCE PARSES AS PYTHON 3.12", isinstance(ast.parse(intake_source, feature_version=(3, 12)), ast.Module), True)
    check("T16 PORTABLE FINGERPRINT SOURCE DOES NOT USE AST DUMP", "ast.dump" in intake_source, False)

    tampered_request = replace(request, title="Different title")
    check("BOUND REQUEST TAMPERING IS REJECTED", "request_fingerprint_mismatch" in _codes(intake_developer_task_proposal(tampered_request, _raw(request))), True)

    tampered_context_request = replace(request, context_digest="0" * 64)
    check("CONTEXT DIGEST TAMPERING IS REJECTED", "context_digest_mismatch" in _codes(intake_developer_task_proposal(tampered_context_request, _raw(request))), True)

    check(
        "CONTEXT GIT BLOB MUST MATCH EXACT BYTES",
        "blob_content_mismatch" in _request_error_codes(context_entries=[_context_input(oid="0" * 40)]),
        True,
    )

    duplicate_context = [
        _context_input(path=TARGET_PATH),
        _context_input(path="Modules/Text_Normalizer.py"),
    ]
    check("CONTEXT PATHS ARE CASE-INSENSITIVE UNIQUE", "duplicate_context_path" in _request_error_codes(context_entries=duplicate_context), True)

    check(
        "TARGET MUST BE PRESENT IN CONTEXT",
        "target_not_bound" in _request_error_codes(
            context_entries=[_context_input(path="modules/reply_builder.py")],
            target_path=TARGET_PATH,
        ),
        True,
    )

    check(
        "UNSAFE CONTEXT PATH IS REJECTED",
        "forbidden_context_path" in _request_error_codes(
            context_entries=[_context_input(path="data/private.py")],
            target_path="data/private.py",
        ),
        True,
    )

    check(
        "NONREGULAR TARGET MODE IS REJECTED",
        "unsupported_mode" in _request_error_codes(context_entries=[_context_input(mode="100755")]),
        True,
    )

    check(
        "REQUEST AND PLAN ARE FROZEN",
        {
            "request": _is_frozen(request, "title", "x"),
            "plan": _is_frozen(plan, "status", "x") if plan else False,
        },
        {"request": True, "plan": True},
    )

    check(
        "RAW RESPONSE HASH BINDS EXACT IMPORT",
        plan.proposal.raw_response_sha256 if plan else "",
        hashlib.sha256(_raw(request)).hexdigest(),
    )

    check(
        "MANIFEST SOURCE REF IS LOCAL REQUEST BINDING",
        plan.manifest.source_ref if plan else "",
        f"dtr-proposal:{request.request_id}",
    )

    check(
        "MANIFEST FINGERPRINT USES EXISTING ALGORITHM",
        plan.manifest_fingerprint if plan else "",
        developer_task_manifest_fingerprint(plan.manifest) if plan else None,
    )

    check(
        "UNKNOWN MODEL COMMAND CANNOT BECOME PLAN",
        intake_developer_task_proposal(
            request,
            json.dumps({**_proposal_payload(request), "command": "git push"}, separators=(",", ":")).encode(),
        ).ok,
        False,
    )

    empty_patch = intake_developer_task_proposal(request, _raw(request, patch_text=""))
    check("EMPTY PATCH IS REJECTED", "invalid_string" in _codes(empty_patch), True)

    empty_explanation = intake_developer_task_proposal(request, _raw(request, explanation=""))
    check("EMPTY EXPLANATION IS REJECTED", "invalid_string" in _codes(empty_explanation), True)

    wrong_kind = intake_developer_task_proposal(request, _raw(request, kind="OTHER"))
    check("WRONG PROPOSAL KIND IS REJECTED", "invalid_kind" in _codes(wrong_kind), True)

    response_list = json.dumps([1, 2, 3]).encode()
    check("NONOBJECT PROPOSAL ROOT IS REJECTED", "invalid_type" in _codes(intake_developer_task_proposal(request, response_list)), True)

    check(
        "REQUEST FINGERPRINT CHANGES WITH INSTRUCTION",
        _request(instruction="A").request_fingerprint == _request(instruction="B").request_fingerprint,
        False,
    )

    check(
        "REQUEST FINGERPRINT CHANGES WITH TARGET PREIMAGE",
        _request(context_entries=[_context_input(content=b"a\n")]).request_fingerprint
        == _request(context_entries=[_context_input(content=b"b\n")]).request_fingerprint,
        False,
    )

    check(
        "PLAN EVIDENCE EXPLICITLY RECORDS NO AUTHORITY",
        {
            key: plan.evidence_dict()[key]
            for key in ("authority_granted", "runtime_authorized", "promotion_authorized")
        } if plan else {},
        {
            "authority_granted": False,
            "runtime_authorized": False,
            "promotion_authorized": False,
        },
    )

    print()
    print("=== SUMMARY ===")
    summary = {
        "kind": "DTRA_PROPOSAL_INTAKE_EVAL_V1",
        "result": "PASS" if fail_count == 0 else "FAIL",
        "case_count": case_count,
        "fail_count": fail_count,
        "dtra_acceptance_requirements_covered": [f"T{i:02d}" for i in range(1, 17)],
        "repo_write": False,
        "network": False,
        "sandbox": False,
        "patch_executed": False,
        "runtime_authorized": False,
        "promotion_authorized": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


def _is_frozen(instance: Any, field: str, value: Any) -> bool:
    try:
        setattr(instance, field, value)
    except FrozenInstanceError:
        return True
    except Exception:
        return False
    return False


if __name__ == "__main__":
    raise SystemExit(main())
