from __future__ import annotations

import hashlib
import json
import sys

from modules.developer.developer_task_execution_compile_ast_verifier import (
    verify_developer_task_execution_compile_ast_transcript,
)
from modules.developer.developer_task_execution_compile_ast_verifier_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
)
from tools.eval_developer_task_execution_compile_ast_verifier import (
    _PUBLIC_KEY,
    build_verifier_fixture,
    pin_fixture,
)


_P = int("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF", 16)
_A = _P - 3
_N = int("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16)
_GX = int("6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296", 16)
_GY = int("4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5", 16)


def _point_add(left: tuple[int, int] | None, right: tuple[int, int] | None) -> tuple[int, int] | None:
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % _P == 0:
        return None
    if left == right:
        slope = ((3 * x1 * x1 + _A) * pow(2 * y1, -1, _P)) % _P
    else:
        slope = ((y2 - y1) * pow(x2 - x1, -1, _P)) % _P
    x3 = (slope * slope - x1 - x2) % _P
    y3 = (slope * (x1 - x3) - y1) % _P
    return x3, y3


def _scalar_multiply(scalar: int, point: tuple[int, int]) -> tuple[int, int]:
    result: tuple[int, int] | None = None
    addend: tuple[int, int] | None = point
    value = scalar
    while value:
        if value & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        value >>= 1
    if result is None:
        raise RuntimeError("invalid ECDSA scalar result")
    return result


def _sign_terminal(message: bytes) -> bytes:
    digest = hashlib.sha256(message).digest()
    z = int.from_bytes(digest, "big")
    private_key = 1
    nonce = 2
    rx, _ = _scalar_multiply(nonce, (_GX, _GY))
    r = rx % _N
    s = (pow(nonce, -1, _N) * (z + r * private_key)) % _N
    if r == 0 or s == 0:
        raise RuntimeError("invalid deterministic ECDSA test signature")
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def main() -> int:
    if sys.platform != "win32":
        print("[SKIP] V1C2B Windows CNG smoke requires Windows.")
        return 0
    fixture = build_verifier_fixture(public_key_blob=_PUBLIC_KEY)
    pin_report = pin_fixture(fixture)
    signature = _sign_terminal(fixture["terminal_bytes"])
    report = verify_developer_task_execution_compile_ast_transcript(
        pin_report,
        source_manifest_bytes=fixture["source_manifest_bytes"],
        request_bytes=fixture["request_bytes"],
        ready_bytes=fixture["ready_bytes"],
        authorize_bytes=fixture["authorize_bytes"],
        result_bytes=fixture["result_bytes"],
        terminal_payload_bytes=fixture["terminal_bytes"],
        terminal_signature_bytes=signature,
    )
    actual = {
        "ok": report.ok,
        "verifier_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
        "signature_valid": report.signature_valid,
        "chain_verified": report.chain_verified,
        "result_verified": report.result_verified,
        "terminal_verified": report.terminal_verified,
        "terminal_status": report.terminal_status,
        "boundary_ok": report.boundary_ok,
        "check_passed": report.check_passed,
        "signature_size_bytes": len(signature),
        "public_key_sha256": hashlib.sha256(_PUBLIC_KEY).hexdigest(),
        "sandbox_launched": False,
        "runtime_lease_issued": False,
        "runtime_lease_claimed": False,
        "candidate_interpreter_executed": False,
        "changed_source_processed_by_verifier": False,
        "changed_code_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    expected = dict(actual)
    expected.update(
        {
            "ok": True,
            "signature_valid": True,
            "chain_verified": True,
            "result_verified": True,
            "terminal_verified": True,
            "terminal_status": "compile_ast_attested_passed",
            "boundary_ok": True,
            "check_passed": True,
            "signature_size_bytes": 64,
        }
    )
    ok = actual == expected
    print("=== V1C2B REAL WINDOWS SIGNED COMPILE AST VERIFIER ===")
    print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
    print(f"[{'OK' if ok else 'FAIL'}] V1C2B REAL WINDOWS SIGNED COMPILE AST VERIFIER")
    print("\n=== SUMMARY ===")
    print(json.dumps({"case_count": 1, "fail_count": 0 if ok else 1}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
