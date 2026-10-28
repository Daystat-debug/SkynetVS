"""Private SQLite accounting for complete, identified correction snapshots.

The opt-in runtime coordinator controls activation and memory projection.
Initialization binds existing IDs without credit. Later credit requires the
fresh ledger epoch on both endpoints; old/no-epoch events remain ineligible.
An epoch is a local cutover marker, not authentication or independent evidence.
SQLite serializes ledger changes, not the history file or another memory file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from uuid import uuid4

from modules.learning import correction_pair_evidence as _planner
from modules.learning.learning_history_snapshot import read_learning_history_snapshot


KIND = "SKYNETVS_CORRECTION_EVIDENCE_LEDGER_RESULT_V1"
STATE_KIND = "SKYNETVS_CORRECTION_EVIDENCE_LEDGER_V1"
RELATIVE_PATH = ("data", "learning", "correction_evidence.sqlite3")
EPOCH_FIELD = "evidence_epoch"
APPLICATION_ID = 1397441868
LIMITS = {
    "bound_events": 1_000_000,
    "bound_payload_bytes": 256 * 1024 * 1024,
    "accepted_pairs": 500_000,
    "pair_payload_bytes": 128 * 1024 * 1024,
    "database_bytes": 512 * 1024 * 1024,
}
SCOPE = {
    "output": "PRIVATE_LEDGER_RESULT",
    "cutover": "EXACT_EPOCH_ON_BOTH_ENDPOINTS",
    "history_snapshot_atomic": False,
    "event_identity_authenticated": False,
    "independent_observations_verified": False,
    "correction_memory_written": False,
    "legacy_aggregate_disabled": False,
    "runtime_integration": False,
    "training_readiness": "NOT_ASSESSED",
    "refusal_guarantees_unchanged_file_bytes": False,
}
SCHEMA = {
    "meta": "CREATE TABLE meta (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), kind TEXT NOT NULL, schema_version INTEGER NOT NULL, rule_version TEXT NOT NULL, epoch TEXT NOT NULL, baseline_rows INTEGER NOT NULL, legacy_source TEXT NOT NULL)",
    "events": "CREATE TABLE events (event_id BLOB PRIMARY KEY NOT NULL, payload BLOB NOT NULL, baseline INTEGER NOT NULL CHECK (baseline IN (0, 1)), quarantined INTEGER NOT NULL CHECK (quarantined IN (0, 1)))",
    "pairs": "CREATE TABLE pairs (failed_id BLOB PRIMARY KEY NOT NULL REFERENCES events(event_id), corrected_id BLOB UNIQUE NOT NULL REFERENCES events(event_id), evidence BLOB NOT NULL, CHECK (failed_id != corrected_id))",
    "endpoints": "CREATE TABLE endpoints (event_id BLOB PRIMARY KEY NOT NULL REFERENCES events(event_id), pair_failed_id BLOB NOT NULL REFERENCES pairs(failed_id), role TEXT NOT NULL CHECK (role IN ('failed', 'corrected')), UNIQUE (pair_failed_id, role))",
}


class _Refused(ValueError):
    def __init__(self, reason):
        self.reason = reason


def _result(operation, *, status="REFUSED", reason=None, input_reason=None,
            epoch=None, committed=False, file_created=False, stats=None):
    return {"kind": KIND, "operation": operation, "status": status,
            "reason": reason, "input_reason": input_reason, "epoch": epoch,
            "transaction_committed": committed, "ledger_file_created": file_created,
            "stats": stats, "scope": dict(SCOPE), "limits": dict(LIMITS)}


def _identity(info):
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def _safe_component(info, directory):
    if (stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
        raise _Refused("UNSAFE_PATH")
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise _Refused("UNSAFE_PATH")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise _Refused("UNSAFE_PATH")


def _inspect_storage(target, *, allow_missing=False):
    """Ordinary path checks, not a guarantee against hostile replacement races."""
    chain = []
    current = Path(target.anchor)
    for part in target.parts[1:-1]:
        current /= part
        info = current.lstat()
        _safe_component(info, True)
        chain.append(_identity(info))
    try:
        info = target.lstat()
    except FileNotFoundError:
        if not allow_missing:
            raise _Refused("LEDGER_MISSING") from None
        identity = None
    else:
        _safe_component(info, False)
        if info.st_size > LIMITS["database_bytes"]:
            raise _Refused("RESOURCE_LIMIT")
        identity = _identity(info)
    for suffix in ("-journal", "-wal", "-shm"):
        sidecar = target.with_name(target.name + suffix)
        try:
            side_info = sidecar.lstat()
        except FileNotFoundError:
            continue
        _safe_component(side_info, False)
        if side_info.st_size > LIMITS["database_bytes"]:
            raise _Refused("RESOURCE_LIMIT")
        if suffix != "-journal" or identity is None:
            raise _Refused("UNEXPECTED_SIDECAR")
    return tuple(chain), identity


def _key(event_id):
    # An ASCII JSON string preserves opaque IDs, including lone surrogates,
    # without invoking SQLite's UTF-8 text encoder on the original value.
    return json.dumps(event_id, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _prepare_rows(rows):
    """Intentionally share the pinned planner's exact bounded JSON comparison."""
    budget = {"nodes": 0, "units": 0}
    groups = {}
    canonical_total = 0
    for row in rows:
        _, event_id, _ = _planner._top_fields(row, budget)
        if event_id is None:
            continue
        payload, _ = _planner._canonical_payload(row, budget)
        if payload is None:
            raise _Refused("UNCOMPARABLE_EVENT_PAYLOAD")
        canonical_total += len(payload)
        if canonical_total > _planner.MAX_CANONICAL_TOTAL_BYTES:
            raise _Refused("RESOURCE_LIMIT")
        key = _key(event_id)
        previous = groups.get(key)
        if previous is None:
            groups[key] = {"payload": payload, "row": row, "duplicates": False}
        elif previous["payload"] != payload:
            raise _Refused("EVENT_PAYLOAD_CONFLICT")
        else:
            previous["duplicates"] = True
    return groups


