from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from modules.config import Settings
from modules.entity_registry import get_site_url


REPORT_DIR = ROOT / "data" / "logs" / "stt_quality"
LATEST_REPORT = REPORT_DIR / "latest.json"


@dataclass(frozen=True)
class Case:
    code: str
    phrase: str
    intent: str
    slot: str = ""
    value: str = ""
    expected_refinement_reason: str | None = None


def _cases() -> list[Case]:
    return [
        Case(
            "openai",
            "скайнет открой openai",
            "OPEN_URL",
            "url",
            get_site_url("openai"),
        ),
        Case(
            "openai_dot_com",
            "скайнет открой openai точка com",
            "OPEN_URL",
            "url",
            get_site_url("openai"),
        ),
        Case(
            "github",
            "скайнет открой github",
            "OPEN_URL",
            "url",
            get_site_url("github"),
        ),
        Case(
            "chatgpt",
            "скайнет открой chat gpt",
            "OPEN_URL",
            "url",
            get_site_url("chatgpt"),
        ),
        Case(
            "discord",
            "скайнет открой discord",
            "OPEN_APP",
            "app",
            "discord",
        ),
        Case(
            "youtube",
            "скайнет открой youtube",
            "OPEN_URL",
            "url",
            get_site_url("youtube"),
        ),
        Case(
            code="music_play",
            phrase="скайнет запусти музыку",
            intent="MUSIC_PLAY",
            expected_refinement_reason="accepted_complete",
        ),
        Case(
            code="music_pause",
            phrase="скайнет останови музыку",
            intent="MUSIC_PAUSE",
            expected_refinement_reason="accepted_complete",
        ),
    ]


def _runtime_log(explicit: str | None) -> Path:
    path = Path(explicit or Settings.from_env().log_path)

    if path.is_absolute():
        return path

    return ROOT / path


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _wait_event(
    path: Path,
    offset: int,
    timeout: float,
) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(1.0, timeout)

    while time.monotonic() < deadline:
        if _size(path) < offset:
            offset = 0

        if _size(path) > offset:
            with path.open("rb") as stream:
                stream.seek(offset)

                while True:
                    line_start = stream.tell()
                    line = stream.readline()

                    if not line:
                        break

                    # Не потребляем строку, которую logger ещё не дописал.
                    if not line.endswith(b"\n"):
                        offset = line_start
                        break

                    offset = stream.tell()

                    try:
                        row = json.loads(
                            line.decode(
                                "utf-8",
                                errors="replace",
                            )
                        )
                    except Exception:
                        continue

                    if (
                        isinstance(row, dict)
                        and row.get("kind") == "stt_diagnostic"
                    ):
                        return row

        time.sleep(0.2)

    return None


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)

    return {}


def _norm(slot: str, value: Any) -> str:
    text = str(value or "").strip().lower()

    if slot == "url":
        return text.rstrip("/")

    return text


def _matches(
    meta: dict[str, Any],
    case: Case,
) -> bool:
    actual_intent = str(
        meta.get("intent") or ""
    ).upper().strip()

    if actual_intent != case.intent:
        return False

    # У некоторых команд, например MUSIC_PLAY,
    # обязательные slots отсутствуют.
    if not case.slot:
        return True

    slots = _dict(meta.get("slots"))

    return _norm(
        case.slot,
        slots.get(case.slot),
    ) == _norm(
        case.slot,
        case.value,
    )


def _evaluate(
    case: Case,
    event: dict[str, Any] | None,
    *,
    attempt: int,
) -> dict[str, Any]:
    if event is None:
        return {
            "case": asdict(case),
            "attempt": attempt,
            "passed": False,
            "outcome": "no_event",
        }

    final_meta = _dict(event.get("final_meta"))
    candidate_meta = _dict(
        event.get("refinement_candidate_meta")
    )
    final_slots = _dict(final_meta.get("slots"))

    changed = bool(event.get("changed_by_refinement"))
    reason = str(event.get("refinement_reason") or "")

    semantic_match = _matches(final_meta, case)

    expected_reason = case.expected_refinement_reason
    policy_match = (
        expected_reason is None
        or reason == expected_reason
    )

    passed = semantic_match and policy_match

    if semantic_match and not policy_match:
        outcome = "policy_mismatch"

    elif passed:
        if changed:
            outcome = "refined_success"
        elif reason == "accepted_complete":
            outcome = "accepted_complete_success"
        else:
            outcome = "direct_success"

    elif reason == "refine_failed":
        outcome = "refine_failed"

    elif changed:
        # Refinement изменил команду, но итог не совпал с ожиданием.
        outcome = "unsafe_refinement"

    elif _matches(candidate_meta, case):
        # Whisper понял правильно, но policy отклонила кандидата.
        outcome = "candidate_correct_but_rejected"

    elif (
        str(final_meta.get("intent") or "").upper()
        != case.intent
    ):
        outcome = "intent_mismatch"

    elif case.slot and not _norm(
        case.slot,
        final_slots.get(case.slot),
    ):
        outcome = "missing_slots"

    else:
        outcome = "slot_mismatch"

    stt = _dict(event.get("stt"))

    return {
        "case": asdict(case),
        "attempt": attempt,
        "passed": passed,
        "outcome": outcome,
        "raw_text": event.get("raw_text"),
        "final_text": event.get("final_text"),
        "final_meta": final_meta,
        "candidate_text": event.get(
            "refinement_candidate_text"
        ),
        "candidate_meta": candidate_meta,
        "refinement_reason": reason,
        "changed_by_refinement": changed,
        "active_model_path": stt.get(
            "active_model_path"
        ),
        "event_ts": event.get("ts"),
    }


