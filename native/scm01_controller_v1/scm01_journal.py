"""Create-exclusive one-shot marker and append/fsync intent journal.

This is guest-side crash evidence, not the future host-side authorization consumer.
No deletion, resume, truncation, or replay of previous journals is provided.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import time
from scm01_contract import ContractError


def encoded(record):
    return (json.dumps(record, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n').encode('ascii')


def write_all(fd, data):
    while data:
        n = os.write(fd, data)
        if n <= 0:
            raise OSError('short journal write')
        data = data[n:]


class ExclusiveJournal:
    def __init__(self, directory: Path, capsule):
        capsule.validate_shape()
        self.sequence = 0
        self.healthy = True
        self.closed = False
        self.fd = None
        # The later runtime capsule must bind this pre-provisioned private guest directory.
        directory = Path(directory)
        if not directory.is_dir() or directory.is_symlink():
            raise ContractError('pre-provisioned journal directory required')
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
        marker = directory / 'SCM01_CONTROLLER_V1.once.json'
        fd = os.open(marker, flags, 0o600)
        try:
            write_all(fd, encoded({'kind': 'SCM01_START_INTENT', 'run_id': capsule.run_id,
                                  'guest_id': capsule.guest_id, 'authorization_sha256': capsule.authorization_sha256,
                                  'runtime_permission_is_not_minted_here': True}))
            os.fsync(fd)
        finally:
            os.close(fd)
        # If any subsequent operation fails, the marker deliberately remains consumed.
        self.fd = os.open(directory / ('SCM01_' + capsule.run_id + '.jsonl'), flags, 0o600)
        try:
            os.fsync(self.fd)
        except BaseException:
            fd, self.fd = self.fd, None
            self.closed = True
            self.healthy = False
            os.close(fd)
            raise

    def record(self, event, **data):
        if not self.healthy or self.closed:
            raise ContractError('journal unavailable; no new mutation is allowed')
        self.sequence += 1
        row = {'sequence': self.sequence, 'event': event, 'utc_ns': time.time_ns(),
               'monotonic_ns': time.monotonic_ns(), **data}
        try:
            write_all(self.fd, encoded(row))
            os.fsync(self.fd)
        except BaseException:
            self.healthy = False
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            fd, self.fd = self.fd, None
            if fd is not None:
                os.close(fd)
