"""One owner of retained program files, Job, process/thread and overlapped channels.
Tests inject a fake syscall port into THIS implementation, not a parallel owner.
Only controller._native_root constructs it with the real fixed WinApi.
"""
from pathlib import PureWindowsPath
from .contract import (need, digest, JobLimits, CREATE_FLAGS, FRAME_LIMIT, CLEANUP_NS,
                       Identity, ContractError)
from .bootstrap_data import serialize
from .resources import Resources
from .admission import LaunchLease

# Incomplete native I/O must keep its buffers/OVERLAPPED/event/pipe alive. An
# unresolved owner cannot be reused. Its dedicated controller must not continue tasks.
_QUARANTINED = []


class WindowsOwner:
    def __init__(self, api, plan, bundle, clock, pause):
        self.api,self.plan,self.bundle,self.clock,self.pause=api,plan,bundle,clock,pause
        self.resources=Resources()
        self.phase='NEW'
        self.supervisor=None
        self.pins=[]
        self.directories=[]
        self.job=self.process=self.thread=None
        self.child=None
        self.ends={}
        self.create_attempted=False
        self.resume_attempted=False
        self.forced=False
        self.sequence=0
        self.waiting=False
        self.stderr_op=None
        self.stderr_bytes=b''
        self.stdin_closed=False
        self.stdout_eof=False
        self.stderr_eof=False
        self.cleanup_consumed=False
        self._unresolved_retained=False
        self._claimed_lease=None
        self.retirement_observed=False
        self.last_ns=clock()

    def _retain_unresolved(self):
        """Keep incomplete native ownership alive without calling any provider.

        Only this owner's confirmed terminal phases avoid retention. Retention
        is sticky: it never authorizes retry or claims that cleanup completed.
        """
        if self._unresolved_retained or self.phase in ('RELEASED','FAILED_RETIRED'):
            return
        _QUARANTINED.append(self)
        self._unresolved_retained=True
        self.phase='UNKNOWN'

    def now(self, deadline):
        n=self.clock()
        need(type(n) is int and self.last_ns<=n<deadline,'owner_deadline_or_clock')
        self.last_ns=n
        return n

    def _adopt_process_handles(self):
        # A CreateProcess return followed by a Python exception still leaves ownership here.
        for r in self.resources.items:
            if r.name=='process':self.process=r.value
            elif r.name=='thread':self.thread=r.value

    def retain(self,deadline):
        need(self.phase=='NEW','owner_phase')
        self.bundle.validate(self.plan)
        self.supervisor=self.api.identity()
        self.now(deadline)
        files=(self.plan.runtime.executable,self.plan.runtime.python_dll)+self.bundle.file_pins(self.plan)
        directories=[]
        seen=set()
        for pin in files:
            for path in reversed(PureWindowsPath(pin.path).parents):
                s=str(path)
                if s.casefold() not in seen:
                    seen.add(s.casefold());directories.append(s)
        for i,path in enumerate(directories):
            self.now(deadline)
            h,info=self.api.open_pin(path,True,self.resources,'directory_'+str(i))
            self.directories.append((h,info))
        for i,pin in enumerate(files):
            self.now(deadline)
            h,before=self.api.open_pin(pin.path,False,self.resources,'pin_'+str(i))
            need(before['size']==pin.size,'pin_initial_size')
            raw=self.api.read_pin(h,pin.size)
            after=self.api.file_info(h)
            need(before==after and digest(raw)==pin.sha256,'pin_bytes_or_identity')
            self.pins.append((h,pin,after))
        self.now(deadline)
        self.phase='RETAINED'
        return self.supervisor

    def recheck_pins(self,deadline):
        for h,expected in self.directories:
            self.now(deadline)
            # Directory last-write time may change when unrelated children change.
            # Retain object identity/type/final path; do not make mtime an authority predicate.
            actual=self.api.file_info(h)
            for key in ('path','identity','attributes'):
                need(actual[key]==expected[key],'retained_directory_changed')
        for h,pin,expected in self.pins:
            self.now(deadline)
            need(self.api.file_info(h)==expected,'retained_file_changed')
            need(digest(self.api.read_pin(h,pin.size))==pin.sha256,'retained_bytes_changed')
            need(self.api.file_info(h)==expected,'retained_file_changed_after_read')
        self.now(deadline)
        return True

    def job_ready(self,deadline):
        need(self.phase=='RETAINED','owner_phase')
        self.now(deadline)
        self.job=self.api.create_job(self.resources)
        limits=self.api.job_limits(self.job)
        members=self.api.job_members(self.job)
        need(members==(),'job_not_empty')
        self.now(deadline)
        self.phase='JOB_READY'
        return dict(limits=limits,members=members,complete=True)

    def _await(self,op,deadline,*,watch_stderr=True):
        while True:
            self.now(deadline)
            if watch_stderr:self.check_stderr()
            if self.api.poll_io(op):
                self.now(deadline)
                error,result=op.error,op.result
                self.api.dispose_io(op,self.resources)
                need(error==0 or (error==109 and op.kind=='read'),'io_failed:'+str(error))
                return result
            self.pause(0.001)

    def prepare_channels(self,deadline):
        need(self.phase=='JOB_READY','owner_phase')
        self.now(deadline)
        logon=self.api.logon_sid()
        for label in ('stdin','stdout','stderr'):
            self.now(deadline)
            host,child,op=self.api.create_pipe_pair(self.plan.run_id,label,logon,self.resources)
            self.ends[label]=(host,child)
            self._await(op,deadline,watch_stderr=False)
            need(self.api.pipe_client_pid(host)==self.supervisor.pid,'pipe_not_self_connected')
        self.now(deadline)
        self.phase='CHANNELS_READY'

    def claim_launch(self,lease,deadline):
        need(self.phase=='CHANNELS_READY' and self._claimed_lease is None,'claim_once_phase')
        need(type(lease) is LaunchLease,'launch_lease_required')
        self.now(deadline)
        lease.claim(self,self.plan,self.api.identity(),self.clock())
        self._claimed_lease=lease
        self.phase='CLAIMED'

    def create(self,lease,deadline):
        need(self.phase=='CLAIMED' and not self.create_attempted,'create_once_phase')
        need(type(lease) is LaunchLease and lease is self._claimed_lease,'launch_claim_required')
        self.now(deadline)
        lease.require_claim(self,self.plan,self.api.identity(),self.clock())
        self.now(deadline)
        ends=tuple(self.ends[n][1] for n in ('stdin','stdout','stderr'))
        need(len(set(ends))==3 and all(self.api.inheritable(h) for h in ends),'child_handle_list')
        need(not self.api.inheritable(self.job),'job_must_not_be_inherited')
        need(self.api.job_members(self.job)==(),'job_not_empty_before_create')
        self.api.job_limits(self.job).validate()
        context=serialize(self.plan,self.bundle).hex()
        # Synchronous preparation calls may have consumed the claim lifetime.
        lease.require_claim(self,self.plan,self.supervisor,self.clock())
        self.now(deadline)
        self.create_attempted=True  # Poison before the syscall, never reset this flag.
        try:
            self.process,self.thread,pid=self.api.create_process(
                self.job,ends,self.plan,context,self.resources)
        finally:
            self._adopt_process_handles()
        # Close our child-end duplicates before any later resume can occur.
        for n in ('stdin','stdout','stderr'):
            self.resources.close_one('child_'+n)
        self.api.set_inheritable(self.process,False)
        self.api.set_inheritable(self.thread,False)
        self.child=self.api.identity(self.process)
        need(self.child.pid==pid,'created_pid_mismatch')
        need(self.api.process_in_job(self.process,self.job),'not_in_job_at_create')
        self.now(deadline)
        self.phase='CREATED'
        return dict(identity=self.child,flags=CREATE_FLAGS,job_list_applied=True)

    def verify_before_resume(self,deadline):
        need(self.phase=='CREATED','owner_phase')
        self.now(deadline)
        identity=self.api.identity(self.process)
        need(identity==self.child,'child_identity_drift')
        need(identity.image.casefold()==self.plan.runtime.executable.path.casefold(),'child_image')
        need((identity.session_id,identity.authentication_id,identity.user_sid)==
             (self.supervisor.session_id,self.supervisor.authentication_id,self.supervisor.user_sid),
             'child_token_drift')
        need(not self.api.process_exited(self.process),'child_exited_before_resume')
        need(self.api.process_in_job(self.process,self.job),'child_job_membership')
        members=self.api.job_members(self.job)
        need(members==(identity.pid,),'job_extra_or_missing_child')
        limits=self.api.job_limits(self.job)
        for r in self.resources.items:
            if r.is_handle and r.state=='OPEN':
                need(not self.api.inheritable(r.value),'parent_handle_inheritable:'+r.name)
        self.recheck_pins(deadline)
        self.phase='VERIFIED'
        return dict(identity=identity,members=members,complete=True,limits=limits,
                    child_handle_roles=('stdin','stdout','stderr'),parent_child_ends_closed=True,
                    all_parent_handles_noninheritable=True,program_pins_unchanged=True)

    def resume(self,deadline):
        need(self.phase=='VERIFIED' and not self.resume_attempted,'resume_once_phase')
        self.now(deadline)
        need(self.api.identity(self.process)==self.child,'identity_before_resume')
        need(self.api.job_members(self.job)==(self.child.pid,),'job_before_resume')
        need(not self.api.process_exited(self.process),'exited_before_resume')
        # Independent diagnostic channel is already draining when the worker first runs.
        self.stderr_op=self.api.start_io(self.ends['stderr'][0],8193,'read',self.resources)
        self.now(deadline)
        self.resume_attempted=True
        previous=self.api.resume(self.thread)
        need(previous==1,'resume_suspend_count')
        self.now(deadline)
        self.phase='RUNNING'
        return dict(previous_suspend_count=previous)

    def check_stderr(self):
        op=self.stderr_op
        if op is None:return
        if self.api.poll_io(op):
            error,result=op.error,op.result
            self.api.dispose_io(op,self.resources)
            self.stderr_op=None
            need(error in (0,109),'stderr_io_error')
            need(type(result) is bytes,'stderr_result_type')
            self.stderr_bytes=result[:8192]
            self.stderr_eof=not result
            need(not result,'stderr_not_empty')

    def send(self,packet,deadline):
        need(self.phase=='RUNNING' and not self.waiting and self.sequence<3,'send_phase')
        from .protocol import decode,DIRECTIONS
        decode(self.plan,DIRECTIONS[0],self.sequence,packet)  # Before write effect.
        self.waiting=True
        at=0
        while at<len(packet):
            self.now(deadline)
            op=self.api.start_io(self.ends['stdin'][0],len(packet)-at,'write',self.resources,packet[at:])
            n=self._await(op,deadline)
            need(type(n) is int and 0<n<=len(packet)-at,'write_count')
            at+=n

    def _read_exact(self,n,deadline):
        out=bytearray()
        while len(out)<n:
            self.now(deadline)
            op=self.api.start_io(self.ends['stdout'][0],n-len(out),'read',self.resources)
            part=self._await(op,deadline)
            need(type(part) is bytes and 0<len(part)<=n-len(out),'reply_eof_or_size')
            out.extend(part)
        return bytes(out)

    def receive(self,deadline):
        need(self.phase=='RUNNING' and self.waiting,'receive_phase')
        head=self._read_exact(4,deadline)
        n=int.from_bytes(head,'little')
        need(0<n<=FRAME_LIMIT,'reply_length')
        packet=head+self._read_exact(n,deadline)
        from .protocol import decode,DIRECTIONS
        decode(self.plan,DIRECTIONS[1],self.sequence,packet)
        identity=self.api.identity(self.process)
        need(identity==self.child,'reply_peer_drift')
        self.now(deadline)
        self.waiting=False;self.sequence+=1
        return dict(packet=packet,identity=identity)

    def retire(self,deadline):
        need(self.phase=='RUNNING' and self.sequence==3 and not self.waiting,'retire_phase')
        self.now(deadline)
        self.resources.close_one('host_stdin');self.stdin_closed=True
        extra=self.api.start_io(self.ends['stdout'][0],1,'read',self.resources)
        while True:
            self.now(deadline)
            self.check_stderr()
            if not self.stdout_eof and self.api.poll_io(extra):
                error,result=extra.error,extra.result
                self.api.dispose_io(extra,self.resources)
                need(error in (0,109) and result==b'','unexpected_stdout_tail')
                self.stdout_eof=True
            exited=self.api.process_exited(self.process)
            if exited and self.stdout_eof and self.stderr_eof:break
            self.pause(0.001)
        code=self.api.exit_code(self.process)
        members=self.api.job_members(self.job)
        need(code==0 and members==(),'not_normal_retirement')
        self.now(deadline)
        self.retirement_observed=True
        self.phase='RETIRED'
        return dict(signaled=True,exit_code=code,members=members,complete=True)

    def quiescent(self):
        need(self.phase=='RETIRED','owner_phase')
        need(not self.api.operations and self.stdout_eof and self.stderr_eof,'io_not_quiescent')
        self.phase='QUIESCENT'
        return dict(pending_io=0,threads_alive=0,stderr_bytes=len(self.stderr_bytes))

    def release(self,deadline):
        need(self.phase=='QUIESCENT','owner_phase')
        self.recheck_pins(deadline)
        errors=self.resources.close_all()
        need(not errors and self.resources.all_closed(),'resource_release_uncertain')
        self.now(deadline)
        self.phase='RELEASED'
        return {**self.resources.summary(),'program_pins_unchanged':True}

    def cleanup(self,deadline):
        """One forced-retirement attempt at most. Never upgrades failed work to success."""
        need(not self.cleanup_consumed,'cleanup_once')
        self.cleanup_consumed=True
        try:
            return self._cleanup_consumed_attempt(deadline)
        finally:
            # Includes clock/pause, handle adoption and result-building failures.
            self._retain_unresolved()

    def _cleanup_consumed_attempt(self,deadline):
        """Body of the single cleanup call; entered only by cleanup above."""
        self._adopt_process_handles()
        errors=[]
        def attempt(fn):
            try:return fn()
            except BaseException as exc:
                errors.append(type(exc).__name__+':'+str(exc)[:160]);return None
        def is_open(name):
            return any(r.name==name and r.state=='OPEN' for r in self.resources.items)
        exited=self.retirement_observed
        if self.process is not None and is_open('process'):
            exited=attempt(lambda:self.api.process_exited(self.process)) is True
        if self.create_attempted and not exited and self.job is not None and is_open('job'):
            self.forced=True
            attempt(lambda:self.api.terminate_job(self.job))
        for op in list(self.api.operations):
            attempt(lambda op=op:self.api.cancel_io(op))
        clock_valid=True
        last=self.clock()
        need(type(last) is int and last>=self.last_ns,'cleanup_clock_regression_or_type')
        while last<deadline:
            for op in list(self.api.operations):
                if op.disposed:continue
                if attempt(lambda op=op:self.api.poll_io(op)) is True:
                    attempt(lambda op=op:self.api.dispose_io(op,self.resources))
            if self.process is not None and is_open('process'):
                exited=attempt(lambda:self.api.process_exited(self.process)) is True
            if not self.api.operations and (exited or not self.create_attempted):break
            self.pause(0.001)
            n=self.clock()
            if type(n) is not int or n<last:
                clock_valid=False;break
            last=n
        members=() if self.job is None or (self.retirement_observed and not is_open('job')) else attempt(lambda:self.api.job_members(self.job))
        empty=members==()
        quiet=not self.api.operations
        no_child=not self.create_attempted
        safe_to_release=quiet and (no_child or (exited and empty))
        if safe_to_release:
            errors.extend(self.resources.close_all())
        else:
            # Job may be closed to request kill-on-close, but process/I/O buffers stay held.
            if any(r.name=='job' and r.state=='OPEN' for r in self.resources.items):
                attempt(lambda:self.resources.close_one('job'))
            self._retain_unresolved()
        complete=False
        if clock_valid:
            finished=self.clock()
            complete=(type(finished) is int and last<=finished<deadline and
                      safe_to_release and self.resources.all_closed() and not errors and
                      not self._unresolved_retained)
        self.phase='FAILED_RETIRED' if complete else 'UNKNOWN'
        self._retain_unresolved()
        return dict(no_child_created=no_child,child_exited=exited,job_empty=empty,
                    io_quiescent=quiet,handles_released=self.resources.all_closed(),
                    forced=self.forced,errors=errors,cleanup_confirmed=complete,
                    quarantined=self._unresolved_retained)
