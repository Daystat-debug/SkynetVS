"""Explicit Windows x64 SCM bindings. Import performs NO WinDLL/SCM calls.

The normal constructor ALWAYS hits runtime_gate before loading a library in V1.
The fake-functions constructor exists solely for offline ABI/marshalling tests.
No service configuration repair, control, process enumeration or termination APIs.
"""
from __future__ import annotations
import ctypes as C
import hashlib
import time
from scm01_contract import (Reply, LabCapsule, need, ContractError, SERVICE_NAME, ACCOUNT,
                            CONFIG_BYTES, SECURITY_BYTES, status_from_raw)
import runtime_gate

U32, BOOL, PTR = C.c_uint32, C.c_int32, C.c_void_p
WSTR, PU32 = C.c_wchar_p, C.POINTER(U32)
SC_MANAGER_CONNECT_CREATE = 0x0003
SERVICE_READ_CREATE = 0x00030015  # READ_CONTROL | DELETE | QUERY_CONFIG | QUERY_STATUS | START
SERVICE_PROBE = 0x0004

class SERVICE_STATUS_PROCESS(C.Structure):
    _fields_ = [(n, U32) for n in ('dwServiceType', 'dwCurrentState', 'dwControlsAccepted',
                 'dwWin32ExitCode', 'dwServiceSpecificExitCode', 'dwCheckPoint', 'dwWaitHint',
                 'dwProcessId', 'dwServiceFlags')]
class QUERY_SERVICE_CONFIGW(C.Structure):
    _fields_ = [('dwServiceType', U32), ('dwStartType', U32), ('dwErrorControl', U32),
                ('lpBinaryPathName', PTR), ('lpLoadOrderGroup', PTR), ('dwTagId', U32),
                ('lpDependencies', PTR), ('lpServiceStartName', PTR), ('lpDisplayName', PTR)]
class SC_ACTION(C.Structure):
    _fields_ = [('Type', U32), ('Delay', U32)]
class SERVICE_FAILURE_ACTIONSW(C.Structure):
    _fields_ = [('dwResetPeriod', U32), ('lpRebootMsg', PTR), ('lpCommand', PTR),
                ('cActions', U32), ('lpsaActions', PTR)]
class SERVICE_TRIGGER_INFO(C.Structure):
    _fields_ = [('cTriggers', U32), ('pTriggers', PTR), ('pReserved', PTR)]
class SERVICE_DELAYED_AUTO_START_INFO(C.Structure):
    _fields_ = [('fDelayedAutostart', BOOL)]
class SERVICE_FAILURE_ACTIONS_FLAG(C.Structure):
    _fields_ = [('fFailureActionsOnNonCrashFailures', BOOL)]
class SERVICE_SID_INFO(C.Structure):
    _fields_ = [('dwServiceSidType', U32)]
class SERVICE_REQUIRED_PRIVILEGES_INFOW(C.Structure):
    _fields_ = [('pmszRequiredPrivileges', PTR)]
class SERVICE_LAUNCH_PROTECTED_INFO(C.Structure):
    _fields_ = [('dwLaunchProtected', U32)]

STRUCTURES = (SERVICE_STATUS_PROCESS, QUERY_SERVICE_CONFIGW, SC_ACTION,
              SERVICE_FAILURE_ACTIONSW, SERVICE_TRIGGER_INFO, SERVICE_DELAYED_AUTO_START_INFO,
              SERVICE_FAILURE_ACTIONS_FLAG, SERVICE_SID_INFO, SERVICE_REQUIRED_PRIVILEGES_INFOW,
              SERVICE_LAUNCH_PROTECTED_INFO)