def _connect(target):
    return sqlite3.connect(target.as_uri() + "?mode=rw", uri=True,
                           timeout=0, isolation_level=None)


def _configure(connection):
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA trusted_schema = OFF")
    if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
        raise _Refused("STATE_INVALID")
    if connection.execute("PRAGMA journal_mode").fetchone() != ("delete",):
        raise _Refused("STATE_INVALID")
    connection.execute("PRAGMA synchronous = FULL")
    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    if type(page_size) is not int or not 512 <= page_size <= 65536 or page_size & (page_size - 1):
        raise _Refused("STATE_INVALID")
    maximum = LIMITS["database_bytes"] // page_size
    if connection.execute("PRAGMA max_page_count = " + str(maximum)).fetchone()[0] > maximum:
        raise _Refused("RESOURCE_LIMIT")


def _validate_state(connection):
    actual = connection.execute(
        "SELECT name, type, tbl_name, sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' LIMIT " + str(len(SCHEMA) + 1)
    ).fetchall()
    if {name: (kind, table, sql) for name, kind, table, sql in actual} != {
            name: ("table", name, sql) for name, sql in SCHEMA.items()} or len(actual) != len(SCHEMA):
        raise _Refused("STATE_INVALID")
    if (connection.execute("PRAGMA application_id").fetchone() != (APPLICATION_ID,)
            or connection.execute("PRAGMA user_version").fetchone() != (1,)):
        raise _Refused("STATE_INVALID")
    meta = connection.execute("SELECT * FROM meta LIMIT 2").fetchall()
    if (len(meta) != 1 or len(meta[0]) != 7 or meta[0][:4] != (1, STATE_KIND, 1, _planner.RULE_VERSION)
            or type(meta[0][4]) is not str or re.fullmatch(r"[0-9a-f]{32}", meta[0][4]) is None
            or type(meta[0][5]) is not int or not 0 <= meta[0][5] <= _planner.MAX_ROWS
            or meta[0][6] != "feedback_analyzer_v2"):
        raise _Refused("STATE_INVALID")
    event_count = connection.execute("SELECT count(*) FROM events").fetchone()[0]
    pair_count = connection.execute("SELECT count(*) FROM pairs").fetchone()[0]
    if event_count > LIMITS["bound_events"] or pair_count > LIMITS["accepted_pairs"]:
        raise _Refused("RESOURCE_LIMIT")
    event_bytes, baseline_count, quarantine_count = connection.execute(
        "SELECT coalesce(sum(length(payload)), 0), coalesce(sum(baseline), 0), coalesce(sum(quarantined), 0) FROM events"
    ).fetchone()
    pair_bytes = connection.execute("SELECT coalesce(sum(length(evidence)), 0) FROM pairs").fetchone()[0]
    if event_bytes > LIMITS["bound_payload_bytes"] or pair_bytes > LIMITS["pair_payload_bytes"]:
        raise _Refused("RESOURCE_LIMIT")
    if baseline_count > meta[0][5]:
        raise _Refused("STATE_INVALID")
    malformed_event = connection.execute(
        "SELECT 1 FROM events WHERE typeof(event_id) != 'blob' OR length(event_id) = 0 "
        "OR typeof(payload) != 'blob' OR length(payload) = 0 OR typeof(baseline) != 'integer' "
        "OR baseline NOT IN (0, 1) OR typeof(quarantined) != 'integer' OR quarantined NOT IN (0, 1) LIMIT 1"
    ).fetchone()
    malformed_pair = connection.execute(
        "SELECT 1 FROM pairs WHERE typeof(failed_id) != 'blob' OR typeof(corrected_id) != 'blob' "
        "OR typeof(evidence) != 'blob' OR length(evidence) = 0 OR failed_id = corrected_id LIMIT 1"
    ).fetchone()
    malformed_endpoint = connection.execute(
        "SELECT 1 FROM endpoints WHERE typeof(event_id) != 'blob' OR typeof(pair_failed_id) != 'blob' "
        "OR typeof(role) != 'text' OR role NOT IN ('failed', 'corrected') LIMIT 1"
    ).fetchone()
    if malformed_event or malformed_pair or malformed_endpoint:
        raise _Refused("STATE_INVALID")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise _Refused("STATE_INVALID")
    if connection.execute("SELECT count(*) FROM endpoints").fetchone()[0] != 2 * pair_count:
        raise _Refused("STATE_INVALID")
    if connection.execute(
        "SELECT 1 FROM pairs p LEFT JOIN endpoints f ON f.event_id = p.failed_id "
        "LEFT JOIN endpoints c ON c.event_id = p.corrected_id "
        "WHERE f.event_id IS NULL OR c.event_id IS NULL OR f.pair_failed_id != p.failed_id "
        "OR c.pair_failed_id != p.failed_id OR f.role != 'failed' OR c.role != 'corrected' LIMIT 1"
    ).fetchone() is not None:
        raise _Refused("STATE_INVALID")
    return {"epoch": meta[0][4], "events": event_count, "event_bytes": event_bytes,
            "baseline": baseline_count, "quarantined": quarantine_count,
            "pairs": pair_count, "pair_bytes": pair_bytes}


