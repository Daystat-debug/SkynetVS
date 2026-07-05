from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.confirmation import (
    build_confirmation_prompt,
    is_confirmation_no,
    is_confirmation_yes,
)


Case = Dict[str, Any]


YES_CASES: List[str] = [
    "да",
    "ага",
    "угу",
    "подтверждаю",
    "подтвердить",
    "ок",
    "okay",
    "ok",
    "выполняй",
]


NO_CASES: List[str] = [
    "нет",
    "не",
    "отмена",
    "отменить",
    "не надо",
    "не нужно",
    "стоп",
]


NEUTRAL_CASES: List[str] = [
    "",
    "может быть",
    "потом",
    "не понял",
    "очисти корзину",
    "открой блокнот",
]


def main() -> int:
    fail_count = 0

    print("=== CONFIRMATION EVAL REPORT ===")

    print()
    print("--- YES PHRASES ---")
    for text in YES_CASES:
        ok = is_confirmation_yes(text) and not is_confirmation_no(text)
        print(json.dumps({"text": text, "yes": is_confirmation_yes(text), "no": is_confirmation_no(text)}, ensure_ascii=False))
        if not ok:
            fail_count += 1
            print("[FAIL] expected yes only")
        else:
            print("[OK] yes phrase")

    print()
    print("--- NO PHRASES ---")
    for text in NO_CASES:
        ok = is_confirmation_no(text) and not is_confirmation_yes(text)
        print(json.dumps({"text": text, "yes": is_confirmation_yes(text), "no": is_confirmation_no(text)}, ensure_ascii=False))
        if not ok:
            fail_count += 1
            print("[FAIL] expected no only")
        else:
            print("[OK] no phrase")

    print()
    print("--- NEUTRAL PHRASES ---")
    for text in NEUTRAL_CASES:
        ok = not is_confirmation_yes(text) and not is_confirmation_no(text)
        print(json.dumps({"text": text, "yes": is_confirmation_yes(text), "no": is_confirmation_no(text)}, ensure_ascii=False))
        if not ok:
            fail_count += 1
            print("[FAIL] expected neutral")
        else:
            print("[OK] neutral phrase")

    print()
    print("--- PROMPT BUILDER ---")
    prompt = build_confirmation_prompt(
        {
            "intent": "EMPTY_RECYCLE_BIN",
            "slots": {},
        }
    )

    prompt_ok = isinstance(prompt, str) and bool(prompt.strip())
    print(json.dumps({"prompt": prompt}, ensure_ascii=False))

    if not prompt_ok:
        fail_count += 1
        print("[FAIL] expected non-empty confirmation prompt")
    else:
        print("[OK] prompt is not empty")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "yes_cases": len(YES_CASES),
                "no_cases": len(NO_CASES),
                "neutral_cases": len(NEUTRAL_CASES),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())