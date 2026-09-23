"""BEN01 wire: pure canonical codec. No authority, filesystem or native loading."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import re

WIRE = {'constant_fields': {'schema': 'SKYNETVS_SCM01_WSB01_BENIGN_V1', 'version': 1, 'profile': 'SCM01-WSB01', 'experiment': 'SCM01-WSB01-BEN01', 'evidence_domain': 'BENIGN_SANDBOX_LAB', 'scenario': 'fixed_digest_roundtrip', 'guard': None}, 'message_fields': {'request': ['capsule_sha256', 'evidence_domain', 'experiment', 'grant_id', 'guard', 'kind', 'layout_sha256', 'nonce', 'policy_sha256', 'profile', 'run_id', 'runtime_sha256', 'scenario', 'schema', 'schema_sha256', 'scm_budget', 'source_sha256', 'version', 'wsb_sha256'], 'ready': ['capsule_sha256', 'evidence_domain', 'experiment', 'guest_runtime', 'kind', 'layout_sha256', 'nonce', 'policy_sha256', 'profile', 'public_key_blob_hex', 'request_sha256', 'run_id', 'runtime_sha256', 'schema', 'schema_sha256', 'source_sha256', 'version', 'wsb_sha256'], 'ready_commit': ['evidence_domain', 'experiment', 'kind', 'nonce', 'profile', 'ready_sha256', 'ready_signature_sha256', 'run_id', 'schema', 'version'], 'authorization': ['evidence_domain', 'experiment', 'grant_id', 'kind', 'nonce', 'profile', 'public_key_sha256', 'ready_sha256', 'ready_signature_sha256', 'request_sha256', 'run_id', 'scenario', 'schema', 'scm_budget', 'session_binding_sha256', 'version'], 'authorization_commit': ['authorization_sha256', 'evidence_domain', 'experiment', 'kind', 'nonce', 'profile', 'run_id', 'schema', 'version'], 'journal_record': ['data', 'event', 'evidence_domain', 'experiment', 'guest_monotonic_ns', 'kind', 'nonce', 'profile', 'run_id', 'schema', 'sequence', 'version'], 'terminal': ['authorization_commit_sha256', 'authorization_sha256', 'capsule_sha256', 'evidence_domain', 'experiment', 'journal_bytes', 'journal_records', 'journal_sha256', 'kind', 'layout_sha256', 'nonce', 'policy_sha256', 'profile', 'public_key_sha256', 'ready_sha256', 'request_sha256', 'response_sha256', 'result', 'run_id', 'runtime_sha256', 'schema', 'schema_sha256', 'session_binding_sha256', 'source_sha256', 'version', 'wsb_sha256'], 'terminal_commit': ['evidence_domain', 'experiment', 'journal_sha256', 'kind', 'nonce', 'profile', 'run_id', 'schema', 'terminal_sha256', 'terminal_signature_sha256', 'version'], 'failure': ['code', 'evidence_domain', 'experiment', 'kind', 'message', 'nonce', 'profile', 'run_id', 'schema', 'version']}, 'scalar_rules': {'ids': 'run_id/grant_id 32 lowercase hex; nonce 64 lowercase hex', 'sha256': '64 lowercase hex', 'version': 'exact int 1, not bool', 'counts': 'uint64 integers unless smaller explicit bound; not bool', 'public_key_blob_hex': '144 lowercase hex chars: 72-byte CNG P256 public blob', 'floats': 'forbidden', 'unknown_fields': 'forbidden', 'duplicate_keys': 'forbidden'}, 'encoding': 'ensure_ascii=True; recursive sort_keys=True; compact; exactly one LF; strict bounded parser', 'scm_budget_fields': {'create': 0, 'start': 0, 'delete': 0, 'control_service': 0, 'manual_guard_spawn': 0}, 'guest_runtime_fields': ['major', 'minor', 'micro', 'pointer_bits', 'isolated', 'no_site', 'dont_write_bytecode'], 'guest_runtime_evidence_warning': 'Self-report compared against fixed runtime descriptor; not independent OS provenance or host Python equality', 'journal_events': {'BEGIN': [], 'AUTHORIZATION_OBSERVED': ['authorization_sha256', 'authorization_commit_sha256'], 'BENIGN_COMPLETED': ['response_sha256'], 'FINAL': ['result'], 'ERROR': ['code']}, 'journal_success_order': ['BEGIN', 'AUTHORIZATION_OBSERVED', 'BENIGN_COMPLETED', 'FINAL'], 'journal_success_result': 'BENIGN_TASK_COMPLETED', 'journal_failure_result': 'BENIGN_TASK_FAILED', 'shutdown': 'Bootstrap requests one fixed shutdown only after guest interpreter returns; terminal/journal do not falsely attest shutdown requested or VM disposal. Host observes retirement independently.', 'hash_scopes': {'policy_sha256': 'SHA256(canonical static policy object), no embedded computed policy hash', 'schema_sha256': 'SHA256(canonical static wire descriptor), no embedded computed schema hash', 'source_sha256': 'SHA256(canonical sorted executable-source manifest for .py/.ps1 files only); excludes metadata manifests to avoid self-reference', 'capsule_sha256': 'SHA256(canonical sorted exact guest-code member manifest); excludes manifest itself and run/request data', 'runtime_sha256': 'SHA256(pinned retained runtime content manifest); fixed runtime identities not guessed from version', 'layout_sha256': 'SHA256(canonical role paths/settings/config hash descriptor); wsb config excludes request hash', 'response_sha256': 'SHA256(fixed roundtrip domain bytes + exact request bytes)'}, 'signature': {'algorithm': 'ECDSA_P256_SHA256_CNG', 'ready_domain': 'SKYNETVS/SCM01-WSB01/BENIGN_SANDBOX_LAB/READY/V1\x00', 'terminal_domain': 'SKYNETVS/SCM01-WSB01/BENIGN_SANDBOX_LAB/TERMINAL/V1\x00', 'api_input': 'SHA256(domain_bytes + exact_payload_bytes), one prehash', 'public_blob_bytes': 72, 'raw_signature_bytes': 64, 'host_verdict_requires_real_provider': True}}
POLICY = {'profile': 'SCM01-WSB01-BEN01', 'backend': 'traditional_wsb_logoncommand_v1', 'guest_identity': 'existing WDAGUtilityAccount; no SYSTEM task/account/ACL mutation', 'host_processes': {'supervisor': 1, 'artifact_worker': 1, 'worker_job_active_process_limit': 1, 'worker_creation_flags': ['CREATE_SUSPENDED', 'DETACHED_PROCESS', 'CREATE_UNICODE_ENVIRONMENT'], 'sandbox_in_worker_job': False, 'launch_budget': 1}, 'retirement': {'basis': 'EXCLUSIVE_HOST_KNOWN_PROCESSSET_V1', 'hypervisor_disposal_proven': False, 'same_user_host_adversary_protection': False, 'requires_exclusive_operator_session': True, 'required_empty_complete_scans': 3, 'minimum_scan_spacing_ms': 250, 'foreign_pid_cleanup': False, 'force_implies_failure': True}, 'budgets': {'ready_seconds': 120, 'guest_authorization_seconds': 90, 'terminal_after_publication_seconds': 60, 'shutdown_grace_seconds': 45, 'host_absolute_seconds': 300, 'cleanup_seconds': 10}, 'limits': {'request': 32768, 'ready': 65536, 'authorization': 16384, 'completion_marker': 4096, 'journal': 65536, 'journal_records': 16, 'record': 8192, 'terminal': 65536, 'failure': 16384, 'signature': 64, 'accepted_raw_snapshot': 262144}, 'required_output': ['ready.json', 'ready.sig', 'ready.commit.json', 'journal.jsonl', 'terminal.json', 'terminal.sig', 'terminal.commit.json'], 'optional_failure': 'failure.json', 'real_scm_budget': 0, 'guard_payload': None, 'disk_quota_claimed': False}

PROFILE = 'SCM01-WSB01'
EXPERIMENT = 'SCM01-WSB01-BEN01'
DOMAIN = 'BENIGN_SANDBOX_LAB'
FAKE_DOMAIN = 'OFFLINE_MODEL'
SCHEMA = 'SKYNETVS_SCM01_WSB01_BENIGN_V1'
ROUNDTRIP_DOMAIN = b'SKYNETVS/SCM01-WSB01-BEN01/ROUNDTRIP/V1\0'
READY_DOMAIN = b'SKYNETVS/SCM01-WSB01/BENIGN_SANDBOX_LAB/READY/V1\0'
TERMINAL_DOMAIN = b'SKYNETVS/SCM01-WSB01/BENIGN_SANDBOX_LAB/TERMINAL/V1\0'
ZERO_BUDGET = {'create': 0, 'start': 0, 'delete': 0,
               'control_service': 0, 'manual_guard_spawn': 0}
RUNTIME_FLAGS = {'major': 3, 'minor': 13, 'micro': 15, 'pointer_bits': 64,
                 'isolated': True, 'no_site': True, 'dont_write_bytecode': True}
SUCCESS_FILES = ('ready.json', 'ready.sig', 'ready.commit.json', 'journal.jsonl',
                 'terminal.json', 'terminal.sig', 'terminal.commit.json')
CAPS = {'request': 32768, 'ready': 65536, 'authorization': 16384,
        'ready_commit': 4096, 'authorization_commit': 4096,
        'terminal_commit': 4096, 'journal_record': 8192,
        'terminal': 65536, 'failure': 16384}
FILE_CAPS = {'ready.json': 65536, 'ready.sig': 64, 'ready.commit.json': 4096,
             'journal.jsonl': 65536, 'terminal.json': 65536,
             'terminal.sig': 64, 'terminal.commit.json': 4096, 'failure.json': 16384}
COMMON = {'schema': SCHEMA, 'version': 1, 'profile': PROFILE,
          'experiment': EXPERIMENT, 'evidence_domain': DOMAIN}


class BenignError(ValueError):
    """Stable fail-closed code. Native wrappers preserve original error as cause."""


def need(condition, code):
    if not condition:
        raise BenignError(code)


def uint(value, maximum=(1 << 64) - 1):
    need(type(value) is int and 0 <= value <= maximum, 'uint')
    return value


def hexstr(value, length=64):
    need(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None,
         'hex')
    return value


def sha(data):
    need(type(data) is bytes, 'bytes')
    return hashlib.sha256(data).hexdigest()


def _shape(x, depth=0):
    need(depth <= 16, 'json_depth')
    t = type(x)
    if t is dict:
        need(len(x) <= 1024, 'json_fields')
        for k, v in x.items():
            need(type(k) is str, 'json_key_type')
            _shape(k, depth + 1); _shape(v, depth + 1)
    elif t is list:
        need(len(x) <= 1024, 'json_items')
        for v in x:
            _shape(v, depth + 1)
    elif t is str:
        need(len(x) <= 65536 and not any(0xd800 <= ord(c) <= 0xdfff for c in x), 'json_string')
    elif t is int:
        need(-(1 << 64) < x < (1 << 64), 'json_int_range')
    else:
        need(x is None or t is bool, 'json_type')


def canonical(value):
    _shape(value)
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')


POLICY_SHA = sha(canonical(POLICY))
SCHEMA_SHA = sha(canonical(WIRE))


def _pairs(pairs):
    obj = {}
    for k, v in pairs:
        need(k not in obj, 'duplicate_key')
        obj[k] = v
    return obj


def _integer(s):
    need(len(s.lstrip('-')) <= 20, 'integer_digits')
    return int(s)


def _reject_number(_s):
    raise BenignError('float_or_nonfinite')


def parse_json(raw, cap=262144):
    need(type(raw) is bytes and 0 < len(raw) <= cap, 'raw_size')
    need(raw.endswith(b'\n') and not raw.endswith(b'\n\n') and b'\r' not in raw, 'LF')
    # Pre-scan before entering the JSON decoder to bound its stack.
    depth = 0; quoted = False; escaped = False
    for c in raw:
        if quoted:
            if escaped:
                escaped = False
            elif c == 92:
                escaped = True
            elif c == 34:
                quoted = False
        elif c == 34:
            quoted = True
        elif c in (91, 123):
            depth += 1; need(depth <= 16, 'json_depth')
        elif c in (93, 125):
            depth -= 1; need(depth >= 0, 'json_balance')
    need(not quoted and not escaped and depth == 0, 'json_balance')
    try:
        obj = json.loads(raw.decode('ascii'), object_pairs_hook=_pairs,
                         parse_int=_integer, parse_float=_reject_number,
                         parse_constant=_reject_number)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise BenignError('json_syntax') from exc
    _shape(obj)
    need(canonical(obj) == raw, 'noncanonical')
    return obj


@dataclass(frozen=True)
class BenignDocument:
    kind: str
    raw: bytes

    @property
    def fields(self):
        # Return a new structure; no shared mutable parsed state.
        return parse_json(self.raw, CAPS[self.kind])

    @property
    def sha256(self):
        return sha(self.raw)


Completion = BenignDocument


def _exact_keys(obj, names):
    need(type(obj) is dict and set(obj) == set(names), 'exact_fields')


def _fields(kind, obj):
    need(kind in CAPS, 'message_kind')
    _exact_keys(obj, WIRE['message_fields'][kind])
    for k, v in COMMON.items():
        need(type(obj[k]) is type(v) and obj[k] == v, 'domain_or_version')
    need(obj['kind'] == kind, 'kind_mismatch')
    hexstr(obj['run_id'], 32); hexstr(obj['nonce'])
    for k, v in obj.items():
        if k.endswith('_sha256'):
            hexstr(v)
        if k == 'grant_id':
            hexstr(v, 32)
    if 'schema_sha256' in obj:
        need(obj['schema_sha256'] == SCHEMA_SHA, 'schema_pin')
    if 'policy_sha256' in obj:
        need(obj['policy_sha256'] == POLICY_SHA, 'policy_pin')
    if 'guard' in obj:
        need(obj['guard'] is None, 'guard_forbidden')
    if 'scenario' in obj:
        need(obj['scenario'] == 'fixed_digest_roundtrip', 'scenario')
    if 'scm_budget' in obj:
        _exact_keys(obj['scm_budget'], ZERO_BUDGET)
        for x in obj['scm_budget'].values():
            uint(x, 0)
    if kind == 'ready':
        hexstr(obj['public_key_blob_hex'], 144)
        # Geometry/header validation is additionally performed in crypto provider.
        _exact_keys(obj['guest_runtime'], RUNTIME_FLAGS)
        for k, v in RUNTIME_FLAGS.items():
            need(type(obj['guest_runtime'][k]) is type(v) and obj['guest_runtime'][k] == v,
                 'guest_runtime')
    if kind == 'journal_record':
        uint(obj['sequence'], 15); uint(obj['guest_monotonic_ns'])
        event = obj['event']
        need(type(event) is str and event in WIRE['journal_events'], 'journal_event')
        _exact_keys(obj['data'], WIRE['journal_events'][event])
        for k, v in obj['data'].items():
            if k.endswith('_sha256'):
                hexstr(v)
            elif k == 'result':
                need(v in ('BENIGN_TASK_COMPLETED', 'BENIGN_TASK_FAILED'), 'journal_result')
            else:
                need(type(v) is str and re.fullmatch('[A-Z0-9_]{1,96}', v), 'error_code')
    if kind == 'terminal':
        uint(obj['journal_bytes'], 65536); uint(obj['journal_records'], 16)
        need(obj['journal_records'] >= 3, 'journal_records')
        need(obj['result'] in ('BENIGN_TASK_COMPLETED', 'BENIGN_TASK_FAILED'), 'terminal_result')
    if kind == 'failure':
        need(type(obj['code']) is str and re.fullmatch('[A-Z0-9_]{1,96}', obj['code']), 'error_code')
        need(type(obj['message']) is str and len(obj['message']) <= 2048, 'error_message')


def parse_benign(kind, raw):
    need(type(kind) is str and kind in CAPS, 'message_kind')
    obj = parse_json(raw, CAPS[kind]); _fields(kind, obj)
    return BenignDocument(kind, raw)


def serialize_benign(kind, fields):
    raw = canonical(fields)
    parse_benign(kind, raw)
    return raw


def message(kind, run_id, nonce, **extra):
    obj = dict(COMMON, kind=kind, run_id=run_id, nonce=nonce)
    need(not set(extra).intersection(obj), 'constant_override')
    obj.update(extra)
    return serialize_benign(kind, obj)


def parse_completion(kind, raw):
    need(kind in ('ready_commit', 'authorization_commit', 'terminal_commit'), 'completion_kind')
    return parse_benign(kind, raw)


def bind(left, right, keys):
    for k in keys:
        need(k in left and k in right and type(left[k]) is type(right[k]) and left[k] == right[k],
             'binding:' + k)


def expected_response(request_raw):
    parse_benign('request', request_raw)
    return sha(ROUNDTRIP_DOMAIN + request_raw)
