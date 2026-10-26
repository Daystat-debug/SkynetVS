"""Read-only, aggregate-only structural audit of two learning JSONL files.

Usage: python -I -S -B tools/audit_learning_data.py [--repo TRUSTED_LOCAL_ROOT]
The default root belongs to this script, not the caller's working directory.
Stdout is one closed-schema JSON object; exit 0 means no checked structural
findings, 1 means findings, and 2 means incomplete/missing/empty inputs. Neither
0 nor valid checkpoints establish event identity, count accuracy or readiness
for training/promotion. The audit never calls application code or changes data.
File metadata checks detect ordinary concurrent changes; they are not a lock or
an atomic snapshot. Reading may update filesystem access times.
"""
from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
import stat
import sys


KIND = "SKYNETVS_LEARNING_DATA_AUDIT_V1"
LIMITS = {"bytes_per_file": 32 * 1024 * 1024, "bytes_per_line": 256 * 1024,
          "lines_per_file": 100_000, "json_nesting": 64}
INPUTS = {"command_history": ("data", "learning", "command_history.jsonl"),
          "correction_memory": ("data", "learning", "correction_memory.jsonl")}
SCOPE = {"checks": "STRUCTURE_ONLY", "files_written": False,
         "runtime_modules_imported": False, "models_loaded": False,
         "counts_recomputed": False, "historical_counts_verified": False,
         "stable_event_identity_verified": False, "cross_file_atomic_snapshot": False}
EXIT_CODES = {"NO_ISSUES_IN_CHECKED_STRUCTURE": 0, "FINDINGS_IN_CHECKED_STRUCTURE": 1,
              "INPUTS_MISSING": 2, "NO_DATA_TO_CHECK": 2, "NOT_FULLY_CHECKED": 2}
FILE_STATES = {"READ", "EMPTY", "MISSING", "UNREADABLE", "NON_REGULAR",
               "SYMLINK_REFUSED", "LIMIT_REACHED", "CHANGED_DURING_READ", "NOT_CHECKED"}
INVOCATIONS = {"OK", "INVALID_ARGUMENTS", "INVALID_REPO", "INTERNAL_ERROR"}
COMMON_FINDINGS = ("invalid_utf8_lines", "invalid_json_lines", "duplicate_field_lines",
                   "non_finite_number_lines", "non_object_rows", "invalid_unicode_lines",
                   "invalid_text_rows", "invalid_intent_rows", "invalid_confidence_rows",
                   "confidence_out_of_range_rows", "invalid_slots_rows",
                   "invalid_timestamp_rows", "mixed_timezone_files")
FINDINGS = {
    "command_history": COMMON_FINDINGS + (
        "invalid_accepted_rows", "invalid_meta_rows", "invalid_missing_slots_rows",
        "invalid_auxiliary_text_rows", "accepted_without_intent_rows",
        "out_of_order_timestamp_rows", "invalid_event_id_rows", "duplicate_event_id_rows"),
    "correction_memory": COMMON_FINDINGS + (
        "invalid_key_rows", "key_mismatch_rows", "duplicate_key_rows",
        "duplicate_normalized_key_rows", "invalid_seen_count_rows", "invalid_sources_rows",
        "duplicate_sources_rows", "invalid_checkpoint_rows", "invalid_status_rows",
        "last_seen_before_created_rows"),
}
OBSERVATIONS = {
    "command_history": ("naive_timestamp_values", "aware_timestamp_values", "accepted_rows",
                        "rejected_rows", "rows_without_event_id", "rows_with_event_id"),
    "correction_memory": ("naive_timestamp_values", "aware_timestamp_values",
                          "rows_without_checkpoint", "rows_with_checkpoint",
                          "rows_with_legacy_baseline"),
}


class _DuplicateField(ValueError):
    pass


class _NonFinite(ValueError):
    pass


class _LimitReached(ValueError):
    pass


class _UnsafePath(ValueError):
    def __init__(self, state):
        self.state = state


def _new_input(name):
    return {"state": "NOT_CHECKED", "complete": False, "unchanged_during_read": False,
            "bytes_read": 0, "lines_read": 0, "blank_lines": 0, "object_rows": 0,
            "findings": dict.fromkeys(FINDINGS[name], 0),
            "observations": dict.fromkeys(OBSERVATIONS[name], 0)}


