from __future__ import annotations

import json
from typing import List

from dotenv import load_dotenv

load_dotenv()

from modules.dictation_commands import is_dictation_stop_phrase, strip_hotword_prefix


HOTWORDS = ("скайнет", "skynet")


STOP_CASES: List[str] = [
    "прекрати печать",
    "останови печать",
    "выйди из режима диктовки",
    "выключи режим диктовки",
    "выйди из режима ввода текста",
    "выключи режим ввода текста",
    "заверши диктовку",
]


STOP_WITH_HOTWORD_CASES: List[str] = [
    "скайнет прекрати печать",
    "скайнет выключи режим диктовки",
    "skynet заверши диктовку",
]


NEUTRAL_CASES: List[str] = [
    "",
    "печатаю текст",
    "привет",
    "открой блокнот",
    "режим диктовки",
    "нажми enter",
    "удали символ",
]


def main() -> int:
    fail_count = 0

    print("=== DICTATION COMMANDS EVAL REPORT ===")

    print()
    print("--- STOP PHRASES ---")
    for text in STOP_CASES:
        actual = is_dictation_stop_phrase(text)
        print(json.dumps({"text": text, "is_stop": actual}, ensure_ascii=False))

        if not actual:
            fail_count += 1
            print("[FAIL] expected stop phrase")
        else:
            print("[OK] stop phrase")

    print()
    print("--- STOP PHRASES WITH HOTWORD ---")
    for text in STOP_WITH_HOTWORD_CASES:
        stripped = strip_hotword_prefix(text, hotwords=HOTWORDS)
        actual = is_dictation_stop_phrase(text, hotwords=HOTWORDS)

        print(
            json.dumps(
                {
                    "text": text,
                    "stripped": stripped,
                    "is_stop": actual,
                },
                ensure_ascii=False,
            )
        )

        if not actual:
            fail_count += 1
            print("[FAIL] expected stop phrase with hotword")
        else:
            print("[OK] stop phrase with hotword")

    print()
    print("--- NEUTRAL PHRASES ---")
    for text in NEUTRAL_CASES:
        actual = is_dictation_stop_phrase(text)
        print(json.dumps({"text": text, "is_stop": actual}, ensure_ascii=False))

        if actual:
            fail_count += 1
            print("[FAIL] expected neutral phrase")
        else:
            print("[OK] neutral phrase")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "stop_cases": len(STOP_CASES),
                "stop_with_hotword_cases": len(STOP_WITH_HOTWORD_CASES),
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