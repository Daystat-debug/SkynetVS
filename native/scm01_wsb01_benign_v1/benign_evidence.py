"""Structural evidence is not authority. Live finalization requires sealed native receipts."""
from dataclasses import dataclass
from .benign_contract import (need, hexstr, sha, canonical, parse_benign, bind, message,
                              FILE_CAPS, SUCCESS_FILES, expected_response, READY_DOMAIN, TERMINAL_DOMAIN)
from .benign_windows_crypto import validate_public, validate_signature, is_native_receipt
from .benign_windows_session import is_native_retirement
from .benign_windows_fs import is_native_snapshot, is_native_materialization

PIN_KEYS = ('run_id', 'nonce', 'capsule_sha256', 'layout_sha256', 'policy_sha256',
            'runtime_sha256', 'schema_sha256', 'source_sha256', 'wsb_sha256')


@dataclass(frozen=True)
class ExpectedTranscript:
    request: bytes
    session_binding_sha256: str
    boot_binding: str
    materialization_sha256: str = ''

    def fields(self):
        hexstr(self.session_binding_sha256); hexstr(self.boot_binding)
        return parse_benign('request', self.request).fields


@dataclass(frozen=True)
class ReadyCandidate:
    expected: ExpectedTranscript
    raw: bytes
    signature: bytes
    completion: bytes
    key: bytes


@dataclass(frozen=True)
class TranscriptExpectation:
    ready: ReadyCandidate
    authorization: bytes
    authorization_commit: bytes


@dataclass(frozen=True)
class TerminalCandidate:
    result: str
    terminal: bytes
    signature: bytes
    journal: bytes
    snapshot_sha256: str
    completed: bool
    structural_only: bool = True


@dataclass(frozen=True)
class NativeReceipts:
    crypto: tuple
    retirement: object
    materialization: tuple


@dataclass(frozen=True)
class LabVerdict:
    result: str
    terminal_sha256: str
    evidence_domain: str = 'BENIGN_SANDBOX_LAB'
    retirement_basis: str = 'EXCLUSIVE_HOST_KNOWN_PROCESSSET_V1'
    hypervisor_disposal_proven: bool = False
    runtime_authorized: bool = False
    production_execution_authorized: bool = False
    real_scm: bool = False
    guard_executed: bool = False


def _scope(obj, request):
    bind(obj, request, ('run_id', 'nonce', 'experiment', 'profile', 'schema', 'evidence_domain', 'version'))


def snapshot_digest(raw):
    need(type(raw) is dict, 'snapshot_type')
    return sha(canonical([{'name': n, 'bytes': len(b), 'sha256': sha(b)} for n, b in sorted(raw.items())]))


def validate_ready(expected, raw):
    need(type(expected) is ExpectedTranscript and type(raw) is dict and
         set(raw) == {'ready.json', 'ready.sig', 'ready.commit.json'}, 'ready_snapshot')
    req = expected.fields(); r = parse_benign('ready', raw['ready.json']).fields
    m = parse_benign('ready_commit', raw['ready.commit.json']).fields
    bind(r, req, PIN_KEYS); _scope(m, req)
    need(r['request_sha256'] == sha(expected.request), 'ready_request')
    signature = validate_signature(raw['ready.sig'])
    key = validate_public(bytes.fromhex(r['public_key_blob_hex']))
    need(m['ready_sha256'] == sha(raw['ready.json']) and m['ready_signature_sha256'] == sha(signature),
         'ready_completion')
    return ReadyCandidate(expected, raw['ready.json'], signature, raw['ready.commit.json'], key)


def build_authorization(ready):
    need(type(ready) is ReadyCandidate, 'ready_pin_type')
    req = ready.expected.fields()
    auth = message('authorization', req['run_id'], req['nonce'], grant_id=req['grant_id'],
                   request_sha256=sha(ready.expected.request), ready_sha256=sha(ready.raw),
                   ready_signature_sha256=sha(ready.signature), public_key_sha256=sha(ready.key),
                   session_binding_sha256=ready.expected.session_binding_sha256,
                   scenario=req['scenario'], scm_budget=req['scm_budget'])
    marker = message('authorization_commit', req['run_id'], req['nonce'], authorization_sha256=sha(auth))
    return auth, marker


def validate_authorization(ready, auth_raw, marker_raw):
    wanted = build_authorization(ready)
    parse_benign('authorization', auth_raw); parse_benign('authorization_commit', marker_raw)
    need((auth_raw, marker_raw) == wanted, 'authorization_exact_pin')