def _new_report(invocation="OK"):
    return {"kind": KIND, "schema_version": 1, "invocation": invocation,
            "status": "NOT_FULLY_CHECKED", "exit_code": 2, "scope": dict(SCOPE),
            "limits": dict(LIMITS), "inputs": {name: _new_input(name) for name in INPUTS}}


def _status(report):
    inputs = list(report["inputs"].values())
    if report["invocation"] != "OK":
        return "NOT_FULLY_CHECKED"
    if all(item["state"] == "MISSING" for item in inputs):
        return "INPUTS_MISSING"
    if not all(item["complete"] for item in inputs):
        return "NOT_FULLY_CHECKED"
    if any(any(item["findings"].values()) for item in inputs):
        return "FINDINGS_IN_CHECKED_STRUCTURE"
    if not any(item["object_rows"] for item in inputs):
        return "NO_DATA_TO_CHECK"
    return "NO_ISSUES_IN_CHECKED_STRUCTURE"


def _finish(report):
    report["status"] = _status(report)
    report["exit_code"] = EXIT_CODES[report["status"]]
    return report


def validate_public_report(report):
    """Reject additions, dynamic values and false clean statuses before publication.

    This validates the report contract, not authenticity or the source data.
    Numeric values are scan counts only; no measured text, timestamps or hashes
    may be added to this public schema.
    """
    if type(report) is not dict or set(report) != set(_new_report()):
        return False
    if (report["kind"] != KIND or type(report["schema_version"]) is not int
            or report["schema_version"] != 1 or type(report["invocation"]) is not str
            or report["invocation"] not in INVOCATIONS or type(report["status"]) is not str
            or report["status"] not in EXIT_CODES or type(report["exit_code"]) is not int):
        return False
    for field, template in (("scope", SCOPE), ("limits", LIMITS)):
        value = report[field]
        if (type(value) is not dict or set(value) != set(template)
                or any(type(value[key]) is not type(expected) or value[key] != expected
                       for key, expected in template.items())):
            return False
    if type(report["inputs"]) is not dict or set(report["inputs"]) != set(INPUTS):
        return False
    for name, item in report["inputs"].items():
        if type(item) is not dict or set(item) != set(_new_input(name)):
            return False
        if (type(item["state"]) is not str or item["state"] not in FILE_STATES
                or type(item["complete"]) is not bool
                or type(item["unchanged_during_read"]) is not bool
                or item["complete"] != (item["state"] in ("READ", "EMPTY"))
                or (item["complete"] and not item["unchanged_during_read"])):
            return False
        for key in ("bytes_read", "lines_read", "blank_lines", "object_rows"):
            bound = LIMITS["bytes_per_file"] + 1 if key == "bytes_read" else LIMITS["lines_per_file"]
            if type(item[key]) is not int or not 0 <= item[key] <= bound:
                return False
        if item["blank_lines"] + item["object_rows"] > item["lines_read"]:
            return False
        for field, allowed in (("findings", FINDINGS[name]), ("observations", OBSERVATIONS[name])):
            if type(item[field]) is not dict or set(item[field]) != set(allowed):
                return False
            for key, count in item[field].items():
                bound = 1 if key == "mixed_timezone_files" else 2 * LIMITS["lines_per_file"]
                if type(count) is not int or not 0 <= count <= bound:
                    return False
        findings, observations = item["findings"], item["observations"]
        parse_counters = ("invalid_utf8_lines", "invalid_json_lines", "duplicate_field_lines",
                          "non_finite_number_lines", "non_object_rows")
        accounted = item["blank_lines"] + item["object_rows"] + sum(findings[key] for key in parse_counters)
        if accounted > item["lines_read"] or (item["complete"] and accounted != item["lines_read"]):
            return False
        for key, count in findings.items():
            bound = item["lines_read"] if key in parse_counters + ("invalid_unicode_lines",) else item["object_rows"]
            if key != "mixed_timezone_files" and count > bound:
                return False
        if item["state"] in ("MISSING", "NOT_CHECKED", "NON_REGULAR", "SYMLINK_REFUSED") and (
                any(item[key] for key in ("bytes_read", "lines_read", "blank_lines", "object_rows"))
                or any(findings.values()) or any(observations.values()) or item["unchanged_during_read"]):
            return False
        if (findings["mixed_timezone_files"] != int(bool(observations["naive_timestamp_values"]
                                                       and observations["aware_timestamp_values"]))
                or observations["naive_timestamp_values"] + observations["aware_timestamp_values"]
                > (1 if name == "command_history" else 2) * item["object_rows"]):
            return False
        if name == "command_history":
            if (observations["accepted_rows"] + observations["rejected_rows"]
                    + findings["invalid_accepted_rows"] != item["object_rows"]
                    or observations["rows_with_event_id"] + observations["rows_without_event_id"] != item["object_rows"]):
                return False
        elif (observations["rows_without_checkpoint"] + observations["rows_with_checkpoint"]
              + findings["invalid_checkpoint_rows"] != item["object_rows"]):
            return False
        if (item["state"] == "EMPTY" and (item["blank_lines"] != item["lines_read"]
                                         or any(item["findings"].values()))):
            return False
        if item["state"] == "READ" and item["blank_lines"] == item["lines_read"]:
            return False
    return report["status"] == _status(report) and report["exit_code"] == EXIT_CODES[report["status"]]


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateField()
        result[key] = value
    return result


