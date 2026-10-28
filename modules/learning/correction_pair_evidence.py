"""Pure, conservative candidate planning for identified observation pairs.

This callable does no I/O. The opt-in event ledger/runtime supplies its input;
the legacy cumulative analyzer keeps its separate compatibility path.
The caller must preserve original positions, including malformed-row barriers,
and assert snapshot completeness. That assertion is not independently verified.
Returned pairs contain private IDs/text/slots and are not a public audit report.
"""
from __future__ import annotations

from datetime import datetime
import json
import math


KIND = "SKYNETVS_CORRECTION_PAIR_EVIDENCE_PLAN_V1"
RULE_VERSION = "adjacent_unique_observation_v1"
MAX_ROWS = 100_000
MAX_JSON_DEPTH = 64
MAX_JSON_NODES_PER_ROW = 100_000
MAX_CANONICAL_ROW_BYTES = 1024 * 1024
MAX_CANONICAL_TOTAL_BYTES = 64 * 1024 * 1024
MAX_INTEGER_BITS = 16_384
MAX_TOTAL_VISITED_NODES = 8_000_000
MAX_TOTAL_SCALAR_UNITS = 64 * 1024 * 1024
_REPEAT_PHRASES = frozenset(("повтори", "еще", "ещё"))


class _InvalidValue(ValueError):
    pass


class _LimitReached(ValueError):
    pass


def _result(reason, pairs=None, observations=None):
    return {
        "kind": KIND,
        "rule_version": RULE_VERSION,
        "status": "REFUSED" if reason is not None else "READY",
        "reason": reason,
        "scope": {
            "input": "PROVIDED_ORDERED_SNAPSHOT",
            "snapshot_completeness": "CALLER_ASSERTED_NOT_VERIFIED",
            "output": "PRIVATE_DERIVED_HEURISTIC_EVIDENCE",
            "counting_applied": False,
            "persistent_replay_protection": False,
            "independent_observations_verified": False,
            "training_readiness": "NOT_ASSESSED",
        },
        "pairs": [] if pairs is None else pairs,
        "observations": observations,
    }


def _top_fields(row, budget):
    """Inspect exact dict entries without invoking arbitrary key callbacks."""
    present, event_id, timestamp = False, None, None
    if type(row) is dict:
        if len(row) > MAX_JSON_NODES_PER_ROW:
            raise _LimitReached()
        for key, value in row.items():
            budget["nodes"] += 1
            if budget["nodes"] > MAX_TOTAL_VISITED_NODES:
                raise _LimitReached()
            if type(key) is str:
                if key == "event_id":
                    present, event_id = True, value
                elif key == "ts":
                    timestamp = value
    if type(event_id) is str and len(event_id) > MAX_CANONICAL_ROW_BYTES:
        raise _LimitReached()
    if type(timestamp) is str and len(timestamp) > MAX_CANONICAL_ROW_BYTES:
        raise _LimitReached()
    # These fields can still be inspected when another invalid value prevents
    # payload serialization, so bill their work independently of that outcome.
    budget["units"] += sum(len(value) + 2 for value in (event_id, timestamp)
                           if type(value) is str)
    if budget["units"] > MAX_TOTAL_SCALAR_UNITS:
        raise _LimitReached()
    valid_id = type(event_id) is str and bool(event_id.strip())
    return present, event_id if valid_id else None, timestamp


