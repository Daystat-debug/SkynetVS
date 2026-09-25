"""Append-only intent log and exclusive once reservation. No repair/reset/replay path.
fsync requests persistence from the OS; it is not a power-loss/storage attestation.
"""
import os
from pathlib import Path
import stat
from .contract import need, canonical


class DurableJournal:
    def __init__(self, directory, once_path, plan):
        self.directory=Path(directory)
        self.once_path=Path(once_path)
        self.plan=plan.validate()
        self.sequence=0
        self.consumed=False
        self.failed=False
        self.stream=None
        # The future fixed launcher provides fresh paths outside the repository.
        # Neither a model-supplied plan nor child data selects these filesystem paths.
        need(self.directory.parent==self.once_path.parent,'journal_parent')
        for p in (self.directory.parent,*self.directory.parent.parents):
            s=p.lstat()
            need(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode) and
                 not(getattr(s,'st_file_attributes',0)&0x400),'journal_parent_reparse')
        need(not self.directory.exists(),'journal_directory_exists')
        self.directory.mkdir(mode=0o700)
        self.stream=(self.directory/'events.jsonl').open('xb',buffering=0)
        try:
            self.record('REPORT_OPENED',{'runtime_authorized':False,'native_admission':False})
        except BaseException as exc:
            # Constructor failure must not strand its already opened log stream.
            try:self.close()
            except BaseException as close_error:
                exc.add_note('journal_initial_close:'+type(close_error).__name__)
            raise

    @staticmethod
    def _write_all(stream,raw):
        at=0
        while at<len(raw):
            n=stream.write(raw[at:])
            need(type(n) is int and 0<n<=len(raw)-at,'journal_short_write')
            at+=n
        stream.flush()
        os.fsync(stream.fileno())

    def record(self,event,data=None):
        need(not self.failed and self.stream is not None,'journal_unavailable')
        try:
            raw=canonical({'kind':'HWA01_DURABLE_INTENT_V1','run_id':self.plan.run_id,
                           'sequence':self.sequence,'event':event,'data':data or {}})
            need(len(raw)<=65536,'journal_record_limit')
            self._write_all(self.stream,raw)
            self.sequence+=1
        except BaseException:
            self.failed=True
            raise

    def reserve(self):
        need(not self.consumed and not self.failed,'journal_reserve_once')
        self.consumed=True
        raw=canonical({'kind':'HWA01_HOST_WORKER_ONCE_V1','run_id':self.plan.run_id,
                       'plan_sha256':self.plan.fingerprint(),'native_admission':False,
                       'runtime_authorized':False})
        # No overwrite, unlink, retry or recovery capability is derived from this record.
        with self.once_path.open('xb',buffering=0) as f:
            self._write_all(f,raw)
        self.record('RESERVE')

    def close(self):
        if self.stream is not None:
            stream,self.stream=self.stream,None
            stream.close()
