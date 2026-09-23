"""Concrete process/Toolhelp/Job source; all public factories remain gated.
Known process-set retirement is a lab observation, never Hyper-V VM disposal proof.
"""
from dataclasses import dataclass, field
from pathlib import PureWindowsPath
from .benign_contract import need, uint, hexstr, sha, canonical, BenignError
from .benign_layout import winpath, BoundLayout
from .benign_runtime_gate import require_native_authority, require_benign_run_authority

KNOWN_NAMES = ('windowssandbox.exe', 'windowssandboxclient.exe', 'windowssandboxremotesession.exe')
PERSISTENT_NAMES = KNOWN_NAMES[1:]
WORKER_FLAGS = 0x4 | 0x8 | 0x400  # suspended | detached | unicode, not CREATE_NO_WINDOW
EXTENDED_STARTUPINFO_PRESENT = 0x80000
RETIREMENT_BASIS = 'EXCLUSIVE_HOST_KNOWN_PROCESSSET_V1'
MIN_SCAN_NS = 250_000_000
_NATIVE_SEAL = object()


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    created: int
    path: str
    session_id: int
    authentication_id: int
    user_sid: str

    def descriptor(self):
        return dict(pid=self.pid, created=self.created, path=self.path,
                    session_id=self.session_id, authentication_id=self.authentication_id,
                    user_sid=self.user_sid)


@dataclass(frozen=True)
class ProcessSnapshot:
    processes: tuple[ProcessIdentity, ...]
    complete: bool
    at_ns: int
    boot_binding: str
    evidence_domain: str


@dataclass(frozen=True)
class LaunchReceipt:
    identity: ProcessIdentity
    handle: object
    config_sha256: str
    evidence_domain: str


@dataclass(frozen=True)
class SessionBinding:
    run_id: str
    nonce: str
    boot_binding: str
    request_sha256: str
    wsb_sha256: str
    identities: tuple[ProcessIdentity, ...]
    handles: tuple[object, ...] = field(repr=False)
    binding_sha256: str = ''


@dataclass(frozen=True)
class RetirementObservation:
    run_id: str
    nonce: str
    boot_binding: str
    binding_sha256: str
    normal: bool
    forced: bool
    handles_signaled: bool
    empty_scan_ticks: tuple[int, ...]
    evidence_domain: str = 'OFFLINE_MODEL'
    _seal: object = field(default=None, repr=False, compare=False)


def is_native_retirement(r, run_id, nonce, binding, boot):
    return (type(r) is RetirementObservation and r._seal is _NATIVE_SEAL and
            r.evidence_domain == 'NATIVE_WIN32_LAB' and r.run_id == run_id and r.nonce == nonce and
            r.boot_binding == boot and r.binding_sha256 == binding and r.normal is True and
            r.forced is False and r.handles_signaled is True and len(r.empty_scan_ticks) == 3 and
            all(b - a >= MIN_SCAN_NS for a, b in zip(r.empty_scan_ticks, r.empty_scan_ticks[1:])))


@dataclass(frozen=True)
class CleanupOutcome:
    attempted: tuple[int, ...]
    confirmed: tuple[int, ...]
    errors: tuple[str, ...]
    failure: bool = True
    hypervisor_disposal_proven: bool = False