def _prepare_changes(connection, groups, pairs, state, initialize, row_count):
    new_events = []
    quarantine = []
    known = {}
    stats = dict.fromkeys(("input_rows", "visible_ids", "new_bindings", "new_quarantines", "new_pairs",
                           "replayed_pairs", "baseline_pairs_skipped", "epoch_pairs_skipped",
                           "quarantined_pairs_skipped", "consumed_endpoint_pairs_skipped"), 0)
    stats["input_rows"], stats["visible_ids"] = row_count, len(groups)
    for key, group in groups.items():
        existing = connection.execute("SELECT payload, baseline, quarantined FROM events WHERE event_id = ?", (key,)).fetchone()
        if existing is None:
            baseline, blocked = int(initialize), int(group["duplicates"])
            new_events.append((key, group["payload"], baseline, blocked))
        else:
            payload, baseline, blocked = existing
            if payload != group["payload"]:
                raise _Refused("EVENT_PAYLOAD_CONFLICT")
            if group["duplicates"] and not blocked:
                blocked = 1
                quarantine.append((key,))
        known[key] = (baseline, blocked)
    new_pairs = []
    prospective_endpoints = set()
    for pair in pairs:
        identity = pair["pair_identity"]
        failed, corrected = _key(identity["failed_event_id"]), _key(identity["corrected_event_id"])
        if any(known[key][0] for key in (failed, corrected)):
            stats["baseline_pairs_skipped"] += 1
        elif any(known[key][1] for key in (failed, corrected)):
            stats["quarantined_pairs_skipped"] += 1
        elif any(type(groups[key]["row"].get(EPOCH_FIELD)) is not str
                 or groups[key]["row"][EPOCH_FIELD] != state["epoch"] for key in (failed, corrected)):
            stats["epoch_pairs_skipped"] += 1
        elif connection.execute("SELECT 1 FROM pairs WHERE failed_id = ? AND corrected_id = ?", (failed, corrected)).fetchone():
            stats["replayed_pairs"] += 1
        elif (failed in prospective_endpoints or corrected in prospective_endpoints
              or connection.execute("SELECT 1 FROM endpoints WHERE event_id IN (?, ?) LIMIT 1", (failed, corrected)).fetchone()):
            stats["consumed_endpoint_pairs_skipped"] += 1
        else:
            evidence = json.dumps(pair, sort_keys=True, ensure_ascii=True, allow_nan=False,
                                  separators=(",", ":")).encode("ascii")
            new_pairs.append((failed, corrected, evidence))
            prospective_endpoints.update((failed, corrected))
    event_bytes = state["event_bytes"] + sum(len(row[1]) for row in new_events)
    pair_bytes = state["pair_bytes"] + sum(len(row[2]) for row in new_pairs)
    if (state["events"] + len(new_events) > LIMITS["bound_events"]
            or state["pairs"] + len(new_pairs) > LIMITS["accepted_pairs"]
            or event_bytes > LIMITS["bound_payload_bytes"] or pair_bytes > LIMITS["pair_payload_bytes"]):
        raise _Refused("RESOURCE_LIMIT")
    stats.update(new_bindings=len(new_events), new_quarantines=len(quarantine) + sum(row[3] for row in new_events),
                 new_pairs=len(new_pairs), bound_events_total=state["events"] + len(new_events),
                 baseline_events_total=state["baseline"] + sum(row[2] for row in new_events),
                 quarantined_events_total=state["quarantined"] + len(quarantine) + sum(row[3] for row in new_events),
                 accepted_pairs_total=state["pairs"] + len(new_pairs))
    return new_events, quarantine, new_pairs, stats


