from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.stt_refinement import SttRefinementResult
from modules.command_understanding import (
    _maybe_accept_refinement_that_fills_missing_slots,
    _maybe_accept_registry_entity_rescue,
    understand_command_text,
)


class FakeLogger:
    def __init__(self) -> None:
        self.events: List[dict[str, Any]] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"kind": kind, "payload": payload})


class FakeRouter:
    def preprocess(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        return meta


class FakeSTT:
    last_utterance_audio = b"audio"
    last_utterance_text = "скайнет открой окна и"
    samplerate = 16000

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "engine": "fake",
            "active_model_path": "models/test",
            "last_utterance_text": self.last_utterance_text,
            "last_utterance_audio_bytes": len(self.last_utterance_audio),
            "last_utterance_duration_sec": 1.0,
        }


class FakeWhisper:
    def __init__(self, text: str = "открой openai") -> None:
        self.text = text
        self.calls = 0

    def refine_pcm(self, pcm: bytes, *, samplerate: int) -> str:
        _ = pcm
        _ = samplerate
        self.calls += 1
        return self.text


def _print_case(
    name: str,
    *,
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    errors: List[str],
) -> None:
    print()
    print(f"=== {name} ===")
    print(
        json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "errors": errors,
                "ok": not errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print(f"[OK] {name}")


def _check_equal(
    errors: List[str],
    *,
    name: str,
    actual: Any,
    expected: Any,
) -> None:
    if actual != expected:
        errors.append(
            f"{name}: expected={expected!r}, actual={actual!r}"
        )


def _run_end_to_end_trigger_case() -> List[str]:
    """
    Проверяет, что accepted intent с отсутствующим обязательным slot
    действительно запускает Whisper и принимает безопасный OPEN_URL-кандидат.
    """
    logger = FakeLogger()
    whisper = FakeWhisper("открой openai")

    result = understand_command_text(
        "открой окна и",
        router=FakeRouter(),
        logger=logger,
        whisper=whisper,
        stt=FakeSTT(),
        accept_conf=0.35,
        whisper_trigger_conf=0.99,
        print_func=None,
    )

    diagnostic_events = [
        event
        for event in logger.events
        if event.get("kind") == "stt_diagnostic"
    ]
    payload = diagnostic_events[-1]["payload"] if diagnostic_events else {}

    actual = {
        "final_text": result.final_text,
        "intent": result.meta.get("intent"),
        "site": (result.meta.get("slots") or {}).get("site"),
        "url": (result.meta.get("slots") or {}).get("url"),
        "whisper_calls": whisper.calls,
        "diagnostic_trigger_reason": payload.get(
            "refinement_trigger_reason"
        ),
        "diagnostic_refinement_reason": payload.get(
            "refinement_reason"
        ),
        "diagnostic_changed": payload.get(
            "changed_by_refinement"
        ),
    }

    expected = {
        "final_text": "открой openai",
        "intent": "OPEN_URL",
        "site": "openai",
        "url": "https://openai.com",
        "whisper_calls": 1,
        "diagnostic_trigger_reason": "missing_required_slots",
        "diagnostic_refinement_reason": "accepted_refinement",
        "diagnostic_changed": True,
    }

    errors: List[str] = []
    for key, expected_value in expected.items():
        _check_equal(
            errors,
            name=key,
            actual=actual.get(key),
            expected=expected_value,
        )

    _print_case(
        "END-TO-END MISSING-SLOTS TRIGGER",
        actual=actual,
        expected=expected,
        errors=errors,
    )
    return errors


def _apply_policy(
    *,
    candidate_text: str,
    candidate_meta: Dict[str, Any],
    initially_changed: bool,
    initial_reason: str,
) -> SttRefinementResult:
    original_text = "открой окна и"
    original_meta = {
        "intent": "OPEN_URL",
        "confidence": 0.70,
        "slots": {},
        "_text": original_text,
    }

    refinement = SttRefinementResult(
        text=candidate_text if initially_changed else original_text,
        meta=candidate_meta if initially_changed else original_meta,
        changed=initially_changed,
        reason=initial_reason,
        candidate_text=candidate_text,
        candidate_meta=candidate_meta,
        trigger_reason="missing_required_slots",
    )

    return _maybe_accept_refinement_that_fills_missing_slots(
        refinement,
        original_text=original_text,
        original_meta=original_meta,
        missing_slots_before_refinement=["url"],
        force_refine_missing_slots=True,
        accept_conf=0.35,
    )


def _run_positive_policy_case() -> List[str]:
    result = _apply_policy(
        candidate_text="скайнет открой open ai",
        candidate_meta={
            "intent": "OPEN_URL",
            "confidence": 0.39,
            "slots": {
                "site": "openai",
                "site_title": "openai",
                "url": "https://openai.com",
            },
        },
        initially_changed=False,
        initial_reason="refinement_not_better",
    )

    actual = {
        "changed": result.changed,
        "reason": result.reason,
        "final_intent": result.meta.get("intent"),
        "final_url": (result.meta.get("slots") or {}).get("url"),
    }
    expected = {
        "changed": True,
        "reason": "accepted_refinement",
        "final_intent": "OPEN_URL",
        "final_url": "https://openai.com",
    }

    errors: List[str] = []
    for key, expected_value in expected.items():
        _check_equal(
            errors,
            name=key,
            actual=actual.get(key),
            expected=expected_value,
        )

    _print_case(
        "KNOWN OPEN_URL CANDIDATE ACCEPTED",
        actual=actual,
        expected=expected,
        errors=errors,
    )
    return errors


def _run_rejected_policy_case(
    *,
    name: str,
    candidate_text: str,
    candidate_meta: Dict[str, Any],
) -> List[str]:
    """
    Передаём initially_changed=True намеренно: guard обязан откатить даже
    предварительно принятый небезопасный результат базовой refinement-логики.
    """
    result = _apply_policy(
        candidate_text=candidate_text,
        candidate_meta=candidate_meta,
        initially_changed=True,
        initial_reason="accepted_refinement",
    )

    actual = {
        "changed": result.changed,
        "reason": result.reason,
        "final_text": result.text,
        "final_intent": result.meta.get("intent"),
        "final_slots": result.meta.get("slots") or {},
        "candidate_intent": (
            result.candidate_meta or {}
        ).get("intent"),
    }
    expected = {
        "changed": False,
        "reason": "refinement_not_better",
        "final_text": "открой окна и",
        "final_intent": "OPEN_URL",
        "final_slots": {},
    }

    errors: List[str] = []
    for key, expected_value in expected.items():
        _check_equal(
            errors,
            name=key,
            actual=actual.get(key),
            expected=expected_value,
        )

    _print_case(
        name,
        actual=actual,
        expected=expected,
        errors=errors,
    )
    return errors


def _run_registry_rescue_case(
    *,
    name: str,
    original_text: str,
    candidate_text: str,
    expected_site: str | None,
) -> List[str]:
    original_meta = {
        "intent": "OPEN_URL",
        "confidence": 0.60,
        "slots": {},
        "_text": original_text,
    }

    refinement = SttRefinementResult(
        text=original_text,
        meta=original_meta,
        changed=False,
        reason="refinement_not_better",
        candidate_text=candidate_text,
        candidate_meta={
            "intent": "OPEN_URL",
            "confidence": 0.50,
            "slots": {},
        },
        trigger_reason="missing_required_slots",
    )

    result, rescue = (
        _maybe_accept_registry_entity_rescue(
            refinement,
            original_text=original_text,
            original_meta=original_meta,
            missing_slots_before_refinement=["url"],
            force_refine_missing_slots=True,
            accept_conf=0.35,
        )
    )

    slots = result.meta.get("slots") or {}

    actual = {
        "changed": result.changed,
        "reason": result.reason,
        "intent": result.meta.get("intent"),
        "site": slots.get("site"),
        "url": slots.get("url"),
        "rescue_found": rescue is not None,
    }

    should_accept = expected_site is not None

    expected = {
        "changed": should_accept,
        "reason": (
            "accepted_registry_rescue"
            if should_accept
            else "refinement_not_better"
        ),
        "intent": "OPEN_URL",
        "site": expected_site,
        "url": (
            "https://openai.com"
            if expected_site == "openai"
            else (
                "https://chatgpt.com"
                if expected_site == "chatgpt"
                else None
            )
        ),
        "rescue_found": should_accept,
    }

    errors: List[str] = []

    for key, expected_value in expected.items():
        _check_equal(
            errors,
            name=key,
            actual=actual.get(key),
            expected=expected_value,
        )

    _print_case(
        name,
        actual=actual,
        expected=expected,
        errors=errors,
    )

    return errors


def main() -> int:
    all_errors: List[str] = []

    print("=== STT MISSING SLOTS TRIGGER EVAL REPORT ===")

    all_errors.extend(_run_end_to_end_trigger_case())
    all_errors.extend(_run_positive_policy_case())

    all_errors.extend(
        _run_rejected_policy_case(
            name="DIFFERENT INTENT GREET REJECTED",
            candidate_text="скайнет открою оптнай.com",
            candidate_meta={
                "intent": "GREET",
                "confidence": 0.41,
                "slots": {},
            },
        )
    )

    all_errors.extend(
        _run_rejected_policy_case(
            name="DIFFERENT INTENT OPEN_APP REJECTED",
            candidate_text="скайнет открой дискорд",
            candidate_meta={
                "intent": "OPEN_APP",
                "confidence": 0.46,
                "slots": {
                    "app": "discord",
                },
            },
        )
    )

    all_errors.extend(
        _run_rejected_policy_case(
            name="UNKNOWN DOMAIN REJECTED",
            candidate_text="скайнет открой www.opanae.com",
            candidate_meta={
                "intent": "OPEN_URL",
                "confidence": 0.44,
                "slots": {
                    "site": "www.opanae",
                    "site_title": "www.opanae",
                    "url": "https://www.opanae",
                },
            },
        )
    )

    all_errors.extend(
        _run_registry_rescue_case(
            name="OPENI DOMAIN RESCUED AS OPENAI",
            original_text="открой окна и",
            candidate_text="открой openi.com",
            expected_site="openai",
        )
    )

    all_errors.extend(
        _run_registry_rescue_case(
            name="CHATGPT RAW TEXT RESCUED",
            original_text="открой чад же пяти",
            candidate_text="аппетим",
            expected_site="chatgpt",
        )
    )

    all_errors.extend(
        _run_registry_rescue_case(
            name="OPENAE DOMAIN REMAINS REJECTED",
            original_text="открой окна и",
            candidate_text="открой openae.com",
            expected_site=None,
        )
    )

    all_errors.extend(
        _run_registry_rescue_case(
            name="OPENAPI DOMAIN REMAINS REJECTED",
            original_text="открой окна и",
            candidate_text="открой openapi.com",
            expected_site=None,
        )
    )

    all_errors.extend(
        _run_registry_rescue_case(
            name="OPENAI SPOKEN DISTORTION RESCUED",
            original_text="открой оп анаид",
            candidate_text="открой опы на и",
            expected_site="openai",
        )
    )

    all_errors.extend(
        _run_registry_rescue_case(
            name="OPENAI DOT COM SPOKEN DISTORTION RESCUED",
            original_text="открой опыт ай точка ком",
            candidate_text="аи.ком",
            expected_site="openai",
        )
    )

    all_errors.extend(
        _run_registry_rescue_case(
            name="CHATGPT CHARGE GPT RESCUED",
            original_text="открой чат пяти",
            candidate_text="sky-net открой charge-gpt",
            expected_site="chatgpt",
        )
    )

    all_errors.extend(
        _run_registry_rescue_case(
            name="COMMON WORD EXPERIENCE REMAINS REJECTED",
            original_text="открой опытной",
            candidate_text="",
            expected_site=None,
        )
    )

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "case_count": 13,
                "error_count": len(all_errors),
                "ok": not all_errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
