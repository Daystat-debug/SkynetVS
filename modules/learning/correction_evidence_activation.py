"""Controlled private cutover with retained, byte-verified before-images.

The caller must stop older application/builder processes and choose a fresh
backup directory outside the project. One cooperating runtime lock covers the
fixed input backup, admissibility checks, cutover and verification. SQLite is
not opened until all existing database/sidecar bytes have been copied. This is
not a hot-database backup guarantee or protection from noncooperating writers.
No history, correction-memory, model or environment file is rewritten here.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

from modules.learning import correction_evidence_runtime as _runtime
from modules.learning import correction_pair_evidence as _planner
from modules.learning import correction_evidence_ledger as _ledger
from modules.learning import correction_evidence_projection as _projection
from modules.learning.correction_memory import CorrectionMemory
from modules.learning.learning_history_snapshot import read_learning_history_snapshot


KIND = "SKYNETVS_CORRECTION_EVIDENCE_ACTIVATION_V1"
FILES = {
    "command_history.jsonl": 32 * 1024 * 1024,
    "correction_memory.jsonl": 64 * 1024 * 1024,
    "correction_evidence_runtime.json": 4096,
    "correction_evidence.sqlite3": 512 * 1024 * 1024,
    "correction_evidence.sqlite3-journal": 512 * 1024 * 1024,
    "correction_evidence.sqlite3-wal": 512 * 1024 * 1024,
    "correction_evidence.sqlite3-shm": 64 * 1024 * 1024,
}
MAX_BACKUP_BYTES = 768 * 1024 * 1024
MAX_MEMORY_ROWS = 100_000
CHUNK_BYTES = 1024 * 1024
REASONS = frozenset((
    "INVALID_PATH", "BACKUP_IN_PROJECT", "BACKUP_EXISTS", "DIRECTORY_MISSING",
    "UNSAFE_PATH", "BUSY", "LOCK_INVALID", "LOCK_CHANGED", "STORAGE_ERROR",
    "RESOURCE_LIMIT", "INPUT_CHANGED", "BACKUP_FAILED", "HISTORY_REFUSED",
    "HISTORY_INVALID", "HISTORY_DUPLICATE_IDS", "MEMORY_INVALID",
    "MISSING_CONTROL_STATE", "CONTROL_INVALID", "CONTROL_CHANGED", "ORPHAN_LEDGER",
    "LEDGER_INVALID", "EPOCH_MISMATCH", "MEMORY_LEDGER_MISMATCH",
    "AMBIGUOUS_PREPARING_LEDGER", "ACTIVATION_OUTCOME_UNKNOWN", "POSTCHECK_FAILED",
    "HISTORY_CHANGED", "MEMORY_CHANGED", "PAIR_COUNT_CHANGED", "RECEIPT_WRITE_FAILED",
    "INTERNAL_ERROR",
))
SCOPE = {
    "private_backup": "FIXED_FILES_BYTE_VERIFIED_BEFORE_SQLITE",
    "runtime_lock": "COOPERATING_WRITERS_ONLY",
    "old_process_gate": "CALLER_REQUIRED",
    "lock_file": "PERSISTENT_ONE_BYTE_NOT_BACKED_UP",
    "sqlite_read_may_recover_journal": True,
    "atomic_filesystem_snapshot": False,
    "history_written": False,
    "correction_memory_written": False,
    "ledger_sync_run": False,
    "projection_run": False,
    "training_run": False,
    "promotion_run": False,
    "legacy_counts_repaired": False,
    "automatic_restore": False,
    "training_readiness": "NOT_ASSESSED",
}


class _Refused(ValueError):
    def __init__(self, reason):
        self.reason = reason


def _result():
    return {"kind": KIND, "status": "REFUSED", "reason": "INTERNAL_ERROR",
            "stage": "PREFLIGHT", "initial_state": "UNKNOWN", "final_state": "UNKNOWN",
            "backup_status": "NOT_CREATED", "activation_status": "NOT_RUN",
            "history_rows": None, "memory_rows": None, "pairs_before": None, "pairs_after": None,
            "history_preserved": None, "memory_preserved": None, "scope": dict(SCOPE)}


def validate_public_result(value):
    """Validate the complete public envelope; no measured strings are allowed."""
    if type(value) is not dict or set(value) != set(_result()):
        return False
    if value["kind"] != KIND or type(value["kind"]) is not str:
        return False
    enumerations = {
        "status": ("ACTIVATED", "ALREADY_ACTIVE", "REFUSED"),
        "stage": ("PREFLIGHT", "LOCK", "BACKUP", "ADMISSIBILITY", "ACTIVATION", "POSTCHECK", "COMPLETE"),
        "initial_state": ("UNKNOWN", "LEGACY", "PREPARING", "ACTIVE"),
        "final_state": ("UNKNOWN", "LEGACY", "PREPARING", "ACTIVE"),
        "backup_status": ("NOT_CREATED", "INCOMPLETE", "VERIFIED"),
        "activation_status": ("NOT_RUN", "ATTEMPTED", "ACTIVATED", "UNCHANGED", "REFUSED", "UNKNOWN"),
    }
    for name, allowed in enumerations.items():
        if type(value[name]) is not str or value[name] not in allowed:
            return False
    if value["reason"] is not None and (type(value["reason"]) is not str or value["reason"] not in REASONS):
        return False
    for name in ("history_rows", "memory_rows", "pairs_before", "pairs_after"):
        item = value[name]
        if item is not None and (type(item) is not int or not 0 <= item <= 1_000_000):
            return False
    for name in ("history_preserved", "memory_preserved"):
        if value[name] is not None and type(value[name]) is not bool:
            return False
    if (type(value["scope"]) is not dict or set(value["scope"]) != set(SCOPE)
            or any(type(value["scope"][key]) is not type(expected) or value["scope"][key] != expected
                   for key, expected in SCOPE.items())):
        return False
    if value["status"] == "REFUSED":
        return value["reason"] in REASONS and value["stage"] != "COMPLETE"
    if (value["reason"] is not None or value["stage"] != "COMPLETE"
            or value["backup_status"] != "VERIFIED" or value["final_state"] != "ACTIVE"
            or value["history_preserved"] is not True or value["memory_preserved"] is not True
            or any(value[name] is None for name in ("history_rows", "memory_rows", "pairs_before", "pairs_after"))
            or value["pairs_before"] != value["pairs_after"]):
        return False
    if value["status"] == "ACTIVATED":
        return (value["activation_status"] == "ACTIVATED" and value["initial_state"] in ("LEGACY", "PREPARING")
                and value["pairs_after"] == 0)
    return value["activation_status"] == "UNCHANGED" and value["initial_state"] == "ACTIVE"


def _absolute(value):
    if type(value) not in (str, type(Path())):
        raise _Refused("INVALID_PATH")
    try:
        path = Path(value)
        if (not path.is_absolute() or ".." in path.parts or "\x00" in str(path)
                or str(path).startswith(("//", "\\\\"))):
            raise _Refused("INVALID_PATH")
        return path
    except (ValueError, TypeError, OSError):
        raise _Refused("INVALID_PATH") from None


def _version(info):
    # Path stat and fstat have different ctime/permission semantics on Windows
    # CPython 3.12. Compare their common fields across APIs, full fields within.
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), info.st_size, info.st_mtime_ns


def _signature(info):
    return _version(info) + (info.st_mode, info.st_ctime_ns, info.st_nlink)


def _stat(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    _runtime._safe(info)
    return info


def _inventory(base):
    _runtime._directory(base)
    result = {}
    total = 0
    for name, maximum in FILES.items():
        info = _stat(base / name)
        if info is not None:
            if info.st_size > maximum:
                raise _Refused("RESOURCE_LIMIT")
            total += info.st_size
            if total > MAX_BACKUP_BYTES:
                raise _Refused("RESOURCE_LIMIT")
        result[name] = info
    return result


def _same_inventory(left, right):
    return all((None if left[name] is None else _signature(left[name])) ==
               (None if right[name] is None else _signature(right[name])) for name in FILES)


def _fingerprint(path, maximum, expected=None, *, target=None):
    before = _stat(path)
    if before is None:
        if expected is not None:
            raise _Refused("INPUT_CHANGED")
        return None
    if before.st_size > maximum:
        raise _Refused("RESOURCE_LIMIT")
    if expected is not None and _signature(before) != _signature(expected):
        raise _Refused("INPUT_CHANGED")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    destination = None
    try:
        opened = os.fstat(descriptor)
        _runtime._safe(opened)
        if _version(opened) != _version(before):
            raise _Refused("INPUT_CHANGED")
        if target is not None:
            write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            destination = os.open(target, write_flags, 0o600)
        digest = hashlib.sha256()
        size = 0
        while True:
            raw = os.read(descriptor, min(CHUNK_BYTES, maximum - size + 1))
            if not raw:
                break
            size += len(raw)
            if size > maximum:
                raise _Refused("RESOURCE_LIMIT")
            digest.update(raw)
            if destination is not None:
                view = memoryview(raw)
                while view:
                    written = os.write(destination, view)
                    if not written:
                        raise OSError("backup write failed")
                    view = view[written:]
        after_open = os.fstat(descriptor)
        after = _stat(path)
        if (after is None or _signature(after) != _signature(before)
                or _signature(opened) != _signature(after_open) or size != before.st_size):
            raise _Refused("INPUT_CHANGED")
        if destination is not None:
            os.fsync(destination)
        return {"bytes": size, "sha256": digest.hexdigest()}
    finally:
        if destination is not None:
            os.close(destination)
        os.close(descriptor)


def _write_record(path, record):
    raw = (json.dumps(record, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2) + "\n").encode("ascii")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise _Refused("BACKUP_FAILED")


def _backup(base, destination):
    before = _inventory(base)
    copied = destination / "before" / "data" / "learning"
    copied.mkdir(parents=True)
    fingerprints = {}
    metadata = {}
    for name, info in before.items():
        if info is None:
            fingerprints[name] = None
            metadata[name] = None
            continue
        fingerprint = _fingerprint(base / name, FILES[name], info, target=copied / name)
        if _fingerprint(copied / name, FILES[name]) != fingerprint:
            raise _Refused("BACKUP_FAILED")
        fingerprints[name] = fingerprint
        metadata[name] = {"size": info.st_size, "mtime_ns": info.st_mtime_ns,
                          "ctime_ns": info.st_ctime_ns, "mode": info.st_mode,
                          "device": info.st_dev, "inode": info.st_ino}
    if not _same_inventory(before, _inventory(base)):
        raise _Refused("INPUT_CHANGED")
    _write_record(destination / "backup_ready.json", {
        "kind": "SKYNETVS_CORRECTION_EVIDENCE_PRIVATE_BACKUP_V1",
        "state": "VERIFIED_BEFORE_SQLITE", "files": fingerprints, "metadata": metadata,
        "lock_file": "EXCLUDED_WHILE_LOCKED", "atomic_filesystem_snapshot": False,
        "automatic_restore": False,
    })
    return before, fingerprints, destination / "before"


def _verify_inputs(base, before, fingerprints, names):
    _runtime._directory(base)
    for name in names:
        current = _stat(base / name)
        expected = before[name]
        if ((current is None) != (expected is None)
                or current is not None and _signature(current) != _signature(expected)):
            raise _Refused("INPUT_CHANGED")
        if _fingerprint(base / name, FILES[name], expected) != fingerprints[name]:
            raise _Refused("INPUT_CHANGED")


def _admissible_history(backup_repo):
    snapshot = read_learning_history_snapshot(backup_repo)
    if snapshot["status"] != "COMPLETE":
        raise _Refused("HISTORY_REFUSED")
    plan = _planner.plan_correction_pair_evidence(snapshot["rows"], snapshot_complete=True)
    if plan["status"] != "READY":
        raise _Refused("HISTORY_REFUSED")
    observations = plan["observations"]
    if observations["invalid_rows"] or observations["uncomparable_rows"]:
        raise _Refused("HISTORY_INVALID")
    if observations["repeated_event_id_groups"]:
        raise _Refused("HISTORY_DUPLICATE_IDS")
    return len(snapshot["rows"])


def _admissible_memory(backup_base, control):
    memory = CorrectionMemory(str(backup_base / "correction_memory.jsonl"))
    try:
        rows = memory._read_snapshot_rows()
        if len(rows) > MAX_MEMORY_ROWS:
            raise _Refused("RESOURCE_LIMIT")
        budget = {"nodes": 0, "units": 0}
        for row in rows:
            payload, portable = _planner._canonical_payload(row, budget)
            if payload is None or not portable:
                raise _Refused("MEMORY_INVALID")
            if any(type(row.get(name)) is not str or not row[name].strip()
                   for name in ("failed_text", "corrected_text", "corrected_intent")):
                raise _Refused("MEMORY_INVALID")
            if row["key"] != memory._make_key(row["failed_text"], row["corrected_text"], row["corrected_intent"]):
                raise _Refused("MEMORY_INVALID")
            if not 0 <= row.get("corrected_confidence", 0.0) <= 1:
                raise _Refused("MEMORY_INVALID")
            if "status" in row and type(row["status"]) is not str:
                raise _Refused("MEMORY_INVALID")
            if "event_evidence" in row and control["state"] != "ACTIVE":
                raise _Refused("MISSING_CONTROL_STATE")
        return rows
    except _planner._LimitReached:
        raise _Refused("RESOURCE_LIMIT") from None
    except _Refused:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise _Refused("MEMORY_INVALID") from None


def _ledger_state(root, control, rows, *, database_present):
    if control["state"] == "LEGACY" or control["state"] == "PREPARING" and not database_present:
        return None, 0
    totals = _ledger.read_correction_evidence_totals(root)
    if totals["status"] != "READY":
        raise _Refused("LEDGER_INVALID")
    if control["state"] == "PREPARING":
        if totals["pair_count"] != 0:
            raise _Refused("AMBIGUOUS_PREPARING_LEDGER")
    else:
        if totals["epoch"] != control["epoch"]:
            raise _Refused("EPOCH_MISMATCH")
        candidates = {row["key"]: row["count"] for row in totals["candidates"]}
        for row in rows:
            try:
                observed = _projection._checkpoint(row, control["epoch"])
            except _projection._Refused as error:
                raise _Refused("EPOCH_MISMATCH" if error.reason == "EPOCH_MISMATCH" else "MEMORY_INVALID") from None
            if observed > candidates.get(row["key"], 0):
                raise _Refused("MEMORY_LEDGER_MISMATCH")
    return totals["epoch"], totals["pair_count"]


def _reason(error):
    if isinstance(error, (_Refused, _runtime.RuntimeRefused)) and error.reason in REASONS:
        return error.reason
    return "STORAGE_ERROR" if isinstance(error, OSError) else "INTERNAL_ERROR"


def activate_correction_evidence_safely(repo, backup_directory):
    """Create a retained backup and activate or verify the existing event mode.

    ``backup_directory`` must be a fresh absolute local directory outside repo;
    the caller chooses a new directory on every retry and retains earlier ones.
    Raw backup digests and all file contents stay there. The returned dictionary
    is suitable for publication only after validate_public_result succeeds.

    An interruption can leave PREPARING, a partial ledger or an ACTIVE control.
    Nothing is reset/restored automatically. Retrying snapshots that actual state
    and resumes only states accepted by the runtime. The lock file may be created
    before backup and remains afterward; it is never copied through another
    handle while the Windows byte-range lock is held.
    """
    result = _result()
    activation_attempted = False
    try:
        root = _absolute(repo)
        destination = _absolute(backup_directory)
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
            result["backup_status"] = "INCOMPLETE"
            before, fingerprints, backup_repo = _backup(base, destination)
            result["backup_status"] = "VERIFIED"
            result["stage"] = "ADMISSIBILITY"
            backup_base = backup_repo / "data" / "learning"
            control = _runtime.read_learning_evidence_control(backup_base)
            result["initial_state"] = control["state"]
            result["history_rows"] = _admissible_history(backup_repo)
            rows = _admissible_memory(backup_base, control)
            result["memory_rows"] = len(rows)
            _verify_inputs(base, before, fingerprints, FILES)
            # Even an existing-file SQLite read can recover a hot journal. Its
            # before-images and durable marker must already exist at this point.
            _write_record(destination / "sqlite_intent.json", {
                "kind": "SKYNETVS_CORRECTION_EVIDENCE_PRIVATE_INTENT_V1",
                "operation": "EXISTING_LEDGER_VALIDATION_OR_ACTIVATION",
                "initial_state": control["state"],
            })
            prior_epoch, prior_pairs = _ledger_state(
                root, control, rows, database_present=before[_runtime.LEDGER_NAME] is not None)
            result["pairs_before"] = prior_pairs
            _verify_inputs(base, before, fingerprints,
                           ("command_history.jsonl", "correction_memory.jsonl", _runtime.CONTROL_NAME))
            _write_record(destination / "activation_intent.json", {
                "kind": "SKYNETVS_CORRECTION_EVIDENCE_PRIVATE_INTENT_V1",
                "operation": "ACTIVATE_OR_VERIFY", "initial_state": control["state"],
            })
            result["stage"] = "ACTIVATION"
            result["activation_status"] = "ATTEMPTED"
            activation_attempted = True
            try:
                outcome = _runtime._activate_learning_evidence_locked(root, base)
            except Exception:
                result["activation_status"] = "UNKNOWN"
                raise _Refused("ACTIVATION_OUTCOME_UNKNOWN") from None
            if outcome["status"] not in ("ACTIVATED", "UNCHANGED"):
                result["activation_status"] = "UNKNOWN"
                raise _Refused("ACTIVATION_OUTCOME_UNKNOWN")
            result["activation_status"] = outcome["status"]
            result["stage"] = "POSTCHECK"
            after_control = _runtime.read_learning_evidence_control(base)
            result["final_state"] = after_control["state"]
            if after_control["state"] != "ACTIVE":
                raise _Refused("POSTCHECK_FAILED")
            if prior_epoch is not None and after_control["epoch"] != prior_epoch:
                raise _Refused("EPOCH_MISMATCH")
            _, result["pairs_after"] = _ledger_state(root, after_control, rows, database_present=True)
            if result["pairs_after"] != prior_pairs:
                raise _Refused("PAIR_COUNT_CHANGED")
            for name, field, reason in (("command_history.jsonl", "history_preserved", "HISTORY_CHANGED"),
                                         ("correction_memory.jsonl", "memory_preserved", "MEMORY_CHANGED")):
                try:
                    _verify_inputs(base, before, fingerprints, (name,))
                except Exception as error:
                    if isinstance(error, _Refused) and error.reason == "INPUT_CHANGED":
                        result[field] = False
                        raise _Refused(reason) from None
                    result[field] = None
                    raise _Refused("POSTCHECK_FAILED") from None
                result[field] = True
            result.update(status="ALREADY_ACTIVE" if control["state"] == "ACTIVE" else "ACTIVATED",
                          reason=None, stage="COMPLETE")
            if not validate_public_result(result):
                raise _Refused("POSTCHECK_FAILED")
            try:
                _write_record(destination / "outcome.json", result)
            except Exception:
                result.update(status="REFUSED", reason="RECEIPT_WRITE_FAILED", stage="POSTCHECK")
    except Exception as error:
        result.update(status="REFUSED", reason=_reason(error))
        if result["stage"] == "COMPLETE":
            result["stage"] = "POSTCHECK"
    # Never pass an unexpected implementation payload through a public report.
    if not validate_public_result(result):
        result = _result()
        if activation_attempted:
            result.update(stage="POSTCHECK", activation_status="UNKNOWN", reason="ACTIVATION_OUTCOME_UNKNOWN")
    return result
