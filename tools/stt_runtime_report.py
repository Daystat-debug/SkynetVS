from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from modules.command_decision import DEFAULT_REQUIRED_SLOTS


DEFAULT_LOG_PATH = PROJECT_ROOT / "data" / "logs" / "runtime.jsonl"


Row = Dict[str, Any]


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


ACCEPT_CONF = _env_float(
    "NLU_ACCEPT_CONF",
    os.getenv("NLU_MIN_CONF", "0.35"),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_jsonl(path: Path, *, tail: int) -> List[Row]:
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    if tail > 0:
        lines = lines[-tail:]

    rows: List[Row] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except Exception:
            continue

        if isinstance(obj, dict):
            rows.append(obj)

    return rows


def _stt_diagnostic_rows(rows: Iterable[Row]) -> List[Row]:
    return [
        row
        for row in rows
        if row.get("kind") == "stt_diagnostic"
    ]


def _slots(row: Row) -> Dict[str, Any]:
    meta = row.get("final_meta") or {}
    if not isinstance(meta, dict):
        return {}

    slots = meta.get("slots") or {}
    if not isinstance(slots, dict):
        return {}

    return slots


def _intent(row: Row) -> str:
    meta = row.get("final_meta") or {}
    if not isinstance(meta, dict):
        return ""

    return str(meta.get("intent") or "").upper().strip()


def _confidence(row: Row) -> float:
    meta = row.get("final_meta") or {}
    if not isinstance(meta, dict):
        return 0.0

    return _safe_float(meta.get("confidence"))


def _missing_required_slots(row: Row) -> List[str]:
    intent = _intent(row)
    slots = _slots(row)
    required = DEFAULT_REQUIRED_SLOTS.get(intent, ())

    missing: List[str] = []

    for slot_name in required:
        value = slots.get(slot_name)

        if value is None:
            missing.append(slot_name)
            continue

        if isinstance(value, str) and not value.strip():
            missing.append(slot_name)
            continue

    return missing


def _stt(row: Row) -> Dict[str, Any]:
    data = row.get("stt") or {}
    if not isinstance(data, dict):
        return {}
    return data


def _model_path(row: Row) -> str:
    return str(_stt(row).get("active_model_path") or "")


def _duration(row: Row) -> float:
    return _safe_float(_stt(row).get("last_utterance_duration_sec"))


def _refinement_reason(row: Row) -> str:
    return str(row.get("refinement_reason") or "")


def _issues(row: Row) -> List[str]:
    issues: List[str] = []

    intent = _intent(row)
    conf = _confidence(row)
    missing_slots = _missing_required_slots(row)
    reason = _refinement_reason(row)
    model_path = _model_path(row)
    duration = _duration(row)

    if intent and conf >= ACCEPT_CONF and missing_slots:
        issues.append("accepted_intent_missing_required_slots")

    if intent == "OPEN_URL" and not _slots(row).get("url"):
        issues.append("open_url_without_url")

    if missing_slots and reason == "whisper_disabled":
        issues.append("missing_slots_but_whisper_disabled")

    if "model_small" in model_path.replace("\\", "/"):
        issues.append("small_model_used")

    if duration > 6.0:
        issues.append("long_utterance_audio")

    if duration > 0 and duration < 0.6:
        issues.append("very_short_utterance_audio")

    return issues


def _compact_row(row: Row) -> Row:
    stt = _stt(row)
    slots = _slots(row)

    return {
        "ts": row.get("ts"),
        "raw_text": row.get("raw_text"),
        "final_text": row.get("final_text"),
        "intent": _intent(row) or None,
        "confidence": round(_confidence(row), 4),
        "slots": slots,
        "missing_required_slots": _missing_required_slots(row),
        "refinement_reason": _refinement_reason(row),
        "changed_by_refinement": bool(row.get("changed_by_refinement")),
        "active_model_path": stt.get("active_model_path"),
        "audio_duration_sec": stt.get("last_utterance_duration_sec"),
        "audio_bytes": stt.get("last_utterance_audio_bytes"),
        "issues": _issues(row),
    }


def _count_by(rows: Iterable[Row], fn) -> Dict[str, int]:
    counter: Counter[str] = Counter()

    for row in rows:
        value = fn(row)
        if isinstance(value, list):
            for item in value:
                counter[str(item or "unknown")] += 1
        else:
            counter[str(value or "unknown")] += 1

    return dict(sorted(counter.items(), key=lambda pair: pair[0]))


def build_report(
    *,
    log_path: Path,
    tail: int,
    limit: int,
    only_problems: bool,
) -> Dict[str, Any]:
    rows = _read_jsonl(log_path, tail=tail)
    stt_rows = _stt_diagnostic_rows(rows)

    compact = [_compact_row(row) for row in stt_rows]

    problem_rows = [
        row
        for row in compact
        if row.get("issues")
    ]

    shown_rows = problem_rows if only_problems else compact

    if limit > 0:
        shown_rows = shown_rows[-limit:]

    return {
        "log_path": str(log_path),
        "tail": tail,
        "total_jsonl_rows_read": len(rows),
        "stt_diagnostic_count": len(stt_rows),
        "problem_count": len(problem_rows),
        "accept_conf": ACCEPT_CONF,
        "by_model": _count_by(stt_rows, _model_path),
        "by_refinement_reason": _count_by(stt_rows, _refinement_reason),
        "by_issue": _count_by(stt_rows, _issues),
        "events": shown_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--tail", type=int, default=2000)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--only-problems", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    report = build_report(
        log_path=Path(args.log_path),
        tail=int(args.tail),
        limit=int(args.limit),
        only_problems=bool(args.only_problems),
    )

    print("=== STT RUNTIME REPORT ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Аналитический отчёт. Не валит pipeline.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())