from __future__ import annotations

import json
import os

from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.core.config import DEFAULT_NLU_ACCEPT_CONF, Settings
from modules.nlu import _nlu_min_conf


def _env_example_keys() -> list[str]:
    keys: list[str] = []

    for raw_line in Path(".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key = line.split("=", 1)[0].strip()

        if key:
            keys.append(key)

    return keys


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

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings.from_env()
        model_threshold = _nlu_min_conf()

    check(
        "DEFAULT ACCEPT THRESHOLD IS SHARED",
        {
            "constant": DEFAULT_NLU_ACCEPT_CONF,
            "settings": settings.nlu_accept_conf,
            "model": model_threshold,
        },
        {
            "constant": 0.35,
            "settings": 0.35,
            "model": 0.35,
        },
    )

    with patch.dict(
        os.environ,
        {
            "NLU_ACCEPT_CONF": "0.42",
            "NLU_SAY_CONF": "0.61",
        },
        clear=True,
    ):
        settings = Settings.from_env()
        model_threshold = _nlu_min_conf()

    check(
        "CURRENT NLU ENV VARIABLES ARE USED",
        {
            "settings_accept": settings.nlu_accept_conf,
            "model_accept": model_threshold,
            "settings_say": settings.nlu_say_conf,
        },
        {
            "settings_accept": 0.42,
            "model_accept": 0.42,
            "settings_say": 0.61,
        },
    )

    with patch.dict(
        os.environ,
        {
            "NLU_MIN_CONF": "0.91",
        },
        clear=True,
    ):
        settings = Settings.from_env()
        model_threshold = _nlu_min_conf()

    check(
        "LEGACY VARIABLE IS IGNORED",
        {
            "settings": settings.nlu_accept_conf,
            "model": model_threshold,
        },
        {
            "settings": 0.35,
            "model": 0.35,
        },
    )

    env_keys = _env_example_keys()

    check(
        "ENV EXAMPLE DOCUMENTS CURRENT NLU CONTRACT",
        {
            "accept_count": env_keys.count("NLU_ACCEPT_CONF"),
            "say_count": env_keys.count("NLU_SAY_CONF"),
            "legacy_count": env_keys.count("NLU_MIN_CONF"),
        },
        {
            "accept_count": 1,
            "say_count": 1,
            "legacy_count": 0,
        },
    )

    nlu_source = Path("modules/nlu.py").read_text(encoding="utf-8")
    config_source = Path("modules/core/config.py").read_text(encoding="utf-8")

    check(
        "PRODUCTION CODE HAS NO LEGACY NLU VARIABLE",
        {
            "nlu_has_legacy": "NLU_MIN_CONF" in nlu_source,
            "config_has_legacy": "NLU_MIN_CONF" in config_source,
            "nlu_has_current": "NLU_ACCEPT_CONF" in nlu_source,
            "config_has_current": "NLU_ACCEPT_CONF" in config_source,
        },
        {
            "nlu_has_legacy": False,
            "config_has_legacy": False,
            "nlu_has_current": True,
            "config_has_current": True,
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