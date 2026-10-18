"""M087: persist one user-confirmed voice example in the EXISTING label inbox.

The JSONL format and intent IDs are those of tools/label_inbox.py. No training,
model loading, action dispatch, additional registry, or privileged file writes.
This module only runs after an explicit yes in ConfirmedVoiceLearning.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from modules.learning.confirmed_voice_learning import normalize_phrase, validate_intents

_MAX_OUTBOX_BYTES = 8 * 1024 * 1024
_MAX_ROW_BYTES = 4096
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)


class VoiceLearningStoreError(RuntimeError):
    pass


def _check_regular(path: Path, *, can_be_absent: bool = False) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if can_be_absent:
            return False
        raise VoiceLearningStoreError("REQUIRED_PATH_MISSING")
    if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & _REPARSE):
        raise VoiceLearningStoreError("SYMLINK_OR_REPARSE_REFUSED")
    if not stat.S_ISREG(info.st_mode):
        raise VoiceLearningStoreError("NOT_A_REGULAR_FILE")
    if info.st_nlink > 1:
        raise VoiceLearningStoreError("MULTIPLE_HARDLINKS_REFUSED")
    return True


def _check_directory(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise VoiceLearningStoreError("DATA_DIRECTORY_MISSING") from exc
    if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & _REPARSE):
        raise VoiceLearningStoreError("DATA_DIRECTORY_LINK_REFUSED")
    if not stat.S_ISDIR(info.st_mode):
        raise VoiceLearningStoreError("DATA_NOT_DIRECTORY")


class ConfirmedLearningOutbox:
    """Append approved rows to data/inbox_labeled.jsonl, retaining old JSONL.

    ``SAVED`` means a single record was appended and fsync returned success.
    ``ALREADY_RECORDED`` means a matching approved record already exists.
    ``ALREADY_IN_TRAINING`` means the exact phrase is already in intents.json.
    All three statuses do NOT imply training or model activation.
    """

    def __init__(self, *, data_dir: Path, allowed_intents: frozenset[str]) -> None:
        if not isinstance(allowed_intents, frozenset) or not allowed_intents:
            raise ValueError("ALLOWED_INTENTS_REQUIRED")
        if not all(isinstance(x, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", x) for x in allowed_intents):
            raise ValueError("INVALID_ALLOWED_INTENT")
        self._data_dir = Path(data_dir)
        self._allowed = allowed_intents

    def __call__(self, row: dict[str, Any]) -> str:
        if not isinstance(row, dict) or row.get("approved") is not True or row.get("added") is not True:
            raise VoiceLearningStoreError("ROW_NOT_CONFIRMED")
        if row.get("source") != "VOICE_LEARNING_USER_CONFIRMATION_CANDIDATE":
            raise VoiceLearningStoreError("ROW_UNEXPECTED_SOURCE")
        label = row.get("label")
        phrase = row.get("text")
        if not isinstance(label, str) or label not in self._allowed:
            raise VoiceLearningStoreError("INTENT_NOT_ALLOWED")
        if not isinstance(phrase, str) or not (5 <= len(phrase) <= 160) or not (2 <= len(phrase.split()) <= 24):
            raise VoiceLearningStoreError("PHRASE_INVALID")
        normalized = normalize_phrase(phrase)
        if phrase != normalized or not re.search(r"[а-яёa-z]", normalized) or any(ord(c) < 32 or ord(c) == 127 for c in phrase):
            raise VoiceLearningStoreError("PHRASE_UNSAFE")
        _check_directory(self._data_dir)
        intents_path = self._data_dir / "intents.json"
        outbox_path = self._data_dir / "inbox_labeled.jsonl"
        _check_regular(intents_path)
        try:
            contents = intents_path.read_bytes()
            if len(contents) > 2 * 1024 * 1024:
                raise VoiceLearningStoreError("INTENTS_TOO_LARGE")
            names, examples = validate_intents(json.loads(contents.decode("utf-8")))
        except (UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise VoiceLearningStoreError("INTENTS_INVALID") from exc
        if label not in names:
            raise VoiceLearningStoreError("INTENT_NOT_IN_DATASET")
        existing_class = examples.get(normalized)
        if existing_class is not None:
            if existing_class != label:
                raise VoiceLearningStoreError("TRAINING_CLASS_CONFLICT")
            return "ALREADY_IN_TRAINING"
        exists = _check_regular(outbox_path, can_be_absent=True)
        if exists:
            old = outbox_path.read_bytes()
            if len(old) > _MAX_OUTBOX_BYTES:
                raise VoiceLearningStoreError("OUTBOX_TOO_LARGE")
            if old and not old.endswith(b"\n"):
                raise VoiceLearningStoreError("OUTBOX_INCOMPLETE_LAST_LINE")
            try:
                decoded = old.decode("utf-8")
                for line in decoded.splitlines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if not isinstance(rec, dict):
                        raise VoiceLearningStoreError("OUTBOX_RECORD_NOT_OBJECT")
                    value = rec.get("text")
                    if isinstance(value, str) and normalize_phrase(value) == normalized and rec.get("label"):
                        if rec["label"] == label and rec.get("approved") is True:
                            return "ALREADY_RECORDED"
                        raise VoiceLearningStoreError("OUTBOX_LABEL_CONFLICT")
            except (UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise VoiceLearningStoreError("OUTBOX_INVALID") from exc
        record = {
            "text": normalized,
            "meta": {"intent": None, "confidence": None, "slots": {}, "say": ""},
            "label": label,
            "added": True,
            "approved": True,
            "source": "VOICE_LEARNING_USER_CONFIRMATION_CANDIDATE",
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
        }
        payload = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(payload) > _MAX_ROW_BYTES:
            raise VoiceLearningStoreError("RECORD_TOO_LARGE")
        # Existing-data append, not a rewrite. Do not create a second command DB.
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(outbox_path, flags, 0o600)
        try:
            f_info = os.fstat(fd)
            if not stat.S_ISREG(f_info.st_mode) or f_info.st_nlink > 1:
                raise VoiceLearningStoreError("OUTBOX_FD_NOT_REGULAR")
            if f_info.st_size > _MAX_OUTBOX_BYTES:
                raise VoiceLearningStoreError("OUTBOX_GROWN_TOO_LARGE")
            written = os.write(fd, payload)
            if written != len(payload):
                raise VoiceLearningStoreError("SHORT_APPEND_UNCERTAIN")
            os.fsync(fd)
        finally:
            os.close(fd)
        return "SAVED"
