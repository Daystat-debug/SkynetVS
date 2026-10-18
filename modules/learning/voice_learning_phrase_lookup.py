"""M088: safe exact recall of user-confirmed GREET phrases from existing label inbox.

No new command registry and NO model training. Only explicitly approved, user-local
VOICE_LEARNING_USER_CONFIRMATION_CANDIDATE records can match. The sole allowed
intent in this initial integration is GREET. All ordinary NLU rules run first.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
from typing import Any

_ALLOWED = frozenset({'GREET'})
_SOURCE = 'VOICE_LEARNING_USER_CONFIRMATION_CANDIDATE'
_MAX_BYTES = 8 * 1024 * 1024
_REPARSE = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)


class VoicePhraseLookupError(ValueError):
    pass


def normalize(text: str) -> str:
    return ' '.join(text.casefold().split()) if isinstance(text, str) else ''


def _regular(path: Path, *, missing_ok: bool = False) -> bool:
    try:
        s = os.lstat(path)
    except FileNotFoundError:
        if missing_ok:
            return False
        raise VoicePhraseLookupError('REQUIRED_FILE_MISSING')
    if not stat.S_ISREG(s.st_mode) or stat.S_ISLNK(s.st_mode) or bool(getattr(s,'st_file_attributes',0) & _REPARSE):
        raise VoicePhraseLookupError('NOT_REGULAR_FILE_OR_REPARSE')
    if s.st_nlink > 1:
        raise VoicePhraseLookupError('MULTIPLE_HARDLINKS_REFUSED')
    return True


def _directory(path: Path) -> None:
    s = os.lstat(path)
    if not stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode) or bool(getattr(s,'st_file_attributes',0) & _REPARSE):
        raise VoicePhraseLookupError('DIRECTORY_REPARSE_REFUSED')


def load_approved_greetings(data_dir: Path) -> set[str]:
    """Validate complete JSONL and return only approved exact GREET phrases.

    A damaged or conflicting queue raises instead of serving partially trusted data.
    Does not modify the queue, the NLU model, or any other file.
    """
    data_dir = Path(data_dir)
    _directory(data_dir)
    training = data_dir / 'intents.json'
    outbox = data_dir / 'inbox_labeled.jsonl'
    _regular(training)
    if not _regular(outbox, missing_ok=True):
        return set()
    if training.stat().st_size > 2 * 1024 * 1024:
        raise VoicePhraseLookupError('DATASET_TOO_LARGE')
    try:
        ds = json.loads(training.read_text('utf-8'))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise VoicePhraseLookupError('DATASET_INVALID') from exc
    if not isinstance(ds,dict) or not isinstance(ds.get('intents'), list):
        raise VoicePhraseLookupError('DATASET_SCHEMA_INVALID')
    fixed: dict[str,str] = {}
    class_names: set[str] = set()
    for row in ds['intents']:
        if not isinstance(row,dict) or not isinstance(row.get('intent'),str) or not isinstance(row.get('examples'),list):
            raise VoicePhraseLookupError('DATASET_ROW_INVALID')
        label = row['intent']
        if label in class_names:
            raise VoicePhraseLookupError('DATASET_DUPLICATE_INTENT')
        class_names.add(label)
        for ex in row['examples']:
            if not isinstance(ex,str):
                raise VoicePhraseLookupError('DATASET_EXAMPLE_NOT_TEXT')
            phrase = normalize(ex)
            if phrase in fixed and fixed[phrase] != label:
                raise VoicePhraseLookupError('DATASET_EXAMPLE_COLLISION')
            fixed[phrase] = label
    if not _ALLOWED.issubset(class_names):
        raise VoicePhraseLookupError('APPROVED_INTENT_NOT_IN_DATASET')
    if outbox.stat().st_size > _MAX_BYTES:
        raise VoicePhraseLookupError('QUEUE_TOO_LARGE')
    fd = os.open(outbox, os.O_RDONLY | getattr(os,'O_BINARY',0) | getattr(os,'O_NOFOLLOW',0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1 or info.st_size > _MAX_BYTES:
            raise VoicePhraseLookupError('QUEUE_FD_INVALID')
        # Bound reads and refuse a concurrent append: the next lookup can retry.
        chunks = []
        count = 0
        while True:
            block = os.read(fd, min(65536, _MAX_BYTES+1-count))
            if not block:
                break
            count += len(block)
            if count > _MAX_BYTES:
                raise VoicePhraseLookupError('QUEUE_OVERFLOW')
            chunks.append(block)
        if os.fstat(fd).st_size != count:
            raise VoicePhraseLookupError('QUEUE_MODIFIED_WHILE_READING')
        raw = b''.join(chunks)
    finally:
        os.close(fd)
    if raw and not raw.endswith(b'\n'):
        raise VoicePhraseLookupError('QUEUE_INCOMPLETE_LINE')
    try:
        text = raw.decode('utf-8')
    except UnicodeError as exc:
        raise VoicePhraseLookupError('QUEUE_NOT_UTF8') from exc
    confirmed: set[str] = set()
    every_labeled: dict[str,str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if len(line.encode('utf-8')) > 131072:
            raise VoicePhraseLookupError('QUEUE_ROW_TOO_LARGE')
        try:
            row: Any = json.loads(line)
        except (ValueError, TypeError) as exc:
            raise VoicePhraseLookupError('QUEUE_INVALID_JSON') from exc
        if not isinstance(row, dict):
            raise VoicePhraseLookupError('QUEUE_ROW_NOT_OBJECT')
        label = row.get('label')
        val = row.get('text')
        if label is not None and not isinstance(label, str):
            raise VoicePhraseLookupError('QUEUE_LABEL_BAD_TYPE')
        if val is not None and not isinstance(val, str):
            raise VoicePhraseLookupError('QUEUE_TEXT_BAD_TYPE')
        phrase = normalize(val) if isinstance(val, str) else ''
        if label and phrase:
            other = every_labeled.get(phrase)
            if other is not None and other != label:
                raise VoicePhraseLookupError('QUEUE_CONFLICTING_LABELS')
            every_labeled[phrase] = label
        if row.get('source') != _SOURCE:
            continue
        if row.get('approved') is not True or row.get('added') is not True:
            continue
        if label not in _ALLOWED:
            continue
        if not phrase or not (5 <= len(phrase) <= 160) or not (2 <= len(phrase.split()) <= 24):
            raise VoicePhraseLookupError('CONFIRMED_PHRASE_INVALID')
        if any(ord(ch)<32 or ord(ch)==127 for ch in phrase) or not re.search(r'[а-яёa-z]',phrase):
            raise VoicePhraseLookupError('CONFIRMED_PHRASE_UNSAFE')
        if phrase in fixed and fixed[phrase] != label:
            raise VoicePhraseLookupError('CONFIRMED_CONFLICTS_WITH_TRAINING')
        confirmed.add(phrase)
    return confirmed


class ApprovedPhraseLookup:
    def __init__(self, *, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self._stamp: tuple[int,int,int,int] | None = None
        self._known: frozenset[str] = frozenset()
        self._valid = False

    def _current_stamp(self) -> tuple[int,int,int,int]:
        training = self.data_dir/'intents.json'
        outbox = self.data_dir/'inbox_labeled.jsonl'
        a = os.stat(training)
        try:
            b = os.stat(outbox)
        except FileNotFoundError:
            return (a.st_mtime_ns,a.st_size,-1,-1)
        return (a.st_mtime_ns,a.st_size,b.st_mtime_ns,b.st_size)

    def match(self, text: str) -> str | None:
        phrase = normalize(text)
        if not phrase or len(phrase) > 160:
            return None
        try:
            stamp = self._current_stamp()
            if stamp != self._stamp or not self._valid:
                values = load_approved_greetings(self.data_dir)
                self._known = frozenset(values)
                self._stamp = stamp
                self._valid = True
            return 'GREET' if phrase in self._known else None
        except (OSError, ValueError, TypeError):
            # Fail closed for the optional learned matcher. Normal NLU remains.
            self._known = frozenset()
            self._stamp = None
            self._valid = False
            return None


_DEFAULT: ApprovedPhraseLookup | None = None


def match_approved_voice_phrase(text: str) -> str | None:
    global _DEFAULT
    if _DEFAULT is None:
        # Path independent from the application's working directory.
        _DEFAULT = ApprovedPhraseLookup(data_dir=Path(__file__).resolve().parents[2] / 'data')
    return _DEFAULT.match(text)