def _reject_constant(value):
    raise _NonFinite()


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise _NonFinite()
    return result


def _unicode_valid(value):
    stack = [(value, 0)]
    valid = True
    while stack:
        item, depth = stack.pop()
        if depth > LIMITS["json_nesting"]:
            raise _LimitReached()
        if isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeEncodeError:
                valid = False
        elif isinstance(item, dict):
            stack.extend((child, depth + 1) for pair in item.items() for child in pair)
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return valid


def _confidence(value, findings):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except (ValueError, OverflowError):
        valid = False
    if not valid:
        findings["invalid_confidence_rows"] += 1
    elif not 0 <= value <= 1:
        findings["confidence_out_of_range_rows"] += 1


def _timestamp(value, observations):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip())
    except (ValueError, OverflowError):
        return None
    key = "naive_timestamp_values" if result.utcoffset() is None else "aware_timestamp_values"
    observations[key] += 1
    return result


def _history_row(row, item, seen, previous):
    findings, observations = item["findings"], item["observations"]
    if any(not isinstance(row.get(key), str) for key in ("raw_text", "final_text")):
        findings["invalid_text_rows"] += 1
    accepted = row.get("accepted")
    if type(accepted) is not bool:
        findings["invalid_accepted_rows"] += 1
    else:
        observations["accepted_rows" if accepted else "rejected_rows"] += 1
    missing = row.get("missing_slots", [])
    if not isinstance(missing, list) or any(not isinstance(value, str) for value in missing):
        findings["invalid_missing_slots_rows"] += 1
    meta = row.get("meta")
    auxiliary_invalid = any(key in row and not isinstance(row[key], str)
                            for key in ("mode", "immediate_label"))
    if not isinstance(meta, dict):
        findings["invalid_meta_rows"] += 1
    else:
        intent = meta.get("intent")
        if intent is not None and not isinstance(intent, str):
            findings["invalid_intent_rows"] += 1
        if accepted is True and (not isinstance(intent, str) or not intent.strip()):
            findings["accepted_without_intent_rows"] += 1
        _confidence(meta.get("confidence"), findings)
        if not isinstance(meta.get("slots"), dict):
            findings["invalid_slots_rows"] += 1
        auxiliary_invalid |= any(key in meta and not isinstance(meta[key], str)
                                 for key in ("say", "_text"))
    findings["invalid_auxiliary_text_rows"] += int(auxiliary_invalid)
    timestamp = _timestamp(row.get("ts"), observations)
    if timestamp is None:
        findings["invalid_timestamp_rows"] += 1
    else:
        group = timestamp.utcoffset() is not None
        if group in previous and timestamp < previous[group]:
            findings["out_of_order_timestamp_rows"] += 1
        previous[group] = timestamp
    event_id = row.get("event_id")
    if isinstance(event_id, str) and event_id.strip():
        observations["rows_with_event_id"] += 1
        findings["duplicate_event_id_rows"] += int(event_id in seen)
        seen.add(event_id)
    else:
        observations["rows_without_event_id"] += 1
        findings["invalid_event_id_rows"] += int("event_id" in row)


