"""SCM01 source contract. Pure data/evaluation; no Windows or filesystem calls."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import PureWindowsPath
import re
import struct

SERVICE_NAME = 'SkynetVSGuard'
ACCOUNT = r'NT SERVICE\SkynetVSGuard'
GUARD_BYTES = 882176
GUARD_SHA256 = '66736793b396c1c5682ce149df199db34d63499c916d299aa6106f11b3f68fdb'
TERMINAL = (16, 1, 0, 1066, 78, 0, 0)
STATUS_NAMES = ('service_type', 'current_state', 'controls_accepted', 'win32_exit',
                'specific_exit', 'checkpoint', 'wait_hint', 'process_id', 'service_flags')
OBSERVE_SECONDS = 30.0
DELETE_SECONDS = 10.0
POLL_SECONDS = 0.1
MAX_STATUS_POLLS = 301
MAX_DELETE_POLLS = 101
CONFIG_BYTES = 8192
SECURITY_BYTES = 8192

class ContractError(RuntimeError):
    pass

class RuntimeClosed(RuntimeError):
    pass

def need(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)

@dataclass(frozen=True)
class LabCapsule:
    """Input for an eventual signed-off runner, NOT a minted runtime authority.

    V1's public entrypoint and native-backend constructor remain closed regardless
    of these fields. Guest/path/ACL/recovery evidence must be verified by the later
    capsule issuer; a dictionary of assertions is not independent attestation.
    """
    run_id: str
    guest_id: str
    image_path: str
    authorization_sha256: str
    environment_evidence_sha256: str
    guard_bytes: int = GUARD_BYTES
    guard_sha256: str = GUARD_SHA256

    def validate_shape(self) -> None:
        need(type(self.run_id) is str and re.fullmatch('[a-f0-9]{32}', self.run_id) is not None, 'run ID')
        need(type(self.guest_id) is str and 1 <= len(self.guest_id) <= 128, 'named guest required')
        for s in (self.authorization_sha256, self.environment_evidence_sha256):
            need(type(s) is str and re.fullmatch('[a-f0-9]{64}', s) is not None, 'capsule evidence identity')
        need(type(self.guard_bytes) is int and self.guard_bytes == GUARD_BYTES and self.guard_sha256 == GUARD_SHA256,
             'unchanged V3 only')
        p = PureWindowsPath(self.image_path)
        need(type(self.image_path) is str and re.fullmatch('[A-Za-z]:', p.drive) is not None and p.is_absolute(),
             'guest-local absolute drive path only')
        need(p.name == 'Guard.exe' and str(p) == self.image_path, 'canonical Guard.exe path')
        need(not any(c in self.image_path for c in '\x00\r\n"'), 'invalid image path')
        for part in p.parts[1:]:
            need(part not in ('.', '..', '') and not part.endswith(('.', ' ')), 'unsafe component')
            need(not any(c in part for c in ':*?<>|') and all(ord(c) >= 32 for c in part), 'unsafe component')
        need(not any(s in self.image_path.casefold() for s in ('\\downloads\\', '\\lifecyclev1\\', '\\trustedhost\\releases\\')),
             'not a production/downloads deployment path')

    @property
    def binary_command(self) -> str:
        self.validate_shape()
        return '"' + self.image_path + '"'

@dataclass(frozen=True)
class Reply:
    ok: bool
    value: object = None
    winerror: int | None = None
    observation: dict | None = None

    def check(self, operation: str) -> object:
        need(type(self.ok) is bool, operation + ': invalid BOOL observation')
        if not self.ok:
            raise ContractError(f'{operation}: Win32 error {self.winerror}; no retry')
        return self.value


def status_from_raw(raw: bytes) -> dict:
    need(type(raw) is bytes and len(raw) == 36, 'SERVICE_STATUS_PROCESS requires 36 bytes')
    return dict(zip(STATUS_NAMES, struct.unpack('<9I', raw)))


def status_tuple(row: dict) -> tuple:
    need(type(row) is dict and set(row) == set(STATUS_NAMES), 'status exact fields')
    need(all(type(row[k]) is int and 0 <= row[k] <= 0xffffffff for k in STATUS_NAMES), 'status DWORDs')
    return tuple(row[k] for k in STATUS_NAMES[:7])


def prestart_status(row: dict) -> None:
    t = status_tuple(row)
    need(t[0:3] == (16, 1, 0), 'new service must be OWN_PROCESS / STOPPED / controls=0')
    need(t != TERMINAL, 'terminal refusal already present before our start; ambiguous observation')


def terminal_decision(row: dict) -> str:
    t = status_tuple(row)
    need(t[0] == 16 and t[2] == 0, 'unexpected type/accepted controls')
    if t[1] == 2:
        return 'PENDING'
    need(t == TERMINAL, 'unexpected terminal/state tuple; RUNNING is not a valid outcome')
    return 'REFUSAL_OBSERVED'


def verify_config(config: dict, capsule: LabCapsule) -> None:
    expected = {'service_type': 16, 'start_type': 3, 'error_control': 0,
                'binary_path': capsule.binary_command, 'account': ACCOUNT,
                'display_name': SERVICE_NAME, 'dependencies': [], 'load_order_group': '', 'tag_id': 0}
    need(type(config) is dict, 'configuration object')
    for key, value in expected.items():
        need(type(config.get(key)) is type(value) and config[key] == value, 'configuration mismatch: ' + key)
    need(config.get('failure_actions') == [] and config.get('failure_command') == '' and config.get('reboot_message') == '',
         'automatic recovery actions forbidden')
    need(type(config.get('trigger_count')) is int and config['trigger_count'] == 0, 'triggers forbidden')
    need(type(config.get('delayed_auto_start')) is int and config['delayed_auto_start'] == 0, 'delayed start forbidden')
    need(type(config.get('launch_protected')) is int and config['launch_protected'] == 0, 'unexpected launch protection')
    # Defaults are observed and compared for drift, never rewritten to a production profile.
    need(type(config.get('sid_type')) is int, 'SID type observation missing')
    need(type(config.get('required_privileges')) is list and all(type(x) is str for x in config['required_privileges']),
         'required privileges observation missing')
    need(type(config.get('failure_noncrash')) is int and config['failure_noncrash'] in (0, 1), 'failure flag observation missing')
    need(type(config.get('security_sha256')) is str and re.fullmatch('[a-f0-9]{64}', config['security_sha256']) is not None,
         'service security descriptor observation missing')
