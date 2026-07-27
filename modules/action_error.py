from __future__ import annotations

from typing import Any, Mapping


DEFAULT_ACTION_FAILURE_MESSAGE = "Не получилось выполнить команду."


class ActionExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        intent: str,
        operation: str,
        detail: str,
        user_message: str = DEFAULT_ACTION_FAILURE_MESSAGE,
        error_code: str = "action_failed",
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.intent = str(intent or "").upper().strip()
        self.operation = str(operation or "execute").strip().lower()
        self.detail = str(detail or "Unknown action failure").strip()
        self.user_message = str(user_message or DEFAULT_ACTION_FAILURE_MESSAGE).strip()
        self.error_code = str(error_code or "action_failed").strip().lower()
        self.context = dict(context or {})

        super().__init__(f"{self.operation}: {self.detail}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "operation": self.operation,
            "error_code": self.error_code,
            "error_type": type(self).__name__,
            "error": self.detail,
            "user_message": self.user_message,
            "context": dict(self.context),
        }