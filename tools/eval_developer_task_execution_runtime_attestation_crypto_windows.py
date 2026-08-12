from __future__ import annotations

import base64
import json
import sys

from modules.developer.developer_task_execution_runtime_attestation import (
    build_developer_task_execution_runtime_attestation_payload,
)
from modules.developer.developer_task_execution_runtime_attestation_contract import (
    parse_runtime_attestation_result,
)
from modules.developer.developer_task_execution_runtime_attestation_verifier import (
    pin_developer_task_execution_runtime_attestation_transcript,
    verify_developer_task_execution_runtime_attestation_transcript,
)
from tools.eval_developer_task_execution_runtime_attestation_verifier import (
    _AUTH_NONCE,
    _AUTH_OBSERVED_EPOCH,
    _HOST_NONCE,
    _REQUEST_ID,
    _SECOND_PUBLIC_KEY,
    _sample_authorize,
    _sample_ready,
    _sample_request,
    _sample_runtime_result,
    _sample_terminal,
    _sample_wsb,
)


_SIGNATURE = base64.b64decode(
    "08uIzhOQg34GPcCkSKlEQMODp0wK+NgPOUAOWnDDxjcJP4xnB8o7nZ5QMg/FQh3jTMoy68Mjg23JVgTZ/gjhvw=="
)


def _build_fixture() -> tuple[bytes, object, object, object, bytes, object, bytes]:
    bundle = build_developer_task_execution_runtime_attestation_payload()
    wsb_bytes = _sample_wsb()
    request = _sample_request(bundle, wsb_bytes)
    ready = _sample_ready(request, public_key=_SECOND_PUBLIC_KEY)
    authorize = _sample_authorize(request, ready)
    runtime_result_bytes = _sample_runtime_result()
    runtime_result = parse_runtime_attestation_result(runtime_result_bytes)
    terminal_bytes = _sample_terminal(request, ready, authorize, runtime_result)
    return wsb_bytes, request, ready, authorize, runtime_result_bytes, runtime_result, terminal_bytes


def _verify(terminal_bytes: bytes, signature: bytes) -> object:
    wsb_bytes, request, ready, authorize, runtime_result_bytes, _, _ = _build_fixture()
    pin = pin_developer_task_execution_runtime_attestation_transcript(
        expected_request_id=_REQUEST_ID,
        expected_host_nonce=_HOST_NONCE,
        expected_authorization_nonce=_AUTH_NONCE,
        expected_request_sha256=request.sha256,
        authorization_observed_epoch=_AUTH_OBSERVED_EPOCH,
        wsb_bytes=wsb_bytes,
        request_bytes=request.canonical_bytes,
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=authorize.canonical_bytes,
    )
    if not pin.ok:
        raise RuntimeError(f"Runtime-attestation CNG fixture did not pin: {pin.issue_codes}")
    return verify_developer_task_execution_runtime_attestation_transcript(
        pin,
        wsb_bytes=wsb_bytes,
        request_bytes=request.canonical_bytes,
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=authorize.canonical_bytes,
        runtime_result_bytes=runtime_result_bytes,
        terminal_payload_bytes=terminal_bytes,
        terminal_signature_bytes=signature,
    )


def main() -> int:
    if sys.platform != "win32":
        print("[SKIP] V1B4C2A Windows CNG runtime-attestation smoke requires win32.")
        return 0

    _, _, _, _, _, runtime_result, terminal_bytes = _build_fixture()
    exact = _verify(terminal_bytes, _SIGNATURE)
    mutated_terminal = _sample_terminal(
        _build_fixture()[1],
        _build_fixture()[2],
        _build_fixture()[3],
        runtime_result,
        completed_epoch=1786500011,
    )
    changed_message = _verify(mutated_terminal, _SIGNATURE)
    mutated_signature = _SIGNATURE[:-1] + bytes([_SIGNATURE[-1] ^ 1])
    changed_signature = _verify(terminal_bytes, mutated_signature)

    cases = [
        (
            "V1B4C2A EXACT SIGNED RUNTIME TRANSCRIPT VERIFIES THROUGH WINDOWS CNG",
            {
                "ok": exact.ok,
                "signature_valid": exact.signature_valid,
                "runtime_result_verified": exact.runtime_result_verified,
                "terminal_verified": exact.terminal_verified,
                "issue_codes": list(exact.issue_codes),
                "execution_authorized": exact.to_dict()["execution_authorized"],
            },
            {
                "ok": True,
                "signature_valid": True,
                "runtime_result_verified": True,
                "terminal_verified": True,
                "issue_codes": [],
                "execution_authorized": False,
            },
        ),
        (
            "V1B4C2A MUTATED TERMINAL MESSAGE IS REJECTED THROUGH WINDOWS CNG",
            changed_message.ok,
            False,
        ),
        (
            "V1B4C2A MUTATED TERMINAL SIGNATURE IS REJECTED THROUGH WINDOWS CNG",
            changed_signature.ok,
            False,
        ),
    ]
    fail_count = 0
    for name, actual, expected in cases:
        ok = actual == expected
        if not ok:
            fail_count += 1
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": len(cases), "fail_count": fail_count}, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