class _ProcessEngine:
    """Control algorithm shared by fake API and gated Win32 API; no callback promotion."""
    def __init__(self, api, inventory):
        need(type(inventory) is tuple and inventory, 'image_inventory')
        for name, path in inventory:
            need(name.casefold() in KNOWN_NAMES and PureWindowsPath(winpath(path)).name.casefold() == name.casefold(),
                 'sandbox_image_inventory')
        need(len(set(n.casefold() for n, _ in inventory)) == len(inventory), 'inventory_duplicates')
        self.api = api; self.inventory = {n.casefold(): p.casefold() for n, p in inventory}
        self.domain = 'NATIVE_WIN32_LAB' if type(api) is _WinProcessApi else 'OFFLINE_MODEL'
        self.launch_attempted = False
        self._cleanup_attempted = set()
        self._empty_ticks = []
        self._retiring_binding = None
        self._released = set()

    def _identity(self, h, pid, name):
        ident = self.api.identity(h, pid)
        need(type(ident) is ProcessIdentity and ident.pid == pid and ident.created > 0, 'process_metadata')
        need(name.casefold() in self.inventory and ident.path.casefold() == self.inventory[name.casefold()],
             'process_image_path')
        need(ident.user_sid.startswith('S-1-') and ident.authentication_id > 0, 'token_metadata')
        return ident

    def snapshot_complete(self):
        api = self.api; snap = api.snapshot(); out = []; seen = set(); started = api.now_ns()
        try:
            boot = api.boot_binding(); hexstr(boot)
            ok, pid, name, error = api.first(snap)
            steps = 0
            while ok:
                steps += 1; need(steps <= 65536 and api.now_ns() - started <= 2_000_000_000,
                                 'process_scan_budget')
                need(type(pid) is int and pid not in seen, 'duplicate_process_row'); seen.add(pid)
                if name.casefold() in KNOWN_NAMES:
                    h = api.open_process(pid)
                    try:
                        out.append(self._identity(h, pid, name))
                    finally:
                        api.close(h)
                ok, pid, name, error = api.next(snap)
            # A failed enumeration is not an empty snapshot.
            need(error == 18, 'incomplete_process_enumeration')
            need(api.boot_binding() == boot, 'boot_changed')
        finally:
            api.close(snap)
        return ProcessSnapshot(tuple(sorted(out, key=lambda x: x.pid)), True, api.now_ns(), boot, self.domain)

    def launch(self, executable, config_path, config_bytes, expected_sha):
        need(not self.launch_attempted, 'launch_consumed')
        winpath(executable); winpath(config_path)
        need(executable.casefold() == self.inventory.get('windowssandbox.exe'), 'fixed_executable')
        need(PureWindowsPath(config_path).name == 'session.wsb' and sha(config_bytes) == expected_sha,
             'config_binding')
        baseline = self.snapshot_complete(); need(not baseline.processes, 'nonempty_baseline')
        self.launch_attempted = True
        # Concrete API uses exact executable/config only, no shell and no inherited handles.
        h, pid = self.api.launch(executable, config_path)
        try:
            identity = self._identity(h, pid, 'windowssandbox.exe')
        except Exception:
            # Do not terminate an unverified identity, preserve uncertainty.
            self.api.close(h); raise
        return LaunchReceipt(identity, h, expected_sha, self.domain)

    def bind(self, launch, scan, run_id, nonce, request_sha256):
        need(type(launch) is LaunchReceipt and type(scan) is ProcessSnapshot and scan.complete,
             'binding_input')
        hexstr(run_id, 32); hexstr(nonce); hexstr(request_sha256)
        need(scan.boot_binding == self.api.boot_binding(), 'boot_binding')
        anchors = [p for p in scan.processes if PureWindowsPath(p.path).name.casefold() in PERSISTENT_NAMES]
        need(len(anchors) == 1, 'persistent_anchor_ambiguous')
        need(anchors[0].created >= launch.identity.created and
             anchors[0].session_id == launch.identity.session_id and
             anchors[0].authentication_id == launch.identity.authentication_id and
             anchors[0].user_sid == launch.identity.user_sid, 'anchor_window_or_token')
        ids = {launch.identity.pid: launch.identity}
        for p in scan.processes:
            need(p.created >= launch.identity.created and
                 (p.session_id, p.authentication_id, p.user_sid) ==
                 (launch.identity.session_id, launch.identity.authentication_id, launch.identity.user_sid),
                 'preexisting_or_foreign_process')
            if p.pid == launch.identity.pid:
                need(p == launch.identity, 'launcher_pid_reused')
            ids[p.pid] = p
        ordered = tuple(sorted(ids.values(), key=lambda p: p.pid)); handles = []
        try:
            for p in ordered:
                if p == launch.identity:
                    h = launch.handle
                else:
                    h = self.api.open_process(p.pid)
                    try:
                        need(self.api.identity(h, p.pid) == p, 'binding_race')
                    except Exception:
                        self.api.close(h); raise
                handles.append(h)
        except Exception:
            for h in handles:
                if h != launch.handle:
                    self.api.close(h)
            raise
        raw = canonical({'run_id': run_id, 'nonce': nonce, 'boot_binding': scan.boot_binding,
                         'request_sha256': request_sha256, 'wsb_sha256': launch.config_sha256,
                         'processes': [p.descriptor() for p in ordered]})
        return SessionBinding(run_id, nonce, scan.boot_binding, request_sha256,
                              launch.config_sha256, ordered, tuple(handles), sha(raw))

    def observe(self, binding):
        need(binding.binding_sha256 not in self._released, 'binding_released')
        scan = self.snapshot_complete()
        need(scan.boot_binding == binding.boot_binding, 'boot_changed')
        known = set(binding.identities)
        need(all(x in known for x in scan.processes), 'foreign_or_replacement_anchor')
        need(len(binding.handles) == len(binding.identities), 'handle_binding')
        signaled = True
        for h, expected in zip(binding.handles, binding.identities):
            result = self.api.wait(h, 0)
            need(result in (0, 258), 'wait_unknown')
            # A retained signaled handle is the exited process object, not a reused PID.
            # Do not query a dead process token by PID after observing its termination.
            if result == 258:
                need(self.api.identity(h, expected.pid) == expected, 'retirement_identity_changed')
            signaled = signaled and result == 0
        if self._retiring_binding != binding.binding_sha256:
            self._empty_ticks = []; self._retiring_binding = binding.binding_sha256
        if scan.processes or not signaled:
            self._empty_ticks = []
        elif not self._empty_ticks or scan.at_ns - self._empty_ticks[-1] >= MIN_SCAN_NS:
            self._empty_ticks.append(scan.at_ns)
            self._empty_ticks = self._empty_ticks[-3:]
        if len(self._empty_ticks) != 3:
            return None
        return RetirementObservation(binding.run_id, binding.nonce, binding.boot_binding,
                                     binding.binding_sha256, True, False, True, tuple(self._empty_ticks),
                                     self.domain, _NATIVE_SEAL if self.domain == 'NATIVE_WIN32_LAB' else None)

    def cleanup(self, binding, budget_ms=10000):
        need(binding.binding_sha256 not in self._released, 'binding_released')
        need(len(binding.handles) == len(binding.identities), 'cleanup_handle_set')
        uint(budget_ms, 10000); need(budget_ms > 0, 'cleanup_budget')
        started = self.api.now_ns(); attempted = []; confirmed = []; errors = []
        for h, p in zip(binding.handles, binding.identities):
            key = (p.pid, p.created)
            try:
                initial = self.api.wait(h, 0)
                need(initial in (0, 258), 'cleanup_wait_unknown')
                if initial == 0:
                    confirmed.append(p.pid); continue
                need(self.api.identity(h, p.pid) == p, 'cleanup_identity_changed')
                need(key not in self._cleanup_attempted, 'cleanup_attempt_consumed')
                remaining = budget_ms - (self.api.now_ns() - started) // 1_000_000
                need(remaining > 0, 'cleanup_deadline')
                self._cleanup_attempted.add(key); attempted.append(p.pid)
                self.api.terminate(h)
                wait = self.api.wait(h, int(remaining))
                if wait == 0:
                    confirmed.append(p.pid)
                else:
                    errors.append('termination_not_confirmed:' + str(p.pid))
            except Exception as exc:
                errors.append(type(exc).__name__ + ':' + str(exc))
        return CleanupOutcome(tuple(attempted), tuple(confirmed), tuple(errors))


    def release(self, binding_or_launch):
        if type(binding_or_launch) is SessionBinding:
            key = binding_or_launch.binding_sha256
            handles = binding_or_launch.handles
        else:
            need(type(binding_or_launch) is LaunchReceipt, 'release_receipt')
            key = ('launcher', binding_or_launch.identity.pid, binding_or_launch.identity.created)
            handles = (binding_or_launch.handle,)
        need(key not in self._released, 'already_released')
        self._released.add(key)
        errors = []
        for h in dict.fromkeys(handles):
            try:
                self.api.close(h)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise BenignError('release_handles_unknown') from errors[0]


