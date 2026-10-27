"""Replay complete ledger totals into correction memory under the runtime lock.

The JSONL count and its event checkpoint are replaced together. The ledger and
JSONL are deliberately separate commits: a retry reads all committed totals,
so interruption between them neither loses nor repeats an acknowledged count.
Callers must serialize writers with correction_evidence_runtime's lock. This
module does not initialize a ledger, switch modes, run models, or approve data.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from modules.learning import correction_evidence_ledger as _ledger
from modules.learning.correction_memory import CorrectionMemory


KIND = "SKYNETVS_CORRECTION_EVIDENCE_PROJECTION_V1"
SOURCE = "correction_evidence_v1"
CHECKPOINT_FIELD = "event_evidence"
MAX_MEMORY_BYTES = 64 * 1024 * 1024
MAX_MEMORY_ROWS = 100_000


class _Refused(ValueError):
    def __init__(self, reason):
        self.reason = reason


def _result(reason=None, *, input_reason=None, epoch=None, stats=None,
            pair_count=None, memory_written=False):
    return {"kind": KIND,
            "status": "REFUSED" if reason else "APPLIED" if memory_written else "UNCHANGED",
            "reason": reason, "input_reason": input_reason, "epoch": epoch,
            "stats": stats, "pair_count": pair_count, "memory_written": memory_written,
            "scope": {"input": "COMPLETE_COMMITTED_LEDGER_TOTALS",
                      "legacy_counts_repaired": False, "legacy_checkpoints_preserved": True,
                      "counts_and_event_checkpoint": "ONE_JSONL_REPLACEMENT",
                      "ledger_and_memory_atomic": False, "external_writers_serialized": False,
                      "approvals_changed": False, "training_readiness": "NOT_ASSESSED"}}


def _memory_version(target):
    try:
        info = target.lstat()
    except FileNotFoundError:
        return None
    _ledger._safe_component(info, False)
    if info.st_size > MAX_MEMORY_BYTES:
        raise _Refused("RESOURCE_LIMIT")
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _checkpoint(row, epoch):
    if CHECKPOINT_FIELD not in row:
        return 0
    value = row[CHECKPOINT_FIELD]
    if (type(value) is not dict or set(value) != {"version", "epoch", "observed_count"}
            or type(value["version"]) is not int or value["version"] != 1
            or type(value["epoch"]) is not str or re.fullmatch(r"[0-9a-f]{32}", value["epoch"]) is None
            or type(value["observed_count"]) is not int or value["observed_count"] < 0):
        raise _Refused("MEMORY_INVALID")
    if value["epoch"] != epoch:
        raise _Refused("EPOCH_MISMATCH")
    if row.get("seen_count", 0) < value["observed_count"]:
        raise _Refused("MEMORY_INVALID")
    return value["observed_count"]


def project_correction_evidence(repo, *, expected_epoch):
    """Apply full totals, never a delta passed to the legacy cumulative API.

    An existing row without an event checkpoint starts at zero event evidence;
    its old seen_count and legacy cumulative checkpoints are retained. Unknown
    status/metadata fields are preserved. A lower total, missing credited key,
    or another epoch refuses the entire projection. No automatic reset exists.

    A write exception has an unknown outcome because replacement may already
    have happened. Retry reconciles the persisted per-row checkpoint. This is
    an interruption/retry contract, not a multi-file power-loss transaction or
    protection against an external writer bypassing the runtime lock.
    """
    if type(expected_epoch) is not str or re.fullmatch(r"[0-9a-f]{32}", expected_epoch) is None:
        return _result("INVALID_EPOCH")
    totals = _ledger.read_correction_evidence_totals(repo)
    if totals["status"] != "READY":
        return _result("LEDGER_REFUSED", input_reason=totals["reason"])
    if totals["epoch"] != expected_epoch:
        return _result("EPOCH_MISMATCH")
    target = Path(repo) / "data" / "learning" / "correction_memory.jsonl"
    memory = CorrectionMemory(str(target))
    writing = False
    try:
        before = _memory_version(target)
        rows = memory._read_snapshot_rows()
        if _memory_version(target) != before:
            raise _Refused("MEMORY_CHANGED")
        if len(rows) > MAX_MEMORY_ROWS:
            raise _Refused("RESOURCE_LIMIT")
        existing = {row["key"]: row for row in rows}
        candidates = {row["key"]: row for row in totals["candidates"]}
        checkpoints = {}
        for key, row in existing.items():
            previous = _checkpoint(row, expected_epoch)
            checkpoints[key] = previous
            if previous > candidates.get(key, {}).get("count", 0):
                raise _Refused("CHECKPOINT_REGRESSION")
        stats = {"processed": len(candidates), "created": 0, "increased": 0,
                 "unchanged": 0, "new_evidence": 0, "written": False}
        for key, candidate in candidates.items():
            count = candidate["count"]
            previous = checkpoints.get(key, 0)
            delta = count - previous
            if delta == 0:
                stats["unchanged"] += 1
                continue
            if delta < 0:
                raise _Refused("CHECKPOINT_REGRESSION")
            checkpoint = {"version": 1, "epoch": expected_epoch, "observed_count": count}
            now = memory._now()
            if key not in existing:
                row = {"key": key, "created_ts": now, "last_seen_ts": now,
                       "seen_count": count, "status": "candidate", "sources": [SOURCE],
                       **{name: candidate[name] for name in (
                           "failed_text", "corrected_text", "corrected_intent",
                           "corrected_confidence", "corrected_slots")},
                       CHECKPOINT_FIELD: checkpoint}
                rows.append(row)
                existing[key] = row
                stats["created"] += 1
            else:
                row = existing[key]
                row["seen_count"] = row.get("seen_count", 0) + delta
                row["last_seen_ts"] = now
                row["corrected_confidence"] = max(row.get("corrected_confidence", 0.0),
                                                  candidate["corrected_confidence"])
                slots = dict(row.get("corrected_slots") or {})
                slots.update(candidate["corrected_slots"])
                row["corrected_slots"] = slots
                sources = list(row.get("sources") or [])
                if SOURCE not in sources:
                    sources.append(SOURCE)
                row["sources"] = sources
                row[CHECKPOINT_FIELD] = checkpoint
                stats["increased"] += 1
            stats["new_evidence"] += delta
        if len(rows) > MAX_MEMORY_ROWS:
            raise _Refused("RESOURCE_LIMIT")
        if _memory_version(target) != before:
            raise _Refused("MEMORY_CHANGED")
        if stats["new_evidence"]:
            # Serialize/check the final size before asking the existing atomic
            # replacement helper to touch disk. No separate checkpoint write.
            encoded_size = sum(len((json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
                               for row in rows)
            if encoded_size > MAX_MEMORY_BYTES:
                raise _Refused("RESOURCE_LIMIT")
            writing = True
            memory._write_snapshot(rows)
            stats["written"] = True
        return _result(epoch=expected_epoch, stats=stats, pair_count=totals["pair_count"],
                       memory_written=stats["written"])
    except Exception as error:
        if writing:
            return _result("MEMORY_WRITE_OUTCOME_UNKNOWN", memory_written=None)
        if isinstance(error, (_Refused, _ledger._Refused)):
            return _result(error.reason)
        if isinstance(error, (ValueError, TypeError, UnicodeError, RecursionError, OverflowError)):
            return _result("MEMORY_INVALID")
        return _result("STORAGE_ERROR" if isinstance(error, OSError) else "INTERNAL_ERROR")