def validate_terminal(expected, raw_snapshot):
    need(type(expected) is TranscriptExpectation, 'transcript_expectation')
    need(type(raw_snapshot) is dict and set(raw_snapshot) == set(SUCCESS_FILES), 'exact_output_inventory')
    for name, data in raw_snapshot.items():
        need(type(data) is bytes and 0 < len(data) <= FILE_CAPS[name], 'output_file_size')
    need(sum(len(b) for b in raw_snapshot.values()) <= 262144, 'output_total')
    ready = expected.ready; req = ready.expected.fields()
    pinned = validate_ready(ready.expected, {n: raw_snapshot[n] for n in ('ready.json', 'ready.sig', 'ready.commit.json')})
    need(pinned == ready, 'ready_changed_after_pin')
    validate_authorization(ready, expected.authorization, expected.authorization_commit)
    term = parse_benign('terminal', raw_snapshot['terminal.json']).fields
    bind(term, req, PIN_KEYS)
    bindings = {'request_sha256': sha(ready.expected.request), 'ready_sha256': sha(ready.raw),
                'public_key_sha256': sha(ready.key), 'authorization_sha256': sha(expected.authorization),
                'authorization_commit_sha256': sha(expected.authorization_commit),
                'session_binding_sha256': ready.expected.session_binding_sha256}
    for k, v in bindings.items():
        need(term[k] == v, 'terminal_binding:' + k)
    signature = validate_signature(raw_snapshot['terminal.sig'])
    commit = parse_benign('terminal_commit', raw_snapshot['terminal.commit.json']).fields
    _scope(commit, req)
    need(commit['terminal_sha256'] == sha(raw_snapshot['terminal.json']) and
         commit['terminal_signature_sha256'] == sha(signature), 'terminal_completion')
    journal = raw_snapshot['journal.jsonl']; lines = journal.splitlines(keepends=True)
    need(3 <= len(lines) <= 16 and len(journal) <= 65536, 'journal_limit')
    parsed = []
    for index, line in enumerate(lines):
        row = parse_benign('journal_record', line).fields; _scope(row, req)
        need(row['sequence'] == index, 'journal_sequence')
        if parsed:
            need(row['guest_monotonic_ns'] >= parsed[-1]['guest_monotonic_ns'], 'guest_clock_regression')
        parsed.append(row)
    events = [x['event'] for x in parsed]
    success = term['result'] == 'BENIGN_TASK_COMPLETED'
    if success:
        need(events == ['BEGIN', 'AUTHORIZATION_OBSERVED', 'BENIGN_COMPLETED', 'FINAL'], 'journal_order')
        need(term['response_sha256'] == expected_response(ready.expected.request), 'roundtrip_result')
    else:
        need(events in (['BEGIN', 'ERROR', 'FINAL'],
                        ['BEGIN', 'AUTHORIZATION_OBSERVED', 'ERROR', 'FINAL'],
                        ['BEGIN', 'AUTHORIZATION_OBSERVED', 'BENIGN_COMPLETED', 'ERROR', 'FINAL']),
             'failure_journal_shape')
    for row in parsed:
        if row['event'] == 'AUTHORIZATION_OBSERVED':
            need(row['data'] == {k: bindings[k] for k in ('authorization_sha256', 'authorization_commit_sha256')},
                 'journal_authorization')
        if row['event'] == 'BENIGN_COMPLETED':
            need(row['data']['response_sha256'] == expected_response(ready.expected.request), 'journal_result')
    need(parsed[-1]['data'] == {'result': term['result']}, 'final_result')
    need(term['journal_bytes'] == len(journal) and term['journal_records'] == len(lines) and
         term['journal_sha256'] == sha(journal) and commit['journal_sha256'] == sha(journal), 'journal_binding')
    return TerminalCandidate(term['result'], raw_snapshot['terminal.json'], signature, journal,
                             snapshot_digest(raw_snapshot), success)


def finalize_lab(expected, native_receipts, snapshots):
    """Pure verdict gate, not a grant issuer. Fake dictionaries/types never qualify."""
    need(type(native_receipts) is NativeReceipts and type(snapshots) is tuple and len(snapshots) == 2,
         'native_bundle')
    before, after = snapshots
    need(is_native_snapshot(before, 'before_retirement') and is_native_snapshot(after, 'after_retirement'),
         'native_snapshots_required')
    need(before.root_path.casefold() == after.root_path.casefold() and before.raw() == after.raw(),
         'postexit_snapshot_changed')
    candidate = validate_terminal(expected, after.raw()); need(candidate.completed, 'failure_terminal')
    ready = expected.ready; req = ready.expected.fields(); native = native_receipts
    need(is_native_retirement(native.retirement, req['run_id'], req['nonce'],
                              ready.expected.session_binding_sha256, ready.expected.boot_binding),
         'native_retirement_required')
    need(type(native.crypto) is tuple and len(native.crypto) == 4, 'four_crypto_checks')
    checks = ((READY_DOMAIN, ready.raw, ready.signature),
              (TERMINAL_DOMAIN, candidate.terminal, candidate.signature)) * 2
    for receipt, (domain, raw, sig) in zip(native.crypto, checks):
        need(is_native_receipt(receipt, domain, raw, ready.key, sig), 'native_crypto_required')
    need(type(native.materialization) is tuple and len(native.materialization) == 2,
         'materialization_receipts')
    hexstr(ready.expected.materialization_sha256)
    for r, phase in zip(native.materialization, ('before_retirement', 'after_retirement')):
        need(is_native_materialization(r, phase, ready.expected.materialization_sha256), 'static_pin_recheck')
    return LabVerdict('BENIGN_SANDBOX_TRANSPORT_PASS_LAB_ONLY', sha(candidate.terminal))