# BOOL/SC_HANDLE last error is copied immediately, before timestamp/serialization.
SIGNATURES = {
    'OpenSCManagerW': (PTR, [WSTR, WSTR, U32]),
    'OpenServiceW': (PTR, [PTR, WSTR, U32]),
    'CreateServiceW': (PTR, [PTR, WSTR, WSTR, U32, U32, U32, U32, WSTR, WSTR, PU32, WSTR, WSTR, WSTR]),
    'StartServiceW': (BOOL, [PTR, U32, C.POINTER(WSTR)]),
    'QueryServiceStatusEx': (BOOL, [PTR, C.c_int32, PTR, U32, PU32]),
    'QueryServiceConfigW': (BOOL, [PTR, PTR, U32, PU32]),
    'QueryServiceConfig2W': (BOOL, [PTR, U32, PTR, U32, PU32]),
    'QueryServiceObjectSecurity': (BOOL, [PTR, U32, PTR, U32, PU32]),
    'DeleteService': (BOOL, [PTR]),
    'CloseServiceHandle': (BOOL, [PTR]),
}


def abi_layouts():
    return {t.__name__: {'size': C.sizeof(t), 'alignment': C.alignment(t),
                         'offsets': {n: getattr(t, n).offset for n, _ in t._fields_}} for t in STRUCTURES}


def bounded_offset(raw, base, pointer, length, alignment=1):
    need(type(pointer) is int and base <= pointer <= base + len(raw), 'pointer outside returned buffer')
    off = pointer - base
    need(off % alignment == 0 and 0 <= length <= len(raw) - off, 'misaligned/truncated buffer field')
    return off


def read_wstring(raw, base, pointer):
    if pointer is None or pointer == 0:
        return ''
    off = bounded_offset(raw, base, pointer, 2, 2)
    for end in range(off, len(raw) - 1, 2):
        if raw[end:end+2] == b'\0\0':
            return raw[off:end].decode('utf-16-le', 'strict')
    raise ContractError('unterminated bounded UTF16')


def read_multisz(raw, base, pointer):
    if not pointer:
        return []
    off = bounded_offset(raw, base, pointer, 2, 2)
    result = []
    while off < len(raw) - 1:
        value = read_wstring(raw, base, base + off)
        if not value:
            return result
        result.append(value)
        need(len(result) <= 256, 'multi-SZ item budget')
        off += len(value.encode('utf-16-le')) + 2
    raise ContractError('unterminated bounded multi-SZ')


def decode_config(raw, base):
    need(len(raw) >= C.sizeof(QUERY_SERVICE_CONFIGW), 'config header truncated')
    h = QUERY_SERVICE_CONFIGW.from_buffer_copy(raw)
    return {'service_type': int(h.dwServiceType), 'start_type': int(h.dwStartType),
            'error_control': int(h.dwErrorControl), 'binary_path': read_wstring(raw, base, h.lpBinaryPathName),
            'load_order_group': read_wstring(raw, base, h.lpLoadOrderGroup), 'tag_id': int(h.dwTagId),
            'dependencies': read_multisz(raw, base, h.lpDependencies),
            'account': read_wstring(raw, base, h.lpServiceStartName),
            'display_name': read_wstring(raw, base, h.lpDisplayName)}


def decode_optional(level, raw, base):
    if level == 2:
        h = SERVICE_FAILURE_ACTIONSW.from_buffer_copy(raw)
        count = int(h.cActions)
        need(count <= 256, 'recovery action count bound')
        actions = []
        if count:
            off = bounded_offset(raw, base, h.lpsaActions, count * 8, 4)
            for i in range(count):
                a = SC_ACTION.from_buffer_copy(raw, off + i * 8)
                actions.append({'type': int(a.Type), 'delay': int(a.Delay)})
        return {'failure_reset_period': int(h.dwResetPeriod), 'failure_actions': actions,
                'failure_command': read_wstring(raw, base, h.lpCommand),
                'reboot_message': read_wstring(raw, base, h.lpRebootMsg)}
    if level == 3:
        return {'delayed_auto_start': int(SERVICE_DELAYED_AUTO_START_INFO.from_buffer_copy(raw).fDelayedAutostart)}
    if level == 4:
        return {'failure_noncrash': int(SERVICE_FAILURE_ACTIONS_FLAG.from_buffer_copy(raw).fFailureActionsOnNonCrashFailures)}
    if level == 5:
        return {'sid_type': int(SERVICE_SID_INFO.from_buffer_copy(raw).dwServiceSidType)}
    if level == 6:
        h = SERVICE_REQUIRED_PRIVILEGES_INFOW.from_buffer_copy(raw)
        return {'required_privileges': read_multisz(raw, base, h.pmszRequiredPrivileges)}
    if level == 8:
        h = SERVICE_TRIGGER_INFO.from_buffer_copy(raw)
        return {'trigger_count': int(h.cTriggers)}  # Nonzero is rejected without dereferencing triggers.
    if level == 12:
        return {'launch_protected': int(SERVICE_LAUNCH_PROTECTED_INFO.from_buffer_copy(raw).dwLaunchProtected)}
    raise ContractError('unapproved config level')


