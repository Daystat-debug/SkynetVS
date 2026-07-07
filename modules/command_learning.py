from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence


class LearningMemoryLike(Protocol):
    def log_command(
        self,
        *,
        raw_text: str,
        final_text: str,
        meta: Mapping[str, Any],
        mode: str,
        accepted: bool,
        immediate_label: str,
        missing_slots: Sequence[str],
    ) -> None:
        ...

    def log_resolver_candidate(
        self,
        *,
        raw_text: str,
        final_text: str,
        meta: Mapping[str, Any],
        mode: str,
        missing_slots: Sequence[str],
        reason: str,
    ) -> None:
        ...

    def log_nlu_hard_case(
        self,
        *,
        raw_text: str,
        final_text: str,
        meta: Mapping[str, Any],
        mode: str,
        reason: str,
    ) -> None:
        ...

    def log_action_failure(
        self,
        *,
        raw_text: str,
        final_text: str,
        meta: Mapping[str, Any],
        mode: str,
        error: Exception,
    ) -> None:
        ...


def log_command_observation(
    *,
    learning_memory: LearningMemoryLike,
    raw_text: str,
    final_text: str,
    meta: Mapping[str, Any],
    mode: str,
    accepted: bool,
    immediate_label: str,
    missing_slots: Sequence[str],
) -> None:
    """
    Логирует обычный результат понимания команды.

    Если есть missing_slots, дополнительно пишет resolver candidate.
    """
    meta_dict = dict(meta)
    missing = list(missing_slots)

    learning_memory.log_command(
        raw_text=raw_text,
        final_text=final_text,
        meta=meta_dict,
        mode=mode,
        accepted=accepted,
        immediate_label=immediate_label,
        missing_slots=missing,
    )

    if missing:
        learning_memory.log_resolver_candidate(
            raw_text=raw_text,
            final_text=final_text,
            meta=meta_dict,
            mode=mode,
            missing_slots=missing,
            reason="missing_required_slots",
        )


def log_not_accepted_command(
    *,
    learning_memory: LearningMemoryLike,
    raw_text: str,
    final_text: str,
    meta: Mapping[str, Any],
    mode: str,
    reason: str,
) -> None:
    learning_memory.log_nlu_hard_case(
        raw_text=raw_text,
        final_text=final_text,
        meta=dict(meta),
        mode=mode,
        reason=reason,
    )


def log_command_action_failure(
    *,
    learning_memory: LearningMemoryLike,
    raw_text: str,
    final_text: str,
    meta: Mapping[str, Any],
    mode: str,
    error: Exception,
) -> None:
    learning_memory.log_action_failure(
        raw_text=raw_text,
        final_text=final_text,
        meta=dict(meta),
        mode=mode,
        error=error,
    )