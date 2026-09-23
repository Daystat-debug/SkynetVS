"""CONTRACT01-08; shared data-only fixtures. Signatures below are NOT real ECDSA."""
import json
import struct
import unittest
from dataclasses import replace
from .. import benign_contract as c
from .. import benign_evidence as e

RID = '1' * 32
NONCE = '2' * 64
GRANT = '3' * 32
BOOT = '4' * 64
SESSION = '5' * 64
KEY = struct.pack('<II', 0x31534345, 32) + bytes.fromhex(
    '6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296'
    '4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5')
SIG = (1).to_bytes(32, 'big') * 2


def request(run_id=RID, nonce=NONCE, grant=GRANT):
    return c.message('request', run_id, nonce, grant_id=grant, capsule_sha256='a' * 64,
                     layout_sha256='b' * 64, policy_sha256=c.POLICY_SHA, runtime_sha256='c' * 64,
                     schema_sha256=c.SCHEMA_SHA, scm_budget=dict(c.ZERO_BUDGET), source_sha256='d' * 64,
                     wsb_sha256='e' * 64, scenario='fixed_digest_roundtrip', guard=None)


def ready_fixture(expected=None):
    expected = expected or e.ExpectedTranscript(request(), SESSION, BOOT)
    req = expected.fields()
    pins = {k: req[k] for k in e.PIN_KEYS if k not in ('run_id', 'nonce')}
    raw = c.message('ready', req['run_id'], req['nonce'], **pins,
                    request_sha256=c.sha(expected.request), public_key_blob_hex=KEY.hex(),
                    guest_runtime=dict(c.RUNTIME_FLAGS))
    mark = c.message('ready_commit', req['run_id'], req['nonce'], ready_sha256=c.sha(raw),
                     ready_signature_sha256=c.sha(SIG))
    return expected, {'ready.json': raw, 'ready.sig': SIG, 'ready.commit.json': mark}


def full_fixture(expected=None, failure=False):
    expected, r = ready_fixture(expected)
    pin = e.validate_ready(expected, r)
    auth, ac = e.build_authorization(pin)
    exp = e.TranscriptExpectation(pin, auth, ac)
    req = expected.fields()
    rid, nonce = req['run_id'], req['nonce']
    response = c.expected_response(expected.request)
    events = [('BEGIN', {}), ('AUTHORIZATION_OBSERVED', {
        'authorization_sha256': c.sha(auth), 'authorization_commit_sha256': c.sha(ac)})]
    if failure:
        events += [('ERROR', {'code': 'TEST_FAILURE'}), ('FINAL', {'result': 'BENIGN_TASK_FAILED'})]
    else:
        events += [('BENIGN_COMPLETED', {'response_sha256': response}),
                   ('FINAL', {'result': 'BENIGN_TASK_COMPLETED'})]
    journal = b''.join(c.message('journal_record', rid, nonce, sequence=i,
        guest_monotonic_ns=10 + i, event=event, data=data) for i, (event, data) in enumerate(events))
    pins = {k: req[k] for k in e.PIN_KEYS if k not in ('run_id', 'nonce')}
    term = c.message('terminal', rid, nonce, **pins, authorization_commit_sha256=c.sha(ac),
        authorization_sha256=c.sha(auth), journal_bytes=len(journal), journal_records=len(events),
        journal_sha256=c.sha(journal), public_key_sha256=c.sha(KEY), ready_sha256=c.sha(r['ready.json']),
        request_sha256=c.sha(expected.request), response_sha256=response,
        result='BENIGN_TASK_FAILED' if failure else 'BENIGN_TASK_COMPLETED',
        session_binding_sha256=expected.session_binding_sha256)
    tm = c.message('terminal_commit', rid, nonce, journal_sha256=c.sha(journal),
                   terminal_sha256=c.sha(term), terminal_signature_sha256=c.sha(SIG))
    return exp, dict(r, **{'journal.jsonl': journal, 'terminal.json': term,
                          'terminal.sig': SIG, 'terminal.commit.json': tm})


def rewrite(raw, key, value):
    fields = c.parse_json(raw)
    fields[key] = value
    return c.canonical(fields)