def snapshot_complete(permit=None):
    require_native_authority(permit)
    return _ProcessEngine(_WinProcessApi(permit), permit.image_inventory).snapshot_complete()


def probe_host_readonly(permit=None):
    require_native_authority(permit)
    api = _WinProcessApi(permit)
    return {'snapshot': _ProcessEngine(api, permit.image_inventory).snapshot_complete(),
            'boot_binding_basis': 'SUPERVISOR_PROCESS_INCARNATION_V1',
            'os_boot_guid_verified': False}


def launch_bound(layout, permit=None):
    require_benign_run_authority(permit)
    need(type(layout) is BoundLayout, 'layout_type')
    return permit.session.launch(permit.executable, layout.lab_root + '\\session.wsb',
                                 permit.wsb_bytes, sha(permit.wsb_bytes))


def observe_bound(binding, permit=None):
    require_native_authority(permit)
    return permit.session.observe(binding)


def cleanup_bound(binding, budget, permit=None):
    require_native_authority(permit)
    return permit.session.cleanup(binding, budget)


def spawn_artifact_worker(api, descriptor):
    """Internal fake/native algorithm, never an issuer. Real API constructor is gated."""
    need(descriptor.get('flags') == WORKER_FLAGS, 'worker_flags')
    need(descriptor.get('active_process_limit') == 1, 'job_limit')
    need(descriptor.get('role') == 'ARTIFACT_WORKER', 'worker_role')
    h = thread = job = None
    try:
        job = api.create_job(1, 512 * 1024**2, 768 * 1024**2)
        h, thread, pid = api.create_suspended_worker(descriptor)
        api.assign(job, h)
        need(api.job_processes(job) == (pid,), 'unexpected_job_pid')
        api.resume(thread)
        closing_thread = thread; thread = None
        api.close(closing_thread)
        return h, job, pid
    except Exception as original:
        errors = []
        if h is not None:
            try:
                api.terminate(h)
                need(api.wait(h, 10000) == 0, 'worker_cleanup_unknown')
            except Exception as exc:
                errors.append(exc)
        for owned in (thread, h, job):
            if owned is not None:
                try:
                    api.close(owned)
                except Exception as exc:
                    errors.append(exc)
        if errors:
            raise BenignError('worker_setup_cleanup_unknown') from original
        raise


