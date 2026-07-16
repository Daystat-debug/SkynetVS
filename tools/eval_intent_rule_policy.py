from __future__ import annotations

import json

from modules.intent_rules import EXACT_INTENT_RULES


ALLOWED_EXACT_RULE_INTENTS = {
    "STOP_LISTEN",
    "STOP_TALKING",

    "MUTE",
    "UNMUTE",
    "VOLUME_UP",
    "VOLUME_DOWN",

    "MUSIC_PLAY",
    "MUSIC_PAUSE",
    "MUSIC_NEXT",
    "MUSIC_PREV",
    "MUSIC_STOP",
    "MUSIC_RESTART",

    "DICTATION_MODE_ON",
    "DICTATION_MODE_OFF",

    "PRESS_ENTER",
    "PRESS_BACKSPACE",
    "PRESS_TAB",

    "SET_TIMER",
    "TIMER_STATUS",
    "CANCEL_TIMER",
}


def main() -> int:
    mapped_intents = sorted(set(EXACT_INTENT_RULES.values()))
    unexpected_intents = sorted(
        intent
        for intent in mapped_intents
        if intent not in ALLOWED_EXACT_RULE_INTENTS
    )
    system_status_phrases = sorted(
        phrase
        for phrase, intent in EXACT_INTENT_RULES.items()
        if intent == "SYSTEM_STATUS"
    )

    result = {
        "mapped_intents": mapped_intents,
        "unexpected_intents": unexpected_intents,
        "system_status_phrases": system_status_phrases,
        "ok": not unexpected_intents and not system_status_phrases,
    }

    print("=== INTENT RULE POLICY ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["ok"]:
        print("[OK] Intent rule policy")
        return 0

    print("[FAIL] Ordinary semantic intent was added to exact rules")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())