def _canonical_payload(row, budget):
    """Bound exact JSON values before serialization; preserve V2 comparison."""
    active = set()
    nodes = 0
    units = 0
    portable = True

    def charge_units(amount):
        nonlocal units
        units += amount
        budget["units"] += amount
        if units > MAX_CANONICAL_ROW_BYTES or budget["units"] > MAX_TOTAL_SCALAR_UNITS:
            raise _LimitReached()

    def visit(value, depth):
        nonlocal nodes, portable
        nodes += 1
        budget["nodes"] += 1
        if (nodes > MAX_JSON_NODES_PER_ROW or depth > MAX_JSON_DEPTH
                or budget["nodes"] > MAX_TOTAL_VISITED_NODES):
            raise _LimitReached()
        value_type = type(value)
        if value_type is str:
            charge_units(len(value) + 2)
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                portable = False
        elif value_type is int:
            if value.bit_length() > MAX_INTEGER_BITS:
                raise _LimitReached()
            charge_units(value.bit_length() * 30103 // 100000 + 2)
        elif value_type is float:
            if not math.isfinite(value):
                raise _InvalidValue()
            charge_units(24)
        elif value is None or value_type is bool:
            charge_units(5)
        elif value_type in (list, dict):
            if len(value) > MAX_JSON_NODES_PER_ROW or id(value) in active:
                if id(value) in active:
                    raise _InvalidValue()
                raise _LimitReached()
            active.add(id(value))
            charge_units(2 + len(value))
            try:
                if value_type is dict:
                    for key, child in value.items():
                        if type(key) is not str:
                            raise _InvalidValue()
                        visit(key, depth + 1)
                        visit(child, depth + 1)
                else:
                    for child in value:
                        visit(child, depth + 1)
            finally:
                active.remove(id(value))
        else:
            raise _InvalidValue()

    try:
        visit(row, 0)
        payload = json.dumps(row, sort_keys=True, ensure_ascii=True,
                             allow_nan=False, separators=(",", ":")).encode("ascii")
    except _LimitReached:
        raise
    except (_InvalidValue, ValueError, TypeError, OverflowError, RecursionError):
        return None, False
    if len(payload) > MAX_CANONICAL_ROW_BYTES:
        raise _LimitReached()
    return payload, portable


def _timestamp(value):
    if type(value) is not str or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except (ValueError, OverflowError):
        return None


def _row_info(row, timestamp):
    if type(row) is not dict or timestamp is None:
        return None
    if any(type(row.get(key)) is not str for key in ("raw_text", "final_text")):
        return None
    if type(row.get("accepted")) is not bool:
        return None
    if any(key in row and type(row[key]) is not str for key in ("mode", "immediate_label")):
        return None
    missing = row.get("missing_slots", [])
    if type(missing) is not list or any(type(value) is not str for value in missing):
        return None
    meta = row.get("meta")
    if type(meta) is not dict or type(meta.get("slots")) is not dict:
        return None
    intent = meta.get("intent")
    if intent is not None and type(intent) is not str:
        return None
    if row["accepted"] and (type(intent) is not str or not intent.strip()):
        return None
    confidence = meta.get("confidence")
    if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
        return None
    if any(key in meta and type(meta[key]) is not str for key in ("say", "_text")):
        return None
    text = (row["raw_text"] or row["final_text"]).strip()
    if not text:
        return None
    return {"timestamp": timestamp, "accepted": row["accepted"], "text": text,
            "intent": (intent or "").upper(), "confidence": float(confidence),
            "slots": meta["slots"], "missing_slots": missing}


def plan_correction_pair_evidence(rows, *, snapshot_complete: bool):
    """Plan unique adjacent endpoints without changing history or learned counts.

    All occurrences of any repeated ID are barriers, including identical copies.
    Invalid/legacy rows keep their positions; they are never removed or sorted.
    Limits or mixed timestamp modes refuse the whole plan, with no partial pairs.
    Input must not be mutated concurrently. Nested output slots are independent.
    """
    if type(snapshot_complete) is not bool:
        return _result("INVALID_COMPLETENESS_FLAG")
    if not snapshot_complete:
        return _result("INCOMPLETE_SNAPSHOT")
    if type(rows) not in (list, tuple):
        return _result("INVALID_INPUT_CONTAINER")
    if len(rows) > MAX_ROWS:
        return _result("RESOURCE_LIMIT")

    groups = {}
    entries = []
    timestamp_modes = set()
    canonical_total = 0
    work_budget = {"nodes": 0, "units": 0}
    observations = {"input_rows": len(rows), "rows_with_event_id": 0,
                    "rows_without_event_id": 0, "legacy_rows": 0, "invalid_rows": 0,
                    "uncomparable_rows": 0, "repeated_event_id_groups": 0,
                    "repeated_event_id_rows": 0, "conflicting_event_id_groups": 0,
                    "barrier_rows": 0, "candidate_pairs": 0}
    try:
        for row in rows:
            present, event_id, time_value = _top_fields(row, work_budget)
            # Register IDs before schema/value eligibility: a bad later copy
            # must also quarantine an otherwise usable earlier occurrence.
            group = None
            if event_id is not None:
                observations["rows_with_event_id"] += 1
                group = groups.setdefault(event_id, {"count": 0, "payload": None, "conflict": False})
                group["count"] += 1
            else:
                observations["rows_without_event_id"] += 1
            if type(row) is dict and not present:
                observations["legacy_rows"] += 1

            payload, portable = _canonical_payload(row, work_budget)
            if payload is None:
                observations["uncomparable_rows"] += 1
            else:
                canonical_total += len(payload)
                if canonical_total > MAX_CANONICAL_TOTAL_BYTES:
                    raise _LimitReached()
                if group is not None:
                    if group["payload"] is None:
                        group["payload"] = payload
                    elif payload != group["payload"]:
                        group["conflict"] = True
            timestamp = _timestamp(time_value)
            if timestamp is not None:
                timestamp_modes.add(timestamp.utcoffset() is not None)
            info = _row_info(row, timestamp) if payload is not None and portable else None
            if info is None or (present and event_id is None):
                observations["invalid_rows"] += 1
            entries.append((event_id, info))
    except _LimitReached:
        return _result("RESOURCE_LIMIT")

    if len(timestamp_modes) > 1:
        return _result("MIXED_TIMESTAMP_MODES")
    for group in groups.values():
        if group["count"] > 1:
            observations["repeated_event_id_groups"] += 1
            observations["repeated_event_id_rows"] += group["count"]
        observations["conflicting_event_id_groups"] += int(group["conflict"])
    usable = [event_id is not None and info is not None and groups[event_id]["count"] == 1
              for event_id, info in entries]
    observations["barrier_rows"] = len(rows) - sum(usable)

    pairs = []
    consumed_corrected_ids = set()
    for index in range(len(entries) - 1):
        if not usable[index] or not usable[index + 1]:
            continue
        failed_id, failed = entries[index]
        corrected_id, corrected = entries[index + 1]
        if failed["accepted"] or not corrected["accepted"]:
            continue
        if corrected["confidence"] < 0.40 or corrected["missing_slots"]:
            continue
        delta = (corrected["timestamp"] - failed["timestamp"]).total_seconds()
        if not 0 <= delta <= 60:
            continue
        failed_text, corrected_text = failed["text"], corrected["text"]
        if failed_text == corrected_text:
            continue
        if any(" ".join(text.lower().split()) in _REPEAT_PHRASES
               for text in (failed_text, corrected_text)):
            continue
        if corrected_id in consumed_corrected_ids:
            continue
        consumed_corrected_ids.add(corrected_id)
        pairs.append({
            "pair_identity": {"rule_version": RULE_VERSION, "failed_event_id": failed_id,
                              "corrected_event_id": corrected_id},
            "failed_index": index, "corrected_index": index + 1,
            "failed_text": failed_text, "corrected_text": corrected_text,
            "corrected_intent": corrected["intent"],
            "corrected_confidence": corrected["confidence"],
            "corrected_slots": json.loads(json.dumps(corrected["slots"], ensure_ascii=True, allow_nan=False)),
            "delta_sec": round(delta, 2),
        })
    observations["candidate_pairs"] = len(pairs)
    return _result(None, pairs, observations)
