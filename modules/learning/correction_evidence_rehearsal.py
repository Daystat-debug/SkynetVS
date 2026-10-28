"""Freeze actual inputs and rehearse event builds only in a private work copy.

The retained before-image is never opened by SQLite or used as the builder's
work directory. The live learning lock covers capture and its final byte check;
it is released before rehearsal. This is not a claim that unrelated processes
cannot later edit the live project. No activation, reset or automatic restore
is performed. Private copies, including partial attempts, are retained.
"""
from __future__ import annotations

from copy import deepcopy

from modules.learning import correction_evidence_activation as _capture
from modules.learning import correction_evidence_runtime as _runtime
from modules.learning import correction_evidence_ledger as _ledger
from modules.learning import correction_evidence_projection as _projection
from modules.learning import correction_pair_evidence as _planner
from modules.learning.learning_history_snapshot import read_learning_history_snapshot


KIND = "SKYNETVS_CORRECTION_EVIDENCE_REHEARSAL_V1"
REASONS = frozenset((
    "INVALID_PATH", "BACKUP_IN_PROJECT", "BACKUP_EXISTS", "DIRECTORY_MISSING",
    "UNSAFE_PATH", "BUSY", "LOCK_INVALID", "LOCK_CHANGED", "STORAGE_ERROR",
    "RESOURCE_LIMIT", "INPUT_CHANGED", "BACKUP_FAILED", "WORK_COPY_FAILED",
    "ACTIVE_REQUIRED", "CONTROL_INVALID", "CONTROL_CHANGED", "ORPHAN_LEDGER",
    "HISTORY_REFUSED", "HISTORY_INVALID", "HISTORY_DUPLICATE_IDS", "MEMORY_INVALID",
    "MISSING_CONTROL_STATE", "LEDGER_INVALID", "EPOCH_MISMATCH", "MEMORY_LEDGER_MISMATCH",
    "FIRST_BUILD_REFUSED", "SECOND_BUILD_REFUSED", "BUILD_RESULT_INVALID",
    "FIRST_BUILD_OUTCOME_UNKNOWN", "SECOND_BUILD_OUTCOME_UNKNOWN",
    "PROJECTION_MISMATCH", "LEGACY_METADATA_CHANGED", "SECOND_BUILD_NOT_REPLAY",
    "WORK_HISTORY_CHANGED", "WORK_CONTROL_CHANGED", "BACKUP_CHANGED",
    "REPLAY_MEMORY_CHANGED", "REPLAY_LEDGER_CHANGED", "REPLAY_TOTALS_CHANGED",
    "POSTCHECK_FAILED", "RECEIPT_WRITE_FAILED", "INTERNAL_ERROR",
))
SCOPE = {
    "input": "FROZEN_PRIVATE_SEVEN_FILE_CAPTURE",
    "source_preservation": "VERIFIED_AT_CAPTURE_BEFORE_UNLOCK_ONLY",
    "runtime_lock": "COOPERATING_WRITERS_CAPTURE_ONLY",
    "old_process_gate": "CALLER_REQUIRED",
    "lock_file": "PERSISTENT_ONE_BYTE_NOT_BACKED_UP",
    "retained_before": "NEVER_OPENED_BY_SQLITE_OR_BUILDER",
    "sqlite_and_builder_target": "SEPARATE_PRIVATE_WORKING_COPY_ONLY",
    "sqlite_read_may_recover_working_journal": True,
    "live_sqlite_opened": False,
    "live_history_written": False,
    "live_memory_written": False,
    "live_ledger_sync_run": False,
    "live_projection_run": False,
    "activation_run": False,
    "synthetic_live_rows_added": False,
    "training_run": False,
    "promotion_run": False,
    "automatic_restore": False,
    "atomic_filesystem_snapshot": False,
    "training_readiness": "NOT_ASSESSED",
}


class _Refused(ValueError):
    def __init__(self, reason):
        self.reason = reason