def refresh_terminal_mark(raw):
    t = c.parse_benign('terminal', raw['terminal.json']).fields
    raw['terminal.commit.json'] = c.message('terminal_commit', t['run_id'], t['nonce'],
         journal_sha256=t['journal_sha256'], terminal_sha256=c.sha(raw['terminal.json']),
         terminal_signature_sha256=c.sha(raw['terminal.sig']))
    return raw


class ContractTests(unittest.TestCase):
    def test_CONTRACT01_canonical_roundtrip(self):
        raw = request()
        self.assertEqual(c.serialize_benign('request', c.parse_benign('request', raw).fields), raw)
        self.assertEqual(c.canonical({'b': [1, True], 'a': '\u044f'}), b'{"a":"\\u044f","b":[1,true]}\n')
        with self.assertRaises(c.BenignError): c.parse_json(b'[' * 17 + b']' * 17 + b'\n')

    def test_CONTRACT02_malformed_numbers_keys(self):
        for raw in (b'{"a":1,"a":1}\n', b'{"a":1.0}\n', b'{"a":NaN}\n',
                    b'{}\r\n', b'{}\n\n', b'\xef\xbb\xbf{}\n', b'{"a":18446744073709551616}\n'):
            with self.subTest(raw=raw), self.assertRaises(c.BenignError): c.parse_json(raw)
        with self.assertRaises(c.BenignError): c.parse_benign('request', rewrite(request(), 'version', True))

    def test_CONTRACT03_cross_domain_rejected(self):
        for field, value in (('evidence_domain', 'OFFLINE_MODEL'), ('experiment', 'SCM01'),
                             ('schema', 'SKYNETVS_SCM01_WSB01_CLOSED_CORE_V1')):
            with self.subTest(field=field), self.assertRaises(c.BenignError):
                c.parse_benign('request', rewrite(request(), field, value))

    def test_CONTRACT04_scope_cannot_carry_commands(self):
        for key, value in (('command', 'x'), ('guard', {'path': 'x'}), ('scenario', 'other'),
                           ('scm_budget', dict(c.ZERO_BUDGET, create=1))):
            with self.subTest(key=key), self.assertRaises(c.BenignError):
                c.parse_benign('request', rewrite(request(), key, value))

    def test_CONTRACT05_ready_pins(self):
        expected, raw = ready_fixture(); self.assertEqual(e.validate_ready(expected, raw).key, KEY)
        for key in ('runtime_sha256', 'request_sha256', 'nonce', 'source_sha256'):
            broken = dict(raw); broken['ready.json'] = rewrite(raw['ready.json'], key, 'f' * 64)
            with self.subTest(key=key), self.assertRaises(c.BenignError): e.validate_ready(expected, broken)

    def test_CONTRACT06_authorization_binding(self):
        exp, _ = full_fixture()
        e.validate_authorization(exp.ready, exp.authorization, exp.authorization_commit)
        for field in ('session_binding_sha256', 'public_key_sha256', 'ready_signature_sha256'):
            broken = rewrite(exp.authorization, field, 'f' * 64)
            with self.subTest(field=field), self.assertRaises(c.BenignError):
                e.validate_authorization(exp.ready, broken, exp.authorization_commit)

    def test_CONTRACT07_completion_not_boolean_permission(self):
        expected, raw = ready_fixture()
        with self.assertRaises(c.BenignError):
            c.parse_completion('ready_commit', b'a' * 64)
        raw['ready.commit.json'] = rewrite(raw['ready.commit.json'], 'ready_sha256', 'f' * 64)
        with self.assertRaises(c.BenignError): e.validate_ready(expected, raw)
        with self.assertRaises(c.BenignError): c.parse_benign('authorization', b'{"approved":true}\n')

    def test_CONTRACT08_hash_graph_acyclic(self):
        self.assertNotIn('policy_sha256', c.POLICY)
        self.assertNotIn('schema_sha256', c.WIRE)
        a = request(); b = request(nonce='9' * 64)
        self.assertNotEqual(c.expected_response(a), c.expected_response(b))
        self.assertEqual(c.POLICY_SHA, c.sha(c.canonical(c.POLICY)))
        self.assertEqual(c.SCHEMA_SHA, c.sha(c.canonical(c.WIRE)))