def _storage_reason(error):
    code = getattr(error, "sqlite_errorcode", 0) & 0xff
    if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        return "BUSY"
    if code in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
        return "STATE_INVALID"
    return "STORAGE_ERROR"


def _run(repo, initialize):
    operation = "INITIALIZE" if initialize else "SYNC"
    snapshot = read_learning_history_snapshot(repo)
    if snapshot["status"] != "COMPLETE":
        return _result(operation, reason="HISTORY_REFUSED", input_reason=snapshot["reason"])
    rows = snapshot["rows"]
    plan = _planner.plan_correction_pair_evidence(rows, snapshot_complete=True)
    if plan["status"] != "READY":
        return _result(operation, reason="PLAN_REFUSED", input_reason=plan["reason"])
    try:
        groups = _prepare_rows(rows)
    except _planner._LimitReached:
        return _result(operation, reason="RESOURCE_LIMIT")
    except _Refused as error:
        return _result(operation, reason=error.reason)
    except Exception:
        return _result(operation, reason="INTERNAL_ERROR")

    target = Path(repo).joinpath(*RELATIVE_PATH)
    connection = None
    created = False
    commit_attempted = False
    rollback_attempted = False
    try:
        path_identity = _inspect_storage(target, allow_missing=initialize)
        if initialize:
            if path_identity[1] is not None:
                raise _Refused("LEDGER_ALREADY_EXISTS")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(target, flags, 0o600)
            created = True
            os.close(descriptor)
            path_identity = _inspect_storage(target)
        connection = _connect(target)
        _configure(connection)
        connection.execute("BEGIN IMMEDIATE")
        if _inspect_storage(target) != path_identity:
            raise _Refused("PATH_CHANGED")
        if initialize:
            if connection.execute("SELECT name FROM sqlite_master").fetchone() is not None:
                raise _Refused("STATE_INVALID")
            for statement in SCHEMA.values():
                connection.execute(statement)
            connection.execute("PRAGMA application_id = " + str(APPLICATION_ID))
            connection.execute("PRAGMA user_version = 1")
            epoch = uuid4().hex
            connection.execute("INSERT INTO meta VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (1, STATE_KIND, 1, _planner.RULE_VERSION, epoch, len(rows), "feedback_analyzer_v2"))
        state = _validate_state(connection)
        new_events, quarantine, new_pairs, stats = _prepare_changes(
            connection, groups, plan["pairs"], state, initialize, len(rows))
        connection.executemany("INSERT INTO events VALUES (?, ?, ?, ?)", new_events)
        connection.executemany("UPDATE events SET quarantined = 1 WHERE event_id = ?", quarantine)
        for failed, corrected, evidence in new_pairs:
            connection.execute("INSERT INTO pairs VALUES (?, ?, ?)", (failed, corrected, evidence))
            connection.executemany("INSERT INTO endpoints VALUES (?, ?, ?)",
                                   ((failed, failed, "failed"), (corrected, failed, "corrected")))
        if _inspect_storage(target) != path_identity:
            raise _Refused("PATH_CHANGED")
        changed = initialize or bool(new_events or quarantine or new_pairs)
        if not changed:
            rollback_attempted = True
            connection.rollback()
            return _result(operation, status="UNCHANGED", epoch=state["epoch"], stats=stats)
        commit_attempted = True
        connection.commit()
        return _result(operation, status="INITIALIZED" if initialize else "APPLIED",
                       epoch=state["epoch"], committed=True, file_created=created, stats=stats)
    except Exception as error:
        reason = (error.reason if isinstance(error, _Refused) else
                  _storage_reason(error) if isinstance(error, sqlite3.Error) else
                  "LEDGER_ALREADY_EXISTS" if isinstance(error, FileExistsError) else
                  "STORAGE_ERROR" if isinstance(error, OSError) else "INTERNAL_ERROR")
        unknown = commit_attempted or rollback_attempted
        if connection is not None:
            try:
                if connection.in_transaction:
                    connection.rollback()
            except Exception:
                unknown = True
        if unknown:
            reason = "COMMIT_OUTCOME_UNKNOWN" if commit_attempted else "ROLLBACK_OUTCOME_UNKNOWN"
        return _result(operation, reason=reason, committed=None if unknown else False, file_created=created)
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def initialize_correction_evidence_ledger(repo):
    """Bind the complete current history as baseline and create a fresh epoch.

    The final file is exclusively created. A failed initialization may leave an
    empty/partial owned file; it is preserved and never automatically reset.
    No learned counts or legacy source switch are applied by this component.
    """
    return _run(repo, True)


def sync_correction_evidence_ledger(repo):
    """Record eligible epoch-marked pairs in the existing ledger, once per ID.

    Rotated/overlapping histories can replay known IDs but cannot change their
    payload. Both endpoints must be unused, nonbaseline and nonquarantined.
    A later conflict/quarantine never retracts already accepted historical pairs.
    Unknown transaction outcomes return no fresh evidence; retry via this API.
    Never apply a returned delta directly to another file as an atomic operation.
    """
    return _run(repo, False)


TOTALS_KIND = "SKYNETVS_CORRECTION_EVIDENCE_TOTALS_V1"


def _totals_result(reason=None, *, epoch=None, candidates=None, pair_count=None):
    return {"kind": TOTALS_KIND, "status": "REFUSED" if reason else "READY",
            "reason": reason, "epoch": epoch, "candidates": [] if reason else candidates,
            "pair_count": pair_count, "scope": {
                "output": "PRIVATE_COMPLETE_ACCEPTED_TOTALS", "history_read": False,
                "correction_memory_written": False, "historical_quarantine_retracts_credit": False,
                "authenticated_state": False, "training_readiness": "NOT_ASSESSED",
                "refusal_guarantees_unchanged_file_bytes": False}}


def _decode_canonical(raw, maximum):
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise _Refused("STATE_INVALID")
    try:
        value = json.loads(raw)
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=True,
                             allow_nan=False, separators=(",", ":")).encode("ascii")
        if encoded != raw:
            raise ValueError()
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise _Refused("STATE_INVALID") from None
    return value


