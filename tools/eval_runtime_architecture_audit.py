from __future__ import annotations

import ast
import json

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from modules.action_error import ActionExecutionError
from modules.actions import Actions
from modules.router import Router
from modules.runtime_service_health import RuntimeServiceHealth
from modules.runtime_service_health_monitor import RuntimeServiceHealthMonitor
from modules.runtime_shutdown import shutdown_runtime_services


class DummyService:
    pass


class FalseyService:
    def __bool__(self) -> bool:
        return False


class UnexpectedAudioOutput:
    def set_headphones(self) -> Any:
        return SimpleNamespace(
            status="unexpected_status"
        )


class RepeatActions:
    def __init__(self) -> None:
        self.fail = True

    def handle(
        self,
        meta: dict[str, Any],
    ) -> str:
        return str(
            meta.get("intent") or ""
        )

    def execute(
        self,
        meta: dict[str, Any],
    ) -> None:
        _ = meta

        if self.fail:
            raise RuntimeError(
                "fake repeatable action failure"
            )


class FakeClock:
    def __init__(
        self,
        value: float = 1000.0,
    ) -> None:
        self.value = float(value)

    def __call__(self) -> float:
        return self.value

    def advance(
        self,
        seconds: float,
    ) -> None:
        self.value += float(seconds)


class FakeTTS:
    def __init__(
        self,
        events: list[str],
        *,
        stop_result: bool,
    ) -> None:
        self._events = events
        self._stop_result = stop_result

    def stop(self) -> bool:
        self._events.append(
            "tts.stop"
        )
        return self._stop_result


class FakeTimerService:
    def __init__(
        self,
        events: list[str],
        *,
        error: Exception | None = None,
    ) -> None:
        self._events = events
        self._error = error

    def cancel(self) -> None:
        self._events.append(
            "timer.cancel"
        )

        if self._error is not None:
            raise self._error


class FakeReminderService:
    def __init__(
        self,
        events: list[str],
        *,
        count: int = 0,
    ) -> None:
        self._events = events
        self._count = int(count)

    def shutdown(self) -> None:
        self._events.append(
            "reminders.shutdown"
        )

    def status(self) -> Any:
        self._events.append(
            "reminders.status"
        )
        return SimpleNamespace(
            count=self._count
        )


def _call_name(
    node: ast.AST,
) -> str:
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return node.attr

    return ""


def _find_calls(
    tree: ast.AST,
    name: str,
) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and _call_name(node.func) == name
        )
    ]


def _keyword_map(
    call: ast.Call,
) -> dict[str, str]:
    return {
        str(item.arg): ast.unparse(
            item.value
        )
        for item in call.keywords
        if item.arg is not None
    }