def _result():
    return {
        "kind": KIND, "status": "REFUSED", "reason": "INTERNAL_ERROR",
        "stage": "PREFLIGHT", "coverage": "NOT_ASSESSED", "captured_state": "UNKNOWN",
        "backup_status": "NOT_CREATED", "working_copy_status": "NOT_CREATED",
        "first_build_status": "NOT_RUN", "second_build_status": "NOT_RUN",
        "history_rows": None, "current_epoch_rows": None,
        "memory_rows_before": None, "memory_rows_after": None,
        "pairs_before": None, "pairs_after_first": None, "pairs_after_second": None,
        "new_pairs_first": None, "new_evidence_first": None, "new_evidence_second": None,
        "source_preserved_at_capture": None, "backup_preserved": None,
        "working_history_preserved": None, "working_control_preserved": None,
        "legacy_metadata_preserved": None, "replay_memory_preserved": None,
        "replay_ledger_preserved": None, "replay_totals_preserved": None,
        "scope": dict(SCOPE),
    }


def validate_public_result(value):
    """Closed public schema: fixed vocabulary, bounded counts and known flags."""
    if type(value) is not dict or set(value) != set(_result()):
        return False
    if type(value["kind"]) is not str or value["kind"] != KIND:
        return False
    enumerations = {
        "status": ("VERIFIED", "REFUSED"),
        "stage": ("PREFLIGHT", "LOCK", "BACKUP", "COPY", "ADMISSIBILITY",
                  "FIRST_BUILD", "FIRST_VERIFY", "SECOND_BUILD", "SECOND_VERIFY", "POSTCHECK", "COMPLETE"),
        "coverage": ("NEW_PAIRS", "PENDING_PROJECTION_ONLY", "NO_NEW_PAIRS", "NOT_ASSESSED"),
        "captured_state": ("UNKNOWN", "LEGACY", "PREPARING", "ACTIVE"),
        "backup_status": ("NOT_CREATED", "INCOMPLETE", "VERIFIED"),
        "working_copy_status": ("NOT_CREATED", "INCOMPLETE", "VERIFIED"),
        "first_build_status": ("NOT_RUN", "ATTEMPTED", "APPLIED", "UNCHANGED", "REFUSED", "UNKNOWN"),
        "second_build_status": ("NOT_RUN", "ATTEMPTED", "APPLIED", "UNCHANGED", "REFUSED", "UNKNOWN"),
    }
    for name, allowed in enumerations.items():
        if type(value[name]) is not str or value[name] not in allowed:
            return False
    count_names = ("history_rows", "current_epoch_rows", "memory_rows_before", "memory_rows_after",
                   "pairs_before", "pairs_after_first", "pairs_after_second", "new_pairs_first",
                   "new_evidence_first", "new_evidence_second")
    flag_names = ("source_preserved_at_capture", "backup_preserved", "working_history_preserved",
                  "working_control_preserved", "legacy_metadata_preserved", "replay_memory_preserved",
                  "replay_ledger_preserved", "replay_totals_preserved")
    for name in count_names:
        if value[name] is not None and (type(value[name]) is not int or not 0 <= value[name] <= 1_000_000):
            return False
    for name in flag_names:
        if value[name] is not None and type(value[name]) is not bool:
            return False
    if value["reason"] is not None and (type(value["reason"]) is not str or value["reason"] not in REASONS):
        return False
    if (type(value["scope"]) is not dict or set(value["scope"]) != set(SCOPE)
            or any(type(value["scope"][key]) is not type(expected) or value["scope"][key] != expected
                   for key, expected in SCOPE.items())):
        return False
    if value["status"] == "REFUSED":
        return (value["reason"] in REASONS and value["stage"] != "COMPLETE"
                and value["coverage"] == "NOT_ASSESSED")
    if (value["reason"] is not None or value["stage"] != "COMPLETE"
            or value["captured_state"] != "ACTIVE" or value["backup_status"] != "VERIFIED"
            or value["working_copy_status"] != "VERIFIED"
            or value["first_build_status"] not in ("APPLIED", "UNCHANGED")
            or value["second_build_status"] != "UNCHANGED"
            or any(value[name] is None for name in count_names)
            or any(value[name] is not True for name in flag_names)
            or value["current_epoch_rows"] > value["history_rows"]
            or value["pairs_before"] > value["pairs_after_first"]
            or value["pairs_after_first"] != value["pairs_after_second"]
            or value["new_pairs_first"] != value["pairs_after_first"] - value["pairs_before"]
            or value["new_evidence_second"] != 0
            or value["new_evidence_first"] < value["new_pairs_first"]
            or value["new_evidence_first"] > value["pairs_after_first"]
            or 2 * value["new_pairs_first"] > value["current_epoch_rows"]
            or value["memory_rows_after"] < value["memory_rows_before"]
            or (value["first_build_status"] == "APPLIED") != (value["new_evidence_first"] > 0)):
        return False
    expected = ("NEW_PAIRS" if value["new_pairs_first"] else
                "PENDING_PROJECTION_ONLY" if value["new_evidence_first"] else "NO_NEW_PAIRS")
    return value["coverage"] == expected