def _validated_stored_pair(record, epoch):
    failed_id, corrected_id, evidence, failed_raw, corrected_raw, failed_baseline, corrected_baseline = record
    failed = _decode_canonical(failed_raw, _planner.MAX_CANONICAL_ROW_BYTES)
    corrected = _decode_canonical(corrected_raw, _planner.MAX_CANONICAL_ROW_BYTES)
    pair = _decode_canonical(evidence, 2 * _planner.MAX_CANONICAL_ROW_BYTES)
    if (type(failed) is not dict or type(corrected) is not dict or type(pair) is not dict
            or failed_baseline or corrected_baseline
            or any(type(row.get(EPOCH_FIELD)) is not str or row[EPOCH_FIELD] != epoch
                   for row in (failed, corrected))
            or _key(failed.get("event_id")) != failed_id
            or _key(corrected.get("event_id")) != corrected_id
            or type(pair.get("failed_index")) is not int
            or not 0 <= pair["failed_index"] < _planner.MAX_ROWS - 1
            or type(pair.get("corrected_index")) is not int
            or pair["corrected_index"] != pair["failed_index"] + 1):
        raise _Refused("STATE_INVALID")
    plan = _planner.plan_correction_pair_evidence([failed, corrected], snapshot_complete=True)
    if plan["status"] != "READY" or len(plan["pairs"]) != 1:
        raise _Refused("STATE_INVALID")
    expected = dict(plan["pairs"][0], failed_index=pair["failed_index"], corrected_index=pair["corrected_index"])
    if json.dumps(expected, sort_keys=True, ensure_ascii=True, allow_nan=False,
                  separators=(",", ":")).encode("ascii") != evidence:
        raise _Refused("STATE_INVALID")
    return pair