def _create_worker_with_inheritance(api, descriptor):
    """Restore own pipe inheritance even when setup/CreateProcess succeeds then fails.
    A newly created, not-yet-Job-bound child is never lost on inheritance-reset failure.
    """
    handles = tuple(descriptor['child_handles'])
    need(len(handles) == 2 and all(handles) and handles[0] != handles[1], 'pipe_handle_list')
    touched = []; created = None; failure = None; cleanup_errors = []
    try:
        for handle in handles:
            touched.append(handle)  # A failed SetHandleInformation may have an unknown outcome.
            api.set_inherit(handle, True)
        created = api.create_worker_raw(descriptor)
    except Exception as exc:
        failure = exc
    finally:
        for handle in reversed(touched):
            try:
                api.set_inherit(handle, False)
            except Exception as exc:
                cleanup_errors.append(exc)
    if failure is not None or cleanup_errors:
        if created is not None:
            process, thread, _pid = created
            try:
                api.terminate(process)
                need(api.wait(process, 10000) == 0, 'prejob_child_retirement_unknown')
            except Exception as exc:
                cleanup_errors.append(exc)
            for handle in (thread, process):
                try:
                    api.close(handle)
                except Exception as exc:
                    cleanup_errors.append(exc)
        raise BenignError('worker_inheritance_or_create_unknown') from (failure or cleanup_errors[0])
    return created