def _memory_row(row, item, seen, normalized):
    findings, observations = item["findings"], item["observations"]
    key = row.get("key")
    if not isinstance(key, str) or not key.strip():
        findings["invalid_key_rows"] += 1
    else:
        findings["duplicate_key_rows"] += int(key in seen)
        seen.add(key)
    texts_ok = all(isinstance(row.get(name), str) and row[name].strip()
                   for name in ("failed_text", "corrected_text"))
    intent = row.get("corrected_intent")
    intent_ok = isinstance(intent, str) and bool(intent.strip())
    findings["invalid_text_rows"] += int(not texts_ok)
    findings["invalid_intent_rows"] += int(not intent_ok)
    if texts_ok and intent_ok:
        canonical = " | ".join((" ".join(row["failed_text"].lower().split()),
                                " ".join(row["corrected_text"].lower().split()), intent.strip().upper()))
        findings["key_mismatch_rows"] += int(key != canonical)
        findings["duplicate_normalized_key_rows"] += int(canonical in normalized)
        normalized.add(canonical)
    count = row.get("seen_count", 0)
    findings["invalid_seen_count_rows"] += int(type(count) is not int or count < 0)
    _confidence(row.get("corrected_confidence", 0.0), findings)
    slots = row.get("corrected_slots")
    findings["invalid_slots_rows"] += int(slots is not None and not isinstance(slots, dict))
    sources = row.get("sources")
    if sources is not None:
        if not isinstance(sources, list) or any(not isinstance(value, str) for value in sources):
            findings["invalid_sources_rows"] += 1
        else:
            findings["duplicate_sources_rows"] += int(len(sources) != len(set(sources)))
    if "status" in row and (not isinstance(row["status"], str) or not row["status"].strip()):
        findings["invalid_status_rows"] += 1
    states = row.get("cumulative_evidence", {})
    if not isinstance(states, dict):
        findings["invalid_checkpoint_rows"] += 1
    elif not states:
        observations["rows_without_checkpoint"] += 1
    else:
        valid, legacy = True, False
        for source, state in states.items():
            state_valid = (isinstance(source, str) and bool(source.strip()) and isinstance(state, dict)
                           and type(state.get("version")) is int and state["version"] == 1
                           and type(state.get("observed_count")) is int and state["observed_count"] >= 0
                           and type(state.get("legacy_baseline")) is bool)
            valid &= state_valid
            legacy |= bool(state_valid and state["legacy_baseline"])
        findings["invalid_checkpoint_rows"] += int(not valid)
        observations["rows_with_checkpoint"] += int(valid)
        observations["rows_with_legacy_baseline"] += int(legacy)
    created = _timestamp(row.get("created_ts"), observations)
    last_seen = _timestamp(row.get("last_seen_ts"), observations)
    if created is None or last_seen is None:
        findings["invalid_timestamp_rows"] += 1
    elif (created.utcoffset() is None) == (last_seen.utcoffset() is None) and last_seen < created:
        findings["last_seen_before_created_rows"] += 1