class WinScmApi:
    def __init__(self, authority=None):
        runtime_gate.require_runtime_authority(authority)  # V1 ALWAYS refuses here.
        need(C.sizeof(PTR) == 8 and C.sizeof(C.c_wchar) == 2, 'Windows x64 ABI required')
        dll = C.WinDLL('advapi32.dll', use_last_error=True, winmode=0x800)
        functions = {}
        for name, (result, arguments) in SIGNATURES.items():
            f = getattr(dll, name)
            f.restype, f.argtypes = result, arguments
            functions[name] = f
        self._initialize(functions, C.get_last_error)

    @classmethod
    def _from_bound_functions_for_offline_tests(cls, functions, get_last_error):
        """No loader/OS calls; not a runtime authorization path of controller_main."""
        obj = object.__new__(cls)
        obj._initialize(functions, get_last_error)
        return obj

    def _initialize(self, functions, last_error):
        need(set(functions) == set(SIGNATURES), 'exact Win32 function table')
        self.functions, self.last_error = functions, last_error
        self.handles = []
        self.created_handle = None
        self.used = dict(create=0, start=0, delete=0)
        self.manager_open_attempted = False

    def _invoke(self, name, args):
        before = time.monotonic_ns()
        value = self.functions[name](*args)
        error = self.last_error() if not value else None
        return value, error, {'operation': name, 'started_monotonic_ns': before,
                              'finished_monotonic_ns': time.monotonic_ns(), 'observed_utc_ns': time.time_ns(),
                              'ok': bool(value), 'winerror': error}

    def _register(self, handle, role):
        self.handles.append({'handle': handle, 'role': role, 'close_attempted': False, 'closed': False})
        return handle

    def _close_row(self, row):
        need(not row['close_attempted'], 'CloseServiceHandle retry forbidden')
        row['close_attempted'] = True
        v, e, obs = self._invoke('CloseServiceHandle', (row['handle'],))
        row['closed'] = bool(v)
        return Reply(bool(v), bool(v), e, obs)

    def open_manager(self):
        need(not self.manager_open_attempted, 'OpenSCManager budget')
        self.manager_open_attempted = True
        v, e, obs = self._invoke('OpenSCManagerW', (None, None, SC_MANAGER_CONNECT_CREATE))
        if v:
            self._register(v, 'manager')
        return Reply(bool(v), v, e, obs)

    def probe(self, manager):
        v, e, obs = self._invoke('OpenServiceW', (manager, SERVICE_NAME, SERVICE_PROBE))
        if not v:
            return Reply(False, None, e, obs)
        self._register(v, 'probe')
        close = self._close_row(self.handles[-1])
        need(close.ok, 'probe handle closure failed; presence is not absence')
        obs['close'] = close.observation
        return Reply(True, 'PRESENT', None, obs)

    def _budget(self, action, handle=None):
        need(self.used[action] == 0, action + ': backend operation already attempted')
        if handle is not None:
            need(self.created_handle is not None and handle == self.created_handle,
                 'mutation requires retained creation handle; never adopt')
            need(any(x['handle'] == handle and x['role'] == 'created' and not x['close_attempted'] for x in self.handles),
                 'created service handle no longer owned')
        self.used[action] = 1

    def create_service(self, manager, capsule: LabCapsule):
        capsule.validate_shape()
        self._budget('create')
        v, e, obs = self._invoke('CreateServiceW', (manager, SERVICE_NAME, SERVICE_NAME, SERVICE_READ_CREATE,
                 16, 3, 0, capsule.binary_command, None, None, None, ACCOUNT, None))
        if v:
            self.created_handle = self._register(v, 'created')
        return Reply(bool(v), v, e, obs)

    def start_service(self, handle):
        self._budget('start', handle)
        v, e, obs = self._invoke('StartServiceW', (handle, 0, None))
        return Reply(bool(v), bool(v), e, obs)

    def delete_service(self, handle):
        self._budget('delete', handle)
        v, e, obs = self._invoke('DeleteService', (handle,))
        return Reply(bool(v), bool(v), e, obs)

    def status(self, handle):
        buf, needed = C.create_string_buffer(36), U32(0)
        v, e, obs = self._invoke('QueryServiceStatusEx', (handle, 0, C.byref(buf), 36, C.byref(needed)))
        obs.update(allocated_bytes=36, pcbBytesNeeded_observed=int(needed.value),
                   raw_hex=bytes(buf).hex() if v else None,
                   size_semantics='pcbBytesNeeded is only a required size on ERROR_INSUFFICIENT_BUFFER; not success length')
        return Reply(bool(v), status_from_raw(bytes(buf)) if v else None, e, obs)

    def _config_buffer(self, name, handle, level=None, capacity=CONFIG_BYTES):
        buf, needed = C.create_string_buffer(capacity), U32(0)
        args = (handle, C.byref(buf), capacity, C.byref(needed)) if level is None else (handle, level, C.byref(buf), capacity, C.byref(needed))
        v, e, obs = self._invoke(name, args)
        obs.update(level=level, allocated_bytes=capacity, buffer_base=C.addressof(buf),
                   pcbBytesNeeded_observed=int(needed.value), raw_hex=bytes(buf).hex() if v else None,
                   success_length_not_inferred_from_pcbBytesNeeded=True)
        # Full zero-initialized buffer captured. No pointer is followed outside it; no resizing/retry.
        return Reply(bool(v), (bytes(buf), C.addressof(buf)) if v else None, e, obs)

    def config(self, handle):
        observations = []
        r = self._config_buffer('QueryServiceConfigW', handle)
        observations.append(r.observation)
        if not r.ok:
            return Reply(False, None, r.winerror, {'queries': observations})
        try:
            config = decode_config(*r.value)
            for level in (2, 3, 4, 5, 6, 8, 12):
                r = self._config_buffer('QueryServiceConfig2W', handle, level)
                observations.append(r.observation)
                if not r.ok:
                    return Reply(False, None, r.winerror, {'queries': observations})
                config.update(decode_optional(level, *r.value))
            r = self._config_buffer('QueryServiceObjectSecurity', handle, 7, SECURITY_BYTES)  # OWNER|GROUP|DACL; no SACL/privilege.
            observations.append(r.observation)
            if not r.ok:
                return Reply(False, None, r.winerror, {'queries': observations})
            config['security_sha256'] = hashlib.sha256(r.value[0]).hexdigest()
            config['security_buffer_bytes'] = len(r.value[0])
            return Reply(True, config, None, {'queries': observations, 'normalized_config': config,
                                           'ACL_trust_accepted': False, 'token_profile_accepted': False})
        except (ValueError, UnicodeError, ContractError) as exc:
            return Reply(False, None, None, {'queries': observations, 'decode_error': type(exc).__name__ + ': ' + str(exc)})

    def close_services(self):
        observations, errors = [], []
        for row in reversed(self.handles):
            if row['role'] == 'manager':
                continue
            if not row['close_attempted']:
                try:
                    r = self._close_row(row)
                    observations.append(r.observation)
                except BaseException as exc:
                    errors.append(type(exc).__name__ + ': ' + str(exc))
            if not row['closed']:
                errors.append('unconfirmed ' + row['role'] + ' handle closure')
        return Reply(not errors, not errors, None, {'closures': observations, 'errors': errors})

    def close_all(self):
        observations, errors = [], []
        for row in reversed(self.handles):
            if not row['close_attempted']:
                try:
                    r = self._close_row(row)
                    observations.append(r.observation)
                except BaseException as exc:
                    errors.append(type(exc).__name__ + ': ' + str(exc))
            if not row['closed']:
                errors.append('unconfirmed ' + row['role'] + ' handle closure')
        return Reply(not errors, not errors, None, {'closures': observations, 'errors': errors})
