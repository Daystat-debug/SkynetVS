from __future__ import annotations

from typing import Any, Iterable, Mapping, Protocol

from modules.command_decision import build_command_decision
from modules.nlu import (
    pick_generic_uncertain_response,
    pick_uncertain_response,
)


class ReplyRouter(Protocol):
    def reply(self, meta: dict[str, Any]) -> str:
        ...


DEFAULT_FORCE_BASE_REPLY_INTENTS = {
    "SHOW_IP",
    "WEATHER",
    "SET_TIMER",
    "TIMER_STATUS",
    "CANCEL_TIMER",
}


def build_reply_text(
    *,
    router: ReplyRouter,
    meta: Mapping[str, Any],
    accept_conf: float,
    say_conf: float,
    force_base_reply_intents: Iterable[str] = DEFAULT_FORCE_BASE_REPLY_INTENTS,
) -> str:
    """
    Строит текст ответа ассистента.

    Логика:
      - accepted + высокая уверенность -> обычный reply;
      - accepted + низкая уверенность -> uncertain reply;
      - not accepted -> fallback из meta["say"].
    """
    meta_dict = dict(meta)
    intent = str(meta.get("intent") or "").upper()
    slots = dict(meta.get("slots") or {})
    conf = float(meta.get("confidence") or 0.0)

    decision = build_command_decision(
        meta,
        accept_conf=accept_conf,
    )

    if decision.accepted:
        base = router.reply(meta_dict) or (meta.get("say") or "...")

        force_base = {
            str(x).upper()
            for x in force_base_reply_intents
        }

        if conf >= say_conf or intent in force_base:
            return base

        uncertain = pick_uncertain_response(
            intent,
            slots,
        )
        if uncertain:
            return uncertain

        generic_uncertain = pick_generic_uncertain_response()
        if generic_uncertain:
            return generic_uncertain

        return "Похоже, я не до конца уверен, но попробую выполнить команду."

    return str(meta.get("say") or "Не понял команду. Повтори, пожалуйста.")