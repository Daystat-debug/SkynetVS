from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


EventFunc = Callable[[str, dict[str, Any]], None]
PrintFunc = Callable[[str], None]
CleanupFunc = Callable[[], Any]


@dataclass(frozen=True)
class RuntimeShutdownFailure:
    service: str
    operation: str
    error_type: str
    error: str


@dataclass(frozen=True)
class RuntimeShutdownReport:
    attempted: tuple[str, ...]
    succeeded: tuple[str, ...]
    failures: tuple[RuntimeShutdownFailure, ...]


def _error_text(error: BaseException) -> str:
    return str(error).strip() or type(error).__name__


def _safe_print(
    print_func: PrintFunc | None,
    message: str,
) -> None:
    if print_func is None:
        return

    try:
        print_func(message)
    except Exception:
        pass


def _safe_event(
    event_func: EventFunc | None,
    kind: str,
    payload: dict[str, Any],
) -> None:
    if event_func is None:
        return

    try:
        event_func(kind, payload)
    except Exception:
        pass


def shutdown_runtime_services(
    *,
    cancel_command_timer_func: CleanupFunc,
    tts: Any,
    timer_service: Any,
    reminder_service: Any,
    event_func: EventFunc | None = None,
    print_func: PrintFunc | None = print,
) -> RuntimeShutdownReport:
    attempted: list[str] = []
    succeeded: list[str] = []
    failures: list[RuntimeShutdownFailure] = []

    def attempt(
        service: str,
        operation: str,
        cleanup_func: CleanupFunc,
    ) -> bool:
        key = f"{service}.{operation}"
        attempted.append(key)

        try:
            cleanup_func()
        except Exception as error:
            failure = RuntimeShutdownFailure(
                service=service,
                operation=operation,
                error_type=type(error).__name__,
                error=_error_text(error),
            )
            failures.append(failure)

            _safe_print(
                print_func,
                f"[SHUTDOWN] {service}.{operation} failed: {failure.error}",
            )
            _safe_event(
                event_func,
                "runtime_shutdown_failed",
                {
                    "service": failure.service,
                    "operation": failure.operation,
                    "error_type": failure.error_type,
                    "error": failure.error,
                },
            )
            return False

        succeeded.append(key)
        return True

    attempt(
        "command_timer",
        "cancel",
        cancel_command_timer_func,
    )

    if tts is not None:
        def stop_tts() -> None:
            if not tts.stop():
                raise RuntimeError(
                    "TTS stop returned false"
                )

        attempt(
            "tts",
            "stop",
            stop_tts,
        )

    if timer_service is not None:
        attempt(
            "timer",
            "cancel",
            timer_service.cancel,
        )

    if reminder_service is not None:
        reminder_shutdown_ok = attempt(
            "reminders",
            "shutdown",
            reminder_service.shutdown,
        )

        if reminder_shutdown_ok:
            def report_reminder_shutdown() -> None:
                snapshot = reminder_service.status()

                if event_func is not None:
                    event_func(
                        "reminder_service_stopped",
                        {
                            "remaining_count": snapshot.count,
                        },
                    )

            attempt(
                "reminders",
                "report_stopped",
                report_reminder_shutdown,
            )

    return RuntimeShutdownReport(
        attempted=tuple(attempted),
        succeeded=tuple(succeeded),
        failures=tuple(failures),
    )