def _success_rate(
    passed: int,
    total: int,
) -> float:
    if total <= 0:
        return 0.0

    return round(
        passed * 100.0 / total,
        1,
    )


def _aggregate_cases(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for item in results:
        case = _dict(item.get("case"))
        code = str(case.get("code") or "unknown")
        grouped[code].append(item)

    summaries: list[dict[str, Any]] = []

    for code, attempts in grouped.items():
        passed = sum(
            bool(item.get("passed"))
            for item in attempts
        )

        outcomes = Counter(
            str(item.get("outcome") or "unknown")
            for item in attempts
        )

        models = Counter(
            str(
                item.get("active_model_path")
                or "unknown"
            )
            for item in attempts
        )

        first_case = _dict(
            attempts[0].get("case")
        )

        summaries.append(
            {
                "code": code,
                "phrase": first_case.get("phrase"),
                "intent": first_case.get("intent"),
                "attempts": len(attempts),
                "passed": passed,
                "failed": len(attempts) - passed,
                "success_rate": _success_rate(
                    passed,
                    len(attempts),
                ),
                "by_outcome": dict(
                    sorted(outcomes.items())
                ),
                "by_model": dict(
                    sorted(models.items())
                ),
            }
        )

    return summaries


def _make_report(
    results: list[dict[str, Any]],
    log_path: Path,
) -> dict[str, Any]:
    passed = sum(
        bool(item.get("passed"))
        for item in results
    )

    failed = len(results) - passed

    outcomes = Counter(
        str(item.get("outcome") or "unknown")
        for item in results
    )

    models = Counter(
        str(
            item.get("active_model_path")
            or "unknown"
        )
        for item in results
    )

    case_summaries = _aggregate_cases(results)

    cases_all_passed = sum(
        int(item["failed"] == 0)
        for item in case_summaries
    )

    return {
        "version": 2,
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "log_path": str(log_path),
        "summary": {
            "total_cases": len(case_summaries),
            "total_attempts": len(results),
            # Оставляем для совместимости с --strict.
            "passed": passed,
            "failed": failed,
            "passed_attempts": passed,
            "failed_attempts": failed,
            "overall_success_rate": _success_rate(
                passed,
                len(results),
            ),
            "cases_all_passed": cases_all_passed,
            "cases_with_failures": (
                len(case_summaries)
                - cases_all_passed
            ),
            "by_outcome": dict(
                sorted(outcomes.items())
            ),
            "by_model": dict(
                sorted(models.items())
            ),
        },
        "cases": case_summaries,
        "results": results,
    }


def _save(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = REPORT_DIR / (
        f"{datetime.now():%Y%m%d_%H%M%S}"
        "_stt_quality.json"
    )

    report["report_path"] = str(path)

    text = (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    LATEST_REPORT.write_text(
        text,
        encoding="utf-8",
    )


def _print(report: dict[str, Any]) -> None:
    summary = _dict(report.get("summary"))
    results = list(report.get("results") or [])

    case_summaries = list(
        report.get("cases")
        or _aggregate_cases(results)
    )

    total_attempts = int(
        summary.get("total_attempts")
        or len(results)
    )

    passed_attempts = int(
        summary.get(
            "passed_attempts",
            summary.get("passed", 0),
        )
        or 0
    )

    failed_attempts = int(
        summary.get(
            "failed_attempts",
            summary.get("failed", 0),
        )
        or 0
    )

    overall_rate = summary.get(
        "overall_success_rate"
    )

    if overall_rate is None:
        overall_rate = _success_rate(
            passed_attempts,
            total_attempts,
        )

    print()
    print("=== STT QUALITY BASELINE V2 ===")
    print(
        f"Attempts: {passed_attempts}/"
        f"{total_attempts} passed "
        f"({overall_rate}%)"
    )
    print(
        f"Failed attempts: {failed_attempts}"
    )

    print(
        "Outcomes:",
        json.dumps(
            summary.get("by_outcome") or {},
            ensure_ascii=False,
        ),
    )

    print(
        "Models:",
        json.dumps(
            summary.get("by_model") or {},
            ensure_ascii=False,
        ),
    )

    print()
    print("=== CASE RELIABILITY ===")

    for item in case_summaries:
        status = (
            "PASS"
            if int(item.get("failed") or 0) == 0
            else "FAIL"
        )

        print(
            f"[{status}] {item.get('code')}: "
            f"{item.get('passed')}/"
            f"{item.get('attempts')} "
            f"({item.get('success_rate')}%)"
        )

        print(
            "       outcomes="
            + json.dumps(
                item.get("by_outcome") or {},
                ensure_ascii=False,
            )
        )

    failed_results = [
        item
        for item in results
        if not item.get("passed")
    ]

    if failed_results:
        print()
        print("=== FAILED ATTEMPTS ===")

        for item in failed_results:
            case = _dict(item.get("case"))

            print(
                f"[FAIL] {case.get('code')} "
                f"attempt={item.get('attempt', 1)}: "
                f"{item.get('outcome')}"
            )

            print(
                f"       raw={item.get('raw_text')!r} "
                f"-> final={item.get('final_text')!r}"
            )

            candidate = item.get("candidate_text")
            if candidate:
                print(
                    f"       candidate={candidate!r}"
                )

    print()
    print(
        "Full report:",
        report.get("report_path"),
    )


def run(args: argparse.Namespace) -> int:
    log_path = _runtime_log(args.log_path)
    baseline = _cases()
    results: list[dict[str, Any]] = []

    print("=== STT QUALITY BASELINE V2 ===")
    print(
        "SkynetVS должен работать "
        "в другом терминале."
    )
    print(
        "Перед тестом дождись: "
        "[STT] switched to new model"
    )
    print(
        f"Runtime log: {log_path}"
    )

    attempts_per_case = max(
        1,
        int(args.attempts),
    )

    if args.case_codes:
        selected_codes = set(args.case_codes)
        baseline = [
            case
            for case in baseline
            if case.code in selected_codes
        ]

    total_runs = (
        len(baseline)
        * attempts_per_case
    )
    run_index = 0

    for case in baseline:
        for case_attempt in range(
            1,
            attempts_per_case + 1,
        ):
            run_index += 1
            event = None

            for retry_index in range(
                max(0, int(args.retries)) + 1
            ):
                print()
                print(
                    f"[{run_index}/{total_runs}] "
                    f"{case.code}, "
                    f"attempt "
                    f"{case_attempt}/"
                    f"{attempts_per_case}"
                )
                print(
                    f"Произнеси: {case.phrase}"
                )

                input(
                    "Нажми Enter непосредственно "
                    "перед произнесением..."
                )

                event = _wait_event(
                    log_path,
                    _size(log_path),
                    args.timeout,
                )

                if event is not None:
                    break

                print(
                    f"[TIMEOUT] Нет stt_diagnostic "
                    f"за {args.timeout} сек."
                )

                if retry_index < args.retries:
                    print(
                        "[INFO] Повторяем попытку "
                        "из-за таймаута."
                    )

            result = _evaluate(
                case,
                event,
                attempt=case_attempt,
            )

            results.append(result)

            print(
                f"[CAPTURED] {case.code} "
                f"attempt={case_attempt}: "
                f"{result['outcome']}"
            )

    report = _make_report(
        results,
        log_path,
    )

    _save(report)
    _print(report)

    if (
        args.strict
        and report["summary"]["failed"]
    ):
        return 1

    return 0


def show_report(
    args: argparse.Namespace,
) -> int:
    if not LATEST_REPORT.exists():
        print(
            "[FAIL] Сначала запусти "
            "STT quality session."
        )
        return 1

    report = json.loads(
        LATEST_REPORT.read_text(
            encoding="utf-8"
        )
    )

    if args.json:
        print(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _print(report)

    if (
        args.strict
        and report["summary"]["failed"]
    ):
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    run_parser = commands.add_parser("run")
    run_parser.add_argument("--log-path")
    run_parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="Количество успешных захватов каждого кейса",
    )
    run_parser.add_argument(
        "--case",
        dest="case_codes",
        action="append",
        choices=[
            case.code
            for case in _cases()
        ],
        help=(
            "Запустить только выбранный кейс. "
            "Параметр можно повторять."
        ),
    )
    run_parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
    )
    run_parser.add_argument(
        "--retries",
        type=int,
        default=1,
    )
    run_parser.add_argument(
        "--strict",
        action="store_true",
    )

    report_parser = commands.add_parser(
        "report"
    )
    report_parser.add_argument(
        "--json",
        action="store_true",
    )
    report_parser.add_argument(
        "--strict",
        action="store_true",
    )

    args = parser.parse_args()

    if args.command == "run":
        return run(args)

    return show_report(args)


if __name__ == "__main__":
    raise SystemExit(main())