from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
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
    slot: str
    value: str


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
    slots = _dict(meta.get("slots"))

    return (
        str(meta.get("intent") or "").upper() == case.intent
        and _norm(
            case.slot,
            slots.get(case.slot),
        )
        == _norm(
            case.slot,
            case.value,
        )
    )


def _evaluate(
    case: Case,
    event: dict[str, Any] | None,
) -> dict[str, Any]:
    if event is None:
        return {
            "case": asdict(case),
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
    passed = _matches(final_meta, case)

    if passed:
        outcome = (
            "refined_success"
            if changed
            else "direct_success"
        )

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

    elif not _norm(
        case.slot,
        final_slots.get(case.slot),
    ):
        outcome = "missing_slots"

    else:
        outcome = "slot_mismatch"

    stt = _dict(event.get("stt"))

    return {
        "case": asdict(case),
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


def _make_report(
    results: list[dict[str, Any]],
    log_path: Path,
) -> dict[str, Any]:
    passed = sum(
        bool(item["passed"])
        for item in results
    )

    outcomes = Counter(
        item["outcome"]
        for item in results
    )

    models = Counter(
        str(
            item.get("active_model_path")
            or "unknown"
        )
        for item in results
    )

    return {
        "version": 1,
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "log_path": str(log_path),
        "summary": {
            "total_cases": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "by_outcome": dict(
                sorted(outcomes.items())
            ),
            "by_model": dict(
                sorted(models.items())
            ),
        },
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
    summary = report["summary"]

    print()
    print("=== STT QUALITY BASELINE V1 ===")
    print(
        f"Passed: "
        f"{summary['passed']}/"
        f"{summary['total_cases']}"
    )

    print(
        "Outcomes:",
        json.dumps(
            summary["by_outcome"],
            ensure_ascii=False,
        ),
    )

    print(
        "Models:",
        json.dumps(
            summary["by_model"],
            ensure_ascii=False,
        ),
    )

    print()

    for item in report["results"]:
        case = item["case"]
        status = (
            "PASS"
            if item["passed"]
            else "FAIL"
        )

        model = Path(
            str(
                item.get("active_model_path")
                or "unknown"
            )
        ).name

        print(
            f"[{status}] {case['code']}: "
            f"{item['outcome']} | "
            f"model={model}"
        )

        print(
            f"       raw={item.get('raw_text')!r} "
            f"-> final={item.get('final_text')!r}"
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

    print("=== STT QUALITY BASELINE V1 ===")
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

    for index, case in enumerate(
        baseline,
        start=1,
    ):
        event = None

        for attempt in range(
            args.retries + 1
        ):
            print()
            print(
                f"[{index}/{len(baseline)}] "
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

            if attempt < args.retries:
                print(
                    "[INFO] Повторяем кейс."
                )

        result = _evaluate(
            case,
            event,
        )

        results.append(result)

        print(
            f"[CAPTURED] {case.code}: "
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