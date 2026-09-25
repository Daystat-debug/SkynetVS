"""Pure HWA01 data contracts. Validation is not authorization or a filesystem check."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from pathlib import PureWindowsPath
import re

BASE_COMMIT = 'e3bedde8f946d96b8685be2716ea523d5c0d6e31'
TRUST_MODEL = 'TRUSTED_LOCAL_CPYTHON312_HOST_ONLY_V1'
PROFILE = 'HWA01_FIXED_SHA256_PROBE_V1'
FIXED_PAYLOAD = b'SkynetVS HWA01 fixed data probe. Never execute this input.\n'
FRAME_LIMIT = 8192
TOTAL_NS = 30_000_000_000
STARTUP_NS = 10_000_000_000
EXCHANGE_NS = 5_000_000_000
CLEANUP_NS = 10_000_000_000
# CREATE_SUSPENDED | DETACHED_PROCESS | CREATE_UNICODE_ENVIRONMENT |
# EXTENDED_STARTUPINFO_PRESENT. The separate JOB_LIST attribute is mandatory.
CREATE_FLAGS = 0x0008040c


class ContractError(ValueError):
    pass


def need(value: bool, code: str) -> None:
    if value is not True:
        raise ContractError(code)


def uint(value: int, maximum: int = (1 << 63) - 1, minimum: int = 0) -> int:
    need(type(value) is int and minimum <= value <= maximum, 'integer_range_or_type')
    return value


def hex_digest(value: str, length: int = 64) -> str:
    need(type(value) is str and len(value) == length and
         all(ch in '0123456789abcdef' for ch in value), 'hex_digest')
    return value


def windows_path(value: str) -> str:
    """Finite lexical policy only: actual identity must be observed through retained handles."""
    need(type(value) is str and 3 < len(value) <= 240, 'path_type_or_length')
    need(re.match(r'^[A-Z]:\\', value) is not None and '/' not in value, 'local_absolute_path')
    need(not any(ord(ch) < 32 or 0xd800 <= ord(ch) <= 0xdfff for ch in value), 'path_character')
    parts = value[3:].split('\\')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{a}{n}' for a in ('COM', 'LPT') for n in range(1, 10)}
    for part in parts:
        need(bool(part) and part not in ('.', '..') and not part.endswith((' ', '.')),
             'path_component')
        need(not any(ch in part for ch in ':*?"<>|'), 'path_character')
        need(part.split('.')[0].upper() not in reserved, 'reserved_path_component')
    need(str(PureWindowsPath(value)) == value, 'path_not_canonical')
    return value


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')


def digest(value: bytes) -> str:
    need(type(value) is bytes, 'digest_bytes')
    return sha256(value).hexdigest()


@dataclass(frozen=True, slots=True)
class FilePin:
    path: str
    size: int
    sha256: str

    def validate(self) -> 'FilePin':
        windows_path(self.path)
        uint(self.size, 32 * 1024 * 1024, 1)
        hex_digest(self.sha256)
        return self


@dataclass(frozen=True, slots=True)
class RuntimeSelection:
    executable: FilePin
    python_dll: FilePin
    version: str = '3.12.10'
    trust_model: str = TRUST_MODEL

    def validate(self) -> 'RuntimeSelection':
        need(type(self.executable) is FilePin and type(self.python_dll) is FilePin, 'runtime_pin_types')
        self.executable.validate()
        self.python_dll.validate()
        exe, dll = PureWindowsPath(self.executable.path), PureWindowsPath(self.python_dll.path)
        need(exe.name == 'python.exe' and dll.name == 'python312.dll', 'runtime_names')
        need(str(exe.parent).casefold() == str(dll.parent).casefold(), 'runtime_directory')
        need(not any(p.casefold() in ('.venv', 'venv', 'scripts') for p in exe.parts),
             'venv_redirector_not_direct_runtime')
        need(self.version == '3.12.10' and self.trust_model == TRUST_MODEL, 'runtime_profile')
        return self


@dataclass(frozen=True, slots=True)
class Plan:
    run_id: str
    nonce: str
    runtime: RuntimeSelection
    entrypoint: FilePin
    source_manifest_sha256: str
    base_commit: str = BASE_COMMIT
    profile: str = PROFILE

    def validate(self) -> 'Plan':
        hex_digest(self.run_id, 32)
        hex_digest(self.nonce)
        hex_digest(self.source_manifest_sha256)
        need(type(self.runtime) is RuntimeSelection and type(self.entrypoint) is FilePin, 'plan_types')
        self.runtime.validate()
        self.entrypoint.validate()
        need(PureWindowsPath(self.entrypoint.path).name == 'host_worker_entry.py', 'fixed_entrypoint')
        need(self.base_commit == BASE_COMMIT and self.profile == PROFILE, 'fixed_profile')
        return self

    def descriptor(self) -> dict:
        self.validate()
        return {'kind': 'HWA01_PLAN_DATA_V1', **asdict(self),
                'operation': 'SHA256_FIXED_DATA', 'probe_sha256': digest(FIXED_PAYLOAD),
                'probe_bytes': len(FIXED_PAYLOAD),
                'native_authority': False, 'sandbox_authority': False}

    def fingerprint(self) -> str:
        return digest(canonical(self.descriptor()))


@dataclass(frozen=True, slots=True)
class Identity:
    pid: int
    created: int
    image: str
    session_id: int
    authentication_id: int
    user_sid: str

    def validate(self) -> 'Identity':
        uint(self.pid, 0xffffffff, 1)
        uint(self.created, (1 << 64) - 1, 1)
        windows_path(self.image)
        uint(self.session_id, 0xffffffff)
        uint(self.authentication_id, (1 << 64) - 1)
        need(type(self.user_sid) is str and len(self.user_sid) <= 184 and
             re.fullmatch(r'S-1-[0-9]+(?:-[0-9]+){1,15}', self.user_sid) is not None, 'sid_shape')
        return self


@dataclass(frozen=True, slots=True)
class JobLimits:
    active_processes: int = 1
    process_memory: int = 512 * 1024**2
    job_memory: int = 768 * 1024**2
    kill_on_close: bool = True
    breakaway: bool = False
    silent_breakaway: bool = False

    def validate(self) -> 'JobLimits':
        need(type(self.active_processes) is int and self.active_processes == 1, 'job_active_limit')
        need(type(self.process_memory) is int and self.process_memory == 512 * 1024**2,
             'job_process_memory')
        need(type(self.job_memory) is int and self.job_memory == 768 * 1024**2, 'job_memory')
        need(self.kill_on_close is True and self.breakaway is False and
             self.silent_breakaway is False, 'job_flags')
        return self
