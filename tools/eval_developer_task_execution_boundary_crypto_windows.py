from __future__ import annotations

import base64
import json
import sys

from modules.developer.developer_task_execution_boundary_crypto import (
    verify_ecdsa_p256_sha256_cng,
)


_PUBLIC_KEY = base64.b64decode(
    "RUNTMSAAAABrF9Hy4SxCR/i85uVjpEDydwN9gS3rM6D0oTlF2JjClk/jQuL+Gn+bjufrSnwPnhYrzjNXazFezsu2QGg3v1H1"
)
_MESSAGE = base64.b64decode("U2t5bmV0VlMgVjFCM0IgQ05HIHNtb2tlIHZlY3RvciB2MQ==")
_SIGNATURE = base64.b64decode(
    "RpWlqdIzvEUPAvSVAsbO2KPK5jA/+tfOfqJN3y0QLW2sglwPmUs4TpAyIZtd5sqjd9JKCOQIsP/jBX7hIaRO1w=="
)


def main() -> int:
    if sys.platform != "win32":
        print("[SKIP] Windows CNG signature smoke requires win32.")
        return 0

    cases = [
        (
            "KNOWN ECDSA P256 SIGNATURE VERIFIES THROUGH WINDOWS CNG",
            verify_ecdsa_p256_sha256_cng(_PUBLIC_KEY, _MESSAGE, _SIGNATURE),
            True,
        ),
        (
            "MUTATED MESSAGE IS REJECTED THROUGH WINDOWS CNG",
            verify_ecdsa_p256_sha256_cng(_PUBLIC_KEY, _MESSAGE + b"!", _SIGNATURE),
            False,
        ),
        (
            "MUTATED SIGNATURE IS REJECTED THROUGH WINDOWS CNG",
            verify_ecdsa_p256_sha256_cng(
                _PUBLIC_KEY,
                _MESSAGE,
                _SIGNATURE[:-1] + bytes([_SIGNATURE[-1] ^ 1]),
            ),
            False,
        ),
    ]
    fail_count = 0
    for name, actual, expected in cases:
        ok = actual == expected
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, indent=2))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")
        if not ok:
            fail_count += 1
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": len(cases), "fail_count": fail_count}, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