def _reason(error):
    if isinstance(error, _planner._LimitReached):
        return "RESOURCE_LIMIT"
    if isinstance(error, (_Refused, _capture._Refused, _runtime.RuntimeRefused)):
        return error.reason if error.reason in REASONS else "INTERNAL_ERROR"
    return "STORAGE_ERROR" if isinstance(error, OSError) else "INTERNAL_ERROR"


def _versions(base):
    inventory = _capture._inventory(base)
    return {name: (None if info is None else _capture._signature(info),
                   _capture._fingerprint(base / name, _capture.FILES[name], info))
            for name, info in inventory.items()}


def _working_copy(backup_repo, working_repo, fingerprints):
    source = backup_repo / "data" / "learning"
    target = working_repo / "data" / "learning"
    target.mkdir(parents=True)
    for name, maximum in _capture.FILES.items():
        copied = _capture._fingerprint(source / name, maximum,
                                       target=target / name if fingerprints[name] is not None else None)
        if copied != fingerprints[name] or _capture._fingerprint(target / name, maximum) != fingerprints[name]:
            raise _Refused("WORK_COPY_FAILED")
    return target


def _history_counts(repo, epoch):
    snapshot = read_learning_history_snapshot(repo)
    if snapshot["status"] != "COMPLETE":
        raise _Refused("HISTORY_REFUSED")
    plan = _planner.plan_correction_pair_evidence(snapshot["rows"], snapshot_complete=True)
    if plan["status"] != "READY":
        raise _Refused("HISTORY_REFUSED")
    observed = plan["observations"]
    if observed["invalid_rows"] or observed["uncomparable_rows"]:
        raise _Refused("HISTORY_INVALID")
    if observed["repeated_event_id_groups"]:
        raise _Refused("HISTORY_DUPLICATE_IDS")
    return len(snapshot["rows"]), sum(row.get("evidence_epoch") == epoch for row in snapshot["rows"])


def _totals(repo, control, rows):
    totals = _ledger.read_correction_evidence_totals(repo)
    if totals["status"] != "READY":
        raise _Refused("LEDGER_INVALID")
    if totals["epoch"] != control["epoch"]:
        raise _Refused("EPOCH_MISMATCH")
    candidates = {row["key"]: row["count"] for row in totals["candidates"]}
    for row in rows:
        try:
            checkpoint = _projection._checkpoint(row, control["epoch"])
        except _projection._Refused as error:
            raise _Refused("EPOCH_MISMATCH" if error.reason == "EPOCH_MISMATCH" else "MEMORY_INVALID") from None
        if checkpoint > candidates.get(row["key"], 0):
            raise _Refused("MEMORY_LEDGER_MISMATCH")
    return totals