class _WinProcessApi:
    """Gated Win64 implementation. No dynamic DLL/native call until constructor is authorized.
    Boot correlation is bound to the current supervisor incarnation, not an OS boot GUID.
    A supervisor cannot survive a reboot; restart never resumes the consumed grant.
    """
    def __init__(self, permit):
        require_native_authority(permit)
        import ctypes as c
        import sys
        need(sys.platform == 'win32' and c.sizeof(c.c_void_p) == 8, 'win64')
        self.c = c; self.k = c.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        self.a = c.WinDLL('advapi32.dll', use_last_error=True, winmode=0x800)
        U = c.c_uint32; I = c.c_int32; Q = c.c_uint64; H = c.c_void_p; S = c.c_size_t; W = c.c_wchar_p
        class PE(c.Structure):
            _fields_ = [('size', U), ('usage', U), ('pid', U), ('heap', S), ('module', U),
                        ('threads', U), ('parent', U), ('priority', I), ('flags', U), ('name', c.c_wchar * 260)]
        class PI(c.Structure):
            _fields_ = [('process', H), ('thread', H), ('pid', U), ('tid', U)]
        class SI(c.Structure):
            _fields_ = [('cb', U), ('reserved', W), ('desktop', W), ('title', W),
                        ('x', U), ('y', U), ('xs', U), ('ys', U), ('xc', U), ('yc', U),
                        ('fill', U), ('flags', U), ('show', c.c_uint16), ('cb2', c.c_uint16),
                        ('res2', H), ('stdin', H), ('stdout', H), ('stderr', H)]
        class SX(c.Structure):
            _fields_ = [('base', SI), ('attributes', H)]
        class Limits(c.Structure):
            _fields_ = [('process_time', c.c_int64), ('job_time', c.c_int64), ('flags', U),
                        ('minws', S), ('maxws', S), ('active', U), ('affinity', S),
                        ('priority', U), ('scheduling', U)]
        class Ext(c.Structure):
            _fields_ = [('basic', Limits), ('io', Q * 6), ('processmem', S), ('jobmem', S),
                        ('peakprocess', S), ('peakjob', S)]
        self.PE, self.PI, self.SI, self.SX, self.Ext = PE, PI, SI, SX, Ext
        need(c.sizeof(PE) == 568 and c.sizeof(SI) == 104 and c.sizeof(SX) == 112 and
             c.sizeof(Ext) == 144 and c.sizeof(PI) == 24, 'process_abi')
        self.entries = {}
        signatures = {
            'CreateToolhelp32Snapshot': (H, [U, U]),
            'Process32FirstW': (I, [H, c.POINTER(PE)]), 'Process32NextW': (I, [H, c.POINTER(PE)]),
            'OpenProcess': (H, [U, I, U]), 'CloseHandle': (I, [H]),
            'GetProcessTimes': (I, [H, H, H, H, H]),
            'QueryFullProcessImageNameW': (I, [H, U, W, c.POINTER(U)]),
            'ProcessIdToSessionId': (I, [U, c.POINTER(U)]),
            'WaitForSingleObject': (U, [H, U]), 'TerminateProcess': (I, [H, U]),
            'GetCurrentProcessId': (U, []), 'GetTickCount64': (Q, []),
            'OpenThread': (H, [U, I, U]), 'CancelSynchronousIo': (I, [H]),
            'CreateProcessW': (I, [W, W, H, H, I, U, H, W, H, c.POINTER(PI)]),
            'CreateJobObjectW': (H, [H, W]), 'SetInformationJobObject': (I, [H, I, H, U]),
            'QueryInformationJobObject': (I, [H, I, H, U, c.POINTER(U)]),
            'AssignProcessToJobObject': (I, [H, H]), 'ResumeThread': (U, [H]),
            'InitializeProcThreadAttributeList': (I, [H, U, U, c.POINTER(S)]),
            'UpdateProcThreadAttribute': (I, [H, U, S, H, S, H, H]),
            'DeleteProcThreadAttributeList': (None, [H]),
            'CreatePipe': (I, [c.POINTER(H), c.POINTER(H), H, U]),
            'SetHandleInformation': (I, [H, U, U]),
            'PeekNamedPipe': (I, [H, H, U, H, c.POINTER(U), H]),
            'ReadFile': (I, [H, H, U, c.POINTER(U), H]),
            'WriteFile': (I, [H, H, U, c.POINTER(U), H]),
            'LocalFree': (H, [H])}
        for n, (ret, args) in signatures.items():
            f = getattr(self.k, n); f.restype = ret; f.argtypes = args
        for n, args in {'OpenProcessToken': [H, U, c.POINTER(H)],
                        'GetTokenInformation': [H, I, H, U, c.POINTER(U)],
                        'ConvertSidToStringSidW': [H, c.POINTER(W)]}.items():
            f = getattr(self.a, n); f.restype = I; f.argtypes = args
        pid = int(self.k.GetCurrentProcessId()); h = self.open_process(pid)
        try:
            self._boot = sha(canonical({'basis': 'SUPERVISOR_PROCESS_INCARNATION_V1',
                                         **self.identity(h, pid).descriptor()}))
        finally:
            self.close(h)

    def _ok(self, result):
        if not result:
            raise self.c.WinError(self.c.get_last_error())
        return result

    def now_ns(self):
        import time
        return time.monotonic_ns()

    def boot_binding(self):
        return self._boot

    def snapshot(self):
        h = self.k.CreateToolhelp32Snapshot(2, 0)
        if h == self.c.c_void_p(-1).value:
            raise self.c.WinError(self.c.get_last_error())
        pe = self.PE(); pe.size = self.c.sizeof(pe); self.entries[h] = pe
        return h

    def _step(self, h, first):
        pe = self.entries[h]; self.c.set_last_error(0)
        ok = (self.k.Process32FirstW if first else self.k.Process32NextW)(h, self.c.byref(pe))
        return bool(ok), int(pe.pid), str(pe.name), self.c.get_last_error() if not ok else 0

    def first(self, h):
        return self._step(h, True)

    def next(self, h):
        return self._step(h, False)

    def open_process(self, pid):
        # Retained cleanup handles need terminate/query/synchronize; no privilege repair.
        return self._ok(self.k.OpenProcess(0x1000 | 0x100000 | 1, False, pid))

    def identity(self, h, pid):
        c = self.c; times = [c.c_uint64() for _ in range(4)]
        self._ok(self.k.GetProcessTimes(h, *(c.byref(t) for t in times)))
        path = c.create_unicode_buffer(1024); n = c.c_uint32(len(path))
        self._ok(self.k.QueryFullProcessImageNameW(h, 0, path, c.byref(n)))
        sid = c.c_uint32(); self._ok(self.k.ProcessIdToSessionId(pid, c.byref(sid)))
        token = c.c_void_p(); self._ok(self.a.OpenProcessToken(h, 8, c.byref(token)))
        try:
            def token_buffer(cls):
                n = c.c_uint32(); c.set_last_error(0)
                ok = self.a.GetTokenInformation(token, cls, None, 0, c.byref(n))
                need(not ok and c.get_last_error() == 122 and 0 < n.value <= 16384, 'token_size_query')
                b = c.create_string_buffer(n.value)
                self._ok(self.a.GetTokenInformation(token, cls, b, n.value, c.byref(n))); return b
            user = token_buffer(1); stats = token_buffer(10)
            need(len(stats) >= 16, 'token_statistics_size')
            authentication = int.from_bytes(bytes(stats)[8:16], 'little')
            sidptr = c.cast(user, c.POINTER(c.c_void_p))[0]; text = c.c_wchar_p()
            self._ok(self.a.ConvertSidToStringSidW(sidptr, c.byref(text)))
            try:
                user_sid = text.value
            finally:
                need(not self.k.LocalFree(c.cast(text, c.c_void_p)), 'LocalFree')
        finally:
            self.close(token.value)
        return ProcessIdentity(pid, times[0].value, path.value, sid.value, authentication, user_sid)

    def close(self, h):
        self.entries.pop(h, None); self._ok(self.k.CloseHandle(h))

    def wait(self, h, ms):
        return int(self.k.WaitForSingleObject(h, ms))

    def terminate(self, h):
        self._ok(self.k.TerminateProcess(h, 1))

    def _environment(self):
        # Fixed minimal environment; future host admission pins Windows path separately.
        return ('PATH=C:\\Windows\\System32\0SystemRoot=C:\\Windows\0'
                'TEMP=C:\\Windows\\Temp\0TMP=C:\\Windows\\Temp\0WINDIR=C:\\Windows\0\0')

    def launch(self, executable, config_path):
        c = self.c; si = self.SI(); si.cb = c.sizeof(si); pi = self.PI()
        command = c.create_unicode_buffer('"' + executable + '" "' + config_path + '"')
        env = c.create_unicode_buffer(self._environment())
        self._ok(self.k.CreateProcessW(executable, command, None, None, False, 0x400,
                                      env, str(PureWindowsPath(config_path).parent), c.byref(si), c.byref(pi)))
        self.close(pi.thread)
        return pi.process, int(pi.pid)

    def create_job(self, active, processmem, jobmem):
        c = self.c; h = self._ok(self.k.CreateJobObjectW(None, None)); limits = self.Ext()
        limits.basic.flags = 0x2000 | 0x8 | 0x100 | 0x200
        limits.basic.active = active; limits.processmem = processmem; limits.jobmem = jobmem
        try:
            self._ok(self.k.SetInformationJobObject(h, 9, c.byref(limits), c.sizeof(limits)))
            return h
        except Exception:
            self.close(h); raise

    def assign(self, job, process):
        self._ok(self.k.AssignProcessToJobObject(job, process))

    def job_processes(self, job):
        c = self.c
        class Pids(c.Structure):
            _fields_ = [('assigned', c.c_uint32), ('listed', c.c_uint32), ('pids', c.c_size_t * 2)]
        p = Pids(); length = c.c_uint32()
        self._ok(self.k.QueryInformationJobObject(job, 3, c.byref(p), c.sizeof(p), c.byref(length)))
        need(p.assigned == p.listed and p.listed <= 2, 'job_accounting_incomplete')
        return tuple(int(x) for x in p.pids[:p.listed])

    def resume(self, thread):
        need(self.k.ResumeThread(thread) == 1, 'resume_count')

    def set_inherit(self, handle, enabled):
        self._ok(self.k.SetHandleInformation(handle, 1, 1 if enabled else 0))

    def create_suspended_worker(self, descriptor):
        return _create_worker_with_inheritance(self, descriptor)

    def create_worker_raw(self, descriptor):
        c = self.c; exe = winpath(descriptor['executable']); script = winpath(descriptor['script'])
        need(PureWindowsPath(script).name == 'benign_worker.py' and descriptor['flags'] == WORKER_FLAGS,
             'fixed_worker_entry')
        handles = tuple(descriptor['child_handles'])
        arr = (c.c_void_p * 2)(*handles); length = c.c_size_t()
        c.set_last_error(0)
        ok = self.k.InitializeProcThreadAttributeList(None, 1, 0, c.byref(length))
        need(not ok and c.get_last_error() == 122 and 0 < length.value <= 65536, 'attribute_size')
        attrs = c.create_string_buffer(length.value); initialized = False
        sx = self.SX(); sx.base.cb = c.sizeof(sx); pi = self.PI()
        try:
            self._ok(self.k.InitializeProcThreadAttributeList(attrs, 1, 0, c.byref(length))); initialized = True
            self._ok(self.k.UpdateProcThreadAttribute(attrs, 0, 0x20002, arr, c.sizeof(arr), None, None))
            sx.attributes = c.cast(attrs, c.c_void_p)
            sx.base.flags = 0x100; sx.base.stdin = handles[0]; sx.base.stdout = handles[1]; sx.base.stderr = handles[1]
            command = c.create_unicode_buffer('"' + exe + '" -I -S -B -X utf8 "' + script + '"')
            env = c.create_unicode_buffer(self._environment())
            self._ok(self.k.CreateProcessW(exe, command, None, None, True,
                                          WORKER_FLAGS | EXTENDED_STARTUPINFO_PRESENT, env,
                                          str(PureWindowsPath(script).parent), c.byref(sx), c.byref(pi)))
            return pi.process, pi.thread, int(pi.pid)
        finally:
            if initialized:
                self.k.DeleteProcThreadAttributeList(attrs)

    def create_pipe(self):
        c = self.c; read = c.c_void_p(); write = c.c_void_p()
        self._ok(self.k.CreatePipe(c.byref(read), c.byref(write), None, 65536))
        return read.value, write.value

    def pipe_available(self, h):
        n = self.c.c_uint32()
        self._ok(self.k.PeekNamedPipe(h, None, 0, None, self.c.byref(n), None)); return n.value

    def pipe_read(self, h, n):
        c = self.c; b = (c.c_ubyte * n)(); got = c.c_uint32()
        self._ok(self.k.ReadFile(h, b, n, c.byref(got), None)); return bytes(b[:got.value])

    def pipe_write(self, h, data):
        c = self.c; b = (c.c_ubyte * len(data)).from_buffer_copy(data); got = c.c_uint32()
        self._ok(self.k.WriteFile(h, b, len(data), c.byref(got), None))
        need(got.value == len(data), 'pipe_short_write')


    def cancel_thread_io(self, native_thread_id):
        """Cancellation request only. The caller must join the owned pump thread separately."""
        uint(native_thread_id, 0xffffffff); need(native_thread_id > 0, 'thread_id')
        h = self._ok(self.k.OpenThread(1, False, native_thread_id))  # THREAD_TERMINATE for cancellation.
        try:
            if not self.k.CancelSynchronousIo(h):
                need(self.c.get_last_error() == 1168, 'cancel_sync_io_failed')  # No pending I/O is allowed.
        finally:
            self.close(h)


