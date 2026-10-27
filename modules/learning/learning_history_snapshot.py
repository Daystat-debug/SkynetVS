"""Bounded, read-only command-history snapshots for private pair planning.

One LF-terminated physical line produces one dict-or-None position. Successfully
decoded dictionaries retain every field, including schema-invalid values and
surrogate escapes, so the downstream planner can still see their event IDs.
COMPLETE means bounded EOF plus unchanged observed metadata, not a clean log,
an atomic filesystem snapshot, authenticated events, or readiness for training.
This module has no CLI and is not connected to the runtime or memory builder.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import stat


KIND = "SKYNETVS_LEARNING_HISTORY_SNAPSHOT_V1"
INPUT = ("data", "learning", "command_history.jsonl")
LIMITS = {
    "bytes_per_file": 32 * 1024 * 1024,
    "bytes_per_line": 256 * 1024,
    "physical_lines": 100_000,
    "json_container_depth": 64,
    "lexical_units_per_line": 100_000,
    "lexical_units_total": 2_000_000,
    "integer_decimal_digits": 4096,
}
REASONS = frozenset(("INVALID_REPO", "MISSING", "UNREADABLE", "NON_REGULAR",
                     "SYMLINK_REFUSED", "RESOURCE_LIMIT", "UNTERMINATED_FINAL_LINE",
                     "CHANGED_DURING_READ", "INTERNAL_ERROR"))
SCOPE = {
    "input": "FIXED_COMMAND_HISTORY_FILE",
    "output": "PRIVATE_ORDERED_ROWS",
    "positions": "ONE_PER_LF_TERMINATED_PHYSICAL_LINE",
    "completeness": "BOUNDED_EOF_AND_OBSERVED_METADATA",
    "atomic_snapshot": False,
    "file_writes": False,
    "event_identity_authenticated": False,
    "undecodable_event_ids_recovered": False,
    "runtime_integration": False,
    "training_readiness": "NOT_ASSESSED",
}


class _ResourceLimit(ValueError):
    pass


class _DuplicateField(ValueError):
    pass


class _NonFinite(ValueError):
    pass


class _Refused(ValueError):
    def __init__(self, reason):
        self.reason = reason


def _result(reason=None, rows=None, observations=None):
    return {"kind": KIND, "status": "REFUSED" if reason else "COMPLETE",
            "reason": reason, "snapshot_complete": reason is None,
            "metadata_unchanged": reason is None,
            "rows": [] if reason else rows,
            "observations": None if reason else observations,
            "scope": dict(SCOPE), "limits": dict(LIMITS)}


def _signature(info, *, directory=False):
    identity = (info.st_dev, info.st_ino, info.st_mode)
    return identity if directory else identity + (info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _file_version(info):
    # Windows CPython 3.12 path stat and fstat disagree on ctime semantics and
    # can expose different permission bits. Compare only compatible fields
    # across APIs; full signatures still protect successive same-API checks.
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), info.st_size, info.st_mtime_ns)


def _inspect(path):
    chain = []
    current = Path(path.anchor)
    for index, part in enumerate(path.parts[1:]):
        current /= part
        info = current.lstat()
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise _Refused("SYMLINK_REFUSED")
        directory = index < len(path.parts) - 2
        if (directory and not stat.S_ISDIR(info.st_mode)) or (not directory and not stat.S_ISREG(info.st_mode)):
            raise _Refused("NON_REGULAR")
        chain.append(_signature(info, directory=directory))
    return tuple(chain), info


def _lexical_budget(line, observations):
    """Count conservative lexical units before JSON allocation, even on bad JSON.

    One unit is an opening container, an opening quoted string (including keys),
    or the start of a non-whitespace/non-structural run outside strings. Closing
    containers clamp depth at zero; the JSON parser separately validates syntax.
    These units bound work/retained structures, not actual decoded nodes or RAM.
    """
    depth = units = 0
    in_string = escaped = primitive = False
    for character in line:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        charge = False
        if character == '"':
            in_string = True
            primitive = False
            charge = True
        elif character in "[{":
            depth += 1
            if depth > LIMITS["json_container_depth"]:
                raise _ResourceLimit()
            primitive = False
            charge = True
        elif character in "]}":
            depth = max(0, depth - 1)
            primitive = False
        elif character in " \t\r\n,:":
            primitive = False
        elif not primitive:
            primitive = True
            charge = True
        if charge:
            units += 1
            observations["lexical_units"] += 1
            if (units > LIMITS["lexical_units_per_line"]
                    or observations["lexical_units"] > LIMITS["lexical_units_total"]):
                raise _ResourceLimit()


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateField()
        result[key] = value
    return result


def _bounded_int(value):
    negative = value.startswith("-")
    digits = value[1:] if negative else value
    if len(digits) > LIMITS["integer_decimal_digits"]:
        raise _ResourceLimit()
    # Small chunks avoid depending on the process-wide int-string digit limit.
    result = 0
    for start in range(0, len(digits), 9):
        chunk = digits[start:start + 9]
        result = result * 10 ** len(chunk) + int(chunk)
    return -result if negative else result


def _reject_constant(_value):
    raise _NonFinite()


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise _NonFinite()
    return result


def _decode_line(raw, observations):
    try:
        line = raw.decode("utf-8")
    except UnicodeDecodeError:
        observations["invalid_utf8_lines"] += 1
        return None
    if not line.strip(" \t\r\n"):
        observations["blank_lines"] += 1
        return None
    _lexical_budget(line, observations)
    try:
        row = json.loads(line, object_pairs_hook=_strict_object,
                         parse_constant=_reject_constant, parse_float=_finite_float,
                         parse_int=_bounded_int)
    except _ResourceLimit:
        raise
    except _DuplicateField:
        observations["duplicate_field_lines"] += 1
    except _NonFinite:
        observations["non_finite_number_lines"] += 1
    except RecursionError:
        raise _ResourceLimit() from None
    except (ValueError, TypeError, OverflowError):
        observations["invalid_json_lines"] += 1
    else:
        if type(row) is dict:
            observations["decoded_objects"] += 1
            return row
        observations["non_object_lines"] += 1
    return None


def _read_rows(stream, observed_size):
    rows = []
    observations = dict.fromkeys(("bytes_read", "physical_lines", "decoded_objects", "barrier_lines",
                                 "blank_lines", "invalid_utf8_lines", "invalid_json_lines",
                                 "duplicate_field_lines", "non_finite_number_lines", "non_object_lines",
                                 "lexical_units"), 0)
    while True:
        maximum = min(LIMITS["bytes_per_line"] + 1,
                      LIMITS["bytes_per_file"] - observations["bytes_read"] + 1)
        if observations["physical_lines"] >= LIMITS["physical_lines"]:
            maximum = 1
        raw = stream.readline(maximum)
        if not raw:
            break
        observations["bytes_read"] += len(raw)
        if (len(raw) > LIMITS["bytes_per_line"]
                or observations["bytes_read"] > LIMITS["bytes_per_file"]
                or observations["physical_lines"] >= LIMITS["physical_lines"]):
            raise _ResourceLimit()
        if not raw.endswith(b"\n"):
            raise _Refused("UNTERMINATED_FINAL_LINE")
        observations["physical_lines"] += 1
        row = _decode_line(raw, observations)
        observations["barrier_lines"] += int(row is None)
        rows.append(row)
    if observations["bytes_read"] != observed_size:
        raise _Refused("CHANGED_DURING_READ")
    return rows, observations


def read_learning_history_snapshot(repo):
    """Read one explicit local repository's fixed history without writes/imports.

    Refusal always clears rows and observations. A nonempty final fragment
    without LF is incomplete even when it happens to be valid JSON. Blank and
    malformed complete lines remain None barriers; strict-decoded dictionaries
    are never schema-filtered. IDs hidden in failed parses cannot be recovered.
    File checks detect ordinary changes, not adversarial metadata restoration or
    every race. Filesystem access times may change due to ordinary reads.
    """
    if type(repo) not in (str, type(Path())):
        return _result("INVALID_REPO")
    try:
        root = Path(repo)
        if (not root.is_absolute() or ".." in root.parts or "\x00" in str(root)
                or str(root).startswith(("//", "\\\\"))):
            return _result("INVALID_REPO")
    except (TypeError, ValueError, OSError):
        return _result("INVALID_REPO")
    target = root.joinpath(*INPUT)
    descriptor = None
    opened_once = False
    try:
        before, initial = _inspect(target)
        if initial.st_size > LIMITS["bytes_per_file"]:
            raise _ResourceLimit()
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(target, flags)
        opened_once = True
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode) or _file_version(opened) != _file_version(initial)
                or _inspect(target)[0] != before):
            raise _Refused("CHANGED_DURING_READ")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            rows, observations = _read_rows(stream, opened.st_size)
            if (_signature(os.fstat(stream.fileno())) != _signature(opened)
                    or _inspect(target)[0] != before):
                raise _Refused("CHANGED_DURING_READ")
        return _result(rows=rows, observations=observations)
    except _ResourceLimit:
        return _result("RESOURCE_LIMIT")
    except _Refused as exc:
        reason = exc.reason
        if opened_once and reason in ("SYMLINK_REFUSED", "NON_REGULAR"):
            reason = "CHANGED_DURING_READ"
        return _result(reason)
    except FileNotFoundError:
        return _result("CHANGED_DURING_READ" if opened_once else "MISSING")
    except OSError:
        return _result("UNREADABLE")
    except Exception:
        return _result("INTERNAL_ERROR")
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