def _build(working_repo, destination, result, prefix, control):
    current = _runtime.read_learning_evidence_control(working_repo / "data" / "learning")
    if current["state"] != "ACTIVE":
        raise _Refused("ACTIVE_REQUIRED")
    if current != control:
        raise _Refused("EPOCH_MISMATCH")
    _capture._write_record(destination / (prefix + "_build_intent.json"), {
        "kind": "SKYNETVS_CORRECTION_REHEARSAL_PRIVATE_INTENT_V1", "pass": prefix,
        "target": "SEPARATE_PRIVATE_WORKING_COPY", "live_operation": False,
    })
    result[prefix + "_build_status"] = "ATTEMPTED"
    try:
        outcome = _runtime.build_learning_corrections(working_repo)
    except Exception:
        result[prefix + "_build_status"] = "UNKNOWN"
        raise _Refused(prefix.upper() + "_BUILD_OUTCOME_UNKNOWN") from None
    # Never publish the returned private payload; preserve it only locally.
    if (type(outcome) is not dict or outcome.get("kind") != _runtime.KIND
            or outcome.get("operation") != "BUILD"
            or outcome.get("status") not in ("APPLIED", "UNCHANGED", "REFUSED")):
        result[prefix + "_build_status"] = "UNKNOWN"
        raise _Refused("BUILD_RESULT_INVALID")
    result[prefix + "_build_status"] = outcome["status"]
    _capture._write_record(destination / (prefix + "_build_outcome.json"), outcome)
    if outcome["status"] == "REFUSED":
        raise _Refused(prefix.upper() + "_BUILD_REFUSED")
    stats = outcome.get("stats")
    if (outcome.get("mode") != "EVENT" or type(stats) is not dict
            or set(stats) != {"processed", "created", "increased", "unchanged", "new_evidence", "written"}
            or any(type(stats[name]) is not int or not 0 <= stats[name] <= 1_000_000
                   for name in ("processed", "created", "increased", "unchanged", "new_evidence"))
            or type(stats["written"]) is not bool
            or stats["written"] != (stats["new_evidence"] > 0)
            or (outcome["status"] == "APPLIED") != stats["written"]):
        raise _Refused("BUILD_RESULT_INVALID")
    result["new_evidence_" + prefix] = stats["new_evidence"]
    return stats


def _same_json(left, right):
    # Ordinary Python equality equates bool/int, int/float and signed zero.
    # The established portable JSON canonical form retains these differences.
    values = []
    for item in (left, right):
        raw, portable = _planner._canonical_payload(item, {"nodes": 0, "units": 0})
        if raw is None or not portable:
            raise _Refused("MEMORY_INVALID")
        values.append(raw)
    return values[0] == values[1]


def _same_totals(left, right):
    return (_same_json({key: value for key, value in left.items() if key != "candidates"},
                       {key: value for key, value in right.items() if key != "candidates"})
            and len(left["candidates"]) == len(right["candidates"])
            and all(_same_json(a, b) for a, b in zip(left["candidates"], right["candidates"])))


def _verify_projection(before_rows, after_rows, totals, epoch, stats):
    old = {row["key"]: row for row in before_rows}
    current = {row["key"]: row for row in after_rows}
    candidates = {row["key"]: row for row in totals["candidates"]}
    if list(current)[:len(old)] != list(old) or set(current) != set(old) | set(candidates):
        raise _Refused("PROJECTION_MISMATCH")
    credited = 0
    changed = 0
    for key, row in current.items():
        original = old.get(key)
        previous = _projection._checkpoint(original, epoch) if original is not None else 0
        count = candidates.get(key, {}).get("count", 0)
        delta = count - previous
        if delta < 0 or row.get("seen_count", 0) != (original.get("seen_count", 0) if original else 0) + delta:
            raise _Refused("PROJECTION_MISMATCH")
        if delta == 0:
            if not _same_json(row, original):
                raise _Refused("LEGACY_METADATA_CHANGED")
            continue
        credited += delta
        changed += 1
        checkpoint = {"version": 1, "epoch": epoch, "observed_count": count}
        if row.get("event_evidence") != checkpoint:
            raise _Refused("PROJECTION_MISMATCH")
        if original is not None:
            mutable = {"seen_count", "event_evidence", "last_seen_ts", "corrected_confidence", "corrected_slots", "sources"}
            if not _same_json({name: value for name, value in row.items() if name not in mutable},
                              {name: value for name, value in original.items() if name not in mutable}):
                raise _Refused("LEGACY_METADATA_CHANGED")
            expected = deepcopy(original)
            expected["seen_count"] = original.get("seen_count", 0) + delta
            expected["event_evidence"] = checkpoint
            expected["last_seen_ts"] = row.get("last_seen_ts")
            expected["corrected_confidence"] = max(original.get("corrected_confidence", 0.0),
                                                    candidates[key]["corrected_confidence"])
            expected["corrected_slots"] = dict(original.get("corrected_slots") or {})
            expected["corrected_slots"].update(candidates[key]["corrected_slots"])
            expected["sources"] = list(original.get("sources") or [])
            if _projection.SOURCE not in expected["sources"]:
                expected["sources"].append(_projection.SOURCE)
        else:
            expected = {"key": key, "created_ts": row.get("last_seen_ts"), "last_seen_ts": row.get("last_seen_ts"),
                        "seen_count": count, "status": "candidate", "sources": [_projection.SOURCE],
                        **{name: candidates[key][name] for name in (
                            "failed_text", "corrected_text", "corrected_intent",
                            "corrected_confidence", "corrected_slots")},
                        "event_evidence": checkpoint}
        if type(row.get("last_seen_ts")) is not str or not row["last_seen_ts"] or not _same_json(row, expected):
            raise _Refused("PROJECTION_MISMATCH")
    if (credited != stats["new_evidence"] or stats["processed"] != len(candidates)
            or stats["created"] != len(set(current) - set(old))
            or stats["increased"] != changed - stats["created"]
            or stats["unchanged"] != len(candidates) - changed):
        raise _Refused("PROJECTION_MISMATCH")


