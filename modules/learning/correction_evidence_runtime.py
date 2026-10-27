"""Opt-in coordination for correction evidence, using one persistent switch.

Only an explicit activation creates PREPARING then ACTIVE. Any control file or
orphan ledger disables the legacy builder; damaged state never enables fallback.
The advisory lock covers cooperating activation, builder and command writers.
It is released by the OS when its descriptor/process closes and is never deleted.
It does not serialize older processes or arbitrary external edits.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import re
import stat
import tempfile


KIND = "SKYNETVS_CORRECTION_EVIDENCE_RUNTIME_RESULT_V1"
CONTROL_KIND = "SKYNETVS_CORRECTION_EVIDENCE_RUNTIME_CONTROL_V1"
CONTROL_NAME = "correction_evidence_runtime.json"
LOCK_NAME = "correction_evidence_runtime.lock"
LEDGER_NAME = "correction_evidence.sqlite3"
CONTROL_MAX_BYTES = 4096


class RuntimeRefused(ValueError):
    """Fixed reason codes, without private payloads, paths or raw exceptions."""

    def __init__(self, reason, detail_reason=None):
        self.reason = reason
        self.detail_reason = detail_reason
        super().__init__(reason)


def _local_path(value):
    if type(value) not in (str, type(Path())):
        raise RuntimeRefused("INVALID_PATH")
    try:
        path = Path(value)
        if ".." in path.parts or "\x00" in str(path) or str(path).startswith(("//", "\\\\")):
            raise RuntimeRefused("INVALID_PATH")
        return Path(os.path.abspath(path))
    except (TypeError, OSError, ValueError):
        raise RuntimeRefused("INVALID_PATH") from None


def _safe(info, *, directory=False):
    if (stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or (not stat.S_ISDIR(info.st_mode) if directory else
                not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
        raise RuntimeRefused("UNSAFE_PATH")


def _identity(info):
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def _directory(base, *, create=False):
    path = _local_path(base)
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if not create:
                raise RuntimeRefused("DIRECTORY_MISSING") from None
            try:
                current.mkdir()
            except FileExistsError:
                pass
            info = current.lstat()
        _safe(info, directory=True)
    return path


@contextmanager
def learning_evidence_lock(base_dir):
    """Acquire a nonblocking local advisory lock, without stale-file removal.

    The file intentionally survives release. BUSY is a refusal, not permission
    to continue without serialization. Creation of this one-byte file is a
    disclosed runtime side effect even while legacy counting is still selected.
    """
    descriptor = None
    try:
        base = _directory(base_dir, create=True)
        target = base / LOCK_NAME
        try:
            _safe(target.lstat())
        except FileNotFoundError:
            pass
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o600)
        info = os.fstat(descriptor)
        _safe(info)
        if info.st_size not in (0, 1):
            raise RuntimeRefused("LOCK_INVALID")
        if info.st_size == 0:
            os.write(descriptor, b"\x00")
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise RuntimeRefused("BUSY") from None
            raise
        _safe(target.lstat())
        if _identity(target.lstat()) != _identity(info):
            raise RuntimeRefused("LOCK_CHANGED")
        yield base
    except RuntimeRefused:
        raise
    except OSError:
        raise RuntimeRefused("STORAGE_ERROR") from None
    finally:
        if descriptor is not None:
            # Closing the handle releases its OS lock, including after a crash.
            os.close(descriptor)


def _present(path):
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def _strict_object(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("duplicate field")
        value[name] = item
    return value


def _reject_constant(_value):
    raise ValueError("invalid constant")


def _control_bytes(base):
    target = base / CONTROL_NAME
    try:
        before = target.lstat()
    except FileNotFoundError:
        return None
    _safe(before)
    if not 0 < before.st_size <= CONTROL_MAX_BYTES:
        raise RuntimeRefused("CONTROL_INVALID")
    with target.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        _safe(opened)
        raw = stream.read(CONTROL_MAX_BYTES + 1)
        after_open = os.fstat(stream.fileno())
    after = target.lstat()
    _safe(after)
    if (_identity(before) != _identity(opened) or _identity(before) != _identity(after)
            or (opened.st_size, opened.st_mtime_ns) != (after_open.st_size, after_open.st_mtime_ns)
            or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
            or len(raw) != before.st_size or len(raw) > CONTROL_MAX_BYTES):
        raise RuntimeRefused("CONTROL_CHANGED")
    return raw


def read_learning_evidence_control(base_dir):
    """Read the fixed control under the caller's learning_evidence_lock.

    The lock file is not an activation marker. An absent control is legacy only
    when no ledger or SQLite sidecar exists. ACTIVE does not read the database
    on every command: its epoch labels new observations while the builder must
    independently validate the ledger. PREPARING may log unstamped observations.
    """
    try:
        base = _directory(base_dir)
        raw = _control_bytes(base)
        if raw is None:
            if any(_present(base / (LEDGER_NAME + suffix)) for suffix in ("", "-journal", "-wal", "-shm")):
                raise RuntimeRefused("ORPHAN_LEDGER")
            return {"state": "LEGACY", "epoch": None}
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object, parse_constant=_reject_constant)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise RuntimeRefused("CONTROL_INVALID") from None
        if (type(value) is not dict or set(value) != {"kind", "version", "state", "epoch"}
                or value["kind"] != CONTROL_KIND or type(value["version"]) is not int or value["version"] != 1
                or value["state"] not in ("PREPARING", "ACTIVE")):
            raise RuntimeRefused("CONTROL_INVALID")
        epoch = value["epoch"]
        if ((value["state"] == "PREPARING" and epoch is not None)
                or (value["state"] == "ACTIVE" and
                    (type(epoch) is not str or re.fullmatch(r"[0-9a-f]{32}", epoch) is None))):
            raise RuntimeRefused("CONTROL_INVALID")
        return {"state": value["state"], "epoch": epoch}
    except RuntimeRefused:
        raise
    except OSError:
        raise RuntimeRefused("STORAGE_ERROR") from None


def _encoded_control(state, epoch):
    return (json.dumps({"kind": CONTROL_KIND, "version": 1, "state": state, "epoch": epoch},
                       sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _create_preparing(base):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(base / CONTROL_NAME, flags, 0o600)
    # A failed/partial creation remains visible and prevents legacy fallback.
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(_encoded_control("PREPARING", None))
        stream.flush()
        os.fsync(stream.fileno())


def _activate_control(base, epoch):
    before = _control_bytes(base)
    if read_learning_evidence_control(base)["state"] != "PREPARING":
        raise RuntimeRefused("CONTROL_CHANGED")
    descriptor, name = tempfile.mkstemp(prefix="." + CONTROL_NAME + ".", suffix=".tmp", dir=base)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_encoded_control("ACTIVE", epoch))
            stream.flush()
            os.fsync(stream.fileno())
        if _control_bytes(base) != before:
            raise RuntimeRefused("CONTROL_CHANGED")
        os.replace(temporary, base / CONTROL_NAME)
    finally:
        if temporary.exists():
            temporary.unlink()


def _result(operation, status="REFUSED", *, mode=None, reason=None, detail_reason=None, stats=None):
    return {"kind": KIND, "operation": operation, "status": status, "mode": mode,
            "reason": reason, "detail_reason": detail_reason, "stats": stats,
            "scope": {"runtime_opt_in": True, "private_data": True,
                      "training_run": False, "training_readiness": "NOT_ASSESSED",
                      "ledger_and_memory_single_transaction": False}}


def _repo_learning(repo):
    root = _local_path(repo)
    if not Path(repo).is_absolute():
        raise RuntimeRefused("INVALID_REPO")
    return root, root / "data" / "learning"


def _legacy_memory(base):
    from modules.learning.correction_memory import CorrectionMemory
    memory = CorrectionMemory(str(base / "correction_memory.jsonl"))
    # A deleted control/database must not reactivate aggregate counting after
    # event projection left its checkpoint in an otherwise valid memory file.
    if any("event_evidence" in row for row in memory._read_snapshot_rows()):
        raise RuntimeRefused("MISSING_CONTROL_STATE")
    return memory


def activate_learning_evidence(repo):
    """Explicitly freeze legacy accrual, initialize a baseline, then activate.

    Existing history and correction-memory bytes are preserved. Retry resumes a
    valid PREPARING record with an absent or valid zero-pair ledger. Invalid or
    ambiguous state is retained for review, never automatically rebuilt/reset.
    Stop older application/builder processes before the first activation.
    """
    try:
        from modules.learning.correction_evidence_ledger import (
            initialize_correction_evidence_ledger, read_correction_evidence_totals)
        root, learning = _repo_learning(repo)
        with learning_evidence_lock(learning) as base:
            control = read_learning_evidence_control(base)
            if control["state"] == "LEGACY":
                _legacy_memory(base)
                _create_preparing(base)
            elif control["state"] == "PREPARING":
                _legacy_memory(base)
            if control["state"] == "ACTIVE":
                totals = read_correction_evidence_totals(root)
                if totals["status"] != "READY":
                    raise RuntimeRefused("LEDGER_READ_REFUSED", totals["reason"])
                if totals["epoch"] != control["epoch"]:
                    raise RuntimeRefused("EPOCH_MISMATCH")
                return _result("ACTIVATE", "UNCHANGED", mode="EVENT")
            if not _present(base / LEDGER_NAME):
                initialized = initialize_correction_evidence_ledger(root)
                if initialized["status"] != "INITIALIZED":
                    raise RuntimeRefused("LEDGER_INITIALIZATION_REFUSED", initialized["reason"])
            totals = read_correction_evidence_totals(root)
            if totals["status"] != "READY":
                raise RuntimeRefused("LEDGER_READ_REFUSED", totals["reason"])
            if totals["pair_count"] != 0:
                raise RuntimeRefused("AMBIGUOUS_PREPARING_LEDGER")
            _activate_control(base, totals["epoch"])
            return _result("ACTIVATE", "ACTIVATED", mode="EVENT")
    except RuntimeRefused as error:
        return _result("ACTIVATE", reason=error.reason, detail_reason=error.detail_reason)
    except OSError:
        return _result("ACTIVATE", reason="STORAGE_ERROR")
    except (ValueError, TypeError):
        return _result("ACTIVATE", reason="INPUT_INVALID")
    except Exception:
        return _result("ACTIVATE", reason="INTERNAL_ERROR")


def build_learning_corrections(repo):
    """Route before analyzer reads; active mode replays full durable totals."""
    try:
        root, learning = _repo_learning(repo)
        with learning_evidence_lock(learning) as base:
            control = read_learning_evidence_control(base)
            if control["state"] == "PREPARING":
                raise RuntimeRefused("ACTIVATION_PENDING")
            if control["state"] == "LEGACY":
                from modules.learning.feedback_analyzer import FeedbackAnalyzer
                memory = _legacy_memory(base)
                report = FeedbackAnalyzer(str(base)).analyze(correction_limit=None)
                stats = memory.sync_cumulative_candidates(
                    report.get("correction_pairs") or [], source="feedback_analyzer_v2")
                return _result("BUILD", "LEGACY", mode="LEGACY", stats=stats)
            from modules.learning.correction_evidence_ledger import (
                read_correction_evidence_totals, sync_correction_evidence_ledger)
            from modules.learning.correction_evidence_projection import project_correction_evidence
            before_sync = read_correction_evidence_totals(root)
            if before_sync["status"] != "READY":
                raise RuntimeRefused("LEDGER_READ_REFUSED", before_sync["reason"])
            if before_sync["epoch"] != control["epoch"]:
                raise RuntimeRefused("EPOCH_MISMATCH")
            synced = sync_correction_evidence_ledger(root)
            if synced["status"] not in ("APPLIED", "UNCHANGED"):
                raise RuntimeRefused("LEDGER_SYNC_REFUSED", synced["reason"])
            if synced["epoch"] != control["epoch"]:
                raise RuntimeRefused("EPOCH_MISMATCH")
            projected = project_correction_evidence(root, expected_epoch=control["epoch"])
            if projected["status"] not in ("APPLIED", "UNCHANGED"):
                raise RuntimeRefused("PROJECTION_REFUSED", projected["reason"])
            return _result("BUILD", projected["status"], mode="EVENT", stats=projected["stats"])
    except RuntimeRefused as error:
        return _result("BUILD", reason=error.reason, detail_reason=error.detail_reason)
    except OSError:
        return _result("BUILD", reason="STORAGE_ERROR")
    except (ValueError, TypeError):
        return _result("BUILD", reason="INPUT_INVALID")
    except Exception:
        return _result("BUILD", reason="INTERNAL_ERROR")