@dataclass(frozen=True)
class WorkerSourcePin:
    executable: str
    executable_sha256: str
    script: str
    source_sha256: str

    def validate(self):
        winpath(self.executable); winpath(self.script)
        hexstr(self.executable_sha256); hexstr(self.source_sha256)
        need(PureWindowsPath(self.script).name == 'benign_worker.py', 'fixed_worker_script')
        return self


class _OwnedWorker:
    """Retained own child/job and private pipe ends, not PID/name-based admission.
    No public constructor may call this with arbitrary callbacks as native proof.
    """
    def __init__(self, api, source_pin):
        source_pin.validate()
        self.api, self.source_pin = api, source_pin
        self.process = self.job = self.pid = self.identity = None
        self.input_write = self.output_read = None
        self.child_read = self.child_write = None
        self.started = self.stop_attempted = self.closed = False
        self.domain = 'NATIVE_WIN32_LAB' if type(api) is _WinProcessApi else 'OFFLINE_MODEL'
        self.boot = api.boot_binding(); hexstr(self.boot)

    def start_once(self):
        need(not self.started and not self.closed, 'worker_start_consumed'); self.started = True
        owned = []
        try:
            self.child_read, self.input_write = self.api.create_pipe()
            owned += [self.child_read, self.input_write]
            self.output_read, self.child_write = self.api.create_pipe()
            owned += [self.output_read, self.child_write]
            need(len(set(owned)) == 4 and all(owned), 'worker_pipe_alias')
            for handle in owned: self.api.set_inherit(handle, False)
            descriptor = dict(flags=WORKER_FLAGS, active_process_limit=1, role='ARTIFACT_WORKER',
                executable=self.source_pin.executable, script=self.source_pin.script,
                child_handles=(self.child_read, self.child_write))
            self.process, self.job, self.pid = spawn_artifact_worker(self.api, descriptor)
            self.identity = self.api.identity(self.process, self.pid)
            need(type(self.identity) is ProcessIdentity and self.identity.pid == self.pid and
                 self.identity.path.casefold() == self.source_pin.executable.casefold(), 'worker_image_identity')
            # Child keeps only its inherited copies. Parent closes child ends before pumping.
            for attr in ('child_read', 'child_write'):
                h = getattr(self, attr); setattr(self, attr, None); self.api.close(h)
            self.check_live()
        except Exception:
            try: self.stop_once(10000)
            finally: self.close_pipes()
            raise

    def check_live(self):
        need(self.started and not self.closed and not self.stop_attempted and self.process is not None,
             'worker_not_live')
        need(self.api.boot_binding() == self.boot, 'supervisor_incarnation_changed')
        need(self.api.wait(self.process, 0) == 258, 'worker_exited')
        need(self.api.identity(self.process, self.pid) == self.identity, 'worker_handle_identity')
        need(self.api.job_processes(self.job) == (self.pid,), 'worker_job_membership')
        return self.identity

    def binding_bytes(self):
        self.check_live()
        return canonical({'kind': 'BEN01_OWNED_WORKER_V1', 'supervisor_incarnation': self.boot,
            'process': self.identity.descriptor(), 'script': self.source_pin.script,
            'executable_sha256': self.source_pin.executable_sha256, 'source_sha256': self.source_pin.source_sha256})

    def stop_once(self, budget_ms=10000):
        uint(budget_ms, 10000); need(budget_ms > 0, 'worker_stop_budget')
        need(not self.stop_attempted, 'worker_stop_consumed'); self.stop_attempted = True
        errors = []; confirmed = self.process is None
        if self.process is not None:
            try:
                state = self.api.wait(self.process, 0)
                need(state in (0, 258), 'worker_wait_unknown')
                if state == 258:
                    # Handle came directly from our CreateProcess call even if identity capture failed.
                    self.api.terminate(self.process)
                    state = self.api.wait(self.process, budget_ms)
                confirmed = state == 0
                need(confirmed, 'worker_stop_unconfirmed')
            except Exception as exc: errors.append(exc)
        for attr in ('job', 'process'):
            h = getattr(self, attr); setattr(self, attr, None)
            if h is not None:
                try: self.api.close(h)
                except Exception as exc: errors.append(exc)
        self.closed = True
        if errors: raise BenignError('worker_retirement_or_close_unknown') from errors[0]
        return confirmed

    def close_pipes(self):
        # Caller must join/cancel its pipe pump first. Never close a handle in use by that thread.
        errors = []
        for attr in ('child_read', 'child_write', 'input_write', 'output_read'):
            h = getattr(self, attr); setattr(self, attr, None)
            if h is not None:
                try: self.api.close(h)
                except Exception as exc: errors.append(exc)
        if errors: raise BenignError('worker_pipe_close_unknown') from errors[0]


def create_owned_worker(source_pin, permit=None):
    require_benign_run_authority(permit)
    # The future admitted context must hold verified executable/source snapshots across CreateProcess.
    # This constructor does not read a caller-provided approved flag and has no source-only issuer.
    return _OwnedWorker(_WinProcessApi(permit), source_pin)


class _BlockingPipeChannel:
    """Single I/O-thread/child use only. Never called directly by the watchdog."""
    def __init__(self, api, read_handle, write_handle):
        need(read_handle and write_handle and read_handle != write_handle, 'pipe_handle_pair')
        self.api, self.read_handle, self.write_handle = api, read_handle, write_handle

    def receive_bounded(self, cap):
        uint(cap, 1048580); need(cap > 0, 'pipe_read_cap')
        return self.api.pipe_read(self.read_handle, min(cap, 65536))

    def send_bounded(self, data):
        need(type(data) is bytes and 0 < len(data) <= 1048580, 'pipe_write_cap')
        for offset in range(0, len(data), 65536):
            self.api.pipe_write(self.write_handle, data[offset:offset + 65536])