def read_correction_evidence_totals(repo):
    """Read a complete replayable projection input from committed ledger pairs.

    No command history is read. Each stored pair is rechecked against both bound
    event payloads and the frozen planner. Already admitted pairs remain counted
    after a later duplicate quarantine. This does not authenticate a database or
    detect an arbitrary restore of an older database and memory together.

    Existing-file mode and one SQLite transaction prevent a torn totals read.
    SQLite may perform hot-journal recovery; this is not a byte-read-only API.
    Callers serialize the subsequent memory replacement with the runtime lock.
    """
    if type(repo) not in (str, type(Path())):
        return _totals_result("INVALID_REPO")
    try:
        root = Path(repo)
        if (not root.is_absolute() or ".." in root.parts or "\x00" in str(root)
                or str(root).startswith(("//", "\\\\"))):
            return _totals_result("INVALID_REPO")
    except (ValueError, TypeError, OSError):
        return _totals_result("INVALID_REPO")
    connection = None
    rollback_attempted = False
    try:
        target = root.joinpath(*RELATIVE_PATH)
        identity = _inspect_storage(target)
        connection = _connect(target)
        _configure(connection)
        connection.execute("BEGIN IMMEDIATE")
        state = _validate_state(connection)
        grouped = {}
        # Rowid preserves admission order without changing the closed V1 schema.
        # The supported ledger API never deletes/reinserts accepted pairs.
        records = connection.execute(
            "SELECT p.failed_id, p.corrected_id, p.evidence, f.payload, c.payload, f.baseline, c.baseline "
            "FROM pairs p JOIN events f ON f.event_id = p.failed_id "
            "JOIN events c ON c.event_id = p.corrected_id ORDER BY p.rowid")
        observed = 0
        for record in records:
            pair = _validated_stored_pair(record, state["epoch"])
            failed, corrected = pair["failed_text"], pair["corrected_text"]
            intent = pair["corrected_intent"].strip().upper()
            key = " | ".join((" ".join(failed.lower().split()).strip(),
                              " ".join(corrected.lower().split()).strip(), intent))
            if key not in grouped:
                grouped[key] = {"key": key, "failed_text": failed, "corrected_text": corrected,
                                "corrected_intent": intent, "corrected_confidence": pair["corrected_confidence"],
                                "corrected_slots": dict(pair["corrected_slots"]), "count": 1}
            else:
                candidate = grouped[key]
                candidate["count"] += 1
                candidate["corrected_confidence"] = max(candidate["corrected_confidence"], pair["corrected_confidence"])
                candidate["corrected_slots"].update(pair["corrected_slots"])
            observed += 1
        if observed != state["pairs"]:
            raise _Refused("STATE_INVALID")
        if _inspect_storage(target) != identity:
            raise _Refused("PATH_CHANGED")
        rollback_attempted = True
        connection.rollback()
        return _totals_result(epoch=state["epoch"], candidates=list(grouped.values()), pair_count=observed)
    except Exception as error:
        reason = (error.reason if isinstance(error, _Refused) else
                  _storage_reason(error) if isinstance(error, sqlite3.Error) else
                  "STORAGE_ERROR" if isinstance(error, OSError) else "INTERNAL_ERROR")
        unknown = rollback_attempted
        if connection is not None:
            try:
                if connection.in_transaction:
                    connection.rollback()
            except Exception:
                unknown = True
        return _totals_result("ROLLBACK_OUTCOME_UNKNOWN" if unknown else reason)
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