def _signature(info, *, directory=False):
    identity = (info.st_dev, info.st_ino, info.st_mode)
    return identity if directory else identity + (info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _inspect(path):
    """Inspect each component without following symlinks/reparse points."""
    chain = []
    current = Path(path.anchor)
    parts = path.parts[1:]
    for index, part in enumerate(parts):
        current /= part
        info = current.lstat()
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise _UnsafePath("SYMLINK_REFUSED")
        directory = index < len(parts) - 1
        if (directory and not stat.S_ISDIR(info.st_mode)) or (not directory and not stat.S_ISREG(info.st_mode)):
            raise _UnsafePath("NON_REGULAR")
        chain.append(_signature(info, directory=directory))
    return tuple(chain), info


def _read_input(root, name, item):
    target = root.joinpath(*INPUTS[name])
    descriptor = None
    observed = None
    try:
        before, initial = _inspect(target)
        if initial.st_size > LIMITS["bytes_per_file"]:
            item["state"] = "LIMIT_REACHED"
            return
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(target, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _signature(opened) != _signature(initial) or _inspect(target)[0] != before:
            item["state"] = "CHANGED_DURING_READ"
            return
        observed = before
        seen, related = set(), {} if name == "command_history" else set()
        state = "READ"
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            while True:
                maximum = min(LIMITS["bytes_per_line"] + 1, LIMITS["bytes_per_file"] - item["bytes_read"] + 1)
                raw = stream.readline(maximum)
                if not raw:
                    break
                item["bytes_read"] += len(raw)
                if (len(raw) > LIMITS["bytes_per_line"] or item["bytes_read"] > LIMITS["bytes_per_file"]
                        or item["lines_read"] >= LIMITS["lines_per_file"]):
                    state = "LIMIT_REACHED"
                    break
                item["lines_read"] += 1
                findings = item["findings"]
                try:
                    line = raw.decode("utf-8")
                except UnicodeDecodeError:
                    findings["invalid_utf8_lines"] += 1
                    continue
                if not line.strip():
                    item["blank_lines"] += 1
                    continue
                try:
                    row = json.loads(line, object_pairs_hook=_strict_object,
                                     parse_constant=_reject_constant, parse_float=_finite_float)
                    unicode_valid = _unicode_valid(row)
                except _DuplicateField:
                    findings["duplicate_field_lines"] += 1
                    continue
                except _NonFinite:
                    findings["non_finite_number_lines"] += 1
                    continue
                except (RecursionError, _LimitReached):
                    state = "LIMIT_REACHED"
                    break
                except (ValueError, TypeError, OverflowError):
                    findings["invalid_json_lines"] += 1
                    continue
                findings["invalid_unicode_lines"] += int(not unicode_valid)
                if not isinstance(row, dict):
                    findings["non_object_rows"] += 1
                    continue
                item["object_rows"] += 1
                if name == "command_history":
                    _history_row(row, item, seen, related)
                else:
                    _memory_row(row, item, seen, related)
            stable = _signature(os.fstat(stream.fileno())) == _signature(initial) and _inspect(target)[0] == before
        item["unchanged_during_read"] = stable
        if not stable:
            state = "CHANGED_DURING_READ"
        elif state == "READ" and item["blank_lines"] == item["lines_read"]:
            state = "EMPTY"
        item["state"] = state
        item["complete"] = state in ("READ", "EMPTY")
    except FileNotFoundError:
        item["state"] = "CHANGED_DURING_READ" if observed is not None else "MISSING"
    except _UnsafePath as exc:
        item["state"] = exc.state
    except OSError:
        item["state"] = "UNREADABLE"
    finally:
        if descriptor is not None:
            os.close(descriptor)
        observations = item["observations"]
        item["findings"]["mixed_timezone_files"] = int(
            bool(observations["naive_timestamp_values"] and observations["aware_timestamp_values"]))
    return observed


def audit_learning_data(repo=None):
    """Return only sanitized aggregate data; no application imports or writes."""
    report = _new_report()
    try:
        root = Path(os.path.abspath(repo if repo is not None else Path(__file__).parent.parent))
    except (TypeError, ValueError):
        return _finish(_new_report("INVALID_REPO"))
    try:
        if (os.name == "nt" and root.drive.startswith("\\\\")) or not root.is_dir():
            report["invocation"] = "INVALID_REPO"
        else:
            snapshots = {}
            for name, item in report["inputs"].items():
                snapshots[name] = _read_input(root, name, item)
            # A first input can change while the second input is being scanned.
            for name, snapshot in snapshots.items():
                if snapshot is None:
                    continue
                try:
                    changed = _inspect(root.joinpath(*INPUTS[name]))[0] != snapshot
                except (OSError, _UnsafePath):
                    changed = True
                if changed:
                    item = report["inputs"][name]
                    item.update(state="CHANGED_DURING_READ", complete=False, unchanged_during_read=False)
    except Exception:
        # Diagnostic callers must not publish exception text or private paths.
        return _finish(_new_report("INTERNAL_ERROR"))
    return _finish(report)


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        report = audit_learning_data()
    elif len(arguments) == 2 and arguments[0] == "--repo" and arguments[1]:
        report = audit_learning_data(arguments[1])
    else:
        report = _finish(_new_report("INVALID_ARGUMENTS"))
    if not validate_public_report(report):
        report = _finish(_new_report("INTERNAL_ERROR"))
    try:
        sys.stdout.write(json.dumps(report, ensure_ascii=True, allow_nan=False, sort_keys=True) + "\n")
    except BrokenPipeError:
        return 2
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
