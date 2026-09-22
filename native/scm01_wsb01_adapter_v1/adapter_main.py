"""Public entrypoint. Every argument is ignored; no dispatch or runtime issuer exists."""
import json
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    print(json.dumps({"kind": "SCM01_WSB01_CLOSED_CORE_V1",
                      "result": "RUNTIME_CLOSED_SOURCE_ONLY", "evidence_domain": "OFFLINE_MODEL",
                      "runtime_authorized": False, "crypto_verified": False,
                      "sandbox": False, "guest_bootstrap": False, "real_scm": False,
                      "guard": False}, sort_keys=True, separators=(",", ":")))
    return 92


if __name__ == "__main__":
    raise SystemExit(main())