def _find_method(
    tree: ast.Module,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef:
    for node in tree.body:
        if (
            not isinstance(node, ast.ClassDef)
            or node.name != class_name
        ):
            continue

        for item in node.body:
            if (
                isinstance(item, ast.FunctionDef)
                and item.name == method_name
            ):
                return item

    raise RuntimeError(
        f"Method not found: {class_name}.{method_name}"
    )


def _new_actions(
    *,
    audio_output: Any = None,
    timer_service: Any = None,
    reminder_service: Any = None,
    event_func: Callable[
        [str, dict[str, Any]],
        None,
    ] | None = None,
) -> Actions:
    return Actions(
        audio=None,
        audio_output=audio_output,
        screenshot_service=DummyService(),
        weather_service=DummyService(),
        typing_service=DummyService(),
        window_context_service=DummyService(),
        timer_service=timer_service,
        reminder_service=reminder_service,
        event_func=event_func,
    )


def _capture_action_failure(
    intent: str,
    slots: dict[str, Any],
) -> dict[str, Any]:
    events: list[str] = []

    actions = _new_actions(
        event_func=lambda name, payload: events.append(
            name
        )
    )

    try:
        actions.execute(
            {
                "intent": intent,
                "slots": slots,
            }
        )
    except ActionExecutionError as error:
        return {
            "intent": intent,
            "error_code": error.error_code,
            "operation": error.operation,
            "service": error.context.get(
                "service"
            ),
            "event_count": len(events),
        }
    except Exception as error:
        return {
            "intent": intent,
            "error_type": type(error).__name__,
        }

    return {
        "intent": intent,
        "error_type": "not_raised",
    }


def _health_report(
    status: str,
    *,
    error: str = "",
    version: int = 1,
):
    health = RuntimeServiceHealth()

    if status == "ready":
        health.ready(
            "stt",
            details={
                "version": version,
            },
        )
    else:
        health.degraded(
            "stt",
            details={
                "version": version,
            },
            error=error,
        )

    return health.build()


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(
        name: str,
        actual: Any,
        expected: Any,
    ) -> None:
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

    actions_path = Path(
        "modules/actions.py"
    )
    main_path = Path(
        "main.py"
    )
    pipeline_path = Path(
        "tools/pipeline.py"
    )

    actions_tree = ast.parse(
        actions_path.read_text(
            encoding="utf-8"
        )
    )
    main_tree = ast.parse(
        main_path.read_text(
            encoding="utf-8"
        )
    )

    actions_init = _find_method(
        actions_tree,
        "Actions",
        "__init__",
    )

    hidden_constructors = sorted({
        _call_name(node.func)
        for node in ast.walk(
            actions_init
        )
        if (
            isinstance(node, ast.Call)
            and _call_name(node.func) in {
                "ScreenshotService",
                "WeatherService",
                "TypingService",
                "WindowContextService",
            }
        )
    })

    check(
        "ACTIONS DOES NOT CREATE HIDDEN RUNTIME SERVICES",
        hidden_constructors,
        [],
    )

    services = {
        name: FalseyService()
        for name in (
            "audio",
            "audio_output",
            "screenshot",
            "weather",
            "typing",
            "window",
            "timer",
            "reminder",
        )
    }

    actions = Actions(
        audio=services["audio"],
        audio_output=services["audio_output"],
        screenshot_service=services["screenshot"],
        weather_service=services["weather"],
        typing_service=services["typing"],
        window_context_service=services["window"],
        timer_service=services["timer"],
        reminder_service=services["reminder"],
    )

    identity = {
        "audio": (
            actions._audio
            is services["audio"]
        ),
        "audio_output": (
            actions._audio_output
            is services["audio_output"]
        ),
        "screenshot": (
            actions._screenshot_service
            is services["screenshot"]
        ),
        "weather": (
            actions._weather_service
            is services["weather"]
        ),
        "typing": (
            actions._typing_service
            is services["typing"]
        ),
        "window": (
            actions._window_context_service
            is services["window"]
        ),
        "timer": (
            actions._timer_service
            is services["timer"]
        ),
        "reminder": (
            actions._reminder_actions
            is not None
            and actions._reminder_actions._service
            is services["reminder"]
        ),
    }

    check(
        "FALSEY DEPENDENCIES PRESERVE IDENTITY",
        identity,
        {
            name: True
            for name in identity
        },
    )

    constructors = (
        "VoskSTT",
        "EdgeTTS",
        "AudioControl",
        "AudioOutputControl",
        "ScreenshotService",
        "WeatherService",
        "TypingService",
        "WindowContextService",
        "TimerService",
        "ReminderService",
        "RuntimeServiceHealthMonitor",
        "Actions",
        "Router",
    )

    actions_calls = _find_calls(
        main_tree,
        "Actions",
    )
    health_calls = _find_calls(
        main_tree,
        "collect_runtime_service_health",
    )

    actions_args = (
        _keyword_map(actions_calls[0])
        if len(actions_calls) == 1
        else {}
    )
    health_args = (
        _keyword_map(health_calls[0])
        if len(health_calls) == 1
        else {}
    )

    shared = (
        "audio",
        "audio_output",
        "weather_service",
        "timer_service",
        "reminder_service",
    )

    ownership = {
        "constructor_counts": {
            name: len(
                _find_calls(
                    main_tree,
                    name,
                )
            )
            for name in constructors
        },
        "actions_call_count": len(
            actions_calls
        ),
        "health_call_count": len(
            health_calls
        ),
        "shared": {
            name: (
                actions_args.get(name)
                == health_args.get(name)
                == name
            )
            for name in shared
        },
    }

    check(
        "MAIN OWNS ONE INSTANCE AND SHARES IT WITH ACTIONS AND HEALTH",
        ownership,
        {
            "constructor_counts": {
                name: 1
                for name in constructors
            },
            "actions_call_count": 1,
            "health_call_count": 1,
            "shared": {
                name: True
                for name in shared
            },
        },
    )

    unavailable_cases = (
        (
            "AUDIO_OUTPUT_HEADPHONES",
            {},
            "audio_output_unavailable",
            "audio_output.switch",
            "audio_output",
            1,
        ),
        (
            "SET_TIMER",
            {
                "duration_seconds": 10,
            },
            "timer_unavailable",
            "timer.start",
            "timer",
            0,
        ),
        (
            "CANCEL_TIMER",
            {},
            "timer_unavailable",
            "timer.cancel",
            "timer",
            0,
        ),
        (
            "CREATE_REMINDER",
            {},
            "reminder_unavailable",
            "reminder.create",
            "reminder",
            0,
        ),
        (
            "CANCEL_REMINDER",
            {},
            "reminder_unavailable",
            "reminder.cancel",
            "reminder",
            0,
        ),
    )

    unavailable_actual = [
        _capture_action_failure(
            intent,
            slots,
        )
        for intent, slots, *_ in unavailable_cases
    ]

    unavailable_expected = [
        {
            "intent": intent,
            "error_code": error_code,
            "operation": operation,
            "service": service,
            "event_count": event_count,
        }
        for (
            intent,
            _,
            error_code,
            operation,
            service,
            event_count,
        ) in unavailable_cases
    ]

    check(
        "UNAVAILABLE CRITICAL SERVICES ARE EXPLICIT ACTION FAILURES",
        unavailable_actual,
        unavailable_expected,
    )

    output_events: list[
        dict[str, Any]
    ] = []

    actions = _new_actions(
        audio_output=UnexpectedAudioOutput(),
        event_func=lambda name, payload: output_events.append(
            {
                "name": name,
                "status": payload.get(
                    "status"
                ),
            }
        ),
    )

    output_error = ""

    try:
        actions.execute(
            {
                "intent": "AUDIO_OUTPUT_HEADPHONES",
                "slots": {},
            }
        )
    except Exception as error:
        output_error = str(error)

    check(
        "UNEXPECTED AUDIO OUTPUT STATUS EMITS ONE FAILURE EVENT",
        {
            "error": output_error,
            "events": output_events,
        },
        {
            "error": (
                "Unexpected audio output status: "
                "unexpected_status"
            ),
            "events": [
                {
                    "name": "audio_output_failed",
                    "status": "unexpected_error",
                },
            ],
        },
    )

    repeat_actions = RepeatActions()

    router = Router(
        repeat_actions,
        settings=SimpleNamespace(
            exec_mode="direct",
            repeat_context_sec=15.0,
        ),
    )

    failed_raised = False

    try:
        router.execute(
            {
                "intent": "VOLUME_UP",
                "confidence": 1.0,
                "slots": {},
                "_text": "сделай громче",
            }
        )
    except RuntimeError:
        failed_raised = True

    after_failure = router.preprocess(
        {
            "intent": None,
            "confidence": 0.0,
            "slots": {},
            "_text": "ещё",
        }
    )

    repeat_actions.fail = False

    router.execute(
        {
            "intent": "VOLUME_UP",
            "confidence": 1.0,
            "slots": {},
            "_text": "сделай громче",
        }
    )

    after_success = router.preprocess(
        {
            "intent": None,
            "confidence": 0.0,
            "slots": {},
            "_text": "ещё",
        }
    )

    check(
        "FAILED REPEATABLE ACTION IS NOT STORED",
        {
            "failed_raised": failed_raised,
            "after_failure": (
                after_failure.get("intent"),
                after_failure.get(
                    "_repeat_failed"
                ),
            ),
            "after_success": (
                after_success.get("intent"),
                after_success.get(
                    "_from_history"
                ),
            ),
        },
        {
            "failed_raised": True,
            "after_failure": (
                None,
                True,
            ),
            "after_success": (
                "VOLUME_UP",
                True,
            ),
        },
    )

    clock = FakeClock()

    monitor = RuntimeServiceHealthMonitor(
        enabled=True,
        interval_sec=1.0,
        monotonic_func=clock,
    )

    monitor.set_baseline(
        _health_report(
            "ready",
            version=1,
        )
    )

    clock.advance(1.0)

    degraded = monitor.poll_if_due(
        lambda: _health_report(
            "degraded",
            error="STT heartbeat is stale",
            version=2,
        )
    )

    clock.advance(1.0)

    details_only = monitor.poll_if_due(
        lambda: _health_report(
            "degraded",
            error="STT heartbeat is stale",
            version=3,
        )
    )

    clock.advance(1.0)

    recovered = monitor.poll_if_due(
        lambda: _health_report(
            "ready",
            version=4,
        )
    )

    check(
        "HEALTH MONITOR DETECTS FAILURE AND RECOVERY WITHOUT DETAILS NOISE",
        {
            "degraded": (
                degraded
                .transition
                .changed_services[0]
                .previous_status,
                degraded
                .transition
                .changed_services[0]
                .current_status,
            ),
            "details_only_transition": (
                details_only.transition
                is not None
            ),
            "recovered": (
                recovered
                .transition
                .changed_services[0]
                .previous_status,
                recovered
                .transition
                .changed_services[0]
                .current_status,
            ),
        },
        {
            "degraded": (
                "ready",
                "degraded",
            ),
            "details_only_transition": False,
            "recovered": (
                "degraded",
                "ready",
            ),
        },
    )

    shutdown_events: list[str] = []
    log_events: list[
        dict[str, Any]
    ] = []

    def cancel_command_timer() -> None:
        shutdown_events.append(
            "command_timer.cancel"
        )
        raise RuntimeError(
            "fake command timer failure"
        )

    shutdown_report = shutdown_runtime_services(
        cancel_command_timer_func=cancel_command_timer,
        tts=FakeTTS(
            shutdown_events,
            stop_result=False,
        ),
        timer_service=FakeTimerService(
            shutdown_events,
            error=RuntimeError(
                "fake timer failure"
            ),
        ),
        reminder_service=FakeReminderService(
            shutdown_events,
            count=3,
        ),
        event_func=lambda name, payload: log_events.append(
            {
                "name": name,
                "payload": payload,
            }
        ),
        print_func=None,
    )

    check(
        "SHUTDOWN ATTEMPTS SERVICES INDEPENDENTLY",
        {
            "events": shutdown_events,
            "attempted": list(
                shutdown_report.attempted
            ),
            "succeeded": list(
                shutdown_report.succeeded
            ),
            "failures": [
                f"{item.service}.{item.operation}"
                for item in shutdown_report.failures
            ],
            "log_events": [
                item["name"]
                for item in log_events
            ],
            "remaining_count": next(
                (
                    item["payload"].get(
                        "remaining_count"
                    )
                    for item in log_events
                    if (
                        item["name"]
                        == "reminder_service_stopped"
                    )
                ),
                None,
            ),
        },
        {
            "events": [
                "command_timer.cancel",
                "tts.stop",
                "timer.cancel",
                "reminders.shutdown",
                "reminders.status",
            ],
            "attempted": [
                "command_timer.cancel",
                "tts.stop",
                "timer.cancel",
                "reminders.shutdown",
                "reminders.report_stopped",
            ],
            "succeeded": [
                "reminders.shutdown",
                "reminders.report_stopped",
            ],
            "failures": [
                "command_timer.cancel",
                "tts.stop",
                "timer.cancel",
            ],
            "log_events": [
                "runtime_shutdown_failed",
                "runtime_shutdown_failed",
                "runtime_shutdown_failed",
                "reminder_service_stopped",
            ],
            "remaining_count": 3,
        },
    )

    pipeline_text = pipeline_path.read_text(
        encoding="utf-8"
    )
    monitor_text = Path(
        "modules/runtime_service_health_monitor.py"
    ).read_text(
        encoding="utf-8"
    )
    stt_text = Path(
        "modules/stt_vosk.py"
    ).read_text(
        encoding="utf-8"
    )
    tts_text = Path(
        "modules/tts_edge.py"
    ).read_text(
        encoding="utf-8"
    )
    runtime_text = Path(
        "modules/command_runtime.py"
    ).read_text(
        encoding="utf-8"
    )

    required_checks = (
        "tools/eval_audio_control_windows.py",
        "tools/eval_tts_lifecycle.py",
        "tools/eval_stt_lifecycle.py",
        "tools/eval_stt_health_runtime.py",
        "tools/eval_runtime_service_health_monitor.py",
        "tools/eval_command_runtime.py",
        "tools/eval_developer_task_contract.py",
        "tools/eval_runtime_architecture_audit.py",
    )

    guards = {
        "missing_pipeline_checks": [
            item
            for item in required_checks
            if item not in pipeline_text
        ],
        "main_uses_runtime_shutdown": bool(
            _find_calls(
                main_tree,
                "shutdown_runtime_services",
            )
        ),
        "monitor_has_background_thread": (
            "import threading" in monitor_text
            or "threading.Thread" in monitor_text
        ),
        "stt_generation_guard": all(
            item in stt_text
            for item in (
                "_stream_generation",
                "_last_resumed_at",
                "_resume_pending",
            )
        ),
        "tts_generation_guard": all(
            item in tts_text
            for item in (
                "_operation_seq",
                "_active_operation",
                "terminal_claimed",
            )
        ),
        "command_action_failure_boundary": all(
            item in runtime_text
            for item in (
                "_handle_action_failure",
                'reason="action_failed"',
            )
        ),
        "windows_audio_smoke_exists": Path(
            "tools/eval_audio_control_windows.py"
        ).is_file(),
    }

    check(
        "PRODUCTION GUARDS REMAIN WIRED",
        guards,
        {
            "missing_pipeline_checks": [],
            "main_uses_runtime_shutdown": True,
            "monitor_has_background_thread": False,
            "stt_generation_guard": True,
            "tts_generation_guard": True,
            "command_action_failure_boundary": True,
            "windows_audio_smoke_exists": True,
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