def _verify_work_input(base, captured, result):
    current = _versions(base)
    for name, field, reason in (
            ("command_history.jsonl", "working_history_preserved", "WORK_HISTORY_CHANGED"),
            (_runtime.CONTROL_NAME, "working_control_preserved", "WORK_CONTROL_CHANGED")):
        result[field] = current[name] == captured[name]
        if not result[field]:
            raise _Refused(reason)
    return current


def rehearse_correction_evidence(repo, run_directory):
    """Retain a raw capture, then verify two builds in a separate private copy.

    A fresh absolute run_directory with an existing safe parent is required.
    The caller stops old Python processes. Neither live SQLite nor the raw
    backup is opened by SQLite. Refusals retain every created file; no outcome
    implies a rollback of a partially changed working copy.
    """
    result = _result()
    destination = None
    created = False
    try:
        root = _capture._absolute(repo)
        destination = _capture._absolute(run_directory)
        if destination == root or root in destination.parents or destination in root.parents:
            raise _Refused("BACKUP_IN_PROJECT")
        _runtime._directory(root)
        base = _runtime._directory(root / "data" / "learning")
        _runtime._directory(destination.parent)
        try:
            destination.lstat()
        except FileNotFoundError:
            pass
        else:
            raise _Refused("BACKUP_EXISTS")
        result["stage"] = "LOCK"
        with _runtime.learning_evidence_lock(base):
            result["stage"] = "BACKUP"
            destination.mkdir(mode=0o700)
            created = True
            result["backup_status"] = "INCOMPLETE"
            before, fingerprints, backup_repo = _capture._backup(base, destination)
            result["backup_status"] = "VERIFIED"
            _capture._verify_inputs(base, before, fingerprints, _capture.FILES)
            result["source_preserved_at_capture"] = True
        # Only the frozen private bytes are used from this point onward.
        result["stage"] = "COPY"
        backup_base = backup_repo / "data" / "learning"
        backup_versions = _versions(backup_base)
        result["working_copy_status"] = "INCOMPLETE"
        working = destination / "working"
        work_base = _working_copy(backup_repo, working, fingerprints)
        result["working_copy_status"] = "VERIFIED"
        captured_work = _versions(work_base)
        result["stage"] = "ADMISSIBILITY"
        control = _runtime.read_learning_evidence_control(work_base)
        result["captured_state"] = control["state"]
        if control["state"] != "ACTIVE":
            raise _Refused("ACTIVE_REQUIRED")
        result["history_rows"], result["current_epoch_rows"] = _history_counts(working, control["epoch"])
        initial_rows = _capture._admissible_memory(work_base, control)
        result["memory_rows_before"] = len(initial_rows)
        totals_before = _totals(working, control, initial_rows)
        result["pairs_before"] = totals_before["pair_count"]
        result["stage"] = "FIRST_BUILD"
        first_stats = _build(working, destination, result, "first", control)
        result["stage"] = "FIRST_VERIFY"
        first_rows = _capture._admissible_memory(work_base, control)
        totals_first = _totals(working, control, first_rows)
        result["pairs_after_first"] = totals_first["pair_count"]
        if result["pairs_after_first"] < result["pairs_before"]:
            raise _Refused("PROJECTION_MISMATCH")
        result["new_pairs_first"] = result["pairs_after_first"] - result["pairs_before"]
        _verify_projection(initial_rows, first_rows, totals_first, control["epoch"], first_stats)
        result["legacy_metadata_preserved"] = True
        result["memory_rows_after"] = len(first_rows)
        first_versions = _verify_work_input(work_base, captured_work, result)
        result["stage"] = "SECOND_BUILD"
        second_stats = _build(working, destination, result, "second", control)
        result["stage"] = "SECOND_VERIFY"
        if result["second_build_status"] != "UNCHANGED" or second_stats["new_evidence"] or second_stats["written"]:
            raise _Refused("SECOND_BUILD_NOT_REPLAY")
        second_rows = _capture._admissible_memory(work_base, control)
        totals_second = _totals(working, control, second_rows)
        result["pairs_after_second"] = totals_second["pair_count"]
        second_versions = _verify_work_input(work_base, captured_work, result)
        result["replay_memory_preserved"] = (first_versions["correction_memory.jsonl"] ==
                                              second_versions["correction_memory.jsonl"] and first_rows == second_rows)
        if not result["replay_memory_preserved"]:
            raise _Refused("REPLAY_MEMORY_CHANGED")
        # Whole database and sidecar bytes also bind events, quarantines and
        # endpoints, not just accepted pair counts. Hashes remain private.
        names = (_runtime.LEDGER_NAME, *(_runtime.LEDGER_NAME + suffix for suffix in ("-journal", "-wal", "-shm")))
        result["replay_ledger_preserved"] = all(first_versions[name] == second_versions[name] for name in names)
        if not result["replay_ledger_preserved"]:
            raise _Refused("REPLAY_LEDGER_CHANGED")
        result["replay_totals_preserved"] = _same_totals(totals_first, totals_second)
        if not result["replay_totals_preserved"]:
            raise _Refused("REPLAY_TOTALS_CHANGED")
        result["stage"] = "POSTCHECK"
        result["backup_preserved"] = _versions(backup_base) == backup_versions
        if not result["backup_preserved"]:
            raise _Refused("BACKUP_CHANGED")
        result.update(status="VERIFIED", reason=None, stage="COMPLETE",
                      coverage="NEW_PAIRS" if result["new_pairs_first"] else
                      "PENDING_PROJECTION_ONLY" if result["new_evidence_first"] else "NO_NEW_PAIRS")
        if not validate_public_result(result):
            raise _Refused("POSTCHECK_FAILED")
    except Exception as error:
        result.update(status="REFUSED", reason=_reason(error), coverage="NOT_ASSESSED")
        if result["stage"] == "COMPLETE":
            result["stage"] = "POSTCHECK"
    if not validate_public_result(result):
        # Preserve whether either build was attempted, without exporting an
        # unexpected payload or claiming the copy remained unchanged.
        first, second = result.get("first_build_status"), result.get("second_build_status")
        result = _result()
        result.update(stage="POSTCHECK", reason="POSTCHECK_FAILED",
                      first_build_status="NOT_RUN" if first == "NOT_RUN" else "UNKNOWN",
                      second_build_status="NOT_RUN" if second == "NOT_RUN" else "UNKNOWN")
    if created:
        try:
            _capture._write_record(destination / "outcome.json", result)
        except Exception:
            result.update(status="REFUSED", reason="RECEIPT_WRITE_FAILED", stage="POSTCHECK", coverage="NOT_ASSESSED")
    return result
